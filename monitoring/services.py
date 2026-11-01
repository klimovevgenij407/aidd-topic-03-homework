"""Watchlist evaluation and notification delivery."""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

from dashboard.models import PriceSnapshot
from monitoring.models import Notification, WatchlistItem

logger = logging.getLogger(__name__)


def _format_direction(item: WatchlistItem) -> str:
    return (
        "выше или равна"
        if item.direction == WatchlistItem.Direction.ABOVE
        else "ниже или равна"
    )


def _send_email(notification: Notification) -> None:
    if not settings.WATCHLIST_EMAIL_NOTIFICATIONS:
        return
    try:
        send_mail(
            subject=f"Investing: {notification.share.ticker} достигла целевой цены",
            message=notification.message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[notification.user.email],
            fail_silently=True,
        )
    except Exception:
        logger.exception("Failed to send watchlist e-mail for %s", notification.pk)


def evaluate_watchlists(snapshot: PriceSnapshot) -> list[Notification]:
    """Evaluate active watchlist items for the snapshot's share.

    A notification is created only on the transition from "condition is false"
    to "condition is true". While the condition remains true, repeated price
    ticks do not create duplicates. When the condition stops holding the item is
    re-armed for the next crossing.
    """

    items = WatchlistItem.objects.select_related("watchlist", "share").filter(
        share=snapshot.share,
        is_active=True,
    )
    created_notifications: list[Notification] = []

    for item in items:
        matches = item.condition_matches(snapshot.price)
        if matches and not item.condition_met:
            with transaction.atomic():
                notification, created = Notification.objects.get_or_create(
                    watchlist_item=item,
                    price_snapshot=snapshot,
                    defaults={
                        "user_id": item.watchlist.user_id,
                        "share_id": snapshot.share_id,
                        "price": snapshot.price,
                        "message": (
                            f"{snapshot.share.ticker}: цена {snapshot.price} "
                            f"{_format_direction(item)} целевому уровню "
                            f"{item.target_price}."
                        ),
                    },
                )
                item.condition_met = True
                item.last_notified_at = snapshot.captured_at
                item.save(update_fields=["condition_met", "last_notified_at"])
            if created:
                created_notifications.append(notification)
                _send_email(notification)
        elif not matches and item.condition_met:
            item.condition_met = False
            item.save(update_fields=["condition_met"])

    return created_notifications


def mark_all_read(user) -> int:
    return user.notifications.filter(is_read=False).update(is_read=True)
