"""Invitation email only. Never log credentials, invitation tokens or message bodies."""
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr
from html import escape
from ipaddress import ip_address
import smtplib
import ssl
from urllib.parse import quote, urlsplit

from fastapi import HTTPException
from pydantic import ValidationError

from app.core.config import Settings


def _email_settings():
    # SMTP credentials and temporary public URLs may rotate while the app is
    # running. Read the canonical settings sources for email only; do not clear
    # the shared cache used by authentication, billing or the database engine.
    try:
        return Settings()
    except ValidationError:
        # Pydantic validation details can contain settings input values. Never
        # return or log those through the invitation endpoint.
        raise HTTPException(503, 'Invitation email configuration is invalid. Ask the administrator to check the email settings.') from None


def _public_origin():
    origin = _email_settings().PUBLIC_FRONTEND_URL.strip().rstrip('/')
    try:
        parsed = urlsplit(origin)
        host = (parsed.hostname or '').lower().rstrip('.')
        valid = (parsed.scheme == 'https' and host and '.' in host
                 and not parsed.username and not parsed.password
                 and not parsed.query and not parsed.fragment and not parsed.path
                 and not any(character in origin for character in ['\\', '\r', '\n', '\t', ' '])
                 and not host.endswith(('.localhost', '.local', '.internal', '.lan', '.test', '.invalid')))
        parsed.port
        try:
            valid = valid and ip_address(host).is_global
        except ValueError:
            valid = valid and not host.replace('.', '').isdigit()
    except ValueError:
        valid = False
    if not valid:
        raise HTTPException(503, 'Invitation email is unavailable: configure a public HTTPS PUBLIC_FRONTEND_URL. Localhost and private addresses cannot be emailed.')
    return origin


def invitation_url(token):
    return _public_origin() + '/invite#invite=' + quote(token, safe='')


def is_local_url(url):
    """Compatibility for existing callers; outgoing messages never allow these."""
    try:
        host = (urlsplit(url).hostname or '').lower().rstrip('.')
        if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal', '.lan')):
            return True
        try:
            return not ip_address(host).is_global
        except ValueError:
            return False
    except ValueError:
        return True


def smtp_options():
    settings = _email_settings()
    host = settings.SMTP_HOST.strip().lower()
    username = settings.SMTP_USERNAME.strip()
    sender = parseaddr(settings.SMTP_FROM.strip())[1]
    password = settings.SMTP_PASSWORD
    # Google displays app passwords in groups of four. Those separators are
    # formatting, not part of the actual Gmail SMTP credential.
    if host == 'smtp.gmail.com':
        password = ''.join(password.split())
    if not all([host, username, sender, password]) or '@' not in sender:
        raise HTTPException(503, 'Invitation email is unavailable because SMTP is not fully configured. Ask the MaxBud administrator to configure email delivery.')
    if host == 'smtp.gmail.com' and ((settings.SMTP_SECURITY == 'starttls' and settings.SMTP_PORT != 587)
                                   or (settings.SMTP_SECURITY == 'ssl' and settings.SMTP_PORT != 465)):
        raise HTTPException(503, 'Gmail SMTP requires STARTTLS on port 587 or SSL on port 465. No invitation email was sent.')
    return host, settings.SMTP_PORT, settings.SMTP_SECURITY, username, password, sender


def configured():
    try:
        smtp_options()
        return True
    except HTTPException:
        return False


def require_configuration():
    _public_origin()
    smtp_options()


def send_invitation(email, *, household_name, inviter_name, url):
    """Return after SMTP accepts DATA, without treating a failed QUIT as failed mail."""
    require_configuration()
    parsed = urlsplit(url)
    if (not url.startswith(_public_origin() + '/invite#invite=') or parsed.path != '/invite'
            or parsed.query or not parsed.fragment.startswith('invite=') or is_local_url(url)):
        raise HTTPException(503, 'Invitation email requires the configured public HTTPS frontend address. No email was sent.')
    host, port, security, username, password, sender = smtp_options()
    message = EmailMessage()
    message['From'] = formataddr(('MaxBud', sender))
    message['To'] = email
    message['Subject'] = f'You\u2019re invited to {household_name} on MaxBud'
    message['Message-ID'] = make_msgid(domain=sender.rsplit('@', 1)[-1])
    message.set_content(
        f'{inviter_name} has invited you to join {household_name} on MaxBud.\n\n'
        f'Accept your invitation: {url}\n\n'
        f'Sign in or create your own account using {email}, then choose Accept Invitation.\n'
        'This invitation expires after seven days. Your personal accounts and financial records stay private.\n\n'
        'If you were not expecting this invitation, you can ignore this email.'
    )
    message.add_alternative(f'''<!doctype html><html><body style="margin:0;background:#EEEAD7;font-family:Arial,sans-serif;color:#174b50">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr><td align="center" style="padding:36px 16px">
<table role="presentation" width="560" style="max-width:100%;background:#fffdf7;border:1px solid #b1e5e6;border-radius:20px" cellspacing="0" cellpadding="0"><tr><td style="padding:32px">
<p style="margin:0 0 28px;font-size:26px;font-weight:bold;color:#36787a">MaxBud</p>
<h1 style="font-size:24px;line-height:1.3;margin:0 0 18px">You\u2019re invited to a shared household</h1>
<p style="font-size:16px;line-height:1.7"><strong>{escape(inviter_name)}</strong> invited you to join <strong>{escape(household_name)}</strong> on MaxBud.</p>
<p style="font-size:15px;line-height:1.7">Manage shared budgets, expenses and goals together, while keeping your personal finances private.</p>
<p style="margin:28px 0"><a href="{escape(url, quote=True)}" style="display:inline-block;background:#B1E5E6;color:#174b50;text-decoration:none;padding:15px 24px;border-radius:10px;font-weight:bold">Accept your invitation</a></p>
<p style="font-size:14px;line-height:1.7">Sign in or register with <strong>{escape(email)}</strong>, then review and accept your invitation. This link expires after seven days.</p>
<p style="font-size:13px;line-height:1.7;color:#587173;border-top:1px solid #d4ded2;padding-top:20px;margin-top:26px">If you weren\u2019t expecting this invitation, you can ignore this email.</p>
</td></tr></table></td></tr></table></body></html>''', subtype='html')
    client = None
    try:
        if security == 'ssl':
            client = smtplib.SMTP_SSL(host, port, timeout=20, context=ssl.create_default_context())
        else:
            client = smtplib.SMTP(host, port, timeout=20)
        client.ehlo()
        if security == 'starttls':
            client.starttls(context=ssl.create_default_context())
            client.ehlo()
        if host == 'smtp.gmail.com':
            # LOGIN avoids an initial AUTH PLAIN response containing the whole
            # credential before Gmail has issued its authentication challenge.
            client.user = username
            client.password = password
            client.auth('LOGIN', client.auth_login, initial_response_ok=False)
        else:
            client.login(username, password)
        refused = client.send_message(message, from_addr=sender, to_addrs=[email])
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
        return message['Message-ID']
    finally:
        if client is not None:
            try:
                client.quit()
            except (OSError, smtplib.SMTPException):
                client.close()


def submission_failure(error):
    if isinstance(error, smtplib.SMTPAuthenticationError):
        return 'Invitation saved, but the mail server rejected SMTP authentication. Verify that SMTP_USERNAME is the Google account that issued the App Password and that Google still permits that credential, then resend. No email was sent.'
    if isinstance(error, smtplib.SMTPRecipientsRefused):
        return 'Invitation saved, but the mail server rejected the recipient. Check the email address. No invitation email was sent.'
    if isinstance(error, smtplib.SMTPDataError):
        return 'Invitation saved, but the mail server rejected the message. The administrator must check email delivery before resending.'
    if isinstance(error, (OSError, smtplib.SMTPException)):
        return 'Invitation saved, but email submission could not be confirmed. Check the mail service and use Resend Invitation to try again.'
    return 'Invitation saved, but email submission failed. Ask the administrator to check email delivery, then resend.'


DELIVERY_MESSAGES = {
    'submitted': 'Invitation email sent. The member can open the email and accept their invitation.',
    'not_configured': 'Email was not sent because the mail service was not configured.',
    'failed': 'Email submission failed. Check the mail settings and resend the invitation.',
    'unconfirmed': 'Email submission is not confirmed. Check with the recipient before resending.',
    'unknown': 'Email submission was not recorded for this invitation.',
}
