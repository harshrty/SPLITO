"""Security-hardening tests: rate limiting + revocable logout."""
from django.core.cache import cache
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.test import APITestCase

from apps.accounts import views as acc_views
from apps.accounts.models import User


class _ThreePerMin(ScopedRateThrottle):
    """Forces a 3/min cap on whatever throttle_scope the view declares (throttling is
    disabled in the general suite, so we bind this straight onto the view to test it)."""
    THROTTLE_RATES = {"login": "3/min", "register": "3/min"}


class RateLimitTests(APITestCase):
    def setUp(self):
        cache.clear()  # throttle counters live in the cache — start each test clean
        self._orig = {v: v.throttle_classes for v in (acc_views.LoginView, acc_views.RegisterView)}
        acc_views.LoginView.throttle_classes = [_ThreePerMin]
        acc_views.RegisterView.throttle_classes = [_ThreePerMin]

    def tearDown(self):
        for view, classes in self._orig.items():
            view.throttle_classes = classes
        cache.clear()

    def test_login_is_rate_limited(self):
        User.objects.create_user(email="t@f.com", display_name="T", password="strongpass123")
        codes = [
            self.client.post("/api/auth/login/", {"email": "t@f.com", "password": "wrong"}).status_code
            for _ in range(5)
        ]
        # after 3 attempts/min the brute-force is cut off with 429
        self.assertIn(429, codes, f"login was not throttled: {codes}")

    def test_register_is_rate_limited(self):
        codes = [
            self.client.post("/api/auth/register/",
                             {"email": f"u{i}@f.com", "display_name": "U", "password": "strongpass123"}).status_code
            for i in range(5)
        ]
        self.assertIn(429, codes, f"register was not throttled: {codes}")


class LogoutRevocationTests(APITestCase):
    def test_logout_blacklists_refresh_token(self):
        User.objects.create_user(email="l@f.com", display_name="L", password="strongpass123")
        login = self.client.post("/api/auth/login/", {"email": "l@f.com", "password": "strongpass123"})
        refresh, access = login.data["refresh"], login.data["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        out = self.client.post("/api/auth/logout/", {"refresh": refresh}, format="json")
        self.assertEqual(out.status_code, 205, out.data)

        # the revoked refresh token can no longer mint a fresh access token
        again = self.client.post("/api/auth/refresh/", {"refresh": refresh}, format="json")
        self.assertEqual(again.status_code, 401)

    def test_logout_requires_a_refresh_token(self):
        User.objects.create_user(email="l2@f.com", display_name="L", password="strongpass123")
        access = self.client.post("/api/auth/login/", {"email": "l2@f.com", "password": "strongpass123"}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(self.client.post("/api/auth/logout/", {}, format="json").status_code, 400)
