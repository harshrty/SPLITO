"""Root URL configuration for SPLITO."""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path


def health(_request):
    return JsonResponse({"status": "ok", "service": "splito"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health, name="health"),
    # app routes wired in later steps:
    # path("api/auth/", include("apps.accounts.urls")),
    # path("api/", include("apps.groups.urls")),
    # ...
]
