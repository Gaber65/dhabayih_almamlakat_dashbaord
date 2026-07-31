from __future__ import annotations
import json
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.addons.jabin_core import JabinLogger
_logger = JabinLogger.get('security.audit_log')

class JabinAuditLog(models.Model):
    _name = 'jabin.audit.log'
    _description = 'JABIN Audit Log'
    _order = 'create_date desc'
    action = fields.Char(string='Action', required=True, index=True, help="Event code in '<domain>.<event>' format (e.g. 'auth.login').")
    severity = fields.Selection(selection=[('info', 'Info'), ('warning', 'Warning'), ('error', 'Error'), ('critical', 'Critical')], string='Severity', default='info', required=True, index=True)
    user_id = fields.Many2one(comodel_name='res.users', string='Actor (User)', index=True, help='The user who performed the action.')
    target_user_id = fields.Many2one(comodel_name='res.users', string='Target User', index=True, help='The user the action was performed on (when different from actor).')
    ip_address = fields.Char(string='IP Address', help='Client IP address (when available).')
    user_agent = fields.Char(string='User Agent', help='Client User-Agent string (truncated).')
    endpoint = fields.Char(string='Endpoint', help='API endpoint that triggered the event.')
    request_id = fields.Char(string='Request ID', index=True, help='Correlation ID for the request (when available).')
    details = fields.Text(string='Details (JSON)', help='Structured extra context stored as a JSON string.')
    summary = fields.Char(string='Summary', help='One-line human-readable summary of the event.')
    create_date = fields.Datetime(string='Timestamp', readonly=True, index=True)

    def write(self, vals):
        raise UserError('Audit log entries cannot be modified.')

    def unlink(self):
        raise UserError('Audit log entries cannot be deleted.')

    def to_dict(self) -> dict:
        self.ensure_one()
        try:
            details = json.loads(self.details) if self.details else None
        except (json.JSONDecodeError, TypeError):
            details = None
        return {'id': self.id, 'action': self.action, 'severity': self.severity, 'user_id': self.user_id.id if self.user_id else None, 'user_name': self.user_id.name if self.user_id else None, 'target_user_id': self.target_user_id.id if self.target_user_id else None, 'target_user_name': self.target_user_id.name if self.target_user_id else None, 'ip_address': self.ip_address or None, 'endpoint': self.endpoint or None, 'request_id': self.request_id or None, 'summary': self.summary or None, 'details': details, 'timestamp': self.create_date.isoformat() if self.create_date else None}