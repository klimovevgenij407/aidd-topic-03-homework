from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from dashboard.models import PriceSnapshot, Share
from monitoring.models import Notification, Watchlist, WatchlistItem
from monitoring.services import evaluate_watchlists, mark_all_read

User = get_user_model()


def make_share(**overrides):
    defaults = {
        "figi": f"FIGI{uuid.uuid4().hex[:10]}",
        "isin": f"ISIN{uuid.uuid4().hex[:10]}",
        "name": "Сбербанк",
        "ticker": f"S{uuid.uuid4().hex[:6].upper()}",
        "currency": "rub",
        "last_price": Decimal("100.00"),
    }
    defaults.update(overrides)
    return Share.objects.create(**defaults)


class WatchlistServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="watch@example.com",
            email="watch@example.com",
            password="StrongPass123!",
        )
        self.share = make_share()
        self.watchlist = Watchlist.objects.create(user=self.user, name="Мой список")
        self.item = WatchlistItem.objects.create(
            watchlist=self.watchlist,
            share=self.share,
            target_price=Decimal("105"),
            direction=WatchlistItem.Direction.ABOVE,
        )

    def snapshot(self, price, minutes=0):
        return PriceSnapshot.objects.create(
            share=self.share,
            price=Decimal(price),
            captured_at=timezone.now() + timedelta(minutes=minutes),
            source=PriceSnapshot.Source.SIMULATED,
        )

    def test_notification_is_created_once_per_condition_crossing(self):
        first = evaluate_watchlists(self.snapshot("110", 1))
        second = evaluate_watchlists(self.snapshot("111", 2))
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 0)
        self.assertEqual(Notification.objects.count(), 1)
        self.item.refresh_from_db()
        self.assertTrue(self.item.condition_met)

        evaluate_watchlists(self.snapshot("90", 3))
        self.item.refresh_from_db()
        self.assertFalse(self.item.condition_met)

        third = evaluate_watchlists(self.snapshot("120", 4))
        self.assertEqual(len(third), 1)
        self.assertEqual(Notification.objects.count(), 2)

    def test_below_direction(self):
        below = WatchlistItem.objects.create(
            watchlist=self.watchlist,
            share=make_share(ticker="GAZP"),
            target_price=Decimal("50"),
            direction=WatchlistItem.Direction.BELOW,
        )
        snapshot = PriceSnapshot.objects.create(
            share=below.share,
            price=Decimal("45"),
            captured_at=timezone.now(),
        )
        created = evaluate_watchlists(snapshot)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].watchlist_item, below)

    def test_inactive_item_does_not_notify(self):
        self.item.is_active = False
        self.item.save(update_fields=["is_active"])
        created = evaluate_watchlists(self.snapshot("110"))
        self.assertEqual(created, [])

    def test_mark_all_read(self):
        evaluate_watchlists(self.snapshot("110"))
        self.assertEqual(mark_all_read(self.user), 1)
        self.assertFalse(Notification.objects.filter(is_read=False).exists())


class WatchlistViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user@example.com",
            email="user@example.com",
            password="StrongPass123!",
        )
        self.other = User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="StrongPass123!",
        )
        self.share = make_share()
        self.watchlist = Watchlist.objects.create(user=self.user, name="Список")
        self.item = WatchlistItem.objects.create(
            watchlist=self.watchlist,
            share=self.share,
            target_price=Decimal("100"),
        )

    def test_requires_login(self):
        response = self.client.get(reverse("monitoring:watchlist_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("user:auth"), response.url)

    def test_create_sets_owner(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("monitoring:watchlist_create"),
            {"name": "Новый список"},
        )
        self.assertRedirects(
            response,
            reverse(
                "monitoring:watchlist_detail",
                args=[Watchlist.objects.get(name="Новый список").pk],
            ),
        )
        self.assertEqual(
            Watchlist.objects.get(name="Новый список").user,
            self.user,
        )

    def test_other_user_cannot_open_watchlist(self):
        self.client.force_login(self.other)
        response = self.client.get(
            reverse("monitoring:watchlist_detail", args=[self.watchlist.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_add_item_and_duplicate_validation(self):
        self.client.force_login(self.user)
        second_share = make_share(ticker="GAZP2")
        response = self.client.post(
            reverse(
                "monitoring:watchlist_item_create",
                args=[self.watchlist.pk],
            ),
            {
                "share": second_share.pk,
                "target_price": "110",
                "direction": WatchlistItem.Direction.ABOVE,
            },
        )
        self.assertRedirects(
            response,
            reverse("monitoring:watchlist_detail", args=[self.watchlist.pk]),
        )
        self.assertEqual(self.watchlist.items.count(), 2)

        response = self.client.post(
            reverse(
                "monitoring:watchlist_item_create",
                args=[self.watchlist.pk],
            ),
            {
                "share": second_share.pk,
                "target_price": "120",
                "direction": WatchlistItem.Direction.ABOVE,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "уже добавлена")

    def test_notification_read_flow(self):
        snapshot = PriceSnapshot.objects.create(
            share=self.share,
            price=Decimal("110"),
            captured_at=timezone.now(),
        )
        evaluate_watchlists(snapshot)
        notification = Notification.objects.get()
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("monitoring:notification_read", args=[notification.pk])
        )
        self.assertRedirects(response, reverse("monitoring:notification_list"))
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_notification_list_only_own(self):
        Notification.objects.create(
            user=self.other,
            watchlist_item=self.item,
            share=self.share,
            price=Decimal("100"),
            price_snapshot=PriceSnapshot.objects.create(
                share=self.share,
                price=Decimal("100"),
                captured_at=timezone.now(),
            ),
            message="Другое",
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("monitoring:notification_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Другое")


class WatchlistAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="api-watch@example.com",
            email="api-watch@example.com",
            password="StrongPass123!",
        )
        self.other = User.objects.create_user(
            username="api-other@example.com",
            email="api-other@example.com",
            password="StrongPass123!",
        )
        self.share = make_share()

    def test_requires_authentication(self):
        response = self.client.get("/api/v1/watchlists/")
        self.assertIn(response.status_code, (401, 403))

    def test_create_and_scope(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/api/v1/watchlists/",
            {"name": "API список"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        watchlist = Watchlist.objects.get(name="API список")
        self.assertEqual(watchlist.user, self.user)

        response = self.client.post(
            "/api/v1/watchlist-items/",
            {
                "watchlist": watchlist.pk,
                "share": self.share.pk,
                "target_price": "100",
                "direction": WatchlistItem.Direction.ABOVE,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        response = self.client.post(
            "/api/v1/watchlist-items/",
            {
                "watchlist": watchlist.pk,
                "share": self.share.pk,
                "target_price": "110",
                "direction": WatchlistItem.Direction.ABOVE,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

        self.client.force_authenticate(self.other)
        response = self.client.get("/api/v1/watchlists/")
        self.assertEqual(response.data["results"], [])
