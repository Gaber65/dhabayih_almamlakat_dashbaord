from __future__ import annotations
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.addons.jabin_core import JabinLogger

_logger = JabinLogger.get('security.permission')


class JabinPermission(models.Model):
    _name = 'jabin.permission'
    _description = 'JABIN Permission'
    _order = 'resource, action'
    _rec_name = 'code'

    code = fields.Char(
        string='Permission Code',
        required=True,
        index=True,
        help="Unique identifier in '<resource>.<action>' format (e.g. 'users.create')."
    )
    name = fields.Char(
        string='Display Name',
        required=True,
        help='Human-readable label.'
    )
    description = fields.Text(
        string='Description',
        help='What this permission allows.'
    )
    resource = fields.Char(
        string='Resource',
        index=True,
        help='The domain resource this permission applies to (extracted from the code).'
    )
    action = fields.Char(
        string='Action',
        index=True,
        help='The action this permission allows (extracted from the code).'
    )
    is_system = fields.Boolean(
        string='System Permission',
        default=True,
        help='System permissions are predefined and cannot be deleted.'
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        index=True
    )
    role_ids = fields.Many2many(
        comodel_name='jabin.role',
        relation='jabin_role_permission_rel',
        column1='permission_id',
        column2='role_id',
        string='Roles',
        help='Roles that grant this permission.'
    )

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'A permission with this code already exists.')
    ]

    @api.constrains('code')
    def _check_code_format(self):
        import re
        for rec in self:
            if rec.code and (not re.match('^[a-z][a-z0-9_]*\\.[a-z][a-z0-9_]*$', rec.code)):
                raise ValidationError(
                    f"Permission code '{rec.code}' must follow the '<resource>.<action>' "
                    "convention (lowercase snake_case, single dot separator)."
                )

    @api.model
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        for vals in vals_list:
            self._split_code(vals)
        return super().create(vals_list)

    def write(self, vals):
        if 'code' in vals:
            self._split_code(vals)
        return super().write(vals)

    def unlink(self):
        system = self.filtered('is_system')
        if system:
            raise ValidationError(
                f"Cannot delete system permissions: {', '.join(system.mapped('code'))}"
            )
        return super().unlink()

    @staticmethod
    def _split_code(vals: dict) -> None:
        code = vals.get('code')
        if not code or '.' not in code:
            return
        parts = code.split('.', 1)
        vals.setdefault('resource', parts[0])
        vals.setdefault('action', parts[1])

    @api.model
    def find_by_code(self, code: str):
        if not code:
            return self.env['jabin.permission']
        return self.search([('code', '=', code)], limit=1)

    def to_public_dict(self) -> dict:
        self.ensure_one()
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'resource': self.resource,
            'action': self.action,
            'description': self.description or None,
            'is_system': self.is_system
        }