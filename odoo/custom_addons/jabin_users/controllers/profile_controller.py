import base64
import json
from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError
from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder
from odoo.addons.jabin_security.utils.token_auth import require_token
from odoo.addons.jabin_security import SecurityContext


def _get_auth_user_id() -> int:
    try:
        raw_header = request.httprequest.headers.get("Authorization", "")
        if raw_header:
            parts = raw_header.split(None, 1)
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                token = parts[1].strip()
                from odoo.addons.jabin_security.utils.jwt_utils import JWTUtils
                claims = JWTUtils.decode_token(token)
                uid = JWTUtils.get_user_id(claims)
                if uid:
                    return uid
    except Exception:
        pass
    return request.env.user.id


def _parse_request_data():
    content_type = request.httprequest.content_type or ""
    if "multipart/form-data" in content_type:
        vals = {k: v for k, v in request.httprequest.form.items()}
        uploaded = request.httprequest.files.get("avatar") or request.httprequest.files.get("image")
        if uploaded:
            raw = uploaded.read()
            if raw:
                vals["avatar"] = base64.b64encode(raw).decode("utf-8")
        return vals
    else:
        raw = request.httprequest.data
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise ValidationError(_("Invalid JSON payload."))


class ProfileController(BaseApiController):
    """Customer Profile REST API Controller."""

    @http.route(
        "/api/v1/me",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_profile(self, **kwargs):
        """Get customer profile."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id()
        with self.handle() as ctx:
            user = request.env["res.users"].sudo().browse(user_id)
            if not user.exists():
                raise ValidationError(_("User profile not found."))

            default_addr = request.env["res.users.address"].sudo().search([("user_id", "=", user.id), ("is_default", "=", True)], limit=1)
            if not default_addr:
                default_addr = request.env["res.users.address"].sudo().search([("user_id", "=", user.id)], limit=1)

            partner_id = user.partner_id.id if user.partner_id else user.id
            avatar_url = self.build_image_url("res.partner", partner_id, "image_1920")

            ctx.set_body(ResponseBuilder.success(data={
                "id": user.id,
                "name": user.name,
                "email": user.email or user.login,
                "phone": user.phone or getattr(user, "recipient_phone", None),
                "avatar": avatar_url,
                "avatar_url": avatar_url,
                "user_type": user.user_type if hasattr(user, "user_type") else "customer",
                "status": user.status if hasattr(user, "status") else "active",
                "preferred_language": getattr(user, "preferred_language", "ar"),
                "preferred_theme": getattr(user, "preferred_theme", "light"),
                "push_notifications_enabled": getattr(user, "push_notifications_enabled", True),
                "loyalty_points": getattr(user, "loyalty_points", 0),
                "default_address": {
                    "id": default_addr.id,
                    "title": default_addr.title,
                    "city": default_addr.city,
                    "street": default_addr.street,
                } if default_addr else None,
            }, message=_("Profile retrieved successfully.")))
        return ctx.response

    @http.route(
        "/api/v1/me",
        type="http",
        auth="public",
        methods=["PUT"],
        csrf=False,
    )
    def update_profile(self, **kwargs):
        """Update customer profile."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id()
        with self.handle() as ctx:
            user = request.env["res.users"].sudo().browse(user_id)
            if not user.exists():
                raise ValidationError(_("User profile not found."))

            data = _parse_request_data()
            vals = {}

            if "name" in data:
                vals["name"] = str(data["name"]).strip()
            if "phone" in data:
                vals["phone"] = str(data["phone"]).strip()
            if "preferred_language" in data:
                lang = str(data["preferred_language"]).lower()
                if lang in ["ar", "en"]:
                    vals["preferred_language"] = lang
            if "preferred_theme" in data:
                theme = str(data["preferred_theme"]).lower()
                if theme in ["light", "dark"]:
                    vals["preferred_theme"] = theme
            if "push_notifications_enabled" in data:
                val = data["push_notifications_enabled"]
                vals["push_notifications_enabled"] = val if isinstance(val, bool) else (str(val).lower() not in ("false", "0", "no"))

            avatar_raw = data.get("avatar") or data.get("image")
            if avatar_raw:
                try:
                    vals["image_1920"] = avatar_raw.encode("utf-8") if isinstance(avatar_raw, str) else avatar_raw
                except Exception:
                    pass

            if vals:
                user.write(vals)

            ctx.set_body(ResponseBuilder.success(data={
                "id": user.id,
                "name": user.name,
                "phone": user.phone,
                "preferred_language": getattr(user, "preferred_language", "ar"),
                "preferred_theme": getattr(user, "preferred_theme", "light"),
                "push_notifications_enabled": getattr(user, "push_notifications_enabled", True),
            }, message=_("Profile updated successfully.")))
        return ctx.response
