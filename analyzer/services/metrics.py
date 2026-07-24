from dataclasses import dataclass
from itertools import combinations

from .excel_parser import DrawRecord


MOLDURA_NUMBERS = {1, 2, 3, 4, 5, 6, 10, 11, 15, 16, 20, 21, 22, 23, 24, 25}


@dataclass
class NumberMetric:
    dezena: int
    frequencia: int
    percentual: float


def build_dashboard_metrics(draws: list[DrawRecord]) -> dict:
    if not draws:
        raise ValueError('Nao ha concursos para analisar.')

    total_draws = len(draws)
    frequency = {number: 0 for number in range(1, 26)}
    last_seen_gap = {number: total_draws for number in range(1, 26)}

    even_count_total = 0
    odd_count_total = 0
    sum_total = 0
    repeat_counts: list[int] = []

    previous_set: set[int] | None = None
    for draw_index, draw in enumerate(draws):
        current_set = set(draw.dezenas)
        for number in current_set:
            frequency[number] += 1
            last_seen_gap[number] = total_draws - draw_index - 1

        even_count = len([number for number in draw.dezenas if number % 2 == 0])
        odd_count = 15 - even_count
        even_count_total += even_count
        odd_count_total += odd_count
        sum_total += sum(draw.dezenas)

        if previous_set is not None:
            repeat_counts.append(len(current_set.intersection(previous_set)))
        previous_set = current_set

    metrics = [_to_metric(number, count, total_draws) for number, count in frequency.items()]
    metrics_sorted_desc = sorted(metrics, key=lambda item: (-item.frequencia, item.dezena))
    metrics_sorted_asc = sorted(metrics, key=lambda item: (item.frequencia, item.dezena))

    overdue = sorted(
        (
            {
                'dezena': number,
                'concursos_sem_sair': gap,
                'ultimo_indice': total_draws - gap,
            }
            for number, gap in last_seen_gap.items()
        ),
        key=lambda item: (-item['concursos_sem_sair'], item['dezena']),
    )

    average_even = even_count_total / total_draws
    average_odd = odd_count_total / total_draws
    average_sum = sum_total / total_draws
    average_repeats = (sum(repeat_counts) / len(repeat_counts)) if repeat_counts else 0.0
    repeat_target = _safe_repeat_target(average_repeats)

    pattern_distribution: dict[str, int] = {}
    for draw in draws:
        even = len([number for number in draw.dezenas if number % 2 == 0])
        odd = 15 - even
        key = f'{even}P-{odd}I'
        pattern_distribution[key] = pattern_distribution.get(key, 0) + 1

    pattern_top = sorted(
        (
            {
                'padrao': key,
                'qtd': value,
                'percentual': round((value / total_draws) * 100, 2),
            }
            for key, value in pattern_distribution.items()
        ),
        key=lambda item: (-item['qtd'], item['padrao']),
    )

    recommended_games = _build_recommended_games(
        draws=draws,
        frequency=frequency,
        last_seen_gap=last_seen_gap,
        repeat_target=repeat_target,
    )

    return {
        'total_draws': total_draws,
        'most_frequent': metrics_sorted_desc[:10],
        'least_frequent': metrics_sorted_asc[:10],
        'hot_numbers': metrics_sorted_desc[:10],
        'overdue_numbers': overdue[:10],
        'all_frequency': metrics_sorted_desc,
        'avg_even': round(average_even, 2),
        'avg_odd': round(average_odd, 2),
        'avg_sum': round(average_sum, 2),
        'avg_repeats': round(average_repeats, 2),
        'repeat_target': repeat_target,
        'top_patterns': pattern_top[:5],
        'recommended_games': recommended_games,
    }


def _to_metric(number: int, count: int, total_draws: int) -> NumberMetric:
    percentage = (count / total_draws) * 100 if total_draws else 0.0
    return NumberMetric(dezena=number, frequencia=count, percentual=round(percentage, 2))


def _safe_repeat_target(average_repeats: float) -> int:
    # The historical mode for repetition usually stays close to this range.
    rounded = int(round(average_repeats))
    return max(7, min(11, rounded))


def _build_recommended_games(
    draws: list[DrawRecord],
    frequency: dict[int, int],
    last_seen_gap: dict[int, int],
    repeat_target: int,
) -> list[dict]:
    recent_draws = draws[-10:]
    recent_frequency = {number: 0 for number in range(1, 26)}
    for draw in recent_draws:
        for number in draw.dezenas:
            recent_frequency[number] += 1

    number_scores = _build_number_scores(frequency, recent_frequency, last_seen_gap)
    last_draw_numbers = set(draws[-1].dezenas)

    pool = _build_candidate_pool(number_scores)
    combo_candidates = _generate_valid_combinations(pool, last_draw_numbers, repeat_target, number_scores)

    if len(combo_candidates) < 3:
        fallback_pool = list(range(1, 26))
        combo_candidates = _generate_valid_combinations(fallback_pool, last_draw_numbers, repeat_target, number_scores)

    selected = _pick_diverse_combinations(combo_candidates, target_count=3)
    if len(selected) < 3:
        # As a safety net, keep filling from top candidates.
        used = {tuple(item['numbers']) for item in selected}
        for candidate in combo_candidates:
            key = tuple(candidate['numbers'])
            if key in used:
                continue
            selected.append(candidate)
            used.add(key)
            if len(selected) == 3:
                break

    return selected[:3]


def _build_number_scores(
    frequency: dict[int, int],
    recent_frequency: dict[int, int],
    last_seen_gap: dict[int, int],
) -> dict[int, float]:
    scores: dict[int, float] = {}
    for number in range(1, 26):
        scores[number] = (
            (frequency[number] * 1.0)
            + (recent_frequency[number] * 6.0)
            + (min(last_seen_gap[number], 25) * 0.8)
        )
    return scores


def _build_candidate_pool(number_scores: dict[int, float]) -> list[int]:
    ordered = sorted(number_scores, key=lambda number: (-number_scores[number], number))
    # 20 numbers keeps search space manageable while preserving strong candidates.
    return ordered[:20]


def _generate_valid_combinations(
    pool: list[int],
    last_draw_numbers: set[int],
    repeat_target: int,
    number_scores: dict[int, float],
) -> list[dict]:
    combos: list[dict] = []

    for combo in combinations(sorted(pool), 15):
        numbers = list(combo)

        even_count = len([number for number in numbers if number % 2 == 0])
        odd_count = 15 - even_count
        if not (even_count == 7 and odd_count == 8):
            continue

        moldura_count = len([number for number in numbers if number in MOLDURA_NUMBERS])
        if not (9 <= moldura_count <= 11):
            continue

        repeat_last = len(set(numbers).intersection(last_draw_numbers))
        if not (7 <= repeat_last <= 11):
            continue

        sequence_points = _sequence_points(numbers)
        score = (
            sum(number_scores[number] for number in numbers)
            - (abs(moldura_count - 10) * 5.0)
            - (abs(repeat_last - repeat_target) * 4.0)
            + (sequence_points * 1.2)
        )

        combos.append(
            {
                'numbers': numbers,
                'score': round(score, 2),
                'even_count': even_count,
                'odd_count': odd_count,
                'moldura_count': moldura_count,
                'center_count': 15 - moldura_count,
                'repeat_last': repeat_last,
                'sequence_points': sequence_points,
            }
        )

    combos.sort(key=lambda item: (-item['score'], item['numbers']))
    return combos


def _sequence_points(numbers: list[int]) -> int:
    points = 0
    run_size = 1
    for idx in range(1, len(numbers)):
        if numbers[idx] == numbers[idx - 1] + 1:
            run_size += 1
        else:
            if run_size >= 2:
                points += run_size
            run_size = 1

    if run_size >= 2:
        points += run_size
    return points


def _pick_diverse_combinations(candidates: list[dict], target_count: int) -> list[dict]:
    selected: list[dict] = []
    for candidate in candidates:
        current = set(candidate['numbers'])
        if not selected:
            selected.append(candidate)
            if len(selected) == target_count:
                break
            continue

        # Limit overlap to keep games reasonably different.
        max_overlap = max(len(current.intersection(set(item['numbers']))) for item in selected)
        if max_overlap <= 13:
            selected.append(candidate)
            if len(selected) == target_count:
                break

    return selected
