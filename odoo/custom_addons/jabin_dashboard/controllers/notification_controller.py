# notification_controller.py
import json
from typing import Dict, Any, Optional

from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError

from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder, JabinLogger
from odoo.addons.jabin_security.utils.token_auth import require_token
from odoo.addons.jabin_security.decorators.permission_required import permission_required

from ..services.notification_service import NotificationService

_logger = JabinLogger.get("notification.controller")


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


class NotificationController(BaseApiController):
    """REST API Controller for Notifications and Admin Push Alerts."""

    @http.route(
        "/api/v1/notifications",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_notifications(self, **kwargs):
        """Get customer notification history."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id() or request.env.user.id
        with self.handle() as ctx:
            limit = int(kwargs.get("limit", 20))
            offset = int(kwargs.get("offset", 0))

            domain = [('user_id', '=', user_id)]
            status_filter = kwargs.get("status")
            if status_filter:
                domain.append(('status', '=', status_filter))

            notifs = request.env['jabin.notification'].sudo().search(
                domain,
                order='create_date desc, id desc',
                limit=limit,
                offset=offset
            )

            res = []
            for n in notifs:
                res.append({
                    "id": n.id,
                    "uuid": n.uuid,
                    "title": n.title,
                    "body": n.body,
                    "image_url": n.image_url,
                    "notification_type": n.notification_type,
                    "priority": n.priority,
                    "deep_link": n.deep_link,
                    "status": n.status,
                    "data": json.loads(n.data_json or '{}'),
                    "sent_at": n.sent_at,
                    "read_at": n.read_at,
                    "order_id": n.order_id.id if n.order_id else None
                })

            unread_count = request.env['jabin.notification'].sudo().search_count([
                ('user_id', '=', user_id),
                ('status', '!=', 'read')
            ])

            ctx.set_body(ResponseBuilder.success(data={
                "unread_count": unread_count,
                "notifications": res
            }, message=_("Notifications retrieved successfully.")))

        return ctx.response

    @http.route(
        "/api/v1/notifications/unread-count",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_unread_count(self, **kwargs):
        """Get unread notification count for the authenticated customer."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id() or request.env.user.id
        with self.handle() as ctx:
            unread_count = request.env['jabin.notification'].sudo().search_count([
                ('user_id', '=', user_id),
                ('status', '!=', 'read')
            ])
            ctx.set_body(ResponseBuilder.success(data={"unread_count": unread_count}, message=_("Unread count retrieved.")))
        return ctx.response

    @http.route(
        "/api/v1/notifications/<int:notification_id>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_notification_detail(self, notification_id: int, **kwargs):
        """Get single notification details."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id() or request.env.user.id
        with self.handle() as ctx:
            notif = request.env['jabin.notification'].sudo().browse(notification_id)
            if not notif.exists() or notif.user_id.id != user_id:
                raise ValidationError(_("Notification not found."))

            # Auto mark as read when fetched in detail
            if notif.status != 'read':
                notif.mark_as_read()

            return ResponseBuilder.success(data={
                "id": notif.id,
                "uuid": notif.uuid,
                "title": notif.title,
                "body": notif.body,
                "image_url": notif.image_url,
                "notification_type": notif.notification_type,
                "priority": notif.priority,
                "deep_link": notif.deep_link,
                "status": notif.status,
                "data": json.loads(notif.data_json or '{}'),
                "sent_at": notif.sent_at,
                "read_at": notif.read_at,
                "order_id": notif.order_id.id if notif.order_id else None
            }, message="Notification details retrieved.")

    @http.route(
        "/api/v1/notifications/read",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def mark_notifications_read(self, **kwargs):
        """Mark notification(s) as read."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id() or request.env.user.id
        with self.handle() as ctx:
            data = _parse_request_data()
            notif_id = data.get("notification_id") or data.get("id")
            mark_all = data.get("mark_all", False)

            if mark_all:
                unread = request.env['jabin.notification'].sudo().search([
                    ('user_id', '=', user_id),
                    ('status', '!=', 'read')
                ])
                unread.mark_as_read()
                return ResponseBuilder.success(data={"marked_count": len(unread)}, message="All notifications marked as read.")

            if not notif_id:
                raise ValidationError(_("notification_id is required."))

            NotificationService.mark_as_read(request.env, user_id, int(notif_id))
            return ResponseBuilder.success(data={"notification_id": int(notif_id), "read": True}, message="Notification marked as read.")

    @http.route(
        "/api/v1/admin/notifications/send",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    @permission_required("notifications.send_admin")
    def admin_send_notification(self, **kwargs):
        """Admin API: Send push notification to a specific user or admins."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            data = _parse_request_data()
            target_user_id = data.get("user_id")
            title = str(data.get("title", "")).strip()
            body = str(data.get("body", "")).strip()
            notification_type = data.get("type", "system")
            deep_link = data.get("deep_link")
            payload_data = data.get("data")
            image_url = data.get("image_url")
            priority = data.get("priority", "normal")

            if target_user_id:
                notif = NotificationService.send_to_user(
                    request.env,
                    user_id=int(target_user_id),
                    title=title,
                    body=body,
                    notification_type=notification_type,
                    deep_link=deep_link,
                    data=payload_data,
                    priority=priority,
                    image_url=image_url
                )
                return ResponseBuilder.success(data={"notification_id": notif.id if notif else None}, message="Notification sent to user.")
            else:
                NotificationService.send_to_admins(
                    request.env,
                    title=title,
                    body=body,
                    notification_type=notification_type,
                    deep_link=deep_link,
                    data=payload_data
                )
                return ResponseBuilder.success(data={"sent_to_admins": True}, message="Notification sent to admins.")

    @http.route(
        "/api/v1/admin/notifications/broadcast",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    @permission_required("notifications.send_admin")
    def admin_broadcast_notification(self, **kwargs):
        """Admin API: Broadcast push notification to topic or all users."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            data = _parse_request_data()
            topic = data.get("topic", "topic:all")
            title = str(data.get("title", "")).strip()
            body = str(data.get("body", "")).strip()
            notification_type = data.get("type", "offer")
            deep_link = data.get("deep_link")
            payload_data = data.get("data")
            image_url = data.get("image_url")

            result = NotificationService.broadcast(
                request.env,
                topic_or_all=topic,
                title=title,
                body=body,
                notification_type=notification_type,
                deep_link=deep_link,
                data=payload_data,
                image_url=image_url
            )
            return ResponseBuilder.success(data=result, message="Broadcast push notification sent successfully.")
