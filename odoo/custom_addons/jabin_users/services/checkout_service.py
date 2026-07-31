from odoo import _
from odoo.exceptions import ValidationError


class CheckoutService:
    """Service handling Cart to Order Checkout conversions."""

    @classmethod
    def process_checkout(cls, env, customer_id: int, delivery_type: str, address_id: int = None, branch_id: int = None, payment_method_id: int = None, notes: str = None, coupon_code: str = None, redeem_points: int = None):
        user = env["res.users"].sudo().browse(customer_id)
        if not user.exists():
            raise ValidationError(_("User not found."))

        cart = env["jabin.cart"].sudo().search([("customer_id", "=", customer_id), ("status", "=", "active")], limit=1)
        if not cart or not cart.line_ids:
            raise ValidationError(_("Active cart is empty."))

        if delivery_type not in ["address", "pickup"]:
            raise ValidationError(_("delivery_type must be either 'address' or 'pickup'."))

        address_obj = None
        if delivery_type == "address":
            if not address_id:
                address_obj = env["res.users.address"].sudo().search([("user_id", "=", customer_id), ("is_default", "=", True)], limit=1)
                if not address_obj:
                    address_obj = env["res.users.address"].sudo().search([("user_id", "=", customer_id)], limit=1)
                if not address_obj:
                    raise ValidationError(_("Delivery address is required."))
            else:
                address_obj = env["res.users.address"].sudo().browse(address_id)
                if not address_obj.exists() or address_obj.user_id.id != customer_id:
                    raise ValidationError(_("Selected delivery address is invalid."))

        if delivery_type == "pickup":
            branch = False
            if branch_id:
                branch = env["jabin.branch"].sudo().browse(branch_id)
            if not branch or not branch.exists() or not branch.active:
                branch = env["jabin.branch"].sudo().search([("active", "=", True)], limit=1)
            if not branch:
                branch = env["jabin.branch"].sudo().create({
                    "name": "الفرع الرئيسي",
                    "code": "MAIN",
                    "address": "الرياض، العليا",
                    "city": "الرياض",
                    "active": True,
                })

        if not payment_method_id:
            payment_method = env["jabin.payment.method"].sudo().search([("code", "=", "cod")], limit=1)
            if not payment_method:
                payment_method = env["jabin.payment.method"].sudo().search([("active", "=", True)], limit=1)
            payment_method_id = payment_method.id if payment_method else None
        else:
            payment_method = env["jabin.payment.method"].sudo().browse(payment_method_id)
            if not payment_method.exists() or not payment_method.active:
                raise ValidationError(_("Selected payment method is invalid."))

        # Determine initial state: COD orders automatically move to confirmed
        initial_state = "confirmed" if (payment_method and payment_method.code == "cod") else "pending_payment"

        order = env["jabin.order"].sudo().create({
            "customer_id": customer_id,
            "state": initial_state,
            "payment_method_id": payment_method_id,
            "internal_notes": notes or cart.notes or "",
        })

        for line in cart.line_ids:
            line_vals = {
                "order_id": order.id,
                "product_id": line.product_id.id,
                "name": line.product_id.name,
                "price_unit": line.price_unit,
                "quantity": line.quantity,
                "discount": line.discount_percent,
                "cutting_option_id": line.cutting_option_id.id if line.cutting_option_id else False,
                "packaging_id": line.packaging_ids.ids[0] if line.packaging_ids else False,
            }
            if line.excluded_part_ids:
                line_vals["excluded_part_ids"] = [(6, 0, line.excluded_part_ids.ids)]

            env["jabin.order.line"].sudo().create(line_vals)

        # Apply coupon code if provided
        if coupon_code and str(coupon_code).strip():
            order.apply_coupon(str(coupon_code).strip())

        # Redeem loyalty points if provided
        if redeem_points and int(redeem_points) > 0:
            pts = int(redeem_points)
            order.apply_loyalty_points(pts)
            from odoo.addons.jabin_dashboard.services.loyalty_service import LoyaltyService
            LoyaltyService.deduct_redeemed_points(env, customer_id, pts, order.id)

        cart.write({
            "status": "checked_out",
            "checked_out_order_id": order.id,
            "delivery_address_id": address_obj.id if address_obj else False,
        })

        return order
