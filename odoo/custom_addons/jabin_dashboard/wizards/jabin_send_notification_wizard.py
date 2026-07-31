# jabin_send_notification_wizard.py
import json
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class JabinSendNotificationWizard(models.TransientModel):
    _name = 'jabin.send.notification.wizard'
    _description = 'Send FCM Push Notification to User Wizard'

    user_id = fields.Many2one(
        'res.users',
        string='Recipient User',
        required=True,
        domain="[('status', '=', 'active')]"
    )
    
    active_device_count = fields.Integer(
        string='Active FCM Devices',
        compute='_compute_active_device_count',
        help='Number of active mobile devices registered for this user.'
    )

    title = fields.Char(
        string='Title',
        required=True,
        default='Notification'
    )
    
    body = fields.Text(
        string='Message / Body',
        required=True
    )

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
    ], string='Notification Type', default='admin', required=True)

    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], string='Priority', default='normal', required=True)

    deep_link = fields.Char(
        string='Deep Link',
        help='Mobile app navigation link (e.g. jabin://offers or jabin://orders/123)'
    )
    
    image_url = fields.Char(
        string='Image URL',
        help='Optional URL of an image to display in the push notification.'
    )
    
    data_json = fields.Text(
        string='Custom Payload (JSON)',
        help='Optional custom JSON key-value object passed to the mobile application.'
    )

    @api.depends('user_id')
    def _compute_active_device_count(self):
        for record in self:
            if record.user_id:
                record.active_device_count = self.env['jabin.device'].sudo().search_count([
                    ('user_id', '=', record.user_id.id),
                    ('is_active', '=', True)
                ])
            else:
                record.active_device_count = 0

    def action_send_notification(self):
        self.ensure_one()
        if not self.title or not self.title.strip():
            raise ValidationError(_("Notification title is required."))
        if not self.body or not self.body.strip():
            raise ValidationError(_("Notification message body is required."))

        extra_data = {}
        if self.data_json and self.data_json.strip():
            try:
                extra_data = json.loads(self.data_json.strip())
                if not isinstance(extra_data, dict):
                    raise ValidationError(_("Custom payload must be a valid JSON object (dictionary)."))
            except ValueError as e:
                raise ValidationError(_("Invalid JSON format in custom payload: %s") % str(e))

        # Send via NotificationService (which handles FCM dispatch & notification history)
        notif = self.env['jabin.notification.service'].send_to_user(
            env=self.env,
            user_id=self.user_id.id,
            title=self.title.strip(),
            body=self.body.strip(),
            notification_type=self.notification_type,
            deep_link=self.deep_link.strip() if self.deep_link else None,
            data=extra_data,
            priority=self.priority,
            image_url=self.image_url.strip() if self.image_url else None
        )

        if not notif:
            msg = _("Failed to process notification for user %s.") % self.user_id.name
            msg_type = 'danger'
        elif notif.status == 'sent':
            msg = _("FCM Push Notification sent successfully to user %s (%d active device(s)).") % (
                self.user_id.name, self.active_device_count
            )
            msg_type = 'success'
        elif notif.status == 'failed':
            msg = _("Notification record created, but FCM push notification failed to deliver.")
            msg_type = 'warning'
        else: # pending
            msg = _("Notification saved in history for user %s. (Note: User has no active registered FCM devices).") % self.user_id.name
            msg_type = 'warning'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('FCM Notification Result'),
                'message': msg,
                'type': msg_type,
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }
