"""Roster scanning — propose a group's people FROM the spreadsheet, before import.

The sheet carries names but not the identity decisions a correct roster needs:
canonical spelling, guest-vs-member, and join dates. So we *propose* (scan_names)
and let the user confirm, then create (apply_roster). This keeps name_alias /
ex_member / non_member meaningful instead of blindly trusting the messy sheet
(which would turn 'Priya', 'priya' and 'Priya S' into three different people).
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from apps.groups.models import Membership, Person, PersonAlias

from .context import normalize_name, parse_name_list
from .parser import parse

# names that read like a one-off tag-along rather than a housemate
GUEST_HINTS = ("friend", "guest", "+1", "'s ", "’s ")


def _safe_date(s: str) -> date | None:
    try:
        return date.fromisoformat((s or "").strip()[:10])
    except ValueError:
        return None


def _merge_key(norm: str) -> str:
    """Drop trailing single-letter initials so 'priya s' groups with 'priya'."""
    toks = norm.split()
    while len(toks) > 1 and len(toks[-1]) == 1:
        toks.pop()
    return " ".join(toks)


def _pick_canonical(variants: list[str], key: str) -> str:
    """Nicest raw spelling for a merged group: prefer the base form (no trailing
    initial, i.e. normalises to the merge key), then a proper-cased, frequent, short one."""
    counts = Counter(v.strip() for v in variants if v.strip())
    return max(counts, key=lambda v: (
        normalize_name(v) == key,   # base form ('Priya') over 'Priya S'
        counts[v],                  # most frequent spelling
        v != v.lower(),             # proper-cased ('Rohan') over 'rohan'
        -len(v.split()),            # fewer words
        -len(v),                    # shorter
    ))


def scan_names(file_bytes: bytes, filename: str, group) -> dict:
    """Parse the sheet and propose a roster. Persists nothing."""
    rows = parse(file_bytes, filename)

    raw_occ: list[str] = []
    dates: list[date] = []
    for r in rows:
        raw = r["raw"]
        payer = (raw.get("paid_by") or "").strip()
        if payer:
            raw_occ.append(payer)
        raw_occ.extend(parse_name_list(raw.get("split_with", "")))
        d = _safe_date(raw.get("date", ""))
        if d:
            dates.append(d)

    # existing roster (canonical names + aliases) so we can flag already-known names
    person_norm = {normalize_name(p.canonical_name) for p in Person.objects.filter(group=group)}
    existing_norm = person_norm | {normalize_name(a.raw_alias) for a in PersonAlias.objects.filter(group=group)}

    # group raw spellings by merge key (case/space/initials collapsed)
    buckets: dict[str, list[str]] = {}
    for raw in raw_occ:
        norm = normalize_name(raw)
        if norm:
            buckets.setdefault(_merge_key(norm), []).append(raw.strip())

    candidates = []
    for key, variants in buckets.items():
        canonical = _pick_canonical(variants, key)
        distinct = sorted({v for v in variants if v})
        norms = {normalize_name(v) for v in distinct} | {key}
        candidates.append({
            "canonical": canonical,
            "variants": distinct,
            "suggested_guest": any(h in key for h in GUEST_HINTS) or len(key.split()) > 2,
            "occurrences": len(variants),
            # the person already exists (by name or an alias) …
            "person_known": bool(norms & person_norm) or bool(norms & existing_norm),
            # … AND every spelling in the file already resolves — nothing to do
            "already_exists": norms <= existing_norm,
        })
    candidates.sort(key=lambda c: (-c["occurrences"], c["canonical"].lower()))

    # smart default join date: earliest sheet date within ~3y of the latest (skip outliers)
    suggested_start = None
    if dates:
        anchor = max(dates)
        sane = [d for d in dates if d >= anchor - timedelta(days=365 * 3)]
        suggested_start = (min(sane) if sane else min(dates)).isoformat()

    return {
        "existing_people": sorted(normalize_name(p.canonical_name)
                                  for p in Person.objects.filter(group=group)),
        "suggested_start_date": suggested_start,
        "candidates": candidates,
    }


def apply_roster(group, start_date: date, people: list[dict]) -> dict:
    """Create the confirmed people, memberships (non-guests) and aliases. Idempotent:
    re-running skips names/aliases that already exist."""
    result = {"people": 0, "memberships": 0, "aliases": 0}
    by_norm = {normalize_name(p.canonical_name): p for p in Person.objects.filter(group=group)}
    alias_norm = {normalize_name(a.raw_alias) for a in PersonAlias.objects.filter(group=group)}

    for entry in people:
        name = (entry.get("canonical") or "").strip()
        if not name:
            continue
        norm = normalize_name(name)
        is_guest = bool(entry.get("is_guest"))

        person = by_norm.get(norm)
        if person is None:
            person = Person.objects.create(group=group, canonical_name=name, is_guest=is_guest)
            by_norm[norm] = person
            result["people"] += 1

        if not is_guest and not Membership.objects.filter(group=group, person=person).exists():
            Membership.objects.create(group=group, person=person, joined_on=start_date)
            result["memberships"] += 1

        # only variant spellings that DON'T already resolve become aliases
        for raw in entry.get("aliases", []):
            an = normalize_name(raw)
            if not an or an == norm or an in alias_norm or an in by_norm:
                continue
            PersonAlias.objects.create(group=group, person=person, raw_alias=raw.strip())
            alias_norm.add(an)
            result["aliases"] += 1

    return result
