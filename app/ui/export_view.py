import streamlit as st
from pathlib import Path
import re

from config.app_params import get_param
from etl.export.export_to_csv import export_companies_to_csv


def render():
    st.header("Eksport danych do plików CSV")
    st.markdown("---")
    st.subheader("Parametry eksportu")

    # =========================================================
    # 2 KOLUMNY – Parametry plików i daty
    # =========================================================
    k1, k2 = st.columns(2)

    with k1:
        st.text_input(
            "Plik spółek (companies)",
            value=get_param("DATA_WSE_COMPANIES"),
            disabled=True,
        )
    with k2:
        st.text_input(
            "Katalog docelowy eksportu",  # DATA_WSE_PATH
            value=get_param("DATA_WSE_PATH"),
            disabled=True,
        )

    with k1:
        st.text_input(
            "Plik notowań dziennych (prices_daily)",
            value=get_param("DATA_WSE_PRICES_DAILY"),
            disabled=True,
        )
    with k2:
        st.text_input(
            "Plik wskaźników dziennych (indicators_daily)",
            value=get_param("DATA_WSE_IND_DAILY"),
            disabled=True,
        )

    # Pola edytowalne: daty
    if "export_date_from" not in st.session_state:
        st.session_state.export_date_from = get_param("EXPORT_DATE_FROM")
    if "export_date_to" not in st.session_state:
        st.session_state.export_date_to = get_param("EXPORT_DATE_TO")

    with k1:
        st.session_state.export_date_from = st.text_input(
            "Data od (YYYY-MM-DD)",
            value=st.session_state.export_date_from,
        )
    with k2:
        st.session_state.export_date_to = st.text_input(
            "Data do (YYYY-MM-DD)",
            value=st.session_state.export_date_to,
        )

    # =========================================================
    # 1 KOLUMNA – Tickery do eksportu (WSE)
    # =========================================================
    if "tickers" not in st.session_state:
        st.session_state.tickers = get_param("EXPORT_TOCSV_WSE_TICKERS")

    tickers = st.text_input(
        "Tickery do eksportu (WSE)",
        value=st.session_state.tickers,
    )
    st.session_state.tickers = tickers

    ticker_pattern = r"^[A-Z0-9]{2,5}(, [A-Z0-9]{2,5})*$"
    tickers_valid = bool(re.fullmatch(ticker_pattern, tickers.strip()))

    if not tickers_valid:
        st.error(
            "Podaj listę tickerów (2–5 znaków, duże litery/cyfry), "
            "rozdzielonych przecinkiem i spacją."
        )

    st.markdown("---")

    # =========================================================
    # ŚCIEŻKI
    # =========================================================
    output_dir = Path(get_param("DATA_WSE_PATH"))
    filename = get_param("DATA_WSE_COMPANIES")
    output_path = output_dir / filename

    # =========================================================
    # SESSION STATE
    # =========================================================
    if "export_requested" not in st.session_state:
        st.session_state.export_requested = False

    if "confirm_overwrite" not in st.session_state:
        st.session_state.confirm_overwrite = False

    # =========================================================
    # KROK 1 – kliknięcie eksportu
    # =========================================================
    if st.button("Wyeksportuj do pliku", disabled=not tickers_valid):
        st.session_state.export_requested = True

    # =========================================================
    # KROK 2 – logika eksportu
    # =========================================================
    if st.session_state.export_requested:

        # --- plik istnieje i brak potwierdzenia ---
        if output_path.exists() and not st.session_state.confirm_overwrite:
            st.warning(f"Plik {output_path} już istnieje. Czy chcesz go nadpisać?")

            c1, c2, c3, c4 = st.columns(4)

            with c1:
                if st.button("Tak, nadpisz plik"):
                    st.session_state.confirm_overwrite = True
                    st.rerun()
            with c2:
                if st.button("Nie, anuluj"):
                    st.info("Eksport anulowany – plik nie został nadpisany.")
                    st.session_state.export_requested = False
                    return
            # c3, c4 puste
            return

        # --- właściwy eksport ---
        from etl.export.export_to_csv import export_prices_daily_to_csv, export_indicators_daily_to_csv, export_indicators_dictionary_to_csv
        try:
            with st.spinner(f"Eksport do pliku: {filename}"):
                export_companies_to_csv(
                    output_dir=str(output_dir),
                    filename=filename,
                    tickers=st.session_state.tickers,
                    overwrite=True,
                )
            st.success(f"Plik {output_path} został zapisany.")

            # Eksport prices_daily.csv
            prices_filename = get_param("DATA_WSE_PRICES_DAILY")
            prices_output_path = output_dir / prices_filename
            with st.spinner(f"Eksport do pliku: {prices_filename}"):
                export_prices_daily_to_csv(
                    output_dir=str(output_dir),
                    filename=prices_filename,
                    tickers=st.session_state.tickers,
                    date_from=st.session_state.export_date_from,
                    date_to=st.session_state.export_date_to,
                    overwrite=True,
                )
            st.success(f"Plik {prices_output_path} został zapisany.")

            # Eksport indicators_daily.csv
            ind_filename = get_param("DATA_WSE_IND_DAILY")
            ind_output_path = output_dir / ind_filename
            with st.spinner(f"Eksport do pliku: {ind_filename}"):
                export_indicators_daily_to_csv(
                    output_dir=str(output_dir),
                    filename=ind_filename,
                    tickers=st.session_state.tickers,
                    date_from=st.session_state.export_date_from,
                    date_to=st.session_state.export_date_to,
                    overwrite=True,
                )
            st.success(f"Plik {ind_output_path} został zapisany.")

            # Eksport indicators_dictionary.csv
            dict_filename = get_param("DATA_WSE_IND_DICT")
            dict_output_path = output_dir / dict_filename
            with st.spinner(f"Eksport do pliku: {dict_filename}"):
                export_indicators_dictionary_to_csv(
                    output_dir=str(output_dir),
                    filename=dict_filename,
                    overwrite=True,
                )
            st.success(f"Plik {dict_output_path} został zapisany.")
        except Exception as e:
            st.error(f"Błąd eksportu: {e}")
        finally:
            st.session_state.export_requested = False
            st.session_state.confirm_overwrite = False
