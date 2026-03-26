import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine
from core.db import get_engine
from typing import Optional
import sqlalchemy as sa

def export_prices_daily_to_csv(
    output_dir: str,
    filename: str,
    tickers: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    overwrite: bool = False,
) -> str:
    """
    Eksportuje dane z tabeli prices_daily (z JOIN do companies) do pliku CSV.
    - output_dir: katalog docelowy
    - filename: nazwa pliku CSV
    - tickers: string z tickerami oddzielonymi przecinkiem (np. "1AT, 11B, TEN"), None lub pusty = wszystkie
    - overwrite: czy nadpisać istniejący plik
    Zwraca: ścieżkę do zapisanego pliku CSV
    Rzuca FileExistsError jeśli plik istnieje i overwrite=False
    """
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    output_dir_abs = (PROJECT_ROOT / output_dir).resolve()
    output_dir_abs.mkdir(parents=True, exist_ok=True)
    output_path = output_dir_abs / filename

    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Plik {output_path} już istnieje.")

    engine = get_engine()
    where_clauses = []
    if tickers:
        tickers_list = [t.strip() for t in tickers.split(",") if t.strip()]
        placeholders = ", ".join([f"'{t}'" for t in tickers_list])
        where_clauses.append(f"c.ticker IN ({placeholders})")
    if date_from:
        where_clauses.append(f"p.trade_date >= '{date_from}'")
    if date_to:
        where_clauses.append(f"p.trade_date <= '{date_to}'")

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    query = f"""
        SELECT p.*
        FROM prices_daily p
        JOIN companies c ON c.company_id = p.company_id
        {where_sql}
        ORDER BY p.company_id ASC
    """

    df = pd.read_sql(query, engine)
    df.to_csv(output_path, index=False)
    return str(output_path)
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine
from core.db import get_engine
from typing import Optional

def export_companies_to_csv(
    output_dir: str,
    filename: str,
    tickers: Optional[str] = None,
    overwrite: bool = False,
) -> str:
    """
    Eksportuje dane z tabeli companies do pliku CSV.
    - output_dir: katalog docelowy
    - filename: nazwa pliku CSV
    - tickers: string z tickerami oddzielonymi przecinkiem (np. "1AT, 11B, TEN"), None lub pusty = wszystkie
    - overwrite: czy nadpisać istniejący plik
    Zwraca: ścieżkę do zapisanego pliku CSV
    Rzuca FileExistsError jeśli plik istnieje i overwrite=False
    """

    # Ustal katalog główny projektu względem tego pliku (niezależnie od cwd)
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    output_dir_abs = (PROJECT_ROOT / output_dir).resolve()
    output_dir_abs.mkdir(parents=True, exist_ok=True)
    output_path = output_dir_abs / filename

    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Plik {output_path} już istnieje.")

    engine = get_engine()
    if tickers:
        tickers_list = [t.strip() for t in tickers.split(",") if t.strip()]
        placeholders = ", ".join([f"'{t}'" for t in tickers_list])
        query = f"SELECT * FROM companies WHERE ticker IN ({placeholders}) ORDER BY company_id ASC"
    else:
        query = "SELECT * FROM companies ORDER BY company_id ASC"

    df = pd.read_sql(query, engine)
    df.to_csv(output_path, index=False)
    return str(output_path)

def export_indicators_daily_to_csv(
    output_dir: str,
    filename: str,
    tickers: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    overwrite: bool = False,
) -> str:
    """
    Eksportuje dane z tabeli indicators_daily (LEFT JOIN z prices_daily, JOIN z companies) do pliku CSV.
    - output_dir: katalog docelowy
    - filename: nazwa pliku CSV
    - tickers: string z tickerami oddzielonymi przecinkiem (np. "1AT, 11B, TEN"), None lub pusty = wszystkie
    - date_from, date_to: zakres dat (string YYYY-MM-DD)
    - overwrite: czy nadpisać istniejący plik
    Zwraca: ścieżkę do zapisanego pliku CSV
    Rzuca FileExistsError jeśli plik istnieje i overwrite=False
    """
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    output_dir_abs = (PROJECT_ROOT / output_dir).resolve()
    output_dir_abs.mkdir(parents=True, exist_ok=True)
    output_path = output_dir_abs / filename

    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Plik {output_path} już istnieje.")

    engine = get_engine()
    where_clauses = []
    if tickers:
        tickers_list = [t.strip() for t in tickers.split(",") if t.strip()]
        placeholders = ", ".join([f"'{t}'" for t in tickers_list])
        where_clauses.append(f"c.ticker IN ({placeholders})")
    if date_from:
        where_clauses.append(f"p.trade_date >= '{date_from}'")
    if date_to:
        where_clauses.append(f"p.trade_date <= '{date_to}'")

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    query = f"""
        SELECT i.*
        FROM prices_daily p
        JOIN companies c ON c.company_id = p.company_id
        LEFT JOIN indicators_daily i ON i.company_id = p.company_id AND i.trade_date = p.trade_date
        {where_sql}
        ORDER BY p.company_id ASC
    """

    df = pd.read_sql(query, engine)
    df.to_csv(output_path, index=False)
    return str(output_path)

def export_indicators_dictionary_to_csv(
    output_dir: str,
    filename: str,
    overwrite: bool = False,
) -> str:
    """
    Eksportuje wszystkie dane z tabeli indicators_dictionary do pliku CSV.
    - output_dir: katalog docelowy
    - filename: nazwa pliku CSV
    - overwrite: czy nadpisać istniejący plik
    Zwraca: ścieżkę do zapisanego pliku CSV
    Rzuca FileExistsError jeśli plik istnieje i overwrite=False
    """
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    output_dir_abs = (PROJECT_ROOT / output_dir).resolve()
    output_dir_abs.mkdir(parents=True, exist_ok=True)
    output_path = output_dir_abs / filename

    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Plik {output_path} już istnieje.")

    engine = get_engine()
    query = "SELECT * FROM indicators_dictionary ORDER BY indicator_code ASC"
    df = pd.read_sql(query, engine)
    df.to_csv(output_path, index=False)
    return str(output_path)
