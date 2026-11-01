from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from dashboard.tests.factories import make_share, make_snapshot
from watchlist.models import Notification, PriceAlert, Watchlist, WatchlistItem
from watchlist.services import process_share_alerts, rearm_alert, trigger_alert

User = get_user_model()


class AlertServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alert@example.com", email="alert@example.com", password="x"
        )
        self.share = make_share("SBER", price="100")
        self.watchlist = Watchlist.objects.create(user=self.user, name="W")
        self.item = WatchlistItem.objects.create(
            watchlist=self.watchlist, share=self.share
        )
        self.alert = PriceAlert.objects.create(
            item=self.item,
            condition=PriceAlert.Condition.ABOVE,
            target_price=Decimal("100"),
        )
        self.start = timezone.now() - timedelta(days=1)

    def _snapshot(self, price, minutes):
        return make_snapshot(
            self.share, price, self.start + timedelta(minutes=minutes)
        )

    def test_triggers_once_and_rearms_after_pullback(self):
        first = self._snapshot("105", 1)
        self.assertEqual(len(process_share_alerts(self.share, first)), 1)
        self.assertEqual(len(process_share_alerts(self.share, first)), 0)

        self.alert.refresh_from_db()
        self.assertFalse(self.alert.is_active)
        self.assertEqual(self.alert.triggered_price, Decimal("105"))
        self.assertEqual(Notification.objects.count(), 1)

        # Повторная цена выше порога без возврата не создаёт новое событие.
        process_share_alerts(self.share, self._snapshot("104", 2))
        self.assertEqual(Notification.objects.count(), 1)

        # Возврат ниже порога с запасом снова взводит алерт.
        process_share_alerts(self.share, self._snapshot("90", 3))
        self.alert.refresh_from_db()
        self.assertTrue(self.alert.is_active)
        self.assertEqual(Notification.objects.count(), 1)

        process_share_alerts(self.share, self._snapshot("106", 4))
        self.assertEqual(Notification.objects.count(), 2)

    def test_below_condition(self):
        self.alert.condition = PriceAlert.Condition.BELOW
        self.alert.save(update_fields=["condition"])
        process_share_alerts(self.share, self._snapshot("90", 1))
        self.assertEqual(Notification.objects.count(), 1)
        self.assertIn("ниже", Notification.objects.first().message)

    def test_rearm_margin_is_configurable(self):
        process_share_alerts(self.share, self._snapshot("105", 1))
        self.alert.refresh_from_db()
        self.assertFalse(self.alert.is_active)
        with override_settings(PRICE_ALERT_REARM_MARGIN=0.02):
            process_share_alerts(self.share, self._snapshot("98", 2))
        self.alert.refresh_from_db()
        self.assertTrue(self.alert.is_active)

    def test_trigger_alert_is_idempotent_for_same_snapshot(self):
        snapshot = self._snapshot("105", 1)
        first = trigger_alert(self.alert, snapshot)
        second = trigger_alert(self.alert, snapshot)
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(Notification.objects.count(), 1)

    def test_manual_rearm(self):
        process_share_alerts(self.share, self._snapshot("105", 1))
        self.alert.refresh_from_db()
        rearm_alert(self.alert)
        self.alert.refresh_from_db()
        self.assertTrue(self.alert.is_active)
        self.assertIsNone(self.alert.triggered_at)

    def test_manually_disabled_alert_is_not_rearmed_automatically(self):
        self.alert.is_active = False
        self.alert.triggered_at = None
        self.alert.save(update_fields=["is_active", "triggered_at"])
        process_share_alerts(self.share, self._snapshot("90", 1))
        self.alert.refresh_from_db()
        self.assertFalse(self.alert.is_active)
        self.assertEqual(Notification.objects.count(), 0)

    @override_settings(
        ALERTS_EMAIL_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_email_notification_is_sent(self):
        process_share_alerts(self.share, self._snapshot("105", 1))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("SBER", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ["alert@example.com"])

    @override_settings(ALERTS_EMAIL_ENABLED=False)
    def test_email_is_not_sent_by_default(self):
        process_share_alerts(self.share, self._snapshot("105", 1))
        self.assertEqual(len(mail.outbox), 0)
