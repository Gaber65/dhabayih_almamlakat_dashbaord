# packaging_validator.py
from odoo import _
from odoo.exceptions import ValidationError
from typing import Dict, Any, Optional
from odoo.addons.jabin_core import BaseValidator


class PackagingValidator(BaseValidator):
    """
    Packaging validator using jabin_core BaseValidator infrastructure.
    Inherits all common validation methods from BaseValidator.
    """

    # Constants for validation rules
    MIN_NAME_LENGTH = 2
    MAX_NAME_LENGTH = 100
    MAX_DESCRIPTION_LENGTH = 500

    @staticmethod
    def validate_create(vals: Dict[str, Any], env=None) -> None:
        """
        Validate packaging creation data.

        Args:
            vals: Dictionary of values to validate
            env: Odoo environment (required for uniqueness checks)

        Raises:
            ValidationError: If validation fails
        """
        # Validate required fields
        PackagingValidator.validate_required_fields(vals, ['name'])

        # Validate name (includes uniqueness check)
        if 'name' in vals:
            PackagingValidator._validate_packaging_name(
                vals['name'],
                check_uniqueness=True,
                env=env,  # Pass env as is - we'll use sudo() on the model
                exclude_id=None
            )

        # Validate active boolean if present
        if 'active' in vals:
            PackagingValidator.validate_field_type(
                vals['active'],
                bool,
                'Active'
            )

        # Validate description if present
        if 'description' in vals and vals['description']:
            PackagingValidator.validate_string_length(
                vals['description'],
                'Description',
                max_length=PackagingValidator.MAX_DESCRIPTION_LENGTH
            )

    @staticmethod
    def validate_update(packaging, vals: Dict[str, Any]) -> None:
        """
        Validate packaging update data.

        Args:
            packaging: The packaging record being updated
            vals: Dictionary of values to validate

        Raises:
            ValidationError: If validation fails
        """
        # Validate name if present
        if 'name' in vals:
            PackagingValidator._validate_packaging_name(
                vals['name'],
                check_uniqueness=True,
                env=packaging.env,  # Pass env as is
                exclude_id=packaging.id
            )

        # Validate active if present
        if 'active' in vals:
            PackagingValidator.validate_field_type(
                vals['active'],
                bool,
                'Active'
            )

        # Validate description if present
        if 'description' in vals and vals['description']:
            PackagingValidator.validate_string_length(
                vals['description'],
                'Description',
                max_length=PackagingValidator.MAX_DESCRIPTION_LENGTH
            )

    @staticmethod
    def validate_delete(packaging) -> None:
        """
        Validate packaging deletion.

        Args:
            packaging: The packaging record to delete

        Raises:
            ValidationError: If validation fails
        """
        # Check if packaging has products
        if packaging.product_ids:
            product_names = packaging.product_ids.mapped('name')
            product_list = ', '.join(product_names[:5])
            if len(product_names) > 5:
                product_list += f' and {len(product_names) - 5} more...'

            raise ValidationError(
                _("Cannot delete packaging '%(name)s' because it has %(count)s product(s): %(products)s") % {
                    'name': packaging.name,
                    'count': len(packaging.product_ids),
                    'products': product_list
                }
            )

    @staticmethod
    def validate_packaging_exists(env, packaging_id: int) -> None:
        """
        Validate that packaging exists.

        Args:
            env: Odoo environment
            packaging_id: ID of packaging to check

        Raises:
            ValidationError: If packaging not found
        """
        if not packaging_id:
            raise ValidationError(_("Packaging ID is required."))

        PackagingValidator.validate_positive_number(packaging_id, 'Packaging ID')

        # ✅ CORRECT: Use sudo() on the model
        if not env['jabin.packaging'].sudo().browse(packaging_id).exists():
            raise ValidationError(_("Packaging not found."))

    @staticmethod
    def validate_bulk_operation(packaging_ids: list, env) -> None:
        """
        Validate packagings for bulk operations.

        Args:
            packaging_ids: List of packaging IDs
            env: Odoo environment

        Raises:
            ValidationError: If validation fails
        """
        if not packaging_ids:
            raise ValidationError(_("No packagings selected."))

        # ✅ CORRECT: Use sudo() on the model
        packagings = env['jabin.packaging'].sudo().browse(packaging_ids)
        if len(packagings) != len(packaging_ids):
            raise ValidationError(_("One or more packagings not found."))

        # Check for invalid operations
        for packaging in packagings:
            if packaging.product_ids:
                raise ValidationError(
                    _("Packaging '%(name)s' has products and cannot be processed.") % {
                        'name': packaging.name
                    }
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
            PackagingValidator.validate_positive_number(
                limit,
                'Limit',
                allow_zero=False
            )

        if offset is not None:
            PackagingValidator.validate_positive_number(
                offset,
                'Offset',
                allow_zero=True
            )

        if order is not None and not isinstance(order, str):
            raise ValidationError(_("Order must be a string."))

    # ------------------------------------------------------------------
    # Private helper methods
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_packaging_name(
            name: str,
            check_uniqueness: bool = False,
            env=None,
            exclude_id: Optional[int] = None
    ) -> None:
        """
        Validate packaging name with all rules.

        Args:
            name: Packaging name to validate
            check_uniqueness: Whether to check uniqueness in database
            env: Odoo environment for uniqueness check
            exclude_id: ID to exclude from uniqueness check

        Raises:
            ValidationError: If validation fails
        """
        # Validate string length
        PackagingValidator.validate_string_length(
            name,
            'Packaging Name',
            min_length=PackagingValidator.MIN_NAME_LENGTH,
            max_length=PackagingValidator.MAX_NAME_LENGTH
        )

        # Validate contains at least one alphanumeric character
        if not any(c.isalnum() for c in name):
            raise ValidationError(
                _("Packaging name must contain at least one alphanumeric character.")
            )

        # Validate no leading/trailing whitespace
        if name != name.strip():
            raise ValidationError(
                _("Packaging name cannot have leading or trailing spaces.")
            )

        # Validate no consecutive spaces
        if '  ' in name:
            raise ValidationError(
                _("Packaging name cannot contain consecutive spaces.")
            )

        # ✅ CORRECT: Use sudo() on the model in the uniqueness check
        if check_uniqueness and env:
            # Use sudo() on the model, not on the environment
            model = env['jabin.packaging'].sudo()
            domain = [('name', '=', name)]
            if exclude_id:
                domain.append(('id', '!=', exclude_id))

            if model.search_count(domain) > 0:
                raise ValidationError(
                    _("Packaging name must be unique!")
                )

    # ------------------------------------------------------------------
    # Convenience validation methods for common scenarios
    # ------------------------------------------------------------------

    @staticmethod
    def validate_name_unique(env, name: str, exclude_id: Optional[int] = None) -> None:
        """
        Quick validation for unique packaging name.

        Args:
            env: Odoo environment
            name: Packaging name to check
            exclude_id: ID to exclude from check

        Raises:
            ValidationError: If name already exists
        """
        # ✅ CORRECT: Use sudo() on the model
        model = env['jabin.packaging'].sudo()
        domain = [('name', '=', name)]
        if exclude_id:
            domain.append(('id', '!=', exclude_id))

        if model.search_count(domain) > 0:
            raise ValidationError(
                _("Packaging name must be unique!")
            )