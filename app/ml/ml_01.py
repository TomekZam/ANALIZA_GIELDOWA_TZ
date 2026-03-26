# app/ui/ml_01.py
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib  # <-- potrzebne do wczytywania zapisanych modeli z dysku
import numpy as np
import pandas as pd
import streamlit as st
import warnings

from dataclasses import dataclass

from config.app_params import get_param
from app.ml.ml_datasets import get_ml_datasets

# Rejestr modeli (wspólny kod dla ML-01/ML-TEST)
from app.ml.model_registry import (
    available_catalogs,
    build_model_filename,
    filters_hash,
    list_models_from_dir,
    models_table,
    save_model_and_meta,
    dir_test,
    project_root,  # <-- potrzebne do zamiany ścieżek względnych z meta JSON na absolutne
)

# sklearn: pipeline + preprocessing + modele + metryki
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, PowerTransformer
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
)
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.dummy import DummyClassifier
import matplotlib.pyplot as plt  # wykresy
from sklearn.inspection import permutation_importance  # wpływ cech
from sklearn.metrics import precision_score, recall_score
from st_aggrid import AgGrid, GridOptionsBuilder
import plotly.graph_objects as go
from app.ui.column_metadata import COLUMN_LABELS





"""
Machine Learning
=======

Ekran: ML (laboratorium ML)

Założenia projektu:
1) data_overview.py -> tworzy df_market_all
2) analysis_view_v3.py -> przygotowuje EDA / analizy statystyczne (bez ML)
3) ml_01.py -> pobiera kanoniczne datasety ML (df_market_train/validation/test) z app/ml/ml_datasets.py:
    - df_market_train 
    - df_market_validation 
    - df_market_test

Kluczowa zasada:
- Ten ekran NIE POWIELA EDA z analysis_view_v3.py.
- Tu skupiamy się wyłącznie na:
  * definicji problemu ML,
  * przygotowaniu danych do ML (setup),
  * szybkim porównaniu modeli (compare_models),
  * prezentacji wyników w sposób „ML-owy”.

"""


# ============================================================
# KONFIGURACJA / STAŁE
# ============================================================

# Kolumny do wykluczenia (lista ignorowanych kolumn – traktujemy jako „ignore_features”)
DEFAULT_IGNORE_FEATURES = [
    "company_id",
    "ticker",
    "company_name",
    "trade_date",
    "open_price", 
    "high_price", 
    "low_price",
    "close_price",
    "source_ticker",
    "created_at_x",
    "ticker_x",
    "created_at_y",
    "modified_at",
    "ticker_y",
    "calc_flags",
    "sma_200", 
    "sma_50", 
    "sma_20",
    "ema_12", 
    "ema_26", 
    "macd_signal", 
    "macd_hist", 
    "vwap_20d",
    "fut_barrier_20p_12p_60d", 
    "fut_barrier_100p_50p_20d", 
    "fut_barrier_50p_20p_20d", 
    "fut_barrier_20p_12p_20d", 
    "fut_barrier_50p_20p_60d", 
    "fut_barrier_50p_20p_120d", 
    "fut_barrier_5p_3p_5d", 
    "fut_barrier_20p_12p_2d", 
    "fut_imp_2", 
    "fut_imp_20", 
    "fut_imp_60", 
    "fut_imp_120", 
    "fut_signal_2", 
    "fut_signal_20", 
    "fut_signal_60", 
    "fut_signal_120", 
    "fut_signal_20_hyb",     
]

# Dodatkowe ostrzeżenia: żeby w UI nie sypało warningami sklearn
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)


# ============================================================
# FORMATOWANIE TABEL UI — oparte na istniejących mapowaniach
# ============================================================

def _safe_project_relative_path(path_str: object) -> str:
    """
    Zamienia ścieżkę absolutną na względną względem katalogu projektu.
    Jeśli nie da się zrelatywizować, zwraca oryginalny string.
    """
    if path_str is None:
        return ""
    s = str(path_str).strip()
    if not s:
        return ""

    try:
        p = Path(s)
        root = project_root().resolve()
        if p.is_absolute():
            try:
                return p.resolve().relative_to(root).as_posix()
            except Exception:
                return p.as_posix()
        return p.as_posix()
    except Exception:
        return s


def _fmt_pct_2(v: object) -> object:
    """
    Format liczby jako procent z dokładnością do 2 miejsc.
    """
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except Exception:
        pass

    try:
        return f"{float(v):.2f}%"
    except Exception:
        return v


def _fmt_u4(v: object) -> object:
    """
    Format liczby ułamkowej do 4 miejsc po przecinku.
    """
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except Exception:
        pass

    try:
        return f"{float(v):.4f}"
    except Exception:
        return v


def _ui_target_value(target_code: object) -> str:
    """
    Przyjazna prezentacja wartości targetu.
    Wykorzystujemy istniejące COLUMN_LABELS, tak jak w innych ekranach.
    """
    if target_code is None:
        return ""
    code = str(target_code)
    return COLUMN_LABELS.get(code, code)


def _models_table_ui(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Formatuje tabele modeli:
    - 'Zapisane modele — podgląd katalogów'
    - 'Dostępne modele'

    Źródła etykiet:
    - COLUMN_LABELS -> kolumny biznesowe / target
    - ML01_QUALITY_FILTER_SHORTCODES -> opisy filtrów jakościowych
    """
    if df_raw is None or df_raw.empty:
        return pd.DataFrame()

    df = df_raw.copy()

    # 1) wartości
    if "_meta_fp" in df.columns:
        df["_meta_fp"] = df["_meta_fp"].apply(_safe_project_relative_path)

    if "target" in df.columns:
        df["target"] = df["target"].apply(_ui_target_value)

    # Kolumny liczbowe zostawiamy jako NUMERYCZNE.
    # Dzięki temu:
    # - sortowanie działa poprawnie,
    # - Streamlit / Arrow nie próbuje mieszać pustych stringów z liczbami.
    #
    # Ważne:
    # w metadanych modeli część pól potrafi przyjść jako "", None albo string.
    # Dlatego normalizujemy je jawnie do typów liczbowych już tutaj.
    numeric_cols = [
        "w",               # okno sesji
        "k",               # top-k
        "p",               # top-%
        "min_conditions",  # minimalna liczba warunków
        "val_prec",        # precyzja validation
        "val_n",           # liczba rekordów validation
        "val_ret20",       # zysk 20 validation
        "val_ret60",       # zysk 60 validation
        "val_ret120",      # zysk 120 validation
    ]

    for col in numeric_cols:
        if col in df.columns:
            # errors="coerce" zamienia "", None i śmieciowe wartości na NaN,
            # dzięki czemu kolumna staje się bezpieczna dla Arrow i sortowania.
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 2) nazwy kolumn
    rename_map = {
        "created_at": "Utworzono",
        "filename": "Plik modelu",
        "comment": "Komentarz",
        "model_name": "Model",
        "target": "Target (y)",
        "w": "Okno sesji",
        "k": "Top-K",
        "p": "Top-%",
        "min_conditions": "Min. warunków",
        "val_prec": "Precyzja VAL",
        "val_n": "Liczba VAL",
        "val_ret20": "Zysk 20 VAL",
        "val_ret60": "Zysk 60 VAL",
        "val_ret120": "Zysk 120 VAL",
        "_meta_fp": "Plik meta",
    }

    # dynamiczne kolumny filtrów: F:<filter_key>
    filt_map = get_param("ML01_QUALITY_FILTER_SHORTCODES")
    for c in list(df.columns):
        if c.startswith("F:"):
            filter_key = c[2:]
            if filter_key in filt_map:
                rename_map[c] = f"F: {filt_map[filter_key][1]}"
            else:
                rename_map[c] = c

    # jeśli jakieś kolumny biznesowe trafią tu wprost, też korzystamy z COLUMN_LABELS
    for c in list(df.columns):
        if c not in rename_map and c in COLUMN_LABELS:
            rename_map[c] = COLUMN_LABELS[c]

    df = df.rename(columns=rename_map)
    return df

def _render_models_table_aggrid(
    df_view: pd.DataFrame,
    *,
    table_key: str,
    height: int = 420,
) -> None:
    """
    Renderuje tabelę modeli przez AgGrid zamiast st.dataframe.

    Dlaczego to jest potrzebne:
    - w ML (TEST) kliknięcie w nagłówek kolumny ma sortować CAŁĄ tabelę,
      a nie tylko aktualnie widoczny fragment,
    - AgGrid robi to stabilnie po całym zbiorze,
    - kolumny procentowe mogą pozostać liczbowe, a znak % dodajemy
      tylko na etapie wyświetlania.

    Uwaga:
    - df_view powinien mieć już docelowe nazwy kolumn do UI,
    - LP powinno być już nadane wcześniej.
    """
    if df_view is None or df_view.empty:
        st.info("Brak danych do wyświetlenia.")
        return

    # Lokalny import, żeby helper był samowystarczalny.
    from st_aggrid import JsCode

    gb = GridOptionsBuilder.from_dataframe(df_view)

    # Domyślna konfiguracja kolumn:
    # - sortowanie i filtrowanie włączone,
    # - szerokości kolumn można zmieniać ręcznie,
    # - nie wymuszamy automatycznego dopasowania, bo tabela jest szeroka.
    gb.configure_default_column(
        sortable=True,
        filter=True,
        resizable=True,
        minWidth=80,
    )

    # Formatter liczb zmiennoprzecinkowych do 4 miejsc.
    js_fmt_4 = JsCode(
        """
        function(params) {
            if (params.value === null || params.value === undefined || params.value === '') {
                return '';
            }
            const v = Number(params.value);
            if (isNaN(v)) {
                return params.value;
            }
            return v.toFixed(4);
        }
        """
    )

    # Formatter procentów.
    # Ważne: wartość pozostaje NUMERYCZNA do sortowania,
    # a % jest dodawane tylko do prezentacji.
    js_fmt_pct2 = JsCode(
        """
        function(params) {
            if (params.value === null || params.value === undefined || params.value === '') {
                return '';
            }
            const v = Number(params.value);
            if (isNaN(v)) {
                return params.value;
            }
            return v.toFixed(2) + '%';
        }
        """
    )

    # LP jako kolumna liczbowa.
    if "LP" in df_view.columns:
        gb.configure_column(
            "LP",
            type=["numericColumn"],
            width=60,
            minWidth=55,
        )

    # Kolumny tekstowe / opisowe.
    if "Utworzono" in df_view.columns:
        gb.configure_column("Utworzono", width=140, minWidth=130)

    if "Plik modelu" in df_view.columns:
        gb.configure_column("Plik modelu", width=360, minWidth=260)

    if "Komentarz" in df_view.columns:
        gb.configure_column("Komentarz", width=90, minWidth=80)

    if "Model" in df_view.columns:
        gb.configure_column("Model", width=130, minWidth=120)

    if "Target (y)" in df_view.columns:
        gb.configure_column("Target (y)", width=120, minWidth=110)

    # Kolumny liczb całkowitych.
    for col_name in ["Okno sesji", "Top-K", "Liczba VAL"]:
        if col_name in df_view.columns:
            gb.configure_column(
                col_name,
                type=["numericColumn"],
                width=90,
                minWidth=80,
            )

    # Kolumny liczbowe z 4 miejscami po przecinku.
    for col_name in ["Top-%", "Min. warunków", "Precyzja VAL"]:
        if col_name in df_view.columns:
            gb.configure_column(
                col_name,
                type=["numericColumn"],
                valueFormatter=js_fmt_4,
                width=105,
                minWidth=95,
            )

    # Kolumny zysków jako liczby + formatter procentowy.
    for col_name in ["Zysk 20 VAL", "Zysk 60 VAL", "Zysk 120 VAL"]:
        if col_name in df_view.columns:
            gb.configure_column(
                col_name,
                type=["numericColumn"],
                valueFormatter=js_fmt_pct2,
                width=105,
                minWidth=95,
            )

    grid_options = gb.build()

    AgGrid(
        df_view,
        gridOptions=grid_options,
        height=height,
        theme="balham",  # Ujednolicamy theme z pozostałymi tabelami AgGrid w module ML.
        key=table_key,
        fit_columns_on_grid_load=False,  # Zostawiamy False, bo ta tabela jest szeroka i ma ręcznie ustawiane szerokości kolumn.
        allow_unsafe_jscode=True,
        enable_enterprise_modules=False,
    )

def _grid_27_ui(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Formatuje 'Tabela 27 kombinacji'.

    Zasady:
    - kolumna techniczna 'lp' jest prezentowana w UI jako 'LP',
    - 'LP' ma być pierwszą kolumną tabeli i jest stabilnym identyfikatorem wiersza,
    - wartości procentowe formatujemy do 2 miejsc,
    - metryki ułamkowe formatujemy do 4 miejsc.
    """
    if df_raw is None or df_raw.empty:
        return pd.DataFrame()

    df = df_raw.copy()

    rename_map = {
        "lp": "LP",
        "window_sessions": "Rozmiar okna sesji",
        "max_signals": "Top-K",
        "top_score_pct": "Top-% (ułamek)",
        "n_selected": "Liczba wybranych",
        "tp": "TP",
        "fp": "FP",
        "precision": "Precyzja",
        "recall": "Recall",
        "avg_score": "Śr. prawdop.",
        "min_score": "Min. prawdop.",
        "max_score": "Max. prawdop.",
        "total_pos_eval": "+1 VAL",
        "avg_ret_20": "Zysk 20 (%)",
        "avg_ret_60": "Zysk 60 (%)",
        "avg_ret_120": "Zysk 120 (%)",
        "avg_ret_end": "Zysk do końca (%)",
    }
    df = df.rename(columns=rename_map)

    # Zostawiamy te kolumny jako LICZBOWE.
    # To jest ważne, ponieważ sortowanie po kliknięciu w nagłówek
    # ma działać po realnych wartościach numerycznych, a nie po stringach.
    #
    # Formatowanie typu:
    # - 12.34%
    # - 0.1234
    # zrobimy dopiero na etapie renderowania w AgGrid.
    for col in ["Zysk 20 (%)", "Zysk 60 (%)", "Zysk 120 (%)", "Zysk do końca (%)"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in ["Precyzja", "Recall", "Śr. prawdop.", "Min. prawdop.", "Max. prawdop."]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # LP ma być pierwszą kolumną tabeli.
    if "LP" in df.columns:
        ordered_cols = ["LP"] + [c for c in df.columns if c != "LP"]
        df = df[ordered_cols]

    return df

def _render_grid_27_aggrid(
    df_view: pd.DataFrame,
    *,
    table_key: str,
    height: int = 900,
) -> None:
    """
    Renderuje tabelę 27 kombinacji przez AgGrid.

    Dlaczego osobny renderer:
    - tabela ma dużo kolumn liczbowych,
    - użytkownik oczekuje poprawnego sortowania po całym zbiorze,
    - format procentów i dokładność do 4 miejsc mają być tylko wizualne,
      bez zamiany danych na stringi.
    """
    if df_view is None or df_view.empty:
        st.info("Brak danych do wyświetlenia.")
        return

    from st_aggrid import JsCode

    gb = GridOptionsBuilder.from_dataframe(df_view)

    # Domyślna konfiguracja kolumn:
    # - włączone sortowanie, filtrowanie i resize,
    # - nie wymuszamy auto-fit wszystkich kolumn, bo tabela jest szeroka.
    gb.configure_default_column(
        sortable=True,
        filter=True,
        resizable=True,
        minWidth=80,
    )

    # Formatter dla liczb z 4 miejscami po przecinku.
    js_fmt_4 = JsCode(
        """
        function(params) {
            if (params.value === null || params.value === undefined || params.value === '') {
                return '';
            }
            const v = Number(params.value);
            if (isNaN(v)) {
                return params.value;
            }
            return v.toFixed(4);
        }
        """
    )

    # Formatter dla procentów.
    # Wartość pozostaje numeryczna do sortowania,
    # a znak % dodajemy tylko wizualnie.
    js_fmt_pct2 = JsCode(
        """
        function(params) {
            if (params.value === null || params.value === undefined || params.value === '') {
                return '';
            }
            const v = Number(params.value);
            if (isNaN(v)) {
                return params.value;
            }
            return v.toFixed(2) + '%';
        }
        """
    )

    # Ustawienia szerokości i typów kolumn.
    if "LP" in df_view.columns:
        gb.configure_column("LP", type=["numericColumn"], width=60, minWidth=55)

    for col_name in [
        "Rozmiar okna sesji",
        "Top-K",
        "Liczba wybranych",
        "TP",
        "FP",
        "+1 VAL",
    ]:
        if col_name in df_view.columns:
            gb.configure_column(
                col_name,
                type=["numericColumn"],
                width=95,
                minWidth=85,
            )

    for col_name in [
        "Top-% (ułamek)",
        "Precyzja",
        "Recall",
        "Śr. prawdop.",
        "Min. prawdop.",
        "Max. prawdop.",
    ]:
        if col_name in df_view.columns:
            gb.configure_column(
                col_name,
                type=["numericColumn"],
                valueFormatter=js_fmt_4,
                width=110,
                minWidth=95,
            )

    for col_name in [
        "Zysk 20 (%)",
        "Zysk 60 (%)",
        "Zysk 120 (%)",
        "Zysk do końca (%)",
    ]:
        if col_name in df_view.columns:
            gb.configure_column(
                col_name,
                type=["numericColumn"],
                valueFormatter=js_fmt_pct2,
                width=110,
                minWidth=100,
            )

    grid_options = gb.build()

    AgGrid(
        df_view,
        gridOptions=grid_options,
        height=height,
        theme="balham",  # Ujednolicamy theme z innymi tabelami AgGrid w aplikacji.
        key=table_key,
        fit_columns_on_grid_load=False,  # Zostawiamy False, bo grid 27 kombinacji jest szeroki i ma własne szerokości kolumn.
        allow_unsafe_jscode=True,
        enable_enterprise_modules=False,
    )

def _test_summary_ui(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Formatuje tabelę:
    'Podsumowanie testu (TEST) + porównanie do VALIDATE (z meta)'
    """
    if df_raw is None or df_raw.empty:
        return pd.DataFrame()

    df = df_raw.copy()

    rename_map = {
        "zbiór": "Zbiór",
        "precision": "Precyzja",
        "n_selected": "Liczba wybranych",
        "avg_ret_20": "Zysk 20 (%)",
        "avg_ret_60": "Zysk 60 (%)",
        "avg_ret_120": "Zysk 120 (%)",
        "avg_ret_end": "Zysk do końca (%)",
    }
    df = df.rename(columns=rename_map)

    for col in ["Zysk 20 (%)", "Zysk 60 (%)", "Zysk 120 (%)", "Zysk do końca (%)"]:
        if col in df.columns:
            df[col] = df[col].apply(_fmt_pct_2)

    if "Precyzja" in df.columns:
        df["Precyzja"] = df["Precyzja"].apply(_fmt_u4)

    return df

# ============================================================
# POMOCNICZE KLASY (żeby było czytelnie)
# ============================================================

@dataclass(frozen=True)
class SetupConfig:
    """
    Konfiguracja „setup” w stylu PyCaret.

    W PyCaret wygląda to mniej więcej tak:
      setup(data=df, target='y', session_id=..., ignore_features=[...],
            fix_imbalance=True, normalize=True, transformation=True)

    U nas te parametry mapujemy na:
    - ignore_features -> drop kolumn
    - fix_imbalance   -> class_weight='balanced' (bez imblearn) lub oversampling (można kiedyś dodać)
    - normalize       -> StandardScaler (po imputacji)
    - transformation  -> PowerTransformer (po imputacji)
    - session_id      -> random_state
    """
    target: str
    session_id: int
    ignore_features: List[str]
    fix_imbalance: bool
    normalize: bool
    transformation: bool
    ml01_mode: str  # "FAST" | "FULL"



@dataclass(frozen=True)
class PreparedData:
    """
    Wynik „setup”:
    - X_train / X_test / y_train / y_test
    - lista cech użytych w ML
    - baseline (częstość klasy pozytywnej)
    """
    X_train: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_test: pd.Series
    feature_cols: List[str]
    baseline_pos_rate: float


# ============================================================
# FUNKCJE: wykrywanie targetów i cech
# ============================================================

def get_label_columns(df: pd.DataFrame) -> List[str]:
    """
    Targety (y) są ZESŁOWNIKOWANE (whitelist) w app_params.
    Lista w UI NIE wynika już z startswith("fut_signal"), tylko z konfiguracji.

    Dodatkowo filtrujemy do tych, które realnie istnieją w df (fail-soft),
    żeby UI nie wywalał się przy brakujących kolumnach.
    """
    configured: List[str] = get_param("ML01_TARGET_SIGNAL_LIST")
    existing = [c for c in configured if c in df.columns]
    return existing


def build_ignore_list(user_ignore: List[str], target: str) -> List[str]:
    """
    Buduje finalną listę kolumn ignorowanych.
    Ważne:
    - target NIGDY nie może trafić do features, więc też go wykluczamy z X.
    """
    out = list(dict.fromkeys(user_ignore))  # usuń duplikaty zachowując kolejność
    if target not in out:
        out.append(target)
    return out


def to_binary_target(series: pd.Series) -> pd.Series:
    """
    Binarizacja targetu:
    - 1 jeśli wartość == 1
    - 0 w przeciwnym wypadku

    To jest spójne z tym, jak interpretowany jest „sygnał +1”.
    """
    s = pd.to_numeric(series, errors="coerce")
    return (s == 1).astype(int)


def get_numeric_feature_cols(df: pd.DataFrame, ignore_cols: List[str]) -> List[str]:
    """
    Dobór cech:
    - bierzemy tylko kolumny, które dają się zrzutować do numeric
    - odrzucamy ignore_cols
    """
    feature_cols: List[str] = []

    for col in df.columns:
        if not isinstance(col, str):
            continue
        if col in ignore_cols:
            continue

        s = pd.to_numeric(df[col], errors="coerce")
        if s.notna().sum() == 0:
            # brak danych liczbowych -> nie jest cechą
            continue

        feature_cols.append(col)

    return feature_cols


# ============================================================
# FUNKCJE: odpowiednik PyCaret setup(...)
# ============================================================

def setup_prepare_data(
    df_train: pd.DataFrame,
    df_val: pd.DataFrame,
    cfg: SetupConfig,
) -> PreparedData:

    """
    Setup pod kanoniczny time split.
    Budujemy X/y osobno dla TRAIN i VALIDATION, używając identycznych feature_cols.
    """

    # 1) Usuwam niepotrzebne w badaniu kolumny czyli ignore list ( lista + target)
    ignore_cols = build_ignore_list(cfg.ignore_features, cfg.target)

    # 2) cechy numeryczne wyznaczamy NA TRAIN (żeby nie „podglądać” testu)
    feature_cols = get_numeric_feature_cols(df_train, ignore_cols)

    # 3) budujemy X/y dla TRAIN
    y_train = to_binary_target(df_train[cfg.target])
    X_train = df_train[feature_cols].apply(pd.to_numeric, errors="coerce")

    # 4) budujemy X/y dla VALIDATION (TE SAME feature_cols!)
    y_val = to_binary_target(df_val[cfg.target])
    X_val = df_val[feature_cols].apply(pd.to_numeric, errors="coerce")

    # 5) baseline – częstość klasy +1 (globalnie na TRAIN+VALIDATION; w ML-02 rozszerzymy o VAL)
    y_all = pd.concat([y_train, y_val], axis=0, ignore_index=True)
    baseline = float(y_all.mean()) if len(y_all) else 0.0

    return PreparedData(
        X_train=X_train,
        X_test=X_val,
        y_train=y_train,
        y_test=y_val,
        feature_cols=feature_cols,
        baseline_pos_rate=baseline,
    )



def build_preprocess_pipeline(cfg: SetupConfig) -> Pipeline:
    """
    Buduje pipeline preprocessingu zgodnie z parametrami:
    - normalize=True       -> StandardScaler
    - transformation=True  -> PowerTransformer

    Zawsze robimy:
    - imputację braków (SimpleImputer medianą)

    Kolejność:
    1) imputacja
    2) (opcjonalnie) transformacja rozkładu (PowerTransformer)
    3) (opcjonalnie) normalizacja (StandardScaler)

    Uwaga:
    - PowerTransformer jest czuły na dane, ale zwykle pomaga przy rozkładach skośnych.
    - W finansach często rozkłady są ciężkoogonowe -> transformacja może mieć sens.
    """
    steps = []

    # imputacja jest niemal zawsze konieczna (wskaźniki mogą mieć NaN)
    steps.append(("imputer", SimpleImputer(strategy="median")))

    # transformacja (np. Yeo-Johnson) – działa też dla wartości ujemnych
    if cfg.transformation:
        steps.append(("power_transform", PowerTransformer(method="yeo-johnson", standardize=False)))

    # normalizacja (skalowanie) – ważne np. dla regresji logistycznej
    if cfg.normalize:
        steps.append(("scaler", StandardScaler()))

    return Pipeline(steps=steps)


# ============================================================
# FUNKCJE: odpowiednik PyCaret compare_models()
# ============================================================

def get_candidate_models(cfg: SetupConfig) -> Dict[str, object]:
    class_weight = "balanced" if cfg.fix_imbalance else None

    if cfg.ml01_mode == "FAST":
        models: Dict[str, object] = {
            "Dummy (most_frequent)": DummyClassifier(strategy="most_frequent", random_state=cfg.session_id),

            "LogisticRegression": LogisticRegression(
                max_iter=400,  # było 800
                class_weight=class_weight,
                random_state=cfg.session_id,
            ),

            "RandomForest": RandomForestClassifier(
                n_estimators=100,  # było 250
                max_depth=None,    # zostawiamy jak w FULL (żeby nie zmieniać charakteru)
                class_weight=class_weight,
                random_state=cfg.session_id,
                n_jobs=-1,
            ),

            "GradientBoosting": GradientBoostingClassifier(
                n_estimators=50,   # domyślnie 100 → w dół
                random_state=cfg.session_id,
            ),
        }
        return models

    # FULL = IDENTYCZNIE jak teraz (zero zmian w parametrach)
    models: Dict[str, object] = {
        "Dummy (most_frequent)": DummyClassifier(strategy="most_frequent", random_state=cfg.session_id),

        "LogisticRegression": LogisticRegression(
            max_iter=800,
            class_weight=class_weight,
            random_state=cfg.session_id,
        ),

        "RandomForest": RandomForestClassifier(
            n_estimators=250,
            max_depth=None,
            class_weight=class_weight,
            random_state=cfg.session_id,
            n_jobs=-1,
        ),

        "GradientBoosting": GradientBoostingClassifier(random_state=cfg.session_id),
    }
    return models

# Mechanizny ML (machine learning)
# Cross-validation porównawcze modeli (CV na TRAIN)
def compare_models_sklearn(
    prepared: PreparedData,
    cfg: SetupConfig,
    scoring: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Odpowiednik PyCaret compare_models().

    Robimy:
    - k-fold cross-validation na TRAIN (żeby nie „podglądać” testu)
    - liczymy metryki i wybieramy best model

    Metryki (domyślne):
    - accuracy (czyli „ile trafień” – UWAGA: przy niezbalansowanych danych bywa myląca)
    - f1 (lepsza przy rzadkiej klasie pozytywnej)
    - roc_auc (jeśli model daje prawdopodobieństwa i y ma 2 klasy)
    """
    if scoring is None:
        scoring = ["accuracy", "f1", "roc_auc"]

    X_train = prepared.X_train
    y_train = prepared.y_train

    preprocess = build_preprocess_pipeline(cfg)
    models = get_candidate_models(cfg)

    # CV: stratified (bo klasa pozytywna może być rzadka)
    n_splits = 3 if cfg.ml01_mode == "FAST" else 5
    cv = StratifiedKFold(n_splits=n_splits, shuffle=False)

    # Kluczowe miejsce faktycznego “badania” modeli:
    rows = []
    for name, model in models.items():
        # pipeline = preprocess + model
        pipe = Pipeline([
            ("prep", preprocess),
            ("model", model),
        ])

        # ==========================================================
        # BADANIE MODELI ML (ETAP 1 / porównanie): CV na TRAIN
        # ==========================================================
        # W tym miejscu porównujemy kandydatów modelowych w sposób powtarzalny:
        # - pipeline = preprocess + model
        # - ocena = średnie metryki z cross_validate(...) na foldach TRAIN
        #
        # UWAGA (czas / leakage):
        # StratifiedKFold nie jest „time-series split”. Chroni proporcje klas,
        # ale nie gwarantuje separacji czasowej jak TimeSeriesSplit / Purged CV.
        # Na etapie ML-01 akceptujemy to jako szybkie porównanie, natomiast
        # docelowo warto rozważyć split stricte czasowy (bez mieszania przyszłości).
        #
        # Uwaga techniczna: roc_auc wymaga 2 klas – jeśli y_train ma tylko jedną,
        # pomijamy roc_auc, żeby cross_validate nie wywracał metryk.
        local_scoring = list(scoring)
        if y_train.nunique() < 2 and "roc_auc" in local_scoring:
            local_scoring.remove("roc_auc")

        cv_res = cross_validate(
            pipe,
            X_train,
            y_train,
            cv=cv,
            scoring=local_scoring,
            n_jobs=-1,
            error_score=np.nan,
        )

        # uśredniamy wyniki
        row = {
            "model": name,
            "cv_accuracy": float(np.nanmean(cv_res.get("test_accuracy", [np.nan]))),
            "cv_f1": float(np.nanmean(cv_res.get("test_f1", [np.nan]))),
            "cv_roc_auc": float(np.nanmean(cv_res.get("test_roc_auc", [np.nan]))),
        }
        rows.append(row)

    out = pd.DataFrame(rows)

    # sortowanie: preferujemy f1, potem roc_auc, na końcu accuracy
    # (bo w danych rynkowych klasa pozytywna często jest rzadka)
    sort_cols = ["cv_f1", "cv_roc_auc", "cv_accuracy"]
    out = out.sort_values(sort_cols, ascending=False).reset_index(drop=True)
    return out


@st.cache_data(show_spinner=False)
def compare_models_sklearn_cached(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    cfg: SetupConfig,
) -> pd.DataFrame:
    """
    Cache wrapper dla ciężkiego CV.
    Uwaga: cache zależy od X_train/y_train oraz cfg (target/parametry preprocessing).
    """
    prepared_tmp = PreparedData(
        X_train=X_train,
        X_test=X_train.iloc[0:0].copy(),  # placeholder, nieużywane w compare_models
        y_train=y_train,
        y_test=y_train.iloc[0:0].copy(),  # placeholder
        feature_cols=list(X_train.columns),
        baseline_pos_rate=float(pd.to_numeric(y_train, errors="coerce").mean()) if len(y_train) else 0.0,
    )
    return compare_models_sklearn(prepared_tmp, cfg)


def make_model_pipeline(
    best_model_name: str,
    cfg: SetupConfig,
    *,
    mode: Optional[str] = None,
) -> Pipeline:
    """
    Buduje NIEWYTRANOWANY pipeline = preprocess + model.

    Użycie:
    - FINALIZE (TRAIN+VALIDATION): tworzymy pipeline i dopiero wtedy fit na X_final/y_final.

    Dlaczego to jest potrzebne:
    - w ML-01 mamy już funkcje build_preprocess_pipeline() i get_candidate_models(),
      ale brakowało wspólnego helpera, który składa je w jeden Pipeline.
    """

    # Jeśli chcemy nadpisać tryb (FAST/FULL) na etapie FINALIZE, tworzymy kopię cfg.
    if mode is not None and mode != cfg.ml01_mode:
        cfg_local = SetupConfig(
            target=cfg.target,
            session_id=cfg.session_id,
            ignore_features=list(cfg.ignore_features),
            fix_imbalance=cfg.fix_imbalance,
            normalize=cfg.normalize,
            transformation=cfg.transformation,
            ml01_mode=str(mode),
        )
    else:
        cfg_local = cfg

    preprocess = build_preprocess_pipeline(cfg_local)
    models = get_candidate_models(cfg_local)

    if best_model_name not in models:
        raise KeyError(
            f"Nie znam modelu '{best_model_name}'. Dostępne: {list(models.keys())}"
        )

    model = models[best_model_name]
    pipe = Pipeline([("prep", preprocess), ("model", model)])
    return pipe

# Trening najlepszego modelu na TRAIN
def fit_best_model(
    prepared: PreparedData,
    cfg: SetupConfig,
    best_model_name: str,
):
    """
    Trenujemy najlepszy model (wybrany po CV) na pełnym TRAIN.

    Uwaga metodologiczna (ML):
    - ocena robocza odbywa się na VALIDATION (time-split),
    - zbiór TEST pozostaje „zamrożony” i nie jest używany na tym etapie.
    """
    preprocess = build_preprocess_pipeline(cfg)
    models = get_candidate_models(cfg)

    model = models[best_model_name]
    pipe = Pipeline([("prep", preprocess), ("model", model)])

    pipe.fit(prepared.X_train, prepared.y_train) # Faktyczny trening
    return pipe


@st.cache_resource(show_spinner=False)
def fit_best_model_cached(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    cfg: SetupConfig,
    best_model_name: str,
):
    """
    Cache wrapper na wytrenowany pipeline (Pipeline jest zasobem -> cache_resource).
    """
    prepared_tmp = PreparedData(
        X_train=X_train,
        X_test=X_train.iloc[0:0].copy(),  # placeholder
        y_train=y_train,
        y_test=y_train.iloc[0:0].copy(),  # placeholder
        feature_cols=list(X_train.columns),
        baseline_pos_rate=float(pd.to_numeric(y_train, errors="coerce").mean()) if len(y_train) else 0.0,
    )
    return fit_best_model(prepared_tmp, cfg, best_model_name)



# ============================================================
# INTERPRETOWALNOŚĆ: korelacje i wpływ cech na wynik
# ============================================================

def compute_feature_target_correlations(
    X: pd.DataFrame,
    y: pd.Series,
    method: str = "spearman",
) -> pd.DataFrame:
    """
    Liczy korelacje cech z targetem.

    Dlaczego to robimy:
    - to jest szybki, prosty filtr informacyjny,
    - nie mówi o przyczynowości,
    - ale często pokazuje, które cechy „coś niosą”.

    Uwaga:
    - target jest binarny (0/1), a cechy ciągłe -> korelacja ma charakter orientacyjny,
    - używamy Spearmana (odporniejszy na nieliniowość i odstające wartości).
    """
    y_num = pd.to_numeric(y, errors="coerce")
    rows = []
    for col in X.columns:
        s = pd.to_numeric(X[col], errors="coerce")
        # korelacja liczy się tylko tam, gdzie są dane
        tmp = pd.DataFrame({"x": s, "y": y_num}).dropna()
        if len(tmp) < 100:
            continue
        corr = tmp["x"].corr(tmp["y"], method=method)
        rows.append({"feature": col, f"corr_{method}": corr, "n": len(tmp)})

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["abs_corr"] = out[f"corr_{method}"].abs()
    return out.sort_values("abs_corr", ascending=False).reset_index(drop=True)


def get_model_specific_importance(
    pipe: Pipeline,
    feature_cols: List[str],
) -> pd.DataFrame:
    """
    Próbuje wyciągnąć „model-specific” importance:

    - RandomForest: feature_importances_
    - GradientBoosting: feature_importances_
    - LogisticRegression: coef_ (waga cechy po preprocessingu)

    Uwaga:
    - dla LR współczynniki są po preprocessing’u (skalowanie itp.), więc interpretacja jest względna,
    - dla drzew: importances bywają biasowane (faworyzują cechy o większej liczbie unikalnych wartości),
      dlatego obok tego i tak pokazujemy permutation importance.
    """
    model = pipe.named_steps.get("model", None)
    if model is None:
        return pd.DataFrame(columns=["feature", "importance", "source"])

    # Drzewa / boosting
    if hasattr(model, "feature_importances_"):
        imp = getattr(model, "feature_importances_")
        out = pd.DataFrame({
            "feature": feature_cols,
            "importance": imp,
            "source": "model_feature_importances_",
        }).sort_values("importance", ascending=False)
        return out.reset_index(drop=True)

    # Regresja logistyczna
    if hasattr(model, "coef_"):
        coef = model.coef_.ravel()
        out = pd.DataFrame({
            "feature": feature_cols,
            "importance": coef,
            "abs_importance": np.abs(coef),
            "source": "model_coef_",
        }).sort_values("abs_importance", ascending=False)
        return out.reset_index(drop=True)

    return pd.DataFrame(columns=["feature", "importance", "source"])


def compute_permutation_importance(
    pipe: Pipeline,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    feature_cols: List[str],
    n_repeats: int = 8,
    random_state: int = 123,
) -> pd.DataFrame:
    """
    Permutation importance = model-agnostic wpływ cech.

    Jak działa:
    - mierzymy wynik modelu,
    - potem tasujemy jedną cechę (psujemy ją),
    - patrzymy jak bardzo spada wynik.

    Dlaczego to jest ważne:
    - działa dla każdego modelu,
    - jest dużo bardziej wiarygodne niż same feature_importances_ w drzewach.

    Uwaga:
    - przy ultra-imbalanced danych najlepiej mierzyć spadek w metryce typu ROC AUC lub F1,
      ale w sklearn permutation_importance domyślnie operuje na score() estymatora.
      Nasz pipeline nie ma nadpisanego score, więc użyje accuracy.
      Dlatego: permutation importance traktuj jako orientacyjne,
      a docelowo warto przejść na scoring='roc_auc' (w kolejnej iteracji).
    """
    # sklearn: permutation_importance używa estymatora z metodą score() -> domyślnie accuracy
    r = permutation_importance(
        pipe,
        X_test,
        y_test,
        n_repeats=n_repeats,
        random_state=random_state,
        n_jobs=-1,
    )

    out = pd.DataFrame({
        "feature": feature_cols,
        "importance_mean": r.importances_mean,
        "importance_std": r.importances_std,
    }).sort_values("importance_mean", ascending=False)

    return out.reset_index(drop=True)




# ============================================================
# SELEKCJA RANKINGOWA (ML-01): okna sesyjne + Top-K + Top-Pct
# ============================================================

def _add_session_window_id(
    df: pd.DataFrame,
    date_col: str,
    window_sessions: int,
) -> pd.DataFrame:
    """
    Dodaje window_id jako kolejne okna po N unikalnych sesji (trade_date).
    Okno = N unikalnych dni handlowych widocznych w DF (market-wide).
    """
    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
    out = out.dropna(subset=[date_col]).sort_values(date_col)

    sessions = (
        out[[date_col]]
        .drop_duplicates()
        .sort_values(date_col)
        .reset_index(drop=True)
    )
    sessions["session_idx"] = range(len(sessions))
    sessions["window_id"] = sessions["session_idx"] // int(window_sessions)

    out = out.merge(sessions, on=date_col, how="left")
    return out


def select_signals_topk_then_toppct(
    df_rank: pd.DataFrame,
    *,
    date_col: str = "trade_date",
    score_col: str = "prob",
    window_sessions: int,
    max_signals: int,
    top_score_pct: float,
) -> pd.DataFrame:
    """
    Kanoniczna selekcja (ADR-011 / decyzja):
    1) Top-K: bierzemy maksymalnie max_signals najwyższych score w oknie
    2) Top-Pct: dodatkowo ograniczamy do top_score_pct najlepszych obserwacji w oknie
       (czyli limit = floor(N_okna * top_score_pct))
    Finalnie: bierzemy min(max_signals, limit_pct) obserwacji na okno.
    Dopuszczalne jest 0 sygnałów w oknie.
    """
    if df_rank.empty:
        return df_rank.copy()

    dfw = _add_session_window_id(df_rank, date_col=date_col, window_sessions=window_sessions)

    rows = []
    for wid, g in dfw.groupby("window_id"):
        g = g.sort_values(score_col, ascending=False)

        n_window = len(g)
        pct_limit = int(np.floor(n_window * float(top_score_pct)))

        final_k = min(int(max_signals), int(pct_limit))
        if final_k <= 0:
            continue

        rows.append(g.head(final_k))

    if not rows:
        return dfw.iloc[0:0].copy()

    out = pd.concat(rows, axis=0).sort_values(["window_id", score_col], ascending=[True, False]).reset_index(drop=True)
    return out


def select_signals_toppct_then_topk(
    df_rank: pd.DataFrame,
    *,
    date_col: str = "trade_date",
    score_col: str = "prob",
    window_sessions: int,
    max_signals: int,
    top_score_pct: float,
) -> pd.DataFrame:
    """
    Wariant kontrolny:
    1) Top-Pct: bierzemy top_score_pct najlepszych obserwacji w oknie
       (limit = floor(N_okna * top_score_pct))
    2) Top-K: z tego bierzemy maksymalnie max_signals
    Dopuszczalne jest 0 sygnałów w oknie.
    """
    if df_rank.empty:
        return df_rank.copy()

    dfw = _add_session_window_id(df_rank, date_col=date_col, window_sessions=window_sessions)

    rows = []
    for wid, g in dfw.groupby("window_id"):
        g = g.sort_values(score_col, ascending=False)

        n_window = len(g)
        pct_limit = int(np.floor(n_window * float(top_score_pct)))
        if pct_limit <= 0:
            continue

        g_pct = g.head(pct_limit)
        final_k = min(int(max_signals), len(g_pct))
        if final_k <= 0:
            continue

        rows.append(g_pct.head(final_k))

    if not rows:
        return dfw.iloc[0:0].copy()

    out = pd.concat(rows, axis=0).sort_values(["window_id", score_col], ascending=[True, False]).reset_index(drop=True)
    return out


def compute_selection_metrics(
    df_selected: pd.DataFrame,
    df_all_test_rank: pd.DataFrame,
    y_col: str = "y_true",
    score_col: str = "prob",
) -> Dict[str, float]:
    """
    Metryki selekcji rankingowej na zbiorze VALIDATION.

    precision = TP / (TP + FP) liczony w wybranych sygnałach
    recall    = TP / (TP + FN) względem CAŁEGO zbioru VALIDATION (pomocniczo)
    """
    total_pos = float((df_all_test_rank[y_col] == 1).sum())
    n_sel = float(len(df_selected))
    tp = float((df_selected[y_col] == 1).sum()) if n_sel else 0.0
    fp = float(n_sel - tp)

    precision = tp / n_sel if n_sel > 0 else 0.0
    recall = tp / total_pos if total_pos > 0 else 0.0

    avg_score = float(df_selected[score_col].mean()) if n_sel else np.nan
    min_score = float(df_selected[score_col].min()) if n_sel else np.nan
    max_score = float(df_selected[score_col].max()) if n_sel else np.nan

    return {
        "n_selected": n_sel,
        "tp": tp,
        "fp": fp,
        "precision": precision,
        "recall": recall,
        "avg_score": avg_score,
        "min_score": min_score,
        "max_score": max_score,
        "total_pos_eval": total_pos,
    }


def _build_prices_cache_for_returns(df_val_prices: pd.DataFrame) -> dict[str, tuple[np.ndarray, np.ndarray, dict[pd.Timestamp, int]]]:
    """
    Buduje cache per ticker do szybkiego liczenia ex-post zwrotów:
    ticker -> (dates, closes, dt_to_idx)
    (Analogicznie do _add_expost_returns_for_po_rows, ale budowane 1 raz i reuse w gridzie.)
    """
    if df_val_prices is None or df_val_prices.empty:
        return {}

    prices = df_val_prices.copy()

    if "trade_date" in prices.columns:
        prices["trade_date"] = pd.to_datetime(prices["trade_date"], errors="coerce")

    if not {"ticker", "trade_date", "close_price"}.issubset(prices.columns):
        return {}

    prices = prices.dropna(subset=["ticker", "trade_date"]).sort_values(["ticker", "trade_date"], ascending=True)

    cache: dict[str, tuple[np.ndarray, np.ndarray, dict[pd.Timestamp, int]]] = {}

    for t, grp in prices.groupby("ticker", sort=False):
        g = grp[["trade_date", "close_price"]].copy()
        g["trade_date"] = pd.to_datetime(g["trade_date"], errors="coerce")
        g = g.dropna(subset=["trade_date"]).sort_values("trade_date", ascending=True)

        dates = g["trade_date"].to_numpy()
        closes = pd.to_numeric(g["close_price"], errors="coerce").to_numpy()

        dt_to_idx: dict[pd.Timestamp, int] = {}
        for i, dt in enumerate(dates):
            # jeśli są duplikaty, bierzemy ostatni
            dt_to_idx[pd.Timestamp(dt)] = i

        cache[str(t)] = (dates, closes, dt_to_idx)

    return cache


def _compute_expost_return_means_for_selection(
    df_sel: pd.DataFrame,
    *,
    prices_cache: dict[str, tuple[np.ndarray, np.ndarray, dict[pd.Timestamp, int]]],
    horizons: tuple[int, ...] = (20, 60, 120),
) -> dict[str, float]:
    """
    Liczy średnie ex-post zwrotów dla danej selekcji (df_sel) bez dopinania kolumn do DF.
    Zwraca:
      avg_ret_20, avg_ret_60, avg_ret_120, avg_ret_end
    Wartości w % (tak jak ret_* w tabelach: (future/base - 1) * 100).
    """
    out: dict[str, float] = {f"avg_ret_{h}": np.nan for h in horizons}
    out["avg_ret_end"] = np.nan

    if df_sel is None or df_sel.empty or not prices_cache:
        return out

    if not {"ticker", "trade_date", "close_price"}.issubset(df_sel.columns):
        return out

    dfx = df_sel.copy()
    dfx["trade_date"] = pd.to_datetime(dfx["trade_date"], errors="coerce")

    # listy do akumulacji wyników
    vals: dict[str, list[float]] = {f"avg_ret_{h}": [] for h in horizons}
    vals["avg_ret_end"] = []

    for _, row in dfx.iterrows():
        t = row.get("ticker")
        base_date = row.get("trade_date")
        base_price = row.get("close_price")

        if pd.isna(t) or pd.isna(base_date):
            continue

        try:
            base_price_f = float(base_price)
        except Exception:
            continue
        if base_price_f == 0:
            continue

        key = str(t)
        if key not in prices_cache:
            continue

        dates, closes, dt_to_idx = prices_cache[key]
        if dates.size == 0:
            continue

        base_idx = dt_to_idx.get(pd.Timestamp(base_date))
        if base_idx is None:
            # fallback: normalize (ignoruj czas)
            bd = pd.Timestamp(base_date).normalize()
            base_idx = dt_to_idx.get(bd)
            if base_idx is None:
                continue

        # ret_end: do końca VALIDATE dla danego tickera (ostatnia dostępna sesja)
        last_close = closes[-1] if closes.size else np.nan
        if not np.isnan(last_close):
            vals["avg_ret_end"].append((float(last_close) / base_price_f - 1.0) * 100.0)

        # ret_h: po h sesjach (indeksowo w obrębie VALIDATE dla tickera)
        for h in horizons:
            target_idx = base_idx + int(h)
            if target_idx < closes.size:
                fut_close = closes[target_idx]
                if not np.isnan(fut_close):
                    vals[f"avg_ret_{h}"].append((float(fut_close) / base_price_f - 1.0) * 100.0)

    # średnie
    for h in horizons:
        k = f"avg_ret_{h}"
        out[k] = float(np.mean(vals[k])) if vals[k] else np.nan
    out["avg_ret_end"] = float(np.mean(vals["avg_ret_end"])) if vals["avg_ret_end"] else np.nan

    return out


def run_grid_experiment(
    df_rank: pd.DataFrame,
    *,
    selector_fn,
    windows: List[int],
    max_signals_list: List[int],
    top_pct_list: List[float],
    df_val_prices: pd.DataFrame,
    horizons: tuple[int, ...] = (20, 60, 120),
) -> pd.DataFrame:
    """
    Uruchamia grid 3×3×3 i zwraca tabelę wyników (posortowaną).

    Rozszerzenie:
    - dla każdego wiersza gridu dopisuje średnie 4 zysków (20/60/120/end)
      liczone dla próbek (df_sel) należących do tej konfiguracji.
    - ceny bierzemy z df_val_prices (zwykle to samo co df_rank = df_val_rank_full).
    """
    rows = []

    prices_cache = _build_prices_cache_for_returns(df_val_prices)

    for window_sessions in windows:
        for max_signals in max_signals_list:
            for top_score_pct in top_pct_list:
                df_sel = selector_fn(
                    df_rank,
                    date_col="trade_date",
                    score_col="prob",
                    window_sessions=window_sessions,
                    max_signals=max_signals,
                    top_score_pct=top_score_pct,
                )

                m = compute_selection_metrics(df_sel, df_rank, y_col="y_true", score_col="prob")

                # średnie zysków (ex post) dla tej selekcji
                avg_rets = _compute_expost_return_means_for_selection(
                    df_sel,
                    prices_cache=prices_cache,
                    horizons=horizons,
                )

                rows.append({
                    "window_sessions": window_sessions,
                    "max_signals": max_signals,
                    "top_score_pct": top_score_pct,
                    **m,
                    **avg_rets,
                })

    out = pd.DataFrame(rows)

    # Sort: precision desc, n_selected asc, tp desc (czytelne pod Twój cel)
    out = out.sort_values(
        by=["precision", "n_selected", "tp"],
        ascending=[False, True, False],
    ).reset_index(drop=True)

    return out


    out = pd.DataFrame(rows)
    # Sort: precision desc, n_selected asc, tp desc (czytelne pod Twój cel)
    out = out.sort_values(
        by=["precision", "n_selected", "tp"],
        ascending=[False, True, False],
    ).reset_index(drop=True)
    return out

def _normalize_min_conditions_for_signature(filters: dict, min_conditions: Optional[int]) -> Optional[int]:
    """
    Normalizuje min_conditions do postaci używanej w sygnaturze stanu Tab2.

    Zasady:
    - jeśli nie ma aktywnych filtrów -> zwracamy None,
    - jeśli filtry są aktywne, ale min_conditions jest puste/błędne -> fallback = liczba aktywnych filtrów
      (czyli klasyczne AND),
    - wynik clampujemy do zakresu 1..active_cnt.

    Dzięki temu jedna logiczna konfiguracja filtrów zawsze daje tę samą sygnaturę,
    niezależnie od drobnych różnic typu 0 / None / pusty string.
    """
    active_cnt = sum(1 for v in (filters or {}).values() if bool(v))

    if active_cnt == 0:
        return None

    if min_conditions is None:
        return active_cnt

    try:
        mc = int(min_conditions)
    except Exception:
        mc = active_cnt

    mc = max(1, min(mc, active_cnt))
    return mc


def _build_tab2_filter_runtime_signature(
    *,
    selection_signature: Optional[tuple],
    filters: dict,
    min_conditions: Optional[int],
    df_sel_base: Optional[pd.DataFrame],
) -> tuple:
    """
    Buduje sygnaturę faktycznie policzonego wyniku PO w Tab2.

    Co zawiera sygnatura:
    - wybraną konfigurację PRZED: (window_sessions, max_signals, top_score_pct),
    - dokładny stan checkboxów filtrów,
    - znormalizowane min_conditions,
    - liczność zbioru PRZED.

    Po co:
    - FINALIZE ma umieć sprawdzić, czy zapisany w session_state wynik PO
      rzeczywiście odpowiada aktualnemu stanowi Tab2.
    """
    normalized_mc = _normalize_min_conditions_for_signature(filters, min_conditions)

    return (
        selection_signature,
        tuple(sorted((k, bool(v)) for k, v in (filters or {}).items())),
        normalized_mc,
        len(df_sel_base) if isinstance(df_sel_base, pd.DataFrame) else 0,
    )


def _build_val_summary_from_selected_df(
    df_selected: Optional[pd.DataFrame],
    df_all_rank: pd.DataFrame,
) -> dict:
    """
    Buduje val_summary bezpośrednio z faktycznie wybranego zbioru sygnałów
    (np. z wyniku PO po filtrze), a nie z tabeli gridu.

    Zwracamy ten sam kontrakt pól, który zapisujemy do meta modelu:
    - precision
    - n_selected
    - avg_ret_20
    - avg_ret_60
    - avg_ret_120
    - avg_ret_end

    Wartości avg_ret_* liczymy na podstawie realnie wybranych rekordów.
    """
    if df_selected is None or not isinstance(df_selected, pd.DataFrame):
        return {}

    if df_all_rank is None or not isinstance(df_all_rank, pd.DataFrame) or df_all_rank.empty:
        return {}

    selection_metrics = compute_selection_metrics(
        df_selected,
        df_all_rank,
        y_col="y_true",
        score_col="prob",
    )

    prices_cache = _build_prices_cache_for_returns(df_all_rank)
    avg_rets = _compute_expost_return_means_for_selection(
        df_selected,
        prices_cache=prices_cache,
        horizons=(20, 60, 120),
    )

    return {
        "precision": float(selection_metrics.get("precision", np.nan)),
        "n_selected": int(selection_metrics.get("n_selected", 0)),
        "avg_ret_20": float(avg_rets.get("avg_ret_20", np.nan)),
        "avg_ret_60": float(avg_rets.get("avg_ret_60", np.nan)),
        "avg_ret_120": float(avg_rets.get("avg_ret_120", np.nan)),
        "avg_ret_end": float(avg_rets.get("avg_ret_end", np.nan)),
    }

def show_active_context_badge(cfg: Optional[SetupConfig]) -> None:
    """
    Pokazuje na zakładkach 1/2/3:
    - aktywny target z Tab 0
    - aktywny model z Tab 1 (jeśli został wybrany)
    """
    target_txt = "(brak) — wykonaj Setup w zakładce 0"
    if cfg is not None:
        target_txt = cfg.target

    model_name = st.session_state.get("ml01_best_model_name")
    if not model_name:
        model_name = "(brak) — wybierz model w zakładce 1"

    st.info(f"Aktywny target: {target_txt}  |  Aktywny model: {model_name}")


def analyze_positive_rank_positions(
    df_rank: pd.DataFrame,
    score_col: str = "prob",
    y_col: str = "y_true",
) -> pd.DataFrame:
    """
    Analizuje pozycje prawdziwych sygnałów (+1) w rankingu score.

    Zwraca tabelę:
    - rank_position
    - percentile_position
    - czy w top 1%, 5%, 10%
    """

    if df_rank.empty:
        return pd.DataFrame()

    df = df_rank.copy()
    df = df.sort_values(score_col, ascending=False).reset_index(drop=True)

    df["rank_position"] = df.index + 1
    total_n = len(df)
    df["percentile_position"] = df["rank_position"] / total_n

    df_pos = df[df[y_col] == 1].copy()

    if df_pos.empty:
        return pd.DataFrame()

    df_pos["in_top_1pct"] = df_pos["percentile_position"] <= 0.01
    df_pos["in_top_5pct"] = df_pos["percentile_position"] <= 0.05
    df_pos["in_top_10pct"] = df_pos["percentile_position"] <= 0.10

    return df_pos[[
        "trade_date",
        "ticker",
        "prob",
        "rank_position",
        "percentile_position",
        "in_top_1pct",
        "in_top_5pct",
        "in_top_10pct",
    ]]


def apply_quality_filters(df_rank: pd.DataFrame) -> pd.DataFrame:

    filters = st.session_state.get("ml01_filters", {})
    min_conditions = st.session_state.get("ml01_min_conditions", None)

    if not filters:
        return df_rank

    df = df_rank.copy()

    # Tworzymy licznik spełnionych warunków
    df["_conditions_met"] = 0

    total_active_filters = 0

    # ==============================
    # TREND krótkoterminowy
    # ==============================
    if filters.get("trend") and {"ema_20", "ema_50"}.issubset(df.columns):
        total_active_filters += 1
        df["_conditions_met"] += (df["ema_20"] > df["ema_50"]).astype(int)

    # ==============================
    # TREND długoterminowy
    # ==============================
    if filters.get("trend_long") and {"ema_50", "ema_200"}.issubset(df.columns):
        total_active_filters += 1
        df["_conditions_met"] += (df["ema_50"] > df["ema_200"]).astype(int)

    # ==============================
    # MOMENTUM
    # ==============================
    if filters.get("momentum") and "momentum_12m" in df.columns:
        total_active_filters += 1
        df["_conditions_met"] += (df["momentum_12m"] > 0).astype(int)

    # ==============================
    # RSI
    # ==============================
    if filters.get("rsi") and "rsi_14" in df.columns:
        total_active_filters += 1
        df["_conditions_met"] += (df["rsi_14"] > 50).astype(int)

    # ==============================
    # VOLATILITY
    # ==============================
    if filters.get("volatility") and "volatility_20d" in df.columns:
        total_active_filters += 1
        median_vol = df["volatility_20d"].median()
        df["_conditions_met"] += (df["volatility_20d"] > median_vol).astype(int)

    # ==============================
    # VOLUME
    # ==============================
    if filters.get("volume") and "average_volume_20d" in df.columns:
        total_active_filters += 1
        median_vol = df["average_volume_20d"].median()
        df["_conditions_met"] += (df["average_volume_20d"] > median_vol).astype(int)

    # RSI < 30
    if filters.get("rsi_oversold") and "rsi_14" in df.columns:
        total_active_filters += 1
        df["_conditions_met"] += (df["rsi_14"] < 30).astype(int)

    # RSI < 70
    if filters.get("rsi_not_overbought") and "rsi_14" in df.columns:
        total_active_filters += 1
        df["_conditions_met"] += (df["rsi_14"] < 70).astype(int)

    # MACD > 0
    if filters.get("macd_positive") and "macd_hist" in df.columns:
        total_active_filters += 1
        df["_conditions_met"] += (df["macd_hist"] > 0).astype(int)

    # Close > SMA200
    if filters.get("price_above_sma200") and {"close_price", "sma_200"}.issubset(df.columns):
        total_active_filters += 1
        df["_conditions_met"] += (df["close_price"] > df["sma_200"]).astype(int)

    # ATR > mediana
    if filters.get("atr_high") and "atr_14" in df.columns:
        total_active_filters += 1
        median_atr = df["atr_14"].median()
        df["_conditions_met"] += (df["atr_14"] > median_atr).astype(int)

    # Close > VWAP
    if filters.get("price_above_vwap") and {"close_price", "vwap_20d"}.issubset(df.columns):
        total_active_filters += 1
        df["_conditions_met"] += (df["close_price"] > df["vwap_20d"]).astype(int)


    # =====================================
    # Jeśli nie ustawiono minimalnej liczby warunków
    # -> zachowujemy klasyczne AND
    # =====================================
    if min_conditions is None:
        min_conditions = total_active_filters

    df_filtered = df[df["_conditions_met"] >= min_conditions].copy()

    return df_filtered



def _render_quality_filter_controls(*, key_prefix: str, disabled: bool = False) -> tuple[dict, int]:
    """
    Renderuje checkboxy filtrów jakościowych (domyślnie WYŁĄCZONE).
    Zwraca:
      - filters: dict (np. {"trend": True, ...})
      - min_conditions: int (minimalna liczba spełnionych warunków)
    """
    st.markdown("#### Filtry jakościowe (opcjonalne)")
    st.caption(
        "Te filtry NIE zmieniają tabeli powyżej. "
        "Zadziałają dopiero po kliknięciu **Przefiltruj** i tylko na małym zbiorze z tej zakładki."
    )

    # Helper: nie podajemy "value=", jeśli widget już istnieje w session_state,
    # bo inaczej Streamlit ostrzega (value + SessionState jednocześnie).
    def _cb(label: str, *, key: str, default: bool = False) -> bool:
        if key in st.session_state:
            return st.checkbox(label, key=key, disabled=disabled)
        return st.checkbox(label, value=default, key=key, disabled=disabled)

    c1, c2 = st.columns(2)
    with c1:
        trend = _cb("Trend: ema_20 > ema_50", key=f"{key_prefix}_f_trend", default=False)
        trend_long = _cb("Trend długoterminowy: ema_50 > ema_200", key=f"{key_prefix}_f_trend_long", default=False)
        momentum = _cb("Momentum dodatni (momentum_12m > 0)", key=f"{key_prefix}_f_momentum", default=False)
        rsi_oversold = _cb("RSI < 30 (wyprzedanie)", key=f"{key_prefix}_f_rsi_oversold", default=False)
        macd_positive = _cb("MACD > 0", key=f"{key_prefix}_f_macd", default=False)
        price_above_sma200 = _cb("Close > SMA200", key=f"{key_prefix}_f_price_sma200", default=False)

    with c2:
        rsi = _cb("RSI > 50", key=f"{key_prefix}_f_rsi", default=False)
        volatility = _cb("Volatility > mediana", key=f"{key_prefix}_f_volatility", default=False)
        volume = _cb("Volume > mediana", key=f"{key_prefix}_f_volume", default=False)
        rsi_not_overbought = _cb("RSI < 70 (brak wykupienia)", key=f"{key_prefix}_f_rsi_not_overbought", default=False)
        atr_high = _cb("ATR > mediana", key=f"{key_prefix}_f_atr", default=False)
        price_above_vwap = _cb("Close > VWAP", key=f"{key_prefix}_f_vwap", default=False)

    filters = {
        "trend": trend,
        "trend_long": trend_long,
        "momentum": momentum,
        "rsi": rsi,
        "volatility": volatility,
        "volume": volume,
        "rsi_oversold": rsi_oversold,
        "rsi_not_overbought": rsi_not_overbought,
        "macd_positive": macd_positive,
        "price_above_sma200": price_above_sma200,
        "atr_high": atr_high,
        "price_above_vwap": price_above_vwap,
    }


    active_cnt = sum(1 for v in filters.values() if v)
    if active_cnt == 0:
        st.info("Brak aktywnych filtrów — kliknięcie **Przefiltruj** nie zmieni wyników (PO = PRZED).")

    # Minimalna liczba spełnionych warunków ma sens tylko gdy cokolwiek jest aktywne.
    # Zakres: 1..active_cnt, ale gdy active_cnt=0 dajemy 0 (ignorowane przez filtr).
    mc_key = f"{key_prefix}_min_conditions"

    if active_cnt > 0:
        if mc_key in st.session_state:
            min_conditions = st.number_input(
                "Minimalna liczba spełnionych warunków",
                min_value=1,
                max_value=active_cnt,
                step=1,
                key=mc_key,
                disabled=disabled,
                help=(
                    "Jeśli ustawisz wartość równą liczbie zaznaczonych filtrów → klasyczne AND (wszystkie muszą być spełnione). "
                    "Jeśli mniejszą → podejście 'co najmniej N warunków'."
                ),
            )
        else:
            min_conditions = st.number_input(
                "Minimalna liczba spełnionych warunków",
                min_value=1,
                max_value=active_cnt,
                value=int(active_cnt),
                step=1,
                key=mc_key,
                disabled=disabled,
                help=(
                    "Jeśli ustawisz wartość równą liczbie zaznaczonych filtrów → klasyczne AND (wszystkie muszą być spełnione). "
                    "Jeśli mniejszą → podejście 'co najmniej N warunków'."
                ),
            )
    else:
        min_conditions = 0

    return filters, int(min_conditions)


def _apply_quality_filters_on_df(
    df_small: pd.DataFrame,
    *,
    filters: dict,
    min_conditions: int,
) -> pd.DataFrame:
    """
    Używa istniejącej funkcji apply_quality_filters(df_rank),
    ale podstawia konfigurację filtrów tylko na czas wywołania.

    Dzięki temu NIE filtrujemy dużych zbiorów globalnie
    i nie mieszamy stanu między zakładkami.
    """
    # backup
    prev_filters = st.session_state.get("ml01_filters", None)
    prev_min_cond = st.session_state.get("ml01_min_conditions", None)

    try:
        st.session_state["ml01_filters"] = filters
        # min_conditions=0 oznacza: ignoruj próg (zachowaj zachowanie jak "bez progowania")
        st.session_state["ml01_min_conditions"] = (min_conditions if min_conditions > 0 else None)
        return apply_quality_filters(df_small)
    finally:
        # restore
        if prev_filters is None:
            st.session_state.pop("ml01_filters", None)
        else:
            st.session_state["ml01_filters"] = prev_filters

        if prev_min_cond is None:
            st.session_state.pop("ml01_min_conditions", None)
        else:
            st.session_state["ml01_min_conditions"] = prev_min_cond


def _plot_prob_hist_before_after(df_before: pd.DataFrame, df_after: pd.DataFrame, *, title: str) -> None:
    import matplotlib.pyplot as plt

    if df_before is None or df_before.empty or "prob" not in df_before.columns:
        st.warning("Brak danych 'prob' do histogramu (PRZED).")
        return

    fig, ax = plt.subplots(figsize=(6, 3))

    before_vals = df_before["prob"].dropna().values
    ax.hist(before_vals, bins=30, alpha=0.75, label="PRZED", density=False, color="#1f77b4")

    if df_after is not None and (not df_after.empty) and "prob" in df_after.columns:
        after_vals = df_after["prob"].dropna().values
        ax.hist(after_vals, bins=30, alpha=0.75, label="PO", density=False, color="#ff7f0e")

    ax.set_title(title)
    ax.set_xlabel("prob")
    ax.set_ylabel("liczba obserwacji")
    ax.legend()

    col_left, col_plot, col_stats = st.columns([1, 3, 1])


    with col_plot:
        st.pyplot(fig, width="content")

    with col_stats:
        # --- PRZED ---
        n_before = int(len(df_before)) if df_before is not None else 0
        if df_before is not None and "y_true" in df_before.columns and n_before > 0:
            pos_before = int((df_before["y_true"] == 1).sum())
            pos_rate_before = (pos_before / n_before) * 100.0
        else:
            pos_before = 0
            pos_rate_before = 0.0

        # --- PO ---
        n_after = int(len(df_after)) if df_after is not None else 0
        if df_after is not None and "y_true" in df_after.columns and n_after > 0:
            pos_after = int((df_after["y_true"] == 1).sum())
            pos_rate_after = (pos_after / n_after) * 100.0
        else:
            pos_after = 0
            pos_rate_after = 0.0

        st.markdown("### PRZED (zbiór bazowy)")
        st.metric("Liczba obserwacji (N)", n_before)
        st.metric("Udział klasy pozytywnej (y=1)", f"{pos_rate_before:.1f}%")

        st.markdown("### PO (po filtrach jakościowych)")
        st.metric("Liczba obserwacji (N)", n_after)
        st.metric("Udział klasy pozytywnej (y=1)", f"{pos_rate_after:.1f}%")







def _resolve_key_cols(df: pd.DataFrame) -> list[str]:
    """
    Wybiera kolumny kluczowe do porównywania zbiorów (selected vs not selected).
    Preferujemy company_id+trade_date, fallback ticker+trade_date.
    """
    if df is None or df.empty:
        return ["ticker", "trade_date"]

    if {"company_id", "trade_date"}.issubset(df.columns):
        return ["company_id", "trade_date"]
    if {"ticker", "trade_date"}.issubset(df.columns):
        return ["ticker", "trade_date"]

    # awaryjnie: spróbuj po samym index (ale to najsłabsze)
    return []


def _exclude_rows_by_key(df_all: pd.DataFrame, df_selected: pd.DataFrame) -> pd.DataFrame:
    """
    Zwraca df_all bez wierszy występujących w df_selected (po key_cols).
    """
    if df_all is None or df_all.empty:
        return df_all
    if df_selected is None or df_selected.empty:
        return df_all

    key_cols = _resolve_key_cols(df_all)
    if not key_cols:
        # fallback: jeśli nie ma klucza, nie umiemy wykluczyć deterministycznie
        return df_all.copy()

    sel_keys = df_selected[key_cols].drop_duplicates()
    merged = df_all.merge(sel_keys.assign(_is_sel=1), on=key_cols, how="left")
    out = merged[merged["_is_sel"].isna()].drop(columns=["_is_sel"])
    return out


def _plot_prob_hist_tp_fp_tn_fn(
    df_sel_before: pd.DataFrame,
    df_sel_after: pd.DataFrame,
    df_all_before: pd.DataFrame,
    df_all_after: pd.DataFrame,
    *,
    title_tp_fp: str,
    title_tn_fn: str,
) -> None:
    """
    Rysuje 2 histogramy:
    1) TP vs FP (na zbiorze SELECTED) – PRZED vs PO
    2) TN vs FN (na zbiorze NOT SELECTED) – PRZED vs PO

    Definicje (bez dodatkowego threshold):
    - SELECTED = wynik selekcji rankingowej (grid)
      TP: y_true==1 w selected
      FP: y_true==0 w selected
    - NOT SELECTED = df_all \ selected
      TN: y_true==0 w not-selected
      FN: y_true==1 w not-selected
    """

    import matplotlib.pyplot as plt

    def _safe_probs(df: pd.DataFrame, mask: pd.Series) -> np.ndarray:
        if df is None or df.empty or "prob" not in df.columns:
            return np.array([])
        x = df.loc[mask, "prob"]
        x = pd.to_numeric(x, errors="coerce").dropna()
        return x.values

    # ---------- 1) TP vs FP (SELECTED) ----------
    if df_sel_before is None or df_sel_before.empty or "y_true" not in df_sel_before.columns:
        st.warning("Brak danych SELECTED PRZED lub brak kolumny y_true — nie mogę policzyć TP/FP.")
    else:
        fig1, ax1 = plt.subplots(figsize=(6, 3))

        tp_b = _safe_probs(df_sel_before, df_sel_before["y_true"] == 1)
        fp_b = _safe_probs(df_sel_before, df_sel_before["y_true"] == 0)

        ax1.hist(tp_b, bins=30, alpha=0.80, label="TP (PRZED)", density=False, color="#0047AB")
        ax1.hist(fp_b, bins=30, alpha=0.80, label="FP (PRZED)", density=False, color="#d62728")

        if df_sel_after is not None and (not df_sel_after.empty) and "y_true" in df_sel_after.columns:
            tp_a = _safe_probs(df_sel_after, df_sel_after["y_true"] == 1)
            fp_a = _safe_probs(df_sel_after, df_sel_after["y_true"] == 0)

            ax1.hist(tp_a, bins=30, alpha=0.80, label="TP (PO)", density=False, color="#2ca02c")
            ax1.hist(fp_a, bins=30, alpha=0.80, label="FP (PO)", density=False, color="#e377c2")



        ax1.set_title(title_tp_fp)
        ax1.set_xlabel("prob")
        ax1.set_ylabel("liczba obserwacji")
        # Ujednolicamy oś X z histogramem GLOBAL: bierzemy realny zakres prob z SELECTED (PRZED + PO)
        x_vals = []
        if df_sel_before is not None and (not df_sel_before.empty) and "prob" in df_sel_before.columns:
            x_vals.append(df_sel_before["prob"].dropna().values)
        if df_sel_after is not None and (not df_sel_after.empty) and "prob" in df_sel_after.columns:
            x_vals.append(df_sel_after["prob"].dropna().values)

        if len(x_vals) > 0:
            x_all = np.concatenate(x_vals)
            if x_all.size > 0:
                x_min = float(np.min(x_all))
                x_max = float(np.max(x_all))
                # mały margines, żeby słupki nie kleiły się do ramki
                pad = max(0.001, 0.02 * (x_max - x_min))
                ax1.set_xlim(x_min - pad, x_max + pad)
            else:
                ax1.set_xlim(0, 1)
        else:
            ax1.set_xlim(0, 1)
        ax1.legend()

        col_left, col_plot, col_metrics = st.columns([1, 3, 1])

        with col_plot:
            st.pyplot(fig1, width="content")

        with col_metrics:
            st.markdown("**SELECTED — liczności klas po etykiecie y_true**")

            tp_przed = int((df_sel_before["y_true"] == 1).sum())
            fp_przed = int((df_sel_before["y_true"] == 0).sum())

            tp_po = int((df_sel_after["y_true"] == 1).sum()) if df_sel_after is not None and not df_sel_after.empty else 0
            fp_po = int((df_sel_after["y_true"] == 0).sum()) if df_sel_after is not None and not df_sel_after.empty else 0

            st.metric("TP — trafienia (y=1) w SELECTED (PRZED)", tp_przed)
            st.metric("FP — fałszywe alarmy (y=0) w SELECTED (PRZED)", fp_przed)
            st.metric("TP — trafienia (y=1) w SELECTED (PO)", tp_po)
            st.metric("FP — fałszywe alarmy (y=0) w SELECTED (PO)", fp_po)




    # ---------- 2) TN vs FN (NOT SELECTED) ----------
    # budujemy not-selected PRZED oraz PO:
    not_sel_before = _exclude_rows_by_key(df_all_before, df_sel_before)
    not_sel_after = _exclude_rows_by_key(df_all_after, df_sel_after) if df_sel_after is not None else None

    if not_sel_before is None or not_sel_before.empty or "y_true" not in not_sel_before.columns:
        st.warning("Brak danych NOT-SELECTED PRZED lub brak kolumny y_true — nie mogę policzyć TN/FN.")
    else:
        fig2, ax2 = plt.subplots(figsize=(6, 3))

        tn_b = _safe_probs(not_sel_before, not_sel_before["y_true"] == 0)
        fn_b = _safe_probs(not_sel_before, not_sel_before["y_true"] == 1)

        ax2.hist(tn_b, bins=30, alpha=0.80, label="TN (PRZED)", density=True, color="#003366")
        ax2.hist(fn_b, bins=30, alpha=0.80, label="FN (PRZED)", density=True, color="#ff6600")


        if not_sel_after is not None and (not not_sel_after.empty) and "y_true" in not_sel_after.columns:
            tn_a = _safe_probs(not_sel_after, not_sel_after["y_true"] == 0)
            fn_a = _safe_probs(not_sel_after, not_sel_after["y_true"] == 1)

            ax2.hist(tn_a, bins=30, alpha=0.80, label="TN (PO)", density=True, color="#00cc66")
            ax2.hist(fn_a, bins=30, alpha=0.80, label="FN (PO)", density=True, color="#cc0000")



        ax2.set_title(title_tn_fn)
        ax2.set_xlabel("prob")
        ax2.set_ylabel("gęstość rozkładu")
        ax2.set_xlim(0, 1)
        ax2.legend()

        col_left, col_plot, col_metrics = st.columns([1, 3, 1])

        with col_plot:
            st.pyplot(fig2, width="content")

        with col_metrics:
            st.markdown("**NOT SELECTED — liczności**")

            tn_przed = int((not_sel_before["y_true"] == 0).sum())
            fn_przed = int((not_sel_before["y_true"] == 1).sum())

            tn_po = int((not_sel_after["y_true"] == 0).sum()) if not_sel_after is not None and not not_sel_after.empty else 0
            fn_po = int((not_sel_after["y_true"] == 1).sum()) if not_sel_after is not None and not not_sel_after.empty else 0

            st.metric("TN (PRZED)", tn_przed)
            st.metric("FN (PRZED)", fn_przed)
            st.metric("TN (PO)", tn_po)
            st.metric("FN (PO)", fn_po)


def _plot_pre_filter_analytics(df_small: pd.DataFrame) -> None:
    """
    Analityczne histogramy PRZED filtrowaniem.
    Cel: pomóc zdecydować, jakie filtry jakościowe włączyć.
    """

    import matplotlib.pyplot as plt
    import numpy as np

    if df_small is None or df_small.empty or "prob" not in df_small.columns:
        st.warning("Brak danych do analizy rozkładu (prob).")
        return

    # ======================================================
    # Rozkład prob (cały zbiór PRZED)
    # ======================================================

    fig1, ax1 = plt.subplots(figsize=(6, 3))
    probs = pd.to_numeric(df_small["prob"], errors="coerce").dropna()

    ax1.hist(probs, bins=25, density=False, alpha=0.85, color="#1f77b4")
    ax1.set_title("Rozkład score (prob) — zbiór PRZED filtrowaniem")
    ax1.set_xlabel("prob (score modelu)")
    ax1.set_ylabel("liczba obserwacji")

    if len(probs) > 0:
        pad = max(0.001, 0.02 * (probs.max() - probs.min()))
        ax1.set_xlim(probs.min() - pad, probs.max() + pad)

    col_l, col_plot, col_stats = st.columns([1, 3, 1])

    with col_plot:
        st.pyplot(fig1, width="content")

    with col_stats:
        st.markdown("### Statystyki score")
        st.metric("Liczba sygnałów", len(probs))
        st.metric("Średni score", f"{probs.mean():.4f}")
        st.metric("Mediana score", f"{probs.median():.4f}")
        st.metric("Min / Max", f"{probs.min():.3f} / {probs.max():.3f}")

    # ======================================================
    # Rozkład prob wg klasy (y_true)
    # ======================================================

    if "y_true" in df_small.columns and df_small["y_true"].nunique() > 1:

        fig2, ax2 = plt.subplots(figsize=(6, 3))

        tp_vals = df_small[df_small["y_true"] == 1]["prob"].dropna()
        fp_vals = df_small[df_small["y_true"] == 0]["prob"].dropna()

        ax2.hist(tp_vals, bins=25, density=False, alpha=0.85,
                 label="y=1 (trafienia)", color="#0047AB")
        ax2.hist(fp_vals, bins=25, density=False, alpha=0.65,
                 label="y=0 (fałszywe alarmy)", color="#d62728")

        ax2.set_title("Score (prob) vs klasa rzeczywista (y_true) — PRZED")
        ax2.set_xlabel("prob (score modelu)")
        ax2.set_ylabel("liczba obserwacji")

        if len(probs) > 0:
            ax2.set_xlim(probs.min() - pad, probs.max() + pad)

        ax2.legend()

        col_l, col_plot, col_stats = st.columns([1, 3, 1])

        with col_plot:
            st.pyplot(fig2, width="content")

        with col_stats:
            st.markdown("### Rozkład klas")
            n_total = len(df_small)
            n_pos = int((df_small["y_true"] == 1).sum())
            n_neg = int((df_small["y_true"] == 0).sum())

            st.metric("Trafienia (y=1)", n_pos)
            st.metric("Fałszywe alarmy (y=0)", n_neg)
            st.metric("Udział klasy +1", f"{(n_pos/n_total)*100:.1f}%")

    # ======================================================
    # Percentyle score (czy cutoff ma sens?)
    # ======================================================

    fig3, ax3 = plt.subplots(figsize=(6, 3))

    percentiles = np.percentile(probs, [50, 75, 90, 95])
    ax3.hist(probs, bins=25, density=False, alpha=0.85, color="#2ca02c")

    for p in percentiles:
        ax3.axvline(p, linestyle="--")

    ax3.set_title("Score (prob) z zaznaczonymi percentylami")
    ax3.set_xlabel("prob (score modelu)")
    ax3.set_ylabel("liczba obserwacji")

    if len(probs) > 0:
        ax3.set_xlim(probs.min() - pad, probs.max() + pad)

    col_l, col_plot, col_stats = st.columns([1, 3, 1])

    with col_plot:
        st.pyplot(fig3, width="content")

    with col_stats:
        st.markdown("### Percentyle score")
        st.metric("P50 (mediana)", f"{percentiles[0]:.4f}")
        st.metric("P75", f"{percentiles[1]:.4f}")
        st.metric("P90", f"{percentiles[2]:.4f}")
        st.metric("P95", f"{percentiles[3]:.4f}")
        st.markdown("---")

    st.markdown(
    """
    ### Jak interpretować percentyle?

    Percentyl oznacza, że określony procent sygnałów ma **score (prob) mniejszy lub równy** tej wartości.

    Przykład:
    - **P90 = 0.9962** oznacza, że 90% sygnałów ma score ≤ 0.9962,
    a tylko 10% ma wyższy score.

    Można to wykorzystać jako:
    - próg selekcji (np. wybór Top 10% sygnałów),
    - punkt odniesienia do budowy filtrów jakościowych,
    - ocenę, czy model silnie koncentruje score w górnym zakresie.

    Jeżeli percentyle są bardzo blisko siebie (np. P75–P95),
    oznacza to, że model daje podobne wysokie oceny wielu sygnałom
    — wtedy sama selekcja po score może być niewystarczająca
    i warto użyć dodatkowych filtrów jakościowych.
    """
    )


# ============================================================
# UI HELPERS: AgGrid + zestaw kolumn dla tabel PRZED/PO
# ============================================================

def _safe_to_dt(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series([pd.NaT] * len(df))
    return pd.to_datetime(df[col], errors="coerce")


def _build_table_view_base(
    df: pd.DataFrame,
    *,
    df_val_prices: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    dfx = df.copy()

    # Dodaj zwroty ex post (na podstawie VALIDATE) także dla PRZED (mały zbiór)
    if df_val_prices is not None and not df_val_prices.empty:
        dfx = _add_expost_returns_for_po_rows(dfx, df_val_prices=df_val_prices, horizons=(20, 60, 120))

    if "trade_date" in dfx.columns:
        dfx["trade_date"] = _safe_to_dt(dfx, "trade_date")
        dfx = dfx.sort_values("trade_date", ascending=True)

    # Tworzymy kolumnę TP / FP
    if "y_true" in dfx.columns:
        dfx["Typ rekordu"] = np.where(dfx["y_true"] == 1, "TP", "FP")

    rename_map = {
        "trade_date": "Data notowania",
        "ticker": "Ticker",
        "company_name": "Nazwa spółki",
        "close_price": "Cena",
        "prob": "Prawdopodobieństwo",

        # zyski ex post
        "ret_20": "Zysk 20 sesji",
        "ret_60": "Zysk 60 sesji",
        "ret_120": "Zysk 120 sesji",
        "ret_end": "Zysk do końca VALIDATE",
    }

    base_cols_prefix = [
        "trade_date",
        "ticker",
        "company_name",
        "close_price",  # Cena
    ]

    profit_cols = [c for c in ["ret_20", "ret_60", "ret_120", "ret_end"] if c in dfx.columns]

    base_cols_suffix = [
        "prob",  # Prawdopodobieństwo po zyskach (tak jak w tabeli PO)
        "Typ rekordu",
    ]

    cols = [c for c in (base_cols_prefix + profit_cols + base_cols_suffix) if c in dfx.columns]
    cols = list(dict.fromkeys(cols))

    out = dfx[cols].copy().reset_index(drop=True)
    out.insert(0, "Lp.", out.index + 1)
    out = out.rename(columns=rename_map)
    return out



def _quality_filter_indicator_cols(filters: dict) -> list[str]:
    """
    Mapowanie: aktywny filtr -> kolumny wskaźników do pokazania (tylko w PO).
    """
    mapping = {
        "trend": ["ema_20", "ema_50"],
        "trend_long": ["ema_50", "ema_200"],
        "momentum": ["momentum_12m"],
        "rsi": ["rsi_14"],
        "volatility": ["volatility_20d"],
        "volume": ["average_volume_20d"],

        "rsi_oversold": ["rsi_14"],
        "rsi_not_overbought": ["rsi_14"],
        "macd_positive": ["macd_hist"],
        "price_above_sma200": ["close_price", "sma_200"],
        "atr_high": ["atr_14"],
        "price_above_vwap": ["close_price", "vwap_20d"],
    }

    cols = []
    for k, is_on in (filters or {}).items():
        if not is_on:
            continue
        cols.extend(mapping.get(k, []))

    # usuń duplikaty zachowując kolejność
    return list(dict.fromkeys(cols))


def _add_expost_returns_for_po_rows(
    dfx: pd.DataFrame,
    *,
    df_val_prices: pd.DataFrame,
    horizons: tuple[int, ...] = (20, 60, 120),
) -> pd.DataFrame:
    """
    Dodaje do dfx kolumny:
    - ret_20, ret_60, ret_120: procentowy zwrot po N sesjach (liczone po indeksie sesyjnym w VALIDATE)
    - ret_end: zwrot do końca dostępnego okresu VALIDATE

    Uwaga: kolumny są numeryczne (float), a znak % dodamy w AgGrid formatterze,
    żeby sortowanie działało poprawnie.
    """
    if dfx is None or dfx.empty:
        return dfx
    if df_val_prices is None or df_val_prices.empty:
        # brak danych cenowych VALIDATE → zwroty będą puste
        for h in horizons:
            dfx[f"ret_{h}"] = np.nan
        dfx["ret_end"] = np.nan
        return dfx

    # przygotowanie cen VALIDATE: tylko potrzebne kolumny
    prices = df_val_prices.copy()
    if "trade_date" in prices.columns:
        prices["trade_date"] = pd.to_datetime(prices["trade_date"], errors="coerce")
    if "ticker" not in prices.columns or "close_price" not in prices.columns or "trade_date" not in prices.columns:
        for h in horizons:
            dfx[f"ret_{h}"] = np.nan
        dfx["ret_end"] = np.nan
        return dfx

    prices = prices.dropna(subset=["ticker", "trade_date"]).sort_values(["ticker", "trade_date"], ascending=True)

    # cache per ticker → (dates, closes, date->idx)
    cache: dict[str, tuple[np.ndarray, np.ndarray, dict[pd.Timestamp, int]]] = {}

    def _get_ticker_cache(t: str):
        if t in cache:
            return cache[t]
        p = prices.loc[prices["ticker"] == t, ["trade_date", "close_price"]].copy()
        if p.empty:
            cache[t] = (np.array([]), np.array([]), {})
            return cache[t]
        p["trade_date"] = pd.to_datetime(p["trade_date"], errors="coerce")
        p = p.dropna(subset=["trade_date"]).sort_values("trade_date", ascending=True)
        dates = p["trade_date"].to_numpy()
        closes = pd.to_numeric(p["close_price"], errors="coerce").to_numpy()
        # mapowanie: trade_date -> index (uwaga: jeśli są duplikaty, bierzemy ostatni)
        dt_to_idx: dict[pd.Timestamp, int] = {}
        for i, dt in enumerate(dates):
            dt_to_idx[pd.Timestamp(dt)] = i
        cache[t] = (dates, closes, dt_to_idx)
        return cache[t]

    # przygotuj kolumny wynikowe
    for h in horizons:
        dfx[f"ret_{h}"] = np.nan
    dfx["ret_end"] = np.nan

    # potrzebujemy w dfx: ticker, trade_date, close_price
    if "ticker" not in dfx.columns or "trade_date" not in dfx.columns or "close_price" not in dfx.columns:
        return dfx

    # normalizujemy daty w dfx
    dfx["trade_date"] = pd.to_datetime(dfx["trade_date"], errors="coerce")

    # liczenie per wiersz (mały zbiór → wystarczy)
    for i, row in dfx.iterrows():
        t = row.get("ticker")
        base_date = row.get("trade_date")
        base_price = row.get("close_price")

        if pd.isna(t) or pd.isna(base_date):
            continue

        try:
            base_price_f = float(base_price)
        except Exception:
            continue

        dates, closes, dt_to_idx = _get_ticker_cache(str(t))
        if dates.size == 0:
            continue

        base_idx = dt_to_idx.get(pd.Timestamp(base_date))
        if base_idx is None:
            # jeśli nie znaleziono idealnie daty (np. różne godziny),
            # spróbuj dopasować po dacie (YYYY-MM-DD) ignorując czas
            bd = pd.Timestamp(base_date).normalize()
            base_idx = dt_to_idx.get(bd)
            if base_idx is None:
                continue

        # horyzonty
        for h in horizons:
            idx_h = base_idx + h
            if idx_h < len(closes) and base_price_f:
                try:
                    price_h = float(closes[idx_h])
                    dfx.at[i, f"ret_{h}"] = ((price_h - base_price_f) / base_price_f) * 100.0
                except Exception:
                    pass

        # do końca VALIDATE
        if len(closes) > 0 and base_price_f:
            try:
                end_price = float(closes[-1])
                dfx.at[i, "ret_end"] = ((end_price - base_price_f) / base_price_f) * 100.0
            except Exception:
                pass

    return dfx

def _build_table_view_after(
    df: pd.DataFrame,
    *,
    filters: dict,
    df_val_prices: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    dfx = df.copy()

    # Dodaj zwroty ex post (na podstawie VALIDATE) dla każdego wiersza tabeli PO
    if df_val_prices is not None and not df_val_prices.empty:
        dfx = _add_expost_returns_for_po_rows(dfx, df_val_prices=df_val_prices, horizons=(20, 60, 120))

    if "trade_date" in dfx.columns:
        dfx["trade_date"] = _safe_to_dt(dfx, "trade_date")
        dfx = dfx.sort_values("trade_date", ascending=True)

    if "y_true" in dfx.columns:
        dfx["Typ rekordu"] = np.where(dfx["y_true"] == 1, "TP", "FP")

    rename_map = {
        "trade_date": "Data notowania",
        "ticker": "Ticker",
        "company_name": "Nazwa spółki",
        "close_price": "Cena",
        "prob": "Prawdopodobieństwo",

        # zyski ex post (kolumny numeryczne; % dodamy formatterem AgGrid)
        "ret_20": "Zysk 20 sesji",
        "ret_60": "Zysk 60 sesji",
        "ret_120": "Zysk 120 sesji",
        "ret_end": "Zysk do końca VALIDATE",

        # fundamenty
        "mtv": "Kapitalizacja",
        "pb": "P/B",
        "pe": "P/E",

        # wskaźniki warunkowe (filtry jakościowe)
        "ema_20": "EMA 20",
        "ema_50": "EMA 50",
        "ema_200": "EMA 200",
        "momentum_12m": "Momentum 12m",
        "rsi_14": "RSI 14",
        "volatility_20d": "Zmienność 20d",
        "average_volume_20d": "Śr. wolumen 20d",
        "macd_hist": "MACD hist",
        "sma_200": "SMA 200",
        "atr_14": "ATR 14",
        "vwap_20d": "VWAP 20d",
    }

    base_cols_prefix = [
        "trade_date",
        "ticker",
        "company_name",
        "close_price",  # Cena
    ]

    profit_cols = [c for c in ["ret_20", "ret_60", "ret_120", "ret_end"] if c in dfx.columns]

    base_cols_suffix = [
        "prob",         # Prawdopodobieństwo (ma być po zyskach)
        "Typ rekordu",
    ]

    opt_fund = [c for c in ["mtv", "pb", "pe"] if c in dfx.columns]
    ind_cols = [c for c in _quality_filter_indicator_cols(filters) if c in dfx.columns]

    # kolejność: bazowe (do ceny) -> zyski -> prawdopodobieństwo -> typ -> fundamenty -> warunkowe
    cols = [c for c in (base_cols_prefix + profit_cols + base_cols_suffix + opt_fund + ind_cols) if c in dfx.columns]
    cols = list(dict.fromkeys(cols))  # usuń duplikaty zachowując kolejność

    out = dfx[cols].copy().reset_index(drop=True)
    out.insert(0, "Lp.", out.index + 1)
    out = out.rename(columns=rename_map)

    return out



def _render_aggrid_table(
    df_view: pd.DataFrame,
    *,
    table_key: str,
    height: int = 480,
    page_size: int = 10,
    avg_row_override: Optional[dict] = None,
):
    if df_view is None or df_view.empty:
        st.info("Brak danych do wyświetlenia.")
        return None

    dup = df_view.columns[df_view.columns.duplicated()].tolist()
    if dup:
        st.warning(f"Duplikaty kolumn w tabeli — usuwam nadmiarowe: {dup}")
        df_view = df_view.loc[:, ~df_view.columns.duplicated()]

    gb = GridOptionsBuilder.from_dataframe(df_view)
    from st_aggrid import JsCode

    gb.configure_default_column(
        sortable=True,
        filter=True,
        resizable=True,
        autoSizeColumns=False,
        minWidth=70,
        width=110,
    )

    # węższe kolumny bazowe
    # ---------------------------------------------------------
    # Formatery wspólne dla tabel AgGrid:
    # - Data notowania: zawsze YYYY-MM-DD, bez godziny
    # - Prawdopodobieństwo i wskaźniki liczbowe: 4 miejsca po przecinku
    # - Zyski ex post: 2 miejsca po przecinku + znak %
    # ---------------------------------------------------------

    date_fmt = JsCode(
        """
        function(params) {
            if (params.value === null || params.value === undefined || params.value === '') return '';
            const raw = String(params.value);

            // jeśli już wygląda jak YYYY-MM-DD..., obetnij tylko część daty
            if (raw.length >= 10) {
                return raw.slice(0, 10);
            }
            return raw;
        }
        """
    )

    num4_fmt = JsCode(
        """
        function(params) {
            if (params.value === null || params.value === undefined || params.value === '') return '';
            const v = Number(params.value);
            if (isNaN(v)) return params.value;
            return v.toFixed(4);
        }
        """
    )

    gb.configure_column("Lp.", width=70, minWidth=60)
    gb.configure_column("Data notowania", width=130, minWidth=120, valueFormatter=date_fmt)
    gb.configure_column("Ticker", width=90, minWidth=80)
    gb.configure_column("Nazwa spółki", width=160, minWidth=140)
    gb.configure_column("Cena", width=90, minWidth=80)
    gb.configure_column("Prawdopodobieństwo", width=150, minWidth=140, type=["numericColumn"], valueFormatter=num4_fmt)
    gb.configure_column("Typ rekordu", width=110, minWidth=100)

    # formatter procentów dla zysków ex post (wartości są float, pokazujemy "xx.xx%")
    pct_fmt = JsCode(
        """
        function(params) {
            if (params.value === null || params.value === undefined || params.value === '') return '';
            const v = Number(params.value);
            if (isNaN(v)) return params.value;
            return v.toFixed(2) + '%';
        }
        """
    )

    for col_name in [
        "Zysk 20 sesji",
        "Zysk 60 sesji",
        "Zysk 120 sesji",
        "Zysk do końca VALIDATE",
        "Zysk do końca TEST",
    ]:
        if col_name in df_view.columns:
            gb.configure_column(
                col_name,
                type=["numericColumn"],
                valueFormatter=pct_fmt,
                width=160,
                minWidth=150,
            )

    # Kolumny liczbowe wskaźnikowe / modelowe:
    # pokazujemy do 4 miejsc po przecinku.
    indicator_numeric_cols = [
        "Prawdopodobieństwo",
        "P/B",
        "P/E",
        "Kapitalizacja",
        "EMA 20",
        "EMA 50",
        "EMA 200",
        "Momentum 12m",
        "RSI 14",
        "Zmienność 20d",
        "Śr. wolumen 20d",
        "MACD hist",
        "SMA 200",
        "ATR 14",
        "VWAP 20d",
    ]

    for col_name in indicator_numeric_cols:
        if col_name in df_view.columns:
            gb.configure_column(
                col_name,
                type=["numericColumn"],
                valueFormatter=num4_fmt,
                width=120,
                minWidth=110,
            )

    gb.configure_pagination(
        paginationAutoPageSize=False,
        paginationPageSize=page_size,
    )

    grid_options = gb.build()

    # -------------------------
    # Wiersz średnich (pin na dole)
    # - jeśli avg_row_override podany: nie liczymy średnich, tylko wstrzykujemy wartości
    # - inaczej: zachowanie jak wcześniej (liczenie z df_view)
    # -------------------------
    profit_view_cols = ["Zysk 20 sesji", "Zysk 60 sesji", "Zysk 120 sesji", "Zysk do końca VALIDATE"]
    avg_cols = [c for c in (profit_view_cols + ["Prawdopodobieństwo"]) if c in df_view.columns]

    avg_row = {c: None for c in df_view.columns}

    # etykieta wiersza średnich – w kolumnie tekstowej
    if "Nazwa spółki" in avg_row:
        avg_row["Nazwa spółki"] = "ŚREDNIA"
    elif "Ticker" in avg_row:
        avg_row["Ticker"] = "ŚREDNIA"

    if avg_row_override:
        for c in avg_cols:
            if c in avg_row_override:
                avg_row[c] = avg_row_override.get(c)
    else:
        for c in avg_cols:
            s = pd.to_numeric(df_view[c], errors="coerce")
            avg = float(s.mean()) if s.notna().any() else np.nan
            avg_row[c] = avg  # float -> formatowanie % robi AgGrid formatter

    grid_options["pinnedBottomRowData"] = [avg_row]

    return AgGrid(
        df_view,
        gridOptions=grid_options,
        height=height,
        theme="balham",
        fit_columns_on_grid_load=True,
        key=table_key,
        allow_unsafe_jscode=True,
    )



def _render_validate_price_chart_for_selected_row(
    df_val: pd.DataFrame,
    selected_row: pd.Series,
) -> None:
    """
    Wykres cen dla wybranej firmy (ticker) na zbiorze VALIDATION (pełny zakres dat),
    z overlay EMA50/EMA200 + marker dnia wskazanego przez selected_row,
    oraz sekcją 'Efekt 20 sesji' i 'Efekt do końca VALIDATE' pod wykresem.

    UWAGA: To jest analiza ex post (historyczna), nie sygnał decyzyjny.
    """

    if df_val is None or not isinstance(df_val, pd.DataFrame) or df_val.empty:
        st.info("Brak danych VALIDATION do zbudowania wykresu.")
        return

    # wymagane pola w df_val
    required_cols = {"trade_date", "ticker", "close_price", "ema_50", "ema_200"}
    missing = [c for c in required_cols if c not in df_val.columns]
    if missing:
        st.info(f"Brak kolumn w df_val potrzebnych do wykresu: {missing}")
        return

    if selected_row is None or len(selected_row) == 0:
        st.info("Nie wybrano rekordu PO do analizy.")
        return

    if "Ticker" not in selected_row or "Data notowania" not in selected_row:
        st.info("Wybrany rekord nie zawiera pól 'Ticker' / 'Data notowania'.")
        return

    ticker = str(selected_row["Ticker"])
    picked_date_raw = selected_row["Data notowania"]
    picked_dt = pd.to_datetime(picked_date_raw, errors="coerce")
    if pd.isna(picked_dt):
        st.info("Nie udało się rozpoznać daty wybranego rekordu.")
        return

    # filtr firmy na VALIDATE
    df = df_val.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
    df = df.dropna(subset=["trade_date"])
    df = df[df["ticker"].astype(str) == ticker].sort_values("trade_date").reset_index(drop=True)

    if df.empty:
        st.info(f"Brak danych VALIDATION dla tickera: {ticker}")
        return

    # --- znajdź bazowy dzień do oceny:
    # 1) dokładny match po dacie (normalize),
    # 2) jeśli brak – najbliższa data <= picked_dt
    mask_exact = df["trade_date"].dt.normalize() == picked_dt.normalize()
    if mask_exact.any():
        base_idx = int(np.where(mask_exact.values)[0][0])
    else:
        prev_idx = df.index[df["trade_date"] <= picked_dt]
        if len(prev_idx) == 0:
            base_idx = 0
        else:
            base_idx = int(prev_idx.max())

    base_date = df.loc[base_idx, "trade_date"]
    base_price = float(df.loc[base_idx, "close_price"])

    # --- ujednolicone liczenie % (ten sam mechanizm co w tabeli PO)
    _one = pd.DataFrame([{
        "ticker": ticker,
        "trade_date": base_date,
        "close_price": base_price,
    }])

    _one = _add_expost_returns_for_po_rows(_one, df_val_prices=df, horizons=(20, 60, 120))

    pct_20 = _one.loc[0, "ret_20"]
    pct_60 = _one.loc[0, "ret_60"]
    pct_120 = _one.loc[0, "ret_120"]
    pct_end = _one.loc[0, "ret_end"]

    # --- target: +20 sesji (t+20 w sensie indeksu sesyjnego)
    idx_20 = base_idx + 20
    has_20 = idx_20 < len(df)
    if has_20:
        date_20 = df.loc[idx_20, "trade_date"]
        price_20 = float(df.loc[idx_20, "close_price"])
    else:
        date_20 = None
        price_20 = None

    # --- target: +60 sesji
    idx_60 = base_idx + 60
    has_60 = idx_60 < len(df)
    if has_60:
        date_60 = df.loc[idx_60, "trade_date"]
        price_60 = float(df.loc[idx_60, "close_price"])
    else:
        date_60 = None
        price_60 = None

    # --- target: +120 sesji
    idx_120 = base_idx + 120
    has_120 = idx_120 < len(df)
    if has_120:
        date_120 = df.loc[idx_120, "trade_date"]
        price_120 = float(df.loc[idx_120, "close_price"])
    else:
        date_120 = None
        price_120 = None

    # --- target: koniec dostępnego okresu VALIDATE
    end_idx = len(df) - 1
    end_date = df.loc[end_idx, "trade_date"]
    end_price = float(df.loc[end_idx, "close_price"])


    # --- zapis do session_state (do użycia w innych miejscach UI, np. tabela)
    st.session_state["ml01_expost_validate"] = {
        "ticker": ticker,
        "base_idx": base_idx,
        "base_date": base_date,
        "base_price": base_price,
        "p20": {"h": 20, "has": has_20, "date": date_20, "price": price_20, "pct": pct_20},
        "p60": {"h": 60, "has": has_60, "date": date_60, "price": price_60, "pct": pct_60},
        "p120": {"h": 120, "has": has_120, "date": date_120, "price": price_120, "pct": pct_120},
        "pend": {"label": "end_validate", "date": end_date, "price": end_price, "pct": pct_end},
    }


    # -------------------------
    # WYKRES (Plotly)
    # -------------------------
    fig = go.Figure()

    # CENA
    fig.add_trace(
        go.Scatter(
            x=df["trade_date"],
            y=df["close_price"],
            mode="lines",
            name="Cena",
            line=dict(width=2),
            hovertemplate="Data: %{x|%Y-%m-%d}<br>Cena: %{y:.2f}<extra></extra>",
        )
    )

    # EMA 50
    fig.add_trace(
        go.Scatter(
            x=df["trade_date"],
            y=df["ema_50"],
            mode="lines",
            name="EMA 50",
            line=dict(width=1.5, dash="dot"),
            hovertemplate="Data: %{x|%Y-%m-%d}<br>EMA 50: %{y:.2f}<extra></extra>",
        )
    )

    # EMA 200
    fig.add_trace(
        go.Scatter(
            x=df["trade_date"],
            y=df["ema_200"],
            mode="lines",
            name="EMA 200",
            line=dict(width=1.5, dash="dash"),
            hovertemplate="Data: %{x|%Y-%m-%d}<br>EMA 200: %{y:.2f}<extra></extra>",
        )
    )

    # Marker PO (bazowy dzień)
    prob_txt = ""
    if "Prawdopodobieństwo" in selected_row and pd.notna(selected_row["Prawdopodobieństwo"]):
        try:
            prob_txt = f"prob={float(selected_row['Prawdopodobieństwo']):.4f}"
        except Exception:
            prob_txt = ""

    fig.add_trace(
        go.Scatter(
            x=[base_date],
            y=[base_price],
            mode="markers",
            name="PO (wybrany dzień)",
            marker=dict(size=10),
            hovertemplate=(
                "PO: %{x|%Y-%m-%d}<br>"
                "Cena: %{y:.2f}<br>"
                f"{prob_txt}<extra></extra>"
            ),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=[base_date],
            y=[base_price * 1.01],
            text=["PO"],
            mode="text",
            textposition="top center",
            textfont=dict(size=12),
            showlegend=False,
            hoverinfo="skip",
        )
    )

    fig.update_layout(
        height=420,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(
            orientation="h",
            y=1.08,
            x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=12),
        ),
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
        gridwidth=1,
        tickformat="%Y-%m-%d",
    )

    st.plotly_chart(fig, width="stretch")

    # -------------------------
    # SEKcJA: EFEKT EX POST
    # -------------------------
    st.markdown("#### Efekt ex post (VALIDATE)")

    def _fmt_date(d) -> str:
        if d is None:
            return "—"
        try:
            return pd.to_datetime(d).strftime("%Y-%m-%d")
        except Exception:
            return str(d)

    def _fmt_price(v) -> str:
        if v is None or pd.isna(v):
            return "—"
        try:
            return f"{float(v):.2f}"
        except Exception:
            return str(v)

    def _fmt_pct(v) -> tuple[str, str, str]:
        """
        returns: (text, color, label)
        """
        if v is None or pd.isna(v):
            return ("—", "#9aa0a6", "BRAK DANYCH")
        v = float(v)
        color = "#2ecc71" if v > 0 else ("#e74c3c" if v < 0 else "#9aa0a6")
        label = "ZYSK" if v > 0 else ("STRATA" if v < 0 else "0%")
        sign = "+" if v > 0 else ""
        return (f"{sign}{v:.2f}%", color, label)

    # linia 1: +20 sesji
    pct20_txt, pct20_color, pct20_label = _fmt_pct(pct_20)
    if has_20:
        line_20 = (
            f"<b>+20 sesji:</b> "
            f"t={_fmt_date(base_date)} (cena {_fmt_price(base_price)}) "
            f"→ t+20={_fmt_date(date_20)} (cena {_fmt_price(price_20)}) "
            f"| Δ=<span style='color:{pct20_color}; font-weight:700'>{pct20_txt}</span> "
            f"(<span style='color:{pct20_color}; font-weight:700'>{pct20_label}</span>)"
        )
    else:
        line_20 = (
            f"<b>+20 sesji:</b> "
            f"t={_fmt_date(base_date)} (cena {_fmt_price(base_price)}) "
            f"→ t+20=— (brak pełnych 20 sesji w końcówce VALIDATE) "
            f"| Δ=<span style='color:{pct20_color}; font-weight:700'>{pct20_txt}</span>"
        )

    # linia 2: do końca okresu VALIDATE
    pctend_txt, pctend_color, pctend_label = _fmt_pct(pct_end)
    line_end = (
        f"<b>Do końca VALIDATE:</b> "
        f"t={_fmt_date(base_date)} (cena {_fmt_price(base_price)}) "
        f"→ koniec={_fmt_date(end_date)} (cena {_fmt_price(end_price)}) "
        f"| Δ=<span style='color:{pctend_color}; font-weight:700'>{pctend_txt}</span> "
        f"(<span style='color:{pctend_color}; font-weight:700'>{pctend_label}</span>)"
    )

    # linia 3: +60 sesji
    pct60_txt, pct60_color, pct60_label = _fmt_pct(pct_60)
    if has_60:
        line_60 = (
            f"<b>+60 sesji:</b> "
            f"t={_fmt_date(base_date)} (cena {_fmt_price(base_price)}) "
            f"→ t+60={_fmt_date(date_60)} (cena {_fmt_price(price_60)}) "
            f"| Δ=<span style='color:{pct60_color}; font-weight:700'>{pct60_txt}</span> "
            f"(<span style='color:{pct60_color}; font-weight:700'>{pct60_label}</span>)"
        )
    else:
        line_60 = (
            f"<b>+60 sesji:</b> "
            f"t={_fmt_date(base_date)} (cena {_fmt_price(base_price)}) "
            f"→ t+60=— (brak pełnych 60 sesji w końcówce VALIDATE) "
            f"| Δ=<span style='color:{pct60_color}; font-weight:700'>{pct60_txt}</span>"
        )

    # linia 4: +120 sesji
    pct120_txt, pct120_color, pct120_label = _fmt_pct(pct_120)
    if has_120:
        line_120 = (
            f"<b>+120 sesji:</b> "
            f"t={_fmt_date(base_date)} (cena {_fmt_price(base_price)}) "
            f"→ t+120={_fmt_date(date_120)} (cena {_fmt_price(price_120)}) "
            f"| Δ=<span style='color:{pct120_color}; font-weight:700'>{pct120_txt}</span> "
            f"(<span style='color:{pct120_color}; font-weight:700'>{pct120_label}</span>)"
        )
    else:
        line_120 = (
            f"<b>+120 sesji:</b> "
            f"t={_fmt_date(base_date)} (cena {_fmt_price(base_price)}) "
            f"→ t+120=— (brak pełnych 120 sesji w końcówce VALIDATE) "
            f"| Δ=<span style='color:{pct120_color}; font-weight:700'>{pct120_txt}</span>"
        )

    st.markdown(line_20, unsafe_allow_html=True)
    st.markdown(line_60, unsafe_allow_html=True)
    st.markdown(line_120, unsafe_allow_html=True)
    st.markdown(line_end, unsafe_allow_html=True)

    st.caption(
        "Uwaga: To jest wynik historyczny (ex post) liczony na danych VALIDATE. "
        "Nie jest to rekomendacja inwestycyjna ani sygnał bieżący."
    )

# ============================================================
# Helpers: ML (TEST) — wczytanie modelu + predykcja + walidacje
# ============================================================

def _resolve_artifact_path(rel_path_posix: str) -> Path:
    """
    Meta JSON zapisuje ścieżki względne względem katalogu projektu (POSIX-like).
    Tu zamieniamy je na ścieżkę absolutną w runtime.
    """
    if not rel_path_posix:
        raise ValueError("Pusta ścieżka artefaktu w meta JSON.")
    return project_root() / Path(rel_path_posix)


def _load_model_from_meta(meta: dict) -> object:
    """
    Wczytuje model (joblib) wskazany w meta.

    Strategia:
    1) najpierw próbujemy dokładnie ścieżkę z meta["model_file"],
    2) jeśli pliku nie ma, próbujemy fallback po samej nazwie pliku
       w znanych katalogach modeli.

    Po co fallback:
    - starsze meta JSON mogły zapisać nieaktualną nazwę / ścieżkę modelu,
    - sam plik .joblib może istnieć poprawnie w katalogu test/prd/prezentation,
      ale meta wskazuje zły path,
    - dzięki temu ML (TEST) potrafi jeszcze odzyskać model zamiast kończyć się
      FileNotFoundError.
    """
    rel_model = meta.get("model_file")
    if not rel_model:
        raise ValueError("Meta nie zawiera klucza 'model_file'.")

    # Próba 1: ścieżka dokładnie z meta JSON.
    fp = _resolve_artifact_path(rel_model)
    if fp.exists():
        return joblib.load(fp)

    # Próba 2: fallback po samej nazwie pliku.
    # To naprawia przypadki, gdy meta zawiera błędną ścieżkę względną,
    # ale sam plik modelu istnieje w jednym z katalogów modeli.
    model_name_only = Path(str(rel_model)).name

    fallback_dirs: list[Path] = []

    try:
        fallback_dirs.append(dir_test())
    except Exception:
        pass

    try:
        for cat in available_catalogs():
            if getattr(cat, "path", None) is not None:
                fallback_dirs.append(Path(cat.path))
    except Exception:
        pass

    # Usuwamy duplikaty katalogów, zachowując kolejność.
    dedup_dirs: list[Path] = []
    seen_dirs: set[str] = set()
    for d in fallback_dirs:
        try:
            key = str(Path(d).resolve())
        except Exception:
            key = str(d)
        if key not in seen_dirs:
            seen_dirs.add(key)
            dedup_dirs.append(Path(d))

    for d in dedup_dirs:
        candidate = Path(d) / model_name_only
        if candidate.exists():
            return joblib.load(candidate)

    # Jeśli tu trafiliśmy, to nie znaleźliśmy modelu ani po pełnej ścieżce z meta,
    # ani po samej nazwie pliku w katalogach modeli.
    raise FileNotFoundError(
        f"Plik modelu nie istnieje. "
        f"meta['model_file']={rel_model!r}, "
        f"resolved={fp}"
    )


def _predict_proba_1(model_obj: object, X: pd.DataFrame) -> np.ndarray:
    """
    Zwraca prawdopodobieństwo klasy pozytywnej.
    Obsługuje:
    - predict_proba
    - decision_function (fallback -> sigmoid)
    """
    if hasattr(model_obj, "predict_proba"):
        proba = model_obj.predict_proba(X)
        if proba is None or len(proba.shape) != 2 or proba.shape[1] < 2:
            raise ValueError("predict_proba zwróciło nieoczekiwany kształt.")
        return proba[:, 1]

    if hasattr(model_obj, "decision_function"):
        scores = model_obj.decision_function(X)
        # sigmoid jako fallback
        return 1.0 / (1.0 + np.exp(-scores))

    raise ValueError("Model nie wspiera ani predict_proba, ani decision_function.")


def _seed_quality_filters_state_from_meta(*, key_prefix: str, meta: dict) -> None:
    """
    Ustawia domyślne wartości checkboxów filtrów jakościowych na podstawie meta.

    Zasada:
    - seedujemy TYLKO jeśli dany klucz nie istnieje w session_state
      (żeby nie nadpisywać ręcznych zmian usera).
    - jeśli meta.min_conditions jest None/null:
        * interpretujemy to jako klasyczne AND (czyli wymagaj wszystkich aktywnych filtrów)
        * i seedujemy min_conditions = liczba aktywnych filtrów (jeśli > 0)
      Dzięki temu UI nie pokazuje arbitralnego "3".
    """
    qf = (meta.get("quality_filters") or {})
    min_cond = meta.get("min_conditions")

    mapping = {
        "trend": f"{key_prefix}_f_trend",
        "trend_long": f"{key_prefix}_f_trend_long",
        "momentum": f"{key_prefix}_f_momentum",
        "rsi_oversold": f"{key_prefix}_f_rsi_oversold",
        "macd_positive": f"{key_prefix}_f_macd",
        "price_above_sma200": f"{key_prefix}_f_price_sma200",
        "rsi": f"{key_prefix}_f_rsi",
        "volatility": f"{key_prefix}_f_volatility",
        "volume": f"{key_prefix}_f_volume",
        "rsi_not_overbought": f"{key_prefix}_f_rsi_not_overbought",
        "atr_high": f"{key_prefix}_f_atr",
        "price_above_vwap": f"{key_prefix}_f_vwap",
    }

    # 1) seed checkboxów
    for fk, ss_key in mapping.items():
        if ss_key not in st.session_state:
            st.session_state[ss_key] = bool(qf.get(fk, False))

    # 2) seed min_conditions
    mc_key = f"{key_prefix}_min_conditions"
    if mc_key not in st.session_state:
        active_cnt = sum(1 for v in qf.values() if bool(v))

        if min_cond is None:
            # interpretacja historyczna: brak progu => klasyczne AND (jeśli w ogóle są filtry)
            if active_cnt > 0:
                st.session_state[mc_key] = int(active_cnt)
        else:
            try:
                st.session_state[mc_key] = int(min_cond)
            except Exception:
                # jeśli meta ma śmieci, nie psujemy UI
                if active_cnt > 0:
                    st.session_state[mc_key] = int(active_cnt)


def _build_test_rank_full(
    df_test: pd.DataFrame,
    *,
    model_obj: object,
    meta: dict,
) -> pd.DataFrame:
    """
    Buduje df_test_rank_full:
    - bierze feature_cols z meta
    - liczy prob
    - dodaje y_true (binarny) na podstawie targetu z meta
    """
    if df_test is None or df_test.empty:
        return pd.DataFrame()

    feature_cols = meta.get("feature_cols") or []
    target_col = meta.get("target")

    if not feature_cols:
        raise ValueError("Meta nie zawiera 'feature_cols' — nie wiem jakie kolumny podać do modelu.")
    if not target_col:
        raise ValueError("Meta nie zawiera 'target' — nie wiem jak policzyć y_true na TEST.")

    missing_features = [c for c in feature_cols if c not in df_test.columns]
    if missing_features:
        raise ValueError(f"Brak wymaganych kolumn feature w df_test: {missing_features}")

    if target_col not in df_test.columns:
        raise ValueError(f"Brak targetu '{target_col}' w df_test.")

    dfx = df_test.copy()

    # y_true binarne (zgodnie z resztą ML-01)
    dfx["y_true"] = to_binary_target(dfx[target_col])

    X = dfx[feature_cols].copy()

    # predykcja prob
    prob = _predict_proba_1(model_obj, X)
    dfx["prob"] = pd.to_numeric(prob, errors="coerce")

    # minimalna walidacja integralności
    if dfx["prob"].isna().all():
        raise ValueError("Wszystkie wartości 'prob' wyszły NaN — model/pipeline może być niespójny z danymi TEST.")

    return dfx


def _plot_prob_hist_rank_vs_filtered(
    df_rank_selected: pd.DataFrame,
    df_filtered: pd.DataFrame,
    *,
    title: str,
) -> None:
    """
    Histogram: rozkład prob dla:
    - po selekcji rankingowej (RANK)
    - po filtrach jakościowych (PO)

    UX/wygląd:
    - rysujemy wykres w "środkowej" kolumnie, żeby nie rozlewał się na całą szerokość,
      bo w Streamlit to psuje layout (szczególnie na dużych ekranach).
    """
    import matplotlib.pyplot as plt

    if df_rank_selected is None or df_rank_selected.empty or "prob" not in df_rank_selected.columns:
        st.warning("Brak danych 'prob' do histogramu (RANK).")
        return

    # Rozsądny rozmiar w px zależy od DPI, ale ta proporcja daje czytelny wykres
    # i nie rozwala layoutu w zakładce.
    fig, ax = plt.subplots(figsize=(5.6, 2.8))

    rank_vals = pd.to_numeric(df_rank_selected["prob"], errors="coerce").dropna().values
    ax.hist(rank_vals, bins=30, alpha=0.75, label="RANK (po selekcji)", density=False)

    if df_filtered is not None and (not df_filtered.empty) and "prob" in df_filtered.columns:
        po_vals = pd.to_numeric(df_filtered["prob"], errors="coerce").dropna().values
        ax.hist(po_vals, bins=30, alpha=0.75, label="PO (po filtrach)", density=False)

    ax.set_title(title)
    ax.set_xlabel("prob")
    ax.set_ylabel("liczba obserwacji")
    ax.legend()

    col_l, col_plot, col_r = st.columns([1, 3, 1])
    with col_plot:
        st.pyplot(fig, width="content")


def _render_test_price_chart_for_selected_row(
    df_test: pd.DataFrame,
    selected_row: pd.Series,
) -> None:
    """
    Kopia logiki wykresu z VALIDATE, ale opisana jako TEST.
    Wykres cen dla wybranej firmy (ticker) na zbiorze TEST (pełny zakres dat),
    z overlay EMA50/EMA200 + marker dnia wskazanego przez selected_row,
    oraz sekcją 'Efekt ex post (TEST)' pod wykresem.

    UWAGA: To jest analiza ex post (historyczna), nie sygnał decyzyjny.
    """
    if df_test is None or not isinstance(df_test, pd.DataFrame) or df_test.empty:
        st.info("Brak danych TEST do zbudowania wykresu.")
        return

    required_cols = {"trade_date", "ticker", "close_price", "ema_50", "ema_200"}
    missing = [c for c in required_cols if c not in df_test.columns]
    if missing:
        st.info(f"Brak kolumn w df_test potrzebnych do wykresu: {missing}")
        return

    if selected_row is None or len(selected_row) == 0:
        st.info("Nie wybrano rekordu PO do analizy.")
        return

    if "Ticker" not in selected_row or "Data notowania" not in selected_row:
        st.info("Wybrany rekord nie zawiera pól 'Ticker' / 'Data notowania'.")
        return

    ticker = str(selected_row["Ticker"])
    picked_dt = pd.to_datetime(selected_row["Data notowania"], errors="coerce")
    if pd.isna(picked_dt):
        st.info("Nie udało się rozpoznać daty wybranego rekordu.")
        return

    df = df_test.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
    df = df.dropna(subset=["trade_date"])
    df = df[df["ticker"].astype(str) == ticker].sort_values("trade_date").reset_index(drop=True)

    if df.empty:
        st.info(f"Brak danych TEST dla tickera: {ticker}")
        return

    mask_exact = df["trade_date"].dt.normalize() == picked_dt.normalize()
    if mask_exact.any():
        base_idx = int(np.where(mask_exact.values)[0][0])
    else:
        prev_idx = df.index[df["trade_date"] <= picked_dt]
        base_idx = int(prev_idx.max()) if len(prev_idx) else 0

    base_date = df.loc[base_idx, "trade_date"]
    base_price = float(df.loc[base_idx, "close_price"])

    _one = pd.DataFrame([{
        "ticker": ticker,
        "trade_date": base_date,
        "close_price": base_price,
    }])
    _one = _add_expost_returns_for_po_rows(_one, df_val_prices=df, horizons=(20, 60, 120))

    pct_20 = _one.loc[0, "ret_20"]
    pct_60 = _one.loc[0, "ret_60"]
    pct_120 = _one.loc[0, "ret_120"]
    pct_end = _one.loc[0, "ret_end"]

    # --- wykres plotly (jak w wersji VALIDATE)
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["trade_date"], y=df["close_price"],
        mode="lines", name="Close",
    ))
    fig.add_trace(go.Scatter(
        x=df["trade_date"], y=df["ema_50"],
        mode="lines", name="EMA 50",
    ))
    fig.add_trace(go.Scatter(
        x=df["trade_date"], y=df["ema_200"],
        mode="lines", name="EMA 200",
    ))
    fig.add_trace(go.Scatter(
        x=[base_date], y=[base_price],
        mode="markers", name="Dzień sygnału",
        marker=dict(size=10),
    ))

    fig.update_layout(
        title=f"TEST — {ticker}: cena + EMA50/EMA200 (marker dnia sygnału)",
        xaxis_title="Data",
        yaxis_title="Cena",
        height=420,
        margin=dict(l=10, r=10, t=50, b=10),
    )
    st.plotly_chart(fig, width="stretch")

        # --------------------------------------------------------
    # Efekt ex post (TEST) — wizualnie tak samo jak VALIDATE
    # --------------------------------------------------------
    st.markdown("#### Efekt ex post (TEST)")

    def _fmt_date(d) -> str:
        try:
            return pd.to_datetime(d).strftime("%Y-%m-%d")
        except Exception:
            return str(d)

    def _fmt_price(v) -> str:
        try:
            return f"{float(v):.2f}"
        except Exception:
            return str(v)

    def _fmt_pct(v) -> tuple[str, str, str]:
        """
        Zwraca:
        - pct_txt: '+1.23%' / '-4.56%' / '—'
        - color:   kolor tekstu
        - label:   'ZYSK' / 'STRATA' / 'BRAK'
        """
        if v is None or pd.isna(v):
            return ("—", "#888888", "BRAK")
        try:
            vv = float(v)
            sign = "+" if vv > 0 else ""
            pct_txt = f"{sign}{vv:.2f}%"
            if vv > 0:
                return (pct_txt, "#2ca02c", "ZYSK")
            if vv < 0:
                return (pct_txt, "#d62728", "STRATA")
            return (pct_txt, "#888888", "0.00")
        except Exception:
            return (str(v), "#888888", "BRAK")

    # Wyliczamy daty/ceny w t+H w sposób jawny (po indeksie sesji w ramach tickera).
    # To jest spójne z interpretacją "sesje" w UI.
    def _get_future_point(offset: int) -> tuple[pd.Timestamp | None, float | None]:
        idx = base_idx + offset
        if idx < 0 or idx >= len(df):
            return (None, None)
        return (df.loc[idx, "trade_date"], float(df.loc[idx, "close_price"]))

    date_20, price_20 = _get_future_point(20)
    date_60, price_60 = _get_future_point(60)
    date_120, price_120 = _get_future_point(120)

    date_end = df.loc[len(df) - 1, "trade_date"]
    price_end = float(df.loc[len(df) - 1, "close_price"])

    pct20_txt, pct20_color, pct20_label = _fmt_pct(pct_20)
    pct60_txt, pct60_color, pct60_label = _fmt_pct(pct_60)
    pct120_txt, pct120_color, pct120_label = _fmt_pct(pct_120)
    pctend_txt, pctend_color, pctend_label = _fmt_pct(pct_end)

    if date_20 is not None:
        line_20 = (
            f"<b>+20 sesji:</b> "
            f"t={_fmt_date(base_date)} (cena {_fmt_price(base_price)}) "
            f"→ t+20={_fmt_date(date_20)} (cena {_fmt_price(price_20)}) "
            f"| Δ=<span style='color:{pct20_color}; font-weight:700'>{pct20_txt}</span> "
            f"(<span style='color:{pct20_color}; font-weight:700'>{pct20_label}</span>)"
        )
    else:
        line_20 = (
            f"<b>+20 sesji:</b> "
            f"t={_fmt_date(base_date)} (cena {_fmt_price(base_price)}) "
            f"→ t+20=— (brak pełnych 20 sesji w końcówce TEST) "
            f"| Δ=<span style='color:{pct20_color}; font-weight:700'>{pct20_txt}</span>"
        )

    if date_60 is not None:
        line_60 = (
            f"<b>+60 sesji:</b> "
            f"t={_fmt_date(base_date)} (cena {_fmt_price(base_price)}) "
            f"→ t+60={_fmt_date(date_60)} (cena {_fmt_price(price_60)}) "
            f"| Δ=<span style='color:{pct60_color}; font-weight:700'>{pct60_txt}</span> "
            f"(<span style='color:{pct60_color}; font-weight:700'>{pct60_label}</span>)"
        )
    else:
        line_60 = (
            f"<b>+60 sesji:</b> "
            f"t={_fmt_date(base_date)} (cena {_fmt_price(base_price)}) "
            f"→ t+60=— (brak pełnych 60 sesji w końcówce TEST) "
            f"| Δ=<span style='color:{pct60_color}; font-weight:700'>{pct60_txt}</span>"
        )

    if date_120 is not None:
        line_120 = (
            f"<b>+120 sesji:</b> "
            f"t={_fmt_date(base_date)} (cena {_fmt_price(base_price)}) "
            f"→ t+120={_fmt_date(date_120)} (cena {_fmt_price(price_120)}) "
            f"| Δ=<span style='color:{pct120_color}; font-weight:700'>{pct120_txt}</span> "
            f"(<span style='color:{pct120_color}; font-weight:700'>{pct120_label}</span>)"
        )
    else:
        line_120 = (
            f"<b>+120 sesji:</b> "
            f"t={_fmt_date(base_date)} (cena {_fmt_price(base_price)}) "
            f"→ t+120=— (brak pełnych 120 sesji w końcówce TEST) "
            f"| Δ=<span style='color:{pct120_color}; font-weight:700'>{pct120_txt}</span>"
        )

    line_end = (
        f"<b>Do końca TEST:</b> "
        f"t={_fmt_date(base_date)} (cena {_fmt_price(base_price)}) "
        f"→ koniec={_fmt_date(date_end)} (cena {_fmt_price(price_end)}) "
        f"| Δ=<span style='color:{pctend_color}; font-weight:700'>{pctend_txt}</span> "
        f"(<span style='color:{pctend_color}; font-weight:700'>{pctend_label}</span>)"
    )

    st.markdown(line_20, unsafe_allow_html=True)
    st.markdown(line_60, unsafe_allow_html=True)
    st.markdown(line_120, unsafe_allow_html=True)
    st.markdown(line_end, unsafe_allow_html=True)

    st.caption(
        "Uwaga: To jest wynik historyczny (ex post) liczony na danych TEST. "
        "Nie jest to rekomendacja inwestycyjna ani sygnał bieżący."
    )

# ============================================================
# RENDER: UI Streamlit
# ============================================================

def render() -> None:

    # Ekran ML-01: laboratorium ML oparte o kanoniczny time split (TRAIN/VAL/TEST).
    # W ML-01 używamy TRAIN + VALIDATION.
    # TEST pozostaje nietknięty („święty”) do przyszłych etapów ML-02 / ML-03.

    st.subheader("Machine Learning (time split: TRAIN/VAL/TEST)")
    # Opis całego modułu ML.
    # wybór sygnału -> przygotowanie danych -> trening -> walidacja -> test.
    st.info(
        "Ten ekran służy do sprawdzenia, czy wybrany sygnał rynkowy "
        "(np. **Sygnał 20 D**) można próbować przewidywać na podstawie danych historycznych.\n\n"
        "Proces pracy jest podzielony na kolejne kroki: "
        "przygotowanie danych, porównanie modeli, optymalizację sposobu wyboru sygnałów "
        "oraz końcowy test na danych, które nie były używane wcześniej w uczeniu."
    )

    # Jeśli nie ma danych bazowych (df_market_all) albo nie da się zbudować datasetów,
    # informujemy użytkownika, że najpierw musi załadować dane w ekranie „Przegląd danych”.
    try:
        df_train, df_val, df_test, meta = get_ml_datasets()
    except Exception as e:
        st.info(
            "Brak kanonicznych datasetów ML.\n\n"
            "Najpierw przejdź na **Przegląd danych** i załaduj dane (utwórz df_market_all), "
            "a następnie wróć do ML.\n\n"
            f"Szczegóły: {e}"
        )
        return

    st.markdown(" ")

    # Rozdzielamy proces na zakładki:
    # 0) Setup: definicja zagadnienia ML i przygotowanie danych (X/y)
    # 1) Compare Models: CV na TRAIN + ocena na TEST
    # 2) Ranking — kanoniczny wariant selekcji (Top-K → Top-Pct)
    # 3) ML (TEST) - testy gotowego modelu ML
    tab0, tab1, tab2, tab3 = st.tabs([
        "1. Setup danych ML (TRAIN/VALIDATION)",
        "2. Trening i walidacja modeli (TRAIN/VALIDATION)",
        "3. Optymalizacja strategii sygnałów (VALIDATION)",
        "4. Finalny test modelu (TEST)",
    ])

    # ========================================================
    # TAB 0 — SETUP (odpowiednik: setup(...))
    # ========================================================
    with tab0:
        st.markdown("### Setup danych ML (TRAIN/VALIDATION)")
        st.caption(
            "W tej zakładce wybierasz sygnał, który model ma przewidywać, "
            "ustawiasz podstawowe parametry eksperymentu i przygotowujesz dane wejściowe do dalszych testów."
        )

        st.markdown("### Tryb eksperymentu ML")
        ml01_mode = st.radio(
            "Wybierz tryb (wpływa na szybkość i dokładność porównania modeli):",
            options=["FAST", "FULL"],
            index=0,  # domyślnie FAST
            horizontal=True,
            help=(
                "FAST (domyślny): CV=3, transformation=FALSE (wymuszane), "
                "LogisticRegression max_iter=400, RandomForest n_estimators=100, "
                "GradientBoosting n_estimators=50.\n"
                "FULL: CV=5, transformation wg checkboxa, "
                "LogisticRegression max_iter=800, RandomForest n_estimators=250, "
                "GradientBoosting domyślne (n_estimators=100)."
            ),
        )
        st.markdown(
            "- **FAST** – dobry do szybkiego sprawdzenia pomysłu i porównania modeli.\n"
            "- **FULL** – lepszy do dokładniejszej oceny, ale wymaga więcej czasu na obliczenia."
        )

        # --- 0.1
        # Wybór targetu (etykiety future).
        # Lista targetów jest ZESŁOWNIKOWANA w app_params: ML01_TARGET_SIGNAL_LIST
        label_cols = get_label_columns(df_train)
        if not label_cols:
            st.warning(
                "Brak skonfigurowanych targetów dostępnych w danych TRAIN.\n\n"
                "Sprawdź: ML01_TARGET_SIGNAL_LIST oraz czy te kolumny istnieją w df_market_train."
            )
            return

        # Słownik opisów targetów (UX): "<nazwa> - <opis>"
        target_desc: Dict[str, str] = get_param("ML01_TARGET_SIGNAL_DESCRIPTIONS")

        def _format_target(col_name: str) -> str:
            # Mapowanie identyczne jak w ekranie "Przegląd danych"
            ui_name = COLUMN_LABELS.get(col_name, col_name)

            desc = target_desc.get(col_name, "(brak opisu w słowniku)")
            return f"{ui_name}  -  {desc}"

        # Heurystyka: jeśli istnieje fut_signal_20, preferujemy go jako domyślny target.
        if "fut_signal_20" in label_cols:
            default_target = "fut_signal_20"
        elif "fut_signal_20_hyb" in label_cols:
            default_target = "fut_signal_20_hyb"
        else:
            default_target = label_cols[0]

        target = st.selectbox(
            "Etykieta, którą model ma przewidywać (Target (y))",
            options=label_cols,
            index=label_cols.index(default_target),
            format_func=_format_target,
        )

        # --- 0.2
        # Parametry eksperymentu ML (w stylu PyCaret), mapowane potem na pipeline sklearn.
        # Dajemy w UI parametry 1:1, tylko pod spodem realizujemy je w sklearn.
        colA, colB = st.columns(2)

        with colA:
            session_id = st.number_input("ID sesji session_id (random_state) - ustala ziarno losowości", min_value=0, value=123, step=1)

        with colB:
            fix_imbalance = st.checkbox("fix_imbalance (pomaga przy rzadkiej klasie pozytywnej (+1))", value=True)

        colD, colE = st.columns(2)
        with colD:
            normalize = st.checkbox("normalize (skaluje cechy (StandardScaler), żeby miały porównywalną skalę)", value=True)
        with colE:
            transformation = st.checkbox("transformation (transformation zmienia rozkład cech (PowerTransformer / Yeo-Johnson))", value=True)

        # FAST: wymuszamy transformation=False (checkbox zostaje, ale nie działa w FAST)
        if ml01_mode == "FAST":
            transformation = False
            st.info("Tryb FAST: transformation jest wymuszone na FALSE (dla szybkości).")


        # --- 0.3 
        # Ignore features (lista ignorowanych kolumn)
        st.markdown("#### Kolumny wykluczane")
        st.caption(
            "Poniższa lista odpowiada dokładnie temu, co podałeś. "
            "To są metadane / identyfikatory / artefakty joinów — nie powinny trafiać do ML."
        )

        # Wybór kolumn do wykluczenia z cech (X).
        # To głównie identyfikatory, daty, pola techniczne i same targety future (żeby nie było leakage).
        ignore_features = st.multiselect(
            "Kolumny do wykluczenia z X (features)",
            options=sorted(df_train.columns.tolist()),
            default=[c for c in DEFAULT_IGNORE_FEATURES if c in df_train.columns],
        )

        # --- 0.4
        # Budujemy konfigurację setup, która steruje: targetem, preprocessingiem i obsługą imbalance.
        cfg = SetupConfig(
            target=target,
            session_id=int(session_id),
            ignore_features=ignore_features,
            fix_imbalance=fix_imbalance,
            normalize=normalize,
            transformation=transformation,
            ml01_mode=ml01_mode,
        )

        # --- 0.5 
        # Uruchomienie setup (w sensie: przygotuj dane)
        # Wykonujemy setup: wyznaczamy cechy na TRAIN i budujemy X/y osobno dla TRAIN oraz TEST.
        # (Brak losowego splitu — podział jest czasowy i ustalony w ml_datasets.py)
        prepared = setup_prepare_data(df_train=df_train, df_val=df_val, cfg=cfg)


        # --- 
        # 0.6 
        # Szybki sanity-check: liczności train/val/test oraz baseline częstości klasy +1.
        st.markdown("#### Podsumowanie setup")
        c1, c2, c3, c4, c5 = st.columns(5)
        
        # Baseline = częstość klasy pozytywnej w całym df
        c1.metric("N (train) - liczba wierszy w zbiorze treningowym (train)", f"{len(df_train):,}")
        c2.metric("N (val) - liczba wierszy w zbiorze walidacyjnym (validation)", f"{len(df_val):,}")
        c3.metric("N (test) - liczba wierszy w zbiorze testowym (test)", f"{len(df_test):,}")  # pozostaje informacyjnie, ale NIEUŻYWANY
        c4.metric("X_train rows (liczba wierszy po przygotowaniu danych)", f"{len(prepared.X_train):,}")
        c5.metric("Baseline (+1) [train+val] (częstość klasy pozytywnej (y=1)", f"{prepared.baseline_pos_rate*100:.4f}%")

        # (opcjonalnie) pokaż warningi ze splitu
        # Ostrzeżenia, jeśli zakresy dat nachodzą na siebie albo split jest niespójny.
        if meta.get("warnings"):
            st.warning(" / ".join(meta["warnings"]))

        st.markdown("#### Cechy (X) po wykluczeniach")
        st.caption(
            "Poniżej znajduje się lista cech, które po wykluczeniach i podstawowym sprawdzeniu jakości danych "
            "zostaną użyte w dalszych etapach modelowania."
        )

        # Lista końcowych cech używanych przez model.
        st.code(prepared.feature_cols)

        st.info(
            "Przygotowanie danych zostało zakończone. "
            "Przejdź do zakładki **Trening i walidacja modeli (TRAIN/VALIDATION)**, "
            "aby porównać modele na tych samych danych."
        )


        # Cache wyników setup w session_state:
        # dzięki temu tab „Compare Models” nie musi ponownie liczyć przygotowania danych.
        st.session_state["ml01_cfg"] = cfg
        st.session_state["ml01_prepared"] = prepared


    # ========================================================
    # TAB 1 — COMPARE MODELS (odpowiednik: compare_models())
    # ========================================================
    # Ewaluacja wybranego modelu na VALIDATION + wyliczenie prob (predict_proba)
    with tab1:
        st.markdown("### Trening i walidacja modeli (TRAIN/VALIDATION)")
        st.caption(
            "W tej zakładce porównujesz kilka modeli na danych treningowych, "
            "a następnie sprawdzasz, jak wybrany model zachowuje się na późniejszym zbiorze walidacyjnym. "
            "Zbiór TEST nie jest tu jeszcze używany."
        )

        st.info(
            "Jak czytać tę zakładkę:\n"
            "- **Tabela u góry** pokazuje wstępne porównanie modeli na danych treningowych.\n"
            "- **Po wyborze modelu** aplikacja trenuje go na pełnym zbiorze TRAIN.\n"
            "- **Wyniki na VALIDATION** pokazują, czy model radzi sobie na danych z późniejszego okresu.\n"
            "- **Kolejna zakładka** wykorzystuje prawdopodobieństwa modelu do budowy rankingu sygnałów."
        )

        # Pobieramy wynik setup z session_state. Jeśli setup nie był wykonany, blokujemy dalsze kroki.
        cfg: Optional[SetupConfig] = st.session_state.get("ml01_cfg")
        prepared: Optional[PreparedData] = st.session_state.get("ml01_prepared")

        show_active_context_badge(cfg)

        if cfg is None or prepared is None:
            st.info("Najpierw wykonaj **Setup** w zakładce 0.")
            return

        # Porównanie modeli: cross-validation na TRAIN (bez podglądania TEST).
        # Wyniki służą do wyboru najlepszego modelu do dalszej oceny.
        status_box = st.empty()
        status_box.warning("Trwa przeliczanie modeli (cross-validation na TRAIN). Może potrwać kilka minut...")

        results = compare_models_sklearn_cached(prepared.X_train, prepared.y_train, cfg) # uruchomienie CV (cache)

        status_box.empty()


        st.markdown("#### Wyniki cross-validation na TRAIN")
        results_view = results.rename(columns={
            "model": "Model",
            "cv_accuracy": "Accuracy (CV)",
            "cv_f1": "F1 (CV)",
            "cv_roc_auc": "ROC AUC (CV)",
        })
        st.dataframe(results_view, hide_index=True)
        st.caption(
            "To są metryki **z cross-validation na TRAIN** (średnia po foldach). "
            "Służą do wstępnego porównania modeli na tych samych danych i preprocessingu."
        )

        with st.expander("Jak interpretować metryki porównania modeli", expanded=False):
            st.markdown(
                "- **Accuracy** pokazuje ogólny odsetek poprawnych wskazań modelu, "
                "ale przy rzadkich sygnałach może być myląca.\n"
                "- **F1** lepiej uwzględnia równowagę między trafieniami i fałszywymi alarmami.\n"
                "- **ROC AUC** pokazuje, jak dobrze model odróżnia przypadki z sygnałem od pozostałych.\n\n"
                "**Jak wybierać model?**\n"
                "- jako punkt startowy patrz na wyniki z tabeli porównawczej,\n"
                "- później sprawdź, jak wybrany model działa na zbiorze VALIDATION,\n"
                "- ostatecznie najlepszy model powinien dobrze radzić sobie nie tylko w porównaniu CV, "
                "ale także na danych z późniejszego okresu."
            )

        # Wybór najlepszego modelu (domyślnie pierwszy po sortowaniu)
        best_default = results.iloc[0]["model"] if not results.empty else None
        best_model_name = st.selectbox(
            "Wybierz model (trening: TRAIN, ocena: VALIDATION)",
            options=results["model"].tolist() if not results.empty else [],
            index=0 if best_default else 0,
        )
        st.caption(
            "Wybrany model zostanie teraz wytrenowany na pełnym TRAIN, a następnie oceniony na VALIDATION. "
            "Ta ocena jest bardziej „życiowa”, bo VALIDATION to dane z późniejszego okresu (time-split)."
        )

        if not best_model_name:
            st.warning("Brak modeli do porównania (sprawdź dane).")
            return

        # Trenujemy wybrany model na pełnym TRAIN i wykonujemy ocenę na VALIDATION.
        pipe = fit_best_model_cached(prepared.X_train, prepared.y_train, cfg, best_model_name)


        # ==========================================================
        # BADANIE MODELI ML (ETAP 2 / ocena): TRAIN -> VALIDATION
        # Diagnostyka na VALIDATION (time-split) + interpretacja wyników
        # ==========================================================
        # VALIDATION jest „przyszłością” względem TRAIN, więc to tutaj najczęściej widać:
        # - czy model realnie działa poza treningiem,
        # - czy generuje zbyt dużo fałszywych alarmów (false positive),
        # - czy nadaje się do rankingu Top-K/Top-%.
        y_true = prepared.y_test

        # Prawdopodobieństwo klasy 1 (do rankingu) — jeśli brak, ranking będzie ograniczony
        if hasattr(pipe, "predict_proba") and y_true.nunique() == 2:
            y_prob = pipe.predict_proba(prepared.X_test)[:, 1]
        else:
            st.warning("Model nie wspiera predict_proba() – selekcja rankingowa (Top-K/Top-Pct) będzie niedostępna.")
            y_prob = np.full(shape=len(prepared.X_test), fill_value=np.nan)

        # Predykcja klas (domyślny próg modelu; nie musi być optymalny dla tradingu)
        y_pred = pipe.predict(prepared.X_test)

        # --- metryki na VALIDATION ---
        acc = accuracy_score(y_true, y_pred)
        prec = precision_score(y_true, y_pred, zero_division=0)
        rec = recall_score(y_true, y_pred, zero_division=0)
        f1 = f1_score(y_true, y_pred, zero_division=0)

        roc = np.nan
        if np.isfinite(y_prob).any() and y_true.nunique() == 2:
            try:
                roc = roc_auc_score(y_true, y_prob)
            except Exception:
                roc = np.nan

        st.markdown("#### Ewaluacja na VALIDATION (diagnostyka — jak model zachowuje się na „przyszłości”)")
        st.caption(
            "Ta sekcja pokazuje jakość wybranego modelu na VALIDATION. "
            "W tradingu zwykle ważne są: (a) czy `prob` dobrze porządkuje przypadki (ROC AUC), "
            "(b) czy alarmy nie są „za tanie” (Precision), "
            "a nie sama accuracy."
        )

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Accuracy", f"{acc:.3f}")
        c2.metric("Precision", f"{prec:.3f}")
        c3.metric("Recall", f"{rec:.3f}")
        c4.metric("F1", f"{f1:.3f}")
        c5.metric("ROC AUC", "-" if not np.isfinite(roc) else f"{roc:.3f}")

        # Macierz pomyłek = ile jest FP/FN/TP/TN (bardzo ważne przy rzadkiej klasie +1)
        try:
            cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
            cm_df = pd.DataFrame(cm, index=["y=0 (brak sygnału)", "y=1 (sygnał)"], columns=["pred=0", "pred=1"])
            st.dataframe(cm_df, width="stretch")
        except Exception:
            pass

        with st.expander("Jak interpretować Precision/Recall i macierz pomyłek?", expanded=False):
            st.markdown(
                "- **Precision**: z wszystkich predykcji `pred=1` ile faktycznie było `y=1`. "
                "Niska precision = dużo fałszywych alarmów (FP).\n"
                "- **Recall**: z wszystkich prawdziwych `y=1` ile model wykrył jako `pred=1`. "
                "Wysoki recall przy niskiej precision często oznacza „łapiemy dużo, ale z dużym szumem”.\n"
                "- **Macierz pomyłek**:\n"
                "  - **FP** (y=0, pred=1): fałszywy alarm\n"
                "  - **FN** (y=1, pred=0): pominięty sygnał\n"
                "W kolejnych zakładkach próbujemy podejściem rankingowym (Top-K/Top-%) znaleźć kompromis, "
                "który podnosi precision kosztem mniejszej liczby transakcji."
            )

        # --- automatyczne wnioski (czytelne dla osoby nietechnicznej) ---
        pos_rate = float(np.mean(y_true.values)) if len(y_true) else 0.0
        pred_pos_rate = float(np.mean((y_pred == 1))) if len(y_true) else 0.0

        conclusions = []
        conclusions.append(f"- Częstość klasy pozytywnej w VALIDATION (y=1): **{pos_rate*100:.3f}%**.")
        conclusions.append(f"- Odsetek predykcji pozytywnych modelu (pred=1): **{pred_pos_rate*100:.3f}%**.")

        if prec < 0.05 and rec > 0.2:
            conclusions.append("- Wzorzec: **niska Precision + wyższy Recall** → model generuje dużo fałszywych alarmów. "
                               "W praktyce tradingowej może to oznaczać wiele słabych wejść. "
                               "Rozwiązaniem bywa selekcja rankingowa Top-K/Top-% lub zmiana progu decyzyjnego.")
        if acc > 0.8 and pos_rate < 0.05:
            conclusions.append("- **Wysoka Accuracy przy rzadkiej klasie** nie musi oznaczać dobrego modelu "
                               "(łatwo mieć wysoką accuracy przewidując prawie zawsze 0).")
        if np.isfinite(roc):
            if roc >= 0.7:
                conclusions.append("- **ROC AUC jest sensowne** → `prob` ma potencjał do rankingu (kolejne zakładki Top-K/Top-%).")
            elif roc <= 0.55:
                conclusions.append("- **ROC AUC blisko 0.5** → model słabo rozdziela klasy; ranking może niewiele poprawić.")
        else:
            conclusions.append("- Brak ROC AUC (np. brak `predict_proba` albo jedna klasa) → ranking probabilistyczny będzie ograniczony.")

        st.markdown("#### Wnioski (automatyczna interpretacja)")
        # Dobór „koloru” komunikatu: prosty heurystyczny
        if prec < 0.05 and pred_pos_rate > pos_rate * 3:
            st.warning("\n".join(conclusions))
        else:
            st.info("\n".join(conclusions))

        # Budujemy tabelę rankingową dla VALIDATION na bazie df_val (metadane) + y_true + prob
        df_val_rank = df_val.copy()
        df_val_rank["y_true"] = y_true.values
        df_val_rank["prob"] = y_prob



        # cache do kolejnych zakładek (żeby nie liczyć ponownie)
        st.session_state["ml01_best_model_name"] = best_model_name
        st.session_state["ml01_fitted_pipe"] = pipe
        st.session_state["ml01_df_val_rank_full"] = df_val_rank


    # ========================================================
    # TAB 2 — Optymalizacja strategii sygnałów (VALIDATION)
    # ========================================================
    with tab2:
        st.markdown("### Optymalizacja strategii sygnałów (VALIDATION)")
        st.caption(
            "Krok 1: na górze liczona jest tabela 27 kombinacji parametrów (grid) na całym zbiorze VALIDATION.\n"
            "Krok 2: wybierasz jedną kombinację.\n"
            "Krok 3: dla tej kombinacji pokazujemy mały zbiór sygnałów **PRZED**.\n"
            "Krok 4: filtry jakościowe uruchamiasz ręcznie przyciskiem i oglądasz wynik **PO** (szybko, bo na małym zbiorze).\n"
        )

        cfg: Optional[SetupConfig] = st.session_state.get("ml01_cfg")
        show_active_context_badge(cfg)

        df_val_rank_full = st.session_state.get("ml01_df_val_rank_full")
        if df_val_rank_full is None:
            st.info("Najpierw przejdź do zakładki **1. Compare Models** i wytrenuj model (żeby powstał ranking TEST).")
            return
        if not isinstance(df_val_rank_full, pd.DataFrame) or df_val_rank_full.empty:
            st.info("Ranking TEST jest pusty — wróć do zakładki **1. Compare Models**.")
            return

        # ========================================================
        # (A) GRID 27 kombinacji — liczymy zawsze (jak wcześniej)
        # ========================================================
        st.markdown("#### Tabela 27 kombinacji — PRZED wyborem konfiguracji (przed filtrami)")
        st.caption(
            "To jest ranking konfiguracji selekcji (Top-K → Top-Pct) na całym zbiorze VALIDATION. \n"
            "Wybierz jedną konfigurację poniżej — na niej zostanie zbudowany zbiór 'PRZED' wyborem filtrów."
        )

        windows = list(get_param("ML01_WINDOW_SESSIONS_GRID"))
        max_signals_list = list(get_param("ML01_MAX_SIGNALS_GRID"))
        top_pct_list = list(get_param("ML01_TOP_SCORE_PCT_GRID"))

        # Uwaga: to może trwać (27 przebiegów po całym rankingu VALIDATION).
        # To jest świadome i zgodne z wcześniejszym zachowaniem tej zakładki.
        # ========================================================
        # Cache gridu: żeby kliknięcia checkboxów filtrów nie przeliczały 27 kombinacji
        # ========================================================
        grid_key = (
            st.session_state.get("ml01_best_model_name"),
            cfg.target if cfg is not None else None,
            len(df_val_rank_full),
        )

        cached_key = st.session_state.get("tab2_grid_cache_key")
        cached_res = st.session_state.get("tab2_grid_cache")

        if cached_res is None or cached_key != grid_key:
            status_box = st.empty()
            status_box.warning("Trwa przeliczanie tabeli (27 kombinacji na VALIDATION). Może potrwać kilka minut...")

            res = run_grid_experiment(
                df_rank=df_val_rank_full,
                df_val_prices=df_val_rank_full,  # źródło cen do ex-post zysków (VALIDATION)
                selector_fn=select_signals_topk_then_toppct,
                windows=windows,
                max_signals_list=max_signals_list,
                top_pct_list=top_pct_list,
            )

            status_box.empty()

            st.session_state["tab2_grid_cache"] = res
            st.session_state["tab2_grid_cache_key"] = grid_key
        else:
            res = cached_res

        if st.button("Odśwież grid (27 kombinacji)", help="Wymusza ponowne przeliczenie tabeli grid."):
            st.session_state.pop("tab2_grid_cache", None)
            st.session_state.pop("tab2_grid_cache_key", None)
            st.experimental_rerun()

        # Wyświetlenie tabeli grid
        # Tworzymy stabilne LP liczone od 1.
        # LP jest identyfikatorem biznesowym wiersza w obrębie aktualnego gridu:
        # - pokazujemy je jako pierwszą kolumnę tabeli,
        # - używamy tego samego LP w selectboxie poniżej,
        # - dzięki temu numer w selectboxie zgadza się z numerem w tabeli
        #   nawet wtedy, gdy użytkownik posortuje tabelę po innej kolumnie.
        res_with_lp = res.reset_index(drop=True).copy()
        res_with_lp.insert(0, "lp", np.arange(1, len(res_with_lp) + 1))

        # Budujemy widok UI, ale bez zamiany kolumn numerycznych na stringi.
        # Dzięki temu sortowanie po nagłówkach będzie działało poprawnie.
        res_view = _grid_27_ui(res_with_lp)

        # AgGrid zapewnia poprawne sortowanie po całym zbiorze rekordów,
        # a nie tylko w obrębie aktualnie widocznego fragmentu tabeli.
        _render_grid_27_aggrid(
            res_view,
            table_key="tab2_grid_27_table",
            height=900,
        )


        with st.expander("Opis tabeli - algorytm", expanded=False):
            st.markdown(
                """
**Co pokazuje tabela?**  
To ranking 27 konfiguracji selekcji sygnałów na zbiorze **VALIDATION**.

**Jak działa selekcja (Top-K → Top-%):**
1. Dzielimy oś czasu VALIDATION na kolejne **okna sesji** o rozmiarze `window_sessions` (np. 50 sesji). Każdy rekord (ticker, trade_date) trafia do jednego `window_id`.
2. W każdym oknie bierzemy **wszystkie rekordy** z tego okna i sortujemy malejąco po `prob` (prawdopodobieństwo `y=1` wg modelu).
3. Liczymy limit liczbowy Top-% w oknie:  
   `pct_limit = floor(N_okna * top_score_pct)`, gdzie `N_okna` to liczba rekordów w oknie (nie liczba sesji).
4. W oknie wybieramy tylko rekordy o **najwyższym `prob`** (największej szansie na „dobry sygnał” wg modelu):  
   `final_k = min(Top-K, pct_limit)`, a następnie bierzemy `head(final_k)` z listy posortowanej malejąco po `prob`.  
   To oznacza, że **sygnał = rekord (ticker, trade_date)**, który model uznał za najbardziej prawdopodobny do klasy pozytywnej (`y=1`) w danym oknie.  
   „Dobry sygnał” w tym module oznacza sygnał, który **po fakcie** okazuje się trafny, tj. ma `y_true=1` w VALIDATION (dlatego później liczymy TP/FP).
5. **N wybranych** (`n_selected`) to łączna liczba takich „najbardziej obiecujących” rekordów z całego VALIDATION:  
   sumujemy wybory ze wszystkich okien: `n_selected = Σ final_k`.  
   Następnie oceniamy jakość wyboru:  
   - **TP** = ile wybranych rekordów było „dobrym sygnałem” (`y_true=1`),  
   - **FP** = ile wybranych rekordów okazało się błędnych (`y_true=0`).  
   Im wyższe `prob` (względem innych rekordów w oknie), tym większa **oczekiwana** szansa, że rekord będzie miał `y_true=1` — ale to jest hipoteza modelu, która dopiero jest weryfikowana metrykami.
6. Dla tak wybranych sygnałów liczymy:
   - **TP**: liczba wybranych rekordów z `y_true=1`,
   - **FP**: liczba wybranych rekordów z `y_true=0`,
   - (stąd m.in. **Precyzja** = TP/(TP+FP)).

**Uwaga:** Top-% jest **ułamkiem 0–1** (np. 0.001 = 0.1%). Przy małych oknach i bardzo małym Top-% może wyjść `pct_limit=0`, co daje 0 sygnałów.
                """
            )

            st.markdown("#### Legenda (parametry z kodu → znaczenie)")
            legend = pd.DataFrame([
                {"param": "Rozmiar okna sesji", "znaczenie": "Okno rankingowe wyszukiwania najlepszych sygnałów (liczba sesji jednego okna rankingowego)."},
                {"param": "Top-K", "znaczenie": "Maks. liczba sygnałów wybieranych w jednym oknie (limit K; dodatkowo ograniczane przez Top-%)."},
                {"param": "Top-% (ułamek)", "znaczenie": "Ograniczenie procentowe (ułamek) liczby wybieranych sygnałów w oknie (Top-Pct), np. 0.001 = 0.1%, 1.0 = 100%."},
                {"param": "N wybranych", "znaczenie": "Łączna liczba sygnałów finalnie wybranych ze wszystkich okien (w całym zbiorze VALIDATION) – może być 0."},
                {"param": "TP", "znaczenie": "Liczba wybranych sygnałów, które są prawdziwie pozytywne (y_true = 1) w VALIDATION."},
                {"param": "FP", "znaczenie": "Liczba wybranych sygnałów, które są fałszywie pozytywne (y_true = 0) w VALIDATION."},
                {"param": "Precyzja", "znaczenie": "Precyzja: TP / (TP+FP) w sygnałach wybranych przez selekcję (KPI główne)."},
                {"param": "Wykrywalność", "znaczenie": "Czułość/Recall względem całego VALIDATION: TP / (TP+FN)."},
                {"param": "Śr prawdop.", "znaczenie": "Średni score (prawdopodobieństwo) w sygnałach wybranych przez selekcję."},
                {"param": "Min prawdop.", "znaczenie": "Minimalny score (prawdopodobieństwo) w sygnałach wybranych przez selekcję."},
                {"param": "Max prawdop.", "znaczenie": "Maksymalny score (prawdopodobieństwo) w sygnałach wybranych przez selekcję."},
                {"param": "+1 VAL", "znaczenie": "Liczba wszystkich pozytywnych przypadków (+1) w całym VALIDATION."},
                {"param": "Zysk 20 (%)", "znaczenie": "Średni zysk (%) po 20 sesjach dla sygnałów z tej konfiguracji."},
                {"param": "Zysk 60 (%)", "znaczenie": "Średni zysk (%) po 60 sesjach dla sygnałów z tej konfiguracji."},
                {"param": "Zysk 120 (%)", "znaczenie": "Średni zysk (%) po 120 sesjach dla sygnałów z tej konfiguracji."},
                {"param": "Zysk do końca (%)", "znaczenie": "Średni zysk (%) do końca okresu VALIDATION dla sygnałów z tej konfiguracji."},
            ])
            st.table(legend)

        st.divider()

        st.markdown("#### Wybierz konfigurację z tabeli")
        st.caption(
            "Poniższy wybór ustawia parametry selekcji. Następnie zobaczysz mały zbiór sygnałów PRZED, "
            "na którym możesz testować filtry jakościowe."
        )

        # Domyślnie wybieramy pierwszy wiersz, który realnie coś wybrał.
        # Uwaga: pracujemy już na res_with_lp, a nie na surowym res.
        default_idx = 0
        if "n_selected" in res_with_lp.columns:
            nonzero = res_with_lp.index[res_with_lp["n_selected"] > 0].tolist()
            if nonzero:
                default_idx = nonzero[0]

        # Lista opcji opiera się na stabilnym LP, a nie na indeksie 0..N-1.
        # Dzięki temu numer w selectboxie jest zgodny z kolumną LP w tabeli.
        option_lps = res_with_lp["lp"].tolist()

        # Domyślnie selectbox ma wskazać LP odpowiadające default_idx.
        default_lp = int(res_with_lp.iloc[default_idx]["lp"])

        def _format_grid_pick_option(lp_value: int) -> str:
            """
            Buduje opis opcji w selectboxie na podstawie stabilnego LP.
            Zyski formatujemy tak samo jak w tabeli gridu: 2 miejsca + znak %.
            """
            row = res_with_lp.loc[res_with_lp["lp"] == lp_value].iloc[0]

            return (
                f"[{int(row['lp'])}] "
                f"win={int(row['window_sessions'])} | "
                f"K={int(row['max_signals'])} | "
                f"pct={row['top_score_pct']} | "
                f"prec={float(row['precision']):.4f} | "
                f"n={int(row['n_selected'])} | "
                f"TP={int(row['tp'])} | "
                f"FP={int(row['fp'])} | "
                f"z20={_fmt_pct_2(row.get('avg_ret_20', np.nan))} | "
                f"z60={_fmt_pct_2(row.get('avg_ret_60', np.nan))} | "
                f"z120={_fmt_pct_2(row.get('avg_ret_120', np.nan))} | "
                f"zend={_fmt_pct_2(row.get('avg_ret_end', np.nan))}"
            )

        chosen_lp = st.selectbox(
            "Konfiguracja",
            options=option_lps,
            index=option_lps.index(default_lp),
            format_func=_format_grid_pick_option,
            key="tab2_grid_pick",
        )

        # Pobieramy rekord po LP, a nie po pozycji indeksu.
        chosen_row = res_with_lp.loc[res_with_lp["lp"] == int(chosen_lp)].iloc[0]
        window_sessions = int(chosen_row["window_sessions"])
        max_signals = int(chosen_row["max_signals"])
        top_score_pct = float(chosen_row["top_score_pct"])

        st.info(
            f"Aktywna konfiguracja PRZED: window_sessions={window_sessions}, max_signals={max_signals}, top_score_pct={top_score_pct}"
        )

        # ========================================================
        # (B) PRZED — mały zbiór sygnałów dla wybranej konfiguracji
        # ========================================================
        st.markdown("#### Podgląd sygnałów (PRZED filtrem) dla wybranej konfiguracji")
        st.caption(
            "To jest mały zbiór wynikowy dla wybranej konfiguracji z tabeli. "
            "Ta tabela jest zawsze liczona **bez filtrów jakościowych** i stanowi punkt odniesienia (PRZED)."
        )

        # Reset PO tylko gdy zmienia się źródło PRZED (czyli wybrana konfiguracja).
        # Czyścimy zarówno sam wynik PO, jak i jego sygnaturę,
        # żeby FINALIZE nie użył przypadkiem starego wyniku z innej konfiguracji.
        current_signature = (window_sessions, max_signals, top_score_pct)
        prev_signature = st.session_state.get("tab2_sel_signature")
        if prev_signature != current_signature:
            st.session_state.pop("tab2_df_sel_filtered", None)
            st.session_state.pop("tab2_filtered_signature", None)

        st.session_state["tab2_sel_signature"] = current_signature

        df_sel_base = select_signals_topk_then_toppct(
            df_val_rank_full,
            date_col="trade_date",
            score_col="prob",
            window_sessions=window_sessions,
            max_signals=max_signals,
            top_score_pct=top_score_pct,
        )

        if df_sel_base is None or df_sel_base.empty:
            st.warning(
                "Selekcja zwróciła 0 rekordów (PRZED) dla tej konfiguracji. "
                "Wybierz inną konfigurację z gridu (np. większy top_score_pct)."
            )
        else:
            df_view_before = _build_table_view_base(df_sel_base, df_val_prices=df_val_rank_full)

            avg_override = {
                "Zysk 20 sesji": chosen_row.get("avg_ret_20", np.nan),
                "Zysk 60 sesji": chosen_row.get("avg_ret_60", np.nan),
                "Zysk 120 sesji": chosen_row.get("avg_ret_120", np.nan),
                "Zysk do końca VALIDATE": chosen_row.get("avg_ret_end", np.nan),
                # średnie prawdopodobieństwo już jest w gridzie jako avg_score
                "Prawdopodobieństwo": chosen_row.get("avg_score", np.nan),
            }

            _render_aggrid_table(
                df_view_before,
                table_key="tab2_table_before",
                height=420,
                page_size=10,
                avg_row_override=avg_override,
            )


            st.markdown("#### Analiza rozkładu (PRZED filtrowaniem)")
            _plot_pre_filter_analytics(df_sel_base)



        st.divider()

        # ========================================================
        # (C) Filtry jakościowe — liczymy dopiero po kliknięciu (PO)
        # ========================================================
        st.markdown("#### Diagnostyka filtrów: PRZED vs PO (PRZED wybranymi filtrami i PO wybraniu filtrów)")
        st.caption(
            "Filtry poniżej działają **wyłącznie** na tabeli PRZED z tej zakładki. "
            "Po kliknięciu **Przefiltruj** zobaczysz dodatkową tabelę PO oraz histogram PRZED vs PO. "
            "Możesz testować różne kombinacje — za każdym razem punktem startu jest PRZED."
        )

        filters, min_conditions = _render_quality_filter_controls(key_prefix="tab2")

        btn = st.button(
            "Przefiltruj",
            key="tab2_apply_filters_btn",
            type="primary",
            disabled=(df_sel_base is None or df_sel_base.empty),
        )

        if btn and df_sel_base is not None and (not df_sel_base.empty):
            with st.spinner("Filtrowanie małego zbioru (PO)…"):
                df_sel_filtered = _apply_quality_filters_on_df(
                    df_sel_base,
                    filters=filters,
                    min_conditions=min_conditions,
                )

            # Zapisujemy faktycznie policzony wynik PO.
            st.session_state["tab2_df_sel_filtered"] = df_sel_filtered

            # Zapisujemy także sygnaturę tego konkretnego wyniku,
            # aby FINALIZE mógł sprawdzić, czy PO odpowiada aktualnemu stanowi Tab2.
            st.session_state["tab2_filtered_signature"] = _build_tab2_filter_runtime_signature(
                selection_signature=st.session_state.get("tab2_sel_signature"),
                filters=filters,
                min_conditions=min_conditions,
                df_sel_base=df_sel_base,
            )

        df_sel_filtered = st.session_state.get("tab2_df_sel_filtered")

        if df_sel_base is not None and (not df_sel_base.empty):
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Liczba obserwacji (PRZED)", f"{len(df_sel_base):,}".replace(",", " "))
            with col2:
                st.metric("Liczba obserwacji (PO)", f"{len(df_sel_filtered):,}".replace(",", " ") if df_sel_filtered is not None else "—")

        if df_sel_filtered is not None:
            st.success("Poniżej widzisz wynik PO filtrze (histogram + tabela).")

            # Histogram
            _plot_prob_hist_before_after(
                df_sel_base,
                df_sel_filtered,
                title="Rozkład prob: PRZED vs PO (Tab2)"
            )

            # Dodatkowa diagnostyka: TP vs FP oraz TN vs FN (PRZED vs PO)
            # Definicja bez threshold:
            # - SELECTED = df_sel_base / df_sel_filtered
            # - NOT SELECTED = df_val_rank_full \ SELECTED
            _plot_prob_hist_tp_fp_tn_fn(
                df_sel_before=df_sel_base,
                df_sel_after=df_sel_filtered,
                df_all_before=df_val_rank_full,
                df_all_after=df_val_rank_full,  # UWAGA: df_all nie zmienia się po filtrach — zmienia się tylko SELECTED
                title_tp_fp="TP vs FP: rozkład prob (SELECTED) — PRZED vs PO (Tab2)",
                title_tn_fn="TN vs FN: rozkład prob (NOT SELECTED) — PRZED vs PO (Tab2)",
            )

            # Opis wykresu
            st.markdown(
                """
        **Jak czytać wykres:**
        - **Niebieski** = rozkład `prob` dla sygnałów **PRZED** filtrem.
        - **Pomarańczowy** = rozkład `prob` dla sygnałów **PO** filtrze.

        **Oś X** = score modelu (`prob`) — im bliżej 1.0, tym wyższa ocena modelu.  
        **Oś Y** = liczba sygnałów w danym przedziale score.

        **Interpretacja praktyczna:**
        Jeśli rozkład PO przesuwa się w prawo (więcej sygnałów z wysokim `prob`)
        przy umiarkowanym spadku liczby obserwacji — filtr poprawia jakość selekcji.
        """
            )
            st.caption(
                "Dodatkowe wykresy poniżej pokazują rozkłady `prob` rozbite na grupy błędów:\n"
                "- TP vs FP w zbiorze wybranych sygnałów (SELECTED)\n"
                "- TN vs FN w zbiorze niewybranych (NOT SELECTED)\n"
                "To pozwala ocenić, czy filtry wycinają głównie FP bez utraty TP."
            )


            st.markdown("#### Wynik PO (po filtrze)")

            df_view_after = _build_table_view_after(df_sel_filtered, filters=filters, df_val_prices=df_val)
            grid_resp = _render_aggrid_table(
                df_view_after,
                table_key="tab2_table_after",
                height=420,
                page_size=10,
            )


            st.caption(
                "Tabela przedstawia listę sygnałów wykrytych przez ML treningowy. "                
                "Jak czytać kolumny zysków: gdyby kupić akcje w dniu z kolumny **Data notowania** "                
                "i sprzedać je po liczbie sesji wskazanej w nazwie kolumny (np. **Zysk 20 sesji**, **Zysk 60 sesji**, **Zysk 120 sesji**), "
                "to historyczna stopa zwrotu wyniosłaby tyle, ile widzisz w danym wierszu. "
                "Kolumna **Zysk do końca VALIDATE** pokazuje wynik trzymania pozycji do końca dostępnego okresu walidacyjnego. "
                "Możesz sortować tabelę po tych kolumnach rosnąco/malejąco, aby szybko znaleźć najlepsze i najsłabsze przypadki."
            )

            st.markdown("#### Wybór rekordu PO do analizy")

            if df_view_after is not None and not df_view_after.empty:

                # upewniamy się że sortowanie identyczne jak tabela
                df_pick = df_view_after.copy().reset_index(drop=True)

                # budujemy listę indeksów (zgodnych z Lp)
                options = df_pick.index.tolist()

                def format_option(i: int) -> str:
                    row = df_pick.loc[i]

                    # --- bezpieczne formatowanie daty ---
                    date_val = row["Data notowania"]

                    if hasattr(date_val, "strftime"):
                        date_str = date_val.strftime("%Y-%m-%d")
                    else:
                        dt = pd.to_datetime(date_val, errors="coerce")
                        date_str = dt.strftime("%Y-%m-%d") if not pd.isna(dt) else str(date_val)

                    def _fmt_pct_short(v) -> str:
                        if v is None or pd.isna(v):
                            return "—"
                        try:
                            v = float(v)
                            sign = "+" if v > 0 else ""
                            return f"{sign}{v:.2f}%"
                        except Exception:
                            return str(v)

                    z20 = _fmt_pct_short(row.get("Zysk 20 sesji", np.nan))
                    z60 = _fmt_pct_short(row.get("Zysk 60 sesji", np.nan))
                    z120 = _fmt_pct_short(row.get("Zysk 120 sesji", np.nan))
                    zend = _fmt_pct_short(row.get("Zysk do końca VALIDATE", np.nan))

                    return (
                        f"{int(row['Lp.']):>3} | "
                        f"{date_str} | "
                        f"{row['Ticker']} | "
                        f"{row['Nazwa spółki']} | "
                        f"z20={z20} | z60={z60} | z120={z120} | zend={zend} | "
                        f"prob={row['Prawdopodobieństwo']:.4f} | "
                        f"{row['Typ rekordu']}"
                    )


                selected_idx = st.selectbox(
                    "Wybierz wiersz (możesz wyszukiwać po tekście):",
                    options=options,
                    format_func=format_option,
                    key="tab2_po_pick_idx",
                )

                selected_row = df_pick.loc[selected_idx]

                st.session_state["ml01_selected_row"] = selected_row

                st.markdown(
                    f"### Firma do analizy: "
                    f"{selected_row['Ticker']} ({selected_row['Nazwa spółki']})"
                )
                # NOWY WYKRES: ceny historyczne z VALIDATION + zaznaczenie dnia wybranego rekordu
                _render_validate_price_chart_for_selected_row(df_val, selected_row)

            else:
                st.info("Brak rekordów do wyboru.")




        else:
            st.info("Aby zobaczyć wynik PO filtrze — ustaw checkboxy i kliknij **Przefiltruj**.")

        st.divider()



        # ========================================================
        # FINALIZE (VAL) — ostatni trening na TRAIN+VALIDATION + zapis artefaktów
        # ========================================================
        st.divider()
        st.markdown("### FINALIZE (VAL) — trenuj na TRAIN+VALIDATION i zapisz model do TEST-catalog")

        st.caption(
            "Ten krok robi **ostatni trening** na danych TRAIN+VALIDATION (bez dotykania TEST), "
            "a następnie zapisuje artefakt modelu (.joblib) oraz metadane (.json) do katalogu: app/ml/models/test."
        )

        # --------------------------------------------------------
        # 1) Zbieramy konfigurację selekcji (w/k/p) i filtry z Tab2 (jeśli user je ustawił)
        #    Uwaga: zapis ma być możliwy także bez filtrów => filtry mogą być puste.
        # --------------------------------------------------------
        tab2_signature = st.session_state.get("tab2_sel_signature")  # (w, k, p) jeśli user wybierał
        if isinstance(tab2_signature, tuple) and len(tab2_signature) == 3:
            sel_w, sel_k, sel_p = tab2_signature
        else:
            sel_w, sel_k, sel_p = None, None, None

        # Filtry quality (checkboxy) – zawsze dostępne, ale mogą być wszystkie False
        # Jeżeli user nie był w Tab2, klucze mogą nie istnieć -> wtedy traktujemy jako brak filtrów.
        # Mapowanie kluczy jest spójne z _render_quality_filter_controls(key_prefix="tab2").
        quality_filters = {
            "trend": bool(st.session_state.get("tab2_f_trend", False)),
            "trend_long": bool(st.session_state.get("tab2_f_trend_long", False)),
            "momentum": bool(st.session_state.get("tab2_f_momentum", False)),
            "rsi_oversold": bool(st.session_state.get("tab2_f_rsi_oversold", False)),
            "macd_positive": bool(st.session_state.get("tab2_f_macd", False)),
            "price_above_sma200": bool(st.session_state.get("tab2_f_price_sma200", False)),
            "rsi": bool(st.session_state.get("tab2_f_rsi", False)),
            "volatility": bool(st.session_state.get("tab2_f_volatility", False)),
            "volume": bool(st.session_state.get("tab2_f_volume", False)),
            "rsi_not_overbought": bool(st.session_state.get("tab2_f_rsi_not_overbought", False)),
            "atr_high": bool(st.session_state.get("tab2_f_atr", False)),
            "price_above_vwap": bool(st.session_state.get("tab2_f_vwap", False)),
        }

        # Minimalna liczba spełnionych warunków (min_conditions)
        # ------------------------------------------------------
        # UI dla min_conditions istnieje w _render_quality_filter_controls(...):
        # key = f"{key_prefix}_min_conditions" (dla Tab2 => "tab2_min_conditions")
        #
        # Zasady:
        # - jeśli nie ma aktywnych filtrów => min_conditions zapisujemy jako None (filtry nie mają wpływu)
        # - jeśli są aktywne filtry:
        #   * próbujemy pobrać wartość z session_state (Tab2)
        #   * jeśli brak (user nie otworzył Tab2 / nie renderował filtrów) => fallback: AND (active_cnt)
        active_cnt = sum(1 for v in quality_filters.values() if v)

        if active_cnt == 0:
            min_conditions = None
        else:
            raw_mc = st.session_state.get("tab2_min_conditions", None)
            if raw_mc is None:
                # fallback: klasyczne AND (wszystkie aktywne warunki muszą być spełnione)
                min_conditions = active_cnt
            else:
                try:
                    mc_int = int(raw_mc)
                except Exception:
                    mc_int = active_cnt

                # clamp do sensownego zakresu 1..active_cnt
                if mc_int < 1:
                    mc_int = 1
                if mc_int > active_cnt:
                    mc_int = active_cnt

                min_conditions = mc_int

        # Hash filtrów do krótkiej nazwy pliku (pełna lista filtrów jest w JSON)
        f_hash = filters_hash(quality_filters, min_conditions=min_conditions)

        # Target shortcode do nazwy pliku (jeśli brak w słowniku -> fallback)
        target_short = get_param("ML01_TARGET_SIGNAL_SHORTCODES").get(cfg.target, cfg.target[:6].upper())

        # --------------------------------------------------------
        # 2) Generator nazwy pliku + komentarz
        # --------------------------------------------------------
        # Uwaga:
        # Streamlit trzyma stan widgetów po key=..., dlatego samo value=...
        # nie wystarcza do „przełączenia” formularza na nowy rekord.
        # Poniżej jawnie wykrywamy zmianę kontekstu FINALIZE
        # i seedujemy formularz nową nazwą + pustym komentarzem.

        finalize_comment_key = "ml01_finalize_comment"
        finalize_filename_key = "ml01_finalize_filename"
        finalize_context_key = "ml01_finalize_context_signature"
        overwrite_pending_key = "ml01_finalize_overwrite_pending"

        # Flaga: po udanym zapisie formularz ma zostać zresetowany
        # na początku następnego rerunu (a nie w tym samym przebiegu).
        finalize_reset_after_save_key = "ml01_finalize_reset_after_save"

        # Ostatnia automatycznie wygenerowana nazwa pliku.
        # Dzięki temu wiemy, czy użytkownik ręcznie zmienił filename.
        finalize_last_auto_filename_key = "ml01_finalize_last_auto_filename"

        # Flaga ręcznej edycji nazwy.
        # Gdy True, nie nadpisujemy już filename automatem po zmianie komentarza.
        finalize_filename_manual_key = "ml01_finalize_filename_manual"

        # Stały seed czasu dla bieżącego kontekstu formularza.
        # Dzięki temu auto-generowana nazwa nie „skacze” co rerun.
        finalize_ts_seed_key = "ml01_finalize_ts_seed"

        # Podpis kontekstu biznesowego dla FINALIZE.
        # Gdy zmieni się wybrana konfiguracja / model / target / hash filtrów,
        # formularz ma przejść w tryb zapisu NOWEGO modelu.
        finalize_context_signature = (
            str(best_model_name),
            str(cfg.target),
            sel_w,
            sel_k,
            sel_p,
            str(f_hash),
        )

        prev_finalize_context = st.session_state.get(finalize_context_key)
        reset_after_save = bool(st.session_state.get(finalize_reset_after_save_key, False))

        # Reset formularza wykonujemy wyłącznie przed utworzeniem widgetów.
        # Dzieje się to w dwóch sytuacjach:
        # 1) zmienił się kontekst biznesowy (np. wybrano nowy rekord z tabeli 27 kombinacji),
        # 2) poprzedni zapis zakończył się sukcesem i trzeba przygotować pusty formularz.
        if prev_finalize_context != finalize_context_signature or reset_after_save:
            ts_seed = datetime.now()
            default_fname_seed = build_model_filename(
                model_name=best_model_name,
                target_shortcode=target_short,
                window_sessions=sel_w,
                max_signals=sel_k,
                top_score_pct=sel_p,
                filters_h=f_hash,
                comment="",
                ts=ts_seed,
            )

            st.session_state[finalize_comment_key] = ""
            st.session_state[finalize_filename_key] = default_fname_seed
            st.session_state[finalize_last_auto_filename_key] = default_fname_seed
            st.session_state[finalize_filename_manual_key] = False
            st.session_state[finalize_ts_seed_key] = ts_seed.isoformat(timespec="seconds")
            st.session_state[overwrite_pending_key] = False
            st.session_state[finalize_context_key] = finalize_context_signature
            st.session_state[finalize_reset_after_save_key] = False

        # Odczytujemy aktualny seed czasu dla bieżącego formularza.
        # Seed pozostaje stały aż do zmiany kontekstu lub kolejnego udanego zapisu.
        ts_seed_raw = st.session_state.get(finalize_ts_seed_key)
        try:
            ts_seed = datetime.fromisoformat(ts_seed_raw) if ts_seed_raw else datetime.now()
        except Exception:
            ts_seed = datetime.now()

        prev_auto_filename = st.session_state.get(finalize_last_auto_filename_key)
        current_filename_state = st.session_state.get(finalize_filename_key)

        # Jeżeli aktualny filename różni się od ostatniej auto-wygenerowanej nazwy,
        # uznajemy, że użytkownik zmienił go ręcznie i nie wolno go już automatycznie nadpisywać.
        if prev_auto_filename is not None and current_filename_state is not None:
            st.session_state[finalize_filename_manual_key] = (current_filename_state != prev_auto_filename)

        # Callback uruchamiany po zmianie komentarza.
        # Dzięki temu aktualizacja nazwy pliku odbywa się w bezpieczny sposób:
        # po interakcji użytkownika i przed kolejnym pełnym renderem.
        def _on_finalize_comment_change() -> None:
            if bool(st.session_state.get(finalize_filename_manual_key, False)):
                return

            ts_seed_local_raw = st.session_state.get(finalize_ts_seed_key)
            try:
                ts_seed_local = datetime.fromisoformat(ts_seed_local_raw) if ts_seed_local_raw else datetime.now()
            except Exception:
                ts_seed_local = datetime.now()

            comment_now = st.session_state.get(finalize_comment_key, "")

            new_auto_filename = build_model_filename(
                model_name=best_model_name,
                target_shortcode=target_short,
                window_sessions=sel_w,
                max_signals=sel_k,
                top_score_pct=sel_p,
                filters_h=f_hash,
                comment=comment_now,
                ts=ts_seed_local,
            )

            st.session_state[finalize_filename_key] = new_auto_filename
            st.session_state[finalize_last_auto_filename_key] = new_auto_filename

        colN1, colN2 = st.columns([2, 1])

        with colN2:
            user_comment = st.text_input(
                "Komentarz pliku",
                help="Krótki opis (np. 'val_ok', 'trend_rsi', 'rf_best'). Trafi do metadanych i do tabeli modeli.",
                key=finalize_comment_key,
                on_change=_on_finalize_comment_change,
            )

        with colN1:
            filename_joblib = st.text_input(
                "Nazwa pliku modelu (można ją edytować przed zapisem)",
                help=(
                    "Plik zapisze się w app/ml/models/test. "
                    "Dopóki nie edytujesz tej nazwy ręcznie, komentarz będzie "
                    "automatycznie dopisywany do członu __c=<comment>."
                ),
                key=finalize_filename_key,
            )

        # Mapowanie pól nazwy (Twoje wymaganie)
        with st.expander("Mapowanie pól nazwy pliku → pola na ekranie", expanded=False):
            st.markdown(
                f"""
**Format:** `YYYYMMDD_HHMM__<model>__y=<target>__w=<window>__k=<max>__p=<pct>__f=<hash>__c=<comment>.joblib`

- `YYYYMMDD_HHMM` → timestamp zapisu (moment FINALIZE)
- `<model>` → wybrany model z zakładki „Porównanie modeli” (`best_model_name`)
- `y=<target>` → target (y) wybrany w Setup (`cfg.target`) w skrócie: `{target_short}`
- `w=<window>` → `window_sessions` z Tab2 („Rozmiar okna sesji”), jeśli wybrane
- `k=<max>` → `max_signals` z Tab2 („Top-K”), jeśli wybrane
- `p=<pct>` → `top_score_pct` z Tab2 („Top-%”), jeśli wybrane
- `f=<hash>` → krótki hash konfiguracji filtrów (pełna lista filtrów jest w JSON + tabeli)
- `c=<comment>` → Twój komentarz (oddzielna kolumna w tabeli)
"""
            )

        if sel_w is None:
            st.warning(
                "Nie widzę wybranej konfiguracji (w/k/p) z Tab2. "
                "Możesz zapisać model mimo to (w/k/p będzie 'na'), "
                "ale rekomendowane: wybierz konfigurację w Tab2 przed FINALIZE."
            )

        # --------------------------------------------------------
        # 3) Przycisk FINALIZE (z potwierdzeniem nadpisania)
        # --------------------------------------------------------
        out_dir = dir_test()

        # Kandydat nazwy do sprawdzania kolizji:
        # - gdy nazwa jest ręcznie edytowana -> sprawdzamy dokładnie ją,
        # - gdy nazwa jest automatyczna -> sprawdzamy wariant wyliczony z aktualnego komentarza.
        if bool(st.session_state.get(finalize_filename_manual_key, False)):
            filename_for_exists_check = filename_joblib
        else:
            filename_for_exists_check = build_model_filename(
                model_name=best_model_name,
                target_shortcode=target_short,
                window_sessions=sel_w,
                max_signals=sel_k,
                top_score_pct=sel_p,
                filters_h=f_hash,
                comment=user_comment,
                ts=ts_seed,
            )

        fp_model = out_dir / filename_for_exists_check

        def _do_finalize_save() -> None:
            # Ostatni trening: TRAIN + VALIDATION
            X_final = pd.concat([prepared.X_train, prepared.X_test], axis=0, ignore_index=True)
            y_final = pd.concat([prepared.y_train, prepared.y_test], axis=0, ignore_index=True)

            with st.spinner("FINALIZE: trening na TRAIN+VALIDATION i zapis modelu…"):
                pipe_final = make_model_pipeline(best_model_name, cfg, mode=ml01_mode)
                pipe_final.fit(X_final, y_final)

                # Podsumowanie VAL do meta modelu.
                #
                # Zasada:
                # 1) jeśli użytkownik policzył wynik PO w Tab2 i ten wynik jest zgodny
                #    z aktualną konfiguracją (w/k/p + filtry + min_conditions),
                #    to zapisujemy metryki z PO;
                # 2) w przeciwnym razie robimy bezpieczny fallback do metryk PRZED z gridu.
                val_summary = {}

                try:
                    current_selection_signature = (
                        (sel_w, sel_k, sel_p)
                        if (sel_w is not None and sel_k is not None and sel_p is not None)
                        else None
                    )

                    current_tab2_runtime_signature = _build_tab2_filter_runtime_signature(
                        selection_signature=current_selection_signature,
                        filters=quality_filters,
                        min_conditions=min_conditions,
                        df_sel_base=(
                            select_signals_topk_then_toppct(
                                df_val_rank_full,
                                date_col="trade_date",
                                score_col="prob",
                                window_sessions=sel_w,
                                max_signals=sel_k,
                                top_score_pct=sel_p,
                            )
                            if current_selection_signature is not None
                            else None
                        ),
                    )

                    saved_filtered_signature = st.session_state.get("tab2_filtered_signature")
                    df_sel_filtered_saved = st.session_state.get("tab2_df_sel_filtered")

                    can_use_filtered_summary = (
                        current_selection_signature is not None
                        and isinstance(df_sel_filtered_saved, pd.DataFrame)
                        and saved_filtered_signature == current_tab2_runtime_signature
                    )

                    if can_use_filtered_summary:
                        # Używamy REALNIE policzonego wyniku PO.
                        val_summary = _build_val_summary_from_selected_df(
                            df_selected=df_sel_filtered_saved,
                            df_all_rank=df_val_rank_full,
                        )
                    else:
                        # Fallback: metryki PRZED z gridu.
                        res_grid = st.session_state.get("tab2_grid_cache")
                        if isinstance(res_grid, pd.DataFrame) and sel_w is not None:
                            match = res_grid[
                                (res_grid["window_sessions"] == sel_w)
                                & (res_grid["max_signals"] == sel_k)
                                & (res_grid["top_score_pct"] == sel_p)
                            ]
                            if not match.empty:
                                r0 = match.iloc[0]
                                val_summary = {
                                    "precision": float(r0.get("precision", np.nan)),
                                    "n_selected": int(r0.get("n_selected", 0)),
                                    "avg_ret_20": float(r0.get("avg_ret_20", np.nan)),
                                    "avg_ret_60": float(r0.get("avg_ret_60", np.nan)),
                                    "avg_ret_120": float(r0.get("avg_ret_120", np.nan)),
                                    "avg_ret_end": float(r0.get("avg_ret_end", np.nan)),
                                }
                except Exception:
                    val_summary = {}

                # Id selektora rankingowego (ważne dla odtworzenia TEST)
                # W ML-01 kanoniczny wariant to: Top-K → Top-Pct
                rank_selector_id = "topk_then_toppct"

                meta = {
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                    "comment": user_comment,
                    "model_name": best_model_name,
                    "target": cfg.target,
                    "ml01_mode": ml01_mode,

                    # Setup
                    "setup_cfg": {
                        "session_id": cfg.session_id,
                        "fix_imbalance": cfg.fix_imbalance,
                        "normalize": cfg.normalize,
                        "transformation": cfg.transformation,
                        "ignore_features": list(cfg.ignore_features),
                    },

                    # Kontrakt cech
                    "feature_cols": list(prepared.feature_cols),

                    # Konfiguracja selekcji rankingowej (Tab2)
                    # rank_selector_id mówi, którego algorytmu selekcji użyć w ML-TEST
                    "rank_selector_id": rank_selector_id,
                    "rank_params": {
                        "window_sessions": sel_w,
                        "max_signals": sel_k,
                        "top_score_pct": sel_p,
                    },

                    # Filtry jakościowe (pełna informacja)
                    "quality_filters": {k: bool(v) for k, v in quality_filters.items()},
                    "min_conditions": min_conditions,
                    "filters_hash": f_hash,

                    # Ex post (VAL) – żebyś widział efekt przy zapisie
                    "val_summary": val_summary,
                }

                # Nazwa pliku do zapisu:
                # - jeśli użytkownik NIE edytował filename ręcznie,
                #   to tuż przed zapisem budujemy nazwę jeszcze raz z AKTUALNEGO komentarza,
                #   żeby zapisać dokładnie to, co wynika z bieżącego stanu formularza;
                # - jeśli użytkownik edytował nazwę ręcznie, szanujemy jego wartość 1:1.
                #
                # WAŻNE:
                # Nie wolno tutaj robić:
                #   st.session_state[finalize_filename_key] = ...
                # ponieważ widget text_input z tym key został już wcześniej utworzony
                # w tym samym przebiegu renderu. Taka modyfikacja kończy się
                # StreamlitAPIException.
                if bool(st.session_state.get(finalize_filename_manual_key, False)):
                    filename_to_save = filename_joblib
                else:
                    filename_to_save = build_model_filename(
                        model_name=best_model_name,
                        target_shortcode=target_short,
                        window_sessions=sel_w,
                        max_signals=sel_k,
                        top_score_pct=sel_p,
                        filters_h=f_hash,
                        comment=user_comment,
                        ts=ts_seed,
                    )

                    # Możemy zaktualizować wyłącznie pomocniczy stan techniczny,
                    # który NIE jest kluczem widgetu.
                    st.session_state[finalize_last_auto_filename_key] = filename_to_save

                # Bardzo ważne:
                # meta JSON musi wskazywać DOKŁADNIE ten plik .joblib,
                # który faktycznie zapisujemy na dysk.
                #
                # Bez tego może powstać niespójność:
                # - plik modelu zapisze się pod filename_to_save
                # - ale meta["model_file"] będzie wskazywać starszą / inną nazwę
                #   (np. sprzed przebudowania nazwy z komentarza).
                #
                # To później wywraca ML (TEST), bo _load_model_from_meta(...)
                # ładuje model właśnie na podstawie meta["model_file"].
                meta["model_file"] = (out_dir / filename_to_save).resolve().relative_to(project_root().resolve()).as_posix()

                save_model_and_meta(
                    out_dir=out_dir,
                    filename_joblib=filename_to_save,
                    model_obj=pipe_final,
                    meta=meta,
                )

            # Po udanym zapisie NIE modyfikujemy bezpośrednio wartości widgetów
            # (bo zostały już utworzone w tym przebiegu i Streamlit rzuca wyjątek).
            # Zamiast tego ustawiamy flagę, a właściwy reset formularza wykona się
            # na początku następnego rerunu, jeszcze przed zbudowaniem text_input.
            st.session_state[overwrite_pending_key] = False
            st.session_state[finalize_context_key] = finalize_context_signature
            st.session_state[finalize_reset_after_save_key] = True

            st.success(f"Zapisano model i metadane do: {out_dir}")
            st.rerun()

        # Klik zapis:
        if st.button("FINALIZE: Trenuj na TRAIN+VAL i zapisz model", type="primary", key="ml01_finalize_btn"):
            if fp_model.exists():
                st.session_state[overwrite_pending_key] = True
            else:
                st.session_state[overwrite_pending_key] = False
                _do_finalize_save()

        # Potwierdzenie nadpisania (2-krokowe)
        if fp_model.exists() and st.session_state.get(overwrite_pending_key):
            st.warning(f"Plik już istnieje: {fp_model.name}. Czy na pewno chcesz nadpisać?")
            cO1, cO2 = st.columns(2)
            with cO1:
                if st.button("Tak, nadpisz", key="ml01_finalize_overwrite_yes"):
                    st.session_state[overwrite_pending_key] = False
                    _do_finalize_save()
            with cO2:
                if st.button("Nie, anuluj", key="ml01_finalize_overwrite_no"):
                    st.session_state[overwrite_pending_key] = False
                    st.info("Anulowano nadpisanie. Zmień nazwę pliku i spróbuj ponownie.")

        # --------------------------------------------------------
        # 4) Tabela zapisanych modeli (3 katalogi + dynamiczne kolumny filtrów)
        # --------------------------------------------------------
        st.divider()
        st.markdown("### Zapisane modele — podgląd katalogów")

        catalogs = available_catalogs()
        cC1, cC2, cC3 = st.columns(3)
        with cC1:
            show_test = st.checkbox("Pokaż: test", value=True, key="ml01_models_show_test")
        with cC2:
            show_prd = st.checkbox("Pokaż: prd", value=False, key="ml01_models_show_prd")
        with cC3:
            show_prez = st.checkbox("Pokaż: prezentation", value=False, key="ml01_models_show_prez")

        selected_dirs = []
        if show_test:
            selected_dirs.append(("test", dir_test()))
        if show_prd:
            selected_dirs.append(("prd", [c.path for c in catalogs if c.key == "prd"][0]))
        if show_prez:
            selected_dirs.append(("prezentation", [c.path for c in catalogs if c.key == "prezentation"][0]))

        metas_all = []
        for _, d in selected_dirs:
            metas_all.extend(list_models_from_dir(d))

        if not metas_all:
            st.info("Brak zapisanych modeli w wybranych katalogach.")
        else:
            df_models = models_table(metas_all).copy()

            # Sortowanie startowe:
            # pokazujemy najwyższy Zysk 20 VAL na górze już przy pierwszym
            # wejściu do tabeli. Użytkownik nadal może później posortować
            # tabelę po dowolnej innej kolumnie.
            raw_sort_col = "val_ret20"
            if raw_sort_col in df_models.columns:
                df_models[raw_sort_col] = pd.to_numeric(
                    df_models[raw_sort_col],
                    errors="coerce",
                )
                df_models = df_models.sort_values(
                    by=raw_sort_col,
                    ascending=False,
                    na_position="last",
                    kind="stable",
                ).reset_index(drop=True)

            # Budujemy widok UI z docelowymi nazwami kolumn.
            # Metryki pozostają liczbowe, więc AgGrid będzie sortował je poprawnie.
            df_models_view = _models_table_ui(df_models).copy()

            # Render przez AgGrid zamiast st.dataframe.
            # To naprawia sortowanie po kliknięciu w nagłówki kolumn
            # dla całego zbioru rekordów, a nie tylko dla widocznego fragmentu tabeli.
            _render_models_table_aggrid(
                df_models_view,
                table_key="saved_models_catalog_table",
                height=420,
            )

            with st.expander("Legenda filtrów (skrót → opis)", expanded=False):
                filt_map = get_param("ML01_QUALITY_FILTER_SHORTCODES")

                # Budujemy prostą tabelę pomocniczą z opisem skrótów filtrów.
                legend_rows = [
                    {"filter_key": k, "code": v[0], "description": v[1]}
                    for k, v in filt_map.items()
                ]

                # Streamlit odchodzi od parametru use_container_width.
                # width="stretch" daje to samo zachowanie co dawniej use_container_width=True.
                st.dataframe(
                    pd.DataFrame(legend_rows),
                    width="stretch",
                    hide_index=True,
                )

    # ========================================================
    # TAB 3 — ML (TEST) — test zapisanych modeli na zbiorze TEST
    # ========================================================
    with tab3:
        st.markdown("### Finalny test modelu (TEST)")
        st.caption(
            "Ta zakładka służy do końcowego sprawdzenia modelu na danych TEST, "
            "czyli na zbiorze odłożonym wcześniej i niewykorzystywanym w uczeniu. "
            "Dzięki temu możesz zobaczyć, jak model zachowuje się na najbardziej niezależnych danych."
        )

        # --------------------------------------------------------
        # (A) Wybór katalogów modeli (test/prd/prezentation)
        # Domyślne zaznaczenie:
        # - DEMO -> prezentation
        # - DEV  -> test
        # --------------------------------------------------------
        # Runtime source of truth:
        # APP_TEST_ON_CSV_FILES=True oznacza, że aplikacja działa w trybie CSV/DEMO
        # (albo jawne DEMO, albo fallback po braku DB).
        app_mode = str(get_param("APP_MODE")).upper()
        app_runs_on_csv = bool(get_param("APP_TEST_ON_CSV_FILES"))

        # Domyślny katalog modeli:
        # - CSV / DEMO / fallback bez DB -> prezentation
        # - DB -> test
        default_prez = app_runs_on_csv
        default_test = not app_runs_on_csv

        catalogs = available_catalogs()
        cat_map = {c.key: c for c in catalogs}

        st.markdown("#### Katalog modeli (wybierz jeden)")

        # Radio zamiast checkboxów => zawsze tylko 1 katalog naraz.
        # Domyślnie:
        # - DEMO -> prezentation
        # - DEV/PROD/TEST -> test
        available_keys = [k for k in ["test", "prd", "prezentation"] if k in cat_map]

        if not available_keys:
            st.warning("Brak skonfigurowanych katalogów modeli (test/prd/prezentation).")
            st.stop()

        default_key = "prezentation" if default_prez else "test"
        if default_key not in available_keys:
            default_key = available_keys[0]

        def _reset_tab3_on_catalog_change() -> None:
            """
            Czyści stan zakładki ML(TEST) po zmianie katalogu modeli.
            Dzięki temu nie mieszamy:
            - wybranego modelu,
            - wyników predykcji na TEST,
            - filtrów jakościowych z poprzedniego modelu,
            - trybu eksperymentalnego.
            """
            keys_to_drop = [
                "tab3_pick_model_idx",
                "tab3_selected_meta",
                "tab3_df_test_rank_full",
                "tab3_df_sel_rank",
                "tab3_df_sel_filtered",
                "tab3_test_summary",
                "tab3_pick_row_idx",
                "tab3_experiment_mode",
                "tab3_min_conditions",
                # Ostatnia policzona konfiguracja filtrów (faktyczny wynik PO).
                "tab3_filters_signature",
                # Bazowa konfiguracja filtrów z meta modelu.
                # Służy wyłącznie do automatycznego replay po wyborze modelu.
                "tab3_base_filters_signature",
]
            for k in keys_to_drop:
                st.session_state.pop(k, None)

            for k in list(st.session_state.keys()):
                if isinstance(k, str) and k.startswith("tab3_f_"):
                    st.session_state.pop(k, None)

        selected_key = st.radio(
            "Wybierz katalog:",
            options=available_keys,
            index=available_keys.index(default_key),
            horizontal=True,
            key="tab3_models_catalog_radio",
            on_change=_reset_tab3_on_catalog_change,
        )

        selected_dirs: list[Path] = [cat_map[selected_key].path]

        metas_all: list[dict] = []
        for d in selected_dirs:
            metas_all.extend(list_models_from_dir(d))

        st.markdown("#### Dostępne modele")
        if not metas_all:
            st.info("Brak zapisanych modeli w wybranych katalogach.")
            st.stop()

        # --------------------------------------------------------
        # Tabela modeli + stabilne LP dla tabeli i listy wyboru
        # --------------------------------------------------------
        # Zasada biznesowa:
        # 1) najpierw sortujemy SUROWE dane modeli po metryce zysku,
        # 2) dopiero potem formatujemy kolumny do UI,
        # 3) na końcu nadajemy LP,
        # 4) ta sama kolejność i te same LP muszą być użyte w tabeli
        #    oraz w selectboxie "Wybierz model do testu".
        #
        # Dlaczego tak?
        # W _models_table_ui() kolumny val_ret20 / val_ret60 / val_ret120
        # są zamieniane na tekst typu "4.49%". Taki tekst nie nadaje się
        # do bezpiecznego sortowania numerycznego przez pd.to_numeric(...),
        # bo znak "%" daje NaN. Dlatego sortujemy wcześniej, na surowej
        # kolumnie liczbowej "val_ret20".
        df_models = models_table(metas_all).copy()

        # Przygotowujemy klucz techniczny do bezpiecznego połączenia:
        # tabela UI <-> meta modelu.
        # Używamy pełnej nazwy pliku modelu jako stabilnego identyfikatora w obrębie katalogu.
        meta_by_model_file = {
            Path(m.get("model_file", "")).name: m
            for m in metas_all
        }

        # Sortowanie po surowej kolumnie liczbowej "val_ret20" malejąco.
        # Dzięki temu na górze tabeli są rekordy z najwyższym zyskiem 20 VAL.
        raw_sort_col = "val_ret20"
        if raw_sort_col in df_models.columns:
            df_models[raw_sort_col] = pd.to_numeric(
                df_models[raw_sort_col],
                errors="coerce",
            )
            df_models = df_models.sort_values(
                by=raw_sort_col,
                ascending=False,
                na_position="last",
                kind="stable",
            ).reset_index(drop=True)

        # Dopiero po sortowaniu formatujemy dane do warstwy UI.
        df_models_view = _models_table_ui(df_models).copy()

        # Po sortowaniu nadajemy stabilne LP 1..N.
        # LP jest częścią danych wiersza, więc numer w tabeli
        # i numer w selectboxie odnoszą się do tego samego modelu.
        df_models_view.insert(0, "LP", np.arange(1, len(df_models_view) + 1))

        # Renderujemy tabelę modeli przez AgGrid.
        # Dzięki temu sortowanie po kliknięciu w nagłówek działa
        # globalnie dla całego zbioru rekordów, a nie tylko dla
        # aktualnie widocznego fragmentu tabeli.
        _render_models_table_aggrid(
            df_models_view,
            table_key="tab3_models_table",
            height=420,
        )

        # Budujemy źródło prawdy dla selectboxa na podstawie TEJ SAMEJ,
        # już posortowanej tabeli. Dzięki temu:
        # - LP w tabeli
        # - LP w selectboxie
        # odnoszą się do dokładnie tego samego modelu.
        models_with_lp = []
        for _, row in df_models_view.iterrows():
            lp = int(row["LP"])
            model_file_name = str(row.get("Plik modelu", ""))
            meta = meta_by_model_file.get(model_file_name)

            # Dodatkowe zabezpieczenie:
            # jeśli nie uda się znaleźć meta po nazwie pliku, pomijamy taki rekord.
            # W normalnym scenariuszu nie powinno się to zdarzyć.
            if meta is None:
                continue

            models_with_lp.append({
                "lp": lp,
                "meta": meta,
            })

        # Wygodny opis opcji w selectboxie.
        # LP na początku musi być zgodne z LP z tabeli "Dostępne modele".
        def _model_label(item: dict) -> str:
            m = item["meta"]
            fn = Path(m.get("model_file", "")).name
            created = m.get("created_at", "")
            comment = m.get("comment", "")
            model_name = m.get("model_name", "")
            target = m.get("target", "")
            lp = int(item["lp"])
            return f"[{lp}] {created} | {fn} | {model_name} | y={target} | {comment}"

        # Lista opcji opiera się na stabilnym LP przypisanym PO sortowaniu tabeli.
        # Dzięki temu numer w selectboxie odpowiada numerowi LP widocznemu w tabeli.
        option_lps = [item["lp"] for item in models_with_lp]

        prev_meta_sel = st.session_state.get("tab3_selected_meta")
        # Domyślnie wybieramy pierwszy model z posortowanej listy,
        # czyli model z najwyższym "Zysk 20 VAL".
        default_lp = option_lps[0]

        if prev_meta_sel:
            prev_model_file = str(prev_meta_sel.get("model_file", ""))
            for item in models_with_lp:
                item_model_file = str(item["meta"].get("model_file", ""))
                if item_model_file == prev_model_file:
                    default_lp = int(item["lp"])
                    break

        chosen_lp = st.selectbox(
            "Wybierz model do testu",
            options=option_lps,
            index=option_lps.index(default_lp),
            format_func=lambda lp: _model_label(next(item for item in models_with_lp if item["lp"] == lp)),
            key="tab3_pick_model_idx",
        )


        # Aktualny wybór z selectboxa.
        chosen_item = next(item for item in models_with_lp if item["lp"] == int(chosen_lp))
        selected_meta = chosen_item["meta"]

        # Wariant A:
        # wybór w selectboxie NATYCHMIAST przełącza aktywny model.
        # Jeżeli wybrano inny model niż poprzednio aktywny,
        # czyścimy wyniki i odtwarzamy stan filtrów z meta nowego modelu.
        selected_model_file = str(selected_meta.get("model_file", ""))
        prev_model_file = str(prev_meta_sel.get("model_file", "")) if prev_meta_sel else ""

        if (not prev_meta_sel) or (selected_model_file != prev_model_file):
            st.session_state["tab3_selected_meta"] = selected_meta

            # Czyścimy stan filtrów z poprzedniego modelu, aby seed z meta nowego modelu
            # zawsze odtworzył konfigurację zapisaną razem z modelem.
            st.session_state.pop("tab3_min_conditions", None)
            st.session_state.pop("tab3_pick_row_idx", None)
            for k in list(st.session_state.keys()):
                if isinstance(k, str) and k.startswith("tab3_f_"):
                    st.session_state.pop(k, None)

            # Seed filtrów jakościowych z meta nowego modelu.
            _seed_quality_filters_state_from_meta(key_prefix="tab3", meta=selected_meta)

            # Czyścimy poprzednie wyniki testu.
            # Dzięki temu poniższe sekcje NIE pokazują danych starego modelu.
            for k in [
                "tab3_df_test_rank_full",
                "tab3_df_sel_rank",
                "tab3_df_sel_filtered",
                "tab3_filters_signature",
                "tab3_base_filters_signature",
                "tab3_test_summary",
            ]:
                st.session_state.pop(k, None)

            # Opcjonalnie wymuszamy rerun, aby użytkownik od razu zobaczył
            # spójny stan całej zakładki dla nowego modelu.
            st.rerun()

        meta_sel = st.session_state.get("tab3_selected_meta")
        if not meta_sel:
            st.info("Wybierz model do testu.")
            st.stop()

        st.markdown("----")

        # --------------------------------------------------------
        # (B) Parametry selekcji rankingowej — domyślnie z meta
        # --------------------------------------------------------
        rp = meta_sel.get("rank_params") or {}
        rank_selector_id = meta_sel.get("rank_selector_id", "topk_then_toppct")

        default_w = int(rp.get("window_sessions", 50) or 50)
        default_k = int(rp.get("max_signals", 3) or 3)
        default_p = float(rp.get("top_score_pct", 0.001) or 0.001)

        st.markdown("#### Parametry selekcji (zapisane w modelu)")
        st.write(
            {
                "rank_selector_id": rank_selector_id,
                "window_sessions": default_w,
                "max_signals": default_k,
                "top_score_pct": default_p,
            }
        )

        # Parametry selekcji na zakładce TEST są "zamrożone" i zawsze bierzemy je z meta modelu.
        # Dzięki temu zakładka TEST pozostaje stricte ewaluacyjna (holdout), bez strojenia.
        w = default_w
        k = default_k
        p = default_p

        # --------------------------------------------------------
        # (C) Uruchom test: predykcja prob na df_test + selekcja rankingowa
        # --------------------------------------------------------
        if "tab3_df_test_rank_full" not in st.session_state:
            with st.spinner("Wczytywanie modelu i predykcja na zbiorze TEST..."):
                model_obj = _load_model_from_meta(meta_sel)

                # !!! Najważniejsza zasada: bazujemy TYLKO na df_test !!!
                df_test_rank_full = _build_test_rank_full(df_test, model_obj=model_obj, meta=meta_sel)

                st.session_state["tab3_df_test_rank_full"] = df_test_rank_full

        df_test_rank_full = st.session_state.get("tab3_df_test_rank_full")
        if df_test_rank_full is None or df_test_rank_full.empty:
            st.warning("Brak danych TEST po predykcji (df_test_rank_full puste).")
            st.stop()

        # wybór funkcji selekcji
        if rank_selector_id == "toppct_then_topk":
            selector_fn = select_signals_toppct_then_topk
        else:
            selector_fn = select_signals_topk_then_toppct  # domyślne / kanoniczne

        if "tab3_df_sel_rank" not in st.session_state:
            with st.spinner("Selekcja rankingowa na TEST (RANK)..."):
                df_sel_rank = selector_fn(
                    df_test_rank_full,
                    window_sessions=w,
                    max_signals=k,
                    top_score_pct=p,
                )
            st.session_state["tab3_df_sel_rank"] = df_sel_rank

        df_sel_rank = st.session_state.get("tab3_df_sel_rank")

        st.markdown("#### Diagnostyka selekcji: RANK → PO (filtry jakościowe)")

        # --------------------------------------------------------
        # TRYB EKSPERYMENTALNY:
        # - źródłem prawdy jest runtime: APP_TEST_ON_CSV_FILES
        # - jeśli aplikacja działa na CSV (DEMO / fallback bez DB), to zakładka TEST jest strict read-only
        # - checkbox "Tryb eksperymentalny" pokazujemy TYLKO poza runtime CSV
        # --------------------------------------------------------
        app_runs_on_csv = bool(get_param("APP_TEST_ON_CSV_FILES"))

        if not app_runs_on_csv:
            exp_mode = st.checkbox(
                "Tryb eksperymentalny (pozwól zmieniać tylko filtry jakościowe na TEST)",
                value=False,
                key="tab3_experiment_mode",
                help=(
                    "Uwaga: zmienianie filtrów na zbiorze TEST może prowadzić do dopasowania wyników "
                    "do tego konkretnego zbioru. Traktuj tę opcję wyłącznie jako narzędzie pomocnicze, "
                    "a nie jako część właściwej oceny modelu."
                    "Używaj tego trybu wyłącznie diagnostycznie."
                ),
            )
        else:
            # CSV/DEMO => strict read-only, bez eksperymentowania
            exp_mode = False

        # Render kontrolek filtrów.
        # Po wyborze modelu ich wartości są seedowane z meta JSON modelu.
        # W trybie read-only user nie może ich zmieniać, ale nadal chcemy
        # wykorzystać zapisane wartości do automatycznego odtworzenia wyniku PO.
        filters, min_conditions = _render_quality_filter_controls(
            key_prefix="tab3",
            disabled=(app_runs_on_csv or (not exp_mode)),
        )

        # --------------------------------------------------------
        # AUTO-ODTWORZENIE PO Z META MODELU
        # --------------------------------------------------------
        # To jest kluczowa zmiana:
        # - po wybraniu modelu chcemy automatycznie policzyć wynik PO na TEST
        #   z filtrów zapisanych razem z modelem,
        # - dzięki temu metryka "PO (po filtrach)" pokazuje realny wynik modelu,
        #   a nie "—".
        #

        # --------------------------------------------------------
        # WARIANT B:
        # - po wyborze modelu automatycznie odtwarzamy PO z filtrów zapisanych w meta,
        # - po ręcznej zmianie checkboxów w trybie eksperymentalnym NIE przeliczamy PO automatycznie,
        # - przeliczenie eksperymentalne następuje dopiero po kliknięciu "Przefiltruj (TEST)".
        # --------------------------------------------------------

        # Bieżący stan kontrolek z UI.
        # To jest stan, którym użytkownik może eksperymentować.
        current_filters = filters
        current_min_conditions = min_conditions

        # Bazowa konfiguracja modelu pochodzi z meta_sel.
        # Uwaga: seed do session_state został wykonany wcześniej przy choose_btn,
        # ale do automatycznego replay nie chcemy polegać na aktualnym stanie checkboxów,
        # bo user mógł je już zmienić w trybie eksperymentalnym.
        base_filters = dict(meta_sel.get("quality_filters") or {})
        base_min_conditions = meta_sel.get("min_conditions", None)

        # Normalizacja min_conditions:
        # - jeśli w meta jest None, zostawiamy None,
        # - jeśli w meta jest liczba, rzutujemy jawnie na int.
        if base_min_conditions is not None:
            base_min_conditions = int(base_min_conditions)

        # Sygnatura bazowa służy WYŁĄCZNIE do automatycznego replay po wyborze modelu
        # albo po zmianie modelu / wyniku RANK.
        base_filters_signature = (
            tuple(sorted((k, bool(v)) for k, v in base_filters.items())),
            base_min_conditions,
            len(df_sel_rank) if df_sel_rank is not None else 0,
            str(meta_sel.get("model_file", "")),
        )

        prev_base_filters_signature = st.session_state.get("tab3_base_filters_signature")

        # --------------------------------------------------------
        # AUTO-REPLAY z meta modelu
        # --------------------------------------------------------
        # Automatyczne liczenie PO wykonujemy tylko dla bazowej konfiguracji modelu.
        # Ręczne zmiany checkboxów NIE uruchamiają tego bloku.
        if (
            "tab3_df_sel_filtered" not in st.session_state
            or prev_base_filters_signature != base_filters_signature
        ):
            if df_sel_rank is None or df_sel_rank.empty:
                st.session_state["tab3_df_sel_filtered"] = df_sel_rank
            else:
                active_base_filters_count = sum(1 for v in base_filters.values() if bool(v))

                # Jeżeli model nie ma aktywnych filtrów zapisanych w meta, to PO = RANK.
                if active_base_filters_count == 0:
                    st.session_state["tab3_df_sel_filtered"] = df_sel_rank.copy()
                else:
                    with st.spinner("Odtwarzanie filtrów jakościowych zapisanych w modelu (PO na TEST)..."):
                        st.session_state["tab3_df_sel_filtered"] = _apply_quality_filters_on_df(
                            df_sel_rank,
                            filters=base_filters,
                            min_conditions=(base_min_conditions if base_min_conditions is not None else 0),
                        )

            # Zapisujemy:
            # - bazową sygnaturę modelu, aby wiedzieć czy replay jest nadal aktualny,
            # - sygnaturę faktycznie policzonego wyniku PO.
            st.session_state["tab3_base_filters_signature"] = base_filters_signature
            st.session_state["tab3_filters_signature"] = base_filters_signature

        # Przycisk ma sens tylko poza DEMO/CSV i tylko w trybie eksperymentalnym.
        if (not app_runs_on_csv) and exp_mode:
            apply_btn = st.button(
                "Przefiltruj (TEST)",
                key="tab3_apply_filters_btn",
                type="primary",
                disabled=(df_sel_rank is None or df_sel_rank.empty),
            )
        else:
            apply_btn = False

        # --------------------------------------------------------
        # RĘCZNE PRZELICZENIE eksperymentalne
        # --------------------------------------------------------
        # Tylko kliknięcie przycisku uruchamia przeliczenie z aktualnych checkboxów.
        if apply_btn and df_sel_rank is not None and (not df_sel_rank.empty):
            with st.spinner("Filtrowanie jakościowe na TEST (PO)…"):
                st.session_state["tab3_df_sel_filtered"] = _apply_quality_filters_on_df(
                    df_sel_rank,
                    filters=current_filters,
                    min_conditions=current_min_conditions,
                )

            # Zapisujemy sygnaturę faktycznie policzonego wyniku eksperymentalnego.
            current_filters_signature = (
                tuple(sorted((k, bool(v)) for k, v in current_filters.items())),
                None if current_min_conditions is None else int(current_min_conditions),
                len(df_sel_rank) if df_sel_rank is not None else 0,
                str(meta_sel.get("model_file", "")),
            )
            st.session_state["tab3_filters_signature"] = current_filters_signature

        df_sel_filtered = st.session_state.get("tab3_df_sel_filtered")
        if df_sel_filtered is None:
            # Bezpieczny fallback: PO nie może być puste w UI.
            df_sel_filtered = df_sel_rank


        # Metryki pokazujemy dopiero po ustaleniu finalnego df_sel_filtered.
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Liczba obserwacji w TEST", f"{len(df_test_rank_full):,}".replace(",", " "))
        with c2:
            st.metric("RANK (po selekcji)", f"{len(df_sel_rank):,}".replace(",", " ") if df_sel_rank is not None else "—")
        with c3:
            st.metric("PO (po filtrach)", f"{len(df_sel_filtered):,}".replace(",", " ") if df_sel_filtered is not None else "—")

        # --------------------------------------------------------
        # (E) Diagramy (jak w tab2) — ale baseline to RANK (nie „PRZED”)
        # --------------------------------------------------------
        _plot_prob_hist_rank_vs_filtered(
            df_sel_rank,
            df_sel_filtered,
            title="Rozkład prob: RANK vs PO (TEST)",
        )

        # TP/FP, TN/FN: nadal ma sens, bo mamy y_true na TEST
        _plot_prob_hist_tp_fp_tn_fn(
            df_sel_before=df_sel_rank,
            df_sel_after=df_sel_filtered,
            df_all_before=df_test_rank_full,
            df_all_after=df_test_rank_full,
            title_tp_fp="TP vs FP: rozkład prob (SELECTED) — RANK vs PO (TEST)",
            title_tn_fn="TN vs FN: rozkład prob (NOT SELECTED) — RANK vs PO (TEST)",
        )

        st.markdown("#### Wynik PO (po filtrze) — TEST")

        df_view_after = _build_table_view_after(df_sel_filtered, filters=filters, df_val_prices=df_test)

        # poprawiamy podpis ret_end, bo helper ma nazwę "VALIDATE"
        if "Zysk do końca VALIDATE" in df_view_after.columns:
            df_view_after = df_view_after.rename(columns={"Zysk do końca VALIDATE": "Zysk do końca TEST"})

        grid_resp = _render_aggrid_table(
            df_view_after,
            table_key="tab3_table_after",
            height=420,
            page_size=10,
        )

        st.markdown("#### Wybór rekordu PO do analizy")
        if df_view_after is not None and not df_view_after.empty:
            df_pick = df_view_after.copy().reset_index(drop=True)
            options_idx = df_pick.index.tolist()

            def format_option(i: int) -> str:
                row = df_pick.loc[i]
                date_val = row.get("Data notowania")

                if hasattr(date_val, "strftime"):
                    date_str = date_val.strftime("%Y-%m-%d")
                else:
                    dt = pd.to_datetime(date_val, errors="coerce")
                    date_str = dt.strftime("%Y-%m-%d") if pd.notna(dt) else "—"

                ticker = str(row.get("Ticker", "—"))
                prob = row.get("Prawdopodobieństwo", np.nan)
                try:
                    prob_str = f"{float(prob):.4f}" if pd.notna(prob) else "—"
                except Exception:
                    prob_str = "—"

                ret20 = row.get("Zysk 20 sesji", np.nan)
                try:
                    ret20_str = f"{float(ret20):.2f}%" if pd.notna(ret20) else "—"
                except Exception:
                    ret20_str = "—"

                return f"{i+1}. {ticker} | {date_str} | prob={prob_str} | 20d={ret20_str}"

            picked_idx = st.selectbox(
                "Wybierz rekord z tabeli PO:",
                options=options_idx,
                format_func=format_option,
                key="tab3_pick_row_idx",
            )

            chosen_row = df_pick.loc[int(picked_idx)]
            st.markdown("#### Firma do analizy:")
            st.write(chosen_row[["Ticker", "Data notowania", "Prawdopodobieństwo"]].to_dict())

            _render_test_price_chart_for_selected_row(df_test, chosen_row)

        # --------------------------------------------------------
        # (F) Metryki TEST + porównanie z VALIDATE (z meta)
        # --------------------------------------------------------
        st.markdown("### Podsumowanie testu (TEST) + porównanie do VALIDATE (z meta)")

        prices_cache_test = _build_prices_cache_for_returns(df_test)
        sel_metrics = compute_selection_metrics(df_sel_filtered, df_test_rank_full, y_col="y_true", score_col="prob")
        mean_returns = _compute_expost_return_means_for_selection(df_sel_filtered, prices_cache=prices_cache_test, horizons=(20, 60, 120))

        test_summary = {
            "precision": float(sel_metrics.get("precision", np.nan)),
            "n_selected": float(sel_metrics.get("n_selected", np.nan)),
            "avg_ret_20": float(mean_returns.get("avg_ret_20", np.nan)),
            "avg_ret_60": float(mean_returns.get("avg_ret_60", np.nan)),
            "avg_ret_120": float(mean_returns.get("avg_ret_120", np.nan)),
            "avg_ret_end": float(mean_returns.get("avg_ret_end", np.nan)),
        }
        st.session_state["tab3_test_summary"] = test_summary

        val_summary = meta_sel.get("val_summary") or {}

        df_cmp = pd.DataFrame([
            {
                "zbiór": "VALIDATE (z meta modelu)",
                "precision": val_summary.get("precision"),
                "n_selected": val_summary.get("n_selected"),
                "avg_ret_20": val_summary.get("avg_ret_20"),
                "avg_ret_60": val_summary.get("avg_ret_60"),
                "avg_ret_120": val_summary.get("avg_ret_120"),
                "avg_ret_end": val_summary.get("avg_ret_end"),
            },
            {
                "zbiór": "TEST (obliczone)",
                "precision": test_summary.get("precision"),
                "n_selected": test_summary.get("n_selected"),
                "avg_ret_20": test_summary.get("avg_ret_20"),
                "avg_ret_60": test_summary.get("avg_ret_60"),
                "avg_ret_120": test_summary.get("avg_ret_120"),
                "avg_ret_end": test_summary.get("avg_ret_end"),
            },
        ])

        df_cmp_view = _test_summary_ui(df_cmp)
        st.dataframe(df_cmp_view, width="stretch", hide_index=True)

        st.caption(
            "To porównanie jest prostą diagnostyką driftu: "
            "czy wyniki ex post (20/60/120) oraz precision na TEST są podobne do VALIDATE "
            "(zapisanego w momencie zapisu modelu)."
        )
