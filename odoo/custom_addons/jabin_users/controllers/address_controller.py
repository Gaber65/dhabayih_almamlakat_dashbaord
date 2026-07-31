import json
from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError
from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder
from odoo.addons.jabin_security.utils.token_auth import require_token
from odoo.addons.jabin_security import SecurityContext


def _get_auth_user_id() -> int:
    try:
        raw_header = request.httprequest.headers.get("Authorization", "")
        if raw_header:
            parts = raw_header.split(None, 1)
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                token = parts[1].strip()
                from odoo.addons.jabin_security.utils.jwt_utils import JWTUtils
                claims = JWTUtils.decode_token(token)
                uid = JWTUtils.get_user_id(claims)
                if uid:
                    return uid
    except Exception:
        pass
    return request.env.user.id


def _parse_json_body():
    raw = request.httprequest.data
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise ValidationError(_("Invalid JSON payload."))


class AddressController(BaseApiController):
    """Customer Address REST API Controller."""

    @http.route(
        "/api/v1/addresses",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def list_addresses(self, **kwargs):
        """List addresses for the logged-in customer."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id()
        with self.handle() as ctx:
            addresses = request.env["res.users.address"].sudo().search([("user_id", "=", user_id)], order="is_default desc, id desc")
            res = []
            for addr in addresses:
                res.append({
                    "id": addr.id,
                    "title": addr.title,
                    "recipient_name": addr.recipient_name,
                    "recipient_phone": addr.recipient_phone,
                    "country_id": addr.country_id.id,
                    "country_name": addr.country_id.name,
                    "city": addr.city,
                    "street": addr.street,
                    "latitude": addr.latitude,
                    "longitude": addr.longitude,
                    "is_default": addr.is_default,
                })
            ctx.set_body(ResponseBuilder.success(data=res, message=_("Addresses retrieved successfully.")))
        return ctx.response

    @http.route(
        "/api/v1/addresses",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def create_address(self, **kwargs):
        """Create a new delivery address for the logged-in customer."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id()
        with self.handle() as ctx:
            data = _parse_json_body()
            title = data.get("title") or "Home"
            recipient_name = data.get("recipient_name")
            country_id = data.get("country_id")
            city = data.get("city")
            street = data.get("street")

            if not recipient_name or not city or not street:
                raise ValidationError(_("recipient_name, city, and street are required."))

            if not country_id:
                default_country = request.env["res.country"].sudo().search([("code", "=", "SA")], limit=1)
                country_id = default_country.id if default_country else 1

            is_default = bool(data.get("is_default", False))
            if is_default:
                # Unset previous defaults
                existing_defaults = request.env["res.users.address"].sudo().search([("user_id", "=", user_id), ("is_default", "=", True)])
                existing_defaults.write({"is_default": False})

            addr = request.env["res.users.address"].sudo().create({
                "user_id": user_id,
                "title": title,
                "recipient_name": recipient_name,
                "recipient_phone": data.get("recipient_phone"),
                "country_id": int(country_id),
                "city": city,
                "street": street,
                "latitude": float(data.get("latitude", 0.0)),
                "longitude": float(data.get("longitude", 0.0)),
                "is_default": is_default,
            })

            ctx.set_body(ResponseBuilder.success(data={
                "id": addr.id,
                "title": addr.title,
                "recipient_name": addr.recipient_name,
                "recipient_phone": addr.recipient_phone,
                "country_id": addr.country_id.id,
                "country_name": addr.country_id.name,
                "city": addr.city,
                "street": addr.street,
                "latitude": addr.latitude,
                "longitude": addr.longitude,
                "is_default": addr.is_default,
            }, message=_("Address created successfully."), code=201))
        return ctx.response

    @http.route(
        "/api/v1/addresses/<int:address_id>",
        type="http",
        auth="public",
        methods=["PUT"],
        csrf=False,
    )
    def update_address(self, address_id: int, **kwargs):
        """Update an existing address for the logged-in customer."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id()
        with self.handle() as ctx:
            addr = request.env["res.users.address"].sudo().browse(address_id)
            if not addr.exists() or addr.user_id.id != user_id:
                raise ValidationError(_("Address not found."))

            data = _parse_json_body()
            vals = {}
            for k in ["title", "recipient_name", "recipient_phone", "city", "street"]:
                if k in data:
                    vals[k] = data[k]
            if "country_id" in data:
                vals["country_id"] = int(data["country_id"])
            if "latitude" in data:
                vals["latitude"] = float(data["latitude"])
            if "longitude" in data:
                vals["longitude"] = float(data["longitude"])
            if "is_default" in data and bool(data["is_default"]):
                request.env["res.users.address"].sudo().search([("user_id", "=", user_id), ("is_default", "=", True)]).write({"is_default": False})
                vals["is_default"] = True

            addr.write(vals)
            ctx.set_body(ResponseBuilder.success(data={
                "id": addr.id,
                "title": addr.title,
                "recipient_name": addr.recipient_name,
                "recipient_phone": addr.recipient_phone,
                "country_id": addr.country_id.id,
                "country_name": addr.country_id.name,
                "city": addr.city,
                "street": addr.street,
                "latitude": addr.latitude,
                "longitude": addr.longitude,
                "is_default": addr.is_default,
            }, message=_("Address updated successfully.")))
        return ctx.response

    @http.route(
        "/api/v1/addresses/<int:address_id>",
        type="http",
        auth="public",
        methods=["DELETE"],
        csrf=False,
    )
    def delete_address(self, address_id: int, **kwargs):
        """Delete an address."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id()
        with self.handle() as ctx:
            addr = request.env["res.users.address"].sudo().browse(address_id)
            if not addr.exists() or addr.user_id.id != user_id:
                raise ValidationError(_("Address not found."))

            addr.unlink()
            ctx.set_body(ResponseBuilder.success(message=_("Address deleted successfully.")))
        return ctx.response

    @http.route(
        "/api/v1/addresses/<int:address_id>/set-default",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def set_default_address(self, address_id: int, **kwargs):
        """Set an address as default."""
        denied = require_token()
        if denied:
            return denied

        user_id = _get_auth_user_id()
        with self.handle() as ctx:
            addr = request.env["res.users.address"].sudo().browse(address_id)
            if not addr.exists() or addr.user_id.id != user_id:
                raise ValidationError(_("Address not found."))

            request.env["res.users.address"].sudo().search([("user_id", "=", user_id), ("is_default", "=", True)]).write({"is_default": False})
            addr.write({"is_default": True})
            ctx.set_body(ResponseBuilder.success(data={"id": addr.id, "is_default": True}, message=_("Default address updated.")))
        return ctx.response
