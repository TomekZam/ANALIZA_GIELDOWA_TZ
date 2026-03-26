import pandas as pd

from analysis.calculated_indicators.base import CalculatedIndicator


class MACDLine(CalculatedIndicator):
    """
    MACD line = EMA(12) - EMA(26)

    Wymaga:
    - ema_12
    - ema_26
    """

    code = "macd_line"
    required_indicators = ["ema_12", "ema_26"]

    def compute(
        self,
        prices_df: pd.DataFrame,
        indicators_df: pd.DataFrame | None = None,
    ) -> pd.Series:
        if indicators_df is None:
            raise ValueError("MACDLine requires indicators_df")

        indicators_df = indicators_df.sort_values("trade_date")

        ema_12 = indicators_df.set_index("trade_date")["ema_12"]
        ema_26 = indicators_df.set_index("trade_date")["ema_26"]
        return ema_12 - ema_26

