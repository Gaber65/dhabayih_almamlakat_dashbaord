# cutting_option_service.py
from odoo import _, fields
from odoo.exceptions import ValidationError, AccessError

from ..validators.cutting_option_validator import CuttingOptionValidator


class CuttingOptionService:
    """Cutting Option business logic service layer."""

    @staticmethod
    def create_cutting_option(env, vals):
        """
        Create a new cutting option.

        Args:
            env: Odoo environment
            vals: Dictionary of cutting option values

        Returns:
            jabin.cutting.option: The created cutting option record

        Raises:
            ValidationError: If validation fails
            AccessError: If user lacks permissions
        """
        # Validate input
        CuttingOptionValidator.validate_create(vals)

        # Create cutting option
        cutting_option = env["jabin.cutting.option"].sudo().create(vals)

        return cutting_option

    @staticmethod
    def update_cutting_option(env, option_id, vals):
        """
        Update an existing cutting option.

        Args:
            env: Odoo environment
            option_id: ID of cutting option to update
            vals: Dictionary of values to update

        Returns:
            jabin.cutting.option: The updated cutting option record

        Raises:
            ValidationError: If validation fails or record not found
            AccessError: If user lacks permissions
        """
        # Find the cutting option
        cutting_option = env["jabin.cutting.option"].sudo().browse(option_id)

        if not cutting_option.exists():
            raise ValidationError(_("Cutting option not found."))

        # Validate update
        CuttingOptionValidator.validate_update(cutting_option, vals)

        # Perform update
        cutting_option.write(vals)

        return cutting_option

    @staticmethod
    def delete_cutting_option(env, option_id):
        """
        Delete a cutting option.

        Args:
            env: Odoo environment
            option_id: ID of cutting option to delete

        Returns:
            bool: True if deletion succeeded

        Raises:
            ValidationError: If record not found or has products
            AccessError: If user lacks permissions
        """
        # Find the cutting option
        cutting_option = env["jabin.cutting.option"].sudo().browse(option_id)

        if not cutting_option.exists():
            raise ValidationError(_("Cutting option not found."))

        # Check for products (business rule)
        if cutting_option.product_ids:
            raise ValidationError(
                _("Cannot delete cutting option with existing products.")
            )

        # Perform deletion
        cutting_option.unlink()

        return True

    @staticmethod
    def get_cutting_option(env, option_id, lang=None):
        """
        Get a single cutting option by ID.

        Args:
            env: Odoo environment
            option_id: ID of cutting option to retrieve
            lang: Language code for translations

        Returns:
            jabin.cutting.option: The cutting option record

        Raises:
            ValidationError: If record not found
        """
        cutting_option = (
            env["jabin.cutting.option"]
            .sudo()
            .with_context(lang=lang)
            .browse(option_id)
        )

        if not cutting_option.exists():
            raise ValidationError(_("Cutting option not found."))

        return cutting_option

    @staticmethod
    def get_cutting_options(
            env,
            domain=None,
            limit=None,
            offset=None,
            order=None,
            lang=None,
    ):
        """
        Get a list of cutting options with pagination.

        Args:
            env: Odoo environment
            domain: Search domain
            limit: Maximum number of records
            offset: Number of records to skip
            order: Sort order
            lang: Language code for translations

        Returns:
            jabin.cutting.option: Recordset of cutting options
        """
        return (
            env["jabin.cutting.option"]
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
    def get_cutting_option_by_name(env, name, lang=None):
        """
        Get a cutting option by name.

        Args:
            env: Odoo environment
            name: Cutting option name
            lang: Language code for translations

        Returns:
            jabin.cutting.option: The cutting option record

        Raises:
            ValidationError: If record not found
        """
        cutting_option = (
            env["jabin.cutting.option"]
            .sudo()
            .with_context(lang=lang)
            .search([("name", "=", name)], limit=1)
        )

        if not cutting_option:
            raise ValidationError(_("Cutting option not found."))

        return cutting_option

    @staticmethod
    def check_cutting_option_exists(env, option_id):
        """
        Check if a cutting option exists.

        Args:
            env: Odoo environment
            option_id: ID of cutting option to check

        Returns:
            bool: True if cutting option exists

        Raises:
            ValidationError: If record not found
        """
        exists = env["jabin.cutting.option"].sudo().browse(option_id).exists()

        if not exists:
            raise ValidationError(_("Cutting option not found."))

        return True

    @staticmethod
    def toggle_cutting_option_active(env, option_id):
        """
        Toggle active status of a cutting option.

        Args:
            env: Odoo environment
            option_id: ID of cutting option

        Returns:
            jabin.cutting.option: The updated cutting option record

        Raises:
            ValidationError: If record not found
            AccessError: If user lacks permissions
        """
        cutting_option = env["jabin.cutting.option"].sudo().browse(option_id)

        if not cutting_option.exists():
            raise ValidationError(_("Cutting option not found."))

        cutting_option.write({"active": not cutting_option.active})

        return cutting_option