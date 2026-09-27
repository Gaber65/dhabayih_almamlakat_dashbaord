import json
from typing import Dict, Any
from odoo import http, _
from odoo.http import request
from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder
from odoo.addons.jabin_security.utils.token_auth import require_token
from odoo.addons.jabin_security.decorators.permission_required import permission_required


def _parse_branch_data() -> Dict[str, Any]:
    content_type = request.httprequest.content_type or ""
    vals = {}
    if "multipart/form-data" in content_type:
        vals = {
            k: v
            for k, v in request.httprequest.form.items()
            if k not in ["id"]
        }
        if "active" in vals:
            vals["active"] = vals["active"].lower() not in ("false", "0", "no")
    else:
        raw = request.httprequest.data
        if raw:
            try:
                vals = json.loads(raw)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON payload.")
        vals.pop("id", None)

    if "is_active" in vals:
        vals["active"] = bool(vals.pop("is_active"))
    return vals


def _serialize_branch(b):
    return {
        "id": b.id,
        "name": b.name,
        "code": b.code or "",
        "address": b.address or "",
        "city": b.city or "",
        "phone": b.phone or "",
        "latitude": b.latitude or 0.0,
        "longitude": b.longitude or 0.0,
        "opening_hours": b.opening_hours or "",
        "active": b.active,
        "is_active": b.active,
    }


class BranchController(BaseApiController):
    """Store Branch REST API Controller."""

    @http.route(
        "/api/v1/branches",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        cors="*",
    )
    def list_branches(self, **kwargs):
        """List active store branches for pickup or admin management."""
        with self.handle() as ctx:
            all_param = kwargs.get("all") or kwargs.get("include_inactive")
            if all_param and str(all_param).lower() in ("true", "1", "yes"):
                domain = []
            else:
                domain = [("active", "=", True)]

            branches = request.env["jabin.branch"].sudo().search(domain, order="name")
            res = [_serialize_branch(b) for b in branches]
            ctx.set_body(ResponseBuilder.success(data=res, message=_("Branches retrieved successfully.")))
        return ctx.response

    @http.route(
        "/api/v1/branches/<int:branch_id>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        cors="*",
    )
    def get_branch(self, branch_id, **kwargs):
        """Get branch detail by ID."""
        with self.handle() as ctx:
            branch = request.env["jabin.branch"].sudo().browse(branch_id)
            if not branch.exists():
                ctx.set_body(ResponseBuilder.not_found(message=_("Branch not found.")))
                return ctx.response
            ctx.set_body(ResponseBuilder.success(data=_serialize_branch(branch), message=_("Branch retrieved successfully.")))
        return ctx.response

    @http.route(
        "/api/v1/branches",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    @permission_required("catalog.manage")
    def create_branch(self, **kwargs):
        """Create a new branch."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            vals = _parse_branch_data()
            if not vals.get("name") or not vals.get("address") or not vals.get("city"):
                ctx.set_body(ResponseBuilder.bad_request(message=_("Name, address, and city are required fields.")))
                return ctx.response

            branch_vals = {
                "name": str(vals.get("name")).strip(),
                "address": str(vals.get("address")).strip(),
                "city": str(vals.get("city")).strip(),
            }
            if "code" in vals:
                branch_vals["code"] = str(vals.get("code") or "").strip()
            if "phone" in vals:
                branch_vals["phone"] = str(vals.get("phone") or "").strip()
            if "opening_hours" in vals:
                branch_vals["opening_hours"] = str(vals.get("opening_hours") or "").strip()
            if "latitude" in vals and vals.get("latitude") is not None:
                try:
                    branch_vals["latitude"] = float(vals.get("latitude"))
                except (ValueError, TypeError):
                    pass
            if "longitude" in vals and vals.get("longitude") is not None:
                try:
                    branch_vals["longitude"] = float(vals.get("longitude"))
                except (ValueError, TypeError):
                    pass
            if "active" in vals:
                branch_vals["active"] = bool(vals.get("active"))

            branch = request.env["jabin.branch"].sudo().create(branch_vals)
            ctx.set_body(
                ResponseBuilder.success(
                    data=_serialize_branch(branch),
                    message=_("Branch created successfully."),
                    code=201,
                )
            )
        return ctx.response

    @http.route(
        "/api/v1/branches/<int:branch_id>",
        type="http",
        auth="public",
        methods=["PUT"],
        csrf=False,
        cors="*",
    )
    @permission_required("catalog.manage")
    def update_branch(self, branch_id, **kwargs):
        """Update an existing branch."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            branch = request.env["jabin.branch"].sudo().browse(branch_id)
            if not branch.exists():
                ctx.set_body(ResponseBuilder.not_found(message=_("Branch not found.")))
                return ctx.response

            vals = _parse_branch_data()
            update_vals = {}
            if "name" in vals:
                update_vals["name"] = str(vals["name"]).strip()
            if "address" in vals:
                update_vals["address"] = str(vals["address"]).strip()
            if "city" in vals:
                update_vals["city"] = str(vals["city"]).strip()
            if "code" in vals:
                update_vals["code"] = str(vals["code"] or "").strip()
            if "phone" in vals:
                update_vals["phone"] = str(vals["phone"] or "").strip()
            if "opening_hours" in vals:
                update_vals["opening_hours"] = str(vals["opening_hours"] or "").strip()
            if "latitude" in vals:
                try:
                    update_vals["latitude"] = float(vals["latitude"])
                except (ValueError, TypeError):
                    pass
            if "longitude" in vals:
                try:
                    update_vals["longitude"] = float(vals["longitude"])
                except (ValueError, TypeError):
                    pass
            if "active" in vals:
                update_vals["active"] = bool(vals["active"])

            if update_vals:
                branch.write(update_vals)

            ctx.set_body(
                ResponseBuilder.success(
                    data=_serialize_branch(branch),
                    message=_("Branch updated successfully."),
                )
            )
        return ctx.response

    @http.route(
        "/api/v1/branches/<int:branch_id>",
        type="http",
        auth="public",
        methods=["DELETE"],
        csrf=False,
        cors="*",
    )
    @permission_required("catalog.manage")
    def delete_branch(self, branch_id, **kwargs):
        """Delete an existing branch."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            branch = request.env["jabin.branch"].sudo().browse(branch_id)
            if not branch.exists():
                ctx.set_body(ResponseBuilder.not_found(message=_("Branch not found.")))
                return ctx.response

            branch.unlink()
            ctx.set_body(ResponseBuilder.success(message=_("Branch deleted successfully.")))
        return ctx.response
