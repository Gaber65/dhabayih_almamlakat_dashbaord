from __future__ import annotations
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Optional

from odoo.addons.jabin_core import JabinLogger
from odoo import api, fields, models, _
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
    """Jabin One-Time Password (OTP) Model.

    Stores OTP codes securely as hashes with expiration and attempt tracking.
    """
    _name = 'jabin.otp'
    _description = 'Dhabayih Lmamlaka OTP'
    _order = 'created_at desc'
    _rec_name = 'display_name'

    # -- Fields ----------------------------------------------------------- #
    email = fields.Char(
        string='Email',
        required=False,
        index=True,
        help='Email address for which the OTP was generated.'
    )
    phone = fields.Char(
        string='Phone Number',
        index=True,
        help='Saudi mobile phone number (+9665XXXXXXXX) for which the OTP was generated.'
    )
    channel = fields.Selection(
        selection=[
            ('sms', 'SMS'),
            ('email', 'Email'),
            ('whatsapp', 'WhatsApp'),
        ],
        string='Channel',
        default='email',
        required=True,
        index=True,
        help='Delivery channel used to send this OTP.'
    )
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=False
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
    @api.constrains('email', 'phone', 'purpose', 'verified', 'channel')
    def _check_unique_active_otp(self):
        for rec in self:
            if not rec.verified:
                if rec.channel in ('sms', 'whatsapp') or rec.phone:
                    if not rec.phone:
                        raise ValidationError(_('Phone number is required for SMS OTP.'))
                    duplicate = self.search([
                        ('id', '!=', rec.id),
                        ('phone', '=', rec.phone),
                        ('purpose', '=', rec.purpose),
                        ('verified', '=', False),
                    ], limit=1)
                    if duplicate:
                        raise ValidationError(_('Only one active (unverified) OTP per phone and purpose is allowed.'))
                else:
                    if not rec.email:
                        raise ValidationError(_('Email is required for Email OTP.'))
                    duplicate = self.search([
                        ('id', '!=', rec.id),
                        ('email', '=', rec.email),
                        ('purpose', '=', rec.purpose),
                        ('verified', '=', False),
                    ], limit=1)
                    if duplicate:
                        raise ValidationError(_('Only one active (unverified) OTP per email and purpose is allowed.'))

    def init(self):
        super().init()
        # Drop legacy restrictive index if exists, replace with partial indexes
        self.env.cr.execute("""
            DROP INDEX IF EXISTS jabin_otp_email_purpose_active_idx;
            CREATE UNIQUE INDEX IF NOT EXISTS jabin_otp_email_purpose_active_idx
            ON jabin_otp (email, purpose)
            WHERE verified = false AND email IS NOT NULL;
        """)
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS jabin_otp_phone_purpose_active_idx
            ON jabin_otp (phone, purpose)
            WHERE verified = false AND phone IS NOT NULL;
        """)

    # -- Helper Methods ---------------------------------------------------- #
    @api.depends('phone', 'email')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.phone or rec.email or f"OTP #{rec.id}"

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
    @api.model_create_multi
    def create(self, vals_list) -> 'JabinOTP':
        """Override create to set default values and hash the code."""
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        for vals in vals_list:
            if 'code_hash' in vals and vals['code_hash']:
                pass
            elif 'code' in vals and vals['code']:
                vals['code_hash'] = self._hash_code(vals.pop('code'))
            else:
                raise ValidationError('Either code or code_hash must be provided.')

            if 'expires_at' not in vals or not vals['expires_at']:
                vals['expires_at'] = fields.Datetime.to_string(
                    fields.Datetime.now() + timedelta(minutes=5)
                )

            if 'last_sent_at' not in vals or not vals['last_sent_at']:
                vals['last_sent_at'] = fields.Datetime.now()

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
                'OTP created: channel=%s identifier=%s purpose=%s',
                record.channel,
                record.phone or record.email,
                record.purpose,
                extra={'channel': record.channel, 'phone': record.phone, 'email': record.email, 'purpose': record.purpose}
            )
        return records

    def write(self, vals: dict) -> bool:
        """Override write to track verification and update timestamps."""
        if 'verified' in vals and vals['verified'] and not self.verified:
            vals['verified_at'] = fields.Datetime.now()
            for record in self:
                _get_logger().audit(
                    'OTP verified: channel=%s identifier=%s purpose=%s',
                    record.channel,
                    record.phone or record.email,
                    record.purpose,
                    extra={'channel': record.channel, 'phone': record.phone, 'email': record.email, 'purpose': record.purpose}
                )

        if 'resend_count' in vals and vals['resend_count'] > self.resend_count:
            vals['last_sent_at'] = fields.Datetime.now()

        return super().write(vals)

    # -- Query Methods ------------------------------------------------------ #
    @api.model
    def find_active_otp(
            self,
            identifier: str,
            purpose: str,
            include_expired: bool = False
    ) -> 'JabinOTP':
        """Find the active (unverified, not expired) OTP for an email or phone and purpose."""
        identifier = str(identifier).strip()
        domain = [
            ('purpose', '=', purpose),
            ('verified', '=', False),
            '|',
            ('email', '=', identifier.lower()),
            ('phone', '=', identifier)
        ]
        if not include_expired:
            domain.append(('expires_at', '>', fields.Datetime.now()))
        return self.search(domain, limit=1)

    @api.model
    def find_by_code_hash(self, code_hash: str) -> 'JabinOTP':
        """Find OTP by its hash."""
        return self.search([('code_hash', '=', code_hash)], limit=1)

    @api.model
    def count_recent_resends(self, identifier: str, purpose: str, minutes: int = 1) -> int:
        """Count OTP resends for an identifier (email or phone) and purpose in the last N minutes."""
        cutoff = fields.Datetime.now() - timedelta(minutes=minutes)
        identifier = str(identifier).strip()
        return self.search_count([
            ('purpose', '=', purpose),
            ('last_sent_at', '>=', cutoff),
            '|',
            ('email', '=', identifier.lower()),
            ('phone', '=', identifier)
        ])

    @api.model
    def invalidate_all_for_email(self, email: str, purpose: Optional[str] = None) -> int:
        """Backwards compatible alias for invalidate_all_for_identifier."""
        return self.invalidate_all_for_identifier(email, purpose)

    @api.model
    def invalidate_all_for_identifier(self, identifier: str, purpose: Optional[str] = None) -> int:
        """Invalidate all unverified OTPs for an email or phone."""
        identifier = str(identifier).strip()
        domain = [
            ('verified', '=', False),
            '|',
            ('email', '=', identifier.lower()),
            ('phone', '=', identifier)
        ]
        if purpose:
            domain.append(('purpose', '=', purpose))

        records = self.search(domain)
        count = len(records)
        if records:
            records.unlink()
            _get_logger().audit(
                'Deleted %d OTPs for identifier=%s purpose=%s',
                count,
                identifier,
                purpose or 'all',
                extra={'identifier': identifier, 'count': count, 'purpose': purpose}
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
            'phone': self.phone,
            'channel': self.channel,
            'purpose': self.purpose,
            'expires_at': self.expires_at,
            'attempts': self.attempts,
            'max_attempts': self.max_attempts,
            'resend_count': self.resend_count,
            'verified': self.verified,
            'created_at': self.created_at,
        }