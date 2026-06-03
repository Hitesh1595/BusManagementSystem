"""
Resend transactional email wrapper.

In dev (RESEND_API_KEY empty), log the email instead of sending — never raise.
In prod, send via Resend SDK; on failure, log + continue (non-fatal per spec §17).
"""

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()


async def send_email(to: str, subject: str, html: str) -> None:
    """
    Send a transactional email via Resend.

    When RESEND_API_KEY is empty (dev/sandbox), logs the email payload instead
    of making a network call. This ensures the reset flow is exercisable locally
    without any external credentials.

    Failures in production are logged but never re-raised so a single bad email
    address or transient Resend outage does not break the caller.
    """
    if not settings.RESEND_API_KEY:
        log.info(
            "email.sandbox",
            to=to,
            subject=subject,
            note="RESEND_API_KEY not set — email not sent (dev mode)",
        )
        return

    try:
        import resend  # lazy import so tests that don't set the key never need the package

        resend.api_key = settings.RESEND_API_KEY
        resend.Emails.send(
            {
                "from": settings.EMAIL_FROM,
                "to": [to],
                "subject": subject,
                "html": html,
            }
        )
        log.info("email.sent", to=to, subject=subject)
    except Exception as exc:
        log.error("email.send_failed", to=to, subject=subject, error=str(exc))
        # Never raise — a failed email should not break the caller (spec §17).
