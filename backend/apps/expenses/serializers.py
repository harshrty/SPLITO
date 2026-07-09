from decimal import Decimal

from rest_framework import serializers

from apps.groups.models import Person

from .models import Expense, ExpenseShare, Settlement
from .services.expense_service import ExpenseService, ExpenseValidationError


class ExpenseShareSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseShare
        fields = ("id", "person", "share_input", "computed_owed_minor")


class ExpenseSerializer(serializers.ModelSerializer):
    """Read representation, including the split line-items (Rohan's audit)."""

    shares = ExpenseShareSerializer(many=True, read_only=True)

    class Meta:
        model = Expense
        fields = (
            "id", "group", "spent_on", "description", "paid_by",
            "original_amount_minor", "original_currency", "amount_base_minor",
            "fx_rate", "fx_rate_source", "split_type", "status", "notes", "shares",
        )


class ExpenseCreateSerializer(serializers.Serializer):
    spent_on = serializers.DateField()
    description = serializers.CharField(max_length=200)
    paid_by = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=3)  # allow 899.995 in, we round
    currency = serializers.ChoiceField(choices=["INR", "USD"])
    split_type = serializers.ChoiceField(choices=["equal", "unequal", "percentage", "share"])
    participants = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    details = serializers.DictField(required=False)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["split_type"] != "equal" and not attrs.get("details"):
            raise serializers.ValidationError(
                {"details": f"{attrs['split_type']} split requires per-person details"}
            )
        return attrs

    def create(self, validated):
        group = self.context["group"]
        details = validated.get("details")
        if details is not None:
            # JSON keys are strings → coerce to int person_id and Decimal value
            details = {int(k): Decimal(str(v)) for k, v in details.items()}
        try:
            return ExpenseService().create(
                group=group,
                spent_on=validated["spent_on"],
                description=validated["description"],
                paid_by_id=validated["paid_by"],
                amount=validated["amount"],
                currency=validated["currency"],
                split_type=validated["split_type"],
                participants=validated["participants"],
                details=details,
                notes=validated.get("notes"),
            )
        except ExpenseValidationError as exc:
            raise serializers.ValidationError({"detail": str(exc)})

    def to_representation(self, instance):
        return ExpenseSerializer(instance).data


class SettlementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Settlement
        fields = ("id", "group", "from_person", "to_person", "amount_minor",
                  "settled_on", "note", "origin")
        read_only_fields = ("group", "origin")

    def validate(self, attrs):
        if attrs["from_person"] == attrs["to_person"]:
            raise serializers.ValidationError("from_person and to_person must differ")
        if attrs["amount_minor"] <= 0:
            raise serializers.ValidationError("amount_minor must be positive")
        return attrs
