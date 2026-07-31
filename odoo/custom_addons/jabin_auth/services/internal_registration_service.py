# addons/jabin_auth/services/internal_registration_service.py

from __future__ import annotations

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, AccessDenied
from odoo.addons.jabin_core import JabinLogger
from odoo.addons.jabin_auth.validators import InternalRegistrationValidator

_logger = JabinLogger.get("auth.internal.registration.service")

# System parameter key that holds the internal secret value.
_SECRET_PARAM_KEY = "jabin.internal.admin.secret"


class InternalRegistrationService(models.AbstractModel):
    """Service responsible for creating Odoo administrator accounts via the
    internal registration endpoint.

    This service intentionally bypasses:
    * OTP generation / verification
    * Email verification
    * The normal customer registration workflow

    It is intended **only** for trusted internal callers who supply the
    correct ``X-Internal-Secret`` header value.

    Security checklist enforced here:
    - Secret is validated before *anything* else is processed.
    - The secret value is **never** written to logs.
    - Stack traces are suppressed from API responses (handled by the controller).
    - Duplicate ``login`` (username) and ``email`` are rejected.
    - Passwords are hashed by Odoo's native mechanism.
    - The created account is immediately active and assigned administrator
      permissions (``base.group_system``).
    """

    _name = "jabin.auth.internal.registration.service"
    _description = "Internal Admin Registration Service"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @api.model
    def register_admin(self, secret: str, data: dict) -> dict:
        """Create a new Odoo administrator account.

        Steps (in order):
        1. Validate the internal secret.
        2. Validate and normalise the request payload.
        3. Check uniqueness of ``login`` (username) and ``email``.
        4. Create the ``res.users`` record with an active status.
        5. Hash the password using Odoo's native mechanism.
        6. Assign ``base.group_system`` (Administrator).
        7. Commit the transaction.
        8. Log the successful creation.

        Args:
            secret: Value from the ``X-Internal-Secret`` request header.
            data:   Parsed JSON body ``{name, username, email, password}``.

        Returns:
            dict with ``success=True`` and a confirmation message.

        Raises:
            :class:`odoo.exceptions.AccessDenied`: If the secret is invalid.
            :class:`odoo.exceptions.ValidationError`: If validation or
                uniqueness checks fail.
        """
        # Step 1 — validate internal secret (do this first, before touching data)
        self._validate_secret(secret)

        # Step 2 — validate request payload
        result = InternalRegistrationValidator.validate(data)
        if not result.ok:
            # Build a single human-readable message from all field errors
            messages = "; ".join(e.message for e in result.errors)
            _logger.warning(
                "ADMIN_REGISTER_VALIDATION_FAILED | errors: %s",
                messages,
            )
            raise ValidationError(_(messages))

        # Step 3 — normalise
        payload = InternalRegistrationValidator.normalise(data)
        username: str = payload["username"]
        email: str = payload["email"]
        name: str = payload["name"]
        password: str = payload["password"]

        # Step 4 — uniqueness checks
        self._assert_username_unique(username)
        self._assert_email_unique(email)

        # Step 5 — create res.users record
        user = self._create_admin_user(name=name, username=username, email=email)

        # Step 6 — set hashed password via Odoo's native mechanism
        self._set_password(user, password)

        # Step 7 — assign administrator group
        self._grant_admin_group(user)

        # Step 8 — commit transaction
        self.env.cr.commit()

        _logger.audit(
            "ADMIN_CREATED | login=%s | email=%s | user_id=%s",
            username,
            email,
            user.id,
        )

        return {"success": True, "message": "Administrator created successfully"}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_secret(self, provided_secret: str) -> None:
        """Compare *provided_secret* against the system configuration value.

        The stored secret is read from ``ir.config_parameter`` using the key
        ``jabin.internal.admin.secret``.  The provided value is **never**
        written to any log entry — only a boolean result is logged.

        Raises:
            :class:`odoo.exceptions.AccessDenied`: If the secret is missing,
                blank, or does not match the stored value.
        """
        if not provided_secret or not provided_secret.strip():
            _logger.warning("ADMIN_REGISTER_FAILED | reason=missing_secret")
            raise AccessDenied("Internal secret is required.")

        stored_secret = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(_SECRET_PARAM_KEY, default="")
        )

        if not stored_secret:
            _logger.error(
                "ADMIN_REGISTER_FAILED | reason=secret_param_not_configured"
                " | param=%s",
                _SECRET_PARAM_KEY,
            )
            raise AccessDenied("Internal registration is not configured.")

        # Constant-time comparison to prevent timing-based secret enumeration
        import hmac as _hmac

        if not _hmac.compare_digest(
            provided_secret.strip(), stored_secret.strip()
        ):
            _logger.warning(
                "ADMIN_REGISTER_FAILED | reason=invalid_secret"
            )
            raise AccessDenied("Invalid internal secret.")

    def _assert_username_unique(self, username: str) -> None:
        """Raise ValidationError if *username* is already taken as a login.

        Args:
            username: Normalised login string to check.

        Raises:
            :class:`odoo.exceptions.ValidationError`: If a user with this
                login already exists.
        """
        existing = self.env["res.users"].sudo().search(
            [("login", "=", username)], limit=1
        )
        if existing:
            _logger.warning(
                "ADMIN_REGISTER_FAILED | reason=duplicate_username | login=%s",
                username,
            )
            raise ValidationError(
                _(f"Username '{username}' is already registered.")
            )

    def _assert_email_unique(self, email: str) -> None:
        """Raise ValidationError if *email* is already taken.

        ``res.users.login`` is used as the canonical email identifier, matching
        the pattern established by the existing registration service.

        Args:
            email: Normalised (lowercased) email string to check.

        Raises:
            :class:`odoo.exceptions.ValidationError`: If a user with this
                email already exists.
        """
        existing = self.env["res.users"].sudo().search(
            ["|", ("login", "=", email), ("email", "=", email)], limit=1
        )
        if existing:
            _logger.warning(
                "ADMIN_REGISTER_FAILED | reason=duplicate_email | email=%s",
                email,
            )
            raise ValidationError(
                _(f"Email '{email}' is already registered.")
            )

    def _create_admin_user(
        self,
        *,
        name: str,
        username: str,
        email: str,
    ):
        """Create and return a new ``res.users`` record.

        The account is created in ``active`` status with email verification
        already set, bypassing the normal pending → active flow.

        Args:
            name:     Display name for the user.
            username: Login identifier (maps to ``res.users.login``).
            email:    Email address.

        Returns:
            The newly created ``res.users`` recordset (singleton).

        Raises:
            :class:`odoo.exceptions.ValidationError`: If record creation fails.
        """
        try:
            user = self.env["res.users"].sudo().create({
                "name": name,
                "login": username,
                "email": email,
                # Activate immediately — skip pending status
                "active": True,
                "status": "active",
                "verified_at": fields.Datetime.now(),
                "profile_completed": True,
                "user_type": "admin",
            })
            _logger.info(
                "ADMIN_USER_RECORD_CREATED | login=%s | user_id=%s",
                username,
                user.id,
            )
            return user
        except Exception as exc:
            _logger.error(
                "ADMIN_REGISTER_FAILED | reason=create_failed | login=%s | error=%s",
                username,
                exc,
            )
            raise ValidationError(
                _("Failed to create administrator account. Please try again.")
            )

    @staticmethod
    def _set_password(user, password: str) -> None:
        try:
            user.sudo().write({
                "password": password
            })
        except Exception as exc:
            _logger.error(
                "ADMIN_REGISTER_FAILED | reason=password_set_failed"
                " | user_id=%s | error=%s",
                user.id,
                exc,
            )
            raise ValidationError(
                _("Failed to set administrator password. Please try again.")
            )

    def _grant_admin_group(self, user) -> None:
        """Add *user* to ``base.group_system`` (Odoo Administrator).

        Uses ``(4, id)`` ORM command — the standard Odoo way to link a
        Many2many relation without replacing existing groups.

        Args:
            user: ``res.users`` singleton to promote.

        Raises:
            :class:`odoo.exceptions.ValidationError`: If group assignment fails.
        """
        try:
            admin_group = self.env.ref("base.group_system")
            user.sudo().write({
                "groups_id": [(4, admin_group.id)],
            })
            _logger.info(
                "ADMIN_GROUP_GRANTED | user_id=%s | group=%s",
                user.id,
                admin_group.full_name,
            )
        except Exception as exc:
            _logger.error(
                "ADMIN_REGISTER_FAILED | reason=group_grant_failed"
                " | user_id=%s | error=%s",
                user.id,
                exc,
            )
            raise ValidationError(
                _("Failed to assign administrator permissions. Please try again.")
            )
