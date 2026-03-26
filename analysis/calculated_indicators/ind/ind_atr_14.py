import pandas as pd
from analysis.calculated_indicators.base import CalculatedIndicator

class ATR14(CalculatedIndicator):
    """
    ATR_14 (Average True Range, 14 dni) – Zmienność rzeczywista
    """
    code = "atr_14"
    required_indicators = []

    def compute(
        self,
        prices_df: pd.DataFrame,
        indicators_df: pd.DataFrame | None = None,
    ) -> pd.Series:
        prices_df = prices_df.sort_values("trade_date")
        high = prices_df["high_price"]
        low = prices_df["low_price"]
        close = prices_df["close_price"]

        prev_close = close.shift(1)
        tr = pd.concat([
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs()
        ], axis=1).max(axis=1)

        atr = tr.rolling(window=14, min_periods=14).mean()
        return pd.Series(atr.values, index=prices_df["trade_date"])
