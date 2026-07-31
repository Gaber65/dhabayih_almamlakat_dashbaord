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
    """JABIN OTP Service.

    Handles OTP generation, hashing, verification, expiration checks,
    attempt tracking, and resend limiting.
    """
    _name = 'jabin.otp.service'
    _description = 'JABIN OTP Service'

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
            email: str,
            purpose: str,
            user_id: Optional[int] = None,
            invalidate_existing: bool = True
    ) -> Tuple[str, str]:
        """Create a new OTP for the given email and purpose."""
        if not email:
            raise ValidationError('Email is required.')
        if not purpose:
            raise ValidationError('Purpose is required.')

        # Normalize email
        email = email.strip().lower()

        # Invalidate existing OTPs for this email and purpose
        if invalidate_existing:
            # Delete existing OTPs to avoid unique constraint violations
            self.invalidate_existing_otps(email, purpose)

            # Force a database commit to ensure deletion is complete
            self.env.cr.commit()

        # Generate OTP
        plain_code = self.generate_otp()
        code_hash = self.generate_otp_hash(plain_code)

        # Calculate expiration
        expires_at = fields.Datetime.now() + timedelta(minutes=self.OTP_EXPIRY_MINUTES)

        # Create OTP record - MUST use sudo() for anonymous access
        OTP = self.env['jabin.otp'].sudo()
        otp_data = {
            'email': email,
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
            _get_logger().audit(
                'OTP created: email=%s purpose=%s',
                email,
                purpose,
                extra={'email': email, 'purpose': purpose}
            )
        except IntegrityError as exc:
            # If we still get a duplicate, try one more time with a fresh deletion
            self.env.cr.rollback()
            _get_logger().warning(
                'Duplicate OTP detected, forcing cleanup and retry: %s',
                email
            )
            # Force delete any existing OTPs
            OTP.search([
                ('email', '=', email),
                ('purpose', '=', purpose),
                ('verified', '=', False)
            ]).unlink()
            self.env.cr.commit()

            # Try creating again
            try:
                OTP.create(otp_data)
                _get_logger().audit(
                    'OTP created after cleanup: email=%s purpose=%s',
                    email,
                    purpose,
                    extra={'email': email, 'purpose': purpose}
                )
            except Exception as retry_exc:
                _get_logger().error('Failed to create OTP after cleanup: %s', retry_exc)
                raise ValidationError(f'Failed to create OTP: {retry_exc}')

        except Exception as exc:
            _get_logger().error('Failed to create OTP: %s', exc)
            raise ValidationError(f'Failed to create OTP: {exc}')

        return plain_code, code_hash

    @api.model
    def create_and_send_otp(
            self,
            email: str,
            purpose: str,
            user_id: Optional[int] = None
    ) -> str:
        """Create an OTP and send it via email."""
        plain_code, code_hash = self.create_otp(email, purpose, user_id)

        # Send email - MUST use sudo() for anonymous access
        try:
            email_service = self.env['jabin.email.service'].sudo()
            email_service.send_verification_code(email, plain_code, purpose)
            _get_logger().audit(
                'OTP email sent: email=%s purpose=%s',
                email,
                purpose,
                extra={'email': email, 'purpose': purpose}
            )
        except Exception as exc:
            _get_logger().error('Failed to send OTP email: %s', exc)
            # Don't raise here - we want to return the code even if email fails
            pass

        return plain_code

    # -- OTP Verification -------------------------------------------------- #
    @api.model
    def verify_otp(
            self,
            email: str,
            code: str,
            purpose: str
    ) -> bool:
        """Verify an OTP code."""
        if not email or not code or not purpose:
            _get_logger().warning('Verification failed: missing parameters')
            return False

        email = email.strip().lower()

        # Find active OTP - MUST use sudo() for anonymous access
        OTP = self.env['jabin.otp'].sudo()
        otp = OTP.find_active_otp(email, purpose)

        if not otp:
            _get_logger().audit(
                'OTP verification failed: no active OTP found for email=%s purpose=%s',
                email,
                purpose,
                extra={'email': email, 'purpose': purpose, 'reason': 'no_active_otp'}
            )
            return False

        # Check expiration
        if otp.is_expired():
            _get_logger().audit(
                'OTP verification failed: expired for email=%s',
                email,
                extra={'email': email, 'purpose': purpose, 'reason': 'expired'}
            )
            return False

        # Check attempts
        if otp.attempts >= otp.max_attempts:
            _get_logger().audit(
                'OTP verification failed: max attempts reached for email=%s',
                email,
                extra={'email': email, 'purpose': purpose, 'reason': 'max_attempts'}
            )
            return False

        # Verify the code - use the model's static method
        if not OTP._verify_hash(code, otp.code_hash):
            otp.increment_attempts()
            _get_logger().audit(
                'OTP verification failed: invalid code for email=%s',
                email,
                extra={'email': email, 'purpose': purpose, 'reason': 'invalid_code'}
            )
            return False

        # Success - mark as verified
        otp.mark_verified()
        _get_logger().audit(
            'OTP verified successfully: email=%s purpose=%s',
            email,
            purpose,
            extra={'email': email, 'purpose': purpose, 'success': True}
        )
        return True

    # -- OTP Management ---------------------------------------------------- #
    @api.model
    def invalidate_existing_otps(self, email: str, purpose: str) -> int:
        """Invalidate all existing OTPs for an email and purpose."""
        OTP = self.env['jabin.otp'].sudo()
        return OTP.invalidate_all_for_email(email, purpose)

    @api.model
    def can_resend_otp(self, email: str, purpose: str) -> Tuple[bool, str]:
        """Check if user can request an OTP resend."""
        email = email.strip().lower()
        OTP = self.env['jabin.otp'].sudo()

        # Check recent resends (within cooldown period)
        recent_count = OTP.count_recent_resends(email, purpose, minutes=1)
        if recent_count >= self.MAX_RESEND_ATTEMPTS:
            return False, f"Maximum resend attempts ({self.MAX_RESEND_ATTEMPTS}) reached. Please wait before requesting again."

        # Check if there's an active OTP that was sent too recently
        active_otp = OTP.find_active_otp(email, purpose)
        if active_otp and active_otp.resend_count >= self.MAX_RESEND_ATTEMPTS:
            return False, f"Maximum resend attempts ({self.MAX_RESEND_ATTEMPTS}) reached."

        return True, ""

    @api.model
    def resend_otp(
            self,
            email: str,
            purpose: str,
            user_id: Optional[int] = None
    ) -> Tuple[bool, str]:
        """Resend OTP for an email and purpose."""
        can_resend, reason = self.can_resend_otp(email, purpose)
        if not can_resend:
            return False, reason

        # Invalidate existing OTPs
        self.invalidate_existing_otps(email, purpose)

        # Create and send new OTP
        try:
            plain_code = self.create_and_send_otp(email, purpose, user_id)
            return True, "Verification code sent successfully"
        except Exception as exc:
            _get_logger().error('Failed to resend OTP: %s', exc)
            return False, f"Failed to send verification code: {exc}"

    # -- Utility Methods --------------------------------------------------- #
    @api.model
    def get_otp_status(self, email: str, purpose: str) -> dict:
        """Get the status of OTP for an email and purpose."""
        email = email.strip().lower()
        OTP = self.env['jabin.otp'].sudo()

        active_otp = OTP.find_active_otp(email, purpose, include_expired=True)

        if not active_otp:
            return {
                'exists': False,
                'message': 'No OTP found for this email and purpose'
            }

        return {
            'exists': True,
            'expired': active_otp.is_expired(),
            'attempts': active_otp.attempts,
            'max_attempts': active_otp.max_attempts,
            'resend_count': active_otp.resend_count,
            'can_verify': active_otp.can_verify(),
            'can_resend': self.can_resend_otp(email, purpose)[0],
            'expires_in': max(0, (
                        active_otp.expires_at - fields.Datetime.now()).total_seconds()) if not active_otp.is_expired() else 0
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