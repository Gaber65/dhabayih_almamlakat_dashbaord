# category_controller.py
import base64
import json
from typing import Dict, Any, Optional

from odoo import http, _
from odoo.http import request

from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder, JabinLogger
from odoo.addons.jabin_security.utils.token_auth import require_token
from odoo.addons.jabin_security.decorators.permission_required import permission_required

from ..services.category_service import CategoryService
from ..services.product_service import ProductService
from .product_controller import _serialize_product

_logger = JabinLogger.get("category.controller")

# Allowed image MIME types for upload
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


def _read_image_upload(file_field_name: str = "image") -> Optional[bytes]:
    """
    Read an uploaded image from multipart/form-data.

    Returns a base64-encoded bytes string suitable for Odoo Binary fields,
    or None if no file was uploaded.
    Raises ValueError with a human-readable message on invalid input.
    """
    uploaded = request.httprequest.files.get(file_field_name)
    if not uploaded:
        return None

    content_type = (uploaded.content_type or "").lower().split(";")[0].strip()
    if content_type not in _ALLOWED_IMAGE_TYPES:
        raise ValueError(
            f"Unsupported image type '{content_type}'. "
            "Allowed: jpg, jpeg, png, webp."
        )

    raw = uploaded.read()
    if not raw:
        raise ValueError("Uploaded image file is empty.")

    return base64.b64encode(raw)


def _parse_request_data() -> Dict[str, Any]:
    """
    Parse request data from either multipart/form-data or JSON.

    Returns a dictionary of values ready for service layer consumption.
    """
    content_type = request.httprequest.content_type or ""
    vals = {}

    if "multipart/form-data" in content_type:
        # Pull scalar fields from form data
        vals = {
            k: v
            for k, v in request.httprequest.form.items()
            if k not in ["id", "image", "remove_image"]
        }

        # Handle boolean fields
        if "active" in vals:
            vals["active"] = vals["active"].lower() not in ("false", "0", "no")

        # Handle integer fields
        if "sequence" in vals:
            try:
                vals["sequence"] = int(vals["sequence"])
            except ValueError:
                raise ValueError("Sequence must be a valid integer.")

        # Handle image upload
        image_data = _read_image_upload("image")
        if image_data is not None:
            vals["image"] = image_data

        # Handle image removal
        remove_image = request.httprequest.form.get("remove_image")
        if remove_image and remove_image.lower() not in ("false", "0", "no"):
            vals["image"] = False

    else:
        # Parse JSON body
        raw = request.httprequest.data
        if raw:
            try:
                vals = json.loads(raw)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON payload.")

        # Remove id if present
        vals.pop("id", None)

        # Handle image removal from JSON
        if vals.get("remove_image"):
            vals["image"] = False
            vals.pop("remove_image", None)

    return vals


class CategoryController(BaseApiController):
    """Category REST API Controller following enterprise standards."""

    @http.route(
        ["/api/v1/categories", "/api/v1/catalog/category/create"],
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    @permission_required("categories.manage")
    def create_category(self, **kwargs):
        """Create a new category."""
        # Require authentication for data modification
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            # Parse request data
            vals = _parse_request_data()

            # Create category via service
            category = CategoryService.create_category(
                request.env,
                vals,
            )

            # Build success response - use success() NOT http_success()
            # success() returns a DICTIONARY envelope
            ctx.set_body(
                ResponseBuilder.success(
                    data={
                        "id": category.id,
                        "name": category.name,
                        "sequence": category.sequence,
                        "active": category.active,
                        "product_count": category.product_count,
                    },
                    message=_("Category created successfully"),
                    code=201,
                )
            )

        return ctx.response

    @http.route(
        ["/api/v1/categories/<int:category_id>", "/api/v1/catalog/category/<int:category_id>"],
        type="http",
        auth="public",
        methods=["PUT"],
        csrf=False,
    )
    @permission_required("categories.manage")
    def update_category(self, category_id, **kwargs):
        """Update an existing category."""
        # Require authentication for data modification
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            # Parse request data
            vals = _parse_request_data()

            # Update category via service
            category = CategoryService.update_category(
                request.env,
                category_id,
                vals,
            )

            # Build success response - use success() NOT http_success()
            ctx.set_body(
                ResponseBuilder.success(
                    data={
                        "id": category.id,
                        "name": category.name,
                        "sequence": category.sequence,
                        "active": category.active,
                        "product_count": category.product_count,
                    },
                    message=_("Category updated successfully"),
                )
            )

        return ctx.response

    @http.route(
        ["/api/v1/categories/<int:category_id>", "/api/v1/catalog/category/<int:category_id>"],
        type="http",
        auth="public",
        methods=["DELETE"],
        csrf=False,
    )
    @permission_required("categories.manage")
    def delete_category(self, category_id, **kwargs):
        """Delete a category."""
        # Require authentication for data modification
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            # Delete category via service
            CategoryService.delete_category(
                request.env,
                category_id,
            )

            # Only reachable if deletion succeeded
            # Build success response - use success() NOT http_success()
            ctx.set_body(
                ResponseBuilder.success(
                    message=_("Category deleted successfully"),
                )
            )

        return ctx.response

    @http.route(
        "/api/v1/catalog/categories",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_categories(self, **kwargs):
        """Get paginated list of categories."""
        # No authentication required for GET
        with self.handle() as ctx:
            # Parse parameters
            try:
                limit = int(kwargs.get("limit", 100))
                offset = int(kwargs.get("offset", 0))
            except ValueError:
                raise ValueError("Limit and offset must be valid integers.")

            # Validate limit and offset
            if limit < 1:
                raise ValueError("Limit must be at least 1.")
            if offset < 0:
                raise ValueError("Offset must be at least 0.")

            # Handle language
            lang = request.httprequest.headers.get("Accept-Language", "en_US")
            # Map to Odoo language codes
            lang_map = {
                "ar": "ar_001",
                "en": "en_US"
            }
            lang = lang_map.get(lang.split('_')[0], "en_US")

            # Get categories via service
            categories = CategoryService.get_categories(
                request.env,
                domain=[],
                limit=limit,
                offset=offset,
                order="sequence, name",
                lang=lang
            )

            base_url = request.httprequest.host_url.rstrip('/')

            # Build response data
            response_data = {
                "categories": [
                    {
                        "id": category.id,
                        "name": category.name,
                        "image": BaseApiController.build_image_url("jabin.category", category.id, "image", bool(category.image)),
                        "image_url": BaseApiController.build_image_url("jabin.category", category.id, "image", bool(category.image)),
                        "description": category.description,
                        "sequence": category.sequence,
                        "active": category.active,
                        "product_count": category.product_count,
                    }
                    for category in categories
                ],
                "total": len(categories),
                "limit": limit,
                "offset": offset,
            }

            # Build success response - use success() NOT http_success()
            ctx.set_body(
                ResponseBuilder.success(
                    data=response_data,
                    message=_("Categories retrieved successfully"),
                )
            )

        return ctx.response

    @http.route(
        "/api/v1/catalog/category/<int:category_id>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_category(self, category_id, **kwargs):
        """Get a single category by ID."""
        # No authentication required for GET
        with self.handle() as ctx:
            # Handle language
            lang = request.httprequest.headers.get("Accept-Language", "en_US")
            lang_map = {
                "ar": "ar_001",
                "en": "en_US"
            }
            lang = lang_map.get(lang.split('_')[0], "en_US")

            # Get category via service
            category = CategoryService.get_category(
                request.env,
                category_id,
                lang=lang
            )

            base_url = request.httprequest.host_url.rstrip('/')

            # Build response data
            response_data = {
                "id": category.id,
                "name": category.name,
                "image": BaseApiController.build_image_url("jabin.category", category.id, "image", bool(category.image)),
                "image_url": BaseApiController.build_image_url("jabin.category", category.id, "image", bool(category.image)),
                "description": category.description,
                "sequence": category.sequence,
                "active": category.active,
                "product_count": category.product_count,
            }

            # Build success response - use success() NOT http_success()
            ctx.set_body(
                ResponseBuilder.success(
                    data=response_data,
                    message=_("Category retrieved successfully"),
                )
            )

        return ctx.response

    @http.route(
        [
            "/api/v1/categories/<int:category_id>/products",
            "/api/v1/catalog/category/<int:category_id>/products",
        ],
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_category_products(self, category_id, **kwargs):
        """Get products of a specific category."""
        # No authentication required for GET
        with self.handle() as ctx:
            # First verify category exists
            CategoryService.check_category_exists(request.env, category_id)

            # Handle language
            lang = request.httprequest.headers.get("Accept-Language", "en_US")
            lang_map = {
                "ar": "ar_001",
                "en": "en_US"
            }
            lang = lang_map.get(lang.split('_')[0], "en_US")

            # Parse parameters (pagination)
            try:
                limit = int(kwargs.get("limit", 100))
                offset = int(kwargs.get("offset", 0))
            except ValueError:
                raise ValueError("Limit and offset must be valid integers.")

            if limit < 1 or limit > 1000:
                raise ValueError("Limit must be between 1 and 1000.")
            if offset < 0:
                raise ValueError("Offset must be at least 0.")

            # Filter domain
            domain = [("category_id", "=", category_id)]

            # Generic filter param helper (same as product_controller.py)
            filter_param = kwargs.get("filter")
            if filter_param == "best_seller":
                domain.append(("is_best_seller", "=", True))
            elif filter_param == "featured":
                domain.append(("is_featured", "=", True))
            elif filter_param == "offers":
                domain.append(("is_on_offer", "=", True))

            if kwargs.get("active"):
                active = kwargs["active"]
                if active.lower() in ("true", "1", "yes"):
                    domain.append(("active", "=", True))
                elif active.lower() in ("false", "0", "no"):
                    domain.append(("active", "=", False))

            if kwargs.get("on_offer"):
                on_offer = kwargs["on_offer"]
                if on_offer.lower() in ("true", "1", "yes"):
                    domain.append(("is_on_offer", "=", True))
                elif on_offer.lower() in ("false", "0", "no"):
                    domain.append(("is_on_offer", "=", False))

            if kwargs.get("is_featured"):
                featured = kwargs["is_featured"]
                if featured.lower() in ("true", "1", "yes"):
                    domain.append(("is_featured", "=", True))
                elif featured.lower() in ("false", "0", "no"):
                    domain.append(("is_featured", "=", False))

            if kwargs.get("is_best_seller"):
                best_seller = kwargs["is_best_seller"]
                if best_seller.lower() in ("true", "1", "yes"):
                    domain.append(("is_best_seller", "=", True))
                elif best_seller.lower() in ("false", "0", "no"):
                    domain.append(("is_best_seller", "=", False))

            # Get products via service
            records, total = ProductService.get_list(
                request.env,
                domain=domain,
                limit=limit,
                offset=offset,
                order="name",
                lang=lang
            )

            # Build response data
            response_data = {
                "products": [
                    _serialize_product(p)
                    for p in records
                ],
                "total": total,
                "limit": limit,
                "offset": offset,
            }

            # Build success response
            ctx.set_body(
                ResponseBuilder.success(
                    data=response_data,
                    message=_("Products retrieved successfully"),
                )
            )

        return ctx.response