# excluded_part_validator.py
from odoo import _
from odoo.exceptions import ValidationError
from typing import Dict, Any, Optional


class ExcludedPartValidator:
    """
    Excluded Part validator following Category module standards.
    All validation methods are static and focused on data integrity.
    """

    # Constants for validation rules
    MIN_NAME_LENGTH = 2
    MAX_NAME_LENGTH = 100
    MAX_DESCRIPTION_LENGTH = 500

    @staticmethod
    def validate_create(vals: Dict[str, Any]) -> None:
        """
        Validate excluded part creation data.

        Args:
            vals: Dictionary of values to validate

        Raises:
            ValidationError: If validation fails
        """
        # Validate required fields
        ExcludedPartValidator._validate_required_fields(vals, ['name'])

        # Validate name
        if 'name' in vals:
            ExcludedPartValidator._validate_name(vals['name'])

        # Validate active boolean if present
        if 'active' in vals:
            ExcludedPartValidator._validate_boolean(vals['active'], 'Active')

        # Validate description if present
        if 'description' in vals and vals['description']:
            ExcludedPartValidator._validate_string_length(
                vals['description'],
                'Description',
                max_length=ExcludedPartValidator.MAX_DESCRIPTION_LENGTH
            )

    @staticmethod
    def validate_update(vals: Dict[str, Any]) -> None:
        """
        Validate excluded part update data.

        Args:
            vals: Dictionary of values to validate

        Raises:
            ValidationError: If validation fails
        """
        # Validate name if present
        if 'name' in vals:
            ExcludedPartValidator._validate_name(vals['name'])

        # Validate active if present
        if 'active' in vals:
            ExcludedPartValidator._validate_boolean(vals['active'], 'Active')

        # Validate description if present
        if 'description' in vals and vals['description']:
            ExcludedPartValidator._validate_string_length(
                vals['description'],
                'Description',
                max_length=ExcludedPartValidator.MAX_DESCRIPTION_LENGTH
            )

    @staticmethod
    def validate_delete(excluded_part) -> None:
        """
        Validate excluded part deletion.

        Args:
            excluded_part: The excluded part record to delete

        Raises:
            ValidationError: If validation fails
        """
        # Check if excluded part has products
        if excluded_part.product_ids:
            product_names = excluded_part.product_ids.mapped('name')
            product_list = ', '.join(product_names[:5])
            if len(product_names) > 5:
                product_list += f' and {len(product_names) - 5} more...'

            raise ValidationError(
                _("Cannot delete excluded part '%(name)s' because it has %(count)s product(s): %(products)s") % {
                    'name': excluded_part.name,
                    'count': len(excluded_part.product_ids),
                    'products': product_list
                }
            )

    @staticmethod
    def validate_exists(excluded_part) -> None:
        """
        Validate that an excluded part record exists.

        Args:
            excluded_part: The excluded part record to check

        Raises:
            ValidationError: If record doesn't exist
        """
        if not excluded_part or not excluded_part.exists():
            raise ValidationError(_("Excluded part not found."))

    @staticmethod
    def validate_unique_name(env, name: str, exclude_id: Optional[int] = None) -> None:
        """
        Validate that an excluded part name is unique.

        Args:
            env: Odoo environment
            name: Excluded part name to check
            exclude_id: ID to exclude from check

        Raises:
            ValidationError: If name already exists
        """
        domain = [('name', '=', name)]
        if exclude_id:
            domain.append(('id', '!=', exclude_id))

        if env['jabin.excluded.part'].sudo().search_count(domain) > 0:
            raise ValidationError(
                _("Excluded part name must be unique! '%(name)s' already exists.") % {
                    'name': name
                }
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
        Validate excluded part name with all rules.

        Args:
            name: Excluded part name to validate

        Raises:
            ValidationError: If validation fails
        """
        # Validate string length
        ExcludedPartValidator._validate_string_length(
            name,
            'Excluded Part Name',
            min_length=ExcludedPartValidator.MIN_NAME_LENGTH,
            max_length=ExcludedPartValidator.MAX_NAME_LENGTH
        )

        # Validate contains at least one alphanumeric character
        if not any(c.isalnum() for c in name):
            raise ValidationError(
                _("Excluded part name must contain at least one alphanumeric character.")
            )

        # Validate no leading/trailing whitespace
        if name != name.strip():
            raise ValidationError(
                _("Excluded part name cannot have leading or trailing spaces.")
            )

        # Validate no consecutive spaces
        if '  ' in name:
            raise ValidationError(
                _("Excluded part name cannot contain consecutive spaces.")
            )

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