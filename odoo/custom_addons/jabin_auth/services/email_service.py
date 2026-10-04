# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import socket
import smtplib
from typing import Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.utils import formataddr

from odoo import api, models
from odoo.exceptions import ValidationError
from odoo.tools.config import config
from odoo.addons.jabin_core import JabinLogger

_logger = JabinLogger.get("jabin.email")


class EmailService(models.AbstractModel):
    _name = "jabin.email.service"
    _description = "Dhabayih Lmamlaka Email Service"

    APP_NAME_AR = "ذبائح المملكة"
    APP_NAME_EN = "Dhabayih Al-Mamlaka"

    TEMPLATES_AR = {
        "register": {
            "subject": "رمز التحقق لتسجيل حسابك في ذبائح المملكة",
            "badge": "إنشاء حساب جديد",
            "title": "مرحباً بك في ذبائح المملكة!",
            "subtitle": "يسعدنا انضمامك إلينا! لتأكيد إنشاء وتفعيل حسابك الجديد، يُرجى إدخال رمز التحقق التالي في التطبيق:",
            "plain_message": """مرحباً بك في ذبائح المملكة!

يسعدنا انضمامك إلينا! رمز التحقق لتسجيل وتفعيل حسابك هو:
{code}

⏳ هذا الرمز صالح لمدة 5 دقائق فقط.
🔒 تنبيه أمني: لا تشارك هذا الرمز مع أي شخص. موظفو ذبائح المملكة لن يطلبوا منك هذا الرمز أبداً.

مع تحيات،
فريق ذبائح المملكة
Dhabayih Al-Mamlaka
"""
        },
        "login": {
            "subject": "رمز التحقق لتسجيل الدخول إلى ذبائح المملكة",
            "badge": "تأكيد تسجيل الدخول",
            "title": "تأكيد تسجيل الدخول",
            "subtitle": "لتأكيد عملية الدخول إلى حسابك في منصة ذبائح المملكة بأمان وسرية، يُرجى إدخال رمز التحقق التالي:",
            "plain_message": """مرحباً بك،

لتأكيد عملية تسجيل الدخول إلى حسابك في ذبائح المملكة، رمز التحقق الخاص بك هو:
{code}

⏳ هذا الرمز صالح لمدة 5 دقائق فقط.
🔒 تنبيه أمني: لا تشارك هذا الرمز مع أي شخص حرصاً على سرية وأمان حسابك.

مع تحيات،
فريق ذبائح المملكة
Dhabayih Al-Mamlaka
"""
        },
        "password_reset": {
            "subject": "رمز التحقق لإعادة تعيين كلمة المرور - ذبائح المملكة",
            "badge": "استعادة الحساب",
            "title": "إعادة تعيين كلمة المرور",
            "subtitle": "تلقينا طلباً لإعادة تعيين كلمة المرور لحسابك. يُرجى إدخال رمز التحقق التالي للمتابعة:",
            "plain_message": """مرحباً بك،

رمز التحقق لإعادة تعيين كلمة المرور لحسابك في ذبائح المملكة هو:
{code}

⏳ هذا الرمز صالح لمدة 5 دقائق فقط.
إذا لم تقم بطلب إعادة تعيين كلمة المرور، يرجى تجاهل هذه الرسالة.

مع تحيات،
فريق ذبائح المملكة
"""
        },
        "email_change": {
            "subject": "رمز التحقق لتغيير البريد الإلكتروني - ذبائح المملكة",
            "badge": "تحديث البيانات",
            "title": "تأكيد تغيير البريد الإلكتروني",
            "subtitle": "لتأكيد عنوان بريدك الإلكتروني الجديد في منصة ذبائح المملكة، يُرجى استخدام رمز التحقق التالي:",
            "plain_message": """مرحباً بك،

رمز التحقق لتغيير بريدك الإلكتروني في ذبائح المملكة هو:
{code}

⏳ هذا الرمز صالح لمدة 5 دقائق فقط.

مع تحيات،
فريق ذبائح المملكة
"""
        }
    }

    TEMPLATES_EN = {
        "register": {
            "subject": "Verification Code - Welcome to Dhabayih Al-Mamlaka",
            "badge": "New Registration",
            "title": "Welcome to Dhabayih Al-Mamlaka!",
            "subtitle": "We are thrilled to welcome you! To verify and activate your new account, please enter the following verification code:",
            "plain_message": """Welcome to Dhabayih Al-Mamlaka!

Your verification code to activate your account is:
{code}

⏳ This code is valid for 5 minutes only.
🔒 Security notice: Never share this code with anyone. Dhabayih Al-Mamlaka staff will never ask for your code.

Best regards,
Dhabayih Al-Mamlaka Team
"""
        },
        "login": {
            "subject": "Sign-In Verification Code - Dhabayih Al-Mamlaka",
            "badge": "Sign In Verification",
            "title": "Confirm Your Sign In",
            "subtitle": "To securely verify your sign-in to Dhabayih Al-Mamlaka platform, please enter the one-time code below:",
            "plain_message": """Hello,

Your verification code to sign in to your Dhabayih Al-Mamlaka account is:
{code}

⏳ This code is valid for 5 minutes only.
🔒 Security notice: Never share this code with anyone.

Best regards,
Dhabayih Al-Mamlaka Team
"""
        },
        "password_reset": {
            "subject": "Password Reset Code - Dhabayih Al-Mamlaka",
            "badge": "Password Recovery",
            "title": "Reset Your Password",
            "subtitle": "We received a request to reset your account password. Enter the verification code below to proceed:",
            "plain_message": """Hello,

Your verification code to reset your password is:
{code}

⏳ This code is valid for 5 minutes only.
If you did not request this, please safely ignore this email.

Best regards,
Dhabayih Al-Mamlaka Team
"""
        },
        "email_change": {
            "subject": "Email Change Verification - Dhabayih Al-Mamlaka",
            "badge": "Email Verification",
            "title": "Change Email Address",
            "subtitle": "To confirm your new email address on Dhabayih Al-Mamlaka, please enter the verification code below:",
            "plain_message": """Hello,

Your verification code to confirm your new email address is:
{code}

⏳ This code is valid for 5 minutes only.

Best regards,
Dhabayih Al-Mamlaka Team
"""
        }
    }

    # Backward compatibility
    TEMPLATES = TEMPLATES_AR

    # ---------------------------------------------------------
    # HTML Email Builder (Production-Ready)
    # ---------------------------------------------------------
    @api.model
    def _build_html_email(self, code: str, purpose: str = "register", lang: str = "ar") -> str:
        """Construct a luxury, responsive HTML email template for Dhabayih Al-Mamlaka."""
        is_en = (str(lang).lower() == "en")
        t_dict = self.TEMPLATES_EN if is_en else self.TEMPLATES_AR
        tpl = t_dict.get(purpose, t_dict["register"])

        badge = tpl.get("badge", "رمز التحقق" if not is_en else "Verification Code")
        title = tpl.get("title", "ذبائح المملكة" if not is_en else "Dhabayih Al-Mamlaka")
        subtitle = tpl.get("subtitle", "")

        dir_attr = "ltr" if is_en else "rtl"
        align = "left" if is_en else "right"
        opp_align = "right" if is_en else "left"
        font_family = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" if is_en else "'Segoe UI', Tahoma, Geneva, Verdana, 'Cairo', sans-serif"

        brand_title = self.APP_NAME_EN if is_en else self.APP_NAME_AR
        brand_subtitle = "PREMIUM FRESH MEAT" if is_en else "DHABAYIH AL-MAMLAKA"
        tagline = "Premium, hand-selected fresh municipal meat delivered directly to your doorstep" if is_en else "جودة اللحوم البلدية الطازجة والمختارة بعناية تصلك إلى باب منزلك"
        copyright_text = "All rights reserved © 2026 Dhabayih Al-Mamlaka" if is_en else "جميع الحقوق محفوظة © 2026 ذبائح المملكة"
        disclaimer = "This is an automated security email, please do not reply. If you did not request this code, you can safely ignore this email." if is_en else "هذا بريد إلكتروني آلي، يرجى عدم الرد على هذه الرسالة. إذا لم تكن قد طلبت هذا الرمز، يُرجى تجاهل الرسالة بأمان."

        otp_label = "ONE-TIME VERIFICATION CODE (OTP)" if is_en else "رمز التحقق لمرة واحدة (OTP)"
        expiry_badge = "⏳ Valid for 5 minutes only" if is_en else "⏳ هذا الرمز صالح للاستخدام لمدة 5 دقائق فقط"
        security_title = "Security Notice" if is_en else "تنبيه أمني مهم"
        security_body = (
            "Never share this verification code with anyone. <strong>Dhabayih Al-Mamlaka</strong> staff will never ask for your code under any circumstances."
            if is_en else
            "لا تشارك هذا الرمز السري مع أي شخص. لن يطلب منك موظفو <strong>ذبائح المملكة</strong> هذا الرمز إطلاقاً لضمان أمان وخصوصية حسابك."
        )

        # Split dynamic OTP code into individual luxury digit cards
        code_str = str(code).strip()
        digit_cells = ""
        for d in code_str:
            digit_cells += f"""
              <td align="center" valign="middle" style="width: 36px; height: 46px; background-color: #ffffff; border: 1.5px solid #dcd3c1; border-radius: 10px; font-family: 'Courier New', Courier, monospace, sans-serif; font-size: 24px; font-weight: 800; color: #741d30; padding: 0; box-shadow: 0 2px 5px rgba(116, 29, 48, 0.04);">
                {d}
              </td>
              <td style="width: 5px;"></td>
            """
        if digit_cells.endswith('<td style="width: 5px;"></td>\n            '):
            digit_cells = digit_cells[:-len('<td style="width: 5px;"></td>\n            ')]

        security_border = f"border-{align}: 4px solid #741d30;"

        html = f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="{'en' if is_en else 'ar'}" dir="{dir_attr}">
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="format-detection" content="telephone=no" />
  <meta name="x-apple-disable-message-reformatting" />
  <title>{title} - {brand_title}</title>
  <!--[if mso]>
  <style type="text/css">
    body, table, td, p, h1, h2, a, span {{ font-family: Arial, sans-serif !important; }}
  </style>
  <![endif]-->
  <style type="text/css">
    body {{
      margin: 0;
      padding: 0;
      width: 100% !important;
      -webkit-text-size-adjust: 100%;
      -ms-text-size-adjust: 100%;
      background-color: #f7f5f0;
    }}
    img {{
      border: 0;
      outline: none;
      text-decoration: none;
      -ms-interpolation-mode: bicubic;
    }}
    table {{
      border-collapse: collapse;
      mso-table-lspace: 0pt;
      mso-table-rspace: 0pt;
    }}
  </style>
</head>
<body style="margin: 0; padding: 0; background-color: #f7f5f0; font-family: {font_family}; direction: {dir_attr};">
  <div style="width: 100%; background-color: #f7f5f0; margin: 0; padding: 28px 0;">
    <!--[if (gte mso 9)|(IE)]>
    <table role="presentation" align="center" border="0" cellspacing="0" cellpadding="0" width="580" style="width: 580px; margin: 0 auto;">
    <tr>
    <td align="center" valign="top">
    <![endif]-->
    
    <div style="max-width: 580px; width: 100%; margin: 0 auto; padding: 0 12px; box-sizing: border-box;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width: 100%; background-color: #ffffff; border-radius: 20px; border: 1px solid #eae3d2; overflow: hidden; box-shadow: 0 10px 30px rgba(116, 29, 48, 0.05); margin: 0 auto;">
        
        <!-- Top Royal Gradient Accent Line (5px) -->
        <tr>
          <td style="background: linear-gradient(90deg, #c29e52 0%, #741d30 50%, #c29e52 100%); background-color: #741d30; height: 5px; font-size: 1px; line-height: 1px;">&nbsp;</td>
        </tr>

        <!-- Header Section -->
        <tr>
          <td align="center" valign="top" style="background: linear-gradient(180deg, #fdfbf8 0%, #ffffff 100%); background-color: #fdfbf8; padding: 32px 16px 20px; border-bottom: 1px solid #f3ece0; text-align: center;">
            
            <!-- Elegant Logo Frame -->
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 0 auto 14px;">
              <tr>
                <td align="center" valign="middle" style="width: 82px; height: 82px; background-color: #ffffff; border: 2px solid #e7d8be; border-radius: 20px; padding: 6px; box-shadow: 0 8px 18px rgba(116, 29, 48, 0.07);">
                  <img src="cid:app_logo" alt="{brand_title}" width="68" height="68" style="width: 68px; height: 68px; display: block; border-radius: 14px; object-fit: contain;" />
                </td>
              </tr>
            </table>

            <!-- Brand Title & Tagline -->
            <h1 style="margin: 0; font-size: 23px; font-weight: 900; color: #741d30; letter-spacing: -0.5px; line-height: 1.3;">
              {brand_title}
            </h1>
            <p style="margin: 4px 0 0; font-size: 11px; font-weight: 700; color: #c29e52; letter-spacing: 2px; text-transform: uppercase;">
              {brand_subtitle}
            </p>
          </td>
        </tr>

        <!-- Main Content Body -->
        <tr>
          <td align="center" valign="top" style="padding: 28px 20px 32px; text-align: center;">
            
            <!-- Purpose Badge Pill -->
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 0 auto 16px;">
              <tr>
                <td align="center" valign="middle" style="background-color: #fbf7ee; border: 1px solid #ebdcb9; color: #8a6b29; font-size: 12px; font-weight: 800; padding: 5px 16px; border-radius: 50px;">
                  {badge}
                </td>
              </tr>
            </table>

            <!-- Welcoming Title -->
            <h2 style="margin: 0 0 10px; font-size: 20px; font-weight: 800; color: #231c19; line-height: 1.4;">
              {title}
            </h2>

            <!-- Subtitle Context -->
            <p style="margin: 0 0 24px; font-size: 14px; line-height: 1.65; color: #615651; max-width: 440px; margin-left: auto; margin-right: auto;">
              {subtitle}
            </p>

            <!-- Luxury OTP Box -->
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" align="center" style="width: 100%; margin: 0 auto 20px; background-color: #faf7f2; border: 1.5px dashed #c29e52; border-radius: 16px;">
              <tr>
                <td align="center" valign="top" style="padding: 18px 12px;">
                  
                  <!-- OTP Label -->
                  <div style="font-size: 11px; font-weight: 800; color: #741d30; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 12px;">
                    {otp_label}
                  </div>

                  <!-- Discrete Digits Table -->
                  <table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" dir="ltr" style="direction: ltr; margin: 0 auto 12px;">
                    <tr>
                      {digit_cells}
                    </tr>
                  </table>

                  <!-- Expiration Notice Badge -->
                  <table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 0 auto;">
                    <tr>
                      <td align="center" valign="middle" style="background-color: #fff9ed; border: 1px solid #f4dfb2; border-radius: 8px; padding: 5px 12px; font-size: 11px; font-weight: 700; color: #9c7320;">
                        {expiry_badge}
                      </td>
                    </tr>
                  </table>

                </td>
              </tr>
            </table>

            <!-- Security Advisory Card -->
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" align="center" style="width: 100%; margin: 20px auto 0; background-color: #fdfbf8; border: 1px solid #eee6d8; {security_border} border-radius: 10px;">
              <tr>
                <td align="{align}" valign="top" style="padding: 12px 16px; font-size: 12px; line-height: 1.6; color: #5a5049; direction: {dir_attr}; text-align: {align};">
                  <span style="font-size: 14px; line-height: 1;">🔒</span>
                  <strong style="color: #741d30; font-weight: 800; margin-{opp_align}: 4px;">{security_title}:</strong>
                  <span>{security_body}</span>
                </td>
              </tr>
            </table>

          </td>
        </tr>

        <!-- Minimal Elegant Footer -->
        <tr>
          <td align="center" valign="top" style="background-color: #fbf9f5; border-top: 1px solid #f0e9dc; padding: 24px 18px; text-align: center; font-size: 12px; color: #877b73; line-height: 1.7;">
            <p style="margin: 0 0 5px; font-weight: 700; color: #524741;">
              {brand_title} — {tagline}
            </p>
            <p style="margin: 0 0 8px; color: #877b73;">
              {copyright_text}
            </p>
            <p style="margin: 0; font-size: 11px; color: #ad9f95;">
              {disclaimer}
            </p>
          </td>
        </tr>

      </table>
    </div>

    <!--[if (gte mso 9)|(IE)]>
    </td>
    </tr>
    </table>
    <![endif]-->
  </div>
</body>
</html>"""
        return html

    # ---------------------------------------------------------
    # Public Send Methods
    # ---------------------------------------------------------
    @api.model
    def send_verification_code(
            self,
            email: str,
            code: str,
            purpose: str = "register",
            lang: str = "ar"
    ) -> bool:
        """Send a formatted verification code via email."""
        if not email:
            raise ValidationError("Email is required")

        if not code:
            raise ValidationError("OTP code is required")

        is_en = (str(lang).lower() == "en")
        t_dict = self.TEMPLATES_EN if is_en else self.TEMPLATES_AR
        template = t_dict.get(purpose, t_dict["register"])

        subject = template["subject"]
        plain_body = template["plain_message"].format(code=code)
        html_body = self._build_html_email(code=code, purpose=purpose, lang=lang)

        return self.send_email(
            to=email,
            subject=subject,
            body=plain_body,
            html_body=html_body
        )

    # ---------------------------------------------------------
    # SMTP Sender
    # ---------------------------------------------------------
    @api.model
    def send_email(
            self,
            to: str,
            subject: str,
            body: str,
            html_body: Optional[str] = None
    ) -> bool:
        """Send an email using SMTP configuration with Multipart (HTML + Plain + Inline Logo)."""
        smtp = self._smtp_config()

        # If SMTP credentials are not configured, log in console instead of failing
        if not smtp.get("username") or not smtp.get("password"):
            _logger.warning("==================================================")
            _logger.warning("[DEV MODE - NO SMTP CREDENTIALS CONFIGURED]")
            _logger.warning("To: %s | Subject: %s", to, subject)
            _logger.warning("Email Body:\n%s", body)
            _logger.warning("==================================================")
            return True

        try:
            # Root message is 'related' to allow inline images (CID)
            message = MIMEMultipart("related")
            message["From"] = formataddr((self.APP_NAME_AR, smtp["username"]))
            message["To"] = to
            message["Subject"] = subject

            # Alternative part for text vs html
            msg_alternative = MIMEMultipart("alternative")
            message.attach(msg_alternative)

            # Plain text part
            msg_alternative.attach(MIMEText(body, "plain", "utf-8"))

            # HTML part (if provided)
            if html_body:
                msg_alternative.attach(MIMEText(html_body, "html", "utf-8"))

            # Attach inline logo with Content-ID: <app_logo>
            logo_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "static", "src", "img", "app_logo.png"
            )
            if os.path.exists(logo_path):
                try:
                    with open(logo_path, "rb") as f:
                        logo_data = f.read()
                    logo_img = MIMEImage(logo_data, name="app_logo.png")
                    logo_img.add_header("Content-ID", "<app_logo>")
                    logo_img.add_header("Content-Disposition", "inline", filename="app_logo.png")
                    message.attach(logo_img)
                except Exception as img_err:
                    _logger.warning("Failed to attach inline logo to email: %s", img_err)

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
        """Get SMTP configuration from environment variables or Odoo config."""
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

        user_val = env_user if env_user is not None else config.get("smtp_user")
        pass_val = env_password if env_password is not None else config.get("smtp_password")

        username = str(user_val).strip() if user_val and not isinstance(user_val, bool) else ""
        password = str(pass_val).replace(" ", "").strip() if pass_val and not isinstance(pass_val, bool) else ""

        server_val = env_server if env_server is not None else config.get("smtp_server")
        server_host = str(server_val).strip() if server_val and not isinstance(server_val, bool) else "smtp.gmail.com"

        port_val = env_port if env_port is not None else config.get("smtp_port")
        try:
            port_num = int(port_val) if port_val and not isinstance(port_val, bool) else 587
        except (ValueError, TypeError):
            port_num = 587

        return {
            "host": server_host,
            "port": port_num,
            "username": username,
            "password": password,
            "tls": tls_enabled,
            "ssl": ssl_enabled,
        }
