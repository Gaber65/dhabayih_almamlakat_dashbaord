from odoo import models, fields, api, _
from typing import Optional, Dict, Any


class ResUsers(models.Model):
    _inherit = 'res.users'
    _description = 'Jabin User (Extended)'

    # --- Custom Fields (preserved from res.users) ---
    verified_at = fields.Datetime(string='Verified At', readonly=True)

    status = fields.Selection([
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('inactive', 'Inactive')
    ], string='Status', default='pending', required=True, index=True)

    profile_completed = fields.Boolean(string='Profile Completed', default=False)
    phone = fields.Char(string='Phone Number')
    preferred_language = fields.Selection([('ar', 'Arabic'), ('en', 'English')], string='Preferred Language', default='ar')
    preferred_theme = fields.Selection([('light', 'Light'), ('dark', 'Dark')], string='Preferred Theme', default='light')
    push_notifications_enabled = fields.Boolean(string='Push Notifications Enabled', default=True)


    addresses = fields.One2many(
        'res.users.address',
        'user_id',
        string='Addresses'
    )

    user_type = fields.Selection([
        ('individual', 'Individual'),
        ('business', 'Business'),
        ('admin', 'Admin'),
        ('customer', 'Customer')
    ], string='User Type', default='individual')

    balance = fields.Float(string='Balance', default=0.0)

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id.id
    )

    last_login = fields.Datetime(string='Last Login')

    # --- Custom Relationships ---
    order_ids = fields.One2many('jabin.order', 'customer_id', string='All Orders')
    active_order_ids = fields.One2many('jabin.order', 'customer_id', compute='_compute_filtered_orders', string='Active Orders')
    previous_order_ids = fields.One2many('jabin.order', 'customer_id', compute='_compute_filtered_orders', string='Previous Orders')
    cancelled_order_ids = fields.One2many('jabin.order', 'customer_id', compute='_compute_filtered_orders', string='Cancelled Orders')
    refunded_order_ids = fields.One2many('jabin.order', 'customer_id', compute='_compute_filtered_orders', string='Refunded Orders')
    payment_transaction_ids = fields.One2many('jabin.payment.transaction', 'customer_id', string='Payment Transactions')
    activity_ids = fields.One2many('jabin.customer.activity', 'user_id', string='Customer Activities')

    # --- Financial & Activity Metrics ---
    total_orders_count = fields.Integer(string='Total Orders', compute='_compute_financial_metrics')
    total_spending = fields.Monetary(string='Total Spending', compute='_compute_financial_metrics', currency_field='currency_id')
    total_refunds = fields.Monetary(string='Total Refunds', compute='_compute_financial_metrics', currency_field='currency_id')
    pending_payments_count = fields.Integer(string='Pending Payments Count', compute='_compute_financial_metrics')
    completed_payments_count = fields.Integer(string='Completed Payments Count', compute='_compute_financial_metrics')
    preferred_payment_method_id = fields.Many2one('jabin.payment.method', string='Preferred Payment Method', compute='_compute_financial_metrics')
    average_order_value = fields.Monetary(string='Average Order Value', compute='_compute_financial_metrics', currency_field='currency_id')
    last_payment_date = fields.Datetime(string='Last Payment Date', compute='_compute_financial_metrics')
    last_activity_date = fields.Datetime(string='Last Activity Date', compute='_compute_last_activity_date')

    # avatar is replaced by image_1920 from res.users

    # --- Computed Methods ---
    def _compute_filtered_orders(self):
        for user in self:
            user.active_order_ids = user.order_ids.filtered(lambda o: o.state not in ('delivered', 'cancelled', 'refunded'))
            user.previous_order_ids = user.order_ids.filtered(lambda o: o.state == 'delivered')
            user.cancelled_order_ids = user.order_ids.filtered(lambda o: o.state == 'cancelled')
            user.refunded_order_ids = user.order_ids.filtered(lambda o: o.state == 'refunded')

    @api.depends('order_ids.state', 'order_ids.total', 'order_ids.payment_status', 
                 'payment_transaction_ids.status', 'payment_transaction_ids.payment_method_id')
    def _compute_financial_metrics(self):
        for user in self:
            orders = user.order_ids
            user.total_orders_count = len(orders)
            paid_orders = orders.filtered(lambda o: o.state != 'cancelled' and o.payment_status == 'paid')
            user.total_spending = sum(paid_orders.mapped('total'))
            refunded_orders = orders.filtered(lambda o: o.state == 'refunded')
            user.total_refunds = sum(refunded_orders.mapped('total'))

            if user.total_orders_count > 0:
                user.average_order_value = user.total_spending / user.total_orders_count
            else:
                user.average_order_value = 0.0

            transactions = user.payment_transaction_ids
            user.pending_payments_count = len(transactions.filtered(lambda t: t.status == 'pending'))
            user.completed_payments_count = len(transactions.filtered(lambda t: t.status == 'paid'))

            paid_txs = transactions.filtered(lambda t: t.status == 'paid' and t.paid_date)
            user.last_payment_date = max(paid_txs.mapped('paid_date')) if paid_txs else False

            successful_txs = transactions.filtered(lambda t: t.status == 'paid')
            if successful_txs:
                method_counts = {}
                for tx in successful_txs:
                    method_counts[tx.payment_method_id] = method_counts.get(tx.payment_method_id, 0) + 1
                preferred = max(method_counts, key=method_counts.get)
                user.preferred_payment_method_id = preferred.id
            else:
                user.preferred_payment_method_id = False

    @api.depends('activity_ids.timestamp')
    def _compute_last_activity_date(self):
        for user in self:
            user.last_activity_date = max(user.activity_ids.mapped('timestamp')) if user.activity_ids else False

    def log_activity(self, action, related_record=None):
        self.ensure_one()
        self.env['jabin.customer.activity'].sudo().create({
            'user_id': self.id,
            'action': action,
            'related_record': related_record,
            'timestamp': fields.Datetime.now()
        })

    # --- Override create and write to set defaults & log activities ---
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'email' in vals and 'login' not in vals:
                vals['login'] = vals['email']
        users = super().create(vals_list)
        for user in users:
            if user.user_type in ('individual', 'business'):
                user.log_activity('registered', related_record=f'res.users,{user.id}')
                if "jabin.notification.service" in self.env:
                    try:
                        self.env["jabin.notification.service"].send_to_admins(
                            env=self.env,
                            title=_("New Customer Registered"),
                            body=_("Customer '%s' (%s) has registered.") % (user.name, user.login),
                            required_permission='users_manage',
                            notification_type='admin'
                        )
                    except Exception:
                        pass
        return users


    def write(self, vals):
        profile_fields = {'name', 'email', 'login', 'phone', 'user_type', 'image_1920'}
        res = super().write(vals)
        if any(f in vals for f in profile_fields):
            for user in self:
                if user.user_type in ('individual', 'business'):
                    user.log_activity('updated_profile', related_record=f'res.users,{user.id}')
        return res

    # --- Helper Methods (adapted from res.users) ---
    @api.model
    def find_by_email(self, email: str) -> Optional['ResUsers']:
        """Find a user by email address."""
        return self.search([('login', '=', email)], limit=1)

    @api.model
    def find_by_phone(self, phone: str) -> Optional['ResUsers']:
        """Find a user by phone number."""
        return self.search([('partner_id.phone', '=', phone)], limit=1)

    @api.model
    def find_by_login(self, email: str) -> Optional['ResUsers']:
        """Find a user by login (email)."""
        return self.search([('login', '=', email)], limit=1)

    def update_last_login(self) -> None:
        """Update the last login timestamp to now."""
        self.ensure_one()
        self.write({'last_login': fields.Datetime.now()})

    def get_role_codes(self) -> list:
        """Get the role codes assigned to this user."""
        roles = self.env['jabin.role'].search([
            ('user_ids', 'in', self.id)
        ])
        return roles.mapped('code')

    def get_permission_codes(self) -> set:
        """Get the permission codes for this user."""
        roles = self.env['jabin.role'].search([
            ('user_ids', 'in', self.id)
        ])
        permissions = roles.mapped('permission_ids')
        return set(permissions.mapped('code'))

    def to_public_dict(self) -> Dict[str, Any]:
        """Serialize user data for API responses."""
        self.ensure_one()
        partner_id = self.partner_id.id if self.partner_id else self.id
        avatar_url = f"api/v1/image/res.partner/{partner_id}/image_1920" if (self.image_1920 or (self.partner_id and self.partner_id.image_1920)) else None
        return {
            'id': self.id,
            'name': self.name,
            'email': self.login,  # Use login as email
            'phone': self.partner_id.phone if self.partner_id else None,
            'avatar': avatar_url,
            'avatar_url': avatar_url,
            'avatarUrl': avatar_url,
            'status': self.status,
            'profile_completed': self.profile_completed,
            'user_type': self.user_type,
            'balance': self.balance,
            'currency_id': self.currency_id.id if self.currency_id else None,
            'last_login': self.last_login,
            'verified_at': self.verified_at,
        }
