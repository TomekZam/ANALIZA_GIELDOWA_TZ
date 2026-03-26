import pandas as pd

from ..base import CalculatedIndicator


class EMA26(CalculatedIndicator):
    """
    EMA(26) – średnioterminowy trend.

    Liczona na close_price.
    Zwraca Series z indeksem trade_date (spójnie z innymi wskaźnikami).
    """

    code = "ema_26"
    lookback_days = 26

    def compute(
        self,
        prices_df: pd.DataFrame,
        indicators_df: pd.DataFrame | None = None,
    ) -> pd.Series:
        prices_df = prices_df.sort_values("trade_date")
        close = prices_df.set_index("trade_date")["close_price"]

        # EMA: ewm(span=26), adjust=False (spójnie z innymi EMA)
        ema = close.ewm(span=self.lookback_days, adjust=False).mean()
        return ema
