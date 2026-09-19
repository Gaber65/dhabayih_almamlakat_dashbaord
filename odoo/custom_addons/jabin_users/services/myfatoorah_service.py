import json
import logging
import requests
from typing import Dict, Any, Optional
from odoo import _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Default MyFatoorah Test API Key (Standard Sandbox Demo Token provided by MyFatoorah)
DEFAULT_TEST_TOKEN = (
    "rLtt6JWvbUHDDhszafl7xpBpFGqgu0YtkjlWFxxiSZggBt40qUutcquqqvmTyfinT563Q46nBQG5NWQRV2qlFQvnM_WXPAmTJVq"
    "O_bYuaabVMtUXEneM6E8GrywFather_2F2k91b1R2pC7H75a8h_n3k15W1jVb-4n_g6H606k4rT1_j6-70e1b-09257662c15"
)

class MyFatoorahService:
    """Enterprise MyFatoorah Payment Gateway Integration Service."""

    @classmethod
    def _get_config(cls, env) -> Dict[str, str]:
        params = env['ir.config_parameter'].sudo()
        token = params.get_param('myfatoorah.api_key', '').strip()
        env_mode = params.get_param('myfatoorah.environment', 'test').strip().lower()

        if not token:
            # Fallback to demo test token
            token = (
                "rLtt6JWvbUHDDhszafl7xpBpFGqgu0YtkjlWFxxiSZggBt40qUutcquqqvmTyfinT563Q46nBQG5NWQRV2qlFQvnM_WXPAmTJVq"
                "O_bYuaabVMtUXEneM6E8GrywFather_2F2k91b1R2pC7H75a8h_n3k15W1jVb-4n_g6H606k4rT1_j6-70e1b-09257662c15"
            )

        if env_mode == 'live':
            base_url = "https://api-sa.myfatoorah.com"
        else:
            base_url = "https://apitest.myfatoorah.com"

        return {
            'token': token,
            'base_url': base_url,
            'env_mode': env_mode,
        }

    @classmethod
    def initiate_payment(
        cls,
        env,
        order,
        callback_url: str,
        error_url: str,
        payment_method_code: str = 'myfatoorah'
    ) -> Dict[str, Any]:
        """
        Initiates a payment session in MyFatoorah.
        Order must remain in 'pending_payment' state!
        """
        config = cls._get_config(env)
        headers = {
            "Authorization": f"Bearer {config['token']}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        customer = order.customer_id
        customer_name = customer.name or "عميل ذبائح المملكة"
        customer_email = customer.email or f"customer_{customer.id}@dhabayih.com"
        customer_mobile = customer.phone or "0500000000"
        
        # Clean mobile for Saudi number format
        clean_mobile = customer_mobile.replace("+", "").replace(" ", "").replace("-", "")
        if clean_mobile.startswith("966"):
            mobile_country = "+966"
            mobile_number = clean_mobile[3:]
        elif clean_mobile.startswith("05"):
            mobile_country = "+966"
            mobile_number = clean_mobile[1:]
        else:
            mobile_country = "+966"
            mobile_number = clean_mobile

        invoice_value = round(float(order.total_amount), 2)
        if invoice_value <= 0:
            raise ValidationError(_("Order total must be greater than zero to initiate payment."))

        # Map payment gateway sub-method if specified
        gateway_id = 0 # 0 enables all active MyFatoorah gateway payment options
        if payment_method_code in ('mada', 'myfatoorah_mada'):
            gateway_id = 6 # Mada on MyFatoorah
        elif payment_method_code in ('applepay', 'apple_pay', 'myfatoorah_apple'):
            gateway_id = 11 # Apple Pay
        elif payment_method_code in ('stcpay', 'stc_pay'):
            gateway_id = 12 # STC Pay

        payload = {
            "PaymentMethodId": gateway_id,
            "CustomerName": customer_name,
            "DisplayCurrencyIso": "SAR",
            "MobileCountryCode": mobile_country,
            "CustomerMobile": mobile_number,
            "CustomerEmail": customer_email,
            "InvoiceValue": invoice_value,
            "CallBackUrl": callback_url,
            "ErrorUrl": error_url,
            "Language": "ar",
            "CustomerReference": str(order.id),
            "UserDefinedField": order.name,
            "ExpiryDate": "",
            "SourceInfo": "Dhabayih Al-Mamlaka Store",
        }

        endpoint = f"{config['base_url']}/v2/ExecutePayment"
        _logger.info("Initiating MyFatoorah payment for Order ID %s at %s", order.id, endpoint)

        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=25)
            data = resp.json()
        except Exception as e:
            _logger.error("MyFatoorah HTTP request exception: %s", str(e))
            raise ValidationError(_("Connection error while communicating with payment gateway."))

        if not data.get("IsSuccess"):
            error_msg = data.get("Message") or "Failed to initiate payment."
            _logger.error("MyFatoorah payment rejection: %s", data)
            raise ValidationError(_("Payment Gateway Error: %s") % error_msg)

        invoice_data = data.get("Data", {})
        invoice_id = invoice_data.get("InvoiceId")
        payment_url = invoice_data.get("PaymentURL")

        # Create or update transaction record in pending status
        tx = env["jabin.payment.transaction"].sudo().search([
            ("order_id", "=", order.id),
            ("status", "=", "pending")
        ], limit=1)

        if not tx:
            payment_method = env["jabin.payment.method"].sudo().search([
                ("provider", "=", "myfatoorah")
            ], limit=1)
            if not payment_method:
                payment_method = order.payment_method_id

            tx = env["jabin.payment.transaction"].sudo().create({
                "order_id": order.id,
                "customer_id": order.customer_id.id,
                "payment_method_id": payment_method.id if payment_method else order.payment_method_id.id,
                "amount": invoice_value,
                "status": "pending",
                "transaction_ref": str(invoice_id),
            })
        else:
            tx.sudo().write({"transaction_ref": str(invoice_id)})

        return {
            "success": True,
            "invoice_id": invoice_id,
            "payment_url": payment_url,
            "order_id": order.id,
            "order_number": order.name,
        }

    @classmethod
    def verify_payment(cls, env, payment_id: str, expected_order_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Verifies transaction status directly with MyFatoorah API.
        Crucial Rule: ONLY confirms order when MyFatoorah returns InvoiceStatus == 'Paid'.
        """
        if not payment_id:
            return {"success": False, "message": "Missing PaymentId for verification."}

        config = cls._get_config(env)
        headers = {
            "Authorization": f"Bearer {config['token']}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        endpoint = f"{config['base_url']}/v2/GetPaymentStatus"
        payload = {
            "Key": str(payment_id),
            "KeyType": "PaymentId"
        }

        _logger.info("Verifying MyFatoorah PaymentId %s at %s", payment_id, endpoint)

        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=25)
            data = resp.json()
        except Exception as e:
            _logger.error("MyFatoorah verification request failed: %s", str(e))
            return {"success": False, "message": "Failed to verify transaction with bank server."}

        if not data.get("IsSuccess"):
            return {
                "success": False,
                "message": data.get("Message") or "Failed to verify payment status."
            }

        status_data = data.get("Data", {})
        invoice_status = status_data.get("InvoiceStatus") # "Paid", "Failed", "Pending"
        customer_ref = status_data.get("CustomerReference")
        invoice_val = float(status_data.get("InvoiceValue", 0.0))

        # Find target order
        order = None
        if expected_order_id:
            order = env["jabin.order"].sudo().browse(expected_order_id)
        elif customer_ref and customer_ref.isdigit():
            order = env["jabin.order"].sudo().browse(int(customer_ref))

        if not order or not order.exists():
            return {"success": False, "message": "Associated order could not be located."}

        # Validate Invoice Status
        if invoice_status == "Paid":
            # Security verification: invoice amount must match order total
            if abs(float(order.total_amount) - invoice_val) > 0.05:
                _logger.critical(
                    "Amount mismatch detected! Order total: %s, Paid value: %s for Order %s",
                    order.total_amount, invoice_val, order.id
                )
                return {"success": False, "message": "Security mismatch: Paid value does not match order total."}

            # Mark order as confirmed and paid
            order.sudo().write({
                "state": "confirmed",
                "payment_status": "paid",
            })

            # Update or create transaction record
            tx = env["jabin.payment.transaction"].sudo().search([
                ("order_id", "=", order.id)
            ], limit=1)
            
            if tx:
                tx.sudo().write({
                    "status": "paid",
                    "transaction_ref": str(payment_id),
                    "paid_date": fields.Datetime.now(),
                })
            else:
                pm = env["jabin.payment.method"].sudo().search([("provider", "=", "myfatoorah")], limit=1)
                tx = env["jabin.payment.transaction"].sudo().create({
                    "order_id": order.id,
                    "customer_id": order.customer_id.id,
                    "payment_method_id": pm.id if pm else order.payment_method_id.id,
                    "amount": invoice_val,
                    "status": "paid",
                    "transaction_ref": str(payment_id),
                    "paid_date": fields.Datetime.now(),
                })

            # Send push / notification if service available
            try:
                if "jabin.notification.service" in env:
                    env["jabin.notification.service"].send_payment_success(env, order, tx)
            except Exception as ex:
                _logger.warning("Could not send payment notification: %s", ex)

            # Clear user active cart
            try:
                active_cart = env["jabin.cart"].sudo().search([
                    ("customer_id", "=", order.customer_id.id),
                    ("status", "=", "active")
                ], limit=1)
                if active_cart:
                    active_cart.sudo().write({"status": "checked_out", "checked_out_order_id": order.id})
            except Exception as e:
                _logger.warning("Error closing cart after payment: %s", e)

            return {
                "success": True,
                "status": "paid",
                "order_id": order.id,
                "order_number": order.name,
                "amount": invoice_val,
                "payment_id": payment_id,
            }
        else:
            # Payment was not paid (Failed or Cancelled)
            order.sudo().write({
                "payment_status": "failed",
            })
            tx = env["jabin.payment.transaction"].sudo().search([("order_id", "=", order.id)], limit=1)
            if tx:
                tx.sudo().write({"status": "failed", "failure_reason": f"MyFatoorah status: {invoice_status}"})

            return {
                "success": False,
                "status": invoice_status,
                "message": f"Payment was not completed (Status: {invoice_status}).",
                "order_id": order.id,
            }
