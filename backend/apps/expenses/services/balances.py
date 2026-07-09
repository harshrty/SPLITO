"""BalanceService — net balances (from the person_balance view) and debt simplification.

- net_balances: reads the derived view (balances are never stored).
- simplify: greedy min-cash-flow. The optimal problem is NP-hard (SCOPE.md references),
  so this is a documented heuristic, not a provable minimum.
- ledger_for: Rohan's itemized audit — every active share a person owes.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.db import connection

from apps.expenses.models import ExpenseShare


@dataclass(frozen=True)
class Transfer:
    from_person_id: int
    to_person_id: int
    amount_minor: int


class BalanceService:
    def net_balances(self, group_id: int) -> dict[int, int]:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT person_id, net_minor FROM person_balance WHERE group_id = %s",
                [group_id],
            )
            return {pid: int(net) for pid, net in cur.fetchall()}

    def simplify(self, net: dict[int, int]) -> list[Transfer]:
        """Greedy: repeatedly match the biggest debtor to the biggest creditor."""
        creditors = sorted(([p, a] for p, a in net.items() if a > 0), key=lambda x: -x[1])
        debtors = sorted(([p, -a] for p, a in net.items() if a < 0), key=lambda x: -x[1])

        transfers: list[Transfer] = []
        i = j = 0
        while i < len(debtors) and j < len(creditors):
            pay = min(debtors[i][1], creditors[j][1])
            transfers.append(Transfer(debtors[i][0], creditors[j][0], pay))
            debtors[i][1] -= pay
            creditors[j][1] -= pay
            if debtors[i][1] == 0:
                i += 1
            if creditors[j][1] == 0:
                j += 1
        return transfers

    def ledger_for(self, person_id: int) -> list[dict]:
        """Itemized audit: each active expense this person owes a share of."""
        rows = (
            ExpenseShare.objects.filter(person_id=person_id, expense__status="active")
            .select_related("expense")
            .order_by("expense__spent_on")
        )
        out = []
        for s in rows:
            e = s.expense
            out.append({
                "expense_id": e.id,
                "date": e.spent_on,
                "description": e.description,
                "split_type": e.split_type,
                "owed_minor": s.computed_owed_minor,
                "paid_by_me": e.paid_by_id == person_id,
            })
        return out
