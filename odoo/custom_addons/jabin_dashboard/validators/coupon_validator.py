# coupon_validator.py
from typing import Dict, Any, Optional
from odoo import _, fields
from odoo.exceptions import ValidationError
from odoo.addons.jabin_core import BaseValidator


class CouponValidator(BaseValidator):
    """
    Coupon validator using jabin_core BaseValidator infrastructure.
    Validates coupon fields, creation, update, deletion, and order application.
    """

    MIN_CODE_LENGTH = 2
    MAX_CODE_LENGTH = 30
    MIN_NAME_LENGTH = 2
    MAX_NAME_LENGTH = 100
    MAX_DESCRIPTION_LENGTH = 500

    @staticmethod
    def validate_create(vals: Dict[str, Any], env=None) -> None:
        """Validate coupon creation data."""
        # Auto-generate coupon code if not provided
        if not vals.get('code') and env:
            vals['code'] = env['jabin.coupon']._generate_unique_random_code()

        # Validate required fields
        CouponValidator.validate_required_fields(
            vals, ['name', 'discount_type', 'discount_value']
        )

        # Validate code
        if 'code' in vals and vals['code']:
            CouponValidator._validate_coupon_code(
                vals['code'],
                check_uniqueness=True,
                env=env
            )

        # Validate name
        if 'name' in vals:
            CouponValidator.validate_string_length(
                vals['name'],
                'Coupon Name',
                min_length=CouponValidator.MIN_NAME_LENGTH,
                max_length=CouponValidator.MAX_NAME_LENGTH
            )

        # Validate description
        if 'description' in vals and vals['description']:
            CouponValidator.validate_string_length(
                vals['description'],
                'Description',
                max_length=CouponValidator.MAX_DESCRIPTION_LENGTH
            )

        # Validate discount_type
        if 'discount_type' in vals:
            CouponValidator.validate_in_list(
                vals['discount_type'],
                ['percentage', 'fixed'],
                'Discount Type'
            )

        # Validate discount_value
        if 'discount_value' in vals:
            CouponValidator.validate_positive_number(
                vals['discount_value'],
                'Discount Value',
                allow_zero=False
            )
            if vals.get('discount_type') == 'percentage' and float(vals['discount_value']) > 100:
                raise ValidationError(_("Percentage discount value cannot exceed 100%."))

        # Validate minimum_order_amount
        if 'minimum_order_amount' in vals and vals['minimum_order_amount'] is not None:
            CouponValidator.validate_positive_number(
                vals['minimum_order_amount'],
                'Minimum Order Amount',
                allow_zero=True
            )

        # Validate maximum_discount
        if 'maximum_discount' in vals and vals['maximum_discount'] is not None:
            CouponValidator.validate_positive_number(
                vals['maximum_discount'],
                'Maximum Discount',
                allow_zero=True
            )

        # Validate usage limits
        if 'usage_limit' in vals and vals['usage_limit'] is not None:
            CouponValidator.validate_positive_number(
                vals['usage_limit'],
                'Usage Limit',
                allow_zero=True
            )

        if 'usage_limit_per_customer' in vals and vals['usage_limit_per_customer'] is not None:
            CouponValidator.validate_positive_number(
                vals['usage_limit_per_customer'],
                'Usage Limit Per Customer',
                allow_zero=True
            )

        # Validate date range
        start_date = vals.get('start_date')
        end_date = vals.get('end_date')
        if start_date and end_date:
            CouponValidator.validate_date_range(start_date, end_date, 'Start Date', 'End Date')

        # Validate applies_to & relational restrictions
        if 'applies_to' in vals:
            CouponValidator.validate_in_list(
                vals['applies_to'],
                ['all', 'categories', 'products'],
                'Applies To'
            )
            if vals['applies_to'] == 'categories' and not vals.get('category_ids'):
                raise ValidationError(_("Please select at least one category when applies_to is set to Categories."))
            if vals['applies_to'] == 'products' and not vals.get('product_ids'):
                raise ValidationError(_("Please select at least one product when applies_to is set to Products."))

    @staticmethod
    def validate_update(coupon, vals: Dict[str, Any]) -> None:
        """Validate coupon update data."""
        # Validate code if present
        if 'code' in vals:
            CouponValidator._validate_coupon_code(
                vals['code'],
                check_uniqueness=True,
                env=coupon.env,
                exclude_id=coupon.id
            )

        # Validate name if present
        if 'name' in vals:
            CouponValidator.validate_string_length(
                vals['name'],
                'Coupon Name',
                min_length=CouponValidator.MIN_NAME_LENGTH,
                max_length=CouponValidator.MAX_NAME_LENGTH
            )

        # Validate description if present
        if 'description' in vals and vals['description']:
            CouponValidator.validate_string_length(
                vals['description'],
                'Description',
                max_length=CouponValidator.MAX_DESCRIPTION_LENGTH
            )

        # Determine discount type and value
        d_type = vals.get('discount_type', coupon.discount_type)
        if 'discount_type' in vals:
            CouponValidator.validate_in_list(d_type, ['percentage', 'fixed'], 'Discount Type')

        if 'discount_value' in vals:
            CouponValidator.validate_positive_number(
                vals['discount_value'],
                'Discount Value',
                allow_zero=False
            )
            if d_type == 'percentage' and float(vals['discount_value']) > 100:
                raise ValidationError(_("Percentage discount value cannot exceed 100%."))

        # Validate numbers if present
        for field_name, label in [
            ('minimum_order_amount', 'Minimum Order Amount'),
            ('maximum_discount', 'Maximum Discount'),
            ('usage_limit', 'Usage Limit'),
            ('usage_limit_per_customer', 'Usage Limit Per Customer'),
        ]:
            if field_name in vals and vals[field_name] is not None:
                CouponValidator.validate_positive_number(vals[field_name], label, allow_zero=True)

        # Validate dates
        start_date = vals.get('start_date', coupon.start_date)
        end_date = vals.get('end_date', coupon.end_date)
        if start_date and end_date:
            CouponValidator.validate_date_range(start_date, end_date, 'Start Date', 'End Date')

        # Validate applies_to
        applies_to = vals.get('applies_to', coupon.applies_to)
        if 'applies_to' in vals:
            CouponValidator.validate_in_list(applies_to, ['all', 'categories', 'products'], 'Applies To')

        if applies_to == 'categories':
            cat_ids = vals.get('category_ids', coupon.category_ids.ids)
            if not cat_ids:
                raise ValidationError(_("Please select at least one category when applies_to is set to Categories."))
        elif applies_to == 'products':
            prod_ids = vals.get('product_ids', coupon.product_ids.ids)
            if not prod_ids:
                raise ValidationError(_("Please select at least one product when applies_to is set to Products."))

    @staticmethod
    def validate_delete(coupon) -> None:
        """Validate coupon deletion."""
        orders_count = coupon.env['jabin.order'].sudo().search_count([
            ('coupon_id', '=', coupon.id)
        ])
        if orders_count > 0:
            raise ValidationError(
                _("Cannot delete coupon '%(code)s' because it is associated with %(count)s order(s).") % {
                    'code': coupon.code,
                    'count': orders_count
                }
            )

    @staticmethod
    def validate_coupon_exists(env, coupon_id: int) -> None:
        """Validate that coupon exists in database."""
        if not coupon_id:
            raise ValidationError(_("Coupon ID is required."))

        CouponValidator.validate_positive_number(coupon_id, 'Coupon ID')
        if not env['jabin.coupon'].sudo().browse(coupon_id).exists():
            raise ValidationError(_("Coupon not found."))

    @staticmethod
    def validate_apply_coupon(order, coupon, customer_id: Optional[int] = None) -> None:
        """
        Validate coupon application against order context.

        Checks:
        1. Existence
        2. Active status
        3. Date window
        4. Usage limit
        5. Customer usage limit
        6. Minimum order amount
        7. Product/category restrictions
        """
        if not coupon or not coupon.exists():
            raise ValidationError(_("Coupon does not exist."))

        if not coupon.active:
            raise ValidationError(_("Coupon is inactive or invalid."))

        # Check dates
        now = fields.Datetime.now()
        if coupon.start_date and now < coupon.start_date:
            raise ValidationError(_("Coupon is not valid yet."))
        if coupon.end_date and now > coupon.end_date:
            raise ValidationError(_("Coupon has expired."))

        # Check overall usage limit
        if coupon.usage_limit > 0 and coupon.used_count >= coupon.usage_limit:
            raise ValidationError(_("Coupon usage limit has been reached."))

        # Check customer usage limit
        eff_customer_id = customer_id or (order.customer_id.id if order and order.customer_id else None)
        if coupon.usage_limit_per_customer > 0 and eff_customer_id:
            customer_uses = order.env['jabin.order'].sudo().search_count([
                ('customer_id', '=', eff_customer_id),
                ('coupon_id', '=', coupon.id),
                ('state', '!=', 'cancelled')
            ])
            if customer_uses >= coupon.usage_limit_per_customer:
                raise ValidationError(_("You have reached the maximum usage limit for this coupon."))

        if not order:
            raise ValidationError(_("Order object is required to validate coupon application."))

        # Check minimum order amount
        subtotal = order.subtotal
        if coupon.minimum_order_amount > 0 and subtotal < coupon.minimum_order_amount:
            raise ValidationError(
                _("Order subtotal must be at least %(min)s to use coupon '%(code)s'.") % {
                    'min': coupon.minimum_order_amount,
                    'code': coupon.code
                }
            )

        # Check product/category restrictions
        if coupon.applies_to == 'categories':
            matching_lines = order.order_line_ids.filtered(
                lambda l: l.product_id and l.product_id.category_id and l.product_id.category_id.id in coupon.category_ids.ids
            )
            if not matching_lines:
                raise ValidationError(_("This coupon does not apply to any products in your order."))
        elif coupon.applies_to == 'products':
            matching_lines = order.order_line_ids.filtered(
                lambda l: l.product_id and l.product_id.id in coupon.product_ids.ids
            )
            if not matching_lines:
                raise ValidationError(_("This coupon does not apply to any products in your order."))

    # ------------------------------------------------------------------
    # Private helper methods
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_coupon_code(
        code: str,
        check_uniqueness: bool = False,
        env=None,
        exclude_id: Optional[int] = None
    ) -> None:
        """Validate coupon code string and uniqueness."""
        CouponValidator.validate_string_length(
            code,
            'Coupon Code',
            min_length=CouponValidator.MIN_CODE_LENGTH,
            max_length=CouponValidator.MAX_CODE_LENGTH
        )

        clean_code = code.strip().upper()
        if not clean_code.isalnum() and not any(c in clean_code for c in ['_', '-']):
            raise ValidationError(
                _("Coupon code must contain only letters, numbers, hyphens, and underscores.")
            )

        if check_uniqueness and env:
            model = env['jabin.coupon'].sudo()
            domain = [('code', '=', clean_code)]
            if exclude_id:
                domain.append(('id', '!=', exclude_id))
            if model.search_count(domain) > 0:
                raise ValidationError(_("Coupon code '%s' already exists!") % clean_code)
