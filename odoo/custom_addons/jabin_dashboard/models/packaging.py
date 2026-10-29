from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class JabinPackaging(models.Model):
    _name = 'jabin.packaging'
    _description = 'Dhabayih Lmamlaka Packaging'
    _order = 'name'

    name = fields.Char(string='Name', required=True, translate=True)
    description = fields.Text(string='Description', translate=True)
    extra_price = fields.Float(
        string='Extra Price',
        default=0.0,
        digits='Product Price',
        help='Additional packaging cost per complete product unit',
    )
    active = fields.Boolean(string='Active', default=True)

    product_ids = fields.Many2many(
        'jabin.product',
        'jabin_product_packaging_rel',
        'packaging_id',
        'product_id',
        string='Products'
    )
    _sql_constraints = [
        ('unique_name', 'UNIQUE(name)', 'Packaging name must be unique!'),
    ]

    @api.constrains('name')
    def _check_unique_name(self):
        for record in self:
            if self.search_count([
                ('name', '=', record.name),
                ('id', '!=', record.id)
            ]) > 0:
                raise ValidationError(_('Packaging name must be unique!'))
