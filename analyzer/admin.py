from django.contrib import admin

from .models import BetConferenceRun, ConfirmedGame, DailyBetResult


class ConfirmedGameInline(admin.TabularInline):
	model = ConfirmedGame
	extra = 0
	fields = (
		'dezenas',
		'concurso',
		'amount',
		'source',
		'is_checked',
		'is_contemplated',
		'hits_count',
		'prize_amount',
		'checked_at',
	)
	readonly_fields = ('checked_at',)


@admin.register(DailyBetResult)
class DailyBetResultAdmin(admin.ModelAdmin):
	list_display = ('play_date', 'concurso', 'invested_amount', 'returned_amount', 'balance')
	list_filter = ('play_date',)
	search_fields = ('concurso', 'notes')
	inlines = [ConfirmedGameInline]


@admin.register(BetConferenceRun)
class BetConferenceRunAdmin(admin.ModelAdmin):
	list_display = ('checked_at', 'triggered_by', 'checked_count', 'contemplated_count')
	list_filter = ('triggered_by',)
