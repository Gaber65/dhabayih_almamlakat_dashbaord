# addons/jabin_security/models/security_context.py
from odoo import models


class SecurityContext(models.AbstractModel):
    _name = 'jabin.security.context'
    _description = 'Security Context'

    def get_current_user(self):
        """
        Retrieve the currently authenticated user.
        Now looks up res.users instead of res.users.
        """
        # Assuming JWT middleware injects the user_id into the context
        user_id = self.env.context.get('jwt_user_id')
        if not user_id:
            return None

        # Use res.users instead of res.users
        user = self.env['res.users'].browse(user_id).exists()
        return user if user else None

    def get_current_user_id(self):
        """
        Get the ID of the currently authenticated user.
        """
        return self.env.context.get('jwt_user_id')

    def is_authenticated(self):
        """
        Check if there is an authenticated user.
        """
        return bool(self.env.context.get('jwt_user_id'))

    def get_current_user_permissions(self):
        """
        Get the permissions of the currently authenticated user.
        """
        user = self.get_current_user()
        if not user:
            return set()

        # Get permissions through roles
        roles = self.env['jabin.role'].search([
            ('user_ids', 'in', user.id)
        ])
        permissions = roles.mapped('permission_ids')
        return set(permissions.mapped('code'))

    def get_current_user_roles(self):
        """
        Get the roles of the currently authenticated user.
        """
        user = self.get_current_user()
        if not user:
            return []

        roles = self.env['jabin.role'].search([
            ('user_ids', 'in', user.id)
        ])
        return roles.mapped('code')