from odoo import api, fields, models


class JabinBranch(models.Model):
    _name = "jabin.branch"
    _description = "JABIN Store Branch"
    _order = "name"

    name = fields.Char(string="Branch Name", required=True, translate=True)
    code = fields.Char(string="Branch Code", index=True)
    address = fields.Char(string="Address", required=True)
    city = fields.Char(string="City", required=True)
    phone = fields.Char(string="Contact Phone")
    latitude = fields.Float(string="Latitude")
    longitude = fields.Float(string="Longitude")
    opening_hours = fields.Char(string="Opening Hours", default="08:00 AM - 11:00 PM")
    active = fields.Boolean(string="Active", default=True)
