from decimal import Decimal

from django.test import TestCase, override_settings

from analyzer.models import ConfirmedGame, DailyBetResult
from analyzer.services.bet_confirmation import InvalidGameError, confirm_ai_game


@override_settings(AI_BET_UNIT_PRICE=Decimal('3.50'))
class ConfirmAiGameTests(TestCase):
    def test_confirm_creates_daily_result_and_game(self):
        numbers = list(range(1, 16))

        game = confirm_ai_game(
            play_date='2026-08-05',
            numbers=numbers,
            concurso=3752,
            score=0.88,
            rationale='Jogo de teste.',
        )

        daily_result = DailyBetResult.objects.get(play_date='2026-08-05')
        self.assertEqual(daily_result.invested_amount, Decimal('3.50'))
        self.assertEqual(daily_result.returned_amount, Decimal('0'))
        self.assertEqual(daily_result.concurso, 3752)
        self.assertEqual(game.dezenas, numbers)
        self.assertEqual(game.amount, Decimal('3.50'))
        self.assertEqual(game.source, ConfirmedGame.SOURCE_AI)
        self.assertFalse(game.is_checked)

    def test_second_confirmation_same_day_accumulates_invested_amount(self):
        confirm_ai_game(play_date='2026-08-05', numbers=list(range(1, 16)), concurso=3752)
        confirm_ai_game(play_date='2026-08-05', numbers=list(range(2, 17)), concurso=3752)

        daily_result = DailyBetResult.objects.get(play_date='2026-08-05')
        self.assertEqual(daily_result.invested_amount, Decimal('7.00'))
        self.assertEqual(ConfirmedGame.objects.filter(daily_result=daily_result).count(), 2)

    def test_rejects_wrong_number_count(self):
        with self.assertRaises(InvalidGameError):
            confirm_ai_game(play_date='2026-08-05', numbers=list(range(1, 15)), concurso=3752)

    def test_rejects_duplicate_numbers(self):
        numbers = [1] * 15
        with self.assertRaises(InvalidGameError):
            confirm_ai_game(play_date='2026-08-05', numbers=numbers, concurso=3752)

    def test_rejects_out_of_range_numbers(self):
        numbers = list(range(1, 15)) + [26]
        with self.assertRaises(InvalidGameError):
            confirm_ai_game(play_date='2026-08-05', numbers=numbers, concurso=3752)

    def test_allows_missing_concurso(self):
        game = confirm_ai_game(play_date='2026-08-05', numbers=list(range(1, 16)), concurso=None)
        self.assertIsNone(game.concurso)
