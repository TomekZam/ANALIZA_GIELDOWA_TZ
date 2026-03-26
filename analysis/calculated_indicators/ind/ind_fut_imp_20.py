import pandas as pd
import numpy as np

from ..base import CalculatedIndicator
from analysis.calculated_indicators.utils.fut_imp_weights import (
    get_fut_imp_weights,
)


class FutImp20(CalculatedIndicator):
    """
    fut_imp_20

    Wskaźnik agregujący sygnał FUTURE dla horyzontu 20 dni.

    Wzór (jawny, bez iteracji):
        fut_imp_20(t) =
            (fut_barrier_100p_50p_20d(t) * 32)
          + (fut_barrier_50p_20p_20d(t)  * 16)
          + (fut_barrier_20p_12p_20d(t)  * 8)

    Zasady semantyczne (KLUCZOWE):
    - jeżeli którakolwiek składowa = NULL
        → fut_imp_20 = NULL
        → brak zapisu
        → brak ustawienia flagi
    - brak maskowania NULL zerem

    NULL oznacza:
    - „brak gotowości do wyliczenia”
    """

    code = "fut_imp_20"
    lookback_days = 20

    # Jawnie deklarujemy dokładnie te kolumny,
    # które są używane we wzorze
    required_indicators = [
        "fut_barrier_100p_50p_20d",
        "fut_barrier_50p_20p_20d",
        "fut_barrier_20p_12p_20d",
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

        # Pobranie wag (wspólna funkcja)
        weights = get_fut_imp_weights()

        w_t2 = weights["fut_barrier_100p_50p_20d"]  # 32
        w_t3 = weights["fut_barrier_50p_20p_20d"]   # 16
        w_t4 = weights["fut_barrier_20p_12p_20d"]   # 8

        # Porządkowanie danych czasowych
        indicators_df = indicators_df.sort_values("trade_date").copy()
        indicators_df["trade_date"] = pd.to_datetime(
            indicators_df["trade_date"]
        ).dt.date
        indicators_df = indicators_df.set_index("trade_date")

        # JAWNY WZÓR
        # NULL w którejkolwiek składowej → NULL w wyniku
        result = (
            indicators_df["fut_barrier_100p_50p_20d"] * w_t2
            + indicators_df["fut_barrier_50p_20p_20d"] * w_t3
            + indicators_df["fut_barrier_20p_12p_20d"] * w_t4
        )

        return result
