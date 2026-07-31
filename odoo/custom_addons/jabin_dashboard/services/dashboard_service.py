from odoo import api, fields, models, _
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class JabinDashboardService(models.Model):
    _name = 'jabin.dashboard.service'
    _description = 'JABIN Dashboard Service'
    _transient = True

    def get_dashboard_data(self):
        """Get all dashboard data in a single call"""
        return {
            'kpi_data': self._get_kpi_data(),
            'recent_orders': self._get_recent_orders(),
            'top_products': self._get_top_products(),
            'sales_data': self._get_sales_chart_data(),
            'inventory_data': self._get_inventory_data(),
        }

    def _get_kpi_data(self):
        """Calculate KPI metrics"""
        # Total Orders - all orders except cancelled
        total_orders = self.env['jabin.order'].search_count([
            ('state', '!=', 'cancelled')
        ])

        # Total Customers - active users with individual or business type
        total_customers = self.env['res.users'].search_count([
            ('user_type', 'in', ['individual', 'business']),
            ('active', '=', True)
        ])

        # Total Products - active products
        total_products = self.env['jabin.product'].search_count([
            ('active', '=', True)
        ])

        # Total Revenue - from paid orders
        paid_orders = self.env['jabin.order'].search([
            ('payment_status', '=', 'paid'),
            ('state', '!=', 'cancelled')
        ])
        total_revenue = sum(paid_orders.mapped('total'))

        # Pending Orders - orders not yet completed
        pending_orders = self.env['jabin.order'].search_count([
            ('state', 'not in', ['delivered', 'cancelled', 'refunded'])
        ])

        # Low Stock Products
        low_stock = self.env['jabin.product'].search_count([
            ('active', '=', True),
            ('stock_quantity', '<=', 5.0)
        ])

        # Calculate month-over-month growth for progress bars
        current_month = datetime.now().month
        current_year = datetime.now().year

        # Orders growth
        current_month_orders = self.env['jabin.order'].search_count([
            ('date', '>=', datetime(current_year, current_month, 1)),
            ('date', '<',
             datetime(current_year, current_month + 1, 1) if current_month < 12 else datetime(current_year + 1, 1, 1)),
            ('state', '!=', 'cancelled')
        ])

        prev_month = current_month - 1 if current_month > 1 else 12
        prev_year = current_year if current_month > 1 else current_year - 1
        prev_month_orders = self.env['jabin.order'].search_count([
            ('date', '>=', datetime(prev_year, prev_month, 1)),
            ('date', '<', datetime(prev_year, prev_month + 1, 1) if prev_month < 12 else datetime(prev_year + 1, 1, 1)),
            ('state', '!=', 'cancelled')
        ])

        orders_target = 100  # target is 100 orders per month
        orders_progress = min(100, int((current_month_orders / orders_target) * 100)) if orders_target > 0 else 0

        # Revenue growth
        current_month_revenue = sum(
            self.env['jabin.order'].search([
                ('date', '>=', datetime(current_year, current_month, 1)),
                ('date', '<',
                 datetime(current_year, current_month + 1, 1) if current_month < 12 else datetime(current_year + 1, 1,
                                                                                                  1)),
                ('payment_status', '=', 'paid'),
                ('state', '!=', 'cancelled')
            ]).mapped('total')
        )

        revenue_target = 150000  # target revenue per month
        revenue_progress = min(100, int((current_month_revenue / revenue_target) * 100)) if revenue_target > 0 else 0

        # Customer growth
        current_month_customers = self.env['res.users'].search_count([
            ('user_type', 'in', ['individual', 'business']),
            ('create_date', '>=', datetime(current_year, current_month, 1)),
            ('create_date', '<',
             datetime(current_year, current_month + 1, 1) if current_month < 12 else datetime(current_year + 1, 1, 1))
        ])

        customers_target = 50  # target new customers per month
        customers_progress = min(100,
                                 int((current_month_customers / customers_target) * 100)) if customers_target > 0 else 0

        # Pending orders progress
        pending_target = 10  # target for pending orders (lower is better)
        pending_progress = min(100, int((pending_orders / pending_target) * 100)) if pending_target > 0 else 0

        # Low stock progress
        low_stock_target = 5  # target for low stock items (lower is better)
        low_stock_progress = min(100, int((low_stock / low_stock_target) * 100)) if low_stock_target > 0 else 0

        return {
            'total_orders': total_orders,
            'total_customers': total_customers,
            'total_products': total_products,
            'total_revenue': total_revenue,
            'pending_orders': pending_orders,
            'low_stock': low_stock,
            'orders_progress': orders_progress,
            'revenue_progress': revenue_progress,
            'customers_progress': customers_progress,
            'pending_progress': pending_progress,
            'low_stock_progress': low_stock_progress,
            'current_month_revenue': current_month_revenue,
            'current_month_orders': current_month_orders,
            'current_month_customers': current_month_customers,
        }

    def _get_recent_orders(self, limit=5):
        """Get the most recent orders"""
        orders = self.env['jabin.order'].search([], limit=limit, order='date desc')

        result = []
        status_map = dict(self.env['jabin.order']._fields['state'].selection)

        # Define status badge mapping
        badge_map = {
            'draft': 'badge-secondary',
            'pending_payment': 'badge-warning',
            'confirmed': 'badge-primary',
            'preparing': 'badge-info',
            'ready_pickup': 'badge-info',
            'out_delivery': 'badge-info',
            'delivered': 'badge-success',
            'cancelled': 'badge-danger',
            'refunded': 'badge-danger',
        }

        status_display_map = {
            'draft': 'Draft',
            'pending_payment': 'Pending Payment',
            'confirmed': 'Confirmed',
            'preparing': 'Preparing',
            'ready_pickup': 'Ready Pickup',
            'out_delivery': 'Out Delivery',
            'delivered': 'Completed',
            'cancelled': 'Cancelled',
            'refunded': 'Refunded',
        }

        for order in orders:
            customer_name = order.customer_id.name if order.customer_id else _('Unknown Customer')
            status_display = status_display_map.get(order.state, order.state)
            badge_class = badge_map.get(order.state, 'badge-secondary')

            result.append({
                'order_number': order.name,
                'customer': customer_name,
                'date': fields.Datetime.to_string(order.date)[:10] if order.date else '',
                'status': status_display,
                'badge_class': badge_class,
                'total': order.total,
                'formatted_total': self._format_currency(order.total),
            })

        return result

    def _get_top_products(self, limit=5):
        """Get the top selling products"""
        # Get all order lines from non-cancelled orders
        lines = self.env['jabin.order.line'].search([
            ('order_id.state', 'not in', ['draft', 'cancelled'])
        ])

        # Aggregate product sales
        product_sales = {}
        for line in lines:
            product = line.product_id
            if product:
                if product not in product_sales:
                    product_sales[product] = {
                        'units': 0,
                        'revenue': 0,
                        'name': product.name,
                        'category': product.category_id.name or _('Uncategorized'),
                    }
                product_sales[product]['units'] += line.quantity
                product_sales[product]['revenue'] += line.price_subtotal or 0

        # Sort by units sold and get top products
        sorted_products = sorted(
            product_sales.items(),
            key=lambda x: x[1]['units'],
            reverse=True
        )[:limit]

        result = []
        for product, data in sorted_products:
            result.append({
                'name': data['name'],
                'category': data['category'],
                'sales': data['revenue'],
                'formatted_sales': self._format_currency(data['revenue']),
                'units': int(data['units']),
            })

        # If no products found, return empty list
        return result

    def _get_sales_chart_data(self):
        """Get monthly sales data for the chart"""
        # Get data for the current year
        now = datetime.now()
        current_year = now.year
        current_month = now.month

        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

        # Initialize data arrays
        sales_by_month = [0.0] * 12
        orders_by_month = [0] * 12
        customers_by_month = [0] * 12

        # Get all completed orders for current year
        orders = self.env['jabin.order'].search([
            ('date', '>=', datetime(current_year, 1, 1)),
            ('date', '<', datetime(current_year + 1, 1, 1)),
            ('state', 'not in', ['draft', 'cancelled'])
        ])

        for order in orders:
            if order.date:
                month_index = order.date.month - 1
                sales_by_month[month_index] += order.total or 0
                orders_by_month[month_index] += 1

        # Get all customers registered in current year
        customers = self.env['res.users'].search([
            ('create_date', '>=', datetime(current_year, 1, 1)),
            ('create_date', '<', datetime(current_year + 1, 1, 1)),
            ('user_type', 'in', ['individual', 'business'])
        ])

        for customer in customers:
            if customer.create_date:
                month_index = customer.create_date.month - 1
                customers_by_month[month_index] += 1

        # Only return data up to current month
        labels = month_names[:current_month]
        sales_data = sales_by_month[:current_month]
        orders_data = orders_by_month[:current_month]
        customers_data = customers_by_month[:current_month]

        return {
            'labels': labels,
            'datasets': {
                'sales': sales_data,
                'orders': orders_data,
                'customers': customers_data,
            }
        }

    def _get_inventory_data(self):
        """Get inventory statistics"""
        # Total active products
        total_products = self.env['jabin.product'].search_count([
            ('active', '=', True)
        ])

        # Low stock products (<= 5)
        low_stock = self.env['jabin.product'].search_count([
            ('active', '=', True),
            ('stock_quantity', '<=', 5.0),
            ('stock_quantity', '>', 0)
        ])

        # Out of stock products
        out_of_stock = self.env['jabin.product'].search_count([
            ('active', '=', True),
            ('stock_quantity', '=', 0)
        ])

        # Total categories
        total_categories = self.env['jabin.category'].search_count([
            ('active', '=', True)
        ])

        # Calculate stock health percentage
        total_stock = self.env['jabin.product'].search([
            ('active', '=', True)
        ])
        total_quantity = sum(total_stock.mapped('stock_quantity'))

        # Get products with stock (for progress bar)
        products_with_stock = self.env['jabin.product'].search_count([
            ('active', '=', True),
            ('stock_quantity', '>', 0)
        ])
        stock_coverage = int((products_with_stock / total_products) * 100) if total_products > 0 else 0

        return {
            'total': total_products,
            'low_stock': low_stock,
            'out_of_stock': out_of_stock,
            'categories': total_categories,
            'total_quantity': total_quantity,
            'stock_coverage': stock_coverage,
        }

    def _format_currency(self, amount):
        """Format currency value"""
        if not amount:
            return '0.00'
        currency = self.env.company.currency_id
        return currency.format(amount) if currency else f'{amount:.2f}'