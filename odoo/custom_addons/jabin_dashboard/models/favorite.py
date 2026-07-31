from odoo import api, fields, models, _


class JabinFavorite(models.Model):
    _name = "jabin.favorite"
    _description = "JABIN Customer Favorite Product"
    _order = "created_date desc, id desc"

    customer_id = fields.Many2one(
        "res.users",
        string="Customer",
        required=True,
        ondelete="cascade",
        index=True
    )
    product_id = fields.Many2one(
        "jabin.product",
        string="Product",
        required=True,
        ondelete="cascade",
        index=True
    )
    created_date = fields.Datetime(
        string="Created Date",
        default=fields.Datetime.now,
        required=True
    )

    _sql_constraints = [
        ("customer_product_unique", "unique(customer_id, product_id)", "Product is already in customer favorites.")
    ]
