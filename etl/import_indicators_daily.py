from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import List
from shutil import move
import logging

import pandas as pd
from sqlalchemy import text

from core.db import get_engine
from config.etl import (
    INDICATORS_IMPORT_DIR,
    INDICATORS_ARCHIVE_DIR,
    INDICATORS_LOG_DIR,
)

# ============================================================
# MODELE RAPORTU
# ============================================================

@dataclass
class FileImportResult:
    file: str
    ticker: str | None
    indicator: str | None
    updated: int
    inserted: int
    status: str               # "OK" / "SKIPPED" / "FAILED"
    message: str | None = None


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

    results: List[FileImportResult] = field(default_factory=list)

    def finalize(self) -> None:
        self.finished_at = datetime.now().isoformat(timespec="seconds")


# ============================================================
# LOGOWANIE – 1:1 jak prices_daily
# ============================================================

def setup_logging() -> Path:
    INDICATORS_LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_file = INDICATORS_LOG_DIR / (
        f"import_indicators_daily_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s"
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logging.info("=== START IMPORT INDICATORS DAILY ===")
    logging.info("Log file: %s", log_file)

    return log_file


# ============================================================
# FUNKCJE POMOCNICZE (bez zmian semantyki)
# ============================================================

def parse_ticker_and_indicator(raw_ticker: str):
    if "_" not in raw_ticker:
        raise ValueError(f"Invalid ticker format: {raw_ticker}")
    t, i = raw_ticker.split("_", 1)
    return t.lower(), i.lower()


def get_company_id(conn, ticker: str):
    sql = text("""
        SELECT company_id
        FROM companies
        WHERE LOWER(ticker) = :ticker
    """)
    r = conn.execute(sql, {"ticker": ticker}).fetchone()
    return r[0] if r else None


def get_existing_dates(conn, company_id: int):
    sql = text("""
        SELECT trade_date
        FROM indicators_daily
        WHERE company_id = :company_id
    """)
    r = conn.execute(sql, {"company_id": company_id}).fetchall()
    return {row[0] for row in r}


def fetch_indicator_columns(conn):
    sql = text("""
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'dbo'
          AND TABLE_NAME = 'indicators_daily'
          AND COLUMN_NAME NOT IN (
              'company_id',
              'trade_date',
              'created_at',
              'modified_at'
          )
    """)
    r = conn.execute(sql).fetchall()
    return {row[0].lower() for row in r}


# ============================================================
# ARCHIWIZACJA – 1:1 jak prices_daily
# ============================================================

def archive_imported_file(
    *,
    source_path: Path,
    archive_root: Path,
    run_date: date,
) -> Path:
    target_dir = archive_root / run_date.isoformat()
    target_dir.mkdir(parents=True, exist_ok=True)

    target_path = target_dir / source_path.name
    move(str(source_path), str(target_path))

    return target_path


# ============================================================
# PRZETWARZANIE POJEDYNCZEGO PLIKU
# ============================================================

def process_indicator_file(
    *,
    conn,
    file_path: Path,
    dry_run: bool,
) -> FileImportResult:

    try:
        df = pd.read_csv(file_path)

        if df.empty:
            return FileImportResult(
                file=file_path.name,
                ticker=None,
                indicator=None,
                updated=0,
                inserted=0,
                status="SKIPPED",
                message="empty file",
            )

        raw_ticker = df.loc[0, "<TICKER>"]
        ticker, indicator = parse_ticker_and_indicator(raw_ticker)

        indicator_columns = fetch_indicator_columns(conn)
        if indicator not in indicator_columns:
            return FileImportResult(
                file=file_path.name,
                ticker=ticker,
                indicator=indicator,
                updated=0,
                inserted=0,
                status="SKIPPED",
                message=f"indicator '{indicator}' not present in DB",
            )

        company_id = get_company_id(conn, ticker)
        if company_id is None:
            return FileImportResult(
                file=file_path.name,
                ticker=ticker,
                indicator=indicator,
                updated=0,
                inserted=0,
                status="SKIPPED",
                message=f"company '{ticker}' not found",
            )

        df["trade_date"] = pd.to_datetime(df["<DATE>"], format="%Y%m%d").dt.date
        df["value"] = df["<CLOSE>"]
        df = df[["trade_date", "value"]].dropna()

        existing_dates = get_existing_dates(conn, company_id)
        now = datetime.now()

        updates = [
            {
                "company_id": company_id,
                "trade_date": row.trade_date,
                "value": row.value,
                "now": now,
            }
            for row in df.itertuples()
            if row.trade_date in existing_dates
        ]

        inserts = [
            {
                "company_id": company_id,
                "trade_date": row.trade_date,
                "value": row.value,
                "now": now,
            }
            for row in df.itertuples()
            if row.trade_date not in existing_dates
        ]

        if dry_run:
            logging.info(
                "[DRY-RUN] %s | ticker=%s | indicator=%s | would_update=%s | would_insert=%s",
                file_path.name,
                ticker,
                indicator,
                len(updates),
                len(inserts),
            )
            return FileImportResult(
                file=file_path.name,
                ticker=ticker,
                indicator=indicator,
                updated=len(updates),
                inserted=len(inserts),
                status="OK",
            )

        # UPDATE
        if updates:
            update_sql = text(f"""
                UPDATE indicators_daily
                SET {indicator} = :value,
                    modified_at = :now
                WHERE company_id = :company_id
                  AND trade_date = :trade_date
            """)
            conn.execute(update_sql, updates)

        # INSERT
        if inserts:
            insert_sql = text(f"""
                INSERT INTO indicators_daily (
                    company_id,
                    trade_date,
                    {indicator},
                    created_at,
                    modified_at
                )
                VALUES (
                    :company_id,
                    :trade_date,
                    :value,
                    :now,
                    :now
                )
            """)
            conn.execute(insert_sql, inserts)

        return FileImportResult(
            file=file_path.name,
            ticker=ticker,
            indicator=indicator,
            updated=len(updates),
            inserted=len(inserts),
            status="OK",
        )

    except Exception as e:
        logging.exception("FAILED processing file: %s", file_path.name)
        return FileImportResult(
            file=file_path.name,
            ticker=None,
            indicator=None,
            updated=0,
            inserted=0,
            status="FAILED",
            message=str(e),
        )


# ============================================================
# RUNNER
# ============================================================

def import_indicators_daily_from_dir(
    *,
    input_dir: Path,
    archive_dir: Path | None,
    move_imported: bool,
    dry_run: bool,
) -> ImportRunReport:

    logging.info(
        "PARAMS | dry_run=%s | move_imported=%s | input_dir=%s",
        dry_run,
        move_imported,
        input_dir,
    )

    if dry_run:
        logging.info("TRYB DRY-RUN: brak zapisu do DB i brak archiwizacji")

    run_date = date.today()

    report = ImportRunReport(
        input_dir=str(input_dir),
        archive_dir=str(archive_dir) if archive_dir else None,
        started_at=datetime.now().isoformat(timespec="seconds"),
    )

    if not input_dir.exists():
        raise FileNotFoundError(f"Directory not found: {input_dir}")

    files = sorted(input_dir.glob("*.txt"))
    report.files_found = len(files)

    engine = get_engine()
    with engine.begin() as conn:
        for f in files:
            res = process_indicator_file(
                conn=conn,
                file_path=f,
                dry_run=dry_run,
            )

            report.results.append(res)
            report.files_processed += 1

            if res.status == "FAILED":
                report.files_failed += 1

            if (
                res.status in ("OK", "SKIPPED")
                and move_imported
                and archive_dir
                and not dry_run
            ):
                archived = archive_imported_file(
                    source_path=f,
                    archive_root=archive_dir,
                    run_date=run_date,
                )
                report.files_moved += 1
                logging.info(
                    "Plik przeniesiony do archiwum: %s -> %s",
                    f.name,
                    archived,
                )

    report.finalize()
    logging.info(
        "Import zakończony | processed=%s | moved=%s | failed=%s",
        report.files_processed,
        report.files_moved,
        report.files_failed,
    )

    return report


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    log_file = setup_logging()

    report = import_indicators_daily_from_dir(
        input_dir=INDICATORS_IMPORT_DIR,
        archive_dir=INDICATORS_ARCHIVE_DIR,
        move_imported=True,
        dry_run=False,      # <- zmień na True do testu
    )

    for r in report.results:
        logging.info(
            "%s | status=%s | updated=%s | inserted=%s | %s",
            r.file,
            r.status,
            r.updated,
            r.inserted,
            r.message or "",
        )

    logging.info("=== KONIEC IMPORTU ===")
    logging.info("Log zapisany w: %s", log_file)


if __name__ == "__main__":
    main()
