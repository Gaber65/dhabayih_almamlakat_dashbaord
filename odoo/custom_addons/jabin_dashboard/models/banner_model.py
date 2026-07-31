from odoo import fields, models

class Banner(models.Model):
    _name = "banner"
    _description = "Banner"

    image = fields.Image(
        string="Banner Image",
        max_width=1920,
        max_height=800,
    )

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)