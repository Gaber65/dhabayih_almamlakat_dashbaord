# cart_validator.py
from odoo import _
from odoo.exceptions import ValidationError
from typing import Dict, Any, Optional
from odoo.addons.jabin_core import BaseValidator


class CartValidator(BaseValidator):
    """
    Validator for Shopping Cart operations.
    Inherits validation helpers from BaseValidator.
    """

    @staticmethod
    def validate_add_product(vals: Dict[str, Any]) -> None:
        """Validate input for adding a product to the cart."""
        CartValidator.validate_required_fields(vals, ['product_id'])
        CartValidator.validate_field_type(vals['product_id'], int, 'Product ID')

        if 'quantity' in vals:
            CartValidator.validate_positive_number(
                vals['quantity'],
                'Quantity',
                allow_zero=False
            )

    @staticmethod
    def validate_options(env, product_id: int, cutting_option_id=None, packaging_ids=None, excluded_part_ids=None) -> None:
        """Validate that selected customization options belong to the product and are active."""
        product = env['jabin.product'].sudo().browse(product_id)
        if not product.exists():
            raise ValidationError(_("Product not found."))

        if cutting_option_id:
            active_cut_ids = set(product.cutting_option_ids.filtered(lambda x: x.active).ids)
            if int(cutting_option_id) not in active_cut_ids:
                raise ValidationError(_("خيار التقطيع المختار غير متاح للمنتج '%s'.") % product.name)

        if packaging_ids:
            allowed_pkg_ids = set(product.packaging_ids.filtered(lambda x: x.active).ids)
            for pkg_id in packaging_ids:
                if int(pkg_id) not in allowed_pkg_ids:
                    raise ValidationError(_("خيار التغليف المختار غير متاح للمنتج '%s'.") % product.name)

        if excluded_part_ids:
            allowed_part_ids = set(product.excluded_part_ids.filtered(lambda x: x.active).ids)
            for part_id in excluded_part_ids:
                if int(part_id) not in allowed_part_ids:
                    raise ValidationError(_("خيار الاستبعاد المختار غير متاح للمنتج '%s'.") % product.name)

    @staticmethod
    def validate_stock(env, product_id: int, requested_qty: float, current_cart_qty: float = 0.0) -> None:
        """Validate product availability and stock quantity before adding/updating cart."""
        product = env['jabin.product'].sudo().browse(product_id)
        if not product.exists():
            raise ValidationError(_("Product not found."))
        if not product.active:
            raise ValidationError(_("Product '%s' is inactive.") % product.name)
        if not product.is_available:
            raise ValidationError(_("Product '%s' is not available (out of stock).") % product.name)

        total_qty = current_cart_qty + requested_qty
        if product.stock_quantity and total_qty > product.stock_quantity:
            raise ValidationError(
                _("Requested quantity (%(requested)s) exceeds available stock (%(stock)s) for product '%(product)s'.") % {
                    'requested': total_qty,
                    'stock': product.stock_quantity,
                    'product': product.name
                }
            )

    @staticmethod
    def validate_update_quantity(vals: Dict[str, Any]) -> None:
        """Validate input for updating product quantity in the cart."""
        CartValidator.validate_required_fields(vals, ['product_id', 'quantity'])
        CartValidator.validate_field_type(vals['product_id'], int, 'Product ID')
        CartValidator.validate_positive_number(
            vals['quantity'],
            'Quantity',
            allow_zero=False
        )

    @staticmethod
    def validate_checkout(cart) -> None:
        """
        Validate cart state and revalidate sizes and options before allowing checkout.
        """
        if not cart or not cart.exists():
            raise ValidationError(_("السلة غير موجودة."))

        if cart.status != 'active':
            raise ValidationError(_("يمكن إتمام الطلب فقط للسلة النشطة."))

        if not cart.line_ids:
            raise ValidationError(_("لا يمكن إتمام الطلب والسلة فارغة."))

        customer = cart.customer_id
        if not customer or not customer.exists():
            raise ValidationError(_("لا يوجد عميل مرتبط بالسلة."))

        if customer.status not in ('active', 'pending'):
            raise ValidationError(_("حساب العميل غير نشط."))

        SizeModel = cart.env['jabin.product.size'].sudo().with_context(active_test=False)

        for line in cart.line_ids:
            product = line.product_id
            if not product or not product.exists():
                raise ValidationError(_("أحد المنتجات في السلة لم يعد متوفراً."))
            if not product.active:
                raise ValidationError(_("المنتج '%s' لم يعد متاحاً حالياً.") % product.display_name)
            if not product.is_available:
                raise ValidationError(_("المنتج '%s' نفذت كميته من المخزون.") % product.display_name)

            active_sizes = product.with_context(active_test=False).size_ids.filtered(lambda s: s.active)
            if line.size_id:
                size_rec = SizeModel.browse(line.size_id.id)
                if not size_rec.exists() or not size_rec.active or size_rec.product_id.id != product.id:
                    raise ValidationError(
                        _("عذراً، الحجم المختار للمنتج '%s' تم إيقافه أو إزالته. يرجى مراجعة السلة واختيار حجم متاح قبل الدفع.") % product.display_name
                    )
                if round(float(size_rec.price or 0.0), 2) != round(float(line.price_unit or 0.0), 2):
                    line.sudo().write({'price_unit': size_rec.price})
                    raise ValidationError(
                        _("تم تحديث سعر الحجم '%(size)s' للمنتج '%(prod)s' إلى %(price).2f ر.س. يرجى مراجعة السلة قبل إتمام الدفع.") % {
                            'size': size_rec.name,
                            'prod': product.display_name,
                            'price': size_rec.price,
                        }
                    )
            elif active_sizes:
                raise ValidationError(
                    _("تم تحديث الأحجام المتاحة للمنتج '%s'. يرجى مراجعة السلة واختيار الحجم المطلوب قبل الدفع.") % product.display_name
                )

            if line.cutting_option_id:
                if not line.cutting_option_id.active or line.cutting_option_id.id not in product.cutting_option_ids.ids:
                    raise ValidationError(
                        _("خيار التقطيع المختار للمنتج '%s' لم يعد متاحاً. يرجى تحديث خيارات المنتج في السلة.") % product.display_name
                    )

            if line.packaging_ids:
                allowed_pkg_ids = set(product.packaging_ids.filtered(lambda p: p.active).ids)
                for pkg in line.packaging_ids:
                    if not pkg.active or pkg.id not in allowed_pkg_ids:
                        raise ValidationError(
                            _("خيار التغليف المختار للمنتج '%s' لم يعد متاحاً. يرجى تحديث خيارات المنتج في السلة.") % product.display_name
                        )
