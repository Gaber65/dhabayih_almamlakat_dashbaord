from odoo import api, models, _
from odoo.exceptions import ValidationError
from odoo.addons.jabin_core import JabinLogger

_logger = JabinLogger.get("auth.service")


class LoginService(models.AbstractModel):
    _name = 'jabin.auth.login.service'
    _description = 'Login Service'

    @api.model
    def initiate_login(self, email: str) -> dict:
        """
        Step 1: Request login OTP.
        If user is pending, automatically resend verification OTP.

        Args:
            email: User's email address

        Returns:
            dict: Contains expires_in seconds and status info

        Raises:
            ValidationError: If user not found or account is blocked
        """
        User = self.env['res.users']  # Changed from res.users
        OTPService = self.env['jabin.otp.service']

        if not email:
            raise ValidationError(_("Email is required."))

        email = email.strip().lower()
        user = User.find_by_email(email)

        if not user:
            _logger.audit('LOGIN_FAILED', f'User not found: {email}')
            raise ValidationError(_("User not found."))

        # Check account status
        if user.status == 'pending':
            _logger.error(f'Failed to auto-send verification OTP to {email}')
            raise ValidationError(
                _("Your account is not verified. Please complete registration or request a new verification code.")
            )

        if user.status == 'suspended':
            _logger.audit('LOGIN_FAILED', f'Account suspended: {email}')
            raise ValidationError(_("Account is suspended. Please contact support."))

        if user.status == 'inactive':
            _logger.audit('LOGIN_FAILED', f'Account inactive: {email}')
            raise ValidationError(_("Account is inactive. Please contact support."))

        if user.status != 'active':
            _logger.audit('LOGIN_FAILED', f'Invalid account status: {email} ({user.status})')
            raise ValidationError(_("Invalid account status."))

        # User is active - send login OTP
        OTPService.invalidate_existing_otps(email, 'login')

        try:
            plain_code = OTPService.create_and_send_otp(email, 'login', user.id)
            _logger.audit('LOGIN_OTP_SENT', f'Login OTP sent to {email}')

            return {
                'expires_in': OTPService.OTP_EXPIRY_MINUTES * 60,
                'requires_verification': False,
                'message': 'Verification code sent to your email'
            }

        except Exception as e:
            _logger.error(f'Failed to send login OTP to {email}: {e}')
            raise ValidationError(_("Failed to send verification code. Please try again."))

    @api.model
    def verify_login(self, email: str, otp_code: str) -> dict:
        """
        Step 2: Verify login OTP, update last login, and generate tokens.

        Args:
            email: User's email address
            otp_code: OTP code to verify

        Returns:
            dict: Contains tokens with 24-hour access token

        Raises:
            ValidationError: If OTP is invalid or user status is invalid
        """
        User = self.env['res.users']  # Changed from res.users
        OTPService = self.env['jabin.otp.service']
        TokenService = self.env['jabin.auth.token.service']

        if not email or not otp_code:
            raise ValidationError(_("Email and OTP code are required."))

        email = email.strip().lower()
        user = User.find_by_email(email)

        if not user:
            _logger.audit('LOGIN_VERIFY_FAILED', f'User not found: {email}')
            raise ValidationError(_("User not found."))

        # Allow pending users to verify with their OTP
        if user.status == 'pending':
            # Try to verify with registration OTP
            if not OTPService.verify_otp(email, otp_code, purpose='register'):
                _logger.audit('VERIFY_FAILED', f'Invalid registration OTP for {email}')
                raise ValidationError(_("Invalid or expired verification code."))

            # Activate the user
            user.write({'status': 'active'})
            _logger.audit('USER_ACTIVATED', f'User activated via login verification: {email}')

            # Generate tokens
            tokens = TokenService.generate_tokens(user)
            _logger.audit('TOKENS_GENERATED', f'Tokens generated for {email}')

            return tokens

        if user.status != 'active':
            _logger.audit('LOGIN_VERIFY_FAILED', f'Invalid account status for login: {email} ({user.status})')
            raise ValidationError(_("Invalid account status. Please contact support."))

        # Verify login OTP for active users
        if not OTPService.verify_otp(email, otp_code, purpose='login'):
            _logger.audit('LOGIN_VERIFY_FAILED', f'Invalid login OTP for {email}')
            raise ValidationError(_("Invalid or expired OTP."))

        # Update last login timestamp
        user.update_last_login()
        _logger.audit('LOGIN_SUCCESS', f'User logged in: {email}')

        # Generate tokens (Access: 24 hours, Refresh: 7 days)
        tokens = TokenService.generate_tokens(user)
        _logger.audit('TOKENS_GENERATED', f'Tokens generated for {email}')

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