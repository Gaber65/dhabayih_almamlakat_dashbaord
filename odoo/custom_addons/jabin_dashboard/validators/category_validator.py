# category_validator.py
from odoo import _
from odoo.exceptions import ValidationError
from typing import Dict, Any, Optional
from odoo.addons.jabin_core import BaseValidator


class CategoryValidator(BaseValidator):
    """
    Category validator using jabin_core BaseValidator infrastructure.
    Inherits all common validation methods.
    """

    # Constants for validation rules
    MIN_NAME_LENGTH = 2
    MAX_NAME_LENGTH = 255
    MAX_DEPTH = 10
    MAX_IMAGE_SIZE_MB = 5

    @staticmethod
    def validate_create(vals: Dict[str, Any]) -> None:
        """
        Validate category creation data.

        Args:
            vals: Dictionary of values to validate

        Raises:
            ValidationError: If validation fails
        """
        # Validate required fields
        CategoryValidator.validate_required_fields(vals, ['name'])

        # Validate name
        if 'name' in vals:
            CategoryValidator._validate_category_name(
                vals['name'],
                check_uniqueness=True,
                env=vals.get('_env')  # Pass env if available for uniqueness check
            )

        # Validate sequence
        if 'sequence' in vals:
            CategoryValidator.validate_positive_number(
                vals['sequence'],
                'Sequence',
                allow_zero=True
            )

        # Validate active boolean
        if 'active' in vals:
            CategoryValidator.validate_field_type(
                vals['active'],
                bool,
                'Active'
            )

        # Validate image if present
        if 'image' in vals and vals['image']:
            CategoryValidator._validate_image(vals['image'])

        # Validate parent category if present
        if 'parent_id' in vals and vals['parent_id']:
            CategoryValidator._validate_parent_exists(
                vals.get('_env'),
                vals['parent_id']
            )

    @staticmethod
    def validate_update(category, vals: Dict[str, Any]) -> None:
        """
        Validate category update data.

        Args:
            category: The category record being updated
            vals: Dictionary of values to validate

        Raises:
            ValidationError: If validation fails
        """
        # Validate name if present
        if 'name' in vals:
            CategoryValidator._validate_category_name(
                vals['name'],
                check_uniqueness=True,
                env=category.env,
                exclude_id=category.id
            )

        # Validate sequence if present
        if 'sequence' in vals:
            CategoryValidator.validate_positive_number(
                vals['sequence'],
                'Sequence',
                allow_zero=True
            )

        # Validate active if present
        if 'active' in vals:
            CategoryValidator.validate_field_type(
                vals['active'],
                bool,
                'Active'
            )

        # Validate image if present (not None)
        if 'image' in vals and vals['image'] is not None:
            CategoryValidator._validate_image(vals['image'])

        # Validate parent category if present
        if 'parent_id' in vals:
            if vals['parent_id']:
                CategoryValidator._validate_parent_category(
                    category,
                    vals['parent_id']
                )
            # If parent_id is False or None, it's valid (remove parent)

    @staticmethod
    def validate_delete(category) -> None:
        """
        Validate category deletion.

        Args:
            category: The category record to delete

        Raises:
            ValidationError: If validation fails
        """
        # Check if category has products
        if category.product_ids:
            product_names = category.product_ids.mapped('name')
            product_list = ', '.join(product_names[:5])
            if len(product_names) > 5:
                product_list += f' and {len(product_names) - 5} more...'

            raise ValidationError(
                _("Cannot delete category '%(name)s' because it has %(count)s product(s): %(products)s") % {
                    'name': category.name,
                    'count': len(category.product_ids),
                    'products': product_list
                }
            )

        # Check if category has child categories
        if category.child_ids:
            child_names = category.child_ids.mapped('name')
            child_list = ', '.join(child_names[:5])
            if len(child_names) > 5:
                child_list += f' and {len(child_names) - 5} more...'

            raise ValidationError(
                _("Cannot delete category '%(name)s' because it has %(count)s child category(ies): %(children)s") % {
                    'name': category.name,
                    'count': len(category.child_ids),
                    'children': child_list
                }
            )

    @staticmethod
    def validate_category_exists(env, category_id: int) -> None:
        """
        Validate that a category exists.

        Args:
            env: Odoo environment
            category_id: ID of category to check

        Raises:
            ValidationError: If category not found
        """
        if not category_id:
            raise ValidationError(_("Category ID is required."))

        CategoryValidator.validate_positive_number(category_id, 'Category ID')

        if not env['jabin.category'].sudo().browse(category_id).exists():
            raise ValidationError(_("Category not found."))

    @staticmethod
    def validate_bulk_operation(category_ids: list, env) -> None:
        """
        Validate categories for bulk operations.

        Args:
            category_ids: List of category IDs
            env: Odoo environment

        Raises:
            ValidationError: If validation fails
        """
        if not category_ids:
            raise ValidationError(_("No categories selected."))

        # Validate all categories exist
        categories = env['jabin.category'].sudo().browse(category_ids)
        if len(categories) != len(category_ids):
            raise ValidationError(_("One or more categories not found."))

        # Check for invalid operations (e.g., deleting categories with products)
        for category in categories:
            if category.product_ids:
                raise ValidationError(
                    _("Category '%(name)s' has products and cannot be processed.") % {
                        'name': category.name
                    }
                )

    # ------------------------------------------------------------------
    # Private helper methods
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_category_name(
            name: str,
            check_uniqueness: bool = False,
            env=None,
            exclude_id: Optional[int] = None
    ) -> None:
        """
        Validate category name with all rules.

        Args:
            name: Category name to validate
            check_uniqueness: Whether to check uniqueness in database
            env: Odoo environment for uniqueness check
            exclude_id: ID to exclude from uniqueness check

        Raises:
            ValidationError: If validation fails
        """
        # Validate string length
        CategoryValidator.validate_string_length(
            name,
            'Category Name',
            min_length=CategoryValidator.MIN_NAME_LENGTH,
            max_length=CategoryValidator.MAX_NAME_LENGTH
        )

        # Validate contains at least one alphanumeric character
        if not any(c.isalnum() for c in name):
            raise ValidationError(
                _("Category name must contain at least one alphanumeric character.")
            )

        # Validate no leading/trailing whitespace
        if name != name.strip():
            raise ValidationError(
                _("Category name cannot have leading or trailing spaces.")
            )

        # Validate no consecutive spaces (optional)
        if '  ' in name:
            raise ValidationError(
                _("Category name cannot contain consecutive spaces.")
            )

        # Check uniqueness if requested
        if check_uniqueness and env:
            CategoryValidator.validate_unique_field(
                env,
                'jabin.category',
                'name',
                name,
                exclude_id=exclude_id
            )

    @staticmethod
    def _validate_parent_category(category, parent_id: int) -> None:
        """
        Validate parent category assignment including circular reference check.

        Args:
            category: The category record
            parent_id: ID of the proposed parent category

        Raises:
            ValidationError: If validation fails
        """
        parent = category.env['jabin.category'].sudo().browse(parent_id)

        if not parent.exists():
            raise ValidationError(_("Parent category not found."))

        # Check if parent is the same category
        if parent.id == category.id:
            raise ValidationError(_("A category cannot be its own parent."))

        # Check for circular reference
        current = parent
        depth = 0

        while current.parent_id and depth < CategoryValidator.MAX_DEPTH:
            if current.parent_id.id == category.id:
                raise ValidationError(
                    _("Circular parent relationship detected.")
                )
            current = current.parent_id
            depth += 1

        # Check depth limit
        if depth >= CategoryValidator.MAX_DEPTH:
            raise ValidationError(
                _("Category hierarchy depth exceeds maximum allowed depth of %(max_depth)s.") % {
                    'max_depth': CategoryValidator.MAX_DEPTH
                }
            )

    @staticmethod
    def _validate_parent_exists(env, parent_id: int) -> None:
        """
        Validate that a parent category exists.

        Args:
            env: Odoo environment
            parent_id: ID of parent category

        Raises:
            ValidationError: If parent not found
        """
        if not env:
            return  # Can't validate without env

        parent = env['jabin.category'].sudo().browse(parent_id)
        if not parent.exists():
            raise ValidationError(_("Parent category not found."))

    @staticmethod
    def _validate_image(image_data: bytes) -> None:
        """
        Validate image data.

        Args:
            image_data: Binary image data

        Raises:
            ValidationError: If validation fails
        """
        if not image_data:
            return

        # Check if data is bytes
        CategoryValidator.validate_field_type(image_data, bytes, 'Image')

        # Check size (max 5MB)
        if len(image_data) > CategoryValidator.MAX_IMAGE_SIZE_MB * 1024 * 1024:
            raise ValidationError(
                _("Image size must not exceed %(size)d MB.") % {
                    'size': CategoryValidator.MAX_IMAGE_SIZE_MB
                }
            )

        # Optional: Check if it's a valid image by trying to detect format
        # This would require PIL or similar library
        # For now, we'll rely on the controller's MIME type validation

    # ------------------------------------------------------------------
    # Convenience validation methods for common scenarios
    # ------------------------------------------------------------------

    @staticmethod
    def validate_name_unique(env, name: str, exclude_id: Optional[int] = None) -> None:
        """
        Quick validation for unique category name.

        Args:
            env: Odoo environment
            name: Category name to check
            exclude_id: ID to exclude from check

        Raises:
            ValidationError: If name already exists
        """
        CategoryValidator.validate_unique_field(
            env,
            'jabin.category',
            'name',
            name,
            exclude_id=exclude_id
        )

    @staticmethod
    def validate_search_params(
            limit: Optional[int] = None,
            offset: Optional[int] = None,
            order: Optional[str] = None
    ) -> None:
        """
        Validate search/pagination parameters.

        Args:
            limit: Maximum number of records
            offset: Number of records to skip
            order: Sort order string

        Raises:
            ValidationError: If validation fails
        """
        if limit is not None:
            CategoryValidator.validate_positive_number(
                limit,
                'Limit',
                allow_zero=False
            )

        if offset is not None:
            CategoryValidator.validate_positive_number(
                offset,
                'Offset',
                allow_zero=True
            )

        if order is not None and not isinstance(order, str):
            raise ValidationError(_("Order must be a string."))
