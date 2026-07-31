import json
from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError
from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder
from odoo.addons.jabin_security.utils.token_auth import require_token
from odoo.addons.jabin_security.decorators.permission_required import permission_required


def _parse_json_body():
    raw = request.httprequest.data
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise ValidationError(_("Invalid JSON payload."))


class AdminUserController(BaseApiController):
    """Admin User Management REST API Controller."""

    @http.route(
        "/api/v1/admin/users",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    @permission_required("users.manage")
    def list_users(self, **kwargs):
        """Admin API: List customer/user accounts with financial & status metrics."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            limit = int(kwargs.get("limit", 50))
            offset = int(kwargs.get("offset", 0))

            domain = []
            status_filter = kwargs.get("status")
            if status_filter:
                domain.append(("status", "=", status_filter))

            user_type_filter = kwargs.get("user_type")
            if user_type_filter:
                domain.append(("user_type", "=", user_type_filter))

            q = kwargs.get("q")
            if q:
                domain.extend(["|", ("name", "ilike", q), ("login", "ilike", q)])

            users = request.env["res.users"].sudo().search(domain, order="id desc", limit=limit, offset=offset)
            total = request.env["res.users"].sudo().search_count(domain)

            res = []
            for u in users:
                res.append({
                    "id": u.id,
                    "name": u.name,
                    "email": u.email or u.login,
                    "phone": u.phone,
                    "status": getattr(u, "status", "active"),
                    "user_type": getattr(u, "user_type", "customer"),
                    "total_orders_count": getattr(u, "total_orders_count", 0),
                    "total_spending": getattr(u, "total_spending", 0.0),
                    "loyalty_points": getattr(u, "loyalty_points", 0),
                    "create_date": u.create_date,
                })

            ctx.set_body(ResponseBuilder.success(data={
                "data": res,
                "pagination": {
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                }
            }, message=_("User accounts retrieved successfully.")))
        return ctx.response

    @http.route(
        "/api/v1/admin/users/<int:user_id>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    @permission_required("users.manage")
    def get_user_detail(self, user_id: int, **kwargs):
        """Admin API: Get comprehensive user account detail."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            u = request.env["res.users"].sudo().browse(user_id)
            if not u.exists():
                raise ValidationError(_("User not found."))

            addresses = []
            for a in u.addresses:
                addresses.append({
                    "id": a.id,
                    "title": a.title,
                    "recipient_name": a.recipient_name,
                    "recipient_phone": a.recipient_phone,
                    "city": a.city,
                    "street": a.street,
                    "is_default": a.is_default,
                })

            ctx.set_body(ResponseBuilder.success(data={
                "id": u.id,
                "name": u.name,
                "email": u.email or u.login,
                "phone": u.phone,
                "status": getattr(u, "status", "active"),
                "user_type": getattr(u, "user_type", "customer"),
                "total_orders_count": getattr(u, "total_orders_count", 0),
                "total_spending": getattr(u, "total_spending", 0.0),
                "total_refunds": getattr(u, "total_refunds", 0.0),
                "loyalty_points": getattr(u, "loyalty_points", 0),
                "addresses": addresses,
                "create_date": u.create_date,
            }, message=_("User detail retrieved.")))
        return ctx.response

    @http.route(
        "/api/v1/admin/users/<int:user_id>/status",
        type="http",
        auth="public",
        methods=["PUT"],
        csrf=False,
    )
    @permission_required("users.manage")
    def update_user_status(self, user_id: int, **kwargs):
        """Admin API: Change user status (pending, active, suspended, inactive)."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            u = request.env["res.users"].sudo().browse(user_id)
            if not u.exists():
                raise ValidationError(_("User not found."))

            data = _parse_json_body()
            new_status = data.get("status")
            if new_status not in ["pending", "active", "suspended", "inactive"]:
                raise ValidationError(_("Status must be one of: pending, active, suspended, inactive."))

            u.write({"status": new_status})
            u.log_activity("changed_status", related_record=f"res.users,{u.id}")

            ctx.set_body(ResponseBuilder.success(data={
                "id": u.id,
                "status": u.status,
            }, message=_("User status updated successfully.")))
        return ctx.response
