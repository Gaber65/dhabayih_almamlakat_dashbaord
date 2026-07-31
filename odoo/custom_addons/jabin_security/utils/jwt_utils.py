from __future__ import annotations
import os
import uuid
from typing import Any, Dict, Optional
import jwt
ALGORITHM: str = 'HS256'
ISSUER: str = 'jabin'
DEFAULT_ACCESS_TTL: int = 24 * 3600
DEFAULT_REFRESH_TTL: int = 7 * 24 * 3600
_DEV_SECRET: str = 'jabin-dev-secret-change-in-production-please'
CLAIM_SUBJECT = 'sub'
CLAIM_USER_TYPE = 'type'
CLAIM_EMAIL = 'email'
CLAIM_TOKEN_ID = 'jti'
CLAIM_ISSUED_AT = 'iat'
CLAIM_EXPIRY = 'exp'
CLAIM_ISSUER = 'iss'
CLAIM_TOKEN_KIND = 'kind'

class JWTError(Exception):
    def __init__(self, message: str):
        self.message = message

class JWTUtils:

    @staticmethod
    def _resolve_secret(explicit: Optional[str]=None) -> str:
        if explicit:
            return explicit
        env_secret = os.environ.get('JABIN_JWT_SECRET')
        if env_secret:
            return env_secret
        try:
            from odoo.tools.config import config
            cfg_secret = config.get('jabin_jwt_secret')
            if cfg_secret:
                return cfg_secret
        except Exception:
            pass
        return _DEV_SECRET

    @staticmethod
    def encode_access_token(user_id: int, user_type: str, email: str, *, secret: Optional[str]=None, ttl: int=DEFAULT_ACCESS_TTL) -> str:
        return JWTUtils._encode(user_id=user_id, user_type=user_type, email=email, kind='access', ttl=ttl, secret=secret)

    @staticmethod
    def encode_refresh_token(user_id: int, user_type: str, email: str, *, secret: Optional[str]=None, ttl: int=DEFAULT_REFRESH_TTL) -> str:
        return JWTUtils._encode(user_id=user_id, user_type=user_type, email=email, kind='refresh', ttl=ttl, secret=secret)

    @staticmethod
    def _encode(user_id: int, user_type: str, email: str, kind: str, ttl: int, secret: Optional[str]) -> str:
        import time
        now = int(time.time())
        claims = {CLAIM_SUBJECT: str(user_id), CLAIM_USER_TYPE: user_type, CLAIM_EMAIL: email, CLAIM_TOKEN_ID: uuid.uuid4().hex, CLAIM_TOKEN_KIND: kind, CLAIM_ISSUED_AT: now, CLAIM_EXPIRY: now + ttl, CLAIM_ISSUER: ISSUER}
        try:
            return jwt.encode(claims, JWTUtils._resolve_secret(secret), algorithm=ALGORITHM)
        except Exception as exc:
            raise JWTError(f'Failed to encode JWT: {exc}') from exc

    @staticmethod
    def decode_token(token: str, *, secret: Optional[str]=None, verify_exp: bool=True) -> Dict[str, Any]:
        if not token:
            raise JWTError('Token is empty.')
        try:
            payload = jwt.decode(token, JWTUtils._resolve_secret(secret), algorithms=[ALGORITHM], issuer=ISSUER, options={'verify_exp': verify_exp, 'verify_iss': True})
        except jwt.ExpiredSignatureError as exc:
            raise JWTError('Token has expired.') from exc
        except jwt.InvalidIssuerError as exc:
            raise JWTError('Token issuer is invalid.') from exc
        except jwt.InvalidTokenError as exc:
            raise JWTError(f'Invalid token: {exc}') from exc
        except Exception as exc:
            raise JWTError(f'Failed to decode JWT: {exc}') from exc
        return payload

    @staticmethod
    def decode_without_verification(token: str) -> Dict[str, Any]:
        if not token:
            raise JWTError('Token is empty.')
        try:
            return jwt.decode(token, options={'verify_signature': False, 'verify_exp': False, 'verify_iss': False}, algorithms=[ALGORITHM])
        except Exception as exc:
            raise JWTError(f'Failed to decode JWT (unverified): {exc}') from exc

    @staticmethod
    def get_user_id(claims: Dict[str, Any]) -> Optional[int]:
        sub = claims.get(CLAIM_SUBJECT)
        if sub is None:
            return None
        try:
            return int(sub)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def get_token_id(claims: Dict[str, Any]) -> Optional[str]:
        return claims.get(CLAIM_TOKEN_ID)

    @staticmethod
    def get_token_kind(claims: Dict[str, Any]) -> Optional[str]:
        return claims.get(CLAIM_TOKEN_KIND)

    @staticmethod
    def get_user_type(claims: Dict[str, Any]) -> Optional[str]:
        return claims.get(CLAIM_USER_TYPE)

    @staticmethod
    def get_email(claims: Dict[str, Any]) -> Optional[str]:
        return claims.get(CLAIM_EMAIL)