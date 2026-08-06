"""Service to confirm AI-generated games and persist them as financial records."""

from decimal import Decimal

from django.conf import settings
from django.db import transaction

from ..models import ConfirmedGame, DailyBetResult
from .game_validation import InvalidGameError, validate_numbers

__all__ = ['InvalidGameError', 'confirm_ai_game', 'confirm_ai_games']


def _parse_concurso(concurso):
    if concurso in (None, ''):
        return None
    try:
        parsed_concurso = int(concurso)
    except (TypeError, ValueError):
        raise InvalidGameError(f'Invalid concurso: {concurso!r}')
    if parsed_concurso <= 0:
        raise InvalidGameError(f'Invalid concurso: {concurso!r}')
    return parsed_concurso


def confirm_ai_games(play_date, games, concurso=None):
    """Confirm a batch of AI-recommended games in a single financial movement.

    ``games`` is a list of dicts with keys ``numbers`` (required), ``score``
    and ``rationale`` (optional). All games are validated before anything is
    persisted. The day's invested amount is incremented once by
    ``unit_price * len(games)`` and one ``ConfirmedGame`` row is created per
    game.

    Returns the list of created ConfirmedGame instances.
    """
    if not games:
        raise InvalidGameError('At least one game is required.')

    parsed_games = []
    for game in games:
        dezenas = validate_numbers(game.get('numbers'))
        parsed_games.append(
            {
                'dezenas': dezenas,
                'score': game.get('score'),
                'rationale': game.get('rationale') or '',
            }
        )

    parsed_concurso = _parse_concurso(concurso)
    unit_price = settings.AI_BET_UNIT_PRICE
    total_amount = unit_price * len(parsed_games)

    with transaction.atomic():
        daily_result, _created = DailyBetResult.active_objects.active().get_or_create(
            play_date=play_date,
            defaults={
                'invested_amount': Decimal('0'),
                'returned_amount': Decimal('0'),
                'concurso': parsed_concurso,
            },
        )
        daily_result.invested_amount = daily_result.invested_amount + total_amount
        if not daily_result.concurso and parsed_concurso:
            daily_result.concurso = parsed_concurso
        daily_result.save(update_fields=['invested_amount', 'concurso', 'updated_at'])

        created_games = [
            ConfirmedGame.objects.create(
                daily_result=daily_result,
                dezenas=parsed['dezenas'],
                concurso=parsed_concurso,
                amount=unit_price,
                source=ConfirmedGame.SOURCE_AI,
                score=parsed['score'],
                rationale=parsed['rationale'],
            )
            for parsed in parsed_games
        ]

    return created_games


def confirm_ai_game(play_date, numbers, concurso=None, score=None, rationale=''):
    """Confirm a single AI-recommended game. Returns the created ConfirmedGame.

    Kept for backwards compatibility; delegates to ``confirm_ai_games``.
    """
    games = confirm_ai_games(
        play_date,
        [{'numbers': numbers, 'score': score, 'rationale': rationale}],
        concurso=concurso,
    )
    return games[0]
