# -*- coding: utf-8 -*-
"""Utility sub-package of ``jabin_core``.

Re-exports the three cross-cutting utilities that the whole platform relies on:

* :class:`ResponseBuilder` -- builds the canonical JABIN JSON envelope.
* :class:`ApiError`        -- structured representation of a single error.
* :class:`ExceptionMapper` -- converts Odoo exceptions into that envelope.
* :class:`JabinLogger`     -- reusable logger with INFO/WARNING/ERROR/AUDIT.

Import order: ``response_builder`` first (no dependencies), then
``exception_mapper`` (depends on the response builder), then ``logger``
(standalone).
"""

from .response_builder import ResponseBuilder, ApiError  # noqa: F401
from .exception_mapper import ExceptionMapper  # noqa: F401
from .logger import JabinLogger  # noqa: F401
