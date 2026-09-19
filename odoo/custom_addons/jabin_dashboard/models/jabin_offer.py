from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import date

class JabinOffer(models.Model):
    _name = "jabin.offer"
    _description = "Jabin Multi-Product Promotional Offer"
    _order = "sequence, id desc"

    name = fields.Char(string="Offer Title", required=True, translate=True)
    subtitle = fields.Char(string="Subtitle / Tagline", translate=True)
    description = fields.Text(string="Description", translate=True)
    
    banner_image = fields.Image(
        string="Banner Image",
        max_width=1920,
        max_height=800,
        help="High-resolution promotional banner shown on Home and Offers showcase."
    )
    
    discount_type = fields.Selection([
        ("percentage", "Percentage Discount (%)"),
        ("fixed", "Fixed Amount Discount (SAR)")
    ], string="Discount Type", default="percentage", required=True)
    
    discount_value = fields.Float(
        string="Discount Value",
        default=10.0,
        required=True,
        help="Discount percentage or fixed reduction applied to each included product."
    )
    
    product_ids = fields.Many2many(
        "jabin.product",
        "jabin_offer_product_rel",
        "offer_id",
        "product_id",
        string="Included Products",
        domain="[('active', '=', True)]"
    )
    
    start_date = fields.Date(
        string="Start Date",
        default=fields.Date.context_today,
        required=True
    )
    end_date = fields.Date(string="End Date")
    
    active = fields.Boolean(string="Active", default=True)
    sequence = fields.Integer(string="Sequence", default=10)
    
    badge_text = fields.Char(
        string="Offer Badge",
        compute="_compute_badge_text",
        store=True,
        readonly=False,
        help="Promotional badge shown on cards (e.g. خصم 20% or عرض خاص)"
    )
    
    is_currently_active = fields.Boolean(
        string="Is Currently Active",
        compute="_compute_is_currently_active"
    )
    
    products_count = fields.Integer(
        string="Products Count",
        compute="_compute_products_count"
    )

    @api.depends("product_ids")
    def _compute_products_count(self):
        for rec in self:
            rec.products_count = len(rec.product_ids)

    @api.depends("discount_type", "discount_value")
    def _compute_badge_text(self):
        for rec in self:
            if not rec.badge_text:
                if rec.discount_type == "percentage":
                    rec.badge_text = f"خصم {int(rec.discount_value)}%"
                else:
                    rec.badge_text = f"خصم {int(rec.discount_value)} ر.س"

    @api.depends("active", "start_date", "end_date")
    def _compute_is_currently_active(self):
        today = fields.Date.context_today(self)
        for rec in self:
            active_now = rec.active
            if active_now and rec.start_date:
                active_now = rec.start_date <= today
            if active_now and rec.end_date:
                active_now = active_now and (rec.end_date >= today)
            rec.is_currently_active = active_now

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.start_date > rec.end_date:
                raise ValidationError(_("Offer start date cannot be after the end date."))

    @api.constrains("discount_value")
    def _check_discount(self):
        for rec in self:
            if rec.discount_value < 0:
                raise ValidationError(_("Discount value cannot be negative."))
            if rec.discount_type == "percentage" and rec.discount_value > 100:
                raise ValidationError(_("Percentage discount cannot exceed 100%."))

    def calculate_discounted_price(self, original_price: float) -> float:
        """Calculate the offer price for a product given its original price."""
        self.ensure_one()
        if not original_price:
            return 0.0
        if self.discount_type == "percentage":
            ratio = max(0.0, min(1.0, self.discount_value / 100.0))
            return round(original_price * (1.0 - ratio), 2)
        else:
            return round(max(0.0, original_price - self.discount_value), 2)

    def action_view_products(self):
        self.ensure_one()
        return {
            "name": _("Products in Offer"),
            "type": "ir.actions.act_window",
            "res_model": "jabin.product",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.product_ids.ids)],
            "context": {"default_offer_ids": [(4, self.id)]},
        }
