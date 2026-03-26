import pandas as pd
import numpy as np

from ..base import CalculatedIndicator


class Volatility20D(CalculatedIndicator):
    code = "volatility_20d"
    lookback_days = 20

    def compute(
        self,
        prices_df: pd.DataFrame,
        indicators_df: pd.DataFrame | None = None,
    ) -> pd.Series:
        prices_df = prices_df.sort_values("trade_date")
        close = prices_df.set_index("trade_date")["close_price"]
        returns = np.log(close / close.shift(1))
        return returns.rolling(self.lookback_days).std()
