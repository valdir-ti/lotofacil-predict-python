"""Service to confirm AI-generated games and persist them as financial records."""

from decimal import Decimal
import math

from django.conf import settings
from django.db import transaction

from ..models import ConfirmedGame, DailyBetResult
from .game_validation import InvalidGameError, validate_numbers

__all__ = [
    'InvalidGameError',
    'confirm_ai_game',
    'confirm_ai_games',
    'validate_confirmation_payload',
]


def _validate_game_payload(game, index):
    if not isinstance(game, dict):
        raise InvalidGameError(f'Game {index} must be an object.')

    allowed_keys = {'numbers', 'score', 'rationale'}
    unknown_keys = set(game) - allowed_keys
    if unknown_keys:
        raise InvalidGameError(
            f'Game {index} contains unsupported fields: {sorted(unknown_keys)}.'
        )
    if 'numbers' not in game:
        raise InvalidGameError(f'Game {index} must contain numbers.')

    numbers = game['numbers']
    if not isinstance(numbers, list) or any(
        isinstance(value, bool) or not isinstance(value, int) for value in numbers
    ):
        raise InvalidGameError(f'Game {index} numbers must be a list of integers.')

    score = game.get('score')
    if score is not None:
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise InvalidGameError(f'Game {index} score must be a number or null.')
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise InvalidGameError(f'Game {index} score must be between 0 and 1.')

    rationale = game.get('rationale', '')
    if rationale is not None and not isinstance(rationale, str):
        raise InvalidGameError(f'Game {index} rationale must be text or null.')
    if rationale and len(rationale) > 10000:
        raise InvalidGameError(f'Game {index} rationale is too long.')


def validate_confirmation_payload(payload):
    """Validate the public confirmation JSON shape before persistence."""
    if not isinstance(payload, dict):
        raise InvalidGameError('Payload must be a JSON object.')

    allowed_keys = {'games', 'numbers', 'score', 'rationale', 'concurso'}
    unknown_keys = set(payload) - allowed_keys
    if unknown_keys:
        raise InvalidGameError(
            f'Payload contains unsupported fields: {sorted(unknown_keys)}.'
        )
    if 'games' in payload and 'numbers' in payload:
        raise InvalidGameError('Use games or numbers, not both.')

    if 'games' in payload:
        games = payload['games']
        if not isinstance(games, list) or not games:
            raise InvalidGameError('At least one game is required.')
    elif 'numbers' in payload:
        games = [{'numbers': payload.get('numbers'), 'score': payload.get('score'), 'rationale': payload.get('rationale')}]
    else:
        raise InvalidGameError('At least one game is required.')

    max_games = settings.MAX_CONFIRMATION_GAMES
    if len(games) > max_games:
        raise InvalidGameError(f'At most {max_games} games can be confirmed at once.')
    for index, game in enumerate(games, start=1):
        _validate_game_payload(game, index)

    concurso = payload.get('concurso')
    if concurso is not None and (isinstance(concurso, bool) or not isinstance(concurso, int) or concurso <= 0):
        raise InvalidGameError('concurso must be a positive integer or null.')
    return games, concurso


def _parse_concurso(concurso):
    if concurso in (None, ''):
        return None
    if isinstance(concurso, bool):
        raise InvalidGameError(f'Invalid concurso: {concurso!r}')
    try:
        parsed_concurso = int(concurso)
    except (TypeError, ValueError):
        raise InvalidGameError(f'Invalid concurso: {concurso!r}')
    if parsed_concurso <= 0:
        raise InvalidGameError(f'Invalid concurso: {concurso!r}')
    return parsed_concurso


def confirm_ai_games(play_date, games, concurso=None, owner=None):
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
            owner=owner,
            defaults={
                'invested_amount': Decimal('0'),
                'returned_amount': Decimal('0'),
                'concurso': parsed_concurso,
                'owner': owner,
            },
        )
        if owner is not None and daily_result.owner_id != owner.id:
            raise InvalidGameError('The daily result belongs to another user.')
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


def confirm_ai_game(play_date, numbers, concurso=None, score=None, rationale='', owner=None):
    """Confirm a single AI-recommended game. Returns the created ConfirmedGame.

    Kept for backwards compatibility; delegates to ``confirm_ai_games``.
    """
    games = confirm_ai_games(
        play_date,
        [{'numbers': numbers, 'score': score, 'rationale': rationale}],
        concurso=concurso,
        owner=owner,
    )
    return games[0]
