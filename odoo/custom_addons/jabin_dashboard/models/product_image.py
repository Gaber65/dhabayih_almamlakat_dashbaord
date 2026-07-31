from odoo import api, fields, models


class JabinProductImage(models.Model):
    _name = 'jabin.product.image'
    _description = 'JABIN Product Image'
    _order = 'sequence, id'

    product_id = fields.Many2one(
        'jabin.product',
        string='Product',
        required=True,
        ondelete='cascade'
    )
    image = fields.Binary(string='Image', attachment=True, required=True)
    sequence = fields.Integer(string='Sequence', default=10)