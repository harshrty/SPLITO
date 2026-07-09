from rest_framework import serializers

from .models import ExpenseGroup, Membership, Person


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseGroup
        fields = ("id", "name", "base_currency", "created_at")
        read_only_fields = ("created_at",)


class PersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = ("id", "group", "canonical_name", "is_guest")
        read_only_fields = ("group",)


class MembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ("id", "group", "person", "joined_on", "left_on")
        read_only_fields = ("group",)

    def validate(self, attrs):
        left = attrs.get("left_on")
        joined = attrs.get("joined_on") or getattr(self.instance, "joined_on", None)
        if left and joined and left <= joined:
            raise serializers.ValidationError("left_on must be after joined_on")
        return attrs
