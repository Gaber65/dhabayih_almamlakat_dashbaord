from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import datetime


class JabinProduct(models.Model):
    _name = 'jabin.product'
    _description = 'Dhabayih Lmamlaka Product'
    _order = 'name'

    # Basic Information
    category_id = fields.Many2one(
        'jabin.category',
        string='Category',
        required=True,

    )
    name = fields.Char(string='Name', required=True, translate=True, )
    description = fields.Text(string='Description', translate=True)
    sku = fields.Char(string='SKU', required=True, )
    barcode = fields.Char(string='Barcode', )
    _sql_constraints = [
        ('unique_sku', 'unique(sku)', 'SKU must be unique!'),
    ]
    # Pricing
    purchase_price = fields.Float(
        string='Purchase Price',
        required=True,

        digits='Product Price'
    )
    selling_price = fields.Float(
        string='Selling Price',
        required=True,

        digits='Product Price'
    )

    # Offer
    discount_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount')
    ], string='Discount Type', default='percentage')
    discount_value = fields.Float(
        string='Discount Value',
        default=0.0,
        digits='Product Price'
    )
    offer_price = fields.Float(
        string='Offer Price',
        compute='_compute_offer_price',
        store=True,
        digits='Product Price'
    )
    offer_start_date = fields.Date(string='Offer Start Date')
    offer_end_date = fields.Date(string='Offer End Date')
    offer_ids = fields.Many2many(
        'jabin.offer',
        'jabin_offer_product_rel',
        'product_id',
        'offer_id',
        string='Promotional Offers'
    )
    is_on_offer = fields.Boolean(
        string='Is On Offer',
        compute='_compute_is_on_offer',
        store=True
    )

    # Profit
    profit = fields.Float(
        string='Profit',
        compute='_compute_profit',
        store=True,
        digits='Product Price'
    )
    offer_profit = fields.Float(
        string='Offer Profit',
        compute='_compute_offer_profit',
        store=True,
        digits='Product Price'
    )
    profit_percentage = fields.Float(
        string='Profit Percentage',
        compute='_compute_profit_percentage',
        store=True
    )

    # Stock
    stock_quantity = fields.Float(
        string='Stock Quantity',
        default=0.0,

    )
    minimum_stock = fields.Float(
        string='Minimum Stock',
        default=0.0
    )

    # Product Details
    weight = fields.Float(string='Weight (kg)')
    preparation_time = fields.Float(string='Preparation Time (minutes)')

    # Media
    main_image = fields.Binary(string='Main Image', attachment=True)

    # Status
    active = fields.Boolean(string='Active', default=True, )
    is_available = fields.Boolean(
        string='Is Available',
        compute='_compute_is_available',
        store=True
    )
    is_featured = fields.Boolean(string='Is Featured', default=False)
    is_best_seller = fields.Boolean(string='Is Best Seller', default=False)

    # Relationships
    cutting_option_ids = fields.Many2many(
        'jabin.cutting.option',
        'jabin_product_cutting_rel',
        'product_id',
        'cutting_id',
        string='Cutting Options'
    )
    packaging_ids = fields.Many2many(
        'jabin.packaging',
        'jabin_product_packaging_rel',
        'product_id',
        'packaging_id',
        string='Packaging Options'
    )
    excluded_part_ids = fields.Many2many(
        'jabin.excluded.part',
        'jabin_product_excluded_rel',
        'product_id',
        'excluded_id',
        string='Excluded Parts'
    )
    product_image_ids = fields.One2many(
        'jabin.product.image',
        'product_id',
        string='Product Images'
    )

    # Constraints
    @api.constrains('sku')
    def _check_unique_sku(self):
        for record in self:
            if self.search_count([
                ('sku', '=', record.sku),
                ('id', '!=', record.id)
            ]) > 0:
                raise ValidationError(_('SKU must be unique!'))

    @api.constrains('barcode')
    def _check_unique_barcode(self):
        for record in self:
            if record.barcode:
                if self.search_count([
                    ('barcode', '=', record.barcode),
                    ('id', '!=', record.id)
                ]) > 0:
                    raise ValidationError(_('Barcode must be unique!'))

    @api.constrains('selling_price', 'purchase_price')
    def _check_positive_prices(self):
        for record in self:
            if record.selling_price < 0:
                raise ValidationError(_('Selling Price cannot be negative!'))
            if record.purchase_price < 0:
                raise ValidationError(_('Purchase Price cannot be negative!'))

    @api.constrains('stock_quantity', 'minimum_stock')
    def _check_positive_stock(self):
        for record in self:
            if record.stock_quantity < 0:
                raise ValidationError(_('Stock Quantity cannot be negative!'))
            if record.minimum_stock < 0:
                raise ValidationError(_('Minimum Stock cannot be negative!'))

    # Computed Fields
    @api.depends('selling_price', 'discount_type', 'discount_value', 'offer_ids', 'offer_ids.discount_type', 'offer_ids.discount_value', 'offer_ids.active', 'offer_ids.start_date', 'offer_ids.end_date')
    def _compute_offer_price(self):
        today = fields.Date.context_today(self)
        for record in self:
            best_price = record.selling_price

            # 1. Check individual offer
            has_individual = bool(record.discount_value > 0 and (not record.offer_start_date or record.offer_start_date <= today) and (not record.offer_end_date or record.offer_end_date >= today))
            if has_individual:
                if record.discount_type == 'percentage':
                    best_price = record.selling_price - (record.selling_price * record.discount_value / 100.0)
                else:
                    best_price = record.selling_price - record.discount_value

            # 2. Check group promotional offers
            for offer in record.offer_ids:
                if offer.is_currently_active:
                    offer_calc = offer.calculate_discounted_price(record.selling_price)
                    if offer_calc < best_price:
                        best_price = offer_calc

            record.offer_price = max(0.0, round(best_price, 2))

    @api.depends('offer_start_date', 'offer_end_date', 'discount_value', 'offer_ids', 'offer_ids.active', 'offer_ids.start_date', 'offer_ids.end_date')
    def _compute_is_on_offer(self):
        today = fields.Date.context_today(self)
        for record in self:
            individual_active = bool(
                record.discount_value > 0 and
                (not record.offer_start_date or record.offer_start_date <= today) and
                (not record.offer_end_date or record.offer_end_date >= today)
            )
            group_active = any(o.is_currently_active for o in record.offer_ids)
            record.is_on_offer = individual_active or group_active

    @api.depends('selling_price', 'purchase_price')
    def _compute_profit(self):
        for record in self:
            record.profit = record.selling_price - record.purchase_price

    @api.depends('offer_price', 'purchase_price')
    def _compute_offer_profit(self):
        for record in self:
            record.offer_profit = record.offer_price - record.purchase_price

    @api.depends('selling_price', 'purchase_price')
    def _compute_profit_percentage(self):
        for record in self:
            if record.purchase_price > 0:
                record.profit_percentage = (
                        (record.selling_price - record.purchase_price) /
                        record.purchase_price * 100
                )
            else:
                record.profit_percentage = 0.0

    @api.depends('stock_quantity')
    def _compute_is_available(self):
        for record in self:
            record.is_available = record.stock_quantity > 0

    @api.model_create_multi
    def create(self, vals_list):
        records = super(JabinProduct, self).create(vals_list)
        for record in records:
            if record.active:
                try:
                    self.env["jabin.notification.service"].sudo().send_new_product(self.env, record)
                except Exception:
                    pass
        return records

    def action_activate(self):
        self.active = True

    def action_deactivate(self):
        self.active = False

    def action_update_stock(self):
        # Open wizard for stock update
        return {
            'type': 'ir.actions.act_window',
            'name': _('Update Stock'),
            'res_model': 'jabin.product.stock.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_id': self.id,
                'default_current_stock': self.stock_quantity,
            }
        }
