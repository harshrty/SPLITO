"""GroupContext — the read-model detectors use to reason about a staged CSV.

Built from the group's existing people, aliases and memberships (the user sets these
up before importing). Provides name resolution and temporal membership checks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from apps.groups.models import Membership, Person


def normalize_name(raw: str) -> str:
    """'  Rohan ' / 'ROHAN' -> 'rohan'; collapses internal whitespace."""
    return " ".join((raw or "").strip().lower().split())


def parse_amount(raw: str) -> Decimal | None:
    try:
        return Decimal((raw or "").strip())
    except (InvalidOperation, ValueError):
        return None


def parse_name_list(raw: str) -> list[str]:
    """'Aisha;Rohan;Priya' -> ['Aisha','Rohan','Priya'] (verbatim, unstripped tokens kept)."""
    return [tok for tok in (raw or "").split(";") if tok.strip() != ""]


def parse_detail_map(raw: str) -> dict[str, str]:
    """'Rohan 700; Priya 400' -> {'Rohan':'700','Priya':'400'};
    'Aisha 30%' keeps the % on the value. Last token of each entry is the value."""
    out: dict[str, str] = {}
    for entry in (raw or "").split(";"):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.rsplit(" ", 1)
        if len(parts) == 2:
            name, value = parts
            out[name.strip()] = value.strip()
    return out


@dataclass
class GroupContext:
    name_to_id: dict[str, int] = field(default_factory=dict)
    id_to_name: dict[int, str] = field(default_factory=dict)
    guest_ids: set[int] = field(default_factory=set)
    memberships: dict[int, list[tuple]] = field(default_factory=dict)
    min_date: date | None = None
    max_date: date | None = None
    currencies: tuple = ("INR", "USD")

    @classmethod
    def build(cls, group, today: date) -> "GroupContext":
        ctx = cls(max_date=today)
        joins = []
        for p in Person.objects.filter(group=group):
            ctx.id_to_name[p.id] = p.canonical_name
            ctx.name_to_id[normalize_name(p.canonical_name)] = p.id
            if p.is_guest:
                ctx.guest_ids.add(p.id)
        for a in group.aliases.all():
            ctx.name_to_id[normalize_name(a.raw_alias)] = a.person_id
        for m in Membership.objects.filter(group=group):
            ctx.memberships.setdefault(m.person_id, []).append((m.joined_on, m.left_on))
            joins.append(m.joined_on)
        ctx.min_date = min(joins) if joins else None
        return ctx

    def resolve(self, raw_name: str) -> int | None:
        return self.name_to_id.get(normalize_name(raw_name))

    def is_member_on(self, person_id: int, on: date) -> bool:
        for joined, left in self.memberships.get(person_id, []):
            if joined <= on and (left is None or on <= left):
                return True
        return False
