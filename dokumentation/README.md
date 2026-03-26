# Analiza Giełdowa (AnGG) – tryb DEV

**Analiza Giełdowa (AnGG)** to projekt analityczno-badawczy służący do
eksploracji historycznych danych rynkowych spółek giełdowych
z wykorzystaniem **analizy technicznej, fundamentalnej oraz analiz statystycznych (EDA)**.

Projekt ma charakter **edukacyjny i badawczy**.
Nie stanowi doradztwa inwestycyjnego ani rekomendacji typu *kup / sprzedaj*.

---

## Cel projektu

Celem projektu jest:

- zbudowanie **spójnego, powtarzalnego i udokumentowanego** podejścia do analizy giełdowej,
- eksploracja zależności pomiędzy ceną a wskaźnikami technicznymi i fundamentalnymi,
- analiza historycznych sygnałów typu *future* (ex post),
- przygotowanie danych i wiedzy pod dalsze analizy oraz modele machine learning.

Projekt koncentruje się na **rozumieniu rynku**, a nie na bezpośrednim przewidywaniu cen.

---

## Instrukcja aplikacji:

[**ADR-010 – Instrukcja programu / Zachowanie ekranów aplikacji**](documentation/adr/ADR-010-Instrukcja-programu.md)


---

## Charakter repozytorium (DEV)

To repozytorium jest przeznaczone do **lokalnego developmentu** i prac analitycznych.

Tryb DEV oznacza:
- możliwość pracy na **bazie danych SQL**,
- możliwość fallbacku do **plików CSV**,
- pełny dostęp do warstwy analitycznej i infrastrukturalnej,
- brak ograniczeń funkcjonalnych obecnych w wersji DEMO.

---

## Tryby pracy aplikacji

Aplikacja wspiera dwa jawnie zdefiniowane tryby pracy:

### DEV
- aplikacja **może korzystać z bazy danych SQL**,
- przy starcie wykonywany jest test połączenia z DB,
- w przypadku braku połączenia następuje automatyczny fallback do CSV,
- tryb przeznaczony do:
  - developmentu,
  - analiz,
  - rozwoju ETL i modeli.

### DEMO
- aplikacja działa **wyłącznie na plikach CSV**,
- brak połączenia z DB,
- tryb przeznaczony do:
  - publicznej prezentacji,
  - Streamlit Cloud,
  - repozytoriów demonstracyjnych.

---

## Konfiguracja trybu pracy

Tryb pracy aplikacji jest sterowany **parametrami aplikacyjnymi**, a nie zmiennymi środowiskowymi.

Plik:
config/app_params.py


Kluczowe parametry:

python
# DEMO: aplikacja działa WYŁĄCZNIE na CSV (bez DB)
# DEV : aplikacja może używać DB
"APP_MODE": "DEV",   # DEMO | DEV

# Flaga pochodna – NIE ZMIENIANA runtime
"APP_TEST_ON_CSV_FILES": False

### Zasady

- `APP_MODE` jest parametrem nadrzędnym i decyzyjnym,
- `APP_TEST_ON_CSV_FILES` jest ustawiany wyłącznie podczas inicjalizacji aplikacji,
- zmiana trybu wymaga restartu aplikacji.

---

### Konfiguracja środowiskowa (`.env`)

Plik `.env` służy wyłącznie do:

- sekretów,
- konfiguracji środowiskowej,
- połączenia z bazą danych (DB).

---

### Zasada obowiązująca w projekcie

- `.env` → sekrety i środowisko (DB, hasła, hosty)
- `config/app_params.py` → zachowanie aplikacji (tryby, feature flags)
- `config/etl.py` → parametry procesów ETL

Plik `.env` nie jest wersjonowany i nie trafia do repozytorium.

AnGG/
├── app.py                  # entry point aplikacji Streamlit
├── app/                    # warstwa UI (Streamlit)
│   └── ui/
├── core/                   # konfiguracja, DB, infrastruktura
├── etl/                    # import i przetwarzanie danych
├── analysis/               # analiza danych, wskaźniki, ML
├── automation/             # przyszłe joby / schedulery
├── config/                 # konfiguracja aplikacji i ETL
├── documentation/          # dokumentacja (ADR, backlog, brief)
├── environment.yml         # definicja środowiska Conda
└── README.md


### Uruchomienie aplikacji (DEV)

1. Utwórz środowisko Conda:
conda env create -f environment.yml
conda activate analiza_gg

2. Upewnij się, że plik .env zawiera poprawne dane połączenia do DB.

3. Uruchom aplikację:
streamlit run app.py

### Źródła danych

W trybie DEV aplikacja może korzystać z:

- lokalnej bazy danych Microsoft SQL Server Express,
- plików CSV (fallback lub tryb testowy).

Struktura danych jest identyczna w obu przypadkach,
co pozwala przełączać źródło bez zmian w logice aplikacji.

---

### Dokumentacja

Pełna dokumentacja projektu znajduje się w katalogu:
documentation/


Najważniejsze pliki:

- `ARCHITECTURE_SUMMARY.md` – opis architektury,
- `BACKLOG.md` – pytania i kierunki dalszych prac,
- `adr/` – decyzje architektoniczne (ADR).



---

### Status projektu

- Status: w toku
- Charakter: analityczno-badawczy
- Tryb repozytorium: DEV (lokalne)

### Zastrzeżenie

Projekt nie generuje rekomendacji inwestycyjnych.
Wszystkie analizy mają charakter historyczny (ex post)
i służą wyłącznie budowie wiedzy oraz dalszym badaniom.
