"""SplitEngine — turns an expense amount into per-person shares in integer paise.

Design (SCOPE.md / DECISIONS.md D5):
- All money is integer minor units (paise). No floats, ever.
- INVARIANT: the returned shares always sum EXACTLY to `amount_minor`.
- Remainder rule: when a total does not divide evenly, the leftover paise are given
  to the first R participants ordered by ascending person_id (deterministic, testable,
  explainable — we deliberately diverge from Splitwise's random assignment).

`equal`, `share`, and `percentage` are all "proportional" splits (equal == everyone
weight 1). `unequal` is the only absolute split. Exact rational arithmetic (Fraction)
guarantees the floor step never drifts.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

MINOR_UNITS = 100  # INR has 2 decimal places → 1 rupee = 100 paise


class SplitError(ValueError):
    """Raised when a split is internally inconsistent (bad math / missing data)."""


@dataclass(frozen=True)
class ShareLine:
    person_id: int
    share_input: Decimal | None      # raw per-person input to persist; None for equal
    computed_owed_minor: int         # final paise this person owes


def compute(
    amount_minor: int,
    split_type: str,
    participants: list[int],
    details: dict[int, Decimal | int | float | str] | None = None,
) -> list[ShareLine]:
    """Return one ShareLine per participant. Sum(computed_owed_minor) == amount_minor."""
    if not participants:
        raise SplitError("at least one participant is required")
    ids = sorted(participants)
    if len(set(ids)) != len(ids):
        raise SplitError("duplicate participants")

    if split_type == "equal":
        weights = {pid: Fraction(1) for pid in ids}
        return _proportional(amount_minor, ids, weights, store_input=None)

    if details is None:
        raise SplitError(f"'{split_type}' split requires per-person details")
    if set(details) != set(ids):
        raise SplitError("details must be provided for exactly the participants")

    if split_type == "percentage":
        pcts = {pid: Decimal(str(details[pid])) for pid in ids}
        total = sum(pcts.values())
        if total != Decimal(100):
            raise SplitError(f"percentages must total 100, got {total}")
        weights = {pid: Fraction(pcts[pid]) for pid in ids}
        return _proportional(amount_minor, ids, weights, store_input=pcts)

    if split_type == "share":
        w = {pid: Decimal(str(details[pid])) for pid in ids}
        if any(v < 0 for v in w.values()):
            raise SplitError("share weights must be non-negative")
        if sum(w.values()) <= 0:
            raise SplitError("total share weight must be positive")
        weights = {pid: Fraction(w[pid]) for pid in ids}
        return _proportional(amount_minor, ids, weights, store_input=w)

    if split_type == "unequal":
        majors = {pid: Decimal(str(details[pid])) for pid in ids}
        minors = {pid: _to_minor(majors[pid]) for pid in ids}
        got = sum(minors.values())
        if got != amount_minor:
            raise SplitError(f"unequal shares sum to {got} paise, expected {amount_minor}")
        return [ShareLine(pid, majors[pid], minors[pid]) for pid in ids]

    raise SplitError(f"unknown split_type: {split_type!r}")


def _to_minor(major: Decimal) -> int:
    """Convert a major-unit amount (₹700) to paise, rejecting sub-paisa precision."""
    scaled = major * MINOR_UNITS
    if scaled != scaled.to_integral_value():
        raise SplitError(f"amount {major} has sub-paisa precision")
    return int(scaled)


def _proportional(
    amount_minor: int,
    ids: list[int],
    weights: dict[int, Fraction],
    store_input: dict[int, Decimal] | None,
) -> list[ShareLine]:
    """Split `amount_minor` by weights, flooring each share then distributing the
    leftover paise to the first R participants by ascending id."""
    total_w = sum(weights.values())
    floors = {pid: math.floor(Fraction(amount_minor) * weights[pid] / total_w) for pid in ids}
    remainder = amount_minor - sum(floors.values())  # always in [0, len(ids))

    result: list[ShareLine] = []
    for i, pid in enumerate(ids):
        owed = floors[pid] + (1 if i < remainder else 0)
        share_input = None if store_input is None else store_input[pid]
        result.append(ShareLine(pid, share_input, owed))
    return result


class SplitEngine:
    """Class facade matching the LLD contract."""

    compute = staticmethod(compute)
