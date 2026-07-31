# home_controller.py
from odoo import http, _
from odoo.http import request
from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder

from ..services.product_service import ProductService
from ..services.category_service import CategoryService
from ..services.banner_service import BannerService
from ..controllers.product_controller import _serialize_product, _get_lang

class HomeController(BaseApiController):
    """Home REST API Controller."""

    @http.route(
        "/api/v1/home",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_home_data(self, **kwargs):
        """Get aggregated home page data with optional authentication."""
        with self.handle() as ctx:
            lang = _get_lang()
            base_url = request.httprequest.host_url.rstrip('/')
            env = request.env

            # Safely attempt optional user authentication via Bearer token
            user_id = None
            try:
                raw_header = request.httprequest.headers.get("Authorization", "")
                if raw_header:
                    parts = raw_header.split(None, 1)
                    if len(parts) == 2 and parts[0].lower() == 'bearer':
                        token = parts[1].strip()
                        from odoo.addons.jabin_security.utils.jwt_utils import JWTUtils
                        claims = JWTUtils.decode_token(token)
                        user_id = JWTUtils.get_user_id(claims)
            except Exception:
                # Invalid or expired token is ignored -> treated as guest
                user_id = None

            if not user_id and request.env.user and request.env.user.id != env.ref('base.public_user').id:
                user_id = request.env.user.id

            user_highlight = None
            delivery_location = None

            if user_id:
                u = env['res.users'].sudo().browse(user_id)
                if u.exists():
                    user_highlight = u.to_public_dict() if hasattr(u, 'to_public_dict') else {
                        "id": u.id,
                        "name": u.name,
                        "email": u.email,
                    }
                    # Populate delivery location for authenticated user
                    branch = env["jabin.branch"].sudo().search([("active", "=", True)], limit=1, order="name")
                    if branch:
                        delivery_location = {
                            "id": branch.id,
                            "name": branch.name,
                            "address": branch.address,
                            "city": branch.city,
                            "latitude": branch.latitude,
                            "longitude": branch.longitude,
                        }

            # 2. Dynamic Banners (Public)
            banners = BannerService.get_banners(
                env,
                domain=[('active', '=', True)],
                limit=10,
                lang=lang
            )
            banners_data = [
                {
                    "id": b.id,
                    "name": b.name,
                    "image": BaseApiController.build_image_url("banner", b.id, "image", bool(b.image)),
                    "image_url": BaseApiController.build_image_url("banner", b.id, "image", bool(b.image)),
                }
                for b in banners
            ]

            # 3. Jabin Highlight (Public Stories Feed)
            jabin_highlight = []
            if 'jabin.highlight.service' in env:
                jabin_highlight = env['jabin.highlight.service'].sudo().get_feed()

            # 4. Categories (Public)
            categories = CategoryService.get_categories(
                env,
                domain=[('active', '=', True)],
                limit=15,
                lang=lang,
                order="sequence, name"
            )
            categories_data = [
                {
                    "id": c.id,
                    "name": c.name,
                    "image": BaseApiController.build_image_url("jabin.category", c.id, "image", bool(c.image)),
                    "image_url": BaseApiController.build_image_url("jabin.category", c.id, "image", bool(c.image)),
                    "sequence": c.sequence,
                    "product_count": c.product_count,
                }
                for c in categories
            ]

            # 5. Featured Products (Public)
            featured, _total = ProductService.get_list(
                env,
                domain=[('is_featured', '=', True), ('active', '=', True)],
                limit=10,
                lang=lang
            )
            featured_data = [_serialize_product(p) for p in featured]

            # 6. Best Sellers (Public)
            best_sellers, _total = ProductService.get_list(
                env,
                domain=[('is_best_seller', '=', True), ('active', '=', True)],
                limit=10,
                lang=lang
            )
            best_sellers_data = [_serialize_product(p) for p in best_sellers]

            # 7. Recommended Products (Public)
            recommended, _total = ProductService.get_list(
                env,
                domain=[('active', '=', True)],
                limit=10,
                order="id desc", # Fallback order
                lang=lang
            )
            recommended_data = [_serialize_product(p) for p in recommended]

            response_data = {
                "delivery_location": delivery_location,
                "user_highlight": user_highlight,
                "jabin_highlight": jabin_highlight,
                "banners": banners_data,
                "categories": categories_data,
                "featured_products": featured_data,
                "best_sellers": best_sellers_data,
                "recommended_products": recommended_data,
            }

            ctx.set_body(
                ResponseBuilder.success(
                    data=response_data,
                    message=_("Home data retrieved successfully"),
                )
            )

        return ctx.response
