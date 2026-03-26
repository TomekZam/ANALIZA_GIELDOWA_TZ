# etl/import_companies.py

"""
Import danych spółek do systemu AnGG – KROK 2.

Zakres:
- wczytanie CSV
- walidacja
- ODCZYT danych z DB
- porównanie CSV vs DB

UWAGA:
Ten etap NIE zapisuje danych do bazy.
"""

import logging
import pandas as pd

from config.etl import COMPANIES_CSV_PATH
from sqlalchemy import text
from core.db import get_engine  # <- korzystamy ze wspólnego kodu DB


REQUIRED_COLUMNS = ["ticker", "name"]


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def load_csv(path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Plik CSV nie istnieje: {path}")

    df = pd.read_csv(path)

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Brak wymaganych kolumn w CSV: {missing_cols}. "
            f"Dostępne kolumny: {list(df.columns)}"
        )

    return df


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["ticker"] = out["ticker"].astype(str).str.strip().str.upper()
    out["name"] = out["name"].astype(str).str.strip()
    return out


def validate(df: pd.DataFrame) -> None:
    if df["ticker"].isna().any() or (df["ticker"] == "").any():
        raise ValueError("Wykryto puste tickery w CSV.")

    if df["name"].isna().any() or (df["name"] == "").any():
        raise ValueError("Wykryto puste nazwy spółek w CSV.")

    if df["ticker"].duplicated().any():
        raise ValueError("Wykryto zduplikowane tickery w CSV.")


# ===== DB (READ ONLY) =====

def load_existing_tickers_from_db() -> set[str]:
    """
    Pobiera z bazy danych tickery już istniejące w tabeli companies.
    TYLKO ODCZYT.
    """
    engine = get_engine()

    query = text("SELECT ticker FROM companies")

    with engine.connect() as conn:
        result = conn.execute(query)
        tickers = {row[0] for row in result}

    return tickers


def compare_csv_vs_db(df_csv: pd.DataFrame, tickers_db: set[str]) -> None:
    """
    Porównuje tickery z CSV z tickerami w DB i loguje wynik.
    """
    tickers_csv = set(df_csv["ticker"])

    new_tickers = tickers_csv - tickers_db
    existing_tickers = tickers_csv & tickers_db

    logging.info("=== PORÓWNANIE CSV vs DB ===")
    logging.info("Liczba spółek w CSV: %s", len(tickers_csv))
    logging.info("Liczba spółek w DB: %s", len(tickers_db))
    logging.info("Nowe spółki do dodania: %s", len(new_tickers))
    logging.info("Spółki już istniejące w DB: %s", len(existing_tickers))


def insert_new_companies(df: pd.DataFrame, tickers_db: set[str]) -> int:
    """
    Wstawia do tabeli companies tylko nowe spółki (INSERT-ONLY).
    Zwraca liczbę zapisanych rekordów.
    """
    # Filtrowanie tylko nowych tickerów
    df_new = df[~df["ticker"].isin(tickers_db)]

    if df_new.empty:
        logging.info("Brak nowych spółek do dodania.")
        return 0

    engine = get_engine()

    insert_sql = text("""
        INSERT INTO companies (ticker, company_name)
        VALUES (:ticker, :company_name)
    """)

    records = [
        {
            "ticker": row.ticker,
            "company_name": row.name,
        }
        for row in df_new.itertuples(index=False)
    ]

    with engine.begin() as conn:  # BEGIN + COMMIT / ROLLBACK
        conn.execute(insert_sql, records)

    return len(records)


def main() -> None:
    setup_logging()

    logging.info("Start importu spółek – porównanie CSV vs DB")
    logging.info("Plik źródłowy: %s", COMPANIES_CSV_PATH)

    df = load_csv(COMPANIES_CSV_PATH)
    df = normalize(df)
    validate(df)

    logging.info("Walidacja CSV zakończona sukcesem.")

    tickers_db = load_existing_tickers_from_db()
    compare_csv_vs_db(df, tickers_db)

    # ===== INSERT-ONLY =====

    inserted_count = insert_new_companies(df, tickers_db)

    logging.info("Zapis do DB zakończony.")
    logging.info("Dodano nowych spółek: %s", inserted_count)


if __name__ == "__main__":
    main()
