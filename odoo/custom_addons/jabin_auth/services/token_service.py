from odoo import models
from odoo.addons.jabin_security.utils.jwt_utils import (
    JWTUtils,
    DEFAULT_ACCESS_TTL,
)


class TokenService(models.AbstractModel):
    _name = "jabin.auth.token.service"
    _description = "Token Service"

    def generate_tokens(self, user: models.Model) -> dict:
        return {
            "access_token": JWTUtils.encode_access_token(
                user_id=user.id,
                user_type=user.user_type,
                email=user.login,  # Use login as email
            ),
            "refresh_token": JWTUtils.encode_refresh_token(
                user_id=user.id,
                user_type=user.user_type,
                email=user.login,  # Use login as email
            ),
            "user_type": user.user_type,

            "token_type": "Bearer",
            "expires_in": DEFAULT_ACCESS_TTL,
        }