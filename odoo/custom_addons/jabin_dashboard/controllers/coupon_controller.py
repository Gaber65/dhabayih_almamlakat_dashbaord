# coupon_controller.py
import json
from typing import Dict, Any, Optional

from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError

from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder, JabinLogger
from odoo.addons.jabin_security.utils.token_auth import require_token
from odoo.addons.jabin_security.decorators.permission_required import permission_required

from ..services.coupon_service import CouponService

_logger = JabinLogger.get("coupon.controller")


def _get_auth_user_id() -> Optional[int]:
    """Helper to extract user ID from Authorization Bearer token."""
    try:
        raw_header = request.httprequest.headers.get("Authorization", "")
    except Exception:
        return None

    token = ""
    if raw_header:
        parts = raw_header.split(None, 1)
        if len(parts) == 2 and parts[0].lower() == 'bearer':
            token = parts[1].strip()

    if not token:
        return None

    try:
        from odoo.addons.jabin_security.utils.jwt_utils import JWTUtils
        claims = JWTUtils.decode_token(token)
        return JWTUtils.get_user_id(claims)
    except Exception:
        return None


def _parse_request_data() -> Dict[str, Any]:
    """Parse request data from either multipart/form-data or JSON."""
    content_type = request.httprequest.content_type or ""
    vals = {}

    if "multipart/form-data" in content_type:
        vals = {
            k: v
            for k, v in request.httprequest.form.items()
            if k not in ["id"]
        }
        if "active" in vals:
            vals["active"] = vals["active"].lower() not in ("false", "0", "no")

        for num_field in ["discount_value", "minimum_order_amount", "maximum_discount"]:
            if num_field in vals and vals[num_field] != "":
                try:
                    vals[num_field] = float(vals[num_field])
                except ValueError:
                    raise ValueError(f"{num_field} must be a valid number.")

        for int_field in ["usage_limit", "usage_limit_per_customer"]:
            if int_field in vals and vals[int_field] != "":
                try:
                    vals[int_field] = int(vals[int_field])
                except ValueError:
                    raise ValueError(f"{int_field} must be a valid integer.")
    else:
        raw = request.httprequest.data
        if raw:
            try:
                vals = json.loads(raw)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON payload.")
        vals.pop("id", None)

    return vals


class CouponController(BaseApiController):
    """Coupon / Promo Code REST API Controller following enterprise standards."""

    @http.route(
        "/api/v1/coupons",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    @permission_required("coupons.manage")
    def create_coupon(self, **kwargs):
        """Create a new coupon (Admin API)."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            vals = _parse_request_data()
            coupon = CouponService.create_coupon(request.env, vals)

            ctx.set_body(
                ResponseBuilder.success(
                    data=coupon.get_summary_dict(),
                    message=_("Coupon created successfully"),
                    code=201,
                )
            )
        return ctx.response

    @http.route(
        "/api/v1/coupons/<int:coupon_id>",
        type="http",
        auth="public",
        methods=["PUT"],
        csrf=False,
    )
    @permission_required("coupons.manage")
    def update_coupon(self, coupon_id, **kwargs):
        """Update an existing coupon (Admin API)."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            vals = _parse_request_data()
            coupon = CouponService.update_coupon(request.env, coupon_id, vals)

            ctx.set_body(
                ResponseBuilder.success(
                    data=coupon.get_summary_dict(),
                    message=_("Coupon updated successfully"),
                )
            )
        return ctx.response

    @http.route(
        "/api/v1/coupons/<int:coupon_id>",
        type="http",
        auth="public",
        methods=["DELETE"],
        csrf=False,
    )
    @permission_required("coupons.manage")
    def delete_coupon(self, coupon_id, **kwargs):
        """Delete a coupon (Admin API)."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            CouponService.delete_coupon(request.env, coupon_id)

            ctx.set_body(
                ResponseBuilder.success(
                    message=_("Coupon deleted successfully"),
                )
            )
        return ctx.response

    @http.route(
        "/api/v1/coupons/<int:coupon_id>/toggle-active",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    @permission_required("coupons.manage")
    def toggle_coupon_active(self, coupon_id, **kwargs):
        """Activate or deactivate a coupon (Admin API)."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            coupon = CouponService.toggle_coupon_active(request.env, coupon_id)

            ctx.set_body(
                ResponseBuilder.success(
                    data=coupon.get_summary_dict(),
                    message=_("Coupon active status toggled successfully"),
                )
            )
        return ctx.response

    @http.route(
        "/api/v1/coupons",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def list_coupons(self, **kwargs):
        """Get paginated list of coupons."""
        with self.handle() as ctx:
            try:
                limit = int(kwargs.get("limit", 100))
                offset = int(kwargs.get("offset", 0))
            except ValueError:
                raise ValueError("Limit and offset must be valid integers.")

            if limit < 1:
                raise ValueError("Limit must be at least 1.")
            if offset < 0:
                raise ValueError("Offset must be at least 0.")

            domain = []
            active_param = kwargs.get("active")
            if active_param is not None:
                domain.append(("active", "=", active_param.lower() in ("true", "1", "yes")))

            code_param = kwargs.get("code")
            if code_param:
                domain.append(("code", "ilike", code_param.strip()))

            search_param = kwargs.get("search")
            if search_param:
                domain.append("|")
                domain.append(("code", "ilike", search_param.strip()))
                domain.append(("name", "ilike", search_param.strip()))

            lang = request.httprequest.headers.get("Accept-Language", "en_US")
            lang_map = {"ar": "ar_001", "en": "en_US"}
            lang = lang_map.get(lang.split('_')[0], "en_US")

            coupons = CouponService.get_coupons(
                request.env,
                domain=domain,
                limit=limit,
                offset=offset,
                order="id desc",
                lang=lang,
            )
            total_count = CouponService.get_coupons_count(request.env, domain=domain)

            ctx.set_body(
                ResponseBuilder.success(
                    data={
                        "coupons": [c.get_summary_dict() for c in coupons],
                        "total": total_count,
                        "limit": limit,
                        "offset": offset,
                    },
                    message=_("Coupons retrieved successfully"),
                )
            )
        return ctx.response

    @http.route(
        "/api/v1/coupons/<int:coupon_id>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_coupon_details(self, coupon_id, **kwargs):
        """Get coupon details by ID."""
        with self.handle() as ctx:
            lang = request.httprequest.headers.get("Accept-Language", "en_US")
            lang_map = {"ar": "ar_001", "en": "en_US"}
            lang = lang_map.get(lang.split('_')[0], "en_US")

            coupon = CouponService.get_coupon(request.env, coupon_id, lang=lang)

            ctx.set_body(
                ResponseBuilder.success(
                    data=coupon.get_summary_dict(),
                    message=_("Coupon details retrieved successfully"),
                )
            )
        return ctx.response

    @http.route(
        "/api/v1/orders/apply-coupon",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def apply_coupon_to_order(self, **kwargs):
        """Apply a coupon code to an order."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            customer_id = _get_auth_user_id()
            vals = _parse_request_data()
            code = vals.get("code") or kwargs.get("code")
            order_id = vals.get("order_id") or kwargs.get("order_id")

            if order_id:
                try:
                    order_id = int(order_id)
                except ValueError:
                    raise ValueError("order_id must be a valid integer.")

            if not code:
                raise ValidationError(_("Coupon code ('code') is required."))

            result = CouponService.apply_coupon_to_order(
                request.env,
                order_id=order_id,
                code=code,
                customer_id=customer_id
            )

            ctx.set_body(
                ResponseBuilder.success(
                    data=result,
                    message=_("Coupon applied to order successfully"),
                )
            )
        return ctx.response

    @http.route(
        "/api/v1/orders/remove-coupon",
        type="http",
        auth="public",
        methods=["DELETE", "POST"],
        csrf=False,
    )
    def remove_coupon_from_order(self, **kwargs):
        """Remove applied coupon from an order."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            customer_id = _get_auth_user_id()
            vals = _parse_request_data()
            order_id = vals.get("order_id") or kwargs.get("order_id")

            if order_id:
                try:
                    order_id = int(order_id)
                except ValueError:
                    raise ValueError("order_id must be a valid integer.")

            result = CouponService.remove_coupon_from_order(
                request.env,
                order_id=order_id,
                customer_id=customer_id
            )

            ctx.set_body(
                ResponseBuilder.success(
                    data=result,
                    message=_("Coupon removed from order successfully"),
                )
            )
        return ctx.response
