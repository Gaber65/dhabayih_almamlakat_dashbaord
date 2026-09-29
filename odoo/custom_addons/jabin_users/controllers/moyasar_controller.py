import json
import logging
from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError
from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder
from ..services.moyasar_service import MoyasarService

_logger = logging.getLogger(__name__)


def _parse_body():
    raw = request.httprequest.data
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
    return {k: v for k, v in request.httprequest.form.items()}


class MoyasarController(BaseApiController):
    """Moyasar Gateway Controller supporting Mada, Apple Pay, Credit Cards, and STC Pay."""

    @http.route(
        [
            "/api/v1/payments/moyasar/initiate",
            "/api/v1/payments/initiate",
            "/api/v1/payments/myfatoorah/initiate",
        ],
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def initiate_payment(self, **kwargs):
        """Initiate payment session with Moyasar (Invoices API)."""
        with self.handle() as ctx:
            data = _parse_body()
            order_id = data.get("order_id") or kwargs.get("order_id")
            if not order_id:
                raise ValidationError(_("order_id is required."))

            order = request.env["jabin.order"].sudo().browse(int(order_id))
            if not order.exists():
                raise ValidationError(_("Order not found."))

            base_url = request.httprequest.host_url.rstrip('/')
            default_callback = f"{base_url}/api/v1/payments/moyasar/callback"

            callback_url = data.get("callback_url") or default_callback
            error_url = data.get("error_url") or default_callback
            payment_method_code = data.get("payment_method_code") or "moyasar"

            res = MoyasarService.initiate_payment(
                request.env,
                order,
                callback_url=callback_url,
                error_url=error_url,
                payment_method_code=payment_method_code,
            )

            ctx.set_body(
                ResponseBuilder.success(
                    data=res,
                    message=_("Payment session initialized successfully with Moyasar"),
                )
            )
        return ctx.response

    @http.route(
        [
            "/api/v1/payments/moyasar/verify",
            "/api/v1/payments/verify",
            "/api/v1/payment/verify",
            "/api/v1/payments/myfatoorah/verify",
        ],
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def verify_payment(self, **kwargs):
        """Verify payment transaction status with Moyasar gateway."""
        with self.handle() as ctx:
            data = _parse_body()
            payment_id = (
                data.get("payment_id")
                or data.get("paymentId")
                or data.get("id")
                or kwargs.get("paymentId")
                or kwargs.get("id")
            )
            order_id = data.get("order_id") or kwargs.get("order_id")

            if not payment_id:
                raise ValidationError(_("payment_id or invoice_id is required for verification."))

            # Check if the payment_id is a fallback marker (e.g. "order_XX_paid")
            # from the Flutter WebView when no real Moyasar ID was available.
            # In this case, check the order status directly.
            is_fallback = str(payment_id).startswith("order_") and str(payment_id).endswith("_paid")

            if is_fallback and order_id:
                order = request.env["jabin.order"].sudo().browse(int(order_id))
                if order.exists() and order.payment_status == "paid":
                    res = {
                        "success": True,
                        "status": "paid",
                        "payment_status": "paid",
                        "state": order.state,
                        "order_id": order.id,
                        "order_number": order.name,
                        "amount": order.total,
                        "payment_id": payment_id,
                    }
                else:
                    # Try Moyasar verification as last resort — look for paid transaction
                    tx = request.env["jabin.payment.transaction"].sudo().search([
                        ("order_id", "=", int(order_id)),
                        ("status", "=", "paid")
                    ], limit=1)
                    if tx:
                        res = {
                            "success": True,
                            "status": "paid",
                            "payment_status": "paid",
                            "state": "confirmed",
                            "order_id": int(order_id),
                            "order_number": order.name if order.exists() else "",
                            "amount": tx.amount,
                            "payment_id": tx.transaction_ref or payment_id,
                        }
                    else:
                        res = {
                            "success": False,
                            "message": "Payment not yet confirmed. Please wait or try again.",
                        }
            else:
                res = MoyasarService.verify_payment(
                    request.env,
                    payment_id=str(payment_id),
                    expected_order_id=int(order_id) if order_id else None,
                )

            if res.get("success"):
                ctx.set_body(
                    ResponseBuilder.success(
                        data=res,
                        message=_("Payment verified successfully and order is confirmed."),
                    )
                )
            else:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=res.get("message") or _("Payment verification failed."),
                        code=400,
                        data=res,
                    )
                )
        return ctx.response

    @http.route(
        [
            "/api/v1/payments/moyasar/callback",
            "/api/v1/payments/myfatoorah/callback",
        ],
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
        cors="*",
    )
    def payment_callback(self, **kwargs):
        """Browser redirect callback from Moyasar after customer payment."""
        payment_id = kwargs.get("id") or kwargs.get("paymentId") or kwargs.get("payment_id")
        order_id = kwargs.get("order_id")
        status_param = kwargs.get("status")

        success = False
        order_num = ""
        msg = ""
        verified_order_id = order_id

        if payment_id:
            res = MoyasarService.verify_payment(
                request.env,
                payment_id=str(payment_id),
                expected_order_id=int(order_id) if order_id else None,
            )
            success = res.get("success", False)
            order_num = res.get("order_number", "")
            msg = res.get("message", "")
            verified_order_id = res.get("order_id") or order_id
        elif status_param == "paid" and order_id:
            # Moyasar may redirect without a payment_id but with status=paid
            # Try to verify by checking order status
            try:
                order = request.env["jabin.order"].sudo().browse(int(order_id))
                if order.exists() and order.payment_status == "paid":
                    success = True
                    order_num = order.name
                    verified_order_id = order.id
            except Exception:
                pass

        # Try to detect frontend origin and redirect there instead of rendering HTML
        frontend_base = kwargs.get("frontend_url") or kwargs.get("redirect_to")

        if not frontend_base:
            # Check config parameter
            configured_fe = request.env["ir.config_parameter"].sudo().get_param("jabin.frontend_url")
            if configured_fe:
                frontend_base = configured_fe.rstrip('/')

        if not frontend_base:
            # Check Referer/Origin headers
            referer = request.httprequest.headers.get("Referer", "")
            origin = request.httprequest.headers.get("Origin", "")
            for url in [referer, origin]:
                if url and (":5173" in url or ":3000" in url or ":8080" in url or "localhost" in url):
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    frontend_base = f"{parsed.scheme}://{parsed.netloc}"
                    break

        if not frontend_base:
            # If request host is local network or localhost, derive default React frontend url
            req_host = request.httprequest.host.split(":")[0]
            if req_host in ("localhost", "127.0.0.1") or req_host.startswith("192.168.") or req_host.startswith("10."):
                frontend_base = f"http://{req_host}:5173"

        if frontend_base:
            # Redirect to the frontend's payment callback page
            redirect_params = f"order_id={verified_order_id or ''}"
            if payment_id:
                redirect_params += f"&id={payment_id}"
            if success:
                redirect_params += "&status=paid"

            redirect_url = f"{frontend_base}/payment/callback?{redirect_params}"
            return request.redirect(redirect_url, code=302)

        # Fallback: render inline HTML status page
        status_text = "تم تأكيد طلبك بنجاح!" if success else "تعذر إتمام عملية الدفع"
        badge_bg = "#ecfdf5" if success else "#fef2f2"
        badge_color = "#059669" if success else "#dc2626"
        icon_svg = (
            """<svg class="icon success" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
            </svg>"""
            if success
            else """<svg class="icon failed" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>"""
        )

        html_status = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>حالة الدفع | ذبائح المملكة</title>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Tajawal', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #f8fafc;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 20px;
        }}
        .card {{
            background: white;
            padding: 40px 30px;
            border-radius: 24px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05);
            text-align: center;
            max-width: 440px;
            width: 100%;
        }}
        .icon-box {{
            width: 80px;
            height: 80px;
            border-radius: 50%;
            background: {badge_bg};
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 24px;
        }}
        .icon {{
            width: 40px;
            height: 40px;
            stroke: {badge_color};
        }}
        h2 {{
            color: #1e293b;
            font-size: 22px;
            font-weight: 700;
            margin-bottom: 12px;
        }}
        p {{
            color: #64748b;
            font-size: 15px;
            line-height: 1.6;
            margin-bottom: 24px;
        }}
        .details {{
            background: #f8fafc;
            border-radius: 14px;
            padding: 16px;
            margin-bottom: 28px;
            text-align: right;
            font-size: 14px;
            color: #334155;
        }}
        .details-row {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
        }}
        .details-row:last-child {{ margin-bottom: 0; }}
        .btn {{
            display: block;
            width: 100%;
            padding: 14px;
            background: #0f172a;
            color: white;
            text-decoration: none;
            border-radius: 12px;
            font-weight: 600;
            font-size: 15px;
            transition: all 0.2s;
        }}
        .btn:hover {{ background: #1e293b; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon-box">
            {icon_svg}
        </div>
        <h2>{status_text}</h2>
        <p>{"شكراً لك! تم استلام دفعتك عبر ميسر وتم تحويل طلبك للتجهيز مباشرة." if success else "نعتذر، تعذر إتمام العملية. يمكنك إعادة المحاولة مجدداً."}</p>
        
        <div class="details">
            <div class="details-row">
                <span style="color: #64748b;">رقم المرجع:</span>
                <span style="font-weight: 600; font-family: monospace;">{payment_id or '—'}</span>
            </div>
            {f'<div class="details-row"><span style="color: #64748b;">رقم الطلب:</span><span style="font-weight: 600;">{order_num}</span></div>' if order_num else ''}
        </div>

        <a href="/" class="btn">العودة للتطبيق / المتجر</a>
    </div>
</body>
</html>
"""
        return request.make_response(html_status, headers=[("Content-Type", "text/html; charset=utf-8")])

    @http.route(
        "/api/v1/payments/moyasar/webhook",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def moyasar_webhook(self, **kwargs):
        """Asynchronous webhook listener from Moyasar (for events like payment_paid)."""
        data = _parse_body()
        _logger.info("Received Moyasar Webhook event: %s", data.get("type"))

        # Moyasar sends payload with 'id', 'type' (e.g. 'payment_paid'), and 'data' object
        event_type = data.get("type")
        payment_info = data.get("data") or {}
        payment_id = payment_info.get("id") or data.get("id")

        if payment_id and event_type in (
            "payment_paid", "payment.paid", "paid",
            "payment_refunded", "payment.refunded", "refunded",
            "invoice.paid", "invoice.refunded"
        ):
            try:
                res = MoyasarService.verify_payment(request.env, payment_id=str(payment_id), force_check=True)
                _logger.info("Moyasar Webhook processed event '%s' for payment %s: %s", event_type, payment_id, res.get("success"))
            except Exception as e:
                _logger.error("Error processing Moyasar Webhook: %s", e)

        return request.make_response(
            json.dumps({"status": "received"}),
            headers=[("Content-Type", "application/json")]
        )
