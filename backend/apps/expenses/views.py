from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.groups.models import ExpenseGroup, Person
from apps.groups.views import owned_group

from .models import Expense, Settlement
from .serializers import (ExpenseCreateSerializer, ExpenseSerializer,
                          SettlementSerializer)
from .services.balances import BalanceService


class ExpenseListCreate(generics.ListCreateAPIView):
    def get_queryset(self):
        group = owned_group(self.request.user, self.kwargs["group_id"])
        return (Expense.objects.filter(group=group)
                .prefetch_related("shares").order_by("spent_on", "id"))

    def get_serializer_class(self):
        return ExpenseCreateSerializer if self.request.method == "POST" else ExpenseSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if self.request.method == "POST":
            ctx["group"] = owned_group(self.request.user, self.kwargs["group_id"])
        return ctx


class ExpenseDetail(generics.RetrieveAPIView):
    serializer_class = ExpenseSerializer

    def get_queryset(self):
        return Expense.objects.filter(group__created_by=self.request.user).prefetch_related("shares")

    def delete(self, request, *args, **kwargs):
        """Void (soft-delete) an expense — keeps it for audit."""
        expense = self.get_object()
        expense.status = "void"
        expense.save(update_fields=["status"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class SettlementListCreate(generics.ListCreateAPIView):
    serializer_class = SettlementSerializer

    def get_queryset(self):
        group = owned_group(self.request.user, self.kwargs["group_id"])
        return Settlement.objects.filter(group=group).order_by("settled_on", "id")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if self.request.method == "POST":
            ctx["group"] = owned_group(self.request.user, self.kwargs["group_id"])
        return ctx

    def perform_create(self, serializer):
        group = owned_group(self.request.user, self.kwargs["group_id"])
        serializer.save(group=group, origin="manual")


class BalancesView(APIView):
    def get(self, request, group_id):
        owned_group(request.user, group_id)
        net = BalanceService().net_balances(group_id)
        return Response([{"person_id": pid, "net_minor": v} for pid, v in net.items()])


class SimplifiedBalancesView(APIView):
    def get(self, request, group_id):
        owned_group(request.user, group_id)
        svc = BalanceService()
        transfers = svc.simplify(svc.net_balances(group_id))
        return Response([
            {"from_person_id": t.from_person_id, "to_person_id": t.to_person_id,
             "amount_minor": t.amount_minor}
            for t in transfers
        ])


class LedgerView(APIView):
    """Rohan's itemized audit for a person."""

    def get(self, request, person_id):
        person = get_object_or_404(Person, pk=person_id, group__created_by=request.user)
        return Response(BalanceService().ledger_for(person.id))
