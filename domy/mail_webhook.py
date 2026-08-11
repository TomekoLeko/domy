"""Shared Make.com mail webhook delivery."""
import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)


def post_mail_webhook(receiver, subject, content, *, context_label=''):
    """
    POST JSON {receiver, subject, content} to settings.MAIL_WEBHOOK.
    Never raises — logs and returns a status dict (same shape as finance order emails).
    """
    webhook_url = (getattr(settings, 'MAIL_WEBHOOK', '') or '').strip()
    if not webhook_url:
        logger.warning(
            "MAIL_WEBHOOK is not configured; skipping email%s",
            f" ({context_label})" if context_label else "",
        )
        return {
            'provider': 'make_webhook',
            'attempted': False,
            'sent': False,
            'reason': 'webhook_not_configured',
        }

    payload = {
        'receiver': receiver,
        'subject': subject,
        'content': content,
    }

    try:
        req = Request(
            webhook_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            method='POST',
        )
        with urlopen(req, timeout=10):
            return {
                'provider': 'make_webhook',
                'attempted': True,
                'sent': True,
                'reason': None,
            }
    except (HTTPError, URLError, TimeoutError, ValueError):
        logger.exception(
            "Failed to send webhook email%s",
            f" ({context_label})" if context_label else "",
        )
        return {
            'provider': 'make_webhook',
            'attempted': True,
            'sent': False,
            'reason': 'request_failed',
        }
    except Exception:
        logger.exception(
            "Unexpected error while sending webhook email%s",
            f" ({context_label})" if context_label else "",
        )
        return {
            'provider': 'make_webhook',
            'attempted': True,
            'sent': False,
            'reason': 'unexpected_error',
        }
