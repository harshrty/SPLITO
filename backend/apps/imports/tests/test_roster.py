"""Tests for auto-populating a group's roster FROM the spreadsheet (scan + apply)."""
from datetime import date
from io import StringIO

from django.test import TestCase

from apps.accounts.models import User
from apps.groups.models import ExpenseGroup, Membership, Person, PersonAlias
from apps.imports.services.roster import apply_roster, scan_names

COLUMNS = ["date", "description", "paid_by", "amount", "currency",
           "split_type", "split_with", "split_details", "notes"]


def _csv(rows):
    buf = StringIO()
    buf.write(",".join(COLUMNS) + "\n")
    for r in rows:
        buf.write(",".join(str(r.get(c, "")) for c in COLUMNS) + "\n")
    return buf.getvalue().encode("utf-8")


class RosterScanTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="h@f.com", display_name="H", password="strongpass123")
        self.group = ExpenseGroup.objects.create(name="Flat", created_by=self.user)

    def test_scan_merges_variants_and_flags_guests(self):
        rows = [
            {"date": "2026-02-05", "paid_by": "Rohan", "amount": "100", "split_with": "Aisha;Priya"},
            {"date": "2026-03-01", "paid_by": "priya", "amount": "50", "split_with": "Priya S;rohan"},
            {"date": "2026-03-10", "paid_by": "Aisha", "amount": "40", "split_with": "Dev's friend Kabir"},
        ]
        out = scan_names(_csv(rows), "in.csv", self.group)
        by_canon = {c["canonical"]: c for c in out["candidates"]}

        # Priya / priya / Priya S collapse to ONE candidate
        self.assertIn("Priya", by_canon)
        self.assertIn("Priya S", by_canon["Priya"]["variants"])
        self.assertNotIn("priya", [c["canonical"] for c in out["candidates"] if c["canonical"] != "Priya"])
        # the tag-along is suggested as a guest
        self.assertTrue(by_canon["Dev's friend Kabir"]["suggested_guest"])
        # sane default start date (earliest in-range sheet date)
        self.assertEqual(out["suggested_start_date"], "2026-02-05")

    def test_scan_flags_already_existing_people(self):
        Person.objects.create(group=self.group, canonical_name="Aisha")
        rows = [{"date": "2026-02-05", "paid_by": "Aisha", "amount": "100", "split_with": "Rohan"}]
        out = scan_names(_csv(rows), "in.csv", self.group)
        flags = {c["canonical"]: c["already_exists"] for c in out["candidates"]}
        self.assertTrue(flags["Aisha"])       # fully covered
        self.assertFalse(flags["Rohan"])      # brand new

    def test_scan_person_known_but_spelling_missing_is_not_fully_covered(self):
        # Priya exists, but the messy "Priya S" spelling was never aliased
        Person.objects.create(group=self.group, canonical_name="Priya")
        rows = [{"date": "2026-02-05", "paid_by": "Priya", "amount": "100", "split_with": "Priya S"}]
        out = scan_names(_csv(rows), "in.csv", self.group)
        priya = next(c for c in out["candidates"] if c["canonical"] == "Priya")
        self.assertTrue(priya["person_known"])       # the person exists …
        self.assertFalse(priya["already_exists"])    # … but not every spelling resolves yet

    def test_apply_backfills_missing_alias_without_duplicating_person(self):
        Person.objects.create(group=self.group, canonical_name="Priya")
        res = apply_roster(self.group, date(2026, 2, 1),
                           [{"canonical": "Priya", "is_guest": False, "aliases": ["Priya S"]}])
        self.assertEqual(res["people"], 0)            # not duplicated
        self.assertEqual(res["aliases"], 1)           # missing spelling linked
        self.assertEqual(Person.objects.filter(group=self.group).count(), 1)
        self.assertEqual(PersonAlias.objects.get(group=self.group).raw_alias, "Priya S")


class RosterApplyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="h@f.com", display_name="H", password="strongpass123")
        self.group = ExpenseGroup.objects.create(name="Flat", created_by=self.user)

    def test_apply_creates_people_memberships_and_aliases(self):
        people = [
            {"canonical": "Priya", "is_guest": False, "aliases": ["Priya", "priya", "Priya S"]},
            {"canonical": "Dev's friend Kabir", "is_guest": True, "aliases": []},
        ]
        res = apply_roster(self.group, date(2026, 2, 1), people)

        self.assertEqual(res["people"], 2)
        self.assertEqual(res["memberships"], 1)          # guest gets none
        self.assertEqual(res["aliases"], 1)               # only "Priya S" (others normalise to "priya")
        self.assertTrue(Person.objects.filter(group=self.group, canonical_name="Priya").exists())
        guest = Person.objects.get(group=self.group, canonical_name="Dev's friend Kabir")
        self.assertTrue(guest.is_guest)
        self.assertFalse(Membership.objects.filter(person=guest).exists())
        self.assertEqual(PersonAlias.objects.get(group=self.group).raw_alias, "Priya S")

    def test_apply_is_idempotent(self):
        people = [{"canonical": "Rohan", "is_guest": False, "aliases": ["rohan"]}]
        apply_roster(self.group, date(2026, 2, 1), people)
        res = apply_roster(self.group, date(2026, 2, 1), people)  # run again
        self.assertEqual(res["people"], 0)
        self.assertEqual(res["memberships"], 0)
        self.assertEqual(Person.objects.filter(group=self.group).count(), 1)
        self.assertEqual(Membership.objects.filter(group=self.group).count(), 1)


class RosterApiTests(TestCase):
    """The scan → apply → import path an end user actually walks, over HTTP."""

    def setUp(self):
        from rest_framework.test import APIClient
        self.user = User.objects.create_user(email="h@f.com", display_name="H", password="strongpass123")
        self.group = ExpenseGroup.objects.create(name="Flat", created_by=self.user)
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_scan_then_apply_populates_group(self):
        rows = [{"date": "2026-02-05", "paid_by": "Rohan", "amount": "100", "split_with": "Aisha;Priya S"}]
        from django.core.files.uploadedfile import SimpleUploadedFile
        upload = SimpleUploadedFile("in.csv", _csv(rows), content_type="text/csv")
        scan = self.api.post(f"/api/groups/{self.group.id}/import/scan-roster/", {"file": upload})
        self.assertEqual(scan.status_code, 200, scan.data)
        self.assertTrue(len(scan.data["candidates"]) >= 3)

        people = [{"canonical": c["canonical"], "is_guest": c["suggested_guest"], "aliases": c["variants"]}
                  for c in scan.data["candidates"]]
        apply = self.api.post(f"/api/groups/{self.group.id}/import/apply-roster/",
                              {"start_date": "2026-02-01", "people": people}, format="json")
        self.assertEqual(apply.status_code, 201, apply.data)
        self.assertEqual(Person.objects.filter(group=self.group).count(), 3)
