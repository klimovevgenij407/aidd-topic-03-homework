from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from dashboard.tests.factories import make_share
from watchlist.models import Notification, PriceAlert, Watchlist, WatchlistItem

User = get_user_model()


class WatchlistApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="api@example.com", email="api@example.com", password="x"
        )
        self.other = User.objects.create_user(
            username="other@example.com", email="other@example.com", password="x"
        )
        self.share = make_share("SBER")
        self.client.force_authenticate(self.user)

    def test_create_watchlist_is_scoped_to_user(self):
        response = self.client.post("/api/v1/watchlists/", {"name": "Мой"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        watchlist = Watchlist.objects.get(pk=response.data["id"])
        self.assertEqual(watchlist.user, self.user)

    def test_cannot_add_item_to_foreign_watchlist(self):
        foreign = Watchlist.objects.create(user=self.other, name="secret")
        response = self.client.post(
            "/api/v1/watchlist-items/",
            {"watchlist": foreign.pk, "share": self.share.pk, "note": ""},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_does_not_leak_other_users_data(self):
        Watchlist.objects.create(user=self.other, name="secret")
        Watchlist.objects.create(user=self.user, name="mine")
        response = self.client.get("/api/v1/watchlists/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [item["name"] for item in response.data["results"]]
        self.assertEqual(names, ["mine"])

    def test_alert_creation_and_rearm(self):
        watchlist = Watchlist.objects.create(user=self.user, name="W")
        item = WatchlistItem.objects.create(watchlist=watchlist, share=self.share)
        response = self.client.post(
            "/api/v1/price-alerts/",
            {
                "item": item.pk,
                "condition": "above",
                "target_price": "120.5",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        alert = PriceAlert.objects.get(pk=response.data["id"])
        alert.is_active = False
        alert.save(update_fields=["is_active"])

        response = self.client.post(f"/api/v1/price-alerts/{alert.pk}/rearm/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        alert.refresh_from_db()
        self.assertTrue(alert.is_active)

    def test_negative_alert_target_rejected(self):
        watchlist = Watchlist.objects.create(user=self.user, name="W")
        item = WatchlistItem.objects.create(watchlist=watchlist, share=self.share)
        response = self.client.post(
            "/api/v1/price-alerts/",
            {"item": item.pk, "condition": "above", "target_price": "-1"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_notifications_are_user_scoped(self):
        watchlist = Watchlist.objects.create(user=self.user, name="W")
        item = WatchlistItem.objects.create(watchlist=watchlist, share=self.share)
        alert = PriceAlert.objects.create(
            item=item,
            condition=PriceAlert.Condition.ABOVE,
            target_price=Decimal("120"),
        )
        Notification.objects.create(
            user=self.user, alert=alert, price=Decimal("121"), message="mine"
        )
        Notification.objects.create(
            user=self.other, alert=alert, price=Decimal("121"), message="other"
        )
        response = self.client.get("/api/v1/notifications/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["message"], "mine")
