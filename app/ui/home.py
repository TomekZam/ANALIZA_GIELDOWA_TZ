import streamlit as st
from config.app_params import get_param
from etl.data_provider import get_data_source_label
from etl.data_provider import (
    get_company_ids_for_tickers_csv,
    get_last_prices_for_company_ids,
)
from app.ui.column_metadata import COLUMN_LABELS
import pandas as pd

# AgGrid wykorzystujemy już w innych ekranach aplikacji.
# Dzięki temu tabela na stronie startowej będzie wyglądała nowocześniej
# i pozwoli na wygodne sortowanie / filtrowanie danych.
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

def _format_change_with_arrow(value: float | None) -> str:
    """
    Formatuje zmianę dzienną w sposób spójny z ekranem 'Przegląd danych'.

    Przykłady:
    - dodatnia wartość  -> ▲ 1.05
    - ujemna wartość    -> ▼ 0.38
    - zero              -> — 0.00
    """
    if value is None or pd.isna(value):
        return ""

    value = float(value)
    formatted = f"{abs(value):,.2f}".replace(",", " ")

    if value > 0:
        return f"▲ {formatted}"
    if value < 0:
        return f"▼ {formatted}"
    return f"— {formatted}"

def _render_home_market_table(df_view: pd.DataFrame) -> None:
    """
    Renderuje tabelę 'Dane startowe aplikacji' w spójnej, nowoczesnej formie.

    Założenia:
    - zachowujemy prosty układ znany ze starej tabeli,
    - poprawiamy sortowanie i filtrowanie dzięki AgGrid,
    - nie dodajemy na siłę dodatkowych kolumn, aby nie zawężać widoku,
    - wszystkie wartości mają być czytelne od razu po wejściu na stronę startową.
    """
    if df_view is None or df_view.empty:
        st.info("Brak danych do wyświetlenia.")
        return

    gb = GridOptionsBuilder.from_dataframe(df_view)

    # Domyślna konfiguracja tabeli.
    gb.configure_default_column(
        sortable=True,
        filter=True,
        resizable=True,
        minWidth=90,
    )

    # Paginacja poprawia czytelność przy większej liczbie spółek.
    gb.configure_pagination(
        paginationAutoPageSize=False,
        paginationPageSize=10,
    )

    gb.configure_grid_options(
        domLayout="normal",
    )

    # Kolumny tekstowe.
    if "Ticker" in df_view.columns:
        gb.configure_column("Ticker", width=90, minWidth=80, pinned="left")

    if "Nazwa spółki" in df_view.columns:
        gb.configure_column("Nazwa spółki", width=180, minWidth=160)

    if "Data" in df_view.columns:
        gb.configure_column("Data", width=120, minWidth=110)

    # Kolumny liczbowe.
    if "Cena" in df_view.columns:
        gb.configure_column("Cena", type=["numericColumn"], width=110, minWidth=100)

    if "Wolumen" in df_view.columns:
        gb.configure_column("Wolumen", type=["numericColumn"], width=120, minWidth=110)

    # 'Zmiana' jest formatowana tekstowo (np. ▲ 1.05),
    # więc nie konfigurujemy jej jako czysto numerycznej.
    if "Zmiana" in df_view.columns:
        gb.configure_column("Zmiana", width=110, minWidth=100)

    if "Zmiana %" in df_view.columns:
        gb.configure_column("Zmiana %", type=["numericColumn"], width=110, minWidth=100)

    grid_options = gb.build()

    AgGrid(
        df_view,
        gridOptions=grid_options,
        height=390,
        theme="balham",
        update_mode=GridUpdateMode.NO_UPDATE,
        # Dopasowanie kolumn do szerokości siatki poprawia wygląd
        # i ogranicza ryzyko, że część kolumn „ucieknie” poza widoczny obszar.
        fit_columns_on_grid_load=True,
        allow_unsafe_jscode=False,
    )

def render():

    # --------------------------------------------------------
    # Last prices for LOAD_TICKERS (session cache)
    # --------------------------------------------------------
    if "df_last_load_tickers" not in st.session_state:
        tickers_csv = get_param("LOAD_TICKERS")
        company_ids = get_company_ids_for_tickers_csv(tickers_csv)

        if company_ids:
            st.session_state["df_last_load_tickers"] = (
                get_last_prices_for_company_ids(company_ids)
            )
        else:
            st.session_state["df_last_load_tickers"] = None


    # ========================================================
    # Sekcja: krótki opis aplikacji + rozwijana instrukcja
    # ========================================================
    st.subheader("Jak korzystać z aplikacji **Analiza Giełdowa** (realizacja przez TomZam)")

    # Krótki, widoczny od razu opis strony startowej.
    # Ma szybko wyjaśnić czym jest aplikacja i jaką ścieżką najlepiej przez nią przejść.
    st.markdown(
        """
        **Analiza Giełdowa** to aplikacja do badania danych rynkowych
        i eksperymentowania z modelami predykcyjnymi na podstawie danych historycznych.

        **Rekomendowany sposób pracy:**
        **zobacz sygnał → zrozum sygnał → spróbuj go przewidzieć**

        Najlepiej przechodzić przez aplikację w tej kolejności:

        - **1. Przegląd danych** – zobacz sygnał i jego kontekst na wykresach,
        - **2. Analiza danych** – sprawdź, z jakimi wskaźnikami i warunkami rynkowymi sygnał może być powiązany,
        - **3. Machine Learning** – przetestuj, czy analizowany sygnał da się przewidywać na podstawie danych historycznych.
        """
    )

    st.caption("Zacznij od ekranu **Przegląd danych**.")

    # Pełna instrukcja jest dostępna w ekspanderze,
    # żeby nie przeciążać strony startowej zbyt dużą ilością tekstu.
    with st.expander("Pokaż pełny opis działania aplikacji", expanded=False):
        col_a, col_b, col_c = st.columns(3)

        with col_a:
            st.markdown(
                """
                **1. Ekran: Przegląd danych**
                - załaduj dane do aplikacji,
                - zapoznaj się z działaniem ekranu korzystając z rozwijanych sekcji opisujących poszczególne elementy analizy,
                - zwracaj uwagę na symbole **(?)**, które pokazują dodatkowe wyjaśnienia znaczenia wybranych wskaźników i sygnałów,
                - sprawdź dostępny zakres danych na wykresach,
                - zweryfikuj kompletność notowań i wskaźników,
                - wybierz interesujące spółki i okresy,
                - zobacz, jakie wskaźniki i sygnały są dostępne,
                - poznaj ich znaczenie i podstawową interpretację,
                - sprawdź pokrycie historyczne danych,
                - oceń ogólny charakter danych rynkowych (trend, zmienność, aktywność obrotu),
                - zidentyfikuj okresy wzrostów, spadków i konsolidacji,
                - wybierz przykładowy sygnał, np. **Sygnał 20 D**, i zobacz na wykresie (można je przybliżać i oddalać), kiedy historycznie występował oraz w jakim kontekście rynkowym się pojawiał,
                - sprawdź, jak zachowywała się cena oraz wybrane wskaźniki w pobliżu wystąpień tego sygnału,
                - zbuduj intuicję, czy dany sygnał wygląda na interesujący i czy warto badać go dalej na kolejnych ekranach,
                - przygotuj się do dalszej analizy zależności, a następnie do próby przewidywania tego sygnału w module Machine Learning.

                **Efekt:** rozumiesz, jak sygnał wygląda w danych historycznych.
                """
            )

        with col_b:
            st.markdown(
                """
                **2. Ekran: Analiza danych**
                - wybierz sygnał do analizy, np. **Sygnał 20 D**, który chcesz później próbować przewidywać w ekranie Machine Learning,
                - zapoznaj się z poszczególnymi zakładkami analiz, w szczególności z analizą EDA wybranego sygnału,
                - sprawdź, jak często sygnał występuje i w jakich okresach rynkowych pojawia się najczęściej,
                - zbadaj zależności pomiędzy wybranym sygnałem a wskaźnikami technicznymi oraz ich kombinacjami,
                - oceń, które wskaźniki mogą mieć związek z późniejszym pojawieniem się sygnału,
                - identyfikuj konfiguracje cech zwiększające prawdopodobieństwo wystąpienia analizowanego sygnału,
                - sprawdź stabilność tych zależności w różnych okresach rynkowych,
                - wytypuj wskaźniki o potencjalnie najwyższej wartości predykcyjnej,
                - wytypuj wskaźniki, które warto ograniczyć lub usunąć w przyszłych modelach (np. gdy powielają informacje),
                - buduj hipotezy analityczne, które będą mogły zostać zweryfikowane w kolejnym kroku przy użyciu modeli Machine Learning,
                - potraktuj ten ekran jako etap przygotowania do predykcji: najpierw poznajesz sygnał i jego kontekst, a dopiero później sprawdzasz w ML, czy da się go przewidywać na podstawie danych historycznych.

                **Efekt:** rozumiesz, co może wyjaśniać występowanie sygnału.
                """
            )

        with col_c:
            st.markdown(
                """
                **3. Ekran: Machine Learning**

                Ekran Machine Learning pozwala sprawdzić,
                czy na podstawie danych historycznych można zbudować model
                wskazujący potencjalnie interesujące sygnały rynkowe. Eksperymentuj z budową modeli predykcyjnych na podstawie danych historycznych,
                przechodząc kolejne kroki procesu analitycznego:

                - **Setup danych ML (TRAIN/VAL)**  
                wybierz sygnał (target), który ma być prognozowany przez model np. **Sygnał 20 D**,  
                ustaw tryb uczenia (**FAST** – szybkie testy, **FULL** – dokładniejsze modele),  
                wskaż kolumny, które mają zostać wykluczone z modelu oraz podstawowe opcje przygotowania danych  
                (np. balans klas, normalizacja, transformacje).

                - **Trening i walidacja modeli (TRAIN/VAL)**  
                uruchom proces budowy i porównania kilku przykładowych modeli Machine Learning.  
                Modele są trenowane na danych historycznych (TRAIN), a ich jakość oceniana na oddzielnym zbiorze walidacyjnym (VALIDATION).  
                Na tej podstawie wybierz model najlepiej dopasowany do analizowanego sygnału.

                - **Optymalizacja strategii sygnałów (VALIDATION)**  
                sprawdź, jak wyniki modelu mogą zostać wykorzystane w praktyce inwestycyjnej.  
                W tym kroku analizujesz ranking spółek wskazanych przez model i testujesz różne warianty selekcji sygnałów z wykorzystaniem dodatkowych filtrów danych  
                (np. wybór najlepszych spółek w określonych oknach czasowych).

                - **Finalny test modelu (TEST)**  
                wykonaj końcową weryfikację wybranego modelu na danych, które nie były używane wcześniej w procesie uczenia.  
                Pozwala to ocenić, jak model może zachowywać się w rzeczywistych warunkach rynkowych.

                **Efekt:** sprawdzasz, czy analizowany sygnał można próbować przewidywać.
                """
            )


    # ========================================================
    # Sekcja: dane startowe aplikacji
    # ========================================================
    st.markdown("---")
    st.subheader("Dane startowe aplikacji")
    # Opis nad tabelą pokazuje dynamicznie datę ostatniego notowania
    # widocznego w tabeli. Dzięki temu tekst zawsze pozostaje spójny
    # z faktycznie załadowanymi danymi.
    df_last = st.session_state.get("df_last_load_tickers")

    last_trade_date_txt = "—"
    if isinstance(df_last, pd.DataFrame) and not df_last.empty and "trade_date" in df_last.columns:
        last_trade_date = pd.to_datetime(df_last["trade_date"], errors="coerce").max()
        if pd.notna(last_trade_date):
            last_trade_date_txt = last_trade_date.strftime("%Y-%m-%d")

    st.caption(
        f"W systemie dostępne są dane historyczne od początku notowań giełdowych "
        f"do dnia **{last_trade_date_txt}**. "
        f"Poniższa tabela prezentuje ostatnie dostępne notowanie dla każdej spółki "
        f"w tym zakresie danych. "
        f"Tabelę można sortować i filtrować, aby szybciej znaleźć spółki z największą zmianą, "
        f"najwyższym wolumenem lub interesującą ceną."
    )


    if df_last is None or df_last.empty:
        st.info("Brak skonfigurowanych tickerów lub brak danych do wyświetlenia.")
    else:
        df_view = df_last.copy()

        # ----------------------------------------------------
        # Przygotowanie danych do tabeli startowej
        # ----------------------------------------------------

        # 1) Usuń kolumnę techniczną, jeśli jest dostępna.
        if "company_id" in df_view.columns:
            df_view = df_view.drop(columns=["company_id"])

        # 2) Uporządkuj datę do formatu tekstowego YYYY-MM-DD.
        # Używamy stringa zamiast obiektu date, ponieważ AgGrid
        # w tej tabeli lepiej renderuje zwykły tekst niż obiekt daty.
        if "trade_date" in df_view.columns:
            df_view["trade_date"] = pd.to_datetime(
                df_view["trade_date"],
                errors="coerce",
            ).dt.strftime("%Y-%m-%d")

        # 3) Zostawiamy prosty zestaw kolumn znany ze starej tabeli,
        # ale przywracamy także kolumnę 'change' / 'Zmiana',
        # aby układ był spójny z ekranem 'Przegląd danych'.
        preferred_cols = [
            "ticker",
            "company_name",
            "trade_date",
            "close_price",
            "volume",
            "change",
            "change_pct",
        ]
        existing_cols = [c for c in preferred_cols if c in df_view.columns]
        df_view = df_view[existing_cols].copy()

        # 4) Najpierw porządkujemy wartości surowe,
        # a dopiero potem zmieniamy nazwy kolumn na przyjazne dla użytkownika.
        if "close_price" in df_view.columns:
            df_view["close_price"] = pd.to_numeric(df_view["close_price"], errors="coerce").round(2)

        if "volume" in df_view.columns:
            df_view["volume"] = pd.to_numeric(df_view["volume"], errors="coerce")

        if "change_pct" in df_view.columns:
            df_view["change_pct"] = pd.to_numeric(df_view["change_pct"], errors="coerce").round(2)

        # Kolumna 'change' jest prezentowana w wersji tekstowej ze strzałką,
        # tak samo jak na ekranie 'Przegląd danych'.
        if "change" in df_view.columns:
            df_view["change"] = pd.to_numeric(df_view["change"], errors="coerce")
            df_view["change"] = df_view["change"].apply(_format_change_with_arrow)

        # 5) Zmień nazwy kolumn na przyjazne dla użytkownika.
        rename_map = {
            "ticker": "Ticker",
            "company_name": "Nazwa spółki",
            "trade_date": "Data",
            "close_price": "Cena",
            "volume": "Wolumen",
            "change": "Zmiana",
            "change_pct": "Zmiana %",
        }
        df_view = df_view.rename(columns=rename_map)

        # 6) Zachowujemy domyślny porządek po zmianie procentowej,
        # bo jest to najbardziej użyteczny widok startowy.
        if "Zmiana %" in df_view.columns:
            df_view = df_view.sort_values(
                by="Zmiana %",
                ascending=False,
                na_position="last",
                kind="stable",
            ).reset_index(drop=True)

        # 7) Render tabeli przez AgGrid.
        _render_home_market_table(df_view)



    # ========================================================
    # Sekcja: informacje techniczne
    # ========================================================
    st.markdown("---")

    # Sekcja techniczna jest ukryta domyślnie, żeby nie dominowała
    # wizualnie nad częścią analityczną strony startowej.
    with st.expander("Informacje techniczne", expanded=False):
        col_s1, col_s2, col_s3 = st.columns(3)

        with col_s1:
            st.metric(
                label="Tryb pracy",
                value="CSV" if get_param("APP_TEST_ON_CSV_FILES") else "DB",
            )

        with col_s2:
            st.metric(
                label="Połączenie z bazą",
                value="OK" if get_param("DB_CONNECTION_AVAILABLE") else "NIEDOSTĘPNE",
            )

        with col_s3:
            st.metric(
                label="Źródło danych",
                value=get_data_source_label(),
            )


