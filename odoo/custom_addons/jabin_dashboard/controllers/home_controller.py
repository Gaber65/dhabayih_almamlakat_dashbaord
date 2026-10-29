import json
import re
import urllib.parse
from odoo import http, fields, _
from odoo.http import request
from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder
from odoo.addons.jabin_security.utils.token_auth import require_token

from ..services.product_service import ProductService
from ..services.category_service import CategoryService
from ..services.banner_service import BannerService
from ..controllers.product_controller import _serialize_product, _get_lang

class HomeController(BaseApiController):
    """Home REST API Controller."""

    @http.route(
        "/api/v1/home",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        cors="*",
    )
    def get_home_data(self, **kwargs):
        """Get aggregated home page data with optional authentication."""
        with self.handle() as ctx:
            lang = _get_lang()
            base_url = request.httprequest.host_url.rstrip('/')
            env = request.env

            # Safely attempt optional user authentication via Bearer token
            user_id = None
            try:
                raw_header = request.httprequest.headers.get("Authorization", "")
                if raw_header:
                    parts = raw_header.split(None, 1)
                    if len(parts) == 2 and parts[0].lower() == 'bearer':
                        token = parts[1].strip()
                        from odoo.addons.jabin_security.utils.jwt_utils import JWTUtils
                        claims = JWTUtils.decode_token(token)
                        user_id = JWTUtils.get_user_id(claims)
            except Exception:
                # Invalid or expired token is ignored -> treated as guest
                user_id = None

            if not user_id and request.env.user and request.env.user.id != env.ref('base.public_user').id:
                user_id = request.env.user.id

            user_highlight = None
            delivery_location = None

            if user_id:
                u = env['res.users'].sudo().browse(user_id)
                if u.exists():
                    user_highlight = u.to_public_dict() if hasattr(u, 'to_public_dict') else {
                        "id": u.id,
                        "name": u.name,
                        "email": u.email,
                    }
                    # Populate delivery location for authenticated user
                    branch = env["jabin.branch"].sudo().search([("active", "=", True)], limit=1, order="name")
                    if branch:
                        delivery_location = {
                            "id": branch.id,
                            "name": branch.name,
                            "address": branch.address,
                            "city": branch.city,
                            "latitude": branch.latitude,
                            "longitude": branch.longitude,
                        }

            # 2. Dynamic Banners (Public)
            banners = BannerService.get_banners(
                env,
                domain=[('active', '=', True)],
                limit=10,
                lang=lang
            )
            banners_data = [
                {
                    "id": b.id,
                    "name": b.name,
                    "image": BaseApiController.build_image_url("banner", b.id, "image", bool(b.image)),
                    "image_url": BaseApiController.build_image_url("banner", b.id, "image", bool(b.image)),
                    "banner_type": getattr(b, "banner_type", "offer"),
                    "offer_id": b.offer_id.id if getattr(b, "offer_id", None) else None,
                    "deep_link": getattr(b, "deep_link", None) or (f"jabin://offers/{b.offer_id.id}" if getattr(b, "offer_id", None) else "jabin://offers"),
                }
                for b in banners
            ]

            # 2.1 Active Offers
            today = fields.Date.context_today(env['jabin.offer']) if 'jabin.offer' in env else None
            offers_data = []
            if 'jabin.offer' in env:
                active_offers = env['jabin.offer'].sudo().search([
                    ('active', '=', True),
                    ('start_date', '<=', today),
                    '|',
                    ('end_date', '=', False),
                    ('end_date', '>=', today)
                ], order="sequence, id desc", limit=6)
                from .offer_controller import OfferController
                offer_ctrl = OfferController()
                offers_data = [offer_ctrl._serialize_offer(o, include_products=True) for o in active_offers]

                # Automatically include active offers with banner images in home banners
                existing_offer_ids = {b.offer_id.id for b in banners if getattr(b, 'offer_id', None)}
                offer_banners = []
                for off in active_offers:
                    if off.id not in existing_offer_ids:
                        img_url = BaseApiController.build_image_url("jabin.offer", off.id, "banner_image", bool(off.banner_image))
                        if img_url:
                            offer_banners.append({
                                "id": 10000 + off.id,
                                "name": off.name,
                                "image": img_url,
                                "image_url": img_url,
                                "banner_type": "offer",
                                "offer_id": off.id,
                                "deep_link": f"jabin://offers/{off.id}",
                            })
                if offer_banners:
                    banners_data = offer_banners + banners_data

            # 3. Jabin Highlight (Public Stories Feed)
            jabin_highlight = []
            if 'jabin.highlight.service' in env:
                jabin_highlight = env['jabin.highlight.service'].sudo().get_feed()

            # 4. Categories (Public)
            categories = CategoryService.get_categories(
                env,
                domain=[('active', '=', True)],
                limit=15,
                lang=lang,
                order="sequence, name"
            )
            categories_data = [
                {
                    "id": c.id,
                    "name": c.name,
                    "image": BaseApiController.build_image_url("jabin.category", c.id, "image", bool(c.image)),
                    "image_url": BaseApiController.build_image_url("jabin.category", c.id, "image", bool(c.image)),
                    "sequence": c.sequence,
                    "product_count": c.product_count,
                }
                for c in categories
            ]

            # 5. Featured Products (Public)
            featured, _total = ProductService.get_list(
                env,
                domain=[('active', '=', True)],
                limit=10,
                order="id desc",
                lang=lang
            )
            featured_data = [_serialize_product(p) for p in featured]

            # 6. Best Sellers (Public)
            best_sellers, _total = ProductService.get_list(
                env,
                domain=[('active', '=', True)],
                limit=10,
                order="id desc",
                lang=lang
            )
            best_sellers_data = [_serialize_product(p) for p in best_sellers]

            # 7. Recommended Products (Public)
            recommended, _total = ProductService.get_list(
                env,
                domain=[('active', '=', True)],
                limit=10,
                order="id desc",
                lang=lang
            )
            recommended_data = [_serialize_product(p) for p in recommended]

            # 8. WhatsApp & Public Settings
            wa_number = env['ir.config_parameter'].sudo().get_param('jabin.whatsapp_number', '+966500000000')
            wa_msg = env['ir.config_parameter'].sudo().get_param('jabin.whatsapp_default_message', 'مرحباً، أود الاستفسار عن ذبائح المملكة')
            wa_enabled = env['ir.config_parameter'].sudo().get_param('jabin.whatsapp_enabled', 'True') in ('True', 'true', '1')
            import re
            import urllib.parse
            clean_digits = re.sub(r'[^0-9]', '', wa_number)
            wa_url = f"https://wa.me/{clean_digits}?text={urllib.parse.quote(wa_msg)}"
            whatsapp_data = {
                "enabled": wa_enabled,
                "phone": wa_number,
                "number": wa_number,
                "default_message": wa_msg,
                "chat_url": wa_url,
            }

            response_data = {
                "delivery_location": delivery_location,
                "user_highlight": user_highlight,
                "jabin_highlight": jabin_highlight,
                "whatsapp": whatsapp_data,
                "banners": banners_data,
                "offers": offers_data,
                "categories": categories_data,
                "featured_products": featured_data,
                "best_sellers": best_sellers_data,
                "recommended_products": recommended_data,
            }

            ctx.set_body(
                ResponseBuilder.success(
                    data=response_data,
                    message=_("Home data retrieved successfully"),
                )
            )

        return ctx.response

    @http.route(
        "/api/v1/settings/public",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        cors="*",
    )
    def get_public_settings(self, **kwargs):
        """Get publicly available system settings (WhatsApp, Loyalty rates, delivery fee)."""
        with self.handle() as ctx:
            env = request.env
            wa_number = env['ir.config_parameter'].sudo().get_param('jabin.whatsapp_number', '+966500000000')
            wa_msg = env['ir.config_parameter'].sudo().get_param('jabin.whatsapp_default_message', 'مرحباً، أود الاستفسار عن ذبائح المملكة')
            wa_enabled = env['ir.config_parameter'].sudo().get_param('jabin.whatsapp_enabled', 'True') in ('True', 'true', '1')
            delivery_fee = float(env['ir.config_parameter'].sudo().get_param('jabin.delivery.fee', '0.0'))

            import re
            import urllib.parse
            clean_digits = re.sub(r'[^0-9]', '', wa_number)
            wa_url = f"https://wa.me/{clean_digits}?text={urllib.parse.quote(wa_msg)}"
            config = env['ir.config_parameter'].sudo()

            app_updates = {
                "android": {
                    "latest_version": config.get_param('jabin.app.android.latest_version', '1.0.0'),
                    "min_version": config.get_param('jabin.app.android.min_version', '1.0.0'),
                    "force_update": config.get_param('jabin.app.android.force_update', 'false').lower() in ('true', '1'),
                    "store_url": config.get_param('jabin.app.android.store_url', 'https://play.google.com/store/apps/details?id=com.dhabayih.lmamlaka'),
                },
                "ios": {
                    "latest_version": config.get_param('jabin.app.ios.latest_version', '1.0.0'),
                    "min_version": config.get_param('jabin.app.ios.min_version', '1.0.0'),
                    "force_update": config.get_param('jabin.app.ios.force_update', 'false').lower() in ('true', '1'),
                    "store_url": config.get_param('jabin.app.ios.store_url', 'https://apps.apple.com/app/id6470000000'),
                },
                "title_ar": config.get_param('jabin.app.update_title_ar', 'تحديث جديد متوفر'),
                "title_en": config.get_param('jabin.app.update_title_en', 'New Update Available'),
                "message_ar": config.get_param('jabin.app.update_message_ar', 'يتوفر إصدار جديد من تطبيق ذبائح المملكة بمزايا وتحسينات جديدة. يرجى التحديث للمتابعة.'),
                "message_en": config.get_param('jabin.app.update_message_en', 'A new version of Dhabayih Al-Mamlaka is available with new improvements. Please update to continue.'),
            }

            data = {
                "whatsapp": {
                    "enabled": wa_enabled,
                    "phone": wa_number,
                    "number": wa_number,
                    "default_message": wa_msg,
                    "chat_url": wa_url,
                },
                "support_phone": config.get_param('jabin.support_phone', '920000000'),
                "delivery_fee": delivery_fee,
                "app_updates": app_updates,
            }
            ctx.set_body(ResponseBuilder.success(data=data, message=_("Settings retrieved successfully.")))
        return ctx.response

    @http.route(
        "/api/v1/app/check_update",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        cors="*",
    )
    def check_app_update(self, **kwargs):
        """Check whether the client app requires a mandatory (force) or optional update."""
        with self.handle() as ctx:
            env = request.env
            config = env['ir.config_parameter'].sudo()

            platform = (kwargs.get('platform') or 'android').lower().strip()
            if platform not in ('android', 'ios'):
                platform = 'android'

            current_version = (kwargs.get('version') or kwargs.get('current_version') or '1.0.0').strip()
            lang = (kwargs.get('lang') or 'ar').lower().strip()

            latest_version = config.get_param(f'jabin.app.{platform}.latest_version', '1.0.0').strip()
            min_version = config.get_param(f'jabin.app.{platform}.min_version', '1.0.0').strip()
            force_flag = config.get_param(f'jabin.app.{platform}.force_update', 'false').lower() in ('true', '1')
            store_url = config.get_param(
                f'jabin.app.{platform}.store_url',
                'https://play.google.com/store/apps/details?id=com.dhabayih.lmamlaka' if platform == 'android' else 'https://apps.apple.com/app/id6470000000'
            ).strip()

            def _parse_version(v_str):
                clean = (v_str or '0').split('+')[0].strip()
                res = []
                for p in clean.split('.'):
                    try:
                        res.append(int(p))
                    except (ValueError, TypeError):
                        res.append(0)
                return res

            def _cmp_versions(v1, v2):
                p1, p2 = _parse_version(v1), _parse_version(v2)
                ml = max(len(p1), len(p2))
                p1 += [0] * (ml - len(p1))
                p2 += [0] * (ml - len(p2))
                for a, b in zip(p1, p2):
                    if a > b:
                        return 1
                    if a < b:
                        return -1
                return 0

            is_below_min = _cmp_versions(current_version, min_version) < 0
            is_below_latest = _cmp_versions(current_version, latest_version) < 0

            # Force update is triggered if current version is below minimum supported version,
            # or if the admin explicitly enabled the global force_update flag and an update exists.
            force_update = is_below_min or (force_flag and is_below_latest)
            update_available = is_below_latest or is_below_min

            if lang == 'en':
                title = config.get_param('jabin.app.update_title_en', 'New Update Available')
                message = config.get_param('jabin.app.update_message_en', 'A new version of Dhabayih Al-Mamlaka is available with new improvements. Please update to continue.')
            else:
                title = config.get_param('jabin.app.update_title_ar', 'تحديث جديد متوفر')
                message = config.get_param('jabin.app.update_message_ar', 'يتوفر إصدار جديد من تطبيق ذبائح المملكة بمزايا وتحسينات جديدة. يرجى التحديث للمتابعة.')

            data = {
                "update_available": update_available,
                "force_update": force_update,
                "current_version": current_version,
                "latest_version": latest_version,
                "min_version": min_version,
                "platform": platform,
                "store_url": store_url,
                "title": title,
                "message": message,
            }
            ctx.set_body(ResponseBuilder.success(data=data, message=_("Update status retrieved successfully.")))
        return ctx.response

    @http.route(
        ["/api/v1/admin/settings/app_version", "/api/v1/settings/app_version"],
        type="http",
        auth="public",
        methods=["GET", "POST", "PUT"],
        csrf=False,
        cors="*",
    )
    def manage_app_version_settings(self, **kwargs):
        """Get or update mobile app version update rules (force/optional)."""
        env = request.env
        config = env['ir.config_parameter'].sudo()

        if request.httprequest.method in ("POST", "PUT"):
            denied = require_token()
            if denied:
                return denied

            with self.handle() as ctx:
                content_type = request.httprequest.content_type or ""
                vals = {}
                if "multipart/form-data" in content_type:
                    vals = dict(request.httprequest.form.items())
                else:
                    raw = request.httprequest.data
                    if raw:
                        try:
                            vals = json.loads(raw)
                        except json.JSONDecodeError:
                            raise ValueError("Invalid JSON payload.")

                # Android parameters
                if "android_latest_version" in vals:
                    config.set_param('jabin.app.android.latest_version', str(vals['android_latest_version']).strip())
                if "android_min_version" in vals:
                    config.set_param('jabin.app.android.min_version', str(vals['android_min_version']).strip())
                if "android_force_update" in vals:
                    val = vals['android_force_update']
                    is_true = val if isinstance(val, bool) else str(val).lower() not in ('false', '0', 'no')
                    config.set_param('jabin.app.android.force_update', str(is_true).lower())
                if "android_store_url" in vals:
                    config.set_param('jabin.app.android.store_url', str(vals['android_store_url']).strip())

                # iOS parameters
                if "ios_latest_version" in vals:
                    config.set_param('jabin.app.ios.latest_version', str(vals['ios_latest_version']).strip())
                if "ios_min_version" in vals:
                    config.set_param('jabin.app.ios.min_version', str(vals['ios_min_version']).strip())
                if "ios_force_update" in vals:
                    val = vals['ios_force_update']
                    is_true = val if isinstance(val, bool) else str(val).lower() not in ('false', '0', 'no')
                    config.set_param('jabin.app.ios.force_update', str(is_true).lower())
                if "ios_store_url" in vals:
                    config.set_param('jabin.app.ios.store_url', str(vals['ios_store_url']).strip())

                # Messages
                if "title_ar" in vals:
                    config.set_param('jabin.app.update_title_ar', str(vals['title_ar']).strip())
                if "title_en" in vals:
                    config.set_param('jabin.app.update_title_en', str(vals['title_en']).strip())
                if "message_ar" in vals:
                    config.set_param('jabin.app.update_message_ar', str(vals['message_ar']).strip())
                if "message_en" in vals:
                    config.set_param('jabin.app.update_message_en', str(vals['message_en']).strip())

                data = {
                    "android": {
                        "latest_version": config.get_param('jabin.app.android.latest_version', '1.0.0'),
                        "min_version": config.get_param('jabin.app.android.min_version', '1.0.0'),
                        "force_update": config.get_param('jabin.app.android.force_update', 'false').lower() in ('true', '1'),
                        "store_url": config.get_param('jabin.app.android.store_url', 'https://play.google.com/store/apps/details?id=com.dhabayih.lmamlaka'),
                    },
                    "ios": {
                        "latest_version": config.get_param('jabin.app.ios.latest_version', '1.0.0'),
                        "min_version": config.get_param('jabin.app.ios.min_version', '1.0.0'),
                        "force_update": config.get_param('jabin.app.ios.force_update', 'false').lower() in ('true', '1'),
                        "store_url": config.get_param('jabin.app.ios.store_url', 'https://apps.apple.com/app/id6470000000'),
                    },
                    "title_ar": config.get_param('jabin.app.update_title_ar', 'تحديث جديد متوفر'),
                    "title_en": config.get_param('jabin.app.update_title_en', 'New Update Available'),
                    "message_ar": config.get_param('jabin.app.update_message_ar', 'يتوفر إصدار جديد من تطبيق ذبائح المملكة بمزايا وتحسينات جديدة. يرجى التحديث للمتابعة.'),
                    "message_en": config.get_param('jabin.app.update_message_en', 'A new version of Dhabayih Al-Mamlaka is available with new improvements. Please update to continue.'),
                }
                ctx.set_body(ResponseBuilder.success(data=data, message=_("App version settings updated successfully.")))
            return ctx.response

        # GET method
        with self.handle() as ctx:
            data = {
                "android": {
                    "latest_version": config.get_param('jabin.app.android.latest_version', '1.0.0'),
                    "min_version": config.get_param('jabin.app.android.min_version', '1.0.0'),
                    "force_update": config.get_param('jabin.app.android.force_update', 'false').lower() in ('true', '1'),
                    "store_url": config.get_param('jabin.app.android.store_url', 'https://play.google.com/store/apps/details?id=com.dhabayih.lmamlaka'),
                },
                "ios": {
                    "latest_version": config.get_param('jabin.app.ios.latest_version', '1.0.0'),
                    "min_version": config.get_param('jabin.app.ios.min_version', '1.0.0'),
                    "force_update": config.get_param('jabin.app.ios.force_update', 'false').lower() in ('true', '1'),
                    "store_url": config.get_param('jabin.app.ios.store_url', 'https://apps.apple.com/app/id6470000000'),
                },
                "title_ar": config.get_param('jabin.app.update_title_ar', 'تحديث جديد متوفر'),
                "title_en": config.get_param('jabin.app.update_title_en', 'New Update Available'),
                "message_ar": config.get_param('jabin.app.update_message_ar', 'يتوفر إصدار جديد من تطبيق ذبائح المملكة بمزايا وتحسينات جديدة. يرجى التحديث للمتابعة.'),
                "message_en": config.get_param('jabin.app.update_message_en', 'A new version of Dhabayih Al-Mamlaka is available with new improvements. Please update to continue.'),
            }
            ctx.set_body(ResponseBuilder.success(data=data, message=_("App version settings retrieved successfully.")))
        return ctx.response

    @http.route(
        ["/api/v1/admin/settings/contact", "/api/v1/settings/contact"],
        type="http",
        auth="public",
        methods=["PUT", "POST"],
        csrf=False,
        cors="*",
    )
    def update_contact_settings(self, **kwargs):
        """Update WhatsApp and customer support contact settings."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            content_type = request.httprequest.content_type or ""
            vals = {}
            if "multipart/form-data" in content_type:
                vals = dict(request.httprequest.form.items())
            else:
                raw = request.httprequest.data
                if raw:
                    try:
                        vals = json.loads(raw)
                    except json.JSONDecodeError:
                        raise ValueError("Invalid JSON payload.")

            env = request.env
            config = env['ir.config_parameter'].sudo()

            if "whatsapp_number" in vals:
                config.set_param('jabin.whatsapp_number', str(vals['whatsapp_number']).strip())
            elif "phone" in vals:
                config.set_param('jabin.whatsapp_number', str(vals['phone']).strip())

            if "whatsapp_default_message" in vals:
                config.set_param('jabin.whatsapp_default_message', str(vals['whatsapp_default_message']).strip())
            elif "default_message" in vals:
                config.set_param('jabin.whatsapp_default_message', str(vals['default_message']).strip())

            if "whatsapp_enabled" in vals:
                enabled_val = vals["whatsapp_enabled"]
                is_enabled = enabled_val if isinstance(enabled_val, bool) else str(enabled_val).lower() not in ("false", "0", "no")
                config.set_param('jabin.whatsapp_enabled', str(is_enabled))
            elif "enabled" in vals:
                enabled_val = vals["enabled"]
                is_enabled = enabled_val if isinstance(enabled_val, bool) else str(enabled_val).lower() not in ("false", "0", "no")
                config.set_param('jabin.whatsapp_enabled', str(is_enabled))

            if "support_phone" in vals:
                config.set_param('jabin.support_phone', str(vals['support_phone']).strip())

            wa_number = config.get_param('jabin.whatsapp_number', '+966500000000')
            wa_msg = config.get_param('jabin.whatsapp_default_message', 'مرحباً، أود الاستفسار عن ذبائح المملكة')
            wa_enabled = config.get_param('jabin.whatsapp_enabled', 'True') in ('True', 'true', '1')
            support_phone = config.get_param('jabin.support_phone', '920000000')
            delivery_fee = float(config.get_param('jabin.delivery.fee', '0.0'))

            clean_digits = re.sub(r'[^0-9]', '', wa_number)
            wa_url = f"https://wa.me/{clean_digits}?text={urllib.parse.quote(wa_msg)}"

            data = {
                "whatsapp": {
                    "enabled": wa_enabled,
                    "phone": wa_number,
                    "number": wa_number,
                    "default_message": wa_msg,
                    "chat_url": wa_url,
                },
                "support_phone": support_phone,
                "delivery_fee": delivery_fee,
            }
            ctx.set_body(ResponseBuilder.success(data=data, message=_("Contact settings updated successfully.")))
        return ctx.response

    @http.route(
        ["/api/v1/admin/settings/invoice", "/api/v1/settings/invoice"],
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        cors="*",
    )
    def get_invoice_settings(self, **kwargs):
        """Get company tax & invoice printing settings."""
        with self.handle() as ctx:
            env = request.env
            config = env['ir.config_parameter'].sudo()
            main_comp = env.ref('base.main_company', raise_if_not_found=False) or env['res.company'].sudo().search([], limit=1)

            company_raw = (main_comp.name or "") if main_comp else ""
            company_name = "ذبائح المملكة" if (not company_raw or "YourCompany" in company_raw or "My Company" in company_raw) else company_raw

            data = {
                "company_name": company_name,
                "company_name_en": "Dhabayih Lmamlaka",
                "vat_number": (main_comp.vat if main_comp else "") or "310198765400003",
                "cr_number": (main_comp.company_registry if main_comp else "") or "1010892341",
                "phone": (main_comp.phone if main_comp else "") or config.get_param('jabin.support_phone', '0568741660'),
                "email": (main_comp.email if main_comp else "") or "info@dhabayih.com",
                "address": f"{main_comp.street or 'طريق الملك فهد'} - {main_comp.city or 'الرياض'}" if main_comp else "المملكة العربية السعودية - الرياض",
                "paper_format": config.get_param('jabin_invoice.paper_format', 'thermal_80'),
                "receipt_width": int(config.get_param('jabin_invoice.receipt_width', 80)),
                "show_logo": config.get_param('jabin_invoice.show_logo', 'True') in ('True', 'true', '1'),
                "show_qr": config.get_param('jabin_invoice.show_qr', 'True') in ('True', 'true', '1'),
                "header_note": config.get_param('jabin_invoice.header_note', 'ذبائح ولحوم بلدية طازجة وفق الشريعة الإسلامية'),
                "footer_note": config.get_param('jabin_invoice.footer_note', 'شكراً لتسوقكم من ذبائح المملكة | خدمة العملاء: 0568741660'),
                "vat_rate": float(config.get_param('jabin_invoice.vat_rate', '15.0')),
                "prefix": config.get_param('jabin_invoice.prefix', 'INV-'),
            }
            ctx.set_body(ResponseBuilder.success(data=data, message=_("Invoice settings retrieved successfully.")))
        return ctx.response

    @http.route(
        ["/api/v1/admin/settings/invoice", "/api/v1/settings/invoice"],
        type="http",
        auth="public",
        methods=["POST", "PUT"],
        csrf=False,
        cors="*",
    )
    def update_invoice_settings(self, **kwargs):
        """Update company tax & invoice printing settings."""
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            content_type = request.httprequest.content_type or ""
            vals = {}
            if "multipart/form-data" in content_type:
                vals = dict(request.httprequest.form.items())
            else:
                raw = request.httprequest.data
                if raw:
                    try:
                        vals = json.loads(raw)
                    except json.JSONDecodeError:
                        raise ValueError("Invalid JSON payload.")

            env = request.env
            config = env['ir.config_parameter'].sudo()
            main_comp = env.ref('base.main_company', raise_if_not_found=False) or env['res.company'].sudo().search([], limit=1)

            if main_comp:
                comp_vals = {}
                if "company_name" in vals and vals["company_name"]:
                    comp_vals["name"] = str(vals["company_name"]).strip()
                if "vat_number" in vals:
                    comp_vals["vat"] = str(vals["vat_number"]).strip()
                if "cr_number" in vals:
                    comp_vals["company_registry"] = str(vals["cr_number"]).strip()
                if "phone" in vals:
                    comp_vals["phone"] = str(vals["phone"]).strip()
                if "email" in vals:
                    comp_vals["email"] = str(vals["email"]).strip()
                if "address" in vals:
                    comp_vals["street"] = str(vals["address"]).strip()
                if comp_vals:
                    main_comp.sudo().write(comp_vals)

            if "paper_format" in vals:
                config.set_param('jabin_invoice.paper_format', str(vals["paper_format"]))
            if "receipt_width" in vals:
                config.set_param('jabin_invoice.receipt_width', str(int(vals["receipt_width"])))
            if "show_logo" in vals:
                val_bool = vals["show_logo"] in (True, 'True', 'true', '1', 1)
                config.set_param('jabin_invoice.show_logo', str(val_bool))
            if "show_qr" in vals:
                val_bool = vals["show_qr"] in (True, 'True', 'true', '1', 1)
                config.set_param('jabin_invoice.show_qr', str(val_bool))
            if "header_note" in vals:
                config.set_param('jabin_invoice.header_note', str(vals["header_note"]).strip())
            if "footer_note" in vals:
                config.set_param('jabin_invoice.footer_note', str(vals["footer_note"]).strip())
            if "vat_rate" in vals:
                config.set_param('jabin_invoice.vat_rate', str(float(vals["vat_rate"])))
            if "prefix" in vals:
                config.set_param('jabin_invoice.prefix', str(vals["prefix"]).strip())

            return self.get_invoice_settings()


