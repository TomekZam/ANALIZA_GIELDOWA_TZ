# etl/import_prices_daily.py

"""
Import (ETL) notowań dziennych (prices_daily) – KROK 1 (szkielet).

Zakres tego kroku:
- iteracja po plikach TXT w katalogu
- parsowanie pliku (format jak Stooq ASCII: <TICKER>,<PER>,<DATE>,...)
- walidacja podstawowa + logowanie problemów
- raport wynikowy (pod UI)
- opcjonalne przenoszenie plików do archiwum (domyślnie WYŁĄCZONE)

UWAGA:
Ten etap NIE zapisuje danych do bazy (DB dodamy w kolejnym kroku).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from shutil import move
from typing import Any
from config.etl import (
    PRICES_DAILY_IMPORT_DIR,
    PRICES_DAILY_ARCHIVE_DIR,
)
from config.etl import PRICES_DAILY_LOG_DIR
from core.db import get_engine
from sqlalchemy import text
from datetime import date

import pandas as pd


# ========= Konfiguracja / kontrakt formatu =========

REQUIRED_COLUMNS = [
    "<TICKER>",
    "<PER>",
    "<DATE>",
    "<OPEN>",
    "<HIGH>",
    "<LOW>",
    "<CLOSE>",
    "<VOL>",
]

# Stooq ASCII zwykle ma jeszcze: <TIME>, <OPENINT>
OPTIONAL_COLUMNS = ["<TIME>", "<OPENINT>"]

# Mapowanie do "czytelnych" nazw (na razie pod raport / dalsze kroki)
COLUMN_RENAME = {
    "<TICKER>": "source_ticker",
    "<PER>": "period",
    "<DATE>": "trade_date",
    "<TIME>": "trade_time",
    "<OPEN>": "open",
    "<HIGH>": "high",
    "<LOW>": "low",
    "<CLOSE>": "close",
    "<VOL>": "volume",
    "<OPENINT>": "openint",
}


# ========= Model raportu / problemów =========

@dataclass
class ImportIssue:
    level: str                # "WARNING" / "ERROR"
    code: str                 # krótki kod, np. "MISSING_COL", "BAD_DATE"
    message: str
    file: str
    line_no: int | None = None
    source_ticker: str | None = None


@dataclass
class FileImportResult:
    file: str
    source_ticker: str | None
    company_id: int | None          # NOWE
    rows_total: int
    rows_ok: int
    rows_invalid: int
    issues: list[ImportIssue] = field(default_factory=list)
    status: str = "OK"          # "OK" / "SKIPPED" / "FAILED"


@dataclass
class ImportRunReport:
    input_dir: str
    archive_dir: str | None
    started_at: str
    finished_at: str | None = None

    files_found: int = 0
    files_processed: int = 0
    files_moved: int = 0
    files_failed: int = 0

    results: list[FileImportResult] = field(default_factory=list)

    def finalize(self) -> None:
        self.finished_at = datetime.now().isoformat(timespec="seconds")


# ========= Logowanie =========

def setup_logging() -> Path:
    """
    Konfiguruje logowanie:
    - INFO+ do konsoli
    - INFO+ do pliku (1 plik = 1 run)
    Zwraca ścieżkę do pliku logu.
    """
    PRICES_DAILY_LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_file = PRICES_DAILY_LOG_DIR / (
        f"import_prices_daily_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # wyczyść ewentualne stare handlery (ważne przy re-runach)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s"
    )

    # --- konsola ---
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # --- plik ---
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logging.info("=== START IMPORT PRICES DAILY ===")
    logging.info("Plik logu: %s", log_file)

    return log_file



# ========= Parsowanie / walidacja =========

def _read_prices_file(path: Path) -> pd.DataFrame:
    """
    Czyta plik TXT w formacie CSV (separator przecinek).
    """
    if not path.exists():
        raise FileNotFoundError(f"Plik nie istnieje: {path}")

    # dtype=str aby najpierw kontrolować konwersje i lepiej logować problemy
    df = pd.read_csv(path, dtype=str)
    return df


def _validate_required_columns(df: pd.DataFrame, file_name: str) -> list[ImportIssue]:
    issues: list[ImportIssue] = []
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        issues.append(
            ImportIssue(
                level="ERROR",
                code="MISSING_COL",
                message=f"Brak wymaganych kolumn: {missing}. Dostępne: {list(df.columns)}",
                file=file_name,
            )
        )
    return issues


def _normalize_and_cast(df: pd.DataFrame, file_name: str) -> tuple[pd.DataFrame, list[ImportIssue]]:
    """
    - rename kolumn
    - trim/upper ticker
    - konwersje typów (data + liczby)
    - oznaczanie wierszy błędnych (do odfiltrowania)
    """
    issues: list[ImportIssue] = []

    out = df.rename(columns=COLUMN_RENAME).copy()

    # --- ticker ---
    if "source_ticker" in out.columns:
        out["source_ticker"] = out["source_ticker"].astype(str).str.strip().str.upper()

    # --- period (D) ---
    if "period" in out.columns:
        out["period"] = out["period"].astype(str).str.strip().str.upper()

    # --- trade_date: YYYYMMDD ---
    if "trade_date" in out.columns:
        # errors='coerce' -> NaT, potem odfiltrujemy
        out["trade_date_parsed"] = pd.to_datetime(out["trade_date"], format="%Y%m%d", errors="coerce")
        bad = out["trade_date_parsed"].isna()
        if bad.any():
            bad_count = int(bad.sum())
            issues.append(
                ImportIssue(
                    level="WARNING",
                    code="BAD_DATE",
                    message=f"Wykryto {bad_count} wierszy z niepoprawną datą (trade_date). Zostaną pominięte.",
                    file=file_name,
                )
            )
    else:
        out["trade_date_parsed"] = pd.NaT

    # --- liczby ---
    for col in ["open", "high", "low", "close", "volume"]:
        if col in out.columns:
            out[f"{col}_num"] = pd.to_numeric(out[col].str.replace(",", ".", regex=False), errors="coerce")
            bad = out[f"{col}_num"].isna()
            if bad.any():
                bad_count = int(bad.sum())
                issues.append(
                    ImportIssue(
                        level="WARNING",
                        code="BAD_NUM",
                        message=f"Wykryto {bad_count} wierszy z niepoprawną wartością liczbową w kolumnie '{col}'. Zostaną pominięte.",
                        file=file_name,
                    )
                )
        else:
            out[f"{col}_num"] = pd.NA

    return out, issues


def parse_prices_daily_file(
    path: Path,
    dry_run: bool = False,
) -> FileImportResult:
    """
    Parsuje pojedynczy plik i zwraca wynik + listę problemów.
    """
    file_name = path.name
    issues: list[ImportIssue] = []

    try:
        df_raw = _read_prices_file(path)
    except Exception as e:
        logging.exception("Nie udało się wczytać pliku: %s", path)
        return FileImportResult(
            file=file_name,
            source_ticker=None,
            company_id=None,          # ← TO DODAJEMY
            rows_total=0,
            rows_ok=0,
            rows_invalid=0,
            issues=[
                ImportIssue(
                    level="ERROR",
                    code="READ_FAIL",
                    message=str(e),
                    file=file_name,
                )
            ],
            status="FAILED",
        )


    # walidacja kolumn
    issues.extend(_validate_required_columns(df_raw, file_name))
    if any(i.level == "ERROR" for i in issues):
        for i in issues:
            logging.error("[%s] %s", i.code, i.message)
        return FileImportResult(
            file=file_name,
            source_ticker=None,
            company_id=None,          # ← TO DODAJEMY
            rows_total=len(df_raw),
            rows_ok=0,
            rows_invalid=len(df_raw),
            issues=issues,
            status="FAILED",
        )


    df_norm, norm_issues = _normalize_and_cast(df_raw, file_name)
    issues.extend(norm_issues)

    # ticker (zakładamy: jeden ticker na plik)
    source_ticker: str | None = None
    if "source_ticker" in df_norm.columns and not df_norm["source_ticker"].empty:
        uniq = df_norm["source_ticker"].dropna().unique().tolist()
        if len(uniq) == 1:
            source_ticker = str(uniq[0])
        else:
            # nietypowe: wiele tickerów w 1 pliku
            source_ticker = str(uniq[0]) if uniq else None
            issues.append(
                ImportIssue(
                    level="WARNING",
                    code="MULTI_TICKER",
                    message=f"W pliku wykryto wiele tickerów: {uniq[:10]} (pokazano max 10). Przyjmuję pierwszy: {source_ticker}",
                    file=file_name,
                    source_ticker=source_ticker,
                )
            )

    # podstawowa walidacja wierszy:
    # - period == D
    # - trade_date poprawna
    # - OHLC i VOL poprawne liczbowe
    ok_mask = pd.Series(True, index=df_norm.index)

    if "period" in df_norm.columns:
        bad_period = df_norm["period"] != "D"
        if bad_period.any():
            issues.append(
                ImportIssue(
                    level="WARNING",
                    code="BAD_PERIOD",
                    message=f"Wykryto {int(bad_period.sum())} wierszy z <PER> != 'D'. Zostaną pominięte.",
                    file=file_name,
                    source_ticker=source_ticker,
                )
            )
        ok_mask &= ~bad_period

    ok_mask &= df_norm["trade_date_parsed"].notna()

    for col in ["open_num", "high_num", "low_num", "close_num", "volume_num"]:
        ok_mask &= df_norm[col].notna()

    rows_total = len(df_norm)
    rows_ok = int(ok_mask.sum())
    df_valid = df_norm.loc[ok_mask].copy()
    rows_invalid = rows_total - rows_ok

    # log podsumowania pliku
    logging.info("Plik: %s | ticker: %s | wiersze: %s | OK: %s | błędne: %s",
                 file_name, source_ticker, rows_total, rows_ok, rows_invalid)

    # loguj warnings
    for i in issues:
        if i.level == "WARNING":
            logging.warning("[%s] %s | plik=%s | ticker=%s",
                            i.code, i.message, i.file, i.source_ticker)

    status = "OK" if rows_ok > 0 else "SKIPPED"
    if rows_ok == 0:
        issues.append(
            ImportIssue(
                level="ERROR",
                code="NO_VALID_ROWS",
                message="Brak poprawnych wierszy po walidacji – plik pominięty.",
                file=file_name,
                source_ticker=source_ticker,
            )
        )
        logging.error("[%s] %s | plik=%s", "NO_VALID_ROWS", "Brak poprawnych wierszy po walidacji – plik pominięty.", file_name)

    company_id: int | None = None

    if source_ticker:
        company_id = map_ticker_to_company_id(source_ticker)

        if company_id is None:
            issues.append(
                ImportIssue(
                    level="ERROR",
                    code="COMPANY_NOT_FOUND",
                    message=f"Brak spółki w tabeli companies dla tickera '{source_ticker}'",
                    file=file_name,
                    source_ticker=source_ticker,
                )
            )
            logging.error(
                "[COMPANY_NOT_FOUND] Brak spółki w DB | ticker=%s | plik=%s",
                source_ticker,
                file_name,
            )

            status = "FAILED"

    inserted = 0
    skipped = 0

    if status == "OK" and company_id is not None:
        if dry_run:
            inserted = len(df_valid)
            skipped = 0

            logging.info(
                "[DRY-RUN] Symulacja zapisu | ticker=%s | rows=%s",
                source_ticker,
                inserted,
            )
        else:
            inserted, skipped = insert_prices_daily(
                company_id=company_id,
                df=df_valid,
                source_ticker=source_ticker,
            )

            logging.info(
                "Zapis do prices_daily | ticker=%s | inserted=%s | skipped=%s",
                source_ticker,
                inserted,
                skipped,
            )



    return FileImportResult(
        file=file_name,
        source_ticker=source_ticker,
        company_id=company_id,
        rows_total=rows_total,
        rows_ok=rows_ok,
        rows_invalid=rows_invalid,
        issues=issues,
        status=status,
    )



# ========= Mapowanie =========

def map_ticker_to_company_id(source_ticker: str) -> int | None:
    """
    Mapuje source_ticker (z pliku) na companies.company_id.
    Zwraca company_id albo None jeśli nie znaleziono.
    """
    engine = get_engine()

    query = text("""
        SELECT company_id
        FROM companies
        WHERE ticker = :ticker
    """)

    with engine.connect() as conn:
        value = conn.execute(query, {"ticker": source_ticker}).scalar()

    return int(value) if value is not None else None




def insert_prices_daily(
    *,
    company_id: int,
    df: pd.DataFrame,
    source_ticker: str,
) -> tuple[int, int]:
    """
    Zapisuje dane do prices_daily.
    Zwraca: (inserted_rows, skipped_duplicates)
    """
    engine = get_engine()

    insert_sql = text("""
        INSERT INTO prices_daily (
            company_id,
            trade_date,
            open_price,
            high_price,
            low_price,
            close_price,
            volume,
            source_ticker,
            created_at
        )
        SELECT
            :company_id,
            :trade_date,
            :open_price,
            :high_price,
            :low_price,
            :close_price,
            :volume,
            :source_ticker,
            GETDATE()
        WHERE NOT EXISTS (
            SELECT 1
            FROM prices_daily
            WHERE company_id = :company_id
              AND trade_date = :trade_date
        )
    """)

    inserted = 0
    skipped = 0

    with engine.begin() as conn:  # transakcja
        for _, row in df.iterrows():
            params = {
                "company_id": company_id,
                "trade_date": row["trade_date_parsed"].date(),
                "open_price": float(row["open_num"]),
                "high_price": float(row["high_num"]),
                "low_price": float(row["low_num"]),
                "close_price": float(row["close_num"]),
                "volume": int(row["volume_num"]),
                "source_ticker": source_ticker,
            }

            result = conn.execute(insert_sql, params)

            if result.rowcount == 1:
                inserted += 1
            else:
                skipped += 1

    return inserted, skipped



def archive_imported_file(
    *,
    source_path: Path,
    archive_root: Path,
    run_date: date,
) -> Path:
    """
    Przenosi plik do archiwum w strukturze:
    archive_root/YYYY-MM-DD/filename
    Zwraca docelową ścieżkę pliku.
    """
    target_dir = archive_root / run_date.isoformat()
    target_dir.mkdir(parents=True, exist_ok=True)

    target_path = target_dir / source_path.name
    move(str(source_path), str(target_path))

    return target_path



# ========= Runner: katalog -> wszystkie pliki =========

def import_prices_daily_from_dir(
    input_dir: Path,
    archive_dir: Path | None = None,
    move_imported: bool = False,
    dry_run: bool = False,
) -> ImportRunReport:

    """
    Przetwarza wszystkie pliki *.txt w katalogu input_dir.
    Jeśli move_imported=True oraz archive_dir podane, to pliki z wynikiem OK zostaną przeniesione.
    """

    logging.info(
    "PARAMS | dry_run=%s | move_imported=%s | input_dir=%s",
    dry_run,
    move_imported,
    input_dir,
    )

    if dry_run:
        logging.info("TRYB DRY-RUN: brak zapisu do DB i brak archiwizacji plików")

    run_date = date.today()
    report = ImportRunReport(
        input_dir=str(input_dir),
        archive_dir=str(archive_dir) if archive_dir else None,
        started_at=datetime.now().isoformat(timespec="seconds"),
    )

    if not input_dir.exists():
        raise FileNotFoundError(f"Katalog wejściowy nie istnieje: {input_dir}")

    files = sorted(input_dir.glob("*.txt"))
    report.files_found = len(files)
    logging.info("Znaleziono plików TXT: %s | katalog: %s", report.files_found, input_dir)

    if move_imported and archive_dir:
        archive_dir.mkdir(parents=True, exist_ok=True)

    for f in files:
        try:
            res = parse_prices_daily_file(f, dry_run=dry_run)
            report.results.append(res)
            report.files_processed += 1

            if res.status == "OK" and move_imported and archive_dir and not dry_run:
                archived_path = archive_imported_file(
                    source_path=f,
                    archive_root=archive_dir,
                    run_date=run_date,
                )
                report.files_moved += 1
                logging.info(
                    "Plik przeniesiony do archiwum: %s -> %s",
                    f.name,
                    archived_path,
                )

            if res.status == "FAILED":
                report.files_failed += 1

        except Exception as e:
            logging.exception("Błąd krytyczny przy przetwarzaniu pliku: %s", f.name)
            report.files_failed += 1
            report.results.append(
                FileImportResult(
                    file=f.name,
                    source_ticker=None,
                    company_id=None,        # ← TO DODAJEMY
                    rows_total=0,
                    rows_ok=0,
                    rows_invalid=0,
                    issues=[
                        ImportIssue(
                            level="ERROR",
                            code="FATAL",
                            message=str(e),
                            file=f.name,
                        )
                    ],
                    status="FAILED",
                )
            )


    mapped = [r for r in report.results if r.company_id]
    unmapped = [r for r in report.results if r.source_ticker and r.company_id is None]

    logging.info("Pliki z poprawnym mapowaniem spółki: %s", len(mapped))
    logging.info("Pliki BEZ mapowania spółki: %s", len(unmapped))

    if unmapped:
        logging.warning(
            "Tickery bez mapowania: %s",
            sorted({r.source_ticker for r in unmapped}),
        )


    report.finalize()
    logging.info(
        "Import zakończony | processed=%s | moved=%s | failed=%s",
        report.files_processed,
        report.files_moved,
        report.files_failed,
    )
    return report


def main() -> None:
    log_file = setup_logging()

    report = import_prices_daily_from_dir(
        input_dir=PRICES_DAILY_IMPORT_DIR,
        archive_dir=PRICES_DAILY_ARCHIVE_DIR,
        move_imported=False,   # bezpiecznie: brak archiwizacji
        dry_run=True,          # bezpiecznie: brak zapisu do DB
    )

    ok_files = [r for r in report.results if r.status == "OK"]
    tickers = sorted({r.source_ticker for r in ok_files if r.source_ticker})
    logging.info("Zaimportowane tickery (z poprawnymi wierszami): %s", tickers)
    logging.info("=== KONIEC IMPORTU ===")
    logging.info("Log zapisany w: %s", log_file)


if __name__ == "__main__":
    main()
