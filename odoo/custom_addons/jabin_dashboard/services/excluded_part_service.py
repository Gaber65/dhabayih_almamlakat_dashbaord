# excluded_part_service.py
from odoo import _
from odoo.exceptions import ValidationError

from ..validators.excluded_part_validator import ExcludedPartValidator


class ExcludedPartService:
    """
    Excluded Part business logic service layer.
    Following Category module architecture standards.
    """

    @staticmethod
    def create(env, vals):
        """
        Create a new excluded part.

        Args:
            env: Odoo environment
            vals: Dictionary of excluded part values

        Returns:
            jabin.excluded.part: The created excluded part record

        Raises:
            ValidationError: If validation fails
        """
        # Validate input
        ExcludedPartValidator.validate_create(vals)

        # Validate uniqueness
        if 'name' in vals:
            ExcludedPartValidator.validate_unique_name(env, vals['name'])

        # Create excluded part with sudo for system operations
        excluded_part = env['jabin.excluded.part'].sudo().create(vals)

        return excluded_part

    @staticmethod
    def update(env, part_id, vals):
        """
        Update an existing excluded part.

        Args:
            env: Odoo environment
            part_id: ID of excluded part to update
            vals: Dictionary of values to update

        Returns:
            jabin.excluded.part: The updated excluded part record

        Raises:
            ValidationError: If validation fails or record not found
        """
        # Get the excluded part
        excluded_part = env['jabin.excluded.part'].sudo().browse(part_id)
        ExcludedPartValidator.validate_exists(excluded_part)

        # Validate update data
        ExcludedPartValidator.validate_update(vals)

        # Validate uniqueness if name is changing
        if 'name' in vals:
            ExcludedPartValidator.validate_unique_name(env, vals['name'], exclude_id=part_id)

        # Perform update
        excluded_part.write(vals)

        return excluded_part

    @staticmethod
    def delete(env, part_id):
        """
        Delete an excluded part.

        Args:
            env: Odoo environment
            part_id: ID of excluded part to delete

        Returns:
            bool: True if deletion succeeded

        Raises:
            ValidationError: If record not found or has dependencies
        """
        # Get the excluded part
        excluded_part = env['jabin.excluded.part'].sudo().browse(part_id)
        ExcludedPartValidator.validate_exists(excluded_part)

        # Validate deletion
        ExcludedPartValidator.validate_delete(excluded_part)

        # Perform deletion
        excluded_part.unlink()

        return True

    @staticmethod
    def get_by_id(env, part_id, lang=None):
        """
        Get a single excluded part by ID.

        Args:
            env: Odoo environment
            part_id: ID of excluded part to retrieve
            lang: Language code for translations

        Returns:
            jabin.excluded.part: The excluded part record

        Raises:
            ValidationError: If record not found
        """
        excluded_part = (
            env['jabin.excluded.part']
            .sudo()
            .with_context(lang=lang)
            .browse(part_id)
        )
        ExcludedPartValidator.validate_exists(excluded_part)

        return excluded_part

    @staticmethod
    def get_list(
        env,
        domain=None,
        limit=100,
        offset=0,
        order='name',
        lang=None
    ):
        """
        Get a list of excluded parts with pagination.

        Args:
            env: Odoo environment
            domain: Search domain (list of tuples)
            limit: Maximum number of records
            offset: Number of records to skip
            order: Sort order string
            lang: Language code for translations

        Returns:
            tuple: (recordset, total_count)
        """
        domain = domain or []
        Model = env['jabin.excluded.part'].sudo().with_context(lang=lang)

        # Get total count
        total = Model.search_count(domain)

        # Get paginated records
        records = Model.search(
            domain,
            limit=limit,
            offset=offset,
            order=order
        )

        return records, total

    @staticmethod
    def toggle_active(env, part_id):
        """
        Toggle active status of an excluded part.

        Args:
            env: Odoo environment
            part_id: ID of excluded part

        Returns:
            jabin.excluded.part: The updated excluded part record

        Raises:
            ValidationError: If record not found
        """
        excluded_part = env['jabin.excluded.part'].sudo().browse(part_id)
        ExcludedPartValidator.validate_exists(excluded_part)

        excluded_part.write({'active': not excluded_part.active})

        return excluded_part