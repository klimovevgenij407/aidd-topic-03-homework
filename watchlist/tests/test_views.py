from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from dashboard.tests.factories import make_share
from watchlist.models import Notification, PriceAlert, Watchlist, WatchlistItem

User = get_user_model()


class WatchlistViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="w@example.com", email="w@example.com", password="pass12345"
        )
        self.share = make_share("SBER", price="100")
        self.client.login(username="w@example.com", password="pass12345")

    def test_pages_require_login(self):
        self.client.logout()
        for url in ("/watchlists/", "/notifications/"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)

    def test_create_watchlist_and_item_and_alert(self):
        response = self.client.post(reverse("watchlist:index"), {"name": "Мой"})
        self.assertEqual(response.status_code, 302)
        watchlist = Watchlist.objects.get(user=self.user)
        self.assertEqual(watchlist.name, "Мой")

        response = self.client.post(
            reverse("watchlist:detail", args=[watchlist.pk]),
            {"share": self.share.pk, "note": "наблюдаю"},
        )
        self.assertEqual(response.status_code, 302)
        item = WatchlistItem.objects.get(watchlist=watchlist)
        self.assertEqual(item.note, "наблюдаю")

        response = self.client.post(
            reverse("watchlist:alert-create", args=[item.pk]),
            {"condition": "above", "target_price": "120"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(item.alerts.count(), 1)

    def test_duplicate_item_is_rejected(self):
        watchlist = Watchlist.objects.create(user=self.user, name="W")
        WatchlistItem.objects.create(watchlist=watchlist, share=self.share)
        response = self.client.post(
            reverse("watchlist:detail", args=[watchlist.pk]),
            {"share": self.share.pk, "note": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "уже есть")
        self.assertEqual(WatchlistItem.objects.count(), 1)

    def test_invalid_alert_target_is_rejected(self):
        watchlist = Watchlist.objects.create(user=self.user, name="W")
        item = WatchlistItem.objects.create(watchlist=watchlist, share=self.share)
        response = self.client.post(
            reverse("watchlist:alert-create", args=[item.pk]),
            {"condition": "above", "target_price": "-5"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(item.alerts.count(), 0)

    def test_alert_toggle_and_notifications(self):
        watchlist = Watchlist.objects.create(user=self.user, name="W")
        item = WatchlistItem.objects.create(watchlist=watchlist, share=self.share)
        alert = PriceAlert.objects.create(
            item=item,
            condition=PriceAlert.Condition.ABOVE,
            target_price=Decimal("120"),
        )
        response = self.client.post(
            reverse("watchlist:alert-toggle", args=[alert.pk])
        )
        self.assertEqual(response.status_code, 302)
        alert.refresh_from_db()
        self.assertFalse(alert.is_active)

        notification = Notification.objects.create(
            user=self.user,
            alert=alert,
            price=Decimal("121"),
            message="test",
        )
        response = self.client.post(reverse("watchlist:notifications"))
        self.assertEqual(response.status_code, 302)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_other_user_cannot_open_watchlist(self):
        other = User.objects.create_user(
            username="other@example.com", email="other@example.com", password="x"
        )
        watchlist = Watchlist.objects.create(user=other, name="secret")
        response = self.client.get(reverse("watchlist:detail", args=[watchlist.pk]))
        self.assertEqual(response.status_code, 404)
