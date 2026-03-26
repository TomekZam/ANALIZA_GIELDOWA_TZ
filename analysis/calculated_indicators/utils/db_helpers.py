# analysis/calculated_indicators/utils/db_helpers.py
"""
Helpery DB dla wskaźników wyliczanych lokalnie (calculated indicators).

Założenia (potwierdzone):
- logiczny klucz indicators_daily = (company_id, trade_date)
- 1 rekord prices_daily ⇔ 1 rekord indicators_daily (docelowo)
- wskaźniki mogą być:
  * brak rekordu w indicators_daily  -> INSERT
  * rekord istnieje, kolumna NULL    -> UPDATE
  * rekord + wartość istnieje        -> SKIP

Plik zaprojektowany tak, aby obsługiwać:
- initial fill (wszystko NULL / brak rekordów)
- incremental fill (nowe dni po imporcie notowań)
"""




from typing import Iterable
import pandas as pd
from sqlalchemy import text

from core.db import get_engine
from analysis.calculated_indicators.utils.calc_flags import flag_for


# ------------------------------------------------------------------
# READ HELPERS
# ------------------------------------------------------------------

def fetch_companies(company_ids: Iterable[int] | None = None) -> pd.DataFrame:
    """
    Pobiera listę aktywnych spółek.
    Zwraca: company_id, ticker
    """
    engine = get_engine()

    base_sql = """
        SELECT company_id, ticker
        FROM companies
        WHERE is_active = 1
    """

    params = {}

    if company_ids:
        placeholders = []
        for idx, cid in enumerate(company_ids):
            key = f"cid_{idx}"
            placeholders.append(f":{key}")
            params[key] = int(cid)

        in_clause = ", ".join(placeholders)
        sql = base_sql + f" AND company_id IN ({in_clause})"
    else:
        sql = base_sql

    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def fetch_prices(company_id: int, date_from=None) -> pd.DataFrame:
    """
    Pobiera ceny dzienne (EOD) dla spółki.
    """
    engine = get_engine()

    sql = """
        SELECT trade_date, close_price, volume, high_price, low_price
        FROM prices_daily
        WHERE company_id = :company_id
    """

    params = {"company_id": company_id}

    if date_from:
        sql += " AND trade_date >= :date_from"
        params["date_from"] = date_from

    sql += " ORDER BY trade_date"

    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def fetch_indicator_state(company_id: int, indicator_code: str) -> pd.DataFrame:
    """
    Zwraca:
    trade_date | <indicator_code>

    gdzie:
    - NULL  -> rekord istnieje, ale brak wartości
    - NaN   -> brak rekordu w indicators_daily
    """
    engine = get_engine()

    sql = f"""
        SELECT
            p.trade_date,
            i.{indicator_code}
        FROM prices_daily p
        LEFT JOIN indicators_daily i
            ON i.company_id = p.company_id
           AND i.trade_date = p.trade_date
        WHERE p.company_id = :company_id
        ORDER BY p.trade_date
    """

    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params={"company_id": company_id})


def fetch_indicator_values(
    company_id: int,
    indicator_codes: list[str],
) -> pd.DataFrame:
    """
    Pobiera wskazane wskaźniki z indicators_daily dla jednej spółki.
    """
    engine = get_engine()

    cols_sql = ", ".join(indicator_codes)

    sql = f"""
        SELECT
            trade_date,
            {cols_sql}
        FROM indicators_daily
        WHERE company_id = :company_id
        ORDER BY trade_date
    """

    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params={"company_id": company_id})


# ------------------------------------------------------------------
# WRITE HELPERS
# ------------------------------------------------------------------

def insert_missing_indicator_rows(
    company_id: int,
    trade_dates: list,
) -> None:
    """
    Wstawia brakujące rekordy (company_id, trade_date) do indicators_daily.
    Chroni przed duplikatami (PRIMARY KEY).
    """
    if not trade_dates:
        return

    engine = get_engine()

    sql = """
        INSERT INTO indicators_daily (company_id, trade_date, created_at)
        SELECT :company_id, :trade_date, GETDATE()
        WHERE NOT EXISTS (
            SELECT 1
            FROM indicators_daily
            WHERE company_id = :company_id
              AND trade_date = :trade_date
        )
    """

    with engine.begin() as conn:
        for trade_date in trade_dates:
            conn.execute(
                text(sql),
                {
                    "company_id": company_id,
                    "trade_date": trade_date,
                },
            )


def update_indicator_values(
    company_id: int,
    indicator_code: str,
    df: pd.DataFrame,
    bit: int,
) -> int:
    """
    Aktualizuje indicators_daily TYLKO gdy:
    - rekord istnieje
    - kolumna wskaźnika jest NULL
    - nowa wartość jest NOT NULL

    Zwraca: liczbę faktycznie zaktualizowanych wierszy.
    """

    if df.empty:
        return 0

    # 1️⃣ TWARDY FILTR: usuwamy wszystkie NULL-e
    df = df[~df[indicator_code].isna()]
    if df.empty:
        # KLUCZOWY EARLY EXIT – NIC DO ROBIENIA
        return 0

    engine = get_engine()

    # 2️⃣ Batch przez temp table (1 round-trip)
    sql_create_tmp = """
        CREATE TABLE #vals (
            trade_date DATE PRIMARY KEY,
            val FLOAT
        );
    """

    sql_insert_tmp = """
        INSERT INTO #vals (trade_date, val)
        VALUES (:trade_date, :val);
    """

    sql_update = f"""
        UPDATE d
        SET
            d.{indicator_code} = v.val,
            d.calc_flags = ISNULL(d.calc_flags, 0) | CAST(:bit AS BIGINT),
            d.modified_at = GETDATE()
        FROM indicators_daily d
        JOIN #vals v ON v.trade_date = d.trade_date
        WHERE d.company_id = :company_id
          AND d.{indicator_code} IS NULL;
    """

    sql_drop_tmp = "DROP TABLE #vals;"

    rows_updated = 0

    with engine.begin() as conn:
        conn.execute(text(sql_create_tmp))

        conn.execute(
            text(sql_insert_tmp),
            [
                {"trade_date": r["trade_date"], "val": r[indicator_code]}
                for _, r in df.iterrows()
            ],
        )

        result = conn.execute(
            text(sql_update),
            {
                "company_id": company_id,
                "bit": bit,
            },
        )
        rows_updated = result.rowcount or 0

        conn.execute(text(sql_drop_tmp))

    return rows_updated




# ============================================================
# NOT COMPUTABLE FLAGS HELPERS
# ============================================================


def mark_not_computable(
    company_id: int,
    indicator_code: str,
    trade_dates: list,
) -> int:
    """
    Ustawia flagę 'NOT COMPUTABLE' (bitową) dla danego wskaźnika
    i listy trade_dates.

    Zwraca liczbę faktycznie oznaczonych wierszy.
    """
    if not trade_dates:
        return 0

    bit = flag_for(indicator_code)
    engine = get_engine()

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE #dates (
                trade_date DATE PRIMARY KEY
            );
        """))

        conn.execute(
            text("INSERT INTO #dates (trade_date) VALUES (:d)"),
            [{"d": d} for d in trade_dates],
        )

        result = conn.execute(text("""
            UPDATE d
            SET d.calc_flags = ISNULL(d.calc_flags, 0) | CAST(:bit AS BIGINT)
            FROM indicators_daily d
            JOIN #dates x
              ON x.trade_date = d.trade_date
            WHERE d.company_id = :company_id
              AND (d.calc_flags & :bit) = 0
        """), {
            "company_id": company_id,
            "bit": bit,
        })

        conn.execute(text("DROP TABLE #dates"))

        return result.rowcount or 0


def filter_dates_not_flagged(
    company_id: int,
    trade_dates: list,
    bit: int,
) -> list:
    """
    Zwraca TYLKO te trade_dates, które NIE mają ustawionej
    flagi 'NOT COMPUTABLE' dla danego bitu.

    To MUSI być użyte PRZED indicator.compute().
    """
    if not trade_dates:
        return []

    engine = get_engine()

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE #dates (
                trade_date DATE PRIMARY KEY
            );
        """))

        conn.execute(
            text("INSERT INTO #dates (trade_date) VALUES (:d)"),
            [{"d": d} for d in trade_dates],
        )

        rows = conn.execute(text("""
            SELECT x.trade_date
            FROM #dates x
            JOIN indicators_daily d
              ON d.company_id = :company_id
             AND d.trade_date = x.trade_date
            WHERE (d.calc_flags & :bit) = 0
        """), {
            "company_id": company_id,
            "bit": bit,
        }).fetchall()

        conn.execute(text("DROP TABLE #dates"))

    return [r[0] for r in rows]

def fetch_company_ids_needing_indicator(
    indicator_code: str,
    bit: int,
    company_ids: Iterable[int] | None = None,
) -> list[int]:
    """
    Zwraca company_id, dla których istnieje CO NAJMNIEJ JEDEN trade_date taki, że:
    - wskaźnik jest do uzupełnienia (kolumna indicator_code jest NULL albo brak rekordu),
    Dzięki temu pipeline nie iteruje po całej bazie, tylko po spółkach z pracą do wykonania.
    """
    engine = get_engine()

    # bazowo: aktywne spółki
    base_sql = f"""
        SELECT DISTINCT c.company_id
        FROM companies c
        JOIN prices_daily p
          ON p.company_id = c.company_id
        LEFT JOIN indicators_daily i
          ON i.company_id = p.company_id
         AND i.trade_date = p.trade_date
        WHERE c.is_active = 1
          AND (
                i.trade_date IS NULL         -- brak rekordu w indicators_daily
                OR i.{indicator_code} IS NULL -- rekord jest, ale wskaźnik NULL
              )
    """

    params = {}

    if company_ids:
        placeholders = []
        for idx, cid in enumerate(company_ids):
            key = f"cid_{idx}"
            placeholders.append(f":{key}")
            params[key] = int(cid)

        in_clause = ", ".join(placeholders)
        sql = base_sql + f" AND c.company_id IN ({in_clause})"
    else:
        sql = base_sql

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).fetchall()

    return [r[0] for r in rows]




def sync_calc_flags_for_indicator(indicator_code: str) -> None:
    """
    Synchronizuje bit calc_flags dla jednego wskaźnika
    zgodnie z semantyką ADR-016:
    - kolumna NOT NULL  => bit = 1
    - kolumna NULL      => bit = 0
    """
    bit = flag_for(indicator_code)

    sql = f"""
    UPDATE d
    SET d.calc_flags =
        CASE
            WHEN d.{indicator_code} IS NOT NULL
                THEN d.calc_flags | {bit}
            ELSE
                d.calc_flags & ~{bit}
        END
    FROM dbo.indicators_daily d
    """

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(sql))


def fetch_indicator_columns() -> list[str]:
    """
    Zwraca listę nazw kolumn wskaźników w tabeli indicators_daily
    (bez kolumn technicznych).
    """
    engine = get_engine()

    sql = """
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'indicators_daily'
          AND COLUMN_NAME NOT IN (
              'company_id',
              'trade_date',
              'created_at',
              'calc_flags'
          )
    """

    with engine.connect() as conn:
        rows = conn.execute(text(sql)).fetchall()

    return [row[0] for row in rows]

