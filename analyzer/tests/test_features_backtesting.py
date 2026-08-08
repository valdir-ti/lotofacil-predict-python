from datetime import date

from django.test import SimpleTestCase

from analyzer.services.backtesting import run_backtest
from analyzer.services.excel_parser import DrawRecord
from analyzer.services.features import calculate_game_features, calculate_number_features, validate_game
from analyzer.services.metrics import (
    _pick_diverse_candidates,
    calculate_diversity_adjusted_score,
    calculate_diversity_penalty,
    calculate_game_score,
    calculate_portfolio_diversity,
    generate_recommended_games,
)


def _draws(count=25):
    return [
        DrawRecord(
            concurso=index + 1,
            data_sorteio=date(2024, 1, 1),
            dezenas=sorted(((number + index - 1) % 25) + 1 for number in range(1, 16)),
        )
        for index in range(count)
    ]


class FeaturesAndBacktestingTests(SimpleTestCase):
    def test_number_features_are_normalized_and_complete(self):
        features = calculate_number_features(_draws(12))

        self.assertEqual(set(features), set(range(1, 26)))
        self.assertTrue(all(0 <= item['number_score'] <= 100 for item in features.values()))
        self.assertIn('last_10_score', features[1])
        self.assertIn('recent_frequency_score', features[1])

    def test_game_validation_and_score_are_deterministic(self):
        draws = _draws()
        game = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 16, 17, 18, 19]
        valid, reason = validate_game(game, set(draws[-1].dezenas))

        self.assertTrue(valid, reason)
        game_features = calculate_game_features(game, set(draws[-1].dezenas))
        score = calculate_game_score(game, draws, calculate_number_features(draws))
        self.assertEqual(game_features['even_count'], 7)
        self.assertTrue(0 <= score <= 100)

    def test_generated_games_are_valid_and_diverse(self):
        draws = _draws()
        games = generate_recommended_games(draws)

        self.assertEqual(len(games), 3)
        for game in games:
            valid, reason = validate_game(game['numbers'], set(draws[-1].dezenas))
            self.assertTrue(valid, reason)
        self.assertLessEqual(
            len(set(games[0]['numbers']).intersection(games[1]['numbers'])), 13
        )

    def test_backtest_is_walk_forward(self):
        draws = [
            DrawRecord(
                concurso=index + 1,
                data_sorteio=date(2024, 1, 1),
                dezenas=list(range(1, 16)),
            )
            for index in range(20)
        ]
        draws.extend(
            DrawRecord(
                concurso=index + 21,
                data_sorteio=date(2024, 2, 1),
                dezenas=list(range(11, 26)),
            )
            for index in range(5)
        )
        result = run_backtest(draws, min_history=20, game_count=2)

        self.assertEqual(result['tested_contests'], 5)
        self.assertEqual(result['records'][0]['contest_index'], 20)
        self.assertIn('legacy_heuristic', result['summary'])
        self.assertIn('structural_random', result['summary'])
        self.assertIn('legacy_heuristic', result['portfolio_summary'])
        prefix_features = calculate_number_features(draws[:20])
        self.assertEqual(prefix_features[25]['historical_frequency'], 0)

    def test_overlap_penalty_is_progressive_and_hard_limit_remains(self):
        self.assertEqual(calculate_diversity_penalty(8), 0)
        self.assertLess(calculate_diversity_penalty(10), calculate_diversity_penalty(13))
        adjusted, penalty = calculate_diversity_adjusted_score(90, [13])
        self.assertEqual(penalty, 30)
        self.assertEqual(adjusted, 60)
        adjusted, penalty = calculate_diversity_adjusted_score(90, [14])
        self.assertEqual(adjusted, float('-inf'))
        self.assertEqual(penalty, float('inf'))

    def test_selection_prefers_diversity_when_scores_are_close(self):
        first = list(range(1, 16))
        overlap_13 = first[:13] + [16, 17]
        overlap_9 = first[:9] + [16, 17, 18, 19, 20, 21]
        selected = _pick_diverse_candidates(
            [
                {'numbers': first, 'score': 90, 'intrinsic_score': 90},
                {'numbers': overlap_13, 'score': 89, 'intrinsic_score': 89},
                {'numbers': overlap_9, 'score': 87, 'intrinsic_score': 87},
            ],
            target_count=2,
        )
        self.assertEqual(selected[1]['numbers'], overlap_9)
        self.assertEqual(selected[1]['diversity_penalty'], 2)

    def test_bad_candidate_does_not_win_only_for_being_different(self):
        first = list(range(1, 16))
        poor = [11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]
        selected = _pick_diverse_candidates(
            [
                {'numbers': first, 'score': 95, 'intrinsic_score': 95},
                {'numbers': poor, 'score': 50, 'intrinsic_score': 50},
            ],
            target_count=2,
        )
        self.assertEqual(selected[0]['numbers'], first)
        self.assertEqual(selected[1]['numbers'], poor)

    def test_portfolio_metrics_measure_shared_core(self):
        games = [
            list(range(1, 16)),
            list(range(1, 14)) + [16, 17],
            list(range(1, 13)) + [16, 17, 18],
        ]
        metrics = calculate_portfolio_diversity(games)

        self.assertEqual(metrics['max_overlap'], 14)
        self.assertEqual(metrics['shared_by_all'], 12)
        self.assertEqual(metrics['unique_numbers'], 18)
