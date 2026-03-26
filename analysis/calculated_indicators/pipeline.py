# analysis/calculated_indicators/pipeline.py

"""
Pipeline obliczania WSZYSTKICH wskaźników wyliczanych lokalnie.

Założenia:
- jawna, ręczna kolejność
- brak dynamicznego grafu zależności
- idempotentność (bezpieczne wielokrotne uruchomienia)
"""

from typing import Iterable, List, Dict

from analysis.calculated_indicators.dispatcher import run_indicator
from analysis.calculated_indicators.registry import INDICATORS_REGISTRY
from analysis.calculated_indicators.utils.db_helpers import (
    fetch_companies,
    fetch_company_ids_needing_indicator,
)
from analysis.calculated_indicators.utils.calc_flags import flag_for
from analysis.calculated_indicators.utils.db_helpers import fetch_indicator_columns




# JAWNA KOLEJNOŚĆ LICZENIA WSKAŹNIKÓW
INDICATOR_PIPELINE: List[str] = [
    "average_volume_20d",
    "obv",
    "vwap_20d",
    "atr_14",
    "max_drawdown_252d",
    "tqs_60d",
    "momentum_12m",
    "volatility_20d",
    "sma_20",
    "sma_50",
    "sma_200",
    "ema_12",
    "ema_20",
    "ema_26",
    "ema_50",
    "ema_200",
    "macd_line",
    "macd_signal",
    "macd_hist",
    "rsi_14",
    "sharpe_20d",
    "earnings_yield",
    # FUTURE / labels (stub na teraz; implementacja później)
    "fut_barrier_5p_3p_5d",
    "fut_barrier_20p_12p_20d",
    "fut_barrier_20p_12p_60d",
    "fut_barrier_50p_20p_120d",
    "fut_barrier_100p_50p_20d",
    "fut_barrier_50p_20p_20d",
    "fut_barrier_50p_20p_60d",
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



def validate_pipeline() -> None:
    db_columns = set(fetch_indicator_columns())  # kolumny indicators_daily

    for code in INDICATOR_PIPELINE:
        if code not in INDICATORS_REGISTRY:
            raise ValueError(f"Indicator '{code}' not found in registry")

        if code not in db_columns:
            raise RuntimeError(
                f"DB schema mismatch: column '{code}' missing in indicators_daily. "
                f"Run migration before pipeline."
            )

def run_all_indicators(
    company_ids: Iterable[int] | None = None,
    dry_run: bool = False,
    on_company_start=None,      # callback: on_company_start(indicator_code, company_id)
    limit_sessions: int | None = None,
) -> List[Dict]:

    """
    Uruchamia pełny pipeline wskaźników w ustalonej kolejności.

    Parametry:
    - company_ids : opcjonalna lista company_id (None = wszystkie)
    - dry_run     : True = bez zapisu do DB

    Zwraca:
    - listę raportów z dispatcherów
    """
    validate_pipeline()

    reports: List[Dict] = []

    for indicator_code in INDICATOR_PIPELINE:
        last_company_id = None   # <<< RESET NA NOWY WSKAŹNIK

        indicator = INDICATORS_REGISTRY[indicator_code]
        bit = flag_for(indicator_code)


        # tylko spółki, które mają cokolwiek do uzupełnienia i nie są w całości NOT_COMPUTABLE
        if company_ids is not None:
            base_company_ids = list(company_ids)
        else:
            base_company_ids = fetch_companies()["company_id"].tolist()

        company_id_list = fetch_company_ids_needing_indicator(
            indicator_code=indicator_code,
            bit=bit,
            company_ids=base_company_ids,
        )

        if not company_id_list:
            reports.append({
                "indicator": indicator_code,
                "status": "pominięto",
                "reason": "brak rekordów do przeliczenia",
            })
            continue



        # ---------------------------------------------------------
        # Agregacja raportu per wskaźnik (bez company_id w raporcie)
        # ---------------------------------------------------------
        rows_inserted_total = 0
        rows_updated_total = 0
        rows_marked_not_computable_total = 0

        errors = 0
        reasons: list[str] = []

        for company_id in company_id_list:
            if on_company_start and company_id != last_company_id:
                on_company_start(
                    indicator_code=indicator_code,
                    company_id=company_id,
                )
                last_company_id = company_id


            try:
                report = run_indicator(
                    company_id=company_id,
                    indicator_code=indicator_code,
                    indicator=indicator,
                    dry_run=dry_run,
                    limit_sessions=limit_sessions,
                )



                rows_inserted_total += int(report.get("rows_inserted", 0) or 0)
                rows_updated_total += int(report.get("rows_updated", 0) or 0)
                rows_marked_not_computable_total += int(report.get("rows_marked_not_computable", 0) or 0)

            except ValueError as e:
                errors += 1
                reasons.append(str(e))


        # Jeden wiersz raportu na wskaźnik (zgodnie z ADR-014)
        reports.append(
            {
                "indicator": indicator_code,
                "companies": len(company_id_list),
                "rows_inserted": rows_inserted_total,
                "rows_updated": rows_updated_total,
                "rows_marked_not_computable": rows_marked_not_computable_total,

                # dla kompatybilności z istniejącym logowaniem w run_all_indicators_with_logging
                "rows_skipped": rows_marked_not_computable_total,

                # status/powód – tylko jeśli były błędy
                "status": "OK" if errors == 0 else "skipped",
                "reason": "—" if errors == 0 else f"errors={errors}; " + "; ".join(reasons[:3]),
            }
        )


    return reports

# ============================================================
# LOGOWANIE (spójne z importami) + wrapper dla UI
# ============================================================

from pathlib import Path
from datetime import datetime
import logging

from config.etl import INDICATORS_LOG_DIR


def setup_logging_calculated_indicators() -> Path:
    """
    Konfiguracja logowania dla wyliczania wskaźników (calculated indicators).

    - katalog logów: import/prd/indicators/logs (INDICATORS_LOG_DIR)
    - nazwa pliku: calculate_indicators_daily_YYYYMMDD_HHMMSS.log
    - zwraca ścieżkę logu do pokazania w UI
    """
    INDICATORS_LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_file = INDICATORS_LOG_DIR / (
        f"calculate_indicators_daily_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logging.info("=== START CALCULATE INDICATORS DAILY ===")
    logging.info("Log file: %s", log_file)

    return log_file


def run_all_indicators_with_logging(
    company_ids: Iterable[int] | None = None,
    dry_run: bool = False,
    on_company_start=None,
    limit_sessions: int | None = None,
):

    """
    Wrapper dla UI:
    - ustawia logowanie do pliku
    - uruchamia pipeline
    - loguje podsumowanie
    - zwraca (reports, log_file)
    """
    log_file = setup_logging_calculated_indicators()

    logging.info("PARAMS | dry_run=%s | company_ids=%s", dry_run, "ALL" if company_ids is None else "CUSTOM")
    if dry_run:
        logging.info("TRYB DRY-RUN: brak zapisu do DB")

    reports = run_all_indicators(
        company_ids=company_ids,
        dry_run=dry_run,
        on_company_start=on_company_start,
        limit_sessions=limit_sessions,
    )


    # Podsumowanie per wskaźnik
    for r in reports:
        indicator = r.get("indicator")
        status = r.get("status", "OK")
        companies = r.get("companies")
        rows_inserted = r.get("rows_inserted")
        rows_updated = r.get("rows_updated")
        rows_skipped = r.get("rows_skipped")
        reason = r.get("reason")

        if status == "skipped":
            logging.warning("IND=%s | status=SKIPPED | reason=%s", indicator, reason)
        else:
            logging.info(
                "IND=%s | companies=%s | inserted=%s | updated=%s | skipped=%s",
                indicator,
                companies,
                rows_inserted,
                rows_updated,
                rows_skipped,
            )

    logging.info("=== END CALCULATE INDICATORS DAILY ===")

    return reports, log_file
