# -*- coding: utf-8 -*-
"""Centralised constants package for the JABIN ERP platform.

Every enum lives in its own module so that downstream modules can import only
the constants they need (``from odoo.addons.jabin_core.constants.user_types import UserType``)
instead of pulling the whole package. All enums use Python's ``enum`` module so
that values are stable, documented, and impossible to typo.

Design rules applied across the whole package
---------------------------------------------
* **Stable values** -- enum *values* are never changed once shipped; new states
  are only ever *appended*. This keeps serialized data (DB rows, API payloads,
  logs) forward/backward compatible.
* **Self-documenting** -- every member carries a human-readable label via the
  ``label`` property, so controllers/UIs can render them without extra maps.
* **String-based enums** -- values are short UPPER_SNAKE strings, not integers,
  so they remain meaningful in JSON payloads and database columns.
* **Lookup helpers** -- each enum exposes ``has_value()`` and ``from_value()``
  for safe parsing of incoming API data.
"""

from .user_types import UserType  # noqa: F401
from .order_status import OrderStatus  # noqa: F401
from .payment_status import PaymentStatus  # noqa: F401
from .delivery_status import DeliveryStatus  # noqa: F401
from .stock_status import StockStatus  # noqa: F401
from .notification_types import NotificationType  # noqa: F401
