/** @odoo-module **/

import {Component, useState, onWillStart} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

export class JabinDashboard extends Component {

    static template = "jabin_dashboard.DashboardComponent";

    setup() {
        this.state = useState({
            loading: true,
            error: null,
            // KPI Data
            total_orders: 0,
            total_customers: 0,
            total_products: 0,
            total_revenue: 0,
            pending_orders: 0,
            low_stock: 0,
            // Recent Orders
            recent_orders: [],
            // Top Products
            top_products: [],
            // Chart Data
            sales_labels: [],
            sales_data: [],
            orders_data: [],
            customers_data: [],
            // Inventory
            inventory_total: 0,
            inventory_low_stock: 0,
            inventory_out_of_stock: 0,
            inventory_categories: 0,
            inventory_total_quantity: 0,
            inventory_coverage: 0,
            // Monthly stats
            current_month_orders: 0,
            current_month_revenue: 0,
            current_month_customers: 0,
            // Additional stats
            order_growth: 0,
            revenue_growth: 0,
            customer_growth: 0,
        });

        this.orm = useService("orm");
        this.notification = useService("notification");

        onWillStart(async () => {
            await this.loadDashboardData();
        });
    }

    async loadDashboardData() {
        this.state.loading = true;
        this.state.error = null;

        try {
            await Promise.all([
                this.loadKpiData(),
                this.loadRecentOrders(),
                this.loadTopProducts(),
                this.loadChartData(),
                this.loadInventoryData(),
            ]);
        } catch (error) {
            console.error('Dashboard Error:', error);
            this.state.error = 'Unable to load dashboard data. Please refresh the page.';
            this.notification.add('Error loading dashboard data', { type: 'danger' });
        } finally {
            this.state.loading = false;
        }
    }

    // ==================== KPI DATA ====================
    async loadKpiData() {
        try {
            const now = new Date();
            const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
            const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 1);
            const lastMonthStart = new Date(now.getFullYear(), now.getMonth() - 1, 1);
            const lastMonthEnd = new Date(now.getFullYear(), now.getMonth(), 1);

            // Parallel queries for better performance
            const [
                totalOrders,
                totalCustomers,
                totalProducts,
                pendingOrders,
                lowStock,
                monthOrders,
                monthRevenueOrders,
                monthCustomers,
                lastMonthOrders,
                lastMonthRevenueOrders,
                lastMonthCustomers
            ] = await Promise.all([
                this.orm.searchCount('jabin.order', [['state', '!=', 'cancelled']]),
                this.orm.searchCount('res.users', [
                    ['user_type', 'in', ['individual', 'business']],
                    ['active', '=', true]
                ]),
                this.orm.searchCount('jabin.product', [['active', '=', true]]),
                this.orm.searchCount('jabin.order', [
                    ['state', 'not in', ['delivered', 'cancelled', 'refunded']]
                ]),
                this.orm.searchCount('jabin.product', [
                    ['active', '=', true],
                    ['stock_quantity', '<=', 5],
                    ['stock_quantity', '>', 0]
                ]),
                this.orm.searchCount('jabin.order', [
                    ['date', '>=', monthStart.toISOString()],
                    ['date', '<', monthEnd.toISOString()],
                    ['state', '!=', 'cancelled']
                ]),
                this.orm.searchRead('jabin.order', [
                    ['date', '>=', monthStart.toISOString()],
                    ['date', '<', monthEnd.toISOString()],
                    ['payment_status', '=', 'paid'],
                    ['state', '!=', 'cancelled']
                ], ['total']),
                this.orm.searchCount('res.users', [
                    ['user_type', 'in', ['individual', 'business']],
                    ['create_date', '>=', monthStart.toISOString()],
                    ['create_date', '<', monthEnd.toISOString()]
                ]),
                this.orm.searchCount('jabin.order', [
                    ['date', '>=', lastMonthStart.toISOString()],
                    ['date', '<', lastMonthEnd.toISOString()],
                    ['state', '!=', 'cancelled']
                ]),
                this.orm.searchRead('jabin.order', [
                    ['date', '>=', lastMonthStart.toISOString()],
                    ['date', '<', lastMonthEnd.toISOString()],
                    ['payment_status', '=', 'paid'],
                    ['state', '!=', 'cancelled']
                ], ['total']),
                this.orm.searchCount('res.users', [
                    ['user_type', 'in', ['individual', 'business']],
                    ['create_date', '>=', lastMonthStart.toISOString()],
                    ['create_date', '<', lastMonthEnd.toISOString()]
                ])
            ]);

            const totalRevenue = monthRevenueOrders.reduce((sum, order) => sum + (order.total || 0), 0);
            const lastMonthRevenue = lastMonthRevenueOrders.reduce((sum, order) => sum + (order.total || 0), 0);

            // Calculate growth percentages
            const orderGrowth = lastMonthOrders > 0
                ? ((monthOrders - lastMonthOrders) / lastMonthOrders) * 100
                : monthOrders > 0 ? 100 : 0;

            const revenueGrowth = lastMonthRevenue > 0
                ? ((totalRevenue - lastMonthRevenue) / lastMonthRevenue) * 100
                : totalRevenue > 0 ? 100 : 0;

            const customerGrowth = lastMonthCustomers > 0
                ? ((monthCustomers - lastMonthCustomers) / lastMonthCustomers) * 100
                : monthCustomers > 0 ? 100 : 0;

            this.state.total_orders = totalOrders;
            this.state.total_customers = totalCustomers;
            this.state.total_products = totalProducts;
            this.state.total_revenue = totalRevenue;
            this.state.pending_orders = pendingOrders;
            this.state.low_stock = lowStock;
            this.state.current_month_orders = monthOrders;
            this.state.current_month_revenue = totalRevenue;
            this.state.current_month_customers = monthCustomers;
            this.state.order_growth = Math.round(orderGrowth * 10) / 10;
            this.state.revenue_growth = Math.round(revenueGrowth * 10) / 10;
            this.state.customer_growth = Math.round(customerGrowth * 10) / 10;

        } catch (error) {
            console.error('Error loading KPI data:', error);
            throw error;
        }
    }

    // ==================== RECENT ORDERS ====================
    async loadRecentOrders() {
        try {
            const orders = await this.orm.searchRead('jabin.order', [],
                ['name', 'customer_id', 'date', 'state', 'total'],
                {limit: 5, order: 'date desc'}
            );

            const statusMap = {
                'draft': 'Draft',
                'pending_payment': 'Pending',
                'confirmed': 'Confirmed',
                'preparing': 'Preparing',
                'ready_pickup': 'Ready',
                'out_delivery': 'Shipping',
                'delivered': 'Completed',
                'cancelled': 'Cancelled',
                'refunded': 'Refunded'
            };

            const badgeMap = {
                'draft': 'badge-secondary',
                'pending_payment': 'badge-warning',
                'confirmed': 'badge-primary',
                'preparing': 'badge-info',
                'ready_pickup': 'badge-info',
                'out_delivery': 'badge-info',
                'delivered': 'badge-success',
                'cancelled': 'badge-danger',
                'refunded': 'badge-danger'
            };

            const customerIds = orders.map(o => o.customer_id[0]).filter(id => id);
            let customerMap = {};

            if (customerIds.length > 0) {
                const customers = await this.orm.searchRead('res.users',
                    [['id', 'in', customerIds]],
                    ['id', 'name']
                );
                customerMap = customers.reduce((map, c) => {
                    map[c.id] = c.name;
                    return map;
                }, {});
            }

            this.state.recent_orders = orders.map(order => {
                const customerName = customerMap[order.customer_id[0]] || 'Guest';
                const date = order.date ? new Date(order.date).toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric'
                }) : 'N/A';
                const status = statusMap[order.state] || order.state;
                const badge = badgeMap[order.state] || 'badge-secondary';

                return {
                    order_number: order.name || 'N/A',
                    customer: customerName,
                    date: date,
                    status: status,
                    badge_class: badge,
                    total: order.total || 0,
                    formatted_total: this.formatCurrency(order.total || 0),
                };
            });

        } catch (error) {
            console.error('Error loading recent orders:', error);
            this.state.recent_orders = [];
        }
    }

    // ==================== TOP PRODUCTS ====================
    async loadTopProducts() {
        try {
            const lines = await this.orm.searchRead('jabin.order.line', [
                ['order_id.state', 'not in', ['draft', 'cancelled']]
            ], ['product_id', 'quantity', 'price_subtotal']);

            const productMap = {};
            const productIds = [];

            lines.forEach(line => {
                const productId = line.product_id ? line.product_id[0] : null;
                if (productId) {
                    productIds.push(productId);
                    if (!productMap[productId]) {
                        productMap[productId] = { units: 0, revenue: 0 };
                    }
                    productMap[productId].units += line.quantity || 0;
                    productMap[productId].revenue += line.price_subtotal || 0;
                }
            });

            let products = [];
            if (productIds.length > 0) {
                products = await this.orm.searchRead('jabin.product',
                    [['id', 'in', productIds]],
                    ['id', 'name', 'category_id']
                );
            }

            const result = products.map(product => ({
                name: product.name || 'Unknown Product',
                category: product.category_id ? product.category_id[1] : 'Uncategorized',
                sales: productMap[product.id]?.revenue || 0,
                units: Math.round(productMap[product.id]?.units || 0),
                formatted_sales: this.formatCurrency(productMap[product.id]?.revenue || 0),
            }));

            result.sort((a, b) => b.units - a.units);
            this.state.top_products = result.slice(0, 5);

        } catch (error) {
            console.error('Error loading top products:', error);
            this.state.top_products = [];
        }
    }

    // ==================== CHART DATA ====================
    async loadChartData() {
        try {
            const now = new Date();
            const currentYear = now.getFullYear();
            const currentMonth = now.getMonth();

            const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

            const yearStart = new Date(currentYear, 0, 1);
            const yearEnd = new Date(currentYear + 1, 0, 1);

            const orders = await this.orm.searchRead('jabin.order', [
                ['date', '>=', yearStart.toISOString()],
                ['date', '<', yearEnd.toISOString()],
                ['state', 'not in', ['draft', 'cancelled']]
            ], ['date', 'total']);

            const salesByMonth = new Array(12).fill(0);
            const ordersByMonth = new Array(12).fill(0);

            orders.forEach(order => {
                if (order.date) {
                    const month = new Date(order.date).getMonth();
                    salesByMonth[month] += order.total || 0;
                    ordersByMonth[month] += 1;
                }
            });

            const customers = await this.orm.searchRead('res.users', [
                ['create_date', '>=', yearStart.toISOString()],
                ['create_date', '<', yearEnd.toISOString()],
                ['user_type', 'in', ['individual', 'business']]
            ], ['create_date']);

            const customersByMonth = new Array(12).fill(0);
            customers.forEach(customer => {
                if (customer.create_date) {
                    const month = new Date(customer.create_date).getMonth();
                    customersByMonth[month] += 1;
                }
            });

            const labels = monthNames.slice(0, currentMonth + 1);
            const salesData = salesByMonth.slice(0, currentMonth + 1);
            const ordersData = ordersByMonth.slice(0, currentMonth + 1);
            const customersData = customersByMonth.slice(0, currentMonth + 1);

            this.state.sales_labels = labels;
            this.state.sales_data = salesData;
            this.state.orders_data = ordersData;
            this.state.customers_data = customersData;

        } catch (error) {
            console.error('Error loading chart data:', error);
            this.state.sales_labels = [];
            this.state.sales_data = [];
            this.state.orders_data = [];
            this.state.customers_data = [];
        }
    }

    // ==================== INVENTORY DATA ====================
    async loadInventoryData() {
        try {
            const [total, lowStock, outOfStock, categories, products, withStock] = await Promise.all([
                this.orm.searchCount('jabin.product', [['active', '=', true]]),
                this.orm.searchCount('jabin.product', [
                    ['active', '=', true],
                    ['stock_quantity', '<=', 5],
                    ['stock_quantity', '>', 0]
                ]),
                this.orm.searchCount('jabin.product', [
                    ['active', '=', true],
                    ['stock_quantity', '=', 0]
                ]),
                this.orm.searchCount('jabin.category', [['active', '=', true]]),
                this.orm.searchRead('jabin.product',
                    [['active', '=', true]],
                    ['stock_quantity']
                ),
                this.orm.searchCount('jabin.product', [
                    ['active', '=', true],
                    ['stock_quantity', '>', 0]
                ])
            ]);

            const totalQuantity = products.reduce((sum, p) => sum + (p.stock_quantity || 0), 0);
            const coverage = total > 0 ? Math.round((withStock / total) * 100) : 0;

            this.state.inventory_total = total;
            this.state.inventory_low_stock = lowStock;
            this.state.inventory_out_of_stock = outOfStock;
            this.state.inventory_categories = categories;
            this.state.inventory_total_quantity = totalQuantity;
            this.state.inventory_coverage = coverage;

        } catch (error) {
            console.error('Error loading inventory data:', error);
        }
    }

    // ==================== HELPER METHODS ====================
    formatCurrency(amount) {
        if (!amount) return '$0.00';
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(amount);
    }

    formatCurrencyShort(amount) {
        if (!amount) return '$0';
        if (amount >= 1000000) {
            return '$' + (amount / 1000000).toFixed(1) + 'M';
        }
        if (amount >= 1000) {
            return '$' + (amount / 1000).toFixed(1) + 'K';
        }
        return this.formatCurrency(amount);
    }

    get formattedRevenue() {
        return this.formatCurrency(this.state.total_revenue || 0);
    }

    get formattedOrders() {
        return (this.state.total_orders || 0).toLocaleString();
    }

    get formattedCustomers() {
        return (this.state.total_customers || 0).toLocaleString();
    }

    get formattedProducts() {
        return (this.state.total_products || 0).toLocaleString();
    }

    get formattedPendingOrders() {
        return (this.state.pending_orders || 0).toLocaleString();
    }

    get formattedLowStock() {
        return (this.state.low_stock || 0).toLocaleString();
    }

    get ordersProgress() {
        const target = Math.max(100, this.state.total_orders * 0.1);
        return Math.min(100, Math.round((this.state.current_month_orders / target) * 100));
    }

    get revenueProgress() {
        const target = Math.max(50000, this.state.total_revenue * 0.1);
        return Math.min(100, Math.round((this.state.current_month_revenue / target) * 100));
    }

    get customersProgress() {
        const target = Math.max(50, this.state.total_customers * 0.1);
        return Math.min(100, Math.round((this.state.current_month_customers / target) * 100));
    }

    get pendingProgress() {
        const target = Math.max(10, this.state.total_orders * 0.05);
        return Math.min(100, Math.round((this.state.pending_orders / target) * 100));
    }

    get lowStockProgress() {
        const target = Math.max(5, this.state.inventory_total * 0.1);
        return Math.min(100, Math.round((this.state.low_stock / target) * 100));
    }

    getGrowthIndicator(value) {
        if (value > 0) return 'success';
        if (value < 0) return 'danger';
        return 'secondary';
    }

    getGrowthIcon(value) {
        if (value > 0) return 'fa-arrow-up';
        if (value < 0) return 'fa-arrow-down';
        return 'fa-minus';
    }
}

// Register the dashboard action
registry.category("actions").add(
    "jabin_dashboard.dashboard_view",
    JabinDashboard
);