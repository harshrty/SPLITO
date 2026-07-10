from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (AliasDelete, AliasListCreate, GroupViewSet,
                    MembershipDetail, MembershipListCreate, PersonListCreate)

router = SimpleRouter()
router.register("groups", GroupViewSet, basename="group")

urlpatterns = router.urls + [
    path("groups/<int:group_id>/people/", PersonListCreate.as_view(), name="group-people"),
    path("groups/<int:group_id>/memberships/", MembershipListCreate.as_view(), name="group-memberships"),
    path("memberships/<int:pk>/", MembershipDetail.as_view(), name="membership-detail"),
    path("groups/<int:group_id>/aliases/", AliasListCreate.as_view(), name="group-aliases"),
    path("aliases/<int:pk>/", AliasDelete.as_view(), name="alias-detail"),
]
