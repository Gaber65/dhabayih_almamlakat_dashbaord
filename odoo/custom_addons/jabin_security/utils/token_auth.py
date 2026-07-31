"""
jabin_security/utils/token_auth.py
------------------------------------
Lightweight helper used by controllers that stay on auth='public'.

Usage inside any controller method::

    from odoo.addons.jabin_security.utils.token_auth import require_token

    @http.route('/api/...', type='http', auth='public', methods=['POST'], csrf=False)
    def my_write_endpoint(self, **kw):
        denied = require_token()
        if denied:
            return denied
        # … safe to proceed …

`require_token` returns:
  - ``None``          when the token is present and valid (caller continues).
  - An HTTP Response  (401 JSON) when the token is missing or invalid.

GET endpoints must NOT call this helper.
"""
from __future__ import annotations

import json
from typing import Optional

from odoo.http import request, Response

from odoo.addons.jabin_security.utils.jwt_utils import JWTError, JWTUtils


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_bearer(raw_header: str) -> str:
    """Return the token string from 'Bearer <token>', or ''."""
    if not raw_header:
        return ""
    parts = raw_header.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return ""


def _unauthorized(message: str) -> Response:
    """Build a 401 JSON response matching the project's envelope format."""
    body = json.dumps({
        "success": False,
        "message": message,
        "code": 401,
        "data": None,
        "meta": {},
        "errors": [{"field": "Authorization", "message": message}],
    })
    return Response(
        body,
        status=401,
        headers={"Content-Type": "application/json"},
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def require_token() -> Optional[Response]:
    """
    Validate the Bearer token on the current request.

    Returns ``None`` if the token is valid (caller should proceed).
    Returns a ``401`` :class:`odoo.http.Response` if the token is missing,
    malformed, expired, or of the wrong kind.

    Only call this from write endpoints (POST / PUT / PATCH / DELETE).
    GET endpoints must remain fully public.
    """
    try:
        raw_header = request.httprequest.headers.get("Authorization", "")
    except Exception:
        raw_header = ""

    token = _extract_bearer(raw_header)

    if not token:
        return _unauthorized("Unauthorized")

    try:
        claims = JWTUtils.decode_token(token)
    except JWTError:
        return _unauthorized("Unauthorized")

    # Only access tokens are accepted for API write operations.
    if JWTUtils.get_token_kind(claims) != "access":
        return _unauthorized("Unauthorized")

    # Verify the referenced user still exists.
    user_id = JWTUtils.get_user_id(claims)
    if user_id is None:
        return _unauthorized("Unauthorized")

    try:
        user = request.env["res.users"].sudo().browse(user_id)  # Changed from res.users
        if not user.exists():
            return _unauthorized("Unauthorized")
    except Exception:
        return _unauthorized("Unauthorized")

    # All checks passed — let the caller continue.
    return None