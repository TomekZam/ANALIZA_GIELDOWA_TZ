# app/ui/column_metadata.py

COLUMN_LABELS = {
    # --- identyfikacja ---
    "name": "Spółka",
    "ticker": "Ticker",
    "company_name": "Nazwa spółki",
    "change": "Zmiana %",

    # --- notowania ---
    "trade_date": "Data",
    "open_price": "Cena otwarcia",
    "high_price": "Cena maksymalna",
    "low_price": "Cena minimalna",
    "close_price": "Cena",
    "volume": "Wolumen",

    # --- fundamenty ---
    "mv": "Kapitalizacja",
    "pe": "P/E",
    "pb": "P/B",
    "earnings_yield": "Stopa zwrotu z zysków",

    # --- momentum / ryzyko ---
    "momentum_12m": "Momentum 12 M",
    "volatility_20d": "Zmienność 20 D",
    "sharpe_20d": "Sharpe 20 D",
    "max_drawdown_252d": "Max obniżenie 252 D",

    # --- trendy ---
    "sma_20": "SMA 20",
    "sma_50": "SMA 50",
    "sma_200": "SMA 200",
    "ema_12": "EMA 12",
    "ema_20": "EMA 20",
    "ema_26": "EMA 26",
    "ema_50": "EMA 50",
    "ema_200": "EMA 200",

    # --- oscylatory ---
    "rsi_14": "RSI 14",
    "macd_line": "MACD",
    "macd_signal": "MACD Sygnał",
    "macd_hist": "MACD Histogram",

    # --- wolumen / zmienność ---
    "average_volume_20d": "Śr. wolumen 20 D",
    "obv": "OBV",
    "vwap_20d": "VWAP 20 D",
    "atr_14": "ATR 14",

    # --- scoring ---
    "tqs_60d": "TQS 60 D",

    # --- future / ML: barriery ---
    "fut_barrier_20p_12p_60d": "Bariera w 60D (+20% / -12%)",
    "fut_barrier_100p_50p_20d": "Bariera w 20D (+100% / -50%)",
    "fut_barrier_50p_20p_20d": "Bariera w 20D (+50% / -20%)",
    "fut_barrier_20p_12p_20d": "Bariera w 20D (+20% / -12%)",
    "fut_barrier_50p_20p_60d": "Bariera w 60D (+50% / -20%)",
    "fut_barrier_50p_20p_120d": "Bariera w 120D (+50% / -20%)",
    "fut_barrier_5p_3p_5d": "Bariera w 5D (+5% / -3%)",
    "fut_barrier_20p_12p_2d": "Bariera w 2D (+20% / -12%)",

    # --- future / ML impuls ---
    "fut_imp_2": "Suma imp. w 2 D",
    "fut_imp_20": "Suma imp. w 20 D",
    "fut_imp_60": "Suma imp. w 60 D",
    "fut_imp_120": "Suma imp. w 120 D",

    # --- future / ML sygnał ---
    "fut_signal_2": "Sygnał 2 D",
    "fut_signal_20": "Sygnał 20 D",
    "fut_signal_60": "Sygnał 60 D",
    "fut_signal_120": "Sygnał 120 D",

     # --- future / ML sygnał hybrydowy ---   
    "fut_signal_20_hyb": "Sygnał 20 D (hyb.)",



}


COLUMN_GROUPS = {
    "core": {
        "label": "Notowania",
        "columns": [
            "trade_date",
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "volume",
        ],
        "default": True,
    },
    "fundamentals": {
        "label": "Fundamenty",
        "columns": ["mv", "pe", "pb", "earnings_yield"],
        "default": True,
    },
    "momentum_risk": {
        "label": "Momentum / ryzyko",
        "columns": ["momentum_12m", "volatility_20d", "sharpe_20d", "max_drawdown_252d"],
        "default": True,
    },
    "trends": {
        "label": "Trendy (SMA / EMA)",
        "columns": ["sma_20", "sma_50", "sma_200", "ema_12", "ema_20", "ema_26", "ema_50", "ema_200"],
        "default": False,
    },
    "oscillators": {
        "label": "Oscylatory",
        "columns": ["rsi_14", "macd_line", "macd_signal", "macd_hist"],
        "default": False,
    },
    "volume_vol": {
        "label": "Wolumen / zmienność",
        "columns": ["average_volume_20d", "obv", "vwap_20d", "atr_14"],
        "default": False,
    },
    "quality": {
        "label": "Jakość / scoring",
        "columns": ["tqs_60d"],
        "default": False,
    },
    "future_signals": {
        "label": "Future: sygnały / impact",
        "columns": [
            "fut_signal_2", "fut_signal_20", "fut_signal_60", "fut_signal_120", "fut_signal_20_hyb",
            "fut_imp_2", "fut_imp_20", "fut_imp_60", "fut_imp_120",
        ],
        "default": False,
    },
    "future_barriers": {
        "label": "Future: bariery",
        "columns": [
            "fut_barrier_20p_12p_2d",
            "fut_barrier_5p_3p_5d",
            "fut_barrier_20p_12p_20d",
            "fut_barrier_50p_20p_20d",
            "fut_barrier_100p_50p_20d",
            "fut_barrier_20p_12p_60d",
            "fut_barrier_50p_20p_60d",
            "fut_barrier_50p_20p_120d",
        ],
        "default": False,
    },
}



# ============================================================
# Rozszerzone opisy wskaźników (tooltipy UI)
# ============================================================

INDICATOR_TOOLTIPS: dict[str, str] = {

    # --- IDENTYFIKACJA / META -------------------------------------------
    "name": "Nazwa logiczna spółki używana w systemie.",
    "ticker": "Ticker giełdowy spółki.",
    "company_name": "Pełna nazwa spółki notowanej na giełdzie.",
    "change": (
        "Procentowa zmiana ceny zamknięcia względem poprzedniej sesji.\n\n"
        "Szybki wskaźnik kierunku i skali dziennego ruchu."
    ),

    # --- NOTOWANIA -------------------------------------------------------
    "trade_date": "Data sesji giełdowej.",
    "open_price": "Cena otwarcia instrumentu w danym dniu.",
    "high_price": "Najwyższa cena osiągnięta w trakcie sesji.",
    "low_price": "Najniższa cena osiągnięta w trakcie sesji.",

    "close_price": (
        "Cena zamknięcia instrumentu w danym dniu sesyjnym.\n\n"
        "Podstawowa referencja do obliczeń wskaźników i analiz trendu."
    ),

    "volume": (
        "Wolumen obrotu – liczba akcji, które zmieniły właściciela.\n\n"
        "Potwierdza siłę lub słabość ruchu ceny."
    ),

    # --- FUNDAMENTY ------------------------------------------------------
    "mv": (
        "Kapitalizacja rynkowa spółki.\n\n"
        "Iloczyn liczby akcji i ceny rynkowej. "
        "Opisuje skalę spółki."
    ),

    "pe": (
        "P/E – Price to Earnings.\n\n"
        "Relacja ceny akcji do zysku na akcję. "
        "Im niższe P/E, tym potencjalnie tańsza spółka."
    ),

    "pb": (
        "P/B – Price to Book Value.\n\n"
        "Relacja ceny rynkowej do wartości księgowej spółki."
    ),

    "earnings_yield": (
        "Stopa zwrotu z zysków (Earnings Yield).\n\n"
        "Odwrotność P/E. Ułatwia porównania z rentownością obligacji."
    ),

    # --- MOMENTUM / RYZYKO -----------------------------------------------
    "momentum_12m": (
        "Momentum 12M.\n\n"
        "Zmiana ceny w horyzoncie 12 miesięcy. "
        "Mierzy długoterminową siłę trendu."
    ),

    "volatility_20d": (
        "Zmienność 20D.\n\n"
        "Miara rozrzutu dziennych zmian ceny w krótkim terminie."
    ),

    "sharpe_20d": (
        "Wskaźnik Sharpe’a (20 dni).\n\n"
        "Relacja stopy zwrotu do ponoszonego ryzyka."
    ),

    "max_drawdown_252d": (
        "Maksymalne obsunięcie kapitału z ostatnich 252 sesji.\n\n"
        "Pokazuje najgorszy historyczny scenariusz straty."
    ),

    # --- TRENDY: SMA / EMA -----------------------------------------------
    "sma_20": "SMA 20 – krótkoterminowa prosta średnia krocząca.",
    "sma_50": "SMA 50 – średnioterminowa prosta średnia krocząca.",
    "sma_200": (
        "SMA 200 – długoterminowa średnia krocząca.\n\n"
        "Granica pomiędzy trendem wzrostowym i spadkowym."
    ),

    "ema_12": "EMA 12 – szybka wykładnicza średnia krocząca.",
    "ema_20": "EMA 20 – krótkoterminowa wykładnicza średnia krocząca.",
    "ema_26": "EMA 26 – wolniejsza EMA używana w MACD.",
    "ema_50": "EMA 50 – średnioterminowa wykładnicza średnia krocząca.",
    "ema_200": "EMA 200 – długoterminowa wykładnicza średnia krocząca.",

    # --- OSCYLATORY ------------------------------------------------------
    "rsi_14": (
        "RSI 14 – Relative Strength Index.\n\n"
        "Oscylator pokazujący stany wykupienia i wyprzedania rynku."
    ),

    "macd_line": (
        "MACD – różnica EMA 12 i EMA 26.\n\n"
        "Identyfikuje zmiany momentum i trendu."
    ),

    "macd_signal": (
        "Linia sygnału MACD.\n\n"
        "Przecięcia z MACD generują sygnały transakcyjne."
    ),

    "macd_hist": (
        "Histogram MACD.\n\n"
        "Pokazuje tempo narastania lub wygasania momentum."
    ),

    # --- WOLUMEN / ZMIENNOŚĆ ---------------------------------------------
    "average_volume_20d": (
        "Średni wolumen z 20 sesji.\n\n"
        "Punkt odniesienia dla bieżącej aktywności rynku."
    ),

    "obv": (
        "OBV – On Balance Volume.\n\n"
        "Kumulatywny wskaźnik wolumenu potwierdzający trend ceny."
    ),

    "vwap_20d": (
        "VWAP 20D – średnia cena ważona wolumenem.\n\n"
        "Pokazuje realny średni koszt transakcji."
    ),

    "atr_14": (
        "ATR 14 – Average True Range.\n\n"
        "Miara zmienności, często używana do zarządzania ryzykiem."
    ),

    # --- JAKOŚĆ / SCORING -----------------------------------------------
    "tqs_60d": (
        "TQS 60D – syntetyczny wskaźnik jakości trendu.\n\n"
        "Łączy stabilność, kierunek i zmienność ruchu ceny."
    ),


    # --- FUTURE / ML: BARIERY -------------------------------------------
    "fut_barrier_20p_12p_2d": (
        "Informacja o tym, że w horyzoncie 2 sesji\n\n"  
        "+1 - jako pierwsza pokonana będzie bariera +20%\n\n"
        "-1 - jako pierwsza pokonana będzie bariera -12%\n\n"                   
    ),
    "fut_barrier_5p_3p_5d": (
        "Informacja o tym, że w horyzoncie 5 sesji\n\n"  
        "+1 - jako pierwsza pokonana będzie bariera +5%\n\n"
        "-1 - jako pierwsza pokonana będzie bariera -3%\n\n"                   
        "Znak tej bariery zatwierdza kierunek pojawiania się sygnałów (wykorzystane w fut_signal_X i fut_signal_20_hyb)\n\n"   
    ),    
    "fut_barrier_20p_12p_20d": (
        "Informacja o tym, że w horyzoncie 20 sesji\n\n"  
        "+1 - jako pierwsza pokonana będzie bariera +20%\n\n"
        "-1 - jako pierwsza pokonana będzie bariera -12%\n\n"                   
    ),
    "fut_barrier_50p_20p_20d": (
        "Informacja o tym, że w horyzoncie 20 sesji\n\n"  
        "+1 - jako pierwsza pokonana będzie bariera +50%\n\n"
        "-1 - jako pierwsza pokonana będzie bariera -20%\n\n"                   
    ),
    "fut_barrier_100p_50p_20d": (
        "Informacja o tym, że w horyzoncie 20 sesji\n\n"  
        "+1 - jako pierwsza pokonana będzie bariera +100%\n\n"
        "-1 - jako pierwsza pokonana będzie bariera -50%\n\n"                   
    ),
    "fut_barrier_20p_12p_60d": (
        "Informacja o tym, że w horyzoncie 60 sesji\n\n"  
        "+1 - jako pierwsza pokonana będzie bariera +20%\n\n"
        "-1 - jako pierwsza pokonana będzie bariera -12%\n\n"                   
    ),
    "fut_barrier_50p_20p_60d": (
        "Informacja o tym, że w horyzoncie 60 sesji\n\n"  
        "+1 - jako pierwsza pokonana będzie bariera +50%\n\n"
        "-1 - jako pierwsza pokonana będzie bariera -20%\n\n"                   
    ),
    "fut_barrier_50p_20p_120d": (
        "Informacja o tym, że w horyzoncie 120 sesji\n\n"  
        "+1 - jako pierwsza pokonana będzie bariera +50%\n\n"
        "-1 - jako pierwsza pokonana będzie bariera -20%\n\n"                   
    ),


    # --- FUTURE / ML: IMPULS --------------------------------------------
    "fut_imp_2": (
        "Informacja o impulsie w horyzoncie 2 sesji\n\n"
        "+64 - jako pierwszy wystąpi wzrost +20%\n\n"
        "-64 - jako pierwszy wystąpi spadek -12%"
    ),
    "fut_imp_20": (
        "Suma informacji o impulsie w horyzoncie 20 sesji\n\n"
        "+32 - jako pierwszy wystąpi wzrost +100%\n\n"
        "-32 - jako pierwszy wystąpi spadek -50%\n\n"        
        "+16 - jako pierwszy wystąpi wzrost +50%\n\n"
        "-16 - jako pierwszy wystąpi spadek -20%\n\n"   
        "+8 - jako pierwszy wystąpi wzrost +20%\n\n"
        "-8 - jako pierwszy wystąpi spadek -12%\n\n"           
        "Opisuje siłę i spójność impulsu, nie jego kierunek."
    ),
    "fut_imp_60": (
        "Suma informacji o impulsie w horyzoncie 60 sesji\n\n"  
        "+4 - jako pierwszy wystąpi wzrost +50%\n\n"
        "-4 - jako pierwszy wystąpi spadek -20%\n\n"   
        "+2 - jako pierwszy wystąpi wzrost +20%\n\n"
        "-2 - jako pierwszy wystąpi spadek -12%\n\n"           
        "Opisuje siłę i spójność impulsu, nie jego kierunek."        
    ),
    "fut_imp_120": (
        "Suma informacji o impulsie w horyzoncie 120 sesji\n\n"  
        "+1 - jako pierwszy wystąpi wzrost +50%\n\n"
        "-1 - jako pierwszy wystąpi spadek -20%\n\n"           
        "Opisuje siłę i spójność impulsu, nie jego kierunek."            
    ),

    # --- FUTURE / ML: SYGNAŁY -------------------------------------------
    "fut_signal_2": (
        "Sygnał wzmocnienia impulsu w horyzoncie 2 sesji\n\n"  
        "+1 - wzmocnią się wzrosty\n\n"
        "-1 - pogłębią się spadki\n\n"           
        "Czy rynek pozwalał na sensowne granie w tym kierunku?\n\n" 
        "Binarny i niepowtarzający się w kolejnych sesjach sygnał kierunkowy."           
    ),
    "fut_signal_20": (
        "Sygnał wzmocnienia impulsu w horyzoncie 20 sesji\n\n"  
        "+1 - wzmocnią się wzrosty\n\n"
        "-1 - pogłębią się spadki\n\n"           
        "Czy rynek pozwalał na sensowne granie w tym kierunku?\n\n" 
        "Binarny i niepowtarzający się w kolejnych sesjach sygnał kierunkowy."           
    ),
    "fut_signal_60": (
        "Sygnał wzmocnienia impulsu w horyzoncie 60 sesji\n\n"  
        "+1 - wzmocnią się wzrosty\n\n"
        "-1 - pogłębią się spadki\n\n"           
        "Czy rynek pozwalał na sensowne granie w tym kierunku?\n\n" 
        "Binarny i niepowtarzający się w kolejnych sesjach sygnał kierunkowy."           
    ),
    "fut_signal_120": (
        "Sygnał wzmocnienia impulsu w horyzoncie 120 sesji\n\n"  
        "+1 - wzmocnią się wzrosty\n\n"
        "-1 - pogłębią się spadki\n\n"           
        "Czy rynek pozwalał na sensowne granie w tym kierunku?\n\n" 
        "Binarny i niepowtarzający się w kolejnych sesjach sygnał kierunkowy."           
    ),

    "fut_signal_20_hyb": (
        "Sygnał hybrydowy 20D.\n\n"
        "Uwzględnia zarówno klasyczny sygnał fut_signal_20, jak i kontynuację trendu.\n\n"
        "Sygnał mówi: Czy w tym miejscu pojawił się nowy, jakościowy impuls, a nie tylko kontynuacja stanu rynku?\n\n"
        "Dodatkowo `fut_signal_20_hyb` wymaga wcześniejszego osłabienia / pauzy, resetu referencji, braku bezpośredniego powtórzenia impulsu.\n\n"
        "Dlatego `fut_signal_20_hyb` jest rzadszy, ale bardziej wartościowy niż `fut_signal_20`.\n\n"
        "Binarny i niepowtarzający się w kolejnych sesjach sygnał kierunkowy."

    ),


}
