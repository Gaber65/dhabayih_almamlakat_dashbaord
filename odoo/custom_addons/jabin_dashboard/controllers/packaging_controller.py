# packaging_controller.py
import json
from typing import Dict, Any, Optional

from odoo import http, _
from odoo.http import request

from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder, JabinLogger
from odoo.addons.jabin_security.utils.token_auth import require_token
from odoo.addons.jabin_security.decorators.permission_required import permission_required

from ..services.packaging_service import PackagingService

_logger = JabinLogger.get("packaging.controller")


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
            if k not in ["id"]
        }

        # Handle boolean fields
        if "active" in vals:
            vals["active"] = vals["active"].lower() not in ("false", "0", "no")

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

    return vals


class PackagingController(BaseApiController):
    """Packaging REST API Controller following enterprise standards."""

    @http.route(
        ["/api/v1/packagings", "/api/v1/catalog/packaging/create"],
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    @permission_required("catalog.manage")
    def create_packaging(self, **kwargs):
        """Create new packaging."""
        # Require authentication for data modification
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            # Parse request data
            vals = _parse_request_data()

            # Create packaging via service
            packaging = PackagingService.create_packaging(
                request.env,
                vals,
            )

            # Build success response
            ctx.set_body(
                ResponseBuilder.success(
                    data={
                        "id": packaging.id,
                        "name": packaging.name,
                        "description": packaging.description,
                        "active": packaging.active,
                    },
                    message=_("Packaging created successfully"),
                    code=201,
                )
            )

        return ctx.response

    @http.route(
        ["/api/v1/packagings/<int:packaging_id>", "/api/v1/catalog/packaging/<int:packaging_id>"],
        type="http",
        auth="public",
        methods=["PUT"],
        csrf=False,
    )
    @permission_required("catalog.manage")
    def update_packaging(self, packaging_id, **kwargs):
        """Update existing packaging."""
        # Require authentication for data modification
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            # Parse request data
            vals = _parse_request_data()

            # Update packaging via service
            packaging = PackagingService.update_packaging(
                request.env,
                packaging_id,
                vals,
            )

            # Build success response
            ctx.set_body(
                ResponseBuilder.success(
                    data={
                        "id": packaging.id,
                        "name": packaging.name,
                        "description": packaging.description,
                        "active": packaging.active,
                    },
                    message=_("Packaging updated successfully"),
                )
            )

        return ctx.response

    @http.route(
        ["/api/v1/packagings/<int:packaging_id>", "/api/v1/catalog/packaging/<int:packaging_id>"],
        type="http",
        auth="public",
        methods=["DELETE"],
        csrf=False,
    )
    @permission_required("catalog.manage")
    def delete_packaging(self, packaging_id, **kwargs):
        """Delete packaging."""
        # Require authentication for data modification
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            # Delete packaging via service
            PackagingService.delete_packaging(
                request.env,
                packaging_id,
            )

            # Only reachable if deletion succeeded
            ctx.set_body(
                ResponseBuilder.success(
                    message=_("Packaging deleted successfully"),
                )
            )

        return ctx.response

    @http.route(
        "/api/v1/catalog/packaging/<int:packaging_id>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_packaging(self, packaging_id, **kwargs):
        """Get a single packaging by ID."""
        # No authentication required for GET
        with self.handle() as ctx:
            # Handle language
            lang = request.httprequest.headers.get("Accept-Language", "en_US")
            lang_map = {
                "ar": "ar_001",
                "en": "en_US"
            }
            lang = lang_map.get(lang.split('_')[0], "en_US")

            # Get packaging via service
            packaging = PackagingService.get_packaging(
                request.env,
                packaging_id,
                lang=lang
            )

            # Build response data
            response_data = {
                "id": packaging.id,
                "name": packaging.name,
                "description": packaging.description,
                "active": packaging.active,
                "product_count": len(packaging.product_ids),
            }

            ctx.set_body(
                ResponseBuilder.success(
                    data=response_data,
                    message=_("Packaging retrieved successfully"),
                )
            )

        return ctx.response

    @http.route(
        "/api/v1/catalog/packagings",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_packagings(self, **kwargs):
        """Get paginated list of packagings."""
        # No authentication required for GET
        with self.handle() as ctx:
            # Parse parameters
            try:
                limit = int(kwargs.get("limit", 100))
                offset = int(kwargs.get("offset", 0))
                active = kwargs.get("active")
            except ValueError:
                raise ValueError("Limit and offset must be valid integers.")

            # Validate limit and offset
            if limit < 1:
                raise ValueError("Limit must be at least 1.")
            if offset < 0:
                raise ValueError("Offset must be at least 0.")

            # Build domain
            domain = []
            if active is not None:
                domain.append(("active", "=", active.lower() == "true"))

            # Handle language
            lang = request.httprequest.headers.get("Accept-Language", "en_US")
            lang_map = {
                "ar": "ar_001",
                "en": "en_US"
            }
            lang = lang_map.get(lang.split('_')[0], "en_US")

            # Get packagings via service
            packagings = PackagingService.get_packagings(
                request.env,
                domain=domain,
                limit=limit,
                offset=offset,
                order="name",
                lang=lang
            )

            # Build response data
            response_data = {
                "packagings": [
                    {
                        "id": packaging.id,
                        "name": packaging.name,
                        "description": packaging.description,
                        "active": packaging.active,
                    }
                    for packaging in packagings
                ],
                "total": len(packagings),
                "limit": limit,
                "offset": offset,
            }

            ctx.set_body(
                ResponseBuilder.success(
                    data=response_data,
                    message=_("Packagings retrieved successfully"),
                )
            )

        return ctx.response