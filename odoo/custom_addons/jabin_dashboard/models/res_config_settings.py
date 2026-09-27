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

    whatsapp_number = fields.Char(
        string='WhatsApp Support Number (رقم الواتساب)',
        config_parameter='jabin.whatsapp_number',
        default='+966500000000',
        help='WhatsApp phone number for customer support'
    )
    whatsapp_default_message = fields.Char(
        string='WhatsApp Default Message (الرسالة الافتراضية)',
        config_parameter='jabin.whatsapp_default_message',
        default='مرحباً، أود الاستفسار عن ذبائح المملكة',
        help='Initial message pre-filled when opening WhatsApp chat'
    )
    whatsapp_enabled = fields.Boolean(
        string='Enable WhatsApp Support (تفعيل الواتساب)',
        config_parameter='jabin.whatsapp_enabled',
        default=True,
        help='Show or hide WhatsApp chat button across apps'
    )
    support_phone = fields.Char(
        string='Customer Support Phone (رقم الهاتف الموحد / الاتصال)',
        config_parameter='jabin.support_phone',
        default='920000000',
        help='Unified phone number for phone support'
    )

