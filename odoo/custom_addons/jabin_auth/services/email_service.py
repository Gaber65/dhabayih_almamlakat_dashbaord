import os
import socket
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

            # Connect to SMTP server with a 10-second timeout
            if smtp["ssl"]:
                server = smtplib.SMTP_SSL(
                    smtp["host"],
                    smtp["port"],
                    timeout=10
                )
            else:
                server = smtplib.SMTP(
                    smtp["host"],
                    smtp["port"],
                    timeout=10
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

        except (OSError, socket.error, smtplib.SMTPException) as exc:
            _logger.error(
                "SMTP email failed (%s): %s",
                exc.__class__.__name__,
                exc
            )
            raise ValidationError(
                "Failed to send verification email. Please try again later."
            )
        except Exception as exc:
            _logger.error(
                "Unexpected error sending email: %s",
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
        Get SMTP configuration from environment variables or Odoo config.

        Returns:
            dict: SMTP configuration
        """
        env_server = os.getenv("SMTP_SERVER")
        env_port = os.getenv("SMTP_PORT")
        env_user = os.getenv("SMTP_USER")
        env_password = os.getenv("SMTP_PASSWORD")
        env_tls = os.getenv("SMTP_TLS")
        env_ssl = os.getenv("SMTP_SSL")

        tls_value = env_tls if env_tls is not None else config.get("smtp_tls", "True")
        ssl_value = env_ssl if env_ssl is not None else config.get("smtp_ssl", "False")

        if isinstance(tls_value, bool):
            tls_enabled = tls_value
        elif isinstance(tls_value, str):
            tls_enabled = tls_value.lower() in ("true", "1", "yes")
        else:
            tls_enabled = bool(tls_value)

        if isinstance(ssl_value, bool):
            ssl_enabled = ssl_value
        elif isinstance(ssl_value, str):
            ssl_enabled = ssl_value.lower() in ("true", "1", "yes")
        else:
            ssl_enabled = bool(ssl_value)

        return {
            "host": env_server or config.get("smtp_server", "smtp.gmail.com"),
            "port": int(env_port or config.get("smtp_port", 587)),
            "username": env_user or config.get("smtp_user", ""),
            "password": env_password or config.get("smtp_password", ""),
            "tls": tls_enabled,
            "ssl": ssl_enabled,
        }