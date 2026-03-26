import pandas as pd
import numpy as np

from ..base import CalculatedIndicator
from analysis.calculated_indicators.utils.fut_imp_weights import (
    get_fut_imp_weights,
)


class FutImp2(CalculatedIndicator):
    """
    fut_imp_2

    Wskaźnik agregujący sygnał FUTURE dla horyzontu 2 dni.

    Wzór (jawny, bez iteracji):
        fut_imp_2(t) = fut_barrier_20p_12p_2d(t) * waga

    Zasady semantyczne (KLUCZOWE):
    - jeżeli fut_barrier_20p_12p_2d(t) = NULL
        → fut_imp_2(t) = NULL
        → brak zapisu
        → brak ustawienia flagi
    - jeżeli fut_barrier_20p_12p_2d(t) ∈ {1, 0, -1}
        → fut_imp_2(t) ∈ {64, 0, -64}

    NULL oznacza:
    - „brak gotowości do wyliczenia”
    - oczekiwanie na przyszłe uzupełnienie danych wejściowych
    """

    code = "fut_imp_2"
    lookback_days = 2

    # Jawnie deklarujemy dokładnie te kolumny,
    # które są używane we wzorze
    required_indicators = [
        "fut_barrier_20p_12p_2d",
    ]

    def compute(
        self,
        prices_df: pd.DataFrame,
        indicators_df: pd.DataFrame | None = None,
    ) -> pd.Series:

        # Brak danych wejściowych → nic nie liczymy
        if indicators_df is None or indicators_df.empty:
            prices_df = prices_df.sort_values("trade_date")
            return pd.Series(
                np.nan,
                index=prices_df["trade_date"],
            )

        # Pobranie wagi (wspólna funkcja)
        weights = get_fut_imp_weights()
        weight = weights["fut_barrier_20p_12p_2d"]

        # Porządkowanie danych czasowych
        indicators_df = indicators_df.sort_values("trade_date").copy()
        indicators_df["trade_date"] = pd.to_datetime(
            indicators_df["trade_date"]
        ).dt.date
        indicators_df = indicators_df.set_index("trade_date")

        # JAWNY WZÓR
        # NULL w składowej → NULL w wyniku
        result = indicators_df["fut_barrier_20p_12p_2d"] * weight

        return result
