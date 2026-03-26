from __future__ import annotations
from typing import Dict, List
import logging

import pandas as pd

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from analysis.calculated_indicators.base import CalculatedIndicator

from analysis.calculated_indicators.registry import INDICATORS_REGISTRY
from analysis.calculated_indicators.utils.db_helpers import (
    fetch_prices,
    fetch_indicator_state,
    fetch_indicator_values,
    insert_missing_indicator_rows,
    update_indicator_values,
    mark_not_computable,
    filter_dates_not_flagged,
)


from analysis.calculated_indicators.utils.calc_flags import flag_for

logger = logging.getLogger(__name__)

def _terminal_nan_dates(values_df: pd.DataFrame, indicator_code: str) -> list:
    """
    Zwraca daty, które są NaN/NULL *terminalnie*:
    - prefix NaN przed pierwszą wartością nie-NaN
    - suffix NaN po ostatniej wartości nie-NaN

    Bezpieczne: NIE oznacza NaN w środku szeregu.
    Jeśli brak jakichkolwiek wartości nie-NaN -> zwraca [] (nie zamykamy wskaźnika).
    """
    if values_df.empty:
        return []

    df = values_df.sort_values("trade_date")
    is_ok = ~df[indicator_code].isna()

    if not is_ok.any():
        # brak jakichkolwiek policzalnych wartości -> NIE oznaczamy nic terminalnie
        return []

    first_valid_date = df.loc[is_ok, "trade_date"].iloc[0]
    last_valid_date = df.loc[is_ok, "trade_date"].iloc[-1]

    prefix = df[(df["trade_date"] < first_valid_date) & (df[indicator_code].isna())]["trade_date"].tolist()
    suffix = df[(df["trade_date"] > last_valid_date) & (df[indicator_code].isna())]["trade_date"].tolist()

    return prefix + suffix


def run_indicator(
    company_id: int,
    indicator_code: str,
    indicator: "CalculatedIndicator",
    dry_run: bool,
    limit_sessions: int | None = None,
) -> Dict:
    """
    Executes calculation for a single indicator and company.
    Fully idempotent and optimized:
    - compute() is NEVER called if nothing can be computed
    - NOT_COMPUTABLE flags fully cut off future runs
    """

    report = {
        "rows_inserted": 0,
        "rows_updated": 0,
        "rows_marked_not_computable": 0,
    }

    # ------------------------------------------------------------------
    # 1. Load prices and existing indicator state
    # ------------------------------------------------------------------
    prices_df = fetch_prices(company_id)
    if limit_sessions is not None and not prices_df.empty:
        prices_df = prices_df.sort_values("trade_date", ascending=False).head(limit_sessions).sort_values("trade_date")
    if prices_df.empty:
        # logger.info(f"[SKIP] {indicator_code} | company_id={company_id} | no prices")
        return report

    required_indicators = indicator.required_indicators or []

    if required_indicators:
        indicators_df = fetch_indicator_values(
            company_id=company_id,
            indicator_codes=required_indicators,
        )
    else:
        indicators_df = None


    # ------------------------------------------------------------------
    # 2. Determine missing trade dates
    # ------------------------------------------------------------------
    state_df = fetch_indicator_state(company_id=company_id, indicator_code=indicator_code)
    missing_trade_dates = state_df[state_df[indicator_code].isna()]["trade_date"].tolist()


    if not missing_trade_dates:
        # logger.info(f"[SKIP] {indicator_code} | company_id={company_id} | no missing dates")
        return report

    # ------------------------------------------------------------------
    # 3. Insert missing indicator rows (structure only)
    # ------------------------------------------------------------------
    if not dry_run:
        insert_missing_indicator_rows(company_id=company_id, trade_dates=missing_trade_dates)
        report["rows_inserted"] += len(missing_trade_dates)

    # ------------------------------------------------------------------
    # 4. Filter out trade_dates already marked as NOT_COMPUTABLE (bit=1)
    # ------------------------------------------------------------------
    bit = flag_for(indicator_code)

    if not dry_run:
        # ważne: działa poprawnie po insert_missing_indicator_rows,
        # bo filter_dates_not_flagged JOINuje do indicators_daily
        missing_trade_dates = filter_dates_not_flagged(
            company_id=company_id,
            trade_dates=missing_trade_dates,
            bit=bit,
        )

        if not missing_trade_dates:
            # logger.info(f"[SKIP] {indicator_code} | company_id={company_id} | all missing dates are NOT_COMPUTABLE")
            return report


    # ------------------------------------------------------------------
    # 5. Compute indicator ONLY for remaining dates
    # ------------------------------------------------------------------
    values_series = indicator.compute(
        prices_df=prices_df,
        indicators_df=indicators_df,
    )

    values_df = (
        values_series.loc[values_series.index.isin(missing_trade_dates)]
        .rename(indicator_code)
        .reset_index()
    )

    raw_values_df = values_df.copy()


    # ------------------------------------------------------------------
    # FUTURE vs CALCULATED – semantyka zapisu wartości 0
    # ------------------------------------------------------------------
    # Dla wskaźników typu 'calculated':
    #   0 = brak sygnału → traktujemy jak NULL (nie zapisujemy)
    # Dla wskaźników typu 'future' (fut_*):
    #   0 = istotna wartość → MUSI zostać zapisana
    

    if values_df.empty:
        # logger.info(f"[SKIP] {indicator_code} | company_id={company_id} | compute returned empty")
        return report

    # ------------------------------------------------------------------
    # 6. Split computable vs non-computable
    # ------------------------------------------------------------------
    ok_df = values_df[~values_df[indicator_code].isna()]
    bad_df = values_df[values_df[indicator_code].isna()]

    # ------------------------------------------------------------------
    # 6b. Mark terminal NaN (window edges) as NOT_COMPUTABLE
    # ------------------------------------------------------------------
    if not dry_run and not bad_df.empty:
        terminal_dates = _terminal_nan_dates(
            values_df=raw_values_df,
            indicator_code=indicator_code,
        )

        if terminal_dates:
            marked = mark_not_computable(
                company_id=company_id,
                indicator_code=indicator_code,
                trade_dates=terminal_dates,
            )
            report["rows_marked_not_computable"] += marked


    # ------------------------------------------------------------------
    # 7. Update computable values
    # ------------------------------------------------------------------

    if not dry_run and not ok_df.empty:
        updated = update_indicator_values(
            company_id=company_id,
            indicator_code=indicator_code,
            df=ok_df,
            bit=bit,
        )
        report["rows_updated"] += updated

    return report


def run_all_indicators(
    company_id: int,
    dry_run: bool,
) -> Dict[str, Dict]:
    """
    Runs all registered indicators for a single company.
    """

    results: Dict[str, Dict] = {}

    for indicator_code, indicator in INDICATORS_REGISTRY.items():
        logger.info(
            f"[START] indicator={indicator_code} | company_id={company_id}"
        )

        result = run_indicator(
            company_id=company_id,
            indicator_code=indicator_code,
            indicator=indicator,
            dry_run=dry_run,
        )

        results[indicator_code] = result

        logger.info(
            f"[END] indicator={indicator_code} | company_id={company_id} | {result}"
        )

    return results
