
from __future__ import annotations

from typing import Any, Dict

def set_param(name: str, value: Any) -> None:
    """
    Ustawia wartość parametru aplikacyjnego (do cache'owania statusu, np. połączenia z bazą).
    """
    _APP_PARAMS[name] = value


# ============================================================
# CENTRALNE REPOZYTORIUM PARAMETRÓW APLIKACYJNYCH
# ------------------------------------------------------------
# - parametry jawne (wersjonowane w repo)
# - read-only (nieedytowane w runtime)
# - dostęp WYŁĄCZNIE przez get_param()
# ============================================================

_APP_PARAMS: Dict[str, Any] = {
    
    # --------------------------------------------------------
    # Połączenie z bazą danych
    # --------------------------------------------------------
    # Parametr określający czy połączenie z bazą danych jest dostępne
    # Uwaga: aktualizowany dynamicznie w runtime, nie wersjonowany
    "DB_CONNECTION_AVAILABLE": False,


    # --------------------------------------------------------
    # Tryb pracy aplikacji
    # --------------------------------------------------------

    # DEMO: aplikacja działa WYŁĄCZNIE na CSV (bez DB)
    # DEV : aplikacja może używać DB
    "APP_MODE": "DEMO",   # DEMO | DEV

    # Flaga pochodna – NIE ZMIENIANA runtime
    "APP_TEST_ON_CSV_FILES": True,


    # --------------------------------------------------------
    # Ścieżki i pliki do logo
    "APP_ASSETS_PATH": "app/ui/assets",
    "APP_LOGO_FILE": "logo_angg.png",

    # --------------------------------------------------------
    # Eksport do CSV
    # --------------------------------------------------------
    
    # Grupa WSE:
    "DATA_WSE_PATH": "analysis/data/wse/",
    "DATA_WSE_COMPANIES": "companies.csv",
    "DATA_WSE_PRICES_DAILY": "prices_daily.csv",
    "DATA_WSE_IND_DAILY": "indicators_daily.csv",
    "DATA_WSE_IND_DICT": "indicators_dictionary.csv",
    # Wig 20:
    # "EXPORT_TOCSV_WSE_TICKERS": "ALE, ALR, BDX, CCC, CDR, DNP, KGH, KRU, KTY, LPP, MBK, OPL, PCO, PEO, PGE, PKN, PKO, PZU, SPL, ZAB",
    # Wig 40:
    # "EXPORT_TOCSV_WSE_TICKERS": "11B, ABE, ACP, APR, ASB, ASE, ATT, BFT, BHW, BNP, CAR, CBF, CPS, DIA, DOM, DVL, EAT, ENA, EUR, GPP, GPW, HUG, ING, JSW, LBW, MBR, MIL, MRB, NEU, NWG, PEP, RBW, SNT, TEN, TPE, TXT, VOX, VRC, WPL, XTB",
    # Wig 80:
    # "EXPORT_TOCSV_WSE_TICKERS": "1AT, ABS, ACG, AGO, ALL, AMB, AMC, APT, ARH, ARL, AST, ATC, BCX, BIO, BLO, BMC, BOS, BRS, CIG, CLC, CLN, CMP, COG, CRI, CRJ, CTX, DAD, DAT, DCR, ECH, ELT, ENT, ERB, FRO, FTE, GEA, GRX, KGN, LWB, MAB, MCI, MCR, MDG, MLG, MLS, MNC, MRC, MSZ, MUR, OND, OPN, PBX, PCR, PLW, PXM, QRS, RVU, SCP, SEL, SGN, SHO, SKA, SLV, SNK, STP, STX, SVE, TAR, TOA, TOR, UNI, UNT, VGO, VOT, VRG, WLT, WTN, WWL, XTP, ZEP",
    # Wig 20 + Wig 40:
    "EXPORT_TOCSV_WSE_TICKERS": "ALE, ALR, BDX, CCC, CDR, DNP, KGH, KRU, KTY, LPP, MBK, OPL, PCO, PEO, PGE, PKN, PKO, PZU, SPL, ZAB, 11B, ABE, ACP, APR, ASB, ASE, ATT, BFT, BHW, BNP, CAR, CBF, CPS, DIA, DOM, DVL, EAT, ENA, EUR, GPP, GPW, HUG, ING, JSW, LBW, MBR, MIL, MRB, NEU, NWG, PEP, RBW, SNT, TEN, TPE, TXT, VOX, VRC, WPL, XTB",
    # Wig 20 + Wig 40 + Wig 80
    #"EXPORT_TOCSV_WSE_TICKERS": "ALE, ALR, BDX, CCC, CDR, DNP, KGH, KRU, KTY, LPP, MBK, OPL, PCO, PEO, PGE, PKN, PKO, PZU, SPL, ZAB, 11B, ABE, ACP, APR, ASB, ASE, ATT, BFT, BHW, BNP, CAR, CBF, CPS, DIA, DOM, DVL, EAT, ENA, EUR, GPP, GPW, HUG, ING, JSW, LBW, MBR, MIL, MRB, NEU, NWG, PEP, RBW, SNT, TEN, TPE, TXT, VOX, VRC, WPL, XTB, 1AT, ABS, ACG, AGO, ALL, AMB, AMC, APT, ARH, ARL, AST, ATC, BCX, BIO, BLO, BMC, BOS, BRS, CIG, CLC, CLN, CMP, COG, CRI, CRJ, CTX, DAD, DAT, DCR, ECH, ELT, ENT, ERB, FRO, FTE, GEA, GRX, KGN, LWB, MAB, MCI, MCR, MDG, MLG, MLS, MNC, MRC, MSZ, MUR, OND, OPN, PBX, PCR, PLW, PXM, QRS, RVU, SCP, SEL, SGN, SHO, SKA, SLV, SNK, STP, STX, SVE, TAR, TOA, TOR, UNI, UNT, VGO, VOT, VRG, WLT, WTN, WWL, XTP, ZEP",

    "EXPORT_DATE_FROM": "1990-01-01",
    "EXPORT_DATE_TO": "2026-01-01",

 
    # --------------------------------------------------------
    # Podgląd danych
    # --------------------------------------------------------
    
    # Grupa WSE:
    "LOAD_DATA_WSE_PATH": "analysis/data/wse/",
    "LOAD_DATA_WSE_COMPANIES": "companies.csv",
    "LOAD_DATA_WSE_PRICES_DAILY": "prices_daily.csv",
    "LOAD_DATA_WSE_IND_DAILY": "indicators_daily.csv",
    "LOAD_DATA_WSE_IND_DICT": "indicators_dictionary.csv",
    "LOAD_TICKERS": "ALE, ALR, BDX, CCC, CDR, DNP, KGH, KRU, KTY, LPP, MBK, OPL, PCO, PEO, PGE, PKN, PKO, PZU, SPL, ZAB",
    # Wig 20
    # "LOAD_TICKERS": "ALE, ALR, BDX, CCC, CDR, DNP, KGH, KRU, KTY, LPP, MBK, OPL, PCO, PEO, PGE, PKN, PKO, PZU, SPL, ZAB",
    # Wig 40
    # "LOAD_TICKERS": "11B, ABE, ACP, APR, ASB, ASE, ATT, BFT, BHW, BNP, CAR, CBF, CPS, DIA, DOM, DVL, EAT, ENA, EUR, GPP, GPW, HUG, ING, JSW, LBW, MBR, MIL, MRB, NEU, NWG, PEP, RBW, SNT, TEN, TPE, TXT, VOX, VRC, WPL, XTB",
    # Wig 80
    # "LOAD_TICKERS": "1AT, ABS, ACG, AGO, ALL, AMB, AMC, APT, ARH, ARL, AST, ATC, BCX, BIO, BLO, BMC, BOS, BRS, CIG, CLC, CLN, CMP, COG, CRI, CRJ, CTX, DAD, DAT, DCR, ECH, ELT, ENT, ERB, FRO, FTE, GEA, GRX, KGN, LWB, MAB, MCI, MCR, MDG, MLG, MLS, MNC, MRC, MSZ, MUR, OND, OPN, PBX, PCR, PLW, PXM, QRS, RVU, SCP, SEL, SGN, SHO, SKA, SLV, SNK, STP, STX, SVE, TAR, TOA, TOR, UNI, UNT, VGO, VOT, VRG, WLT, WTN, WWL, XTP, ZEP",
    # Wig 20 + Wig 40:
    "LOAD_TICKERS": "ALE, ALR, BDX, CCC, CDR, DNP, KGH, KRU, KTY, LPP, MBK, OPL, PCO, PEO, PGE, PKN, PKO, PZU, SPL, ZAB, 11B, ABE, ACP, APR, ASB, ASE, ATT, BFT, BHW, BNP, CAR, CBF, CPS, DIA, DOM, DVL, EAT, ENA, EUR, GPP, GPW, HUG, ING, JSW, LBW, MBR, MIL, MRB, NEU, NWG, PEP, RBW, SNT, TEN, TPE, TXT, VOX, VRC, WPL, XTB",
    # Wig 20 + Wig 40 + Wig 80
    # "LOAD_TICKERS": "ALE, ALR, BDX, CCC, CDR, DNP, KGH, KRU, KTY, LPP, MBK, OPL, PCO, PEO, PGE, PKN, PKO, PZU, SPL, ZAB, 11B, ABE, ACP, APR, ASB, ASE, ATT, BFT, BHW, BNP, CAR, CBF, CPS, DIA, DOM, DVL, EAT, ENA, EUR, GPP, GPW, HUG, ING, JSW, LBW, MBR, MIL, MRB, NEU, NWG, PEP, RBW, SNT, TEN, TPE, TXT, VOX, VRC, WPL, XTB, 1AT, ABS, ACG, AGO, ALL, AMB, AMC, APT, ARH, ARL, AST, ATC, BCX, BIO, BLO, BMC, BOS, BRS, CIG, CLC, CLN, CMP, COG, CRI, CRJ, CTX, DAD, DAT, DCR, ECH, ELT, ENT, ERB, FRO, FTE, GEA, GRX, KGN, LWB, MAB, MCI, MCR, MDG, MLG, MLS, MNC, MRC, MSZ, MUR, OND, OPN, PBX, PCR, PLW, PXM, QRS, RVU, SCP, SEL, SGN, SHO, SKA, SLV, SNK, STP, STX, SVE, TAR, TOA, TOR, UNI, UNT, VGO, VOT, VRG, WLT, WTN, WWL, XTP, ZEP",
    "LOAD_DATE_FROM": "1990-01-01",
    "LOAD_DATE_TO": "2026-01-01",


    # --------------------------------------------------------
    # Aplikacja / UI
    # --------------------------------------------------------
    "APP_NAME": "Analiza Giełdowa",
    "APP_VERSION": "1.0.0",
    "APP_ENV": "prod",  # local | dev | prod (na przyszłość)



    # --------------------------------------------------------
    # UI – zachowanie / limity
    # --------------------------------------------------------
    "UI_PAGE_SIZE": 50,
    "UI_MAX_ROWS_PREVIEW": 1000,
    "UI_ENABLE_EXPERIMENTAL": False,
    "UI_DEFAULT_DRY_RUN": True,



    # --------------------------------------------------------


    # Calculated indicators – kontrola uruchomień
    # --------------------------------------------------------

    # Limit: calculate only 300 indicators
    "CALCULATE_ONLY_300_INDICATORS": False,



    # --------------------------------------------------------

    # Future / ML
    # --------------------------------------------------------

    # --------------------------------------------------------
    # ML-01 – Selekcja rankingowa (grid eksperymentów)
    # --------------------------------------------------------

    # Maksymalna liczba kandydatów w oknie (Top-K)
    "ML01_MAX_SIGNALS_GRID": [3, 5, 10],

    # Okno rankingowe w liczbie sesji handlowych (N unikalnych trade_date)
    "ML01_WINDOW_SESSIONS_GRID": [10, 25, 50],

    # Filtr jakościowy: procent najlepszych obserwacji w oknie (Top-Pct)
    # np. 0.001 = 0.1%, 0.005 = 0.5%, 0.05 = 5%
    "ML01_TOP_SCORE_PCT_GRID": [0.001, 0.005, 0.05],


    # --------------------------------------------------------
    # ML-01 – Target (y): lista dozwolonych etykiet do wyboru do badania w modelu ML
    # --------------------------------------------------------

    # Lista targetów (kolejność = kolejność w UI)
    "ML01_TARGET_SIGNAL_LIST": [
        "fut_signal_20_hyb",
        "fut_signal_20",
        "fut_signal_60",
        "fut_signal_120",
        #"fut_signal_2", # na razie nie chę tego sygnału na liście wyboru
    ],

    # --------------------------------------------------------
    # ML-01 – słownik opisów etykiet (Target y) dla fut_signal*
    # --------------------------------------------------------
    # Cel: poprawa UX w selectboxie targetu na ekranie ML-01.
    # UI pokazuje: "<nazwa kolumny> - <opis>".
    #
    # Konwencja wartości fut_signal_*:
    # +1 = zdarzenie pozytywne, -1 = negatywne, 0 = brak zdarzenia w horyzoncie,
    # NaN = brak pełnego horyzontu danych (końcówka szeregu).
    "ML01_TARGET_SIGNAL_DESCRIPTIONS": {
        "fut_signal_2": "Etykieta przewidująca wzrost  (+1) lub spadek (-1) w H=2 sesji. Efekt końcowy przewidziany w krótkim horyzoncie (2 sesje)",
        "fut_signal_20": "Etykieta przewidująca wzrost (+1) lub spadek (-1) w H=20 sesji. Efekt końcowy przewidziany w krótkim horyzoncie (~1 miesiąc)",
        "fut_signal_60": "Etykieta przewidująca wzrost (+1) lub spadek (-1) w H=60 sesji. Efekt końcowy przewidziany w średnim horyzoncie (~3 miesięcy)",
        "fut_signal_120": "Etykieta przewidująca wzrost (+1) lub spadek (-1) w H=120 sesji. Efekt końcowy przewidziany w dłuższym horyzoncie (~6 miesięcy)",
        "fut_signal_20_hyb": "Etykieta 'gold' przewidująca kontynuację wzrostu w H=20 sesji (hybrydowa). Rzadki jakościowy impuls / moment decyzyjny po pauzie",
    },

    # --------------------------------------------------------
    # ML-01 – skróty do nazw plików (krótka nazwa, ograniczona długość)
    # --------------------------------------------------------

    # Krótkie kody dla targetów (do filename + szybki podgląd w tabelach modeli)
    "ML01_TARGET_SIGNAL_SHORTCODES": {
        "fut_signal_2": "S2",
        "fut_signal_20": "S20",
        "fut_signal_60": "S60",
        "fut_signal_120": "S120",
        "fut_signal_20_hyb": "S20H",
    },

    # Krótkie kody filtrów jakościowych (do JSON + ewentualnie do filename)
    # Uwaga: filename ma być krótki -> do nazwy trafia tylko hash filtrów,
    # a pełna lista filtrów jest w JSON i w tabeli modeli jako kolumny dynamiczne.
    "ML01_QUALITY_FILTER_SHORTCODES": {
        "trend": ("TR", "Trend: ema_20 > ema_50"),
        "trend_long": ("TL", "Trend LT: ema_50 > ema_200"),
        "momentum": ("MOM", "Momentum: momentum_12m > 0"),
        "rsi_oversold": ("RSI30", "RSI < 30 (wyprzedanie)"),
        "macd_positive": ("MACD", "MACD > 0"),
        "price_above_sma200": ("SMA200", "Close > SMA200"),
        "rsi": ("RSI50", "RSI > 50"),
        "volatility": ("VOL", "Volatility > mediana"),
        "volume": ("VOLM", "Volume > mediana"),
        "rsi_not_overbought": ("RSI70", "RSI < 70 (brak wykupienia)"),
        "atr_high": ("ATR", "ATR > mediana"),
        "price_above_vwap": ("VWAP", "Close > VWAP"),
    },

}







def get_param(name: str) -> Any:
    """
    Zwraca wartość parametru aplikacyjnego.

    Zasady:
    - brak parametru = jawny błąd (fail fast)
    - brak wartości domyślnej (żeby nie ukrywać błędów)
    """
    if name not in _APP_PARAMS:
        raise KeyError(
            f"Brak parametru aplikacyjnego: '{name}'. "
            f"Dostępne: {sorted(_APP_PARAMS.keys())}"
        )
    return _APP_PARAMS[name]


def get_all_params() -> Dict[str, Any]:
    """
    Zwraca kopię parametrów (snapshot).
    Przydatne do diagnostyki, np. UI read-only.
    """
    return dict(_APP_PARAMS)


