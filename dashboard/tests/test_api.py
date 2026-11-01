from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from dashboard.models import Share
from dashboard.tests.factories import make_share, make_snapshot

User = get_user_model()


class ShareApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="api@example.com", email="api@example.com", password="pass12345"
        )
        self.share = make_share("AAPL", price="100.50")
        self.payload = {
            "figi": "BBG000B9XRY5",
            "isin": "US0378331004",
            "name": "Company_test",
            "ticker": "TEST",
            "currency": "usd",
            "uid": "uid-test",
            "last_price": 1.5,
            "is_trend_high": False,
        }

    def test_list_is_public_and_serializes_decimal(self):
        response = self.client.get("/api/v1/shares/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["ticker"], "AAPL")
        self.assertEqual(response.data["results"][0]["uid"], "uid-AAPL")

    def test_detail_and_missing(self):
        response = self.client.get(f"/api/v1/shares/{self.share.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get("/api/v1/shares/9999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_cannot_write(self):
        response = self.client.post("/api/v1/shares/", self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        response = self.client.delete(f"/api/v1/shares/{self.share.pk}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authenticated_crud(self):
        self.client.force_authenticate(self.user)
        response = self.client.post("/api/v1/shares/", self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Share.objects.count(), 2)

        share = Share.objects.get(ticker="TEST")
        response = self.client.put(
            f"/api/v1/shares/{share.pk}/",
            {**self.payload, "name": "Renamed"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Renamed")

        response = self.client.delete(f"/api/v1/shares/{share.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_invalid_create(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/api/v1/shares/", {"figi": "only-figi"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_last_price_is_read_only(self):
        self.client.force_authenticate(self.user)
        response = self.client.patch(
            f"/api/v1/shares/{self.share.pk}/",
            {"last_price": "999"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.share.refresh_from_db()
        self.assertNotEqual(self.share.last_price, 999)


class PriceHistoryApiTests(APITestCase):
    def setUp(self):
        self.share = make_share("HIST")
        today = timezone.now()
        make_snapshot(self.share, "100", today - timedelta(days=29))
        make_snapshot(self.share, "110", today)

    def test_history_returns_points_and_stats(self):
        response = self.client.get(
            "/api/v1/price-history/", {"share": self.share.pk, "days": 30}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(len(body["points"]), 2)
        self.assertEqual(body["stats"]["count"], 2)
        self.assertAlmostEqual(float(body["stats"]["change"]), 10.0)
        self.assertAlmostEqual(float(body["stats"]["change_pct"]), 10.0)

    def test_requires_share(self):
        response = self.client.get("/api/v1/price-history/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_days(self):
        response = self.client.get(
            "/api/v1/price-history/", {"share": self.share.pk, "days": "x"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get(
            "/api/v1/price-history/", {"share": self.share.pk, "days": 99999}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_share(self):
        response = self.client.get("/api/v1/price-history/", {"share": 9999})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_non_numeric_share(self):
        response = self.client.get("/api/v1/price-history/", {"share": "abc"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
