# -*- coding: utf-8 -*-
from __future__ import annotations
import threading
from typing import List, Optional, Set

_thread_local = threading.local()


class SecurityContext:
    """
    In-memory security context representing the authenticated user for the current request.
    Thread-safe and request-bound.
    """

    def __init__(
        self,
        user_id: Optional[int] = None,
        user_type: Optional[str] = None,
        email: Optional[str] = None,
        roles: Optional[List[str]] = None,
        permissions: Optional[Set[str]] = None,
        token_id: Optional[str] = None,
    ):
        self.user_id: Optional[int] = user_id
        self.user_type: Optional[str] = user_type
        self.email: Optional[str] = email
        self.roles: List[str] = list(roles or [])
        self.permissions: Set[str] = set(permissions or set())
        self.token_id: Optional[str] = token_id

    @property
    def is_authenticated(self) -> bool:
        """True if a valid user ID is associated with this context."""
        return self.user_id is not None

    @property
    def is_admin(self) -> bool:
        """
        True if the user has administrative privileges.
        Root superuser (id=1), user_type='admin' or 'system_admin',
        or having 'admin' / 'system_admin' in roles.
        """
        if not self.is_authenticated:
            return False
        if self.user_id == 1:
            return True
        if self.user_type in ("admin", "system_admin"):
            return True
        return bool({"admin", "system_admin"}.intersection(self.roles))

    def has_permission(self, permission_code: str) -> bool:
        """Check if the user has a specific permission or is an admin."""
        if not self.is_authenticated:
            return False
        if self.is_admin:
            return True
        return permission_code in self.permissions

    def has_any_permission(self, permission_codes: List[str]) -> bool:
        """Check if user has at least one of the given permissions or is an admin."""
        if not self.is_authenticated:
            return False
        if self.is_admin:
            return True
        return any(p in self.permissions for p in permission_codes)

    def has_all_permissions(self, permission_codes: List[str]) -> bool:
        """Check if user has all of the given permissions or is an admin."""
        if not self.is_authenticated:
            return False
        if self.is_admin:
            return True
        return all(p in self.permissions for p in permission_codes)

    def has_role(self, role_code: str) -> bool:
        """Check if user has a specific role or is an admin."""
        if not self.is_authenticated:
            return False
        if self.is_admin:
            return True
        return role_code in self.roles

    # Backward compatibility helpers
    def get_current_user_id(self) -> Optional[int]:
        return self.user_id

    def get_current_user_roles(self) -> List[str]:
        return list(self.roles)

    def get_current_user_permissions(self) -> Set[str]:
        return set(self.permissions)

    @classmethod
    def anonymous(cls) -> SecurityContext:
        """Return an unauthenticated anonymous context."""
        return cls(
            user_id=None,
            user_type=None,
            email=None,
            roles=[],
            permissions=set(),
            token_id=None,
        )

    @classmethod
    def set(cls, ctx: SecurityContext) -> None:
        """Store the context in thread-local storage and on request if available."""
        _thread_local.security_context = ctx
        try:
            from odoo.http import request
            if request:
                setattr(request, "_jabin_security_context", ctx)
        except Exception:
            pass

    @classmethod
    def get(cls) -> SecurityContext:
        """
        Retrieve the active security context.
        If not set, attempts auto-resolution from the current HTTP request Bearer token.
        """
        request = None
        try:
            from odoo.http import request
            if request and hasattr(request, "_jabin_security_context"):
                ctx = getattr(request, "_jabin_security_context", None)
                if ctx:
                    return ctx
        except Exception:
            request = None

        # Try thread-local
        ctx = getattr(_thread_local, "security_context", None)
        if ctx:
            return ctx

        # Auto-resolve from current HTTP Authorization header if available
        if request and hasattr(request, "httprequest"):
            try:
                raw_header = request.httprequest.headers.get("Authorization", "")
                if not raw_header and hasattr(request.httprequest, "environ"):
                    raw_header = request.httprequest.environ.get("HTTP_AUTHORIZATION", "")
                if raw_header:
                    parts = raw_header.split(None, 1)
                    if len(parts) == 2 and parts[0].lower() == "bearer":
                        token = parts[1].strip()
                        from odoo.addons.jabin_security.utils.jwt_utils import JWTUtils
                        claims = JWTUtils.decode_token(token)
                        if JWTUtils.get_token_kind(claims) == "access":
                            user_id = JWTUtils.get_user_id(claims)
                            user_type = JWTUtils.get_user_type(claims)
                            email = JWTUtils.get_email(claims)
                            token_id = JWTUtils.get_token_id(claims)
                            if user_id:
                                try:
                                    if request.env:
                                        authz_svc = request.env["jabin.authorization.service"].sudo()
                                        ctx = authz_svc.build_context(user_id, token_id=token_id)
                                        cls.set(ctx)
                                        return ctx
                                except Exception:
                                    pass
                                # Fallback context from token claims if DB lookup fails
                                ctx = SecurityContext(
                                    user_id=user_id,
                                    user_type=user_type,
                                    email=email,
                                    roles=[user_type] if user_type else [],
                                    permissions=set(),
                                    token_id=token_id,
                                )
                                cls.set(ctx)
                                return ctx
            except Exception:
                pass

        return cls.anonymous()