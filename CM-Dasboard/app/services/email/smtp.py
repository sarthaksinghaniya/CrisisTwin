import smtplib
import logging
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings

logger = logging.getLogger(__name__)

def sync_send_email(email_to: str, subject: str, html_content: str) -> None:
    """
    Synchronous email dispatch using smtplib.
    """
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning(
            f"\n[MOCK EMAIL DISPATCH] To: {email_to}\n"
            f"Subject: {subject}\n"
            f"Body:\n{html_content}\n"
        )
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.EMAILS_FROM_EMAIL
    msg["To"] = email_to

    # Attach html body
    msg.attach(MIMEText(html_content, "html"))

    try:
        # Connect to Gmail SMTP
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_TLS:
                server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAILS_FROM_EMAIL, email_to, msg.as_string())
            logger.info(f"Successfully sent email to {email_to}")
    except Exception as e:
        logger.error(f"Failed to send email to {email_to}: {str(e)}", exc_info=True)
        raise e

async def async_send_otp_email(email_to: str, otp: str) -> None:
    """
    Async wrapping of the sync SMTP dispatch using asyncio.to_thread.
    """
    subject = "Delhi CMO Grievance Portal - OTP Verification Code"
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; padding: 20px; line-height: 1.6;">
            <h2 style="color: #0b3c5d;">Delhi CMO Grievance Management System</h2>
            <p>Hello,</p>
            <p>You requested a verification code to log in to the Chief Minister's Office Grievance Portal.</p>
            <div style="background-color: #f5f7fa; border-radius: 4px; padding: 15px; text-align: center; margin: 20px 0;">
                <span style="font-size: 24px; font-weight: bold; letter-spacing: 5px; color: #d9534f;">{otp}</span>
            </div>
            <p style="font-size: 13px; color: #777;">This OTP is cryptographically secure and is valid for <strong>4 minutes</strong>. If you did not make this request, please ignore this email.</p>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
            <p style="font-size: 12px; color: #999; text-align: center;">Government of National Capital Territory of Delhi &copy; 2026</p>
        </body>
    </html>
    """
    await asyncio.to_thread(sync_send_email, email_to, subject, html_content)
