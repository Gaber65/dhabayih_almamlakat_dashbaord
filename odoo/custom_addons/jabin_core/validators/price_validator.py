from __future__ import annotations
import decimal
import re
from typing import Optional, Union
from ..helpers.validation_helper import ValidationResult, ValidationHelper
_NUMERIC_STR = re.compile('^-?\\d+(\\.\\d+)?$')

class PriceValidator:
    MAX_VALUE: decimal.Decimal = decimal.Decimal('1000000000')
    MAX_DECIMAL_PLACES: int = 2

    @staticmethod
    def validate(value: Optional[Union[int, float, str, decimal.Decimal]], field: str='price') -> ValidationResult:
        result = ValidationResult()
        if ValidationHelper.is_missing(value):
            result.add(f'{field} is required.', field=field)
            return result
        decimal_value = PriceValidator._to_decimal(value, field, result)
        if decimal_value is None:
            return result
        if decimal_value < 0:
            result.add(f'{field} must not be negative.', field=field)
        if decimal_value > PriceValidator.MAX_VALUE:
            result.add(f'{field} must not exceed {PriceValidator.MAX_VALUE}.', field=field)
        if isinstance(value, str) and '.' in value:
            places = len(value.split('.', 1)[1])
            if places > PriceValidator.MAX_DECIMAL_PLACES:
                result.add(f'{field} must not have more than {PriceValidator.MAX_DECIMAL_PLACES} decimal places.', field=field)
        return result

    @staticmethod
    def is_valid(value: Optional[Union[int, float, str, decimal.Decimal]]) -> bool:
        return PriceValidator.validate(value).ok

    @staticmethod
    def _to_decimal(value: Union[int, float, str, decimal.Decimal], field: str, result: ValidationResult) -> Optional[decimal.Decimal]:
        try:
            if isinstance(value, bool):
                raise TypeError('boolean is not a valid price')
            if isinstance(value, decimal.Decimal):
                return value
            if isinstance(value, int):
                return decimal.Decimal(value)
            if isinstance(value, float):
                return decimal.Decimal(str(value))
            if isinstance(value, str):
                stripped = value.strip()
                if not _NUMERIC_STR.match(stripped):
                    raise ValueError('not a numeric string')
                return decimal.Decimal(stripped)
            raise TypeError(f'unsupported type {type(value).__name__}')
        except (ValueError, TypeError, decimal.InvalidOperation):
            result.add(f'{field} must be a valid numeric value.', field=field)
            return None

    @staticmethod
    def to_decimal(value: Union[int, float, str, decimal.Decimal]) -> decimal.Decimal:
        if isinstance(value, decimal.Decimal):
            return value
        if isinstance(value, int):
            return decimal.Decimal(value)
        if isinstance(value, float):
            return decimal.Decimal(str(value))
        return decimal.Decimal(str(value).strip())