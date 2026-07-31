# res_config_settings.py
from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    loyalty_earning_rate = fields.Float(
        string='Loyalty Earning Rate (Points per 1 SAR)',
        config_parameter='jabin_loyalty.earning_rate',
        default=1.0,
        help='Number of loyalty points earned for every 1 SAR spent. Default is 1 SAR = 1 Point.'
    )
    loyalty_redemption_rate = fields.Float(
        string='Loyalty Redemption Rate (Points per 1 SAR Discount)',
        config_parameter='jabin_loyalty.redemption_rate',
        default=100.0,
        help='Number of loyalty points required for 1 SAR discount. Default is 100 Points = 1 SAR.'
    )
    loyalty_min_redemption = fields.Integer(
        string='Minimum Redemption Threshold (Points)',
        config_parameter='jabin_loyalty.min_redemption',
        default=500,
        help='Minimum points required in wallet to perform redemption. Default is 500 Points.'
    )
