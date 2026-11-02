# product_service.py
from odoo import _
from odoo.exceptions import ValidationError

from ..validators.product_validator import ProductValidator
from datetime import datetime


class ProductService:
    """
    Product business logic service layer.
    Following Category module architecture standards.
    """

    @staticmethod
    def create(env, vals):
        """
        Create a new product.

        Args:
            env: Odoo environment
            vals: Dictionary of product values

        Returns:
            jabin.product: The created product record

        Raises:
            ValidationError: If validation fails
        """
        # Validate input
        ProductValidator.validate_create(vals)

        # Validate SKU uniqueness
        if 'sku' in vals:
            ProductValidator.validate_unique_sku(env, vals['sku'])

        # Validate barcode uniqueness if provided
        if 'barcode' in vals and vals['barcode']:
            ProductValidator.validate_unique_barcode(env, vals['barcode'])

        # Create product with sudo for system operations
        product = env['jabin.product'].sudo().create(vals)

        return product

    @staticmethod
    def update(env, product_id, vals):
        """
        Update an existing product.

        Args:
            env: Odoo environment
            product_id: ID of product to update
            vals: Dictionary of values to update

        Returns:
            jabin.product: The updated product record

        Raises:
            ValidationError: If validation fails or record not found
        """
        # Get the product
        product = env['jabin.product'].sudo().browse(product_id)
        ProductValidator.validate_exists(product)

        # Validate update data
        ProductValidator.validate_update(vals)

        # Validate SKU uniqueness if changing
        if 'sku' in vals:
            ProductValidator.validate_unique_sku(env, vals['sku'], exclude_id=product_id)

        # Validate barcode uniqueness if changing
        if 'barcode' in vals and vals['barcode']:
            ProductValidator.validate_unique_barcode(env, vals['barcode'], exclude_id=product_id)

        # Perform update
        product.write(vals)

        return product

    @staticmethod
    def delete(env, product_id):
        """
        Delete a product.

        Args:
            env: Odoo environment
            product_id: ID of product to delete

        Returns:
            bool: True if deletion succeeded

        Raises:
            ValidationError: If record not found or has dependencies
        """
        # Get the product
        product = env['jabin.product'].sudo().browse(product_id)
        ProductValidator.validate_exists(product)

        # Validate deletion
        ProductValidator.validate_delete(product)

        # Perform deletion
        product.unlink()

        return True

    @staticmethod
    def get_by_id(env, product_id, lang=None):
        """
        Get a single product by ID.

        Args:
            env: Odoo environment
            product_id: ID of product to retrieve
            lang: Language code for translations

        Returns:
            jabin.product: The product record

        Raises:
            ValidationError: If record not found
        """
        product = (
            env['jabin.product']
            .sudo()
            .with_context(lang=lang)
            .browse(product_id)
        )
        ProductValidator.validate_exists(product)

        return product

    @staticmethod
    def get_list(
        env,
        domain=None,
        limit=100,
        offset=0,
        order='sequence, name, id',
        lang=None
    ):
        """
        Get a list of products with pagination.

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
        Model = env['jabin.product'].sudo().with_context(lang=lang)

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
    def get_products_on_offer(env, lang=None):
        """
        Get all products currently on offer.

        Args:
            env: Odoo environment
            lang: Language code for translations

        Returns:
            jabin.product: Recordset of products on offer
        """
        today = datetime.now().date()
        domain = [
            ('is_on_offer', '=', True),
            ('offer_start_date', '<=', today),
            ('offer_end_date', '>=', today)
        ]
        return (
            env['jabin.product']
            .sudo()
            .with_context(lang=lang)
            .search(domain)
        )

    @staticmethod
    def update_stock(env, product_id, quantity):
        """
        Update product stock quantity.

        Args:
            env: Odoo environment
            product_id: ID of product
            quantity: Quantity to add (positive) or remove (negative)

        Returns:
            jabin.product: The updated product record

        Raises:
            ValidationError: If validation fails
        """
        product = env['jabin.product'].sudo().browse(product_id)
        ProductValidator.validate_exists(product)

        # Validate stock update
        ProductValidator.validate_stock_update(product, quantity)

        # Update stock
        product.stock_quantity += quantity

        return product

    @staticmethod
    def toggle_active(env, product_id):
        """
        Toggle product active status.

        Args:
            env: Odoo environment
            product_id: ID of product

        Returns:
            jabin.product: The updated product record

        Raises:
            ValidationError: If record not found
        """
        product = env['jabin.product'].sudo().browse(product_id)
        ProductValidator.validate_exists(product)

        product.write({'active': not product.active})

        return product

    @staticmethod
    def reorder_product(env, product_id, category_id, position='last', target_product_id=None):
        """
        Reorder product inside a specific category.
        
        Args:
            env: Odoo environment
            product_id: Product ID to move
            category_id: Category ID context
            position: 'first', 'last', int index (1-based), 'before', or 'after'
            target_product_id: ID of reference product for 'before' or 'after'
        """
        product = env['jabin.product'].sudo().browse(product_id)
        if not product.exists():
            raise ValidationError(_('Product not found.'))

        category = env['jabin.category'].sudo().browse(category_id)
        if not category.exists():
            raise ValidationError(_('Category not found.'))

        # Check if product is in this category or moving into this category
        if product.category_id.id != category_id:
            product.write({'category_id': category_id})

        # Fetch all products in this category ordered by current sequence, id
        category_products = env['jabin.product'].sudo().search(
            [('category_id', '=', category_id)],
            order='sequence, id'
        )

        prod_list = [p for p in category_products if p.id != product.id]

        if position == 'first':
            prod_list.insert(0, product)
        elif position == 'last':
            prod_list.append(product)
        elif position in ('before', 'after'):
            target_idx = -1
            if target_product_id:
                for idx, p in enumerate(prod_list):
                    if p.id == target_product_id:
                        target_idx = idx
                        break
            if target_idx == -1:
                if position == 'before':
                    prod_list.insert(0, product)
                else:
                    prod_list.append(product)
            else:
                insert_idx = target_idx if position == 'before' else target_idx + 1
                prod_list.insert(insert_idx, product)
        else:
            try:
                pos_idx = int(position) - 1 # 1-based index
                pos_idx = max(0, min(len(prod_list), pos_idx))
                prod_list.insert(pos_idx, product)
            except (ValueError, TypeError):
                prod_list.append(product)

        # Re-index all products in this category with clean gap (10, 20, 30...)
        for idx, p in enumerate(prod_list):
            new_seq = (idx + 1) * 10
            if p.sequence != new_seq:
                p.write({'sequence': new_seq})

        return product
