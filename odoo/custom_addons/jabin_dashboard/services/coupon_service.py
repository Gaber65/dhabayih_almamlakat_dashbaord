# coupon_service.py
from typing import Dict, Any, List, Optional
from odoo import _, fields
from odoo.exceptions import ValidationError
from ..validators.coupon_validator import CouponValidator


class CouponService:
    """Coupon / Promo Code business logic service layer."""

    @staticmethod
    def _format_m2m_vals(vals: Dict[str, Any]) -> Dict[str, Any]:
        """Format Many2many list of IDs into Odoo ORM command format [(6, 0, ids)]."""
        formatted = dict(vals)
        for field in ['category_ids', 'product_ids']:
            if field in formatted and isinstance(formatted[field], list):
                # Ensure all elements are integers
                ids = [int(i) for i in formatted[field] if i is not None]
                formatted[field] = [(6, 0, ids)]
        return formatted

    @staticmethod
    def create_coupon(env, vals: Dict[str, Any]):
        """
        Create a new coupon.

        Args:
            env: Odoo environment
            vals: Dictionary of coupon attributes

        Returns:
            jabin.coupon: Created coupon record
        """
        CouponValidator.validate_create(vals, env=env)
        formatted_vals = CouponService._format_m2m_vals(vals)
        coupon = env["jabin.coupon"].sudo().create(formatted_vals)
        return coupon

    @staticmethod
    def update_coupon(env, coupon_id: int, vals: Dict[str, Any]):
        """
        Update an existing coupon.

        Args:
            env: Odoo environment
            coupon_id: ID of coupon to update
            vals: Dictionary of attributes to update

        Returns:
            jabin.coupon: Updated coupon record
        """
        coupon = env["jabin.coupon"].sudo().browse(coupon_id)
        if not coupon.exists():
            raise ValidationError(_("Coupon not found."))

        CouponValidator.validate_update(coupon, vals)
        formatted_vals = CouponService._format_m2m_vals(vals)
        coupon.write(formatted_vals)
        return coupon

    @staticmethod
    def delete_coupon(env, coupon_id: int) -> bool:
        """
        Delete a coupon.

        Args:
            env: Odoo environment
            coupon_id: ID of coupon to delete

        Returns:
            bool: True if deletion succeeded
        """
        coupon = env["jabin.coupon"].sudo().browse(coupon_id)
        if not coupon.exists():
            raise ValidationError(_("Coupon not found."))

        CouponValidator.validate_delete(coupon)
        coupon.unlink()
        return True

    @staticmethod
    def get_coupon(env, coupon_id: int, lang: Optional[str] = None):
        """
        Get a single coupon by ID.

        Args:
            env: Odoo environment
            coupon_id: ID of coupon
            lang: Language code

        Returns:
            jabin.coupon: Coupon record
        """
        coupon = env["jabin.coupon"].sudo().with_context(lang=lang).browse(coupon_id)
        if not coupon.exists():
            raise ValidationError(_("Coupon not found."))
        return coupon

    @staticmethod
    def get_coupons(
        env,
        domain: Optional[List[Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order: Optional[str] = None,
        lang: Optional[str] = None,
    ):
        """
        Get a list of coupons with pagination and filtering.

        Args:
            env: Odoo environment
            domain: Search domain
            limit: Record limit
            offset: Record offset
            order: Sort order
            lang: Language code

        Returns:
            jabin.coupon: Recordset of coupons
        """
        return (
            env["jabin.coupon"]
            .sudo()
            .with_context(lang=lang)
            .search(
                domain or [],
                limit=limit or 100,
                offset=offset or 0,
                order=order or "id desc",
            )
        )

    @staticmethod
    def get_coupons_count(env, domain: Optional[List[Any]] = None) -> int:
        """Count total coupons matching search domain."""
        return env["jabin.coupon"].sudo().search_count(domain or [])

    @staticmethod
    def toggle_coupon_active(env, coupon_id: int):
        """Toggle active status of a coupon."""
        coupon = env["jabin.coupon"].sudo().browse(coupon_id)
        if not coupon.exists():
            raise ValidationError(_("Coupon not found."))
        coupon.write({"active": not coupon.active})
        return coupon

    @staticmethod
    def apply_coupon_to_order(env, order_id: Optional[int], code: str, customer_id: Optional[int] = None):
        """
        Apply a coupon code to an order.

        Args:
            env: Odoo environment
            order_id: ID of order (optional if customer_id provided)
            code: Coupon code string
            customer_id: Authenticated customer ID

        Returns:
            dict: Summary of the order with applied coupon details
        """
        if not order_id and customer_id:
            # Find active draft/pending order for customer
            order = env["jabin.order"].sudo().search([
                ("customer_id", "=", customer_id),
                ("state", "in", ["draft", "pending_payment"])
            ], order="id desc", limit=1)
        elif order_id:
            order = env["jabin.order"].sudo().browse(order_id)
        else:
            order = None

        if not order or not order.exists():
            raise ValidationError(_("Active order not found."))

        if customer_id and order.customer_id.id != customer_id:
            raise ValidationError(_("Order does not belong to the authenticated user."))

        order.apply_coupon(code)

        return {
            "order_id": order.id,
            "order_number": order.name,
            "subtotal": order.subtotal,
            "coupon": {
                "id": order.coupon_id.id,
                "code": order.coupon_id.code,
                "name": order.coupon_id.name,
                "discount_type": order.coupon_id.discount_type,
                "discount_value": order.coupon_id.discount_value,
            },
            "discount_amount": order.discount_amount,
            "total_after_discount": order.total_after_discount,
            "tax_amount": order.tax_amount,
            "grand_total": order.total,
        }

    @staticmethod
    def remove_coupon_from_order(env, order_id: Optional[int], customer_id: Optional[int] = None):
        """
        Remove applied coupon from an order.

        Args:
            env: Odoo environment
            order_id: ID of order
            customer_id: Authenticated customer ID

        Returns:
            dict: Summary of the order without coupon
        """
        if not order_id and customer_id:
            order = env["jabin.order"].sudo().search([
                ("customer_id", "=", customer_id),
                ("state", "in", ["draft", "pending_payment"])
            ], order="id desc", limit=1)
        elif order_id:
            order = env["jabin.order"].sudo().browse(order_id)
        else:
            order = None

        if not order or not order.exists():
            raise ValidationError(_("Active order not found."))

        if customer_id and order.customer_id.id != customer_id:
            raise ValidationError(_("Order does not belong to the authenticated user."))

        order.remove_coupon()

        return {
            "order_id": order.id,
            "order_number": order.name,
            "subtotal": order.subtotal,
            "coupon": None,
            "discount_amount": order.discount_amount,
            "total_after_discount": order.total_after_discount,
            "tax_amount": order.tax_amount,
            "grand_total": order.total,
        }
