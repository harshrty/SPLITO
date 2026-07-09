from django.shortcuts import get_object_or_404
from rest_framework import generics, viewsets

from .models import ExpenseGroup, Membership, Person
from .serializers import GroupSerializer, MembershipSerializer, PersonSerializer


def owned_group(user, group_id):
    """Fetch a group the requesting user owns, else 404."""
    return get_object_or_404(ExpenseGroup, pk=group_id, created_by=user)


class GroupViewSet(viewsets.ModelViewSet):
    serializer_class = GroupSerializer

    def get_queryset(self):
        return ExpenseGroup.objects.filter(created_by=self.request.user).order_by("id")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class PersonListCreate(generics.ListCreateAPIView):
    serializer_class = PersonSerializer

    def get_queryset(self):
        group = owned_group(self.request.user, self.kwargs["group_id"])
        return Person.objects.filter(group=group).order_by("id")

    def perform_create(self, serializer):
        group = owned_group(self.request.user, self.kwargs["group_id"])
        serializer.save(group=group)


class MembershipListCreate(generics.ListCreateAPIView):
    serializer_class = MembershipSerializer

    def get_queryset(self):
        group = owned_group(self.request.user, self.kwargs["group_id"])
        return Membership.objects.filter(group=group).order_by("id")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if self.request.method == "POST":
            ctx["group"] = owned_group(self.request.user, self.kwargs["group_id"])
        return ctx

    def perform_create(self, serializer):
        group = owned_group(self.request.user, self.kwargs["group_id"])
        serializer.save(group=group)


class MembershipDetail(generics.RetrieveUpdateAPIView):
    """Update left_on when a member moves out."""

    serializer_class = MembershipSerializer

    def get_queryset(self):
        return Membership.objects.filter(group__created_by=self.request.user)
