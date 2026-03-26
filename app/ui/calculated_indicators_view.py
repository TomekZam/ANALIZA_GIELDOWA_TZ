import streamlit as st
import pandas as pd

from analysis.calculated_indicators.pipeline import (
    INDICATOR_PIPELINE,
    validate_pipeline,
)
from analysis.calculated_indicators.registry import INDICATORS_REGISTRY
from core.db import get_engine
from sqlalchemy import text
import numpy as np
from config.app_params import get_param

# =========================================================
# Kolorowa interpretacja % pokrycia (UI helper)
# =========================================================

def coverage_badge(x):
    if not isinstance(x, str):
        return x

    try:
        value = float(x.replace("%", "").strip())
    except ValueError:
        return x

    if value >= 99:
        return f"🟢 {value:.2f} %"
    elif value >= 90:
        return f"🟡 {value:.2f} %"
    else:
        return f"🔴 {value:.2f} %"


def load_indicator_descriptions() -> dict[str, str]:
    """
    Zwraca słownik:
    { indicator_code: description }
    """
    sql = text("""
        SELECT indicator_code, description
        FROM indicators_dictionary
        WHERE is_active = 1
    """)

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(sql).fetchall()

    return {row[0]: row[1] for row in rows}


def render() -> None:
    st.subheader("Przeliczenie wskaźników")
    
        # =========================================================
    # Cache clear – tylko raz na sesję (REAL RUN)
    # =========================================================
    if "cache_cleared_for_real_run" not in st.session_state:
        st.session_state["cache_cleared_for_real_run"] = False

    st.markdown("""
    <style>
    /* Kontener tabeli */
    .indikatory-table {
        width: 100%;
        max-width: 100%;
        table-layout: fixed;
        border-collapse: collapse;
    }

    /* Komórki */
    .indikatory-table th,
    .indikatory-table td {
        padding: 8px 10px;
        vertical-align: top;
        text-align: left;
        overflow-wrap: anywhere;
        word-break: break-word;
    }

    /* Kolumna: wskaźnik */
    .indikatory-table th:nth-child(1),
    .indikatory-table td:nth-child(1) {
        width: 18%;
    }

    /* Kolumna: Opis wskaźnika (GŁÓWNA) */
    .indikatory-table th:nth-child(2),
    .indikatory-table td:nth-child(2) {
        width: 26%;
        white-space: normal;
    }

    /* Kolumna: Wymagane wskaźniki */
    .indikatory-table th:nth-child(3),
    .indikatory-table td:nth-child(3) {
        width: 18%;
    }

    /* Kolumna: Opis wymaganych */
    .indikatory-table th:nth-child(4),
    .indikatory-table td:nth-child(4) {
        width: 26%;
        white-space: normal;
    }

    /* Kolumna: Liczba zależności */
    .indikatory-table th:nth-child(5),
    .indikatory-table td:nth-child(5) {
        width: 12%;
        text-align: center;
    }
                
    /* ============================= */
    /* Tabela RAPORTU wykonania      */
    /* ============================= */

    .report-table {
        width: 100%;
        table-layout: fixed;
        border-collapse: collapse;
    }

    .report-table th,
    .report-table td {
        padding: 8px 10px;
        text-align: center;
        white-space: nowrap;
    }

    /* 1: Wskaźnik */
    .report-table th:nth-child(1),
    .report-table td:nth-child(1) {
        width: 20%;
        text-align: left;
    }

    /* 2: Spółka */
    .report-table th:nth-child(2),
    .report-table td:nth-child(2) {
        width: 10%;
    }

    /* 3: Dodane */
    .report-table th:nth-child(3),
    .report-table td:nth-child(3) {
        width: 12%;
    }

    /* 4: Zmienione */
    .report-table th:nth-child(4),
    .report-table td:nth-child(4) {
        width: 12%;
    }

    /* 5: Nie obliczalne */
    .report-table th:nth-child(5),
    .report-table td:nth-child(5) {
        width: 14%;
    }

    /* 6: Status */
    .report-table th:nth-child(6),
    .report-table td:nth-child(6) {
        width: 12%;
    }

    /* 7: Pokrycie % */
    .report-table th:nth-child(7),
    .report-table td:nth-child(7) {
        width: 20%;
    }

    </style>
    """, unsafe_allow_html=True)





# ----------------------------------------------
# miejsce z którego zabrałem Pipeline wskaźników
# ----------------------------------------------


# do przeniesienia - start
    # =========================================================
    # Mini-walidacja pipeline (read-only)
    # =========================================================

    st.markdown("### Pipeline wskaźników")

    try:
        validate_pipeline()
        pipeline_valid = True
        st.success("Pipeline jest spójny z registry wskaźników.")
    except Exception as e:
        pipeline_valid = False
        st.error("Pipeline NIE jest spójny z registry wskaźników.")
        st.exception(e)

    st.markdown("**Kolejność wyliczania wskaźników:**")
    st.code(
        "\n".join(
            f"{idx + 1}. {code}"
            for idx, code in enumerate(INDICATOR_PIPELINE)
        ),
        language="text",
    )
    
    # =========================================================
    # Zależności wskaźników (required_indicators) – read-only
    # =========================================================

    st.markdown("### Zależności wskaźników")

    descriptions = load_indicator_descriptions()

    rows = []
    for code in INDICATOR_PIPELINE:
        indicator = INDICATORS_REGISTRY.get(code)
        required = getattr(indicator, "required_indicators", []) or []

        rows.append(
            {
                "Wskaźnik": code,
                "Opis wskaźnika": descriptions.get(code) or "—",
                "Wymagane wskaźniki": ", ".join(required) if required else "—",
                "Opis wymaganych": (
                    ", ".join(
                        descriptions.get(r) or r
                        for r in required
                    )
                    if required else "—"
                ),
                "Liczba zależności": len(required),
            }
        )
# do przeniesienia - koniec



    deps_df = pd.DataFrame(rows)

    with st.container():
        st.markdown(
            deps_df.to_html(
                index=False,
                escape=False,
                classes="indikatory-table"
            ),
            unsafe_allow_html=True
        )



    st.markdown("### Tryb wykonania")

    # =========================================================
    # Tryb wykonania – domyślna wartość z parametrów aplikacji
    # =========================================================

    default_dry_run = get_param("UI_DEFAULT_DRY_RUN")
    default_limit_300 = get_param("CALCULATE_ONLY_300_INDICATORS")

    # Ustaw wartość domyślną TYLKO przy pierwszym renderze
    if "calc_indicators_dry_run" not in st.session_state:
        st.session_state["calc_indicators_dry_run"] = default_dry_run

    if "limit_300_indicators" not in st.session_state:
        st.session_state["limit_300_indicators"] = default_limit_300

    dry_run = st.checkbox(
        "DRY-RUN (bez zapisu do DB)",
        value=st.session_state["calc_indicators_dry_run"],
        help="Symulacja wyliczeń: brak zapisu do bazy. Raport i logi będą wygenerowane.",
        key="calc_indicators_dry_run",
    )

    limit_300 = st.checkbox(
        "Ogranicz przeliczenie wskaźników do 300 ostatnich notowań",
        value=st.session_state["limit_300_indicators"],
        help="Jeśli zaznaczone, wyliczenie wskaźników będzie wykonane tylko dla 300 najnowszych notowań.",
        key="limit_300_indicators",
    )


    if dry_run:
        st.info("Tryb DRY-RUN: brak zapisu do DB - dzienne aktualizacje: 2 minuty, przeliczenie całego nowego wskaźnika: około 10 minut.")
    else:
        st.warning("Tryb REAL RUN: dane zostaną zapisane do DB (UPDATE tylko dla wartości NULL) - dzienne aktualizacje: 2 minuty, przeliczenie całego nowego wskaźnika: około 25 minut.")

    if st.button(
        "Rozpocznij wyliczenie wskaźników",
        disabled=not pipeline_valid,
    ):
        status_line = st.empty()
        with st.spinner("Wyliczanie wskaźników w toku..."):
            try:
                # =========================================================
                # REAL RUN → czyść cache tylko raz na sesję
                # =========================================================
                if not dry_run:
                    if not st.session_state["cache_cleared_for_real_run"]:
                        st.cache_data.clear()
                        st.cache_resource.clear()
                        st.session_state["cache_cleared_for_real_run"] = True

                # =========================================================
                # UI callback: aktualizacja statusu jednej firmy
                # =========================================================
                def ui_company_progress(company_id: int):
                    status_line.info(f"Przeliczenie firmy: ID={company_id}")


                # Import lokalny (żeby nie obciążać czasu startu UI)                                
                from analysis.calculated_indicators.pipeline import run_all_indicators_with_logging

                # ---------------------------------------------
                # Callback UI: aktualizacja statusu JEDNEJ firmy
                # ---------------------------------------------
                # Callback UI: aktualizacja statusu (wskaźnik + firma)
                def on_company_start(indicator_code: str, company_id: int):
                    status_line.info(
                        f"Przeliczanie parametru: {indicator_code}, firma: ID={company_id}"
                    )


                # Obsługa limitowania do 300 sesji
                limit_sessions = 300 if limit_300 else None
                reports, log_file = run_all_indicators_with_logging(
                    company_ids=None,
                    dry_run=dry_run,
                    on_company_start=on_company_start,
                    limit_sessions=limit_sessions,
                )

                if dry_run:
                    status_line.success("DRY RUN zakończony — brak zapisu do bazy danych")
                else:
                    status_line.success("Zapis do bazy danych zakończony")


                st.success("Wyliczenie wskaźników zakończone")

                if dry_run:
                    status_line.info("DRY RUN zakończony – brak zapisu do bazy danych.")
                else:
                    status_line.info("Zapis do bazy danych zakończony.")

                st.markdown("### Raport")


                report_df = pd.DataFrame(reports)

                # =========================================================
                # UI: przygotowanie danych (formatowanie na nazwach technicznych)
                # =========================================================

                # Uzupełnij brakujące kolumny, żeby tabela była stabilna
                for col in ["company_id", "rows_inserted", "rows_updated", "rows_marked_not_computable", "status", "reason"]:
                    if col not in report_df.columns:
                        report_df[col] = pd.NA

                # Formatowanie liczb (bez .0) - NAJPIERW robimy numeryczne typy
                for col in ["company_id", "rows_inserted", "rows_updated", "rows_marked_not_computable"]:
                    if col in report_df.columns:
                        report_df[col] = pd.to_numeric(report_df[col], errors="coerce")

                # coverage_pct liczymy dopiero po konwersji do numeric
                if {"rows_inserted", "rows_updated"}.issubset(report_df.columns):
                    denom = pd.to_numeric(report_df["rows_inserted"], errors="coerce").astype("float64")
                    numer = pd.to_numeric(report_df["rows_updated"], errors="coerce").astype("float64")

                    # unikamy dzielenia przez 0 bez degradacji dtype
                    denom = denom.mask(denom == 0, np.nan)
                    report_df["coverage_pct"] = ((numer / denom) * 100).round(2)

               
                # separator tysięcy + brak .0
                def fmt_int(x):
                    if pd.isna(x):
                        return "—"
                    return f"{int(x):,}".replace(",", " ")

                if "company_id" in report_df.columns:
                    report_df["company_id"] = report_df["company_id"].apply(fmt_int)

                for col in ["rows_inserted", "rows_updated", "rows_marked_not_computable"]:
                    if col in report_df.columns:
                        report_df[col] = report_df[col].apply(fmt_int)

                # Status/Powód: zamiast NaN pokaż kreskę
                for col in ["status", "reason"]:
                    if col in report_df.columns:
                        report_df[col] = report_df[col].fillna("—")

                # Pokrycie: format + badge
                if "coverage_pct" in report_df.columns:
                    report_df["coverage_pct"] = report_df["coverage_pct"].apply(
                        lambda x: f"{x:.2f} %" if pd.notna(x) else "—"
                    )
                    report_df["coverage_pct"] = report_df["coverage_pct"].apply(coverage_badge)

                # =========================================================
                # UI: krótkie polskie nazwy kolumn (NA KONIEC)
                # =========================================================


                COLUMN_RENAME_MAP = {
                    "indicator": "Wskaźnik",
                    "rows_inserted": "Możliwe dodane",
                    "rows_updated": "Zmienione",
                    "rows_marked_not_computable": "Nie obliczalne",
                    "status": "Status",
                    "coverage_pct": "Pokrycie %",
                }

                report_df = report_df.rename(columns=COLUMN_RENAME_MAP)

                # =========================================================
                # UI: wybór i kolejność kolumn (żeby nie "przybywały" przypadkowe)
                # =========================================================

                columns_to_show = ["Wskaźnik", "Dodane", "Zmienione", "Nie obliczalne", "Status", "Pokrycie %"]
                report_df = report_df[[c for c in columns_to_show if c in report_df.columns]]

                # Render
                if report_df.empty:
                    st.info("Brak danych w raporcie (pusta lista).")
                else:
                    st.markdown(
                        report_df.to_html(
                            index=False,
                            escape=False,
                            classes="report-table"
                        ),
                        unsafe_allow_html=True
                    )




                st.markdown("### Logi")
                st.info(f"Log zapisany w pliku:\n\n{log_file}")

            except Exception as e:
                st.error("Błąd podczas wyliczania wskaźników")
                st.exception(e)

