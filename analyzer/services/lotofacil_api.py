from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
import logging
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.conf import settings

LOTOFACIL_API_URL = 'https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil'
LOTOFACIL_API_FALLBACK_URL = 'https://loteriascaixa-api.herokuapp.com/api/lotofacil/latest'
logger = logging.getLogger(__name__)


def _normalize_contest_date(value):
    if value is None:
        return None

    if not isinstance(value, str):
        value = str(value)

    raw_value = value.strip()
    if not raw_value:
        return None

    # API da Caixa costuma retornar DD/MM/YYYY, mas aceitamos alguns formatos
    # comuns para manter compatibilidade em caso de ajuste no endpoint.
    for date_format in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
        try:
            parsed = datetime.strptime(raw_value, date_format).date()
            return parsed.strftime('%d/%m/%Y')
        except ValueError:
            continue

    return None


def _format_brl(value):
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return 'R$ 0,00'

    formatted = f'{decimal_value:,.2f}'
    formatted = formatted.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'R$ {formatted}'


def _build_unavailable_response():
    return {
        'has_data': False,
        'next_contest_number': None,
        'next_contest_date': None,
        'next_accumulated_value': None,
    }


def _build_request(url):
    return Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://loterias.caixa.gov.br/',
            'Origin': 'https://loterias.caixa.gov.br',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
        },
    )


def _fetch_payload(url, timeout):
    request = _build_request(url)
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode('utf-8-sig'))

    if not isinstance(payload, dict):
        raise ValueError('Payload da API nao e um objeto JSON.')

    return payload


def _extract_contest_data(payload):
    current_contest_number = payload.get('numero') or payload.get('concurso')
    next_contest_number = payload.get('numeroConcursoProximo') or payload.get('proximoConcurso')
    if next_contest_number is None and isinstance(current_contest_number, int):
        next_contest_number = current_contest_number + 1

    next_contest_date = _normalize_contest_date(payload.get('dataProximoConcurso'))

    next_accumulated = payload.get('valorEstimadoProximoConcurso')
    if next_accumulated is None:
        next_accumulated = payload.get('valorAcumuladoProximoConcurso')

    return {
        'has_data': bool(next_contest_number and next_contest_date),
        'next_contest_number': next_contest_number,
        'next_contest_date': next_contest_date,
        'next_accumulated_value': _format_brl(next_accumulated),
    }


def _request_timeout(timeout):
    if timeout is not None:
        return timeout
    return settings.LOTOFACIL_API_TIMEOUT_SECONDS


def fetch_next_lotofacil_draw(timeout=None):
    timeout = _request_timeout(timeout)
    for api_url in (LOTOFACIL_API_URL, LOTOFACIL_API_FALLBACK_URL):
        try:
            payload = _fetch_payload(api_url, timeout=timeout)
            contest_data = _extract_contest_data(payload)
            if contest_data['has_data']:
                return contest_data
            logger.warning('API da Lotofácil retornou dados incompletos: %s', api_url)
        except (URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            logger.warning('Falha ao consultar API da Lotofácil (%s): %s', api_url, exc)
            continue

    return _build_unavailable_response()


# Lotofacil pays prizes for contestants who hit 11 to 15 numbers. The official
# API returns a "faixa" (tier) per prize bracket, ordered from the highest hit
# count (faixa 1 = 15 hits) down to the lowest (faixa 5 = 11 hits). This
# mapping should be double-checked against a live API response, since Caixa
# may adjust the payload shape without notice.
_PRIZE_TIER_TO_HITS = {1: 15, 2: 14, 3: 13, 4: 12, 5: 11}


def _parse_drawn_numbers(payload):
    raw_numbers = (
        payload.get('dezenasSorteadasOrdemSorteio')
        or payload.get('listaDezenas')
        or payload.get('dezenas')
    )
    if not raw_numbers:
        return None

    numbers = set()
    for value in raw_numbers:
        try:
            numbers.add(int(value))
        except (TypeError, ValueError):
            continue

    return numbers if len(numbers) == 15 else None


def _parse_prize_by_hits(payload):
    raw_tiers = payload.get('listaRateioPremio') or payload.get('premiacoes') or []
    prize_by_hits = {}

    for tier in raw_tiers:
        if not isinstance(tier, dict):
            continue

        faixa = tier.get('faixa')
        hits = _PRIZE_TIER_TO_HITS.get(faixa)
        if hits is None:
            continue

        prize_value = tier.get('valorPremio')
        winners = tier.get('numeroDeGanhadores', tier.get('ganhadores'))
        try:
            winners_count = int(winners) if winners is not None else None
        except (TypeError, ValueError):
            winners_count = None

        # A prize tier with zero winners has no real payout to consider.
        if winners_count == 0:
            continue

        try:
            prize_by_hits[hits] = Decimal(str(prize_value))
        except (InvalidOperation, TypeError):
            continue

    return prize_by_hits


def _build_result_unavailable_response():
    return {'has_data': False, 'drawn_numbers': None, 'prize_by_hits': {}}


def _extract_contest_number(payload):
    value = payload.get('numero') or payload.get('concurso')
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def fetch_lotofacil_result(concurso, timeout=None):
    """Fetch the official result for an already-drawn Lotofacil contest.

    Returns {'has_data': bool, 'drawn_numbers': set[int] | None, 'prize_by_hits': dict[int, Decimal]}.
    """
    timeout = _request_timeout(timeout)
    requested_contest = int(concurso)
    for base_url in (LOTOFACIL_API_URL, LOTOFACIL_API_FALLBACK_URL.rsplit('/latest', 1)[0]):
        api_url = f'{base_url}/{concurso}'
        try:
            payload = _fetch_payload(api_url, timeout=timeout)
        except (URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                'Falha ao consultar resultado do concurso %s (%s): %s',
                requested_contest,
                api_url,
                exc,
            )
            continue

        returned_contest = _extract_contest_number(payload)
        if returned_contest != requested_contest:
            logger.warning(
                'API retornou concurso inesperado: solicitado=%s retornado=%s (%s)',
                requested_contest,
                returned_contest,
                api_url,
            )
            continue

        drawn_numbers = _parse_drawn_numbers(payload)
        if not drawn_numbers:
            logger.warning(
                'API não retornou 15 dezenas para o concurso %s (%s)',
                requested_contest,
                api_url,
            )
            continue

        return {
            'has_data': True,
            'drawn_numbers': drawn_numbers,
            'prize_by_hits': _parse_prize_by_hits(payload),
        }

    return _build_result_unavailable_response()
