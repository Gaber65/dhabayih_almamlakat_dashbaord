# addons/jabin_auth/controllers/auth.py

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request
import json
from odoo.exceptions import AccessDenied

from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder, JabinLogger

_logger = JabinLogger.get("auth.controller")


class AuthController(BaseApiController):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _handle_validation_error(exc: ValidationError):
        msg = str(exc)
        lower = msg.lower()

        if "already registered" in lower:
            return ResponseBuilder.http_conflict(message=msg)

        if "not found" in lower:
            return ResponseBuilder.http_not_found(message=msg)

        return ResponseBuilder.http_bad_request(message=msg)

    @staticmethod
    def _handle_server_error(action: str, exc: Exception):
        _logger.exception("%s failed: %s", action, exc)
        return ResponseBuilder.http_server_error(
            message="Internal server error"
        )

    @staticmethod
    def _get_request_data():
        """Get JSON data from request body for type='http' routes."""
        try:
            # Get the raw request data
            raw_data = request.httprequest.data.decode('utf-8')
            if raw_data:
                return json.loads(raw_data)
            return {}
        except json.JSONDecodeError:
            return {}
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Register
    # ------------------------------------------------------------------

    @http.route(
        "/api/v1/auth/register",
        type="http",  # Using http for proper status codes
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def register(self):
        try:
            data = self._get_request_data()
            email = data.get("email")

            if not email:
                return ResponseBuilder.http_bad_request(
                    message="Email is required"
                )

            result = (
                request.env["jabin.auth.registration.service"]
                .sudo()
                .initiate_registration(email)
            )

            return ResponseBuilder.http_success(
                data={"expires_in": result.get("expires_in")},
                message="OTP sent to your email.",
                code=200
            )

        except ValidationError as exc:
            return self._handle_validation_error(exc)

        except Exception as exc:
            return self._handle_server_error("Register", exc)

    # ------------------------------------------------------------------
    # Register Verify OTP
    # ------------------------------------------------------------------

    @http.route(
        "/api/v1/auth/register/verify",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def register_verify(self):
        try:
            data = self._get_request_data()
            email = data.get("email")
            otp = data.get("otp")

            if not email or not otp:
                return ResponseBuilder.http_bad_request(
                    message="Email and OTP are required"
                )

            tokens = (
                request.env["jabin.auth.registration.service"]
                .sudo()
                .verify_registration(email, otp)
            )

            return ResponseBuilder.http_success(
                data=tokens,
                message="Registration successful.",
            )

        except ValidationError as exc:
            return self._handle_validation_error(exc)

        except Exception as exc:
            return self._handle_server_error("Register verify", exc)

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    @http.route(
        "/api/v1/auth/login",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def login(self):
        try:
            data = self._get_request_data()
            email = data.get("email")

            if not email:
                return ResponseBuilder.http_bad_request(
                    message="Email is required"
                )

            result = (
                request.env["jabin.auth.login.service"]
                .sudo()
                .initiate_login(email)
            )

            # Check if user needs verification
            if result.get('requires_verification'):
                return ResponseBuilder.http_success(
                    data={
                        "expires_in": result.get("expires_in"),
                        "requires_verification": True,
                        "action": "verify_account"
                    },
                    message=result.get('message', 'Account needs verification. A code has been sent to your email.'),
                    code=202  # 202 Accepted - Not yet verified but we sent the code
                )

            return ResponseBuilder.http_success(
                data={"expires_in": result.get("expires_in")},
                message="Login OTP sent to your email.",
            )

        except ValidationError as exc:
            return self._handle_validation_error(exc)

        except Exception as exc:
            return self._handle_server_error("Login", exc)

    @http.route(
        "/api/v1/auth/resend-verification",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def resend_verification(self):
        """
        Explicitly resend verification OTP for pending accounts.
        """
        try:
            data = self._get_request_data()
            email = data.get("email")

            if not email:
                return ResponseBuilder.http_bad_request(
                    message="Email is required"
                )

            result = (
                request.env["jabin.auth.login.service"]
                .sudo()
                .resend_verification_for_pending(email)
            )

            return ResponseBuilder.http_success(
                data={"expires_in": result.get("expires_in")},
                message="Verification code resent to your email.",
            )

        except ValidationError as exc:
            return self._handle_validation_error(exc)

        except Exception as exc:
            return self._handle_server_error("Resend Verification", exc)

    # ------------------------------------------------------------------
    # Login Verify OTP
    # ------------------------------------------------------------------

    @http.route(
        "/api/v1/auth/login/verify",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def login_verify(self):
        try:
            data = self._get_request_data()
            email = data.get("email")
            otp = data.get("otp")

            if not email or not otp:
                return ResponseBuilder.http_bad_request(
                    message="Email and OTP are required"
                )

            tokens = (
                request.env["jabin.auth.login.service"]
                .sudo()
                .verify_login(email, otp)
            )

            return ResponseBuilder.http_success(
                data=tokens,
                message="Login successful.",
            )

        except ValidationError as exc:
            return self._handle_validation_error(exc)

        except Exception as exc:
            return self._handle_server_error("Login verify", exc)

    # ------------------------------------------------------------------
    # Internal Admin Registration
    # ------------------------------------------------------------------

    @http.route(
        "/api/v1/internal/register-admin",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def register_admin(self):
        """Create an Odoo administrator account bypassing OTP/email verification.

        Authentication is via the ``X-Internal-Secret`` request header.
        This endpoint is intended **only** for trusted internal system
        initialisation and must never be exposed to end-users.

        Returns:
            200 + ``{"success": true, "message": "Administrator created
            successfully"}`` on success.
            400 for validation failures.
            403 for a missing or invalid internal secret.
            409 for duplicate username or email.
            500 for unexpected server errors.
        """

        try:
            # Extract secret from header — never log its value
            secret = request.httprequest.headers.get("X-Internal-Secret", "")

            data = self._get_request_data()

            (
                request.env["jabin.auth.internal.registration.service"]
                .sudo()
                .register_admin(secret, data)
            )

            return ResponseBuilder.http_success(
                message="Administrator created successfully",
                code=200,
            )

        except AccessDenied as exc:
            _logger.warning("ADMIN_REGISTER | access_denied: %s", exc)
            return ResponseBuilder.http_forbidden(
                message=str(exc) or "Invalid or missing internal secret."
            )

        except ValidationError as exc:
            return self._handle_validation_error(exc)

        except Exception as exc:
            return self._handle_server_error("Register admin", exc)

    @http.route(
        "/api/v1/auth/refresh",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def refresh_token(self):
        try:
            token = None
            raw_header = request.httprequest.headers.get("Authorization", "")
            if raw_header:
                parts = raw_header.split(None, 1)
                if len(parts) == 2 and parts[0].lower() == 'bearer':
                    token = parts[1].strip()

            if not token:
                try:
                    body = self._get_request_data()
                    token = body.get("refresh_token") or body.get("refreshToken")
                except Exception:
                    pass

            if not token:
                return ResponseBuilder.http_unauthorized(message="Missing refresh token in Authorization header or body")

            from odoo.addons.jabin_security.utils.jwt_utils import JWTUtils, JWTError
            try:
                claims = JWTUtils.decode_token(token)
            except JWTError as exc:
                return ResponseBuilder.http_unauthorized(message=str(exc))

            kind = JWTUtils.get_token_kind(claims)
            if kind != 'refresh':
                return ResponseBuilder.http_bad_request(message="Invalid token kind. Refresh token expected.")

            jti = JWTUtils.get_token_id(claims)

            refresh_token_model = request.env['jabin.refresh.token'].sudo()
            if not refresh_token_model.is_valid(jti):
                return ResponseBuilder.http_unauthorized(message="Refresh token is revoked or expired.")

            user_id = JWTUtils.get_user_id(claims)
            user = request.env['res.users'].sudo().browse(user_id)
            if not user.exists() or (hasattr(user, "status") and user.status != "active"):
                return ResponseBuilder.http_unauthorized(message="User account is inactive or not found.")

            # Revoke old refresh token so it cannot be used again
            old_token_rec = refresh_token_model.find_by_jti(jti)
            if old_token_rec:
                old_token_rec.revoke()
            else:
                from datetime import datetime, timedelta
                from odoo.addons.jabin_security.utils.jwt_utils import DEFAULT_REFRESH_TTL
                expires_at = datetime.utcnow() + timedelta(seconds=DEFAULT_REFRESH_TTL)
                try:
                    refresh_token_model.create({
                        'jti': jti,
                        'user_id': user.id,
                        'expires_at': expires_at,
                        'is_revoked': True,
                        'revoked_at': fields.Datetime.now(),
                    })
                except Exception:
                    pass

            # generate_tokens automatically issues & registers new refresh token in DB
            tokens_data = request.env["jabin.auth.token.service"].sudo().generate_tokens(user)

            if hasattr(request.env['jabin.security.audit.service'].sudo(), 'log_token_refresh'):
                try:
                    request.env['jabin.security.audit.service'].sudo().log_token_refresh(user.id)
                except Exception:
                    pass

            return ResponseBuilder.http_success(
                data=tokens_data,
                message="Token refreshed successfully.",
            )

        except Exception as exc:
            return self._handle_server_error("Token refresh", exc)
