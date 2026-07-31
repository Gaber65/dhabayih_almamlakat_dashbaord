# device_validator.py
from typing import Dict, Any
from odoo import _
from odoo.exceptions import ValidationError
from odoo.addons.jabin_core import BaseValidator


class DeviceValidator(BaseValidator):
    """Validator for Device registration and token management."""

    VALID_DEVICE_TYPES = ['android', 'ios', 'web']

    @staticmethod
    def validate_register(vals: Dict[str, Any]) -> None:
        """Validate device registration input data."""
        DeviceValidator.validate_required_fields(vals, ['fcm_token', 'device_type'])

        if 'device_type' in vals:
            DeviceValidator.validate_in_list(
                vals['device_type'],
                DeviceValidator.VALID_DEVICE_TYPES,
                'Device Type'
            )

        if not vals.get('fcm_token') or not str(vals['fcm_token']).strip():
            raise ValidationError(_("FCM token cannot be empty."))

    @staticmethod
    def validate_update_token(new_token: str) -> None:
        """Validate FCM token update."""
        if not new_token or not str(new_token).strip():
            raise ValidationError(_("New FCM token is required."))
