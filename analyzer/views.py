from decimal import Decimal

from django.contrib import messages
from django.db.models import Count, Sum
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render

from .forms import DailyBetResultForm, ExcelUploadForm
from .models import DailyBetResult
from .services.excel_parser import parse_lotofacil_excel
from .services.lotofacil_api import fetch_next_lotofacil_draw
from .services.metrics import build_dashboard_metrics


def _financial_chart_data():
	records = list(
		DailyBetResult.active_objects.active().order_by('play_date')[:30]
	)

	if not records:
		return {
			'has_data': False,
			'labels': [],
			'invested': [],
			'returned': [],
			'balance': [],
			'cumulative_balance': [],
			'total_invested': 0,
			'total_returned': 0,
			'total_balance': 0,
			'roi_percent': 0,
			'profitable_bets_percent': 0,
			'profitable_bets_count': 0,
			'loss_bets_count': 0,
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
		'total_invested': total_invested,
		'total_returned': total_returned,
		'total_balance': total_balance,
		'roi_percent': roi_percent,
		'profitable_bets_percent': profitable_bets_percent,
		'profitable_bets_count': profitable_records_count,
		'loss_bets_count': loss_records_count,
	}


def home(request):
	form = ExcelUploadForm()
	chart_data = _financial_chart_data()
	next_draw = fetch_next_lotofacil_draw()

	if request.method == 'POST':
		form = ExcelUploadForm(request.POST, request.FILES)
		if form.is_valid():
			try:
				parse_result = parse_lotofacil_excel(form.cleaned_data['file'])
				dashboard = build_dashboard_metrics(parse_result.draws)
				context = {
					'form': form,
					'parse_result': parse_result,
					'dashboard': dashboard,
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
		},
	)


def daily_results(request):
	records = DailyBetResult.active_objects.active()
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

	context = {
		'records': records,
		'total_invested': total_invested,
		'total_returned': total_returned,
		'balance': balance,
		'roi_percent': roi_percent,
		'records_count': aggregates['records_count'] or 0,
	}
	return render(request, 'analyzer/daily_results.html', context)


def daily_result_create(request):
	form = DailyBetResultForm()

	if request.method == 'POST':
		form = DailyBetResultForm(request.POST)
		if form.is_valid():
			form.save()
			messages.success(request, 'Registro financeiro salvo com sucesso.')
			return redirect('daily_results')

	context = {
		'form': form,
		'page_title': 'Novo Registro Financeiro',
		'page_heading': 'Novo Registro Diario',
		'page_subtitle': 'Salve o valor investido e o valor retornado do dia.',
		'submit_label': 'Salvar registro',
	}
	return render(request, 'analyzer/daily_result_form.html', context)


def daily_result_edit(request, record_id):
	record = get_object_or_404(DailyBetResult.active_objects.active(), pk=record_id)
	form = DailyBetResultForm(instance=record)

	if request.method == 'POST':
		form = DailyBetResultForm(request.POST, instance=record)
		if form.is_valid():
			form.save()
			messages.success(request, 'Registro financeiro atualizado com sucesso.')
			return redirect('daily_results')

	context = {
		'form': form,
		'record': record,
		'page_title': 'Editar Registro Financeiro',
		'page_heading': 'Editar Registro Diario',
		'page_subtitle': 'Atualize os dados do registro selecionado.',
		'submit_label': 'Salvar alteracoes',
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
