# analysis/calculated_indicators/registry.py
"""
Registry wskaźników wyliczanych lokalnie (calculated indicators).

To jest SINGLE SOURCE OF TRUTH dla:
- dostępnych wskaźników
- mapowania: indicator_code -> implementacja

Dispatcher i UI korzystają wyłącznie z tego rejestru.
"""

from .ind.ind_momentum_12m import Momentum12M
from .ind.ind_volatility_20d import Volatility20D
from .ind.ind_earnings_yield import EarningsYield
from .ind.ind_sharpe_20d import Sharpe20D
from .ind.ind_sma_200 import SMA200
from .ind.ind_sma_50 import SMA50
from .ind.ind_sma_20 import SMA20
from .ind.ind_ema_200 import EMA200
from .ind.ind_ema_50 import EMA50
from .ind.ind_ema_20 import EMA20
from .ind.ind_rsi_14 import RSI14
from .ind.ind_ema_12 import EMA12
from .ind.ind_ema_26 import EMA26
from .ind.ind_macd_line import MACDLine
from .ind.ind_macd_signal import MACDSignal
from .ind.ind_macd_hist import MACDHist
from .ind.ind_average_volume_20d import AverageVolume20D
from .ind.ind_obv import OBV
from .ind.ind_vwap_20d import VWAP20D
from .ind.ind_atr_14 import ATR14
from .ind.ind_max_drawdown_252d import MaxDrawdown252D
from .ind.ind_tqs_60d import TQS60D
from .ind.ind_fut_barrier_5p_3p_5d import FutBarrier5p3p5D
from .ind.ind_fut_barrier_20p_12p_20d import FutBarrier20p12p20D
from .ind.ind_fut_barrier_20p_12p_60d import FutBarrier20p12p60D
from .ind.ind_fut_barrier_50p_20p_120d import FutBarrier50p20p120D
from .ind.ind_fut_barrier_100p_50p_20d import FutBarrier100p50p20D
from .ind.ind_fut_barrier_50p_20p_20d import FutBarrier50p20p20D
from .ind.ind_fut_barrier_50p_20p_60d import FutBarrier50p20p60D
from .ind.ind_fut_barrier_20p_12p_2d import FutBarrier20p12p2D
from .ind.ind_fut_imp_2 import FutImp2
from .ind.ind_fut_imp_20 import FutImp20
from .ind.ind_fut_imp_60 import FutImp60
from .ind.ind_fut_imp_120 import FutImp120
from .ind.ind_fut_signal_2 import FutSignal2
from .ind.ind_fut_signal_20 import FutSignal20
from .ind.ind_fut_signal_60 import FutSignal60
from .ind.ind_fut_signal_120 import FutSignal120
from .ind.ind_fut_signal_20_hyb import FutSignal20Hyb


INDICATORS_REGISTRY = {
    "momentum_12m": Momentum12M(),
    "volatility_20d": Volatility20D(),
    "earnings_yield": EarningsYield(),
    "sharpe_20d": Sharpe20D(),
    "sma_20": SMA20(),  
    "sma_50": SMA50(),
    "sma_200": SMA200(),
    "ema_12": EMA12(),
    "ema_20": EMA20(),
    "ema_26": EMA26(),
    "ema_50": EMA50(),
    "ema_200": EMA200(),
    "rsi_14": RSI14(),
    "macd_line": MACDLine(),
    "macd_signal": MACDSignal(),
    "macd_hist": MACDHist(),
    "average_volume_20d": AverageVolume20D(),
    "obv": OBV(),
    "vwap_20d": VWAP20D(),
    "atr_14": ATR14(),
    "max_drawdown_252d": MaxDrawdown252D(),
    "tqs_60d": TQS60D(),
    "fut_barrier_5p_3p_5d": FutBarrier5p3p5D(),
    "fut_barrier_20p_12p_20d": FutBarrier20p12p20D(),
    "fut_barrier_20p_12p_60d": FutBarrier20p12p60D(),
    "fut_barrier_50p_20p_120d": FutBarrier50p20p120D(),
    "fut_barrier_100p_50p_20d": FutBarrier100p50p20D(),
    "fut_barrier_50p_20p_20d": FutBarrier50p20p20D(),
    "fut_barrier_50p_20p_60d": FutBarrier50p20p60D(),
    "fut_barrier_20p_12p_2d": FutBarrier20p12p2D(),
    "fut_imp_2": FutImp2(),
    "fut_imp_20": FutImp20(),
    "fut_imp_60": FutImp60(),
    "fut_imp_120": FutImp120(),
    "fut_signal_2": FutSignal2(),
    "fut_signal_20": FutSignal20(),
    "fut_signal_60": FutSignal60(),
    "fut_signal_120": FutSignal120(),
    "fut_signal_20_hyb": FutSignal20Hyb(),


}