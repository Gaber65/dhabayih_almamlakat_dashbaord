# -*- coding: utf-8 -*-
from __future__ import annotations
import re
import json
import requests
from typing import Optional, Dict, Any, Tuple

from odoo import api, models, _
from odoo.exceptions import ValidationError
from odoo.addons.jabin_core import JabinLogger

_logger = JabinLogger.get('authentica.service')


class AuthenticaService(models.AbstractModel):
    """Authentica SA SMS & OTP Gateway Integration Service.

    Documentation: https://authenticasa.docs.apiary.io/
    Base URL: https://api.authentica.sa/api/v2/
    """
    _name = 'jabin.authentica.service'
    _description = 'Authentica SA SMS Service'

    BASE_URL = 'https://api.authentica.sa/api/v2'
    REQUEST_TIMEOUT = 12  # seconds

    # -------------------------------------------------------------------------
    # Configuration Helpers
    # -------------------------------------------------------------------------
    @api.model
    def _get_config(self) -> Dict[str, Any]:
        """Fetch Authentica settings from ir.config_parameter."""
        ICP = self.env['ir.config_parameter'].sudo()
        return {
            'api_key': (ICP.get_param('authentica.api_key') or '').strip(),
            'template_id': (ICP.get_param('authentica.template_id') or '').strip(),
            'sender_id': (ICP.get_param('authentica.sender_id') or 'Dhabayih').strip(),
            'method': ICP.get_param('authentica.method') or 'sms',
            'enable_sms': ICP.get_param('authentica.enable_sms', default='True') in ('True', 'true', '1', True),
            'mock_mode': ICP.get_param('authentica.mock_mode', default='False') in ('True', 'true', '1', True),
        }

    # -------------------------------------------------------------------------
    # Phone Normalization
    # -------------------------------------------------------------------------
    @api.model
    def normalize_saudi_phone(self, phone: str) -> str:
        """Normalize any input Saudi phone number into international E.164 format (+9665XXXXXXXX).

        Accepted formats:
            0501234567   -> +966501234567
            501234567    -> +966501234567
            +966501234567 -> +966501234567
            00966501234567 -> +966501234567
            966501234567  -> +966501234567
        """
        if not phone:
            raise ValidationError(_('Phone number is required.'))

        # Strip all formatting characters (spaces, dashes, parens)
        cleaned = re.sub(r'[\s\-\(\)\.]+', '', str(phone).strip())

        # Normalize prefixes
        if cleaned.startswith('00966'):
            cleaned = '+' + cleaned[2:]
        elif cleaned.startswith('966'):
            cleaned = '+' + cleaned
        elif cleaned.startswith('05') and len(cleaned) == 10:
            cleaned = '+966' + cleaned[1:]
        elif cleaned.startswith('5') and len(cleaned) == 9:
            cleaned = '+966' + cleaned

        # Validate strictly against Saudi mobile pattern (+9665XXXXXXXX)
        if not re.match(r'^\+9665\d{8}$', cleaned):
            raise ValidationError(
                _('Invalid Saudi mobile phone number (%s). Must be a valid mobile starting with 05.') % phone
            )

        return cleaned

    # -------------------------------------------------------------------------
    # Balance Monitoring
    # -------------------------------------------------------------------------
    @api.model
    def get_balance(self) -> Dict[str, Any]:
        """Fetch current SMS/OTP balance from Authentica SA.

        Endpoint: GET /balance
        """
        config = self._get_config()
        api_key = config['api_key']

        if not api_key:
            return {
                'success': False,
                'message': _('Authentica API Key is not configured. Please add it in settings.')
            }

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Authorization': api_key,
        }

        try:
            url = f"{self.BASE_URL}/balance"
            response = requests.get(url, headers=headers, timeout=self.REQUEST_TIMEOUT)

            if response.status_code == 200:
                data = response.json()
                balance_val = data.get('data', {}).get('balance', 0) if isinstance(data.get('data'), dict) else 0
                return {
                    'success': True,
                    'balance': balance_val,
                    'message': data.get('message', 'Balance retrieved successfully')
                }
            elif response.status_code == 401:
                return {
                    'success': False,
                    'message': _('Unauthorized: Invalid Authentica API Key.')
                }
            else:
                return {
                    'success': False,
                    'message': f"Authentica Error (HTTP {response.status_code}): {response.text[:200]}"
                }
        except requests.exceptions.RequestException as exc:
            _logger.error('Failed to connect to Authentica balance endpoint: %s', exc)
            return {
                'success': False,
                'message': f"Connection Error: {str(exc)}"
            }

    # -------------------------------------------------------------------------
    # Send OTP
    # -------------------------------------------------------------------------
    @api.model
    def send_otp(
        self,
        phone: str,
        otp: Optional[str] = None,
        template_id: Optional[str] = None,
        fallback_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send OTP code via Authentica SMS / WhatsApp gateway.

        Endpoint: POST /send-otp
        """
        config = self._get_config()
        if not config['enable_sms']:
            raise ValidationError(_('SMS OTP service is currently disabled in system settings.'))

        normalized_phone = self.normalize_saudi_phone(phone)
        effective_template_id = (template_id or config['template_id'] or '').strip()

        # Handle Mock Mode or Missing API Key gracefully for development
        if config['mock_mode'] or not config['api_key']:
            _logger.warning(
                'AUTHENTICA MOCK MODE [OTP]: phone=%s, otp=%s, template_id=%s',
                normalized_phone, otp, effective_template_id
            )
            return {
                'success': True,
                'mock': True,
                'message': 'OTP sent in development mock mode.',
                'phone': normalized_phone
            }

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Authorization': config['api_key'],
        }

        payload: Dict[str, Any] = {
            'method': config['method'],
            'phone': normalized_phone,
        }

        if effective_template_id:
            payload['template_id'] = effective_template_id

        if otp:
            payload['otp'] = str(otp)

        if fallback_email:
            payload['fallback_email'] = fallback_email

        try:
            url = f"{self.BASE_URL}/send-otp"
            response = requests.post(
                url,
                headers=headers,
                data=json.dumps(payload),
                timeout=self.REQUEST_TIMEOUT
            )

            if response.status_code in (200, 201):
                data = response.json()
                _logger.audit(
                    'AUTHENTICA_OTP_SENT',
                    f"OTP sent successfully to {normalized_phone}",
                    extra={'phone': normalized_phone, 'method': config['method']}
                )
                return {
                    'success': True,
                    'mock': False,
                    'message': data.get('message', 'OTP sent successfully'),
                    'phone': normalized_phone
                }
            elif response.status_code == 401:
                _logger.error('Authentica unauthorized: Invalid API key.')
                raise ValidationError(_('Failed to send SMS: Invalid Authentica API Key.'))
            else:
                try:
                    err_json = response.json()
                    err_msg = err_json.get('message') or str(err_json.get('errors') or response.text[:200])
                except Exception:
                    err_msg = response.text[:200]
                _logger.error('Authentica send OTP error (HTTP %s): %s', response.status_code, err_msg)
                raise ValidationError(_('Failed to send SMS OTP via Authentica: %s') % err_msg)

        except requests.exceptions.Timeout:
            _logger.error('Authentica request timed out for phone %s', normalized_phone)
            raise ValidationError(_('SMS gateway timeout. Please try again in a few moments.'))
        except requests.exceptions.RequestException as exc:
            _logger.error('Authentica request exception: %s', exc)
            raise ValidationError(_('Failed to communicate with SMS gateway: %s') % str(exc))

    # -------------------------------------------------------------------------
    # Verify OTP
    # -------------------------------------------------------------------------
    @api.model
    def verify_otp(self, phone: str, otp: str, email: Optional[str] = None) -> Dict[str, Any]:
        """Verify OTP with Authentica SA (if remote verification is enabled).

        Endpoint: POST /verify-otp
        """
        config = self._get_config()
        normalized_phone = self.normalize_saudi_phone(phone)

        if config['mock_mode'] or not config['api_key']:
            return {'success': True, 'mock': True, 'message': 'Verified in mock mode.'}

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Authorization': config['api_key'],
        }

        payload: Dict[str, Any] = {
            'phone': normalized_phone,
            'otp': str(otp),
        }
        if email:
            payload['email'] = email

        try:
            url = f"{self.BASE_URL}/verify-otp"
            response = requests.post(url, headers=headers, json=payload, timeout=self.REQUEST_TIMEOUT)
            data = response.json()
            is_valid = bool(data.get('status') or data.get('success'))
            return {
                'success': is_valid,
                'message': data.get('message', 'OTP verified')
            }
        except Exception as exc:
            _logger.error('Authentica verify-otp error: %s', exc)
            return {'success': False, 'message': str(exc)}
