import json
from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError
from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder
from odoo.addons.jabin_security.utils.token_auth import require_token
from odoo.addons.jabin_security import SecurityContext
from ..validators.favorite_validator import FavoriteValidator


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
    raw = request.httprequest.data
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise ValidationError(_("Invalid JSON payload."))


from .product_controller import _get_product_main_image_url


class FavoriteController(BaseApiController):
    """Customer Favorites / Wishlist REST API Controller."""

    @http.route(
        "/api/v1/favorites",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def list_favorites(self, **kwargs):
        """List user favorite products."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id()
        with self.handle() as ctx:
            limit = int(kwargs.get("limit", 50))
            offset = int(kwargs.get("offset", 0))

            favs = request.env["jabin.favorite"].sudo().search([("customer_id", "=", user_id)], order="created_date desc, id desc", limit=limit, offset=offset)

            res = []
            for f in favs:
                p = f.product_id
                main_img_url = _get_product_main_image_url(p)
                res.append({
                    "favorite_id": f.id,
                    "product_id": p.id,
                    "name": p.name,
                    "sku": p.sku,
                    "selling_price": p.selling_price,
                    "offer_price": p.offer_price if p.is_on_offer else p.selling_price,
                    "main_image": main_img_url,
                    "main_image_url": main_img_url,
                    "is_available": p.is_available,
                    "created_date": f.created_date,
                })
            ctx.set_body(ResponseBuilder.success(data=res, message=_("Favorites retrieved successfully.")))
        return ctx.response

    @http.route(
        "/api/v1/favorites",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def add_favorite(self, **kwargs):
        """Add product to user favorites."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id()
        with self.handle() as ctx:
            data = _parse_json_body()
            FavoriteValidator.validate_add(data)
            product_id = int(data["product_id"])

            product = request.env["jabin.product"].sudo().browse(product_id)
            if not product.exists():
                raise ValidationError(_("Product not found."))

            existing = request.env["jabin.favorite"].sudo().search([("customer_id", "=", user_id), ("product_id", "=", product_id)], limit=1)
            if existing:
                ctx.set_body(ResponseBuilder.success(data={"favorite_id": existing.id, "product_id": product_id}, message=_("Product is already in favorites.")))
            else:
                fav = request.env["jabin.favorite"].sudo().create({
                    "customer_id": user_id,
                    "product_id": product_id,
                })
                ctx.set_body(ResponseBuilder.success(data={"favorite_id": fav.id, "product_id": product_id}, message=_("Product added to favorites."), code=201))
        return ctx.response

    @http.route(
        "/api/v1/favorites/<int:product_id>",
        type="http",
        auth="public",
        methods=["DELETE"],
        csrf=False,
    )
    def remove_favorite(self, product_id: int, **kwargs):
        """Remove product from user favorites."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id()
        with self.handle() as ctx:
            existing = request.env["jabin.favorite"].sudo().search([("customer_id", "=", user_id), ("product_id", "=", product_id)])
            if existing:
                existing.unlink()
            ctx.set_body(ResponseBuilder.success(message=_("Product removed from favorites.")))
        return ctx.response
