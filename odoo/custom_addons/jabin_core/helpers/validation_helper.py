from __future__ import annotations
from typing import Any, Iterable, List, Optional
from ..utils.response_builder import ApiError

class ValidationResult:
    __slots__ = ('_errors',)

    def __init__(self) -> None:
        self._errors: List[ApiError] = []

    @property
    def ok(self) -> bool:
        return not self._errors

    @property
    def errors(self) -> List[ApiError]:
        return self._errors

    @property
    def has_errors(self) -> bool:
        return bool(self._errors)

    def add(self, message: str, field: Optional[str]=None) -> None:
        self._errors.append(ApiError(message=message, field=field))

    def add_error(self, error: ApiError) -> None:
        self._errors.append(error)

    def merge(self, other: 'ValidationResult') -> None:
        self._errors.extend(other._errors)

    def require(self, field: str, value: Any, message: Optional[str]=None) -> None:
        if ValidationHelper.is_missing(value):
            self.add(message or f'{field} is required.', field=field)

    def require_type(self, field: str, value: Any, expected_type: type, message: Optional[str]=None) -> None:
        if ValidationHelper.is_missing(value):
            return
        if not isinstance(value, expected_type):
            self.add(message or f'{field} must be a {expected_type.__name__}.', field=field)

    def __repr__(self) -> str:
        return f'ValidationResult(ok={self.ok}, errors={len(self._errors)})'

class ValidationHelper:

    @staticmethod
    def is_missing(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str) and value.strip() == '':
            return True
        if isinstance(value, (list, tuple, dict, set)) and len(value) == 0:
            return True
        return False

    @staticmethod
    def is_present(value: Any) -> bool:
        return not ValidationHelper.is_missing(value)

    @staticmethod
    def is_int(value: Any) -> bool:
        if isinstance(value, bool):
            return False
        if isinstance(value, int):
            return True
        if isinstance(value, str):
            try:
                int(value)
                return True
            except ValueError:
                return False
        return False

    @staticmethod
    def is_float(value: Any) -> bool:
        if isinstance(value, bool):
            return False
        if isinstance(value, (int, float)):
            return True
        if isinstance(value, str):
            try:
                float(value)
                return True
            except ValueError:
                return False
        return False

    @staticmethod
    def is_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return True
        if isinstance(value, str):
            return value.strip().lower() in {'true', 'false', '1', '0', 'yes', 'no'}
        return False

    @staticmethod
    def has_length(value: str, min_length: int=0, max_length: Optional[int]=None) -> bool:
        if not isinstance(value, str):
            return False
        length = len(value)
        if length < min_length:
            return False
        if max_length is not None and length > max_length:
            return False
        return True

    @staticmethod
    def is_in_choices(value: Any, choices: Iterable[Any]) -> bool:
        return value in set(choices)

    @staticmethod
    def to_int(value: Any, default: Optional[int]=None) -> Optional[int]:
        if isinstance(value, bool):
            return int(value)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def to_float(value: Any, default: Optional[float]=None) -> Optional[float]:
        if isinstance(value, bool):
            return float(value)
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def to_bool(value: Any, default: Optional[bool]=None) -> Optional[bool]:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            lower = value.strip().lower()
            if lower in {'true', '1', 'yes'}:
                return True
            if lower in {'false', '0', 'no'}:
                return False
        return default