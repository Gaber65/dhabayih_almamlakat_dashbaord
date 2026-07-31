import json
from typing import Dict, Any, Optional

from odoo import http, _
from odoo.exceptions import ValidationError
from odoo.http import request

from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder, JabinLogger
from odoo.addons.jabin_security.utils.token_auth import require_token


from ..services.cart_service import CartService

_logger = JabinLogger.get("cart.controller")


def _get_auth_user_id() -> Optional[int]:
    """Helper to extract user ID from Authorization Bearer token."""
    try:
        raw_header = request.httprequest.headers.get("Authorization", "")
    except Exception:
        return None

    token = ""
    if raw_header:
        parts = raw_header.split(None, 1)
        if len(parts) == 2 and parts[0].lower() == 'bearer':
            token = parts[1].strip()

    if not token:
        return None

    try:
        from odoo.addons.jabin_security.utils.jwt_utils import JWTUtils
        claims = JWTUtils.decode_token(token)
        return JWTUtils.get_user_id(claims)
    except Exception:
        return None


def _parse_request_data() -> Dict[str, Any]:
    """Parse request data from either multipart/form-data or JSON."""
    content_type = request.httprequest.content_type or ""
    vals = {}

    if "multipart/form-data" in content_type:
        vals = {
            k: v
            for k, v in request.httprequest.form.items()
        }
        if "product_id" in vals:
            try:
                vals["product_id"] = int(vals["product_id"])
            except ValueError:
                raise ValueError("Product ID must be a valid integer.")
        if "quantity" in vals:
            try:
                vals["quantity"] = float(vals["quantity"])
            except ValueError:
                raise ValueError("Quantity must be a valid number.")
    else:
        raw = request.httprequest.data
        if raw:
            try:
                vals = json.loads(raw)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON payload.")
    return vals


class CartController(BaseApiController):
    """Shopping Cart REST API Controller following enterprise standards."""

    @http.route(
        "/api/v1/cart",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_cart(self, **kwargs):
        """Retrieve current user's active cart."""
        with self.handle() as ctx:
            customer_id = _get_auth_user_id()
            if not customer_id:
                raise ValidationError(_("Authentication required to retrieve cart."))

            cart = CartService.get_or_create_active_cart(request.env, customer_id)
            ctx.set_body(
                ResponseBuilder.success(
                    data=cart.get_summary(),
                    message=_("Cart retrieved successfully"),
                )
            )
        return ctx.response

    @http.route(
        "/api/v1/cart/add",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def add_product(self, **kwargs):
        """Add product to the active cart."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            customer_id = _get_auth_user_id()
            if not customer_id:
                raise ValidationError(_("Customer authentication session not found."))

            vals = _parse_request_data()
            product_id = vals.get("product_id")
            quantity = vals.get("quantity", 1.0)
            cutting_option_id = vals.get("cutting_option_id")
            packaging_ids = vals.get("packaging_ids")
            excluded_part_ids = vals.get("excluded_part_ids")
            notes = vals.get("notes")

            cart = CartService.add_product(
                request.env,
                customer_id,
                product_id,
                quantity,
                cutting_option_id=cutting_option_id,
                packaging_ids=packaging_ids,
                excluded_part_ids=excluded_part_ids,
                notes=notes,
            )

            ctx.set_body(
                ResponseBuilder.success(
                    data=cart.get_summary(),
                    message=_("Product added to cart successfully"),
                    code=201,
                )
            )
        return ctx.response

    @http.route(
        "/api/v1/cart/remove/<int:product_id>",
        type="http",
        auth="public",
        methods=["DELETE"],
        csrf=False,
    )
    def remove_product(self, product_id, **kwargs):
        """Remove product from active cart."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            customer_id = _get_auth_user_id()
            if not customer_id:
                raise ValidationError(_("Customer authentication session not found."))

            cart = CartService.remove_product(
                request.env,
                customer_id,
                product_id,
            )

            ctx.set_body(
                ResponseBuilder.success(
                    data=cart.get_summary(),
                    message=_("Product removed from cart successfully"),
                )
            )
        return ctx.response

    @http.route(
        "/api/v1/cart/update",
        type="http",
        auth="public",
        methods=["PUT"],
        csrf=False,
    )
    def update_quantity(self, **kwargs):
        """Update product quantity in active cart."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            customer_id = _get_auth_user_id()
            if not customer_id:
                raise ValidationError(_("Customer authentication session not found."))

            vals = _parse_request_data()
            product_id = vals.get("product_id")
            quantity = vals.get("quantity")
            cutting_option_id = vals.get("cutting_option_id")
            packaging_ids = vals.get("packaging_ids")
            excluded_part_ids = vals.get("excluded_part_ids")
            notes = vals.get("notes")

            if quantity is None:
                raise ValidationError(_("Quantity is required."))

            cart = CartService.update_quantity(
                request.env,
                customer_id,
                product_id,
                quantity,
                cutting_option_id=cutting_option_id,
                packaging_ids=packaging_ids,
                excluded_part_ids=excluded_part_ids,
                notes=notes,
            )

            ctx.set_body(
                ResponseBuilder.success(
                    data=cart.get_summary(),
                    message=_("Cart updated successfully"),
                )
            )
        return ctx.response

    @http.route(
        "/api/v1/cart/increase/<int:product_id>",
        type="http",
        auth="public",
        methods=["PATCH"],
        csrf=False,
    )
    def increase_quantity(self, product_id, **kwargs):
        """Increase quantity of product in cart by 1."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            customer_id = _get_auth_user_id()
            if not customer_id:
                raise ValidationError(_("Customer authentication session not found."))

            cart = CartService.increase_quantity(
                request.env,
                customer_id,
                product_id,
            )

            ctx.set_body(
                ResponseBuilder.success(
                    data=cart.get_summary(),
                    message=_("Quantity increased successfully"),
                )
            )
        return ctx.response

    @http.route(
        "/api/v1/cart/decrease/<int:product_id>",
        type="http",
        auth="public",
        methods=["PATCH"],
        csrf=False,
    )
    def decrease_quantity(self, product_id, **kwargs):
        """Decrease quantity of product in cart by 1."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            customer_id = _get_auth_user_id()
            if not customer_id:
                raise ValidationError(_("Customer authentication session not found."))

            cart = CartService.decrease_quantity(
                request.env,
                customer_id,
                product_id,
            )

            ctx.set_body(
                ResponseBuilder.success(
                    data=cart.get_summary(),
                    message=_("Quantity decreased successfully"),
                )
            )
        return ctx.response

class TestController(http.Controller):

    @http.route('/test_cart', auth='public', type='http', methods=['GET'], csrf=False)
    def test_cart(self, **kw):
        return "OK"