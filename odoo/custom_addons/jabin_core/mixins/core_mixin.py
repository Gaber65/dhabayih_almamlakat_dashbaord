from odoo import models


class JabinCoreMixin(models.AbstractModel):
    _name = "jabin.core.mixin"
    _description = "JABIN Core Mixin"

    _inherit = [
        "jabin.soft.delete.mixin",
        "jabin.timestamp.mixin",
        "jabin.audit.mixin",
        "jabin.active.mixin",
    ]