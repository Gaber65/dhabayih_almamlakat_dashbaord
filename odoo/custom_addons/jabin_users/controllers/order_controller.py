import json
from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError
from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder
from odoo.addons.jabin_security.utils.token_auth import require_token
from odoo.addons.jabin_security import SecurityContext
from ..services.checkout_service import CheckoutService


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


def _parse_json_body():
    raw = request.httprequest.data
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise ValidationError(_("Invalid JSON payload."))


class OrderController(BaseApiController):
    """Customer Orders and Checkout REST API Controller."""

    @http.route(
        "/api/v1/checkout",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def checkout(self, **kwargs):
        """Perform checkout from active customer cart."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id()
        with self.handle() as ctx:
            data = _parse_json_body()
            delivery_type = data.get("delivery_type", "address")
            address_id = data.get("address_id")
            branch_id = data.get("branch_id")
            payment_method_id = data.get("payment_method_id")
            notes = data.get("notes")
            coupon_code = data.get("coupon_code")
            redeem_points = data.get("redeem_points")

            order = CheckoutService.process_checkout(
                request.env,
                customer_id=user_id,
                delivery_type=delivery_type,
                address_id=address_id,
                branch_id=branch_id,
                payment_method_id=payment_method_id,
                notes=notes,
                coupon_code=coupon_code,
                redeem_points=redeem_points
            )

            ctx.set_body(ResponseBuilder.success(data={
                "order_id": order.id,
                "order_number": order.name,
                "state": order.state,
                "payment_status": order.payment_status,
                "subtotal": getattr(order, "subtotal", order.total),
                "discount_amount": getattr(order, "discount_amount", 0.0),
                "points_redeemed": getattr(order, "points_redeemed", 0),
                "loyalty_discount_amount": getattr(order, "loyalty_discount_amount", 0.0),
                "total": order.total,
            }, message=_("Checkout completed successfully."), code=201))
        return ctx.response

    @http.route(
        "/api/v1/orders",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def list_orders(self, **kwargs):
        """List customer orders with optional state filtering."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id()
        with self.handle() as ctx:
            limit = int(kwargs.get("limit", 20))
            offset = int(kwargs.get("offset", 0))

            domain = [("customer_id", "=", user_id)]
            state_filter = kwargs.get("state")
            if state_filter == "active":
                domain.append(("state", "in", ["draft", "pending_payment", "confirmed", "preparing", "ready_pickup", "out_delivery"]))
            elif state_filter == "previous":
                domain.append(("state", "=", "delivered"))
            elif state_filter == "cancelled":
                domain.append(("state", "in", ["cancelled", "refunded"]))
            elif state_filter:
                domain.append(("state", "=", state_filter))

            orders = request.env["jabin.order"].sudo().search(domain, order="date desc, id desc", limit=limit, offset=offset)

            res = []
            for ord_rec in orders:
                res.append({
                    "id": ord_rec.id,
                    "name": ord_rec.name,
                    "date": ord_rec.date,
                    "state": ord_rec.state,
                    "payment_status": ord_rec.payment_status,
                    "subtotal": ord_rec.subtotal,
                    "discount_amount": ord_rec.discount_amount,
                    "tax_amount": ord_rec.tax_amount,
                    "total": ord_rec.total,
                    "item_count": len(ord_rec.order_line_ids),
                    "payment_method": ord_rec.payment_method_id.name if ord_rec.payment_method_id else None,
                })
            ctx.set_body(ResponseBuilder.success(data=res, message=_("Orders retrieved successfully.")))
        return ctx.response

    @http.route(
        "/api/v1/orders/<int:order_id>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_order_detail(self, order_id: int, **kwargs):
        """Get order detail including items and timeline history."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id()
        with self.handle() as ctx:
            order = request.env["jabin.order"].sudo().browse(order_id)
            if not order.exists() or (order.customer_id.id != user_id and not request.env.user.has_group('base.group_user')):
                raise ValidationError(_("Order not found."))

            lines = []
            for l in order.order_line_ids:
                lines.append({
                    "id": l.id,
                    "product_id": getattr(l, "product_id", None) and l.product_id.id,
                    "name": l.name,
                    "price_unit": l.price_unit,
                    "quantity": l.quantity,
                    "discount": l.discount,
                    "price_subtotal": l.price_subtotal,
                    "discount_amount": l.discount_amount,
                    "cutting_option": {"id": l.cutting_option_id.id, "name": l.cutting_option_id.name} if hasattr(l, "cutting_option_id") and l.cutting_option_id else None,
                    "packaging": {"id": l.packaging_id.id, "name": l.packaging_id.name} if hasattr(l, "packaging_id") and l.packaging_id else None,
                    "excluded_parts": [{"id": p.id, "name": p.name} for p in l.excluded_part_ids] if hasattr(l, "excluded_part_ids") else [],
                })

            timeline = []
            for t in order.timeline_ids:
                timeline.append({
                    "id": t.id,
                    "status_from": t.status_from,
                    "status_to": t.status_to,
                    "description": t.description,
                    "timestamp": t.timestamp,
                })

            ctx.set_body(ResponseBuilder.success(data={
                "id": order.id,
                "name": order.name,
                "date": order.date,
                "state": order.state,
                "payment_status": order.payment_status,
                "subtotal": getattr(order, "subtotal", 0.0),
                "discount_amount": getattr(order, "discount_amount", 0.0),
                "coupon_code": getattr(order.coupon_id, "code", None) if hasattr(order, "coupon_id") and order.coupon_id else None,
                "points_redeemed": getattr(order, "points_redeemed", 0),
                "loyalty_discount_amount": getattr(order, "loyalty_discount_amount", 0.0),
                "tax_amount": order.tax_amount,
                "total": order.total,
                "payment_method": order.payment_method_id.name if order.payment_method_id else None,
                "notes": order.internal_notes,
                "lines": lines,
                "timeline": timeline,
            }, message=_("Order details retrieved.")))
        return ctx.response

    @http.route(
        "/api/v1/orders/<int:order_id>/cancel",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def cancel_order(self, order_id: int, **kwargs):
        """Cancel an order (customer allowed only if state is draft, pending_payment, or confirmed)."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id()
        with self.handle() as ctx:
            order = request.env["jabin.order"].sudo().browse(order_id)
            if not order.exists() or (order.customer_id.id != user_id and not request.env.user.has_group('base.group_user')):
                raise ValidationError(_("Order not found."))

            if order.state not in ["draft", "pending_payment", "confirmed"]:
                raise ValidationError(_("Order cannot be cancelled in its current state ('%s').") % order.state)

            order.action_cancel()
            ctx.set_body(ResponseBuilder.success(data={"id": order.id, "state": order.state}, message=_("Order cancelled successfully.")))
        return ctx.response

    @http.route(
        "/api/v1/orders/<int:order_id>/receive",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def receive_order(self, order_id: int, **kwargs):
        """Confirm receipt of order by customer (updates state to 'delivered')."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id()
        with self.handle() as ctx:
            order = request.env["jabin.order"].sudo().browse(order_id)
            if not order.exists() or (order.customer_id.id != user_id and not request.env.user.has_group('base.group_user')):
                raise ValidationError(_("Order not found."))

            if order.state not in ["out_delivery", "ready_pickup"]:
                raise ValidationError(_("Order cannot be marked as received in its current state ('%s').") % order.state)

            order.action_mark_delivered()
            ctx.set_body(ResponseBuilder.success(data={"id": order.id, "state": order.state}, message=_("Order marked as received successfully.")))
        return ctx.response
