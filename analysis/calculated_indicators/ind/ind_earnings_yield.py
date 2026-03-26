import pandas as pd

from ..base import CalculatedIndicator


class EarningsYield(CalculatedIndicator):
    code = "earnings_yield"
    lookback_days = None
    required_indicators = ["pe"]


    def compute(
        self,
        prices_df: pd.DataFrame,
        indicators_df: pd.DataFrame | None,
    ) -> pd.Series:
        if indicators_df is None or "pe" not in indicators_df.columns:
            raise ValueError("EarningsYield requires 'pe' column in indicators_df")

        pe = indicators_df.set_index("trade_date")["pe"]
        pe = pe.where(pe > 0)
        return 1 / pe
