from odoo import _
from odoo.exceptions import ValidationError
from typing import Dict, List, Any, Optional, Union
import re
from datetime import datetime, date


class ValidationUtils:
    """
    Utility class with common validation functions.
    This is a convenience wrapper around BaseValidator methods.
    """

    @staticmethod
    def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> None:
        """Validate required fields are present"""
        from .base_validator import BaseValidator
        BaseValidator.validate_required_fields(data, required_fields)

    @staticmethod
    def validate_string_length(value: str, field_name: str,
                               min_length: Optional[int] = None,
                               max_length: Optional[int] = None) -> None:
        """Validate string length"""
        from .base_validator import BaseValidator
        BaseValidator.validate_string_length(value, field_name, min_length, max_length)

    @staticmethod
    def validate_positive_number(value: float, field_name: str,
                                 allow_zero: bool = False) -> None:
        """Validate positive number"""
        from .base_validator import BaseValidator
        BaseValidator.validate_positive_number(value, field_name, allow_zero)

    @staticmethod
    def validate_string_format(value: str, field_name: str,
                               pattern: str, message: Optional[str] = None) -> None:
        """Validate string format with regex pattern"""
        from .base_validator import BaseValidator
        BaseValidator.validate_string_format(value, field_name, pattern, message)

    @staticmethod
    def validate_unique_field(env, model_name: str, field_name: str,
                              value: Any, exclude_id: Optional[int] = None) -> None:
        """Validate unique field"""
        from .base_validator import BaseValidator
        BaseValidator.validate_unique_field(env, model_name, field_name, value, exclude_id)

    @staticmethod
    def validate_date_range(start_date, end_date,
                            field_start: str = 'Start Date',
                            field_end: str = 'End Date') -> None:
        """Validate date range"""
        from .base_validator import BaseValidator
        BaseValidator.validate_date_range(start_date, end_date, field_start, field_end)

    @staticmethod
    def validate_in_list(value: Any, allowed_values: List[Any],
                         field_name: str) -> None:
        """Validate value is in allowed list"""
        from .base_validator import BaseValidator
        BaseValidator.validate_in_list(value, allowed_values, field_name)

    @staticmethod
    def validate_email(email: str, field_name: str = 'Email') -> None:
        """Validate email format"""
        from .base_validator import BaseValidator
        BaseValidator.validate_email(email, field_name)

    @staticmethod
    def validate_phone(phone: str, field_name: str = 'Phone') -> None:
        """Validate phone number"""
        from .base_validator import BaseValidator
        BaseValidator.validate_phone(phone, field_name)

    @staticmethod
    def validate_url(url: str, field_name: str = 'URL') -> None:
        """Validate URL format"""
        from .base_validator import BaseValidator
        BaseValidator.validate_url(url, field_name)

    @staticmethod
    def validate_datetime_range(start_datetime, end_datetime,
                                field_start: str = 'Start Date/Time',
                                field_end: str = 'End Date/Time') -> None:
        """Validate datetime range"""
        if start_datetime and end_datetime and start_datetime > end_datetime:
            raise ValidationError(
                _('%(start)s cannot be after %(end)s') % {
                    'start': field_start,
                    'end': field_end
                }
            )

    @staticmethod
    def validate_future_date(date_value: date, field_name: str = 'Date') -> None:
        """Validate that a date is in the future"""
        if date_value and date_value <= date.today():
            raise ValidationError(
                _('%(field)s must be in the future') % {'field': field_name}
            )

    @staticmethod
    def validate_past_date(date_value: date, field_name: str = 'Date') -> None:
        """Validate that a date is in the past"""
        if date_value and date_value >= date.today():
            raise ValidationError(
                _('%(field)s must be in the past') % {'field': field_name}
            )

    @staticmethod
    def validate_not_empty(value: Any, field_name: str) -> None:
        """Validate that a value is not empty"""
        if value in [None, '', [], {}, False]:
            raise ValidationError(
                _('%(field)s cannot be empty') % {'field': field_name}
            )

    @staticmethod
    def validate_no_special_chars(value: str, field_name: str,
                                  allowed_special_chars: str = '-_ ') -> None:
        """Validate that a string contains only alphanumeric and allowed special characters"""
        import re
        if value:
            pattern = r'^[a-zA-Z0-9' + re.escape(allowed_special_chars) + r']+$'
            if not re.match(pattern, value):
                raise ValidationError(
                    _('%(field)s contains invalid characters') % {'field': field_name}
                )

    @staticmethod
    def validate_numeric_range(value: float, field_name: str,
                               min_value: Optional[float] = None,
                               max_value: Optional[float] = None) -> None:
        """Validate numeric range"""
        if value is not None:
            if min_value is not None and value < min_value:
                raise ValidationError(
                    _('%(field)s must be at least %(min)s') % {
                        'field': field_name,
                        'min': min_value
                    }
                )
            if max_value is not None and value > max_value:
                raise ValidationError(
                    _('%(field)s cannot exceed %(max)s') % {
                        'field': field_name,
                        'max': max_value
                    }
                )

    @staticmethod
    def validate_boolean(value: Any, field_name: str) -> None:
        """Validate that a value is a boolean"""
        if not isinstance(value, bool):
            raise ValidationError(
                _('%(field)s must be a boolean value') % {'field': field_name}
            )

    @staticmethod
    def validate_dict_keys(data: Dict[str, Any],
                           required_keys: List[str],
                           optional_keys: List[str] = None) -> None:
        """Validate dictionary keys"""
        if not isinstance(data, dict):
            raise ValidationError(_('Data must be a dictionary'))

        # Check for missing required keys
        missing_keys = [key for key in required_keys if key not in data]
        if missing_keys:
            raise ValidationError(
                _('Missing required keys: %s') % ', '.join(missing_keys)
            )

        # Check for extra keys
        if optional_keys is not None:
            allowed_keys = set(required_keys + optional_keys)
            extra_keys = set(data.keys()) - allowed_keys
            if extra_keys:
                raise ValidationError(
                    _('Unexpected keys: %s') % ', '.join(extra_keys)
                )

    @staticmethod
    def validate_foreign_key(env, model_name: str, field_name: str,
                             value: int, required: bool = True) -> None:
        """Validate that a foreign key exists"""
        if not value:
            if required:
                raise ValidationError(
                    _('%(field)s is required') % {'field': field_name}
                )
            return

        if not env[model_name].browse(value).exists():
            raise ValidationError(
                _('%(field)s with ID %(id)s does not exist') % {
                    'field': field_name,
                    'id': value
                }
            )