from odoo import fields, models

class JabinOrderLine(models.Model):
    _inherit = "jabin.order.line"

    product_id = fields.Many2one(
        "jabin.product",
        string="Product",
        required=True,
        ondelete="restrict"
    )
    cutting_option_id = fields.Many2one(
        "jabin.cutting.option",
        string="Cutting Option",
        ondelete="restrict"
    )
    packaging_id = fields.Many2one(
        "jabin.packaging",
        string="Packaging Option",
        ondelete="restrict"
    )
    excluded_part_ids = fields.Many2many(
        "jabin.excluded.part",
        "jabin_order_line_excluded_part_rel",
        "order_line_id",
        "part_id",
        string="Excluded Parts"
    )
