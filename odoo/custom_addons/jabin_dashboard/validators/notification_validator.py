# notification_validator.py
from typing import Dict, Any
from odoo import _
from odoo.exceptions import ValidationError
from odoo.addons.jabin_core import BaseValidator


class NotificationValidator(BaseValidator):
    """Validator for Push Notification requests."""

    VALID_PRIORITIES = ['low', 'normal', 'high', 'urgent']
    VALID_TYPES = ['order', 'offer', 'banner', 'product', 'coupon', 'loyalty', 'payment', 'system', 'admin']

    @staticmethod
    def validate_send(vals: Dict[str, Any]) -> None:
        """Validate notification sending payload."""
        NotificationValidator.validate_required_fields(vals, ['title', 'body'])

        if 'priority' in vals and vals['priority']:
            NotificationValidator.validate_in_list(
                vals['priority'],
                NotificationValidator.VALID_PRIORITIES,
                'Priority'
            )

        if 'notification_type' in vals and vals['notification_type']:
            NotificationValidator.validate_in_list(
                vals['notification_type'],
                NotificationValidator.VALID_TYPES,
                'Notification Type'
            )
