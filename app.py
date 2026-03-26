
import streamlit as st
import os
from dotenv import load_dotenv
# --- Import widoków UI ---
from app.ui.home import render as render_home
def render_import_view():
    from app.ui.import_view import render as render_import
    render_import()
from app.ui.indicators_view import render as render_indicators

from config.app_params import get_param, set_param
from config.app_params import _APP_PARAMS
from app.ui.data_overview import render as render_data_overview
from app.ui.analysis_view import render as render_analysis
from app.ui.analysis_view_v2 import render as render_analysis_v2
from app.ui.analysis_view_v3 import render as render_analysis_v3
from etl.data_provider import get_asset_path
from app.ml.ml_01 import render as render_ml_01





# st.title("Analiza giełdowa")              # H1 → css h1
# st.header("Przegląd danych")              # H2 → css h2
# st.subheader("Dostępny zakres danych")    # H3 → css h3
# st.subheader("Filtry")                    # H3 → css h3
# st.markdown("**Dostępny zakres danych**") # H4 (nie stylizowany)

# Zmiana na poziom niższe nagłówki:
# st.title ->  st.header
# st.header ->  st.subheader
# st.subheader ->  st.markdown(


# --- Inicjalizacja parametrów aplikacji ---
load_dotenv()


# --- Cache stanu połączenia (Streamlit session) ---
if "RUNTIME_MODE_INIT_DONE" not in st.session_state:
    st.session_state.RUNTIME_MODE_INIT_DONE = False


def init_runtime_mode_once() -> None:
    """
    Inicjalizacja trybu pracy aplikacji (1x na sesję Streamlit).

    Reguły:
    1) .env APP_TEST_ON_CSV_FILES=True => wymuszamy CSV (bez testu DB)
    2) .env APP_TEST_ON_CSV_FILES=False => próbujemy DB:
       - jeśli test DB OK => tryb DB
       - jeśli test DB FAIL => fallback do CSV
    """
    if st.session_state.RUNTIME_MODE_INIT_DONE:
        return


    from config.app_params import get_param, set_param

    app_mode = get_param("APP_MODE")

    if app_mode == "DEMO":
        set_param("APP_TEST_ON_CSV_FILES", True)
        set_param("DB_CONNECTION_AVAILABLE", False)
    else:
        from core.db import update_db_connection_status
        update_db_connection_status()



    st.session_state.RUNTIME_MODE_INIT_DONE = True


# --- inicjalizacja trybu (1x) ---
init_runtime_mode_once()

# stan aplikacji ZAWSZE bierzemy z _APP_PARAMS
APP_TEST_ON_CSV_FILES = _APP_PARAMS["APP_TEST_ON_CSV_FILES"]


# --- Konfiguracja aplikacji ---
if APP_TEST_ON_CSV_FILES:
    st.set_page_config(
        page_title="Analiza giełdowa – obsługa bazy danych z plików CSV",
        layout="wide",
    )
else:
    st.set_page_config(
        page_title="Analiza giełdowa",
        layout="wide",
    )


# ============================================================
# GLOBALNY CSS – tryb compact (UI analityczne)
# ============================================================
st.markdown(
    """
    <style>
    /* =========================================================
       1) GLOBAL BASE + TŁO
       ========================================================= */
    html, body {
        font-size: 16px;                 /* (A) Baza całej aplikacji */
        background-color: #12161d;
    }
    div[data-testid="stAppViewContainer"],
    section.main > div {
        background-color: #12161d;       /* (B) Tło głównej powierzchni */
    }

    /* =========================================================
       2) NAGŁÓWKI (to steruje: Analiza giełdowa / Przegląd danych / Filtry / Dostępny zakres danych)
       ========================================================= */
    h1 {                                  /* Analiza giełdowa → wizualnie jak dawne H2 */
        font-size: 0.4rem;
        margin-bottom: 0.45rem;
    }

    h2 {                                  /* Przegląd danych → wizualnie jak dawne H3 */
        font-size: 0.35rem;
        margin-bottom: 0.35rem;
    }

    h3 {                                  /* Sekcje → jeszcze mniejsze */
        font-size: 0.25rem;
        margin-bottom: 0.30rem;
    }

    /* =========================================================
       3) ETYKIETY WIDGETÓW (to steruje: Firmy / Data od / Data do)
       Uwaga: w Streamlit potrafi być renderowane jako stWidgetLabel
       albo jako MarkdownContainer – dlatego dajemy oba warianty.
       ========================================================= */

    /* (F) Najczęstszy wariant etykiet pól */
    div[data-testid="stWidgetLabel"] {
        font-size: 0.75rem !important;    /* ← Firmy / Data od / Data do */
        font-weight: 600;
        color: #e6e6e6;
        margin-bottom: 0.2rem;
    }

    /* (G) Wariant gdy etykieta jest markdownem nad widgetem */
    div[data-testid="stTextArea"] div[data-testid="stMarkdownContainer"] p,
    div[data-testid="stDateInput"] div[data-testid="stMarkdownContainer"] p,
    div[data-testid="stTextInput"] div[data-testid="stMarkdownContainer"] p,
    div[data-testid="stSelectbox"] div[data-testid="stMarkdownContainer"] p,
    div[data-testid="stMultiselect"] div[data-testid="stMarkdownContainer"] p {
        font-size: 1.05rem !important;    /* ← Firmy / Data od / Data do */
        font-weight: 600;
        color: #e6e6e6;
        margin-bottom: 0.2rem;
    }

    /* =========================================================
       4) CHECKBOXY (to steruje: Wszystkie dostępne firmy + wskaźniki)
       ========================================================= */
    div[data-testid="stCheckbox"] label {
        font-size: 0.70rem;               /* (H) Tekst przy checkboxach */
        line-height: 1.05;
        padding: 0 2px;
    }
    div[data-testid="stCheckbox"] {
        margin-bottom: 0.05rem;
    }

    /* =========================================================
       5) EXPANDERY (to steruje: np. "Opis działania ekranu", "Diagnostyka: ...")
       ========================================================= */
    details > summary {
        font-size: 0.85rem;               /* (I) Tytuły expanderów */
        padding: 0.25rem 0;
    }

    /* =========================================================
       6) UKŁAD / GĘSTOŚĆ
       ========================================================= */
    section[data-testid="stVerticalBlock"] {
        gap: 0.4rem;
    }
    div[data-testid="column"] {
        padding-left: 0.25rem;
        padding-right: 0.25rem;
    }

    /* =========================================================
       7) AG GRID
       ========================================================= */
    .ag-theme {
        font-size: 12px;                  /* (J) Tabela AgGrid */
    }
    </style>
    """,
    unsafe_allow_html=True,
)





st.sidebar.caption(
    f"{get_param('APP_NAME')} "
    f"v{get_param('APP_VERSION')} "
    f"[{get_param('APP_ENV')}]"
)



# --- Sidebar: nawigacja ---
# W tym miejscu definiujemy:
# 1) etykiety widoczne w menu po lewej stronie
# 2) mapę nazw sekcji do funkcji renderujących widoki
#
# Dzięki temu zmiana nazwy pozycji w menu nie wymaga już
# pamiętania o osobnym poprawianiu wielu if/elif niżej.

st.sidebar.title("Moduły")


def render_export_view():
    """
    Wrapper dla ekranu eksportu.

    Import robimy lokalnie w momencie wejścia na ekran,
    tak jak było wcześniej w routingu. To pozwala zachować
    dotychczasowe zachowanie aplikacji.
    """
    from app.ui.export_view import render as render_export
    render_export()


# Mapa wszystkich sekcji aplikacji.
# Klucz słownika to tekst widoczny w sidebarze.
# Wartość to funkcja, która renderuje dany ekran.
SECTION_VIEWS = {
    "Start": render_home,
    "Przegląd danych": render_data_overview,
    "Analiza danych": render_analysis_v3,
    "Machine Learning": render_ml_01,
    "Import danych": render_import_view,
    "Eksport danych": render_export_view,
}

# Kolejność pozycji w sidebarze.
# Trzymamy ją osobno, aby łatwo sterować układem menu.
section_options = [
    "Start",
    "Przegląd danych",
    "Analiza danych",
    "Machine Learning",
    "Import danych",
    "Eksport danych",

    # W razie potrzeby można przywrócić stare widoki,
    # "Analiza v1", 
    # "Analiza v2", 
    # "Przegląd wskaźników",
]

# Jeżeli aplikacja działa w trybie CSV, ukrywamy sekcje
# wymagające operacji importu/eksportu.
if APP_TEST_ON_CSV_FILES:
    hidden_sections = {"Import danych", "Eksport danych"}
    section_options = [name for name in section_options if name not in hidden_sections]

section = st.sidebar.radio(
    "Wybierz:",
    options=section_options,
)


# ============================================================
# CZYSZCZENIE „ZAWIESZONYCH” PLACEHOLDERÓW PRZY ZMIANIE EKRANU
# (eliminuje „duchy” poprzednich widoków)
# ============================================================
prev_section = st.session_state.get("_prev_section")
if prev_section != section:
    # wyczyść wszystkie placeholdery zapisane w session_state (np. *_root_placeholder)
    for k, v in list(st.session_state.items()):
        if isinstance(k, str) and (k.endswith("_root_placeholder") or k.endswith("_placeholder")):
            try:
                # DeltaGenerator / placeholder ma metodę empty()
                if hasattr(v, "empty"):
                    v.empty()
            except Exception:
                pass

    st.session_state["_prev_section"] = section

# ============================================================
# GLOBALNY ROOT STRONY (czyści cały ekran przy rerun)
# ============================================================

if "global_root" not in st.session_state:
    st.session_state["global_root"] = st.empty()

global_root = st.session_state["global_root"]
# global_root.empty()

# --- Routing widoków ---



with global_root.container():

    # --- Globalny nagłówek aplikacji (header + logo) ---
    col_title, col_logo = st.columns([4, 1])

    with col_title:
        if APP_TEST_ON_CSV_FILES:
            st.header("Analiza giełdowa – obsługa bazy danych z plików CSV")
        else:
            st.header("Analiza giełdowa")

    with col_logo:
        logo_path = get_asset_path("APP_ASSETS_PATH", "APP_LOGO_FILE")
        st.image(
            logo_path,
            width=180,
        )

    # --- Routing widoków ---
    # Pobieramy funkcję przypisaną do wybranej sekcji w sidebarze.
    # Dzięki temu logika wyboru ekranu jest w jednym miejscu
    # i nie trzeba utrzymywać długiego łańcucha if/elif.
    selected_view = SECTION_VIEWS.get(section)

    if selected_view is not None:
        selected_view()
    else:
        st.error(f"Nieznana sekcja aplikacji: {section}")

    # --- Stopka ---
    st.markdown("---")
    st.caption("Projekt: Analiza giełdowa (TomZam)")
