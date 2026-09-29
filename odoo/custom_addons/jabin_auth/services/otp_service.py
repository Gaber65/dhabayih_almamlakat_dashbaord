from __future__ import annotations
import secrets
import string
from datetime import timedelta
from typing import TYPE_CHECKING, Optional, Tuple

from odoo.addons.jabin_core import JabinLogger
from odoo import api, models, fields
from odoo.exceptions import ValidationError
from psycopg2 import IntegrityError

# Initialize logger properly
_logger = None


def _get_logger():
    global _logger
    if _logger is None:
        _logger = JabinLogger.get('otp.service')
    return _logger


class OtpService(models.AbstractModel):
    """Jabin OTP Service.

    Handles OTP generation, hashing, verification, expiration checks,
    attempt tracking, and resend limiting.
    """
    _name = 'jabin.otp.service'
    _description = 'Dhabayih Lmamlaka OTP Service'

    # -- Configuration ---------------------------------------------------- #
    OTP_LENGTH = 6
    OTP_EXPIRY_MINUTES = 5
    MAX_ATTEMPTS = 5
    RESEND_COOLDOWN_SECONDS = 60
    MAX_RESEND_ATTEMPTS = 5
    OTP_CHARACTERS = string.digits  # Only digits for simplicity

    # -- OTP Generation --------------------------------------------------- #
    @staticmethod
    def generate_otp(length: int = OTP_LENGTH) -> str:
        """Generate a random OTP code."""
        return ''.join(secrets.choice(OtpService.OTP_CHARACTERS) for _ in range(length))

    @api.model
    def generate_otp_hash(self, code: str) -> str:
        """Generate a secure hash for an OTP code."""
        OTP = self.env['jabin.otp']
        return OTP._hash_code(code)

    # -- OTP Creation ------------------------------------------------------ #
    @api.model
    def create_otp(
            self,
            identifier: str,
            purpose: str,
            channel: Optional[str] = None,
            user_id: Optional[int] = None,
            invalidate_existing: bool = True
    ) -> Tuple[str, str]:
        """Create a new OTP for the given email or phone and purpose."""
        if not identifier:
            raise ValidationError('Identifier (email or phone) is required.')
        if not purpose:
            raise ValidationError('Purpose is required.')

        identifier = str(identifier).strip()
        email_val = None
        phone_val = None

        # Determine channel and normalize identifier
        if channel == 'sms' or (not channel and '@' not in identifier):
            channel = 'sms'
            authentica_service = self.env['jabin.authentica.service'].sudo()
            phone_val = authentica_service.normalize_saudi_phone(identifier)
            normalized_identifier = phone_val
        else:
            channel = 'email'
            email_val = identifier.lower()
            normalized_identifier = email_val

        # Invalidate existing OTPs for this identifier and purpose
        if invalidate_existing:
            self.invalidate_existing_otps(normalized_identifier, purpose)
            self.env.cr.commit()

        # Generate OTP
        plain_code = self.generate_otp()
        code_hash = self.generate_otp_hash(plain_code)

        # Calculate expiration
        expires_at = fields.Datetime.now() + timedelta(minutes=self.OTP_EXPIRY_MINUTES)

        # Create OTP record - MUST use sudo() for anonymous access
        OTP = self.env['jabin.otp'].sudo()
        otp_data = {
            'email': email_val,
            'phone': phone_val,
            'channel': channel,
            'user_id': user_id,
            'purpose': purpose,
            'code_hash': code_hash,
            'expires_at': expires_at,
            'max_attempts': self.MAX_ATTEMPTS,
            'resend_count': 0,
            'last_sent_at': fields.Datetime.now(),
            'verified': False,
        }

        try:
            OTP.create(otp_data)
        except IntegrityError:
            self.env.cr.rollback()
            _get_logger().warning(
                'Duplicate OTP detected, forcing cleanup and retry: %s',
                normalized_identifier
            )
            OTP.search([
                '|',
                ('email', '=', email_val),
                ('phone', '=', phone_val),
                ('purpose', '=', purpose),
                ('verified', '=', False)
            ]).unlink()
            self.env.cr.commit()

            try:
                OTP.create(otp_data)
            except Exception as retry_exc:
                _get_logger().error('Failed to create OTP after cleanup: %s', retry_exc)
                raise ValidationError(f'Failed to create OTP: {retry_exc}')

        except Exception as exc:
            _get_logger().error('Failed to create OTP: %s', exc)
            raise ValidationError(f'Failed to create OTP: {exc}')

        return plain_code, code_hash

    @api.model
    def create_and_send_phone_otp(
            self,
            phone: str,
            purpose: str,
            user_id: Optional[int] = None
    ) -> str:
        """Create an OTP and send it via Authentica SA SMS gateway."""
        authentica_service = self.env['jabin.authentica.service'].sudo()
        normalized_phone = authentica_service.normalize_saudi_phone(phone)
        plain_code, code_hash = self.create_otp(
            identifier=normalized_phone,
            purpose=purpose,
            channel='sms',
            user_id=user_id
        )

        try:
            authentica_service.send_otp(phone=normalized_phone, otp=plain_code)
            _get_logger().audit(
                'OTP SMS sent via Authentica: phone=%s purpose=%s',
                normalized_phone,
                purpose,
                extra={'phone': normalized_phone, 'purpose': purpose}
            )
        except Exception as exc:
            _get_logger().error('Failed to send OTP SMS: %s', exc)
            raise

        return plain_code

    @api.model
    def create_and_send_email_otp(
            self,
            email: str,
            purpose: str,
            user_id: Optional[int] = None
    ) -> str:
        """Create an OTP and send it via Gmail / SMTP email."""
        email_val = email.strip().lower()
        plain_code, code_hash = self.create_otp(
            identifier=email_val,
            purpose=purpose,
            channel='email',
            user_id=user_id
        )

        try:
            email_service = self.env['jabin.email.service'].sudo()
            email_service.send_verification_code(email_val, plain_code, purpose)
            _get_logger().audit(
                'OTP email sent: email=%s purpose=%s',
                email_val,
                purpose,
                extra={'email': email_val, 'purpose': purpose}
            )
        except Exception as exc:
            _get_logger().error('Failed to send OTP email: %s', exc)
            raise

        return plain_code

    @api.model
    def create_and_send_otp(
            self,
            identifier: str,
            purpose: str,
            user_id: Optional[int] = None,
            channel: Optional[str] = None
    ) -> str:
        """Create and send OTP through the appropriate channel (SMS or Email)."""
        identifier = str(identifier).strip()
        if channel == 'sms' or (not channel and '@' not in identifier):
            return self.create_and_send_phone_otp(phone=identifier, purpose=purpose, user_id=user_id)
        else:
            return self.create_and_send_email_otp(email=identifier, purpose=purpose, user_id=user_id)

    # -- OTP Verification -------------------------------------------------- #
    @api.model
    def verify_otp(
            self,
            identifier: str,
            code: str,
            purpose: str
    ) -> bool:
        """Verify an OTP code for either phone or email."""
        if not identifier or not code or not purpose:
            _get_logger().warning('Verification failed: missing parameters')
            return False

        identifier = str(identifier).strip()
        if '@' not in identifier:
            try:
                identifier = self.env['jabin.authentica.service'].normalize_saudi_phone(identifier)
            except Exception:
                pass
        else:
            identifier = identifier.lower()

        # Find active OTP - MUST use sudo() for anonymous access
        OTP = self.env['jabin.otp'].sudo()
        otp = OTP.find_active_otp(identifier, purpose)

        if not otp:
            _get_logger().audit(
                'OTP verification failed: no active OTP found for identifier=%s purpose=%s',
                identifier,
                purpose,
                extra={'identifier': identifier, 'purpose': purpose, 'reason': 'no_active_otp'}
            )
            return False

        # Check expiration
        if otp.is_expired():
            _get_logger().audit(
                'OTP verification failed: expired for identifier=%s',
                identifier,
                extra={'identifier': identifier, 'purpose': purpose, 'reason': 'expired'}
            )
            return False

        # Check attempts
        if otp.attempts >= otp.max_attempts:
            _get_logger().audit(
                'OTP verification failed: max attempts reached for identifier=%s',
                identifier,
                extra={'identifier': identifier, 'purpose': purpose, 'reason': 'max_attempts'}
            )
            return False

        # Verify the code hash
        if not OTP._verify_hash(code, otp.code_hash):
            otp.increment_attempts()
            _get_logger().audit(
                'OTP verification failed: invalid code for identifier=%s',
                identifier,
                extra={'identifier': identifier, 'purpose': purpose, 'reason': 'invalid_code'}
            )
            return False

        # Success - mark as verified
        otp.mark_verified()
        _get_logger().audit(
            'OTP verified successfully: identifier=%s purpose=%s channel=%s',
            identifier,
            purpose,
            otp.channel,
            extra={'identifier': identifier, 'purpose': purpose, 'channel': otp.channel, 'success': True}
        )
        return True

    # -- OTP Management ---------------------------------------------------- #
    @api.model
    def invalidate_existing_otps(self, identifier: str, purpose: str) -> int:
        """Invalidate all existing OTPs for an identifier (phone or email) and purpose."""
        OTP = self.env['jabin.otp'].sudo()
        return OTP.invalidate_all_for_identifier(identifier, purpose)

    @api.model
    def can_resend_otp(self, identifier: str, purpose: str) -> Tuple[bool, str]:
        """Check if user can request an OTP resend."""
        identifier = str(identifier).strip()
        OTP = self.env['jabin.otp'].sudo()

        recent_count = OTP.count_recent_resends(identifier, purpose, minutes=1)
        if recent_count >= self.MAX_RESEND_ATTEMPTS:
            return False, f"Maximum resend attempts ({self.MAX_RESEND_ATTEMPTS}) reached. Please wait before requesting again."

        active_otp = OTP.find_active_otp(identifier, purpose)
        if active_otp and active_otp.resend_count >= self.MAX_RESEND_ATTEMPTS:
            return False, f"Maximum resend attempts ({self.MAX_RESEND_ATTEMPTS}) reached."

        return True, ""

    @api.model
    def resend_otp(
            self,
            identifier: str,
            purpose: str,
            user_id: Optional[int] = None,
            channel: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Resend OTP for an identifier and purpose."""
        can_resend, reason = self.can_resend_otp(identifier, purpose)
        if not can_resend:
            return False, reason

        self.invalidate_existing_otps(identifier, purpose)

        try:
            self.create_and_send_otp(identifier, purpose, user_id=user_id, channel=channel)
            return True, "Verification code sent successfully"
        except Exception as exc:
            _get_logger().error('Failed to resend OTP: %s', exc)
            return False, f"Failed to send verification code: {exc}"

    # -- Utility Methods --------------------------------------------------- #
    @api.model
    def get_otp_status(self, identifier: str, purpose: str) -> dict:
        """Get the status of OTP for an email or phone and purpose."""
        identifier = str(identifier).strip()
        OTP = self.env['jabin.otp'].sudo()

        active_otp = OTP.find_active_otp(identifier, purpose, include_expired=True)

        if not active_otp:
            return {
                'exists': False,
                'message': 'No OTP found for this identifier and purpose'
            }

        return {
            'exists': True,
            'channel': active_otp.channel,
            'expired': active_otp.is_expired(),
            'attempts': active_otp.attempts,
            'max_attempts': active_otp.max_attempts,
            'resend_count': active_otp.resend_count,
            'can_verify': active_otp.can_verify(),
            'can_resend': self.can_resend_otp(identifier, purpose)[0],
            'expires_in': max(0, (
                active_otp.expires_at - fields.Datetime.now()
            ).total_seconds()) if not active_otp.is_expired() else 0
        }

    @api.model
    def cleanup_expired_otps(self) -> int:
        """Clean up all expired OTPs."""
        OTP = self.env['jabin.otp'].sudo()
        expired_otps = OTP.search([('expires_at', '<', fields.Datetime.now())])

        if expired_otps:
            count = len(expired_otps)
            expired_otps.unlink()
            _get_logger().audit('Cleaned up %d expired OTPs', count)
            return count

        return 0