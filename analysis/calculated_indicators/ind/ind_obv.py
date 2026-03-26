import pandas as pd
from analysis.calculated_indicators.base import CalculatedIndicator

class OBV(CalculatedIndicator):
    """
    OBV (On-Balance Volume) – Kierunek kapitału
    """
    code = "obv"
    required_indicators = []

    def compute(
        self,
        prices_df: pd.DataFrame,
        indicators_df: pd.DataFrame | None = None,
    ) -> pd.Series:
        prices_df = prices_df.sort_values("trade_date")
        close = prices_df["close_price"].values
        volume = prices_df["volume"].values

        obv = [0]
        for i in range(1, len(close)):
            if close[i] > close[i - 1]:
                obv.append(obv[-1] + volume[i])
            elif close[i] < close[i - 1]:
                obv.append(obv[-1] - volume[i])
            else:
                obv.append(obv[-1])
        return pd.Series(obv, index=prices_df["trade_date"])
