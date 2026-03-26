import numpy as np
import pandas as pd

from ..base import CalculatedIndicator


class FutBarrier20p12p2D(CalculatedIndicator):
    """
    Wskaźnik FUTURE (etykieta): fut_barrier_20p_12p_2d

    FIRST HIT – zgodnie z ADR-016
    Dla dnia t analizujemy close(t+1) ... close(t+H):

    +1  -> jeśli jako pierwsze osiągnięto close >= close(t) * (1 + R_UP)
    -1  -> jeśli jako pierwsze osiągnięto close <= close(t) * (1 - S_DOWN)
     0  -> jeśli w horyzoncie nie osiągnięto żadnej bariery
    NaN -> jeśli brak pełnego horyzontu danych lub NaN w danych wejściowych

    close-only, batch-friendly, wektorowe.
    """

    code = "fut_barrier_20p_12p_2d"

    HORIZON_DAYS = 2
    R_UP = 0.20
    S_DOWN = 0.12

    def compute(
        self,
        prices_df: pd.DataFrame,
        indicators_df: pd.DataFrame | None = None,
    ) -> pd.Series:

        # --- przygotowanie danych ---
        prices_df = prices_df.sort_values("trade_date")

        close = (
            prices_df
            .set_index("trade_date")["close_price"]
            .astype(float)
        )

        close_values = close.to_numpy(dtype=float)
        n = close_values.shape[0]

        H = int(self.HORIZON_DAYS)
        up_mult = 1.0 + float(self.R_UP)
        dn_mult = 1.0 - float(self.S_DOWN)

        # wynik domyślny: NaN (w tym ostatnie H dni)
        out = np.full(n, np.nan, dtype=float)

        # brak pełnego horyzontu -> wszystko NaN
        if n <= H:
            return pd.Series(out, index=close.index, name=self.code)

        # --- sliding window na przyszłość ---
        # windows[i] = close(t+1) ... close(t+H)
        try:
            from numpy.lib.stride_tricks import sliding_window_view
            windows = sliding_window_view(
                close_values[1:], window_shape=H
            )  # shape: (n-H, H)
        except Exception:
            # fallback (bezpieczny)
            from numpy.lib.stride_tricks import as_strided
            x = close_values[1:]
            shape = (n - H, H)
            strides = (x.strides[0], x.strides[0])
            windows = as_strided(x, shape=shape, strides=strides)

        base = close_values[: n - H]  # close(t)

        # --- walidacja danych ---
        valid = np.isfinite(base) & np.all(np.isfinite(windows), axis=1)

        up_level = base * up_mult
        dn_level = base * dn_mult

        hit_up = windows >= up_level[:, None]
        hit_dn = windows <= dn_level[:, None]

        any_up = hit_up.any(axis=1)
        any_dn = hit_dn.any(axis=1)

        # indeks pierwszego trafienia
        sentinel = H + 1
        first_up = np.where(any_up, hit_up.argmax(axis=1), sentinel)
        first_dn = np.where(any_dn, hit_dn.argmax(axis=1), sentinel)

        res = np.zeros(n - H, dtype=float)

        only_up = any_up & ~any_dn
        only_dn = any_dn & ~any_up
        both = any_up & any_dn

        res[only_up] = 1.0
        res[only_dn] = -1.0

        # oba trafione -> decyduje pierwsze (remis = -1, jak w referencji)
        # oba trafione -> decyduje pierwsze
        # remis (first_up == first_dn) -> 0
        fu = first_up[both]
        fd = first_dn[both]
        res[both] = np.where(
            fu < fd, 1.0,
            np.where(fu > fd, -1.0, 0.0)
        )


        # invalid -> NaN
        res[~valid] = np.nan

        out[: n - H] = res

        return pd.Series(out, index=close.index, name=self.code)
