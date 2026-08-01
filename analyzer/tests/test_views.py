from io import BytesIO
from decimal import Decimal
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook

from datetime import date

from analyzer.forms import DailyBetResultForm
from analyzer.models import DailyBetResult


def _excel_payload():
    workbook = Workbook()
    sheet = workbook.active
    headers = ['Concurso', 'Data Sorteio'] + [f'Bola{i}' for i in range(1, 16)]
    sheet.append(headers)
    sheet.append([1, '01/01/2024', *range(1, 16)])

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output.read()


def _model_prediction():
    games = [
        {
            'numbers': list(range(start, start + 15)),
            'score': 0.8,
            'rationale': 'Jogo de teste da IA.',
        }
        for start in range(1, 4)
    ]
    return {
        'model_result': {
            'meta': {'used_draws': 1, 'notes': 'Análise de teste.'},
            'recommended_games': games,
        },
        'raw_arrays': {},
    }


class HomeViewTests(TestCase):
    @patch('analyzer.views.fetch_next_lotofacil_draw')
    def test_home_page_loads(self, mock_next_draw):
        mock_next_draw.return_value = {
            'has_data': True,
            'next_contest_number': 3744,
            'next_contest_date': '24/07/2026',
            'next_accumulated_value': 'R$ 2.000.000,00',
        }

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Análise de Resultados da Lotofácil')
        self.assertContains(response, 'Resumo financeiro recente')
        self.assertContains(response, 'Próximo concurso da Lotofácil')
        self.assertContains(response, '3744')
        self.assertContains(response, '24/07/2026')
        self.assertContains(response, 'R$ 2.000.000,00')

    @patch('analyzer.views.fetch_next_lotofacil_draw')
    def test_home_page_shows_financial_totals(self, mock_next_draw):
        mock_next_draw.return_value = {
            'has_data': False,
            'next_contest_number': None,
            'next_contest_date': None,
            'next_accumulated_value': None,
        }

        DailyBetResult.objects.create(
            play_date='2026-07-23',
            concurso=3599,
            invested_amount=Decimal('10.50'),
            returned_amount=Decimal('5.00'),
        )
        DailyBetResult.objects.create(
            play_date='2026-07-24',
            concurso=3600,
            invested_amount=Decimal('4.50'),
            returned_amount=Decimal('7.00'),
        )

        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'R$ 15,00')
        self.assertContains(response, 'R$ 12,00')
        self.assertContains(response, 'class="negative"')
        self.assertContains(response, 'Saldo acumulado:')
        self.assertContains(response, 'ROI total:')
        self.assertContains(response, '% de apostas lucrativas:')
        self.assertContains(response, 'Apostas lucrativas:')
        self.assertContains(response, 'Apostas com prejuízo:')
        self.assertContains(response, '-20,00%')
        self.assertContains(response, '50,00%')
        self.assertContains(response, '>1<')
        self.assertContains(response, 'Ganhos/Perdas acumulado')
        self.assertContains(response, 'cumulative_balance')
        self.assertNotContains(response, '{{ financial_chart_data.total_invested')
        self.assertNotContains(response, '{{ financial_chart_data.total_returned')

    @patch('analyzer.views.fetch_next_lotofacil_draw')
    def test_home_page_shows_fallback_when_next_draw_unavailable(self, mock_next_draw):
        mock_next_draw.return_value = {
            'has_data': False,
            'next_contest_number': None,
            'next_contest_date': None,
            'next_accumulated_value': None,
        }

        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dados do próximo concurso indisponíveis no momento.')

    @patch('analyzer.views.generate_games_from_excel_file')
    def test_upload_excel_and_get_results(self, mock_predict):
        mock_predict.return_value = _model_prediction()
        file_data = _excel_payload()
        uploaded = SimpleUploadedFile(
            'lotofacil.xlsx',
            file_data,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        response = self.client.post('/', {'file': uploaded})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard de Resultados')
        self.assertContains(response, 'Todos os indicadores abaixo usam 100% dos concursos válidos')
        self.assertContains(response, '3 jogos recomendados pela IA')
        self.assertContains(response, '3 jogos recomendados pela análise local')
        self.assertContains(response, 'Jogo de teste da IA.')
        self.assertContains(response, '>01<')

    @patch('analyzer.views.generate_games_from_excel_file')
    def test_upload_excel_keeps_local_games_when_ai_fails(self, mock_predict):
        mock_predict.side_effect = ValueError('OpenAI unavailable')
        uploaded = SimpleUploadedFile(
            'lotofacil.xlsx',
            _excel_payload(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        response = self.client.post('/', {'file': uploaded})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '3 jogos recomendados pela análise local')
        self.assertContains(response, 'A IA não respondeu com uma recomendação válida.')
        self.assertNotContains(response, '3 jogos recomendados pela IA')

    @patch('analyzer.views.generate_games_from_excel_file')
    def test_prediction_api_omits_graph_payloads(self, mock_predict):
        mock_predict.return_value = _model_prediction()
        uploaded = SimpleUploadedFile(
            'lotofacil.xlsx',
            _excel_payload(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        response = self.client.post('/predict/upload/', {'file': uploaded})

        self.assertEqual(response.status_code, 200)
        self.assertIn('model_result', response.json())
        self.assertNotIn('graphs', response.json())


class FinancialViewsTests(TestCase):
    def test_financial_list_page_loads(self):
        response = self.client.get('/financeiro/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Controle de Investimento x Retorno')

    def test_financial_create_get_loads_form(self):
        response = self.client.get('/financeiro/novo/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Novo Registro Diario')

    def test_financial_form_uses_html_date_input(self):
        form = DailyBetResultForm()

        self.assertEqual(form.fields['play_date'].widget.input_type, 'date')

    def test_financial_form_renders_existing_date_in_html_format(self):
        record = DailyBetResult(play_date=date(2024, 7, 24), invested_amount=10, returned_amount=12)
        form = DailyBetResultForm(instance=record)

        rendered = form['play_date'].as_widget()

        self.assertIn('value="2024-07-24"', rendered)

    def test_financial_create_post_persists_and_redirects(self):
        response = self.client.post(
            '/financeiro/novo/',
            {
                'play_date': '24/07/2026',
                'concurso': '3600',
                'invested_amount': '30.00',
                'returned_amount': '18.00',
                'notes': '3 jogos recomendados',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/financeiro/')
        self.assertEqual(DailyBetResult.objects.count(), 1)

        record = DailyBetResult.objects.first()
        self.assertEqual(record.concurso, 3600)
        self.assertEqual(record.invested_amount, Decimal('30.00'))
        self.assertEqual(record.returned_amount, Decimal('18.00'))

    def test_financial_create_blocks_duplicate_date(self):
        DailyBetResult.objects.create(
            play_date='2026-07-24',
            concurso=3600,
            invested_amount=Decimal('30.00'),
            returned_amount=Decimal('18.00'),
            notes='primeiro',
        )

        response = self.client.post(
            '/financeiro/novo/',
            {
                'play_date': '24/07/2026',
                'concurso': '3601',
                'invested_amount': '40.00',
                'returned_amount': '0.00',
                'notes': 'duplicado',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ja existe um registro para esta data.')
        self.assertEqual(DailyBetResult.objects.count(), 1)

    def test_financial_list_shows_aggregated_values(self):
        DailyBetResult.objects.create(
            play_date='2026-07-23',
            concurso=3599,
            invested_amount=Decimal('30.00'),
            returned_amount=Decimal('0.00'),
        )
        DailyBetResult.objects.create(
            play_date='2026-07-24',
            concurso=3600,
            invested_amount=Decimal('45.00'),
            returned_amount=Decimal('90.00'),
        )

        response = self.client.get('/financeiro/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'R$ 75,00')
        self.assertContains(response, 'R$ 90,00')
        self.assertContains(response, 'R$ 15,00')
        self.assertContains(response, '20,00%')
        self.assertContains(response, 'Quantidade de registros')
        self.assertContains(response, '2')

    def test_financial_edit_updates_record(self):
        record = DailyBetResult.objects.create(
            play_date='2026-07-24',
            concurso=3600,
            invested_amount=Decimal('30.00'),
            returned_amount=Decimal('0.00'),
            notes='antes',
        )

        response = self.client.post(
            f'/financeiro/{record.id}/editar/',
            {
                'play_date': '24/07/2026',
                'concurso': '3601',
                'invested_amount': '35.00',
                'returned_amount': '20.00',
                'notes': 'depois',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/financeiro/')

        record.refresh_from_db()
        self.assertEqual(record.concurso, 3601)
        self.assertEqual(record.invested_amount, Decimal('35.00'))
        self.assertEqual(record.returned_amount, Decimal('20.00'))
        self.assertEqual(record.notes, 'depois')

    def test_financial_edit_blocks_duplicate_date(self):
        DailyBetResult.objects.create(
            play_date='2026-07-23',
            concurso=3599,
            invested_amount=Decimal('20.00'),
            returned_amount=Decimal('0.00'),
        )
        record = DailyBetResult.objects.create(
            play_date='2026-07-24',
            concurso=3600,
            invested_amount=Decimal('30.00'),
            returned_amount=Decimal('10.00'),
        )

        response = self.client.post(
            f'/financeiro/{record.id}/editar/',
            {
                'play_date': '23/07/2026',
                'concurso': '3600',
                'invested_amount': '30.00',
                'returned_amount': '10.00',
                'notes': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ja existe um registro para esta data.')

    def test_financial_delete_deactivates_record(self):
        record = DailyBetResult.objects.create(
            play_date='2026-07-24',
            concurso=3600,
            invested_amount=Decimal('30.00'),
            returned_amount=Decimal('10.00'),
        )

        response = self.client.post(f'/financeiro/{record.id}/excluir/')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/financeiro/')
        record.refresh_from_db()
        self.assertFalse(record.is_active)
        self.assertIsNotNone(record.deactivated_at)
        self.assertEqual(DailyBetResult.objects.count(), 1)
