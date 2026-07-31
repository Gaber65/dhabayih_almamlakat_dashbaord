from odoo import _
from odoo.exceptions import ValidationError


class FavoriteValidator:
    """Validator for favorite/wishlist payload and entities."""

    @classmethod
    def validate_add(cls, data: dict):
        if not data or not data.get("product_id"):
            raise ValidationError(_("product_id is required."))
        try:
            int(data["product_id"])
        except ValueError:
            raise ValidationError(_("product_id must be an integer."))
