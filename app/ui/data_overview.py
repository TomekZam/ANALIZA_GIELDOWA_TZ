# app/ui/data_overview.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple
import pandas as pd
import streamlit as st
from config.app_params import get_param
from etl.data_provider import (
    get_companies,
    get_prices_daily,
    get_indicators_daily,
    get_indicators_dictionary,
    get_company_ids_for_tickers,
    get_company_ids_for_tickers_csv,
    get_prices_daily_date_range,
    get_data_source_label,
    init_data_mode,
    parse_tickers,
    get_last_prices_for_company_ids,

)
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
# Dokumentacja kontrolki tabeli AG Grid:
# https://pypi.org/project/streamlit-aggrid/
# https://www.ag-grid.com/javascript-data-grid/getting-started/

from app.ui.column_metadata import COLUMN_LABELS, COLUMN_GROUPS, INDICATOR_TOOLTIPS
import plotly.graph_objects as go
from datetime import date
from plotly.subplots import make_subplots
from app.ml.ml_datasets import clear_ml_datasets


# ============================================================
# Klucz session_state          | Nazwa logiczna   | Rola                               
# ---------------------------- | ---------------- | ---------------------------------- 

# Pierwsze 4 DF = maksymalny zakres danych (lewa sekcja):
# do_df_companies              |   df_companies   | Słownik spółek (master data)  - wszystkie dostępne ograniczone parametrem "LOAD_TICKERS"     
# do_df_prices_daily           |   df_prices      | Notowania dzienne (OHLCV + ticker)  - wszystkie dostępne ograniczone parametrem "LOAD_TICKERS"
# do_df_indicators_daily       |   df_ind         | Wskaźniki techniczne  - wszystkie dostępne ograniczone parametrem "LOAD_TICKERS"           
# do_df_indicators_dictionary  |   df_ind_dict    | Słownik wskaźników  - wszystkie dostępne ograniczone parametrem "LOAD_TICKERS"               

# Ostatni DF = zakres roboczy / analityczny (prawa sekcja):
# do_df_market_view            |   df_market      | Jedna firma. Zbiorczy DF do wizualizacji łączący dane z kilku df (df_companies + df_prices + df_ind)     
# do_df_market_all             |   df_market_all  | Wszsytkie firmy.Zbiorczy DF do wizualizacji łączący dane z kilku df (df_companies + df_prices + df_ind)     
# Powstaje z prawego filtra: jedna spółka + filtry daty (połączenie danych 1 firmy, notowań + wskaźników)
#                              |   df_table       | Tabela ograniczona tylko do jednej firmy. Powstała z df_market na potrzeby widoku tabeli (posortowana malejąco)
# ---------------------------- | df_last_load_tickers | Lista notowań z ostatniego dostępnego dnia dla spółek z parametru "LOAD_TICKERS"



# ============================================================
# Session State Keys
# ============================================================

SSK = {
    # lewa sekcja
    "all_mode": "do_all_companies_mode",
    "avail_tickers": "do_available_tickers",
    "avail_tickers_all": "do_available_tickers_all",
    "avail_tickers_str": "do_available_tickers_str",
    "filter_tickers_str": "do_filter_tickers_str",
    "avail_date_from": "do_available_date_from",
    "avail_date_to": "do_available_date_to",
    # df-y (maksymalny zakres)
    "df_companies": "do_df_companies",
    "df_prices": "do_df_prices_daily",
    "df_ind": "do_df_indicators_daily",
    "df_ind_dict": "do_df_indicators_dictionary",
    # df zbiorczy
    "df_market": "do_df_market_view", # df dla jednej wybranej do podglądu firmy
    # df zbiorczy (WSZYSTKIE SPÓŁKI) – pod analizy globalne
    "df_market_all": "do_df_market_all",
}

FUTURE_SIGNAL_COLS = {
    "fut_signal_2",
    "fut_signal_20",
    "fut_signal_60",
    "fut_signal_120",
    "fut_signal_20_hyb",
}


# ============================================================
# UI column configuration (TEMP – do ustalenia)
# ============================================================

UI_MARKET_COLUMNS = [
    "trade_date",
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "volume",
]

# ============================================================
# Table column groups (UI)
# ============================================================

BASE_TABLE_COLUMNS = [
    "trade_date",
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "volume",
]

FUNDAMENTAL_COLUMNS = [
    "mv",
    "pe",
    "pb",
    "earnings_yield",
]

DEFAULT_CHART_INDICATORS = {
    "volume",
    "ema_50",
    "ema_200",
}


# ============================================================
# Dataclasses
# ============================================================

@dataclass(frozen=True)
class AvailableRange:
    tickers: List[str]
    date_from: str
    date_to: str


# ============================================================
# Session helpers
# ============================================================

def _ss_init_defaults() -> None:
    if SSK["all_mode"] not in st.session_state:
        st.session_state[SSK["all_mode"]] = False

    if SSK["avail_tickers"] not in st.session_state:
        st.session_state[SSK["avail_tickers"]] = parse_tickers(get_param("LOAD_TICKERS"))
    if SSK["avail_tickers_all"] not in st.session_state:
        st.session_state[SSK["avail_tickers_all"]] = list(st.session_state[SSK["avail_tickers"]])
    if SSK["avail_tickers_str"] not in st.session_state:
        st.session_state[SSK["avail_tickers_str"]] = ", ".join(st.session_state[SSK["avail_tickers"]])
    if SSK["filter_tickers_str"] not in st.session_state:
        st.session_state[SSK["filter_tickers_str"]] = st.session_state[SSK["avail_tickers_str"]]

    if SSK["avail_date_from"] not in st.session_state:
        st.session_state[SSK["avail_date_from"]] = str(get_param("LOAD_DATE_FROM"))
    if SSK["avail_date_to"] not in st.session_state:
        st.session_state[SSK["avail_date_to"]] = str(get_param("LOAD_DATE_TO"))

    for k in ("df_companies", "df_prices", "df_ind", "df_ind_dict", "df_market", "df_market_all"):
        if SSK[k] not in st.session_state:
            st.session_state[SSK[k]] = None



def _reset_all_screen_state() -> None:
    for k in (
        SSK["df_companies"],
        SSK["df_prices"],
        SSK["df_ind"],
        SSK["df_ind_dict"],
        SSK["df_market"],
        SSK["df_market_all"],
    ):
        st.session_state[k] = None




# ============================================================
# Date helpers
# ============================================================


def _clip_date_range_to_params(
    src_from: Optional[str],
    src_to: Optional[str],
) -> Tuple[str, str]:
    p_from = pd.to_datetime(get_param("LOAD_DATE_FROM"))
    p_to = pd.to_datetime(get_param("LOAD_DATE_TO"))

    if src_from:
        p_from = max(p_from, pd.to_datetime(src_from))
    if src_to:
        p_to = min(p_to, pd.to_datetime(src_to))

    return p_from.date().isoformat(), p_to.date().isoformat()


# ============================================================
# Available range logic (LEFT PANEL)
# ============================================================

def _compute_available_range_all_mode() -> AvailableRange:
    df_c = get_companies(None)
    tickers = (
        df_c["ticker"].dropna().astype(str).sort_values().tolist()
        if not df_c.empty and "ticker" in df_c.columns
        else []
    )

    src_from, src_to = get_prices_daily_date_range(None)
    eff_from, eff_to = _clip_date_range_to_params(src_from, src_to)

    return AvailableRange(
        tickers=tickers,
        date_from=eff_from,
        date_to=eff_to,
    )


def _compute_available_range_default() -> AvailableRange:
    return AvailableRange(
        tickers=parse_tickers(get_param("LOAD_TICKERS")),
        date_from=str(get_param("LOAD_DATE_FROM")),
        date_to=str(get_param("LOAD_DATE_TO")),
    )


# ============================================================
# Data loading
# ============================================================

def _load_max_datasets(tickers: List[str], date_from: str, date_to: str) -> None:
    company_ids = get_company_ids_for_tickers(tickers)

    with st.spinner("Trwa ładowanie danych (companies / prices / indicators). Może potrwać kilka minut"):
        st.session_state[SSK["df_companies"]] = get_companies(company_ids or None)
        st.session_state[SSK["df_prices"]] = get_prices_daily(company_ids or None, date_from, date_to)
        st.session_state[SSK["df_ind"]] = get_indicators_daily(company_ids or None, date_from, date_to)
        st.session_state[SSK["df_ind_dict"]] = get_indicators_dictionary()


def _refresh_df_last_load_tickers_from_ui() -> None:
    """
    Odświeża snapshot rynku (df_last_load_tickers)
    na podstawie aktualnej listy tickerów z UI
    (Dostępny zakres danych / Firmy).
    """
    tickers: list[str] = st.session_state.get(SSK["avail_tickers"], [])

    if not tickers:
        st.session_state["df_last_load_tickers"] = None
        return

    company_ids = get_company_ids_for_tickers(tickers)

    if company_ids:
        st.session_state["df_last_load_tickers"] = (
            get_last_prices_for_company_ids(company_ids)
        )
    else:
        st.session_state["df_last_load_tickers"] = None


def _build_market_view_df(
    selected_ticker: str,
) -> pd.DataFrame:
    df_c = st.session_state[SSK["df_companies"]]
    df_p = st.session_state[SSK["df_prices"]]
    df_i = st.session_state[SSK["df_ind"]]

    if df_c is None or df_p is None or df_i is None:
        return pd.DataFrame()

    # --- identyfikacja spółki ---
    company_row = df_c.loc[df_c["ticker"] == selected_ticker].iloc[0]
    company_id = int(company_row["company_id"])
    company_name = company_row["company_name"]

    # --- notowania ---
    df_p = df_p[df_p["company_id"] == company_id].copy()
    df_p["trade_date"] = pd.to_datetime(df_p["trade_date"], errors="coerce")


    # --- wskaźniki ---
    df_i = df_i[df_i["company_id"] == company_id].copy()
    if not df_i.empty:
        df_i["trade_date"] = pd.to_datetime(df_i["trade_date"], errors="coerce")

    # --- merge ---
    df_out = df_p.merge(df_i, on=["company_id", "trade_date"], how="left")

    # --- ticker: porządek po merge ---
    if "ticker_x" in df_out.columns:
        df_out = df_out.rename(columns={"ticker_x": "ticker"})

    # --- usunięcie kolumn technicznych / ETL ---
    df_out = df_out.drop(
        columns=[
            c for c in [
                "ticker_y",
                "created_at",
                "created_at_x",
                "created_at_y",
                "modified_at",
                "source_ticker",
                "calc_flags",
            ]
            if c in df_out.columns
        ],
        errors="ignore",
    )

    # --- company_name + name ---
    df_out["company_name"] = company_name
    df_out["name"] = df_out["ticker"] + " (" + df_out["company_name"] + ")"

    # --- normalizacja daty (bez czasu) ---
    df_out["trade_date"] = df_out["trade_date"].dt.strftime("%Y-%m-%d")

    return df_out


def _build_market_all_df() -> pd.DataFrame:
    """
    Buduje DF market-wide (wszystkie spółki) z danych już załadowanych do session_state:
    - prices_daily (p)
    - indicators_daily (i)
    - companies (c)
    Join: p LEFT JOIN i po (company_id, trade_date) + join companies po company_id
    """
    df_c = st.session_state.get(SSK["df_companies"])
    df_p = st.session_state.get(SSK["df_prices"])
    df_i = st.session_state.get(SSK["df_ind"])

    if not isinstance(df_p, pd.DataFrame) or df_p.empty:
        return pd.DataFrame()

    # indicators mogą być puste – ale join i tak ma działać (LEFT JOIN)
    if not isinstance(df_i, pd.DataFrame):
        df_i = pd.DataFrame()

    p = df_p.copy()
    i = df_i.copy()

    # standaryzacja dat
    if "trade_date" in p.columns:
        p["trade_date"] = pd.to_datetime(p["trade_date"], errors="coerce")
        p = p.dropna(subset=["trade_date"])
    if not i.empty and "trade_date" in i.columns:
        i["trade_date"] = pd.to_datetime(i["trade_date"], errors="coerce")
        i = i.dropna(subset=["trade_date"])

    # join prices + indicators po (company_id, trade_date) — dokładnie jak w SQL
    if not i.empty:
        df = p.merge(i, on=["company_id", "trade_date"], how="left")
    else:
        df = p

    # join companies (ticker + company_name)
    if isinstance(df_c, pd.DataFrame) and not df_c.empty and "company_id" in df.columns:
        keep_c = [c for c in ["company_id", "ticker", "company_name"] if c in df_c.columns]
        if keep_c:
            df = df.merge(
                df_c[keep_c].drop_duplicates("company_id"),
                on="company_id",
                how="left",
            )

    # porządki po potencjalnych duplikatach kolumn
    df = df.loc[:, ~df.columns.duplicated()]

    return df.reset_index(drop=True)



def _prepare_market_table_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    cols = [c for c in UI_MARKET_COLUMNS if c in df.columns]
    return df[cols].copy()


def _format_numeric_columns_for_table(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue

        # nie ruszamy intów (wolumen, OBV, itp.)
        if pd.api.types.is_integer_dtype(df[col]):
            continue

        series = df[col].dropna()
        if series.empty:
            continue

        max_val = series.abs().max()

        # bardzo duże liczby -> zostaw (np. mv)
        if max_val > 1_000_000:
            continue

        # sprawdź "dokładność"
        decimals = series.astype(str).str.split(".").str[1].str.len()
        max_decimals = decimals.max()

        if max_decimals and max_decimals > 6:
            df[col] = df[col].round(6)
        else:
            df[col] = df[col].round(2)

    return df


def format_change_with_arrow(value: float | None) -> str:
    if value is None or pd.isna(value):
        return ""

    value = float(value)
    formatted = f"{abs(value):,.2f}".replace(",", " ")

    if value > 0:
        return f"▲ {formatted}"
    if value < 0:
        return f"▼ {formatted}"
    return f"— {formatted}"



def render_chart_section(selected_indicators: list[str]):
    """
    Wariant B: 2 panele (subplots)
    - góra: cena + trendy (SMA/EMA/VWAP)
    - dół: oscylatory / momentum / zmienność / future / inne
    """

    df_market = st.session_state.get(SSK["df_market"])
    if df_market is None or df_market.empty:
        st.info("Brak danych do wyświetlenia wykresu.")
        return

    # --------------------------------------------------
    # Przygotowanie danych
    # --------------------------------------------------
    df = df_market.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
    df = df.dropna(subset=["trade_date"]).sort_values("trade_date")

    min_date = df["trade_date"].min().date()
    max_date = df["trade_date"].max().date()

    # --------------------------------------------------
    # Kontrolki UI
    # --------------------------------------------------
    # st.subheader("Wykres cenowy")

    col1, col2 = st.columns(2)
    with col1:
        date_from = st.date_input(
            "Data od",
            value=min_date,
            min_value=min_date,
            max_value=max_date,
            key="chart_date_from",
        )
    with col2:
        date_to = st.date_input(
            "Data do",
            value=max_date,
            min_value=min_date,
            max_value=max_date,
            key="chart_date_to",
        )

    if date_from > date_to:
        st.warning("Data początkowa nie może być większa niż data końcowa.")
        return





    # --------------------------------------------------
    # Filtrowanie danych pod wykres
    # --------------------------------------------------
    mask = (
        (df["trade_date"].dt.date >= date_from)
        & (df["trade_date"].dt.date <= date_to)
    )
    df_chart = df.loc[mask]
    if df_chart.empty:
        st.warning("Brak danych w wybranym zakresie dat.")
        return

    # --------------------------------------------------
    # Routing wskaźników: góra (price overlay) vs dół (oscylatory)
    # --------------------------------------------------
    price_overlay = set(COLUMN_GROUPS.get("trends", {}).get("columns", [])) | {"vwap_20d"}

    top_inds = [
        c for c in selected_indicators
        if c in price_overlay
    ]

    future_signal_inds = [
        c for c in selected_indicators
        if c in FUTURE_SIGNAL_COLS
    ]

    bottom_inds = [
        c for c in selected_indicators
        if c not in price_overlay and c not in FUTURE_SIGNAL_COLS
    ]

    # --------------------------------------------------
    # Subplots (2 panele)
    # --------------------------------------------------
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.7, 0.3],
    )

    # --- Panel 1: cena ---
    fig.add_trace(
        go.Scatter(
            x=df_chart["trade_date"],
            y=df_chart["close_price"],
            mode="lines",
            name="Zamknięcie",
            line=dict(width=2),
            hovertemplate=(
                "Data: %{x|%Y-%m-%d}<br>"
                "Zamknięcie: %{y:.2f}<extra></extra>"
            ),
        ),
        row=1,
        col=1,
    )

    # --- Panel 1: trendy (SMA/EMA/VWAP) ---
    for ind in top_inds:
        label = COLUMN_LABELS.get(ind, ind)
        fig.add_trace(
            go.Scatter(
                x=df_chart["trade_date"],
                y=df_chart[ind],
                mode="lines",
                name=label,
                line=dict(width=1),
                hovertemplate=(
                    "Data: %{x|%Y-%m-%d}<br>"
                    f"{label}: %{{y:.4f}}<extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )

    # --- Panel 1: sygnały future jako zdarzenia na cenie ---
    for ind in future_signal_inds:
        label = COLUMN_LABELS.get(ind, ind)
        s = pd.to_numeric(df_chart[ind], errors="coerce")

        marks = df_chart.loc[s.notna() & (s != 0), ["trade_date", "close_price"]].copy()
        if marks.empty:
            continue

        marks["val"] = s.loc[marks.index].astype(int)

        # markery
        fig.add_trace(
            go.Scatter(
                x=marks["trade_date"],
                y=marks["close_price"],
                mode="markers",
                name=label,
                marker=dict(size=9),
                hovertemplate=(
                    "Data: %{x|%Y-%m-%d}<br>"
                    "Cena: %{y:.2f}<br>"
                    f"{label}: %{{text}}<extra></extra>"
                ),
                text=marks["val"].astype(str),
            ),
            row=1,
            col=1,
        )

        # tekst +1 / -1
        fig.add_trace(
            go.Scatter(
                x=marks["trade_date"],
                y=marks["close_price"] * 1.01,
                text=marks["val"].astype(str),
                mode="text",
                textposition="top center",
                textfont=dict(size=12),
                showlegend=False,
                hoverinfo="skip",
            ),
            row=1,
            col=1,
        )



    # --- Panel 2: oscylatory / reszta ---
    for ind in bottom_inds:
        label = COLUMN_LABELS.get(ind, ind)
        fig.add_trace(
            go.Scatter(
                x=df_chart["trade_date"],
                y=df_chart[ind],
                mode="lines",
                name=label,
                line=dict(width=1),
                hovertemplate=(
                    "Data: %{x|%Y-%m-%d}<br>"
                    f"{label}: %{{y:.4f}}<extra></extra>"
                ),
            ),
            row=2,
            col=1,
        )

    # --------------------------------------------------
    # Layout + format osi czasu
    # --------------------------------------------------
    fig.update_layout(
        height=650,     # wysokość wykresu 
        margin=dict(l=20, r=20, t=40, b=20),
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )

    # format osi X (wymuszenie pełnej daty)
    fig.update_xaxes(tickformat="%Y-%m-%d", showgrid=True, row=2, col=1)
    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
        gridwidth=1,
        tickformat="%Y-%m-%d",
    )

    # opisy osi
    fig.update_yaxes(title_text="Cena", showgrid=True, row=1, col=1)
    fig.update_yaxes(title_text="Wskaźniki", showgrid=True, row=2, col=1)

    st.plotly_chart(fig, width="stretch")

def render_company_filter() -> None:
    df_c = st.session_state.get(SSK["df_companies"])
    if not isinstance(df_c, pd.DataFrame) or df_c.empty:
        st.info("Brak danych spółek.")
        return

    # tylko potrzebne kolumny
    df_c = df_c[["ticker", "company_name"]].dropna()

    # mapa: "TICKER (NAZWA)" -> "TICKER"
    label_to_ticker = {
        f"{row.ticker} ({row.company_name})": row.ticker
        for row in df_c.itertuples(index=False)
    }

    all_labels = sorted(label_to_ticker.keys())

    # session state
    if "filter_ticker_search" not in st.session_state:
        st.session_state["filter_ticker_search"] = ""

    if "selected_ticker" not in st.session_state:
        st.session_state["selected_ticker"] = df_c["ticker"].iloc[0]

    # st.markdown("### Filtry")

    # wyszukiwarka (NIE scrolluje)
    search = st.text_input(
        "Szukaj firmy (ticker lub nazwa)",
        value=st.session_state["filter_ticker_search"],
        key="filter_ticker_search",
    )

    filtered_labels = [
        label for label in all_labels
        if search.lower() in label.lower()
    ]

    if not filtered_labels:
        st.warning("Brak firm spełniających filtr.")
        return

    # aktualna etykieta
    current_label = next(
        (l for l, t in label_to_ticker.items()
         if t == st.session_state["selected_ticker"]),
        filtered_labels[0],
    )

    # 🔑 KLUCZ: ograniczenie wysokości = wysokość wykresu
    with st.container(height=650):
        selected_label = st.radio(
            "Firma",
            filtered_labels,
            index=(
                filtered_labels.index(current_label)
                if current_label in filtered_labels
                else 0
            ),
            label_visibility="collapsed",
        )

    selected_ticker = label_to_ticker[selected_label]

    if selected_ticker != st.session_state["selected_ticker"]:
        st.session_state["selected_ticker"] = selected_ticker
        st.session_state[SSK["df_market"]] = _build_market_view_df(selected_ticker)
        st.rerun()




def render_chart_indicators(df: pd.DataFrame) -> list[str]:
    # st.markdown("### Wskaźniki techniczne")

    selected_indicators: list[str] = []

    ordered_columns: list[str] = []
    for group_key, group in COLUMN_GROUPS.items():
        if group_key == "core":
            if "volume" in group["columns"]:
                ordered_columns.append("volume")
            continue
        ordered_columns.extend(group["columns"])

    ordered_columns = [c for c in ordered_columns if c in df.columns]

    cols_per_row = 9
    rows = [
        ordered_columns[i:i + cols_per_row]
        for i in range(0, len(ordered_columns), cols_per_row)
    ]

    for row in rows:
        cols = st.columns(cols_per_row)
        for i, indicator in enumerate(row):
            with cols[i]:
                key = f"chart_ind_{indicator}"
                default = indicator in DEFAULT_CHART_INDICATORS
                if st.checkbox(
                    COLUMN_LABELS.get(indicator, indicator),
                    value=st.session_state.get(key, default),
                    key=key,
                    help=INDICATOR_TOOLTIPS.get(indicator, ""),
                ):
                    selected_indicators.append(indicator)

    return selected_indicators





# ============================================================
# Analizy – jedna spółka (poniżej tabeli "Notowania")
# ============================================================

def _ui_label(col: str) -> str:
    return COLUMN_LABELS.get(col, col)


def _prep_df_for_analysis(df_m: pd.DataFrame) -> pd.DataFrame:
    """
    Standaryzacja do analiz:
    - trade_date -> datetime
    - sort rosnąco
    - drop NaT
    """
    df = df_m.copy()
    if "trade_date" not in df.columns:
        return pd.DataFrame()

    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
    df = df.dropna(subset=["trade_date"]).sort_values("trade_date")
    return df


def _last_valid(series: pd.Series):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return None
    return float(s.iloc[-1])


def _pct_rank(series: pd.Series, value: float) -> float:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return float("nan")
    return float((s <= value).mean() * 100.0)

def _scale_series_to_target_range(src: pd.Series, target: pd.Series) -> pd.Series:
    """
    Skaluje serię src (np. close_price) do zakresu wartości target (np. wskaźnika),
    zachowując kształt zmian. Dzięki temu można dodać "kierunek ceny" bez drugiej osi Y.
    """
    src = pd.to_numeric(src, errors="coerce")
    target = pd.to_numeric(target, errors="coerce")

    src_min, src_max = src.min(), src.max()
    tgt_min, tgt_max = target.min(), target.max()

    # zabezpieczenia: brak danych lub stała seria
    if pd.isna(src_min) or pd.isna(src_max) or pd.isna(tgt_min) or pd.isna(tgt_max):
        return pd.Series(index=src.index, data=[pd.NA] * len(src))
    if src_max == src_min or tgt_max == tgt_min:
        return pd.Series(index=src.index, data=[pd.NA] * len(src))

    src_norm = (src - src_min) / (src_max - src_min)
    return tgt_min + src_norm * (tgt_max - tgt_min)


def _safe_series(df: pd.DataFrame, col: str) -> pd.Series | None:
    if col not in df.columns:
        return None
    return pd.to_numeric(df[col], errors="coerce")


def _render_analysis_header(title: str, desc_md: str) -> None:
    st.subheader(title)
    with st.expander("Opis analizy", expanded=False):
        st.info(desc_md)


def render_company_colored_header(
    df: pd.DataFrame,
    section_title: str,
) -> None:
    """
    Renderuje nagłówek sekcji w formacie:
    ALE (ALLEGRO) – Nazwa sekcji
    z kolorem zgodnym z globalnym kontekstem spółki.
    """
    if df.empty:
        return

    status_kind, _, _ = compute_overall_state(df)
    name = df["name"].iloc[0]

    full_title = f"{name} – {section_title}"

    if status_kind == "success":
        st.success(f"**{full_title}**")
    elif status_kind == "error":
        st.error(f"**{full_title}**")
    else:
        st.warning(f"**{full_title}**")



def _render_summary_box(lines: list[str]) -> None:
    """
    Podsumowanie opisowe (wymóg #6).
    """
    if not lines:
        return
    st.markdown("**Podsumowanie (automatyczne):**")
    st.markdown("\n".join([f"- {ln}" for ln in lines]))



def render_company_section_header(
    df: pd.DataFrame,
    section_title: str,
    level: str = "section",
) -> None:
    """
    Renderuje spójny nagłówek sekcji:
    <TICKER> (<NAZWA>) – <section_title>

    Kolor zgodny z compute_overall_state(df).
    """

    if df.empty:
        return

    status_kind, _, _ = compute_overall_state(df)

    name = df["name"].iloc[0]

    full_title = (
        f"{name}"
        if section_title.strip() == ""
        else f"{name} – {section_title}"
    )

    if status_kind == "success":
        st.success(f"**{full_title}**")
    elif status_kind == "error":
        st.error(f"**{full_title}**")
    else:
        st.warning(f"**{full_title}**")




def _analysis_trend_health(df: pd.DataFrame) -> None:
    st.divider()
    render_company_colored_header(
        df,
        "Kontekst trendu i „zdrowie trendu”",
    )

    _render_analysis_header( "",   
        """
Ta analiza pokazuje, **w jakim reżimie trendowym** znajduje się spółka.

**Jak czytać:**
- Porównujemy cenę do długiej średniej (np. EMA 200 / SMA 200) oraz do średniej średnioterminowej (np. EMA 50).
- Jeśli cena jest **powyżej** długiej średniej, zwykle oznacza to reżim wzrostowy (trend długoterminowy sprzyja).
- Jeśli cena jest **poniżej** długiej średniej, zwykle oznacza to reżim spadkowy (trend długoterminowy nie sprzyja).
- Dodatkowo patrzymy na dystans ceny od średnich – duży dystans oznacza „rozciągnięcie” (ryzyko korekty), mały dystans – „blisko trendu”.
        """.strip(),
    )

    if df.empty or "close_price" not in df.columns:
        st.info("Brak danych do analizy trendu (wymagana kolumna: Zamknięcie).")
        return

    close = _safe_series(df, "close_price")
    ema50 = _safe_series(df, "ema_50") if "ema_50" in df.columns else None
    ema200 = _safe_series(df, "ema_200") if "ema_200" in df.columns else None
    sma200 = _safe_series(df, "sma_200") if "sma_200" in df.columns else None

    last_close = _last_valid(close)
    last_ema50 = _last_valid(ema50) if ema50 is not None else None
    last_ema200 = _last_valid(ema200) if ema200 is not None else None
    last_sma200 = _last_valid(sma200) if sma200 is not None else None

    long_ma_name = None
    long_ma_val = None
    if last_ema200 is not None:
        long_ma_name, long_ma_val = "ema_200", last_ema200
    elif last_sma200 is not None:
        long_ma_name, long_ma_val = "sma_200", last_sma200

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(_ui_label("close_price"), f"{last_close:.2f}" if last_close is not None else "—")
    with col2:
        if last_ema50 is not None and last_close is not None:
            st.metric(_ui_label("ema_50"), f"{last_ema50:.2f}", f"{(last_close/last_ema50-1)*100:.2f}% vs cena")
        else:
            st.metric(_ui_label("ema_50"), "—")
    with col3:
        if long_ma_name and long_ma_val is not None and last_close is not None:
            st.metric(_ui_label(long_ma_name), f"{long_ma_val:.2f}", f"{(last_close/long_ma_val-1)*100:.2f}% vs cena")
        else:
            st.metric("Długa średnia (200)", "—")

    # wykres: ostatnie ~252 sesje
    # df_tail = df.tail(252).copy()
    # wykres: ostatnie wszystkie sesje
    df_tail = df.copy()    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_tail["trade_date"], y=df_tail["close_price"], mode="lines", name=_ui_label("close_price")))
    if "ema_50" in df_tail.columns:
        fig.add_trace(go.Scatter(x=df_tail["trade_date"], y=df_tail["ema_50"], mode="lines", name=_ui_label("ema_50")))
    if long_ma_name and long_ma_name in df_tail.columns:
        fig.add_trace(go.Scatter(x=df_tail["trade_date"], y=df_tail[long_ma_name], mode="lines", name=_ui_label(long_ma_name)))
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", y=1.05))   
    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
        gridwidth=1,
        tickformat="%Y-%m-%d",
    )
    st.plotly_chart(fig, width="stretch")

    # podsumowanie
    summary = []
    if last_close is not None and long_ma_val is not None:
        if last_close >= long_ma_val:
            summary.append(f"Cena jest **powyżej** długiej średniej ({_ui_label(long_ma_name)}): reżim długoterminowy sprzyja wzrostom.")
        else:
            summary.append(f"Cena jest **poniżej** długiej średniej ({_ui_label(long_ma_name)}): reżim długoterminowy jest słabszy.")
    if last_close is not None and last_ema50 is not None:
        if last_close >= last_ema50:
            summary.append("Cena jest powyżej średniej średnioterminowej (EMA 50) – momentum w średnim horyzoncie jest dodatnie.")
        else:
            summary.append("Cena jest poniżej EMA 50 – średni horyzont wskazuje na korektę / słabszą dynamikę.")
    _render_summary_box(summary)


def _analysis_impulses(df: pd.DataFrame) -> None:
    st.divider()
    render_company_colored_header(
        df,
        "Impulsy historyczne (momenty decyzyjne)”",
    )
    _render_analysis_header(
        "",
        """
Ta analiza pokazuje **miejsca na wykresie**, w których historycznie pojawiał się sygnał impulsu (`Sygnał 20 D (hyb.)`).

**Ważne:**
- To są **etykiety historyczne (future)** – powstają „po fakcie”.
- Nie są sygnałem bieżącym do działania, tylko narzędziem do:
  - walidacji,
  - nauki wzorców,
  - rozumienia, jak spółka „rusza”.
- Największa wartość jest wtedy, gdy impuls pojawia się w zgodnym kontekście trendowym.
        """.strip(),
    )

    if df.empty or "close_price" not in df.columns:
        st.info("Brak danych do analizy impulsów.")
        return

    col_hyb = "fut_signal_20_hyb"
    col_ctx = "fut_signal_20"

    if col_hyb not in df.columns:
        st.info(f"Brak kolumny {_ui_label(col_hyb)} – nie da się zaznaczyć impulsów.")
        return

    hyb = _safe_series(df, col_hyb)
    df_imp = df.copy()
    df_imp["hyb"] = hyb

    # impulsy: nie-NaN i != 0
    marks = df_imp.dropna(subset=["hyb"])
    marks = marks[marks["hyb"] != 0]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["trade_date"], y=df["close_price"], mode="lines", name=_ui_label("close_price")))
    if not marks.empty:
        fig.add_trace(go.Scatter(
            x=marks["trade_date"], y=marks["close_price"],
            mode="markers",
            name=_ui_label(col_hyb),
            marker=dict(size=9),
            hovertemplate="Data: %{x|%Y-%m-%d}<br>Cena: %{y:.2f}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=marks["trade_date"],
            y=marks["close_price"] * 1.01,
            text=marks["hyb"].astype(int).astype(str),
            mode="text",
            textposition="top center",
            textfont=dict(size=12),
            showlegend=False,
            hoverinfo="skip",
        ))

    fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", y=1.05))
    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
        gridwidth=1,
        tickformat="%Y-%m-%d",
    )
    st.plotly_chart(fig, width="stretch")

    # mini tabela ostatnich impulsów
    summary = []
    if marks.empty:
        summary.append("W wybranym zakresie danych nie wystąpiły impulsy (`hyb`) lub dane są niepełne.")
        _render_summary_box(summary)
        return

    # kontekst (opcjonalnie)
    ctx_info = ""
    if col_ctx in df.columns:
        ctx = _safe_series(df, col_ctx)
        marks = marks.copy()
        marks["ctx"] = ctx.loc[marks.index].values
        ctx_info = " + kontekst"
    show = marks.tail(10)[["trade_date", "close_price"] + (["ctx"] if "ctx" in marks.columns else [])].copy()
    show = show.rename(columns={
        "trade_date": _ui_label("trade_date"),
        "close_price": _ui_label("close_price"),
        "ctx": _ui_label(col_ctx),
    })
    st.dataframe(show, width="stretch", hide_index=True)

    summary.append(f"Znaleziono **{len(marks)}** impulsów ({_ui_label(col_hyb)}) w aktualnym zakresie.")
    if "ctx" in marks.columns:
        in_trend = (marks["ctx"] == 1).sum()
        against = (marks["ctx"] == -1).sum()
        summary.append(f"Impulsy w zgodnym kontekście ({_ui_label(col_ctx)}=+1): **{in_trend}**, przeciw: **{against}**.")
    _render_summary_box(summary)


def _analysis_volatility_vs_impulse(df: pd.DataFrame) -> None:
    st.divider()
    render_company_colored_header(
        df,
        "Zmienność a impuls (kompresja → ekspansja)",
    )
    _render_analysis_header(
        "",
        """
Ta analiza pokazuje, czy impulsy pojawiają się po okresach **niskiej zmienności** (kompresji)
i czy potem następuje **wzrost zmienności** (ekspansja).

**Jak czytać:**
- Niska zmienność często oznacza „zbieranie energii”.
- Impuls (szczególnie `hyb`) często pojawia się po takim okresie.
- Jeśli impulsy występują przy stale wysokiej zmienności – rynek może być bardziej chaotyczny.
        """.strip(),
    )

    if df.empty:
        st.info("Brak danych do analizy zmienności.")
        return

    if "volatility_20d" not in df.columns:
        st.info(f"Brak kolumny {_ui_label('volatility_20d')}.")
        return

    hyb_col = "fut_signal_20_hyb"
    vol = _safe_series(df, "volatility_20d")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["trade_date"], y=vol, mode="lines", name=_ui_label("volatility_20d")))
    # --- overlay: kierunek ceny (przeskalowany do volatility_20d) ---
    if "close_price" in df.columns:
        price_scaled = _scale_series_to_target_range(df["close_price"], vol)
        fig.add_trace(go.Scatter(
            x=df["trade_date"],
            y=price_scaled,
            mode="lines",
            name="Cena (kierunek)",
            line=dict(color="red", width=1, dash="dot"),
            opacity=0.8,
        ))


    if hyb_col in df.columns:
        hyb = _safe_series(df, hyb_col)
        marks = df.copy()
        marks["hyb"] = hyb
        marks = marks.dropna(subset=["hyb"])
        marks = marks[marks["hyb"] != 0]
        if not marks.empty:
            fig.add_trace(go.Scatter(
                x=marks["trade_date"], y=pd.to_numeric(marks["volatility_20d"], errors="coerce"),
                mode="markers", name=_ui_label(hyb_col),
                marker=dict(size=9),
            ))
            fig.add_trace(go.Scatter(
                x=marks["trade_date"],
                y=pd.to_numeric(marks["volatility_20d"], errors="coerce") * 1.03,
                text=marks["hyb"].astype(int).astype(str),
                mode="text",
                textposition="top center",
                textfont=dict(size=12),
                showlegend=False,
                hoverinfo="skip",
            ))

    fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", y=1.05))
    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
        gridwidth=1,
        tickformat="%Y-%m-%d",
    )
    st.plotly_chart(fig, width="stretch")

    last_vol = _last_valid(vol)
    summary = []
    if last_vol is not None:
        summary.append(f"Ostatnia wartość {_ui_label('volatility_20d')}: **{last_vol:.4f}**.")
    if hyb_col in df.columns:
        hyb = _safe_series(df, hyb_col)
        cnt = (hyb.dropna() != 0).sum()
        summary.append(f"Liczba impulsów (`hyb`) w zakresie: **{int(cnt)}**.")
    _render_summary_box(summary)


def _analysis_volatility_vs_base_impulse(df: pd.DataFrame) -> None:
    st.divider()
    render_company_colored_header(
        df,
        "Zmienność a impuls (kontekst bazowy)",
    )
    _render_analysis_header(
        "",
        """
Ta analiza pokazuje zależność pomiędzy **zmiennością rynku**
a występowaniem **bazowych impulsów (`Sygnał 20 D`)**.

**Jak czytać:**
- Bazowy impuls (`fut_signal_20`) oznacza ruch zgodny z prostym kontekstem trendowym.
- W przeciwieństwie do wersji hybrydowej, impulsy mogą pojawiać się częściej.
- Analiza pomaga porównać:
  - gdzie pojawia się „surowy” sygnał,
  - a gdzie tylko sygnał jakościowy (hybrydowy).
        """.strip(),
    )

    if df.empty:
        st.info("Brak danych do analizy zmienności.")
        return

    if "volatility_20d" not in df.columns:
        st.info(f"Brak kolumny {_ui_label('volatility_20d')}.")
        return

    base_col = "fut_signal_20"
    vol = _safe_series(df, "volatility_20d")

    fig = go.Figure()

    # --- zmienność ---
    fig.add_trace(go.Scatter(
        x=df["trade_date"],
        y=vol,
        mode="lines",
        name=_ui_label("volatility_20d"),
    ))

    # --- overlay: kierunek ceny ---
    if "close_price" in df.columns:
        price_scaled = _scale_series_to_target_range(df["close_price"], vol)
        fig.add_trace(go.Scatter(
            x=df["trade_date"],
            y=price_scaled,
            mode="lines",
            name="Cena (kierunek)",
            line=dict(color="red", width=1, dash="dot"),
            opacity=0.8,
        ))

    # --- impulsy bazowe ---
    if base_col in df.columns:
        base = _safe_series(df, base_col)
        marks = df.copy()
        marks["base"] = base
        marks = marks.dropna(subset=["base"])
        marks = marks[marks["base"] != 0]

        if not marks.empty:
            # markery
            fig.add_trace(go.Scatter(
                x=marks["trade_date"],
                y=pd.to_numeric(marks["volatility_20d"], errors="coerce"),
                mode="markers",
                name=_ui_label(base_col),
                marker=dict(size=9),
            ))

            # tekst 1 / -1
            fig.add_trace(go.Scatter(
                x=marks["trade_date"],
                y=pd.to_numeric(marks["volatility_20d"], errors="coerce") * 1.03,
                text=marks["base"].astype(int).astype(str),
                mode="text",
                textposition="top center",
                textfont=dict(size=12),
                showlegend=False,
                hoverinfo="skip",
            ))

    fig.update_layout(
        height=320,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", y=1.05),
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
        gridwidth=1,
        tickformat="%Y-%m-%d",
    )
    st.plotly_chart(fig, width="stretch")

    summary = []
    last_vol = _last_valid(vol)
    if last_vol is not None:
        summary.append(f"Ostatnia wartość {_ui_label('volatility_20d')}: **{last_vol:.4f}**.")
    if base_col in df.columns:
        cnt = (pd.to_numeric(df[base_col], errors="coerce").dropna() != 0).sum()
        summary.append(f"Liczba impulsów bazowych (`Sygnał 20 D`) w zakresie: **{int(cnt)}**.")
    _render_summary_box(summary)



def _analysis_volume_confirmation(df: pd.DataFrame) -> None:
    st.divider()
    render_company_colored_header(
        df,
        "Wolumen jakościowy (potwierdzenie ruchu)",
    )
    _render_analysis_header(
        "",
        """
Ta analiza ocenia, czy ruchy ceny są wspierane przez **ponadnormatywny wolumen**.

**Jak czytać:**
- Porównujemy bieżący wolumen do średniej z 20 dni.
- Gdy wolumen jest istotnie większy niż średnia, oznacza to większe zaangażowanie rynku.
- Brak wolumenu przy ruchu ceny może oznaczać ruch „bez paliwa”.
        """.strip(),
    )

    if df.empty:
        st.info("Brak danych do analizy wolumenu.")
        return

    if "volume" not in df.columns:
        st.info(f"Brak kolumny {_ui_label('volume')}.")
        return
    if "average_volume_20d" not in df.columns:
        st.info(f"Brak kolumny {_ui_label('average_volume_20d')} – nie policzę relacji do średniej.")
        return

    v = _safe_series(df, "volume")
    vavg = _safe_series(df, "average_volume_20d")

    ratio = (v / vavg).replace([pd.NA, pd.NaT, float("inf"), float("-inf")], pd.NA)
    df_r = df.copy()
    df_r["vol_ratio"] = pd.to_numeric(ratio, errors="coerce")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_r["trade_date"], y=df_r["vol_ratio"], mode="lines", name="Wolumen / Śr.20D"))
    # --- overlay: kierunek ceny (przeskalowany do vol_ratio) ---
    if "close_price" in df_r.columns:
        price_scaled = _scale_series_to_target_range(df_r["close_price"], df_r["vol_ratio"])
        fig.add_trace(go.Scatter(
            x=df_r["trade_date"],
            y=price_scaled,
            mode="lines",
            name="Cena (kierunek)",
            line=dict(color="red", width=1, dash="dot"),
            opacity=0.8,
        ))
    
    # linia 1.0 jako próg "normalny"
    fig.add_trace(go.Scatter(
        x=df_r["trade_date"],
        y=[1.0] * len(df_r),
        mode="lines",
        name="Poziom 1.0",
        line=dict(width=1, dash="dot"),
    ))
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", y=1.05))
    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
        gridwidth=1,
        tickformat="%Y-%m-%d",
    )
    st.plotly_chart(fig, width="stretch")

    last_ratio = _last_valid(df_r["vol_ratio"])
    spikes = (df_r["vol_ratio"] >= 1.5).sum()

    summary = []
    if last_ratio is not None:
        summary.append(f"Ostatnia relacja wolumenu do średniej: **{last_ratio:.2f}×**.")
    summary.append(f"Liczba dni z wolumenem ≥ **1.5×** średniej: **{int(spikes)}**.")
    _render_summary_box(summary)


def _analysis_momentum(df: pd.DataFrame) -> None:
    st.divider()
    render_company_colored_header(
        df,
        "Momentum w czasie (siła długoterminowa)",
    )
    _render_analysis_header(
        "",
        """
Ta analiza pokazuje wskaźnik **Momentum 12M**, czyli uproszczoną miarę „siły” rynku w horyzoncie rocznym.

**Jak czytać:**
- Dodatnie momentum oznacza, że rynek był w długoterminowej fazie wzrostowej.
- Ujemne momentum oznacza słabszy / spadkowy reżim.
- Momentum jest wskaźnikiem kontekstowym: pomaga zrozumieć, czy spółka ma „wiatr w plecy”.
        """.strip(),
    )

    if df.empty:
        st.info("Brak danych do analizy momentum.")
        return

    if "momentum_12m" not in df.columns:
        st.info(f"Brak kolumny {_ui_label('momentum_12m')}.")
        return

    mom = _safe_series(df, "momentum_12m")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["trade_date"], y=mom, mode="lines", name=_ui_label("momentum_12m")))
    # --- overlay: kierunek ceny (przeskalowany do momentum) ---
    if "close_price" in df.columns:
        price_scaled = _scale_series_to_target_range(df["close_price"], mom)
        fig.add_trace(go.Scatter(
            x=df["trade_date"],
            y=price_scaled,
            mode="lines",
            name="Cena (kierunek)",
            line=dict(color="red", width=1, dash="dot"),
            opacity=0.8,
        ))

    fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", y=1.05))
    
    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
        gridwidth=1,
        tickformat="%Y-%m-%d",
    )
    st.plotly_chart(fig, width="stretch")

    last_mom = _last_valid(mom)
    summary = []
    if last_mom is not None:
        summary.append(f"Ostatnia wartość {_ui_label('momentum_12m')}: **{last_mom:.4f}** (znak mówi o długoterminowej sile).")
    _render_summary_box(summary)


def _analysis_drawdown(df: pd.DataFrame) -> None:
    st.divider()
    render_company_colored_header(
        df,
        "Ryzyko obsunięć (drawdown)",
    )
    _render_analysis_header(
        "",
        """
Ta analiza pokazuje ryzyko instrumentu poprzez **maksymalne obsunięcie w 252 dniach**.

**Jak czytać:**
- Im większe (bardziej ujemne) obsunięcie, tym trudniej „wytrzymać” ten rynek w portfelu.
- Niskie obsunięcia sugerują bardziej uporządkowany rynek.
- To nie jest rekomendacja – to opis profilu ryzyka.
        """.strip(),
    )

    if df.empty:
        st.info("Brak danych do analizy obsunięć.")
        return

    if "max_drawdown_252d" not in df.columns:
        st.info(f"Brak kolumny {_ui_label('max_drawdown_252d')}.")
        return

    dd = _safe_series(df, "max_drawdown_252d")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["trade_date"], y=dd, mode="lines", name=_ui_label("max_drawdown_252d")))
    # --- overlay: kierunek ceny (przeskalowany do drawdown) ---
    if "close_price" in df.columns:
        price_scaled = _scale_series_to_target_range(df["close_price"], dd)
        fig.add_trace(go.Scatter(
            x=df["trade_date"],
            y=price_scaled,
            mode="lines",
            name="Cena (kierunek)",
            line=dict(color="red", width=1, dash="dot"),
            opacity=0.8,
        ))

    fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", y=1.05))    
    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
        gridwidth=1,
        tickformat="%Y-%m-%d",
    )
    st.plotly_chart(fig, width="stretch")

    s = pd.to_numeric(dd, errors="coerce").dropna()
    summary = []
    if not s.empty:
        summary.append(f"Ostatni drawdown (252D): **{s.iloc[-1]:.4f}**.")
        summary.append(f"Najgorszy drawdown w zakresie: **{s.min():.4f}**.")
    _render_summary_box(summary)


def _analysis_percentiles_today(df: pd.DataFrame) -> None:
    st.divider()
    render_company_colored_header(
        df,
        "„Czy dziś jest wyjątkowo?” – percentyle względem historii spółki",
    )
    _render_analysis_header(
        "",
        """
Ta analiza porównuje **dzisiejsze wartości wskaźników** do historii tej spółki.

**Jak czytać percentyl:**
- 90 percentyl = dzisiejsza wartość jest wyższa niż 90% historycznych obserwacji.
- 10 percentyl = dzisiejsza wartość jest niższa niż 90% historii (czyli należy do niskich wartości).

To pomaga zrozumieć „czy dziś jest normalnie czy ekstremalnie”
w ramach tej konkretnej spółki (nie rynku jako całości).
        """.strip(),
    )

    if df.empty:
        st.info("Brak danych do analizy percentyli.")
        return

    candidates = [
        "rsi_14",
        "volatility_20d",
        "sharpe_20d",
        "tqs_60d",
        "momentum_12m",
    ]

    rows = []
    for col in candidates:
        if col not in df.columns:
            continue
        s = _safe_series(df, col)
        v = _last_valid(s)
        if v is None:
            continue
        p = _pct_rank(s, v)
        rows.append({
            "Wskaźnik": _ui_label(col),
            "Wartość (ostatnia)": v,
            "Percentyl (0-100)": p,
        })

    if not rows:
        st.info("Brak wystarczających danych wskaźników do percentyli.")
        return

    df_out = pd.DataFrame(rows)
    st.dataframe(df_out, width="stretch", hide_index=True)

    # mały element graficzny: słupki percentyli
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_out["Wskaźnik"],
        y=df_out["Percentyl (0-100)"],
        name="Percentyl",
    ))
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), yaxis=dict(range=[0, 100]))
    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
        gridwidth=1,
        tickformat="%Y-%m-%d",
    )
    st.plotly_chart(fig, width="stretch")

    summary = []
    top = df_out.sort_values("Percentyl (0-100)", ascending=False).head(2)
    low = df_out.sort_values("Percentyl (0-100)", ascending=True).head(2)

    summary.append(f"Najwyższe percentyle dziś: **{', '.join(top['Wskaźnik'].tolist())}**.")
    summary.append(f"Najniższe percentyle dziś: **{', '.join(low['Wskaźnik'].tolist())}**.")
    _render_summary_box(summary)


def _analysis_future_ex_post(df: pd.DataFrame) -> None:
    st.divider()
    render_company_colored_header(
    df,
    "Walidacja ex post (future): warunki → wynik historyczny",
)
    _render_analysis_header(
        "",
        """
Ta analiza pokazuje **zależność historyczną**: jakie warunki wskaźników „w dniu t”
częściej współwystępowały z określonym wynikiem future.

**Ważne:**
- Wskaźniki future (etykiety) są liczone „po fakcie” i nie są sygnałem bieżącym.
- Celem jest walidacja i zrozumienie: *czy pewne stany rynku częściej prowadziły do lepszych wyników*.

W tej wersji bierzemy przykład:
- warunek: koszyki RSI,
- wynik: `Bariera +20% / -12% (20 D)` (jeśli dostępna).
        """.strip(),
    )

    if df.empty:
        st.info("Brak danych do analizy future ex post.")
        return

    rsi_col = "rsi_14"
    fut_col = "fut_barrier_20p_12p_20d"

    if rsi_col not in df.columns:
        st.info(f"Brak {_ui_label(rsi_col)} – nie zrobię koszyków RSI.")
        return
    if fut_col not in df.columns:
        st.info(f"Brak {_ui_label(fut_col)} – brak etykiety future do walidacji.")
        return

    rsi = _safe_series(df, rsi_col)
    fut = _safe_series(df, fut_col)

    tmp = pd.DataFrame({
        "trade_date": df["trade_date"],
        "rsi": rsi,
        "fut": fut,
    }).dropna()

    if tmp.empty:
        st.info("Brak pełnych danych RSI + future w wybranym zakresie.")
        return

    # koszyki RSI
    bins = [-float("inf"), 30, 50, 70, float("inf")]
    labels = ["< 30", "30–50", "50–70", "> 70"]
    tmp["RSI koszyk"] = pd.cut(tmp["rsi"], bins=bins, labels=labels)

    # statystyki: ile +1 / 0 / -1 per koszyk
    pivot = (
        tmp
        .assign(fut_sign=tmp["fut"].astype(float))
        .groupby(["RSI koszyk", "fut_sign"], observed=True)
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )

    # zmień nazwy kolumn wynikowych na przyjazne
    col_map = {"RSI koszyk": f"{_ui_label(rsi_col)} – koszyk"}
    for c in pivot.columns:
        if c == "RSI koszyk":
            continue
        # fut_sign może być -1, 0, 1
        col_map[c] = f"Wynik {_ui_label(fut_col)} = {int(c)}"
    pivot = pivot.rename(columns=col_map)

    st.dataframe(pivot, width="stretch", hide_index=True)

    # wykres: udział wyników w koszykach
    # (robimy stacked "ręcznie" – kilka barów)
    fig = go.Figure()
    x = pivot[col_map["RSI koszyk"]]
    for c in [cc for cc in pivot.columns if cc != col_map["RSI koszyk"]]:
        fig.add_trace(go.Bar(x=x, y=pivot[c], name=c))
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10), barmode="stack", legend=dict(orientation="h", y=1.05))
    st.plotly_chart(fig, width="stretch")

    summary = []
    total = len(tmp)
    summary.append(f"Liczba obserwacji w walidacji: **{total}** (tam gdzie RSI i future są dostępne).")
    _render_summary_box(summary)



def compute_overall_state(df: pd.DataFrame) -> tuple[str, str, list[str]]:
    """
    Zwraca:
    - status_kind: "success" | "warning" | "error"
    - etykietę tekstową,
    - listę powodów (krótkie zdania).
    """
    reasons: list[str] = []
    score = 0

    # =========================
    # TREND długoterminowy
    # =========================
    close = _safe_series(df, "close_price")
    ema200 = _safe_series(df, "ema_200")
    sma200 = _safe_series(df, "sma_200")

    last_close = _last_valid(close)
    long_ma = _last_valid(ema200) or _last_valid(sma200)

    if last_close is not None and long_ma is not None:
        if last_close >= long_ma:
            score += 1
            reasons.append("Cena powyżej długiej średniej (trend sprzyjający).")
        else:
            score -= 1
            reasons.append("Cena poniżej długiej średniej (trend niesprzyjający).")

    # =========================
    # MOMENTUM
    # =========================
    if "momentum_12m" in df.columns:
        mom = _last_valid(_safe_series(df, "momentum_12m"))
        if mom is not None:
            if mom > 0:
                score += 1
                reasons.append("Dodatnie momentum długoterminowe.")
            else:
                score -= 1
                reasons.append("Ujemne momentum długoterminowe.")

    # =========================
    # ZMIENNOŚĆ (percentyl)
    # =========================
    if "volatility_20d" in df.columns:
        vol = _safe_series(df, "volatility_20d")
        last_vol = _last_valid(vol)
        if last_vol is not None:
            pct = _pct_rank(vol, last_vol)
            if pct > 70:
                score -= 1
                reasons.append("Zmienność wysoka względem historii.")
            elif pct < 30:
                score += 1
                reasons.append("Zmienność niska względem historii.")

    # =========================
    # WOLUMEN
    # =========================
    if {"volume", "average_volume_20d"}.issubset(df.columns):
        ratio = _last_valid(
            _safe_series(df, "volume") / _safe_series(df, "average_volume_20d")
        )
        if ratio is not None:
            if ratio >= 1.5:
                score += 1
                reasons.append("Wolumen istotnie powyżej średniej.")
            elif ratio < 0.8:
                score -= 1
                reasons.append("Wolumen niski – słabe potwierdzenie ruchu.")

    # =========================
    # MAPOWANIE NA KOLOR (box)
    # =========================
    if score >= 2:
        return "success", "Kontekst sprzyjający", reasons
    if score <= -2:
        return "error", "Kontekst niesprzyjający", reasons
    return "warning", "Kontekst niejednoznaczny", reasons



def _render_company_state_badge(df: pd.DataFrame) -> None:
    """
    Prezentuje stan ogólny spółki jako kolorowy box Streamlit:
    - st.success / st.warning / st.error
    + expander z opisem znaczenia kolorów.
    """
    status_kind, label, reasons = compute_overall_state(df)

    # Box koloru (bez emoji)
    msg = f"**Stan ogólny spółki:** {label}"
    if status_kind == "success":
        st.success(msg)
    elif status_kind == "error":
        st.error(msg)
    else:
        st.warning(msg)

    # Expander: znaczenie kolorów (wymagane)
    with st.expander("Znaczenie kolorów znacznika firmy", expanded=False):
        st.info(
            """
Kolor znacznika pokazuje ogólny obraz sytuacji spółki
na podstawie aktualnych danych historycznych.

**To nie jest prognoza ani rekomendacja inwestycyjna.**
Znacznik ma charakter orientacyjny i pomaga szybciej ocenić kontekst rynkowy.

### Zielony – kontekst sprzyjający
Sytuacja techniczna spółki wygląda relatywnie korzystnie:
trend i momentum są spójne, a ryzyko nie wygląda na podwyższone.

### Żółty – kontekst niejednoznaczny
Obraz rynku jest mieszany.
Część sygnałów wygląda korzystnie, a część ostrzegawczo.

### Czerwony – kontekst niesprzyjający
Sytuacja techniczna jest słabsza:
trend może być gorszy, a zmienność lub ryzyko wyższe.
            """.strip()
        )

    # „Dlaczego?” – krótkie powody (opcjonalnie, ale bardzo użyteczne)
    if reasons:
        with st.expander("Dlaczego taki stan?", expanded=False):
            for r in reasons:
                st.markdown(f"- {r}")




def _analysis_global_summary(df: pd.DataFrame) -> None:
    
    render_company_section_header(
        df,
        "Globalne podsumowanie sytuacji spółki",
    )

    _render_company_state_badge(df)

    with st.expander("Jak czytać to podsumowanie", expanded=False):
        st.info(
            """
To podsumowanie zbiera najważniejsze wnioski z analiz pokazanych wyżej.

Pomaga szybko ocenić:
- jaki jest ogólny obraz sytuacji spółki,
- czy trend wygląda korzystnie czy słabiej,
- jak wygląda zmienność, wolumen i ryzyko,
- czy w danych widać historyczne impulsy lub sygnały warte dalszej analizy.

To podsumowanie:
- nie jest sygnałem kupna ani sprzedaży,
- nie przewiduje przyszłości,
- nie zastępuje pełnej analizy wykresów i wskaźników,
  ale pomaga szybciej zrozumieć najważniejsze obserwacje.
            """.strip()
        )

    if df.empty:
        st.info("Brak danych do wygenerowania globalnego podsumowania.")
        return

    summary_lines: list[str] = []

    # =========================
    # TREND (długoterminowy)
    # =========================
    close = _safe_series(df, "close_price")
    ema200 = _safe_series(df, "ema_200") if "ema_200" in df.columns else None
    sma200 = _safe_series(df, "sma_200") if "sma_200" in df.columns else None

    last_close = _last_valid(close)
    long_ma_val = None
    long_ma_name = None

    if ema200 is not None and _last_valid(ema200) is not None:
        long_ma_val = _last_valid(ema200)
        long_ma_name = "ema_200"
    elif sma200 is not None and _last_valid(sma200) is not None:
        long_ma_val = _last_valid(sma200)
        long_ma_name = "sma_200"

    if last_close is not None and long_ma_val is not None:
        if last_close >= long_ma_val:
            summary_lines.append(
                f"**Trend długoterminowy jest wzrostowy** – cena znajduje się powyżej {_ui_label(long_ma_name)}."
            )
        else:
            summary_lines.append(
                f"**Trend długoterminowy jest słabszy** – cena znajduje się poniżej {_ui_label(long_ma_name)}."
            )

    # =========================
    # MOMENTUM
    # =========================
    if "momentum_12m" in df.columns:
        mom = _safe_series(df, "momentum_12m")
        last_mom = _last_valid(mom)
        if last_mom is not None:
            if last_mom > 0:
                summary_lines.append(
                    "**Momentum długoterminowe jest dodatnie** – historycznie rynek miał „wiatr w plecy”."
                )
            else:
                summary_lines.append(
                    "**Momentum długoterminowe jest ujemne** – presja w długim horyzoncie była słabsza."
                )

    # =========================
    # ZMIENNOŚĆ
    # =========================
    if "volatility_20d" in df.columns:
        vol = _safe_series(df, "volatility_20d")
        last_vol = _last_valid(vol)
        if last_vol is not None:
            vol_pct = _pct_rank(vol, last_vol)
            if vol_pct < 30:
                summary_lines.append(
                    "**Zmienność jest niska względem historii spółki** – rynek jest relatywnie spokojny."
                )
            elif vol_pct > 70:
                summary_lines.append(
                    "**Zmienność jest wysoka względem historii spółki** – rynek jest bardziej nerwowy."
                )

    # =========================
    # WOLUMEN
    # =========================
    if "volume" in df.columns and "average_volume_20d" in df.columns:
        v = _safe_series(df, "volume")
        vavg = _safe_series(df, "average_volume_20d")
        if v is not None and vavg is not None:
            ratio = _last_valid(v / vavg)
            if ratio is not None:
                if ratio >= 1.5:
                    summary_lines.append(
                        "🔊 **Wolumen jest wyraźnie podwyższony** – ruchy ceny są wspierane aktywnością rynku."
                    )
                elif ratio < 0.8:
                    summary_lines.append(
                        "**Wolumen jest niski** – bieżące ruchy mogą mieć ograniczone potwierdzenie."
                    )

    # =========================
    # RYZYKO (DRAWDOWN)
    # =========================
    if "max_drawdown_252d" in df.columns:
        dd = _safe_series(df, "max_drawdown_252d")
        if dd is not None:
            worst = pd.to_numeric(dd, errors="coerce").min()
            if worst is not None:
                summary_lines.append(
                    f"**Historyczne obsunięcia bywały istotne** – najgorszy drawdown (252D): {worst:.2%}."
                )

    # =========================
    # IMPULSY
    # =========================
    if "fut_signal_20_hyb" in df.columns:
        hyb = _safe_series(df, "fut_signal_20_hyb")
        if hyb is not None:
            cnt = (hyb.dropna() != 0).sum()
            if cnt > 0:
                summary_lines.append(
                    f"W analizowanym okresie wystąpiły **{int(cnt)} historyczne impulsy jakościowe** (hyb)."
                )
            else:
                summary_lines.append(
                    "W analizowanym okresie **nie zidentyfikowano wyraźnych impulsów jakościowych**."
                )

    # =========================
    # PREZENTACJA PODSUMOWANIA
    # =========================
    if not summary_lines:
        st.info("Nie udało się wygenerować syntetycznego podsumowania dla wybranego zakresu danych.")
        return

    st.markdown("### Syntetyczne wnioski")
    for line in summary_lines:
        st.markdown(f"- {line}")




def render_company_analyses_below_table(df_m: pd.DataFrame) -> None:
    """
    Główny renderer analiz: wołamy go poniżej tabeli 'Notowania'.
    """
    df = _prep_df_for_analysis(df_m)
    if df.empty:
        st.info("Brak danych do analiz (pusty df_market).")
        return

    # Analizy (kolejność jak w opisie)
    _analysis_trend_health(df)
    _analysis_impulses(df)
    _analysis_volatility_vs_impulse(df)
    _analysis_volatility_vs_base_impulse(df)    
    _analysis_volume_confirmation(df)
    _analysis_momentum(df)
    _analysis_drawdown(df)
    _analysis_percentiles_today(df)
    _analysis_future_ex_post(df)








# ============================================================
# Render
# ============================================================

def render() -> None:
    init_data_mode()
    _ss_init_defaults()

    # Główny opis ekranu.
    # Tekst jest krótszy i bardziej przystępny dla osoby,
    # która dopiero poznaje aplikację i nie zna jeszcze projektu.
    st.info(
        "Ten ekran służy do przeglądania historycznych notowań spółek "
        "oraz wskaźników technicznych wyliczonych na podstawie tych danych.\n\n"
        "Możesz tutaj wybrać spółki i zakres dat, obejrzeć wykres ceny, "
        "porównać zachowanie wskaźników oraz zobaczyć, kiedy historycznie "
        "pojawiały się wybrane sygnały, np. **Sygnał 20 D**.\n\n"
        "Celem ekranu jest lepsze zrozumienie zachowania spółki i kontekstu rynkowego "
        "przed przejściem do bardziej zaawansowanych analiz oraz do prób przewidywania sygnałów "
        "w module Machine Learning."
    )
    
    st.subheader("Przegląd spółek giełdowych (dane rzeczywiste do daty 2025-12-31)")
    st.caption(f"Źródło danych: **{get_data_source_label()}**")

    col_l, col_r = st.columns(2)

    # LEFT
    with col_l:

        # --- opis ---
        with st.expander("Opis działania ekranu", expanded=False):
            st.info(
                """
Na tym ekranie możesz:

- wybrać spółki i zakres dat, na których ma pracować aplikacja,
- załadować dane notowań i wskaźników technicznych,
- zobaczyć ostatnie dostępne notowania dla wybranych spółek,
- wybrać jedną spółkę do szczegółowego podglądu,
- analizować wykres ceny, wskaźniki i historyczne sygnały,
- przygotować dane do dalszej pracy w ekranach **Analiza danych** i **Machine Learning**.

W praktyce jest to ekran startowy do poznania danych i zbudowania kontekstu
przed przejściem do bardziej zaawansowanych analiz.
                """.strip()
            )

        # --- zakres danych (read-only) ---
        st.text_area(
            "Dostępne firmy (ograniczone do zawartości dostępnej bazy danych)",
            ", ".join(st.session_state[SSK["avail_tickers_all"]]),
            disabled=True,
        )

        # --- reset filtra do pełnej listy dostępnych firm ---
        if st.button("Reset filtra do listy dostępnych firm"):
            st.session_state[SSK["filter_tickers_str"]] = ", ".join(
                st.session_state[SSK["avail_tickers_all"]]
            )
            st.rerun()


        # --- filtr firm (editable) ---
        st.text_area(
            "Filtr firm (ograniczenie listy przeglądanych firm)",
            key=SSK["filter_tickers_str"],
            help="Tickery rozdzielone przecinkami. Ten filtr ogranicza spółki ładowane po kliknięciu przycisku.",
        )


        # --- daty w 1 wierszu (2 kolumny) ---
        col_d1, col_d2 = st.columns(2, gap="small")
        with col_d1:
            st.text_input(
                "Data od",
                st.session_state[SSK["avail_date_from"]],
                disabled=True,
            )
        with col_d2:
            st.text_input(
                "Data do",
                st.session_state[SSK["avail_date_to"]],
                disabled=True,
            )


        # ============================================================
        # Checkbox + przycisk w jednej linii
        # ============================================================

        prev_mode = st.session_state[SSK["all_mode"]]

        col_chk, col_btn = st.columns([1, 3], gap="small")

        with col_chk:
            all_mode = st.checkbox(
                "Wszystkie dostępne firmy",
                value=prev_mode,
                help="Wczytanie notowań wszystkich firm dostępnych w bazie danych",
            )

        with col_btn:
            load_clicked = st.button(
                "Załaduj dane by wyświetlić wykresy",
                type="primary",
                width="stretch",
            )

        # --- reakcja na zmianę trybu ---
        if all_mode != prev_mode:
            st.session_state[SSK["all_mode"]] = all_mode
            _reset_all_screen_state()

            rng = (
                _compute_available_range_all_mode()
                if all_mode
                else _compute_available_range_default()
            )

            st.session_state[SSK["avail_tickers"]] = rng.tickers
            st.session_state[SSK["avail_tickers_all"]] = list(rng.tickers)
            st.session_state[SSK["avail_tickers_str"]] = ", ".join(rng.tickers)
            st.session_state[SSK["avail_date_from"]] = rng.date_from
            st.session_state[SSK["avail_date_to"]] = rng.date_to

        # --- kliknięcie przycisku ---
        if load_clicked:
            _reset_all_screen_state()

            # tickery do ładowania bierzemy z "Filtr firm" (jeśli pusty -> fallback do dostępnych)
            raw_filter = st.session_state.get(SSK["filter_tickers_str"], "").strip()
            tickers_to_load = parse_tickers(raw_filter) if raw_filter else st.session_state[SSK["avail_tickers"]]

  
            _load_max_datasets(
                tickers_to_load,
                st.session_state[SSK["avail_date_from"]],
                st.session_state[SSK["avail_date_to"]],
            )

            _refresh_df_last_load_tickers_from_ui()

            # jednorazowa inicjalizacja df_market
            df_c = st.session_state.get(SSK["df_companies"])
            if isinstance(df_c, pd.DataFrame) and not df_c.empty:
                first_ticker = df_c["ticker"].dropna().iloc[0]
                st.session_state["selected_ticker"] = first_ticker
                st.session_state[SSK["df_market"]] = _build_market_view_df(first_ticker)
                # df_market_all (WSZYSTKIE SPÓŁKI) – gotowy dataset pod analizy globalne
                st.session_state[SSK["df_market_all"]] = _build_market_all_df()
                clear_ml_datasets()       


        # --- liczniki ---
        if isinstance(st.session_state.get(SSK["df_companies"]), pd.DataFrame):
            st.caption(f"Firmy: {len(st.session_state[SSK['df_companies']])}")
            st.caption(f"Notowania: {len(st.session_state[SSK['df_prices']])}")


    # RIGHT
    with col_r:
        df_last = st.session_state.get("df_last_load_tickers")

        snapshot_date = "—"
        if isinstance(df_last, pd.DataFrame) and not df_last.empty and "trade_date" in df_last.columns:
            snapshot_date = (
                pd.to_datetime(df_last["trade_date"], errors="coerce")
                .max()
                .date()
                .isoformat()
            )

        st.subheader(f"Notowania z {snapshot_date}")


        if not isinstance(df_last, pd.DataFrame) or df_last.empty:
            st.info("Brak danych snapshotu rynku.")
        else:
            # --- przygotowanie DF ---
            df_tmp = df_last.copy()

            # formatowanie zmiany: zawsze 2 miejsca po przecinku
            if "change" in df_tmp.columns:
                df_tmp["change"] = pd.to_numeric(df_tmp["change"], errors="coerce")
                df_tmp["change"] = df_tmp["change"].apply(format_change_with_arrow)


            # usunięcie kolumny technicznej
            if "company_id" in df_tmp.columns:
                df_tmp = df_tmp.drop(columns=["company_id"])

            if "trade_date" in df_tmp.columns:
                df_tmp = df_tmp.drop(columns=["trade_date"])


            # --- AG GRID ---
            gb = GridOptionsBuilder.from_dataframe(df_tmp)

            # --- konfiguracja kolumn ---


            for col in df_tmp.columns:
                if col == "change":
                    gb.configure_column(
                        col,
                        headerName=COLUMN_LABELS.get(col, col),
                        cellStyle={"textAlign": "right"},
                    )
                else:
                    gb.configure_column(
                        col,
                        headerName=COLUMN_LABELS.get(col, col),
                    )


            gb.configure_default_column(
                sortable=True,
                resizable=True,
            )

            gb.configure_pagination(
                enabled=True,
                paginationAutoPageSize=False,
                paginationPageSize=20,
            )

            AgGrid(
                df_tmp,
                gridOptions=gb.build(),
                update_mode=GridUpdateMode.NO_UPDATE,
                height=645,
                theme="balham",
            )






    # ============================================================
    # BOTTOM SECTION – diagnostyka / wyniki (FULL WIDTH)
    # ============================================================


    df_m = st.session_state.get(SSK["df_market"])

    if isinstance(df_m, pd.DataFrame) and not df_m.empty:
        st.divider()

        # --- diagnostyka kolumn ---
        # ", expanded=False):
        #     st.write("Liczba kolumn:", len(df_m.columns))
        #     st.code("\n".join(df_m.columns), language="text")



        # --- nagłówek ---
        render_company_section_header(
            _prep_df_for_analysis(df_m),
            "",
        )

        # Lista rozwijalna wskaźników analitycznych – opis
        with st.expander("Opis wskaźników analitycznych"):
            col_l, col_r = st.columns(2)

            with col_l:
                st.markdown("""
        ### Trend i struktura rynku
        **Opisują kierunek oraz reżim rynku.**  
        Wskaźniki:
        - SMA (20, 50, 200)
        - EMA (12, 20, 26, 50, 200)

        Czy rynek jest w trendzie wzrostowym, spadkowym
        czy w fazie przejściowej.

        ---

        ### Momentum i dynamika ceny
        **Mierzą siłę i tempo zmian ceny.**  
        Wskaźniki:
        - Momentum 12M
        - MACD, MACD Signal, MACD Histogram
        - RSI 14

        Czy rynek przyspiesza, traci impet,
        czy porusza się neutralnie.

        ---

        ### Wolumen i potwierdzenie ruchu
        **Pokazują zaangażowanie kapitału.**  
        Wskaźniki:
        - Wolumen
        - Średni wolumen 20D
        - OBV
        - VWAP 20D

        Czy ruch ceny jest wspierany
        realnym obrotem.
        """)

            with col_r:
                st.markdown("""
        ### Zmienność i ryzyko
        **Opisują intensywność wahań cenowych.**  
        Wskaźniki:
        - Zmienność 20D
        - ATR 14

        Czy rynek jest spokojny,
        czy znajduje się w fazie podwyższonej niepewności.

        ---

        ### Jakość trendu i relacja zysku do ryzyka
        **Ocena stabilności i „czystości” ruchu.**  
        Wskaźniki:
        - Sharpe Ratio 20D
        - Trend Quality Score (TQS 60D)
        - Maksymalne obsunięcie 252D

        Czy trend jest uporządkowany,
        czy chaotyczny i ryzykowny.

        ---

        ### Wskaźniki fundamentalne (syntetyczne)
        **Kontekst wyceny spółki.**  
        Wskaźniki:
        - Kapitalizacja
        - P/E
        - P/B
        - Stopa zwrotu z zysków

        Czy cena rynkowa
        jest wsparta fundamentami.
        """)

            st.markdown("""
        ---

        ### Wskaźniki typu *future* (etykiety historyczne)
        **Opisują sygnały z przeszłości i pokazują co wydarzyło się *po danym dniu*. W ekranach przeglądu danych i analizy generowane są na podstawie przyszłych cen danej spółki, gdzie przyszłe ceny są znane. W ekranach związanych z **"ML"** nastąpią próby przewidzenia występowania sygnałów typu "future". **  
        Wskaźniki:
        - Sygnały (20D, 60D, 120D, hybrydowe) typu "future"
        - Bariery cenowe (20D, 60D, 120D)
        - Suma impulsów jakościowych

        **Nie są to sygnały bieżące ani rekomendacje inwestycyjne.**  
        Służą do analizy historycznej, porównań analogii rynkowych oraz przygotowania danych pod modele ML.

        Wszystkie wskaźniki **opisują rynek**, a nie podejmują decyzji. Ich interpretacja zawsze wymaga uwzględnienia **kontekstu, horyzontu czasowego i relacji między grupami**.
        """)



        # 1) Wskaźniki nad wykresem (FULL WIDTH)
        selected_indicators = render_chart_indicators(df_m)


        # 2) Układ 1 : 7
        col_filters, col_chart = st.columns([1, 7], gap="large")

        with col_filters:
            render_company_filter()

        with col_chart:
            render_chart_section(selected_indicators)

        st.divider()




        # ============================================================
        # ANALIZY – poniżej wykresu "Notowania" (jedna spółka)
        # ============================================================


        # ============================================================
        # GLOBALNE PODSUMOWANIE SYTUACJI SPÓŁKI (NA GÓRZE)
        # ============================================================

        _analysis_global_summary(_prep_df_for_analysis(df_m))


        # ============================================================
        # Wybór grup kolumn (UI)
        # ============================================================

        selected_columns: list[str] = []

        # ============================================================
        # Wybór grup kolumn (UI) – checkboxy w jednej linii
        # ============================================================

        selected_columns: list[str] = []

        # kolejność taka jak w dict (Python 3.7+ zachowuje kolejność definicji)
        group_items = list(COLUMN_GROUPS.items())

        # jedna linia: tyle kolumn ile grup
        cols = st.columns(len(group_items), gap="small")

        for i, (group_key, group) in enumerate(group_items):
            with cols[i]:
                default = bool(group.get("default", False))
                show_group = st.checkbox(
                    group["label"],
                    value=default,
                    key=f"cols_group_{group_key}",
                )
                if show_group:
                    selected_columns.extend(group["columns"])




        # ============================================================
        # DANE DO TABELI (TU POWSTAJE df_table)
        # ============================================================

        # fallback bezpieczeństwa – zawsze CORE
        if not selected_columns:
            selected_columns = COLUMN_GROUPS["core"]["columns"].copy()

        # tylko kolumny faktycznie obecne w df_market
        visible_columns = [c for c in selected_columns if c in df_m.columns]

        # --- USUNIĘCIE NIECHCIANYCH CEN Z TABELI ---
        HIDDEN_PRICE_COLUMNS = {
            "open_price",   # cena otwarcia
            "high_price",   # cena maksymalna
            "low_price",    # cena minimalna
        }

        visible_columns = [
            c for c in visible_columns
            if c not in HIDDEN_PRICE_COLUMNS
        ]


        df_table = df_m[visible_columns].copy()

        # sortowanie TYLKO lokalne (najnowsze na górze)
        if "trade_date" in df_table.columns:
            df_table = df_table.sort_values("trade_date", ascending=False)

        # --- formatowanie liczb (TYLKO UI) ---
        df_table = _format_numeric_columns_for_table(df_table)

        # ============================================================
        # AG GRID
        # ============================================================

        gb = GridOptionsBuilder.from_dataframe(df_table)




        # mapowanie nazw kolumn (DB -> UI)
        for col in df_table.columns:
            gb.configure_column(
                col,
                headerName=COLUMN_LABELS.get(col, col),
            )

        gb.configure_default_column(
            filter=True,
            sortable=True,
            resizable=True,
        )

        gb.configure_pagination(
            enabled=True,
            paginationAutoPageSize=False,
            paginationPageSize=50,
        )

        AgGrid(
            df_table,
            gridOptions=gb.build(),
            update_mode=GridUpdateMode.NO_UPDATE,
            height=500,
            theme="balham",
            key=f"table_{'_'.join(df_table.columns)}",
        )




        # ============================================================
        # ANALIZY – poniżej tabeli "Notowania" (jedna spółka)
        # ============================================================

        render_company_analyses_below_table(df_m)









