from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from analyzer.models import BetConferenceRun, ConfirmedGame, DailyBetResult
from analyzer.services.bet_checker import check_pending_games


def _make_pending_game(numbers, concurso=3752, play_date='2026-08-05'):
    daily_result = DailyBetResult.objects.create(
        play_date=play_date,
        concurso=concurso,
        invested_amount=Decimal('3.50'),
        returned_amount=Decimal('0'),
    )
    return ConfirmedGame.objects.create(
        daily_result=daily_result,
        dezenas=numbers,
        concurso=concurso,
        amount=Decimal('3.50'),
        source=ConfirmedGame.SOURCE_AI,
    )


class CheckPendingGamesTests(TestCase):
    @patch('analyzer.services.bet_checker.fetch_lotofacil_result')
    def test_marks_contemplated_game_and_updates_returned_amount(self, mock_fetch):
        game = _make_pending_game(list(range(1, 16)))
        mock_fetch.return_value = {
            'has_data': True,
            'drawn_numbers': set(range(1, 16)),
            'prize_by_hits': {15: Decimal('500000.00')},
        }

        result = check_pending_games(force=True)

        game.refresh_from_db()
        self.assertTrue(game.is_checked)
        self.assertTrue(game.is_contemplated)
        self.assertEqual(game.hits_count, 15)
        self.assertEqual(sorted(game.matched_numbers), list(range(1, 16)))
        self.assertEqual(game.prize_amount, Decimal('500000.00'))

        daily_result = game.daily_result
        daily_result.refresh_from_db()
        self.assertEqual(daily_result.returned_amount, Decimal('500000.00'))

        self.assertEqual(result['checked_count'], 1)
        self.assertEqual(result['contemplated_count'], 1)
        self.assertEqual(BetConferenceRun.objects.count(), 1)

    @patch('analyzer.services.bet_checker.fetch_lotofacil_result')
    def test_marks_non_contemplated_game_without_touching_returned_amount(self, mock_fetch):
        game = _make_pending_game(list(range(1, 16)))
        mock_fetch.return_value = {
            'has_data': True,
            'drawn_numbers': set(range(11, 26)),
            'prize_by_hits': {},
        }

        check_pending_games(force=True)

        game.refresh_from_db()
        self.assertTrue(game.is_checked)
        self.assertFalse(game.is_contemplated)
        self.assertEqual(game.hits_count, 5)
        self.assertIsNone(game.prize_amount)

        daily_result = game.daily_result
        daily_result.refresh_from_db()
        self.assertEqual(daily_result.returned_amount, Decimal('0'))

    @patch('analyzer.services.bet_checker.fetch_lotofacil_result')
    def test_skips_when_result_not_available_yet(self, mock_fetch):
        game = _make_pending_game(list(range(1, 16)))
        mock_fetch.return_value = {'has_data': False, 'drawn_numbers': None, 'prize_by_hits': {}}

        check_pending_games(force=True)

        game.refresh_from_db()
        self.assertFalse(game.is_checked)

    @patch('analyzer.services.bet_checker.fetch_lotofacil_result')
    def test_does_not_run_twice_in_the_same_day_unless_forced(self, mock_fetch):
        _make_pending_game(list(range(1, 16)))
        mock_fetch.return_value = {
            'has_data': True,
            'drawn_numbers': set(range(1, 16)),
            'prize_by_hits': {15: Decimal('500000.00')},
        }

        first_result = check_pending_games(force=False)
        second_result = check_pending_games(force=False)

        self.assertTrue(first_result['ran'])
        self.assertFalse(second_result['ran'])
        self.assertEqual(mock_fetch.call_count, 1)
        self.assertEqual(BetConferenceRun.objects.count(), 1)

    @patch('analyzer.services.bet_checker.fetch_lotofacil_result')
    def test_forced_recheck_does_not_duplicate_financial_return(self, mock_fetch):
        game = _make_pending_game(list(range(1, 16)))
        mock_fetch.return_value = {
            'has_data': True,
            'drawn_numbers': set(range(1, 16)),
            'prize_by_hits': {15: Decimal('500000.00')},
        }

        first_result = check_pending_games(force=True)
        second_result = check_pending_games(force=True)

        game.refresh_from_db()
        game.daily_result.refresh_from_db()
        self.assertEqual(first_result['checked_count'], 1)
        self.assertEqual(second_result['checked_count'], 0)
        self.assertEqual(game.daily_result.returned_amount, Decimal('500000.00'))

    @patch('analyzer.services.bet_checker.fetch_lotofacil_result')
    def test_ignores_games_without_concurso(self, mock_fetch):
        daily_result = DailyBetResult.objects.create(
            play_date='2026-08-05',
            invested_amount=Decimal('3.50'),
            returned_amount=Decimal('0'),
        )
        game = ConfirmedGame.objects.create(
            daily_result=daily_result,
            dezenas=list(range(1, 16)),
            concurso=None,
            amount=Decimal('3.50'),
        )

        check_pending_games(force=True)

        game.refresh_from_db()
        self.assertFalse(game.is_checked)
        mock_fetch.assert_not_called()
