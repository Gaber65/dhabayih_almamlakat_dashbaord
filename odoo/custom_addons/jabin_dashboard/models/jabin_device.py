# jabin_device.py
import uuid
from odoo import models, fields, api, _

class JabinDevice(models.Model):
    _name = 'jabin.device'
    _description = 'JABIN Customer Device'
    _order = 'last_seen desc, id desc'

    uuid = fields.Char(
        string='Device UUID',
        required=True,
        index=True,
        copy=False,
        default=lambda self: str(uuid.uuid4())
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        index=True,
        ondelete='cascade'
    )
    device_name = fields.Char(string='Device Name')
    device_type = fields.Selection([
        ('android', 'Android'),
        ('ios', 'iOS'),
        ('web', 'Web')
    ], string='Device Type', required=True, default='android', index=True)

    fcm_token = fields.Char(
        string='FCM Token',
        required=True,
        index=True,
        copy=False
    )
    app_version = fields.Char(string='App Version')
    os_version = fields.Char(string='OS Version')
    language = fields.Char(string='Language', default='en')
    timezone = fields.Char(string='Timezone', default='UTC')
    is_active = fields.Boolean(
        string='Is Active',
        default=True,
        index=True,
        help='Whether this device token is active and eligible for push notifications.'
    )
    last_seen = fields.Datetime(
        string='Last Seen',
        default=fields.Datetime.now,
        required=True
    )
    created_at = fields.Datetime(
        string='Created At',
        default=fields.Datetime.now,
        readonly=True
    )
    updated_at = fields.Datetime(
        string='Updated At',
        default=fields.Datetime.now,
        readonly=True
    )

    _sql_constraints = [
        ('fcm_token_unique', 'unique(fcm_token)', 'The FCM device token must be unique across all devices.')
    ]

    def deactivate(self):
        """Deactivate this device token (e.g. on logout or invalid token)."""
        return self.write({
            'is_active': False,
            'updated_at': fields.Datetime.now()
        })

    def touch(self):
        """Update last_seen timestamp."""
        return self.write({
            'last_seen': fields.Datetime.now(),
            'updated_at': fields.Datetime.now()
        })
