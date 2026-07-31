from odoo import http, _
from odoo.http import request
from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder


class PaymentMethodController(BaseApiController):
    """Payment Methods REST API Controller."""

    @http.route(
        "/api/v1/payment-methods",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
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
