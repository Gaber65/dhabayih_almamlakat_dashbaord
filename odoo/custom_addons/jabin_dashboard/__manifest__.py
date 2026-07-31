{
    'name': 'JABIN Dashboard',
    'version': '17.0.1.0.0',
    'category': 'Sales',
    'summary': 'JABIN Admin Dashboard Framework',
    'description': """
        JABIN Admin Dashboard Foundation Module
        Provides the dashboard framework for JABIN ERP system.
        No business logic included - only dashboard infrastructure.
    """,
    'author': 'JABIN',
    'website': 'https://www.jabin.com',
    'depends': [
        'base',
        'web',
        'jabin_core',
        'jabin_auth',
        'jabin_users',
        'jabin_api',
        'jabin_highlight',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/dashboard_data.xml',
        'data/loyalty_data.xml',
        'data/firebase_data.xml',

        'views/jabin_users_views.xml',  # Users views and actions FIRST

        'views/dashboard_views.xml',
        'views/category_views.xml',
        'views/product_views.xml',
        'views/cutting_option_views.xml',
        'views/packaging_views.xml',
        'views/excluded_part_views.xml',
        'views/banner_views.xml',
        'views/coupon_views.xml',

        'views/order_views.xml',   # Orders, Payments, Activity views + their actions
        'views/loyalty_transaction_views.xml',
        'views/loyalty_adjust_wizard_views.xml',
        'views/send_notification_wizard_views.xml',
        'views/res_config_settings_views.xml',

        'views/device_views.xml',
        'views/notification_views.xml',

        'views/actions.xml',  # Load after all views are defined
        'views/menus.xml',  # Load after all actions are defined
    ],



    'assets': {
        'web.assets_backend': [
            'jabin_dashboard/static/src/css/dashboard.scss',
            'jabin_dashboard/static/src/js/dashboard.js',
            'jabin_dashboard/static/src/xml/dashboard_templates.xml',
        ],
    },
    'demo': [
        'data/demo_data.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': True,
}