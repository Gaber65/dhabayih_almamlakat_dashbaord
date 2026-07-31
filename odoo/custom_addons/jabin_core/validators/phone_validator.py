from __future__ import annotations
import re
from typing import Optional
from ..helpers.validation_helper import ValidationResult, ValidationHelper
_PHONE_REGEX = re.compile('^\\+?[\\d\\s\\-\\(\\)]+$')

class PhoneValidator:
    MIN_DIGITS: int = 7
    MAX_DIGITS: int = 15

    @staticmethod
    def validate(value: Optional[str], field: str='phone') -> ValidationResult:
        result = ValidationResult()
        if ValidationHelper.is_missing(value):
            result.add(f'{field} is required.', field=field)
            return result
        raw = str(value).strip()
        if not _PHONE_REGEX.match(raw):
            result.add(f"{field} may only contain digits, spaces, hyphens, parentheses and an optional leading '+'.", field=field)
            return result
        digits = PhoneValidator.normalise(raw)
        digit_count = len(digits.lstrip('+'))
        if digit_count < PhoneValidator.MIN_DIGITS:
            result.add(f'{field} must contain at least {PhoneValidator.MIN_DIGITS} digits.', field=field)
        elif digit_count > PhoneValidator.MAX_DIGITS:
            result.add(f'{field} must contain at most {PhoneValidator.MAX_DIGITS} digits.', field=field)
        return result

    @staticmethod
    def is_valid(value: Optional[str]) -> bool:
        return PhoneValidator.validate(value).ok

    @staticmethod
    def normalise(value: str) -> str:
        raw = value.strip()
        leading_plus = '+' if raw.startswith('+') else ''
        digits = re.sub('\\D', '', raw)
        return f'{leading_plus}{digits}'