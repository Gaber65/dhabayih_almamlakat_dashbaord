from odoo import _
from odoo.exceptions import ValidationError
from typing import Dict, List, Any, Optional
import re


class BaseValidator:
    """
    Base validation class that provides common validation methods.
    All validators should inherit from this class.
    """

    @staticmethod
    def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> None:
        """
        Validate that all required fields are present and not empty

        Args:
            data: Dictionary of data to validate
            required_fields: List of field names that are required

        Raises:
            ValidationError: If any required field is missing or empty
        """
        missing_fields = []
        for field in required_fields:
            value = data.get(field)
            if value in [None, False, '', []]:
                missing_fields.append(field)

        if missing_fields:
            raise ValidationError(
                _('Required fields missing: %s') % ', '.join(missing_fields)
            )

    @staticmethod
    def validate_field_type(value: Any, expected_type: type, field_name: str) -> None:
        """
        Validate that a field has the expected type

        Args:
            value: Value to validate
            expected_type: Expected Python type
            field_name: Name of the field for error messages

        Raises:
            ValidationError: If the value is not of the expected type
        """
        if not isinstance(value, expected_type):
            raise ValidationError(
                _('Field %(field)s must be of type %(type)s') % {
                    'field': field_name,
                    'type': expected_type.__name__
                }
            )

    @staticmethod
    def validate_positive_number(value: float, field_name: str, allow_zero: bool = False) -> None:
        """
        Validate that a number is positive

        Args:
            value: Number to validate
            field_name: Name of the field for error messages
            allow_zero: Whether zero is allowed

        Raises:
            ValidationError: If the number is negative or zero (when not allowed)
        """
        if value is None:
            return

        try:
            num_value = float(value)
        except (TypeError, ValueError):
            raise ValidationError(
                _('%(field)s must be a valid number') % {'field': field_name}
            )

        if allow_zero:
            if num_value < 0:
                raise ValidationError(
                    _('%(field)s cannot be negative!') % {'field': field_name}
                )
        else:
            if num_value <= 0:
                raise ValidationError(
                    _('%(field)s must be greater than zero!') % {'field': field_name}
                )

    @staticmethod
    def validate_string_length(value: str, field_name: str,
                               min_length: Optional[int] = None,
                               max_length: Optional[int] = None) -> None:
        """
        Validate that a string has the correct length

        Args:
            value: String to validate
            field_name: Name of the field for error messages
            min_length: Minimum allowed length
            max_length: Maximum allowed length

        Raises:
            ValidationError: If the string length is outside the allowed range
        """
        if value is None:
            return

        if not isinstance(value, str):
            raise ValidationError(
                _('%(field)s must be a string') % {'field': field_name}
            )

        length = len(value)

        if min_length is not None and length < min_length:
            raise ValidationError(
                _('%(field)s must be at least %(min)d characters long') % {
                    'field': field_name,
                    'min': min_length
                }
            )

        if max_length is not None and length > max_length:
            raise ValidationError(
                _('%(field)s cannot exceed %(max)d characters') % {
                    'field': field_name,
                    'max': max_length
                }
            )

    @staticmethod
    def validate_string_format(value: str, field_name: str,
                               pattern: str, message: Optional[str] = None) -> None:
        """
        Validate that a string matches a regex pattern

        Args:
            value: String to validate
            field_name: Name of the field for error messages
            pattern: Regex pattern to match
            message: Custom error message (optional)

        Raises:
            ValidationError: If the string doesn't match the pattern
        """
        if value is None or value == '':
            return

        if not isinstance(value, str):
            raise ValidationError(
                _('%(field)s must be a string') % {'field': field_name}
            )

        if not re.match(pattern, value):
            if message:
                raise ValidationError(_(message))
            else:
                raise ValidationError(
                    _('%(field)s has an invalid format') % {'field': field_name}
                )

    @staticmethod
    def validate_unique_field(env, model_name: str, field_name: str,
                              value: Any, exclude_id: Optional[int] = None) -> None:
        """
        Validate that a field value is unique in the database

        Args:
            env: Odoo environment
            model_name: Name of the model to check
            field_name: Name of the field to validate
            value: Value to check for uniqueness
            exclude_id: ID to exclude from the check (for updates)

        Raises:
            ValidationError: If the value already exists
        """
        if value is None or value == '':
            return

        domain = [(field_name, '=', value)]
        if exclude_id:
            domain.append(('id', '!=', exclude_id))

        if env[model_name].search_count(domain) > 0:
            raise ValidationError(
                _('%(field)s must be unique!') % {
                    'field': field_name.replace('_', ' ').title()
                }
            )

    @staticmethod
    def validate_date_range(start_date, end_date,
                            field_start: str = 'Start Date',
                            field_end: str = 'End Date') -> None:
        """
        Validate that start date is before end date

        Args:
            start_date: Start date
            end_date: End date
            field_start: Name of start field for error messages
            field_end: Name of end field for error messages

        Raises:
            ValidationError: If start date is after end date
        """
        if start_date and end_date and start_date > end_date:
            raise ValidationError(
                _('%(start)s cannot be after %(end)s') % {
                    'start': field_start,
                    'end': field_end
                }
            )

    @staticmethod
    def validate_in_list(value: Any, allowed_values: List[Any],
                         field_name: str) -> None:
        """
        Validate that a value is in a list of allowed values

        Args:
            value: Value to validate
            allowed_values: List of allowed values
            field_name: Name of the field for error messages

        Raises:
            ValidationError: If the value is not in the allowed list
        """
        if value is None:
            return

        if value not in allowed_values:
            raise ValidationError(
                _('%(field)s must be one of: %(values)s') % {
                    'field': field_name,
                    'values': ', '.join(str(v) for v in allowed_values)
                }
            )

    @staticmethod
    def validate_email(email: str, field_name: str = 'Email') -> None:
        """
        Validate email format

        Args:
            email: Email address to validate
            field_name: Name of the field for error messages

        Raises:
            ValidationError: If the email format is invalid
        """
        if not email:
            return

        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        BaseValidator.validate_string_format(
            email,
            field_name,
            email_pattern,
            f'{field_name} format is invalid'
        )

    @staticmethod
    def validate_phone(phone: str, field_name: str = 'Phone') -> None:
        """
        Validate phone number format (basic validation)

        Args:
            phone: Phone number to validate
            field_name: Name of the field for error messages

        Raises:
            ValidationError: If the phone format is invalid
        """
        if not phone:
            return

        # Basic international phone number validation
        phone_pattern = r'^\+?[0-9\s\-()]{8,20}$'
        BaseValidator.validate_string_format(
            phone,
            field_name,
            phone_pattern,
            f'{field_name} format is invalid'
        )

    @staticmethod
    def validate_url(url: str, field_name: str = 'URL') -> None:
        """
        Validate URL format

        Args:
            url: URL to validate
            field_name: Name of the field for error messages

        Raises:
            ValidationError: If the URL format is invalid
        """
        if not url:
            return

        url_pattern = r'^https?://[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}(/[a-zA-Z0-9\-\._~:/?#\[\]@!$&\'()*+,;=]*)?$'
        BaseValidator.validate_string_format(
            url,
            field_name,
            url_pattern,
            f'{field_name} format is invalid'
        )