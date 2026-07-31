from __future__ import annotations
import functools
from typing import Any, Callable
from odoo.addons.jabin_core import ResponseBuilder
from odoo.addons.jabin_security.utils.jwt_utils import JWTError, JWTUtils
from odoo.addons.jabin_security.utils.security_context import SecurityContext


def _extract_bearer_token(raw_header: str) -> str:
    if not raw_header:
        return ''
    parts = raw_header.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == 'bearer':
        return parts[1].strip()
    return ''


def auth_required(func: Callable) -> Callable:
    return _build_auth_decorator(func, optional=False)


def auth_optional(func: Callable) -> Callable:
    return _build_auth_decorator(func, optional=True)


def _build_auth_decorator(func: Callable, *, optional: bool) -> Callable:

    @functools.wraps(func)
    def wrapper(self, *args: Any, **kwargs: Any):
        try:
            from odoo import http
            from odoo.http import request
        except Exception:
            return func(self, *args, **kwargs)
        raw_header = ''
        try:
            httprequest = request.httprequest
            raw_header = httprequest.headers.get('Authorization', '')
        except Exception:
            raw_header = ''
        token = _extract_bearer_token(raw_header)
        if not token:
            if optional:
                SecurityContext.set(SecurityContext.anonymous())
                return func(self, *args, **kwargs)
            envelope = ResponseBuilder.unauthorized(
                message='Authentication required. Provide a Bearer token.',
                errors=[{'field': 'Authorization', 'message': 'Missing Bearer token.'}]
            )
            return self._build_response(envelope, status=401)
        try:
            claims = JWTUtils.decode_token(token)
        except JWTError as exc:
            envelope = ResponseBuilder.unauthorized(
                message=str(exc),
                errors=[{'field': 'Authorization', 'message': str(exc)}]
            )
            return self._build_response(envelope, status=401)
        kind = JWTUtils.get_token_kind(claims)
        if kind != 'access':
            envelope = ResponseBuilder.unauthorized(
                message='Invalid token type. An access token is required.',
                errors=[{'field': 'Authorization', 'message': 'Not an access token.'}]
            )
            return self._build_response(envelope, status=401)
        user_id = JWTUtils.get_user_id(claims)
        if user_id is None:
            envelope = ResponseBuilder.unauthorized(
                message='Token does not contain a valid user identifier.'
            )
            return self._build_response(envelope, status=401)
        user = request.env['res.users'].browse(user_id)  # Changed from res.users
        if not user.exists():
            envelope = ResponseBuilder.unauthorized(
                message='Token references a non-existent user.'
            )
            return self._build_response(envelope, status=401)
        authz_svc = request.env['jabin.authorization.service']
        if not authz_svc.is_account_active(user_id):
            try:
                request.env['jabin.audit.service'].log(
                    action='auth.blocked_inactive',
                    severity='warning',
                    user_id=user_id,
                    summary='Access blocked – account not active'
                )
            except Exception:
                pass
            envelope = ResponseBuilder.forbidden(
                message='Account is suspended or inactive.'
            )
            return self._build_response(envelope, status=403)
        token_id = JWTUtils.get_token_id(claims)
        ctx = authz_svc.build_context(user_id, token_id=token_id)
        SecurityContext.set(ctx)
        return func(self, *args, **kwargs)
    wrapper._jabin_auth = True
    wrapper._jabin_auth_optional = optional
    return wrapper