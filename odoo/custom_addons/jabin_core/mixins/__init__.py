# -*- coding: utf-8 -*-
"""Mixins sub-package of ``jabin_core``.

Odoo ``AbstractModel`` mixins that future business models inherit to avoid
re-declaring the same fields and override logic over and over. Because they are
``AbstractModel`` classes they do **not** create their own database tables; they
only contribute their fields and methods to the concrete model that inherits
them.

Mixins provided
---------------
* :class:`TimestampMixin`    -- ``create_date`` / ``write_date`` tracking.
* :class:`AuditMixin`        -- ``created_by`` / ``updated_by`` tracking.
* :class:`ActiveMixin`       -- ``active`` flag + archive/unarchive.
* :class:`SoftDeleteMixin`   -- ``is_deleted`` / ``deleted_at`` (prepared only).

Design rules
------------
* Each mixin has a single responsibility (SOLID-S).
* Mixins never implement business logic; they provide only generic behaviour
  that is meaningful for *any* model.
* Mixins import Odoo lazily so the rest of ``jabin_core`` remains importable in
  plain-Python test contexts.
"""

from .timestamp_mixin import TimestampMixin  # noqa: F401
from .audit_mixin import AuditMixin  # noqa: F401
from .active_mixin import ActiveMixin  # noqa: F401
from .soft_delete_mixin import SoftDeleteMixin  # noqa: F401
from .core_mixin import JabinCoreMixin
