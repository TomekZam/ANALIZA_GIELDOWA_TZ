import pandas as pd

from ..base import CalculatedIndicator


class Momentum12M(CalculatedIndicator):
    code = "momentum_12m"
    lookback_days = 252

    def compute(
        self,
        prices_df: pd.DataFrame,
        indicators_df: pd.DataFrame | None = None,
    ) -> pd.Series:
        prices_df = prices_df.sort_values("trade_date")
        close = prices_df.set_index("trade_date")["close_price"]
        return close / close.shift(self.lookback_days) - 1
