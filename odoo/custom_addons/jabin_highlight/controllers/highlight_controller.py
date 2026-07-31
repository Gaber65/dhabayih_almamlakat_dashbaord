# addons/jabin_highlight/controllers/highlight_controller.py

from __future__ import annotations

from typing import Dict, Any, Optional

from odoo import _, http
from odoo.http import request
from odoo.exceptions import AccessError, MissingError, ValidationError

from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder, JabinLogger
from odoo.addons.jabin_security.utils.token_auth import require_token
from odoo.addons.jabin_security.decorators.permission_required import permission_required

_logger = JabinLogger.get("highlight.controller")


class HighlightController(BaseApiController):
    """REST controller for the Highlights (Stories) feature.

    All routes require a valid JWT ``Authorization: Bearer <token>`` header
    enforced by the ``require_token()`` decorator.

    The controller is intentionally thin:
    * Parse the request (headers, files, path params, JSON body).
    * Resolve the authenticated user_id from SecurityContext.
    * Delegate all business logic to ``jabin.highlight.service``.
    * Build and return the HTTP response via ResponseBuilder.

    Route         Method  Auth           Description
    ------------- ------  -------------- -----------
    /api/v1/highlights      POST    JWT required  Upload a new highlight
    /api/v1/highlights      GET     JWT required  Get highlights feed (all users)
    /api/v1/highlights/<id> GET     JWT required  Get a specific user's highlights
    /api/v1/highlights/<id> DELETE  JWT required  Delete a highlight
    """

    @staticmethod
    def _service():
        """Shorthand for the highlight service via sudo."""
        return request.env["jabin.highlight.service"].sudo()

    @staticmethod
    def _current_user_id() -> Optional[int]:
        """Resolve the authenticated user's ID from the security context.

        require_token() has already validated the JWT and populated
        SecurityContext before the controller method runs.
        Returns None if called outside an authenticated context.
        """
        try:
            from odoo.addons.jabin_security import SecurityContext
            ctx = SecurityContext.get()
            return ctx.user_id if ctx and ctx.is_authenticated else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # POST /api/v1/highlights — Create a highlight
    # ------------------------------------------------------------------

    @http.route(
        "/api/v1/highlights",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    @permission_required("highlights.manage")
    def create_highlight(self):
        """Upload a new highlight (image or video).

        Expected: ``multipart/form-data`` with fields:
        * ``media``       — The file (required).
        * ``media_type``  — ``'image'`` or ``'video'`` (required).

        Returns:
            201 Created + serialised highlight data.
        """
        # Require authentication for data modification
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            user_id = self._current_user_id()
            if not user_id:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=_("Authentication required."),
                        code=401,
                    )
                )
                return ctx.response

            media_type = request.httprequest.form.get("media_type", "")
            file_storage = request.httprequest.files.get("media")

            highlight_data = self._service().create_highlight(
                user_id=user_id,
                media_type=media_type,
                file_storage=file_storage,
            )

            ctx.set_body(
                ResponseBuilder.success(
                    data=highlight_data,
                    message=_("Highlight created successfully."),
                    code=201,
                )
            )

        return ctx.response

    # ------------------------------------------------------------------
    # GET /api/v1/highlights — Feed (all users, grouped)
    # ------------------------------------------------------------------

    @http.route(
        "/api/v1/highlights",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_feed(self):
        """Return all active highlights grouped by user.

        Groups are ordered newest-user-first (Instagram/WhatsApp style).
        Within each group, highlights are oldest → newest.

        Returns:
            200 + list of ``{"user": {...}, "highlights": [...]}``
        """
        with self.handle() as ctx:
            feed = self._service().get_feed()

            ctx.set_body(
                ResponseBuilder.success(
                    data=feed,
                    message=_("Highlights feed retrieved successfully."),
                )
            )

        return ctx.response

    # ------------------------------------------------------------------
    # GET /api/v1/highlights/<user_id> — Single user's highlights
    # ------------------------------------------------------------------

    @http.route(
        "/api/v1/highlights/<int:user_id>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_user_highlights(self, user_id: int):
        """Return active highlights for a specific user (oldest → newest).

        Args:
            user_id: The target user's database ID (path parameter).

        Returns:
            200 + list of serialised highlight dicts.
            404 if the user does not exist.
        """
        # Require authentication
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            requesting_user_id = self._current_user_id()
            if not requesting_user_id:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=_("Authentication required."),
                        code=401,
                    )
                )
                return ctx.response

            highlights = self._service().get_user_highlights(user_id)

            ctx.set_body(
                ResponseBuilder.success(
                    data=highlights,
                    message=_("Highlights for user %(user_id)s retrieved successfully.") % {
                        'user_id': user_id
                    },
                )
            )

        return ctx.response

    # ------------------------------------------------------------------
    # DELETE /api/v1/highlights/<highlight_id>
    # ------------------------------------------------------------------

    @http.route(
        "/api/v1/highlights/<int:highlight_id>",
        type="http",
        auth="public",
        methods=["DELETE"],
        csrf=False,
    )
    @permission_required("highlights.manage")
    def delete_highlight(self, highlight_id: int):
        """Delete a highlight by ID.

        * Owner can delete their own highlights.
        * Odoo Administrators can delete any highlight.

        Args:
            highlight_id: ID of the highlight to delete (path parameter).

        Returns:
            200 on success.
            403 if the caller is not the owner or an admin.
            404 if the highlight does not exist.
        """
        # Require authentication for data modification
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            user_id = self._current_user_id()
            if not user_id:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=_("Authentication required."),
                        code=401,
                    )
                )
                return ctx.response

            self._service().delete_highlight(
                highlight_id=highlight_id,
                requesting_user_id=user_id,
            )

            ctx.set_body(
                ResponseBuilder.success(
                    message=_("Highlight deleted successfully."),
                )
            )

        return ctx.response