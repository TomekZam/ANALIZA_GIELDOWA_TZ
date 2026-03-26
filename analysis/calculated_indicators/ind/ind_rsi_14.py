import pandas as pd
import numpy as np

from ..base import CalculatedIndicator


class RSI14(CalculatedIndicator):
    """
    RSI (14) – Relative Strength Index wg Wildera (EMA).
    Zakres: 0–100.
    """
    code = "rsi_14"
    lookback_days = 14

    def compute(
        self,
        prices_df: pd.DataFrame,
        indicators_df: pd.DataFrame | None = None,
    ) -> pd.Series:
        prices_df = prices_df.sort_values("trade_date")

        close = prices_df.set_index("trade_date")["close_price"]
        delta = close.diff()

        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)

        # Wilder RSI: EMA z alpha = 1/14
        avg_gain = gain.ewm(alpha=1 / self.lookback_days, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / self.lookback_days, adjust=False).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi
