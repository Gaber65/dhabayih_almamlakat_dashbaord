# jabin_order_ext.py
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class JabinOrder(models.Model):
    _inherit = 'jabin.order'

    cart_id = fields.Many2one(
        'jabin.cart',
        string='Source Cart',
        readonly=True,
        ondelete='restrict'
    )
    coupon_id = fields.Many2one(
        'jabin.coupon',
        string='Applied Coupon',
        ondelete='set null',
        help='Coupon or promo code applied to this order'
    )
    coupon_code = fields.Char(
        string='Coupon Code',
        related='coupon_id.code',
        store=True,
        readonly=True
    )
    total_after_discount = fields.Monetary(
        string='Total After Discount',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        help='Order subtotal minus total discount amount'
    )
    points_redeemed = fields.Integer(
        string='Points Redeemed',
        default=0,
        help='Number of loyalty points redeemed for a discount on this order.'
    )
    loyalty_discount_amount = fields.Monetary(
        string='Loyalty Discount',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        help='Discount amount in SAR from redeemed loyalty points.'
    )
    loyalty_points_earned = fields.Integer(
        string='Points Earned',
        default=0,
        help='Loyalty points earned by customer upon order delivery.'
    )
    loyalty_points_awarded = fields.Boolean(
        string='Loyalty Points Awarded',
        default=False,
        copy=False,
        help='Flag indicating whether earned points have been posted to customer wallet.'
    )
    loyalty_points_deducted = fields.Boolean(
        string='Loyalty Points Deducted',
        default=False,
        copy=False,
        help='Flag indicating whether redeemed points have been deducted from customer wallet.'
    )

    @api.depends(
        'order_line_ids.price_subtotal',
        'order_line_ids.discount_amount',
        'tax_amount',
        'coupon_id',
        'coupon_id.discount_type',
        'coupon_id.discount_value',
        'coupon_id.maximum_discount',
        'coupon_id.applies_to',
        'coupon_id.category_ids',
        'coupon_id.product_ids',
        'points_redeemed'
    )
    def _compute_totals(self):
        for order in self:
            lines = order.order_line_ids
            subtotal = sum(lines.mapped('price_subtotal'))
            line_discount = sum(lines.mapped('discount_amount'))
            coupon_discount = order._calculate_coupon_discount(subtotal)

            loyalty_discount = 0.0
            if order.points_redeemed > 0:
                loyalty_discount = self.env['jabin.loyalty.service'].calculate_redemption_value(
                    self.env, order.points_redeemed
                )

            total_discount = line_discount + coupon_discount + loyalty_discount
            order.loyalty_discount_amount = loyalty_discount
            order.subtotal = subtotal
            order.discount_amount = total_discount
            order.total_after_discount = max(0.0, subtotal - total_discount)
            order.total = order.total_after_discount + order.tax_amount

    def _calculate_coupon_discount(self, subtotal: float = 0.0) -> float:
        """Calculate discount amount for the applied coupon based on order lines."""
        self.ensure_one()
        if not self.coupon_id:
            return 0.0

        coupon = self.coupon_id

        # Calculate eligible subtotal
        if coupon.applies_to == 'categories':
            eligible_lines = self.order_line_ids.filtered(
                lambda l: l.product_id and l.product_id.category_id and l.product_id.category_id.id in coupon.category_ids.ids
            )
            eligible_subtotal = sum(eligible_lines.mapped('price_subtotal'))
        elif coupon.applies_to == 'products':
            eligible_lines = self.order_line_ids.filtered(
                lambda l: l.product_id and l.product_id.id in coupon.product_ids.ids
            )
            eligible_subtotal = sum(eligible_lines.mapped('price_subtotal'))
        else:
            eligible_subtotal = subtotal

        if eligible_subtotal <= 0.0:
            return 0.0

        if coupon.discount_type == 'percentage':
            raw_discount = (eligible_subtotal * coupon.discount_value) / 100.0
            if coupon.maximum_discount > 0.0:
                discount = min(raw_discount, coupon.maximum_discount)
            else:
                discount = raw_discount
        else:  # fixed amount
            discount = min(coupon.discount_value, eligible_subtotal)

        return round(discount, 2)

    def apply_coupon(self, coupon_code: str):
        """Apply a coupon code to the order."""
        self.ensure_one()
        if not coupon_code:
            raise ValidationError(_("Coupon code is required."))

        clean_code = coupon_code.strip().upper()
        coupon = self.env['jabin.coupon'].sudo().search([('code', '=', clean_code)], limit=1)

        from ..validators.coupon_validator import CouponValidator
        CouponValidator.validate_apply_coupon(order=self, coupon=coupon, customer_id=self.customer_id.id if self.customer_id else None)

        self.write({'coupon_id': coupon.id})
        self._compute_totals()

        return self

    def remove_coupon(self):
        """Remove coupon from the order."""
        self.ensure_one()
        if self.coupon_id:
            self.write({'coupon_id': False})
            self._compute_totals()
        return self

    def apply_loyalty_points(self, points: int):
        """Apply loyalty points redemption to the order."""
        self.ensure_one()
        # Order total before loyalty discount
        subtotal_before_loyalty = self.subtotal - (self.discount_amount - self.loyalty_discount_amount) + self.tax_amount
        self.env['jabin.loyalty.service'].validate_redemption(
            env=self.env,
            customer_id=self.customer_id.id if self.customer_id else None,
            points=points,
            order_total=subtotal_before_loyalty
        )
        self.write({'points_redeemed': points})
        self._compute_totals()
        return self

    def remove_loyalty_points(self):
        """Remove loyalty points redemption from the order."""
        self.ensure_one()
        if self.points_redeemed > 0:
            self.write({'points_redeemed': 0})
            self._compute_totals()
        return self

    def write(self, vals):
        res = super().write(vals)
        # If order state changes to confirmed, increment used_count for coupon
        if 'state' in vals and vals['state'] == 'confirmed':
            for order in self:
                if order.coupon_id:
                    order.coupon_id.sudo().write({'used_count': order.coupon_id.used_count + 1})
        return res

