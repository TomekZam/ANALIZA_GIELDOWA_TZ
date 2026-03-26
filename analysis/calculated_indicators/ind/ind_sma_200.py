import pandas as pd

from ..base import CalculatedIndicator


class SMA200(CalculatedIndicator):
    code = "sma_200"
    lookback_days = 200

    def compute(
        self,
        prices_df: pd.DataFrame,
        indicators_df: pd.DataFrame | None = None,
    ) -> pd.Series:
        prices_df = prices_df.sort_values("trade_date")
        close = prices_df.set_index("trade_date")["close_price"]

        # SMA(200) z ceny zamknięcia
        return close.rolling(self.lookback_days).mean()
