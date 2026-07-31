# product_validator.py
from odoo import _
from odoo.exceptions import ValidationError
from typing import Dict, Any, Optional
from datetime import datetime


class ProductValidator:
    """
    Product validator following Category module standards.
    All validation methods are static and focused on data integrity.
    """

    # Constants
    MIN_NAME_LENGTH = 2
    MAX_NAME_LENGTH = 200
    MAX_DESCRIPTION_LENGTH = 2000
    SKU_PATTERN = r'^[A-Z0-9\-_]+$'
    ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}

    @staticmethod
    def validate_create(vals: Dict[str, Any]) -> None:
        """
        Validate product creation data.

        Args:
            vals: Dictionary of values to validate

        Raises:
            ValidationError: If validation fails
        """
        # Validate required fields
        ProductValidator._validate_required_fields(
            vals,
            ['name', 'sku', 'category_id', 'purchase_price', 'selling_price']
        )

        # Validate name
        if 'name' in vals:
            ProductValidator._validate_name(vals['name'])

        # Validate SKU
        if 'sku' in vals:
            ProductValidator._validate_sku(vals['sku'])

        # Validate category_id
        if 'category_id' in vals:
            ProductValidator._validate_positive_integer(vals['category_id'], 'Category ID')

        # Validate prices
        if 'purchase_price' in vals:
            ProductValidator._validate_non_negative_number(vals['purchase_price'], 'Purchase Price')

        if 'selling_price' in vals:
            ProductValidator._validate_non_negative_number(vals['selling_price'], 'Selling Price')

        # Validate stock
        if 'stock_quantity' in vals:
            ProductValidator._validate_non_negative_number(vals['stock_quantity'], 'Stock Quantity')

        if 'minimum_stock' in vals:
            ProductValidator._validate_non_negative_number(vals['minimum_stock'], 'Minimum Stock')

        # Validate discount
        if 'discount_type' in vals:
            ProductValidator._validate_discount_type(vals['discount_type'])

        if 'discount_value' in vals:
            ProductValidator._validate_non_negative_number(vals['discount_value'], 'Discount Value')

        # Validate offer dates
        ProductValidator._validate_offer_dates(
            vals.get('offer_start_date'),
            vals.get('offer_end_date')
        )

        # Validate description if present
        if 'description' in vals and vals['description']:
            ProductValidator._validate_string_length(
                vals['description'],
                'Description',
                max_length=ProductValidator.MAX_DESCRIPTION_LENGTH
            )

    @staticmethod
    def validate_update(vals: Dict[str, Any]) -> None:
        """
        Validate product update data.

        Args:
            vals: Dictionary of values to validate

        Raises:
            ValidationError: If validation fails
        """
        # Validate name if present
        if 'name' in vals:
            ProductValidator._validate_name(vals['name'])

        # Validate SKU if present
        if 'sku' in vals:
            ProductValidator._validate_sku(vals['sku'])

        # Validate category_id if present
        if 'category_id' in vals:
            ProductValidator._validate_positive_integer(vals['category_id'], 'Category ID')

        # Validate prices if present
        if 'purchase_price' in vals:
            ProductValidator._validate_non_negative_number(vals['purchase_price'], 'Purchase Price')

        if 'selling_price' in vals:
            ProductValidator._validate_non_negative_number(vals['selling_price'], 'Selling Price')

        # Validate stock if present
        if 'stock_quantity' in vals:
            ProductValidator._validate_non_negative_number(vals['stock_quantity'], 'Stock Quantity')

        if 'minimum_stock' in vals:
            ProductValidator._validate_non_negative_number(vals['minimum_stock'], 'Minimum Stock')

        # Validate discount if present
        if 'discount_type' in vals:
            ProductValidator._validate_discount_type(vals['discount_type'])

        if 'discount_value' in vals:
            ProductValidator._validate_non_negative_number(vals['discount_value'], 'Discount Value')

        # Validate offer dates
        ProductValidator._validate_offer_dates(
            vals.get('offer_start_date'),
            vals.get('offer_end_date')
        )

        # Validate description if present
        if 'description' in vals and vals['description']:
            ProductValidator._validate_string_length(
                vals['description'],
                'Description',
                max_length=ProductValidator.MAX_DESCRIPTION_LENGTH
            )

    @staticmethod
    def validate_delete(product) -> None:
        """
        Validate product deletion.

        Args:
            product: The product record to delete

        Raises:
            ValidationError: If validation fails
        """
        ProductValidator._validate_exists(product)

        # Check if product has any dependencies
        # Add any business rules for deletion here

    @staticmethod
    def validate_exists(product) -> None:
        """
        Validate that a product record exists.

        Args:
            product: The product record to check

        Raises:
            ValidationError: If record doesn't exist
        """
        if not product or not product.exists():
            raise ValidationError(_("Product not found."))

    @staticmethod
    def validate_unique_sku(env, sku: str, exclude_id: Optional[int] = None) -> None:
        """
        Validate that a product SKU is unique.

        Args:
            env: Odoo environment
            sku: Product SKU to check
            exclude_id: ID to exclude from check

        Raises:
            ValidationError: If SKU already exists
        """
        domain = [('sku', '=', sku)]
        if exclude_id:
            domain.append(('id', '!=', exclude_id))

        if env['jabin.product'].sudo().search_count(domain) > 0:
            raise ValidationError(
                _("SKU must be unique! '%s' already exists.") % sku
            )

    @staticmethod
    def validate_unique_barcode(env, barcode: str, exclude_id: Optional[int] = None) -> None:
        """
        Validate that a product barcode is unique.

        Args:
            env: Odoo environment
            barcode: Product barcode to check
            exclude_id: ID to exclude from check

        Raises:
            ValidationError: If barcode already exists
        """
        if not barcode:
            return

        domain = [('barcode', '=', barcode)]
        if exclude_id:
            domain.append(('id', '!=', exclude_id))

        if env['jabin.product'].sudo().search_count(domain) > 0:
            raise ValidationError(
                _("Barcode must be unique! '%s' already exists.") % barcode
            )

    @staticmethod
    def validate_stock_update(product, quantity: float) -> None:
        """
        Validate stock update operation.

        Args:
            product: The product record
            quantity: Quantity to add/remove

        Raises:
            ValidationError: If validation fails
        """
        ProductValidator._validate_exists(product)

        if quantity < 0 and abs(quantity) > product.stock_quantity:
            raise ValidationError(
                _("Insufficient stock! Current stock: %(stock)s, Requested: %(requested)s") % {
                    'stock': product.stock_quantity,
                    'requested': abs(quantity)
                }
            )

    @staticmethod
    def validate_image_type(content_type: str) -> None:
        """
        Validate image MIME type.

        Args:
            content_type: Image MIME type

        Raises:
            ValueError: If image type is not allowed
        """
        if content_type not in ProductValidator.ALLOWED_IMAGE_TYPES:
            raise ValueError(
                f"Unsupported image type '{content_type}'. "
                "Allowed: jpg, jpeg, png, webp."
            )

    # ------------------------------------------------------------------
    # Private helper methods
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_required_fields(vals: Dict[str, Any], required_fields: list) -> None:
        """
        Validate that required fields are present and not empty.

        Args:
            vals: Dictionary of values
            required_fields: List of required field names

        Raises:
            ValidationError: If required field is missing or empty
        """
        for field in required_fields:
            if field not in vals or vals[field] is None or str(vals[field]).strip() == '':
                raise ValidationError(_("Field '%s' is required.") % field)

    @staticmethod
    def _validate_name(name: str) -> None:
        """
        Validate product name with all rules.

        Args:
            name: Product name to validate

        Raises:
            ValidationError: If validation fails
        """
        ProductValidator._validate_string_length(
            name,
            'Product Name',
            min_length=ProductValidator.MIN_NAME_LENGTH,
            max_length=ProductValidator.MAX_NAME_LENGTH
        )

        if not any(c.isalnum() for c in name):
            raise ValidationError(
                _("Product name must contain at least one alphanumeric character.")
            )

        if name != name.strip():
            raise ValidationError(
                _("Product name cannot have leading or trailing spaces.")
            )

        if '  ' in name:
            raise ValidationError(
                _("Product name cannot contain consecutive spaces.")
            )

    @staticmethod
    def _validate_sku(sku: str) -> None:
        """
        Validate product SKU format.

        Args:
            sku: SKU to validate

        Raises:
            ValidationError: If validation fails
        """
        if not sku or not sku.strip():
            raise ValidationError(_("SKU is required."))

        import re
        if not re.match(ProductValidator.SKU_PATTERN, sku):
            raise ValidationError(
                _("SKU must contain only uppercase letters, numbers, hyphens, and underscores.")
            )

        if sku != sku.strip():
            raise ValidationError(_("SKU cannot have leading or trailing spaces."))

    @staticmethod
    def _validate_string_length(
        value: str,
        field_name: str,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None
    ) -> None:
        """
        Validate string length constraints.

        Args:
            value: String to validate
            field_name: Name of the field for error messages
            min_length: Minimum length required
            max_length: Maximum length allowed

        Raises:
            ValidationError: If validation fails
        """
        if value is None:
            return

        if not isinstance(value, str):
            raise ValidationError(_("%s must be a string.") % field_name)

        if min_length is not None and len(value) < min_length:
            raise ValidationError(
                _("%(field)s must be at least %(min)d characters long.") % {
                    'field': field_name,
                    'min': min_length
                }
            )

        if max_length is not None and len(value) > max_length:
            raise ValidationError(
                _("%(field)s must not exceed %(max)d characters.") % {
                    'field': field_name,
                    'max': max_length
                }
            )

    @staticmethod
    def _validate_non_negative_number(value: Any, field_name: str) -> None:
        """
        Validate that a number is non-negative.

        Args:
            value: Value to validate
            field_name: Name of the field for error messages

        Raises:
            ValidationError: If validation fails
        """
        try:
            num = float(value)
        except (TypeError, ValueError):
            raise ValidationError(_("%s must be a valid number.") % field_name)

        if num < 0:
            raise ValidationError(_("%s cannot be negative.") % field_name)

    @staticmethod
    def _validate_positive_integer(value: Any, field_name: str) -> None:
        """
        Validate that a value is a positive integer.

        Args:
            value: Value to validate
            field_name: Name of the field for error messages

        Raises:
            ValidationError: If validation fails
        """
        try:
            num = int(value)
        except (TypeError, ValueError):
            raise ValidationError(_("%s must be a valid integer.") % field_name)

        if num <= 0:
            raise ValidationError(_("%s must be greater than 0.") % field_name)

    @staticmethod
    def _validate_boolean(value: Any, field_name: str) -> None:
        """
        Validate that a value is a boolean.

        Args:
            value: Value to validate
            field_name: Name of the field for error messages

        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(value, bool):
            raise ValidationError(_("%s must be a boolean value.") % field_name)

    @staticmethod
    def _validate_discount_type(discount_type: str) -> None:
        """
        Validate discount type.

        Args:
            discount_type: Discount type to validate

        Raises:
            ValidationError: If validation fails
        """
        allowed_types = ['percentage', 'fixed']
        if discount_type not in allowed_types:
            raise ValidationError(
                _("Discount type must be one of: %s") % ', '.join(allowed_types)
            )

    @staticmethod
    def _validate_offer_dates(start_date, end_date) -> None:
        """
        Validate offer date range.

        Args:
            start_date: Offer start date
            end_date: Offer end date

        Raises:
            ValidationError: If validation fails
        """
        if start_date and end_date and start_date > end_date:
            raise ValidationError(_("Offer start date cannot be after end date."))

        if start_date and not end_date:
            raise ValidationError(_("Offer end date is required when start date is set."))

        if end_date and not start_date:
            raise ValidationError(_("Offer start date is required when end date is set."))

    @staticmethod
    def _validate_exists(product) -> None:
        """
        Validate that a product exists.

        Args:
            product: Product record to check

        Raises:
            ValidationError: If product doesn't exist
        """
        if not product or not product.exists():
            raise ValidationError(_("Product not found."))