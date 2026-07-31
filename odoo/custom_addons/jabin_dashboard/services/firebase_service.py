# firebase_service.py
import os
import json
from typing import Dict, Any, List, Optional
from odoo import models, api, _
from odoo.addons.jabin_core import JabinLogger

_logger = JabinLogger.get("firebase.service")

try:
    import firebase_admin
    from firebase_admin import credentials, messaging
    HAS_FIREBASE = True
except ImportError:
    firebase_admin = None
    credentials = None
    messaging = None
    HAS_FIREBASE = False


class FirebaseService(models.AbstractModel):
    _name = 'jabin.firebase.service'
    _description = 'JABIN Firebase Cloud Messaging Service'

    _firebase_app = None

    @api.model
    def initialize(self, env=None) -> bool:
        """
        Initialize Firebase Admin SDK singleton.
        Reads credentials from system parameter 'jabin.firebase.credentials'
        or environment variable 'JABIN_FIREBASE_CREDENTIALS'.
        """
        if not HAS_FIREBASE:
            _logger.warning("firebase_admin Python package is not installed. Push notifications via Firebase are disabled.")
            return False

        if firebase_admin._apps:
            # Firebase Admin SDK already initialized
            return True

        target_env = env or self.env
        icp = target_env['ir.config_parameter'].sudo()

        # 1. Check system parameter
        cred_path = icp.get_param('jabin.firebase.credentials', '')

        # 2. Check environment variable fallback
        if not cred_path:
            cred_path = os.environ.get('JABIN_FIREBASE_CREDENTIALS', '')

        # 3. Check default path fallback inside module
        if not cred_path:
            module_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cred_path = os.path.join(module_dir, 'data', 'firebase_credentials.json')

        if not cred_path or not os.path.isabs(cred_path):
            # Resolve relative path against workspace or addons path
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            potential_path = os.path.normpath(os.path.join(base_dir, '..', cred_path))
            if os.path.exists(potential_path):
                cred_path = potential_path
            else:
                cred_path = os.path.normpath(os.path.join(base_dir, cred_path))

        if not os.path.exists(cred_path):
            _logger.error(f"Firebase credentials file not found at: {cred_path}")
            return False

        try:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            _logger.info("Firebase Admin SDK initialized successfully.")
            return True
        except Exception as e:
            _logger.error(f"Failed to initialize Firebase Admin SDK: {str(e)}")
            return False

    @api.model
    def _is_invalid_token_error(self, exc: Exception) -> bool:
        """Helper to identify if an exception represents an invalid/expired FCM token."""
        if not HAS_FIREBASE:
            return False
        if isinstance(exc, getattr(messaging, 'UnregisteredError', Exception)):
            return True
        if isinstance(exc, getattr(messaging, 'SenderIdMismatchError', Exception)):
            return True

        msg = str(exc).lower()
        invalid_keywords = [
            'unregistered', 'invalid-registration-token', 'registration-token-not-registered',
            'not-found', 'mismatch', 'invalidtoken'
        ]
        return any(k in msg for k in invalid_keywords)

    @api.model
    def _deactivate_token(self, env, token: str):
        """Deactivate invalid FCM device token."""
        if not token:
            return
        devices = env['jabin.device'].sudo().search([('fcm_token', '=', token)])
        if devices:
            devices.deactivate()
            _logger.info(f"Deactivated invalid FCM token for device(s): {devices.ids}")

    @api.model
    def _prepare_data_dict(self, data: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """Format data dictionary values as strings (FCM data requirement)."""
        if not data:
            return {}
        formatted = {}
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                formatted[str(k)] = json.dumps(v)
            elif v is None:
                formatted[str(k)] = ""
            else:
                formatted[str(k)] = str(v)
        return formatted

    @api.model
    def send(self, env, token: str, title: str, body: str, data: Optional[Dict[str, Any]] = None, image_url: Optional[str] = None) -> bool:
        """
        Send notification to a single device token.
        """
        if not token or not token.strip():
            return False

        if not self.initialize(env):
            _logger.warning(f"Firebase not initialized. Skipped sending notification '{title}' to token {token[:10]}...")
            return False

        data_dict = self._prepare_data_dict(data)

        notification_kwargs = {'title': title, 'body': body}
        if image_url:
            notification_kwargs['image'] = image_url

        try:
            msg = messaging.Message(
                notification=messaging.Notification(**notification_kwargs),
                data=data_dict,
                token=token.strip()
            )
            response = messaging.send(msg)
            _logger.info(f"FCM notification sent successfully: {response}")
            return True
        except Exception as exc:
            _logger.error(f"FCM send failed for token {token[:10]}...: {str(exc)}")
            if self._is_invalid_token_error(exc):
                self._deactivate_token(env, token)
            return False

    @api.model
    def send_multicast(self, env, tokens: List[str], title: str, body: str, data: Optional[Dict[str, Any]] = None, image_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Send notification to multiple device tokens.
        """
        valid_tokens = [t.strip() for t in tokens if t and t.strip()]
        if not valid_tokens:
            return {'success_count': 0, 'failure_count': 0, 'responses': []}

        if not self.initialize(env):
            _logger.warning(f"Firebase not initialized. Skipped multicast notification '{title}' to {len(valid_tokens)} tokens.")
            return {'success_count': 0, 'failure_count': len(valid_tokens), 'responses': []}

        data_dict = self._prepare_data_dict(data)
        notification_kwargs = {'title': title, 'body': body}
        if image_url:
            notification_kwargs['image'] = image_url

        try:
            multicast_msg = messaging.MulticastMessage(
                notification=messaging.Notification(**notification_kwargs),
                data=data_dict,
                tokens=valid_tokens
            )
            batch_response = messaging.send_each_for_multicast(multicast_msg)

            success_count = batch_response.success_count
            failure_count = batch_response.failure_count

            # Process individual response errors for invalid token cleanup
            for idx, resp in enumerate(batch_response.responses):
                if not resp.success and resp.exception:
                    _logger.error(f"Multicast item failed for token {valid_tokens[idx][:10]}...: {str(resp.exception)}")
                    if self._is_invalid_token_error(resp.exception):
                        self._deactivate_token(env, valid_tokens[idx])

            _logger.info(f"FCM multicast completed: {success_count} succeeded, {failure_count} failed.")
            return {
                'success_count': success_count,
                'failure_count': failure_count
            }
        except Exception as exc:
            _logger.error(f"FCM multicast batch failed: {str(exc)}")
            return {'success_count': 0, 'failure_count': len(valid_tokens)}

    @api.model
    def send_topic(self, env, topic: str, title: str, body: str, data: Optional[Dict[str, Any]] = None, image_url: Optional[str] = None) -> bool:
        """
        Send notification to a FCM topic.
        """
        if not topic or not topic.strip():
            return False

        if not self.initialize(env):
            _logger.warning(f"Firebase not initialized. Skipped topic notification '{title}' to topic '{topic}'.")
            return False

        data_dict = self._prepare_data_dict(data)
        notification_kwargs = {'title': title, 'body': body}
        if image_url:
            notification_kwargs['image'] = image_url

        try:
            msg = messaging.Message(
                notification=messaging.Notification(**notification_kwargs),
                data=data_dict,
                topic=topic.strip()
            )
            response = messaging.send(msg)
            _logger.info(f"FCM topic notification sent successfully to topic '{topic}': {response}")
            return True
        except Exception as exc:
            _logger.error(f"FCM send topic failed for topic '{topic}': {str(exc)}")
            return False
