# notification_service.py
import json
from typing import Dict, Any, List, Optional
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError

from ..validators.device_validator import DeviceValidator
from ..validators.notification_validator import NotificationValidator
from .firebase_service import FirebaseService
from odoo.addons.jabin_core import JabinLogger

_logger = JabinLogger.get("notification.service")


class NotificationService(models.AbstractModel):
    _name = 'jabin.notification.service'
    _description = 'JABIN Notification Management Service'

    # --- Device Management Methods ---
    @api.model
    def register_device(self, env, customer_id: int, device_vals: Dict[str, Any]):
        """Register or update a customer device token."""
        DeviceValidator.validate_register(device_vals)

        customer = env['res.users'].sudo().browse(customer_id)
        if not customer.exists():
            raise ValidationError(_("Customer not found."))

        fcm_token = str(device_vals['fcm_token']).strip()
        device = env['jabin.device'].sudo().search([('fcm_token', '=', fcm_token)], limit=1)

        vals = {
            'user_id': customer.id,
            'device_name': device_vals.get('device_name', 'Mobile Device'),
            'device_type': device_vals.get('device_type', 'android'),
            'app_version': device_vals.get('app_version'),
            'os_version': device_vals.get('os_version'),
            'language': device_vals.get('language', 'en'),
            'timezone': device_vals.get('timezone', 'UTC'),
            'is_active': True,
            'last_seen': fields.Datetime.now(),
            'updated_at': fields.Datetime.now()
        }

        if device:
            device.sudo().write(vals)
        else:
            if 'uuid' in device_vals and device_vals['uuid']:
                vals['uuid'] = device_vals['uuid']
            vals['fcm_token'] = fcm_token
            device = env['jabin.device'].sudo().create(vals)

        _logger.info(f"Registered device ID {device.id} for user ID {customer.id}")
        return device

    @api.model
    def update_token(self, env, customer_id: int, old_token_or_uuid: Optional[str], new_token: str):
        """Update FCM token for existing customer device."""
        DeviceValidator.validate_update_token(new_token)

        clean_new = new_token.strip()
        device = False

        if old_token_or_uuid:
            clean_old = old_token_or_uuid.strip()
            device = env['jabin.device'].sudo().search([
                '|', ('fcm_token', '=', clean_old), ('uuid', '=', clean_old),
                ('user_id', '=', customer_id)
            ], limit=1)

        if not device:
            device = env['jabin.device'].sudo().search([
                ('user_id', '=', customer_id),
                ('is_active', '=', True)
            ], order='last_seen desc', limit=1)

        if device:
            device.sudo().write({
                'fcm_token': clean_new,
                'is_active': True,
                'last_seen': fields.Datetime.now(),
                'updated_at': fields.Datetime.now()
            })
            return device
        else:
            # Create device if not found
            return self.register_device(env, customer_id, {'fcm_token': clean_new, 'device_type': 'android'})

    @api.model
    def logout_device(self, env, customer_id: int, token_or_uuid: Optional[str] = None):
        """Deactivate customer device on logout."""
        domain = [('user_id', '=', customer_id)]
        if token_or_uuid:
            clean = token_or_uuid.strip()
            domain.append(('|', ('fcm_token', '=', clean), ('uuid', '=', clean)))

        devices = env['jabin.device'].sudo().search(domain)
        if devices:
            devices.deactivate()
            _logger.info(f"Deactivated {len(devices)} device(s) for user ID {customer_id} on logout.")
        return True

    # --- Notification Dispatcher Methods ---
    @api.model
    def send_to_user(
        self,
        env,
        user_id: int,
        title: str,
        body: str,
        notification_type: str = 'system',
        deep_link: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        order_id: Optional[int] = None,
        priority: str = 'normal',
        image_url: Optional[str] = None
    ):
        """Send push notification to all active devices of a customer and save history record."""
        payload_vals = {
            'title': title,
            'body': body,
            'notification_type': notification_type,
            'priority': priority
        }
        NotificationValidator.validate_send(payload_vals)

        customer = env['res.users'].sudo().browse(user_id)
        if not customer.exists():
            _logger.warning(f"Cannot send notification: User ID {user_id} not found.")
            return False

        if hasattr(customer, 'push_notifications_enabled') and not customer.push_notifications_enabled:
            _logger.info(f"Notification skipped: User ID {user_id} has push notifications disabled.")
            return False

        full_data = dict(data or {})
        if deep_link:
            full_data['deep_link'] = deep_link
        if order_id:
            full_data['order_id'] = str(order_id)
        full_data['type'] = notification_type

        # Create history record
        notif = env['jabin.notification'].sudo().create({
            'user_id': customer.id,
            'title': title,
            'body': body,
            'image_url': image_url,
            'notification_type': notification_type,
            'priority': priority,
            'deep_link': deep_link,
            'data_json': json.dumps(full_data),
            'status': 'pending',
            'order_id': order_id,
            'created_by': env.user.id if env.user else False
        })

        active_devices = env['jabin.device'].sudo().search([
            ('user_id', '=', customer.id),
            ('is_active', '=', True)
        ])

        if not active_devices:
            _logger.info(f"User ID {customer.id} has no active FCM devices. Notification saved in history as pending.")
            return notif

        tokens = active_devices.mapped('fcm_token')

        if len(tokens) == 1:
            success = FirebaseService.send(
                env=env,
                token=tokens[0],
                title=title,
                body=body,
                data=full_data,
                image_url=image_url
            )
            if success:
                notif.mark_as_sent()
            else:
                notif.mark_as_failed("FCM send failed.")
        else:
            result = FirebaseService.send_multicast(
                env=env,
                tokens=tokens,
                title=title,
                body=body,
                data=full_data,
                image_url=image_url
            )
            if result.get('success_count', 0) > 0:
                notif.mark_as_sent()
            else:
                notif.mark_as_failed("FCM multicast failed.")

        return notif

    @api.model
    def send_to_admins(
        self,
        env,
        title: str,
        body: str,
        required_permission: Optional[str] = None,
        notification_type: str = 'admin',
        deep_link: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ):
        """Send push notification to Admin mobile application users."""
        admin_users = env['res.users'].sudo().search([
            ('user_type', '=', 'admin'),
            ('status', '=', 'active')
        ])

        if required_permission and 'jabin.permission' in env:
            filtered_admins = []
            for admin in admin_users:
                perms = admin.get_permission_codes() if hasattr(admin, 'get_permission_codes') else set()
                if required_permission in perms or admin.has_group('base.group_system'):
                    filtered_admins.append(admin)
            admin_users = env['res.users'].sudo().browse([a.id for a in filtered_admins])

        if not admin_users:
            _logger.info("No matching admin users found for push notification.")
            return True

        for admin in admin_users:
            self.send_to_user(
                env=env,
                user_id=admin.id,
                title=title,
                body=body,
                notification_type=notification_type,
                deep_link=deep_link,
                data=data,
                priority='high'
            )

        return True

    @api.model
    def broadcast(
        self,
        env,
        topic_or_all: str,
        title: str,
        body: str,
        notification_type: str = 'offer',
        deep_link: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        image_url: Optional[str] = None
    ):
        """Broadcast push notification to topic or all active users."""
        full_data = dict(data or {})
        if deep_link:
            full_data['deep_link'] = deep_link

        if topic_or_all and topic_or_all.startswith('topic:'):
            topic_name = topic_or_all.split(':', 1)[1]
            return FirebaseService.send_topic(
                env=env,
                topic=topic_name,
                title=title,
                body=body,
                data=full_data,
                image_url=image_url
            )

        # Broadcast to all active customer devices
        devices = env['jabin.device'].sudo().search([('is_active', '=', True)])
        tokens = devices.mapped('fcm_token')

        if tokens:
            return FirebaseService.send_multicast(
                env=env,
                tokens=tokens,
                title=title,
                body=body,
                data=full_data,
                image_url=image_url
            )

        return {'success_count': 0, 'failure_count': 0}

    # --- Business Event Notifications ---
    @api.model
    def send_order_created(self, env, order):
        """Notification triggered when a new order is created."""
        title = _("Order Created")
        body = _("Your order #%s has been created successfully.") % order.name
        deep_link = f"jabin://orders/{order.id}"
        data = {'order_id': order.id, 'status': order.state}

        # Customer notification
        self.send_to_user(
            env=env,
            user_id=order.customer_id.id,
            title=title,
            body=body,
            notification_type='order',
            deep_link=deep_link,
            data=data,
            order_id=order.id
        )

        # Admin alert
        admin_title = _("New Order Created")
        admin_body = _("New order #%s placed by %s for %s SAR.") % (order.name, order.customer_id.name, order.total)
        self.send_to_admins(
            env=env,
            title=admin_title,
            body=admin_body,
            required_permission='orders_manage',
            notification_type='admin',
            deep_link=deep_link,
            data=data
        )

    @api.model
    def send_order_status_changed(self, env, order, new_state: str):
        """Notification triggered when an order changes status."""
        status_map = {
            'confirmed': (_("Order Confirmed"), _("Your order #%s has been confirmed by restaurant/store.") % order.name),
            'preparing': (_("Order Preparing"), _("Your order #%s is now being prepared.") % order.name),
            'ready_pickup': (_("Order Ready"), _("Your order #%s is ready for pickup!") % order.name),
            'out_delivery': (_("Out for Delivery"), _("Your order #%s is out for delivery with our driver.") % order.name),
            'delivered': (_("Order Delivered"), _("Your order #%s has been delivered. Enjoy! ") % order.name),
            'cancelled': (_("Order Cancelled"), _("Your order #%s has been cancelled.") % order.name),
            'refunded': (_("Order Refunded"), _("Your order #%s has been refunded.") % order.name),
        }

        if new_state not in status_map:
            return

        title, body = status_map[new_state]
        deep_link = f"jabin://orders/{order.id}"
        data = {'order_id': order.id, 'status': new_state}

        # Customer Notification
        self.send_to_user(
            env=env,
            user_id=order.customer_id.id,
            title=title,
            body=body,
            notification_type='order',
            deep_link=deep_link,
            data=data,
            order_id=order.id
        )

        # Admin Alerts for Cancelled / Refunded
        if new_state in ('cancelled', 'refunded'):
            admin_title = _("Order %s") % new_state.capitalize()
            admin_body = _("Order #%s for customer %s is now %s.") % (order.name, order.customer_id.name, new_state)
            self.send_to_admins(
                env=env,
                title=admin_title,
                body=admin_body,
                required_permission='orders_manage',
                notification_type='admin',
                deep_link=deep_link,
                data=data
            )

    @api.model
    def send_new_offer(self, env, offer_title: str, offer_desc: str, deep_link: Optional[str] = None):
        """Broadcast new promotion offer notification."""
        title = offer_title or _("Special Offer!")
        body = offer_desc or _("Check out our new offer on JABIN!")
        link = deep_link or "jabin://offers"
        self.broadcast(env, topic_or_all='topic:offers', title=title, body=body, notification_type='offer', deep_link=link)

    @api.model
    def send_new_banner(self, env, banner):
        """Notification for new banner promo."""
        title = banner.title if hasattr(banner, 'title') and banner.title else _("New Highlight!")
        body = banner.description if hasattr(banner, 'description') and banner.description else _("Check out what's new on JABIN today.")
        deep_link = f"jabin://banners/{banner.id}" if hasattr(banner, 'id') else "jabin://home"
        self.broadcast(env, topic_or_all='topic:all', title=title, body=body, notification_type='banner', deep_link=deep_link)

    @api.model
    def send_new_product(self, env, product):
        """Notification for newly arrived product."""
        title = _("New Product Arrived!")
        body = _("Explore our new item: %s.") % (product.display_name if hasattr(product, 'display_name') else product.name)
        deep_link = f"jabin://products/{product.id}"
        self.broadcast(env, topic_or_all='topic:products', title=title, body=body, notification_type='product', deep_link=deep_link)

    @api.model
    def send_coupon(self, env, coupon, customer_id: Optional[int] = None):
        """Notification for coupon availability."""
        title = _("Discount Coupon Available! 🎉")
        body = _("Use promo code '%s' to get discounts on your next order!") % coupon.code
        deep_link = f"jabin://coupons/{coupon.code}"

        if customer_id:
            self.send_to_user(env, customer_id, title, body, notification_type='coupon', deep_link=deep_link)
        else:
            self.broadcast(env, topic_or_all='topic:all', title=title, body=body, notification_type='coupon', deep_link=deep_link)

    @api.model
    def send_loyalty_points(self, env, customer_id: int, points: int, action_type: str = 'earn'):
        """Notification for loyalty points changes."""
        if action_type == 'earn':
            title = _("Loyalty Points Earned!")
            body = _("You have earned %s loyalty points on your recent purchase!") % points
        else:
            title = _("Loyalty Points Redeemed")
            body = _("You redeemed %s loyalty points for a discount.") % points

        deep_link = "jabin://loyalty"
        self.send_to_user(
            env=env,
            user_id=customer_id,
            title=title,
            body=body,
            notification_type='loyalty',
            deep_link=deep_link,
            data={'points': points, 'action': action_type}
        )

    @api.model
    def send_payment_success(self, env, order, tx=None):
        """Notification for payment success."""
        title = _("Payment Successful")
        body = _("Your payment of %s SAR for order #%s was completed.") % (order.total, order.name)
        deep_link = f"jabin://orders/{order.id}"
        self.send_to_user(env, order.customer_id.id, title, body, notification_type='payment', deep_link=deep_link, order_id=order.id)

    @api.model
    def send_payment_failed(self, env, order, tx=None):
        """Notification for payment failure."""
        title = _("Payment Failed")
        body = _("Payment attempt for order #%s failed. Please retry your payment.") % order.name
        deep_link = f"jabin://orders/{order.id}/pay"

        # Customer alert
        self.send_to_user(env, order.customer_id.id, title, body, notification_type='payment', deep_link=deep_link, order_id=order.id, priority='high')

        # Admin alert
        admin_title = _("Payment Failed Alert")
        admin_body = _("Payment failed for order #%s (Customer: %s).") % (order.name, order.customer_id.name)
        self.send_to_admins(env, admin_title, admin_body, required_permission='payments_manage', notification_type='admin', deep_link=deep_link)

    @api.model
    def mark_as_read(self, env, user_id: int, notification_id: int):
        """Mark a notification as read."""
        notif = env['jabin.notification'].sudo().browse(notification_id)
        if not notif.exists() or notif.user_id.id != user_id:
            raise ValidationError(_("Notification not found."))
        notif.mark_as_read()
        return notif

    @api.model
    def cleanup_invalid_tokens(self, env):
        """Routine cleanup of inactive device records older than 90 days."""
        threshold = fields.Datetime.subtract(fields.Datetime.now(), days=90)
        inactive = env['jabin.device'].sudo().search([
            ('is_active', '=', False),
            ('updated_at', '<', threshold)
        ])
        count = len(inactive)
        inactive.unlink()
        _logger.info(f"Cleaned up {count} inactive device records older than 90 days.")
        return count
