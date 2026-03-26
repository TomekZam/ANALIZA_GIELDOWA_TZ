# app/ui/analysis_view_v2.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.ui.column_metadata import COLUMN_LABELS


# ============================================================
# Session State Keys (spójne z data_overview.py + własne dla v2)
# ============================================================

SSK = {
    # DF-y ładowane na ekranie "Przegląd danych"
    "df_companies": "do_df_companies",
    "df_prices": "do_df_prices_daily",
    "df_ind": "do_df_indicators_daily",
    # fallback (widok 1 spółki z Przeglądu danych)
    "df_market_view": "do_df_market_view",
    # cache market-wide df_market w analizie
    "df_market_all": "do_df_market_all",
    # insighty z analiz (osobne od v1)
    "insights": "analysis_v2_insights",
    # wybrany fut_*
    "selected_future": "analysis_v2_selected_future_signal",
}


# ============================================================
# Helpers: labels, safety
# ============================================================

# Zwraca czytelną etykietę kolumny na podstawie słownika
def _ui_label(col: str) -> str:
    # Jeśli kolumna jest w słowniku, zwróć jej etykietę, inaczej nazwę oryginalną
    return COLUMN_LABELS.get(col, col)


# Konwertuje kolumnę 'trade_date' na typ datetime i usuwa wiersze bez daty
def _ensure_datetime_trade_date(df: pd.DataFrame) -> pd.DataFrame:
    # Jeśli DataFrame jest pusty lub nie ma kolumny 'trade_date', zwróć bez zmian
    if df.empty or "trade_date" not in df.columns:
        return df
    out = df.copy()  # Tworzymy kopię, by nie modyfikować oryginału
    out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce")  # Konwersja na datetime
    out = out.dropna(subset=["trade_date"])  # Usuwamy wiersze bez daty
    return out


# Konwertuje serię na liczby, błędy zamienia na NaN
def _safe_numeric(s: pd.Series) -> pd.Series:
    # Używamy pd.to_numeric z errors="coerce" by zamienić błędne wartości na NaN
    return pd.to_numeric(s, errors="coerce")


# Sprawdza czy kolumna to sygnał future (nazwa zaczyna się od 'fut_')
def _is_future_col(c: str) -> bool:
    # Sprawdzamy typ i początek nazwy
    return isinstance(c, str) and c.startswith("fut_")


# Zwraca listę kolumn numerycznych (bez metadanych i sygnałów future)
def _numeric_feature_cols(df: pd.DataFrame) -> List[str]:
    if df.empty:
        return []  # Jeśli DataFrame pusty, zwróć pustą listę
    exclude = {
        "company_id", "ticker", "company_name", "name", "trade_date",
        "created_at", "modified_at", "source_ticker", "calc_flags"
    }
    cols: list[str] = []
    for c in df.columns:
        # Pomijamy kolumny z exclude
        if c in exclude:
            continue
        # Pomijamy kolumny sygnałów future
        if _is_future_col(c):
            continue
        # Dodajemy tylko kolumny numeryczne lub boolowskie
        if pd.api.types.is_numeric_dtype(df[c]) or pd.api.types.is_bool_dtype(df[c]):
            cols.append(c)
    return cols


# Zwraca uporządkowaną listę kolumn sygnałów future
def _available_future_cols(df: pd.DataFrame) -> List[str]:
    if df.empty:
        return []  # Brak danych
    futs = [c for c in df.columns if _is_future_col(c)]  # Lista kolumn future
    preferred = [
        "fut_signal_20_hyb", "fut_signal_20", "fut_signal_60", "fut_signal_120",
        "fut_imp_20", "fut_imp_60", "fut_imp_120"
    ]
    ordered: list[str] = []
    for p in preferred:
        if p in futs:
            ordered.append(p)  # Najpierw preferowane
    for c in sorted(futs):
        if c not in ordered:
            ordered.append(c)  # Potem reszta alfabetycznie
    return ordered


# Ustawia domyślne wartości w stanie sesji Streamlit
def _init_session_defaults() -> None:
    if SSK["insights"] not in st.session_state:
        st.session_state[SSK["insights"]] = []  # Lista insightów
    if SSK["df_market_all"] not in st.session_state:
        st.session_state[SSK["df_market_all"]] = None  # Dane rynkowe
    if SSK["selected_future"] not in st.session_state:
        st.session_state[SSK["selected_future"]] = "fut_signal_20_hyb"  # Domyślny sygnał


# ============================================================
# Insights (ADR-011 style)
# ============================================================

# Dodaje nowy insight (wniosek) do listy insightów w stanie sesji
def _push_insight(payload: Dict[str, Any]) -> None:
    insights = st.session_state.get(SSK["insights"])  # Pobierz aktualną listę insightów
    if not isinstance(insights, list):
        insights = []  # Jeśli nie ma listy, utwórz nową
    payload = dict(payload)  # Upewnij się, że to słownik
    payload.setdefault("ts", pd.Timestamp.utcnow().isoformat())  # Dodaj timestamp jeśli brak
    st.session_state[SSK["insights"]] = insights + [payload]  # Dodaj insight do listy


# Zwraca DataFrame z insightami z sesji (lub pusty DataFrame)
def _insights_df() -> pd.DataFrame:
    insights = st.session_state.get(SSK["insights"], [])  # Pobierz insighty
    if not insights:
        return pd.DataFrame()  # Brak insightów
    return pd.DataFrame(insights)  # Zamień na DataFrame


# ============================================================
# Core computations for v2 (feature discovery)
# ============================================================

# Zwraca DataFrame z rozkładem wartości etykiety future (np. +1, -1, 0)
def _label_distribution(df: pd.DataFrame, fut_col: str) -> pd.DataFrame:
    s = _safe_numeric(df.get(fut_col, pd.Series(dtype=float)))  # Pobierz kolumnę jako liczby
    out = (
        s.dropna()  # Usuń NaN
        .value_counts(dropna=False)  # Policz wystąpienia każdej wartości
        .sort_index()  # Posortuj po wartości
        .rename_axis("label")  # Nazwij kolumnę z wartościami
        .reset_index(name="count")  # Zamień na DataFrame
    )
    out["share"] = out["count"] / out["count"].sum() if out["count"].sum() else 0.0  # Dodaj udział procentowy
    return out


# Zwraca bazowe prawdopodobieństwo wystąpienia +1 w kolumnie future
def _baseline_pos_rate(df: pd.DataFrame, fut_col: str) -> float:
    s = _safe_numeric(df.get(fut_col, pd.Series(dtype=float))).dropna()  # Pobierz kolumnę jako liczby
    if s.empty:
        return float("nan")  # Brak danych
    return float((s == 1).mean())  # Udział +1


    # Zwraca metryki separacji rozkładów cechy względem etykiety future
def _effect_stats_feature(
    df: pd.DataFrame,
    fut_col: str,
    feature_col: str,
    mode: str,
) -> Dict[str, Any]:
    """
    Zwraca ustandaryzowane metryki separacji rozkładów (+1 vs reszta / +1 vs -1).
    Bez testów statystycznych (MVP), skupienie na efektach i interpretowalności.
    """
# Przygotuj dane do porównania rozkładów cechy względem etykiety future
    tmp = df[[fut_col, feature_col]].copy()  # Wybierz tylko potrzebne kolumny
    tmp[fut_col] = _safe_numeric(tmp[fut_col])  # Zamień na liczby
    tmp[feature_col] = _safe_numeric(tmp[feature_col])
    tmp = tmp.dropna(subset=[fut_col, feature_col])  # Usuń wiersze z brakami
    if tmp.empty:
        return {}  # Brak danych

    if mode == "+1 vs -1":
        tmp = tmp[tmp[fut_col].isin([1, -1])]  # Tylko +1 i -1
        a = tmp.loc[tmp[fut_col] == 1, feature_col]  # Wartości dla +1
        b = tmp.loc[tmp[fut_col] == -1, feature_col]  # Wartości dla -1
        group_other = "-1"
    else:
        a = tmp.loc[tmp[fut_col] == 1, feature_col]  # Wartości dla +1
        b = tmp.loc[tmp[fut_col] != 1, feature_col]  # Wartości dla reszty
        group_other = "reszta"

    if a.empty or b.empty:
        return {}  # Brak danych do porównania

    med_a = float(a.median())  # Mediana dla +1
    med_b = float(b.median())  # Mediana dla drugiej grupy
    delta = med_a - med_b  # Różnica median

    std_all = float(tmp[feature_col].std()) if float(tmp[feature_col].std() or 0) != 0 else np.nan  # Odchylenie std
    strength = abs(delta) / std_all if (not np.isnan(std_all) and std_all != 0) else np.nan  # Siła efektu

    return {
        "feature": feature_col,
        "feature_label": _ui_label(feature_col),
        "compare_mode": mode,
        "n_used": int(tmp.shape[0]),
        "n_pos": int((tmp[fut_col] == 1).sum()),
        "n_other": int((tmp[fut_col] != 1).sum()) if mode != "+1 vs -1" else int((tmp[fut_col] == -1).sum()),
        "median_pos": med_a,
        "median_other": med_b,
        "median_delta": float(delta),
        "strength": float(strength) if not np.isnan(strength) else np.nan,
        "p25_pos": float(a.quantile(0.25)),
        "p75_pos": float(a.quantile(0.75)),
        "p25_other": float(b.quantile(0.25)),
        "p75_other": float(b.quantile(0.75)),
        "other_group": group_other,
    }


    # Dzieli cechę na koszyki kwantylowe i liczy P(+1) oraz lift względem baseline
def _lift_by_quantile_buckets(
    df: pd.DataFrame,
    fut_col: str,
    feature_col: str,
    q: int,
    direction: str,
) -> pd.DataFrame:
    """
    Bucketizacja cechy i liczenie P(+1) per bucket oraz lift vs baseline.
    direction:
      - "low->high" (bucket 0 = najniższe wartości)
      - "high->low" (bucket 0 = najwyższe wartości)
    """
# Przygotuj dane do bucketowania cechy
    tmp = df[[fut_col, feature_col]].copy()  # Wybierz tylko potrzebne kolumny
    tmp[fut_col] = _safe_numeric(tmp[fut_col])  # Zamień na liczby
    tmp[feature_col] = _safe_numeric(tmp[feature_col])
    tmp = tmp.dropna(subset=[fut_col, feature_col])  # Usuń wiersze z brakami
    if tmp.empty:
        return pd.DataFrame()  # Brak danych

    base = float((tmp[fut_col] == 1).mean()) if tmp.shape[0] else np.nan  # Bazowy udział +1

    tmp["bucket"] = pd.qcut(tmp[feature_col], q=q, duplicates="drop")  # Podział na koszyki kwantylowe
    agg = tmp.groupby("bucket")[fut_col].agg(
        n="count",  # Liczność w koszyku
        p_pos=lambda s: float((s == 1).mean()),  # Udział +1 w koszyku
    ).reset_index()

    agg["lift"] = agg["p_pos"] / base if (not np.isnan(base) and base != 0) else np.nan  # Lift względem baseline

    if direction == "high->low":
        # Odwróć kolejność bucketów wg środka przedziału
        def _mid(iv) -> float:
            try:
                return float(iv.mid)
            except Exception:
                return float("nan")

        agg["_mid"] = agg["bucket"].apply(_mid)
        agg = agg.sort_values("_mid", ascending=False).drop(columns=["_mid"])
    else:
        # Naturalnie rosnąco (low->high)
        agg = agg.sort_values("bucket", ascending=True)

    return agg


    # Tworzy siatkę interakcji dwóch cech (bucketowanych) i liczy P(+1) oraz lift
def _interaction_grid(
    df: pd.DataFrame,
    fut_col: str,
    f1: str,
    f2: str,
    q1: int,
    q2: int,
) -> Tuple[pd.DataFrame, float]:
    """
    Prosta analiza interakcji 2D:
    - bucket1 = qcut(f1, q1)
    - bucket2 = qcut(f2, q2)
    - P(+1) w komórkach siatki + liczność
    """
# Przygotuj dane do analizy interakcji dwóch cech
    tmp = df[[fut_col, f1, f2]].copy()  # Wybierz tylko potrzebne kolumny
    tmp[fut_col] = _safe_numeric(tmp[fut_col])  # Zamień na liczby
    tmp[f1] = _safe_numeric(tmp[f1])
    tmp[f2] = _safe_numeric(tmp[f2])
    tmp = tmp.dropna(subset=[fut_col, f1, f2])  # Usuń wiersze z brakami
    if tmp.empty:
        return pd.DataFrame(), float("nan")  # Brak danych

    baseline = float((tmp[fut_col] == 1).mean()) if tmp.shape[0] else np.nan  # Bazowy udział +1

    tmp["b1"] = pd.qcut(tmp[f1], q=q1, duplicates="drop")  # Bucketowanie cechy 1
    tmp["b2"] = pd.qcut(tmp[f2], q=q2, duplicates="drop")  # Bucketowanie cechy 2

    grid = (
        tmp.groupby(["b1", "b2"])[fut_col]
        .agg(
            n="count",  # Liczność w komórce
            p_pos=lambda s: float((s == 1).mean()),  # Udział +1 w komórce
        )
        .reset_index()
    )
    grid["lift"] = grid["p_pos"] / baseline if (not np.isnan(baseline) and baseline != 0) else np.nan  # Lift
    return grid, baseline


# ============================================================
# UI sections
# ============================================================

# Wyświetla nagłówek i opis sekcji analizy danych v2
def _render_guard_and_intro() -> None:
    st.subheader("Analiza danych (v2)")  # Nagłówek sekcji
    st.caption(
        "Feature discovery pod ML: identyfikacja cech i interakcji cech, "
        "które różnicują dni z +1 vs reszta (bez prognozowania)."
    )  # Opis sekcji




# Wyświetla podstawowe informacje o analizowanym zbiorze danych i rozkład etykiety future
def _render_dataset_context(df: pd.DataFrame, fut_col: str) -> None:
    st.subheader("Kontekst analizy")  # Nagłówek sekcji

    df2 = _ensure_datetime_trade_date(df)  # Upewnij się, że daty są typu datetime
    n_rows = len(df2)  # Liczba wierszy
    n_comp = int(df2["company_id"].nunique()) if "company_id" in df2.columns else 0  # Liczba spółek
    dmin = df2["trade_date"].min().date().isoformat() if "trade_date" in df2.columns and not df2.empty else "—"  # Najwcześniejsza data
    dmax = df2["trade_date"].max().date().isoformat() if "trade_date" in df2.columns and not df2.empty else "—"  # Najpóźniejsza data

    c1, c2, c3 = st.columns(3, gap="small")  # Trzy kolumny na metryki
    c1.metric("Obserwacje", f"{n_rows:,}".replace(",", " "))  # Liczba obserwacji
    c2.metric("Spółki", f"{n_comp:,}".replace(",", " "))  # Liczba spółek
    c3.metric("Zakres dat", f"{dmin} → {dmax}")  # Zakres dat

    if fut_col not in df.columns:
        st.info(f"Brak kolumny sygnału future: {fut_col}")  # Brak kolumny future
        return

    dist = _label_distribution(df2, fut_col)  # Rozkład etykiety future
    if dist.empty:
        st.info("Brak wartości etykiety future w aktualnym zakresie.")  # Brak danych
        return

    fig = go.Figure()  # Tworzymy wykres
    fig.add_trace(go.Bar(x=dist["label"].astype(str), y=dist["count"], name="Liczność"))  # Słupki
    fig.update_layout(
        height=260,
        margin=dict(l=10, r=10, t=20, b=10),
        xaxis_title="Etykieta",
        yaxis_title="Liczba obserwacji",
    )
    st.plotly_chart(fig, width="stretch")  # Wyświetl wykres

    base = _baseline_pos_rate(df2, fut_col)  # Bazowy udział +1
    if not np.isnan(base):
        st.caption(f"Baseline P(+1) w aktualnym zakresie: **{base*100:.2f}%**")  # Wyświetl baseline


# Sekcja screeningu cech numerycznych względem etykiety future
def _render_feature_screening_section(df: pd.DataFrame, fut_col: str) -> None:
    st.subheader("1️⃣ Screening cech (+1 vs reszta)")  # Nagłówek sekcji

    feature_cols = _numeric_feature_cols(df)  # Lista cech numerycznych
    if not feature_cols:
        st.info("Brak cech numerycznych do analizy.")  # Brak cech do analizy
        return

    c1, c2, c3 = st.columns([4, 2, 2], gap="small")  # Trzy kolumny do wyboru parametrów
    with c1:
        selected = st.multiselect(
            "Zbiór cech do screeningu",
            options=feature_cols,
            default=[c for c in ["rsi_14", "volatility_20d", "momentum_12m", "max_drawdown_252d", "sharpe_20d", "sma_200", "ema_200"] if c in feature_cols],
            format_func=lambda x: _ui_label(x),
            key="ad2_screen_features",
        )  # Wybór cech do analizy
    with c2:
        mode = st.selectbox(
            "Tryb porównania",
            options=["+1 vs reszta", "+1 vs -1"],
            key="ad2_screen_mode",
        )  # Wybór trybu porównania
    with c3:
        top_n = st.number_input("Top N", min_value=5, max_value=50, value=15, step=1, key="ad2_screen_topn")  # Liczba top cech

    if st.button("Uruchom screening", key="ad2_btn_screen"):
        if not selected:
            st.warning("Wybierz przynajmniej jedną cechę.")  # Brak wybranych cech
            return

        with st.spinner("Liczenie metryk screeningu..."):
            rows: list[dict[str, Any]] = []
            for f in selected:
                r = _effect_stats_feature(df, fut_col, f, mode)  # Licz metryki dla każdej cechy
                if r:
                    rows.append(r)

            res = pd.DataFrame(rows)  # Wyniki jako DataFrame

        if res.empty:
            st.info("Brak danych do screeningu (NaN / brak etykiet).")  # Brak wyników
            return

        res = res.sort_values(["strength", "n_pos"], ascending=[False, False])  # Sortuj po sile efektu

        st.dataframe(res.head(int(top_n)), width="stretch", hide_index=True)  # Wyświetl top cech

        # insight: zapisujemy cały ranking jako jeden rekord + top1 jako skrót
        top1 = res.iloc[0].to_dict()  # Najlepsza cecha
        _push_insight({
            "signal": fut_col,
            "kind": "feature_screening",
            "compare_mode": mode,
            "top_feature": top1.get("feature"),
            "top_feature_label": top1.get("feature_label"),
            "top_strength": top1.get("strength"),
            "n_features": int(res.shape[0]),
            "top_table": res.head(int(top_n)).to_dict(orient="records"),
        })  # Zapisz insight
        st.success("Zapisano insight do podsumowania.")

        # szybka wizualizacja top cech
        fig = go.Figure()
        show = res.head(int(top_n)).copy()
        fig.add_trace(go.Bar(
            x=[_ui_label(x) for x in show["feature"]],
            y=show["strength"],
            name="strength",
        ))  # Słupki siły efektu
        fig.update_layout(
            height=280,
            margin=dict(l=10, r=10, t=20, b=10),
            xaxis_title="Cecha",
            yaxis_title="Strength (|Δmedian|/std)",
        )
        st.plotly_chart(fig, width="stretch")  # Wyświetl wykres


# Sekcja analizy liftu w koszykach kwantylowych dla pojedynczej cechy
def _render_feature_lift_section(df: pd.DataFrame, fut_col: str) -> None:
    st.subheader("2️⃣ Lift w koszykach (P(+1) | bucket cechy)")  # Nagłówek sekcji

    feature_cols = _numeric_feature_cols(df)  # Lista cech numerycznych
    if not feature_cols:
        st.info("Brak cech numerycznych do analizy.")  # Brak cech do analizy
        return

    c1, c2, c3 = st.columns([4, 2, 2], gap="small")  # Trzy kolumny do wyboru parametrów
    with c1:
        feature = st.selectbox(
            "Cecha",
            options=feature_cols,
            format_func=lambda x: _ui_label(x),
            key="ad2_lift_feature",
        )  # Wybór cechy
    with c2:
        q = st.slider("Liczba koszyków", min_value=5, max_value=20, value=10, step=1, key="ad2_lift_q")  # Liczba koszyków
    with c3:
        direction = st.selectbox("Kierunek", options=["low->high", "high->low"], key="ad2_lift_dir")  # Kierunek bucketów

    if st.button("Policz lift", key="ad2_btn_lift"):
        with st.spinner("Liczenie bucketów..."):
            agg = _lift_by_quantile_buckets(df, fut_col, feature, int(q), direction)  # Licz bucketowanie

        if agg.empty:
            st.info("Brak danych do liftu (NaN / brak etykiet).")  # Brak wyników
            return

        st.dataframe(agg, width="stretch", hide_index=True)  # Wyświetl tabelę bucketów

        # wykres P(+1) oraz lift
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=agg["bucket"].astype(str),
            y=agg["p_pos"],
            mode="lines+markers",
            name="P(+1)",
        ))  # Wykres P(+1)
        fig.add_trace(go.Scatter(
            x=agg["bucket"].astype(str),
            y=agg["lift"],
            mode="lines+markers",
            name="lift vs baseline",
            yaxis="y2",
        ))  # Wykres liftu
        fig.update_layout(
            height=320,
            margin=dict(l=10, r=10, t=20, b=10),
            xaxis_title="Bucket",
            yaxis=dict(title="P(+1)"),
            yaxis2=dict(title="Lift", overlaying="y", side="right"),
        )
        st.plotly_chart(fig, width="stretch")  # Wyświetl wykres

        # insight
        best = agg.sort_values("lift", ascending=False).iloc[0].to_dict()  # Najlepszy bucket
        _push_insight({
            "signal": fut_col,
            "kind": "feature_lift",
            "feature": feature,
            "feature_label": _ui_label(feature),
            "q": int(q),
            "direction": direction,
            "best_bucket": str(best.get("bucket")),
            "best_lift": float(best.get("lift", np.nan)),
            "best_p_pos": float(best.get("p_pos", np.nan)),
        })  # Zapisz insight
        st.success("Zapisano insight do podsumowania.")


# Sekcja analizy interakcji dwóch cech (2D)
def _render_feature_interactions_section(df: pd.DataFrame, fut_col: str) -> None:
    st.subheader("3️⃣ Interakcje cech (2D)")  # Nagłówek sekcji

    feature_cols = _numeric_feature_cols(df)  # Lista cech numerycznych
    if len(feature_cols) < 2:
        st.info("Za mało cech numerycznych do analizy 2D.")  # Potrzeba co najmniej 2 cech
        return

    c1, c2 = st.columns([3, 3], gap="small")  # Dwie kolumny do wyboru cech
    with c1:
        f1 = st.selectbox("Cecha 1", options=feature_cols, format_func=lambda x: _ui_label(x), key="ad2_int_f1")  # Wybór cechy 1
    with c2:
        f2 = st.selectbox("Cecha 2", options=feature_cols, format_func=lambda x: _ui_label(x), key="ad2_int_f2")  # Wybór cechy 2

    c3, c4, c5 = st.columns([2, 2, 2], gap="small")  # Trzy kolumny do wyboru parametrów
    with c3:
        q1 = st.slider("Koszyki cechy 1", 3, 10, 5, 1, key="ad2_int_q1")  # Liczba bucketów cechy 1
    with c4:
        q2 = st.slider("Koszyki cechy 2", 3, 10, 5, 1, key="ad2_int_q2")  # Liczba bucketów cechy 2
    with c5:
        min_n = st.number_input("Min. liczność komórki", min_value=20, max_value=5000, value=200, step=50, key="ad2_int_minn")  # Minimalna liczność

    if st.button("Analizuj interakcję", key="ad2_btn_interaction"):
        if f1 == f2:
            st.warning("Wybierz dwie różne cechy.")  # Nie można wybrać tej samej cechy
            return

        with st.spinner("Liczenie siatki 2D..."):
            grid, baseline = _interaction_grid(df, fut_col, f1, f2, int(q1), int(q2))  # Licz siatkę interakcji

        if grid.empty:
            st.info("Brak danych do interakcji (NaN / brak etykiet).")  # Brak wyników
            return

        grid2 = grid[grid["n"] >= int(min_n)].copy()  # Filtrowanie po minimalnej liczności
        if grid2.empty:
            st.warning("Po filtrze min_n brak komórek. Zmniejsz min_n albo zwiększ koszyki.")  # Brak komórek po filtrze
            st.dataframe(grid.sort_values("lift", ascending=False), width="stretch", hide_index=True)
            return

        st.caption(f"Baseline P(+1): **{baseline*100:.2f}%**" if not np.isnan(baseline) else "Baseline: —")  # Wyświetl baseline
        st.dataframe(grid2.sort_values("lift", ascending=False), width="stretch", hide_index=True)  # Wyświetl tabelę

        # heatmapa liftu
        pvt = grid2.copy()
        pvt["b1"] = pvt["b1"].astype(str)
        pvt["b2"] = pvt["b2"].astype(str)
        hm = pvt.pivot(index="b1", columns="b2", values="lift")  # Pivot do heatmapy

        fig = go.Figure(
            data=go.Heatmap(
                z=hm.values,
                x=list(hm.columns),
                y=list(hm.index),
                colorbar=dict(title="Lift"),
            )
        )  # Tworzenie heatmapy
        fig.update_layout(
            height=360,
            margin=dict(l=10, r=10, t=20, b=10),
            xaxis_title=_ui_label(f2),
            yaxis_title=_ui_label(f1),
        )
        st.plotly_chart(fig, width="stretch")  # Wyświetl heatmapę

        # insight: top komórka
        best = grid2.sort_values("lift", ascending=False).iloc[0].to_dict()  # Najlepsza komórka
        _push_insight({
            "signal": fut_col,
            "kind": "feature_interaction",
            "feature_1": f1,
            "feature_2": f2,
            "feature_1_label": _ui_label(f1),
            "feature_2_label": _ui_label(f2),
            "q1": int(q1),
            "q2": int(q2),
            "min_n": int(min_n),
            "best_b1": str(best.get("b1")),
            "best_b2": str(best.get("b2")),
            "best_lift": float(best.get("lift", np.nan)),
            "best_p_pos": float(best.get("p_pos", np.nan)),
            "best_n": int(best.get("n", 0)),
        })  # Zapisz insight
        st.success("Zapisano insight do podsumowania.")


# Sekcja podsumowania i prezentacji najważniejszych insightów z analiz
def _render_summary_section(fut_col: str) -> None:
    st.subheader("Podsumowanie zależności")  # Nagłówek sekcji

    df_sig = _insights_df()  # Pobierz insighty
    if df_sig.empty:
        st.info("Brak zapisanych insightów. Uruchom wybrane analizy, aby zbudować podsumowanie.")  # Brak insightów
        return

    st.dataframe(df_sig, width="stretch", hide_index=True)  # Wyświetl tabelę insightów

    st.markdown("### Syntetyczne wnioski")  # Nagłówek wniosków

    lines: list[str] = []
    for _, row in df_sig.iterrows():
        if row.get("signal") != fut_col:
            continue  # Tylko dla wybranego sygnału

        kind = row.get("kind")
        if kind == "feature_screening":
            lines.append(
                f"Screening: top cecha **{row.get('top_feature_label', row.get('top_feature'))}** "
                f"(strength ≈ {float(row.get('top_strength', np.nan)):.3f})."
            )  # Wniosek dla screeningu
        elif kind == "feature_lift":
            lines.append(
                f"Lift: cecha **{row.get('feature_label', row.get('feature'))}** "
                f"→ najlepszy bucket lift ≈ {float(row.get('best_lift', np.nan)):.2f} "
                f"(P(+1) ≈ {float(row.get('best_p_pos', np.nan))*100:.2f}%)."
            )  # Wniosek dla liftu
        elif kind == "feature_interaction":
            lines.append(
                f"Interakcja: **{row.get('feature_1_label', row.get('feature_1'))} × {row.get('feature_2_label', row.get('feature_2'))}** "
                f"→ best lift ≈ {float(row.get('best_lift', np.nan)):.2f} (n={int(row.get('best_n', 0))})."
            )  # Wniosek dla interakcji

    if lines:
        for ln in lines:
            st.markdown(f"- {ln}")  # Wyświetl każdy wniosek
    else:
        st.info("Brak wystarczających danych do automatycznego opisu.")  # Brak wniosków

    c1, c2 = st.columns([1, 1], gap="small")  # Dwie kolumny na akcje
    with c1:
        if st.button("Wyczyść insighty", key="ad2_btn_clear_insights"):
            st.session_state[SSK["insights"]] = []  # Wyczyść insighty
            st.success("Wyczyszczono insighty.")
            st.rerun()
    with c2:
        csv = df_sig.to_csv(index=False).encode("utf-8")  # Eksport do CSV
        st.download_button(
            "Pobierz podsumowanie CSV",
            data=csv,
            file_name=f"analysis_v2_summary_{fut_col}.csv",
            mime="text/csv",
            key="ad2_btn_download_summary",
        )  # Przycisk pobierania CSV


# ============================================================
# Render
# ============================================================

# Główna funkcja renderująca całą stronę analizy danych v2 w aplikacji Streamlit
def render() -> None:
    _init_session_defaults()  # Ustaw domyślne wartości sesji

    df_market = st.session_state.get(SSK["df_market_all"])  # Pobierz dane rynkowe
    if not isinstance(df_market, pd.DataFrame) or df_market.empty:
        st.subheader("Analiza danych (v2)")  # Nagłówek sekcji
        st.info(
            "Brak danych do analizy.\n\n"
            "Przejdź na ekran **„Przegląd danych”** i załaduj dane, "
            "dla których chcesz wykonać analizę."
        )  # Komunikat o braku danych
        return

    _render_guard_and_intro()  # Wyświetl nagłówek i opis

    fut_cols = _available_future_cols(df_market)  # Lista dostępnych sygnałów future
    if not fut_cols:
        st.warning("Brak kolumn future (fut_*) w df_market.")  # Brak sygnałów
        return

    colA, colB = st.columns([2, 3], gap="small")  # Dwie kolumny na wybór sygnału i opis
    with colA:
        fut_col = st.selectbox(
            "Analizowany sygnał future (fut_*)",
            options=fut_cols,
            index=fut_cols.index(st.session_state.get(SSK["selected_future"], fut_cols[0]))
            if st.session_state.get(SSK["selected_future"], fut_cols[0]) in fut_cols
            else 0,
            format_func=lambda x: _ui_label(x),
            key=SSK["selected_future"],
            help="Wybór etykiety future steruje wszystkimi analizami (target).",
        )  # Wybór sygnału future
    with colB:
        st.caption(
            "Analizy są niezależne i uruchamiane świadomie przyciskami. "
            "Każdy etap zapisuje 'insight' do podsumowania na końcu."
        )  # Opis UX

    st.divider()

    # 0) Kontekst
    _render_dataset_context(df_market, fut_col)  # Wyświetl kontekst

    st.divider()

    # 1) Screening cech
    _render_feature_screening_section(df_market, fut_col)  # Screening cech

    st.divider()

    # 2) Lift w koszykach (pojedyncza cecha)
    _render_feature_lift_section(df_market, fut_col)  # Analiza liftu

    st.divider()

    # 3) Interakcje 2D
    _render_feature_interactions_section(df_market, fut_col)  # Interakcje cech

    st.divider()

    # 4) Podsumowanie
    _render_summary_section(fut_col)  # Podsumowanie insightów
