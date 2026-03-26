import pandas as pd

from ..base import CalculatedIndicator


class SMA20(CalculatedIndicator):
    """
    SMA(20) – krótki trend ceny (średnia z 20 sesji).
    """
    code = "sma_20"
    lookback_days = 20

    def compute(
        self,
        prices_df: pd.DataFrame,
        indicators_df: pd.DataFrame | None = None,
    ) -> pd.Series:
        prices_df = prices_df.sort_values("trade_date")
        close = prices_df.set_index("trade_date")["close_price"]

        # min_periods = 20 -> brak wartości dopóki nie ma pełnego okna
        return close.rolling(window=self.lookback_days, min_periods=self.lookback_days).mean()
