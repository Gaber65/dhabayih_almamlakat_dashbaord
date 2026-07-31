from odoo import fields, models, api
from typing import Dict, Any, Optional


class JabinDashboard(models.Model):
    """Placeholder dashboard model - no business logic"""
    _name = 'jabin.dashboard'
    _description = 'JABIN Dashboard'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(
        string='Dashboard Name',
        required=True,
        translate=True,
        help='Name of the dashboard section'
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order of display'
    )

    description = fields.Text(
        string='Description',
        translate=True,
        help='Description of the dashboard section'
    )

    active = fields.Boolean(
        string='Active',
        default=True,
        help='Toggle to hide/unhide this dashboard section'
    )

    color = fields.Integer(
        string='Color Index',
        default=0,
        help='Color accent for the dashboard section'
    )

    icon = fields.Char(
        string='Icon',
        default='fa-dashboard',
        help='FontAwesome icon class for this dashboard section'
    )

    def _get_kpi_data(self) -> Dict[str, Any]:
        """
        Get actual database KPI data
        """
        total_customers = self.env['res.users'].search_count([
            ('user_type', 'in', ('individual', 'business')),
            ('active', '=', True)
        ])
        total_orders = self.env['jabin.order'].search_count([])
        total_products = self.env['jabin.product'].search_count([('active', '=', True)])
        
        paid_orders = self.env['jabin.order'].search([('payment_status', '=', 'paid')])
        total_revenue = sum(paid_orders.mapped('total'))
        
        pending_orders = self.env['jabin.order'].search_count([
            ('state', 'in', ('draft', 'pending_payment', 'confirmed', 'preparing', 'ready_pickup', 'out_delivery'))
        ])
        low_stock = self.env['jabin.product'].search_count([
            ('stock_quantity', '<=', 5.0)
        ])
        
        return {
            'total_orders': total_orders,
            'total_customers': total_customers,
            'total_products': total_products,
            'total_revenue': total_revenue,
            'pending_orders': pending_orders,
            'low_stock': low_stock,
        }

    def _get_recent_orders(self) -> list:
        """
        Get actual recent orders data
        """
        orders = self.env['jabin.order'].search([], limit=5, order='date desc')
        res = []
        for order in orders:
            res.append({
                'order_number': order.name,
                'customer': order.customer_id.name,
                'date': fields.Datetime.to_string(order.date)[:10] if order.date else '',
                'status': dict(order._fields['state'].selection).get(order.state, order.state),
                'total': order.total,
            })
        return res

    def _get_top_products(self) -> list:
        """
        Get actual top products data based on order lines
        """
        lines = self.env['jabin.order.line'].search([
            ('order_id.state', 'not in', ('draft', 'cancelled'))
        ])
        prod_counts = {}
        for line in lines:
            # Check product_id (extended field in jabin_dashboard)
            prod = getattr(line, 'product_id', None)
            if prod:
                prod_counts[prod] = prod_counts.get(prod, 0.0) + line.quantity
        
        sorted_prods = sorted(prod_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        res = []
        for prod, qty in sorted_prods:
            res.append({
                'name': prod.name,
                'category': prod.category_id.name or 'Uncategorized',
                'sales': sum(lines.filtered(lambda l: getattr(l, 'product_id', None) == prod).mapped('price_subtotal')),
                'units': int(qty),
            })
        
        if not res:
            products = self.env['jabin.product'].search([], limit=3)
            for prod in products:
                res.append({
                    'name': prod.name,
                    'category': prod.category_id.name or 'Uncategorized',
                    'sales': 0.0,
                    'units': 0,
                })
        return res

    def _get_chart_data(self) -> Dict[str, Any]:
        """
        Get actual chart data
        """
        orders = self.env['jabin.order'].search([
            ('state', 'not in', ('draft', 'cancelled'))
        ], order='date asc')
        
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        sales_by_month = [0.0] * 12
        orders_by_month = [0] * 12
        customers_by_month = [0] * 12
        
        import datetime
        for order in orders:
            dt = order.date
            if dt:
                m = dt.month - 1
                sales_by_month[m] += order.total
                orders_by_month[m] += 1
        
        customers = self.env['res.users'].search([
            ('user_type', 'in', ('individual', 'business'))
        ])
        for cust in customers:
            dt = cust.create_date
            if dt:
                m = dt.month - 1
                customers_by_month[m] += 1

        now = datetime.datetime.now()
        cur_month = max(1, now.month)
        
        return {
            'labels': months[:cur_month],
            'datasets': {
                'sales': sales_by_month[:cur_month],
                'orders': orders_by_month[:cur_month],
                'customers': customers_by_month[:cur_month],
            }
        }


class JabinDashboardSetting(models.TransientModel):
    """Dashboard settings model"""
    _name = 'jabin.dashboard.setting'
    _description = 'JABIN Dashboard Settings'

    dashboard_layout = fields.Selection([
        ('grid', 'Grid'),
        ('compact', 'Compact'),
        ('detailed', 'Detailed'),
    ], string='Dashboard Layout', default='grid', required=True)

    show_kpi = fields.Boolean(string='Show KPI Cards', default=True)
    show_recent_orders = fields.Boolean(string='Show Recent Orders', default=True)
    show_top_products = fields.Boolean(string='Show Top Products', default=True)
    show_sales_chart = fields.Boolean(string='Show Sales Chart', default=True)
    show_inventory_summary = fields.Boolean(string='Show Inventory Summary', default=True)

    refresh_interval = fields.Integer(
        string='Refresh Interval (seconds)',
        default=60,
        help='Time in seconds between auto-refresh of dashboard data'
    )