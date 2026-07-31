from odoo.addons.jabin_core import EmailValidator
from odoo import api, models, _, fields
from odoo.exceptions import ValidationError
from odoo.addons.jabin_core import JabinLogger

_logger = JabinLogger.get("auth.service")


class RegistrationService(models.AbstractModel):
    _name = 'jabin.auth.registration.service'
    _description = 'Registration Service'

    @api.model
    def initiate_registration(self, email: str) -> dict:
        """
        Step 1: Initiate registration by email.
        Creates a pending user or regenerates OTP for existing pending user.

        Args:
            email: User's email address

        Returns:
            dict: Contains expires_in seconds

        Raises:
            ValidationError: If email is invalid or user already active
        """
        User = self.env['res.users']  # Changed from res.users
        OTPService = self.env['jabin.otp.service']

        if not email:
            raise ValidationError(_("Email is required."))

        if not EmailValidator.validate(email):
            raise ValidationError(_("Invalid email format."))

        email = email.strip().lower()
        user = User.find_by_email(email)

        # Rule: If ACTIVE -> 409 Conflict
        if user and user.status == 'active':
            _logger.audit('REGISTER_FAILED', f'Email already active: {email}')
            raise ValidationError(_("Email already registered. Please login."))

        # Rule: If PENDING -> Regenerate OTP
        if user and user.status == 'pending':
            _logger.audit('REGISTER_RESEND', f'Registration OTP resent to {email}')

            # Invalidate existing OTPs
            OTPService.invalidate_existing_otps(email, 'register')

            # Create and send new OTP
            try:
                plain_code = OTPService.create_and_send_otp(email, 'register', user.id)
                _logger.audit('OTP_SENT', f'Registration OTP sent to {email}')

                return {
                    'expires_in': OTPService.OTP_EXPIRY_MINUTES * 60,
                    'message': 'Verification code sent to your email',
                    'requires_verification': True
                }
            except Exception as e:
                _logger.error(f'Failed to send registration OTP to {email}: {e}')
                raise ValidationError(_("Failed to send verification code. Please try again."))

        # Rule: If NOT EXISTS -> Create pending user
        try:
            new_user = User.create({
                'login': email,  # Login is the email
                'email': email,  # Email field (will be copied to partner)
                'name': email.split('@')[0],  # Default name from email
                'status': 'pending',
                'user_type': 'customer',  # Default user type
                'profile_completed': False,
            })

            _logger.audit('USER_CREATED', f'New pending user created for {email}')

            # Create and send OTP
            plain_code = OTPService.create_and_send_otp(email, 'register', new_user.id)
            _logger.audit('OTP_SENT', f'Registration OTP sent to {email}')

            return {
                'expires_in': OTPService.OTP_EXPIRY_MINUTES * 60,
                'message': 'Verification code sent to your email',
                'requires_verification': True
            }

        except Exception as e:
            _logger.error(f'Failed to create user for {email}: {e}')
            raise ValidationError(_("Failed to create account. Please try again."))

    @api.model
    def verify_registration(self, email: str, otp_code: str) -> dict:
        """
        Step 2: Verify OTP and activate user, then generate tokens.

        Args:
            email: User's email address
            otp_code: OTP code to verify

        Returns:
            dict: Contains tokens and user data

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
            _logger.audit('VERIFY_FAILED', f'User not found: {email}')
            raise ValidationError(_("User not found."))

        if user.status == 'active':
            _logger.audit('VERIFY_FAILED', f'User already active: {email}')
            raise ValidationError(_("Account is already verified. Please login."))

        if user.status != 'pending':
            _logger.audit('VERIFY_FAILED', f'Invalid account status: {email} ({user.status})')
            raise ValidationError(_("Account is not in pending state."))

        # Use OTP service to verify
        if not OTPService.verify_otp(email, otp_code, purpose='register'):
            _logger.audit('OTP_VERIFY_FAILED', f'Invalid registration OTP for {email}')
            raise ValidationError(_("Invalid or expired OTP."))

        # Activate user
        try:
            user.write({
                'status': 'active',
                'verified_at': fields.Datetime.now()
            })

            _logger.audit('USER_ACTIVATED', f'User {email} activated')

        except Exception as e:
            _logger.error(f'Failed to activate user {email}: {e}')
            raise ValidationError(_("Failed to activate account. Please try again."))

        # Generate tokens (Access: 24 hours, Refresh: 7 days)
        try:
            tokens = TokenService.generate_tokens(user)
            _logger.audit('TOKENS_GENERATED', f'Tokens generated for {email}')

            # Add user data to tokens
            tokens['user'] = {
                'id': user.id,
                'email': user.login,  # Use login as email
                'status': user.status,
                'profile_completed': user.profile_completed
            }

            return tokens

        except Exception as e:
            _logger.error(f'Failed to generate tokens for {email}: {e}')
            raise ValidationError(_("Failed to generate authentication tokens. Please try again."))

    @api.model
    def resend_verification(self, email: str) -> dict:
        """
        Resend verification OTP for a pending user.
        This is used when user explicitly requests a new code.

        Args:
            email: User's email address

        Returns:
            dict: Contains expires_in seconds

        Raises:
            ValidationError: If user not found or already active
        """
        User = self.env['res.users']  # Changed from res.users
        OTPService = self.env['jabin.otp.service']

        if not email:
            raise ValidationError(_("Email is required."))

        if not EmailValidator.validate(email):
            raise ValidationError(_("Invalid email format."))

        email = email.strip().lower()
        user = User.find_by_email(email)

        if not user:
            _logger.audit('RESEND_FAILED', f'User not found: {email}')
            raise ValidationError(_("User not found."))

        if user.status == 'active':
            _logger.audit('RESEND_FAILED', f'User already active: {email}')
            raise ValidationError(_("Account is already verified. Please login."))

        if user.status != 'pending':
            _logger.audit('RESEND_FAILED', f'Invalid account status: {email} ({user.status})')
            raise ValidationError(_("Account is not in pending state."))

        # Check rate limiting
        can_resend, reason = OTPService.can_resend_otp(email, 'register')
        if not can_resend:
            _logger.audit('RESEND_RATE_LIMITED', f'Rate limit exceeded for {email}')
            raise ValidationError(_(reason))

        # Invalidate existing OTPs
        OTPService.invalidate_existing_otps(email, 'register')

        # Create and send new OTP
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

    @api.model
    def check_registration_status(self, email: str) -> dict:
        """
        Check the registration status of a user.
        Useful for frontend to determine what UI to show.

        Args:
            email: User's email address

        Returns:
            dict: Status information
        """
        User = self.env['res.users']  # Changed from res.users

        if not email:
            raise ValidationError(_("Email is required."))

        email = email.strip().lower()
        user = User.find_by_email(email)

        if not user:
            return {
                'exists': False,
                'status': 'not_registered',
                'message': 'No account found with this email'
            }

        # Return status information
        status_info = {
            'exists': True,
            'status': user.status,
            'email': user.login,  # Use login as email
            'profile_completed': user.profile_completed
        }

        if user.status == 'pending':
            status_info['message'] = 'Account created but not verified. Please check your email for verification code.'
            status_info['action'] = 'verify_account'
        elif user.status == 'active':
            status_info['message'] = 'Account is active and verified.'
            status_info['action'] = 'login'
        elif user.status == 'suspended':
            status_info['message'] = 'Account is suspended. Please contact support.'
            status_info['action'] = 'contact_support'
        elif user.status == 'inactive':
            status_info['message'] = 'Account is inactive. Please contact support.'
            status_info['action'] = 'contact_support'
        else:
            status_info['message'] = 'Unknown account status.'
            status_info['action'] = 'contact_support'

        return status_info

    @api.model
    def _send_otp_email(self, email: str, otp_code: str, purpose: str = 'register') -> bool:
        """
        Helper method to send OTP email using the email service.

        Args:
            email: Recipient email address
            otp_code: The OTP code to send
            purpose: Purpose of the OTP (used to select template)

        Returns:
            bool: True if sent successfully

        Raises:
            ValidationError: If sending fails
        """
        try:
            email_service = self.env['jabin.email.service']

            # Check if email service exists
            if not email_service:
                _logger.error('Email service not found')
                raise ValidationError(_("Email service not available."))

            # Send the verification code
            success = email_service.send_verification_code(
                email=email,
                code=otp_code,
                purpose=purpose
            )

            if success:
                _logger.audit(
                    'OTP_EMAIL_SENT',
                    f'OTP email sent to {email} for purpose {purpose}',
                    extra={'email': email, 'purpose': purpose}
                )
                return True
            else:
                _logger.error(f'Email service returned False for {email}')
                return False

        except ValidationError as e:
            # Re-raise ValidationError
            raise e
        except Exception as e:
            _logger.error(f'Failed to send OTP email to {email}: {e}')
            raise ValidationError(_("Failed to send verification email. Please try again."))