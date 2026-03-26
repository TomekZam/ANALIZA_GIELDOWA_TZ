import pandas as pd
from analysis.calculated_indicators.base import CalculatedIndicator

class MACDHist(CalculatedIndicator):
    """
    MACD histogram = macd_line - macd_signal

    Wymaga:
    - macd_line
    - macd_signal
    """
    code = "macd_hist"
    required_indicators = ["macd_line", "macd_signal"]

    def compute(
        self,
        prices_df: pd.DataFrame,
        indicators_df: pd.DataFrame | None = None,
    ) -> pd.Series:
        if indicators_df is None:
            raise ValueError("MACDHist requires indicators_df")

        indicators_df = indicators_df.sort_values("trade_date")
        macd_line = indicators_df.set_index("trade_date")["macd_line"]
        macd_signal = indicators_df.set_index("trade_date")["macd_signal"]
        return macd_line - macd_signal
