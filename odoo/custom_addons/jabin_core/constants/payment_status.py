from __future__ import annotations
from enum import Enum
from typing import List

class PaymentStatus(str, Enum):
    UNPAID = 'unpaid'
    PENDING = 'pending'
    PAID = 'paid'
    PARTIALLY_PAID = 'partially_paid'
    REFUNDED = 'refunded'
    PARTIALLY_REFUNDED = 'partially_refunded'
    FAILED = 'failed'
    CANCELLED = 'cancelled'

    @property
    def label(self) -> str:
        return _LABELS[self]

    @classmethod
    def all_values(cls) -> List:
        return [member.value for member in cls]

    @classmethod
    def from_value(cls, value: str) -> 'PaymentStatus':
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError(f"Unknown payment status '{value}'. Valid values: {cls.all_values()}") from exc

    @classmethod
    def has_value(cls, value: str) -> bool:
        try:
            cls(value)
            return True
        except ValueError:
            return False
_LABELS: dict = {PaymentStatus.UNPAID: 'Unpaid', PaymentStatus.PENDING: 'Pending', PaymentStatus.PAID: 'Paid', PaymentStatus.PARTIALLY_PAID: 'Partially Paid', PaymentStatus.REFUNDED: 'Refunded', PaymentStatus.PARTIALLY_REFUNDED: 'Partially Refunded', PaymentStatus.FAILED: 'Failed', PaymentStatus.CANCELLED: 'Cancelled'}