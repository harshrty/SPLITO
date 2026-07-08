from django.contrib import admin

from .models import Expense, ExpenseShare, FxRate, Settlement


class ExpenseShareInline(admin.TabularInline):
    model = ExpenseShare
    extra = 0


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("id", "spent_on", "description", "paid_by",
                    "amount_base_minor", "original_currency", "split_type", "status")
    list_filter = ("status", "split_type", "original_currency", "group")
    inlines = [ExpenseShareInline]


@admin.register(Settlement)
class SettlementAdmin(admin.ModelAdmin):
    list_display = ("id", "settled_on", "from_person", "to_person", "amount_minor", "origin")
    list_filter = ("origin", "group")


@admin.register(FxRate)
class FxRateAdmin(admin.ModelAdmin):
    list_display = ("id", "currency", "rate_to_base", "effective_date")
