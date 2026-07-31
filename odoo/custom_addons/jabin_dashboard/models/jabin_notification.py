# jabin_notification.py
import uuid
import json
from odoo import models, fields, api, _

class JabinNotification(models.Model):
    _name = 'jabin.notification'
    _description = 'JABIN Notification History'
    _order = 'create_date desc, id desc'

    uuid = fields.Char(
        string='Notification UUID',
        required=True,
        index=True,
        copy=False,
        default=lambda self: str(uuid.uuid4())
    )
    user_id = fields.Many2one(
        'res.users',
        string='Recipient User',
        required=True,
        index=True,
        ondelete='cascade'
    )
    title = fields.Char(string='Title', required=True)
    body = fields.Text(string='Body', required=True)
    image_url = fields.Char(string='Image URL')

    notification_type = fields.Selection([
        ('order', 'Order Update'),
        ('offer', 'Offer'),
        ('banner', 'Banner'),
        ('product', 'Product'),
        ('coupon', 'Coupon'),
        ('loyalty', 'Loyalty Points'),
        ('payment', 'Payment'),
        ('system', 'System Alert'),
        ('admin', 'Admin Notification')
    ], string='Type', default='system', required=True, index=True)

    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], string='Priority', default='normal', required=True)

    deep_link = fields.Char(string='Deep Link', help='Mobile app navigation link (e.g. jabin://orders/123)')
    data_json = fields.Text(string='Data Payload (JSON)')

    status = fields.Selection([
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('read', 'Read')
    ], string='Status', default='pending', required=True, index=True)

    sent_at = fields.Datetime(string='Sent At')
    delivered_at = fields.Datetime(string='Delivered At')
    read_at = fields.Datetime(string='Read At')

    order_id = fields.Many2one(
        'jabin.order',
        string='Related Order',
        index=True,
        ondelete='set null'
    )
    created_by = fields.Many2one(
        'res.users',
        string='Created By',
        default=lambda self: self.env.user.id
    )

    def mark_as_read(self):
        """Mark notification as read by user."""
        return self.write({
            'status': 'read',
            'read_at': fields.Datetime.now()
        })

    def mark_as_sent(self):
        """Mark notification as sent."""
        return self.write({
            'status': 'sent',
            'sent_at': fields.Datetime.now(),
            'delivered_at': fields.Datetime.now()
        })

    def mark_as_failed(self, reason=None):
        """Mark notification as failed."""
        vals = {'status': 'failed'}
        if reason:
            try:
                d = json.loads(self.data_json or '{}')
            except Exception:
                d = {}
            d['failure_reason'] = str(reason)
            vals['data_json'] = json.dumps(d)
        return self.write(vals)
