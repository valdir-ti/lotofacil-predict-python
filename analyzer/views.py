import json
import logging
from decimal import Decimal

from django.contrib import messages
from django.conf import settings
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render

from .forms import DailyBetResultForm, ExcelUploadForm, ManualGameForm
from .models import ConfirmedGame, DailyBetResult
from .services.bet_checker import check_pending_games
from .services.bet_confirmation import InvalidGameError, confirm_ai_games
from .services.excel_parser import parse_lotofacil_excel
from .services.lotofacil_api import fetch_next_lotofacil_draw
from .services.metrics import build_dashboard_metrics
from .services.chatgpt_client import generate_games_from_excel_file
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt


DAILY_RESULTS_PAGE_SIZE = 10


logger = logging.getLogger(__name__)


def _financial_chart_data():
	records = list(
		DailyBetResult.active_objects.active()
		.prefetch_related('games')
		.order_by('play_date')[:30]
	)

	if not records:
		return {
			'has_data': False,
			'labels': [],
			'invested': [],
			'returned': [],
			'balance': [],
			'cumulative_balance': [],
			'contemplated': [],
			'total_invested': 0,
			'total_returned': 0,
			'total_balance': 0,
			'roi_percent': 0,
			'profitable_bets_percent': 0,
			'profitable_bets_count': 0,
			'loss_bets_count': 0,
			'contemplated_days_count': 0,
		}

	labels = [record.play_date.strftime('%d/%m') for record in records]
	invested_series = [float(record.invested_amount) for record in records]
	returned_series = [float(record.returned_amount) for record in records]
	balance_series = [float(record.balance) for record in records]
	cumulative_balance_series = []
	running_balance = Decimal('0')
	for record in records:
		running_balance += record.balance
		cumulative_balance_series.append(float(running_balance))
	total_invested = sum((record.invested_amount for record in records), Decimal('0'))
	total_returned = sum((record.returned_amount for record in records), Decimal('0'))
	total_balance = sum((record.balance for record in records), Decimal('0'))
	profitable_records_count = sum(1 for record in records if record.balance > 0)
	loss_records_count = sum(1 for record in records if record.balance < 0)
	contemplated_series = [record.has_contemplated_game for record in records]
	contemplated_days_count = sum(1 for flag in contemplated_series if flag)
	records_count = len(records)
	roi_percent = Decimal('0')
	if total_invested > 0:
		roi_percent = (total_balance / total_invested) * Decimal('100')
	profitable_bets_percent = Decimal('0')
	if records_count > 0:
		profitable_bets_percent = (
			Decimal(profitable_records_count) / Decimal(records_count)
		) * Decimal('100')

	return {
		'has_data': True,
		'labels': labels,
		'invested': invested_series,
		'returned': returned_series,
		'balance': balance_series,
		'cumulative_balance': cumulative_balance_series,
		'contemplated': contemplated_series,
		'total_invested': total_invested,
		'total_returned': total_returned,
		'total_balance': total_balance,
		'roi_percent': roi_percent,
		'profitable_bets_percent': profitable_bets_percent,
		'profitable_bets_count': profitable_records_count,
		'contemplated_days_count': contemplated_days_count,
		'loss_bets_count': loss_records_count,
	}


def home(request):
	try:
		check_pending_games(force=False)
	except Exception:
		logger.exception('Falha ao conferir apostas automaticamente.')

	form = ExcelUploadForm()
	chart_data = _financial_chart_data()
	next_draw = fetch_next_lotofacil_draw()

	if request.method == 'POST':
		form = ExcelUploadForm(request.POST, request.FILES)
		if form.is_valid():
			try:
				uploaded_file = form.cleaned_data['file']
				parse_result = parse_lotofacil_excel(uploaded_file)
				dashboard = build_dashboard_metrics(parse_result.draws)
				ai_games = []
				ai_notes = ''
				ai_error = ''
				try:
					uploaded_file.seek(0)
					prediction = generate_games_from_excel_file(uploaded_file)
					model_result = prediction['model_result']
					ai_games = model_result['recommended_games']
					ai_notes = model_result['meta']['notes']
				except Exception:
					logger.exception('Falha ao gerar recomendações com a IA.')
					ai_error = (
						'A IA não respondeu com uma recomendação válida. '
						'A análise heurística continua disponível abaixo.'
					)
				context = {
					'form': form,
					'parse_result': parse_result,
					'dashboard': dashboard,
					'ai_games': ai_games,
					'ai_notes': ai_notes,
					'ai_used_draws': min(len(parse_result.draws), settings.LLM_MAX_DRAWS),
					'ai_game_count': settings.LLM_GAME_COUNT,
					'ai_error': ai_error,
					'ai_target_concurso': next_draw.get('next_contest_number'),
					'ai_bet_unit_price': settings.AI_BET_UNIT_PRICE,
				}
				return render(request, 'analyzer/results.html', context)
			except ValueError as exc:
				messages.error(request, str(exc))
			except Exception:
				messages.error(
					request,
					'Erro inesperado ao processar o arquivo. Verifique o formato e tente novamente.',
				)

	return render(
		request,
		'analyzer/upload.html',
		{
			'form': form,
			'financial_chart_data': chart_data,
			'next_lotofacil_draw': next_draw,
			'home_total_invested': chart_data['total_invested'],
			'home_total_returned': chart_data['total_returned'],
			'home_total_balance': chart_data['total_balance'],
			'home_roi_percent': chart_data['roi_percent'],
			'home_profitable_bets_percent': chart_data['profitable_bets_percent'],
			'home_profitable_bets_count': chart_data['profitable_bets_count'],
			'home_loss_bets_count': chart_data['loss_bets_count'],
			'home_contemplated_days_count': chart_data['contemplated_days_count'],
		},
	)


def daily_results(request):
	try:
		check_pending_games(force=False)
	except Exception:
		logger.exception('Falha ao conferir apostas automaticamente.')

	records = DailyBetResult.active_objects.active().prefetch_related('games')
	aggregates = records.aggregate(
		total_invested=Sum('invested_amount'),
		total_returned=Sum('returned_amount'),
		records_count=Count('id'),
	)

	total_invested = aggregates['total_invested'] or 0
	total_returned = aggregates['total_returned'] or 0
	balance = total_returned - total_invested
	roi_percent = 0
	if total_invested > 0:
		roi_percent = round((balance / total_invested) * 100, 2)

	paginator = Paginator(records, DAILY_RESULTS_PAGE_SIZE)
	page_obj = paginator.get_page(request.GET.get('page'))

	context = {
		'page_obj': page_obj,
		'total_invested': total_invested,
		'total_returned': total_returned,
		'balance': balance,
		'roi_percent': roi_percent,
		'records_count': aggregates['records_count'] or 0,
	}
	return render(request, 'analyzer/daily_results.html', context)


def conferir_apostas(request):
	if request.method != 'POST':
		return redirect('daily_results')

	try:
		result = check_pending_games(force=True)
	except Exception:
		logger.exception('Falha ao conferir apostas manualmente.')
		messages.error(request, 'Não foi possível conferir as apostas agora. Tente novamente em instantes.')
		return redirect('daily_results')

	if result['checked_count'] == 0:
		messages.success(request, 'Conferência concluída. Nenhum jogo pendente com resultado disponível.')
	else:
		messages.success(
			request,
			f"Conferência concluída: {result['checked_count']} jogo(s) conferido(s), "
			f"{result['contemplated_count']} contemplado(s).",
		)
	return redirect('daily_results')


def daily_result_create(request):
	form = DailyBetResultForm()

	if request.method == 'POST':
		form = DailyBetResultForm(request.POST)
		if form.is_valid():
			with transaction.atomic():
				record = form.save()
				for dezenas in form.cleaned_data['games']:
					ConfirmedGame.objects.create(
						daily_result=record,
						dezenas=dezenas,
						concurso=record.concurso,
						amount=settings.AI_BET_UNIT_PRICE,
						source=ConfirmedGame.SOURCE_MANUAL,
					)
			messages.success(request, 'Registro financeiro salvo com sucesso.')
			return redirect('daily_results')

	context = {
		'form': form,
		'page_title': 'Novo Registro Financeiro',
		'page_heading': 'Novo Registro Diário',
		'page_subtitle': 'Salve o valor investido e o valor retornado do dia.',
		'submit_label': 'Salvar registro',
		'show_games_field': True,
	}
	return render(request, 'analyzer/daily_result_form.html', context)


def daily_result_edit(request, record_id):
	record = get_object_or_404(DailyBetResult.active_objects.active(), pk=record_id)
	existing_games = list(record.games.all())
	initial_games = '\n'.join(
		','.join(str(number) for number in game.dezenas)
		for game in existing_games
	)
	form_initial = {'games': initial_games}
	form = DailyBetResultForm(instance=record, initial=form_initial)
	form.add_game_received_fields(existing_games)

	if request.method == 'POST':
		form = DailyBetResultForm(request.POST, instance=record, initial=form_initial)
		form.add_game_received_fields(existing_games)
		if form.is_valid():
			submitted_games = form.cleaned_data['games']
			current_games = [list(game.dezenas) for game in existing_games]
			games_changed = submitted_games != current_games
			if games_changed and not form.cleaned_data['confirm_games_change']:
				form.add_error(
					'confirm_games_change',
					'Confirme a alteração dos jogos antes de salvar.',
				)
			else:
				with transaction.atomic():
					form.save()
					for index, game in enumerate(existing_games):
						received_field = f'game_{game.pk}_prize_received'
						received = form.cleaned_data.get(received_field) or False
						if index < len(submitted_games):
							new_numbers = submitted_games[index]
							if list(game.dezenas) != new_numbers:
								if game.prize_amount:
									record.returned_amount -= game.prize_amount
								game.dezenas = new_numbers
								game.is_checked = False
								game.is_contemplated = False
								game.hits_count = None
								game.matched_numbers = None
								game.prize_amount = None
								game.prize_received = False
								game.checked_at = None
								game.save()
							elif game.prize_received != received:
								game.prize_received = received
								game.save(update_fields=['prize_received'])
						elif game.prize_amount:
							record.returned_amount -= game.prize_amount
							game.delete()
						else:
							game.delete()

					for new_numbers in submitted_games[len(existing_games):]:
						ConfirmedGame.objects.create(
							daily_result=record,
							dezenas=new_numbers,
							concurso=record.concurso,
							amount=settings.AI_BET_UNIT_PRICE,
							source=ConfirmedGame.SOURCE_MANUAL,
						)

					if games_changed:
						record.save(update_fields=['returned_amount', 'updated_at'])
				messages.success(request, 'Registro financeiro atualizado com sucesso.')
				return redirect('daily_results')

	context = {
		'form': form,
		'record': record,
		'existing_games': existing_games,
		'page_title': 'Editar Registro Financeiro',
		'page_heading': 'Editar Registro Diário',
		'page_subtitle': 'Atualize os dados do registro selecionado.',
		'submit_label': 'Salvar alterações',
		'show_games_field': True,
		'show_games_confirmation': True,
	}
	return render(request, 'analyzer/daily_result_form.html', context)


def daily_result_delete(request, record_id):
	record = get_object_or_404(DailyBetResult.active_objects.active(), pk=record_id)

	if request.method == 'POST':
		record.is_active = False
		record.deactivated_at = timezone.now()
		record.updated_at = timezone.now()
		record.save(update_fields=['is_active', 'deactivated_at', 'updated_at'])
		messages.success(request, 'Registro financeiro desativado com sucesso.')
		return redirect('daily_results')

	context = {
		'record': record,
		'record_play_date': record.play_date.strftime('%d/%m/%Y'),
		'record_concurso': record.concurso or '-',
		'record_invested_amount': f'{record.invested_amount:.2f}',
		'record_returned_amount': f'{record.returned_amount:.2f}',
	}
	return render(request, 'analyzer/daily_result_delete.html', context)


@csrf_exempt
@require_POST
def upload_and_predict(request):
	uploaded_file = request.FILES.get('file')
	if not uploaded_file:
		return JsonResponse({'error': 'file is required'}, status=400)

	try:
		result = generate_games_from_excel_file(uploaded_file)
	except Exception as e:
		return JsonResponse({'error': str(e)}, status=500)

	return JsonResponse(result)


@require_POST
def confirm_ai_games_view(request):
	try:
		payload = json.loads(request.body or '{}')
	except json.JSONDecodeError:
		return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)

	games = payload.get('games')
	if games is None and 'numbers' in payload:
		games = [
			{
				'numbers': payload.get('numbers'),
				'score': payload.get('score'),
				'rationale': payload.get('rationale'),
			}
		]
	concurso = payload.get('concurso')

	if not isinstance(games, list) or not games:
		return JsonResponse({'error': 'At least one game is required.'}, status=400)

	try:
		created_games = confirm_ai_games(
			play_date=timezone.localdate(),
			games=games,
			concurso=concurso,
		)
	except InvalidGameError as exc:
		return JsonResponse({'error': str(exc)}, status=400)
	except Exception:
		logger.exception('Falha ao confirmar jogos da IA.')
		return JsonResponse({'error': 'Erro inesperado ao confirmar os jogos.'}, status=500)

	daily_result = created_games[0].daily_result
	return JsonResponse(
		{
			'ok': True,
			'game_ids': [game.id for game in created_games],
			'invested_amount': float(daily_result.invested_amount),
			'play_date': daily_result.play_date.isoformat(),
		}
	)


def add_manual_game(request, record_id):
	record = get_object_or_404(DailyBetResult.active_objects.active(), pk=record_id)
	form = ManualGameForm(initial={'concurso': record.concurso})

	if request.method == 'POST':
		form = ManualGameForm(request.POST)
		if form.is_valid():
			game = form.save(commit=False)
			game.daily_result = record
			game.source = game.__class__.SOURCE_MANUAL
			if game.is_contemplated:
				game.is_checked = True
			if game.is_checked and not game.checked_at:
				game.checked_at = timezone.now()
			game.save()
			messages.success(request, 'Jogo adicionado com sucesso.')
			return redirect('daily_results')

	context = {
		'form': form,
		'record': record,
	}
	return render(request, 'analyzer/manual_game_form.html', context)
