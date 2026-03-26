import pandas as pd

from ..base import CalculatedIndicator


class EMA12(CalculatedIndicator):
    code = "ema_12"
    span = 12

    def compute(
        self,
        prices_df: pd.DataFrame,
        indicators_df: pd.DataFrame | None = None,
    ) -> pd.Series:
        prices_df = prices_df.sort_values("trade_date")
        close = prices_df.set_index("trade_date")["close_price"]

        return close.ewm(span=self.span, adjust=False).mean()
