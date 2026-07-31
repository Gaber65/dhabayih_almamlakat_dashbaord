from odoo import http, _
from odoo.http import request
from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder


from .product_controller import _get_product_main_image_url


class SearchController(BaseApiController):
    """Unified Search REST API Controller for Products and Categories."""

    @http.route(
        "/api/v1/search",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def search(self, **kwargs):
        """Search products and/or categories by term query ``q``."""
        with self.handle() as ctx:
            query = str(kwargs.get("q", "")).strip()
            search_type = str(kwargs.get("type", "all")).lower()
            limit = int(kwargs.get("limit", 20))
            offset = int(kwargs.get("offset", 0))

            if not query:
                ctx.set_body(ResponseBuilder.success(data={"products": [], "categories": []}, message=_("Query term is empty.")))
                return ctx.response

            result_products = []
            result_categories = []

            if search_type in ["product", "all"]:
                product_domain = [
                    ("active", "=", True),
                    "|", "|",
                    ("name", "ilike", query),
                    ("sku", "ilike", query),
                    ("description", "ilike", query)
                ]
                products = request.env["jabin.product"].sudo().search(product_domain, limit=limit, offset=offset, order="name")
                for p in products:
                    main_img_url = _get_product_main_image_url(p)
                    result_products.append({
                        "id": p.id,
                        "name": p.name,
                        "sku": p.sku,
                        "category_name": p.category_id.name if p.category_id else None,
                        "selling_price": p.selling_price,
                        "offer_price": p.offer_price,
                        "is_on_offer": p.is_on_offer,
                        "stock_quantity": p.stock_quantity,
                        "is_available": p.is_available,
                        "main_image": main_img_url,
                        "main_image_url": main_img_url,
                    })

            if search_type in ["category", "all"]:
                category_domain = [
                    "|",
                    ("name", "ilike", query),
                    ("description", "ilike", query)
                ]
                categories = request.env["jabin.category"].sudo().search(category_domain, limit=limit, offset=offset, order="name")
                for c in categories:
                    result_categories.append({
                        "id": c.id,
                        "name": c.name,
                        "description": c.description,
                        "product_count": len(c.product_ids),
                        "image": self.build_image_url("jabin.category", c.id, "image", bool(c.image)),
                        "image_url": self.build_image_url("jabin.category", c.id, "image", bool(c.image)),
                    })

            ctx.set_body(ResponseBuilder.success(data={
                "query": query,
                "products": result_products,
                "categories": result_categories,
            }, message=_("Search executed successfully.")))
        return ctx.response
