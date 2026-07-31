# jabin_loyalty_adjust_wizard.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class JabinLoyaltyAdjustWizard(models.TransientModel):
    _name = 'jabin.loyalty.adjust.wizard'
    _description = 'Manual Loyalty Points Adjustment Wizard'

    customer_id = fields.Many2one(
        'res.users',
        string='Customer',
        required=True,
        domain="[('user_type', 'in', ['individual', 'business'])]"
    )
    current_points = fields.Integer(
        string='Current Points Balance',
        related='customer_id.loyalty_points',
        readonly=True
    )
    adjustment_type = fields.Selection([
        ('add', 'Add Points'),
        ('remove', 'Deduct Points')
    ], string='Action', default='add', required=True)

    points = fields.Integer(
        string='Points Amount',
        required=True,
        default=100
    )
    reason = fields.Text(
        string='Reason / Justification',
        required=True,
        help='Mandatory notes explaining why points are being manually adjusted.'
    )

    def action_adjust_points(self):
        self.ensure_one()
        if self.points <= 0:
            raise ValidationError(_("Points amount must be greater than zero."))
        if not self.reason or not self.reason.strip():
            raise ValidationError(_("Reason for manual adjustment is required."))

        points_change = self.points if self.adjustment_type == 'add' else -self.points

        # Delegate to LoyaltyService
        self.env['jabin.loyalty.service'].manual_adjust_points(
            env=self.env,
            customer_id=self.customer_id.id,
            points_change=points_change,
            reason=self.reason.strip(),
            admin_user_id=self.env.user.id
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Points Adjusted'),
                'message': _('Successfully adjusted loyalty points for customer %s.') % self.customer_id.name,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }
