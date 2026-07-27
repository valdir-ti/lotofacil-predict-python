from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
from urllib.error import URLError
from urllib.request import Request, urlopen

LOTOFACIL_API_URL = 'https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil'
LOTOFACIL_API_FALLBACK_URL = 'https://loteriascaixa-api.herokuapp.com/api/lotofacil/latest'


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


def fetch_next_lotofacil_draw(timeout=4):
    for api_url in (LOTOFACIL_API_URL, LOTOFACIL_API_FALLBACK_URL):
        try:
            payload = _fetch_payload(api_url, timeout=timeout)
            contest_data = _extract_contest_data(payload)
            if contest_data['has_data']:
                return contest_data
        except (URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            continue

    return _build_unavailable_response()
