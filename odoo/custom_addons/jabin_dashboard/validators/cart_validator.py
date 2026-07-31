# cart_validator.py
from odoo import _
from odoo.exceptions import ValidationError
from typing import Dict, Any, Optional
from odoo.addons.jabin_core import BaseValidator


class CartValidator(BaseValidator):
    """
    Validator for Shopping Cart operations.
    Inherits validation helpers from BaseValidator.
    """

    @staticmethod
    def validate_add_product(vals: Dict[str, Any]) -> None:
        """Validate input for adding a product to the cart."""
        # Require product_id
        CartValidator.validate_required_fields(vals, ['product_id'])

        # Validate product_id is an integer
        CartValidator.validate_field_type(vals['product_id'], int, 'Product ID')

        # Validate quantity if provided
        if 'quantity' in vals:
            CartValidator.validate_positive_number(
                vals['quantity'],
                'Quantity',
                allow_zero=False
            )

    @staticmethod
    def validate_options(env, product_id: int, cutting_option_id=None, packaging_ids=None, excluded_part_ids=None) -> None:
        """Validate that selected customization options belong to the product."""
        product = env['jabin.product'].sudo().browse(product_id)
        if not product.exists():
            raise ValidationError(_("Product not found."))

        if cutting_option_id:
            if int(cutting_option_id) not in product.cutting_option_ids.ids:
                raise ValidationError(_("Selected cutting option is not available for product '%s'.") % product.name)

        if packaging_ids:
            allowed_pkg_ids = set(product.packaging_ids.ids)
            for pkg_id in packaging_ids:
                if int(pkg_id) not in allowed_pkg_ids:
                    raise ValidationError(_("Selected packaging option is not available for product '%s'.") % product.name)

        if excluded_part_ids:
            allowed_part_ids = set(product.excluded_part_ids.ids)
            for part_id in excluded_part_ids:
                if int(part_id) not in allowed_part_ids:
                    raise ValidationError(_("Selected excluded part option is not available for product '%s'.") % product.name)


    @staticmethod
    def validate_stock(env, product_id: int, requested_qty: float, current_cart_qty: float = 0.0) -> None:
        """Validate product availability and stock quantity before adding/updating cart."""
        product = env['jabin.product'].sudo().browse(product_id)
        if not product.exists():
            raise ValidationError(_("Product not found."))
        if not product.active:
            raise ValidationError(_("Product '%s' is inactive.") % product.name)
        if not product.is_available:
            raise ValidationError(_("Product '%s' is not available (out of stock).") % product.name)

        total_qty = current_cart_qty + requested_qty
        if product.stock_quantity and total_qty > product.stock_quantity:
            raise ValidationError(
                _("Requested quantity (%(requested)s) exceeds available stock (%(stock)s) for product '%(product)s'.") % {
                    'requested': total_qty,
                    'stock': product.stock_quantity,
                    'product': product.name
                }
            )

    @staticmethod
    def validate_update_quantity(vals: Dict[str, Any]) -> None:
        """Validate input for updating product quantity in the cart."""
        CartValidator.validate_required_fields(vals, ['product_id', 'quantity'])
        CartValidator.validate_field_type(vals['product_id'], int, 'Product ID')
        CartValidator.validate_positive_number(
            vals['quantity'],
            'Quantity',
            allow_zero=False
        )

    @staticmethod
    def validate_checkout(cart) -> None:
        """
        Validate cart state before allowing checkout.
        
        Args:
            cart: The jabin.cart record
        """
        if not cart or not cart.exists():
            raise ValidationError(_("Cart does not exist."))

        if cart.status != 'active':
            raise ValidationError(_("Only active carts can be checked out."))

        if not cart.line_ids:
            raise ValidationError(_("Cannot checkout an empty cart."))

        # Check customer
        customer = cart.customer_id
        if not customer or not customer.exists():
            raise ValidationError(_("Cart has no customer associated."))

        if customer.status not in ('active', 'pending'):
            raise ValidationError(_("Customer is not active."))

        # Check all products in cart
        for line in cart.line_ids:
            product = line.product_id
            if not product or not product.exists():
                raise ValidationError(_("One of the products in the cart does not exist."))
            if not product.active:
                raise ValidationError(_("Product '%s' is inactive.") % product.display_name)
            if not product.is_available:
                raise ValidationError(_("Product '%s' is not available (out of stock).") % product.display_name)
