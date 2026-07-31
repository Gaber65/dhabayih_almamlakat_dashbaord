# loyalty_validator.py
from typing import Dict, Any, Optional
from odoo import _
from odoo.exceptions import ValidationError
from odoo.addons.jabin_core import BaseValidator


class LoyaltyValidator(BaseValidator):
    """Validator for JABIN Loyalty Points operations."""

    @staticmethod
    def validate_redemption(customer, points: int, order_total: float, min_redemption: int, redemption_rate: float) -> None:
        """
        Validate points redemption request against business rules:
        1. Must be positive integer points.
        2. Must meet minimum redemption threshold (default 500).
        3. Cannot exceed current customer points balance.
        4. Discount (SAR) cannot exceed order total.
        """
        if not isinstance(points, int) or points <= 0:
            raise ValidationError(_("Redemption points must be a positive integer."))

        if points < min_redemption:
            raise ValidationError(
                _("Minimum redemption requirement is %s points (value: %s SAR). You entered %s points.") %
                (min_redemption, round(min_redemption / redemption_rate, 2), points)
            )

        if not customer:
            raise ValidationError(_("Customer record is required for point redemption."))

        if points > customer.loyalty_points:
            raise ValidationError(
                _("Cannot redeem %s points. Customer currently has %s points available.") %
                (points, customer.loyalty_points)
            )

        if redemption_rate <= 0:
            raise ValidationError(_("Invalid system redemption rate."))

        discount_val = round(points / redemption_rate, 2)
        if discount_val > order_total:
            max_points = int(order_total * redemption_rate)
            raise ValidationError(
                _("Redemption discount (%s SAR) exceeds the order total (%s SAR). Maximum redeemable points for this order is %s points.") %
                (discount_val, order_total, max_points)
            )

    @staticmethod
    def validate_manual_adjustment(customer, points_change: int, reason: str) -> None:
        """Validate admin manual points adjustment."""
        if not customer:
            raise ValidationError(_("Customer is required for points adjustment."))

        if not isinstance(points_change, int) or points_change == 0:
            raise ValidationError(_("Adjustment points must be a non-zero integer."))

        if not reason or not reason.strip():
            raise ValidationError(_("Reason/justification is required for manual points adjustment."))

        new_balance = customer.loyalty_points + points_change
        if new_balance < 0:
            raise ValidationError(
                _("Cannot deduct %s points. Customer balance (%s points) cannot go below zero.") %
                (abs(points_change), customer.loyalty_points)
            )

    @staticmethod
    def validate_settings(earning_rate: float, redemption_rate: float, min_redemption: int) -> None:
        """Validate loyalty system configuration settings."""
        if earning_rate <= 0:
            raise ValidationError(_("Earning rate must be greater than zero."))
        if redemption_rate <= 0:
            raise ValidationError(_("Redemption rate must be greater than zero."))
        if min_redemption < 0:
            raise ValidationError(_("Minimum redemption threshold cannot be negative."))
