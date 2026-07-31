from __future__ import annotations
import re
from typing import Optional
from ..helpers.validation_helper import ValidationResult, ValidationHelper
_EMAIL_REGEX = re.compile('^(?=.{1,254}$)(?P<local>[A-Za-z0-9._%+\\-]{1,64})@(?P<domain>([A-Za-z0-9\\-]+\\.)+[A-Za-z]{2,})$')

class EmailValidator:
    EMAIL_PATTERN: str = _EMAIL_REGEX.pattern
    MAX_LENGTH: int = 254

    @staticmethod
    def validate(value: Optional[str], field: str='email') -> ValidationResult:
        result = ValidationResult()
        if ValidationHelper.is_missing(value):
            result.add(f'{field} is required.', field=field)
            return result
        email = str(value).strip().lower()
        if len(email) > EmailValidator.MAX_LENGTH:
            result.add(f'{field} must not exceed {EmailValidator.MAX_LENGTH} characters.', field=field)
            return result
        if not _EMAIL_REGEX.match(email):
            result.add(f'{field} is not a valid email address.', field=field)
        return result

    @staticmethod
    def is_valid(value: Optional[str]) -> bool:
        return EmailValidator.validate(value).ok

    @staticmethod
    def normalise(value: str) -> str:
        return value.strip().lower()