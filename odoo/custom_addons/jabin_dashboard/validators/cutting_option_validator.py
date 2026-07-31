# cutting_option_validator.py
from odoo import _
from odoo.exceptions import ValidationError
from typing import Dict, Any, Optional
from odoo.addons.jabin_core import BaseValidator


class CuttingOptionValidator(BaseValidator):
    """
    Cutting Option validator using jabin_core BaseValidator infrastructure.
    Inherits all common validation methods from BaseValidator.
    """

    # Constants for validation rules
    MIN_NAME_LENGTH = 2
    MAX_NAME_LENGTH = 100
    MAX_DESCRIPTION_LENGTH = 500

    @staticmethod
    def validate_create(vals: Dict[str, Any], env=None) -> None:
        """
        Validate cutting option creation data.

        Args:
            vals: Dictionary of values to validate
            env: Odoo environment (required for uniqueness checks)

        Raises:
            ValidationError: If validation fails
        """
        # Validate required fields
        CuttingOptionValidator.validate_required_fields(vals, ['name'])

        # Validate name (includes uniqueness check)
        if 'name' in vals:
            CuttingOptionValidator._validate_cutting_option_name(
                vals['name'],
                check_uniqueness=True,
                env=env,  # Pass env directly
                exclude_id=None
            )

        # Validate active boolean if present
        if 'active' in vals:
            CuttingOptionValidator.validate_field_type(
                vals['active'],
                bool,
                'Active'
            )

        # Validate description if present
        if 'description' in vals and vals['description']:
            CuttingOptionValidator.validate_string_length(
                vals['description'],
                'Description',
                max_length=CuttingOptionValidator.MAX_DESCRIPTION_LENGTH
            )

    @staticmethod
    def validate_update(cutting_option, vals: Dict[str, Any]) -> None:
        """
        Validate cutting option update data.

        Args:
            cutting_option: The cutting option record being updated
            vals: Dictionary of values to validate

        Raises:
            ValidationError: If validation fails
        """
        # Validate name if present
        if 'name' in vals:
            CuttingOptionValidator._validate_cutting_option_name(
                vals['name'],
                check_uniqueness=True,
                env=cutting_option.env,
                exclude_id=cutting_option.id
            )

        # Validate active if present
        if 'active' in vals:
            CuttingOptionValidator.validate_field_type(
                vals['active'],
                bool,
                'Active'
            )

        # Validate description if present
        if 'description' in vals and vals['description']:
            CuttingOptionValidator.validate_string_length(
                vals['description'],
                'Description',
                max_length=CuttingOptionValidator.MAX_DESCRIPTION_LENGTH
            )

    @staticmethod
    def validate_delete(cutting_option) -> None:
        """
        Validate cutting option deletion.

        Args:
            cutting_option: The cutting option record to delete

        Raises:
            ValidationError: If validation fails
        """
        # Check if cutting option has products
        if cutting_option.product_ids:
            product_names = cutting_option.product_ids.mapped('name')
            product_list = ', '.join(product_names[:5])
            if len(product_names) > 5:
                product_list += f' and {len(product_names) - 5} more...'

            raise ValidationError(
                _("Cannot delete cutting option '%(name)s' because it has %(count)s product(s): %(products)s") % {
                    'name': cutting_option.name,
                    'count': len(cutting_option.product_ids),
                    'products': product_list
                }
            )

    @staticmethod
    def validate_cutting_option_exists(env, option_id: int) -> None:
        """
        Validate that a cutting option exists.

        Args:
            env: Odoo environment
            option_id: ID of cutting option to check

        Raises:
            ValidationError: If cutting option not found
        """
        if not option_id:
            raise ValidationError(_("Cutting option ID is required."))

        CuttingOptionValidator.validate_positive_number(option_id, 'Cutting Option ID')

        if not env['jabin.cutting.option'].sudo().browse(option_id).exists():
            raise ValidationError(_("Cutting option not found."))

    @staticmethod
    def validate_bulk_operation(option_ids: list, env) -> None:
        """
        Validate cutting options for bulk operations.

        Args:
            option_ids: List of cutting option IDs
            env: Odoo environment

        Raises:
            ValidationError: If validation fails
        """
        if not option_ids:
            raise ValidationError(_("No cutting options selected."))

        # Validate all cutting options exist
        options = env['jabin.cutting.option'].sudo().browse(option_ids)
        if len(options) != len(option_ids):
            raise ValidationError(_("One or more cutting options not found."))

        # Check for invalid operations
        for option in options:
            if option.product_ids:
                raise ValidationError(
                    _("Cutting option '%(name)s' has products and cannot be processed.") % {
                        'name': option.name
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
            CuttingOptionValidator.validate_positive_number(
                limit,
                'Limit',
                allow_zero=False
            )

        if offset is not None:
            CuttingOptionValidator.validate_positive_number(
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
    def _validate_cutting_option_name(
            name: str,
            check_uniqueness: bool = False,
            env=None,
            exclude_id: Optional[int] = None
    ) -> None:
        """
        Validate cutting option name with all rules.

        Args:
            name: Cutting option name to validate
            check_uniqueness: Whether to check uniqueness in database
            env: Odoo environment for uniqueness check
            exclude_id: ID to exclude from uniqueness check

        Raises:
            ValidationError: If validation fails
        """
        # Validate string length
        CuttingOptionValidator.validate_string_length(
            name,
            'Cutting Option Name',
            min_length=CuttingOptionValidator.MIN_NAME_LENGTH,
            max_length=CuttingOptionValidator.MAX_NAME_LENGTH
        )

        # Validate contains at least one alphanumeric character
        if not any(c.isalnum() for c in name):
            raise ValidationError(
                _("Cutting option name must contain at least one alphanumeric character.")
            )

        # Validate no leading/trailing whitespace
        if name != name.strip():
            raise ValidationError(
                _("Cutting option name cannot have leading or trailing spaces.")
            )

        # Validate no consecutive spaces
        if '  ' in name:
            raise ValidationError(
                _("Cutting option name cannot contain consecutive spaces.")
            )

        # Check uniqueness if requested
        if check_uniqueness and env:
            CuttingOptionValidator.validate_unique_field(
                env,
                'jabin.cutting.option',
                'name',
                name,
                exclude_id=exclude_id
            )

    # ------------------------------------------------------------------
    # Convenience validation methods for common scenarios
    # ------------------------------------------------------------------

    @staticmethod
    def validate_name_unique(env, name: str, exclude_id: Optional[int] = None) -> None:
        """
        Quick validation for unique cutting option name.

        Args:
            env: Odoo environment
            name: Cutting option name to check
            exclude_id: ID to exclude from check

        Raises:
            ValidationError: If name already exists
        """
        CuttingOptionValidator.validate_unique_field(
            env,
            'jabin.cutting.option',
            'name',
            name,
            exclude_id=exclude_id
        )