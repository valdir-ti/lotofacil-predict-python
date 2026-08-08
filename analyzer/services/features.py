"""Feature extraction for numbers and candidate games."""

from collections import Counter
from typing import Any

from .excel_parser import DrawRecord
from .lottery_rules import (
    LOTTERY_RULES,
    MOLDURA_NUMBERS,
    SCORING_WEIGHTS,
)


def _scale(value: float, maximum: float, reverse: bool = False) -> float:
    if maximum <= 0:
        return 100.0
    result = min(100.0, max(0.0, (value / maximum) * 100.0))
    return round(100.0 - result if reverse else result, 2)


def calculate_number_features(draws: list[DrawRecord]) -> dict[int, dict[str, Any]]:
    """Calculate number features using only the supplied historical draws."""
    if not draws:
        raise ValueError('Nao ha concursos para calcular features.')

    total = len(draws)
    recent_draws = draws[-LOTTERY_RULES['recent_window']:]
    last_10_draws = draws[-LOTTERY_RULES['last_10_window']:]
    historical = Counter(number for draw in draws for number in draw.dezenas)
    recent = Counter(number for draw in recent_draws for number in draw.dezenas)
    last_10 = Counter(number for draw in last_10_draws for number in draw.dezenas)
    last_seen = {number: total for number in range(1, 26)}

    for index, draw in enumerate(draws):
        for number in set(draw.dezenas):
            last_seen[number] = total - index - 1

    max_historical = max(historical.values(), default=0)
    max_recent = max(recent.values(), default=0)
    max_last_10 = max(last_10.values(), default=0)
    max_delay = LOTTERY_RULES['delay_cap']
    features: dict[int, dict[str, Any]] = {}

    for number in range(1, 26):
        delay = min(last_seen[number], max_delay)
        historical_score = _scale(historical[number], max_historical)
        recent_score = _scale(recent[number], max_recent)
        last_10_score = _scale(last_10[number], max_last_10)
        delay_score = _scale(delay, max_delay)
        frame_score = 100.0 if number in MOLDURA_NUMBERS else 0.0
        number_score = (
            historical_score * SCORING_WEIGHTS['historical_frequency']
            + recent_score * SCORING_WEIGHTS['recent_frequency']
            + last_10_score * SCORING_WEIGHTS['last_10_frequency']
            + delay_score * SCORING_WEIGHTS['delay']
            + frame_score * SCORING_WEIGHTS['frame_structure']
        )
        features[number] = {
            'historical_frequency': historical[number],
            'recent_frequency': recent[number],
            'last_10_frequency': last_10[number],
            'last_seen_gap': last_seen[number],
            'historical_frequency_score': historical_score,
            'recent_frequency_score': recent_score,
            'last_10_score': last_10_score,
            'delay_score': delay_score,
            'frame_score': frame_score,
            'number_score': round(number_score, 2),
        }

    return features


def calculate_game_features(numbers: list[int], last_draw: set[int]) -> dict[str, Any]:
    """Calculate structural features for one 15-number candidate."""
    ordered = sorted(numbers)
    even_count = sum(number % 2 == 0 for number in ordered)
    frame_count = sum(number in MOLDURA_NUMBERS for number in ordered)
    repeat_last = len(set(ordered).intersection(last_draw))
    lines = [0] * 5
    columns = [0] * 5
    for number in ordered:
        lines[(number - 1) // 5] += 1
        columns[(number - 1) % 5] += 1

    sequence_points = 0
    longest_sequence = 1
    current_sequence = 1
    for index in range(1, len(ordered)):
        if ordered[index] == ordered[index - 1] + 1:
            current_sequence += 1
        else:
            sequence_points += current_sequence if current_sequence >= 2 else 0
            longest_sequence = max(longest_sequence, current_sequence)
            current_sequence = 1
    sequence_points += current_sequence if current_sequence >= 2 else 0
    longest_sequence = max(longest_sequence, current_sequence)

    return {
        'numbers': ordered,
        'even_count': even_count,
        'odd_count': len(ordered) - even_count,
        'frame_count': frame_count,
        'moldura_count': frame_count,
        'repeat_last': repeat_last,
        'sum': sum(ordered),
        'lines': lines,
        'columns': columns,
        'sequence_points': sequence_points,
        'longest_sequence': longest_sequence,
    }


def validate_game(numbers: list[int], last_draw: set[int]) -> tuple[bool, str]:
    """Deterministically validate all hard composition rules."""
    if len(numbers) != LOTTERY_RULES['game_size']:
        return False, 'O jogo deve possuir exatamente 15 dezenas.'
    if len(set(numbers)) != len(numbers):
        return False, 'O jogo possui dezenas repetidas.'
    if any(number < LOTTERY_RULES['number_min'] or number > LOTTERY_RULES['number_max'] for number in numbers):
        return False, 'O jogo possui dezenas fora do intervalo 1-25.'

    features = calculate_game_features(numbers, last_draw)
    if not LOTTERY_RULES['even_min'] <= features['even_count'] <= LOTTERY_RULES['even_max']:
        return False, 'O jogo deve possuir exatamente 7 pares e 8 impares.'
    if not LOTTERY_RULES['frame_min'] <= features['frame_count'] <= LOTTERY_RULES['frame_max']:
        return False, 'A quantidade de dezenas da moldura deve estar entre 9 e 11.'
    if not LOTTERY_RULES['repeat_min'] <= features['repeat_last'] <= LOTTERY_RULES['repeat_max']:
        return False, 'A repeticao do ultimo concurso deve estar entre 7 e 11.'
    return True, ''
