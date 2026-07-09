"""Root URL configuration for SPLITO."""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(_request):
    return JsonResponse({"status": "ok", "service": "splito"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health, name="health"),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/", include("apps.groups.urls")),
    path("api/", include("apps.expenses.urls")),
    path("api/", include("apps.imports.urls")),
]
