import smtplib
import ssl
from email.message import EmailMessage

from django.conf import settings


def send_email_via_school_smtp(*, settings_obj, to_email, subject, body):
    if not settings_obj or not getattr(settings_obj, "smtp_enabled", False):
        raise ValueError("SMTP is not enabled for this school.")
    if not settings_obj.smtp_host or not settings_obj.smtp_port:
        raise ValueError("SMTP host/port missing.")
    if not settings_obj.smtp_username or not settings_obj.smtp_password:
        raise ValueError("SMTP username/password missing.")

    from_email = settings_obj.smtp_from_email or settings_obj.smtp_username
    from_name = (settings_obj.smtp_from_name or "").strip()
    from_header = f"{from_name} <{from_email}>" if from_name else from_email

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_header
    msg["To"] = to_email
    msg.set_content(body)

    context = ssl.create_default_context()
    helo_name = (getattr(settings, "EMAIL_HELO_NAME", "") or "thewebfix.in").strip()
    if settings_obj.smtp_use_ssl:
        with smtplib.SMTP_SSL(
            settings_obj.smtp_host,
            int(settings_obj.smtp_port),
            context=context,
            timeout=15,
            local_hostname=helo_name,
        ) as smtp:
            smtp.login(settings_obj.smtp_username, settings_obj.smtp_password)
            smtp.send_message(msg)
        return

    with smtplib.SMTP(
        settings_obj.smtp_host,
        int(settings_obj.smtp_port),
        timeout=15,
        local_hostname=helo_name,
    ) as smtp:
        smtp.ehlo()
        if settings_obj.smtp_use_tls:
            smtp.starttls(context=context)
            smtp.ehlo()
        smtp.login(settings_obj.smtp_username, settings_obj.smtp_password)
        smtp.send_message(msg)
