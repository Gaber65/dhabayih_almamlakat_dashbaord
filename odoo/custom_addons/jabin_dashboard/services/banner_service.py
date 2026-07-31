# banner_service.py
from odoo import _
from odoo.exceptions import ValidationError, AccessError

from ..validators.banner_validator import BannerValidator


class BannerService:
    """Banner business logic service layer."""

    @staticmethod
    def create_banner(env, vals):
        """
        Create a new banner.

        Args:
            env: Odoo environment
            vals: Dictionary of banner values

        Returns:
            banner: The created banner record

        Raises:
            ValidationError: If validation fails
            AccessError: If user lacks permissions
        """
        # Validate input
        BannerValidator.validate_create(vals)

        # Create banner
        banner = env["banner"].sudo().create(vals)

        return banner

    @staticmethod
    def update_banner(env, banner_id, vals):
        """
        Update an existing banner.

        Args:
            env: Odoo environment
            banner_id: ID of banner to update
            vals: Dictionary of values to update

        Returns:
            banner: The updated banner record

        Raises:
            ValidationError: If validation fails or record not found
            AccessError: If user lacks permissions
        """
        # Find the banner
        banner = env["banner"].sudo().browse(banner_id)

        if not banner.exists():
            raise ValidationError(_("Banner not found."))

        # Validate update
        BannerValidator.validate_update(banner, vals)

        # Perform update
        banner.write(vals)

        return banner

    @staticmethod
    def delete_banner(env, banner_id):
        """
        Delete a banner.

        Args:
            env: Odoo environment
            banner_id: ID of banner to delete

        Returns:
            bool: True if deletion succeeded

        Raises:
            ValidationError: If record not found
            AccessError: If user lacks permissions
        """
        # Find the banner
        banner = env["banner"].sudo().browse(banner_id)

        if not banner.exists():
            raise ValidationError(_("Banner not found."))

        # Perform deletion
        banner.unlink()

        return True

    @staticmethod
    def get_banner(env, banner_id, lang=None):
        """
        Get a single banner by ID.

        Args:
            env: Odoo environment
            banner_id: ID of banner to retrieve
            lang: Language code for translations

        Returns:
            banner: The banner record

        Raises:
            ValidationError: If record not found
        """
        banner = (
            env["banner"]
            .sudo()
            .with_context(lang=lang)
            .browse(banner_id)
        )

        if not banner.exists():
            raise ValidationError(_("Banner not found."))

        return banner

    @staticmethod
    def get_banners(
            env,
            domain=None,
            limit=None,
            offset=None,
            order=None,
            lang=None,
    ):
        """
        Get a list of banners with pagination.

        Args:
            env: Odoo environment
            domain: Search domain
            limit: Maximum number of records
            offset: Number of records to skip
            order: Sort order
            lang: Language code for translations

        Returns:
            banner: Recordset of banners
        """
        return (
            env["banner"]
            .sudo()
            .with_context(lang=lang)
            .search(
                domain or [],
                limit=limit or 100,
                offset=offset or 0,
                order=order or "name",
            )
        )

    @staticmethod
    def get_banner_by_name(env, name, lang=None):
        """
        Get a banner by name.

        Args:
            env: Odoo environment
            name: Banner name
            lang: Language code for translations

        Returns:
            banner: The banner record

        Raises:
            ValidationError: If record not found
        """
        banner = (
            env["banner"]
            .sudo()
            .with_context(lang=lang)
            .search([("name", "=", name)], limit=1)
        )

        if not banner:
            raise ValidationError(_("Banner not found."))

        return banner

    @staticmethod
    def check_banner_exists(env, banner_id):
        """
        Check if a banner exists.

        Args:
            env: Odoo environment
            banner_id: ID of banner to check

        Returns:
            bool: True if banner exists

        Raises:
            ValidationError: If record not found
        """
        exists = env["banner"].sudo().browse(banner_id).exists()

        if not exists:
            raise ValidationError(_("Banner not found."))

        return True

    @staticmethod
    def toggle_banner_active(env, banner_id):
        """
        Toggle active status of a banner.

        Args:
            env: Odoo environment
            banner_id: ID of banner

        Returns:
            banner: The updated banner record

        Raises:
            ValidationError: If record not found
            AccessError: If user lacks permissions
        """
        banner = env["banner"].sudo().browse(banner_id)

        if not banner.exists():
            raise ValidationError(_("Banner not found."))

        banner.write({"active": not banner.active})

        return banner