# -*- coding: utf-8 -*-
# product_size_controller.py
import json
from typing import Dict, Any, Optional

from odoo import http, _
from odoo.http import request

from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder, JabinLogger
from odoo.addons.jabin_security.utils.token_auth import require_token
from odoo.addons.jabin_security.decorators.permission_required import permission_required

_logger = JabinLogger.get("product_size.controller")


def _parse_size_request_data() -> Dict[str, Any]:
    """Parse request data for product size."""
    content_type = request.httprequest.content_type or ""
    vals = {}

    if "multipart/form-data" in content_type:
        vals = {
            k: v
            for k, v in request.httprequest.form.items()
            if k not in ["id"]
        }
    else:
        raw = request.httprequest.data
        if raw:
            try:
                vals = json.loads(raw)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON payload.")

    vals.pop("id", None)

    # Boolean mapping
    if "active" in vals:
        if isinstance(vals["active"], str):
            vals["active"] = vals["active"].lower() not in ("false", "0", "no")
    if "is_active" in vals:
        vals["active"] = bool(vals.pop("is_active"))

    if "is_default" in vals:
        if isinstance(vals["is_default"], str):
            vals["is_default"] = vals["is_default"].lower() not in ("false", "0", "no")

    # Numeric fields
    if "price" in vals and vals["price"] is not None:
        try:
            vals["price"] = float(vals["price"])
        except ValueError:
            raise ValueError("Price must be a valid number.")

    if "calories" in vals and vals["calories"] is not None:
        try:
            vals["calories"] = int(vals["calories"])
        except ValueError:
            vals["calories"] = 243

    if "sequence" in vals and vals["sequence"] is not None:
        try:
            vals["sequence"] = int(vals["sequence"])
        except ValueError:
            vals["sequence"] = 10

    if "product_id" in vals and vals["product_id"] is not None:
        try:
            vals["product_id"] = int(vals["product_id"])
        except ValueError:
            raise ValueError("Product ID must be a valid integer.")

    # String sanitization
    if "name" in vals and vals["name"]:
        vals["name"] = str(vals["name"]).strip()

    if "sub_title" in vals and vals["sub_title"]:
        vals["sub_title"] = str(vals["sub_title"]).strip()

    # Pop read-only compute fields
    vals.pop("loyalty_points", None)
    vals.pop("points_price", None)

    return vals


def _serialize_size(size) -> Dict[str, Any]:
    """Serialize a jabin.product.size record to dict."""
    return {
        "id": size.id,
        "product_id": size.product_id.id,
        "product_name": size.product_id.name if size.product_id else "",
        "name": size.name or "",
        "sub_title": size.sub_title or "",
        "price": size.price,
        "calories": size.calories,
        "loyalty_points": size.loyalty_points,
        "points_price": size.points_price,
        "sequence": size.sequence,
        "is_default": size.is_default,
        "active": size.active,
        "is_active": size.active,
    }


class ProductSizeController(BaseApiController):
    """Product Carcass Size REST API Controller."""

    @http.route(
        ["/api/v1/sizes", "/api/v1/catalog/sizes"],
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        cors="*",
    )
    def get_sizes(self, **kwargs):
        """Get product sizes, optionally filtered by product_id."""
        with self.handle() as ctx:
            try:
                domain = []
                if kwargs.get("product_id"):
                    try:
                        domain.append(("product_id", "=", int(kwargs["product_id"])))
                    except ValueError:
                        raise ValueError("Product ID must be a valid integer.")

                if kwargs.get("active") is not None:
                    active_str = str(kwargs.get("active")).lower()
                    if active_str in ("true", "1", "yes"):
                        domain.append(("active", "=", True))
                    elif active_str in ("false", "0", "no"):
                        domain.append(("active", "=", False))

                limit = int(kwargs.get("limit", 100))
                offset = int(kwargs.get("offset", 0))

                Model = request.env["jabin.product.size"].sudo()
                total = Model.search_count(domain)
                records = Model.search(domain, limit=limit, offset=offset, order="sequence, id")

                ctx.set_body(
                    ResponseBuilder.success(
                        data=[_serialize_size(s) for s in records],
                        meta={"total": total, "limit": limit, "offset": offset},
                        message=_("Sizes retrieved successfully"),
                    )
                )
            except Exception as e:
                ctx.set_body(ResponseBuilder.error(message=str(e), code=400))

        return ctx.response

    @http.route(
        ["/api/v1/sizes/<int:size_id>", "/api/v1/catalog/sizes/<int:size_id>"],
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        cors="*",
    )
    def get_size_detail(self, size_id, **kwargs):
        """Get size detail by ID."""
        with self.handle() as ctx:
            size = request.env["jabin.product.size"].sudo().browse(size_id)
            if not size.exists():
                ctx.set_body(ResponseBuilder.not_found(message=_("Size not found")))
            else:
                ctx.set_body(
                    ResponseBuilder.success(
                        data=_serialize_size(size),
                        message=_("Size retrieved successfully"),
                    )
                )
        return ctx.response

    @http.route(
        ["/api/v1/sizes", "/api/v1/catalog/sizes"],
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    @permission_required("products.manage")
    def create_size(self, **kwargs):
        """Create a new product size."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            try:
                vals = _parse_size_request_data()
                if not vals.get("product_id"):
                    raise ValueError(_("Field 'product_id' is required."))
                if not vals.get("name"):
                    raise ValueError(_("Field 'name' is required."))
                if "price" not in vals:
                    raise ValueError(_("Field 'price' is required."))

                # Verify product exists
                product = request.env["jabin.product"].sudo().browse(vals["product_id"])
                if not product.exists():
                    raise ValueError(_("Specified product does not exist."))

                size = request.env["jabin.product.size"].sudo().create(vals)
                if not product.has_sizes:
                    product.sudo().write({"has_sizes": True})

                ctx.set_body(
                    ResponseBuilder.success(
                        data=_serialize_size(size),
                        message=_("Size created successfully"),
                        code=201,
                    )
                )
            except Exception as e:
                ctx.set_body(ResponseBuilder.error(message=str(e), code=400))

        return ctx.response

    @http.route(
        ["/api/v1/sizes/<int:size_id>", "/api/v1/catalog/sizes/<int:size_id>"],
        type="http",
        auth="public",
        methods=["PUT"],
        csrf=False,
        cors="*",
    )
    @permission_required("products.manage")
    def update_size(self, size_id, **kwargs):
        """Update an existing product size."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            try:
                size = request.env["jabin.product.size"].sudo().browse(size_id)
                if not size.exists():
                    ctx.set_body(ResponseBuilder.not_found(message=_("Size not found")))
                    return ctx.response

                vals = _parse_size_request_data()
                size.write(vals)

                ctx.set_body(
                    ResponseBuilder.success(
                        data=_serialize_size(size),
                        message=_("Size updated successfully"),
                    )
                )
            except Exception as e:
                ctx.set_body(ResponseBuilder.error(message=str(e), code=400))

        return ctx.response

    @http.route(
        ["/api/v1/sizes/<int:size_id>", "/api/v1/catalog/sizes/<int:size_id>"],
        type="http",
        auth="public",
        methods=["DELETE"],
        csrf=False,
        cors="*",
    )
    @permission_required("products.manage")
    def delete_size(self, size_id, **kwargs):
        """Delete a product size."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            try:
                size = request.env["jabin.product.size"].sudo().browse(size_id)
                if not size.exists():
                    ctx.set_body(ResponseBuilder.not_found(message=_("Size not found")))
                    return ctx.response

                product = size.product_id
                size.unlink()

                # If no more sizes remain, update has_sizes
                if product and product.exists() and not product.size_ids:
                    product.sudo().write({"has_sizes": False})

                ctx.set_body(
                    ResponseBuilder.success(
                        message=_("Size deleted successfully"),
                    )
                )
            except Exception as e:
                ctx.set_body(ResponseBuilder.error(message=str(e), code=400))

        return ctx.response
