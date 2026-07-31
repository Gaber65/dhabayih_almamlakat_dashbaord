# -*- coding: utf-8 -*-
"""Helpers sub-package of ``jabin_core``.

Pure-Python helper classes (no Odoo ORM dependency) used by controllers,
services, and validators. Keeping them ORM-free means they can be unit-tested
in plain Python and reused in non-Odoo contexts (workers, scripts, tests).

Re-exports
----------
* :class:`JsonHelper`         -- safe JSON encode/decode with Decimal/datetime.
* :class:`DatetimeHelper`     -- timezone-aware datetime utilities.
* :class:`PaginationHelper`   -- build the ``meta`` pagination block.
* :class:`StringHelper`       -- slugify / truncate / camelCase helpers.
* :class:`ValidationHelper`   -- generic field-presence / type checks.
"""

from .json_helper import JsonHelper  # noqa: F401
from .datetime_helper import DatetimeHelper  # noqa: F401
from .pagination_helper import PaginationHelper  # noqa: F401
from .string_helper import StringHelper  # noqa: F401
from .validation_helper import ValidationHelper  # noqa: F401
