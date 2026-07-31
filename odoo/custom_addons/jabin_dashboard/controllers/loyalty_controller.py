# loyalty_controller.py
import json
from typing import Dict, Any, Optional

from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError

from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder, JabinLogger
from odoo.addons.jabin_security.utils.token_auth import require_token
from odoo.addons.jabin_security.decorators.permission_required import permission_required

from ..services.loyalty_service import LoyaltyService

_logger = JabinLogger.get("loyalty.controller")


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
    """Parse request JSON data."""
    raw = request.httprequest.data
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON payload.")
    return {}


class LoyaltyController(BaseApiController):
    """REST API Controller for JABIN Loyalty Points System."""

    @http.route(
        "/api/v1/loyalty/summary",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_loyalty_summary(self, **kwargs):
        """Get customer loyalty wallet summary and rules."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id() or request.env.user.id
        with self.handle() as ctx:
            customer_id = kwargs.get("customer_id")
            target_id = int(customer_id) if customer_id else user_id
            summary = LoyaltyService.get_customer_loyalty_summary(request.env, target_id)
            return ResponseBuilder.success(data=summary, message="Loyalty summary retrieved.")

    @http.route(
        "/api/v1/loyalty/transactions",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_transaction_history(self, **kwargs):
        """Get customer loyalty transaction history."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id() or request.env.user.id
        with self.handle() as ctx:
            customer_id = kwargs.get("customer_id")
            target_id = int(customer_id) if customer_id else user_id
            limit = int(kwargs.get("limit", 20))
            offset = int(kwargs.get("offset", 0))

            history = LoyaltyService.get_customer_transaction_history(
                request.env, target_id, limit=limit, offset=offset
            )
            return ResponseBuilder.success(data=history, message="Transaction history retrieved.")

    @http.route(
        "/api/v1/loyalty/calculate-earn",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def calculate_earn(self, **kwargs):
        """Calculate earned points for a given order total."""
        with self.handle() as ctx:
            data = _parse_request_data()
            order_total = float(data.get("order_total", kwargs.get("order_total", 0.0)))
            earned = LoyaltyService.calculate_earned_points(request.env, order_total)
            settings = LoyaltyService.get_settings(request.env)

            return ResponseBuilder.success(data={
                "order_total": order_total,
                "earned_points": earned,
                "earning_rate": settings["earning_rate"]
            }, message="Earned points calculated successfully.")

    @http.route(
        "/api/v1/loyalty/calculate-redemption",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def calculate_redemption(self, **kwargs):
        """Calculate SAR discount value for given loyalty points."""
        with self.handle() as ctx:
            data = _parse_request_data()
            points = int(data.get("points", kwargs.get("points", 0)))
            discount_sar = LoyaltyService.calculate_redemption_value(request.env, points)
            settings = LoyaltyService.get_settings(request.env)

            return ResponseBuilder.success(data={
                "points": points,
                "discount_sar": discount_sar,
                "redemption_rate": settings["redemption_rate"]
            }, message="Redemption value calculated successfully.")

    @http.route(
        "/api/v1/loyalty/validate-redemption",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def validate_redemption(self, **kwargs):
        """Validate whether a customer can redeem given points on an order total."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id() or request.env.user.id
        with self.handle() as ctx:
            data = _parse_request_data()
            points = int(data.get("points", 0))
            order_total = float(data.get("order_total", 0.0))
            customer_id = int(data.get("customer_id", user_id))

            LoyaltyService.validate_redemption(request.env, customer_id, points, order_total)
            discount_sar = LoyaltyService.calculate_redemption_value(request.env, points)

            return ResponseBuilder.success(data={
                "valid": True,
                "customer_id": customer_id,
                "points": points,
                "discount_sar": discount_sar
            }, message="Redemption validation successful.")

    @http.route(
        "/api/v1/loyalty/redeem",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def redeem_points(self, **kwargs):
        """Redeem points on an order and deduct from customer wallet."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id() or request.env.user.id
        with self.handle() as ctx:
            data = _parse_request_data()
            order_id = int(data.get("order_id"))
            points = int(data.get("points"))

            order = request.env["jabin.order"].sudo().browse(order_id)
            if not order.exists():
                raise ValidationError(_("Order %s not found.") % order_id)

            if order.customer_id.id != user_id and not request.env.user.has_group('base.group_user'):
                raise ValidationError(_("Unauthorized to redeem points for this order."))

            order.apply_loyalty_points(points)
            LoyaltyService.deduct_redeemed_points(request.env, order.customer_id.id, points, order.id)

            return ResponseBuilder.success(data={
                "order_id": order.id,
                "points_redeemed": order.points_redeemed,
                "loyalty_discount_amount": order.loyalty_discount_amount,
                "new_order_total": order.total,
                "remaining_points_balance": order.customer_id.loyalty_points
            }, message="Loyalty points redeemed successfully.")

    @http.route(
        "/api/v1/loyalty/adjust",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    @permission_required("loyalty.adjust")
    def adjust_points(self, **kwargs):
        """Admin API: Manually adjust customer points (+/-)."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            data = _parse_request_data()
            customer_id = int(data.get("customer_id"))
            points_change = int(data.get("points_change"))
            reason = str(data.get("reason", "")).strip()

            tx = LoyaltyService.manual_adjust_points(
                request.env,
                customer_id=customer_id,
                points_change=points_change,
                reason=reason,
                admin_user_id=request.env.user.id
            )

            return ResponseBuilder.success(data={
                "transaction_id": tx.id,
                "customer_id": customer_id,
                "points_change": points_change,
                "new_balance": tx.balance_after,
                "reason": reason
            }, message="Customer points adjusted successfully.")

    @http.route(
        "/api/v1/loyalty/settings",
        type="http",
        auth="public",
        methods=["GET", "PUT"],
        csrf=False,
    )
    @permission_required("loyalty.manage_settings")
    def handle_settings(self, **kwargs):
        """Admin API: View or update loyalty configuration settings."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            if request.httprequest.method == "GET":
                settings = LoyaltyService.get_settings(request.env)
                return ResponseBuilder.success(data=settings, message="Loyalty settings retrieved.")
            else:
                data = _parse_request_data()
                earning_rate = float(data.get("earning_rate"))
                redemption_rate = float(data.get("redemption_rate"))
                min_redemption = int(data.get("min_redemption"))

                LoyaltyService.update_settings(request.env, earning_rate, redemption_rate, min_redemption)
                updated = LoyaltyService.get_settings(request.env)
                return ResponseBuilder.success(data=updated, message="Loyalty settings updated successfully.")
