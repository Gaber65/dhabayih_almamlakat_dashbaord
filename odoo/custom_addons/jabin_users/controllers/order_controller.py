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
        cors="*",
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

            myfatoorah_token = None
            if order.payment_method_id and order.payment_method_id.code != "cod":
                myfatoorah_token = request.env['ir.config_parameter'].sudo().get_param('jabin.myfatoorah.api_token', 'myfatoorah_test_token')

            ctx.set_body(ResponseBuilder.success(data={
                "order_id": order.id,
                "order_number": order.name,
                "state": order.state,
                "payment_status": order.payment_status,
                "subtotal": getattr(order, "subtotal", order.total),
                "discount_amount": getattr(order, "discount_amount", 0.0),
                "points_redeemed": getattr(order, "points_redeemed", 0),
                "loyalty_discount_amount": getattr(order, "loyalty_discount_amount", 0.0),
                "delivery_fee": getattr(order, "delivery_fee", 0.0),
                "total": order.total,
                "myfatoorah_token": myfatoorah_token,
            }, message=_("Checkout completed successfully."), code=201))
        return ctx.response

    @http.route(
        "/api/v1/checkout/summary",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        cors="*",
    )
    def checkout_summary(self, **kwargs):
        """Get summary of the checkout before placing the order."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id()
        with self.handle() as ctx:
            from odoo.addons.jabin_dashboard.services.cart_service import CartService
            cart = CartService.get_or_create_active_cart(request.env, user_id)
            
            # 1. Delivery Methods
            delivery_fee_config = float(request.env['ir.config_parameter'].sudo().get_param('jabin.delivery.fee', '31.95'))
            delivery_methods = [
                {"code": "address", "name": _("توصيل الطلبات للعنوان"), "fee": delivery_fee_config},
                {"code": "pickup", "name": _("استلام من المتجر"), "fee": 0.0}
            ]
            
            # 2. Default Address
            address_obj = request.env["res.users.address"].sudo().search([("user_id", "=", user_id), ("is_default", "=", True)], limit=1)
            if not address_obj:
                address_obj = request.env["res.users.address"].sudo().search([("user_id", "=", user_id)], limit=1)
            
            address_data = None
            if address_obj:
                address_data = {
                    "id": address_obj.id,
                    "title": address_obj.title or _("عنوان"),
                    "details": address_obj.street,
                    "city": address_obj.city,
                }
            
            # 3. Payment Methods
            payment_methods = []
            pm_records = request.env["jabin.payment.method"].sudo().search([("active", "=", True)], order="id")
            for pm in pm_records:
                payment_methods.append({
                    "id": pm.id,
                    "code": pm.code,
                    "name": pm.name,
                })
                
            # 4. Order Summary (Assuming default delivery is 'address')
            subtotal = cart.subtotal
            discount = cart.discount_amount
            shipping_cost = delivery_fee_config
            total = subtotal - discount + shipping_cost

            ctx.set_body(ResponseBuilder.success(data={
                "cart_summary": {
                    "line_count": cart.line_count,
                    "subtotal": subtotal,
                    "discount_amount": discount,
                },
                "delivery_methods": delivery_methods,
                "default_address": address_data,
                "payment_methods": payment_methods,
                "order_summary": {
                    "subtotal": subtotal,
                    "discount": discount,
                    "shipping_cost": shipping_cost,
                    "total": total
                }
            }, message=_("Checkout summary retrieved.")))
        return ctx.response

def _is_admin_request() -> bool:
    try:
        raw_header = request.httprequest.headers.get("Authorization", "")
        if raw_header:
            parts = raw_header.split(None, 1)
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                token = parts[1].strip()
                from odoo.addons.jabin_security.utils.jwt_utils import JWTUtils
                claims = JWTUtils.decode_token(token)
                if claims and claims.get("type") in ("admin", "staff"):
                    return True
    except Exception:
        pass
    return request.env.user.has_group('base.group_user')


class OrderController(BaseApiController):
    """Customer Orders and Checkout REST API Controller."""

    @http.route(
        "/api/v1/orders",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        cors="*",
    )
    def list_orders(self, **kwargs):
        """List customer orders with optional state filtering."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id()
        is_admin = _is_admin_request()
        with self.handle() as ctx:
            limit = int(kwargs.get("limit", 50))
            offset = int(kwargs.get("offset", 0))

            domain = [] if is_admin else [("customer_id", "=", user_id)]
            state_filter = kwargs.get("state")
            if state_filter == "active":
                domain.append(("state", "in", ["draft", "pending_payment", "confirmed", "preparing", "ready_pickup", "out_delivery"]))
            elif state_filter == "previous":
                domain.append(("state", "=", "delivered"))
            elif state_filter == "cancelled":
                domain.append(("state", "in", ["cancelled", "refunded"]))
            elif state_filter == "pending":
                domain.append(("state", "in", ["draft", "pending_payment"]))
            elif state_filter == "out_delivery":
                domain.append(("state", "in", ["out_delivery", "out_for_delivery"]))
            elif state_filter and state_filter != "all":
                domain.append(("state", "=", state_filter))

            search_query = kwargs.get("search") or kwargs.get("query")
            if search_query:
                domain.extend([
                    "|", "|",
                    ("name", "ilike", search_query),
                    ("customer_id.name", "ilike", search_query),
                    ("customer_id.phone", "ilike", search_query),
                ])

            orders = request.env["jabin.order"].sudo().search(domain, order="date desc, id desc", limit=limit, offset=offset)

            res = []
            for ord_rec in orders:
                cust = ord_rec.customer_id
                cust_phone = ""
                cust_name = ""
                cust_email = ""
                if cust:
                    cust_name = cust.name or (cust.partner_id.name if getattr(cust, 'partner_id', None) else '') or ""
                    cust_phone = cust.phone or getattr(cust, 'mobile', '') or (cust.partner_id.phone if getattr(cust, 'partner_id', None) else '') or (cust.partner_id.mobile if getattr(cust, 'partner_id', None) else '') or ""
                    cust_email = cust.email or (cust.partner_id.email if getattr(cust, 'partner_id', None) else '') or ""

                res.append({
                    "id": ord_rec.id,
                    "name": ord_rec.name,
                    "date": ord_rec.date,
                    "state": ord_rec.state,
                    "payment_status": ord_rec.payment_status,
                    "subtotal": ord_rec.subtotal,
                    "discount_amount": ord_rec.discount_amount,
                    "tax_amount": ord_rec.tax_amount,
                    "delivery_fee": getattr(ord_rec, "delivery_fee", 0.0),
                    "total": ord_rec.total,
                    "item_count": len(ord_rec.order_line_ids),
                    "payment_method": ord_rec.payment_method_id.name if ord_rec.payment_method_id else None,
                    "delivery_type": getattr(ord_rec, "delivery_type", "address"),
                    "customer": {
                        "id": cust.id if cust else None,
                        "name": cust_name,
                        "phone": cust_phone,
                        "email": cust_email,
                    } if cust else None,
                    "customer_name": cust_name,
                    "customer_phone": cust_phone,
                })
            ctx.set_body(ResponseBuilder.success(data=res, message=_("Orders retrieved successfully.")))
        return ctx.response

    @http.route(
        "/api/v1/orders/<int:order_id>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        cors="*",
    )
    def get_order_detail(self, order_id: int, **kwargs):
        """Get order detail including items and timeline history."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id()
        is_admin = _is_admin_request()
        with self.handle() as ctx:
            order = request.env["jabin.order"].sudo().browse(order_id)
            if not order.exists() or ((not order.customer_id or order.customer_id.id != user_id) and not is_admin):
                raise ValidationError(_("Order not found."))

            lines = []
            for l in order.order_line_ids:
                try:
                    lines.append({
                        "id": l.id,
                        "product_id": getattr(l, "product_id", None) and l.product_id.id,
                        "name": l.name or '',
                        "price_unit": getattr(l, "price_unit", 0.0) or 0.0,
                        "quantity": getattr(l, "quantity", 1.0) or 1.0,
                        "discount": getattr(l, "discount", 0.0) or 0.0,
                        "price_subtotal": getattr(l, "price_subtotal", 0.0) or 0.0,
                        "discount_amount": getattr(l, "discount_amount", 0.0) or 0.0,
                        "cutting_option": {"id": l.cutting_option_id.id, "name": l.cutting_option_id.name} if hasattr(l, "cutting_option_id") and l.cutting_option_id else None,
                        "packaging": {"id": l.packaging_id.id, "name": l.packaging_id.name} if hasattr(l, "packaging_id") and l.packaging_id else None,
                        "excluded_parts": [{"id": p.id, "name": p.name} for p in l.excluded_part_ids] if hasattr(l, "excluded_part_ids") and l.excluded_part_ids else [],
                    })
                except Exception:
                    pass

            timeline = []
            for t in order.timeline_ids:
                try:
                    timeline.append({
                        "id": t.id,
                        "status_from": t.status_from or '',
                        "status_to": t.status_to or '',
                        "description": t.description or '',
                        "timestamp": str(t.timestamp) if t.timestamp else '',
                    })
                except Exception:
                    pass

            cust = order.customer_id if hasattr(order, 'customer_id') and order.customer_id else None
            customer_data = None
            shipping_address_str = None
            if cust:
                try:
                    cust_name = cust.name or (cust.partner_id.name if getattr(cust, 'partner_id', None) else '') or ""
                    cust_phone = cust.phone or getattr(cust, 'mobile', '') or (cust.partner_id.phone if getattr(cust, 'partner_id', None) else '') or (cust.partner_id.mobile if getattr(cust, 'partner_id', None) else '') or ""
                    cust_email = cust.email or (cust.partner_id.email if getattr(cust, 'partner_id', None) else '') or ""
                    customer_data = {
                        "id": cust.id,
                        "name": cust_name,
                        "phone": cust_phone,
                        "email": cust_email,
                    }
                    if hasattr(order, 'delivery_address_id') and order.delivery_address_id:
                        a = order.delivery_address_id
                        parts = [getattr(a, 'city', '') or '', getattr(a, 'street', '') or '']
                        shipping_address_str = " - ".join([p for p in parts if p])
                    elif hasattr(order, 'shipping_address') and order.shipping_address:
                        shipping_address_str = order.shipping_address
                    else:
                        addr_rec = request.env["res.users.address"].sudo().search([("user_id", "=", cust.id)], limit=1)
                        if addr_rec:
                            parts = [getattr(addr_rec, 'city', '') or '', getattr(addr_rec, 'street', '') or '']
                            shipping_address_str = " - ".join([p for p in parts if p])
                except Exception:
                    pass

            ctx.set_body(ResponseBuilder.success(data={
                "id": order.id,
                "name": order.name or '',
                "date": str(order.date) if order.date else '',
                "state": order.state or 'draft',
                "payment_status": order.payment_status or 'pending',
                "customer": customer_data,
                "customer_name": customer_data["name"] if customer_data else "",
                "customer_phone": customer_data["phone"] if customer_data else "",
                "customer_email": customer_data["email"] if customer_data else "",
                "delivery_type": getattr(order, "delivery_type", "address") or "address",
                "shipping_address": shipping_address_str,
                "subtotal": getattr(order, "subtotal", 0.0) or 0.0,
                "discount_amount": getattr(order, "discount_amount", 0.0) or 0.0,
                "coupon_code": getattr(order.coupon_id, "code", None) if hasattr(order, "coupon_id") and order.coupon_id else None,
                "points_redeemed": getattr(order, "points_redeemed", 0) or 0,
                "loyalty_discount_amount": getattr(order, "loyalty_discount_amount", 0.0) or 0.0,
                "tax_amount": getattr(order, "tax_amount", 0.0) or 0.0,
                "delivery_fee": getattr(order, "delivery_fee", 0.0) or 0.0,
                "total": getattr(order, "total", 0.0) or 0.0,
                "payment_method": order.payment_method_id.name if order.payment_method_id else None,
                "notes": order.internal_notes or "",
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
        cors="*",
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
        cors="*",
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

    @http.route(
        "/api/v1/orders/<int:order_id>/switch-payment-method",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def switch_payment_method(self, order_id: int, **kwargs):
        """Switch payment method of a pending order (e.g., from Card to COD)."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id()
        with self.handle() as ctx:
            data = _parse_json_body()
            payment_method_code = data.get("payment_method_code", "cod")

            order = request.env["jabin.order"].sudo().browse(order_id)
            if not order.exists() or order.customer_id.id != user_id:
                raise ValidationError(_("Order not found."))

            if order.state != "pending_payment":
                raise ValidationError(_("Only orders in 'pending_payment' state can have their payment method changed."))

            new_method = request.env["jabin.payment.method"].sudo().search([("code", "=", payment_method_code), ("active", "=", True)], limit=1)
            if not new_method:
                raise ValidationError(_("Payment method '%s' not found or inactive.") % payment_method_code)

            order_vals = {
                "payment_method_id": new_method.id,
            }
            if payment_method_code == "cod":
                order_vals["state"] = "confirmed"
                order_vals["payment_status"] = "pending"
                
            order.write(order_vals)
            
            if "jabin.notification.service" in request.env and payment_method_code == "cod":
                try:
                    request.env["jabin.notification.service"].send_order_status_changed(request.env, order, "confirmed")
                except Exception:
                    pass

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
            }, message=_("Payment method switched successfully.")))
        return ctx.response

    @http.route(
        [
            "/api/v1/orders/<int:order_id>/status",
            "/api/v1/admin/orders/<int:order_id>/status",
            "/api/v1/orders/<int:order_id>",
        ],
        type="http",
        auth="public",
        methods=["POST", "PUT"],
        csrf=False,
        cors="*",
    )
    def update_order_status(self, order_id: int, **kwargs):
        """Update order status (Admin / system transition)."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            data = _parse_json_body()
            new_state = data.get("status") or data.get("state")
            if not new_state:
                raise ValidationError(_("Status/State is required."))

            order = request.env["jabin.order"].sudo().browse(order_id)
            if not order.exists():
                raise ValidationError(_("Order not found."))

            old_state = order.state
            if old_state != new_state:
                # Update order state
                order.write({"state": new_state})

                # Record in timeline
                request.env["jabin.order.timeline"].sudo().create({
                    "order_id": order.id,
                    "status_from": old_state,
                    "status_to": new_state,
                    "description": data.get("description") or _("Status updated from %s to %s.") % (old_state, new_state)
                })

                # Handle side effects
                if new_state == "delivered":
                    order.customer_id.log_activity("order_delivered", related_record=f"jabin.order,{order.id}")
                    if "jabin.loyalty.service" in request.env:
                        request.env["jabin.loyalty.service"].award_earned_points(request.env, order.id)
                elif new_state == "cancelled":
                    order.customer_id.log_activity("cancelled_order", related_record=f"jabin.order,{order.id}")
                    if order.payment_status in ("pending", "authorized"):
                        order.write({"payment_status": "cancelled"})
                    if "jabin.loyalty.service" in request.env:
                        request.env["jabin.loyalty.service"].reverse_order_points(request.env, order.id)
                elif new_state == "refunded":
                    order.customer_id.log_activity("requested_refund", related_record=f"jabin.order,{order.id}")
                    order.write({"payment_status": "refunded"})
                    transactions = request.env["jabin.payment.transaction"].sudo().search([
                        ("order_id", "=", order.id),
                        ("status", "=", "paid")
                    ])
                    transactions.write({"status": "refunded", "refund_status": "full"})
                    if "jabin.loyalty.service" in request.env:
                        request.env["jabin.loyalty.service"].reverse_order_points(request.env, order.id)

                if "jabin.notification.service" in request.env:
                    try:
                        request.env["jabin.notification.service"].send_order_status_changed(request.env, order, new_state)
                    except Exception:
                        pass

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
                "delivery_fee": getattr(order, "delivery_fee", 0.0),
                "total": order.total,
                "payment_method": order.payment_method_id.name if order.payment_method_id else None,
                "notes": order.internal_notes,
                "lines": lines,
                "timeline": timeline,
            }, message=_("Order status updated successfully.")))
        return ctx.response

