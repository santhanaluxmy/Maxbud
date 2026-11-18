"""SMTP delivery never logs credentials, codes, reset links or message bodies."""
from email.message import EmailMessage
import smtplib
import ssl
from app.core.config import get_settings


def configured():
    s = get_settings()
    return bool(s.SMTP_HOST and s.SMTP_FROM and s.SMTP_USERNAME and s.SMTP_PASSWORD)


def send_code(email, code):
    s = get_settings()
    message = EmailMessage()
    message['From'] = s.SMTP_FROM
    message['To'] = email
    message['Subject'] = 'Your MaxBud password recovery code'
    message.set_content(f'Your MaxBud recovery code is {code}. It expires in 10 minutes and can be used once. If you did not request this, ignore this email.')
    client_type = smtplib.SMTP_SSL if s.SMTP_SECURITY == 'ssl' else smtplib.SMTP
    options = {'context': ssl.create_default_context()} if s.SMTP_SECURITY == 'ssl' else {}
    with client_type(s.SMTP_HOST, s.SMTP_PORT, timeout=15, **options) as client:
        if s.SMTP_SECURITY == 'starttls':
            client.starttls(context=ssl.create_default_context())
        client.login(s.SMTP_USERNAME, s.SMTP_PASSWORD)
        client.send_message(message)
