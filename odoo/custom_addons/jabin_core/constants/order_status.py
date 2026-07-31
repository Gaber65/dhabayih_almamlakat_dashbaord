from __future__ import annotations
from enum import Enum
from typing import List

class OrderStatus(str, Enum):
    PENDING = 'pending'
    CONFIRMED = 'confirmed'
    PROCESSING = 'processing'
    SHIPPED = 'shipped'
    DELIVERED = 'delivered'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    RETURNED = 'returned'
    FAILED = 'failed'

    @property
    def label(self) -> str:
        return _LABELS[self]

    @classmethod
    def all_values(cls) -> List[str]:
        return [member.value for member in cls]

    @classmethod
    def from_value(cls, value: str) -> 'OrderStatus':
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError(f"Unknown order status '{value}'. Valid values: {cls.all_values()}") from exc

    @classmethod
    def has_value(cls, value: str) -> bool:
        try:
            cls(value)
            return True
        except ValueError:
            return False
_LABELS: dict = {OrderStatus.PENDING: 'Pending', OrderStatus.CONFIRMED: 'Confirmed', OrderStatus.PROCESSING: 'Processing', OrderStatus.SHIPPED: 'Shipped', OrderStatus.DELIVERED: 'Delivered', OrderStatus.COMPLETED: 'Completed', OrderStatus.CANCELLED: 'Cancelled', OrderStatus.RETURNED: 'Returned', OrderStatus.FAILED: 'Failed'}