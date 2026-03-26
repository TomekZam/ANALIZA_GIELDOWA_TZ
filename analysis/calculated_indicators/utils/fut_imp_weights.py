"""
Mapowanie wag bitowych dla wskaźników FUTURE
wykorzystywanych w algorytmach typu fut_imp_*.

UWAGA:
- To NIE jest calc_flags.
- To jest jawna logika domenowa do agregacji sygnałów FUTURE.
"""

from typing import Dict


def get_fut_imp_weights() -> Dict[str, int]:
    """
    Zwraca mapowanie:
    nazwa_kolumny_w_indicators_daily -> waga_bitowa

    Wagi są wykorzystywane przez algorytm fut_imp_2
    do wyliczenia ważonej miary istotności ruchu ceny.

    Wartości wag:
    - im wyższa waga, tym silniejszy sygnał
    """
    return {
        "fut_barrier_20p_12p_2d": 64,
        "fut_barrier_100p_50p_20d": 32,
        "fut_barrier_50p_20p_20d": 16,
        "fut_barrier_20p_12p_20d": 8,
        "fut_barrier_50p_20p_60d": 4,
        "fut_barrier_20p_12p_60d": 2,
        "fut_barrier_50p_20p_120d": 1,
    }
