from __future__ import annotations

import contextlib
import json as _stdlib_json
from typing import Any, Dict, Optional
from odoo import http  # type: ignore
from odoo.http import request, Response

from odoo.addons.jabin_core import (ResponseBuilder, ExceptionMapper, JabinLogger, JsonHelper)


import base64


# ---------------------------------------------------------------------------
# Handler context object
# ---------------------------------------------------------------------------
class _HandlerContext:
    """Mutable context handed to controllers inside the ``handle`` block.

    It carries the envelope to serialise and builds the final
    :class:`odoo.http.Response` on exit. Keeping it as a small object (instead
    of returning tuples) lets controllers set the body, status, and meta in a
    readable, order-independent way.
    """

    __slots__ = ("_envelope", "_status", "_headers", "controller")

    def __init__(self, controller: "BaseApiController") -> None:
        self.controller = controller
        self._envelope: Dict[str, Any] = ResponseBuilder.success()
        self._status: int = 200
        self._headers: Dict[str, str] = {}

    # -- setters ------------------------------------------------------- #
    def set_body(self, envelope: Dict[str, Any], status: Optional[int] = None) -> None:
        """Set the response envelope and optionally override the HTTP status."""
        self._envelope = envelope
        if status is not None:
            self._status = status
        else:
            # Infer status from the envelope "code" field when present.
            self._status = int(envelope.get("code", 200))

    def set_status(self, status: int) -> None:
        self._status = status

    def add_header(self, name: str, value: str) -> None:
        self._headers[name] = value

    # -- properties ---------------------------------------------------- #
    @property
    def envelope(self) -> Dict[str, Any]:
        return self._envelope

    @property
    def status(self) -> int:
        return self._status

    @property
    def response(self):  # type: ignore[override]
        """Build and return the :class:`odoo.http.Response`."""
        return self.controller._build_response(
            self._envelope, self._status, self._headers
        )


# ---------------------------------------------------------------------------
# Base controller
# ---------------------------------------------------------------------------
class BaseApiController(http.Controller):
    """Foundation controller for every JABIN REST endpoint.

    Subclasses inherit the unified envelope, JSON serialisation, and
    exception handling without re-implementing them.
    """

    # Public API version prefix. Centralised so version bumps happen here.
    API_PREFIX: str = "/api/v1"

    # ------------------------------------------------------------------ #
    # Construction-time logger
    # ------------------------------------------------------------------ #
    @classmethod
    def _logger(cls):
        """Return a logger named after the controller class."""
        return JabinLogger.get(
            f"api.{cls.__name__}",
            context={"controller": cls.__name__},
        )

    # ------------------------------------------------------------------ #
    # JSON helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def parse_json_body() -> Dict[str, Any]:
        """Parse the JSON body of the current request.

        Returns an empty dict when the body is absent or not JSON. Callers
        validate the resulting dict with the validators package.
        """
        try:
            data = request.get_json_data()
        except Exception:
            data = None
        if data is None:
            return {}
        if isinstance(data, dict):
            return data
        if isinstance(data, (bytes, bytearray, str)):
            try:
                parsed = JsonHelper.loads(data)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}

    @classmethod
    def build_image_url(cls, model: str, record_id: int, field_name: str = "image", has_value: bool = True) -> Optional[str]:
        """Build relative URL path for public binary image endpoint."""
        if not record_id:
            return None
        return f"api/v1/image/{model}/{record_id}/{field_name}"

    @http.route(
        [
            "/api/v1/image/<string:model>/<int:record_id>/<string:field_name>",
            "/api/v1/image/<string:model>/<int:record_id>",
        ],
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_public_image(self, model: str, record_id: int, field_name: str = "image", **kwargs):
        """Serve binary images/media with sudo() so public API and mobile clients can view images without session restrictions."""
        try:
            if model not in request.env:
                return Response("Model not found", status=404)

            record = request.env[model].sudo().browse(record_id)
            if not record.exists():
                return Response("Record not found", status=404)

            if field_name not in record._fields:
                return Response("Field not found", status=404)

            raw_val = record[field_name]
            if not raw_val:
                return Response("No image content", status=404)

            if isinstance(raw_val, (bytes, bytearray)):
                image_data = base64.b64decode(raw_val)
            elif isinstance(raw_val, str):
                image_data = base64.b64decode(raw_val.encode("utf-8"))
            else:
                return Response("Invalid content", status=404)

            if not image_data:
                return Response("Empty image", status=404)

            mimetype = "image/jpeg"
            if image_data.startswith(b"\x89PNG\r\n\x1a\n"):
                mimetype = "image/png"
            elif image_data.startswith(b"GIF8"):
                mimetype = "image/gif"
            elif image_data.startswith(b"RIFF") and image_data[8:12] == b"WEBP":
                mimetype = "image/webp"
            elif image_data.startswith(b"\xff\xd8\xff"):
                mimetype = "image/jpeg"
            elif field_name == "video" or image_data.startswith(b"\x00\x00\x00") or b"ftyp" in image_data[:32]:
                mimetype = "video/mp4"

            headers = [
                ("Content-Type", mimetype),
                ("Content-Length", str(len(image_data))),
                ("Cache-Control", "public, max-age=86400"),
                ("Access-Control-Allow-Origin", "*"),
                ("Access-Control-Allow-Methods", "GET, OPTIONS"),
                ("Access-Control-Allow-Headers", "Content-Type, Authorization, Accept, Accept-Language, lang"),
            ]
            return Response(image_data, status=200, headers=headers)
        except Exception:
            return Response("Error loading image", status=500)

    # ------------------------------------------------------------------ #
    # Response building
    # ------------------------------------------------------------------ #
    @classmethod
    def _build_response(
            cls,
            envelope: Dict[str, Any],
            status: int,
            extra_headers: Optional[Dict[str, str]] = None,
    ):
        """Serialise ``envelope`` into an ``application/json`` Response.

        Uses :class:`JsonHelper` so ``Decimal`` / ``datetime`` / ``Enum``
        values are handled correctly.
        """
        body = JsonHelper.dumps(envelope)
        headers = {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, Accept, Accept-Language, lang",
        }
        if extra_headers:
            headers.update(extra_headers)
        return Response(body, status=status, headers=headers)

    @classmethod
    def _respond(
            cls,
            envelope: Dict[str, Any],
            status: Optional[int] = None,
            extra_headers: Optional[Dict[str, str]] = None,
    ):
        """Convenience wrapper: serialise an envelope into a Response.

        The HTTP status is inferred from ``envelope["code"]`` unless
        ``status`` is explicitly provided.
        """
        if status is None:
            status = int(envelope.get("code", 200))
        return cls._build_response(envelope, status, extra_headers)

    # ------------------------------------------------------------------ #
    # Exception-handling context manager
    # ------------------------------------------------------------------ #
    @classmethod
    @contextlib.contextmanager
    def handle(cls):
        """Context manager that catches exceptions and maps them.

        Usage::

            @http.route(...)
            def my_endpoint(self, **kw):
                with self.handle() as ctx:
                    ctx.set_body(ResponseBuilder.success(data=...))
                return ctx.response

        If the block raises, the exception is converted into an error
        envelope via :class:`ExceptionMapper` and the response is built
        from that envelope. The stack trace is logged but never sent to
        the client.
        """
        ctx = _HandlerContext(cls)  # type: ignore[arg-type]
        logger = cls._logger()
        try:
            yield ctx
        except Exception as exc:  # noqa: BLE001 - intentional broad catch
            envelope, code = ExceptionMapper.handle(
                exc,
                logger=logger,
                context={"endpoint": getattr(request, "httprequest", None)
                                     and request.httprequest.path},
            )
            ctx.set_body(envelope, status=code)
        # The caller reads ctx.response after the block.

    # ------------------------------------------------------------------ #
    # Auth placeholders (wired in a later sprint)
    # ------------------------------------------------------------------ #
    @classmethod
    def _current_user(cls):
        """Return the current authenticated user (placeholder).

        Sprint 1 returns ``None`` because no auth is implemented yet.
        The JWT sprint will override this to resolve the user from the
        bearer token.
        """
        return None