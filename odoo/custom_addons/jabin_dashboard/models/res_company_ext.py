# -*- coding: utf-8 -*-
from odoo import models, api
import base64
import os
import logging

_logger = logging.getLogger(__name__)

class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model
    def init_dhabayih_company_defaults(self):
        """Initialize company details, VAT, registry, and branding for Dhabayih Lmamlaka."""
        main_comp = self.env.ref('base.main_company', raise_if_not_found=False) or self.search([], limit=1)
        if not main_comp:
            return

        company_details_html = (
            "<p><strong>ذبائح المملكة - Dhabayih Lmamlaka</strong><br/>"
            "المملكة العربية السعودية - الرياض<br/>"
            "الرقم الضريبي: 310198765400003 | السجل التجاري: 1010892341<br/>"
            "خدمة العملاء والطلب السريع: 0568741660 | 920000000</p>"
        )

        vals = {
            'name': 'ذبائح المملكة',
            'street': 'طريق الملك فهد',
            'city': 'الرياض',
            'zip': '12214',
            'phone': '0568741660',
            'email': 'info@dhabayih.com',
            'website': 'https://dhabayih.com',
            'vat': '310198765400003',
            'company_registry': '1010892341',
            'primary_color': '#0f766e',
            'secondary_color': '#042f2e',
            'report_header': 'ذبائح المملكة - لحوم وذبائح بلدية طازجة',
            'company_details': company_details_html,
        }

        sa_country = self.env.ref('base.sa', raise_if_not_found=False)
        if sa_country:
            vals['country_id'] = sa_country.id

        logo_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'img', 'app_logo.png')
        if os.path.exists(logo_path):
            try:
                with open(logo_path, 'rb') as f:
                    vals['logo'] = base64.b64encode(f.read())
            except Exception as e:
                _logger.warning("Failed to load Dhabayih company logo from %s: %s", logo_path, e)

        main_comp.sudo().write(vals)
        _logger.info("Successfully updated company defaults for: %s (ID: %s)", main_comp.name, main_comp.id)
