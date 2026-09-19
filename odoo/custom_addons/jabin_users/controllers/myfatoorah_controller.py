import json
import logging
from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError
from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder
from ..services.myfatoorah_service import MyFatoorahService

_logger = logging.getLogger(__name__)

def _parse_body():
    raw = request.httprequest.data
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
    return {k: v for k, v in request.httprequest.form.items()}

class MyFatoorahController(BaseApiController):
    """MyFatoorah Gateway Controller for Online Card, Mada, and Apple Pay payments."""

    @http.route(
        "/api/v1/payments/myfatoorah/initiate",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def initiate_myfatoorah_payment(self, **kwargs):
        """Initiate MyFatoorah payment session for an order."""
        with self.handle() as ctx:
            data = _parse_body()
            order_id = data.get("order_id")
            if not order_id:
                raise ValidationError(_("order_id is required."))

            order = request.env["jabin.order"].sudo().browse(int(order_id))
            if not order.exists():
                raise ValidationError(_("Order not found."))

            # Base url for callbacks
            base_url = request.httprequest.host_url.rstrip('/')
            default_callback = f"{base_url}/api/v1/payments/myfatoorah/callback"
            default_error = f"{base_url}/api/v1/payments/myfatoorah/callback"

            callback_url = data.get("callback_url") or default_callback
            error_url = data.get("error_url") or default_error
            payment_method_code = data.get("payment_method_code") or "myfatoorah"

            res = MyFatoorahService.initiate_payment(
                request.env,
                order,
                callback_url=callback_url,
                error_url=error_url,
                payment_method_code=payment_method_code,
            )

            ctx.set_body(
                ResponseBuilder.success(
                    data=res,
                    message=_("Payment session initialized successfully"),
                )
            )
        return ctx.response

    @http.route(
        ["/api/v1/payments/myfatoorah/verify", "/api/v1/payments/verify"],
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def verify_payment(self, **kwargs):
        """Verify payment transaction status with MyFatoorah."""
        with self.handle() as ctx:
            data = _parse_body()
            payment_id = data.get("payment_id") or data.get("paymentId") or kwargs.get("paymentId")
            order_id = data.get("order_id") or kwargs.get("order_id")

            if not payment_id:
                raise ValidationError(_("payment_id is required for verification."))

            res = MyFatoorahService.verify_payment(
                request.env,
                payment_id=str(payment_id),
                expected_order_id=int(order_id) if order_id else None
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
                        data=res
                    )
                )
        return ctx.response

    @http.route(
        "/api/v1/payments/myfatoorah/callback",
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
        cors="*",
    )
    def myfatoorah_callback(self, **kwargs):
        """Browser redirect callback from MyFatoorah after customer payment."""
        payment_id = kwargs.get("paymentId") or kwargs.get("Id")
        order_id = kwargs.get("order_id")

        if payment_id:
            res = MyFatoorahService.verify_payment(
                request.env,
                payment_id=str(payment_id),
                expected_order_id=int(order_id) if order_id else None
            )
            success = res.get("success", False)
            order_num = res.get("order_number", "")
        else:
            success = False
            order_num = ""

        # Return a pleasant branded status response page with auto-redirect to app/web
        html_status = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>نتيجة الدفع - ذبائح المملكة</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; color: #0f172a; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }}
        .card {{ background: white; border-radius: 24px; padding: 36px 28px; max-width: 440px; width: 100%; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.08); border: 1px solid #e2e8f0; }}
        .icon {{ width: 72px; height: 72px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 20px; font-size: 32px; }}
        .icon.success {{ background: #ecfdf5; color: #059669; }}
        .icon.fail {{ background: #fef2f2; color: #dc2626; }}
        h2 {{ margin: 0 0 10px; font-size: 22px; font-weight: 800; }}
        p {{ margin: 0 0 24px; color: #64748b; font-size: 14px; line-height: 1.6; }}
        .btn {{ display: block; width: 100%; padding: 14px; border-radius: 16px; font-weight: 700; font-size: 15px; text-decoration: none; box-sizing: border-box; transition: all 0.2s; }}
        .btn-success {{ background: #8b1d24; color: white; }}
        .btn-retry {{ background: #f1f5f9; color: #334155; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon {'success' if success else 'fail'}">
            {'✓' if success else '✕'}
        </div>
        <h2>{'تم الدفع وتأكيد طلبك بنجاح!' if success else 'تعذر إتمام عملية الدفع'}</h2>
        <p>{'رقم الطلب: ' + order_num + '<br/>تم تحويل الطلب لقسم التجهيز وسيصلك مبرداً في الموعد.' if success else 'لم يتم خصم أي مبلغ أو لم تكتمل العملية. يمكنك إعادة المحاولة بأمان.'}</p>
        <a href="/order-success" class="btn btn-success">{'متابعة تفاصيل الطلب' if success else 'العودة لصفحة الدفع'}</a>
    </div>
    <script>
        // Post message to parent iframe or app webview
        try {{
            if (window.ReactNativeWebView) {{
                window.ReactNativeWebView.postMessage(JSON.stringify({{'success': {str(success).lower()}, 'order_number': '{order_num}'}}));
            }}
            if (window.parent) {{
                window.parent.postMessage({{'type': 'MYFATOORAH_PAYMENT', 'success': {str(success).lower()}, 'order_number': '{order_num}'}}, '*');
            }}
        }} catch(e) {{}}
    </script>
</body>
</html>"""
        return request.make_response(html_status, headers=[('Content-Type', 'text/html; charset=utf-8')])
