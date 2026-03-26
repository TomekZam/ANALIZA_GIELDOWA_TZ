# app/ml/ml_datasets.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict

import pandas as pd
import streamlit as st


# ============================================================
# SESSION STATE KEYS (kontrakt)
# ============================================================

SSK: Dict[str, str] = {
    # źródło danych market-wide (tworzone w data_overview.py)
    "df_market_all": "do_df_market_all",

    # kanoniczne datasety ML (tworzone tutaj, współdzielone przez ML-01/02/03)
    "df_ml_train": "do_df_market_train",
    "df_ml_val": "do_df_market_val",
    "df_ml_test": "do_df_market_test",

    # metadane (żeby wiedzieć, jakim split’em powstały)
    "ml_split_meta": "do_ml_split_meta",
}


# ============================================================
# DEFAULT SPLIT (zgodnie z ADR-011 9.1)
# ============================================================
# TRAIN: 1990-01-01 .. 2015-12-31
# VAL:   2016-01-01 .. 2019-12-31  (domyślnie BEZ NAKŁADANIA z TRAIN)
# TEST:  2020-01-01 .. 2025-12-31

DEFAULT_TRAIN_START = "1990-01-01"
DEFAULT_TRAIN_END = "2015-12-31"
DEFAULT_VAL_START = "2016-01-01"
DEFAULT_VAL_END = "2019-12-31"
DEFAULT_TEST_START = "2020-01-01"
DEFAULT_TEST_END = "2025-12-31"


DEFAULT_DATE_COL = "trade_date"


@dataclass(frozen=True)
class MLSplitConfig:
    date_col: str = DEFAULT_DATE_COL

    train_start: str = DEFAULT_TRAIN_START
    train_end: str = DEFAULT_TRAIN_END

    val_start: str = DEFAULT_VAL_START
    val_end: str = DEFAULT_VAL_END

    test_start: str = DEFAULT_TEST_START
    test_end: str = DEFAULT_TEST_END

    # czy trzymać kopię kolumny date_col jako datetime w wynikach
    keep_datetime_date_col: bool = True


def _to_dt(x: str) -> pd.Timestamp:
    return pd.to_datetime(x, errors="raise")


def _normalize_dates(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
    if date_col not in df.columns:
        raise ValueError(f"[ml_datasets] Brak kolumny daty '{date_col}' w df_market_all.")

    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
    out = out.dropna(subset=[date_col]).sort_values(date_col)
    return out


def _split_3way(
    df: pd.DataFrame,
    cfg: MLSplitConfig,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict]:
    """
    Zwraca: (train_df, val_df, test_df, meta)
    """
    df = _normalize_dates(df, cfg.date_col)

    train_start = _to_dt(cfg.train_start)
    train_end = _to_dt(cfg.train_end)

    val_start = _to_dt(cfg.val_start)
    val_start_str = cfg.val_start


    val_end = _to_dt(cfg.val_end)

    test_start = _to_dt(cfg.test_start)
    test_end = _to_dt(cfg.test_end)

    # --- sanity checks ---
    warnings = []
    if not (train_start <= train_end):
        raise ValueError("[ml_datasets] train_start > train_end.")
    if not (val_start <= val_end):
        raise ValueError("[ml_datasets] val_start > val_end.")
    if not (test_start <= test_end):
        raise ValueError("[ml_datasets] test_start > test_end.")

    # overlap check (nie blokujemy, ale raportujemy)
    if val_start <= train_end:
        warnings.append(
            "VAL nakłada się na TRAIN (val_start <= train_end). "
            "To grozi leakage i dublowaniem obserwacji. "
            "Zalecane: val_start = train_end + 1 dzień."
        )
    if test_start <= val_end:
        warnings.append(
            "TEST nakłada się na VAL (test_start <= val_end). "
            "Zalecane: test_start = val_end + 1 dzień."
        )

    # --- split ---
    train_mask = (df[cfg.date_col] >= train_start) & (df[cfg.date_col] <= train_end)
    val_mask = (df[cfg.date_col] >= val_start) & (df[cfg.date_col] <= val_end)
    test_mask = (df[cfg.date_col] >= test_start) & (df[cfg.date_col] <= test_end)

    train_df = df.loc[train_mask].copy()
    val_df = df.loc[val_mask].copy()
    test_df = df.loc[test_mask].copy()

    if not cfg.keep_datetime_date_col:
        # w wielu miejscach UI masz już stringi dat; tu pozwalamy zachować spójność
        for dfx in (train_df, val_df, test_df):
            dfx[cfg.date_col] = dfx[cfg.date_col].dt.strftime("%Y-%m-%d")

    meta = {
        "date_col": cfg.date_col,
        "train_start": cfg.train_start,
        "train_end": cfg.train_end,
        "val_start": val_start_str,
        "val_end": cfg.val_end,
        "test_start": cfg.test_start,
        "test_end": cfg.test_end,
        "keep_datetime_date_col": cfg.keep_datetime_date_col,
        "n_all": int(len(df)),
        "n_train": int(len(train_df)),
        "n_val": int(len(val_df)),
        "n_test": int(len(test_df)),
        "min_date_all": str(df[cfg.date_col].min().date()) if len(df) else None,
        "max_date_all": str(df[cfg.date_col].max().date()) if len(df) else None,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "warnings": warnings,
    }

    return train_df, val_df, test_df, meta


def ml_datasets_ready() -> bool:
    """Czy kanoniczne datasety ML są już w session_state?"""
    return (
        SSK["df_ml_train"] in st.session_state
        and SSK["df_ml_val"] in st.session_state
        and SSK["df_ml_test"] in st.session_state
        and st.session_state.get(SSK["df_ml_train"]) is not None
        and st.session_state.get(SSK["df_ml_val"]) is not None
        and st.session_state.get(SSK["df_ml_test"]) is not None
    )


def ensure_ml_datasets(cfg: Optional[MLSplitConfig] = None, force_rebuild: bool = False) -> Dict:
    """
    Buduje i cache'uje df_train / df_val / df_test w session_state.

    - jeśli już istnieją i force_rebuild=False -> nic nie robi
    - jeśli force_rebuild=True -> przebudowuje
    - zwraca meta (w tym warningi i liczności)
    """
    if cfg is None:
        cfg = MLSplitConfig()

    if ml_datasets_ready() and not force_rebuild:
        return st.session_state.get(SSK["ml_split_meta"], {})

    df_all = st.session_state.get(SSK["df_market_all"])
    if not isinstance(df_all, pd.DataFrame) or df_all.empty:
        raise ValueError(
            "[ml_datasets] Brak df_market_all w session_state. "
            "Najpierw załaduj dane w 'Podgląd danych' (data_overview.py)."
        )

    df_train, df_val, df_test, meta = _split_3way(df_all, cfg)

    st.session_state[SSK["df_ml_train"]] = df_train
    st.session_state[SSK["df_ml_val"]] = df_val
    st.session_state[SSK["df_ml_test"]] = df_test
    st.session_state[SSK["ml_split_meta"]] = meta

    return meta


def get_ml_datasets() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict]:
    """
    Zwraca (df_train, df_val, df_test, meta).
    Jeśli nie istnieją -> buduje domyślnie.
    """
    meta = ensure_ml_datasets()
    return (
        st.session_state[SSK["df_ml_train"]],
        st.session_state[SSK["df_ml_val"]],
        st.session_state[SSK["df_ml_test"]],
        meta,
    )


def clear_ml_datasets() -> None:
    """Czyści cache datasetów ML (np. po zmianie zakresu danych w data_overview)."""
    for k in ("df_ml_train", "df_ml_val", "df_ml_test", "ml_split_meta"):
        sk = SSK[k]
        if sk in st.session_state:
            st.session_state[sk] = None
