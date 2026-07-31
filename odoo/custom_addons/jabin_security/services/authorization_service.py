from __future__ import annotations
from typing import List, Optional, Set
from odoo import api, models
from odoo.exceptions import MissingError
from odoo.addons.jabin_core import JabinLogger
from odoo.addons.jabin_security.utils.security_context import SecurityContext

_logger = JabinLogger.get('security.authorization_service')


class AuthorizationService(models.AbstractModel):
    _name = 'jabin.authorization.service'
    _description = 'JABIN Authorization Service'

    @api.model
    def build_context(self, user_id: int, token_id: Optional[str] = None) -> SecurityContext:
        user = self.env['res.users'].browse(user_id)  # Changed from res.users
        if not user.exists():
            raise MissingError(f'User {user_id} not found.')
        roles: List[str] = list(user.get_role_codes())
        permissions: Set[str] = set(user.get_permission_codes())
        user_type = getattr(user, 'user_type', None) or None  # Changed from x_user_type
        email = user.login or None
        ctx = SecurityContext(
            user_id=user_id,
            user_type=user_type,
            email=email,
            roles=roles,
            permissions=permissions,
            token_id=token_id
        )
        _logger.debug(
            'Built security context for user %s: roles=%s perms=%d',
            user_id,
            roles,
            len(permissions)
        )
        return ctx

    @api.model
    def is_account_active(self, user_id: int) -> bool:
        user = self.env['res.users'].browse(user_id)  # Changed from res.users
        if not user.exists():
            return False
        # Check if user is active in res.users
        if not user.active:
            return False
        # Check custom status field
        status = getattr(user, 'status', None)
        if status and status not in ('active', 'pending'):
            return False
        return True

    @api.model
    def check_permission(self, ctx: SecurityContext, permission_code: str) -> bool:
        if not ctx or not ctx.is_authenticated:
            return False
        return ctx.has_permission(permission_code)

    @api.model
    def check_any_permission(self, ctx: SecurityContext, permission_codes: List[str]) -> bool:
        if not ctx or not ctx.is_authenticated:
            return False
        return ctx.has_any_permission(permission_codes)

    @api.model
    def check_all_permissions(self, ctx: SecurityContext, permission_codes: List[str]) -> bool:
        if not ctx or not ctx.is_authenticated:
            return False
        if not permission_codes:
            return True
        return ctx.has_all_permissions(permission_codes)

    @api.model
    def check_role(self, ctx: SecurityContext, role_code: str) -> bool:
        if not ctx or not ctx.is_authenticated:
            return False
        if ctx.is_admin:
            return True
        return ctx.has_role(role_code)

    @api.model
    def authorize(
        self,
        ctx: SecurityContext,
        permission_code: Optional[str] = None,
        any_of: Optional[List[str]] = None,
        all_of: Optional[List[str]] = None,
        require_active_account: bool = True
    ) -> bool:
        if not ctx or not ctx.is_authenticated:
            return False
        if require_active_account and ctx.user_id is not None:
            if not self.is_account_active(ctx.user_id):
                _logger.audit(
                    'Authorization denied – inactive account: user=%s',
                    ctx.user_id,
                    extra={'user_id': ctx.user_id, 'action': 'authz_denied_inactive'}
                )
                return False
        if permission_code and (not self.check_permission(ctx, permission_code)):
            return False
        if any_of and (not self.check_any_permission(ctx, any_of)):
            return False
        if all_of and (not self.check_all_permissions(ctx, all_of)):
            return False
        return True