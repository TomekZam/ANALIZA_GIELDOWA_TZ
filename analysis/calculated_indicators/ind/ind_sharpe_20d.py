import pandas as pd
import numpy as np

from ..base import CalculatedIndicator


class Sharpe20D(CalculatedIndicator):
    """
    Sharpe Ratio (20D) – uproszczony (bez stopy wolnej od ryzyka):
        sharpe_20d = mean(returns_log, 20) / volatility_20d

    Dane:
    - prices_df: trade_date, close_price
    - indicators_df: trade_date, volatility_20d
    """
    code = "sharpe_20d"
    lookback_days = 20
    required_indicators = ["volatility_20d"]

    def compute(
        self,
        prices_df: pd.DataFrame,
        indicators_df: pd.DataFrame | None = None,
    ) -> pd.Series:
        # 1) Prices → log returns
        prices_df = prices_df.sort_values("trade_date")
        close = prices_df.set_index("trade_date")["close_price"]
        returns = np.log(close / close.shift(1))

        mean_ret_20d = returns.rolling(self.lookback_days).mean()

        # 2) Volatility (zależność) – musi być w indicators_df
        if indicators_df is None or indicators_df.empty:
            # brak danych zależnych => nic nie policzymy
            return pd.Series(index=mean_ret_20d.index, dtype="float64")

        indicators_df = indicators_df.sort_values("trade_date").set_index("trade_date")

        if "volatility_20d" not in indicators_df.columns:
            # defensywnie: jeśli ktoś źle zdefiniuje required_indicators
            return pd.Series(index=mean_ret_20d.index, dtype="float64")

        vol_20d = indicators_df["volatility_20d"].astype("float64").replace(0.0, np.nan)

        # 3) Sharpe 20D
        sharpe_20d = mean_ret_20d / vol_20d

        # Zwracamy Series indeksowany trade_date (spójnie z resztą wskaźników)
        return sharpe_20d
