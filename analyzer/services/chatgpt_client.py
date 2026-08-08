import json
from typing import Any, Dict, List

try:
    from openai import OpenAI
    _HAS_OPENAI = True
except Exception:
    OpenAI = None
    _HAS_OPENAI = False
from django.conf import settings

from .excel_parser import parse_lotofacil_excel, DrawRecord
from .features import calculate_number_features, validate_game
from .metrics import (
    _pick_diverse_candidates,
    calculate_game_score,
    generate_recommended_games,
)


def _response_schema(game_count: int, max_draws: int) -> Dict[str, Any]:
    return {
        'type': 'object',
        'additionalProperties': False,
        'required': ['meta', 'stats', 'raw_arrays', 'recommended_games'],
        'properties': {
            'meta': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['used_draws', 'notes'],
                'properties': {
                    'used_draws': {'type': 'integer'},
                    'notes': {'type': 'string'},
                },
            },
            'stats': {'type': 'object', 'additionalProperties': False, 'properties': {}},
            'raw_arrays': {'type': 'object', 'additionalProperties': False, 'properties': {}},
            'recommended_games': {
                'type': 'array',
                'minItems': game_count,
                'maxItems': game_count,
                'items': {
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['numbers', 'score', 'rationale'],
                    'properties': {
                        'numbers': {
                            'type': 'array',
                            'minItems': 15,
                            'maxItems': 15,
                            'items': {'type': 'integer'},
                        },
                        'score': {'type': 'number'},
                        'rationale': {'type': 'string'},
                    },
                },
            },
        },
    }


def _build_prompt(game_count: int, max_draws: int) -> str:
    return (
        f"Faça uma análise dos últimos {max_draws} concursos válidos da Lotofácil enviados "
        "nos objetos JSON draws e raw_arrays. draws contém as 15 dezenas de cada concurso, "
        "em ordem cronológica; raw_arrays contém métricas calculadas no servidor.\n\n"
        "Analise frequência histórica, recência, atraso, repetição, sequências, grupos, linhas, "
        "colunas, soma, paridade, moldura, padrões raros e tendências estruturais. Use as métricas "
        "calculadas pelo servidor e não invente nem recalcule desnecessariamente métricas já fornecidas. "
        f"Atue como camada de análise e seleção para montar {game_count} jogos equilibrados candidatos.\n\n"
        "Priorize o pool das 20 dezenas com maior number_score, aproximadamente 10 dezenas de moldura "
        "e aproximadamente 9 dezenas repetidas do último concurso. Busque diversidade entre os jogos. "
        "Essas são preferências heurísticas, não evidências de aumento da probabilidade matemática. "
        "As regras determinísticas e o score final serão recalculados e validados pelo Python.\n\n"
        "Retorne somente um objeto JSON que siga exatamente o schema informado. O objeto deve "
        "conter meta, stats, raw_arrays e recommended_games. stats e raw_arrays devem ser objetos "
        "vazios. meta deve conter used_draws e notes. Cada item de recommended_games deve conter "
        "numbers com 15 inteiros distintos de 1 a 25, score numérico e rationale textual. "
        "Escreva notes e rationale exclusivamente em português brasileiro. "
        "Não inclua Markdown, texto fora do JSON ou chaves alternativas.\n\n"
    )


def _draws_to_serializable(draws: List[DrawRecord]) -> List[List[int]]:
    return [draw.dezenas for draw in draws]


def _validate_game_entry(entry: Dict[str, Any]) -> bool:
    try:
        numbers = entry.get('numbers')
        if not isinstance(numbers, list) or len(numbers) != 15:
            return False
        if len(set(numbers)) != 15:
            return False
        for n in numbers:
            if not isinstance(n, int) or n < 1 or n > 25:
                return False
        # score and rationale
        float(entry.get('score', 0))
        rationale = entry.get('rationale')
        if not isinstance(rationale, str):
            return False
        return True
    except Exception:
        return False


def _compute_local_arrays(draws: List[DrawRecord]) -> Dict[str, Any]:
    total_draws = len(draws)
    frequency = [0] * 25
    last_seen_gap = [total_draws] * 25
    sums_per_draw: List[int] = []
    even_distribution: Dict[str, int] = {}
    lines = [0] * 5
    columns = [0] * 5

    for idx, draw in enumerate(draws):
        s = sum(draw.dezenas)
        sums_per_draw.append(s)
        seen = set(draw.dezenas)
        for n in seen:
            frequency[n - 1] += 1
            last_seen_gap[n - 1] = total_draws - idx - 1
            # line/column mapping: rows of 5
            r = (n - 1) // 5
            c = (n - 1) % 5
            lines[r] += 1
            columns[c] += 1

        even = len([n for n in draw.dezenas if n % 2 == 0])
        odd = 15 - even
        key = f"{even}P-{odd}I"
        even_distribution[key] = even_distribution.get(key, 0) + 1

    return {
        'frequency': frequency,
        'last_seen_gap': last_seen_gap,
        'sums_per_draw': sums_per_draw,
        'lines': lines,
        'columns': columns,
        'even_distribution': even_distribution,
    }


def _fallback_game_entry(game: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'numbers': sorted(game['numbers']),
        'score': float(game['score']),
        'rationale': 'Candidato gerado e validado deterministicamente pelo Python.',
    }


def _finalize_games(
    model_games: Any,
    draws: List[DrawRecord],
    game_count: int,
) -> List[Dict[str, Any]]:
    """Filter LLM candidates, recalculate scores and fill from the local generator."""
    number_features = calculate_number_features(draws)
    last_draw = set(draws[-1].dezenas)
    candidate_pool: List[Dict[str, Any]] = []
    seen: set[tuple[int, ...]] = set()

    if isinstance(model_games, list):
        for entry in model_games:
            if not isinstance(entry, dict) or not _validate_game_entry(entry):
                continue
            numbers = sorted(entry['numbers'])
            valid, _reason = validate_game(numbers, last_draw)
            key = tuple(numbers)
            if not valid or key in seen:
                continue
            score = calculate_game_score(
                numbers,
                draws,
                number_features,
            )
            candidate_pool.append({
                'numbers': numbers,
                'score': score,
                'intrinsic_score': score,
                'rationale': entry['rationale'],
            })
            seen.add(key)

    for local_game in generate_recommended_games(draws, target_count=game_count):
        key = tuple(local_game['numbers'])
        if key in seen:
            continue
        candidate_pool.append(_fallback_game_entry(local_game) | {
            'intrinsic_score': float(local_game['score']),
        })
        seen.add(key)

    selected = _pick_diverse_candidates(candidate_pool, game_count)
    finalized = [
        {
            'numbers': game['numbers'],
            'score': game['intrinsic_score'],
            'rationale': game['rationale'],
        }
        for game in selected
    ]

    if len(finalized) != game_count:
        raise ValueError('Nao foi possivel montar a quantidade configurada de jogos validos.')
    return finalized


def generate_games_from_excel_file(
    uploaded_file,
    model: str | None = None,
    max_draws: int | None = None,
    game_count: int | None = None,
) -> Dict[str, Any]:
    """Parse an Excel file, call the configured LLM, and validate its game JSON.

    Returns dict: {'model_result': parsed_json, 'raw_arrays': {...}}
    """
    max_draws = max_draws if max_draws is not None else settings.LLM_MAX_DRAWS
    game_count = game_count if game_count is not None else settings.LLM_GAME_COUNT
    if max_draws < 1 or game_count < 1:
        raise ValueError('LLM_MAX_DRAWS and LLM_GAME_COUNT must be positive integers.')

    parse_result = parse_lotofacil_excel(uploaded_file)
    draws = parse_result.draws[-max_draws:]
    if not draws:
        raise ValueError('No valid draws were found in the uploaded file.')
    draws_json = _draws_to_serializable(draws)

    raw_arrays = _compute_local_arrays(draws)
    number_features = calculate_number_features(draws)

    payload = {
        'draws': draws_json,
        'raw_arrays': {
            'frequency': raw_arrays['frequency'],
            'last_seen_gap': raw_arrays['last_seen_gap'],
            'sums_per_draw': raw_arrays['sums_per_draw'],
            'lines': raw_arrays['lines'],
            'columns': raw_arrays['columns'],
            'even_distribution': raw_arrays['even_distribution'],
            'number_features': number_features,
        },
    }

    prompt = _build_prompt(game_count, max_draws) + json.dumps(payload, ensure_ascii=False)

    provider = settings.LLM_PROVIDER
    if provider != 'openai':
        raise ValueError('LLM_PROVIDER must be "openai".')

    api_key = getattr(settings, 'OPENAI_API_KEY', None)
    if not api_key:
        raise ValueError('OPENAI_API_KEY is not configured in settings.')
    if not _HAS_OPENAI:
        raise ImportError('The openai package is required to generate predictions.')

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model or settings.OPENAI_MODEL,
        input=prompt,
        max_output_tokens=1200,
        text={
            'format': {
                'type': 'json_schema',
                'name': 'lotofacil_recommendations',
                'strict': True,
                'schema': _response_schema(game_count, max_draws),
            },
        },
    )
    text = getattr(response, 'output_text', None)

    if not text:
        raise ValueError(f'Empty response from {provider}.')

    try:
        result = json.loads(text)
    except Exception as exc:
        raise ValueError(f'Failed to parse model response as JSON: {exc}\nRaw response: {text}')

    if not isinstance(result, dict) or 'recommended_games' not in result:
        returned_keys = sorted(result.keys()) if isinstance(result, dict) else []
        raise ValueError(
            'Model response does not match the required recommended_games schema. '
            f'Returned top-level keys: {returned_keys}; recommended_games type: None; count: None.'
        )

    games = result.get('recommended_games')
    finalized_games = _finalize_games(games, draws, game_count)
    if not isinstance(result, dict):
        result = {}
    result['meta'] = {
        'used_draws': len(draws),
        'notes': result.get('meta', {}).get('notes', '')
        if isinstance(result.get('meta'), dict)
        else '',
    }
    result['stats'] = {}
    result['raw_arrays'] = {}
    result['recommended_games'] = finalized_games

    return {
        'model_result': result,
        'raw_arrays': payload['raw_arrays'],
    }
