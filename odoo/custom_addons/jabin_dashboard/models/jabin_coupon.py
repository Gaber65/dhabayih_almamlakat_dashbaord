# jabin_coupon.py
import random
import string
import uuid
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class JabinCoupon(models.Model):
    _name = "jabin.coupon"
    _description = "JABIN Coupon / Promo Code"
    _order = "id desc"

    @api.model
    def _generate_unique_random_code(self, prefix: str = "JABIN", length: int = 8) -> str:
        """Generate a guaranteed unique random coupon code (e.g. JABIN-X8K9L2)."""
        chars = string.ascii_uppercase + string.digits
        clean_chars = chars.translate(str.maketrans("", "", "0O1I"))
        for _ in range(100):
            rand_str = "".join(random.choices(clean_chars, k=length))
            code = f"{prefix}-{rand_str}" if prefix else rand_str
            if self.sudo().search_count([("code", "=", code)]) == 0:
                return code
        return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"

    # --- Core Fields ---
    code = fields.Char(
        string="Coupon Code",
        default=lambda self: self._generate_unique_random_code(),
        help="Unique promotional discount code (e.g. SAVE10 or auto-generated JABIN-X9K2L4)"
    )
    name = fields.Char(
        string="Coupon Name",
        required=True,
        translate=True,
        help="Descriptive name of the coupon"
    )
    description = fields.Text(
        string="Description",
        translate=True,
        help="Optional details or terms of the coupon"
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        index=True,
        help="Whether this coupon is active and usable"
    )

    # --- Discount Configuration ---
    discount_type = fields.Selection([
        ("percentage", "Percentage"),
        ("fixed", "Fixed Amount")
    ], string="Discount Type", required=True, default="percentage", index=True)

    discount_value = fields.Float(
        string="Discount Value",
        required=True,
        default=0.0,
        help="Percentage (0-100) or fixed amount value of discount"
    )
    minimum_order_amount = fields.Float(
        string="Minimum Order Amount",
        default=0.0,
        help="Minimum subtotal required to apply this coupon (0 for no minimum)"
    )
    maximum_discount = fields.Float(
        string="Maximum Discount",
        default=0.0,
        help="Maximum discount amount allowed for percentage discounts (0 for unlimited)"
    )

    # --- Usage Limits ---
    usage_limit = fields.Integer(
        string="Usage Limit",
        default=0,
        help="Total number of times this coupon can be redeemed across all customers (0 for unlimited)"
    )
    used_count = fields.Integer(
        string="Used Count",
        default=0,
        readonly=True,
        help="Number of times this coupon has been used in confirmed orders"
    )
    usage_limit_per_customer = fields.Integer(
        string="Usage Limit Per Customer",
        default=0,
        help="Max usages per single customer (0 for unlimited)"
    )

    # --- Dates ---
    start_date = fields.Datetime(
        string="Start Date",
        help="Date and time when the coupon becomes valid"
    )
    end_date = fields.Datetime(
        string="End Date",
        help="Date and time when the coupon expires"
    )

    # --- Applicability / Restrictions ---
    applies_to = fields.Selection([
        ("all", "All Products"),
        ("categories", "Categories"),
        ("products", "Products")
    ], string="Applies To", required=True, default="all", index=True)

    category_ids = fields.Many2many(
        "jabin.category",
        "jabin_coupon_category_rel",
        "coupon_id",
        "category_id",
        string="Categories",
        help="Categories eligible for this discount when applies_to is 'categories'"
    )
    product_ids = fields.Many2many(
        "jabin.product",
        "jabin_coupon_product_rel",
        "coupon_id",
        "product_id",
        string="Products",
        help="Products eligible for this discount when applies_to is 'products'"
    )

    _sql_constraints = [
        ("unique_code", "UNIQUE(code)", "Coupon code must be unique!"),
    ]

    # --- Constrains ---
    @api.constrains("code")
    def _check_code_unique(self):
        for record in self:
            if record.code:
                clean_code = record.code.strip().upper()
                existing = self.sudo().search([
                    ("code", "=", clean_code),
                    ("id", "!=", record.id)
                ], limit=1)
                if existing:
                    raise ValidationError(_("Coupon code '%s' already exists!") % clean_code)

    @api.constrains("discount_type", "discount_value")
    def _check_discount_value(self):
        for record in self:
            if record.discount_value <= 0:
                raise ValidationError(_("Discount value must be greater than zero."))
            if record.discount_type == "percentage" and record.discount_value > 100:
                raise ValidationError(_("Percentage discount value cannot exceed 100%."))

    @api.constrains("minimum_order_amount", "maximum_discount", "usage_limit", "usage_limit_per_customer")
    def _check_non_negative_fields(self):
        for record in self:
            if record.minimum_order_amount < 0:
                raise ValidationError(_("Minimum order amount cannot be negative."))
            if record.maximum_discount < 0:
                raise ValidationError(_("Maximum discount cannot be negative."))
            if record.usage_limit < 0:
                raise ValidationError(_("Usage limit cannot be negative."))
            if record.usage_limit_per_customer < 0:
                raise ValidationError(_("Usage limit per customer cannot be negative."))

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.start_date > record.end_date:
                raise ValidationError(_("Start date cannot be after end date."))

    @api.constrains("applies_to", "category_ids", "product_ids")
    def _check_applies_to_selections(self):
        for record in self:
            if record.applies_to == "categories" and not record.category_ids:
                raise ValidationError(_("Please select at least one category when applies_to is set to Categories."))
            if record.applies_to == "products" and not record.product_ids:
                raise ValidationError(_("Please select at least one product when applies_to is set to Products."))

    # --- Actions ---
    # --- Actions ---
    def action_generate_random_code(self):
        """Action button to generate a new random coupon code for existing records."""
        for record in self:
            record.code = record._generate_unique_random_code()
        return True

    def action_generate_random_code_new(self):
        """Action button to generate a new random coupon code for new records."""
        # This method is called from the form view
        # It generates a new code for the current record
        for record in self:
            record.code = record._generate_unique_random_code()

        # Return success notification (optional)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': 'New coupon code generated successfully!',
                'type': 'success',
                'sticky': False,
            }
        }
    # --- ORM Overrides ---
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("code"):
                vals["code"] = self._generate_unique_random_code()
            elif isinstance(vals["code"], str):
                vals["code"] = vals["code"].strip().upper()
        return super().create(vals_list)

    def write(self, vals):
        if "code" in vals and isinstance(vals["code"], str):
            vals["code"] = vals["code"].strip().upper()
        return super().write(vals)

    # --- Helper methods ---
    def get_summary_dict(self):
        """Return a clean structured dictionary of coupon fields for API responses."""
        self.ensure_one()
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description or "",
            "active": self.active,
            "discount_type": self.discount_type,
            "discount_value": self.discount_value,
            "minimum_order_amount": self.minimum_order_amount,
            "maximum_discount": self.maximum_discount,
            "usage_limit": self.usage_limit,
            "used_count": self.used_count,
            "usage_limit_per_customer": self.usage_limit_per_customer,
            "start_date": fields.Datetime.to_string(self.start_date) if self.start_date else None,
            "end_date": fields.Datetime.to_string(self.end_date) if self.end_date else None,
            "applies_to": self.applies_to,
            "category_ids": self.category_ids.ids if self.category_ids else [],
            "categories": [{"id": c.id, "name": c.name} for c in self.category_ids],
            "product_ids": self.product_ids.ids if self.product_ids else [],
            "products": [{"id": p.id, "name": p.name} for p in self.product_ids],
        }
