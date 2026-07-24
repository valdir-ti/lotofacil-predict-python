from django.contrib import admin

from .models import DailyBetResult


@admin.register(DailyBetResult)
class DailyBetResultAdmin(admin.ModelAdmin):
	list_display = ('play_date', 'concurso', 'invested_amount', 'returned_amount', 'balance')
	list_filter = ('play_date',)
	search_fields = ('concurso', 'notes')
