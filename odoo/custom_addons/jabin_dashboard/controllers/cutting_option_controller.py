# cutting_option_controller.py
import json
from typing import Dict, Any, Optional

from odoo import http, _
from odoo.http import request

from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder, JabinLogger
from odoo.addons.jabin_security.utils.token_auth import require_token
from odoo.addons.jabin_security.decorators.permission_required import permission_required

from ..services.cutting_option_service import CuttingOptionService

_logger = JabinLogger.get("cutting_option.controller")


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


class CuttingOptionController(BaseApiController):
    """Cutting Option REST API Controller following enterprise standards."""

    @http.route(
        ["/api/v1/cutting-options", "/api/v1/catalog/cutting-option/create"],
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    @permission_required("catalog.manage")
    def create_cutting_option(self, **kwargs):
        """Create a new cutting option."""
        # Require authentication for data modification
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            # Parse request data
            vals = _parse_request_data()

            # Create cutting option via service
            cutting_option = CuttingOptionService.create_cutting_option(
                request.env,
                vals,
            )

            # Build success response
            ctx.set_body(
                ResponseBuilder.success(
                    data={
                        "id": cutting_option.id,
                        "name": cutting_option.name,
                        "description": cutting_option.description,
                        "active": cutting_option.active,
                    },
                    message=_("Cutting option created successfully"),
                    code=201,
                )
            )

        return ctx.response

    @http.route(
        ["/api/v1/cutting-options/<int:option_id>", "/api/v1/catalog/cutting-option/<int:option_id>"],
        type="http",
        auth="public",
        methods=["PUT"],
        csrf=False,
    )
    @permission_required("catalog.manage")
    def update_cutting_option(self, option_id, **kwargs):
        """Update an existing cutting option."""
        # Require authentication for data modification
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            # Parse request data
            vals = _parse_request_data()

            # Update cutting option via service
            cutting_option = CuttingOptionService.update_cutting_option(
                request.env,
                option_id,
                vals,
            )

            # Build success response
            ctx.set_body(
                ResponseBuilder.success(
                    data={
                        "id": cutting_option.id,
                        "name": cutting_option.name,
                        "description": cutting_option.description,
                        "active": cutting_option.active,
                    },
                    message=_("Cutting option updated successfully"),
                )
            )

        return ctx.response

    @http.route(
        ["/api/v1/cutting-options/<int:option_id>", "/api/v1/catalog/cutting-option/<int:option_id>"],
        type="http",
        auth="public",
        methods=["DELETE"],
        csrf=False,
    )
    @permission_required("catalog.manage")
    def delete_cutting_option(self, option_id, **kwargs):
        """Delete a cutting option."""
        # Require authentication for data modification
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            # Delete cutting option via service
            CuttingOptionService.delete_cutting_option(
                request.env,
                option_id,
            )

            # Only reachable if deletion succeeded
            ctx.set_body(
                ResponseBuilder.success(
                    message=_("Cutting option deleted successfully"),
                )
            )

        return ctx.response

    @http.route(
        "/api/v1/catalog/cutting-option/<int:option_id>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_cutting_option(self, option_id, **kwargs):
        """Get a single cutting option by ID."""
        # No authentication required for GET
        with self.handle() as ctx:
            # Handle language
            lang = request.httprequest.headers.get("Accept-Language", "en_US")
            lang_map = {
                "ar": "ar_001",
                "en": "en_US"
            }
            lang = lang_map.get(lang.split('_')[0], "en_US")

            # Get cutting option via service
            cutting_option = CuttingOptionService.get_cutting_option(
                request.env,
                option_id,
                lang=lang
            )

            # Build response data
            response_data = {
                "id": cutting_option.id,
                "name": cutting_option.name,
                "description": cutting_option.description,
                "active": cutting_option.active,
                "product_count": len(cutting_option.product_ids),
            }

            ctx.set_body(
                ResponseBuilder.success(
                    data=response_data,
                    message=_("Cutting option retrieved successfully"),
                )
            )

        return ctx.response

    @http.route(
        "/api/v1/catalog/cutting-options",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_cutting_options(self, **kwargs):
        """Get paginated list of cutting options."""
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

            # Get cutting options via service
            cutting_options = CuttingOptionService.get_cutting_options(
                request.env,
                domain=domain,
                limit=limit,
                offset=offset,
                order="name",
                lang=lang
            )

            # Build response data
            response_data = {
                "cutting_options": [
                    {
                        "id": option.id,
                        "name": option.name,
                        "description": option.description,
                        "active": option.active,
                    }
                    for option in cutting_options
                ],
                "total": len(cutting_options),
                "limit": limit,
                "offset": offset,
            }

            ctx.set_body(
                ResponseBuilder.success(
                    data=response_data,
                    message=_("Cutting options retrieved successfully"),
                )
            )

        return ctx.response
