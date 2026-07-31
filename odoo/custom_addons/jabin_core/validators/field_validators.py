from odoo import _
from odoo.exceptions import ValidationError
from typing import Dict, List, Any, Optional, Callable
import re
from datetime import datetime, date


class FieldValidators:
    """
    Specialized validators for specific field types.
    Inherits from BaseValidator for common validation methods.
    """

    @staticmethod
    def validate_email(email: str, field_name: str = 'Email') -> None:
        """Validate email format"""
        if not email:
            return

        # RFC 5322 compliant email regex (simplified)
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            raise ValidationError(
                _('%(field)s must be a valid email address') % {'field': field_name}
            )

    @staticmethod
    def validate_phone(phone: str, field_name: str = 'Phone',
                       country_code: Optional[str] = None) -> None:
        """Validate phone number"""
        if not phone:
            return

        # Remove spaces, dashes, parentheses
        clean_phone = re.sub(r'[\s\-\(\)]', '', phone)

        # Basic validation
        if not clean_phone.isdigit():
            raise ValidationError(
                _('%(field)s must contain only digits, spaces, dashes, and parentheses') % {
                    'field': field_name
                }
            )

        # Check length
        if len(clean_phone) < 7 or len(clean_phone) > 15:
            raise ValidationError(
                _('%(field)s must be between 7 and 15 digits') % {'field': field_name}
            )

    @staticmethod
    def validate_url(url: str, field_name: str = 'URL') -> None:
        """Validate URL"""
        if not url:
            return

        # URL regex
        pattern = r'^https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?::\d+)?(?:/[-\w%!$&\'()*+,;=:@/~]*)*$'
        if not re.match(pattern, url):
            raise ValidationError(
                _('%(field)s must be a valid URL') % {'field': field_name}
            )

    @staticmethod
    def validate_sku(sku: str, field_name: str = 'SKU') -> None:
        """Validate SKU format (alphanumeric, dashes, underscores)"""
        if not sku:
            return

        pattern = r'^[A-Z0-9\-_]+$'
        if not re.match(pattern, sku):
            raise ValidationError(
                _('%(field)s must contain only letters, numbers, dashes, and underscores') % {
                    'field': field_name
                }
            )

        if len(sku) < 3 or len(sku) > 50:
            raise ValidationError(
                _('%(field)s must be between 3 and 50 characters') % {'field': field_name}
            )

    @staticmethod
    def validate_barcode(barcode: str, field_name: str = 'Barcode') -> None:
        """Validate barcode (EAN-13, UPC-A, etc.)"""
        if not barcode:
            return

        # Basic validation - only numbers
        if not barcode.isdigit():
            raise ValidationError(
                _('%(field)s must contain only numbers') % {'field': field_name}
            )

        # Check length (EAN-13 is 13 digits, UPC-A is 12)
        if len(barcode) not in [8, 12, 13, 14]:
            raise ValidationError(
                _('%(field)s must be 8, 12, 13, or 14 digits') % {'field': field_name}
            )

    @staticmethod
    def validate_date_format(date_str: str, field_name: str = 'Date',
                             format_str: str = '%Y-%m-%d') -> None:
        """Validate date format"""
        if not date_str:
            return

        try:
            datetime.strptime(date_str, format_str)
        except ValueError:
            raise ValidationError(
                _('%(field)s must be in format %(format)s') % {
                    'field': field_name,
                    'format': format_str
                }
            )

    @staticmethod
    def validate_datetime_format(datetime_str: str, field_name: str = 'DateTime',
                                 format_str: str = '%Y-%m-%d %H:%M:%S') -> None:
        """Validate datetime format"""
        if not datetime_str:
            return

        try:
            datetime.strptime(datetime_str, format_str)
        except ValueError:
            raise ValidationError(
                _('%(field)s must be in format %(format)s') % {
                    'field': field_name,
                    'format': format_str
                }
            )

    @staticmethod
    def validate_currency(amount: float, field_name: str = 'Amount',
                          min_amount: float = 0.0, max_amount: float = 999999999.99) -> None:
        """Validate currency amount"""
        if amount is None:
            return

        try:
            amount = float(amount)
        except (TypeError, ValueError):
            raise ValidationError(
                _('%(field)s must be a valid number') % {'field': field_name}
            )

        if amount < min_amount or amount > max_amount:
            raise ValidationError(
                _('%(field)s must be between %(min)s and %(max)s') % {
                    'field': field_name,
                    'min': min_amount,
                    'max': max_amount
                }
            )

    @staticmethod
    def validate_percentage(value: float, field_name: str = 'Percentage',
                            allow_zero: bool = True) -> None:
        """Validate percentage (0-100)"""
        if value is None:
            return

        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ValidationError(
                _('%(field)s must be a valid number') % {'field': field_name}
            )

        if allow_zero:
            if value < 0 or value > 100:
                raise ValidationError(
                    _('%(field)s must be between 0 and 100') % {'field': field_name}
                )
        else:
            if value <= 0 or value > 100:
                raise ValidationError(
                    _('%(field)s must be between 0 and 100 (exclusive of 0)') % {
                        'field': field_name
                    }
                )

    @staticmethod
    def validate_iban(iban: str, field_name: str = 'IBAN') -> None:
        """Validate IBAN format"""
        if not iban:
            return

        # Basic IBAN validation
        iban = iban.replace(' ', '').upper()

        # Check length (varies by country, typically 15-34)
        if len(iban) < 15 or len(iban) > 34:
            raise ValidationError(
                _('%(field)s must be between 15 and 34 characters') % {'field': field_name}
            )

        # Check alphanumeric
        if not iban.isalnum():
            raise ValidationError(
                _('%(field)s must contain only alphanumeric characters') % {
                    'field': field_name
                }
            )

    @staticmethod
    def validate_vat(vat: str, field_name: str = 'VAT',
                     country_code: Optional[str] = None) -> None:
        """Validate VAT number format"""
        if not vat:
            return

        vat = vat.replace(' ', '').upper()

        # Basic VAT validation (varies by country)
        # This is a simplified version
        if len(vat) < 4 or len(vat) > 20:
            raise ValidationError(
                _('%(field)s must be between 4 and 20 characters') % {'field': field_name}
            )

        # Check alphanumeric
        if not vat.isalnum():
            raise ValidationError(
                _('%(field)s must contain only alphanumeric characters') % {
                    'field': field_name
                }
            )

    @staticmethod
    def validate_postal_code(postal_code: str, field_name: str = 'Postal Code',
                             country_code: Optional[str] = None) -> None:
        """Validate postal code format"""
        if not postal_code:
            return

        # Basic postal code validation
        postal_code = postal_code.strip()

        # Remove spaces for validation
        clean_code = postal_code.replace(' ', '')

        # Most postal codes are alphanumeric
        if not clean_code.isalnum():
            raise ValidationError(
                _('%(field)s must contain only alphanumeric characters') % {
                    'field': field_name
                }
            )

        # Check length
        if len(clean_code) < 3 or len(clean_code) > 10:
            raise ValidationError(
                _('%(field)s must be between 3 and 10 characters') % {'field': field_name}
            )

    @staticmethod
    def validate_password(password: str, field_name: str = 'Password',
                          min_length: int = 8, require_uppercase: bool = True,
                          require_lowercase: bool = True, require_numbers: bool = True,
                          require_special: bool = True) -> None:
        """Validate password strength"""
        if not password:
            return

        if len(password) < min_length:
            raise ValidationError(
                _('%(field)s must be at least %(min)d characters long') % {
                    'field': field_name,
                    'min': min_length
                }
            )

        if require_uppercase and not re.search(r'[A-Z]', password):
            raise ValidationError(
                _('%(field)s must contain at least one uppercase letter') % {
                    'field': field_name
                }
            )

        if require_lowercase and not re.search(r'[a-z]', password):
            raise ValidationError(
                _('%(field)s must contain at least one lowercase letter') % {
                    'field': field_name
                }
            )

        if require_numbers and not re.search(r'\d', password):
            raise ValidationError(
                _('%(field)s must contain at least one number') % {'field': field_name}
            )

        if require_special and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError(
                _('%(field)s must contain at least one special character') % {
                    'field': field_name
                }
            )