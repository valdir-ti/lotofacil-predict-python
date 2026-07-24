from django.contrib import messages
from django.shortcuts import render

from .forms import ExcelUploadForm
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
