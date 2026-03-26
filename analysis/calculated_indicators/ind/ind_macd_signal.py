import pandas as pd

from ..base import CalculatedIndicator


class MACDSignal(CalculatedIndicator):
    """
    MACD Signal Line
    EMA(9) liczona na podstawie macd_line
    """

    code = "macd_signal"
    lookback_days = 9
    required_indicators = ["macd_line"]
    
    def compute(
        self,
        prices_df: pd.DataFrame,
        indicators_df: pd.DataFrame | None = None,
    ) -> pd.Series:
        if indicators_df is None:
            raise ValueError("MACDSignal requires indicators_df")

        indicators_df = indicators_df.sort_values("trade_date")

        macd_line = indicators_df.set_index("trade_date")["macd_line"]

        # EMA(9) na macd_line – spójnie z innymi EMA (adjust=False)
        macd_signal = macd_line.ewm(
            span=self.lookback_days,
            adjust=False
        ).mean()

        return macd_signal
