from typing import Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from odoo import api, models
from odoo.exceptions import ValidationError
from odoo.tools.config import config

from odoo.addons.jabin_core import JabinLogger

_logger = JabinLogger.get("jabin.email")


class EmailService(models.AbstractModel):
    _name = "jabin.email.service"
    _description = "JABIN Email Service"

    TEMPLATES = {
        "register": {
            "subject": "JABIN Registration Verification Code",
            "message": """
Welcome to JABIN.

Your registration verification code is:

{code}

This code expires in 5 minutes.
If you didn't request this code, please ignore this email.

Best regards,
The JABIN Team
"""
        },
        "login": {
            "subject": "JABIN Login Verification Code",
            "message": """
Hello,

Your JABIN login verification code is:

{code}

This code expires in 5 minutes.
If you didn't request this code, please ignore this email.

Best regards,
The JABIN Team
"""
        },
        "password_reset": {
            "subject": "JABIN Password Reset Code",
            "message": """
Hello,

You requested to reset your JABIN password.

Your password reset verification code is:

{code}

This code expires in 5 minutes.
If you didn't request this, please ignore this email.

Best regards,
The JABIN Team
"""
        },
        "email_change": {
            "subject": "JABIN Email Change Verification",
            "message": """
Hello,

You requested to change your JABIN email address.

Your verification code is:

{code}

This code expires in 5 minutes.
If you didn't request this, please ignore this email.

Best regards,
The JABIN Team
"""
        }
    }

    # ---------------------------------------------------------
    # Public
    # ---------------------------------------------------------

    @api.model
    def send_verification_code(
            self,
            email: str,
            code: str,
            purpose: str = "register"
    ) -> bool:
        """
        Send a verification code via email.

        Args:
            email: Recipient email address
            code: The verification code
            purpose: The purpose of the code (register, login, etc.)

        Returns:
            bool: True if sent successfully

        Raises:
            ValidationError: If email or code is missing, or sending fails
        """
        if not email:
            raise ValidationError("Email is required")

        if not code:
            raise ValidationError("OTP code is required")

        # Get template for the purpose, fallback to register
        template = self.TEMPLATES.get(
            purpose,
            self.TEMPLATES["register"]
        )

        # Format the message with the code
        body = template["message"].format(code=code)

        # Send the email
        return self.send_email(
            to=email,
            subject=template["subject"],
            body=body
        )

    # ---------------------------------------------------------
    # SMTP Sender
    # ---------------------------------------------------------

    @api.model
    def send_email(
            self,
            to: str,
            subject: str,
            body: str
    ) -> bool:
        """
        Send an email using SMTP configuration.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body content

        Returns:
            bool: True if sent successfully

        Raises:
            ValidationError: If sending fails
        """
        smtp = self._smtp_config()

        try:
            message = MIMEMultipart()
            message["From"] = smtp["username"]
            message["To"] = to
            message["Subject"] = subject

            message.attach(
                MIMEText(
                    body,
                    "plain",
                    "utf-8"
                )
            )

            # Connect to SMTP server
            if smtp["ssl"]:
                server = smtplib.SMTP_SSL(
                    smtp["host"],
                    smtp["port"]
                )
            else:
                server = smtplib.SMTP(
                    smtp["host"],
                    smtp["port"]
                )

            # Start TLS if configured
            if smtp["tls"]:
                server.starttls()

            # Login if credentials provided
            if smtp["username"] and smtp["password"]:
                server.login(
                    smtp["username"],
                    smtp["password"]
                )

            # Send the email
            server.sendmail(
                smtp["username"],
                to,
                message.as_string()
            )

            server.quit()

            _logger.audit(
                "SMTP email sent",
                extra={
                    "recipient": to,
                    "subject": subject
                }
            )

            return True

        except Exception as exc:
            _logger.exception(
                "SMTP email failed: %s",
                exc
            )
            raise ValidationError(
                "Failed to send verification email. Please try again later."
            )

    # ---------------------------------------------------------
    # SMTP Configuration
    # ---------------------------------------------------------

    @staticmethod
    def _smtp_config() -> dict:
        """
        Get SMTP configuration from Odoo config.

        Returns:
            dict: SMTP configuration
        """
        # Get config values with proper type handling
        tls_value = config.get("smtp_tls", "True")
        ssl_value = config.get("smtp_ssl", "False")

        # Convert to boolean safely
        if isinstance(tls_value, bool):
            tls_enabled = tls_value
        elif isinstance(tls_value, str):
            tls_enabled = tls_value.lower() == "true"
        else:
            tls_enabled = bool(tls_value)

        if isinstance(ssl_value, bool):
            ssl_enabled = ssl_value
        elif isinstance(ssl_value, str):
            ssl_enabled = ssl_value.lower() == "true"
        else:
            ssl_enabled = bool(ssl_value)

        return {
            "host": config.get(
                "smtp_server",
                "smtp.gmail.com"
            ),
            "port": int(
                config.get(
                    "smtp_port",
                    587
                )
            ),
            "username": config.get(
                "smtp_user",
                ""
            ),
            "password": config.get(
                "smtp_password",
                ""
            ),
            "tls": tls_enabled,
            "ssl": ssl_enabled,
        }