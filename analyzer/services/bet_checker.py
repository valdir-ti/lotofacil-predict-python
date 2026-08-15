"""Service to check pending confirmed games against official Lotofacil results."""

import logging

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from ..models import BetConferenceLock, BetConferenceRun, ConfirmedGame
from .lotofacil_api import fetch_lotofacil_result

logger = logging.getLogger(__name__)

MINIMUM_PRIZE_HITS = 11


def _already_ran_today():
    today = timezone.localdate()
    return BetConferenceRun.objects.filter(checked_at__date=today).exists()


def _check_games_for_concurso(concurso, result):
    drawn_numbers = result['drawn_numbers']
    prize_by_hits = result['prize_by_hits']
    pending_games = ConfirmedGame.objects.select_related('daily_result').filter(
        is_checked=False, concurso=concurso
    )

    checked_count = 0
    contemplated_count = 0

    for game in pending_games:
        hits = sorted(set(game.dezenas) & drawn_numbers)
        hits_count = len(hits)
        is_contemplated = hits_count >= MINIMUM_PRIZE_HITS
        prize_amount = prize_by_hits.get(hits_count) if is_contemplated else None

        with transaction.atomic():
            updated_count = ConfirmedGame.objects.filter(
                pk=game.pk, is_checked=False
            ).update(
                hits_count=hits_count,
                matched_numbers=hits,
                is_contemplated=is_contemplated,
                prize_amount=prize_amount,
                is_checked=True,
                checked_at=timezone.now(),
            )

            # Another worker may have checked this game after the pending
            # queryset was read. Only the winner of this conditional update
            # may apply the financial return and counters.
            if not updated_count:
                continue

            if prize_amount:
                type(game.daily_result).objects.filter(pk=game.daily_result_id).update(
                    returned_amount=F('returned_amount') + prize_amount
                )

        checked_count += 1
        if is_contemplated:
            contemplated_count += 1

    return checked_count, contemplated_count


def check_pending_games(force=False):
    """Check all pending (unchecked) confirmed games against official results.

    Skips the run if it already executed today, unless force=True. Always
    logs a BetConferenceRun entry when it actually performs a check.
    Returns {'ran': bool, 'checked_count': int, 'contemplated_count': int}.
    """
    # get_or_create makes the lock row available on fresh installations;
    # select_for_update serializes workers on databases that support row locks.
    BetConferenceLock.objects.get_or_create(name='global')
    with transaction.atomic():
        BetConferenceLock.objects.select_for_update().get(name='global')

        if not force and _already_ran_today():
            return {'ran': False, 'checked_count': 0, 'contemplated_count': 0}

        pending_concursos = (
            ConfirmedGame.objects.filter(is_checked=False, concurso__isnull=False)
            .values_list('concurso', flat=True)
            .distinct()
        )

        total_checked = 0
        total_contemplated = 0

        for concurso in pending_concursos:
            try:
                result = fetch_lotofacil_result(concurso)
            except Exception:
                logger.exception('Falha ao buscar resultado do concurso %s.', concurso)
                continue

            if not result['has_data']:
                continue

            checked_count, contemplated_count = _check_games_for_concurso(concurso, result)
            total_checked += checked_count
            total_contemplated += contemplated_count

        BetConferenceRun.objects.create(
            triggered_by=BetConferenceRun.TRIGGER_MANUAL if force else BetConferenceRun.TRIGGER_AUTO,
            checked_count=total_checked,
            contemplated_count=total_contemplated,
        )

        return {'ran': True, 'checked_count': total_checked, 'contemplated_count': total_contemplated}
