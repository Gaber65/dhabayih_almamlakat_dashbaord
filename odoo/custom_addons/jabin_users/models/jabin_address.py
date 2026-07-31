from odoo import api, fields, models

class JabinUserAddress(models.Model):
    _name = "res.users.address"
    _description = "JABIN User Address"

    user_id = fields.Many2one(
        "res.users",
        required=True,
        ondelete="cascade",
    )

    title = fields.Char(required=True)              # Home, Office, etc.
    recipient_name = fields.Char(required=True)
    recipient_phone = fields.Char()

    country_id = fields.Many2one(
        "res.country",
        required=True,
    )

    city = fields.Char(required=True)
    street = fields.Char(required=True)

    latitude = fields.Float()
    longitude = fields.Float()

    is_default = fields.Boolean(default=False)

    @api.model_create_multi
    def create(self, vals_list):
        addresses = super().create(vals_list)
        for addr in addresses:
            addr.user_id.log_activity("changed_address", related_record=f"res.users.address,{addr.id}")
        return addresses

    def write(self, vals):
        res = super().write(vals)
        for addr in self:
            addr.user_id.log_activity("changed_address", related_record=f"res.users.address,{addr.id}")
        return res