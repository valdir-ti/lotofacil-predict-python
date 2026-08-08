"""Walk-forward evaluation for heuristic games and random baselines."""

import random
from statistics import mean, median
from typing import Any

from .excel_parser import DrawRecord
from .features import validate_game
from .lottery_rules import LOTTERY_RULES
from .metrics import (
    calculate_portfolio_diversity,
    generate_recommended_games,
)


def _hit_count(numbers: list[int], actual: set[int]) -> int:
    return len(set(numbers).intersection(actual))


def _random_game(rng: random.Random) -> list[int]:
    return sorted(rng.sample(range(1, 26), LOTTERY_RULES['game_size']))


def _random_structural_game(rng: random.Random, last_draw: set[int]) -> list[int]:
    for _ in range(100_000):
        numbers = _random_game(rng)
        valid, _reason = validate_game(numbers, last_draw)
        if valid:
            return numbers
    raise RuntimeError('Nao foi possivel gerar baseline aleatorio estrutural.')


def _summarize(records: list[dict[str, Any]], key: str) -> dict[str, Any]:
    hits = [hit for record in records for hit in record[key]]
    return {
        'games': len(hits),
        'mean_hits': round(mean(hits), 3) if hits else 0.0,
        'median_hits': median(hits) if hits else 0.0,
        'max_hits': max(hits, default=0),
        'games_11_plus': sum(hit >= 11 for hit in hits),
        'games_12_plus': sum(hit >= 12 for hit in hits),
        'games_13_plus': sum(hit >= 13 for hit in hits),
        'games_14_plus': sum(hit >= 14 for hit in hits),
        'games_15': sum(hit == 15 for hit in hits),
    }


def _summarize_portfolios(records: list[dict[str, Any]], key: str) -> dict[str, Any]:
    portfolios = [record[key] for record in records]
    if not portfolios:
        return {}
    return {
        metric: round(mean(item[metric] for item in portfolios), 3)
        for metric in (
            'average_overlap',
            'max_overlap',
            'unique_numbers',
            'shared_by_all',
            'diversity_average',
        )
    }


def run_backtest(
    draws: list[DrawRecord],
    min_history: int = 20,
    game_count: int = 3,
    seed: int = 42,
) -> dict[str, Any]:
    """Run a walk-forward backtest without using the tested draw as input."""
    if min_history < 1:
        raise ValueError('min_history deve ser positivo.')
    if len(draws) <= min_history:
        raise ValueError('Sao necessarios concursos posteriores ao historico minimo.')

    rng = random.Random(seed)
    records: list[dict[str, Any]] = []
    for index in range(min_history, len(draws)):
        history = draws[:index]
        actual = set(draws[index].dezenas)
        heuristic_games = generate_recommended_games(history, target_count=game_count)
        legacy_games = generate_recommended_games(
            history,
            target_count=game_count,
            selection_mode='legacy',
        )
        random_games = [_random_game(rng) for _ in range(game_count)]
        structural_games = [
            _random_structural_game(rng, set(history[-1].dezenas))
            for _ in range(game_count)
        ]
        records.append({
            'contest': draws[index].concurso,
            'contest_index': index,
            'heuristic_games': [game['numbers'] for game in heuristic_games],
            'heuristic_hits': [_hit_count(game['numbers'], actual) for game in heuristic_games],
            'legacy_heuristic_games': [game['numbers'] for game in legacy_games],
            'legacy_heuristic_hits': [_hit_count(game['numbers'], actual) for game in legacy_games],
            'random_hits': [_hit_count(game, actual) for game in random_games],
            'structural_random_hits': [_hit_count(game, actual) for game in structural_games],
            'heuristic_portfolio': calculate_portfolio_diversity(
                [game['numbers'] for game in heuristic_games]
            ),
            'legacy_heuristic_portfolio': calculate_portfolio_diversity(
                [game['numbers'] for game in legacy_games]
            ),
            'random_portfolio': calculate_portfolio_diversity(random_games),
            'structural_random_portfolio': calculate_portfolio_diversity(structural_games),
        })

    return {
        'min_history': min_history,
        'tested_contests': len(records),
        'records': records,
        'summary': {
            'heuristic': _summarize(records, 'heuristic_hits'),
            'legacy_heuristic': _summarize(records, 'legacy_heuristic_hits'),
            'random': _summarize(records, 'random_hits'),
            'structural_random': _summarize(records, 'structural_random_hits'),
        },
        'portfolio_summary': {
            'heuristic': _summarize_portfolios(records, 'heuristic_portfolio'),
            'legacy_heuristic': _summarize_portfolios(records, 'legacy_heuristic_portfolio'),
            'random': _summarize_portfolios(records, 'random_portfolio'),
            'structural_random': _summarize_portfolios(records, 'structural_random_portfolio'),
        },
    }
