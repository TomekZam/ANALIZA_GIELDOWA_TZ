import pandas as pd
import numpy as np
from analysis.calculated_indicators.base import CalculatedIndicator

class TQS60D(CalculatedIndicator):
    """
    Trend Quality Score 60d (TQS) – Jakość trendu w oknie 60 dni
    """
    code = "tqs_60d"
    required_indicators = []

    def compute(
        self,
        prices_df: pd.DataFrame,
        indicators_df: pd.DataFrame | None = None,
    ) -> pd.Series:
        prices_df = prices_df.sort_values("trade_date")
        close = prices_df["close_price"].values

        def tqs_window(x):
            y = x
            X = np.arange(len(y))
            if np.all(np.isnan(y)):
                return np.nan
            a, b = np.polyfit(X, y, 1)
            y_fit = a * X + b
            residuals = y - y_fit
            std_res = np.std(residuals)
            return np.abs(a) / std_res if std_res > 0 else np.nan

        tqs = pd.Series(close).rolling(window=60, min_periods=60).apply(tqs_window, raw=True)
        return pd.Series(tqs.values, index=prices_df["trade_date"])
