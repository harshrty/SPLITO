"""Django settings for SPLITO backend."""
import os
import sys
from datetime import timedelta
from pathlib import Path

# Throttling is disabled under the test runner so the suite isn't rate-limited;
# a dedicated test re-enables it via override_settings to prove it works.
TESTING = "test" in sys.argv

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Secure-by-default: DEBUG is off unless explicitly enabled, and a production boot
# (DEBUG off) refuses to start on the throwaway dev key so we never fail open.
_DEV_INSECURE_KEY = "dev-insecure-key-do-not-use-in-production-0123456789abcdef"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", _DEV_INSECURE_KEY)
DEBUG = os.getenv("DJANGO_DEBUG", "False") == "True"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

if not DEBUG and SECRET_KEY == _DEV_INSECURE_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set to a real secret when DEBUG is off"
    )

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    # local apps
    "apps.accounts",
    "apps.groups",
    "apps.expenses",
    "apps.imports",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Local Postgres by default; override with DATABASE_URL in production.
DATABASES = {
    "default": dj_database_url.parse(
        os.getenv("DATABASE_URL", "postgres://splito:splito@localhost:5432/splito"),
        conn_max_age=600,
    )
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
}

# Rate limiting: protects the unauthenticated auth endpoints from brute-force /
# enumeration / spam, and caps authenticated abuse. Disabled under the test runner.
if not TESTING:
    REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    )
    REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
        "anon": "30/min",
        "user": "2000/hour",
        "login": "5/min",       # credential brute-force
        "register": "5/min",    # account spam / enumeration
        "imports": "30/hour",   # file-upload abuse
    }

SIMPLE_JWT = {
    # Short-lived access token limits the blast radius of a leaked/localStorage-stolen
    # token; refresh tokens rotate and the old one is blacklisted so logout can revoke.
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

CORS_ALLOWED_ORIGINS = os.getenv(
    "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Production hardening (enabled when DEBUG is off)
CSRF_TRUSTED_ORIGINS = [
    o for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o
]
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # force HTTPS + HSTS so a bearer token can't be captured over a downgraded
    # (SSL-strip) connection
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
