import json
from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError
from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder
from odoo.addons.jabin_security.utils.token_auth import require_token
from ..services.moyasar_service import MoyasarService


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
    """Payment Methods & Transactions REST API Controller (Moyasar Active Gateway)."""

    @http.route(
        "/api/v1/payment-methods",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        cors="*",
    )
    def list_payment_methods(self, **kwargs):
        """List active payment methods, excluding deprecated MyFatoorah."""
        with self.handle() as ctx:
            all_param = kwargs.get("all") or kwargs.get("include_inactive")
            Model = request.env["jabin.payment.method"].sudo()

            # Ensure COD is active
            cod_record = Model.with_context(active_test=False).search([("code", "=", "cod")], limit=1)
            if cod_record and not cod_record.active:
                cod_record.write({"active": True})

            # Ensure any legacy / unsupported payment method record is deactivated (strictly Moyasar and COD allowed)
            unsupported = Model.search([
                ("code", "not in", ("moyasar", "cod")),
            ])
            if unsupported:
                unsupported.write({"active": False})

            if all_param and str(all_param).lower() in ("true", "1", "yes"):
                methods = Model.with_context(active_test=False).search([
                    ("code", "in", ("moyasar", "cod")),
                ], order="name")
            else:
                methods = Model.search([
                    ("active", "=", True),
                    ("code", "in", ("moyasar", "cod")),
                ], order="name")

            res = []
            for m in methods:
                res.append({
                    "id": m.id,
                    "name": m.name,
                    "code": m.code,
                    "payment_type": m.payment_type,
                    "provider": "moyasar" if m.payment_type in ("card", "wallet") and m.code != "cod" else m.provider,
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
        """Create a new payment method (Moyasar / Manual / Installment)."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            vals = _parse_json_body()
            name = str(vals.get("name") or "").strip()
            code = str(vals.get("code") or "").strip().lower()
            provider = str(vals.get("provider") or "moyasar").strip().lower()
            if not name or not code:
                ctx.set_body(ResponseBuilder.bad_request(message=_("Name and code are required.")))
                return ctx.response

            if code == "myfatoorah" or provider == "myfatoorah":
                ctx.set_body(ResponseBuilder.bad_request(
                    message=_("بوابة ماي فاتورة غير مدعومة، البوابة المعتمدة هي ميسر (Moyasar).")
                ))
                return ctx.response

            create_vals = {
                "name": name,
                "code": code,
                "payment_type": vals.get("payment_type", "card"),
                "provider": provider,
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
            method = request.env["jabin.payment.method"].sudo().with_context(active_test=False).browse(method_id)
            if not method.exists():
                ctx.set_body(ResponseBuilder.not_found(message=_("Payment method not found.")))
                return ctx.response

            vals = _parse_json_body()
            if str(vals.get("provider") or "").lower() == "myfatoorah" or method.code == "myfatoorah":
                ctx.set_body(ResponseBuilder.bad_request(
                    message=_("بوابة ماي فاتورة متوقفة، البوابة المعتمدة هي ميسر (Moyasar).")
                ))
                return ctx.response

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
            method = request.env["jabin.payment.method"].sudo().with_context(active_test=False).browse(method_id)
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
        """List payment transactions with filters for admin dashboard (preserving historical records)."""
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
        """Verify payment with Moyasar gateway and update order status."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            data = _parse_json_body()
            order_id = data.get("order_id")
            payment_id = data.get("payment_id") or data.get("paymentId") or data.get("id")

            if not payment_id:
                raise ValidationError(_("معرف عملية الدفع مطلوب للتحقق."))

            res = MoyasarService.verify_payment(
                request.env,
                payment_id=str(payment_id),
                expected_order_id=int(order_id) if order_id else None,
            )

            if res.get("success"):
                ctx.set_body(ResponseBuilder.success(
                    data=res,
                    message=_("تم التحقق من الدفع عبر ميسر وتأكيد الطلب بنجاح.")
                ))
            else:
                ctx.set_body(ResponseBuilder.error(
                    message=res.get("message") or _("فشل التحقق من عملية الدفع عبر ميسر."),
                    code=400,
                    data=res
                ))
        return ctx.response
