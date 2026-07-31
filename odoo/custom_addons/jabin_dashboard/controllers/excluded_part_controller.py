# excluded_part_controller.py
import json
from typing import Dict, Any

from odoo import http, _
from odoo.exceptions import ValidationError
from odoo.http import request

from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder, JabinLogger
from odoo.addons.jabin_security.utils.token_auth import require_token
from odoo.addons.jabin_security.decorators.permission_required import permission_required

from ..services.excluded_part_service import ExcludedPartService


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


def _get_lang() -> str:
    """Get language from Accept-Language header."""
    lang = request.httprequest.headers.get("Accept-Language", "en_US")
    lang_map = {
        "ar": "ar_001",
        "en": "en_US"
    }
    return lang_map.get(lang.split('_')[0], "en_US")


class ExcludedPartController(BaseApiController):
    """Excluded Part REST API Controller following Category module standards."""

    @http.route(
        ["/api/v1/excluded-parts", "/api/v1/catalog/excluded-part/create"],
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    @permission_required("catalog.manage")
    def create_excluded_part(self, **kwargs):
        """Create a new excluded part."""
        # Require authentication for data modification
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            try:
                # Parse request data
                vals = _parse_request_data()

                # Create excluded part via service
                excluded_part = ExcludedPartService.create(
                    request.env,
                    vals,
                )

                # Build success response
                ctx.set_body(
                    ResponseBuilder.success(
                        data={
                            "id": excluded_part.id,
                            "name": excluded_part.name,
                            "description": excluded_part.description,
                            "active": excluded_part.active,
                        },
                        message=_("Excluded part created successfully"),
                        code=201,
                    )
                )
            except ValidationError as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=str(e),
                        code=400
                    )
                )
            except ValueError as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=str(e),
                        code=400
                    )
                )
            except Exception as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=_("An error occurred while creating the excluded part: %s") % str(e),
                        code=500
                    )
                )

        return ctx.response

    @http.route(
        ["/api/v1/excluded-parts/<int:part_id>", "/api/v1/catalog/excluded-part/<int:part_id>"],
        type="http",
        auth="public",
        methods=["PUT"],
        csrf=False,
    )
    @permission_required("catalog.manage")
    def update_excluded_part(self, part_id, **kwargs):
        """Update an existing excluded part."""
        # Require authentication for data modification
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            try:
                # Parse request data
                vals = _parse_request_data()

                # Update excluded part via service
                excluded_part = ExcludedPartService.update(
                    request.env,
                    part_id,
                    vals,
                )

                # Build success response
                ctx.set_body(
                    ResponseBuilder.success(
                        data={
                            "id": excluded_part.id,
                            "name": excluded_part.name,
                            "description": excluded_part.description,
                            "active": excluded_part.active,
                        },
                        message=_("Excluded part updated successfully"),
                    )
                )
            except ValidationError as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=str(e),
                        code=400
                    )
                )
            except ValueError as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=str(e),
                        code=400
                    )
                )
            except Exception as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=_("An error occurred while updating the excluded part: %s") % str(e),
                        code=500
                    )
                )

        return ctx.response

    @http.route(
        ["/api/v1/excluded-parts/<int:part_id>", "/api/v1/catalog/excluded-part/<int:part_id>"],
        type="http",
        auth="public",
        methods=["DELETE"],
        csrf=False,
    )
    @permission_required("catalog.manage")
    def delete_excluded_part(self, part_id, **kwargs):
        """Delete an excluded part."""
        # Require authentication for data modification
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            try:
                # Delete excluded part via service
                ExcludedPartService.delete(
                    request.env,
                    part_id,
                )

                # Build success response
                ctx.set_body(
                    ResponseBuilder.success(
                        message=_("Excluded part deleted successfully"),
                    )
                )
            except ValidationError as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=str(e),
                        code=400
                    )
                )
            except Exception as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=_("An error occurred while deleting the excluded part: %s") % str(e),
                        code=500
                    )
                )

        return ctx.response

    @http.route(
        "/api/v1/catalog/excluded-part/<int:part_id>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get(self, part_id, **kwargs):
        """Get a single excluded part by ID."""
        with self.handle() as ctx:
            try:
                # Get language from header
                lang = _get_lang()

                # Get excluded part via service
                excluded_part = ExcludedPartService.get_by_id(
                    request.env,
                    part_id,
                    lang=lang
                )

                # Build response data
                response_data = {
                    "id": excluded_part.id,
                    "name": excluded_part.name,
                    "description": excluded_part.description,
                    "active": excluded_part.active,
                    "product_count": len(excluded_part.product_ids),
                }

                ctx.set_body(
                    ResponseBuilder.success(
                        data=response_data,
                        message=_("Excluded part retrieved successfully"),
                    )
                )
            except ValidationError as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=str(e),
                        code=404
                    )
                )
            except Exception as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=_("An error occurred while retrieving the excluded part: %s") % str(e),
                        code=500
                    )
                )

        return ctx.response

    @http.route(
        "/api/v1/catalog/excluded-parts",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_list(self, **kwargs):
        """Get paginated list of excluded parts."""
        with self.handle() as ctx:
            try:
                # Parse and validate parameters
                try:
                    limit = int(kwargs.get("limit", 100))
                    offset = int(kwargs.get("offset", 0))
                except ValueError:
                    raise ValueError("Limit and offset must be valid integers.")

                if limit < 1 or limit > 1000:
                    raise ValueError("Limit must be between 1 and 1000.")
                if offset < 0:
                    raise ValueError("Offset must be at least 0.")

                # Build domain
                domain = []
                if kwargs.get("active"):
                    active = kwargs.get("active")
                    if active.lower() in ("true", "1", "yes"):
                        domain.append(("active", "=", True))
                    elif active.lower() in ("false", "0", "no"):
                        domain.append(("active", "=", False))

                # Get language from header
                lang = _get_lang()

                # Get excluded parts via service
                records, total = ExcludedPartService.get_list(
                    request.env,
                    domain=domain,
                    limit=limit,
                    offset=offset,
                    order="name",
                    lang=lang
                )

                # Build response data
                response_data = {
                    "data": [
                        {
                            "id": part.id,
                            "name": part.name,
                            "description": part.description,
                            "active": part.active,
                        }
                        for part in records
                    ],
                    "pagination": {
                        "total": total,
                        "limit": limit,
                        "offset": offset,
                    }
                }

                ctx.set_body(
                    ResponseBuilder.success(
                        data=response_data,
                        message=_("Excluded parts retrieved successfully"),
                    )
                )
            except ValidationError as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=str(e),
                        code=400
                    )
                )
            except ValueError as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=str(e),
                        code=400
                    )
                )
            except Exception as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=_("An error occurred while retrieving excluded parts: %s") % str(e),
                        code=500
                    )
                )

        return ctx.response