from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import User


class AuthFlowTests(APITestCase):
    def test_register_creates_user(self):
        resp = self.client.post(reverse("register"), {
            "email": "aisha@flat.com", "display_name": "Aisha", "password": "strongpass123",
        })
        self.assertEqual(resp.status_code, 201)
        self.assertNotIn("password", resp.data)
        self.assertTrue(User.objects.filter(email="aisha@flat.com").exists())

    def test_duplicate_email_rejected(self):
        User.objects.create_user(email="a@flat.com", display_name="A", password="strongpass123")
        resp = self.client.post(reverse("register"), {
            "email": "a@flat.com", "display_name": "A2", "password": "strongpass123",
        })
        self.assertEqual(resp.status_code, 400)

    def test_weak_password_rejected(self):
        resp = self.client.post(reverse("register"), {
            "email": "b@flat.com", "display_name": "B", "password": "123",
        })
        self.assertEqual(resp.status_code, 400)

    def test_login_returns_tokens_and_user(self):
        User.objects.create_user(email="c@flat.com", display_name="Cee", password="strongpass123")
        resp = self.client.post(reverse("login"), {
            "email": "c@flat.com", "password": "strongpass123",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)
        self.assertEqual(resp.data["user"]["display_name"], "Cee")

    def test_me_requires_auth(self):
        self.assertEqual(self.client.get(reverse("me")).status_code, 401)

    def test_me_returns_current_user(self):
        User.objects.create_user(email="d@flat.com", display_name="Dee", password="strongpass123")
        token = self.client.post(reverse("login"), {
            "email": "d@flat.com", "password": "strongpass123",
        }).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        resp = self.client.get(reverse("me"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["email"], "d@flat.com")
