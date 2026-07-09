from django.urls import path

from .views import (BalancesView, ExpenseDetail, ExpenseListCreate, LedgerView,
                    SettlementListCreate, SimplifiedBalancesView)

urlpatterns = [
    path("groups/<int:group_id>/expenses/", ExpenseListCreate.as_view(), name="group-expenses"),
    path("expenses/<int:pk>/", ExpenseDetail.as_view(), name="expense-detail"),
    path("groups/<int:group_id>/settlements/", SettlementListCreate.as_view(), name="group-settlements"),
    path("groups/<int:group_id>/balances/", BalancesView.as_view(), name="group-balances"),
    path("groups/<int:group_id>/balances/simplified/", SimplifiedBalancesView.as_view(), name="group-balances-simplified"),
    path("people/<int:person_id>/ledger/", LedgerView.as_view(), name="person-ledger"),
]
