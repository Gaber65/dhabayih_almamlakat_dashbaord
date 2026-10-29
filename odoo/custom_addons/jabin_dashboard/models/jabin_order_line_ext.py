from odoo import api, fields, models


class JabinOrderLine(models.Model):
    _inherit = "jabin.order.line"

    product_id = fields.Many2one(
        "jabin.product",
        string="Product",
        required=False,
        ondelete="restrict"
    )
    cutting_option_id = fields.Many2one(
        "jabin.cutting.option",
        string="Cutting Option",
        ondelete="set null"
    )
    cutting_option_name = fields.Char(
        string="Cutting Option Snapshot"
    )
    cutting_price = fields.Float(
        string="Cutting Fee Snapshot",
        digits="Product Price",
        default=0.0
    )
    packaging_id = fields.Many2one(
        "jabin.packaging",
        string="Packaging Option",
        ondelete="set null"
    )
    packaging_ids = fields.Many2many(
        "jabin.packaging",
        "jabin_order_line_packaging_rel",
        "order_line_id",
        "packaging_id",
        string="Packaging Options"
    )
    packaging_name = fields.Char(
        string="Packaging Snapshot"
    )
    packaging_price = fields.Float(
        string="Packaging Fee Snapshot",
        digits="Product Price",
        default=0.0
    )
    excluded_part_ids = fields.Many2many(
        "jabin.excluded.part",
        "jabin_order_line_excluded_part_rel",
        "order_line_id",
        "part_id",
        string="Excluded Parts"
    )
    size_id = fields.Many2one(
        "jabin.product.size",
        string="Size",
        ondelete="set null"
    )
    size_name = fields.Char(
        string="Size Name Snapshot"
    )
    size_price = fields.Float(
        string="Size Price Snapshot",
        digits="Product Price",
        default=0.0
    )

    @api.depends("price_unit", "quantity", "discount", "cutting_price", "packaging_price")
    def _compute_subtotal(self):
        for line in self:
            base = line.price_unit * line.quantity
            line.discount_amount = base * (line.discount / 100.0)
            options_extra = (float(line.cutting_price or 0.0) + float(line.packaging_price or 0.0)) * line.quantity
            line.price_subtotal = (base - line.discount_amount) + options_extra
