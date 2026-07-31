from __future__ import annotations
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.addons.jabin_core import JabinLogger

_logger = JabinLogger.get('auth.refresh_token')


class JabinRefreshToken(models.Model):
    _name = 'jabin.refresh.token'
    _description = 'JABIN Refresh Token'
    _order = 'expires_at desc'

    jti = fields.Char(
        string='Token ID (jti)',
        required=True,
        index=True,
        help='Unique JWT ID of the refresh token (UUID hex).'
    )
    user_id = fields.Many2one(
        comodel_name='res.users',  # Changed from res.users
        string='User',
        required=True,
        index=True,
        ondelete='cascade',
        help='The user this refresh token belongs to.'
    )
    expires_at = fields.Datetime(
        string='Expires At',
        required=True,
        index=True,
        help='When the refresh token becomes naturally invalid.'
    )
    is_revoked = fields.Boolean(
        string='Revoked',
        default=False,
        index=True,
        help='True when the token has been explicitly revoked (logout, etc.).'
    )
    revoked_at = fields.Datetime(
        string='Revoked At',
        help='Timestamp of revocation (if any).'
    )
    ip_address = fields.Char(
        string='Issuing IP',
        help='Client IP from which the token was issued (for audit).'
    )
    user_agent = fields.Char(
        string='Issuing User-Agent',
        help='Client User-Agent from which the token was issued.'
    )

    _sql_constraints = [
        ('jti_unique', 'unique(jti)', 'A refresh token with this jti already exists.')
    ]

    @api.model
    def register(
            self,
            *,
            jti: str,
            user_id: int,
            expires_at,
            ip_address: str = '',
            user_agent: str = ''
    ):
        if not jti:
            raise ValidationError('Cannot register a refresh token without a jti.')
        return self.create({
            'jti': jti,
            'user_id': user_id,
            'expires_at': expires_at,
            'ip_address': ip_address or None,
            'user_agent': user_agent or None
        })

    @api.model
    def find_by_jti(self, jti: str):
        if not jti:
            return self.env['jabin.refresh.token']
        return self.search([('jti', '=', jti)], limit=1)

    @api.model
    def is_valid(self, jti: str) -> bool:
        token = self.find_by_jti(jti)
        if not token:
            return False
        if token.is_revoked:
            return False
        now = fields.Datetime.now()
        if token.expires_at and token.expires_at <= now:
            return False
        return True

    def revoke(self):
        now = fields.Datetime.now()
        for token in self:
            if not token.is_revoked:
                token.write({'is_revoked': True, 'revoked_at': now})
        _logger.audit(
            'Refresh tokens revoked: count=%d',
            len(self),
            extra={'action': 'revoke_refresh_token', 'count': len(self)}
        )
        return True

    @api.model
    def revoke_all_for_user(self, user_id: int) -> int:
        tokens = self.search([
            ('user_id', '=', user_id),
            ('is_revoked', '=', False)
        ])
        count = len(tokens)
        if count:
            tokens.revoke()
        return count

    @api.model
    def purge_expired(self) -> int:
        now = fields.Datetime.now()
        expired = self.search([
            ('is_revoked', '=', True),
            ('expires_at', '<', now)
        ])
        count = len(expired)
        if count:
            expired.unlink()
        return count

    def to_dict(self) -> dict:
        self.ensure_one()
        return {
            'id': self.id,
            'jti': self.jti,
            'user_id': self.user_id.id,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_revoked': self.is_revoked,
            'revoked_at': self.revoked_at.isoformat() if self.revoked_at else None,
            'ip_address': self.ip_address or None
        }