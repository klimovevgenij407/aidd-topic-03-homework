from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from dashboard.models import Share
from dashboard.tests.factories import make_share, make_snapshot

User = get_user_model()


class ShareViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user@example.com", email="user@example.com", password="pass12345"
        )
        self.share = make_share("SBER", price="100.5")
        make_snapshot(self.share, "100.5", timezone.now())

    def test_list_is_public(self):
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SBER")

    def test_detail_renders_chart(self):
        response = self.client.get(reverse("dashboard:detail", args=[self.share.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "price-chart")
        self.assertContains(response, "100,50")

    def test_detail_missing_returns_404(self):
        response = self.client.get(reverse("dashboard:detail", args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_detail_rejects_unknown_period(self):
        response = self.client.get(
            reverse("dashboard:detail", args=[self.share.pk]), {"days": "abc"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["days"], 180)

    def test_legacy_urls_redirect(self):
        response = self.client.get(f"/{self.share.pk}")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, f"/shares/{self.share.pk}/")

        response = self.client.get("/userlogin/")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, "/user/login/")

    def test_create_requires_login(self):
        response = self.client.get(reverse("dashboard:create"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("user:auth"), response.url)

    def test_authenticated_crud(self):
        self.client.login(username="user@example.com", password="pass12345")
        response = self.client.post(
            reverse("dashboard:create"),
            {
                "figi": "FIGI-NEW",
                "isin": "ISIN-NEW",
                "name": "New Company",
                "ticker": "NEW",
                "currency": "rub",
                "uid": "uid-new",
            },
        )
        self.assertEqual(response.status_code, 302)
        share = Share.objects.get(ticker="NEW")

        response = self.client.post(
            reverse("dashboard:update", args=[share.pk]),
            {
                "figi": "FIGI-NEW",
                "isin": "ISIN-NEW",
                "name": "Updated Company",
                "ticker": "NEW",
                "currency": "rub",
                "uid": "uid-new",
            },
        )
        self.assertEqual(response.status_code, 302)
        share.refresh_from_db()
        self.assertEqual(share.name, "Updated Company")

        response = self.client.post(reverse("dashboard:delete", args=[share.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Share.objects.filter(pk=share.pk).exists())
