# banner_controller.py
import base64
import json
from typing import Dict, Any, Optional

from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError

from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder, JabinLogger
from odoo.addons.jabin_security.utils.token_auth import require_token
from odoo.addons.jabin_security.decorators.permission_required import permission_required

from ..services.banner_service import BannerService
from ..validators.banner_validator import BannerValidator

_logger = JabinLogger.get("banner.controller")

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


class BannerController(BaseApiController):
    """Banner REST API Controller following enterprise standards."""

    @http.route(
        "/api/v1/banner/create",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    @permission_required("banners.manage")
    def create_banner(self, **kwargs):
        """Create a new banner."""
        # Require authentication for data modification
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            # Parse request data
            vals = _parse_request_data()

            # Create banner via service
            banner = BannerService.create_banner(
                request.env,
                vals,
            )

            base_url = request.httprequest.host_url.rstrip('/')

            # Build success response
            ctx.set_body(
                ResponseBuilder.success(
                    data={
                        "id": banner.id,
                        "name": banner.name,
                        "image": BaseApiController.build_image_url("banner", banner.id, "image", bool(banner.image)),
                        "active": banner.active,
                    },
                    message=_("Banner created successfully"),
                    code=201,
                )
            )

        return ctx.response

    @http.route(
        ["/api/v1/banners/<int:banner_id>", "/api/v1/banner/<int:banner_id>"],
        type="http",
        auth="public",
        methods=["PUT"],
        csrf=False,
    )
    @permission_required("banners.manage")
    def update_banner(self, banner_id, **kwargs):
        """Update an existing banner."""
        # Require authentication for data modification
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            # Parse request data
            vals = _parse_request_data()

            # Update banner via service
            banner = BannerService.update_banner(
                request.env,
                banner_id,
                vals,
            )

            base_url = request.httprequest.host_url.rstrip('/')

            # Build success response
            ctx.set_body(
                ResponseBuilder.success(
                    data={
                        "id": banner.id,
                        "name": banner.name,
                        "image": BaseApiController.build_image_url("banner", banner.id, "image", bool(banner.image)),
                        "active": banner.active,
                    },
                    message=_("Banner updated successfully"),
                )
            )

        return ctx.response

    @http.route(
        ["/api/v1/banners/<int:banner_id>", "/api/v1/banner/<int:banner_id>"],
        type="http",
        auth="public",
        methods=["DELETE"],
        csrf=False,
    )
    @permission_required("banners.manage")
    def delete_banner(self, banner_id, **kwargs):
        """Delete a banner."""
        # Require authentication for data modification
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            # Delete banner via service
            BannerService.delete_banner(
                request.env,
                banner_id,
            )

            # Only reachable if deletion succeeded
            ctx.set_body(
                ResponseBuilder.success(
                    message=_("Banner deleted successfully"),
                )
            )

        return ctx.response

    @http.route(
        "/api/v1/banners",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_banners(self, **kwargs):
        """Get paginated list of banners."""
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
            lang_map = {
                "ar": "ar_001",
                "en": "en_US"
            }
            lang = lang_map.get(lang.split('_')[0], "en_US")

            # Get active banners by default
            domain = kwargs.get("all") == "1" and [] or [("active", "=", True)]
            if kwargs.get("active") == "0":
                domain = [("active", "=", False)]
            elif kwargs.get("active") == "1":
                domain = [("active", "=", True)]

            # Get banners via service
            banners = BannerService.get_banners(
                request.env,
                domain=domain,
                limit=limit,
                offset=offset,
                order="name",
                lang=lang
            )

            base_url = request.httprequest.host_url.rstrip('/')

            # Build response data
            response_data = {
                "banners": [
                    {
                        "id": banner.id,
                        "name": banner.name,
                        "image": BaseApiController.build_image_url("banner", banner.id, "image", bool(banner.image)),
                        "image_url": BaseApiController.build_image_url("banner", banner.id, "image", bool(banner.image)),
                        "active": banner.active,
                    }
                    for banner in banners
                ],
                "total": len(banners),
                "limit": limit,
                "offset": offset,
            }

            ctx.set_body(
                ResponseBuilder.success(
                    data=response_data,
                    message=_("Banners retrieved successfully"),
                )
            )

        return ctx.response

    @http.route(
        "/api/v1/banner/<int:banner_id>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_banner(self, banner_id, **kwargs):
        """Get a single banner by ID."""
        with self.handle() as ctx:
            # Handle language
            lang = request.httprequest.headers.get("Accept-Language", "en_US")
            lang_map = {
                "ar": "ar_001",
                "en": "en_US"
            }
            lang = lang_map.get(lang.split('_')[0], "en_US")

            # Get banner via service
            banner = BannerService.get_banner(
                request.env,
                banner_id,
                lang=lang
            )

            base_url = request.httprequest.host_url.rstrip('/')

            # Build response data
            response_data = {
                "id": banner.id,
                "name": banner.name,
                "image": BaseApiController.build_image_url("banner", banner.id, "image", bool(banner.image)),
                "image_url": BaseApiController.build_image_url("banner", banner.id, "image", bool(banner.image)),
                "active": banner.active,
            }

            ctx.set_body(
                ResponseBuilder.success(
                    data=response_data,
                    message=_("Banner retrieved successfully"),
                )
            )

        return ctx.response

    @http.route(
        ["/api/v1/banners/<int:banner_id>/toggle-active", "/api/v1/banner/<int:banner_id>/toggle-active"],
        type="http",
        auth="public",
        methods=["POST", "PATCH"],
        csrf=False,
    )
    @permission_required("banners.manage")
    def toggle_banner_active(self, banner_id, **kwargs):
        """Toggle active status of a banner."""
        # Require authentication for data modification
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            # Toggle banner via service
            banner = BannerService.toggle_banner_active(
                request.env,
                banner_id,
            )

            base_url = request.httprequest.host_url.rstrip('/')

            ctx.set_body(
                ResponseBuilder.success(
                    data={
                        "id": banner.id,
                        "name": banner.name,
                        "active": banner.active,
                        "image": BaseApiController.build_image_url("banner", banner.id, "image", bool(banner.image)),
                    },
                    message=_("Banner status toggled successfully"),
                )
            )

        return ctx.response