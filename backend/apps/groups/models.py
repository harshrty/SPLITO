"""Identity & membership models — maps SCOPE.md Layer A."""
from django.conf import settings
from django.db import models
from django.db.models.functions import Lower, Trim


class ExpenseGroup(models.Model):
    name = models.CharField(max_length=100)
    base_currency = models.CharField(max_length=3, default="INR")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="groups_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "expense_group"
        constraints = [
            models.CheckConstraint(
                check=models.Q(base_currency__in=["INR", "USD"]),
                name="group_base_currency_valid",
            ),
        ]

    def __str__(self):
        return self.name


class Person(models.Model):
    """A balance-bearing participant. NOT the same as a login (User)."""

    group = models.ForeignKey(ExpenseGroup, on_delete=models.CASCADE, related_name="people")
    canonical_name = models.CharField(max_length=80)
    is_guest = models.BooleanField(default=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="persons",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "person"
        constraints = [
            models.UniqueConstraint(fields=["group", "canonical_name"], name="uq_person_group_name"),
        ]

    def __str__(self):
        return self.canonical_name


class PersonAlias(models.Model):
    """Maps messy CSV names (priya / Priya S / rohan ) to one Person."""

    group = models.ForeignKey(ExpenseGroup, on_delete=models.CASCADE, related_name="aliases")
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="aliases")
    raw_alias = models.CharField(max_length=120)

    class Meta:
        db_table = "person_alias"
        constraints = [
            # one alias resolves to one person per group, case/space-insensitive
            models.UniqueConstraint(
                Lower(Trim("raw_alias")), models.F("group"), name="uq_alias_norm",
            ),
        ]

    def __str__(self):
        return f"{self.raw_alias} -> {self.person_id}"


class Membership(models.Model):
    """Time-bounded stay. Answers 'was X a member on date D?'."""

    group = models.ForeignKey(ExpenseGroup, on_delete=models.CASCADE, related_name="memberships")
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="memberships")
    joined_on = models.DateField()
    left_on = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "membership"
        indexes = [models.Index(fields=["group", "person"], name="ix_membership_lookup")]
        constraints = [
            models.CheckConstraint(
                check=models.Q(left_on__isnull=True) | models.Q(left_on__gt=models.F("joined_on")),
                name="membership_left_after_join",
            ),
        ]

    def __str__(self):
        return f"{self.person_id} [{self.joined_on}..{self.left_on or 'active'}]"
