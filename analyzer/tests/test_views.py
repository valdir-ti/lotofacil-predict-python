from io import BytesIO
from decimal import Decimal
import json
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from django.test import TestCase
from openpyxl import Workbook

from datetime import date

from analyzer.forms import DailyBetResultForm
from analyzer.models import ConfirmedGame, DailyBetResult


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


class AuthenticatedViewTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='test-user',
            email='test@example.com',
            password='unused-password',
        )
        self.client.force_login(self.user)


class HomeViewTests(AuthenticatedViewTestCase):
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
            owner=self.user,
            play_date='2026-07-23',
            concurso=3599,
            invested_amount=Decimal('10.50'),
            returned_amount=Decimal('5.00'),
        )
        DailyBetResult.objects.create(
            owner=self.user,
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
        self.assertContains(response, '% de dias lucrativos:')
        self.assertContains(response, 'Dias lucrativos:')
        self.assertContains(response, 'Dias com prejuízo:')
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
        self.assertNotContains(response, '{{ ai_bet_unit_price')
        self.assertNotContains(response, '{{ ai_target_concurso')
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


class FinancialViewsTests(AuthenticatedViewTestCase):
    def test_financial_list_page_loads(self):
        response = self.client.get('/financeiro/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Controle de Investimento x Retorno')

    def test_financial_create_get_loads_form(self):
        response = self.client.get('/financeiro/novo/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Novo Registro Diário')

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
            owner=self.user,
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
        self.assertContains(response, 'Já existe um registro para esta data.')
        self.assertEqual(DailyBetResult.objects.count(), 1)

    def test_financial_list_shows_aggregated_values(self):
        DailyBetResult.objects.create(
            owner=self.user,
            play_date='2026-07-23',
            concurso=3599,
            invested_amount=Decimal('30.00'),
            returned_amount=Decimal('0.00'),
        )
        DailyBetResult.objects.create(
            owner=self.user,
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

    def test_financial_list_pagination_renders_page_values(self):
        for index in range(11):
            DailyBetResult.objects.create(
            owner=self.user,
                play_date=date(2026, 7, 1 + index),
                concurso=3500 + index,
                invested_amount=Decimal('10.00'),
                returned_amount=Decimal('0.00'),
            )

        first_page = self.client.get('/financeiro/?page=1')
        second_page = self.client.get('/financeiro/?page=2')

        self.assertContains(first_page, 'Página 1 de 2')
        self.assertContains(second_page, 'Página 2 de 2')
        self.assertNotContains(first_page, '{{ page_obj.paginator.num_pages')
        self.assertNotContains(second_page, '{{ page_obj.paginator.num_pages')

    def test_financial_edit_updates_record(self):
        record = DailyBetResult.objects.create(
            owner=self.user,
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
            owner=self.user,
            play_date='2026-07-23',
            concurso=3599,
            invested_amount=Decimal('20.00'),
            returned_amount=Decimal('0.00'),
        )
        record = DailyBetResult.objects.create(
            owner=self.user,
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
        self.assertContains(response, 'Já existe um registro para esta data.')

    def test_financial_delete_deactivates_record(self):
        record = DailyBetResult.objects.create(
            owner=self.user,
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


class ConfirmAiGameViewTests(AuthenticatedViewTestCase):
    def test_confirms_valid_game_and_persists_record(self):
        response = self.client.post(
            '/financeiro/confirmar-jogo/',
            data=json.dumps(
                {
                    'numbers': list(range(1, 16)),
                    'concurso': 3752,
                    'score': 0.88,
                    'rationale': 'Jogo de teste.',
                }
            ),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['invested_amount'], 3.5)

        daily_result = DailyBetResult.objects.first()
        self.assertEqual(daily_result.invested_amount, Decimal('3.50'))
        self.assertEqual(ConfirmedGame.objects.count(), 1)

    def test_rejects_invalid_numbers(self):
        response = self.client.post(
            '/financeiro/confirmar-jogo/',
            data=json.dumps({'numbers': [1, 2, 3], 'concurso': 3752}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())
        self.assertEqual(DailyBetResult.objects.count(), 0)

    def test_rejects_get_method(self):
        response = self.client.get('/financeiro/confirmar-jogo/')
        self.assertEqual(response.status_code, 405)


class ConferirApostasViewTests(AuthenticatedViewTestCase):
    @patch('analyzer.views.check_pending_games')
    def test_manual_check_triggers_service_with_force_true(self, mock_check):
        mock_check.return_value = {'ran': True, 'checked_count': 2, 'contemplated_count': 1}

        response = self.client.post('/financeiro/conferir/')

        mock_check.assert_called_once_with(force=True)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/financeiro/')

    def test_rejects_get_method(self):
        response = self.client.get('/financeiro/conferir/')
        self.assertEqual(response.status_code, 302)


class DailyResultsGamesRenderingTests(AuthenticatedViewTestCase):
    @patch('analyzer.views.check_pending_games')
    def test_shows_confirmed_game_with_hit_numbers(self, mock_check):
        mock_check.return_value = {'ran': False, 'checked_count': 0, 'contemplated_count': 0}

        daily_result = DailyBetResult.objects.create(
            owner=self.user,
            play_date='2026-08-05',
            concurso=3752,
            invested_amount=Decimal('3.50'),
            returned_amount=Decimal('500000.00'),
        )
        ConfirmedGame.objects.create(
            daily_result=daily_result,
            dezenas=list(range(1, 16)),
            concurso=3752,
            amount=Decimal('3.50'),
            is_checked=True,
            is_contemplated=True,
            hits_count=15,
            matched_numbers=list(range(1, 16)),
            prize_amount=Decimal('500000.00'),
        )

        response = self.client.get('/financeiro/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Contemplado')
        self.assertContains(response, 'chip hit')
        self.assertNotContains(response, '{% elif')
        self.assertNotContains(response, '{{ game.hits_count }}')

    @patch('analyzer.views.check_pending_games')
    def test_shows_pending_game_awaiting_draw(self, mock_check):
        mock_check.return_value = {'ran': False, 'checked_count': 0, 'contemplated_count': 0}

        daily_result = DailyBetResult.objects.create(
            owner=self.user,
            play_date='2026-08-05',
            concurso=3752,
            invested_amount=Decimal('3.50'),
            returned_amount=Decimal('0'),
        )
        ConfirmedGame.objects.create(
            daily_result=daily_result,
            dezenas=list(range(1, 16)),
            concurso=3752,
            amount=Decimal('3.50'),
        )

        response = self.client.get('/financeiro/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Aguardando sorteio')
        self.assertNotContains(response, '{% elif')

