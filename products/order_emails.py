"""Order-related notification emails (Make.com webhook)."""
import logging

from django.conf import settings

from domy.mail_webhook import post_mail_webhook
from products.models import Order

logger = logging.getLogger(__name__)


def _format_polish_order_date_nominative(dt):
    """e.g. 'wtorek 11 sierpnia 2026' (nominative weekday for standalone date lines)."""
    if not dt:
        return ""

    weekday_names = [
        "poniedziałek",
        "wtorek",
        "środa",
        "czwartek",
        "piątek",
        "sobota",
        "niedziela",
    ]
    month_names = [
        "stycznia",
        "lutego",
        "marca",
        "kwietnia",
        "maja",
        "czerwca",
        "lipca",
        "sierpnia",
        "września",
        "października",
        "listopada",
        "grudnia",
    ]

    return f"{weekday_names[dt.weekday()]} {dt.day} {month_names[dt.month - 1]} {dt.year}"


def _buyer_display_name(buyer):
    if buyer is None:
        return ""
    name = buyer.get_organization_name_or_full_name() or buyer.username or ""
    email = (buyer.email or "").strip()
    if email:
        return f"{name} ({email})" if name else f"({email})"
    return name


def send_admin_new_order_email(order_id):
    """
    Notify admin that a new order was placed.
    Safe to call from transaction.on_commit — never raises to the caller path.
    """
    receiver = (getattr(settings, 'ADMIN_ORDER_EMAIL', '') or '').strip() or 'ays@vp.pl'

    try:
        order = (
            Order.objects
            .filter(id=order_id)
            .select_related('buyer')
            .first()
        )
        if order is None:
            logger.warning("Admin order email skipped: order_id=%s not found", order_id)
            return {
                'provider': 'make_webhook',
                'attempted': False,
                'sent': False,
                'reason': 'order_not_found',
            }

        order_label = order.order_number or str(order.id)
        subject = f"Nowe zamówienie {order_label}"
        order_date_display = _format_polish_order_date_nominative(order.created_at)
        buyer_display = _buyer_display_name(order.buyer)
        amount_display = f"{order.total_cost:.2f}".replace('.', ',')

        message = (
            '<div style="font-family:Arial,Helvetica,sans-serif;color:#1f2937;line-height:1.6;">'
            "<p style=\"margin:0 0 12px 0;\">Hej,</p>"
            "<p style=\"margin:0 0 12px 0;\">W systemie pojawiło się nowe zamówienie.</p>"
            f"<p style=\"margin:0 0 8px 0;\">Numer: <strong>{order_label}</strong></p>"
            f"<p style=\"margin:0 0 8px 0;\">Data: {order_date_display}</p>"
            f"<p style=\"margin:0 0 8px 0;\">Kupujący: {buyer_display}</p>"
            f"<p style=\"margin:0 0 16px 0;\">Wartość: <strong>{amount_display} zł</strong></p>"
            "<hr style=\"border:none;border-top:1px solid #e5e7eb;margin:20px 0 14px 0;\">"
            "<div style=\"text-align:center;color:#6b7280;font-size:13px;\">"
            "<div style=\"font-weight:600;color:#374151;\">Domy</div>"
            "<div>System zamówień i rozliczeń</div>"
            "</div>"
            "</div>"
        )

        return post_mail_webhook(
            receiver,
            subject,
            message,
            context_label=f"admin new order order_id={order.id}",
        )
    except Exception:
        logger.exception(
            "Unexpected error while preparing admin new-order email for order_id=%s",
            order_id,
        )
        return {
            'provider': 'make_webhook',
            'attempted': False,
            'sent': False,
            'reason': 'unexpected_error',
        }
