import pandas as pd
from analysis.calculated_indicators.base import CalculatedIndicator

class VWAP20D(CalculatedIndicator):
    """
    VWAP 20d (Volume Weighted Average Price) – Średnia cena ważona wolumenem z 20 dni
    """
    code = "vwap_20d"
    required_indicators = []

    def compute(
        self,
        prices_df: pd.DataFrame,
        indicators_df: pd.DataFrame | None = None,
    ) -> pd.Series:
        prices_df = prices_df.sort_values("trade_date")
        price = prices_df["close_price"]
        volume = prices_df["volume"]
        vwap = (
            (price * volume)
            .rolling(window=20, min_periods=20)
            .sum() /
            volume.rolling(window=20, min_periods=20).sum()
        )
        return pd.Series(vwap.values, index=prices_df["trade_date"])
