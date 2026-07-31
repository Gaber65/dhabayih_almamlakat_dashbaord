# addons/jabin_highlight/services/highlight_service.py

from __future__ import annotations

import base64
from datetime import timedelta
from typing import Any, Dict, List, Optional

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, MissingError, ValidationError

from odoo.addons.jabin_core import JabinLogger
from odoo.addons.jabin_highlight.validators import HighlightValidator

_logger = JabinLogger.get("highlight.service")

# System parameter keys
_PARAM_EXPIRY_HOURS = "jabin.highlight.expiration_hours"
_PARAM_MAX_IMAGE_MB = "jabin.highlight.max_image_size_mb"
_PARAM_MAX_VIDEO_MB = "jabin.highlight.max_video_size_mb"

# Defaults
_DEFAULT_EXPIRY_HOURS = 24
_DEFAULT_IMAGE_MB = 10
_DEFAULT_VIDEO_MB = 100


class HighlightService(models.AbstractModel):
    """Business logic layer for the Highlights (Stories) feature.

    Responsibilities
    ----------------
    * Validate incoming request data (delegating field checks to
      :class:`~jabin_highlight.validators.HighlightValidator`).
    * Store uploaded media directly in the model fields.
    * Enforce access rules (owner-or-admin for delete).
    * Provide the feed query with correct ordering.
    * Run the scheduled cleanup of expired records.

    All methods are decorated with ``@api.model`` and called via
    ``request.env['jabin.highlight.service'].sudo()`` from the controller.
    ``sudo()`` is required because highlights are uploaded by public-auth
    routes backed by JWT.
    """

    _name = "jabin.highlight.service"
    _description = "JABIN Highlight Service"

    # ==================================================================
    # Public API
    # ==================================================================

    @api.model
    def create_highlight(
        self,
        user_id: int,
        media_type: str,
        file_storage,
    ) -> Dict[str, Any]:
        """Store a new highlight with the uploaded media file.

        Args:
            user_id:      Authenticated user's database ID.
            media_type:   ``'image'`` or ``'video'``.
            file_storage: Werkzeug ``FileStorage`` from
                          ``request.httprequest.files['media']``.

        Returns:
            Serialised highlight dict.

        Raises:
            :class:`~odoo.exceptions.ValidationError`: On invalid input.
        """
        # -- validate user ------------------------------------------------
        user = self.env["res.users"].browse(user_id)
        if not user.exists():
            raise ValidationError(_("Authenticated user not found."))
        if hasattr(user, "status") and user.status not in ("active",):
            raise ValidationError(_("Only active users can create highlights."))

        # -- validate payload via HighlightValidator ----------------------
        max_image_mb = self._get_param_int(_PARAM_MAX_IMAGE_MB, _DEFAULT_IMAGE_MB)
        max_video_mb = self._get_param_int(_PARAM_MAX_VIDEO_MB, _DEFAULT_VIDEO_MB)

        HighlightValidator.validate_create(
            media_type,
            file_storage,
            max_image_mb=max_image_mb,
            max_video_mb=max_video_mb,
        )

        media_type = media_type.lower().strip()

        # -- read file data -----------------------------------------------
        file_bytes = file_storage.read()
        encoded = base64.b64encode(file_bytes).decode("ascii")
        filename = file_storage.filename or f"highlight_{media_type}_{user_id}"
        mimetype = file_storage.mimetype or (
            "image/jpeg" if media_type == "image" else "video/mp4"
        )

        # -- create the highlight record with direct media storage --------
        create_vals = {
            "user_id": user_id,
            "media_type": media_type,
            "media_filename": filename,
            "media_mimetype": mimetype,
        }

        # Store media in the appropriate field
        if media_type == "image":
            create_vals["image"] = encoded
        else:  # video
            create_vals["video"] = encoded

        highlight = self.env["jabin.highlight"].create(create_vals)

        _logger.audit(
            "HIGHLIGHT_CREATED | id=%s | user_id=%s | media_type=%s | filename=%s",
            highlight.id,
            user_id,
            media_type,
            filename,
        )

        return highlight.to_dict()

    @api.model
    def get_feed(self) -> List[Dict[str, Any]]:
        """Return all active highlights grouped by user.

        Ordering
        --------
        * Groups are sorted by the most recent highlight ``create_date``
          within each user's set (newest-user-first, à la Instagram/WhatsApp).
        * Within each group, highlights are ordered oldest → newest.

        Returns:
            List of ``{"user": {...}, "highlights": [...]}`` dicts.
        """
        now = fields.Datetime.now()

        # Fetch all active highlights ordered by user's latest create_date desc,
        # then by individual highlight create_date asc (within each user).
        # We compute this ordering in Python after a single ORM query.
        highlights = self.env["jabin.highlight"].search(
            [
                ("active", "=", True),
                ("expires_at", ">", now),
            ],
            order="create_date asc",
        )

        if not highlights:
            return []

        # Group by user_id, track the latest create_date per user for ordering
        user_groups: Dict[int, Dict[str, Any]] = {}
        user_latest: Dict[int, Any] = {}  # user_id -> latest create_date

        for h in highlights:
            uid = h.user_id.id
            if uid not in user_groups:
                user_groups[uid] = {
                    "user": self._user_to_dict(h.user_id),
                    "highlights": [],
                }
                user_latest[uid] = h.create_date
            user_groups[uid]["highlights"].append(h.to_dict())
            if h.create_date and (
                user_latest[uid] is None or h.create_date > user_latest[uid]
            ):
                user_latest[uid] = h.create_date

        # Sort groups: user with the most recent highlight first
        sorted_uids = sorted(
            user_groups.keys(),
            key=lambda uid: user_latest.get(uid) or fields.Datetime.now(),
            reverse=True,
        )

        return [user_groups[uid] for uid in sorted_uids]

    @api.model
    def get_user_highlights(self, user_id: int) -> List[Dict[str, Any]]:
        """Return active highlights for a specific user (oldest → newest).

        Args:
            user_id: The target user's database ID.

        Returns:
            List of serialised highlight dicts.

        Raises:
            :class:`~odoo.exceptions.MissingError`: If the user does not exist.
        """
        user = self.env["res.users"].browse(user_id)
        if not user.exists():
            raise MissingError(_("User not found."))

        now = fields.Datetime.now()
        highlights = self.env["jabin.highlight"].search(
            [
                ("user_id", "=", user_id),
                ("active", "=", True),
                ("expires_at", ">", now),
            ],
            order="create_date asc",
        )
        return [h.to_dict() for h in highlights]

    @api.model
    def delete_highlight(
        self,
        highlight_id: int,
        requesting_user_id: int,
    ) -> bool:
        """Delete a highlight.

        Access rules
        ------------
        * The owner can delete their own highlights.
        * A user with ``base.group_system`` (Odoo Administrator) can delete
          any highlight.

        Args:
            highlight_id:        ID of the ``jabin.highlight`` record to delete.
            requesting_user_id:  ID of the authenticated user making the request.

        Returns:
            True on success.

        Raises:
            :class:`~odoo.exceptions.MissingError`:  Highlight not found.
            :class:`~odoo.exceptions.AccessError`:   Caller is not the owner or admin.
            :class:`~odoo.exceptions.ValidationError`: Unexpected delete error.
        """
        highlight = self.env["jabin.highlight"].browse(highlight_id)
        if not highlight.exists():
            _logger.warning(
                "HIGHLIGHT_DELETE_FAILED | reason=not_found | id=%s | requester=%s",
                highlight_id,
                requesting_user_id,
            )
            raise MissingError(_("Highlight not found."))

        requesting_user = self.env["res.users"].browse(requesting_user_id)

        # Authorise: owner OR Odoo admin
        is_owner = highlight.user_id.id == requesting_user_id
        is_admin = requesting_user.has_group("base.group_system")

        if not is_owner and not is_admin:
            _logger.warning(
                "HIGHLIGHT_DELETE_DENIED | id=%s | requester=%s | owner=%s",
                highlight_id,
                requesting_user_id,
                highlight.user_id.id,
            )
            raise AccessError(
                _("You do not have permission to delete this highlight.")
            )

        owner_id = highlight.user_id.id

        try:
            highlight.unlink()
        except Exception as exc:
            _logger.error(
                "HIGHLIGHT_DELETE_FAILED | id=%s | error=%s",
                highlight_id,
                exc,
            )
            raise ValidationError(_("Failed to delete highlight. Please try again."))

        _logger.audit(
            "HIGHLIGHT_DELETED | id=%s | owner_id=%s | requester=%s | by_admin=%s",
            highlight_id,
            owner_id,
            requesting_user_id,
            is_admin,
        )

        return True

    @api.model
    def cleanup_expired_highlights(self) -> Dict[str, int]:
        """Delete all expired highlights.

        Called by the scheduled cron job every hour.

        Returns:
            dict with keys ``deleted_highlights``.
        """
        now = fields.Datetime.now()
        expired = self.env["jabin.highlight"].search(
            [("expires_at", "<=", now)],
            order="id asc",
        )

        total = len(expired)
        if total == 0:
            _logger.info("HIGHLIGHT_CLEANUP | no expired highlights found")
            return {"deleted_highlights": 0}

        _logger.info(
            "HIGHLIGHT_CLEANUP_START | count=%s | cutoff=%s",
            total,
            now.isoformat(),
        )

        try:
            expired.unlink()
        except Exception as exc:
            _logger.error("HIGHLIGHT_CLEANUP_FAILED | reason=%s", exc)
            raise

        _logger.audit(
            "HIGHLIGHT_CLEANUP_DONE | deleted=%s",
            total,
        )

        return {"deleted_highlights": total}

    # ==================================================================
    # Private helpers
    # ==================================================================

    def _user_to_dict(self, user) -> Dict[str, Any]:
        """Serialise a res.users record for the feed response."""
        partner_id = user.partner_id.id if user.partner_id else user.id
        avatar_url = f"api/v1/image/res.partner/{partner_id}/image_128"
        return {
            "id": user.id,
            "name": user.name,
            "email": user.login,
            "avatar_url": avatar_url,
        }

    def _get_param_int(self, key: str, default: int) -> int:
        """Read an integer system parameter with a safe fallback."""
        raw = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(key, default=str(default))
        )
        try:
            value = int(raw)
            return value if value > 0 else default
        except (ValueError, TypeError):
            return default