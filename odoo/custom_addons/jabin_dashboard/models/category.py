from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class JabinCategory(models.Model):
    _name = 'jabin.category'
    _description = 'JABIN Category'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True, translate=True)
    image = fields.Binary(string='Image', attachment=True)
    description = fields.Text(string='Description', translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    product_ids = fields.One2many(
        'jabin.product',
        'category_id',
        string='Products'
    )
    product_count = fields.Integer(
        string='Product Count',
        compute='_compute_product_count',
        store=True
    )

    @api.depends('product_ids')
    def _compute_product_count(self):
        for record in self:
            record.product_count = len(record.product_ids)

    @api.constrains('name')
    def _check_unique_name(self):
        for record in self:
            if self.search_count([
                ('name', '=', record.name),
                ('id', '!=', record.id)
            ]) > 0:
                raise ValidationError(_('Category name must be unique!'))

    def unlink(self):
        for record in self:
            if record.product_ids:
                raise ValidationError(
                    _('Cannot delete category with existing products!')
                )
        return super(JabinCategory, self).unlink()

    def name_get(self):
        result = []
        for record in self:
            name = record.name
            if record.active:
                name = f"{name} (Active)"
            else:
                name = f"{name} (Inactive)"
            result.append((record.id, name))
        return result