from __future__ import annotations
import uuid
from typing import Optional
from ..helpers.validation_helper import ValidationResult, ValidationHelper

class UUIDValidator:

    @staticmethod
    def validate(value: Optional[str], field: str='uuid') -> ValidationResult:
        result = ValidationResult()
        if ValidationHelper.is_missing(value):
            result.add(f'{field} is required.', field=field)
            return result
        raw = str(value).strip()
        try:
            uuid.UUID(raw)
        except (ValueError, AttributeError, TypeError):
            result.add(f'{field} is not a valid UUID.', field=field)
        return result

    @staticmethod
    def is_valid(value: Optional[str]) -> bool:
        return UUIDValidator.validate(value).ok

    @staticmethod
    def normalise(value: str) -> str:
        return str(uuid.UUID(str(value).strip()))

    @staticmethod
    def generate() -> str:
        return str(uuid.uuid4())