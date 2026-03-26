import pandas as pd
import numpy as np

from ..base import CalculatedIndicator


class FutSignal120(CalculatedIndicator):
    """
    fut_signal_120

    Wskaźnik typu FUTURE / label.
    Sekwencyjny sygnał kontynuacji impulsu w horyzoncie 120 dni.

    Algorytm:
    - sekwencyjny sygnał kontynuacji impulsu,
    - pamięć `prev_fut_imp_H` aktualizowana WYŁĄCZNIE po ustawieniu sygnału,
    - ignoruje wartości 0 oraz NaN,
    - wymaga zgodności znaku impulsu przyszłego z impulsem bazowym.

    Mapowanie kolumn:
    - fut_imp_0(t)   -> fut_barrier_5p_3p_5d
    - fut_imp_120(t) -> fut_imp_120
    - wynik          -> fut_signal_120
    """

    code = "fut_signal_120"

    # Wymagane wskaźniki wejściowe (muszą być policzone wcześniej)
    required_indicators = [
        "fut_barrier_5p_3p_5d",  # fut_imp_0
        "fut_imp_120",           # fut_imp_120
    ]

    def compute(
        self,
        prices_df: pd.DataFrame,
        indicators_df: pd.DataFrame | None = None,
    ) -> pd.Series:

        if indicators_df is None:
            raise ValueError("indicators_df is required for fut_signal_120")

        # sortowanie sekwencyjne (krytyczne dla algorytmu)
        indicators_df = indicators_df.sort_values("trade_date")

        fut_imp_0 = indicators_df["fut_barrier_5p_3p_5d"].values
        fut_imp_120 = indicators_df["fut_imp_120"].values

        result = []
        prev_fut_imp_120 = None  # pamięć: ostatni impuls, dla którego ustawiono sygnał

        for cur_0, cur_120 in zip(fut_imp_0, fut_imp_120):

            signal = np.nan

            # walidacja danych wejściowych
            cur_0_valid = cur_0 is not None and not np.isnan(cur_0) and cur_0 != 0
            cur_120_valid = cur_120 is not None and not np.isnan(cur_120) and cur_120 != 0

            if cur_0_valid and cur_120_valid:

                # INIT – pierwszy sygnał w historii
                if prev_fut_imp_120 is None:
                    if np.sign(cur_120) == np.sign(cur_0):
                        signal = int(np.sign(cur_120))
                        prev_fut_imp_120 = cur_120

                # CONTINUATION – porównanie do ostatniego SYGNAŁU
                else:
                    if np.sign(cur_120) == np.sign(cur_0):

                        # sygnał dodatni
                        if cur_120 > 0 and cur_120 > prev_fut_imp_120:
                            signal = 1
                            prev_fut_imp_120 = cur_120

                        # sygnał ujemny
                        elif cur_120 < 0 and cur_120 < prev_fut_imp_120:
                            signal = -1
                            prev_fut_imp_120 = cur_120

            # brak sygnału -> prev_fut_imp_120 pozostaje bez zmian
            result.append(signal)

        return pd.Series(
            result,
            index=indicators_df["trade_date"],
            name=self.code,
        )
