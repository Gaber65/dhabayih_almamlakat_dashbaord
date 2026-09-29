# -*- coding: utf-8 -*-
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

    # Invoice & Thermal Printing Settings
    invoice_paper_format = fields.Selection(
        [
            ('thermal_80', 'إيصال حراري 80مم (80mm Thermal Receipt)'),
            ('a4', 'ورقة قياسية (Standard A4)'),
        ],
        string='حجم ورق الفاتورة الافتراضي',
        config_parameter='jabin_invoice.paper_format',
        default='thermal_80',
        help='اختر التنسيق الافتراضي لطباعة الفواتير'
    )
    invoice_receipt_width = fields.Integer(
        string='عرض الإيصال الحراري بالمليمتر (Receipt Width mm)',
        config_parameter='jabin_invoice.receipt_width',
        default=80,
        help='العرض الافتراضي لورق الطابعة الحرارية (80 مم أو 72 مم)'
    )
    invoice_show_logo = fields.Boolean(
        string='إظهار شعار المتجر في الإيصال (Show Logo)',
        config_parameter='jabin_invoice.show_logo',
        default=True,
        help='إظهار لوجو ذبائح المملكة في الفاتورة والإيصال الحراري'
    )
    invoice_show_qr = fields.Boolean(
        string='إظهار باركود هيئة الزكاة (ZATCA QR)',
        config_parameter='jabin_invoice.show_qr',
        default=True,
        help='إظهار رمز الاستجابة السريع لهيئة الزكاة والضريبة والجمارك'
    )
    invoice_header_note = fields.Char(
        string='ملاحظة الترويسة (Header Note)',
        config_parameter='jabin_invoice.header_note',
        default='ذبائح ولحوم بلدية طازجة وفق الشريعة الإسلامية',
        help='عبارة تظهر تحت اسم المتجر في الفاتورة'
    )
    invoice_footer_note = fields.Char(
        string='ملاحظة التذييل (Footer Note)',
        config_parameter='jabin_invoice.footer_note',
        default='شكراً لتسوقكم من ذبائح المملكة | خدمة العملاء: 0568741660',
        help='عبارة شكر أو ملاحظات تظهر في أسفل الفاتورة'
    )

    # -------------------------------------------------------------------------
    # Authentica SA SMS & Dual-Channel OTP Settings
    # -------------------------------------------------------------------------
    authentica_api_key = fields.Char(
        string='Authentica API Key (مفتاح الربط)',
        config_parameter='authentica.api_key',
        default='',
        help='X-Authorization API key provided by Authentica SA portal (portal.authentica.sa)'
    )
    authentica_template_id = fields.Char(
        string='Authentica Template ID (معرّف القالب)',
        config_parameter='authentica.template_id',
        default='',
        help='Approved OTP template ID registered in Authentica'
    )
    authentica_sender_id = fields.Char(
        string='Authentica Sender ID (اسم المرسل)',
        config_parameter='authentica.sender_id',
        default='Dhabayih',
        help='Registered CITC/CST sender name for SMS'
    )
    authentica_method = fields.Selection(
        [
            ('sms', 'رسالة نصية فقط (SMS Only)'),
            ('whatsapp', 'واتساب فقط (WhatsApp Only)'),
            ('sms-or-whatsapp', 'رسالة نصية أو واتساب (SMS or WhatsApp)'),
        ],
        string='طريقة إرسال الرمز (Send Method)',
        config_parameter='authentica.method',
        default='sms',
        help='Delivery channel used by Authentica SA gateway'
    )
    authentica_enable_sms = fields.Boolean(
        string='تفعيل التحقق عبر الجوال (Enable SMS OTP)',
        config_parameter='authentica.enable_sms',
        default=True,
        help='Enable customer registration and login via mobile phone SMS OTP'
    )
    gmail_enable_email = fields.Boolean(
        string='تفعيل التحقق عبر البريد الإلكتروني (Enable Email OTP)',
        config_parameter='jabin_auth.enable_email',
        default=True,
        help='Enable customer registration and login via Gmail / Email OTP'
    )
    authentica_mock_mode = fields.Boolean(
        string='الوضع التجريبي (Sandbox / Mock Mode)',
        config_parameter='authentica.mock_mode',
        default=False,
        help='When enabled, OTP codes will be logged without consuming live Authentica SMS credits'
    )

    def action_check_authentica_balance(self):
        """Action button to query and display live Authentica balance."""
        self.ensure_one()
        authentica_service = self.env.get('jabin.authentica.service')
        if not authentica_service:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'خدمة Authentica غير متوفرة',
                    'message': 'موديل jabin.authentica.service غير مثبت في النظام.',
                    'type': 'danger',
                    'sticky': False,
                }
            }

        res = authentica_service.sudo().get_balance()
        if res.get('success'):
            balance = res.get('balance', 0)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'رصيد Authentica المتبقي',
                    'message': f'رصيد الرسائل المتاح حالياً بحسابك في Authentica هو: {balance} رسالة/عملية.',
                    'type': 'success',
                    'sticky': True,
                }
            }
        else:
            error_msg = res.get('message', 'تعذر جلب الرصيد من البوابة')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'خطأ في الاتصال ببوابة Authentica',
                    'message': f'فشل الاستعلام: {error_msg}',
                    'type': 'warning',
                    'sticky': True,
                }
            }
