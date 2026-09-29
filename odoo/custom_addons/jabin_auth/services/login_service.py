from odoo import api, models, _
from odoo.exceptions import ValidationError
from odoo.addons.jabin_core import JabinLogger

_logger = JabinLogger.get("auth.service")


class LoginService(models.AbstractModel):
    _name = 'jabin.auth.login.service'
    _description = 'Login Service'

    @api.model
    def initiate_login(self, identifier: str, channel: Optional[str] = None) -> dict:
        """
        Step 1: Request login OTP by email or phone.
        If user is pending, automatically resend verification OTP.

        Args:
            identifier: User's email address or Saudi phone number
            channel: 'sms' or 'email' (auto-detected if None)
        """
        User = self.env['res.users']
        OTPService = self.env['jabin.otp.service']
        AuthenticaService = self.env['jabin.authentica.service'].sudo()

        if not identifier:
            raise ValidationError(_("Email or phone number is required."))

        identifier = str(identifier).strip()
        is_phone = channel == 'sms' or (channel is None and '@' not in identifier)

        if is_phone:
            channel = 'sms'
            normalized_identifier = AuthenticaService.normalize_saudi_phone(identifier)
            user = User.find_by_phone(normalized_identifier)
            msg = _("Verification code sent via SMS to your phone.")
        else:
            channel = 'email'
            normalized_identifier = identifier.lower()
            user = User.find_by_email(normalized_identifier)
            msg = _("Verification code sent to your email.")

        if not user:
            _logger.audit('LOGIN_FAILED', f'User not found: {normalized_identifier}')
            raise ValidationError(_("User not found."))

        # Check account status
        if user.status == 'pending':
            # Auto resend verification OTP for pending user
            try:
                OTPService.invalidate_existing_otps(normalized_identifier, 'register')
                OTPService.create_and_send_otp(
                    identifier=normalized_identifier,
                    purpose='register',
                    user_id=user.id,
                    channel=channel
                )
                return {
                    'expires_in': OTPService.OTP_EXPIRY_MINUTES * 60,
                    'requires_verification': True,
                    'channel': channel,
                    'identifier': normalized_identifier,
                    'message': _("Account needs verification. A new code has been sent.")
                }
            except Exception as exc:
                _logger.error(f'Failed to auto-send verification OTP to {normalized_identifier}: {exc}')
                raise ValidationError(
                    _("Your account is not verified. Please complete registration or request a new verification code.")
                )

        if user.status == 'suspended':
            _logger.audit('LOGIN_FAILED', f'Account suspended: {normalized_identifier}')
            raise ValidationError(_("Account is suspended. Please contact support."))

        if user.status == 'inactive':
            _logger.audit('LOGIN_FAILED', f'Account inactive: {normalized_identifier}')
            raise ValidationError(_("Account is inactive. Please contact support."))

        if user.status != 'active':
            _logger.audit('LOGIN_FAILED', f'Invalid account status: {normalized_identifier} ({user.status})')
            raise ValidationError(_("Invalid account status."))

        # User is active - send login OTP
        OTPService.invalidate_existing_otps(normalized_identifier, 'login')

        try:
            OTPService.create_and_send_otp(
                identifier=normalized_identifier,
                purpose='login',
                user_id=user.id,
                channel=channel
            )
            _logger.audit('LOGIN_OTP_SENT', f'Login OTP sent to {normalized_identifier} via {channel}')

            return {
                'expires_in': OTPService.OTP_EXPIRY_MINUTES * 60,
                'requires_verification': False,
                'channel': channel,
                'identifier': normalized_identifier,
                'message': msg
            }

        except Exception as e:
            _logger.error(f'Failed to send login OTP to {normalized_identifier}: {e}')
            raise ValidationError(_("Failed to send verification code. Please try again."))

    @api.model
    def verify_login(self, identifier: str, otp_code: str) -> dict:
        """
        Step 2: Verify login OTP, update last login, and generate tokens.

        Args:
            identifier: User's email address or phone number
            otp_code: OTP code to verify
        """
        User = self.env['res.users']
        OTPService = self.env['jabin.otp.service']
        TokenService = self.env['jabin.auth.token.service']
        AuthenticaService = self.env['jabin.authentica.service'].sudo()

        if not identifier or not otp_code:
            raise ValidationError(_("Email or phone and OTP code are required."))

        identifier = str(identifier).strip()
        if '@' not in identifier:
            normalized_identifier = AuthenticaService.normalize_saudi_phone(identifier)
            user = User.find_by_phone(normalized_identifier)
        else:
            normalized_identifier = identifier.lower()
            user = User.find_by_email(normalized_identifier)

        if not user:
            _logger.audit('LOGIN_VERIFY_FAILED', f'User not found: {normalized_identifier}')
            raise ValidationError(_("User not found."))

        # Allow pending users to verify with their registration OTP
        if user.status == 'pending':
            if not OTPService.verify_otp(normalized_identifier, otp_code, purpose='register'):
                _logger.audit('VERIFY_FAILED', f'Invalid registration OTP for {normalized_identifier}')
                raise ValidationError(_("Invalid or expired verification code."))

            user.write({'status': 'active', 'verified_at': fields.Datetime.now()})
            _logger.audit('USER_ACTIVATED', f'User activated via login verification: {normalized_identifier}')

            tokens = TokenService.generate_tokens(user)
            tokens['user'] = {
                'id': user.id,
                'email': user.email or user.login,
                'phone': user.phone or (user.partner_id.phone if user.partner_id else None),
                'status': user.status,
                'profile_completed': user.profile_completed
            }
            return tokens

        if user.status != 'active':
            _logger.audit('LOGIN_VERIFY_FAILED', f'Invalid account status for login: {normalized_identifier} ({user.status})')
            raise ValidationError(_("Invalid account status. Please contact support."))

        # Verify login OTP for active users
        if not OTPService.verify_otp(normalized_identifier, otp_code, purpose='login'):
            _logger.audit('LOGIN_VERIFY_FAILED', f'Invalid login OTP for {normalized_identifier}')
            raise ValidationError(_("Invalid or expired OTP."))

        # Update last login timestamp
        user.update_last_login()
        _logger.audit('LOGIN_SUCCESS', f'User logged in: {normalized_identifier}')

        tokens = TokenService.generate_tokens(user)
        tokens['user'] = {
            'id': user.id,
            'email': user.email or user.login,
            'phone': user.phone or (user.partner_id.phone if user.partner_id else None),
            'status': user.status,
            'profile_completed': user.profile_completed
        }
        return tokens

    @api.model
    def resend_verification_for_pending(self, email: str) -> dict:
        """
        Explicitly resend verification OTP for pending users.
        Useful if the auto-send didn't work or user requests again.

        Args:
            email: User's email address

        Returns:
            dict: Contains expires_in seconds
        """
        User = self.env['res.users']  # Changed from res.users
        OTPService = self.env['jabin.otp.service']

        if not email:
            raise ValidationError(_("Email is required."))

        email = email.strip().lower()
        user = User.find_by_email(email)

        if not user:
            raise ValidationError(_("User not found."))

        if user.status == 'active':
            raise ValidationError(_("Account is already verified. Please login."))

        if user.status != 'pending':
            raise ValidationError(_("Account is not in pending state."))

        # Check rate limiting
        can_resend, reason = OTPService.can_resend_otp(email, 'register')
        if not can_resend:
            raise ValidationError(_(reason))

        # Invalidate existing OTPs
        OTPService.invalidate_existing_otps(email, 'register')

        # Create and send new verification OTP
        try:
            plain_code = OTPService.create_and_send_otp(email, 'register', user.id)
            _logger.audit('VERIFICATION_RESENT', f'Verification OTP resent to {email}')

            return {
                'expires_in': OTPService.OTP_EXPIRY_MINUTES * 60,
                'message': 'Verification code sent to your email'
            }
        except Exception as e:
            _logger.error(f'Failed to resend verification OTP to {email}: {e}')
            raise ValidationError(_("Failed to send verification code. Please try again."))