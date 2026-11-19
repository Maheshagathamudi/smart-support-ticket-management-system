import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import settings


def send_verification_email(email: str, full_name: str, token: str) -> None:
    if not settings.smtp_host:
        raise RuntimeError("SMTP_HOST must be configured to send verification email.")

    message = EmailMessage()
    message["Subject"] = "Verify your Support Desk email"
    message["From"] = settings.email_from
    message["To"] = email
    link = f"{settings.public_base_url.rstrip('/')}/?verify={token}"
    message.set_content(
        f"Hello {full_name},\n\n"
        f"Verify your email address by opening this link (valid for "
        f"{settings.email_verification_minutes} minutes):\n{link}\n\n"
        "If you did not create this account, you can ignore this message."
    )

    context = ssl.create_default_context()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        server.starttls(context=context)
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)
