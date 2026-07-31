from __future__ import annotations
import functools
from typing import Any, Callable, List, Optional
from odoo.addons.jabin_core import ResponseBuilder
from odoo.addons.jabin_security.utils.security_context import SecurityContext

def permission_required(permission: Optional[str]=None, *, any_of: Optional[List[str]]=None, all_of: Optional[List[str]]=None) -> Callable:
    required_all: List[str] = list(all_of or [])
    if permission:
        required_all.append(permission)
    required_any: List[str] = list(any_of or [])

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        def wrapper(self, *args: Any, **kwargs: Any):
            try:
                from odoo.http import request
            except Exception:
                return func(self, *args, **kwargs)
            ctx = SecurityContext.get()
            if not ctx.is_authenticated:
                envelope = ResponseBuilder.unauthorized(message='Authentication required before permission check.')
                return self._build_response(envelope, status=401)
            authz_svc = request.env['jabin.authorization.service']
            allowed = authz_svc.authorize(ctx, any_of=required_any or None, all_of=required_all or None, require_active_account=True)
            if not allowed:
                try:
                    request.env['jabin.audit.service'].log_unauthorized(user_id=ctx.user_id, action='authz.permission_denied', permission=permission, any_of=required_any, all_of=required_all)
                except Exception:
                    pass
                envelope = ResponseBuilder.forbidden(message='You do not have permission to perform this action.')
                return self._build_response(envelope, status=403)
            return func(self, *args, **kwargs)
        wrapper._jabin_permission = {'permission': permission, 'any_of': required_any, 'all_of': required_all}
        return wrapper
    return decorator