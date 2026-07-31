from __future__ import annotations
from enum import Enum
from typing import List

class NotificationType(str, Enum):
    ORDER = 'order'
    PAYMENT = 'payment'
    DELIVERY = 'delivery'
    PROMOTION = 'promotion'
    SYSTEM = 'system'
    ACCOUNT = 'account'
    STOCK = 'stock'

    @property
    def label(self) -> str:
        return _LABELS[self]

    @classmethod
    def all_values(cls) -> List[str]:
        return [member.value for member in cls]

    @classmethod
    def from_value(cls, value: str) -> 'NotificationType':
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError(f"Unknown notification type '{value}'. Valid values: {cls.all_values()}") from exc

    @classmethod
    def has_value(cls, value: str) -> bool:
        try:
            cls(value)
            return True
        except ValueError:
            return False
_LABELS: dict = {NotificationType.ORDER: 'Order', NotificationType.PAYMENT: 'Payment', NotificationType.DELIVERY: 'Delivery', NotificationType.PROMOTION: 'Promotion', NotificationType.SYSTEM: 'System', NotificationType.ACCOUNT: 'Account', NotificationType.STOCK: 'Stock'}