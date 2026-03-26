
# Importy wymagane do działania aplikacji
from __future__ import annotations
import itertools  # do generowania kombinacji cech
import io  # do obsługi strumieni tekstowych
import math  # funkcje matematyczne
import numpy as np  # operacje na tablicach i liczbach
import pandas as pd  # obsługa ramek danych
import streamlit as st  # framework do aplikacji webowych
import matplotlib.pyplot as plt  # wykresy
import seaborn as sns  # wykresy statystyczne
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode  # tabele interaktywne
from app.ui.column_metadata import COLUMN_LABELS  # słownik etykiet kolumn


# Ustawienia stylu wykresów (czytelny, prosty styl)
sns.set_theme(style="ticks", context="paper")
plt.rcParams.update({
    "axes.titlesize": 10,  # wielkość tytułu osi
    "axes.labelsize": 9,   # wielkość etykiet osi
    "xtick.labelsize": 8,  # wielkość etykiet na osi X
    "ytick.labelsize": 8,  # wielkość etykiet na osi Y
    "legend.fontsize": 8,  # wielkość legendy
})


# ============================================================
# FIGURE SIZING (PX) – stały rozmiar wykresów w Streamlit
# ============================================================

# Bazowe DPI do przeliczania pikseli na cale. Ujednolicamy rozmiary wykresów w pikselach, żeby układ UI nie „pływał” między zakładkami i środowiskami
BASE_DPI = int(plt.rcParams.get("figure.dpi", 110))
# Stałe rozmiary wykresów w pikselach
FIG_HIST_PX = (528, 198)      # histogram
FIG_SCATTER_PX = (528, 228)   # scatter
FIG_HEATMAP_PX = (330, 228)   # heatmapa
FIG_CORR_PX = (528, 396)      # macierz korelacji
# Funkcja pomocnicza do przeliczania px na cale
def _figsize_from_px(width_px: int, height_px: int) -> tuple[float, float]:
    # Zwraca rozmiar wykresu w calach na podstawie px i DPI
    return (width_px / BASE_DPI, height_px / BASE_DPI)
# Tworzy nową figurę matplotlib o zadanym rozmiarze w px
def new_fig(width_px: int, height_px: int):
    return plt.subplots(figsize=_figsize_from_px(width_px, height_px))

# ============================================================
# SESSION STATE KEYS
# ============================================================
# Słownik kluczy do session_state Streamlit (przechowywanie DataFrame). Kontrakt integracyjny z ekranem „Przegląd danych”: tu wskazujemy jak nazywają się DataFrame’y w session_state
SSK = {
    "df_companies": "do_df_companies",  # spółki
    "df_prices": "do_df_prices_daily",  # ceny dzienne
    "df_ind": "do_df_indicators_daily", # wskaźniki dzienne
    "df_market_all": "do_df_market_all", # cały rynek
}

# Lista kolumn z cenami i wolumenem
PRICE_COLS = ["close", "volume"]



# Funkcja pomocnicza: zwraca ładną etykietę kolumny jeśli istnieje, inaczej nazwę kolumny
def label(col: str) -> str:
    return COLUMN_LABELS.get(col, col)

def _analysis_table_ui(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Zmienia techniczne nazwy kolumn tabel analitycznych na nazwy przyjazne dla użytkownika.

    Ważne:
    - nie modyfikujemy logiki obliczeń,
    - zmieniamy wyłącznie warstwę prezentacji,
    - dzięki temu tabele pozostają stabilne, a nagłówki są zrozumiałe.
    """
    if df_raw is None or df_raw.empty:
        return pd.DataFrame()

    df = df_raw.copy()

    rename_map = {
        "Cecha": "Cecha",
        "Cecha X": "Cecha X",
        "Cecha Y": "Cecha Y",
        "best_bin": "Najlepszy przedział",
        "best_bin_x": "Najlepszy przedział X",
        "best_bin_y": "Najlepszy przedział Y",
        "X_bin": "Przedział cechy X",
        "Y_bin": "Przedział cechy Y",
        "hit_rate_%": "Skuteczność (%)",
        "hit_rate_global_%": "Skuteczność globalna (%)",
        "lift_vs_baseline": "Przewaga vs średnia rynkowa",
        "lift_vs_baseline_xy": "Przewaga vs baseline dla tej pary",
        "liczba_+1": "Liczba sygnałów +1",
        "liczba_obs": "Liczba obserwacji",
    }

    df = df.rename(columns=rename_map)
    return df


# ============================================================
# CACHE / PRECOMPUTE HELPERS
# ============================================================

@st.cache_data(show_spinner=False)
def _compute_signal_occurrences_table(df: pd.DataFrame, signal_col: str) -> tuple[pd.DataFrame, str | None]:
    """
    Przygotowuje tabelę ostatnich wystąpień sygnału +1.
    Funkcja zwraca:
    - gotową tabelę do wyświetlenia,
    - albo komunikat błędu/ostrzeżenia.
    Dzięki cache nie filtrujemy i nie sortujemy od nowa przy każdym rerunie.
    """
    required = {"ticker", "company_name", "trade_date", signal_col}
    missing = [c for c in required if c not in df.columns]
    if missing:
        return pd.DataFrame(), f"Brak kolumn w danych: {missing}"

    close_col = "close_price" if "close_price" in df.columns else "close"
    if close_col not in df.columns:
        return pd.DataFrame(), "Brak kolumny ceny zamknięcia (close_price/close) w danych."

    s = pd.to_numeric(df[signal_col], errors="coerce")
    df_sig = df.loc[s == 1, ["ticker", "company_name", "trade_date", close_col, signal_col]].copy()

    if df_sig.empty:
        return pd.DataFrame(), "Brak wystąpień sygnału +1 dla wybranego sygnału."

    df_sig["trade_date"] = pd.to_datetime(df_sig["trade_date"], errors="coerce")
    df_sig = df_sig.dropna(subset=["trade_date"])
    df_sig = df_sig.sort_values("trade_date", ascending=False)

    df_sig["ticker + company_name"] = (
        df_sig["ticker"].fillna("").astype(str) + " – " + df_sig["company_name"].fillna("").astype(str)
    )

    out = df_sig[["ticker + company_name", "trade_date", close_col, signal_col]].copy()
    out = out.rename(columns=label)
    return out, None


@st.cache_data(show_spinner=False)
def _compute_feature_series_by_signal(df: pd.DataFrame, feature: str, signal_col: str) -> tuple[pd.Series, pd.Series]:
    """
    Zwraca dwie serie liczbowe dla danej cechy:
    - bez sygnału,
    - dla sygnału +1.
    Ten sam zestaw danych jest używany przez histogram, boxplot i mediany,
    więc warto policzyć go raz i współdzielić.
    """
    s = pd.to_numeric(df[signal_col], errors="coerce")
    x = pd.to_numeric(df[feature], errors="coerce")

    x0 = x[s != 1].dropna()
    x1 = x[s == 1].dropna()
    return x0, x1


@st.cache_data(show_spinner=False)
def _compute_scatter_data(
    df: pd.DataFrame,
    xcol: str,
    ycol: str,
    signal_col: str,
    sample_limit: int = 8000,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Przygotowuje dane do scattera osobno dla:
    - Brak sygnału
    - Sygnał +1
    Zwracamy gotowe DataFrame już po dropna i ewentualnym samplowaniu.
    """
    tmp = df[[xcol, ycol, signal_col]].copy()
    tmp[xcol] = pd.to_numeric(tmp[xcol], errors="coerce")
    tmp[ycol] = pd.to_numeric(tmp[ycol], errors="coerce")
    tmp[signal_col] = pd.to_numeric(tmp[signal_col], errors="coerce")
    tmp = tmp.dropna(subset=[xcol, ycol])

    g0 = tmp[tmp[signal_col] != 1][[xcol, ycol]].copy()
    g1 = tmp[tmp[signal_col] == 1][[xcol, ycol]].copy()

    if len(g0) > sample_limit:
        g0 = g0.sample(sample_limit, random_state=42)
    if len(g1) > sample_limit:
        g1 = g1.sample(sample_limit, random_state=42)

    return g0, g1


@st.cache_data(show_spinner=False)
def _compute_pair_hit_heatmap_tables(
    df: pd.DataFrame,
    xcol: str,
    ycol: str,
    signal_col: str,
) -> tuple[pd.DataFrame, pd.DataFrame, float, pd.DataFrame]:
    """
    Przygotowuje wszystkie dane do heatmapy:
    - pivot hit-rate,
    - pivot liczności,
    - baseline dla tej samej próby,
    - tabelę TOP konfiguracji.
    Ciężkie operacje qcut/groupby wykonujemy raz i zapisujemy w cache.
    """
    tmp = df[[xcol, ycol]].copy()
    tmp[xcol] = pd.to_numeric(tmp[xcol], errors="coerce")
    tmp[ycol] = pd.to_numeric(tmp[ycol], errors="coerce")
    tmp = tmp.dropna(subset=[xcol, ycol])

    s = pd.to_numeric(df[signal_col], errors="coerce")
    tmp["is_pos"] = (s.loc[tmp.index] == 1).astype(int)

    baseline_xy = float(tmp["is_pos"].mean()) if len(tmp) else 0.0

    tmp["x_bin"] = pd.qcut(tmp[xcol], 3, labels=["niski", "średni", "wysoki"], duplicates="drop")
    tmp["y_bin"] = pd.qcut(tmp[ycol], 3, labels=["niski", "średni", "wysoki"], duplicates="drop")

    pivot = tmp.pivot_table(index="y_bin", columns="x_bin", values="is_pos", aggfunc="mean")
    count_pivot = tmp.pivot_table(index="y_bin", columns="x_bin", values="is_pos", aggfunc="count")

    rows = []
    for y in pivot.index:
        for x in pivot.columns:
            val = pivot.loc[y, x]
            if pd.notna(val):
                rows.append(
                    {
                        "Cecha X": label(xcol),
                        "Cecha Y": label(ycol),
                        "X_bin": x,
                        "Y_bin": y,
                        "hit_rate_%": round(float(val) * 100, 4),
                        "lift_vs_baseline_xy": round(float(val) / baseline_xy, 2) if baseline_xy > 0 else np.nan,
                    }
                )

    top = (
        pd.DataFrame(rows)
        .sort_values(["lift_vs_baseline_xy", "hit_rate_%"], ascending=False)
        .head(10)
        if rows
        else pd.DataFrame(columns=["Cecha X", "Cecha Y", "X_bin", "Y_bin", "hit_rate_%", "lift_vs_baseline_xy"])
    )

    return pivot, count_pivot, baseline_xy, top


@st.cache_data(show_spinner=False)
def _compute_correlation_matrix(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """
    Liczy macierz korelacji raz dla danej listy cech.
    """
    tmp = df[features].apply(pd.to_numeric, errors="coerce")
    return tmp.corr()

# ============================================================
# SYGNAŁ
# ============================================================
# Zwraca listę kolumn z sygnałami (fut_signal*)
def get_signal_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if isinstance(c, str) and c.startswith("fut_signal")]


# Dzieli ramkę danych na dwie grupy: bez sygnału i z sygnałem +1
def split_by_signal(df: pd.DataFrame, signal_col: str):
    s = pd.to_numeric(df[signal_col], errors="coerce")  # konwersja na liczbowe
    return {
        "Brak sygnału": df[s != 1],  # wiersze bez sygnału
        "Sygnał +1": df[s == 1],    # wiersze z sygnałem +1
    }


# ============================================================
# PODSUMOWANIE GLOBALNE
# ============================================================
# Panel z podsumowaniem statystyk dla wybranego sygnału
def summary_panel(df: pd.DataFrame, signal_col: str):
    s = pd.to_numeric(df[signal_col], errors="coerce")  # konwersja na liczby
    is_pos = s == 1  # maska logiczna dla sygnału +1
    n_all = len(df)  # liczba wszystkich obserwacji
    n_pos = int(is_pos.sum())  # liczba sygnałów +1
    baseline = n_pos / n_all if n_all else 0.0  # udział sygnałów +1
    c1, c2, c3 = st.columns(3)  # trzy kolumny na metryki
    c1.metric("Liczba obserwacji", f"{n_all:,}")  # wyświetl liczbę obserwacji
    c2.metric("Liczba sygnałów +1", f"{n_pos:,}")  # liczba sygnałów +1
    c3.metric("Baseline (+1)", f"{baseline*100:.3f}%")  # procent sygnałów +1
    st.caption(
        """
        Baseline - bezwzględne, rynkowe prawdopodobieństwo (losowa spółka, losowy dzień).\n
        Wszystkie analizy koszykowe i rankingowe odpowiadają na pytanie:\n
        **Czy dane cechy zwiększają tę szansę względem baseline?**\n
        """
    )


# Renderuje tabelę z danymi w stylu podglądu danych (AgGrid)
def render_table_like_data_overview(
    df: pd.DataFrame,
    height: int = 420,
    page_size: int = 10,
):
    if df.empty:
        st.info("Brak danych do wyświetlenia.")  # informacja gdy brak danych
        return
    gb = GridOptionsBuilder.from_dataframe(df)  # budowanie opcji tabeli
    gb.configure_default_column(
        sortable=True,  # sortowanie kolumn
        filter=True,    # filtrowanie
        resizable=True, # zmiana szerokości
    )
    gb.configure_pagination(
        paginationAutoPageSize=False,  # własny rozmiar strony
        paginationPageSize=page_size,  # liczba wierszy na stronę
    )
    gb.configure_grid_options(
        domLayout="normal",  # normalny układ DOM
    )
    grid_options = gb.build()  # finalne opcje
    AgGrid(
        df,
        gridOptions=grid_options,
        height=height,
        theme="balham",   # motyw streamlit
        update_mode=GridUpdateMode.NO_UPDATE,  # brak automatycznych aktualizacji
        fit_columns_on_grid_load=True,  # dopasuj szerokość kolumn
        allow_unsafe_jscode=False,  # nie pozwalaj na JS
    )


# Tabela z ostatnimi wystąpieniami sygnału +1
def signal_occurrences_table(df: pd.DataFrame, signal_col: str):
    """
    Warstwa UI do tabeli ostatnich wystąpień sygnału.
    Cięższe przygotowanie danych zostało wyniesione do funkcji cache.
    """
    st.markdown("#### Sygnały (ostatnie wystąpienia)")

    out, message = _compute_signal_occurrences_table(df, signal_col)

    if message:
        # Pokazujemy warning dla braków kolumn,
        # a info dla zwykłego braku wyników.
        if "Brak kolumn" in message or "Brak kolumny ceny" in message:
            st.warning(message)
        else:
            st.info(message)
        return

    render_table_like_data_overview(
        out,
        height=360,
        page_size=10,
    )



# ============================================================
# ANALIZA EDA – zakładka wstępna (bez selektorów)
# ============================================================

def _binary_class_counts(df: pd.DataFrame, signal_col: str) -> pd.DataFrame:
    s = pd.to_numeric(df[signal_col], errors="coerce")
    out = pd.DataFrame({
        "class": np.where(s == 1, "Sygnał +1", "Brak sygnału"),
    })
    return out["class"].value_counts().rename_axis("class").reset_index(name="n")


def _yearly_counts_two_panels(df: pd.DataFrame, signal_col: str):
    """
    Dwa wykresy: liczba obserwacji per rok, osobno dla Brak sygnału i Sygnał +1.
    """
    if "trade_date" not in df.columns:
        st.warning("Brak kolumny trade_date – pomijam analizę w czasie.")
        return

    tmp = df[["trade_date", signal_col]].copy()
    tmp["trade_date"] = pd.to_datetime(tmp["trade_date"], errors="coerce")
    tmp = tmp.dropna(subset=["trade_date"])

    s = pd.to_numeric(tmp[signal_col], errors="coerce")
    tmp["class"] = np.where(s == 1, "Sygnał +1", "Brak sygnału")
    tmp["year"] = tmp["trade_date"].dt.year.astype(int)

    groups = {
        "Brak sygnału": tmp[tmp["class"] == "Brak sygnału"],
        "Sygnał +1": tmp[tmp["class"] == "Sygnał +1"],
    }

    fig, axes = plt.subplots(1, 2, figsize=_figsize_from_px(*FIG_SCATTER_PX), sharey=True)

    for ax, (name, gdf) in zip(axes, groups.items()):
        yr = gdf.groupby("year").size().reset_index(name="n")
        ax.plot(yr["year"], yr["n"], marker="o")
        ax.set_title(name)
        ax.set_xlabel("Rok")
        ax.set_ylabel("Liczba obserwacji")
        ax.grid(alpha=0.2)

    fig.suptitle("Rozkład wystąpień w czasie (per rok)", y=1.05)
    fig.tight_layout()
    st.pyplot(fig, width="content")
    plt.close(fig)


def _feature_summary_table(df: pd.DataFrame, features: list[str], signal_col: str) -> pd.DataFrame:
    """
    Tabela: mediany i średnie cech dla Brak sygnału vs Sygnał +1.
    Proste i łatwe do walidacji.
    """
    s = pd.to_numeric(df[signal_col], errors="coerce")
    is_pos = (s == 1)

    rows = []
    for f in features:
        x = pd.to_numeric(df[f], errors="coerce")
        x0 = x[~is_pos].dropna()
        x1 = x[is_pos].dropna()

        rows.append({
            "Cecha": label(f),
            "Średnia (Brak sygnału)": float(x0.mean()) if len(x0) else np.nan,
            "Mediana (Brak sygnału)": float(x0.median()) if len(x0) else np.nan,
            "Średnia (Sygnał +1)": float(x1.mean()) if len(x1) else np.nan,
            "Mediana (Sygnał +1)": float(x1.median()) if len(x1) else np.nan,
            "N (Brak sygnału)": int(x0.shape[0]),
            "N (Sygnał +1)": int(x1.shape[0]),
        })

    return pd.DataFrame(rows)


def _missingness_table(df: pd.DataFrame, features: list[str], signal_col: str) -> pd.DataFrame:
    """
    Tabela %NULL: globalnie i warunkowo dla Sygnał +1.
    """
    s = pd.to_numeric(df[signal_col], errors="coerce")
    is_pos = (s == 1)

    rows = []
    n_all = len(df)
    n_pos = int(is_pos.sum())

    for f in features:
        miss_all = pd.to_numeric(df[f], errors="coerce").isna().mean() if n_all else np.nan
        miss_pos = pd.to_numeric(df.loc[is_pos, f], errors="coerce").isna().mean() if n_pos else np.nan
        rows.append({
            "Cecha": label(f),
            "% NULL (całość)": round(float(miss_all) * 100, 3) if pd.notna(miss_all) else np.nan,
            "% NULL (Sygnał +1)": round(float(miss_pos) * 100, 3) if pd.notna(miss_pos) else np.nan,
        })

    return pd.DataFrame(rows)


def render_tab_eda(df: pd.DataFrame, signal_col: str, features_eda: list[str]):
    """
    Zakładka 'Analiza EDA' – bez selektorów.
    Analiza dotyczy sygnału wybranego w selectboxie na górze ekranu.
    """
    st.markdown("### Analiza EDA (globalnie, dla całego rynku)")
    st.caption(
        "Ta zakładka ma charakter sanity-check: sprawdza rozkład sygnału w danych, "
        "jego częstość, stabilność w czasie i podstawowe różnice cech."
    )

    # ============================================================
    # Surowe EDA (pełny df, ALL)
    # ============================================================
    st.markdown("#### Surowe informacje o danych")

    with st.expander("Pokaż surowe informacje o DataFrame", expanded=False):

        st.markdown("**df.columns**")
        st.code(list(df.columns))

        st.markdown("**df.info()**")
        buf = io.StringIO()
        df.info(buf=buf)
        st.text(buf.getvalue())


        st.markdown("**df.sample(50)**")
        st.dataframe(df.sample(50, random_state=42), hide_index=True)

    st.info(
        "- Strukturę danych wejściowych (kolumny, typy, braki).\n"
        "- Analizę EDA, która bazuje na pełnym zbiorze rynkowym (ALL), bez filtrowania spółek."
    )

    # ETAP 0 – kontekst
    st.markdown("#### Etap 0: Kontekst")
    st.markdown(
        f"- Analizowany sygnał: **{label(signal_col)}** (`{signal_col}`)\n"
        f"- Liczba obserwacji w rynku: **{len(df):,}**"
    )
    st.info(
        "- Sygnał jest etykietą historyczną (future label), a nie sygnałem bieżącym.\n"
        "- Sygnał mówi, że w ciągu określonej licby sesji pojawi się sygnał +1 (wzrost).\n"
        "- Do jego wyznaczenia wymagane jest poznanie określonej liczny sesji w przód, dlatego nie jest znany dla ostatnich sesji."
    )

    # ETAP 1 – częstość sygnału (baseline) + osobne panele
    st.markdown("#### Etap 1: Częstość sygnału (baseline)")

    counts = _binary_class_counts(df, signal_col)
    n_all = int(counts["n"].sum())
    n_pos = int(counts.loc[counts["class"] == "Sygnał +1", "n"].sum())
    baseline = (n_pos / n_all) if n_all else 0.0


    fig, axes = plt.subplots(1, 2, figsize=_figsize_from_px(*FIG_SCATTER_PX), sharey=True)

    # Brak sygnału
    n0 = int(counts.loc[counts["class"] == "Brak sygnału", "n"].sum())
    axes[0].bar(["Brak sygnału"], [n0])
    axes[0].set_title("Brak sygnału")
    axes[0].set_ylabel("Liczba obserwacji")
    axes[0].grid(alpha=0.2)


    # Sygnał +1
    axes[1].bar(["Sygnał +1"], [n_pos])
    axes[1].set_title("Sygnał +1")
    axes[1].grid(alpha=0.2)

    fig.suptitle("Liczba obserwacji – osobno dla klas", y=1.05)
    fig.tight_layout()
    st.pyplot(fig, width="content")
    plt.close(fig)

    st.info(
        f"- Sygnał +1 występuje w **{baseline*100:.3f}%** obserwacji.\n"
        "- Sygnał jest rzadki, więc wizualizacje muszą być rozdzielone na klasy."
    )

    # ETAP 2 – czas
    st.markdown("#### Etap 2: Rozkład sygnału w czasie (per rok)")
    _yearly_counts_two_panels(df, signal_col)
    st.info(
        "- Sprawdzamy, czy sygnał pojawia się równomiernie w czasie, czy ma okresy koncentracji.\n"
        "- Jeżeli widać 'piki', możliwy jest wpływ reżimów rynkowych (zmiana charakteru rynku)."
    )

    # ETAP 3 – różnice cech (tabela + histogramy per cecha – już masz rozdzielone panele)
    st.markdown("#### Etap 3: Porównanie cech (Brak sygnału vs Sygnał +1)")
    st.markdown("Poniżej: prosta tabela oraz histogramy (zawsze osobno dla klas).")

    st.dataframe(_feature_summary_table(df, features_eda, signal_col), hide_index=True)

    for f in features_eda:
        st.markdown(f"##### Cecha: {label(f)}")

        st.markdown("**Rozkład (histogram)**")
        hist_two_panels(df, f, signal_col)

        st.markdown("**Wartości odstające (boxplot)**")
        boxplot_two_panels(df, f, signal_col)

        st.markdown("**Mediany (Brak sygnału vs Sygnał +1)**")
        median_two_groups_plot(df, f, signal_col)


    st.info(
        "- Jeżeli rozkłady dla Sygnał +1 są przesunięte względem Brak sygnału, to cecha może nieść informację.\n"
        "- Jeżeli rozkłady są podobne, cecha prawdopodobnie nie rozróżnia sygnału."
    )

    # ETAP 4 – brak danych
    st.markdown("#### Etap 4: Jakość danych (% braków)")
    st.dataframe(_missingness_table(df, features_eda, signal_col), hide_index=True)
    st.info(
        "- Cechy z dużą liczbą brakujących wartości mogą być mniej wiarygodne i wymagać ograniczenia lub specjalnego traktowania w dalszej analizie.\n"
        "- Porównanie braków danych dla Sygnał +1 i całego zbioru pomaga sprawdzić, czy dane dla sygnału nie różnią się jakościowo od reszty rynku."
    )


# ============================================================
# HISTOGRAMY
# ============================================================
def hist_two_panels(df, feature, signal_col):
    """
    Histogram korzysta z wcześniej przygotowanych serii dla obu klas.
    Dzięki temu nie wykonujemy za każdym razem split/filter/to_numeric od nowa.
    """
    x0, x1 = _compute_feature_series_by_signal(df, feature, signal_col)

    groups = {
        "Brak sygnału": x0,
        "Sygnał +1": x1,
    }

    fig, axes = plt.subplots(1, 2, figsize=_figsize_from_px(*FIG_HIST_PX), sharey=True)

    for ax, (name, x) in zip(axes, groups.items()):
        sns.histplot(
            x,
            bins=40,
            kde=True,
            stat="density",
            ax=ax,
            color="#d62728" if name == "Sygnał +1" else "#1f77b4",
        )
        ax.set_title(name)
        ax.set_xlabel(label(feature))
        ax.set_ylabel("Gęstość prawdopodobieństwa")
        ax.grid(alpha=0.2)

    fig.suptitle(f"Rozkład cechy: {label(feature)}", y=1.05)
    fig.tight_layout()
    st.pyplot(fig, width="content")
    plt.close(fig)

# ============================================================
# BOXPLOTY – wartości odstające (osobno dla klas)
# ============================================================
def boxplot_two_panels(df, feature, signal_col):
    """
    Boxplot używa tych samych danych pośrednich co histogram,
    więc nie powtarzamy kosztownego przygotowania serii.
    """
    x0, x1 = _compute_feature_series_by_signal(df, feature, signal_col)

    groups = {
        "Brak sygnału": x0,
        "Sygnał +1": x1,
    }

    fig, axes = plt.subplots(1, 2, figsize=_figsize_from_px(*FIG_HIST_PX), sharey=True)

    for ax, (name, x) in zip(axes, groups.items()):
        sns.boxplot(
            x=x,
            ax=ax,
            color="#d62728" if name == "Sygnał +1" else "#1f77b4",
            fliersize=3,
            linewidth=1,
        )
        ax.set_title(name)
        ax.set_xlabel(label(feature))
        ax.grid(alpha=0.2)

    fig.suptitle(f"Wartości odstające (boxplot): {label(feature)}", y=1.05)
    fig.tight_layout()
    st.pyplot(fig, width="content")
    plt.close(fig)

# ============================================================
# MEDIANY – porównanie klas (Brak sygnału vs Sygnał +1)
# ============================================================
def median_two_groups_plot(df, feature, signal_col):
    """
    Porównanie median korzysta z tych samych serii co histogram i boxplot.
    """
    x0, x1 = _compute_feature_series_by_signal(df, feature, signal_col)

    names = ["Brak sygnału", "Sygnał +1"]
    meds = [
        float(x0.median()) if len(x0) else np.nan,
        float(x1.median()) if len(x1) else np.nan,
    ]
    ns = [int(x0.shape[0]), int(x1.shape[0])]

    fig, ax = plt.subplots(figsize=_figsize_from_px(*FIG_HIST_PX))
    ax.bar(names, meds)

    for i, (v, n) in enumerate(zip(meds, ns)):
        if pd.notna(v):
            ax.text(i, v, f"{v:.4g}\n(n={n})", ha="center", va="bottom", fontsize=8)

    ax.set_title(f"Mediany cechy: {label(feature)}")
    ax.set_ylabel("Mediana")
    ax.grid(alpha=0.2, axis="y")

    fig.tight_layout()
    st.pyplot(fig, width="content")
    plt.close(fig)
    
# ============================================================
# SCATTER
# ============================================================
def scatter_two_panels(df, xcol, ycol, signal_col):
    """
    Scatter używa przygotowanych wcześniej danych dla obu klas.
    """
    g0, g1 = _compute_scatter_data(df, xcol, ycol, signal_col)

    groups = {
        "Brak sygnału": g0,
        "Sygnał +1": g1,
    }

    fig, axes = plt.subplots(1, 2, figsize=_figsize_from_px(*FIG_SCATTER_PX), sharex=True, sharey=True)

    for ax, (name, tmp) in zip(axes, groups.items()):
        ax.scatter(
            tmp[xcol],
            tmp[ycol],
            s=15,
            alpha=0.35,
            color="#d62728" if name == "Sygnał +1" else "#1f77b4",
        )
        ax.set_title(name)
        ax.set_xlabel(label(xcol))
        ax.set_ylabel(label(ycol))
        ax.grid(alpha=0.2)

    for ax in axes:
        ax.yaxis.set_tick_params(labelleft=True)

    fig.suptitle(f"{label(xcol)} vs {label(ycol)}", y=1.05)
    fig.tight_layout()
    st.pyplot(fig, width="content")
    plt.close(fig)


# ============================================================
# HIT-RATE WARUNKOWY (KOSZYKI)
# ============================================================
def pair_hit_heatmap(df, xcol, ycol, signal_col):
    """
    Warstwa renderująca heatmapę i tabelę TOP.
    Ciężkie obliczenia są wykonywane w funkcji cache.
    """
    pivot, count_pivot, baseline_xy, top = _compute_pair_hit_heatmap_tables(df, xcol, ycol, signal_col)

    if pivot.empty:
        st.info("Brak danych do policzenia heatmapy dla wybranej pary cech.")
        return

    fig, ax = plt.subplots(figsize=_figsize_from_px(*FIG_HEATMAP_PX))
    sns.heatmap(pivot * 100, annot=True, fmt=".2f", cmap="rocket", ax=ax)
    ax.set_title("Hit-rate warunkowy – P(+1 | koszyk X, koszyk Y)")
    ax.set_xlabel(label(xcol))
    ax.set_ylabel(label(ycol))
    fig.tight_layout()
    st.pyplot(fig, width="content")
    plt.close(fig)

    st.caption(
        f"Baseline dla tej heatmapy (warunkowo na X,Y != NULL): **{baseline_xy*100:.4f}%** "
        "(to jest właściwy punkt odniesienia dla koszyków)."
    )

    # Dodatkowo pokazujemy liczności w każdej komórce,
    # bo wysoki wynik przy bardzo małej próbie może być mylący.
    st.markdown("**Liczba obserwacji w komórkach koszyków:**")
    # width='content' odpowiada dawnemu use_container_width=False
    st.dataframe(count_pivot, width="content")

    st.markdown("**Top konfiguracje (dla tej pary cech):**")
    top_ui = _analysis_table_ui(top)
    st.dataframe(top_ui, hide_index=True)



# ============================================================
# RANKING CECH – po NAJLEPSZYM KOSZYKU (ma sens dla cech nie-NULL)
# ============================================================

def ranking_hit_rate_single(
    df: pd.DataFrame,
    features: list[str],
    signal_col: str,
    q: int = 5,
    min_obs: int = 300,
) -> pd.DataFrame:
    # Ranking 1D: dla każdej cechy dzielimy ją na kwantyle (q),
    # wybieramy najlepszy koszyk (lift vs baseline) i rankujemy cechy po tym wyniku.
    s = (pd.to_numeric(df[signal_col], errors="coerce") == 1).astype(int)  # maska sygnału +1
    baseline = float(s.mean()) if len(s) else 0.0  # bazowy hit-rate

    rows = []  # lista wyników
    for f in features:
        x = pd.to_numeric(df[f], errors="coerce")  # konwersja cechy na liczby
        tmp = pd.DataFrame({"x": x, "is_pos": s}).dropna()  # tylko kompletne wiersze
        if len(tmp) < max(min_obs, q * 50):  # za mało danych do stabilnej analizy
            continue

        try:
            tmp["bin"] = pd.qcut(tmp["x"], q, labels=False, duplicates="drop")  # podział na kwantyle
        except Exception:
            continue  # nie udało się podzielić na kwantyle

        grp = tmp.groupby("bin")["is_pos"].agg(["count", "sum", "mean"]).reset_index()  # agregacja po koszykach
        grp = grp.rename(columns={"count": "n_obs", "sum": "n_pos", "mean": "hit_rate"})  # zmiana nazw kolumn
        grp = grp[grp["n_obs"] >= min_obs]  # tylko koszyki z wystarczającą liczbą obserwacji
        if grp.empty:
            continue  # pomiń jeśli nie ma stabilnych koszyków

        grp["lift"] = grp["hit_rate"] / baseline if baseline > 0 else np.nan  # wylicz lift względem baseline
        best = grp.sort_values(["lift", "n_pos", "n_obs"], ascending=False).iloc[0]  # wybierz najlepszy koszyk

        rows.append({
            "Cecha": label(f),  # nazwa cechy
            "best_bin": int(best["bin"]),  # numer najlepszego koszyka
            "hit_rate_%": round(float(best["hit_rate"]) * 100, 4),  # hit-rate w tym koszyku
            "lift_vs_baseline": round(float(best["lift"]), 3) if pd.notna(best["lift"]) else np.nan,  # lift
            "liczba_+1": int(best["n_pos"]),  # liczba sygnałów +1
            "liczba_obs": int(best["n_obs"]),  # liczba obserwacji w koszyku
        })  # dodaj wynik do listy

    if not rows:
        # Zwróć pustą ramkę jeśli nie ma wyników
        return pd.DataFrame(columns=["Cecha", "best_bin", "hit_rate_%", "lift_vs_baseline", "liczba_+1", "liczba_obs"])

    # Zwróć posortowaną tabelę top 10 cech
    return (
        pd.DataFrame(rows)
        .sort_values(["lift_vs_baseline", "hit_rate_%", "liczba_+1", "liczba_obs"], ascending=False)
        .head(10)
    )


@st.cache_data(show_spinner=False)
def ranking_hit_rate_pairs(
    df: pd.DataFrame,
    features: list[str],
    signal_col: str,
    q: int = 3,
    min_obs: int = 300,
) -> pd.DataFrame:
    """
    Ranking 2D: dla każdej pary cech robimy siatkę q×q na kwantylach
    i wybieramy najlepszą komórkę (lift vs baseline).
    """
    s = (pd.to_numeric(df[signal_col], errors="coerce") == 1).astype(int)
    baseline = float(s.mean()) if len(s) else 0.0

    rows = []
    for f1, f2 in itertools.combinations(features, 2):
        x1 = pd.to_numeric(df[f1], errors="coerce")
        x2 = pd.to_numeric(df[f2], errors="coerce")

        tmp = pd.DataFrame({"x1": x1, "x2": x2, "is_pos": s}).dropna()
        if len(tmp) < max(min_obs, q * q * 50):
            continue

        try:
            tmp["b1"] = pd.qcut(tmp["x1"], q, labels=False, duplicates="drop")
            tmp["b2"] = pd.qcut(tmp["x2"], q, labels=False, duplicates="drop")
        except Exception:
            continue

        grp = tmp.groupby(["b1", "b2"])["is_pos"].agg(["count", "sum", "mean"]).reset_index()
        grp = grp.rename(columns={"count": "n_obs", "sum": "n_pos", "mean": "hit_rate"})
        grp = grp[grp["n_obs"] >= min_obs]
        if grp.empty:
            continue

        grp["lift"] = grp["hit_rate"] / baseline if baseline > 0 else np.nan
        best = grp.sort_values(["lift", "n_pos", "n_obs"], ascending=False).iloc[0]

        rows.append({
            "Cecha X": label(f1),
            "Cecha Y": label(f2),
            "best_bin_x": int(best["b1"]),
            "best_bin_y": int(best["b2"]),
            "hit_rate_%": round(float(best["hit_rate"]) * 100, 4),
            "lift_vs_baseline": round(float(best["lift"]), 3) if pd.notna(best["lift"]) else np.nan,
            "liczba_+1": int(best["n_pos"]),
            "liczba_obs": int(best["n_obs"]),
        })

    if not rows:
        return pd.DataFrame(columns=["Cecha X", "Cecha Y", "best_bin_x", "best_bin_y", "hit_rate_%", "lift_vs_baseline", "liczba_+1", "liczba_obs"])

    return (
        pd.DataFrame(rows)
        .sort_values(["lift_vs_baseline", "hit_rate_%", "liczba_+1", "liczba_obs"], ascending=False)
        .head(10)
    )


# ============================================================
# HIT-RATE GLOBALNY – STARA WERSJA (ALE ZNACZĄCA)
# Global = P(+1 AND najlepszy koszyk) = n_pos_w_koszyku / n_all
# ============================================================

def global_hit_rate_single(
    df: pd.DataFrame,
    features: list[str],
    signal_col: str,
    q: int = 5,
    min_obs: int = 300,
) -> pd.DataFrame:
    s = (pd.to_numeric(df[signal_col], errors="coerce") == 1).astype(int)
    n_all = int(len(df))
    baseline = float(s.mean()) if n_all else 0.0

    rows = []
    for f in features:
        x = pd.to_numeric(df[f], errors="coerce")
        tmp = pd.DataFrame({"x": x, "is_pos": s}).dropna()
        if len(tmp) < max(min_obs, q * 50):
            continue

        try:
            tmp["bin"] = pd.qcut(tmp["x"], q, labels=False, duplicates="drop")
        except Exception:
            continue

        grp = tmp.groupby("bin")["is_pos"].agg(["count", "sum", "mean"]).reset_index()
        grp = grp.rename(columns={"count": "n_obs", "sum": "n_pos", "mean": "hit_rate"})
        grp = grp[grp["n_obs"] >= min_obs]
        if grp.empty:
            continue

        grp["lift"] = grp["hit_rate"] / baseline if baseline > 0 else np.nan
        best = grp.sort_values(["lift", "n_pos", "n_obs"], ascending=False).iloc[0]

        n_pos = int(best["n_pos"])
        rate_global = (n_pos / n_all) if n_all else 0.0

        rows.append({
            "Cecha": label(f),
            "best_bin": int(best["bin"]),
            "hit_rate_global_%": round(rate_global * 100, 4),
            "liczba_+1": n_pos,
            "liczba_obs": int(best["n_obs"]),
        })

    if not rows:
        return pd.DataFrame(columns=["Cecha", "best_bin", "hit_rate_global_%", "liczba_+1", "liczba_obs"])

    return (
        pd.DataFrame(rows)
        .sort_values(["hit_rate_global_%", "liczba_+1", "liczba_obs"], ascending=False)
        .head(10)
    )


@st.cache_data(show_spinner=False)
def global_hit_rate_pairs(
    df: pd.DataFrame,
    features: list[str],
    signal_col: str,
    q: int = 3,
    min_obs: int = 300,
) -> pd.DataFrame:
    s = (pd.to_numeric(df[signal_col], errors="coerce") == 1).astype(int)
    n_all = int(len(df))
    baseline = float(s.mean()) if n_all else 0.0

    rows = []
    for f1, f2 in itertools.combinations(features, 2):
        x1 = pd.to_numeric(df[f1], errors="coerce")
        x2 = pd.to_numeric(df[f2], errors="coerce")

        tmp = pd.DataFrame({"x1": x1, "x2": x2, "is_pos": s}).dropna()
        if len(tmp) < max(min_obs, q * q * 50):
            continue

        try:
            tmp["b1"] = pd.qcut(tmp["x1"], q, labels=False, duplicates="drop")
            tmp["b2"] = pd.qcut(tmp["x2"], q, labels=False, duplicates="drop")
        except Exception:
            continue

        grp = tmp.groupby(["b1", "b2"])["is_pos"].agg(["count", "sum", "mean"]).reset_index()
        grp = grp.rename(columns={"count": "n_obs", "sum": "n_pos", "mean": "hit_rate"})
        grp = grp[grp["n_obs"] >= min_obs]
        if grp.empty:
            continue

        grp["lift"] = grp["hit_rate"] / baseline if baseline > 0 else np.nan
        best = grp.sort_values(["lift", "n_pos", "n_obs"], ascending=False).iloc[0]

        n_pos = int(best["n_pos"])
        rate_global = (n_pos / n_all) if n_all else 0.0

        rows.append({
            "Cecha X": label(f1),
            "Cecha Y": label(f2),
            "best_bin_x": int(best["b1"]),
            "best_bin_y": int(best["b2"]),
            "hit_rate_global_%": round(rate_global * 100, 4),
            "liczba_+1": n_pos,
            "liczba_obs": int(best["n_obs"]),
        })

    if not rows:
        return pd.DataFrame(columns=["Cecha X", "Cecha Y", "best_bin_x", "best_bin_y", "hit_rate_global_%", "liczba_+1", "liczba_obs"])

    return (
        pd.DataFrame(rows)
        .sort_values(["hit_rate_global_%", "liczba_+1", "liczba_obs"], ascending=False)
        .head(10)
    )


# ============================================================
# KORELACJE CECH
# ============================================================
def correlation_heatmap(df: pd.DataFrame, features: list[str]):
    """
    Renderuje macierz korelacji obliczoną wcześniej w cache.
    """
    corr = _compute_correlation_matrix(df, features)

    xlabels = [label(c) for c in corr.columns]
    ylabels = [label(c) for c in corr.index]

    fig, ax = plt.subplots(figsize=_figsize_from_px(*FIG_CORR_PX))
    sns.heatmap(
        corr,
        cmap="coolwarm",
        center=0,
        linewidths=0.5,
        cbar_kws={"label": "Korelacja"},
        xticklabels=xlabels,
        yticklabels=ylabels,
        ax=ax,
    )

    ax.set_title("Macierz korelacji cech")
    ax.tick_params(axis="x", labelrotation=45)
    ax.tick_params(axis="y", labelrotation=0)

    fig.tight_layout()
    st.pyplot(fig, width="content")
    plt.close(fig)


# ============================================================
# MAIN – ZMIENIONY UKŁAD ZAKŁADEK
# ============================================================
def render():
    st.subheader("Analiza – globalna analiza EDA rynku")

    # Na starcie nie tworzymy jeszcze placeholdera w UI.
    # Gdybyśmy zrobili st.empty() tutaj, komunikat i tak pojawiłby się
    # w górnej części ekranu, bo Streamlit zapamiętuje miejsce utworzenia placeholdera.
    global_status = None

    try:

        # Główny opis ekranu.
        # Tekst prowadzi użytkownika przez logikę pracy:
        # wybór sygnału -> zrozumienie jego charakteru -> przygotowanie do ML.
        st.info(
            "Ten ekran służy do analizy wybranego sygnału rynkowego, np. **Sygnału 20 D**, "
            "na podstawie danych historycznych z całego rynku.\n\n"
            "Najpierw wybierasz sygnał, a następnie sprawdzasz, jak często występował, "
            "w jakich warunkach rynkowych się pojawiał oraz które wskaźniki mogły mu towarzyszyć.\n\n"
            "Celem tej analizy nie jest wygenerowanie gotowej decyzji inwestycyjnej, "
            "lecz lepsze zrozumienie sygnału i przygotowanie wiedzy potrzebnej "
            "do dalszych testów w module **Machine Learning**.\n\n"
            "Jeżeli chcesz zobaczyć, jak dany sygnał wygląda na wykresie konkretnej spółki, "
            "wybierz firmę z tabeli **Sygnały (ostatnie wystąpienia)**, a następnie przejdź "
            "na ekran **Przegląd danych** i zaznacz ten sam sygnał na wykresie."
        )

        df = st.session_state.get(SSK["df_market_all"])

        if not isinstance(df, pd.DataFrame) or df.empty:
            st.info(
                "Brak danych do analizy.\n\n"
                "Przejdź na ekran **„Przegląd danych”** i załaduj dane, "
                "dla których chcesz wykonać analizę."
            )
            return


        if df.empty:
            st.warning("Najpierw załaduj dane w 'Przegląd danych'")
            return


        signal_cols = get_signal_cols(df)
        if not signal_cols:
            st.warning("Brak kolumn fut_signal* w danych.")
            return

        # domyślny sygnał: fut_signal_20 (jeśli istnieje)
        default_signal = "fut_signal_20"
        default_index = signal_cols.index(default_signal) if default_signal in signal_cols else 0




        top_left, top_right = st.columns([2, 3])

        with top_left:

            signal_col = st.selectbox(
                "Wybierz sygnał",
                signal_cols,
                index=default_index,
                format_func=label,
            )

            # Jeżeli użytkownik zmienił analizowany sygnał,
            # czyścimy wyniki kosztownych sekcji i zapisane wybory z formularzy.
            # Dzięki temu nie pokazujemy "starych" wyników dla poprzedniego sygnału.
            prev_signal = st.session_state.get("analysis_prev_signal")
            if prev_signal != signal_col:
                st.session_state["analysis_prev_signal"] = signal_col

                # Reset wyników sekcji uruchamianych przyciskiem
                st.session_state["run_ranking_pairs"] = False
                st.session_state["run_global_pairs"] = False
                st.session_state["run_corr_matrix"] = False

                # Reset zapamiętanych wyborów z formularzy
                st.session_state.pop("tab1_feature_selected", None)
                st.session_state.pop("tab2_pair_selected", None)
                st.session_state.pop("tab3_pair_selected", None)

            summary_panel(df, signal_col)

            with st.expander("Opis sygnałów wybieranych do analizy", expanded=False):
                st.markdown("""
### Czym są sygnały dostępne w tym widoku?

Sygnały na tym ekranie są **etykietami historycznymi**.  
To znaczy, że opisują to, co wydarzyło się później po danym dniu w przeszłości.

W praktyce oznacza to, że:

- nie są to bieżące rekomendacje inwestycyjne,
- nie służą do podejmowania decyzji „tu i teraz”,
- pomagają zrozumieć, jakie warunki rynkowe historycznie towarzyszyły wzrostom lub spadkom.

Na tym ekranie analizujemy przede wszystkim przypadki z wartością **+1**,
czyli sytuacje, w których po danym dniu pojawił się ruch wzrostowy
zgodny z definicją wybranego sygnału.

---

### Krótkie znaczenie poszczególnych sygnałów

#### Sygnał 2 D
Krótki, bardzo dynamiczny sygnał.
Pokazuje, czy w ciągu najbliższych 2 sesji pojawił się szybki i wyraźny ruch ceny.

**Najlepiej sprawdza się do analizy:**
- gwałtownych impulsów,
- nagłej zmienności,
- krótkoterminowych wybic.

---

#### Sygnał 20 D
Sygnał krótkiego / średniego horyzontu.
Pomaga ocenić, czy kierunek rynku utrzymał się w kolejnych 20 sesjach.

**Najlepiej sprawdza się do analizy:**
- stabilności trendu,
- jakości krótszego ruchu wzrostowego,
- zależności między sygnałem a podstawowymi wskaźnikami technicznymi.

---

#### Sygnał 60 D
Sygnał średnioterminowy.
Pokazuje, czy ruch utrzymał się przez dłuższy okres i nie był tylko krótkim odbiciem.

**Najlepiej sprawdza się do analizy:**
- jakości trendu,
- trwałości ruchu,
- wpływu zmienności i momentum.

---

#### Sygnał 120 D
Sygnał długoterminowy.
Opisuje bardziej trwały kierunek rynku i mniej reaguje na krótkie wahania.

**Najlepiej sprawdza się do analizy:**
- długiego trendu,
- reżimu rynku,
- stabilności zachowania spółek w czasie.

---

#### Sygnał 20 D (hyb.)
To bardziej selektywny wariant sygnału 20 D.
Wskazuje raczej na **nowy jakościowy impuls** niż na zwykłą kontynuację trendu.

**Najlepiej sprawdza się do analizy:**
- momentów wejścia,
- mocniejszych setupów,
- cech, które mogą być szczególnie przydatne później w ML.

---

### Ważna zasada interpretacji

Na tym ekranie analizujesz **wiedzę historyczną**, a nie gotowy sygnał decyzyjny.

Pytanie, na które odpowiada ta analiza, brzmi:

**„Jakie cechy rynku historycznie towarzyszyły sytuacjom, po których pojawiał się dany sygnał?”**
                """.strip())


            with st.expander("Co zawiera ta analiza EDA?", expanded=False):
                st.markdown("""
Ta sekcja pokazuje **globalną analizę historyczną wybranego sygnału** dla całego rynku.

Znajdziesz tu m.in.:

- jak często dany sygnał występuje,
- czy jego częstość zmienia się w czasie,
- czym różnią się przypadki **bez sygnału** i **z sygnałem +1**,
- które cechy i kombinacje cech mogą częściej towarzyszyć badanemu sygnałowi.

Traktuj tę sekcję jako etap poznania sygnału przed dalszymi testami
w bardziej szczegółowych zakładkach i w module **Machine Learning**.
                """.strip())



        with top_right:
            signal_occurrences_table(df, signal_col)



        usable_features = [c for c in [
            "mv","pb","pe","earnings_yield",
            "momentum_12m","volatility_20d","sharpe_20d","max_drawdown_252d",
            "sma_20","sma_50","sma_200",
            "ema_12","ema_20","ema_26","ema_50","ema_200",
            "rsi_14","macd_line","macd_signal","macd_hist",
            "volume","average_volume_20d","obv","vwap_20d","atr_14",
            "tqs_60d",
        ] if c in df.columns]

        # Placeholder tworzymy dopiero tutaj,
        # czyli dokładnie pomiędzy górną sekcją (metryki + tabela)
        # a listą zakładek. Dzięki temu komunikat pojawi się
        # w dolnej części wspólnego obszaru ekranu.
        global_status = st.empty()

        # Komunikat o przeliczaniu wszystkich zakładek.
        global_status.markdown(
            "<p style='color:#ff6b6b; font-weight:600; margin: 8px 0 10px 0;'>"
            "Trwa przeliczanie wszystkich zakładek. Może potrwać kilka minut"
            "</p>",
            unsafe_allow_html=True,
        )

        tab0, tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "Analiza EDA",
            "Rozkład cechy",
            "Para cech (scatter)",
            "Para cech → hit-rate (koszyki)",
            "Ranking cech (tabele)",
            "Hit-rate globalny (poprzednia wersja)",
            "Korelacje cech",
        ])

        # EDA używa dokładnie tych samych cech co zakładka „Rozkład cechy”
        features_eda = usable_features


        with tab0:
            st.markdown("### Analiza EDA (globalnie, dla całego rynku)")

            show_all = st.checkbox(
                "Pokaż wszystkie cechy (pełna analiza EDA – wolne)",
                value=False,
                help="Wyświetla pełną analizę EDA dla wszystkich cech. "
                    "Może znacząco wydłużyć czas generowania."
            )

            if show_all:
                render_tab_eda(df, signal_col, features_eda)
            else:
                st.info(
                    "Pełna analiza EDA jest wyłączona.\n\n"
                    "Aby przyspieszyć działanie aplikacji:\n"
                    "- korzystaj z zakładek **Rozkład cechy**, **Para cech**, **Koszyki**, **Rankingi**,\n"
                    "- włącz EDA tylko wtedy, gdy chcesz wykonać pełny sanity-check rynku."
                )
               


        with tab1:
            with st.expander("Rozwiń aby poznać dokładny opis", expanded=False):
                st.markdown(
                    """
                    **Co widzisz?**  
                    Porównanie tej samej cechy w dwóch grupach:
                    - dni bez sygnału,
                    - dni z **sygnałem +1**.

                    **Jak to czytać?**  
                    - jeśli oba rozkłady są podobne, cecha raczej słabo odróżnia sygnał,
                    - jeśli dla **Sygnału +1** rozkład wygląda inaczej, cecha może być istotna,
                    - boxplot pomaga dodatkowo zobaczyć zakres wartości i obserwacje odstające.

                    **Ważne:**  
                    To jest analiza opisowa. Pokazuje zależności historyczne,
                    ale sama w sobie nie potwierdza jeszcze wartości predykcyjnej cechy.
                    """
                )

            # Formularz ogranicza liczbę rerunów:
            # użytkownik może wybrać cechę i dopiero kliknięciem uruchamia obliczenia.
            with st.form("tab1_feature_form"):
                feature = st.selectbox(
                    "Cecha",
                    options=[None] + usable_features,
                    format_func=lambda x: "Wybierz cechę…" if x is None else label(x),
                    key="tab1_feature_select",
                )
                run_tab1 = st.form_submit_button("Pokaż rozkład cechy")

            if run_tab1 and feature is None:
                st.info("Wybierz cechę, aby zobaczyć rozkład i boxplot.")
            elif run_tab1:
                st.session_state["tab1_feature_selected"] = feature

            feature_to_show = st.session_state.get("tab1_feature_selected")

            if feature_to_show:
                st.markdown("#### Rozkład (histogram)")
                hist_two_panels(df, feature_to_show, signal_col)

                st.markdown("#### Wartości odstające (boxplot)")
                boxplot_two_panels(df, feature_to_show, signal_col)
            else:
                st.info("Wybierz cechę i kliknij przycisk, aby zobaczyć rozkład i boxplot.")



        with tab2:
            with st.expander("Rozwiń aby poznać dokładny opis", expanded=False):
                st.markdown(
                    """
                    **Co widzisz?**  
                    Dwa wykresy punktowe dla tej samej pary cech:
                    - osobno dla dni bez sygnału,
                    - osobno dla dni z **sygnałem +1**.

                    **Jak to czytać?**  
                    - szukaj obszarów, w których punkty dla **Sygnału +1** pojawiają się częściej,
                    - jeśli układ punktów wygląda podobnie w obu grupach, para cech może być mało użyteczna,
                    - jeśli dla sygnału widać wyraźniejsze skupienie lub inny układ, warto badać tę parę dalej.

                    **Uwaga:**  
                    Ten wykres pomaga zobaczyć zależność wizualnie.
                    Dokładniejsze porównanie ilościowe znajdziesz w kolejnych zakładkach.
                    """
                )

            with st.form("tab2_pair_form"):
                x = st.selectbox(
                    "Cecha X",
                    options=[None] + usable_features,
                    format_func=lambda v: "Wybierz cechę X…" if v is None else label(v),
                    key="tab2_x_select",
                )

                y = st.selectbox(
                    "Cecha Y",
                    options=[None] + usable_features,
                    format_func=lambda v: "Wybierz cechę Y…" if v is None else label(v),
                    key="tab2_y_select",
                )

                run_tab2 = st.form_submit_button("Pokaż porównanie cech")

            if run_tab2:
                if x is None or y is None:
                    st.info("Wybierz dwie cechy, aby zobaczyć zależność.")
                elif x == y:
                    st.warning("Wybierz dwie różne cechy.")
                else:
                    st.session_state["tab2_pair_selected"] = (x, y)

            pair_to_show = st.session_state.get("tab2_pair_selected")

            if pair_to_show:
                x_show, y_show = pair_to_show

                st.markdown("#### Zależność X vs Y (scatter)")
                scatter_two_panels(df, x_show, y_show, signal_col)

                st.markdown("#### Rozkład cechy X (boxplot)")
                boxplot_two_panels(df, x_show, signal_col)

                st.markdown("#### Rozkład cechy Y (boxplot)")
                boxplot_two_panels(df, y_show, signal_col)
            else:
                st.info("Wybierz dwie cechy i kliknij przycisk, aby zobaczyć zależność.")




        # --- TAB3: Para cech → hit-rate (koszyki) ---
        with tab3:
            with st.expander("Rozwiń aby poznać dokładny opis", expanded=False):
                st.markdown(
                    """
                    **Co widzisz?**  
                    Mapę 3×3, w której obie cechy są podzielone na trzy poziomy:
                    **niski / średni / wysoki**.

                    Każda komórka pokazuje, jak często w takich warunkach pojawiał się **sygnał +1**.

                    **Jak to czytać?**  
                    - szukaj komórek z wynikiem wyższym niż średnia dla całego rynku,
                    - jeśli komórka ma wysoki wynik i jednocześnie sensowną liczbę obserwacji,
                      może wskazywać interesującą konfigurację do dalszej analizy,
                    - w tabeli pod wykresem zwracaj uwagę szczególnie na kolumny
                      **Przedział cechy X**, **Przedział cechy Y**, **Skuteczność (%)**
                      oraz **Przewaga vs baseline dla tej pary**,
                    - to dobry krok przejściowy między prostą obserwacją danych a budową cech do ML.
                    
                    **Uwaga:**  
                    Bardzo małe grupy mogą dawać przypadkowo zawyżone wyniki,
                    dlatego później warto patrzeć także na rankingi i liczność obserwacji.
                    """
                )

            default_y = "momentum_12m"
            default_y_index = (
                usable_features.index(default_y) + 1
                if default_y in usable_features
                else 0
            )

            with st.form("tab3_heatmap_form"):
                x = st.selectbox(
                    "Cecha X (koszyki)",
                    options=[None] + usable_features,
                    key="hx_form",
                    format_func=lambda v: "Wybierz cechę X…" if v is None else label(v),
                )

                y = st.selectbox(
                    "Cecha Y (koszyki)",
                    options=[None] + usable_features,
                    index=default_y_index,
                    key="hy_form",
                    format_func=lambda v: "Wybierz cechę Y…" if v is None else label(v),
                )

                run_tab3 = st.form_submit_button("Policz hit-rate dla pary cech")

            if run_tab3:
                if x is None or y is None:
                    st.info("Wybierz dwie cechy, aby policzyć hit-rate.")
                elif x == y:
                    st.warning("Wybierz dwie różne cechy.")
                else:
                    st.session_state["tab3_pair_selected"] = (x, y)

            pair_to_show = st.session_state.get("tab3_pair_selected")

            if pair_to_show:
                x_show, y_show = pair_to_show
                pair_hit_heatmap(df, x_show, y_show, signal_col)
            else:
                st.info("Wybierz dwie cechy i kliknij przycisk, aby policzyć hit-rate.")




        with tab4:
            with st.expander("Rozwiń aby poznać dokładny opis", expanded=False):
                st.markdown(
                    """
                    **Co widzisz?**  
                    Tabelę cech i par cech, które w wybranych zakresach wartości
                    najczęściej towarzyszyły **sygnałowi +1**.

                    **Jak to działa?**  
                    - wartości cech są dzielone na przedziały,
                    - dla każdego przedziału liczony jest udział przypadków z **sygnałem +1**,
                    - do tabeli trafiają najlepsze wyniki.

                    **Najważniejsze kolumny:**  
                    - **Skuteczność (%)** – jak często w danym przedziale pojawiał się sygnał,
                    - **Przewaga vs średnia rynkowa** – jak bardzo wynik jest lepszy od średniej rynkowej,
                    - **Liczba obserwacji** – ile obserwacji stoi za wynikiem,
                    - **Najlepszy przedział X / Y** – który zakres wartości dla danej cechy dawał najlepszy wynik.

                    **Jak to czytać?**  
                    Szukaj cech z wyższym wynikiem i jednocześnie odpowiednio dużą liczbą obserwacji.
                    To są dobrzy kandydaci do dalszej analizy i późniejszych testów w ML.
                    """
                )

            # Przyciski sterujące ciężką sekcją:
            # jeden liczy wynik, drugi ukrywa go i zapobiega dalszemu renderowaniu.
            col_run, col_clear = st.columns(2)

            with col_run:
                if st.button(
                    "Policz ranking cech",
                    key="run_ranking_pairs_btn",
                    help="Oblicza ranking cech i par cech na podstawie najlepszych koszyków. Może być czasochłonne.",
                ):
                    st.session_state["run_ranking_pairs"] = True

            with col_clear:
                if st.button(
                    "Ukryj ranking",
                    key="clear_ranking_pairs_btn",
                    help="Czyści widok rankingu, aby nie renderował się przy kolejnych rerunach.",
                ):
                    st.session_state["run_ranking_pairs"] = False

            if st.session_state.get("run_ranking_pairs", False):
                df_ranking_ui = _analysis_table_ui(
                    ranking_hit_rate_pairs(df, usable_features, signal_col, q=3, min_obs=300)
                )
                st.dataframe(
                    df_ranking_ui,
                    hide_index=True
                )
            else:
                st.info(
                    "Ranking cech jest wyłączony, aby przyspieszyć działanie aplikacji.\n\n"
                    "Kliknij przycisk powyżej, jeśli chcesz obliczyć i wyświetlić tabelę porównawczą."
                )



        with tab5:
            with st.expander("Rozwiń aby poznać dokładny opis", expanded=False):
                st.markdown(
                    """
                    **Co widzisz?**  
                    Starszą wersję porównania, która pokazuje,
                    jaki udział całego rynku stanowią sygnały +1
                    w najlepszych zakresach wybranych cech.

                    **Jak to czytać?**  
                    - wartości w tej tabeli zwykle są niskie, bo same sygnały są rzadkie,
                    - ta zakładka bardziej pokazuje „skalę zjawiska w całym rynku”
                      niż siłę warunku w konkretnej grupie,
                    - traktuj ją pomocniczo, jako dodatkowe spojrzenie na wyniki.

                    **Najważniejsze kolumny:**  
                    - **Skuteczność globalna (%)** – jaki udział całego rynku stanowią sygnały +1
                      w najlepszym przedziale,
                    - **Liczba sygnałów +1** – ile takich przypadków rzeczywiście znaleziono,
                    - **Liczba obserwacji** – jak duża była grupa użyta do porównania,
                    - **Najlepszy przedział X / Y** – który zakres wartości dawał najlepszy wynik.

                    **Kiedy jest przydatna?**  
                    Gdy chcesz sprawdzić, czy dany warunek dotyczy tylko wąskiej niszy,
                    czy ma szersze znaczenie w danych.
                    """
                )

            col_run, col_clear = st.columns(2)

            with col_run:
                if st.button(
                    "Policz hit-rate globalny",
                    key="run_global_pairs_btn",
                    help="Oblicza globalny hit-rate dla najlepszych koszyków cech i par cech. Może być czasochłonne.",
                ):
                    st.session_state["run_global_pairs"] = True

            with col_clear:
                if st.button(
                    "Ukryj hit-rate globalny",
                    key="clear_global_pairs_btn",
                    help="Czyści widok hit-rate globalnego, aby nie renderował się przy kolejnych rerunach.",
                ):
                    st.session_state["run_global_pairs"] = False

            if st.session_state.get("run_global_pairs", False):
                df_global_ui = _analysis_table_ui(
                    global_hit_rate_pairs(df, usable_features, signal_col, q=3, min_obs=300)
                )

                st.dataframe(
                    df_global_ui,
                    hide_index=True
                )
            else:
                st.info(
                    "Tabela hit-rate globalnego jest wyłączona, aby przyspieszyć działanie aplikacji.\n\n"
                    "Kliknij przycisk powyżej, jeśli chcesz ją obliczyć."
                )



        with tab6:
            with st.expander("Rozwiń aby poznać dokładny opis", expanded=False):
                st.markdown(
                    """
                    **Co widzisz?**  
                    Macierz korelacji między cechami, czyli informację o tym,
                    które wskaźniki zachowują się podobnie.

                    **Jak to czytać?**  
                    - wysoka dodatnia korelacja oznacza, że dwie cechy często niosą podobną informację,
                    - wysoka ujemna korelacja oznacza, że często poruszają się w przeciwnych kierunkach,
                    - sama korelacja nie mówi jeszcze, czy cecha jest dobra do przewidywania sygnału.

                    **Po co to jest?**  
                    Ta zakładka pomaga ograniczać powielanie bardzo podobnych wskaźników
                    przed dalszą analizą i budową modeli ML.
                    """
                )

            col_run, col_clear = st.columns(2)

            with col_run:
                if st.button(
                    "Policz macierz korelacji",
                    key="run_corr_matrix_btn",
                    help="Oblicza macierz korelacji dla wszystkich cech. Może być czasochłonne przy większej liczbie cech.",
                ):
                    st.session_state["run_corr_matrix"] = True

            with col_clear:
                if st.button(
                    "Ukryj macierz korelacji",
                    key="clear_corr_matrix_btn",
                    help="Czyści widok macierzy korelacji, aby nie renderował się przy kolejnych rerunach.",
                ):
                    st.session_state["run_corr_matrix"] = False

            if st.session_state.get("run_corr_matrix", False):
                correlation_heatmap(df, usable_features)
            else:
                st.info(
                    "Macierz korelacji jest wyłączona, aby przyspieszyć działanie aplikacji.\n\n"
                    "Kliknij przycisk powyżej, aby ją obliczyć i wyświetlić."
                )



    finally:
        # Czyścimy komunikat tylko wtedy, gdy placeholder został już utworzony.
        # To zabezpiecza kod przed błędem, jeśli funkcja zakończy się wcześniej.
        if global_status is not None:
            global_status.empty()
