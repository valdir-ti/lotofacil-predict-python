import json
from urllib.error import URLError
from unittest.mock import patch

from django.test import SimpleTestCase

from analyzer.services.lotofacil_api import fetch_next_lotofacil_draw


class _MockHttpResponse:
    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class LotofacilApiServiceTests(SimpleTestCase):
    @patch('analyzer.services.lotofacil_api.urlopen')
    def test_returns_valid_next_draw_when_payload_has_expected_fields(self, mock_urlopen):
        payload = {
            'numero': 3745,
            'numeroConcursoProximo': 3746,
            'dataProximoConcurso': '27/07/2026',
            'valorEstimadoProximoConcurso': 9000000.0,
        }
        mock_urlopen.return_value = _MockHttpResponse(json.dumps(payload).encode('utf-8'))

        result = fetch_next_lotofacil_draw()

        self.assertTrue(result['has_data'])
        self.assertEqual(result['next_contest_number'], 3746)
        self.assertEqual(result['next_contest_date'], '27/07/2026')
        self.assertEqual(result['next_accumulated_value'], 'R$ 9.000.000,00')

    @patch('analyzer.services.lotofacil_api.urlopen')
    def test_normalizes_iso_date_when_api_changes_format(self, mock_urlopen):
        payload = {
            'numero': 3745,
            'numeroConcursoProximo': 3746,
            'dataProximoConcurso': '2026-07-27',
            'valorEstimadoProximoConcurso': 9000000.0,
        }
        mock_urlopen.return_value = _MockHttpResponse(json.dumps(payload).encode('utf-8'))

        result = fetch_next_lotofacil_draw()

        self.assertTrue(result['has_data'])
        self.assertEqual(result['next_contest_date'], '27/07/2026')

    @patch('analyzer.services.lotofacil_api.urlopen')
    def test_uses_next_number_fallback_when_missing(self, mock_urlopen):
        payload = {
            'numero': 3745,
            'numeroConcursoProximo': None,
            'dataProximoConcurso': '27/07/2026',
            'valorAcumuladoProximoConcurso': 4520005.36,
        }
        mock_urlopen.return_value = _MockHttpResponse(json.dumps(payload).encode('utf-8'))

        result = fetch_next_lotofacil_draw()

        self.assertTrue(result['has_data'])
        self.assertEqual(result['next_contest_number'], 3746)
        self.assertEqual(result['next_accumulated_value'], 'R$ 4.520.005,36')

    @patch('analyzer.services.lotofacil_api.urlopen')
    def test_returns_unavailable_when_request_fails(self, mock_urlopen):
        mock_urlopen.side_effect = URLError('network down')

        result = fetch_next_lotofacil_draw()

        self.assertFalse(result['has_data'])
        self.assertIsNone(result['next_contest_number'])
        self.assertIsNone(result['next_contest_date'])
        self.assertIsNone(result['next_accumulated_value'])

    @patch('analyzer.services.lotofacil_api.urlopen')
    def test_returns_unavailable_when_payload_is_invalid_json(self, mock_urlopen):
        mock_urlopen.return_value = _MockHttpResponse(b'not-json')

        result = fetch_next_lotofacil_draw()

        self.assertFalse(result['has_data'])
        self.assertIsNone(result['next_contest_number'])
        self.assertIsNone(result['next_contest_date'])

    @patch('analyzer.services.lotofacil_api.urlopen')
    def test_returns_unavailable_when_next_date_cannot_be_parsed(self, mock_urlopen):
        payload = {
            'numero': 3745,
            'numeroConcursoProximo': 3746,
            'dataProximoConcurso': '27-2026-07',
            'valorEstimadoProximoConcurso': 9000000.0,
        }
        mock_urlopen.return_value = _MockHttpResponse(json.dumps(payload).encode('utf-8'))

        result = fetch_next_lotofacil_draw()

        self.assertFalse(result['has_data'])
        self.assertEqual(result['next_contest_number'], 3746)
        self.assertIsNone(result['next_contest_date'])
