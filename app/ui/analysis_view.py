# app/ui/analysis_view.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.ui.column_metadata import COLUMN_LABELS, COLUMN_GROUPS, INDICATOR_TOOLTIPS


# ============================================================
# Session State Keys (spójne z data_overview.py)
# ============================================================

SSK = {
    # DF-y ładowane na ekranie "Podgląd danych"
    "df_companies": "do_df_companies",
    "df_prices": "do_df_prices_daily",
    "df_ind": "do_df_indicators_daily",
    # w data_overview.py to jest widok 1 spółki:
    "df_market_view": "do_df_market_view",
    # tu będziemy przechowywać market-wide df_market:
    "df_market_all": "do_df_market_all",
    # insighty z analiz (ADR-011)
    "insights": "analysis_insights",
    # wybrany fut_*
    "selected_future": "analysis_selected_future_signal",
}


# ============================================================
# Helpers: labels, safety
# ============================================================

# Zwraca przyjazną etykietę kolumny na podstawie słownika COLUMN_LABELS
def _ui_label(col: str) -> str:
    return COLUMN_LABELS.get(col, col)


# Konwertuje kolumnę 'trade_date' na typ datetime i usuwa wiersze z brakującą datą
def _ensure_datetime_trade_date(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "trade_date" not in df.columns:
        return df
    out = df.copy()
    out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce")
    out = out.dropna(subset=["trade_date"])
    return out


# Konwertuje serię na wartości numeryczne, zamieniając błędy na NaN
def _safe_numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


# Sprawdza, czy nazwa kolumny dotyczy sygnału future (zaczyna się od 'fut_')
def _is_future_col(c: str) -> bool:
    return isinstance(c, str) and c.startswith("fut_")


    # Zwraca listę kolumn numerycznych (z wyłączeniem metadanych i sygnałów future)
def _numeric_feature_cols(df: pd.DataFrame) -> List[str]:
    if df.empty:
        return []
    exclude = {
        "company_id",
        "ticker",
        "company_name",
        "name",
        "trade_date",
        "created_at",
        "modified_at",
        "source_ticker",
        "calc_flags",
    }
    cols = []
    for c in df.columns:
        if c in exclude:
            continue
        if _is_future_col(c):
            continue
        if pd.api.types.is_numeric_dtype(df[c]) or pd.api.types.is_bool_dtype(df[c]):
            cols.append(c)
    return cols


    # Zwraca uporządkowaną listę dostępnych kolumn future w DataFrame
def _available_future_cols(df: pd.DataFrame) -> List[str]:
    if df.empty:
        return []
    futs = [c for c in df.columns if _is_future_col(c)]
    # prefer bardziej "kanoniczne" na górze
    preferred = [
        "fut_signal_20_hyb",
        "fut_signal_20",
        "fut_signal_60",
        "fut_signal_120",
        "fut_imp_20",
        "fut_imp_60",
        "fut_imp_120",
    ]
    ordered = []
    for p in preferred:
        if p in futs:
            ordered.append(p)
    for c in sorted(futs):
        if c not in ordered:
            ordered.append(c)
    return ordered


    # Inicjalizuje domyślne wartości w stanie sesji Streamlit dla insightów i danych rynkowych
def _init_session_defaults() -> None:
    if SSK["insights"] not in st.session_state:
        st.session_state[SSK["insights"]] = []
    if SSK["df_market_all"] not in st.session_state:
        st.session_state[SSK["df_market_all"]] = None
    if SSK["selected_future"] not in st.session_state:
        st.session_state[SSK["selected_future"]] = "fut_signal_20_hyb"



# ============================================================
# Insight handling (ADR-011)
# ============================================================

    # Dodaje insight (wniosek z analizy) do stanu sesji Streamlit
def _push_insight(payload: Dict[str, Any]) -> None:
    insights = st.session_state.get(SSK["insights"])
    if not isinstance(insights, list):
        insights = []
    payload = dict(payload)
    payload.setdefault("ts", pd.Timestamp.utcnow().isoformat())
    st.session_state[SSK["insights"]] = insights + [payload]


    # Zwraca DataFrame z insightami zapisanymi w stanie sesji
def _insights_df() -> pd.DataFrame:
    insights = st.session_state.get(SSK["insights"], [])
    if not insights:
        return pd.DataFrame()
    return pd.DataFrame(insights)


# ============================================================
# Core analysis computations
# ============================================================

    # Oblicza rozkład wartości etykiety future (np. +1, -1, 0) wraz z udziałami procentowymi
def _label_distribution(df: pd.DataFrame, fut_col: str) -> pd.DataFrame:
    s = _safe_numeric(df.get(fut_col, pd.Series(dtype=float)))
    out = (
        s.dropna()
        .value_counts(dropna=False)
        .sort_index()
        .rename_axis("label")
        .reset_index(name="count")
    )
    out["share"] = out["count"] / out["count"].sum() if out["count"].sum() else 0.0
    return out


    # Analizuje rozkład cechy numerycznej względem etykiety future i zwraca statystyki grup oraz dane do wykresów
def _effect_stats_numeric_feature(
    df: pd.DataFrame,
    fut_col: str,
    feature_col: str,
    mode: str,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    mode:
      - "+1 vs reszta"
      - "+1 vs -1"
    Zwraca:
      - tabela statystyk grup
      - df_long do wykresów
    """
    tmp = df[[fut_col, feature_col]].copy()
    tmp[fut_col] = _safe_numeric(tmp[fut_col])
    tmp[feature_col] = _safe_numeric(tmp[feature_col])
    tmp = tmp.dropna(subset=[fut_col, feature_col])

    if tmp.empty:
        return pd.DataFrame(), pd.DataFrame()

    if mode == "+1 vs -1":
        tmp = tmp[tmp[fut_col].isin([1, -1])]
        tmp["group"] = np.where(tmp[fut_col] == 1, "+1", "-1")
    else:
        tmp["group"] = np.where(tmp[fut_col] == 1, "+1", "reszta")

    g = tmp.groupby("group")[feature_col]
    stats = g.agg(
        n="count",
        mean="mean",
        median="median",
        std="std",
        p10=lambda x: np.nanpercentile(x, 10),
        p25=lambda x: np.nanpercentile(x, 25),
        p75=lambda x: np.nanpercentile(x, 75),
        p90=lambda x: np.nanpercentile(x, 90),
    ).reset_index()

    # prosty efekt: różnica median (+1 - other)
    if set(stats["group"]) >= {"+1"}:
        med_pos = float(stats.loc[stats["group"] == "+1", "median"].iloc[0])
        if mode == "+1 vs -1" and (stats["group"] == "-1").any():
            med_other = float(stats.loc[stats["group"] == "-1", "median"].iloc[0])
        else:
            med_other = float(stats.loc[stats["group"] != "+1", "median"].iloc[0]) if (stats["group"] != "+1").any() else np.nan
        stats["median_delta_vs_other"] = np.where(stats["group"] == "+1", med_pos - med_other, np.nan)

    return stats, tmp.rename(columns={feature_col: "value"})[["group", "value"]]


    # Tworzy maskę logiczną (boolean) dla prostego setupu inwestycyjnego na podstawie parametrów
def _setup_mask(
    df: pd.DataFrame,
    rsi_threshold: float,
    require_above_sma200: bool,
    vol_quantile: float,
    require_volume_spike: bool,
    volume_spike_mult: float,
) -> Tuple[pd.Series, Dict[str, Any]]:
    """
    Prosty, interpretowalny setup (MVP) – bez kreatora dowolnych warunków.
    Zwraca maskę boolean i opis setupu.
    """
    mask = pd.Series(True, index=df.index)

    # RSI
    if "rsi_14" in df.columns:
        rsi = _safe_numeric(df["rsi_14"])
        mask &= (rsi <= rsi_threshold)

    # Trend: close > SMA200
    if require_above_sma200 and {"close_price", "sma_200"}.issubset(df.columns):
        close = _safe_numeric(df["close_price"])
        sma200 = _safe_numeric(df["sma_200"])
        mask &= (close >= sma200)

    # Volatility quantile
    if "volatility_20d" in df.columns:
        vol = _safe_numeric(df["volatility_20d"])
        q = float(vol.dropna().quantile(vol_quantile)) if not vol.dropna().empty else np.nan
        if not np.isnan(q):
            mask &= (vol <= q)

    # Volume spike
    if require_volume_spike and {"volume", "average_volume_20d"}.issubset(df.columns):
        v = _safe_numeric(df["volume"])
        vavg = _safe_numeric(df["average_volume_20d"])
        ratio = v / vavg
        mask &= (ratio >= volume_spike_mult)

    desc = {
        "rsi_14<=": rsi_threshold if "rsi_14" in df.columns else None,
        "close>=sma_200": require_above_sma200 and {"close_price", "sma_200"}.issubset(df.columns),
        "volatility_20d<=": vol_quantile if "volatility_20d" in df.columns else None,
        "volume/avg20>=": volume_spike_mult if require_volume_spike and {"volume", "average_volume_20d"}.issubset(df.columns) else None,
    }
    return mask.fillna(False), desc


    # Oblicza skuteczność (hit-rate) setupu na podstawie maski i etykiety future
def _setup_hit_stats(df: pd.DataFrame, fut_col: str, mask: pd.Series) -> Dict[str, Any]:
    tmp = df[[fut_col]].copy()
    tmp[fut_col] = _safe_numeric(tmp[fut_col])
    tmp = tmp.dropna(subset=[fut_col])

    if tmp.empty:
        return {"n": 0}

    # alignment mask
    m = mask.reindex(tmp.index).fillna(False)

    total = int(m.sum())
    if total == 0:
        return {"n": 0, "hit_rate_pos": np.nan, "counts": {}}

    sub = tmp.loc[m, fut_col]
    counts = sub.value_counts().to_dict()
    hit_pos = float((sub == 1).mean())

    out = {"n": total, "hit_rate_pos": hit_pos, "counts": counts}
    # opcjonalnie: średni impakt, jeśli analizujemy signal i mamy fut_imp_20
    return out


    # Normalizuje wybrane kolumny do z-score (standaryzacja)
def _normalize_z(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    x = df[cols].apply(_safe_numeric)
    mu = x.mean(skipna=True)
    sigma = x.std(skipna=True).replace(0, np.nan)
    return (x - mu) / sigma


    # Wyszukuje historyczne analogie na podstawie odległości euklidesowej po z-score cech
def _find_analogies(
    df: pd.DataFrame,
    ref_company_id: int,
    ref_date: pd.Timestamp,
    feature_cols: List[str],
    n: int,
) -> pd.DataFrame:
    """
    Prosta analogia: odległość euklidesowa po z-score cech.
    """
    if df.empty or not feature_cols:
        return pd.DataFrame()

    tmp = df.copy()
    tmp = _ensure_datetime_trade_date(tmp)
    tmp = tmp.dropna(subset=["company_id", "trade_date"])
    tmp["company_id"] = tmp["company_id"].astype(int)

    ref_rows = tmp[(tmp["company_id"] == int(ref_company_id)) & (tmp["trade_date"] == ref_date)]
    if ref_rows.empty:
        return pd.DataFrame()

    ref_idx = ref_rows.index[0]

    # przygotuj macierz cech
    x = tmp[feature_cols].apply(_safe_numeric)
    valid_mask = x.notna().all(axis=1)
    tmp2 = tmp.loc[valid_mask].copy()
    x2 = x.loc[valid_mask]

    if ref_idx not in tmp2.index:
        return pd.DataFrame()

    z = _normalize_z(tmp2, feature_cols)
    ref_vec = z.loc[ref_idx].values.astype(float)

    mat = z.values.astype(float)
    d = np.linalg.norm(mat - ref_vec, axis=1)
    tmp2["distance"] = d

    # usuń sam punkt referencyjny
    tmp2 = tmp2.drop(index=ref_idx, errors="ignore")

    # najbliższe N
    cols_out = ["company_id", "ticker", "company_name", "trade_date", "distance"]
    cols_out = [c for c in cols_out if c in tmp2.columns]
    return tmp2.sort_values("distance").head(n)[cols_out]


    # Oblicza skuteczność (hit-rate) setupu w podziale na lata (stabilność w czasie)
def _hit_rate_over_time(df: pd.DataFrame, fut_col: str, mask: pd.Series) -> pd.DataFrame:
    """
    Hit-rate per rok (MVP stabilności).
    """
    tmp = df.copy()
    tmp = _ensure_datetime_trade_date(tmp)
    if tmp.empty or fut_col not in tmp.columns:
        return pd.DataFrame()

    tmp[fut_col] = _safe_numeric(tmp[fut_col])
    tmp = tmp.dropna(subset=["trade_date", fut_col])

    m = mask.reindex(tmp.index).fillna(False)
    tmp = tmp.loc[m].copy()
    if tmp.empty:
        return pd.DataFrame()

    tmp["year"] = tmp["trade_date"].dt.year
    out = (
        tmp.groupby("year")[fut_col]
        .apply(lambda s: float((s == 1).mean()))
        .reset_index(name="hit_rate_pos")
        .sort_values("year")
    )
    return out


# ============================================================
# UI sections
# ============================================================

    # Wyświetla nagłówek i wprowadzenie do sekcji analizy danych
def _render_guard_and_intro() -> None:
    st.subheader("Analiza danych")
    st.caption("Warstwa eksploracyjna całej bazy danych pod przyszłe ML (bez prognozowania).")



    # Wyświetla podstawowe informacje o analizowanym zbiorze danych oraz rozkład etykiety future
def _render_dataset_context(df: pd.DataFrame, fut_col: str) -> None:
    st.subheader("Kontekst analizy")

    df2 = _ensure_datetime_trade_date(df)
    n_rows = len(df2)
    n_comp = int(df2["company_id"].nunique()) if "company_id" in df2.columns else 0
    dmin = df2["trade_date"].min().date().isoformat() if "trade_date" in df2.columns and not df2.empty else "—"
    dmax = df2["trade_date"].max().date().isoformat() if "trade_date" in df2.columns and not df2.empty else "—"

    c1, c2, c3 = st.columns(3, gap="small")
    c1.metric("Obserwacje", f"{n_rows:,}".replace(",", " "))
    c2.metric("Spółki", f"{n_comp:,}".replace(",", " "))
    c3.metric("Zakres dat", f"{dmin} → {dmax}")

    if fut_col not in df.columns:
        st.info(f"Brak kolumny sygnału future: {fut_col}")
        return

    dist = _label_distribution(df2, fut_col)
    if dist.empty:
        st.info("Brak wartości etykiety future w aktualnym zakresie.")
        return

    # wykres rozkładu
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=dist["label"].astype(str),
        y=dist["count"],
        name="Liczność",
    ))
    fig.update_layout(
        height=260,
        margin=dict(l=10, r=10, t=20, b=10),
        xaxis_title="Etykieta",
        yaxis_title="Liczba obserwacji",
    )
    st.plotly_chart(fig, width="stretch")


    # Sekcja analizy rozkładów cech numerycznych względem etykiety future
def _render_feature_distribution_section(df: pd.DataFrame, fut_col: str) -> None:
    st.subheader("Analiza rozkładów cech")

    feature_cols = _numeric_feature_cols(df)
    if not feature_cols:
        st.info("Brak cech numerycznych do analizy.")
        return

    c1, c2, c3 = st.columns([3, 2, 2], gap="small")
    with c1:
        feature = st.selectbox(
            "Cecha",
            options=feature_cols,
            format_func=lambda x: _ui_label(x),
            key="ad_feature_select",
        )
    with c2:
        mode = st.selectbox(
            "Tryb porównania",
            options=["+1 vs reszta", "+1 vs -1"],
            key="ad_feature_mode",
        )
    with c3:
        ignore_nan = st.checkbox("Ignoruj NaN", value=True, key="ad_feature_ignore_nan")

    if st.button("Analizuj rozkład", key="ad_btn_feature"):
        with st.spinner("Liczenie statystyk rozkładu..."):
            stats, df_long = _effect_stats_numeric_feature(df, fut_col, feature, mode)

        if stats.empty or df_long.empty:
            st.info("Brak danych do porównania (sprawdź NaN i dostępność etykiet).")
            return

        # wykres boxplot
        fig = go.Figure()
        for g in df_long["group"].unique():
            fig.add_trace(go.Box(
                y=df_long.loc[df_long["group"] == g, "value"],
                name=str(g),
                boxmean="sd",
            ))
        fig.update_layout(
            height=320,
            margin=dict(l=10, r=10, t=20, b=10),
            yaxis_title=_ui_label(feature),
        )
        st.plotly_chart(fig, width="stretch")

        # tabela stat
        st.dataframe(stats, width="stretch", hide_index=True)

        # insight
        # strength: abs(delta_median) / std(all) – prosta miara
        all_std = float(_safe_numeric(df[feature]).dropna().std()) if feature in df.columns else np.nan
        delta = float(stats["median_delta_vs_other"].dropna().iloc[0]) if "median_delta_vs_other" in stats.columns and not stats["median_delta_vs_other"].dropna().empty else np.nan
        strength = abs(delta) / all_std if (not np.isnan(delta) and not np.isnan(all_std) and all_std != 0) else np.nan

        _push_insight({
            "signal": fut_col,
            "kind": "feature_distribution",
            "feature": feature,
            "feature_label": _ui_label(feature),
            "compare_mode": mode,
            "median_delta": delta,
            "strength": strength,
            "n_used": int(df_long.shape[0]),
        })

        st.success("Zapisano insight do podsumowania.")


    # Sekcja analizy skuteczności prostych setupów inwestycyjnych
def _render_setup_section(df: pd.DataFrame, fut_col: str) -> None:
    st.subheader("Analiza konfiguracji (setupów)")

    # parametry setupu (MVP)
    c1, c2, c3, c4 = st.columns([2, 2, 2, 2], gap="small")
    with c1:
        rsi_thr = st.number_input("RSI 14 ≤", value=40.0, min_value=1.0, max_value=99.0, step=1.0, key="ad_setup_rsi")
    with c2:
        above_sma200 = st.checkbox("Cena ≥ SMA200", value=True, key="ad_setup_sma200")
    with c3:
        vol_q = st.slider("Zmienność ≤ percentyl", min_value=5, max_value=95, value=30, step=5, key="ad_setup_volq")
    with c4:
        vol_spike = st.checkbox("Wolumen spike", value=False, key="ad_setup_volspike")

    vol_mult = 1.5
    if vol_spike:
        vol_mult = st.number_input("Wolumen / Śr.20D ≥", value=1.5, min_value=1.0, max_value=10.0, step=0.1, key="ad_setup_volmult")

    if st.button("Sprawdź setup", key="ad_btn_setup"):
        with st.spinner("Liczenie setupu..."):
            mask, desc = _setup_mask(
                df=df,
                rsi_threshold=float(rsi_thr),
                require_above_sma200=bool(above_sma200),
                vol_quantile=float(vol_q) / 100.0,
                require_volume_spike=bool(vol_spike),
                volume_spike_mult=float(vol_mult),
            )
            stats = _setup_hit_stats(df, fut_col, mask)

        if stats.get("n", 0) == 0:
            st.info("Setup nie zwrócił żadnych obserwacji (lub brak danych).")
            return

        # wynik
        cA, cB, cC = st.columns(3, gap="small")
        cA.metric("Liczba przypadków", f"{int(stats['n']):,}".replace(",", " "))
        cB.metric("Hit-rate (+1)", f"{stats['hit_rate_pos']*100:.2f}%")
        cC.metric("Unikalne wyniki", str(sorted(list(stats.get("counts", {}).keys()))))

        # tabela counts
        counts_df = pd.DataFrame(
            [{"label": k, "count": v} for k, v in stats.get("counts", {}).items()]
        ).sort_values("label")
        st.dataframe(counts_df, width="stretch", hide_index=True)

        # insight
        _push_insight({
            "signal": fut_col,
            "kind": "setup",
            "setup_desc": desc,
            "hit_rate_pos": float(stats["hit_rate_pos"]),
            "n_used": int(stats["n"]),
            "strength": float(stats["hit_rate_pos"]),  # prosto: skuteczność = strength
        })
        st.success("Zapisano insight do podsumowania.")

        # zapisz maskę dla stabilności/analogii (opcjonalnie)
        st.session_state["ad_last_setup_mask"] = mask
        st.session_state["ad_last_setup_desc"] = desc


    # Sekcja wyszukiwania historycznych analogii na podstawie cech i daty referencyjnej
def _render_analogies_section(df: pd.DataFrame, fut_col: str) -> None:
    st.subheader("Analogie historyczne")

    df2 = _ensure_datetime_trade_date(df)
    if df2.empty or "company_id" not in df2.columns or "trade_date" not in df2.columns:
        st.info("Brak danych do analogii.")
        return

    # wybór cech do analogii
    default_features = []
    for gk in ["momentum_risk", "trends", "oscillators", "volume_vol", "quality", "fundamentals"]:
        cols = COLUMN_GROUPS.get(gk, {}).get("columns", [])
        default_features.extend([c for c in cols if c in df2.columns and not _is_future_col(c)])
    default_features = list(dict.fromkeys(default_features))  # unique, keep order

    feat_options = _numeric_feature_cols(df2)
    feat_selected = st.multiselect(
        "Cechy do analogii (z-score)",
        options=feat_options,
        default=[c for c in default_features if c in feat_options][:12],
        format_func=lambda x: _ui_label(x),
        key="ad_analogy_features",
    )

    # wybór punktu odniesienia
    # - ticker
    if "ticker" in df2.columns:
        tickers = df2["ticker"].dropna().astype(str).unique().tolist()
        tickers.sort()
    else:
        tickers = []

    c1, c2, c3 = st.columns([2, 2, 1], gap="small")
    with c1:
        ticker = st.selectbox("Spółka (ticker)", options=tickers, key="ad_analogy_ticker") if tickers else None
    with c2:
        n = st.number_input("Liczba analogii", value=20, min_value=5, max_value=200, step=5, key="ad_analogy_n")
    with c3:
        run = st.button("Znajdź analogie", key="ad_btn_analogies")

    if not ticker or not feat_selected:
        st.info("Wybierz ticker i zestaw cech.")
        return

    # dostępne daty dla tickera
    df_t = df2[df2["ticker"] == ticker]
    if df_t.empty:
        st.info("Brak danych dla wybranego tickera.")
        return

    # data referencyjna (domyślnie najnowsza)
    dates = df_t["trade_date"].dropna().sort_values().unique()
    if len(dates) == 0:
        st.info("Brak dat dla wybranego tickera.")
        return

    ref_date = st.selectbox(
        "Data referencyjna",
        options=list(dates),
        index=len(dates) - 1,
        key="ad_analogy_date",
        format_func=lambda d: pd.Timestamp(d).date().isoformat(),
    )

    if run:
        with st.spinner("Liczenie analogii (odległość po z-score)..."):
            ref_company_id = int(df_t["company_id"].iloc[0])
            ref_date_ts = pd.Timestamp(ref_date)
            res = _find_analogies(
                df=df2,
                ref_company_id=ref_company_id,
                ref_date=ref_date_ts,
                feature_cols=feat_selected,
                n=int(n),
            )

        if res.empty:
            st.info("Nie udało się znaleźć analogii (sprawdź kompletność cech).")
            return

        # wynik
        out = res.copy()
        out["trade_date"] = out["trade_date"].dt.date.astype(str) if "trade_date" in out.columns else out.get("trade_date")
        st.dataframe(out, width="stretch", hide_index=True)

        # jeśli w df2 jest fut_col, policz rozkład outcome analogii (po datach)
        if fut_col in df2.columns and {"company_id", "trade_date"}.issubset(df2.columns):
            join_cols = ["company_id", "trade_date"]
            tmp = df2[join_cols + [fut_col]].copy()
            tmp = _ensure_datetime_trade_date(tmp)
            merged = res.merge(tmp, on=join_cols, how="left")
            merged[fut_col] = _safe_numeric(merged[fut_col])
            dist = merged[fut_col].dropna().value_counts().to_dict()
            hit_pos = float((merged[fut_col] == 1).mean()) if not merged[fut_col].dropna().empty else np.nan

            cA, cB = st.columns(2, gap="small")
            cA.metric("Hit-rate (+1) w analogiach", f"{hit_pos*100:.2f}%" if not np.isnan(hit_pos) else "—")
            cB.metric("Unikalne wyniki", str(sorted(list(dist.keys()))))

            _push_insight({
                "signal": fut_col,
                "kind": "analogies",
                "reference": f"{ticker} @ {pd.Timestamp(ref_date).date().isoformat()}",
                "n_used": int(len(res)),
                "hit_rate_pos": hit_pos,
                "strength": hit_pos,
                "features_used": feat_selected,
            })
            st.success("Zapisano insight do podsumowania.")


    # Sekcja oceny stabilności skuteczności setupu w czasie (per rok)
def _render_stability_section(df: pd.DataFrame, fut_col: str) -> None:
    st.subheader("Stabilność w czasie")

    mask = st.session_state.get("ad_last_setup_mask")
    if not isinstance(mask, pd.Series):
        st.info("Najpierw uruchom analizę setupu (żeby ocenić stabilność tego setupu).")
        return

    if st.button("Analizuj stabilność setupu", key="ad_btn_stability"):
        with st.spinner("Liczenie stabilności (hit-rate per rok)..."):
            out = _hit_rate_over_time(df, fut_col, mask)

        if out.empty:
            st.info("Brak danych do stabilności (mask/etykiety/zakres).")
            return

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=out["year"].astype(int),
            y=out["hit_rate_pos"] * 100.0,
            mode="lines+markers",
            name="Hit-rate (+1)",
        ))
        fig.update_layout(
            height=320,
            margin=dict(l=10, r=10, t=20, b=10),
            xaxis_title="Rok",
            yaxis_title="Hit-rate (+1) [%]",
        )
        st.plotly_chart(fig, width="stretch")
        st.dataframe(out, width="stretch", hide_index=True)

        _push_insight({
            "signal": fut_col,
            "kind": "stability",
            "setup_desc": st.session_state.get("ad_last_setup_desc"),
            "n_years": int(out.shape[0]),
            "min_hit": float(out["hit_rate_pos"].min()),
            "max_hit": float(out["hit_rate_pos"].max()),
            "strength": float(out["hit_rate_pos"].mean()),
        })
        st.success("Zapisano insight do podsumowania.")


    # Sekcja podsumowania i prezentacji najważniejszych insightów z analiz
def _render_summary_section(fut_col: str) -> None:
    st.subheader("Podsumowanie zależności")

    dfi = _insights_df()
    if dfi.empty:
        st.info("Brak zapisanych insightów. Uruchom wybrane analizy, aby zbudować podsumowanie.")
        return

    # filtr po sygnale
    df_sig = dfi[dfi.get("signal") == fut_col].copy() if "signal" in dfi.columns else dfi.copy()
    if df_sig.empty:
        st.info("Brak insightów dla wybranego sygnału.")
        return

    # rank: po strength (desc), a potem n_used
    if "strength" in df_sig.columns:
        df_sig["strength"] = pd.to_numeric(df_sig["strength"], errors="coerce")
    if "n_used" in df_sig.columns:
        df_sig["n_used"] = pd.to_numeric(df_sig["n_used"], errors="coerce")

    sort_cols = [c for c in ["strength", "n_used"] if c in df_sig.columns]
    if sort_cols:
        df_sig = df_sig.sort_values(sort_cols, ascending=[False] * len(sort_cols))

    # pokazujemy sensowne kolumny
    preferred = [
        "kind",
        "feature_label",
        "feature",
        "compare_mode",
        "setup_desc",
        "reference",
        "strength",
        "hit_rate_pos",
        "median_delta",
        "n_used",
        "min_hit",
        "max_hit",
        "ts",
    ]
    cols = [c for c in preferred if c in df_sig.columns]
    # fallback
    if not cols:
        cols = list(df_sig.columns)

    st.dataframe(df_sig[cols], width="stretch", hide_index=True)

    # proste, narracyjne wnioski (bez rekomendacji)
    st.markdown("#### Syntetyczne wnioski")
    top = df_sig.head(5)
    lines = []
    for _, row in top.iterrows():
        kind = str(row.get("kind", ""))
        if kind == "feature_distribution":
            lines.append(
                f"Cecha **{row.get('feature_label', row.get('feature'))}** ma wykrywalną różnicę względem `{fut_col}` "
                f"(siła ≈ {row.get('strength', np.nan):.3f})."
            )
        elif kind == "setup":
            lines.append(
                f"Setup ma hit-rate(+1) ≈ **{float(row.get('hit_rate_pos', np.nan))*100:.2f}%** (n={int(row.get('n_used', 0))})."
            )
        elif kind == "analogies":
            lines.append(
                f"Analogie dla **{row.get('reference','')}**: hit-rate(+1) ≈ **{float(row.get('hit_rate_pos', np.nan))*100:.2f}%**."
            )
        elif kind == "stability":
            lines.append(
                f"Stabilność setupu: średni hit-rate(+1) ≈ **{float(row.get('strength', np.nan))*100:.2f}%**, "
                f"min={float(row.get('min_hit', np.nan))*100:.1f}%, max={float(row.get('max_hit', np.nan))*100:.1f}%."
            )

    if lines:
        for ln in lines:
            st.markdown(f"- {ln}")
    else:
        st.info("Brak wystarczających danych do automatycznego opisu.")

    # akcje
    c1, c2 = st.columns([1, 1], gap="small")
    with c1:
        if st.button("Wyczyść insighty", key="ad_btn_clear_insights"):
            st.session_state[SSK["insights"]] = []
            st.success("Wyczyszczono insighty.")
            st.rerun()
    with c2:
        # eksport jako CSV w UI
        csv = df_sig.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Pobierz podsumowanie CSV",
            data=csv,
            file_name=f"analysis_summary_{fut_col}.csv",
            mime="text/csv",
            key="ad_btn_download_summary",
        )


# ============================================================
# Render
# ============================================================

    # Główna funkcja renderująca całą stronę analizy danych w aplikacji Streamlit
def render() -> None:
    _init_session_defaults()

    df_market = st.session_state.get(SSK["df_market_all"])
    if not isinstance(df_market, pd.DataFrame) or df_market.empty:
        st.subheader("Analiza danych")
        st.info(
            "Brak danych do analizy.\n\n"
            "Przejdź na ekran **„Przegląd danych”** i załaduj dane, "
            "dla których chcesz wykonać analizę."
        )
        return

    _render_guard_and_intro()

    # wybór sygnału fut_*
    fut_cols = _available_future_cols(df_market)
    if not fut_cols:
        st.warning("Brak kolumn future (fut_*) w df_market.")
        return

    # UX: podobny styl do data_overview (małe odstępy, dużo treści)
    colA, colB = st.columns([2, 3], gap="small")
    with colA:
        fut_col = st.selectbox(
            "Analizowany sygnał future (fut_*)",
            options=fut_cols,
            index=fut_cols.index(st.session_state.get(SSK["selected_future"], fut_cols[0]))
            if st.session_state.get(SSK["selected_future"], fut_cols[0]) in fut_cols
            else 0,
            format_func=lambda x: _ui_label(x),
            key=SSK["selected_future"],
            help="Wybór etykiety future steruje wszystkimi analizami (ten sam schemat, różne wyniki).",
        )
    with colB:
        st.caption(
            "Analizy są niezależne i uruchamiane świadomie przyciskami. "
            "Każda analiza zapisuje 'insight' do podsumowania na końcu."
        )

    st.divider()

    # 1) Kontekst
    _render_dataset_context(df_market, fut_col)

    st.divider()

    # 2) Rozkłady cech
    _render_feature_distribution_section(df_market, fut_col)

    st.divider()

    # 3) Setupy
    _render_setup_section(df_market, fut_col)

    st.divider()

    # 4) Analogie
    _render_analogies_section(df_market, fut_col)

    st.divider()

    # 5) Stabilność
    _render_stability_section(df_market, fut_col)

    st.divider()

    # 6) Podsumowanie
    _render_summary_section(fut_col)
