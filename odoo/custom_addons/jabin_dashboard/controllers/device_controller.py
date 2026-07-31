# device_controller.py
import json
from typing import Dict, Any, Optional

from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError

from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder, JabinLogger
from odoo.addons.jabin_security.utils.token_auth import require_token

from ..services.notification_service import NotificationService

_logger = JabinLogger.get("device.controller")


def _get_auth_user_id() -> Optional[int]:
    """Helper to extract user ID from Authorization Bearer token."""
    try:
        raw_header = request.httprequest.headers.get("Authorization", "")
    except Exception:
        return None

    token = ""
    if raw_header:
        parts = raw_header.split(None, 1)
        if len(parts) == 2 and parts[0].lower() == 'bearer':
            token = parts[1].strip()

    if not token:
        return None

    try:
        from odoo.addons.jabin_security.utils.jwt_utils import JWTUtils
        claims = JWTUtils.decode_token(token)
        return JWTUtils.get_user_id(claims)
    except Exception:
        return None


def _parse_request_data() -> Dict[str, Any]:
    """Parse request JSON payload."""
    raw = request.httprequest.data
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON payload.")
    return {}


class DeviceController(BaseApiController):
    """REST API Controller for Customer Device Registration and FCM Token Lifecycle."""

    @http.route(
        "/api/v1/device/register",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def register_device(self, **kwargs):
        """Register or update customer device FCM token."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id() or request.env.user.id
        with self.handle() as ctx:
            data = _parse_request_data()
            device = NotificationService.register_device(request.env, user_id, data)

            return ResponseBuilder.success(data={
                "id": device.id,
                "uuid": device.uuid,
                "user_id": device.user_id.id,
                "device_name": device.device_name,
                "device_type": device.device_type,
                "fcm_token": device.fcm_token,
                "is_active": device.is_active,
                "last_seen": device.last_seen
            }, message="Device registered successfully.")

    @http.route(
        "/api/v1/device/update-token",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def update_token(self, **kwargs):
        """Update FCM token for existing customer device."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id() or request.env.user.id
        with self.handle() as ctx:
            data = _parse_request_data()
            old_token = data.get("old_token") or data.get("uuid")
            new_token = data.get("fcm_token") or data.get("new_token")

            device = NotificationService.update_token(request.env, user_id, old_token, new_token)

            return ResponseBuilder.success(data={
                "id": device.id,
                "uuid": device.uuid,
                "user_id": device.user_id.id,
                "fcm_token": device.fcm_token,
                "is_active": device.is_active
            }, message="Device FCM token updated successfully.")

    @http.route(
        "/api/v1/device/logout",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def logout_device(self, **kwargs):
        """Deactivate customer device upon logout."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id() or request.env.user.id
        with self.handle() as ctx:
            data = _parse_request_data()
            token_or_uuid = data.get("fcm_token") or data.get("uuid")

            NotificationService.logout_device(request.env, user_id, token_or_uuid)
            return ResponseBuilder.success(data={
                "user_id": user_id,
                "logged_out": True
            }, message="Device deactivated successfully.")
