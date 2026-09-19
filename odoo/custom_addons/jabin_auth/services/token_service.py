from datetime import datetime, timedelta
from odoo import models
from odoo.addons.jabin_core import JabinLogger
from odoo.addons.jabin_security.utils.jwt_utils import (
    JWTUtils,
    DEFAULT_ACCESS_TTL,
    DEFAULT_REFRESH_TTL,
)

_logger = JabinLogger.get('auth.token_service')


class TokenService(models.AbstractModel):
    _name = "jabin.auth.token.service"
    _description = "Token Service"

    def generate_tokens(self, user: models.Model) -> dict:
        user_type = getattr(user, 'user_type', None) or 'individual'
        access_token = JWTUtils.encode_access_token(
            user_id=user.id,
            user_type=user_type,
            email=user.login,  # Use login as email
        )
        refresh_token = JWTUtils.encode_refresh_token(
            user_id=user.id,
            user_type=user_type,
            email=user.login,  # Use login as email
        )

        # Automatically register the refresh token in jabin.refresh.token
        try:
            claims = JWTUtils.decode_token(refresh_token)
            jti = JWTUtils.get_token_id(claims)
            expires_at = datetime.utcnow() + timedelta(seconds=DEFAULT_REFRESH_TTL)
            self.env['jabin.refresh.token'].sudo().register(
                jti=jti,
                user_id=user.id,
                expires_at=expires_at,
            )
        except Exception as exc:
            _logger.warning(f"Could not register refresh token in DB: {exc}")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_type": user_type,
            "token_type": "Bearer",
            "expires_in": DEFAULT_ACCESS_TTL,
        }