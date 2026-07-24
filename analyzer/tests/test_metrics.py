from datetime import date

from django.test import SimpleTestCase

from analyzer.services.excel_parser import DrawRecord
from analyzer.services.metrics import build_dashboard_metrics


class MetricsTests(SimpleTestCase):
    def test_build_dashboard_metrics(self):
        draws = [
            DrawRecord(concurso=1, data_sorteio=date(2024, 1, 1), dezenas=list(range(1, 16))),
            DrawRecord(concurso=2, data_sorteio=date(2024, 1, 3), dezenas=list(range(1, 15)) + [16]),
            DrawRecord(concurso=3, data_sorteio=date(2024, 1, 5), dezenas=list(range(2, 17))),
        ]

        dashboard = build_dashboard_metrics(draws)

        self.assertEqual(dashboard['total_draws'], 3)
        self.assertEqual(dashboard['most_frequent'][0].dezena, 2)
        self.assertEqual(dashboard['most_frequent'][0].frequencia, 3)
        self.assertIn('avg_even', dashboard)
        self.assertIn('overdue_numbers', dashboard)
        self.assertEqual(len(dashboard['recommended_games']), 3)

    def test_overdue_numbers_have_non_negative_gap(self):
        draws = [
            DrawRecord(concurso=1, data_sorteio=None, dezenas=list(range(1, 16))),
            DrawRecord(concurso=2, data_sorteio=None, dezenas=list(range(1, 16))),
        ]

        dashboard = build_dashboard_metrics(draws)
        gaps = [item['concursos_sem_sair'] for item in dashboard['overdue_numbers']]

        self.assertTrue(all(gap >= 0 for gap in gaps))

    def test_recommended_games_follow_rules(self):
        draws = [
            DrawRecord(concurso=i + 1, data_sorteio=None, dezenas=list(range(1 + (i % 5), 16 + (i % 5))))
            for i in range(15)
        ]

        dashboard = build_dashboard_metrics(draws)

        self.assertEqual(len(dashboard['recommended_games']), 3)
        for game in dashboard['recommended_games']:
            self.assertEqual(len(game['numbers']), 15)
            self.assertEqual(game['even_count'], 7)
            self.assertEqual(game['odd_count'], 8)
            self.assertTrue(9 <= game['moldura_count'] <= 11)
