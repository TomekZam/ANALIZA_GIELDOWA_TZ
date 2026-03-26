import pandas as pd
import numpy as np

from ..base import CalculatedIndicator


class FutSignal20Hyb(CalculatedIndicator):
    """
    fut_signal_20_hyb

    Wskaźnik typu FUTURE / label (wariant hybrydowy, bardziej "trading").
    Cel: umożliwić ponowny sygnał (re-entry) po okresie osłabienia / konsolidacji,
    ale tylko jeśli impuls jest:
    1) progresywny względem pamięci (local reference),
    2) istotny statystycznie w oknie (Q80/Q20),
    3) zgodny znakiem z kontekstem fut_imp_0.

    Różnica względem fut_signal_20 (monotonicznego):
    - fut_signal_20 porównuje do globalnego ekstremum (od ostatniego sygnału bez resetu),
    - fut_signal_20_hyb po upływie TTL odświeża referencję do lokalnego ekstremum okna.

    Mapowanie kolumn:
    - fut_imp_0(t)  -> fut_barrier_5p_3p_5d
    - fut_imp_20(t) -> fut_imp_20
    - wynik         -> fut_signal_20_hyb
    """

    code = "fut_signal_20_hyb"

    # Wymagane wskaźniki wejściowe (muszą być policzone wcześniej)
    required_indicators = [
        "fut_barrier_5p_3p_5d",  # fut_imp_0 (kontekst znaku)
        "fut_imp_20",            # fut_imp_20 (impuls w horyzoncie 20d)
    ]

    # Parametry hybrydy
    TTL_BARS = 20          # po tylu sesjach od ostatniego sygnału odświeżamy referencję
    WINDOW_BARS = 20       # okno do lokalnego ekstremum i kwantyli
    Q_POS = 0.80           # próg istotności dla trendu dodatniego
    Q_NEG = 0.20           # próg istotności dla trendu ujemnego
    MIN_WINDOW_VALUES = 5  # minimalna liczba wartości w oknie, aby liczyć kwantyl

    def compute(
        self,
        prices_df: pd.DataFrame,
        indicators_df: pd.DataFrame | None = None,
    ) -> pd.Series:

        if indicators_df is None:
            raise ValueError("indicators_df is required for fut_signal_20_hyb")

        # sortowanie sekwencyjne (krytyczne)
        indicators_df = indicators_df.sort_values("trade_date")

        fut_imp_0 = indicators_df["fut_barrier_5p_3p_5d"].values
        fut_imp_20 = indicators_df["fut_imp_20"].values

        result = []

        prev_ref = None          # referencja impulsu (ostatni sygnał lub lokalne ekstremum okna)
        last_signal_idx = None   # indeks (bar) ostatniego sygnału

        def _is_valid(x) -> bool:
            return x is not None and not np.isnan(x) and x != 0

        def _window_values(arr, start, end, sign_mode: int) -> np.ndarray:
            """
            Zwraca wartości z okna [start, end) przefiltrowane:
            - bez 0 i NaN
            - tylko dodatnie (sign_mode=+1) albo tylko ujemne (sign_mode=-1)
            """
            w = arr[start:end]
            w = w[~np.isnan(w)]
            w = w[w != 0]
            if sign_mode > 0:
                w = w[w > 0]
            else:
                w = w[w < 0]
            return w

        for i, (cur_0, cur_20) in enumerate(zip(fut_imp_0, fut_imp_20)):
            signal = np.nan

            # Walidacja wejścia (0/NaN ignorujemy)
            if not (_is_valid(cur_0) and _is_valid(cur_20)):
                result.append(signal)
                continue

            # Zgodność znaku z kontekstem
            if np.sign(cur_0) != np.sign(cur_20):
                result.append(signal)
                continue

            trend_sign = int(np.sign(cur_20))  # +1 albo -1

            # INIT: pierwszy sygnał w historii (jak w bazowym fut_signal_20)
            if prev_ref is None:
                signal = trend_sign
                prev_ref = cur_20
                last_signal_idx = i
                result.append(signal)
                continue

            # HYBRYDOWE "ODŚWIEŻENIE" referencji po TTL (zamiast resetu do 0/None)
            if last_signal_idx is not None and (i - last_signal_idx) >= self.TTL_BARS:
                start = max(0, i - self.WINDOW_BARS)
                end = i

                w = _window_values(fut_imp_20, start, end, trend_sign)
                if w.size > 0:
                    # lokalne ekstremum w oknie
                    prev_ref = float(np.max(w)) if trend_sign > 0 else float(np.min(w))
                # jeśli okno puste, zostawiamy prev_ref bez zmian (bezpieczne)

            # Warunek progresu względem referencji
            progressive = (cur_20 > prev_ref) if trend_sign > 0 else (cur_20 < prev_ref)
            if not progressive:
                result.append(signal)
                continue

            # Warunek istotności względem rozkładu w oknie (Q80/Q20)
            start = max(0, i - self.WINDOW_BARS)
            end = i
            w = _window_values(fut_imp_20, start, end, trend_sign)

            # jeśli za mało danych w oknie -> brak sygnału (konserwatywnie)
            if w.size < self.MIN_WINDOW_VALUES:
                result.append(signal)
                continue

            q = float(np.quantile(w, self.Q_POS if trend_sign > 0 else self.Q_NEG))
            significant = (cur_20 > q) if trend_sign > 0 else (cur_20 < q)
            if not significant:
                result.append(signal)
                continue

            # Jeśli spełnione: progres + istotność + zgodność znaku -> sygnał
            signal = trend_sign
            prev_ref = cur_20
            last_signal_idx = i

            result.append(signal)

        return pd.Series(
            result,
            index=indicators_df["trade_date"],
            name=self.code,
        )
