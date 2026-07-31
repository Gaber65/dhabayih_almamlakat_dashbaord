from odoo import http, _
from odoo.http import request
from odoo.addons.web.controllers.main import ensure_db
from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder
from odoo.addons.jabin_security.utils.token_auth import require_token
from odoo.addons.jabin_security.decorators.permission_required import permission_required


class DashboardController(BaseApiController):

    @http.route(
        ["/api/v1/dashboard/stats", "/jabin_dashboard/data"],
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
    )
    @permission_required("audit.read")
    def get_dashboard_data(self, **kwargs):
        """Get all dashboard data stats (Admin API)."""
        denied = require_token()
        if denied:
            return denied

        ensure_db()
        with self.handle() as ctx:
            service = request.env['jabin.dashboard.service'].sudo()
            data = service.get_dashboard_data()
            ctx.set_body(ResponseBuilder.success(data=data, message=_("Dashboard loaded successfully")))

        return ctx.response