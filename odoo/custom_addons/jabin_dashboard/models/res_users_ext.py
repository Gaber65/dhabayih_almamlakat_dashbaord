from odoo import api, fields, models, _
from typing import Dict, Any

class ResUsers(models.Model):
    _inherit = 'res.users'

    cart_ids = fields.One2many(
        'jabin.cart',
        'customer_id',
        string='Carts'
    )
    
    active_cart_id = fields.Many2one(
        'jabin.cart',
        compute='_compute_active_cart_id',
        string='Active Cart'
    )
    
    checked_out_cart_ids = fields.One2many(
        'jabin.cart',
        'customer_id',
        domain=[('status', '=', 'checked_out')],
        string='Checked Out Carts'
    )

    # --- Loyalty Wallet Fields ---
    loyalty_points = fields.Integer(
        string='Loyalty Points Balance',
        default=0,
        index=True,
        help='Current active loyalty points available for redemption.'
    )
    total_earned_points = fields.Integer(
        string='Total Earned Points',
        default=0,
        help='Lifetime total loyalty points earned by this customer.'
    )
    total_redeemed_points = fields.Integer(
        string='Total Redeemed Points',
        default=0,
        help='Lifetime total loyalty points redeemed by this customer.'
    )
    loyalty_transaction_ids = fields.One2many(
        'jabin.loyalty.transaction',
        'customer_id',
        string='Loyalty Transactions'
    )

    def _compute_active_cart_id(self):
        for user in self:
            active_cart = user.cart_ids.filtered(lambda c: c.status == 'active')
            if not active_cart and user.id:
                # Try to search directly from db to ensure cache is correct
                active_cart = self.env['jabin.cart'].sudo().search([
                    ('customer_id', '=', user.id),
                    ('status', '=', 'active')
                ], limit=1)
                if not active_cart:
                    active_cart = self.env['jabin.cart'].sudo().create({
                        'customer_id': user.id,
                        'currency_id': user.currency_id.id or self.env.company.currency_id.id
                    })
            user.active_cart_id = active_cart[:1]


    def action_open_loyalty_adjust_wizard(self):
        """Open wizard for admin manual points adjustment."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Adjust Loyalty Points'),
            'res_model': 'jabin.loyalty.adjust.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_customer_id': self.id,
            }
        }

    def action_open_send_notification_wizard(self):
        """Open wizard to send FCM push notification to this user."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Send FCM Notification'),
            'res_model': 'jabin.send.notification.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_user_id': self.id,
            }
        }


    def to_public_dict(self) -> Dict[str, Any]:
        """Override to include cart & loyalty metrics in public user dict."""
        res = super().to_public_dict()
        
        # Access active_cart_id to trigger compute and auto-creation if active user
        active_cart = self.active_cart_id
        
        cart_dict = active_cart.get_summary() if active_cart else None
        res.update({
            'active_cart': cart_dict,
            'activeCart': cart_dict,
            'carts_count': len(self.cart_ids),
            'checked_out_carts_count': len(self.checked_out_cart_ids),
            'loyalty_points': self.loyalty_points,
            'total_earned_points': self.total_earned_points,
            'total_redeemed_points': self.total_redeemed_points,
        })
        return res

