from __future__ import annotations
from enum import Enum
from typing import List

class UserType(str, Enum):
    ADMIN = 'admin'
    CUSTOMER = 'customer'
    MANAGER = 'manager'
    EMPLOYEE = 'employee'
    DRIVER = 'driver'

    @property
    def label(self) -> str:
        return _LABELS[self]

    @classmethod
    def all_values(cls) -> List[str]:
        return [member.value for member in cls]

    @classmethod
    def from_value(cls, value: str) -> 'UserType':
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError(f"Unknown user type '{value}'. Valid values: {cls.all_values()}") from exc

    @classmethod
    def has_value(cls, value: str) -> bool:
        try:
            cls(value)
            return True
        except ValueError:
            return False
_LABELS: dict = {UserType.ADMIN: 'Administrator', UserType.CUSTOMER: 'Customer', UserType.MANAGER: 'Manager', UserType.EMPLOYEE: 'Employee', UserType.DRIVER: 'Driver'}