"""Membership temporal logic — the spine of Sam/Meera's requirements."""
from __future__ import annotations

from datetime import date

from django.db.models import Q

from .models import Membership


class MembershipService:
    def members_on(self, group_id: int, on: date) -> set[int]:
        """Person ids whose membership covers `on`.

        Active if joined_on <= on AND (left_on is null OR on <= left_on).
        left_on is the last day of membership (inclusive), so an expense dated
        after left_on excludes that person (Meera left Mar 31 -> not in Apr 2).
        """
        qs = (
            Membership.objects.filter(group_id=group_id, joined_on__lte=on)
            .filter(Q(left_on__isnull=True) | Q(left_on__gte=on))
        )
        return set(qs.values_list("person_id", flat=True))
