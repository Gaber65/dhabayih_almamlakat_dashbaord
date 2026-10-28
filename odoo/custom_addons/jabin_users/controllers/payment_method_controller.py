import json
from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError
from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder
from odoo.addons.jabin_security.utils.token_auth import require_token


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
    try:
        json_data = request.get_json_data()
        if isinstance(json_data, dict):
            return dict(json_data)
    except Exception:
        pass
    raw = request.httprequest.data
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise ValidationError(_("Invalid JSON payload."))


class PaymentMethodController(BaseApiController):
    """Payment Methods & Transactions REST API Controller."""

    @http.route(
        "/api/v1/payment-methods",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        cors="*",
    )
    def list_payment_methods(self, **kwargs):
        """List all payment methods (optionally active-only)."""
        with self.handle() as ctx:
            all_param = kwargs.get("all") or kwargs.get("include_inactive")
            if all_param and str(all_param).lower() in ("true", "1", "yes"):
                domain = []
            else:
                domain = [("active", "=", True)]

            Model = request.env["jabin.payment.method"].sudo()
            if all_param and str(all_param).lower() in ("true", "1", "yes"):
                methods = Model.with_context(active_test=False).search([], order="name")
            else:
                methods = Model.search([("active", "=", True)], order="name")
            res = []
            for m in methods:
                res.append({
                    "id": m.id,
                    "name": m.name,
                    "code": m.code,
                    "payment_type": m.payment_type,
                    "provider": m.provider,
                    "is_installment": m.is_installment,
                    "max_installments": m.max_installments,
                    "description": m.description or "",
                    "active": m.active,
                    "is_active": m.active,
                })
            ctx.set_body(ResponseBuilder.success(data=res, message=_("Payment methods retrieved successfully.")))
        return ctx.response

    @http.route(
        "/api/v1/payment-methods",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def create_payment_method(self, **kwargs):
        """Create a new payment method."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            vals = _parse_json_body()
            name = str(vals.get("name") or "").strip()
            code = str(vals.get("code") or "").strip().lower()
            if not name or not code:
                ctx.set_body(ResponseBuilder.bad_request(message=_("Name and code are required.")))
                return ctx.response

            create_vals = {
                "name": name,
                "code": code,
                "payment_type": vals.get("payment_type", "card"),
                "provider": vals.get("provider", "moyasar"),
                "description": str(vals.get("description") or "").strip(),
                "is_installment": bool(vals.get("is_installment", False)),
                "max_installments": int(vals.get("max_installments") or 0),
                "active": bool(vals.get("active", vals.get("is_active", True))),
            }
            method = request.env["jabin.payment.method"].sudo().create(create_vals)
            ctx.set_body(ResponseBuilder.success(
                data={
                    "id": method.id,
                    "name": method.name,
                    "code": method.code,
                    "payment_type": method.payment_type,
                    "provider": method.provider,
                    "is_installment": method.is_installment,
                    "max_installments": method.max_installments,
                    "description": method.description or "",
                    "active": method.active,
                    "is_active": method.active,
                },
                code=201,
                message=_("Payment method created successfully.")
            ))
        return ctx.response

    @http.route(
        "/api/v1/payment-methods/<int:method_id>",
        type="http",
        auth="public",
        methods=["PUT"],
        csrf=False,
        cors="*",
    )
    def update_payment_method(self, method_id, **kwargs):
        """Update or toggle a payment method."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            method = request.env["jabin.payment.method"].sudo().browse(method_id)
            if not method.exists():
                ctx.set_body(ResponseBuilder.not_found(message=_("Payment method not found.")))
                return ctx.response

            vals = _parse_json_body()
            update_vals = {}
            if "name" in vals:
                update_vals["name"] = str(vals["name"]).strip()
            if "description" in vals:
                update_vals["description"] = str(vals["description"] or "").strip()
            if "payment_type" in vals:
                update_vals["payment_type"] = vals["payment_type"]
            if "provider" in vals:
                update_vals["provider"] = vals["provider"]
            if "is_installment" in vals:
                update_vals["is_installment"] = bool(vals["is_installment"])
            if "max_installments" in vals:
                try:
                    update_vals["max_installments"] = int(vals["max_installments"])
                except (ValueError, TypeError):
                    pass
            if "active" in vals:
                update_vals["active"] = bool(vals["active"])
            elif "is_active" in vals:
                update_vals["active"] = bool(vals["is_active"])

            if update_vals:
                method.write(update_vals)

            ctx.set_body(ResponseBuilder.success(
                data={
                    "id": method.id,
                    "name": method.name,
                    "code": method.code,
                    "payment_type": method.payment_type,
                    "provider": method.provider,
                    "is_installment": method.is_installment,
                    "max_installments": method.max_installments,
                    "description": method.description or "",
                    "active": method.active,
                    "is_active": method.active,
                },
                message=_("Payment method updated successfully.")
            ))
        return ctx.response

    @http.route(
        "/api/v1/payment-methods/<int:method_id>",
        type="http",
        auth="public",
        methods=["DELETE"],
        csrf=False,
        cors="*",
    )
    def delete_payment_method(self, method_id, **kwargs):
        """Deactivate or remove a payment method."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            method = request.env["jabin.payment.method"].sudo().browse(method_id)
            if not method.exists():
                ctx.set_body(ResponseBuilder.not_found(message=_("Payment method not found.")))
                return ctx.response

            try:
                method.unlink()
            except Exception:
                method.write({"active": False})

            ctx.set_body(ResponseBuilder.success(message=_("Payment method deactivated successfully.")))
        return ctx.response

    @http.route(
        ["/api/v1/admin/payments", "/api/v1/admin/payment-transactions"],
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        cors="*",
    )
    def list_payment_transactions(self, **kwargs):
        """List payment transactions with filters for admin dashboard."""
        with self.handle() as ctx:
            domain = []
            status = kwargs.get("status")
            if status and status != "all":
                domain.append(("status", "=", status))

            order_id = kwargs.get("order_id")
            if order_id:
                try:
                    domain.append(("order_id", "=", int(order_id)))
                except ValueError:
                    pass

            method_id = kwargs.get("method_id")
            if method_id:
                try:
                    domain.append(("payment_method_id", "=", int(method_id)))
                except ValueError:
                    pass

            limit = int(kwargs.get("limit", 200))
            offset = int(kwargs.get("offset", 0))

            tx_model = request.env["jabin.payment.transaction"].sudo()
            total = tx_model.search_count(domain)
            records = tx_model.search(domain, limit=limit, offset=offset, order="id desc")

            data = []
            for tx in records:
                customer_name = "-"
                customer_phone = ""
                if tx.customer_id:
                    customer_name = tx.customer_id.name or "-"
                    partner = getattr(tx.customer_id, "partner_id", None)
                    customer_phone = (partner.phone or partner.mobile if partner else "") or getattr(tx.customer_id, "phone", "") or ""

                data.append({
                    "id": tx.id,
                    "order_id": tx.order_id.id if tx.order_id else None,
                    "order_name": tx.order_id.name if tx.order_id else "-",
                    "order_number": tx.order_id.name if tx.order_id else "-",
                    "customer_id": tx.customer_id.id if tx.customer_id else None,
                    "customer_name": customer_name,
                    "customer_phone": customer_phone,
                    "payment_method_id": tx.payment_method_id.id if tx.payment_method_id else None,
                    "payment_method_name": tx.payment_method_id.name if tx.payment_method_id else "-",
                    "payment_method_code": tx.payment_method_id.code if tx.payment_method_id else "-",
                    "amount": float(tx.amount),
                    "currency": tx.currency_id.name if tx.currency_id else "SAR",
                    "status": tx.status,
                    "transaction_ref": tx.transaction_ref or "-",
                    "paid_date": tx.paid_date.isoformat() if tx.paid_date else None,
                    "create_date": tx.create_date.isoformat() if tx.create_date else None,
                    "failure_reason": tx.failure_reason or "",
                    "refund_status": tx.refund_status or "none",
                })

            ctx.set_body(ResponseBuilder.success(
                data=data,
                meta={"total": total, "limit": limit, "offset": offset},
                message=_("Payment transactions retrieved successfully.")
            ))
        return ctx.response

    @http.route(
        "/api/v1/payment/verify",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def verify_payment(self, **kwargs):
        """Verify payment with Moyasar/MyFatoorah and update order status."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id()
        with self.handle() as ctx:
            data = _parse_json_body()
            order_id = data.get("order_id")
            payment_id = data.get("payment_id")

            if not order_id or not payment_id:
                raise ValidationError(_("order_id and payment_id are required."))

            order = request.env["jabin.order"].sudo().browse(order_id)
            if not order.exists() or order.customer_id.id != user_id:
                raise ValidationError(_("Order not found."))

            api_token = request.env['ir.config_parameter'].sudo().get_param('jabin.myfatoorah.api_token', 'myfatoorah_test_token')

            import requests
            url = "https://api.myfatoorah.com/v2/GetPaymentStatus"
            headers = {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "Key": payment_id,
                "KeyType": "PaymentId"
            }
            
            try:
                resp = requests.post(url, headers=headers, json=payload)
            except Exception as exc:
                raise ValidationError(_("Failed to connect to MyFatoorah: %s") % str(exc))

            if resp.status_code != 200:
                raise ValidationError(_("Failed to fetch payment details from MyFatoorah (status code %s).") % resp.status_code)

            payment_data = resp.json().get("Data", {})
            status = payment_data.get("InvoiceStatus")
            
            transactions = payment_data.get("InvoiceTransactions", [])
            currency = "SAR"
            amount = 0
            if transactions:
                currency = transactions[0].get("Currency", "SAR")
                amount = float(transactions[0].get("TransationValue", 0))

            if currency != "SAR":
                raise ValidationError(_("Invalid payment currency: %s") % currency)

            expected_amount = order.total
            if abs(amount - expected_amount) > 0.1:
                raise ValidationError(_("Payment amount mismatch. Expected %s, got %s.") % (expected_amount, amount))

            if status == "Paid":
                tx = request.env["jabin.customer.service"].sudo().process_payment_transaction(
                    order_id=order.id,
                    status="paid",
                    ref=payment_id,
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
                    "delivery_fee": getattr(order, "delivery_fee", 0.0),
                    "total": order.total,
                }, message=_("Payment verified and order confirmed successfully.")))
            else:
                failure_reason = _("Payment not completed (Status: %s).") % status
                tx = request.env["jabin.customer.service"].sudo().process_payment_transaction(
                    order_id=order.id,
                    status="failed",
                    ref=payment_id,
                    failure_reason=failure_reason
                )
                ctx.set_body(ResponseBuilder.error(
                    message=_("Payment verification failed: %s") % failure_reason,
                    code=400,
                    data={
                        "order_id": order.id,
                        "payment_status": "failed",
                        "transaction_id": tx.id
                    }
                ))
        return ctx.response
