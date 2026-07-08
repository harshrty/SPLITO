from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import UserManager


class User(AbstractUser):
    """App login account. Logs in with email; maps to SCOPE.md `app_user`."""

    username = None  # we authenticate by email
    email = models.EmailField(unique=True, max_length=254)
    display_name = models.CharField(max_length=80)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]

    objects = UserManager()

    class Meta:
        db_table = "app_user"

    def __str__(self):
        return self.email
