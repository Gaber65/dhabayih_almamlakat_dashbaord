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
        cors="*",
    )
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

            q = kwargs.get("q") or kwargs.get("search")
            if q:
                domain.extend(["|", "|", ("name", "ilike", q), ("login", "ilike", q), ("phone", "ilike", q)])

            users = request.env["res.users"].sudo().search(domain, order="id desc", limit=limit, offset=offset)
            total = request.env["res.users"].sudo().search_count(domain)

            res = []
            for u in users:
                res.append({
                    "id": u.id,
                    "name": u.name or "",
                    "email": u.email or u.login or "",
                    "phone": u.phone or "",
                    "status": getattr(u, "status", "active") or "active",
                    "user_type": getattr(u, "user_type", "individual") or "individual",
                    "total_orders_count": getattr(u, "total_orders_count", 0) or 0,
                    "total_spending": float(getattr(u, "total_spending", 0.0) or 0.0),
                    "loyalty_points": getattr(u, "loyalty_points", 0) or 0,
                    "create_date": u.create_date.isoformat() if u.create_date else None,
                })

            ctx.set_body(ResponseBuilder.success(data={
                "data": res,
                "users": res,
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
        cors="*",
    )
    def get_user_detail(self, user_id: int, **kwargs):
        """Admin API: Get comprehensive user account detail matching Odoo ERP views."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            u = request.env["res.users"].sudo().browse(user_id)
            if not u.exists():
                raise ValidationError(_("User not found."))

            # Addresses
            addresses = []
            for a in getattr(u, "addresses", []):
                addresses.append({
                    "id": a.id,
                    "title": a.title or "",
                    "recipient_name": a.recipient_name or "",
                    "recipient_phone": a.recipient_phone or "",
                    "city": a.city or "",
                    "street": a.street or "",
                    "country": a.country_id.name if hasattr(a, "country_id") and a.country_id else "",
                    "latitude": getattr(a, "latitude", None),
                    "longitude": getattr(a, "longitude", None),
                    "is_default": a.is_default or False,
                })

            # Orders
            orders = []
            for o in getattr(u, "order_ids", []):
                orders.append({
                    "id": o.id,
                    "name": o.name or "",
                    "date": o.date.isoformat() if hasattr(o, "date") and o.date else (o.create_date.isoformat() if o.create_date else None),
                    "state": o.state or "draft",
                    "payment_status": getattr(o, "payment_status", "pending") or "pending",
                    "total": float(getattr(o, "total", 0.0) or 0.0),
                })

            # Loyalty Transactions
            loyalty_txs = []
            for lt in getattr(u, "loyalty_transaction_ids", []):
                loyalty_txs.append({
                    "id": lt.id,
                    "date": lt.date.isoformat() if hasattr(lt, "date") and lt.date else (lt.create_date.isoformat() if lt.create_date else None),
                    "transaction_type": getattr(lt, "transaction_type", "earn") or "earn",
                    "points": getattr(lt, "points", 0) or 0,
                    "balance_after": getattr(lt, "balance_after", 0) or 0,
                    "order_name": lt.order_id.name if hasattr(lt, "order_id") and lt.order_id else None,
                    "description": lt.description or "",
                })

            ctx.set_body(ResponseBuilder.success(data={
                "id": u.id,
                "name": u.name or "",
                "email": u.email or u.login or "",
                "phone": u.phone or "",
                "status": getattr(u, "status", "active") or "active",
                "user_type": getattr(u, "user_type", "individual") or "individual",
                "profile_completed": getattr(u, "profile_completed", False),
                "verified_at": u.verified_at.isoformat() if getattr(u, "verified_at", False) else None,
                "balance": float(getattr(u, "balance", 0.0) or 0.0),
                "currency": u.currency_id.name if getattr(u, "currency_id", False) else "SAR",
                "company_name": u.company_id.name if getattr(u, "company_id", False) else "",
                
                # Financial Information
                "total_orders_count": getattr(u, "total_orders_count", len(orders)),
                "total_spending": float(getattr(u, "total_spending", 0.0) or 0.0),
                "average_order_value": float(getattr(u, "average_order_value", 0.0) or 0.0),
                "total_refunds": float(getattr(u, "total_refunds", 0.0) or 0.0),
                "preferred_payment_method": u.preferred_payment_method_id.name if getattr(u, "preferred_payment_method_id", False) else None,
                
                # Loyalty Wallet
                "loyalty_points": getattr(u, "loyalty_points", 0) or 0,
                "total_earned_points": getattr(u, "total_earned_points", getattr(u, "loyalty_points", 0)) or 0,
                "total_redeemed_points": getattr(u, "total_redeemed_points", 0) or 0,
                "loyalty_transactions": loyalty_txs,

                # Activity & Dates
                "pending_payments_count": getattr(u, "pending_payments_count", 0) or 0,
                "completed_payments_count": getattr(u, "completed_payments_count", 0) or 0,
                "create_date": u.create_date.isoformat() if u.create_date else None,
                "last_login": u.last_login.isoformat() if getattr(u, "last_login", False) else None,
                "last_activity_date": u.last_activity_date.isoformat() if getattr(u, "last_activity_date", False) else None,

                # Sub-records
                "addresses": addresses,
                "orders": orders,
            }, message=_("User detail retrieved.")))
        return ctx.response

    @http.route(
        "/api/v1/admin/users/<int:user_id>/status",
        type="http",
        auth="public",
        methods=["PUT"],
        csrf=False,
        cors="*",
    )
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
            if hasattr(u, "log_activity"):
                u.log_activity("changed_status", related_record=f"res.users,{u.id}")

            ctx.set_body(ResponseBuilder.success(data={
                "id": u.id,
                "status": u.status,
            }, message=_("User status updated successfully.")))
        return ctx.response

    @http.route(
        "/api/v1/admin/users",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def create_user(self, **kwargs):
        """Admin API: Create a new customer/user account."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            data = _parse_json_body()
            name = (data.get("name") or "").strip()
            email = (data.get("email") or "").strip()
            phone = (data.get("phone") or "").strip()
            password = data.get("password") or "123456"
            user_type = data.get("user_type", "individual")
            status = data.get("status", "active")

            if not name:
                raise ValidationError(_("Customer name is required."))
            if not email and not phone:
                raise ValidationError(_("Email or phone number is required."))

            login = email or phone
            existing = request.env["res.users"].sudo().search([("login", "=", login)], limit=1)
            if existing:
                raise ValidationError(_("A user with this login/email already exists."))

            vals = {
                "name": name,
                "login": login,
                "email": email or False,
                "phone": phone or False,
                "password": password,
            }
            if hasattr(request.env["res.users"], "status"):
                vals["status"] = status
            if hasattr(request.env["res.users"], "user_type"):
                vals["user_type"] = user_type

            user = request.env["res.users"].sudo().create(vals)

            initial_points = int(data.get("loyalty_points") or 0)
            if initial_points > 0 and hasattr(user, "loyalty_points"):
                user.write({"loyalty_points": initial_points})

            ctx.set_body(ResponseBuilder.success(data={
                "id": user.id,
                "name": user.name or "",
                "email": user.email or user.login or "",
                "phone": user.phone or "",
                "status": getattr(user, "status", "active") or "active",
                "user_type": getattr(user, "user_type", "individual") or "individual",
                "total_orders_count": getattr(user, "total_orders_count", 0) or 0,
                "total_spending": float(getattr(user, "total_spending", 0.0) or 0.0),
                "total_refunds": float(getattr(user, "total_refunds", 0.0) or 0.0),
                "loyalty_points": getattr(user, "loyalty_points", 0) or 0,
                "create_date": user.create_date.isoformat() if user.create_date else None,
            }, message=_("Customer created successfully.")))
        return ctx.response

    @http.route(
        "/api/v1/admin/users/<int:user_id>",
        type="http",
        auth="public",
        methods=["PUT"],
        csrf=False,
        cors="*",
    )
    def update_user(self, user_id: int, **kwargs):
        """Admin API: Update customer account details."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            u = request.env["res.users"].sudo().browse(user_id)
            if not u.exists():
                raise ValidationError(_("User not found."))

            data = _parse_json_body()
            vals = {}
            if "name" in data and data["name"]:
                vals["name"] = data["name"].strip()
            if "phone" in data:
                vals["phone"] = data["phone"].strip() if data["phone"] else False
            if "email" in data:
                vals["email"] = data["email"].strip() if data["email"] else False
            if "user_type" in data and hasattr(u, "user_type"):
                vals["user_type"] = data["user_type"]
            if "status" in data and hasattr(u, "status"):
                vals["status"] = data["status"]
            if "password" in data and data["password"]:
                vals["password"] = data["password"]

            if vals:
                u.write(vals)

            ctx.set_body(ResponseBuilder.success(data={
                "id": u.id,
                "name": u.name or "",
                "email": u.email or u.login or "",
                "phone": u.phone or "",
                "status": getattr(u, "status", "active") or "active",
                "user_type": getattr(u, "user_type", "individual") or "individual",
                "total_orders_count": getattr(u, "total_orders_count", 0) or 0,
                "total_spending": float(getattr(u, "total_spending", 0.0) or 0.0),
                "total_refunds": float(getattr(u, "total_refunds", 0.0) or 0.0),
                "loyalty_points": getattr(u, "loyalty_points", 0) or 0,
                "create_date": u.create_date.isoformat() if u.create_date else None,
            }, message=_("Customer updated successfully.")))
        return ctx.response

    @http.route(
        "/api/v1/admin/users/<int:user_id>",
        type="http",
        auth="public",
        methods=["DELETE"],
        csrf=False,
        cors="*",
    )
    def delete_user(self, user_id: int, **kwargs):
        """Admin API: Deactivate / Delete customer account."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            u = request.env["res.users"].sudo().browse(user_id)
            if not u.exists():
                raise ValidationError(_("User not found."))

            vals = {"active": False}
            if hasattr(u, "status"):
                vals["status"] = "inactive"
            u.write(vals)

            ctx.set_body(ResponseBuilder.success(data={
                "id": user_id,
            }, message=_("Customer deactivated successfully.")))
        return ctx.response
