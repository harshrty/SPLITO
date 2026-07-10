from django.db.models.functions import Lower, Trim
from rest_framework import serializers

from .models import ExpenseGroup, Membership, Person, PersonAlias


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


class PersonAliasSerializer(serializers.ModelSerializer):
    """Maps a messy spreadsheet name ('Priya S', 'rohan ') to a canonical Person."""

    class Meta:
        model = PersonAlias
        fields = ("id", "group", "person", "raw_alias")
        read_only_fields = ("group",)

    def validate(self, attrs):
        group = self.context.get("group") or getattr(self.instance, "group", None)
        person = attrs.get("person") or getattr(self.instance, "person", None)
        if group is not None and person is not None and person.group_id != group.id:
            raise serializers.ValidationError({"person": "person is not a member of this group"})
        # return a friendly 400 instead of a DB IntegrityError on the case/space-insensitive
        # uniqueness constraint (uq_alias_norm).
        raw = (attrs.get("raw_alias") or "").strip().lower()
        if group is not None and raw:
            clash = (PersonAlias.objects
                     .annotate(norm=Lower(Trim("raw_alias")))
                     .filter(group=group, norm=raw))
            if self.instance is not None:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise serializers.ValidationError({"raw_alias": "this alias already exists in the group"})
        return attrs


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
        # the person must belong to the group the membership is under (guards create
        # and any re-pointing of `person` on update to a person in another group).
        group = self.context.get("group") or getattr(self.instance, "group", None)
        person = attrs.get("person") or getattr(self.instance, "person", None)
        if group is not None and person is not None and person.group_id != group.id:
            raise serializers.ValidationError({"person": "person is not a member of this group"})
        return attrs
