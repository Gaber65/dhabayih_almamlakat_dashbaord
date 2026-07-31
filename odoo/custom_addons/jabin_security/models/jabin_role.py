from __future__ import annotations
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.addons.jabin_core import JabinLogger

_logger = JabinLogger.get('security.role')


class JabinRole(models.Model):
    _name = 'jabin.role'
    _description = 'JABIN Role'
    _order = 'sequence, code'
    _rec_name = 'code'

    code = fields.Char(
        string='Role Code',
        required=True,
        index=True,
        help="Unique machine-readable role identifier (e.g. 'order_manager')."
    )
    name = fields.Char(
        string='Display Name',
        required=True,
        help='Human-readable role name.'
    )
    description = fields.Text(
        string='Description',
        help='What this role grants and when it should be assigned.'
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Display order in lists.'
    )
    is_system = fields.Boolean(
        string='System Role',
        default=False,
        help='System roles are predefined and cannot be deleted.'
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        index=True
    )
    permission_ids = fields.Many2many(
        comodel_name='jabin.permission',
        relation='jabin_role_permission_rel',
        column1='role_id',
        column2='permission_id',
        string='Permissions',
        help='Permissions granted by this role.'
    )
    user_ids = fields.Many2many(
        comodel_name='res.users',  # Changed from res.users
        relation='jabin_role_user_rel',
        column1='role_id',
        column2='user_id',
        string='Users',
        help='Users assigned to this role.'
    )

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'A role with this code already exists.')
    ]

    @api.constrains('code')
    def _check_code_format(self):
        import re
        for rec in self:
            if rec.code and (not re.match('^[a-z][a-z0-9_]*$', rec.code)):
                raise ValidationError(
                    f"Role code '{rec.code}' must be lowercase snake_case "
                    "(letters, digits, underscores; starting with a letter)."
                )

    def unlink(self):
        system = self.filtered('is_system')
        if system:
            raise ValidationError(
                f"Cannot delete system roles: {', '.join(system.mapped('code'))}"
            )
        return super().unlink()

    @api.model
    def find_by_code(self, code: str):
        if not code:
            return self.env['jabin.role']
        return self.search([('code', '=', code)], limit=1)

    def get_permission_codes(self) -> set:
        self.ensure_one() if len(self) == 1 else None
        perms = self.mapped('permission_ids.code')
        return set(perms)