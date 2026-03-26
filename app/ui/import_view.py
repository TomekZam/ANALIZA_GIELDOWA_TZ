import streamlit as st
from pathlib import Path

from config.etl import COMPANIES_CSV_PATH
from etl.import_prices_daily import setup_logging as setup_prices_logging
from etl.import_companies import (
    setup_logging as setup_companies_logging,
    load_csv,
    normalize,
    validate,
    load_existing_tickers_from_db,
    compare_csv_vs_db,
    insert_new_companies,
)
from app.ui.calculated_indicators_view import render as render_calculated_indicators



def render():
    st.header("Import danych")

    # =========================================================
    # Calculated Indicators Pipeline (pierwsze na liście)
    # =========================================================
    render_calculated_indicators()
    st.markdown("---")


    st.subheader("Import spółek (companies)")

    # --- Parametry importu (read-only) ---
    st.markdown("### Parametry wywołania")

    project_root = Path.cwd()
    relative_path = COMPANIES_CSV_PATH.relative_to(project_root)

    st.write(f"**Ścieżka (względna):** `{relative_path}`")
    st.write(f"**Nazwa pliku:** `{COMPANIES_CSV_PATH.name}`")

    st.markdown("---")

    # --- Akcja ---
    if st.button("Uruchom import spółek"):
        with st.spinner("Import w toku..."):
            try:
                setup_companies_logging()

                # 1. CSV
                df = load_csv(COMPANIES_CSV_PATH)
                df = normalize(df)
                validate(df)

                csv_count = len(df)

                # 2. DB (stan przed)
                tickers_db = load_existing_tickers_from_db()
                db_count_before = len(tickers_db)

                # 3. Porównanie (logi)
                compare_csv_vs_db(df, tickers_db)

                # 4. INSERT-ONLY
                inserted_count = insert_new_companies(df, tickers_db)

                # 5. Podsumowanie
                st.success("Import zakończony pomyślnie")

                st.markdown("### Podsumowanie importu")
                st.write(f"- Liczba spółek w CSV: **{csv_count}**")
                st.write(f"- Liczba spółek w DB (przed importem): **{db_count_before}**")
                st.write(f"- Nowe spółki dodane do DB: **{inserted_count}**")
                st.write(f"- Spółki pominięte (już istniały): **{csv_count - inserted_count}**")

            except Exception as e:
                st.error("Błąd podczas importu")
                st.exception(e)


    # =========================================================
    # Import notowań dziennych (prices_daily)
    # =========================================================

    from etl.import_prices_daily import import_prices_daily_from_dir
    from config.etl import (
        PRICES_DAILY_IMPORT_DIR,
        PRICES_DAILY_ARCHIVE_DIR,
        PRICES_DAILY_LOG_DIR,
    )

    st.markdown("---")
    st.subheader("Import notowań dziennych (prices_daily)")

    st.markdown("### Parametry wywołania")

    st.write(f"**Katalog wejściowy:** `{PRICES_DAILY_IMPORT_DIR}`")
    st.write(f"**Katalog archiwum:** `{PRICES_DAILY_ARCHIVE_DIR}`")
    st.write(f"**Katalog logów:** `{PRICES_DAILY_LOG_DIR}`")

    txt_files = sorted(Path(PRICES_DAILY_IMPORT_DIR).glob("*.txt"))
    st.write(f"**Pliki TXT do importu:** `{len(txt_files)}`")

    if not txt_files:
        st.info("Brak plików TXT do importu.")
    else:
        dry_run = st.checkbox(
            "Dry-run (bez zapisu do DB i bez archiwizacji plików)",
            value=True,
            help="Walidacja + mapowanie + raport. Brak INSERT i brak przenoszenia plików.",
        )
        move_imported = not dry_run  
        if dry_run:
            st.info("Tryb DRY-RUN: brak zapisu do DB i brak archiwizacji plików.")
        else:
            st.warning("Tryb NORMALNY: dane zostaną zapisane do DB i pliki przeniesione do archiwum.")

        if st.button("Uruchom import notowań dziennych"):
            with st.spinner("Import notowań dziennych w toku..."):
                try:
                    log_file = setup_prices_logging() 
                    report = import_prices_daily_from_dir(
                        input_dir=PRICES_DAILY_IMPORT_DIR,
                        archive_dir=PRICES_DAILY_ARCHIVE_DIR,
                        move_imported=move_imported,
                        dry_run=dry_run,
                    )

                    st.success("Import notowań dziennych zakończony")

                    st.markdown("### Podsumowanie importu")
                    st.write({
                        "files_found": report.files_found,
                        "files_processed": report.files_processed,
                        "files_moved": report.files_moved,
                        "files_failed": report.files_failed,
                    })

                    st.markdown("### Szczegóły plików")
                    rows = [
                        {
                            "plik": r.file,
                            "ticker": r.source_ticker,
                            "company_id": r.company_id,
                            "status": r.status,
                            "rows_ok": r.rows_ok,
                            "rows_invalid": r.rows_invalid,
                        }
                        for r in report.results
                    ]
                    st.dataframe(rows, width="stretch")

                    st.markdown("### Logi")
                    st.info(f"Log zapisany w pliku:\n\n{log_file}")
                    st.info(f"Katalog logów:\n\n{PRICES_DAILY_LOG_DIR}")


                except Exception as e:
                    st.error("Błąd podczas importu notowań dziennych")
                    st.exception(e)

    # =========================================================
    # Import wskaźników dziennych (indicators_daily)
    # =========================================================

    from etl.import_indicators_daily import import_indicators_daily_from_dir
    from etl.import_indicators_daily import setup_logging as setup_indicators_logging
    from config.etl import (
        INDICATORS_IMPORT_DIR,
        INDICATORS_ARCHIVE_DIR,
        INDICATORS_LOG_DIR,
    )

    st.markdown("---")
    st.subheader("Import wskaźników dziennych (indicators_daily)")

    st.markdown("### Parametry wywołania")

    st.write(f"**Katalog wejściowy:** `{INDICATORS_IMPORT_DIR}`")
    st.write(f"**Katalog archiwum:** `{INDICATORS_ARCHIVE_DIR}`")
    st.write(f"**Katalog logów:** `{INDICATORS_LOG_DIR}`")

    txt_files = sorted(Path(INDICATORS_IMPORT_DIR).glob("*.txt"))
    st.write(f"**Pliki TXT do importu:** `{len(txt_files)}`")

    if not txt_files:
        st.info("Brak plików TXT do importu wskaźników.")
    else:
        dry_run = st.checkbox(
            "Dry-run (bez zapisu do DB i bez archiwizacji plików) – wskaźniki",
            value=True,
            help="Symulacja UPDATE/INSERT + raport. Brak zapisu do DB i brak przenoszenia plików.",
            key="indicators_dry_run",
        )

        move_imported = not dry_run

        if dry_run:
            st.info("Tryb DRY-RUN: brak zapisu do DB i brak archiwizacji plików.")
        else:
            st.warning(
                "Tryb NORMALNY: dane wskaźników zostaną zapisane do DB "
                "i pliki zostaną przeniesione do archiwum."
            )

        if st.button("Uruchom import wskaźników dziennych"):
            with st.spinner("Import wskaźników dziennych w toku..."):
                try:
                    log_file = setup_indicators_logging()

                    report = import_indicators_daily_from_dir(
                        input_dir=INDICATORS_IMPORT_DIR,
                        archive_dir=INDICATORS_ARCHIVE_DIR,
                        move_imported=move_imported,
                        dry_run=dry_run,
                    )

                    st.success("Import wskaźników dziennych zakończony")

                    st.markdown("### Podsumowanie importu")
                    st.write({
                        "files_found": report.files_found,
                        "files_processed": report.files_processed,
                        "files_moved": report.files_moved,
                        "files_failed": report.files_failed,
                    })

                    st.markdown("### Szczegóły plików")
                    rows = [
                        {
                            "plik": r.file,
                            "ticker": r.ticker,
                            "indicator": r.indicator,
                            "status": r.status,
                            "updated": r.updated,
                            "inserted": r.inserted,
                            "message": r.message,
                        }
                        for r in report.results
                    ]

                    st.dataframe(rows, width="stretch")

                    st.markdown("### Logi")
                    st.info(f"Log zapisany w pliku:\n\n{log_file}")
                    st.info(f"Katalog logów:\n\n{INDICATORS_LOG_DIR}")

                except Exception as e:
                    st.error("Błąd podczas importu wskaźników dziennych")
                    st.exception(e)


