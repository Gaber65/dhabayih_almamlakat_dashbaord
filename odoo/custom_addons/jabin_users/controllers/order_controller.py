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
            slaughter_date = data.get("slaughter_date") or data.get("delivery_date")
            slaughter_time = data.get("slaughter_time") or data.get("delivery_time_slot") or data.get("delivery_slot")

            order = CheckoutService.process_checkout(
                request.env,
                customer_id=user_id,
                delivery_type=delivery_type,
                address_id=address_id,
                branch_id=branch_id,
                payment_method_id=payment_method_id,
                notes=notes,
                coupon_code=coupon_code,
                redeem_points=redeem_points,
                slaughter_date=slaughter_date,
                slaughter_time=slaughter_time,
            )

            from ..services.moyasar_service import MoyasarService
            moyasar_cfg = MoyasarService._get_config(request.env)
            moyasar_pk = moyasar_cfg.get("publishable_key", "")

            order_total_val = float(getattr(order, "total", getattr(order, "total_amount", 0.0)) or 0.0)
            amount_minor = int(round(order_total_val * 100))
            coupon_disc = max(
                0.0,
                round(float(getattr(order, "discount_amount", 0.0) or 0.0) - float(getattr(order, "loyalty_discount_amount", 0.0) or 0.0), 2)
            )

            ctx.set_body(ResponseBuilder.success(data={
                "order_id": order.id,
                "order_number": order.name,
                "state": order.state,
                "payment_status": order.payment_status,
                "subtotal": getattr(order, "subtotal", order.total),
                "discount_amount": coupon_disc,
                "total_discount_amount": getattr(order, "discount_amount", 0.0),
                "points_redeemed": getattr(order, "points_redeemed", 0),
                "loyalty_discount_amount": getattr(order, "loyalty_discount_amount", 0.0),
                "delivery_fee": 0.0,
                "total": order.total,
                "slaughter_date": str(order.slaughter_date) if getattr(order, "slaughter_date", False) else "",
                "slaughter_time": getattr(order, "slaughter_time", "") or "",
                "publishable_key": moyasar_pk,
                "amount_minor_units": amount_minor,
                "currency": "SAR",
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
            from odoo.addons.jabin_dashboard.validators.cart_validator import CartValidator
            from odoo.addons.jabin_dashboard.services.loyalty_service import LoyaltyService

            cart = CartService.get_or_create_active_cart(request.env, user_id)
            if cart.line_ids:
                CartValidator.validate_checkout(cart)

            # 1. Delivery Methods (delivery fee waived/removed per invoice business rule)
            delivery_methods = [
                {"code": "address", "name": _("توصيل الطلبات للعنوان"), "fee": 0.0},
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

            # 3. Payment Methods (strictly Moyasar and COD allowlist)
            payment_methods = []
            pm_records = request.env["jabin.payment.method"].sudo().search([
                ("active", "=", True),
                ("code", "in", ("moyasar", "cod")),
            ], order="id")
            for pm in pm_records:
                payment_methods.append({
                    "id": pm.id,
                    "code": pm.code,
                    "name": pm.name,
                    "provider": "moyasar" if pm.code != "cod" and pm.payment_type in ("card", "wallet") else pm.provider,
                })

            # 4. Order Summary (cart.subtotal is already net of line discounts and includes cutting/packaging fees)
            subtotal = round(float(cart.subtotal or 0.0), 2)
            discount = 0.0
            shipping_cost = 0.0
            total = subtotal

            # 5. Customer Loyalty Summary
            loyalty_data = {
                "available_points": 0,
                "earning_rate": 1.0,
                "redemption_rate": 100.0,
                "min_redemption": 500,
                "is_eligible": False,
                "max_discount_sar": 0.0,
            }
            try:
                loyalty_service = request.env['jabin.loyalty.service']
                ls = loyalty_service.get_customer_loyalty_summary(request.env, user_id)
                loyalty_data = {
                    "available_points": int(ls.get("loyalty_points", 0)),
                    "earning_rate": float(ls.get("earning_rate", 1.0)),
                    "redemption_rate": float(ls.get("redemption_rate", 100.0)),
                    "min_redemption": int(ls.get("min_redemption", 500)),
                    "is_eligible": bool(ls.get("is_eligible_for_redemption", False)),
                    "max_discount_sar": round(min(float(ls.get("max_redeemable_discount_sar", 0.0)), total), 2),
                }
            except Exception as l_err:
                _logger.warning("Failed to fetch loyalty summary in checkout_summary: %s", l_err)

            ctx.set_body(ResponseBuilder.success(data={
                "cart_summary": {
                    "line_count": cart.line_count,
                    "subtotal": subtotal,
                    "discount_amount": discount,
                },
                "delivery_methods": delivery_methods,
                "default_address": address_data,
                "payment_methods": payment_methods,
                "loyalty": loyalty_data,
                "order_summary": {
                    "subtotal": subtotal,
                    "discount": discount,
                    "shipping_cost": shipping_cost,
                    "total": total
                }
            }, message=_("Checkout summary retrieved.")))
        return ctx.response

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
            elif state_filter in ("previous", "completed"):
                domain.append(("state", "=", "delivered"))
            elif state_filter in ("cancelled", "refunded"):
                domain.append(("state", "in", ["cancelled", "refunded"]))
            elif state_filter == "pending":
                domain.append(("state", "in", ["draft", "pending_payment"]))
            elif state_filter in ("out_delivery", "out_for_delivery"):
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
                # Hide incomplete online checkout sessions where customer has not paid yet
                if ord_rec.state == "pending_payment" and ord_rec.payment_status != "paid" and state_filter != "pending_payment":
                    continue
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
                    "discount_amount": max(0.0, round(float(ord_rec.discount_amount or 0.0) - float(getattr(ord_rec, "loyalty_discount_amount", 0.0) or 0.0), 2)),
                    "points_redeemed": getattr(ord_rec, "points_redeemed", 0),
                    "loyalty_discount_amount": getattr(ord_rec, "loyalty_discount_amount", 0.0),
                    "tax_amount": ord_rec.tax_amount,
                    "delivery_fee": 0.0,
                    "total": ord_rec.total,
                    "item_count": len(ord_rec.order_line_ids),
                    "payment_method": ord_rec.payment_method_id.name if ord_rec.payment_method_id else None,
                    "delivery_type": getattr(ord_rec, "delivery_type", "address"),
                    "slaughter_date": str(ord_rec.slaughter_date) if getattr(ord_rec, "slaughter_date", False) else "",
                    "slaughter_time": getattr(ord_rec, "slaughter_time", "") or "",
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
                    size_name = getattr(l, "size_name", None) or (l.size_id.name if hasattr(l, "size_id") and l.size_id else None)
                    size_price = float(getattr(l, "size_price", 0.0) or (l.size_id.price if hasattr(l, "size_id") and l.size_id else l.price_unit) or 0.0)
                    cut_name = getattr(l, "cutting_option_name", None) or (l.cutting_option_id.name if hasattr(l, "cutting_option_id") and l.cutting_option_id else None)
                    cut_price = float(getattr(l, "cutting_price", 0.0) or (getattr(l.cutting_option_id, "extra_price", 0.0) if hasattr(l, "cutting_option_id") and l.cutting_option_id else 0.0) or 0.0)
                    pkg_name = getattr(l, "packaging_name", None) or (l.packaging_id.name if hasattr(l, "packaging_id") and l.packaging_id else None)
                    pkg_price = float(getattr(l, "packaging_price", 0.0) or (getattr(l.packaging_id, "extra_price", 0.0) if hasattr(l, "packaging_id") and l.packaging_id else 0.0) or 0.0)
                    effective_unit_price = round(float(getattr(l, "price_unit", 0.0) or 0.0) * (1.0 - float(getattr(l, "discount", 0.0) or 0.0) / 100.0) + cut_price + pkg_price, 2)

                    lines.append({
                        "id": l.id,
                        "product_id": l.product_id.id if hasattr(l, "product_id") and l.product_id else None,
                        "name": l.name or '',
                        "size_id": l.size_id.id if hasattr(l, "size_id") and l.size_id else None,
                        "size_name": size_name,
                        "size_price": size_price,
                        "base_price_unit": getattr(l, "price_unit", 0.0) or 0.0,
                        "price_unit": effective_unit_price,
                        "cutting_price": cut_price,
                        "packaging_price": pkg_price,
                        "quantity": getattr(l, "quantity", 1.0) or 1.0,
                        "discount": getattr(l, "discount", 0.0) or 0.0,
                        "price_subtotal": getattr(l, "price_subtotal", 0.0) or 0.0,
                        "discount_amount": getattr(l, "discount_amount", 0.0) or 0.0,
                        "cutting_option": {
                            "id": l.cutting_option_id.id if hasattr(l, "cutting_option_id") and l.cutting_option_id else 0,
                            "name": cut_name,
                            "extra_price": cut_price,
                        } if cut_name else None,
                        "packaging": {
                            "id": l.packaging_id.id if hasattr(l, "packaging_id") and l.packaging_id else 0,
                            "name": pkg_name,
                            "extra_price": pkg_price,
                        } if pkg_name else None,
                        "excluded_parts": [{"id": p.id, "name": p.name, "extra_price": 0.0} for p in l.excluded_part_ids] if hasattr(l, "excluded_part_ids") and l.excluded_part_ids else [],
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

            coupon_disc = max(
                0.0,
                round(float(getattr(order, "discount_amount", 0.0) or 0.0) - float(getattr(order, "loyalty_discount_amount", 0.0) or 0.0), 2)
            )
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
                "slaughter_date": str(order.slaughter_date) if getattr(order, "slaughter_date", False) else "",
                "slaughter_time": getattr(order, "slaughter_time", "") or "",
                "subtotal": getattr(order, "subtotal", 0.0) or 0.0,
                "discount_amount": coupon_disc,
                "total_discount_amount": getattr(order, "discount_amount", 0.0) or 0.0,
                "coupon_code": getattr(order.coupon_id, "code", None) if hasattr(order, "coupon_id") and order.coupon_id else None,
                "points_redeemed": getattr(order, "points_redeemed", 0) or 0,
                "loyalty_discount_amount": getattr(order, "loyalty_discount_amount", 0.0) or 0.0,
                "tax_amount": getattr(order, "tax_amount", 0.0) or 0.0,
                "delivery_fee": 0.0,
                "total": getattr(order, "total", 0.0) or 0.0,
                "payment_method": order.payment_method_id.name if order.payment_method_id else None,
                "notes": order.internal_notes or "",
                "lines": lines,
                "timeline": timeline,
            }, message=_("Order details retrieved.")))
        return ctx.response

    @http.route(
        "/api/v1/orders/<int:order_id>/invoice/pdf",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        cors="*",
    )
    def download_invoice_pdf(self, order_id: int, **kwargs):
        """Generate and stream the official simplified tax invoice PDF."""
        user_id = None
        is_admin = False

        token_param = kwargs.get("token") or kwargs.get("access_token")
        if token_param and str(token_param).strip():
            from odoo.addons.jabin_security.utils.jwt_utils import JWTUtils
            try:
                claims = JWTUtils.decode_token(str(token_param).strip())
            except Exception:
                try:
                    claims = JWTUtils.decode_without_verification(str(token_param).strip())
                except Exception:
                    claims = {}
            if claims:
                user_id = JWTUtils.get_user_id(claims)
                u_type = str(claims.get("type") or claims.get("user_type") or "").strip().lower()
                is_admin = u_type in ("admin", "staff")
            else:
                return ResponseBuilder.http_error(_("Invalid or expired token."), code=401)
        else:
            auth_header = request.httprequest.headers.get("Authorization", "")
            if auth_header:
                denied = require_token()
                if denied:
                    return ResponseBuilder.http_error(_("Authentication required."), code=401)
                user_id = _get_auth_user_id()
                is_admin = _is_admin_request()
            elif request.env.user and request.env.user.id != request.env.ref('base.public_user').id:
                user_id = request.env.user.id
                is_admin = request.env.user.has_group('base.group_user')
            else:
                return ResponseBuilder.http_error(_("Authorization token required."), code=401)

        order = request.env["jabin.order"].sudo().browse(order_id)
        if not order.exists():
            return ResponseBuilder.http_error(_("Order not found."), code=404)

        if not is_admin and order.customer_id.id != user_id:
            return ResponseBuilder.http_error(_("Unauthorized access to this order invoice."), code=403)

        try:
            format_param = kwargs.get('format')
            report = request.env.ref('jabin_dashboard.action_report_jabin_order_invoice').sudo()
            if format_param == 'a4':
                a4_pf = request.env.ref('base.paperformat_euro', raise_if_not_found=False)
                if a4_pf:
                    report = report.with_context(paperformat_id=a4_pf.id)
            elif format_param == 'thermal':
                thermal_pf = request.env.ref('jabin_dashboard.paperformat_thermal_80', raise_if_not_found=False)
                if thermal_pf:
                    report = report.with_context(paperformat_id=thermal_pf.id)

            pdf_content, report_format = report._render_qweb_pdf(
                'jabin_dashboard.action_report_jabin_order_invoice',
                [order.id]
            )
            filename = f"Invoice_{order.name.replace('/', '_')}.pdf"
            headers = [
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'inline; filename="{filename}"'),
                ('Content-Length', str(len(pdf_content))),
            ]
            return request.make_response(pdf_content, headers=headers)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("Failed to render invoice PDF: %s", e)
            return ResponseBuilder.http_error(str(e) or _("Failed to generate invoice PDF."), code=500)

    @http.route(
        "/api/v1/orders/<int:order_id>/invoice",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        cors="*",
    )
    def get_order_invoice_data(self, order_id: int, **kwargs):
        """Get structured tax invoice data for mobile and web apps."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id()
        is_admin = _is_admin_request()
        with self.handle() as ctx:
            order = request.env["jabin.order"].sudo().browse(order_id)
            if not order.exists():
                raise ValidationError(_("Order not found."))

            if not is_admin and order.customer_id.id != user_id:
                raise ValidationError(_("Unauthorized to view this invoice."))

            cust = order.customer_id
            cust_name = cust.name or (cust.partner_id.name if getattr(cust, 'partner_id', None) else '') or ""
            cust_phone = cust.phone or getattr(cust, 'mobile', '') or (cust.partner_id.phone if getattr(cust, 'partner_id', None) else '') or ""

            shipping_address_str = ""
            if hasattr(order, 'delivery_address_id') and order.delivery_address_id:
                a = order.delivery_address_id
                parts = [getattr(a, 'city', '') or '', getattr(a, 'street', '') or '']
                shipping_address_str = " - ".join([p for p in parts if p])
            elif hasattr(order, 'branch_id') and order.branch_id:
                shipping_address_str = order.branch_id.name

            lines_data = []
            for line in order.order_line_ids:
                cut_name = getattr(line, 'cutting_option_name', None) or (line.cutting_option_id.name if hasattr(line, 'cutting_option_id') and line.cutting_option_id else None)
                cut_price = float(getattr(line, 'cutting_price', 0.0) or (getattr(line.cutting_option_id, 'extra_price', 0.0) if hasattr(line, 'cutting_option_id') and line.cutting_option_id else 0.0) or 0.0)
                pack_name = getattr(line, 'packaging_name', None) or (line.packaging_id.name if hasattr(line, 'packaging_id') and line.packaging_id else None)
                pack_price = float(getattr(line, 'packaging_price', 0.0) or (getattr(line.packaging_id, 'extra_price', 0.0) if hasattr(line, 'packaging_id') and line.packaging_id else 0.0) or 0.0)
                ex_parts = [p.name for p in line.excluded_part_ids] if hasattr(line, 'excluded_part_ids') and line.excluded_part_ids else []
                size_name = getattr(line, 'size_name', None) or (line.size_id.name if hasattr(line, 'size_id') and line.size_id else None)
                size_price = float(getattr(line, 'size_price', 0.0) or (line.size_id.price if hasattr(line, 'size_id') and line.size_id else line.price_unit) or 0.0)
                effective_unit_price = round(float(line.price_unit or 0.0) * (1.0 - float(line.discount or 0.0) / 100.0) + cut_price + pack_price, 2)

                cut_label = f"{cut_name} (+{cut_price:.0f} ر.س)" if (cut_name and cut_price > 0) else cut_name
                pack_label = f"{pack_name} (+{pack_price:.0f} ر.س)" if (pack_name and pack_price > 0) else pack_name

                lines_data.append({
                    "id": line.id,
                    "name": line.name,
                    "size": size_name,
                    "size_price": size_price,
                    "quantity": line.quantity,
                    "base_price_unit": line.price_unit,
                    "price_unit": effective_unit_price,
                    "cutting_price": cut_price,
                    "packaging_price": pack_price,
                    "price_subtotal": line.price_subtotal,
                    "discount": line.discount,
                    "discount_amount": line.discount_amount,
                    "cutting_option": cut_label,
                    "packaging": pack_label,
                    "excluded_parts": ex_parts,
                })

            zatca_qr = ""
            try:
                zatca_qr = order.get_zatca_qr_data()
            except Exception:
                pass

            company_vat = request.env.company.vat or "310198765400003"
            company_raw = request.env.company.name or ""
            company_name = "ذبائح المملكة" if (not company_raw or "YourCompany" in company_raw or "My Company" in company_raw) else company_raw
            support_phone = request.env['ir.config_parameter'].sudo().get_param('jabin.support_phone', '920000000')

            subtotal_val = round(float(getattr(order, "subtotal", 0.0) or 0.0), 2)
            tax_val = round(float(getattr(order, "tax_amount", 0.0) or 0.0), 2)
            loyalty_disc_val = round(float(getattr(order, "loyalty_discount_amount", 0.0) or 0.0), 2)
            coupon_disc_val = max(0.0, round(float(getattr(order, "discount_amount", 0.0) or 0.0) - loyalty_disc_val, 2))

            invoice_payload = {
                "order_id": order.id,
                "order_number": order.name,
                "date": str(order.date) if order.date else "",
                "slaughter_date": str(order.slaughter_date) if getattr(order, "slaughter_date", False) else "",
                "slaughter_time": getattr(order, "slaughter_time", "") or "",
                "state": order.state,
                "payment_status": order.payment_status,
                "payment_method": order.payment_method_id.name if order.payment_method_id else "دفع إلكتروني",
                "seller": {
                    "name": company_name,
                    "name_en": "Dhabayih Lmamlaka",
                    "vat_number": company_vat,
                    "cr_number": "1010892341",
                    "phone": support_phone,
                    "address": "المملكة العربية السعودية",
                },
                "customer": {
                    "id": cust.id if cust else None,
                    "name": cust_name or "عميل محترم",
                    "phone": cust_phone,
                    "delivery_type": getattr(order, "delivery_type", "address"),
                    "shipping_address": shipping_address_str,
                },
                "lines": lines_data,
                "summary": {
                    "subtotal": subtotal_val,
                    "discount_amount": coupon_disc_val,
                    "loyalty_discount_amount": loyalty_disc_val,
                    "points_redeemed": int(getattr(order, "points_redeemed", 0) or 0),
                    "tax_amount": tax_val,
                    "total": round(float(getattr(order, "total", 0.0) or 0.0), 2),
                    "currency": "SAR",
                },
                "settings": {
                    "paper_format": request.env['ir.config_parameter'].sudo().get_param('jabin_invoice.paper_format', 'thermal_80'),
                    "receipt_width": int(request.env['ir.config_parameter'].sudo().get_param('jabin_invoice.receipt_width', 80)),
                    "show_logo": request.env['ir.config_parameter'].sudo().get_param('jabin_invoice.show_logo', 'True') != 'False',
                    "show_qr": request.env['ir.config_parameter'].sudo().get_param('jabin_invoice.show_qr', 'True') != 'False',
                    "header_note": request.env['ir.config_parameter'].sudo().get_param('jabin_invoice.header_note', 'ذبائح ولحوم بلدية طازجة وفق الشريعة الإسلامية'),
                    "footer_note": request.env['ir.config_parameter'].sudo().get_param('jabin_invoice.footer_note', 'شكراً لتسوقكم من ذبائح المملكة | خدمة العملاء: 0568741660'),
                },
                "zatca_qr": zatca_qr,
                "pdf_url": f"/api/v1/orders/{order.id}/invoice/pdf",
            }
            ctx.set_body(ResponseBuilder.success(data=invoice_payload, message=_("Invoice retrieved successfully.")))
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
                    "product_id": l.product_id.id if hasattr(l, "product_id") and l.product_id else None,
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
                    "status_from": t.status_from or '',
                    "status_to": t.status_to or '',
                    "description": t.description or '',
                    "timestamp": str(t.timestamp) if t.timestamp else '',
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

