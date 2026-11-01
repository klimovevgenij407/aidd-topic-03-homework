from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class RegistrationTests(TestCase):
    def test_get_registration_page(self):
        response = self.client.get(reverse("user:registration"))
        self.assertEqual(response.status_code, 200)

    def test_successful_registration_normalizes_email(self):
        response = self.client.post(
            reverse("user:registration"),
            {
                "email": "  USER@Example.COM ",
                "password1": "Str0ngPass!2026",
                "password2": "Str0ngPass!2026",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get()
        self.assertEqual(user.username, "user@example.com")
        self.assertEqual(user.email, "user@example.com")
        self.assertEqual(response.wsgi_request.user, user)

    def test_duplicate_email_is_case_insensitive(self):
        User.objects.create_user(
            username="dup@example.com", email="dup@example.com", password="x"
        )
        response = self.client.post(
            reverse("user:registration"),
            {
                "email": "DUP@example.com",
                "password1": "Str0ngPass!2026",
                "password2": "Str0ngPass!2026",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "уже зарегистрирован")
        self.assertEqual(User.objects.count(), 1)

    def test_password_mismatch(self):
        response = self.client.post(
            reverse("user:registration"),
            {
                "email": "new@example.com",
                "password1": "Str0ngPass!2026",
                "password2": "Different!2026",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "не совпадают")
        self.assertEqual(User.objects.count(), 0)

    def test_weak_password_rejected(self):
        response = self.client.post(
            reverse("user:registration"),
            {
                "email": "new@example.com",
                "password1": "12345678",
                "password2": "12345678",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 0)

    def test_invalid_or_missing_fields_do_not_crash(self):
        response = self.client.post(
            reverse("user:registration"), {"email": "not-an-email"}
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse("user:registration"), {})
        self.assertEqual(response.status_code, 200)


class AuthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="auth@example.com",
            email="auth@example.com",
            password="Str0ngPass!2026",
        )

    def test_get_login_page(self):
        response = self.client.get(reverse("user:auth"))
        self.assertEqual(response.status_code, 200)

    def test_login_is_case_insensitive(self):
        response = self.client.post(
            reverse("user:auth"),
            {"email": "AUTH@example.com", "password": "Str0ngPass!2026"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_wrong_password_shows_error(self):
        response = self.client.post(
            reverse("user:auth"),
            {"email": "auth@example.com", "password": "wrong"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Неверный логин или пароль")

    def test_missing_fields_do_not_crash(self):
        response = self.client.post(reverse("user:auth"), {})
        self.assertEqual(response.status_code, 200)

    def test_logout(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("user:logout"))
        self.assertEqual(response.status_code, 302)
        response = self.client.get(reverse("dashboard:index"))
        self.assertFalse(response.wsgi_request.user.is_authenticated)
