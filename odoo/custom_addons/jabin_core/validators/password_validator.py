from __future__ import annotations
import re
from typing import Optional
from ..helpers.validation_helper import ValidationResult, ValidationHelper

class PasswordValidator:
    MIN_LENGTH: int = 8
    MAX_LENGTH: int = 128
    SPECIAL_CHARS: str = '!@#$%^&*()_+-=[]{}|;:,.<>?/~`'
    _LOWER = re.compile('[a-z]')
    _UPPER = re.compile('[A-Z]')
    _DIGIT = re.compile('\\d')
    _SPECIAL = re.compile(f'[{re.escape(SPECIAL_CHARS)}]')

    @staticmethod
    def validate(value: Optional[str], field: str='password') -> ValidationResult:
        result = ValidationResult()
        if ValidationHelper.is_missing(value):
            result.add(f'{field} is required.', field=field)
            return result
        password = str(value)
        if len(password) < PasswordValidator.MIN_LENGTH:
            result.add(f'{field} must be at least {PasswordValidator.MIN_LENGTH} characters long.', field=field)
        if len(password) > PasswordValidator.MAX_LENGTH:
            result.add(f'{field} must not exceed {PasswordValidator.MAX_LENGTH} characters.', field=field)
        if not PasswordValidator._LOWER.search(password):
            result.add(f'{field} must contain at least one lowercase letter.', field=field)
        if not PasswordValidator._UPPER.search(password):
            result.add(f'{field} must contain at least one uppercase letter.', field=field)
        if not PasswordValidator._DIGIT.search(password):
            result.add(f'{field} must contain at least one digit.', field=field)
        if not PasswordValidator._SPECIAL.search(password):
            result.add(f'{field} must contain at least one special character ({PasswordValidator.SPECIAL_CHARS}).', field=field)
        return result

    @staticmethod
    def is_valid(value: Optional[str]) -> bool:
        return PasswordValidator.validate(value).ok

    @staticmethod
    def strength_score(value: str) -> int:
        if not value:
            return 0
        score = 0
        if len(value) >= PasswordValidator.MIN_LENGTH:
            score += 1
        if len(value) >= 12:
            score += 1
        if PasswordValidator._LOWER.search(value):
            score += 1
        if PasswordValidator._UPPER.search(value):
            score += 1
        if PasswordValidator._DIGIT.search(value):
            score += 1
        if PasswordValidator._SPECIAL.search(value):
            score += 1
        return min(score, 5)