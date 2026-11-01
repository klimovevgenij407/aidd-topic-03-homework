from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

from config.settings import logger
from market.models import PriceSnapshot
from watchlist.models import Notification, PriceAlert


def _margin() -> Decimal:
    return Decimal(str(getattr(settings, "PRICE_ALERT_REARM_MARGIN", 0.005)))


def maybe_rearm_alerts(share, price: Decimal) -> int:
    """Возвращает в активное состояние алерты, ушедшие от порога.

    Это защищает от повторных уведомлений при колебаниях цены у границы:
    алерт срабатывает один раз, а повторно «взводится» только после
    существенного возврата цены (PRICE_ALERT_REARM_MARGIN).
    """

    margin = _margin()
    rearms = 0
    # Алерты, выключенные вручную, не взводим автоматически: triggered_at
    # отличает срабатывание от ручного отключения.
    inactive = PriceAlert.objects.filter(
        item__share=share, is_active=False, triggered_at__isnull=False
    )
    for alert in inactive:
        if alert.condition == PriceAlert.Condition.ABOVE:
            should_rearm = price <= alert.target_price * (1 - margin)
        else:
            should_rearm = price >= alert.target_price * (1 + margin)
        if should_rearm:
            alert.is_active = True
            alert.triggered_at = None
            alert.triggered_price = None
            alert.save(
                update_fields=[
                    "is_active",
                    "triggered_at",
                    "triggered_price",
                ]
            )
            rearms += 1
    return rearms


def trigger_alert(alert: PriceAlert, snapshot: PriceSnapshot) -> Notification | None:
    """Создаёт уведомление ровно один раз на событие пересечения порога."""

    with transaction.atomic():
        alert = (
            PriceAlert.objects.select_for_update()
            .select_related("item__share", "item__watchlist__user")
            .get(pk=alert.pk)
        )
        if not alert.is_active:
            return None
        notification, created = Notification.objects.get_or_create(
            alert=alert,
            price_snapshot=snapshot,
            defaults={
                "user": alert.item.watchlist.user,
                "price": snapshot.price,
                "message": (
                    f"{alert.item.share.ticker}: {alert.get_condition_display().lower()} "
                    f"{alert.target_price} — текущая цена {snapshot.price}"
                ),
            },
        )
        if not created:
            return None
        alert.is_active = False
        alert.triggered_at = snapshot.captured_at
        alert.triggered_price = snapshot.price
        alert.save(
            update_fields=["is_active", "triggered_at", "triggered_price"]
        )

    _send_email(notification)
    return notification


def _send_email(notification: Notification) -> None:
    if not getattr(settings, "ALERTS_EMAIL_ENABLED", False):
        return
    email = notification.user.email
    if not email:
        return
    try:
        send_mail(
            subject=f"Investing: {notification.alert.item.share.ticker} — целевая цена",
            message=notification.message,
            from_email=None,
            recipient_list=[email],
            fail_silently=False,
        )
    except Exception as exc:  # noqa: BLE001 - уведомление в БД важнее письма
        logger.error("Не удалось отправить e-mail %s: %s", email, exc)


def process_share_alerts(share, snapshot: PriceSnapshot) -> list[Notification]:
    """Проверяет все активные алерты акции по новому снимку цены."""

    maybe_rearm_alerts(share, snapshot.price)
    created: list[Notification] = []
    alerts = (
        PriceAlert.objects.filter(item__share=share, is_active=True)
        .select_related("item__share", "item__watchlist__user")
    )
    for alert in alerts:
        if alert.condition_met(snapshot.price):
            notification = trigger_alert(alert, snapshot)
            if notification is not None:
                created.append(notification)
    return created


def rearm_alert(alert: PriceAlert) -> None:
    alert.is_active = True
    alert.triggered_at = None
    alert.triggered_price = None
    alert.save(update_fields=["is_active", "triggered_at", "triggered_price"])
