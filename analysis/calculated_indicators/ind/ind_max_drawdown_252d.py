import pandas as pd
from analysis.calculated_indicators.base import CalculatedIndicator

class MaxDrawdown252D(CalculatedIndicator):
    """
    Max Drawdown 252d (roczny) – Największe obsunięcie kapitału w oknie 252 dni
    """
    code = "max_drawdown_252d"
    required_indicators = []

    def compute(
        self,
        prices_df: pd.DataFrame,
        indicators_df: pd.DataFrame | None = None,
    ) -> pd.Series:
        prices_df = prices_df.sort_values("trade_date")
        close = prices_df["close_price"]

        def rolling_max_drawdown(series):
            roll_max = series.cummax()
            drawdown = (series - roll_max) / roll_max
            return drawdown.min()

        mdd = (
            close.rolling(window=252, min_periods=252)
            .apply(rolling_max_drawdown, raw=False)
        )
        return pd.Series(mdd.values, index=prices_df["trade_date"])
