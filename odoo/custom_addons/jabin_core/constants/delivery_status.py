from __future__ import annotations
from enum import Enum
from typing import List

class DeliveryStatus(str, Enum):
    PENDING = 'pending'
    ASSIGNED = 'assigned'
    PICKED_UP = 'picked_up'
    IN_TRANSIT = 'in_transit'
    OUT_FOR_DELIVERY = 'out_for_delivery'
    DELIVERED = 'delivered'
    FAILED = 'failed'
    RETURNED = 'returned'
    CANCELLED = 'cancelled'

    @property
    def label(self) -> str:
        return _LABELS[self]

    @classmethod
    def all_values(cls) -> List[str]:
        return [member.value for member in cls]

    @classmethod
    def from_value(cls, value: str) -> 'DeliveryStatus':
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError(f"Unknown delivery status '{value}'. Valid values: {cls.all_values()}") from exc

    @classmethod
    def has_value(cls, value: str) -> bool:
        try:
            cls(value)
            return True
        except ValueError:
            return False
_LABELS: dict = {DeliveryStatus.PENDING: 'Pending', DeliveryStatus.ASSIGNED: 'Assigned', DeliveryStatus.PICKED_UP: 'Picked Up', DeliveryStatus.IN_TRANSIT: 'In Transit', DeliveryStatus.OUT_FOR_DELIVERY: 'Out for Delivery', DeliveryStatus.DELIVERED: 'Delivered', DeliveryStatus.FAILED: 'Failed', DeliveryStatus.RETURNED: 'Returned', DeliveryStatus.CANCELLED: 'Cancelled'}