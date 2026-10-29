import json
import logging
import os
import requests
from typing import Dict, Any, Optional
from odoo import _, fields
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


def _is_valid_pk(key: str) -> bool:
    k = (key or "").strip()
    return (k.startswith("pk_test_") or k.startswith("pk_live_")) and len(k) > 12 and "placeholder" not in k.lower() and "dummy" not in k.lower()


def _is_valid_sk(key: str) -> bool:
    k = (key or "").strip()
    return (k.startswith("sk_test_") or k.startswith("sk_live_")) and len(k) > 12 and "placeholder" not in k.lower() and "dummy" not in k.lower()


class MoyasarService:
    """Enterprise Moyasar Payment Gateway Integration Service (Mada, Apple Pay, Visa/Mastercard, STC Pay)."""

    BASE_URL = "https://api.moyasar.com/v1"

    @classmethod
    def _get_config(cls, env) -> Dict[str, str]:
        params = env['ir.config_parameter'].sudo()
        env_mode = (
            os.environ.get('MOYASAR_ENV')
            or params.get_param('moyasar.environment', 'live')
            or 'live'
        ).strip().lower()

        raw_pk = (
            os.environ.get('MOYASAR_PUBLISHABLE_KEY')
            or params.get_param('moyasar.publishable_key', '')
            or (params.get_param('moyasar.live_pk', '') if env_mode == 'live' else params.get_param('moyasar.test_pk', ''))
            or ''
        ).strip()

        raw_sk = (
            os.environ.get('MOYASAR_SECRET_KEY')
            or params.get_param('moyasar.secret_key', '')
            or (params.get_param('moyasar.live_sk', '') if env_mode == 'live' else params.get_param('moyasar.test_sk', ''))
            or ''
        ).strip()

        # Clean up legacy seeded placeholder strings if present in DB
        if raw_pk in ('dummy_public_key_placeholder', 'your_publishable_key'):
            params.set_param('moyasar.publishable_key', '')
            raw_pk = ''
        if raw_sk in ('dummy_secret_key_placeholder', 'your_secret_key'):
            params.set_param('moyasar.secret_key', '')
            raw_sk = ''

        pk = raw_pk if _is_valid_pk(raw_pk) else ''
        sk = raw_sk if _is_valid_sk(raw_sk) else ''

        return {
            'publishable_key': pk,
            'secret_key': sk,
            'env_mode': env_mode,
            'base_url': cls.BASE_URL,
            'is_configured': bool(pk and sk),
        }

    @classmethod
    def initiate_payment(
        cls,
        env,
        order,
        callback_url: str,
        error_url: str = "",
        payment_method_code: str = 'moyasar'
    ) -> Dict[str, Any]:
        """
        Initiates a Moyasar payment invoice session.
        Order remains in 'pending_payment' state until verified.
        """
        config = cls._get_config(env)
        order_total = round(float(getattr(order, "total", getattr(order, "total_amount", 0.0)) or 0.0), 2)
        if order_total <= 0:
            raise ValidationError(_("إجمالي الطلب صفر، لا يلزم إجراء دفع إلكتروني."))

        # Moyasar requires amount in minor currency units (Halalas for SAR), minimum 100 Halalas (1.00 SAR)
        amount_minor = int(round(order_total * 100))
        if amount_minor < 100:
            raise ValidationError(_("الحد الأدنى للدفع الإلكتروني عبر بوابة ميسر هو 1.00 ر.س (100 هللة)."))

        if not config['secret_key']:
            raise ValidationError(
                _("مفتاح الربط السري لبوابة ميسر (moyasar.secret_key) غير مضبوط في إعدادات النظام.")
            )

        endpoint = f"{config['base_url']}/invoices"
        auth = (config['secret_key'], '')
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        description = f"طلب ذبائح المملكة #{order.name}"
        payload = {
            "amount": amount_minor,
            "currency": "SAR",
            "description": description,
            "callback_url": callback_url,
            "success_url": callback_url,
            "metadata": {
                "order_id": str(order.id),
                "order_number": str(order.name),
                "customer_id": str(order.customer_id.id if order.customer_id else ""),
            }
        }
        if error_url:
            payload["back_url"] = error_url
        elif callback_url:
            payload["back_url"] = callback_url

        _logger.info("Initiating Moyasar invoice for Order ID %s (%s Halalas)", order.id, amount_minor)

        try:
            resp = requests.post(endpoint, json=payload, headers=headers, auth=auth, timeout=20)
            data = resp.json()
        except requests.RequestException as exc:
            _logger.error("Failed to connect to Moyasar API: %s", exc)
            raise ValidationError(_("تعذر الاتصال ببوابة الدفع ميسر، يرجى التحقق من الاتصال والمحاولة مجدداً."))

        if resp.status_code not in (200, 201):
            error_msg = data.get("message") or "تعذر إنشاء جلسة الدفع عبر ميسر."
            _logger.error("Moyasar payment initiation rejected (%s): %s", resp.status_code, data)
            raise ValidationError(_("خطأ من بوابة الدفع ميسر: %s") % error_msg)

        invoice_id = data.get("id")
        payment_url = data.get("url")

        # Create or update pending transaction in Odoo
        try:
            tx = env["jabin.payment.transaction"].sudo().search([
                ("order_id", "=", order.id),
                ("status", "=", "pending")
            ], limit=1)

            pm = env["jabin.payment.method"].sudo().search([
                ("provider", "=", "moyasar"),
                ("code", "!=", "myfatoorah"),
            ], limit=1)
            if not pm:
                pm = order.payment_method_id

            if tx:
                tx.sudo().write({
                    "transaction_ref": invoice_id or tx.transaction_ref,
                    "amount": order_total,
                })
            else:
                env["jabin.payment.transaction"].sudo().create({
                    "order_id": order.id,
                    "customer_id": order.customer_id.id,
                    "payment_method_id": pm.id if pm else order.payment_method_id.id,
                    "amount": order_total,
                    "status": "pending",
                    "transaction_ref": invoice_id or f"inv_{order.id}",
                })
        except Exception as tx_err:
            _logger.warning("Could not create/update pending transaction record: %s", tx_err)

        return {
            "invoice_id": invoice_id,
            "payment_url": payment_url,
            "publishable_key": config["publishable_key"],
            "amount_minor_units": amount_minor,
            "currency": "SAR",
            "order_id": order.id,
            "order_number": order.name,
        }

    @classmethod
    def verify_payment(
        cls,
        env,
        payment_id: str,
        expected_order_id: Optional[int] = None,
        force_check: bool = False,
    ) -> Dict[str, Any]:
        """
        Secure server-to-server verification of a Moyasar payment or invoice.
        Fetches payment details using secret key via HTTP Basic Auth.
        """
        if not payment_id:
            return {"success": False, "message": "معرف عملية الدفع مطلوب للتحقق."}

        # 0. Early idempotent check: if the order is already marked paid in DB, return success immediately
        if expected_order_id and not force_check:
            try:
                existing_order = env["jabin.order"].sudo().browse(int(expected_order_id))
                if existing_order.exists() and existing_order.payment_status == "paid":
                    _logger.info("Order %s is already marked as paid in database.", expected_order_id)
                    ord_total = float(getattr(existing_order, "total", getattr(existing_order, "total_amount", 0.0)))
                    return {
                        "success": True,
                        "status": "paid",
                        "payment_status": "paid",
                        "state": existing_order.state,
                        "order_id": existing_order.id,
                        "order_number": existing_order.name,
                        "total": ord_total,
                        "subtotal": float(getattr(existing_order, "subtotal", ord_total)),
                        "discount_amount": float(getattr(existing_order, "discount_amount", 0.0)),
                        "points_redeemed": int(getattr(existing_order, "points_redeemed", 0)),
                        "loyalty_discount_amount": float(getattr(existing_order, "loyalty_discount_amount", 0.0)),
                        "amount": ord_total,
                        "payment_id": str(payment_id),
                    }
            except Exception as e:
                _logger.warning("Error checking pre-existing order status: %s", e)

        config = cls._get_config(env)
        if not config['secret_key']:
            return {
                "success": False,
                "message": "مفتاح الربط السري لبوابة ميسر (moyasar.secret_key) غير مضبوط على الخادم للتحقق من الدفع.",
                "payment_id": payment_id,
            }

        auth = (config['secret_key'], '')
        headers = {"Accept": "application/json"}

        _logger.info("Verifying Moyasar reference %s (expected_order_id=%s, force_check=%s)", payment_id, expected_order_id, force_check)

        # 1. Try checking as a Payment ID directly
        payment_endpoint = f"{config['base_url']}/payments/{payment_id}"
        payment_data = None
        status = None
        amount_halalas = 0
        currency = "SAR"
        order_meta_id = None

        try:
            resp = requests.get(payment_endpoint, headers=headers, auth=auth, timeout=15)
            if resp.status_code == 200:
                payment_data = resp.json()
                status = payment_data.get("status")
                amount_halalas = payment_data.get("amount", 0)
                currency = payment_data.get("currency", "SAR")
                metadata = payment_data.get("metadata") or {}
                order_meta_id = metadata.get("order_id")
        except Exception as e:
            _logger.warning("Moyasar payment fetch failed, will try invoice endpoint: %s", e)

        # 2. If not found or status isn't decisive, check as an Invoice ID
        if not payment_data or status not in ("paid", "authorized", "captured", "refunded"):
            try:
                invoice_endpoint = f"{config['base_url']}/invoices/{payment_id}"
                inv_resp = requests.get(invoice_endpoint, headers=headers, auth=auth, timeout=15)
                if inv_resp.status_code == 200:
                    inv_data = inv_resp.json()
                    inv_status = inv_data.get("status")
                    amount_halalas = inv_data.get("amount", 0)
                    currency = inv_data.get("currency", "SAR")
                    metadata = inv_data.get("metadata") or {}
                    order_meta_id = metadata.get("order_id")
                    if inv_status in ("paid", "refunded"):
                        status = inv_status
                    payments_list = inv_data.get("payments", [])
                    if payments_list:
                        last_p = payments_list[-1]
                        p_status = last_p.get("status")
                        if p_status in ("paid", "authorized", "captured", "refunded"):
                            status = p_status
                            payment_data = last_p
            except Exception as e:
                _logger.warning("Moyasar invoice fetch failed: %s", e)

        if not status:
            target_oid = expected_order_id or (int(order_meta_id) if order_meta_id and str(order_meta_id).isdigit() else None)
            if target_oid:
                try:
                    unpaid_ord = env["jabin.order"].sudo().browse(int(target_oid))
                    if unpaid_ord.exists() and unpaid_ord.payment_status != "paid" and unpaid_ord.state in ("draft", "pending_payment", "confirmed"):
                        try:
                            env["jabin.customer.service"].sudo().trigger_status_transition(
                                unpaid_ord.id,
                                "cancelled",
                                description="Order automatically cancelled because online payment was not completed."
                            )
                        except Exception:
                            pass
                        unpaid_ord.sudo().write({"payment_status": "cancelled", "state": "cancelled"})
                except Exception as cancel_err:
                    _logger.warning("Failed to auto-cancel incomplete order %s: %s", target_oid, cancel_err)

            return {
                "success": False,
                "status": "cancelled",
                "payment_status": "cancelled",
                "state": "cancelled",
                "message": "لم يتم العثور على عملية الدفع في بوابة ميسر أو تم إلغاء العملية.",
                "payment_id": payment_id
            }

        if currency and str(currency).upper() != "SAR":
            return {
                "success": False,
                "message": f"عملة الدفع غير صالحة ({currency})، يجب أن تكون بالريال السعودي (SAR).",
                "payment_id": payment_id,
            }

        # 3. Locate target order in Odoo
        order = None
        if expected_order_id:
            if order_meta_id and str(order_meta_id).isdigit() and int(order_meta_id) != int(expected_order_id):
                return {
                    "success": False,
                    "message": "عملية الدفع لا تطابق رقم الطلب الحالي.",
                    "payment_id": payment_id,
                }
            order = env["jabin.order"].sudo().browse(int(expected_order_id))
        elif order_meta_id and str(order_meta_id).isdigit():
            order = env["jabin.order"].sudo().browse(int(order_meta_id))

        if not order or not order.exists():
            return {
                "success": False,
                "message": "لم يتم العثور على الطلب المرتبط بعملية الدفع.",
                "payment_id": payment_id,
            }

        paid_amount_sar = round(float(amount_halalas) / 100.0, 2)
        order_total = round(float(getattr(order, "total", getattr(order, "total_amount", 0.0))), 2)

        # 4. Verify payment status
        if status in ("paid", "authorized", "captured") and not (payment_data and payment_data.get("refunded", 0) > 0):
            # Security check: Amount must match within reasonable tolerance (1.0 SAR)
            if abs(order_total - paid_amount_sar) > 1.0 and paid_amount_sar > 0:
                _logger.critical(
                    "Security Mismatch! Order %s total is %s SAR, but Moyasar received %s SAR",
                    order.id, order_total, paid_amount_sar
                )
                return {
                    "success": False,
                    "message": "المبلغ المدفوع لا يطابق إجمالي الطلب.",
                    "order_id": order.id,
                }

            write_vals = {"payment_status": "paid"}
            if order.state in ("draft", "pending_payment"):
                write_vals["state"] = "confirmed"
            order.sudo().write(write_vals)

            pm = env["jabin.payment.method"].sudo().search([
                ("provider", "=", "moyasar"),
                ("code", "!=", "myfatoorah"),
            ], limit=1)
            tx = env["jabin.payment.transaction"].sudo().search([
                ("order_id", "=", order.id),
                "|",
                ("transaction_ref", "=", str(payment_id)),
                ("status", "=", "pending"),
            ], limit=1)
            if tx:
                tx.sudo().write({
                    "status": "paid",
                    "transaction_ref": str(payment_id),
                    "paid_date": fields.Datetime.now(),
                    "amount": paid_amount_sar,
                })
            else:
                tx = env["jabin.payment.transaction"].sudo().create({
                    "order_id": order.id,
                    "customer_id": order.customer_id.id,
                    "payment_method_id": pm.id if pm else order.payment_method_id.id,
                    "amount": paid_amount_sar,
                    "status": "paid",
                    "transaction_ref": str(payment_id),
                    "paid_date": fields.Datetime.now(),
                })

            try:
                if "jabin.notification.service" in env:
                    env["jabin.notification.service"].send_payment_success(env, order, tx)
                    env["jabin.notification.service"].send_order_created(env, order)
            except Exception as notif_err:
                _logger.warning("Could not send payment notification: %s", notif_err)

            try:
                active_cart = env["jabin.cart"].sudo().search([
                    ("customer_id", "=", order.customer_id.id),
                    ("status", "=", "active")
                ], limit=1)
                if active_cart:
                    active_cart.sudo().write({
                        "status": "checked_out",
                        "checked_out_order_id": order.id
                    })
            except Exception as cart_err:
                _logger.warning("Error closing cart after payment: %s", cart_err)

            return {
                "success": True,
                "status": "paid",
                "payment_status": "paid",
                "state": "confirmed",
                "order_id": order.id,
                "order_number": order.name,
                "total": order_total,
                "subtotal": float(getattr(order, "subtotal", order_total)),
                "discount_amount": float(getattr(order, "discount_amount", 0.0)),
                "points_redeemed": int(getattr(order, "points_redeemed", 0)),
                "loyalty_discount_amount": float(getattr(order, "loyalty_discount_amount", 0.0)),
                "amount": paid_amount_sar,
                "payment_id": payment_id,
            }
        elif status == "refunded" or (payment_data and payment_data.get("refunded", 0) > 0):
            refunded_halalas = payment_data.get("refunded", amount_halalas) if payment_data else amount_halalas
            refunded_sar = round(float(refunded_halalas) / 100.0, 2)

            _logger.info("Order %s marked as refunded via Moyasar (Amount: %s SAR)", order.id, refunded_sar)
            try:
                env["jabin.customer.service"].trigger_status_transition(
                    order.id,
                    "refunded",
                    description=_("Payment refunded via Moyasar gateway (%s SAR).") % refunded_sar
                )
            except Exception as trans_err:
                _logger.warning("trigger_status_transition failed: %s, updating directly", trans_err)
                order.sudo().write({"payment_status": "refunded", "state": "refunded"})
                if "jabin.loyalty.service" in env:
                    env["jabin.loyalty.service"].reverse_order_points(env, order.id)

            txs = env["jabin.payment.transaction"].sudo().search([("order_id", "=", order.id)])
            if txs:
                txs.sudo().write({
                    "status": "refunded",
                    "refund_status": "full",
                })

            return {
                "success": True,
                "status": "refunded",
                "payment_status": "refunded",
                "state": "refunded",
                "order_id": order.id,
                "order_number": order.name,
                "amount": paid_amount_sar,
                "refunded_amount": refunded_sar,
                "payment_id": payment_id,
                "message": _("تم استرجاع مبلغ الطلب %s بنجاح عبر ميسر (%s ر.س).") % (order.name, refunded_sar),
            }
        else:
            source_msg = ""
            if payment_data and isinstance(payment_data.get("source"), dict):
                source_msg = payment_data["source"].get("message") or ""
            # Transition pending order to cancelled FIRST so cart and loyalty points are restored
            try:
                env["jabin.customer.service"].sudo().trigger_status_transition(
                    order.id, "cancelled", description=_("Order cancelled due to uncompleted/failed online payment.")
                )
            except Exception:
                pass
            order.sudo().write({"payment_status": "failed", "state": "cancelled"})
            tx = env["jabin.payment.transaction"].sudo().search([("order_id", "=", order.id)], limit=1)
            if tx:
                tx.sudo().write({
                    "status": "failed",
                    "failure_reason": f"Moyasar status: {status} {source_msg}".strip()
                })

            return {
                "success": False,
                "status": status,
                "payment_status": "failed",
                "message": source_msg or f"لم تكتمل عملية الدفع (الحالة: {status}).",
                "order_id": order.id,
                "payment_id": payment_id,
            }

    @classmethod
    def sync_order_status(cls, env, order) -> Dict[str, Any]:
        """Manually or periodically synchronize an order's payment status with Moyasar."""
        txs = env["jabin.payment.transaction"].sudo().search([("order_id", "=", order.id)])
        candidate_refs = [tx.transaction_ref for tx in txs if tx.transaction_ref]

        if not candidate_refs:
            return {"success": False, "message": _("لا يوجد مرجع عملية دفع للطلب %s.") % order.name}

        last_res = None
        for ref in candidate_refs:
            res = cls.verify_payment(env, payment_id=ref, expected_order_id=order.id, force_check=True)
            if res.get("success"):
                return res
            last_res = res

        return last_res or {"success": False, "message": _("تعذر مزامنة حالة الدفع مع بوابة ميسر.")}

    @classmethod
    def refund_payment(cls, env, order, amount_sar: Optional[float] = None) -> Dict[str, Any]:
        """Triggers a refund for an order via Moyasar API."""
        config = cls._get_config(env)
        if not config['secret_key']:
            return {
                "success": False,
                "message": _("مفتاح الربط السري لبوابة ميسر غير مضبوط على الخادم.")
            }
        auth = (config['secret_key'], '')
        headers = {"Accept": "application/json", "Content-Type": "application/json"}

        payment_id = None
        txs = env["jabin.payment.transaction"].sudo().search([("order_id", "=", order.id)])
        candidate_refs = [tx.transaction_ref for tx in txs if tx.transaction_ref]

        for ref in candidate_refs:
            try:
                p_resp = requests.get(f"{config['base_url']}/payments/{ref}", headers=headers, auth=auth, timeout=10)
                if p_resp.status_code == 200:
                    payment_id = ref
                    break
            except Exception:
                pass

            try:
                inv_resp = requests.get(f"{config['base_url']}/invoices/{ref}", headers=headers, auth=auth, timeout=10)
                if inv_resp.status_code == 200:
                    p_list = inv_resp.json().get("payments", [])
                    if p_list:
                        payment_id = p_list[-1].get("id")
                        break
            except Exception:
                pass

        if not payment_id:
            return {
                "success": False,
                "message": _("لم يتم العثور على معرف عملية دفع صالح في ميسر للطلب %s.") % order.name
            }

        refund_endpoint = f"{config['base_url']}/payments/{payment_id}/refund"
        payload = {}
        if amount_sar and amount_sar > 0:
            payload["amount"] = int(round(amount_sar * 100))

        try:
            r = requests.post(refund_endpoint, json=payload, headers=headers, auth=auth, timeout=15)
            if r.status_code in (200, 201):
                refund_data = r.json()
                cls.verify_payment(env, payment_id=payment_id, expected_order_id=order.id, force_check=True)
                return {
                    "success": True,
                    "message": _("تم استرجاع مبلغ الطلب بنجاح عبر بوابة ميسر."),
                    "data": refund_data
                }
            else:
                try:
                    err_msg = r.json().get("message") or r.text
                except Exception:
                    err_msg = r.text
                return {
                    "success": False,
                    "message": _("فشل استرجاع المبلغ عبر ميسر: %s") % err_msg
                }
        except Exception as e:
            return {
                "success": False,
                "message": _("خطأ في الاتصال بواجهة استرجاع المدفوعات في ميسر: %s") % e
            }
