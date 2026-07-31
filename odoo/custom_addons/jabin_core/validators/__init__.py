# -*- coding: utf-8 -*-
"""Validators sub-package of ``jabin_core``.

This package defines the **project-wide validation structure** for the data
formats that recur across business modules. Each validator is a small,
self-contained class with a static :meth:`validate` method returning a
:class:`~jabin_core.helpers.validation_helper.ValidationResult` and a
convenience :meth:`is_valid` boolean predicate.

Sprint 1 scope
--------------
Only the *structure* is required for Sprint 1 -- the rules themselves are
sensible defaults but are intentionally kept simple and overridable so future
modules can tighten them (e.g. enforcing a specific password policy per tenant).

Validators provided
-------------------
* :class:`EmailValidator`    -- RFC-ish email format check.
* :class:`PhoneValidator`    -- E.164-ish phone number check.
* :class:`PasswordValidator` -- configurable password strength policy.
* :class:`PriceValidator`    -- non-negative monetary value with max bound.
* :class:`WeightValidator`   -- non-negative physical weight with max bound.
* :class:`UUIDValidator`     -- canonical UUID string check.

Design principles
----------------
* **Single responsibility** -- each validator knows one format only.
* **No exceptions** -- validators report problems via ``ValidationResult``,
  never by raising, so a request can collect every field error at once.
* **Reusable** -- pure functions, no Odoo dependency; usable in controllers,
  services, and tests.
* **Extensible** -- each class exposes class-level constants (regex, bounds)
  that subclasses or configuration can override.
"""

from .email_validator import EmailValidator  # noqa: F401
from .phone_validator import PhoneValidator  # noqa: F401
from .password_validator import PasswordValidator  # noqa: F401
from .price_validator import PriceValidator  # noqa: F401
from .weight_validator import WeightValidator  # noqa: F401
from .uuid_validator import UUIDValidator  # noqa: F401
from .base_validator import BaseValidator
from .validation_utils import ValidationUtils
from .field_validators import FieldValidators