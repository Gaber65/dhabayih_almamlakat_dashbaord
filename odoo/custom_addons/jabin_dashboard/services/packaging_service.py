# packaging_service.py
from odoo import _, fields
from odoo.exceptions import ValidationError, AccessError

from ..validators.packaging_validator import PackagingValidator


class PackagingService:
    """Packaging business logic service layer."""

    @staticmethod
    def create_packaging(env, vals):
        """
        Create new packaging.

        Args:
            env: Odoo environment
            vals: Dictionary of packaging values

        Returns:
            jabin.packaging: The created packaging record

        Raises:
            ValidationError: If validation fails
            AccessError: If user lacks permissions
        """
        # Validate input - PASS ENV FOR UNIQUENESS CHECK
        PackagingValidator.validate_create(vals, env=env)

        # Create packaging
        packaging = env["jabin.packaging"].sudo().create(vals)

        return packaging

    @staticmethod
    def update_packaging(env, packaging_id, vals):
        """
        Update existing packaging.

        Args:
            env: Odoo environment
            packaging_id: ID of packaging to update
            vals: Dictionary of values to update

        Returns:
            jabin.packaging: The updated packaging record

        Raises:
            ValidationError: If validation fails or record not found
            AccessError: If user lacks permissions
        """
        # Find the packaging
        packaging = env["jabin.packaging"].sudo().browse(packaging_id)

        if not packaging.exists():
            raise ValidationError(_("Packaging not found."))

        # Validate update
        PackagingValidator.validate_update(packaging, vals)

        # Perform update
        packaging.write(vals)

        return packaging

    @staticmethod
    def delete_packaging(env, packaging_id):
        """
        Delete packaging.

        Args:
            env: Odoo environment
            packaging_id: ID of packaging to delete

        Returns:
            bool: True if deletion succeeded

        Raises:
            ValidationError: If record not found or has products
            AccessError: If user lacks permissions
        """
        # Find the packaging
        packaging = env["jabin.packaging"].sudo().browse(packaging_id)

        if not packaging.exists():
            raise ValidationError(_("Packaging not found."))

        # Validate deletion
        PackagingValidator.validate_delete(packaging)

        # Perform deletion
        packaging.unlink()

        return True

    @staticmethod
    def get_packaging(env, packaging_id, lang=None):
        """
        Get a single packaging by ID.

        Args:
            env: Odoo environment
            packaging_id: ID of packaging to retrieve
            lang: Language code for translations

        Returns:
            jabin.packaging: The packaging record

        Raises:
            ValidationError: If record not found
        """
        packaging = (
            env["jabin.packaging"]
            .sudo()
            .with_context(lang=lang)
            .browse(packaging_id)
        )

        if not packaging.exists():
            raise ValidationError(_("Packaging not found."))

        return packaging

    @staticmethod
    def get_packagings(
            env,
            domain=None,
            limit=None,
            offset=None,
            order=None,
            lang=None,
    ):
        """
        Get a list of packagings with pagination.

        Args:
            env: Odoo environment
            domain: Search domain
            limit: Maximum number of records
            offset: Number of records to skip
            order: Sort order
            lang: Language code for translations

        Returns:
            jabin.packaging: Recordset of packagings
        """
        return (
            env["jabin.packaging"]
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
    def get_packaging_by_name(env, name, lang=None):
        """
        Get packaging by name.

        Args:
            env: Odoo environment
            name: Packaging name
            lang: Language code for translations

        Returns:
            jabin.packaging: The packaging record

        Raises:
            ValidationError: If record not found
        """
        packaging = (
            env["jabin.packaging"]
            .sudo()
            .with_context(lang=lang)
            .search([("name", "=", name)], limit=1)
        )

        if not packaging:
            raise ValidationError(_("Packaging not found."))

        return packaging

    @staticmethod
    def check_packaging_exists(env, packaging_id):
        """
        Check if packaging exists.

        Args:
            env: Odoo environment
            packaging_id: ID of packaging to check

        Returns:
            bool: True if packaging exists

        Raises:
            ValidationError: If record not found
        """
        exists = env["jabin.packaging"].sudo().browse(packaging_id).exists()

        if not exists:
            raise ValidationError(_("Packaging not found."))

        return True

    @staticmethod
    def toggle_packaging_active(env, packaging_id):
        """
        Toggle active status of packaging.

        Args:
            env: Odoo environment
            packaging_id: ID of packaging

        Returns:
            jabin.packaging: The updated packaging record

        Raises:
            ValidationError: If record not found
            AccessError: If user lacks permissions
        """
        packaging = env["jabin.packaging"].sudo().browse(packaging_id)

        if not packaging.exists():
            raise ValidationError(_("Packaging not found."))

        packaging.write({"active": not packaging.active})

        return packaging