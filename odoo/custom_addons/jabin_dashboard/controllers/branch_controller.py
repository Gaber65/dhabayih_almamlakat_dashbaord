from odoo import http, _
from odoo.http import request
from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder


class BranchController(BaseApiController):
    """Store Branch REST API Controller."""

    @http.route(
        "/api/v1/branches",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def list_branches(self, **kwargs):
        """List active store branches for pickup."""
        with self.handle() as ctx:
            branches = request.env["jabin.branch"].sudo().search([("active", "=", True)], order="name")
            res = []
            for b in branches:
                res.append({
                    "id": b.id,
                    "name": b.name,
                    "code": b.code,
                    "address": b.address,
                    "city": b.city,
                    "phone": b.phone,
                    "latitude": b.latitude,
                    "longitude": b.longitude,
                    "opening_hours": b.opening_hours,
                })
            ctx.set_body(ResponseBuilder.success(data=res, message=_("Branches retrieved successfully.")))
        return ctx.response
