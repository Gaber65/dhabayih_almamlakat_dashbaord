# addons/jabin_auth/validators/internal_registration_validator.py

from __future__ import annotations

from typing import Any, Dict, Optional

from odoo.addons.jabin_core import (
    EmailValidator,
    PasswordValidator,
    JabinLogger,
)
from odoo.addons.jabin_core.helpers.validation_helper import (
    ValidationResult,
    ValidationHelper,
)

_logger = JabinLogger.get("auth.validator")


class InternalRegistrationValidator:
    """Validator for the internal admin registration payload.

    Validates all four required fields (name, username, email, password)
    using the project-wide validators from ``jabin_core``.
    Uniqueness checks (login / email) are delegated to the service layer,
    which has ORM access.

    Design: purely static — no Odoo ORM dependency — so it can be called
    from both the service layer and unit tests without a database.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def validate(data: Dict[str, Any]) -> ValidationResult:
        """Validate the admin registration payload.

        Checks:
        * ``name``     — required, non-empty string.
        * ``username`` — required, non-empty string (maps to ``res.users.login``).
        * ``email``    — required + RFC-ish format check via ``EmailValidator``.
        * ``password`` — required + strength policy via ``PasswordValidator``.

        Returns:
            :class:`~jabin_core.helpers.validation_helper.ValidationResult`
            with zero errors on success, one or more ``ApiError`` entries on
            failure.
        """
        result = ValidationResult()

        # --- name --------------------------------------------------------
        name: Optional[str] = data.get("name")
        if ValidationHelper.is_missing(name):
            result.add("name is required.", field="name")

        # --- username (maps to res.users.login) --------------------------
        username: Optional[str] = data.get("username")
        if ValidationHelper.is_missing(username):
            result.add("username is required.", field="username")

        # --- email -------------------------------------------------------
        email: Optional[str] = data.get("email")
        email_result = EmailValidator.validate(email, field="email")
        result.merge(email_result)

        # --- password ----------------------------------------------------
        password: Optional[str] = data.get("password")
        password_result = PasswordValidator.validate(password, field="password")
        result.merge(password_result)

        return result

    @staticmethod
    def normalise(data: Dict[str, Any]) -> Dict[str, str]:
        """Return a normalised copy of the validated payload.

        * Strips leading/trailing whitespace from all string fields.
        * Lower-cases ``email`` (canonical form).
        * ``username`` and ``name`` are left in their original case.

        Should only be called after :meth:`validate` returns ``ok=True``.
        """
        return {
            "name": str(data.get("name", "")).strip(),
            "username": str(data.get("username", "")).strip(),
            "email": str(data.get("email", "")).strip().lower(),
            "password": str(data.get("password", "")),
        }
