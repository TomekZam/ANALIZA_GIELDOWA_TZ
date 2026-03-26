# data_provider.py
from __future__ import annotations

import os
from typing import Any, Dict, Literal, Optional, Sequence, Tuple

import pandas as pd

from config.app_params import get_param

DataMode = Literal["csv", "db"]

# tryb pracy providera ustalany LENIWIE, ale tylko raz (na podstawie runtime flags)
_DATA_MODE: Optional[DataMode] = None

# cache per (funkcja, tryb, parametry)
_CACHE: Dict[Tuple[Any, ...], pd.DataFrame] = {}


# ------------------------------------------------------------
# Tryb pracy – provider NIE testuje bazy, tylko czyta runtime flags
# ------------------------------------------------------------

def init_data_mode() -> DataMode:
    """
    Ustala tryb pracy providera na podstawie parametrów runtime:
    - APP_TEST_ON_CSV_FILES (wymusza CSV)
    - DB_CONNECTION_AVAILABLE (jeśli False => CSV fallback)

    Zasada:
    - jeśli APP_TEST_ON_CSV_FILES=True => zawsze CSV
    - jeśli APP_TEST_ON_CSV_FILES=False => DB tylko gdy DB_CONNECTION_AVAILABLE=True,
      w przeciwnym razie CSV

    UWAGA: ta funkcja NIE sprawdza połączenia do bazy. To ma być zrobione 1x w app.py.
    """
    global _DATA_MODE
    if _DATA_MODE is not None:
        return _DATA_MODE

    app_test = bool(get_param("APP_TEST_ON_CSV_FILES"))
    db_ok = bool(get_param("DB_CONNECTION_AVAILABLE"))

    if app_test:
        _DATA_MODE = "csv"
    else:
        _DATA_MODE = "db" if db_ok else "csv"

    return _DATA_MODE


def reset_provider_cache() -> None:
    """Diagnostyka/debug: czyści cache providera."""
    _CACHE.clear()


def get_data_source_label() -> str:
    """Do UI: zwraca czytelny opis źródła danych."""
    mode = init_data_mode()
    return "CSV" if mode == "csv" else "DB"


# ------------------------------------------------------------
# Pomocnicze: CSV paths + filtry
# ------------------------------------------------------------

def _csv_path(param_dir: str, param_file: str) -> str:
    base = get_param(param_dir)
    name = get_param(param_file)
    return os.path.join(base, name)

def get_asset_path(param_dir: str, param_file: str) -> str:
    """
    Rozwiązuje ścieżkę do assetów UI (np. logo),
    dokładnie tym samym wzorcem co CSV.
    """
    base = get_param(param_dir)
    name = get_param(param_file)
    return os.path.join(base, name)


def _normalize_ids(company_ids: Optional[Sequence[int]]) -> Optional[Tuple[int, ...]]:
    if company_ids is None:
        return None
    ids = sorted(set(int(x) for x in company_ids))
    return tuple(ids)


def _normalize_date(d: Optional[str]) -> Optional[pd.Timestamp]:
    if d is None:
        return None
    s = str(d).strip()
    if s == "":
        return None
    return pd.to_datetime(s, errors="coerce")


def _apply_optional_where_filters_csv(
    df: pd.DataFrame,
    company_ids: Optional[Tuple[int, ...]],
    date_from: Optional[str],
    date_to: Optional[str],
    date_col: str = "trade_date",
) -> pd.DataFrame:
    if df.empty:
        return df

    if company_ids is not None and "company_id" in df.columns:
        df = df[df["company_id"].isin(company_ids)]

    d_from = _normalize_date(date_from)
    d_to = _normalize_date(date_to)

    if (d_from is not None or d_to is not None) and date_col in df.columns:
        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        if d_from is not None:
            df = df[df[date_col] >= d_from]
        if d_to is not None:
            df = df[df[date_col] <= d_to]

    return df


def _cache_get(key: Tuple[Any, ...]) -> Optional[pd.DataFrame]:
    return _CACHE.get(key)


def _cache_set(key: Tuple[Any, ...], df: pd.DataFrame) -> pd.DataFrame:
    _CACHE[key] = df
    return df


# ------------------------------------------------------------
# Public API
# ------------------------------------------------------------

def get_companies(company_ids: Optional[Sequence[int]] = None) -> pd.DataFrame:
    """
    companies
    - company_ids=None => brak ograniczenia WHERE
    """
    mode = init_data_mode()
    ids_t = _normalize_ids(company_ids)

    cache_key = ("companies", mode, ids_t)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    if mode == "csv":
        fp = _csv_path("LOAD_DATA_WSE_PATH", "LOAD_DATA_WSE_COMPANIES")
        df = pd.read_csv(fp)
        if ids_t is not None:
            df = df[df["company_id"].isin(ids_t)]
        return _cache_set(cache_key, df)

    # mode == "db"
    from core.db import get_engine

    engine = get_engine()
    where = []
    params: Tuple[Any, ...] = tuple()

    if ids_t is not None:
        placeholders = ",".join(["?"] * len(ids_t))
        where.append(f"company_id IN ({placeholders})")
        params += ids_t

    query = "SELECT * FROM companies"
    if where:
        query += " WHERE " + " AND ".join(where)

    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=params)

    return _cache_set(cache_key, df)


def get_prices_daily(
    company_ids: Optional[Sequence[int]] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> pd.DataFrame:
    """
    prices_daily (+ ticker jeśli istnieje w źródle; dla DB robimy JOIN)
    - company_ids=None => brak WHERE po company_id
    - date_from/date_to optional => brak ograniczeń jeśli brak parametru
    """
    mode = init_data_mode()
    ids_t = _normalize_ids(company_ids)

    cache_key = ("prices_daily", mode, ids_t, date_from, date_to)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    if mode == "csv":
        fp = _csv_path("LOAD_DATA_WSE_PATH", "LOAD_DATA_WSE_PRICES_DAILY")
        df = pd.read_csv(fp)

        # jeśli CSV nie ma tickera, a chcesz go mieć spójnie z DB — dołącz z companies
        if "ticker" not in df.columns and "company_id" in df.columns:
            companies = get_companies(None)
            if {"company_id", "ticker"}.issubset(companies.columns):
                df = df.merge(companies[["company_id", "ticker"]], on="company_id", how="left")

        df = _apply_optional_where_filters_csv(df, ids_t, date_from, date_to, date_col="trade_date")
        return _cache_set(cache_key, df)

    # mode == "db"
    from core.db import get_engine

    engine = get_engine()
    where = []
    params: Tuple[Any, ...] = tuple()

    if ids_t is not None:
        placeholders = ",".join(["?"] * len(ids_t))
        where.append(f"p.company_id IN ({placeholders})")
        params += ids_t

    if date_from:
        where.append("p.trade_date >= ?")
        params += (date_from,)
    if date_to:
        where.append("p.trade_date <= ?")
        params += (date_to,)

    query = """
        SELECT p.*, c.ticker
        FROM prices_daily p
        JOIN companies c ON c.company_id = p.company_id
    """
    if where:
        query += " WHERE " + " AND ".join(where)

    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=params)

    return _cache_set(cache_key, df)


def get_indicators_daily(
    company_ids: Optional[Sequence[int]] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> pd.DataFrame:
    """
    indicators_daily (+ ticker; DB JOIN)
    - company_ids=None => brak WHERE po company_id
    - date_from/date_to optional
    """
    mode = init_data_mode()
    ids_t = _normalize_ids(company_ids)

    cache_key = ("indicators_daily", mode, ids_t, date_from, date_to)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    if mode == "csv":
        fp = _csv_path("LOAD_DATA_WSE_PATH", "LOAD_DATA_WSE_IND_DAILY")
        df = pd.read_csv(fp)

        if "ticker" not in df.columns and "company_id" in df.columns:
            companies = get_companies(None)
            if {"company_id", "ticker"}.issubset(companies.columns):
                df = df.merge(companies[["company_id", "ticker"]], on="company_id", how="left")

        df = _apply_optional_where_filters_csv(df, ids_t, date_from, date_to, date_col="trade_date")
        return _cache_set(cache_key, df)

    # mode == "db"
    from core.db import get_engine

    engine = get_engine()
    where = []
    params: Tuple[Any, ...] = tuple()

    if ids_t is not None:
        placeholders = ",".join(["?"] * len(ids_t))
        where.append(f"i.company_id IN ({placeholders})")
        params += ids_t

    if date_from:
        where.append("i.trade_date >= ?")
        params += (date_from,)
    if date_to:
        where.append("i.trade_date <= ?")
        params += (date_to,)

    query = """
        SELECT i.*, c.ticker
        FROM indicators_daily i
        JOIN companies c ON c.company_id = i.company_id
    """
    if where:
        query += " WHERE " + " AND ".join(where)

    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=params)

    return _cache_set(cache_key, df)


def get_indicators_dictionary() -> pd.DataFrame:
    """
    indicators_dictionary (bez WHERE)
    """
    mode = init_data_mode()

    cache_key = ("indicators_dictionary", mode)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    if mode == "csv":
        fp = _csv_path("LOAD_DATA_WSE_PATH", "LOAD_DATA_WSE_IND_DICT")
        df = pd.read_csv(fp)
        return _cache_set(cache_key, df)

    from core.db import get_engine

    engine = get_engine()
    query = "SELECT * FROM indicators_dictionary"
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)

    return _cache_set(cache_key, df)



from typing import Iterable, List

def parse_tickers(tickers_csv: str | None) -> List[str]:
    """
    Parsuje tickery z formatu: "1AT, 11B, TEN" -> ["1AT","11B","TEN"]
    Obsługuje None / pusty string.
    """
    if not tickers_csv:
        return []
    return [t.strip() for t in tickers_csv.split(",") if t.strip()]


def get_company_ids_for_tickers(tickers: Iterable[str]) -> tuple[int, ...]:
    """
    Centralne mapowanie tickerów -> company_id.
    Zwraca posortowaną krotkę ID (stabilne pod cache).
    """
    tickers_list = sorted({str(t).strip() for t in tickers if str(t).strip()})
    if not tickers_list:
        return tuple()

    companies = get_companies(None)
    if companies.empty or "ticker" not in companies.columns or "company_id" not in companies.columns:
        return tuple()

    # Mapowanie (case-sensitive jak w danych; jeśli chcesz case-insensitive – daj znać)
    ids = companies.loc[companies["ticker"].isin(tickers_list), "company_id"].dropna().astype(int).tolist()
    return tuple(sorted(set(ids)))


def get_company_ids_for_tickers_csv(tickers_csv: str | None) -> tuple[int, ...]:
    """
    Wariant convenience: wejście jako string "1AT, 11B, TEN".
    """
    return get_company_ids_for_tickers(parse_tickers(tickers_csv))


def get_prices_daily_date_range(
    company_ids: Optional[Sequence[int]] = None,
) -> tuple[Optional[str], Optional[str]]:
    """
    Zwraca (min_trade_date, max_trade_date) dla prices_daily.
    - company_ids=None => cały zbiór
    - daty w formacie 'YYYY-MM-DD'
    """
    mode = init_data_mode()
    ids_t = _normalize_ids(company_ids)

    cache_key = ("prices_daily_date_range", mode, ids_t)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # CSV
    if mode == "csv":
        fp = _csv_path("LOAD_DATA_WSE_PATH", "LOAD_DATA_WSE_PRICES_DAILY")
        df = pd.read_csv(fp)

        if ids_t is not None and "company_id" in df.columns:
            df = df[df["company_id"].isin(ids_t)]

        if "trade_date" not in df.columns or df.empty:
            return _cache_set(cache_key, (None, None))

        td = pd.to_datetime(df["trade_date"], errors="coerce").dropna()
        if td.empty:
            return _cache_set(cache_key, (None, None))

        return _cache_set(
            cache_key,
            (td.min().date().isoformat(), td.max().date().isoformat()),
        )

    # DB
    from core.db import get_engine

    engine = get_engine()
    where = []
    params: tuple[Any, ...] = ()

    if ids_t is not None:
        placeholders = ",".join(["?"] * len(ids_t))
        where.append(f"company_id IN ({placeholders})")
        params += ids_t

    query = "SELECT MIN(trade_date) AS d_min, MAX(trade_date) AS d_max FROM prices_daily"
    if where:
        query += " WHERE " + " AND ".join(where)

    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=params)

    if df.empty or pd.isna(df.loc[0, "d_min"]) or pd.isna(df.loc[0, "d_max"]):
        return _cache_set(cache_key, (None, None))

    return _cache_set(
        cache_key,
        (
            pd.to_datetime(df.loc[0, "d_min"]).date().isoformat(),
            pd.to_datetime(df.loc[0, "d_max"]).date().isoformat(),
        ),
    )


def get_last_prices_for_company_ids(company_ids: Sequence[int]) -> pd.DataFrame:
    """
    Zwraca ostatni dostępny rekord notowań (close/volume) per spółka + change (%).
    Kontrakt (DB i CSV): company_id, ticker, company_name, trade_date, close_price, volume, change
    """
    mode = init_data_mode()
    ids_t = _normalize_ids(company_ids)

    if ids_t is None or len(ids_t) == 0:
        return pd.DataFrame(
            columns=[
                "company_id",
                "ticker",
                "company_name",
                "trade_date",
                "close_price",
                "volume",
                "change",
            ]
        )

    cache_key = ("last_prices", mode, ids_t)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # ============================================================
    # CSV MODE – liczone w pandas (bez DB!)
    # ============================================================
    if mode == "csv":
        prices = get_prices_daily(company_ids=ids_t)
        companies = get_companies(company_ids=ids_t)

        if not isinstance(prices, pd.DataFrame) or prices.empty:
            df_empty = pd.DataFrame(
                columns=[
                    "company_id",
                    "ticker",
                    "company_name",
                    "trade_date",
                    "close_price",
                    "volume",
                    "change",
                ]
            )
            return _cache_set(cache_key, df_empty)

        # standaryzacja daty
        if "trade_date" in prices.columns:
            prices = prices.copy()
            prices["trade_date"] = pd.to_datetime(prices["trade_date"], errors="coerce")

        # sortowanie, żeby tail(1) brał faktycznie ostatni dzień
        if {"company_id", "trade_date"}.issubset(prices.columns):
            prices = prices.sort_values(["company_id", "trade_date"])

        # policz change na bazie poprzedniego close
        prices = prices.copy()
        prices["prev_close"] = prices.groupby("company_id")["close_price"].shift(1)
        prices["change"] = ((prices["close_price"] / prices["prev_close"]) - 1.0) * 100.0
        prices["change"] = prices["change"].round(2)

        # ostatnia sesja per spółka
        last_rows = prices.groupby("company_id").tail(1).copy()

        # ------------------------------------------------------------
        # KONTRAKT: CSV ma zwrócić te same kolumny co DB:
        # company_id, ticker, company_name, trade_date, close_price, volume, change
        # UWAGA: prices może JUŻ mieć ticker (bo get_prices_daily() w CSV robi JOIN z companies).
        # Jeśli zrobimy merge z companies zawierającym ticker -> powstaną ticker_x/ticker_y.
        # Dlatego:
        # - jeśli ticker jest już w last_rows -> dogrywamy tylko company_name
        # - jeśli ticker nie ma -> dogrywamy ticker + company_name
        # ------------------------------------------------------------
        if not isinstance(companies, pd.DataFrame) or companies.empty:
            companies = pd.DataFrame(columns=["company_id", "ticker", "company_name"])

        need_cols = ["company_id"]
        if "ticker" not in last_rows.columns:
            need_cols.append("ticker")
        need_cols.append("company_name")

        keep = [c for c in need_cols if c in companies.columns]

        df = last_rows.merge(
            companies[keep],
            on="company_id",
            how="left",
            suffixes=("", "_c"),
        )

        if "ticker" not in df.columns and "ticker_c" in df.columns:
            df = df.rename(columns={"ticker_c": "ticker"})
        if "company_name" not in df.columns and "company_name_c" in df.columns:
            df = df.rename(columns={"company_name_c": "company_name"})

        for c in ("ticker_c", "company_name_c"):
            if c in df.columns:
                df = df.drop(columns=[c])

        cols = [
            "company_id",
            "ticker",
            "company_name",
            "trade_date",
            "close_price",
            "volume",
            "change",
        ]

        missing = [c for c in cols if c not in df.columns]
        if missing:
            raise RuntimeError(
                f"[data_provider.get_last_prices_for_company_ids][CSV] "
                f"Data contract violated. Missing columns: {missing}. "
                f"Available columns: {list(df.columns)}"
            )

        return _cache_set(cache_key, df[cols])

    # ============================================================
    # DB MODE – szybkie zapytanie SQL
    # ============================================================
    from core.db import get_engine

    placeholders = ",".join(["?"] * len(ids_t))

    query = f"""
    WITH ranked AS (
        SELECT
            p.company_id,
            c.ticker,
            c.company_name,
            p.trade_date,
            p.close_price,
            p.volume,
            LAG(p.close_price) OVER (
                PARTITION BY p.company_id
                ORDER BY p.trade_date
            ) AS prev_close,
            ROW_NUMBER() OVER (
                PARTITION BY p.company_id
                ORDER BY p.trade_date DESC
            ) AS rn
        FROM prices_daily p
        JOIN companies c
            ON c.company_id = p.company_id
        WHERE p.company_id IN ({placeholders})
    )
    SELECT
        company_id,
        ticker,
        company_name,
        trade_date,
        close_price,
        volume,
        ROUND((close_price / prev_close - 1) * 100, 2) AS change
    FROM ranked
    WHERE rn = 1
    """

    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=ids_t)

    return _cache_set(cache_key, df)



