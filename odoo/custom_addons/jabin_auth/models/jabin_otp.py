from __future__ import annotations
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Optional

from odoo.addons.jabin_core import JabinLogger
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import mute_logger

# Initialize logger properly
_logger = None


def _get_logger():
    global _logger
    if _logger is None:
        _logger = JabinLogger.get('otp.model')
    return _logger


class OTPPurpose:
    """Enumeration of OTP purposes."""
    REGISTER = 'register'
    LOGIN = 'login'
    PASSWORD_RESET = 'password_reset'
    EMAIL_CHANGE = 'email_change'

    @classmethod
    def get_selection(cls):
        """Get selection list for OTP purposes."""
        return [
            (cls.REGISTER, 'Registration'),
            (cls.LOGIN, 'Login'),
            (cls.PASSWORD_RESET, 'Password Reset'),
            (cls.EMAIL_CHANGE, 'Email Change'),
        ]


class JabinOTP(models.Model):
    """JABIN One-Time Password (OTP) Model.

    Stores OTP codes securely as hashes with expiration and attempt tracking.
    """
    _name = 'jabin.otp'
    _description = 'JABIN OTP'
    _order = 'created_at desc'
    _rec_name = 'email'

    # -- Fields ----------------------------------------------------------- #
    email = fields.Char(
        string='Email',
        required=True,
        index=True,
        help='Email address for which the OTP was generated.'
    )
    user_id = fields.Many2one(
        comodel_name='res.users',  # Changed from res.users
        string='User',
        index=True,
        ondelete='cascade',
        help='Related user record. Null for new registrations.'
    )
    purpose = fields.Selection(
        selection=lambda self: self._get_purpose_selection(),
        string='Purpose',
        required=True,
        index=True,
        default=OTPPurpose.REGISTER,
        help='Purpose of the OTP (register, login, etc.).'
    )
    code_hash = fields.Char(
        string='Code Hash',
        required=True,
        help='SHA256 hash of the OTP code. Never store plain text.'
    )
    expires_at = fields.Datetime(
        string='Expires At',
        required=True,
        index=True,
        help='Timestamp when the OTP expires (5 minutes from creation).'
    )
    attempts = fields.Integer(
        string='Verification Attempts',
        default=0,
        help='Number of verification attempts made.'
    )
    max_attempts = fields.Integer(
        string='Max Attempts',
        default=5,
        help='Maximum allowed verification attempts.'
    )
    resend_count = fields.Integer(
        string='Resend Count',
        default=0,
        help='Number of times OTP was resent.'
    )
    last_sent_at = fields.Datetime(
        string='Last Sent At',
        readonly=True,
        help='Timestamp of the last OTP send/resend.'
    )
    verified = fields.Boolean(
        string='Verified',
        default=False,
        index=True,
        help='Whether the OTP has been successfully verified.'
    )
    verified_at = fields.Datetime(
        string='Verified At',
        readonly=True,
        help='Timestamp when the OTP was verified.'
    )
    created_at = fields.Datetime(
        string='Created At',
        default=fields.Datetime.now,
        readonly=True,
        index=True,
        help='Timestamp when the OTP was created.'
    )
    ip_address = fields.Char(
        string='IP Address',
        help='IP address of the requester.'
    )
    user_agent = fields.Char(
        string='User Agent',
        help='User agent of the requester.'
    )

    # -- Constraints ------------------------------------------------------- #
    _sql_constraints = [
        # Only enforce uniqueness for unverified OTPs
        ('email_purpose_active',
         'UNIQUE(email, purpose) WHERE verified = false',
         'Only one active (unverified) OTP per email and purpose is allowed.'),
    ]
    # -- Helper Methods ---------------------------------------------------- #
    @api.model
    def _get_purpose_selection(self):
        """Get the purpose selection list."""
        return OTPPurpose.get_selection()

    # -- Default Values ---------------------------------------------------- #
    @api.model
    def default_get(self, fields_list: list) -> dict:
        """Set default TTL for OTP expiration."""
        res = super().default_get(fields_list)
        if 'expires_at' in fields_list and 'expires_at' not in res:
            res['expires_at'] = fields.Datetime.to_string(
                fields.Datetime.now() + timedelta(minutes=5)
            )
        return res

    @api.model
    def cleanup_expired_otps_cron(self) -> int:
        """Scheduled action to clean up expired OTPs."""
        return self.env['jabin.otp.service'].cleanup_expired_otps()

    # -- Security Methods -------------------------------------------------- #
    @staticmethod
    def _hash_code(code: str) -> str:
        """Hash the OTP code using SHA256 with salt."""
        if not code:
            raise ValidationError('Cannot hash empty code.')
        salt = secrets.token_hex(16)
        salted_code = f"{code}{salt}"
        return f"{salt}${hashlib.sha256(salted_code.encode()).hexdigest()}"

    @staticmethod
    def _verify_hash(code: str, stored_hash: str) -> bool:
        """Verify a code against the stored hash."""
        if not code or not stored_hash:
            return False
        try:
            salt, hash_value = stored_hash.split('$', 1)
            salted_code = f"{code}{salt}"
            computed_hash = hashlib.sha256(salted_code.encode()).hexdigest()
            return secrets.compare_digest(computed_hash, hash_value)
        except (ValueError, AttributeError):
            return False

    # -- CRUD Overrides ---------------------------------------------------- #
    @api.model
    def create(self, vals_list) -> 'JabinOTP':
        """Override create to set default values and hash the code."""
        # Convert single dict to list if needed
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        for vals in vals_list:
            if 'code_hash' in vals and vals['code_hash']:
                # Code is already hashed (from service)
                pass
            elif 'code' in vals and vals['code']:
                # Hash the plain code
                vals['code_hash'] = self._hash_code(vals.pop('code'))
            else:
                raise ValidationError('Either code or code_hash must be provided.')

            if 'expires_at' not in vals or not vals['expires_at']:
                vals['expires_at'] = fields.Datetime.to_string(
                    fields.Datetime.now() + timedelta(minutes=5)
                )

            # Set last_sent_at on creation
            if 'last_sent_at' not in vals or not vals['last_sent_at']:
                vals['last_sent_at'] = fields.Datetime.now()

            # Extract request metadata
            try:
                from odoo.http import request
                httprequest = getattr(request, 'httprequest', None)
                if httprequest:
                    forwarded = httprequest.headers.get('X-Forwarded-For')
                    vals['ip_address'] = forwarded.split(',')[0].strip() if forwarded else httprequest.remote_addr
                    vals['user_agent'] = httprequest.headers.get('User-Agent', '')[:256]
            except Exception:
                pass

        records = super().create(vals_list)
        for record in records:
            _get_logger().audit(
                'OTP created: email=%s purpose=%s',
                record.email,
                record.purpose,
                extra={'email': record.email, 'purpose': record.purpose}
            )
        return records

    def write(self, vals: dict) -> bool:
        """Override write to track verification and update timestamps."""
        if 'verified' in vals and vals['verified'] and not self.verified:
            vals['verified_at'] = fields.Datetime.now()
            for record in self:
                _get_logger().audit(
                    'OTP verified: email=%s purpose=%s',
                    record.email,
                    record.purpose,
                    extra={'email': record.email, 'purpose': record.purpose}
                )

        if 'resend_count' in vals and vals['resend_count'] > self.resend_count:
            vals['last_sent_at'] = fields.Datetime.now()

        return super().write(vals)

    # -- Query Methods ------------------------------------------------------ #
    @api.model
    def find_active_otp(
            self,
            email: str,
            purpose: str,
            include_expired: bool = False
    ) -> 'JabinOTP':
        """Find the active (unverified, not expired) OTP for an email and purpose."""
        domain = [
            ('email', '=', email),
            ('purpose', '=', purpose),
            ('verified', '=', False),
        ]
        if not include_expired:
            domain.append(('expires_at', '>', fields.Datetime.now()))
        return self.search(domain, limit=1)

    @api.model
    def find_by_code_hash(self, code_hash: str) -> 'JabinOTP':
        """Find OTP by its hash."""
        return self.search([('code_hash', '=', code_hash)], limit=1)

    @api.model
    def count_recent_resends(self, email: str, purpose: str, minutes: int = 1) -> int:
        """Count OTP resends for an email and purpose in the last N minutes."""
        cutoff = fields.Datetime.now() - timedelta(minutes=minutes)
        return self.search_count([
            ('email', '=', email),
            ('purpose', '=', purpose),
            ('last_sent_at', '>=', cutoff),
        ])

    @api.model
    def invalidate_all_for_email(self, email: str, purpose: Optional[str] = None) -> int:
        """
        Invalidate all OTPs for an email (optionally filtered by purpose).
        This deletes the OTP records instead of just marking them expired
        to avoid unique constraint violations.
        """
        domain = [('email', '=', email), ('verified', '=', False)]
        if purpose:
            domain.append(('purpose', '=', purpose))

        # Find all active OTPs
        records = self.search(domain)
        count = len(records)

        if records:
            # Delete the records instead of updating them
            # This ensures no unique constraint violations
            records.unlink()

            _get_logger().audit(
                'Deleted %d OTPs for email=%s purpose=%s',
                count,
                email,
                purpose or 'all',
                extra={'email': email, 'count': count, 'purpose': purpose}
            )

        return count

    # -- Utility Methods --------------------------------------------------- #
    def is_expired(self) -> bool:
        """Check if the OTP has expired."""
        self.ensure_one()
        return self.expires_at < fields.Datetime.now()

    def can_verify(self) -> bool:
        """Check if the OTP can still be verified (not expired, attempts remaining)."""
        self.ensure_one()
        return not self.is_expired() and self.attempts < self.max_attempts

    def increment_attempts(self) -> None:
        """Increment the attempt counter."""
        self.ensure_one()
        self.write({'attempts': self.attempts + 1})

    def mark_verified(self) -> None:
        """Mark the OTP as verified."""
        self.ensure_one()
        self.write({'verified': True, 'verified_at': fields.Datetime.now()})

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses (excludes sensitive data)."""
        self.ensure_one()
        return {
            'id': self.id,
            'email': self.email,
            'purpose': self.purpose,
            'expires_at': self.expires_at,
            'attempts': self.attempts,
            'max_attempts': self.max_attempts,
            'resend_count': self.resend_count,
            'verified': self.verified,
            'created_at': self.created_at,
        }