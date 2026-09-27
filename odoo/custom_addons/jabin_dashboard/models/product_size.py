from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class JabinProductSize(models.Model):
    _name = 'jabin.product.size'
    _description = 'Dhabayih Carcass Product Size'
    _order = 'sequence, id'

    product_id = fields.Many2one(
        'jabin.product',
        string='Product',
        required=True,
        ondelete='cascade',
        index=True
    )
    name = fields.Char(
        string='Size Name',
        required=True,
        translate=True,
        help='Name of the carcass size (e.g. هرفي, جذع وسط)'
    )
    sub_title = fields.Char(
        string='Subtitle / Note',
        translate=True,
        help='Additional note or qualification (e.g. يجزئ عقيقة)'
    )
    price = fields.Float(
        string='Price',
        required=True,
        digits='Product Price',
        help='Selling price for this specific size'
    )
    calories = fields.Integer(
        string='Calories',
        default=243,
        help='Calories per serving / carcass'
    )
    loyalty_points = fields.Float(
        string='Loyalty Points',
        compute='_compute_loyalty_points',
        store=True,
        help='Loyalty points earned when purchasing this size'
    )
    points_price = fields.Integer(
        string='Price in Points',
        compute='_compute_points_price',
        store=True,
        help='Cost in points to purchase this size using loyalty points'
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    is_default = fields.Boolean(
        string='Is Default',
        default=False
    )
    active = fields.Boolean(
        string='Active',
        default=True
    )

    @api.depends('price')
    def _compute_loyalty_points(self):
        earning_rate = float(
            self.env['ir.config_parameter'].sudo().get_param('jabin_loyalty.earning_rate', '0.5')
        )
        for record in self:
            record.loyalty_points = round(record.price * earning_rate, 2)

    @api.depends('price')
    def _compute_points_price(self):
        redemption_rate = float(
            self.env['ir.config_parameter'].sudo().get_param('jabin_loyalty.redemption_rate', '4.0')
        )
        for record in self:
            record.points_price = int(record.price * redemption_rate)

    @api.constrains('price')
    def _check_price(self):
        for record in self:
            if record.price < 0:
                raise ValidationError(_("Price for size '%s' cannot be negative.") % record.name)
