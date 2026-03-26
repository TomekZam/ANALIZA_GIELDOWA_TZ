import pandas as pd
from analysis.calculated_indicators.base import CalculatedIndicator

class AverageVolume20D(CalculatedIndicator):
    """
    Średni wolumen obrotu z 20 dni (Average Volume 20d)
    """
    code = "average_volume_20d"
    required_indicators = []

    def compute(
        self,
        prices_df: pd.DataFrame,
        indicators_df: pd.DataFrame | None = None,
    ) -> pd.Series:
        prices_df = prices_df.sort_values("trade_date")
        return (
            prices_df.set_index("trade_date")["volume"]
            .rolling(window=20, min_periods=20)
            .mean()
        )
