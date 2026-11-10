"""E-mail delivery. Real SMTP when SMTP_HOST is set, otherwise simulated (logged, flagged as 'mock')."""
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from .config import settings

log = logging.getLogger("mailer")


class MailError(Exception):
    pass


def configured() -> bool:
    return bool(settings.smtp_host)


def status() -> dict:
    """Safe to show in the UI: never exposes the user name or the password."""
    return {"smtp": configured(), "host": settings.smtp_host, "port": settings.smtp_port,
            "from": settings.smtp_from or settings.smtp_user, "auto_send_invites": settings.auto_send_invites}


def send_email(to: str, subject: str, body: str, html: str | None = None) -> str:
    """Returns 'smtp' or 'mock'. Raises MailError with a readable message."""
    to = (to or "").strip()
    if not to or "@" not in to:
        raise MailError("Aucune adresse e-mail valide pour ce candidat.")
    if not configured():
        log.info("MOCK e-mail to=%s subject=%s", to, subject)
        return "mock"
    sender = settings.smtp_from or settings.smtp_user
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = sender, to, subject
    msg["Date"], msg["Message-ID"] = formatdate(localtime=True), make_msgid()
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")
    try:
        if settings.smtp_port == 465:
            smtp = smtplib.SMTP_SSL(settings.smtp_host, 465, timeout=20, context=ssl.create_default_context())
        else:
            smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
            if settings.smtp_tls:
                smtp.starttls(context=ssl.create_default_context())
        with smtp:
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    except Exception as e:  # noqa: BLE001
        log.warning("smtp failure to=%s: %s", to, e)
        raise MailError(f"Envoi impossible ({type(e).__name__}: {str(e)[:150]})") from e
    log.info("e-mail sent to=%s subject=%s", to, subject)
    return "smtp"
