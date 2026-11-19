from typing import Optional
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.addons.jabin_core import JabinLogger

_logger = JabinLogger.get("auth.service")


class LoginService(models.AbstractModel):
    _name = 'jabin.auth.login.service'
    _description = 'Login Service'

    @api.model
    def _get_demo_account_config(self) -> dict:
        """Fetch Apple Review / Demo account configuration from system parameters."""
        ICP = self.env['ir.config_parameter'].sudo()
        enabled_raw = ICP.get_param('jabin.auth.demo_enabled', default='True')
        enabled = str(enabled_raw).strip().lower() in ('true', '1', 'yes')
        phones_raw = (ICP.get_param('jabin.auth.demo_phone') or '+966500000000,+966500000001').strip()
        otp_raw = (ICP.get_param('jabin.auth.demo_otp') or '123456').strip()

        authentica = self.env['jabin.authentica.service'].sudo()
        normalized_phones = []
        for raw_item in phones_raw.split(','):
            item = raw_item.strip()
            if not item:
                continue
            try:
                norm = authentica.normalize_saudi_phone(item)
            except Exception:
                norm = item
            if norm not in normalized_phones:
                normalized_phones.append(norm)

        return {
            'enabled': enabled,
            'phones': normalized_phones,
            'primary_phone': normalized_phones[0] if normalized_phones else None,
            'otp': otp_raw,
        }

    @api.model
    def _is_demo_phone(self, normalized_identifier: str) -> bool:
        """Return True if demo mode is enabled and identifier matches a configured demo phone."""
        config = self._get_demo_account_config()
        return bool(config['enabled'] and normalized_identifier in config['phones'])

    @api.model
    def _get_or_create_demo_user(self, normalized_phone: str):
        """Fetch or provision an active customer user for the configured demo phone.

        The primary demo phone is always auto-provisioned if missing.
        Secondary demo phones (e.g. +966500000001) are provisioned once and
        will not be recreated after account deletion.
        """
        User = self.env['res.users'].sudo()
        user = User.find_by_phone(normalized_phone)
        if not user:
            config = self._get_demo_account_config()
            is_primary = normalized_phone == config.get('primary_phone')
            ICP = self.env['ir.config_parameter'].sudo()
            provisioned_key = f'jabin.auth.demo_provisioned.{normalized_phone}'
            if not is_primary and ICP.get_param(provisioned_key):
                return User.browse()

            user = User.create({
                'login': normalized_phone,
                'name': 'Apple Review Demo',
                'phone': normalized_phone,
                'status': 'active',
                'user_type': 'customer',
                'profile_completed': True,
                'verified_at': fields.Datetime.now(),
            })
            if not is_primary:
                ICP.set_param(provisioned_key, 'True')
            _logger.audit('DEMO_USER_CREATED', f'Demo review user created: {normalized_phone}')
        elif user.status == 'pending':
            user.write({
                'status': 'active',
                'profile_completed': True,
                'verified_at': fields.Datetime.now(),
            })
        return user

    @api.model
    def _build_login_response(self, user) -> dict:
        """Generate auth tokens and serialize user payload for login responses."""
        TokenService = self.env['jabin.auth.token.service']
        tokens = TokenService.generate_tokens(user)
        tokens['user'] = {
            'id': user.id,
            'email': user.email or user.login,
            'phone': user.phone or (user.partner_id.phone if user.partner_id else None),
            'status': user.status,
            'profile_completed': user.profile_completed,
        }
        return tokens

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
            msg = _("Verification code sent via SMS to your phone.")
            if self._is_demo_phone(normalized_identifier):
                user = self._get_or_create_demo_user(normalized_identifier)
                if not user:
                    _logger.audit('LOGIN_FAILED', f'Demo user was deleted: {normalized_identifier}')
                    raise ValidationError(_("User not found."))
                _logger.audit('DEMO_LOGIN_OTP_BYPASSED', f'Demo login initiated for {normalized_identifier}')
                return {
                    'expires_in': OTPService.OTP_EXPIRY_MINUTES * 60,
                    'requires_verification': False,
                    'channel': channel,
                    'identifier': normalized_identifier,
                    'message': msg,
                }
            user = User.find_by_phone(normalized_identifier)
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
                plain_code = OTPService.create_and_send_otp(
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
                    'message': _("Account needs verification. A new code has been sent."),
                    'otp': plain_code,
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
            plain_code = OTPService.create_and_send_otp(
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
                'message': msg,
                'otp': plain_code,
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
            if self._is_demo_phone(normalized_identifier):
                demo_config = self._get_demo_account_config()
                if str(otp_code).strip() != demo_config['otp']:
                    _logger.audit('DEMO_LOGIN_VERIFY_FAILED', f'Invalid demo OTP for {normalized_identifier}')
                    raise ValidationError(_("Invalid or expired OTP."))
                user = self._get_or_create_demo_user(normalized_identifier)
                if not user:
                    _logger.audit('LOGIN_VERIFY_FAILED', f'Demo user was deleted: {normalized_identifier}')
                    raise ValidationError(_("User not found."))
                user.update_last_login()
                _logger.audit('DEMO_LOGIN_SUCCESS', f'Demo user logged in: {normalized_identifier}')
                return self._build_login_response(user)
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

            return self._build_login_response(user)

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

        return self._build_login_response(user)

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