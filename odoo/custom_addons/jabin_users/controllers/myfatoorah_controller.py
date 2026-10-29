import json
import logging
from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError
from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder
from odoo.addons.jabin_security.utils.token_auth import require_token
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


class MyFatoorahController(BaseApiController):
    """
    Legacy MyFatoorah route compatibility handler.
    MyFatoorah is removed from active use; all active verification routes delegate to MoyasarService.
    """

    @http.route(
        "/api/v1/payments/myfatoorah/initiate",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def initiate_myfatoorah_payment(self, **kwargs):
        """Reject new MyFatoorah payment initiation; Moyasar is the sole active gateway."""
        with self.handle() as ctx:
            ctx.set_body(
                ResponseBuilder.error(
                    message=_("بوابة ماي فاتورة متوقفة، البوابة المعتمدة للدفع الإلكتروني هي ميسر (Moyasar)."),
                    code=400,
                )
            )
        return ctx.response

    @http.route(
        "/api/v1/payments/myfatoorah/verify",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def verify_payment(self, **kwargs):
        """Delegate verification to MoyasarService."""
        with self.handle() as ctx:
            data = _parse_body()
            payment_id = data.get("payment_id") or data.get("paymentId") or kwargs.get("paymentId")
            order_id = data.get("order_id") or kwargs.get("order_id")

            if not payment_id:
                raise ValidationError(_("payment_id is required for verification."))

            res = MoyasarService.verify_payment(
                request.env,
                payment_id=str(payment_id),
                expected_order_id=int(order_id) if order_id else None
            )

            if res.get("success"):
                ctx.set_body(
                    ResponseBuilder.success(
                        data=res,
                        message=_("تم التحقق من الدفع وتأكيد الطلب بنجاح."),
                    )
                )
            else:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=res.get("message") or _("فشل التحقق من عملية الدفع."),
                        code=400,
                        data=res
                    )
                )
        return ctx.response
