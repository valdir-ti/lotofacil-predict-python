from dataclasses import dataclass
from itertools import combinations

from .excel_parser import DrawRecord
from .features import calculate_game_features, calculate_number_features, validate_game
from .lottery_rules import (
    GAME_SCORING_WEIGHTS,
    LOTTERY_RULES,
    MOLDURA_NUMBERS,
    OVERLAP_PENALTIES,
)


@dataclass
class NumberMetric:
    dezena: int
    frequencia: int
    percentual: float


def _safe_repeat_target(average_repeats: float) -> int:
    rounded = int(round(average_repeats))
    return max(LOTTERY_RULES['repeat_min'], min(LOTTERY_RULES['repeat_max'], rounded))


def _score_preference(value: float, preferred: float, low: float, high: float) -> float:
    if value < low or value > high:
        return 0.0
    distance = abs(value - preferred)
    maximum_distance = max(preferred - low, high - preferred, 1)
    return round(max(0.0, 100.0 - (distance / maximum_distance * 40.0)), 2)


def _distribution_score(values: list[int]) -> float:
    # 15 numbers across five lines/columns: three per group is the neutral center.
    score = 100.0 - sum(abs(value - 3) for value in values) * 10.0
    return round(max(0.0, score), 2)


def _sequence_score(sequence_points: int, longest_sequence: int) -> float:
    # Structural preference only; no sequence is treated as predictive.
    penalty = abs(sequence_points - 8) * 4 + max(0, longest_sequence - 5) * 8
    return round(max(0.0, 100.0 - penalty), 2)


def calculate_game_score(
    numbers: list[int],
    draws: list[DrawRecord],
    number_features: dict[int, dict],
) -> float:
    """Return the intrinsic 0-100 score for one candidate, independent of a portfolio."""
    features = calculate_game_features(numbers, set(draws[-1].dezenas))
    number_score = sum(number_features[number]['number_score'] for number in numbers) / len(numbers)
    frame_score = _score_preference(
        features['frame_count'],
        LOTTERY_RULES['preferred_frame'],
        LOTTERY_RULES['frame_min'],
        LOTTERY_RULES['frame_max'],
    )
    repeat_score = _score_preference(
        features['repeat_last'],
        LOTTERY_RULES['preferred_repeat'],
        LOTTERY_RULES['repeat_min'],
        LOTTERY_RULES['repeat_max'],
    )
    parity_score = 100.0 if features['even_count'] == LOTTERY_RULES['even_min'] else 0.0
    sum_score = max(0.0, 100.0 - abs(features['sum'] - LOTTERY_RULES['target_sum']) * 2.0)
    scores = {
        'numbers': number_score,
        'frame': frame_score,
        'repeat': repeat_score,
        'parity': parity_score,
        'sum': sum_score,
        'lines': _distribution_score(features['lines']),
        'columns': _distribution_score(features['columns']),
        'sequences': _sequence_score(features['sequence_points'], features['longest_sequence']),
    }
    weight_total = sum(GAME_SCORING_WEIGHTS.values())
    return round(
        sum(scores[name] * weight for name, weight in GAME_SCORING_WEIGHTS.items())
        / weight_total,
        2,
    )


def calculate_overlap(candidate: list[int], existing_game: list[int]) -> int:
    return len(set(candidate).intersection(existing_game))


def calculate_diversity_penalty(overlap: int) -> float:
    """Return a progressive selection penalty; overlap above 13 is invalid."""
    if overlap > LOTTERY_RULES['max_game_overlap']:
        return float('inf')
    return OVERLAP_PENALTIES.get(overlap, 0.0)


def calculate_diversity_adjusted_score(
    intrinsic_score: float,
    overlaps: list[int],
) -> tuple[float, float]:
    """Apply the worst pairwise penalty without changing intrinsic scoring."""
    if not overlaps:
        return round(intrinsic_score, 2), 0.0
    penalties = [calculate_diversity_penalty(overlap) for overlap in overlaps]
    penalty = max(penalties)
    if penalty == float('inf'):
        return float('-inf'), penalty
    adjusted = max(0.0, intrinsic_score - penalty)
    return round(adjusted, 2), round(penalty, 2)


def _build_candidate_pool(number_features: dict[int, dict]) -> list[int]:
    ordered = sorted(
        number_features,
        key=lambda number: (-number_features[number]['number_score'], number),
    )
    return ordered[:LOTTERY_RULES['preferred_pool_size']]


def generate_recommended_games(
    draws: list[DrawRecord],
    target_count: int = 3,
    selection_mode: str = 'progressive',
) -> list[dict]:
    """Generate deterministic, valid games from historical features."""
    if not draws:
        raise ValueError('Nao ha concursos para analisar.')
    number_features = calculate_number_features(draws)
    last_draw = set(draws[-1].dezenas)
    pool = _build_candidate_pool(number_features)
    candidates = _generate_candidates(pool, draws, number_features, last_draw)
    if len(candidates) < target_count:
        # The Top 20 is preferential, not an absolute restriction.
        candidates = _generate_candidates(list(range(1, 26)), draws, number_features, last_draw)
    if selection_mode == 'progressive':
        return _pick_diverse_candidates(candidates, target_count)
    if selection_mode == 'legacy':
        return _pick_legacy_candidates(candidates, target_count)
    raise ValueError(f'Modo de selecao desconhecido: {selection_mode}')


def _generate_candidates(
    pool: list[int],
    draws: list[DrawRecord],
    number_features: dict[int, dict],
    last_draw: set[int],
) -> list[dict]:
    candidates: list[dict] = []
    for combination in combinations(sorted(pool), LOTTERY_RULES['game_size']):
        numbers = list(combination)
        valid, _reason = validate_game(numbers, last_draw)
        if not valid:
            continue
        game_features = calculate_game_features(numbers, last_draw)
        score = calculate_game_score(numbers, draws, number_features)
        candidates.append({
            'numbers': numbers,
            'score': score,
            'intrinsic_score': score,
            'diversity_penalty': 0.0,
            'selection_score': score,
            'even_count': game_features['even_count'],
            'odd_count': game_features['odd_count'],
            'moldura_count': game_features['frame_count'],
            'center_count': LOTTERY_RULES['game_size'] - game_features['frame_count'],
            'repeat_last': game_features['repeat_last'],
            'sequence_points': game_features['sequence_points'],
            'sum': game_features['sum'],
            'lines': game_features['lines'],
            'columns': game_features['columns'],
        })
    return sorted(candidates, key=lambda item: (-item['score'], item['numbers']))


def _pick_diverse_candidates(candidates: list[dict], target_count: int) -> list[dict]:
    selected: list[dict] = []
    remaining = list(candidates)
    while remaining and len(selected) < target_count:
        if not selected:
            chosen = remaining[0]
            chosen['diversity_penalty'] = 0.0
            chosen['selection_score'] = chosen['intrinsic_score']
        else:
            scored_candidates = []
            for candidate in remaining:
                overlaps = [
                    calculate_overlap(candidate['numbers'], game['numbers'])
                    for game in selected
                ]
                adjusted, penalty = calculate_diversity_adjusted_score(
                    candidate['intrinsic_score'], overlaps
                )
                if adjusted != float('-inf'):
                    scored_candidates.append((adjusted, candidate, penalty))
            if not scored_candidates:
                break
            _adjusted, chosen, penalty = max(
                scored_candidates,
                key=lambda item: (item[0], item[1]['intrinsic_score'], item[1]['numbers']),
            )
            chosen['diversity_penalty'] = penalty
            chosen['selection_score'] = _adjusted
        selected.append(chosen)
        remaining.remove(chosen)
    return selected


def _pick_legacy_candidates(candidates: list[dict], target_count: int) -> list[dict]:
    """Approximate the previous linear-overlap selector for backtest comparison."""
    selected: list[dict] = []
    remaining = list(candidates)
    while remaining and len(selected) < target_count:
        if not selected:
            chosen = remaining[0]
        else:
            eligible = []
            for candidate in remaining:
                overlaps = [calculate_overlap(candidate['numbers'], game['numbers']) for game in selected]
                if max(overlaps) > LOTTERY_RULES['max_game_overlap']:
                    continue
                adjusted = candidate['intrinsic_score'] - max(overlaps) * 0.8
                eligible.append((adjusted, candidate))
            if not eligible:
                break
            _adjusted, chosen = max(
                eligible,
                key=lambda item: (item[0], item[1]['intrinsic_score'], item[1]['numbers']),
            )
        chosen['diversity_penalty'] = 0.0
        chosen['selection_score'] = chosen['intrinsic_score']
        selected.append(chosen)
        remaining.remove(chosen)
    return selected


def calculate_portfolio_diversity(games: list[list[int]]) -> dict[str, float | int]:
    """Summarize pair overlap and shared core for a group of games."""
    if len(games) < 2:
        return {
            'pair_count': 0,
            'average_overlap': 0.0,
            'max_overlap': 0,
            'unique_numbers': len(set(games[0])) if games else 0,
            'shared_by_all': len(set(games[0])) if games else 0,
            'diversity_average': 100.0,
        }
    overlaps = [
        calculate_overlap(games[index], games[other])
        for index in range(len(games))
        for other in range(index + 1, len(games))
    ]
    shared = set(games[0]).intersection(*(set(game) for game in games[1:]))
    average_overlap = sum(overlaps) / len(overlaps)
    return {
        'pair_count': len(overlaps),
        'average_overlap': round(average_overlap, 2),
        'max_overlap': max(overlaps),
        'unique_numbers': len(set().union(*(set(game) for game in games))),
        'shared_by_all': len(shared),
        'diversity_average': round(100.0 - (average_overlap / 15 * 100.0), 2),
    }


def build_dashboard_metrics(draws: list[DrawRecord]) -> dict:
    if not draws:
        raise ValueError('Nao ha concursos para analisar.')

    total_draws = len(draws)
    number_features = calculate_number_features(draws)
    frequency = {number: number_features[number]['historical_frequency'] for number in range(1, 26)}
    metrics = [
        NumberMetric(number, frequency[number], round(frequency[number] / total_draws * 100, 2))
        for number in range(1, 26)
    ]
    metrics_desc = sorted(metrics, key=lambda item: (-item.frequencia, item.dezena))
    metrics_asc = sorted(metrics, key=lambda item: (item.frequencia, item.dezena))
    overdue = sorted(
        [
            {
                'dezena': number,
                'concursos_sem_sair': number_features[number]['last_seen_gap'],
                'ultimo_indice': total_draws - number_features[number]['last_seen_gap'],
            }
            for number in range(1, 26)
        ],
        key=lambda item: (-item['concursos_sem_sair'], item['dezena']),
    )
    even_values = [sum(number % 2 == 0 for number in draw.dezenas) for draw in draws]
    sums = [sum(draw.dezenas) for draw in draws]
    repeats = [
        len(set(draws[index].dezenas).intersection(draws[index - 1].dezenas))
        for index in range(1, len(draws))
    ]
    pattern_distribution: dict[str, int] = {}
    for even in even_values:
        key = f'{even}P-{15 - even}I'
        pattern_distribution[key] = pattern_distribution.get(key, 0) + 1
    pattern_top = sorted(
        [
            {'padrao': key, 'qtd': value, 'percentual': round(value / total_draws * 100, 2)}
            for key, value in pattern_distribution.items()
        ],
        key=lambda item: (-item['qtd'], item['padrao']),
    )
    average_repeats = sum(repeats) / len(repeats) if repeats else 0.0
    recommended_games = generate_recommended_games(draws)
    return {
        'total_draws': total_draws,
        'most_frequent': metrics_desc[:10],
        'least_frequent': metrics_asc[:10],
        'hot_numbers': metrics_desc[:10],
        'overdue_numbers': overdue[:10],
        'all_frequency': metrics_desc,
        'avg_even': round(sum(even_values) / total_draws, 2),
        'avg_odd': round(15 - sum(even_values) / total_draws, 2),
        'avg_sum': round(sum(sums) / total_draws, 2),
        'avg_repeats': round(average_repeats, 2),
        'repeat_target': _safe_repeat_target(average_repeats),
        'top_patterns': pattern_top[:5],
        'recommended_games': recommended_games,
    }
