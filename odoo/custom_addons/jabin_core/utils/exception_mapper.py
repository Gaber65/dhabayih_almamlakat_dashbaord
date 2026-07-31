# -*- coding: utf-8 -*-
"""Centralised exception mapper for the JABIN platform.

Goal
----
Provide a single point where *any* Odoo / Python exception raised inside an
API request is translated into the canonical JABIN JSON envelope (see
:class:`~jabin_core.utils.response_builder.ResponseBuilder`).

Why centralisation?
-------------------
Without a mapper every controller would need its own ``try/except`` boilerplate,
leading to inconsistent error shapes and accidental stack-trace leaks. The
mapper guarantees:

1. **Consistent shape** -- every error response follows the envelope.
2. **No stack traces in production** -- the traceback is logged (via
   :class:`~jabin_core.utils.logger.JabinLogger`) but never serialised into the
   HTTP body.
3. **Correct HTTP-ish codes** -- each exception family maps to a sensible code.
4. **Structured field errors** -- ``ValidationError`` messages that contain a
   field hint are surfaced as structured ``errors`` entries.

Exception -> code matrix
------------------------
==================  ======  ===================================================
Exception           Code    Meaning
==================  ======  ===================================================
ValidationError      400    Business validation failure (user input).
UserError            400    Generic user-facing error.
AccessError          403    Record-level access denied.
MissingError         404    Record not found.
AccessDenied         401    Authentication failed (bad credentials).
IntegrityError       409    DB constraint violation (duplicate / FK).
Exception            500    Unhandled / unexpected server error.
==================  ======  ===================================================

Usage
-----
Controllers wrap their handler in ``ExceptionMapper.handle(...)``::

    try:
        ...
    except Exception as exc:
        body, status = ExceptionMapper.handle(exc, logger=logger)
        return ResponseBuilder ... # serialise body with status

``handle()`` returns a tuple ``(envelope_dict, http_status_code)``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from .response_builder import ResponseBuilder, ApiError

# ---------------------------------------------------------------------------
# Lazy imports of Odoo exceptions.
#
# The mapper must be importable both inside and outside a running Odoo server
# (e.g. in unit tests). We therefore import the Odoo exception classes lazily
# and degrade gracefully when they are unavailable.
# ---------------------------------------------------------------------------
try:  # pragma: no cover - environment dependent
    from odoo.exceptions import (
        ValidationError,
        UserError,
        AccessError,
        MissingError,
        AccessDenied,
    )
    _ODOO_AVAILABLE = True
except Exception:  # pragma: no cover - Odoo not on path
    # Fallback sentinels so the module loads in plain-Python test contexts.
    class ValidationError(Exception):
        """Fallback when Odoo is not importable (test only)."""

    class UserError(Exception):
        """Fallback when Odoo is not importable (test only)."""

    class AccessError(Exception):
        """Fallback when Odoo is not importable (test only)."""

    class MissingError(Exception):
        """Fallback when Odoo is not importable (test only)."""

    class AccessDenied(Exception):
        """Fallback when Odoo is not importable (test only)."""

    _ODOO_AVAILABLE = False

try:  # psycopg2 may not be installed in non-Odoo test envs.
    from psycopg2.errors import IntegrityError  # type: ignore
except Exception:  # pragma: no cover - psycopg2 not on path

    class IntegrityError(Exception):
        """Fallback when psycopg2 is not importable (test only)."""


# ---------------------------------------------------------------------------
# Mapping table (exception class -> (code, default message))
# ---------------------------------------------------------------------------
# Order matters: subclasses must be checked before their parents because
# Python's ``isinstance`` treats them as compatible. The table is walked in
# insertion order so we keep the most specific types first.
_MAPPING: List[Tuple[type, int, str]] = [
    (ValidationError, 400, "Validation Error"),
    (UserError, 400, "Bad Request"),
    (AccessDenied, 401, "Authentication failed"),
    (AccessError, 403, "Access denied"),
    (MissingError, 404, "Resource not found"),
    (IntegrityError, 409, "Conflict - constraint violation"),
]


class ExceptionMapper:
    """Translate exceptions into the canonical JABIN JSON envelope.

    The class is fully static; it carries no mutable state, which makes it
    trivially thread-safe and testable.
    """

    # Regex used to detect a leading "field:" hint in some Odoo validation
    # messages so we can surface a structured field error. Kept intentionally
    # conservative.
    _FIELD_HINT_PREFIX = "Field "

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    @classmethod
    def handle(
        cls,
        exception: BaseException,
        logger: Optional[logging.Logger] = None,
        *,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], int]:
        """Convert ``exception`` into ``(envelope_dict, http_status)``.

        Parameters
        ----------
        exception:
            The exception raised inside the request handler.
        logger:
            Optional :class:`logging.Logger` (typically a
            :class:`~jabin_core.utils.logger.JabinLogger`). When provided the
            traceback is logged at ERROR level; in production this keeps the
            stack trace out of the HTTP body.
        context:
            Optional dict with request metadata (endpoint, request_id, ...)
            appended to the log entry for traceability.

        Returns
        -------
        (dict, int)
            The JSON envelope and the HTTP status code to set on the response.
        """
        code, message, errors = cls._classify(exception)

        # Log the exception. WARNING for expected business errors, ERROR for
        # unexpected ones (5xx).
        if logger is not None:
            cls._log(exception, code, message, logger, context=context)

        envelope = ResponseBuilder.error(
            message=message,
            code=code,
            errors=errors,
        )
        return envelope, code

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    @classmethod
    def _classify(
        cls, exception: BaseException
    ) -> Tuple[int, str, Optional[List[ApiError]]]:
        """Determine (code, message, errors) for ``exception``.

        Returns the 3-tuple used by :meth:`handle`. ``errors`` is ``None`` for
        non-validation exceptions and a list of :class:`ApiError` for
        validation/business errors.
        """
        # Dynamically inspect exception type and class name
        exc_name = exception.__class__.__name__

        # Walk the mapping table in order (specific -> generic).
        for exc_type, code, default_msg in _MAPPING:
            if isinstance(exception, exc_type) or exc_name == exc_type.__name__:
                if exc_type is ValidationError or exc_name == "ValidationError":
                    errors = cls._build_validation_errors(exception)
                    return code, default_msg, errors
                if exc_type is UserError or exc_name == "UserError":
                    errors = cls._build_validation_errors(exception)
                    return code, default_msg, errors
                return code, default_msg, None

        # Try matching against current odoo.exceptions at runtime
        try:
            import odoo.exceptions as o_exc
            if isinstance(exception, (o_exc.ValidationError, o_exc.UserError)):
                errors = cls._build_validation_errors(exception)
                return 400, "Validation Error", errors
            elif isinstance(exception, o_exc.AccessDenied):
                return 401, "Authentication failed", None
            elif isinstance(exception, o_exc.AccessError):
                return 403, "Access denied", None
            elif isinstance(exception, o_exc.MissingError):
                return 404, "Resource not found", None
        except Exception:
            pass

        # Anything not matched is an unexpected server error.
        return 500, "Internal Server Error", None

    @staticmethod
    def _build_validation_errors(exception: BaseException) -> List[ApiError]:
        """Best-effort extraction of structured field errors from a
        ``ValidationError``.

        Odoo validation messages are free-form strings. When a clear field
        name can be inferred we surface it; otherwise we fall back to a single
        global error (``field=None``).
        """
        raw = str(exception).strip()
        if not raw:
            raw = "Validation failed."

        # If the message is explicitly structured as "Field 'x': ..." surface it.
        if ExceptionMapper._FIELD_HINT_PREFIX in raw:
            # Naive but safe: split on first colon after the field name.
            try:
                _, rest = raw.split("Field", 1)
                field_name, msg = rest.strip().split(":", 1)
                field_name = field_name.strip().strip("'\"")
                msg = msg.strip() or raw
                return [ApiError(message=msg, field=field_name)]
            except Exception:
                pass  # fall through to global error

        return [ApiError(message=raw, field=None)]

    # ------------------------------------------------------------------ #
    # Logging
    # ------------------------------------------------------------------ #
    @staticmethod
    def _log(
        exception: BaseException,
        code: int,
        message: str,
        logger: logging.Logger,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log the exception at the appropriate level.

        * 4xx (client/business) -> WARNING (expected flow).
        * 5xx (server)          -> ERROR + full traceback (needs attention).
        """
        ctx_str = ""
        if context:
            # Avoid leaking sensitive data by only logging keys, not values.
            ctx_str = " | context keys: " + ",".join(sorted(context.keys()))

        if code >= 500:
            logger.error(
                "JABIN unmapped server error: %s (code=%s)%s",
                message,
                code,
                ctx_str,
                exc_info=exception,
            )
        else:
            logger.warning(
                "JABIN business error: %s (code=%s) :: %s%s",
                message,
                code,
                str(exception)[:500],  # truncate very long messages
                ctx_str,
            )

    # ------------------------------------------------------------------ #
    # Introspection helpers (useful for tests / documentation)
    # ------------------------------------------------------------------ #
    @classmethod
    def supported_exceptions(cls) -> List[type]:
        """Return the list of exception classes the mapper explicitly handles."""
        return [exc_type for exc_type, _, _ in _MAPPING]

    @classmethod
    def is_odoo_available(cls) -> bool:
        """Return ``True`` when the real Odoo exception classes are importable."""
        return _ODOO_AVAILABLE
