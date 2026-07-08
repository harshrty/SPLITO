from django.contrib import admin

from .models import ExpenseGroup, Membership, Person, PersonAlias


@admin.register(ExpenseGroup)
class ExpenseGroupAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "base_currency", "created_at")


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("id", "canonical_name", "group", "is_guest")
    list_filter = ("is_guest", "group")


@admin.register(PersonAlias)
class PersonAliasAdmin(admin.ModelAdmin):
    list_display = ("id", "raw_alias", "person", "group")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "person", "group", "joined_on", "left_on")
    list_filter = ("group",)
