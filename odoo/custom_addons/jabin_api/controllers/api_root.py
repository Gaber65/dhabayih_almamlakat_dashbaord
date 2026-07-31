from __future__ import annotations
from typing import Any, Dict, List
try:
    from odoo import http
    _ODOO = True
except Exception:
    _ODOO = False
    http = None
from odoo.addons.jabin_core import ResponseBuilder
from .base import BaseApiController
if _ODOO:

    class ApiRootController(BaseApiController):
        PLATFORM_NAME: str = 'JABIN'
        API_VERSION: str = 'v1'
        PLATFORM_VERSION: str = '17.0.1.0.0'
        STATUS: str = 'online'
        RESOURCES: List[str] = []

        @http.route(['/api/v1/', '/api/v1'], methods=['GET'], type='http', auth='none', csrf=False)
        def api_root(self, **kwargs: Any):
            with self.handle() as ctx:
                data: Dict[str, Any] = {'platform': self.PLATFORM_NAME, 'api_version': self.API_VERSION, 'platform_version': self.PLATFORM_VERSION, 'status': self.STATUS, 'resources': list(self.RESOURCES)}
                ctx.set_body(ResponseBuilder.success(data=data, message='Welcome to the JABIN API'))
            return ctx.response
else:

    class ApiRootController(BaseApiController):
        PLATFORM_NAME: str = 'JABIN'
        API_VERSION: str = 'v1'
        RESOURCES: List[str] = []