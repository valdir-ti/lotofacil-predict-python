"""Centralized, configurable rules and baseline weights for Lotofácil heuristics."""

LOTTERY_RULES = {
    'game_size': 15,
    'number_min': 1,
    'number_max': 25,
    'even_min': 7,
    'even_max': 7,
    'frame_min': 9,
    'frame_max': 11,
    'preferred_frame': 10,
    'repeat_min': 7,
    'repeat_max': 11,
    'preferred_repeat': 9,
    'max_game_overlap': 13,
    'preferred_pool_size': 20,
    'recent_window': 30,
    'last_10_window': 10,
    'delay_cap': 25,
    'target_sum': 195,
}

# These are an initial experimental baseline, not mathematically proven weights.
SCORING_WEIGHTS = {
    'historical_frequency': 0.50,
    'recent_frequency': 0.20,
    'last_10_frequency': 0.10,
    'delay': 0.05,
    'frame_structure': 0.15,
}

GAME_SCORING_WEIGHTS = {
    'numbers': 0.40,
    'frame': 0.10,
    'repeat': 0.10,
    'parity': 0.10,
    'sum': 0.10,
    'lines': 0.07,
    'columns': 0.07,
    'sequences': 0.06,
}

# Selection-only penalties. Intrinsic game scores never include overlap.
OVERLAP_PENALTIES = {
    0: 0.0,
    1: 0.0,
    2: 0.0,
    3: 0.0,
    4: 0.0,
    5: 0.0,
    6: 0.0,
    7: 0.0,
    8: 0.0,
    9: 2.0,
    10: 5.0,
    11: 10.0,
    12: 18.0,
    13: 30.0,
}

MOLDURA_NUMBERS = {
    1, 2, 3, 4, 5, 6, 10, 11, 15,
    16, 20, 21, 22, 23, 24, 25,
}
