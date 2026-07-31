# addons/jabin_highlight/models/highlight.py

from __future__ import annotations

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.addons.jabin_core import JabinLogger

_logger = JabinLogger.get("highlight.model")

# System parameter key for expiration hours (default: 24)
_EXPIRY_PARAM = "jabin.highlight.expiration_hours"
_EXPIRY_DEFAULT = 24

# Allowed media types
MEDIA_TYPE_IMAGE = "image"
MEDIA_TYPE_VIDEO = "video"


class JabinHighlight(models.Model):
    """Temporary media post (Story / Highlight).

    A highlight is a short-lived image or video published by a user.
    It automatically expires ``jabin.highlight.expiration_hours`` hours after
    creation (default 24 h). Only active, non-expired highlights are served
    through the API.

    Design notes
    ------------
    * ``expires_at`` is set once on creation and never changes.
    * ``is_active`` is a non-stored computed field so it always reflects the
      current clock — no cron job is needed to toggle it.
    * The scheduled cleanup cron deletes expired records to reclaim storage.
    * ``active`` is the standard Odoo archive flag; archiving a highlight
      immediately hides it from the API regardless of expiration.
    * ``state`` is a computed field that provides human-readable status.

    Extensibility
    -------------
    Fields such as ``viewers_ids``, ``reactions_ids``, ``privacy``,
    ``mentions_ids``, and ``is_archived`` can be added in future sprints
    without changing this base model.
    """

    _name = "jabin.highlight"
    _description = "JABIN Highlight (Story)"
    _inherit = ["jabin.timestamp.mixin"]
    _order = "create_date asc"
    _rec_name = "name"

    # ------------------------------------------------------------------
    # Basic fields
    # ------------------------------------------------------------------

    name = fields.Char(
        string="Name",
        readonly=True,
        help="Auto-generated display name for the highlight.",
        copy=False,
    )

    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Owner",
        required=True,
        ondelete="restrict",
        index=True,
        help="User who published this highlight.",
    )

    media_type = fields.Selection(
        selection=[
            (MEDIA_TYPE_IMAGE, "Image"),
            (MEDIA_TYPE_VIDEO, "Video"),
        ],
        string="Media Type",
        required=True,
        index=True,
    )

    color = fields.Integer(
        string="Color Index",
        default=0,
        help="Color for kanban view",
    )

    # ------------------------------------------------------------------
    # Media fields (using fields.Image and fields.Binary)
    # ------------------------------------------------------------------

    image = fields.Image(
        string="Image",
        max_width=1920,
        max_height=1920,
        help="The uploaded image file. Max dimensions: 1920x1920.",
    )

    video = fields.Binary(
        string="Video",
        attachment=True,
        help="The uploaded video file.",
    )

    media_filename = fields.Char(
        string="Media Filename",
        help="Original filename of the uploaded media.",
    )

    media_mimetype = fields.Char(
        string="Media MIME Type",
        help="MIME type of the uploaded media.",
    )

    # ------------------------------------------------------------------
    # Expiration
    # ------------------------------------------------------------------

    expires_at = fields.Datetime(
        string="Expires At",
        readonly=True,
        index=True,
        help="Timestamp after which this highlight is no longer visible.",
        copy=False,
    )

    is_active = fields.Boolean(
        string="Active",
        compute="_compute_is_active",
        store=False,
        help="True when the highlight has not yet expired and is not archived.",
    )

    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("active", "Active"),
            ("expired", "Expired"),
            ("archived", "Archived"),
        ],
        string="Status",
        compute="_compute_state",
        store=False,
        help="Human-readable status of the highlight.",
    )

    # ------------------------------------------------------------------
    # Engagement
    # ------------------------------------------------------------------

    views_count = fields.Integer(
        string="Views",
        default=0,
        readonly=True,
        help="Number of times this highlight has been viewed.",
        copy=False,
    )

    # ------------------------------------------------------------------
    # Standard Odoo archive flag
    # ------------------------------------------------------------------

    active = fields.Boolean(
        string="Visible",
        default=True,
        index=True,
        help="Uncheck to immediately hide this highlight from the API (archive).",
    )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains('media_type', 'image', 'video')
    def _check_media_content(self):
        """Ensure that the correct media field is populated based on media_type."""
        for rec in self:
            if rec.media_type == MEDIA_TYPE_IMAGE and not rec.image:
                raise ValidationError(_("Image field is required for image highlights."))
            if rec.media_type == MEDIA_TYPE_VIDEO and not rec.video:
                raise ValidationError(_("Video field is required for video highlights."))
            if rec.media_type == MEDIA_TYPE_IMAGE and rec.video:
                raise ValidationError(_("Video field should be empty for image highlights."))
            if rec.media_type == MEDIA_TYPE_VIDEO and rec.image:
                raise ValidationError(_("Image field should be empty for video highlights."))

    # ------------------------------------------------------------------
    # Computed fields
    # ------------------------------------------------------------------

    @api.depends("expires_at", "active")
    def _compute_is_active(self):
        """Highlight is active when not archived AND not yet expired."""
        now = fields.Datetime.now()
        for rec in self:
            rec.is_active = (
                    rec.active
                    and bool(rec.expires_at)
                    and rec.expires_at > now
            )

    @api.depends("expires_at", "active", "is_active")
    def _compute_state(self):
        """Compute human-readable state."""
        now = fields.Datetime.now()
        for rec in self:
            if not rec.active:
                rec.state = "archived"
            elif not rec.expires_at:
                rec.state = "draft"
            elif rec.expires_at > now:
                rec.state = "active"
            else:
                rec.state = "expired"

    # ------------------------------------------------------------------
    # Lifecycle overrides
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        """Set ``name`` and ``expires_at`` automatically on creation."""
        expiry_hours = self._get_expiration_hours()

        for vals in vals_list:
            # Generate a readable name if not provided
            if not vals.get("name"):
                user_id = vals.get("user_id")
                media_type = vals.get("media_type", "highlight")
                vals["name"] = f"{media_type.capitalize()} highlight – user #{user_id}"

            # expires_at must be set now; create_date is populated by Odoo
            # after super().create(), so we use fields.Datetime.now() as the
            # creation baseline.
            if not vals.get("expires_at"):
                vals["expires_at"] = fields.Datetime.now() + timedelta(
                    hours=expiry_hours
                )

        records = super().create(vals_list)

        for rec in records:
            _logger.audit(
                "HIGHLIGHT_CREATED | id=%s | user_id=%s | media_type=%s | expires_at=%s",
                rec.id,
                rec.user_id.id,
                rec.media_type,
                rec.expires_at,
            )

        return records

    def write(self, vals):
        """Track state changes for auditing."""
        result = super().write(vals)

        if "active" in vals:
            for rec in self:
                if vals["active"]:
                    _logger.audit(
                        "HIGHLIGHT_RESTORED | id=%s | user_id=%s",
                        rec.id,
                        rec.user_id.id,
                    )
                else:
                    _logger.audit(
                        "HIGHLIGHT_ARCHIVED | id=%s | user_id=%s",
                        rec.id,
                        rec.user_id.id,
                    )

        return result

    def unlink(self):
        """Audit deletion before removing."""
        for rec in self:
            _logger.audit(
                "HIGHLIGHT_DELETED_PERMANENTLY | id=%s | user_id=%s",
                rec.id,
                rec.user_id.id,
            )
        return super().unlink()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_view_media(self):
        """Return window action to view the media."""
        self.ensure_one()
        if self.media_type == MEDIA_TYPE_IMAGE and self.image:
            return {
                "type": "ir.actions.act_url",
                "name": _("View Image"),
                "target": "new",
                "url": f"/web/image/jabin.highlight/{self.id}/image?unique={self.write_date.timestamp() if self.write_date else ''}",
            }
        elif self.media_type == MEDIA_TYPE_VIDEO and self.video:
            return {
                "type": "ir.actions.act_url",
                "name": _("View Video"),
                "target": "new",
                "url": f"/web/content/jabin.highlight/{self.id}/video?unique={self.write_date.timestamp() if self.write_date else ''}",
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("No Media"),
            "res_model": "jabin.highlight",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_copy_highlight(self):
        """Create a copy of this highlight."""
        self.ensure_one()
        new_highlight = self.copy({
            "name": f"Copy of {self.name}",
            "views_count": 0,
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "jabin.highlight",
            "res_id": new_highlight.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_archive(self):
        """Archive the highlight."""
        self.write({"active": False})

    def action_restore(self):
        """Restore the highlight."""
        self.write({"active": True})

    @api.model
    def action_open_highlights(self):
        """Open the highlights view."""
        return {
            "type": "ir.actions.act_window",
            "res_model": "jabin.highlight",
            "view_mode": "tree,kanban,form",
            "context": {"active_test": False},
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @api.model
    def _get_expiration_hours(self) -> int:
        """Read expiration window from system parameters."""
        raw = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(_EXPIRY_PARAM, default=str(_EXPIRY_DEFAULT))
        )
        try:
            hours = int(raw)
            return hours if hours > 0 else _EXPIRY_DEFAULT
        except (ValueError, TypeError):
            return _EXPIRY_DEFAULT

    def to_dict(self) -> dict:
        """Serialise a single highlight for API responses.

        Returns a safe, JSON-serialisable dict. Sensitive fields (raw
        binary data) are never included — only the download URL is exposed.
        """
        self.ensure_one()

        # Build the media URL based on type
        if self.media_type == MEDIA_TYPE_IMAGE and self.image:
            media_url = f"api/v1/image/jabin.highlight/{self.id}/image"
        elif self.media_type == MEDIA_TYPE_VIDEO and self.video:
            media_url = f"api/v1/image/jabin.highlight/{self.id}/video"
        else:
            media_url = None

        return {
            "id": self.id,
            "name": self.name,
            "media_type": self.media_type,
            "media_url": media_url,
            "media_filename": self.media_filename,
            "media_mimetype": self.media_mimetype,
            "views_count": self.views_count,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.create_date.isoformat() if self.create_date else None,
            "is_active": self.is_active,
            "state": self.state,
        }

    @api.model
    def _get_highlight_stats(self, user_id=None):
        """Get statistics for highlights."""
        domain = []
        if user_id:
            domain.append(("user_id", "=", user_id))

        total = self.search_count(domain)
        active = self.search_count(domain + [("active", "=", True)])
        expired = self.search_count(domain + [("expires_at", "<=", fields.Datetime.now())])

        return {
            "total": total,
            "active": active,
            "expired": expired,
            "archived": total - active,
        }