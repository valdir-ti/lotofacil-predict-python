import json
from io import BytesIO
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from openpyxl import Workbook

from analyzer.services.chatgpt_client import generate_games_from_excel_file


def _excel_file(draw_count=1):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(['Concurso', 'Data Sorteio', *[f'Bola{number}' for number in range(1, 16)]])
    for contest_number in range(1, draw_count + 1):
        numbers = list(range(1, 15)) + [contest_number + 14]
        sheet.append([contest_number, '01/01/2024', *numbers])

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    output.name = 'lotofacil.xlsx'
    return output


def _model_response(game_count=3):
    games = [
        {
            'numbers': list(range(start, start + 15)),
            'score': 0.8,
            'rationale': 'Valid test game.',
        }
        for start in range(1, game_count + 1)
    ]
    return json.dumps(
        {
            'meta': {'used_draws': 1, 'notes': 'test'},
            'stats': {},
            'raw_arrays': {},
            'recommended_games': games,
        }
    )


@override_settings(
    LLM_PROVIDER='openai',
    OPENAI_API_KEY='test-key',
    OPENAI_MODEL='gpt-5.4-nano',
    LLM_MAX_DRAWS=500,
    LLM_GAME_COUNT=3,
)
class PredictionProviderTests(SimpleTestCase):
    @patch('analyzer.services.chatgpt_client.OpenAI')
    def test_uses_openai_with_configured_model_and_schema(self, mock_openai):
        response = Mock(output_text=_model_response())
        mock_openai.return_value.responses.create.return_value = response

        result = generate_games_from_excel_file(_excel_file())

        self.assertEqual(len(result['model_result']['recommended_games']), 3)
        self.assertEqual(result['model_result']['recommended_games'][0]['numbers'], list(range(1, 16)))
        self.assertNotIn('graphs', result)
        mock_openai.assert_called_once_with(api_key='test-key')
        request = mock_openai.return_value.responses.create.call_args.kwargs
        self.assertEqual(request['model'], 'gpt-5.4-nano')
        prompt = request['input']
        instructions, _payload = prompt.rsplit('\n\n{', 1)
        self.assertIn('montar 3 jogos equilibrados', prompt)
        self.assertIn('português brasileiro', prompt)
        self.assertNotIn('[1, 2, 3, 4, 5', instructions)
        schema = request['text']['format']['schema']
        self.assertEqual(schema['properties']['recommended_games']['type'], 'array')
        self.assertEqual(schema['properties']['meta']['properties']['used_draws']['type'], 'integer')

    @override_settings(LLM_MAX_DRAWS=2)
    @patch('analyzer.services.chatgpt_client.OpenAI')
    def test_sends_only_the_configured_most_recent_draws(self, mock_openai):
        mock_openai.return_value.responses.create.return_value = Mock(
            output_text=_model_response()
        )

        generate_games_from_excel_file(_excel_file(draw_count=3))

        prompt = mock_openai.return_value.responses.create.call_args.kwargs['input']
        _instructions, payload = prompt.rsplit('\n\n', 1)
        sent_draws = json.loads(payload)['draws']
        self.assertEqual(len(sent_draws), 2)
        self.assertEqual(sent_draws[-1][-1], 17)

    @override_settings(LLM_GAME_COUNT=2)
    @patch('analyzer.services.chatgpt_client.OpenAI')
    def test_uses_configured_game_count_for_validation(self, mock_openai):
        mock_openai.return_value.responses.create.return_value = Mock(
            output_text=_model_response(game_count=2)
        )

        result = generate_games_from_excel_file(_excel_file())

        self.assertEqual(len(result['model_result']['recommended_games']), 2)

    @patch('analyzer.services.chatgpt_client.OpenAI')
    def test_reports_returned_keys_when_recommended_games_is_missing(self, mock_generate):
        mock_generate.return_value.responses.create.return_value = Mock(
            output_text=json.dumps({'games': []})
        )

        with self.assertRaisesMessage(
            ValueError,
            "Returned top-level keys: ['games']",
        ):
            generate_games_from_excel_file(_excel_file())
