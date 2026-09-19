import logging
from odoo import http, fields, _
from odoo.http import request
from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder, JabinLogger

_logger = JabinLogger.get("offer.controller")

class OfferController(BaseApiController):

    def _serialize_product(self, product, offer=None):
        selling_price = product.selling_price
        if offer:
            offer_price = offer.calculate_discounted_price(selling_price)
        else:
            offer_price = product.offer_price or selling_price

        # Calculate discount percentage for display
        if selling_price > 0 and offer_price < selling_price:
            discount_pct = round(((selling_price - offer_price) / selling_price) * 100)
        else:
            discount_pct = 0

        # Primary image URL: check main_image first, then gallery
        main_img_url = None
        if getattr(product, "main_image", False):
            main_img_url = BaseApiController.build_image_url(
                "jabin.product", product.id, "main_image", bool(product.main_image)
            )
        elif product.product_image_ids:
            first_img = product.product_image_ids[0]
            main_img_url = BaseApiController.build_image_url(
                "jabin.product.image", first_img.id, "image", bool(first_img.image)
            )

        return {
            "id": product.id,
            "name": product.name,
            "sku": product.sku or "",
            "category_id": product.category_id.id if product.category_id else None,
            "category_name": product.category_id.name if product.category_id else "",
            "selling_price": selling_price,
            "offer_price": offer_price,
            "discount_percentage": discount_pct,
            "is_on_offer": True,
            "stock_quantity": product.stock_quantity,
            "is_available": product.stock_quantity > 0,
            "main_image": main_img_url,
            "main_image_url": main_img_url,
            "image_url": main_img_url,
            "description": product.description or "",
            "cutting_options": [
                {"id": opt.id, "name": opt.name}
                for opt in product.cutting_option_ids
            ],
            "packaging_options": [
                {"id": pkg.id, "name": pkg.name}
                for pkg in product.packaging_ids
            ],
            "excluded_parts": [
                {"id": part.id, "name": part.name}
                for part in product.excluded_part_ids
            ],
            "images": [
                {
                    "id": img.id,
                    "sequence": img.sequence,
                    "image": BaseApiController.build_image_url(
                        "jabin.product.image", img.id, "image", bool(img.image)
                    ),
                    "image_url": BaseApiController.build_image_url(
                        "jabin.product.image", img.id, "image", bool(img.image)
                    ),
                }
                for img in product.product_image_ids
            ],
        }

    def _serialize_offer(self, offer, include_products=True):
        banner_url = BaseApiController.build_image_url(
            "jabin.offer", offer.id, "banner_image", bool(offer.banner_image)
        )
        # Fallback to linked banner image if offer record doesn't have a direct banner_image
        if not banner_url:
            linked_banner = request.env["banner"].sudo().search(
                [("offer_id", "=", offer.id), ("active", "=", True)],
                limit=1
            )
            if linked_banner and linked_banner.image:
                banner_url = BaseApiController.build_image_url(
                    "banner", linked_banner.id, "image", True
                )
        
        data = {
            "id": offer.id,
            "name": offer.name,
            "subtitle": offer.subtitle or "",
            "description": offer.description or "",
            "badge_text": offer.badge_text or f"خصم {int(offer.discount_value)}%",
            "discount_type": offer.discount_type,
            "discount_value": offer.discount_value,
            "banner_image_url": banner_url,
            "start_date": str(offer.start_date) if offer.start_date else None,
            "end_date": str(offer.end_date) if offer.end_date else None,
            "is_active": offer.is_currently_active,
            "products_count": len(offer.product_ids),
        }

        if include_products:
            data["products"] = [
                self._serialize_product(p, offer=offer)
                for p in offer.product_ids
                if p.active
            ]
        return data

    @http.route(
        ["/api/v1/offers", "/api/v1/promotions"],
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        cors="*",
    )
    def list_offers(self, **kwargs):
        """List all active promotional offers with their banners and discounted products."""
        with self.handle() as ctx:
            today = fields.Date.context_today(request.env['jabin.offer'])
            domain = [
                ("active", "=", True),
                ("start_date", "<=", today),
                "|",
                ("end_date", "=", False),
                ("end_date", ">=", today),
            ]

            offers = request.env["jabin.offer"].sudo().search(domain, order="sequence, id desc")
            serialized = [self._serialize_offer(o, include_products=True) for o in offers]

            ctx.set_body(
                ResponseBuilder.success(
                    data={
                        "offers": serialized,
                        "total": len(serialized),
                    },
                    message=_("Active offers retrieved successfully"),
                )
            )
        return ctx.response

    @http.route(
        "/api/v1/offers/<int:offer_id>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        cors="*",
    )
    def get_offer_detail(self, offer_id, **kwargs):
        """Get detail of a single promotional offer by ID."""
        with self.handle() as ctx:
            offer = request.env["jabin.offer"].sudo().browse(offer_id)
            if not offer.exists():
                ctx.set_body(ResponseBuilder.not_found(message=_("Offer not found")))
                return ctx.response

            data = self._serialize_offer(offer, include_products=True)
            ctx.set_body(
                ResponseBuilder.success(
                    data=data,
                    message=_("Offer detail retrieved successfully"),
                )
            )
        return ctx.response
