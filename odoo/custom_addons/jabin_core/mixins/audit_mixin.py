from __future__ import annotations
try:
    from odoo import fields, models
    _ODOO = True
except Exception:
    _ODOO = False
    fields = None
    models = None
if _ODOO:

    class AuditMixin(models.AbstractModel):
        _name = 'jabin.audit.mixin'
        _description = 'JABIN Audit Mixin'
        created_by = fields.Many2one(comodel_name='res.users', string='Created By', readonly=True, help='User who created the record.')
        updated_by = fields.Many2one(comodel_name='res.users', string='Last Updated By', readonly=True, help='User who last updated the record.')

        def create(self, vals_list):
            user_id = self.env.user.id
            if isinstance(vals_list, dict):
                vals_list = dict(vals_list)
                vals_list.setdefault('created_by', user_id)
                vals_list.setdefault('updated_by', user_id)
            else:
                vals_list = [{**vals, 'created_by': vals.get('created_by', user_id), 'updated_by': vals.get('updated_by', user_id)} for vals in vals_list]
            return super().create(vals_list)

        def write(self, vals):
            if 'updated_by' not in vals:
                vals = {**vals, 'updated_by': self.env.user.id}
            return super().write(vals)
else:

    class AuditMixin:
        _name = 'jabin.audit.mixin'
        _description = 'JABIN Audit Mixin (stub)'