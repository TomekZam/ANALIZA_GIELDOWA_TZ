import pandas as pd
import numpy as np

from ..base import CalculatedIndicator


class FutSignal20(CalculatedIndicator):
    """
    fut_signal_20

    Wskaźnik typu FUTURE / label.
    Sekwencyjny sygnał kontynuacji impulsu w horyzoncie 20 dni.

    Algorytm:
    - sekwencyjny sygnał kontynuacji impulsu,
    - pamięć `prev_fut_imp_H` aktualizowana WYŁĄCZNIE po ustawieniu sygnału,
    - ignoruje wartości 0 oraz NaN,
    - wymaga zgodności znaku impulsu przyszłego z impulsem bazowym.

    Mapowanie kolumn:
    - fut_imp_0(t)  -> fut_barrier_5p_3p_5d
    - fut_imp_20(t) -> fut_imp_20
    - wynik         -> fut_signal_20
    """

    code = "fut_signal_20"

    # Wymagane wskaźniki wejściowe (muszą być policzone wcześniej)
    required_indicators = [
        "fut_barrier_5p_3p_5d",  # fut_imp_0
        "fut_imp_20",            # fut_imp_20
    ]

    def compute(
        self,
        prices_df: pd.DataFrame,
        indicators_df: pd.DataFrame | None = None,
    ) -> pd.Series:

        if indicators_df is None:
            raise ValueError("indicators_df is required for fut_signal_20")

        # sortowanie sekwencyjne (krytyczne dla algorytmu)
        indicators_df = indicators_df.sort_values("trade_date")

        fut_imp_0 = indicators_df["fut_barrier_5p_3p_5d"].values
        fut_imp_20 = indicators_df["fut_imp_20"].values

        result = []
        prev_fut_imp_20 = None  # pamięć: ostatni impuls, dla którego ustawiono sygnał

        for cur_0, cur_20 in zip(fut_imp_0, fut_imp_20):

            signal = np.nan

            # walidacja danych wejściowych
            cur_0_valid = cur_0 is not None and not np.isnan(cur_0) and cur_0 != 0
            cur_20_valid = cur_20 is not None and not np.isnan(cur_20) and cur_20 != 0

            if cur_0_valid and cur_20_valid:

                # INIT – pierwszy sygnał w historii
                if prev_fut_imp_20 is None:
                    if np.sign(cur_20) == np.sign(cur_0):
                        signal = int(np.sign(cur_20))
                        prev_fut_imp_20 = cur_20

                # CONTINUATION – porównanie do ostatniego SYGNAŁU
                else:
                    if np.sign(cur_20) == np.sign(cur_0):

                        # sygnał dodatni
                        if cur_20 > 0 and cur_20 > prev_fut_imp_20:
                            signal = 1
                            prev_fut_imp_20 = cur_20

                        # sygnał ujemny
                        elif cur_20 < 0 and cur_20 < prev_fut_imp_20:
                            signal = -1
                            prev_fut_imp_20 = cur_20

            # brak sygnału -> prev_fut_imp_20 pozostaje bez zmian
            result.append(signal)

        return pd.Series(
            result,
            index=indicators_df["trade_date"],
            name=self.code,
        )
