from __future__ import annotations
try:
    from odoo import fields, models
    _ODOO = True
except Exception:
    _ODOO = False
    fields = None
    models = None
if _ODOO:

    class TimestampMixin(models.AbstractModel):
        _name = 'jabin.timestamp.mixin'
        _description = 'JABIN Timestamp Mixin'
        create_date = fields.Datetime(string='Created On', readonly=True, help='Date and time when the record was created (UTC).')
        write_date = fields.Datetime(string='Last Updated On', readonly=True, help='Date and time of the last write to the record (UTC).')
else:

    class TimestampMixin:
        _name = 'jabin.timestamp.mixin'
        _description = 'JABIN Timestamp Mixin (stub)'