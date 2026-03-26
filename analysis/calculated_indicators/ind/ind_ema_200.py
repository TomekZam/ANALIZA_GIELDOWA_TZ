import pandas as pd

from ..base import CalculatedIndicator


class EMA200(CalculatedIndicator):
    code = "ema_200"
    lookback_days = 200

    def compute(
        self,
        prices_df: pd.DataFrame,
        indicators_df: pd.DataFrame | None = None,
    ) -> pd.Series:
        prices_df = prices_df.sort_values("trade_date")
        close = prices_df.set_index("trade_date")["close_price"]

        # EMA: ewm(span=200), standardowo adjust=False (bardziej "trading-like")
        ema = close.ewm(span=self.lookback_days, adjust=False).mean()
        return ema
