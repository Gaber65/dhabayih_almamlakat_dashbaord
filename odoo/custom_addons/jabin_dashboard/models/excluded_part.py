from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class JabinExcludedPart(models.Model):
    _name = 'jabin.excluded.part'
    _description = 'JABIN Excluded Part'
    _order = 'name'

    name = fields.Char(string='Name', required=True, translate=True)
    description = fields.Text(string='Description', translate=True)
    active = fields.Boolean(string='Active', default=True)

    product_ids = fields.Many2many(
        'jabin.product',
        'jabin_product_excluded_rel',
        'excluded_id',
        'product_id',
        string='Products'
    )

    _sql_constraints = [
        ('unique_name', 'unique(name)', 'Excluded Part name must be unique!')
    ]
    @api.constrains('name')
    def _check_unique_name(self):
        for record in self:
            if self.search_count([
                ('name', '=', record.name),
                ('id', '!=', record.id)
            ]) > 0:
                raise ValidationError(_('Excluded Part name must be unique!'))