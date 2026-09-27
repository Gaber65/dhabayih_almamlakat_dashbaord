import base64
import json
import logging
from typing import Dict, Any, Optional
from odoo import http, fields, _
from odoo.http import request
from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder, JabinLogger
from odoo.addons.jabin_security.utils.token_auth import require_token
from odoo.addons.jabin_security.decorators.permission_required import permission_required

_logger = JabinLogger.get("offer.controller")
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


def _read_image_upload(file_field_name: str = "banner_image") -> Optional[bytes]:
    uploaded = request.httprequest.files.get(file_field_name) or request.httprequest.files.get("image")
    if not uploaded:
        return None
    content_type = (uploaded.content_type or "").lower().split(";")[0].strip()
    if content_type not in _ALLOWED_IMAGE_TYPES:
        raise ValueError(f"Unsupported image type '{content_type}'. Allowed: jpg, jpeg, png, webp.")
    raw = uploaded.read()
    if not raw:
        raise ValueError("Uploaded image file is empty.")
    return base64.b64encode(raw)


def _parse_offer_data() -> Dict[str, Any]:
    content_type = request.httprequest.content_type or ""
    vals = {}
    if "multipart/form-data" in content_type:
        vals = {k: v for k, v in request.httprequest.form.items() if k not in ["id"]}
        if "active" in vals:
            vals["active"] = vals["active"].lower() not in ("false", "0", "no")
        img = _read_image_upload("banner_image")
        if img:
            vals["banner_image"] = img.decode("ascii")
    else:
        raw = request.httprequest.data
        if raw:
            try:
                vals = json.loads(raw)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON payload.")
        vals.pop("id", None)

    if "is_active" in vals:
        vals["active"] = bool(vals.pop("is_active"))
    return vals


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
            "active": offer.active,
            "products_count": len(offer.product_ids),
            "product_ids": [p.id for p in offer.product_ids],
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
        """List promotional offers with their banners and discounted products."""
        with self.handle() as ctx:
            all_param = kwargs.get("all") or kwargs.get("include_inactive")
            if all_param and str(all_param).lower() in ("true", "1", "yes"):
                domain = []
            else:
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

    @http.route(
        "/api/v1/offers",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    @permission_required("banners.manage")
    def create_offer(self, **kwargs):
        """Create a new promotional offer."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            vals = _parse_offer_data()
            if not vals.get("name"):
                ctx.set_body(ResponseBuilder.bad_request(message=_("Offer title is required.")))
                return ctx.response

            offer_vals = {
                "name": str(vals.get("name")).strip(),
                "discount_type": vals.get("discount_type") if vals.get("discount_type") in ("percentage", "fixed") else "percentage",
                "discount_value": float(vals.get("discount_value", 10.0)),
            }
            if "subtitle" in vals:
                offer_vals["subtitle"] = str(vals.get("subtitle") or "").strip()
            if "description" in vals:
                offer_vals["description"] = str(vals.get("description") or "").strip()
            if "start_date" in vals and vals.get("start_date"):
                offer_vals["start_date"] = str(vals["start_date"]).strip()
            if "end_date" in vals and vals.get("end_date"):
                offer_vals["end_date"] = str(vals["end_date"]).strip()
            if "badge_text" in vals and vals.get("badge_text"):
                offer_vals["badge_text"] = str(vals["badge_text"]).strip()
            if "active" in vals:
                offer_vals["active"] = bool(vals["active"])
            if "banner_image" in vals and vals.get("banner_image"):
                offer_vals["banner_image"] = vals["banner_image"]

            product_ids = vals.get("product_ids") or vals.get("productIds")
            if product_ids is not None:
                if isinstance(product_ids, list):
                    clean_ids = [int(p) for p in product_ids if str(p).isdigit() or isinstance(p, int)]
                    offer_vals["product_ids"] = [(6, 0, clean_ids)]

            offer = request.env["jabin.offer"].sudo().create(offer_vals)
            ctx.set_body(
                ResponseBuilder.success(
                    data=self._serialize_offer(offer, include_products=True),
                    message=_("Offer created successfully."),
                    code=201,
                )
            )
        return ctx.response

    @http.route(
        "/api/v1/offers/<int:offer_id>",
        type="http",
        auth="public",
        methods=["PUT"],
        csrf=False,
        cors="*",
    )
    @permission_required("banners.manage")
    def update_offer(self, offer_id, **kwargs):
        """Update an existing promotional offer."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            offer = request.env["jabin.offer"].sudo().browse(offer_id)
            if not offer.exists():
                ctx.set_body(ResponseBuilder.not_found(message=_("Offer not found.")))
                return ctx.response

            vals = _parse_offer_data()
            update_vals = {}
            if "name" in vals:
                update_vals["name"] = str(vals["name"]).strip()
            if "subtitle" in vals:
                update_vals["subtitle"] = str(vals["subtitle"] or "").strip()
            if "description" in vals:
                update_vals["description"] = str(vals["description"] or "").strip()
            if "discount_type" in vals and vals["discount_type"] in ("percentage", "fixed"):
                update_vals["discount_type"] = vals["discount_type"]
            if "discount_value" in vals:
                try:
                    update_vals["discount_value"] = float(vals["discount_value"])
                except (ValueError, TypeError):
                    pass
            if "start_date" in vals:
                update_vals["start_date"] = vals["start_date"] or False
            if "end_date" in vals:
                update_vals["end_date"] = vals["end_date"] or False
            if "badge_text" in vals:
                update_vals["badge_text"] = vals["badge_text"]
            if "active" in vals:
                update_vals["active"] = bool(vals["active"])
            if "banner_image" in vals and vals["banner_image"]:
                update_vals["banner_image"] = vals["banner_image"]

            product_ids = vals.get("product_ids") or vals.get("productIds")
            if product_ids is not None and isinstance(product_ids, list):
                clean_ids = [int(p) for p in product_ids if str(p).isdigit() or isinstance(p, int)]
                update_vals["product_ids"] = [(6, 0, clean_ids)]

            if update_vals:
                offer.write(update_vals)

            ctx.set_body(
                ResponseBuilder.success(
                    data=self._serialize_offer(offer, include_products=True),
                    message=_("Offer updated successfully."),
                )
            )
        return ctx.response

    @http.route(
        "/api/v1/offers/<int:offer_id>",
        type="http",
        auth="public",
        methods=["DELETE"],
        csrf=False,
        cors="*",
    )
    @permission_required("banners.manage")
    def delete_offer(self, offer_id, **kwargs):
        """Delete an existing promotional offer."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            offer = request.env["jabin.offer"].sudo().browse(offer_id)
            if not offer.exists():
                ctx.set_body(ResponseBuilder.not_found(message=_("Offer not found.")))
                return ctx.response

            offer.unlink()
            ctx.set_body(ResponseBuilder.success(message=_("Offer deleted successfully.")))
        return ctx.response

    @http.route(
        ["/api/v1/offers/<int:offer_id>/toggle-active", "/api/v1/offers/<int:offer_id>/toggle"],
        type="http",
        auth="public",
        methods=["PUT", "POST"],
        csrf=False,
        cors="*",
    )
    @permission_required("banners.manage")
    def toggle_offer_active(self, offer_id, **kwargs):
        """Toggle active state of a promotional offer."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            offer = request.env["jabin.offer"].sudo().browse(offer_id)
            if not offer.exists():
                ctx.set_body(ResponseBuilder.not_found(message=_("Offer not found.")))
                return ctx.response

            offer.active = not offer.active
            ctx.set_body(
                ResponseBuilder.success(
                    data=self._serialize_offer(offer, include_products=True),
                    message=_("Offer status toggled successfully."),
                )
            )
        return ctx.response
