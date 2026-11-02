# category_service.py
from odoo import _, fields
from odoo.exceptions import ValidationError, AccessError

from ..validators.category_validator import CategoryValidator


class CategoryService:
    """Category business logic service layer."""

    @staticmethod
    def create_category(env, vals):
        """
        Create a new category.

        Args:
            env: Odoo environment
            vals: Dictionary of category values

        Returns:
            jabin.category: The created category record

        Raises:
            ValidationError: If validation fails
            AccessError: If user lacks permissions
        """
        # Validate input
        CategoryValidator.validate_create(vals)

        # Create category
        category = env["jabin.category"].sudo().create(vals)

        return category

    @staticmethod
    def update_category(env, category_id, vals):
        """
        Update an existing category.

        Args:
            env: Odoo environment
            category_id: ID of category to update
            vals: Dictionary of values to update

        Returns:
            jabin.category: The updated category record

        Raises:
            ValidationError: If validation fails or record not found
            AccessError: If user lacks permissions
        """
        # Find the category
        category = env["jabin.category"].sudo().browse(category_id)

        if not category.exists():
            raise ValidationError(_("Category not found."))

        # Validate update
        CategoryValidator.validate_update(category, vals)

        # Perform update
        category.write(vals)

        return category

    @staticmethod
    def delete_category(env, category_id):
        """
        Delete a category.

        Args:
            env: Odoo environment
            category_id: ID of category to delete

        Returns:
            bool: True if deletion succeeded

        Raises:
            ValidationError: If record not found or has products
            AccessError: If user lacks permissions
        """
        # Find the category
        category = env["jabin.category"].sudo().browse(category_id)

        if not category.exists():
            raise ValidationError(_("Category not found."))

        # Check for products
        if category.product_ids:
            raise ValidationError(
                _("Cannot delete category with existing products.")
            )

        # Perform deletion
        category.unlink()

        return True

    @staticmethod
    def get_category(env, category_id, lang=None):
        """
        Get a single category by ID.

        Args:
            env: Odoo environment
            category_id: ID of category to retrieve
            lang: Language code for translations

        Returns:
            jabin.category: The category record

        Raises:
            ValidationError: If record not found
        """
        category = (
            env["jabin.category"]
            .sudo()
            .with_context(lang=lang)
            .browse(category_id)
        )

        if not category.exists():
            raise ValidationError(_("Category not found."))

        return category

    @staticmethod
    def get_categories(
            env,
            domain=None,
            limit=None,
            offset=None,
            order=None,
            lang=None,
    ):
        """
        Get a list of categories with pagination.

        Args:
            env: Odoo environment
            domain: Search domain
            limit: Maximum number of records
            offset: Number of records to skip
            order: Sort order
            lang: Language code for translations

        Returns:
            jabin.category: Recordset of categories
        """
        return (
            env["jabin.category"]
            .sudo()
            .with_context(lang=lang)
            .search(
                domain or [],
                limit=limit or 100,
                offset=offset or 0,
                order=order or "sequence, name",
            )
        )

    @staticmethod
    def get_category_by_name(env, name, lang=None):
        """
        Get a category by name.

        Args:
            env: Odoo environment
            name: Category name
            lang: Language code for translations

        Returns:
            jabin.category: The category record

        Raises:
            ValidationError: If record not found
        """
        category = (
            env["jabin.category"]
            .sudo()
            .with_context(lang=lang)
            .search([("name", "=", name)], limit=1)
        )

        if not category:
            raise ValidationError(_("Category not found."))

        return category

    @staticmethod
    def check_category_exists(env, category_id):
        """
        Check if a category exists.

        Args:
            env: Odoo environment
            category_id: ID of category to check

        Returns:
            bool: True if category exists

        Raises:
            ValidationError: If record not found
        """
        exists = env["jabin.category"].sudo().browse(category_id).exists()

        if not exists:
            raise ValidationError(_("Category not found."))

        return True

    @staticmethod
    def get_category_product_count(env, category_id):
        """
        Get product count for a category.

        Args:
            env: Odoo environment
            category_id: ID of category

        Returns:
            int: Number of products in category

        Raises:
            ValidationError: If record not found
        """
        category = env["jabin.category"].sudo().browse(category_id)

        if not category.exists():
            raise ValidationError(_("Category not found."))

        return len(category.product_ids)

    @staticmethod
    def toggle_category_active(env, category_id):
        """
        Toggle active status of a category.

        Args:
            env: Odoo environment
            category_id: ID of category

        Returns:
            jabin.category: The updated category record

        Raises:
            ValidationError: If record not found
            AccessError: If user lacks permissions
        """
        category = env["jabin.category"].sudo().browse(category_id)

        if not category.exists():
            raise ValidationError(_("Category not found."))

        category.write({"active": not category.active})

        return category

    @staticmethod
    def reorder_category(env, category_id, position='last', target_category_id=None):
        """
        Reorder category globally.
        
        Args:
            env: Odoo environment
            category_id: Category ID to move
            position: 'first', 'last', int index (1-based), 'before', or 'after'
            target_category_id: Reference category ID for 'before'/'after'
        """
        category = env['jabin.category'].sudo().browse(category_id)
        if not category.exists():
            raise ValidationError(_('Category not found.'))

        all_cats = env['jabin.category'].sudo().search([], order='sequence, id')
        cat_list = [c for c in all_cats if c.id != category.id]

        if position == 'first':
            cat_list.insert(0, category)
        elif position == 'last':
            cat_list.append(category)
        elif position in ('before', 'after'):
            target_idx = -1
            if target_category_id:
                for idx, c in enumerate(cat_list):
                    if c.id == target_category_id:
                        target_idx = idx
                        break
            if target_idx == -1:
                if position == 'before':
                    cat_list.insert(0, category)
                else:
                    cat_list.append(category)
            else:
                insert_idx = target_idx if position == 'before' else target_idx + 1
                cat_list.insert(insert_idx, category)
        else:
            try:
                pos_idx = int(position) - 1 # 1-based index
                pos_idx = max(0, min(len(cat_list), pos_idx))
                cat_list.insert(pos_idx, category)
            except (ValueError, TypeError):
                cat_list.append(category)

        # Re-index all categories cleanly
        for idx, c in enumerate(cat_list):
            new_seq = (idx + 1) * 10
            if c.sequence != new_seq:
                c.write({'sequence': new_seq})

        return category
