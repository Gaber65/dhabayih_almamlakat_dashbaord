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
    raw = request.httprequest.data
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise ValidationError(_("Invalid JSON payload."))


class PaymentMethodController(BaseApiController):
    """Payment Methods REST API Controller."""

    @http.route(
        "/api/v1/payment-methods",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        cors="*",
    )
    def list_payment_methods(self, **kwargs):
        """List all active payment methods."""
        with self.handle() as ctx:
            methods = request.env["jabin.payment.method"].sudo().search([("active", "=", True)], order="name")
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
                })
            ctx.set_body(ResponseBuilder.success(data=res, message=_("Payment methods retrieved successfully.")))
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
        """Verify payment with Moyasar and update order status."""
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

            # Read MyFatoorah API Token
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
