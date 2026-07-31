# banner_validator.py
from odoo import _
from odoo.exceptions import ValidationError
from typing import Dict, Any, Optional
from odoo.addons.jabin_core import BaseValidator


class BannerValidator(BaseValidator):
    """
    Banner validator using jabin_core BaseValidator infrastructure.
    Inherits all common validation methods.
    """

    # Constants for validation rules
    MIN_NAME_LENGTH = 2
    MAX_NAME_LENGTH = 255
    MAX_IMAGE_SIZE_MB = 5

    @staticmethod
    def validate_create(vals: Dict[str, Any]) -> None:
        """
        Validate banner creation data.

        Args:
            vals: Dictionary of values to validate

        Raises:
            ValidationError: If validation fails
        """
        # Validate required fields
        BannerValidator.validate_required_fields(vals, ['name'])

        # Validate name
        if 'name' in vals:
            BannerValidator._validate_banner_name(
                vals['name'],
                check_uniqueness=True,
                env=vals.get('_env')  # Pass env if available for uniqueness check
            )

        # Validate active boolean
        if 'active' in vals:
            BannerValidator.validate_field_type(
                vals['active'],
                bool,
                'Active'
            )

        # Validate image if present
        if 'image' in vals and vals['image']:
            BannerValidator._validate_image(vals['image'])

    @staticmethod
    def validate_update(banner, vals: Dict[str, Any]) -> None:
        """
        Validate banner update data.

        Args:
            banner: The banner record being updated
            vals: Dictionary of values to validate

        Raises:
            ValidationError: If validation fails
        """
        # Validate name if present
        if 'name' in vals:
            BannerValidator._validate_banner_name(
                vals['name'],
                check_uniqueness=True,
                env=banner.env,
                exclude_id=banner.id
            )

        # Validate active if present
        if 'active' in vals:
            BannerValidator.validate_field_type(
                vals['active'],
                bool,
                'Active'
            )

        # Validate image if present (not None)
        if 'image' in vals and vals['image'] is not None:
            BannerValidator._validate_image(vals['image'])

    @staticmethod
    def validate_delete(banner) -> None:
        """
        Validate banner deletion.

        Args:
            banner: The banner record to delete

        Raises:
            ValidationError: If validation fails
        """
        # Check if banner is active (optional business rule)
        # You can add additional checks here if needed
        pass

    @staticmethod
    def validate_banner_exists(env, banner_id: int) -> None:
        """
        Validate that a banner exists.

        Args:
            env: Odoo environment
            banner_id: ID of banner to check

        Raises:
            ValidationError: If banner not found
        """
        if not banner_id:
            raise ValidationError(_("Banner ID is required."))

        BannerValidator.validate_positive_number(banner_id, 'Banner ID')

        if not env['banner'].sudo().browse(banner_id).exists():
            raise ValidationError(_("Banner not found."))

    @staticmethod
    def validate_bulk_operation(banner_ids: list, env) -> None:
        """
        Validate banners for bulk operations.

        Args:
            banner_ids: List of banner IDs
            env: Odoo environment

        Raises:
            ValidationError: If validation fails
        """
        if not banner_ids:
            raise ValidationError(_("No banners selected."))

        # Validate all banners exist
        banners = env['banner'].sudo().browse(banner_ids)
        if len(banners) != len(banner_ids):
            raise ValidationError(_("One or more banners not found."))

    # ------------------------------------------------------------------
    # Private helper methods
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_banner_name(
            name: str,
            check_uniqueness: bool = False,
            env=None,
            exclude_id: Optional[int] = None
    ) -> None:
        """
        Validate banner name with all rules.

        Args:
            name: Banner name to validate
            check_uniqueness: Whether to check uniqueness in database
            env: Odoo environment for uniqueness check
            exclude_id: ID to exclude from uniqueness check

        Raises:
            ValidationError: If validation fails
        """
        # Validate string length
        BannerValidator.validate_string_length(
            name,
            'Banner Name',
            min_length=BannerValidator.MIN_NAME_LENGTH,
            max_length=BannerValidator.MAX_NAME_LENGTH
        )

        # Validate contains at least one alphanumeric character
        if not any(c.isalnum() for c in name):
            raise ValidationError(
                _("Banner name must contain at least one alphanumeric character.")
            )

        # Validate no leading/trailing whitespace
        if name != name.strip():
            raise ValidationError(
                _("Banner name cannot have leading or trailing spaces.")
            )

        # Validate no consecutive spaces (optional)
        if '  ' in name:
            raise ValidationError(
                _("Banner name cannot contain consecutive spaces.")
            )

        # Check uniqueness if requested
        if check_uniqueness and env:
            BannerValidator.validate_unique_field(
                env,
                'banner',
                'name',
                name,
                exclude_id=exclude_id
            )

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
        BannerValidator.validate_field_type(image_data, bytes, 'Image')

        # Check size (max 5MB)
        if len(image_data) > BannerValidator.MAX_IMAGE_SIZE_MB * 1024 * 1024:
            raise ValidationError(
                _("Image size must not exceed %(size)d MB.") % {
                    'size': BannerValidator.MAX_IMAGE_SIZE_MB
                }
            )

    # ------------------------------------------------------------------
    # Convenience validation methods for common scenarios
    # ------------------------------------------------------------------

    @staticmethod
    def validate_name_unique(env, name: str, exclude_id: Optional[int] = None) -> None:
        """
        Quick validation for unique banner name.

        Args:
            env: Odoo environment
            name: Banner name to check
            exclude_id: ID to exclude from check

        Raises:
            ValidationError: If name already exists
        """
        BannerValidator.validate_unique_field(
            env,
            'banner',
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
            BannerValidator.validate_positive_number(
                limit,
                'Limit',
                allow_zero=False
            )

        if offset is not None:
            BannerValidator.validate_positive_number(
                offset,
                'Offset',
                allow_zero=True
            )

        if order is not None and not isinstance(order, str):
            raise ValidationError(_("Order must be a string."))