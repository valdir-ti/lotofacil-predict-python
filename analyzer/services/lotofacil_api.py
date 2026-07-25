from decimal import Decimal, InvalidOperation
import json
from urllib.error import URLError
from urllib.request import Request, urlopen

LOTOFACIL_API_URL = 'https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil'


def _format_brl(value):
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return 'R$ 0,00'

    formatted = f'{decimal_value:,.2f}'
    formatted = formatted.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'R$ {formatted}'


def fetch_next_lotofacil_draw(timeout=4):
    request = Request(
        LOTOFACIL_API_URL,
        headers={
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json',
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except (URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return {
            'has_data': False,
            'next_contest_number': None,
            'next_contest_date': None,
            'next_accumulated_value': None,
        }

    current_contest_number = payload.get('numero')
    next_contest_number = payload.get('numeroConcursoProximo')
    if next_contest_number is None and isinstance(current_contest_number, int):
        next_contest_number = current_contest_number + 1

    next_contest_date = payload.get('dataProximoConcurso')

    next_accumulated = payload.get('valorEstimadoProximoConcurso')
    if next_accumulated is None:
        next_accumulated = payload.get('valorAcumuladoProximoConcurso')

    return {
        'has_data': bool(next_contest_number and next_contest_date),
        'next_contest_number': next_contest_number,
        'next_contest_date': next_contest_date,
        'next_accumulated_value': _format_brl(next_accumulated),
    }
