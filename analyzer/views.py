from django.contrib import messages
from django.db.models import Count, Sum
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render

from .forms import DailyBetResultForm, ExcelUploadForm
from .models import DailyBetResult
from .services.excel_parser import parse_lotofacil_excel
from .services.metrics import build_dashboard_metrics


def home(request):
	form = ExcelUploadForm()

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

	return render(request, 'analyzer/upload.html', {'form': form})


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
