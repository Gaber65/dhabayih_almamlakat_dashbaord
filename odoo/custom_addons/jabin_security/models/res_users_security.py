# addons/jabin_security/models/security_context.py
from odoo import models


class SecurityContext(models.AbstractModel):
    _name = 'jabin.security.context'
    _description = 'Security Context'

    def get_current_user(self):
        """
        Retrieve the currently authenticated user.
        Updated to lookup res.users instead of res.users.
        """
        # Assuming JWT middleware injects the user_id into the context
        user_id = self.env.context.get('jwt_user_id')
        if not user_id:
            return None

        # GREENFIELD CHANGE: Lookup res.users
        user = self.env['res.users'].browse(user_id).exists()
        return user if user else None