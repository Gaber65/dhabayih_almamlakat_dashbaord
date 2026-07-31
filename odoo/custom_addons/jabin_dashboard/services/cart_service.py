# cart_service.py
from odoo import _
from odoo.exceptions import ValidationError
from ..validators.cart_validator import CartValidator


class CartService:
    """
    Shopping Cart service layer.
    Manages cart database operations and validation.
    """

    @staticmethod
    def get_or_create_active_cart(env, customer_id):
        """Retrieve the customer's active cart, creating it if none exists."""
        customer = env['res.users'].sudo().browse(customer_id)
        if not customer.exists():
            raise ValidationError(_("Customer not found."))
        
        cart = customer.active_cart_id
        if not cart:
            cart = env['jabin.cart'].sudo().search([
                ('customer_id', '=', customer_id),
                ('status', '=', 'active')
            ], limit=1)
        if not cart:
            currency_id = customer.currency_id.id if (customer.currency_id and customer.currency_id.id) else env.company.currency_id.id
            cart = env['jabin.cart'].sudo().create({
                'customer_id': customer_id,
                'currency_id': currency_id,
                'status': 'active',
            })
        return cart


    @staticmethod
    def add_product(env, customer_id, product_id, quantity=1.0, cutting_option_id=None, packaging_ids=None, excluded_part_ids=None, notes=None):
        """Add a product to the customer's active cart with customization options."""
        CartValidator.validate_add_product({'product_id': product_id, 'quantity': quantity})
        CartValidator.validate_options(env, product_id, cutting_option_id, packaging_ids, excluded_part_ids)
        cart = CartService.get_or_create_active_cart(env, customer_id)
        existing_line = cart.line_ids.filtered(lambda l: l.product_id.id == product_id)
        current_qty = existing_line.quantity if existing_line else 0.0
        CartValidator.validate_stock(env, product_id, float(quantity), current_qty)
        cart.add_product(product_id, quantity, cutting_option_id, packaging_ids, excluded_part_ids, notes)
        return cart

    @staticmethod
    def remove_product(env, customer_id, product_id):
        """Remove a product from the customer's active cart."""
        cart = CartService.get_or_create_active_cart(env, customer_id)
        cart.remove_product(product_id)
        return cart

    @staticmethod
    def update_quantity(env, customer_id, product_id, quantity, cutting_option_id=None, packaging_ids=None, excluded_part_ids=None, notes=None):
        """Update a product's quantity and customization options in the customer's active cart."""
        CartValidator.validate_update_quantity({'product_id': product_id, 'quantity': quantity})
        CartValidator.validate_options(env, product_id, cutting_option_id, packaging_ids, excluded_part_ids)
        CartValidator.validate_stock(env, product_id, float(quantity), 0.0)
        cart = CartService.get_or_create_active_cart(env, customer_id)
        cart.update_quantity(product_id, quantity, cutting_option_id, packaging_ids, excluded_part_ids, notes)
        return cart

    @staticmethod
    def increase_quantity(env, customer_id, product_id):
        """Increase product quantity in active cart by 1."""
        cart = CartService.get_or_create_active_cart(env, customer_id)
        cart.increase_quantity(product_id)
        return cart

    @staticmethod
    def decrease_quantity(env, customer_id, product_id):
        """Decrease product quantity in active cart by 1."""
        cart = CartService.get_or_create_active_cart(env, customer_id)
        cart.decrease_quantity(product_id)
        return cart

    @staticmethod
    def clear_cart(env, customer_id):
        """Clear all lines in the active cart."""
        cart = CartService.get_or_create_active_cart(env, customer_id)
        cart.clear_cart()
        return cart

    @staticmethod
    def get_summary(env, customer_id):
        """Get the active cart summary for the customer."""
        cart = CartService.get_or_create_active_cart(env, customer_id)
        return cart.get_summary()

    @staticmethod
    def checkout(env, customer_id):
        """Checkout the customer's active cart, creating a new order."""
        cart = CartService.get_or_create_active_cart(env, customer_id)
        CartValidator.validate_checkout(cart)
        order = cart.checkout()
        return order

    @staticmethod
    def get_cart_history(env, customer_id):
        """Get past (non-active) carts for this customer."""
        return env['jabin.cart'].sudo().search([
            ('customer_id', '=', customer_id),
            ('status', '!=', 'active')
        ], order='id desc')
