import pandas as pd

from ..base import CalculatedIndicator


class SMA50(CalculatedIndicator):
    code = "sma_50"
    lookback_days = 50

    def compute(
        self,
        prices_df: pd.DataFrame,
        indicators_df: pd.DataFrame | None = None,
    ) -> pd.Series:
        # Ujednolicenie kolejności
        prices_df = prices_df.sort_values("trade_date")

        # Series: index=trade_date, values=close_price
        close = prices_df.set_index("trade_date")["close_price"]

        # Prosta średnia krocząca 50 sesji
        return close.rolling(self.lookback_days).mean()
