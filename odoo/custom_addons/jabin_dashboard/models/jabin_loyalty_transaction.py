# jabin_loyalty_transaction.py
from odoo import models, fields, api, _

class JabinLoyaltyTransaction(models.Model):
    _name = 'jabin.loyalty.transaction'
    _description = 'JABIN Loyalty Transaction'
    _order = 'date desc, id desc'

    customer_id = fields.Many2one(
        'res.users',
        string='Customer',
        required=True,
        index=True,
        ondelete='cascade',
        domain="[('user_type', 'in', ['individual', 'business'])]"
    )
    order_id = fields.Many2one(
        'jabin.order',
        string='Related Order',
        index=True,
        ondelete='set null'
    )
    transaction_type = fields.Selection([
        ('earn', 'Earned'),
        ('redeem', 'Redeemed'),
        ('refund_adjustment', 'Refund Adjustment'),
        ('manual_adjustment', 'Manual Adjustment')
    ], string='Transaction Type', required=True, index=True)

    points = fields.Integer(
        string='Points',
        required=True,
        help='Number of points added (+) or deducted (-)'
    )
    balance_after = fields.Integer(
        string='Balance After',
        required=True,
        help='Customer points balance after this transaction'
    )
    description = fields.Text(
        string='Description',
        help='Notes or justification for this points transaction'
    )
    date = fields.Datetime(
        string='Date',
        default=fields.Datetime.now,
        required=True,
        index=True
    )
    created_by_id = fields.Many2one(
        'res.users',
        string='Created By',
        default=lambda self: self.env.user.id
    )
