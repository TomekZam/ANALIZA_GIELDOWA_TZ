# ARCHITECTURE_SUMMARY – Analiza GG

## Cel dokumentu
Ten dokument stanowi **skondensowane podsumowanie kluczowych decyzji architektonicznych**
projektu „Analiza giełdowa (Analiza GG)”.

Jest przeznaczony jako:
- źródło kontekstu dla AI (Custom GPT),
- skrót decyzyjny dla człowieka,
- alternatywa dla pełnych, szczegółowych ADR w bazie wiedzy GPT.

Pełna dokumentacja techniczna znajduje się w repozytorium projektu.

---

## Charakter projektu
- Projekt **analityczno-badawczy**
- Brak rekomendacji inwestycyjnych typu „kup/sprzedaj”
- Nacisk na **powtarzalność analizy**, przejrzystość i możliwość dalszej automatyzacji

---


# Struktura katalogów projektu Analiza GG (AnGG)

Dokument opisuje aktualną strukturę katalogów i plików projektu
oraz ich **odpowiedzialności architektoniczne**.
Pełni rolę mapy projektu (high-level inventory).

---

## Katalog główny

AnGG/
├── app.py
├── environment.yml
├── .env (gitignored)
├── .gitignore
├── README.md


- `app.py` – entry point aplikacji Streamlit (routing, sidebar)
- `environment.yml` – jedyne źródło prawdy o zależnościach (Conda)
- `.env` – sekrety i konfiguracja środowiskowa (DB, hasła)
- `README.md` – krótki opis repozytorium i sposobu uruchomienia

---

## core/ – warstwa infrastrukturalna

core/
├── init.py
├── config.py
└── db.py


- `config.py` – wczytywanie i walidacja konfiguracji z `.env`
- `db.py` – centralny mechanizm połączenia Python ↔ MS SQL Server  
  (SQLAlchemy, jedno źródło engine)

---

## config/ – jawna konfiguracja procesów

config/
├── init.py
└── etl.py


- `etl.py` – wersjonowane parametry procesów ETL  
  (ścieżki, tryby, nazwy plików, brak sekretów)

---

## etl/ – procesy importu danych

etl/
├── import/
│ └── (pliki wejściowe CSV / ZIP)


- katalog roboczy dla danych wejściowych ETL
- struktura zgodna z przyjętymi wzorcami archiwizacji (`imported/YYYY-MM-DD`)
- brak logiki biznesowej w tym katalogu

---

## analysis/ – warstwa analityczna

analysis/
├── calculated_indicators/
│ ├── base.py
│ ├── dispatcher.py
│ ├── pipeline.py
│ ├── registry.py
| ├── ind/
| │   ├── __init__.py   ← NOWY (ważne!)
| │   ├── ind_momentum_12m.py
| │   ├── ind_volatility_20d.py
| │   ├── ind_sma_200.py
| │   ├── ind_sharpe_20d.py
| │   └── ind_earnings_yield.py
│ └── utils/
│ └── db_helpers.py


- `base.py` – klasa bazowa wskaźnika (`CalculatedIndicator`)
- `ind_*.py` – implementacje pojedynczych wskaźników
- `registry.py` – rejestr dostępnych wskaźników
- `dispatcher.py` – liczenie wskaźnika dla spółki / dnia
- `pipeline.py` – orkiestracja pełnego pipeline’u wskaźników
- `utils/db_helpers.py` – warstwa dostępu do DB dla analizy

---

### Warstwa ML – eksperymenty i rejestr modeli

Projekt zawiera eksperymentalną warstwę ML
zlokalizowaną w katalogu:
app/ml/


Struktura:
app/ml/
├── ml_01.py
├── ml_datasets.py
├── model_registry.py
└── models/


Katalog `models/` przechowuje artefakty eksperymentów ML:

- zapis pipeline ML (`.joblib`)
- metadane modelu (`.json`)

Modele są zapisywane wraz z pełną konfiguracją eksperymentu,
co pozwala na ich odtworzenie i analizę w kolejnych iteracjach ML.

Mechanizm zapisu modeli został zdefiniowany w ADR-012.

Każdy eksperyment ML zapisuje dwa artefakty:

- model pipeline (`.joblib`)
- metadane eksperymentu (`.json`)

Plik `.json` zawiera konfigurację pozwalającą odtworzyć eksperyment, m.in.:

- model ML
- target
- feature set
- konfigurację selekcji rankingowej
- filtry jakościowe
- metryki VALIDATION

Artefakty te stanowią podstawę do późniejszej ewaluacji modeli
na **nieużywanym wcześniej zbiorze TEST**, bez ponownego treningu modeli.


### Rozszerzenie: zakładka `ML (TEST)` jako ewaluacja zapisanych modeli

Warstwa ML została rozszerzona o dedykowaną zakładkę UI:

`ML (TEST)`

Jej odpowiedzialność architektoniczna obejmuje:

- wybór zapisanego modelu z rejestru artefaktów,
- ponowne wczytanie pipeline ML (`.joblib`),
- odczyt metadanych eksperymentu (`.json`),
- odtworzenie selekcji rankingowej i filtrów jakościowych,
- ewaluację modelu wyłącznie na zbiorze `TEST`.

Kluczowe zasady:

- zakładka `ML (TEST)` nie trenuje modeli,
- zakładka nie używa `TRAIN` ani `VALIDATION` do obliczeń,
- `VALIDATION` może być użyte wyłącznie jako źródło zapisanych wcześniej metryk porównawczych,
- parametry selekcji rankingowej są odczytywane z metadanych modelu i pozostają zamrożone,
- pełna odtwarzalność eksperymentu wymaga zapisu:
  - filtrów jakościowych,
  - `min_conditions`,
  - parametrów rankingu,
  - targetu,
  - cech wejściowych modelu.

W runtime CSV / DEMO (flaga `APP_TEST_ON_CSV_FILES=True`)
zakładka działa jako strict read-only,
co chroni holdout TEST przed niekontrolowanym tuningiem.


---

## app/ – warstwa prezentacji (Streamlit)

app/
└── ui/
├── init.py
├── home.py
├── import_view.py
├── data_view.py
├── indicators_view.py
└── extensions.py


- każdy plik = jedna sekcja UI
- każdy moduł udostępnia funkcję `render()`
- brak logiki ETL i analitycznej
- UI pełni rolę **orkiestratora i prezentacji**

---

## documentation/ – dokumentacja projektu

documentation/
├── adr/
│ ├── ADR-00X-*.md
│ └── ADR_INDEX.md
├── ARCHITECTURE_SUMMARY.md
├── BACKLOG.md
├── PROJECT_BRIEF.md
└── README.md


- `adr/` – szczegółowe decyzje architektoniczne (ADR)
- `ADR_INDEX.md` – rejestr ADR
- `ARCHITECTURE_SUMMARY.md` – skrót architektury (high-level)
- `BACKLOG.md` – pytania, pomysły, dalsze kroki
- `PROJECT_BRIEF.md` – cel, zakres i kontekst projektu

---


---

## automation/ – przyszła automatyzacja

automation/


- miejsce na schedulery / batch / orchestrację
- obecnie puste (świadoma decyzja architektoniczna)

---


# Architektura warstwy UI Streamlit (modularna)

- Status: Accepted
- Data: 2026-01-05
- Zakres: Warstwa prezentacji (Streamlit UI)
- Powiązane:
  - ADR-002 – Środowisko i warstwa prezentacji (Streamlit)
  - ADR-004 – Struktura projektu Python i separacja odpowiedzialności

---

## Kontekst

W projekcie „Analiza giełdowa (AnGG)” rozpoczęto implementację
backendowego panelu operacyjnego w Streamlit, służącego do:

- uruchamiania procesów importu danych (ETL),
- przeglądu danych w bazie,
- kontroli stanu i wyników przetwarzania.

Początkowa implementacja w jednym pliku `app.py`
szybko przestała być skalowalna wraz z rozwojem kolejnych sekcji UI.

---

## Decyzja

Przyjęto **modularną architekturę warstwy UI Streamlit**:

1. **Entry point aplikacji**
   - Jedynym punktem startowym aplikacji jest plik:
     `app.py` w katalogu głównym projektu.
   - Aplikacja uruchamiana jest poleceniem:
     ```bash
     streamlit run app.py
     ```

2. **Struktura UI**
   - Warstwa UI znajduje się w pakiecie:
     ```
     app/ui/
     ```
   - Każda sekcja aplikacji Streamlit jest osobnym modułem `.py`.

3. **Kontrakt modułu UI**
   - Każdy moduł UI:
     - odpowiada dokładnie jednej sekcji aplikacji,
     - udostępnia funkcję:
       ```python
       def render():
           ...
       ```
   - Moduły UI nie zawierają logiki ETL ani analitycznej.

4. **Routing**
   - Plik `app.py` pełni wyłącznie rolę:
     - konfiguracji aplikacji,
     - nawigacji (sidebar),
     - routingu do odpowiednich funkcji `render()`.

---

## Przykładowa struktura


AnGG/
├── app.py
├── app/
│   └── ui/
│       ├── home.py
│       ├── import_view.py
│       ├── data_view.py
│       ├── indicators_view.py
│       └── extensions.py
├── etl/
├── core/
├── config/

---

## Uzupełnienie – Integracja ETL indicators_daily

Architektura UI Streamlit została rozszerzona o obsługę importu wskaźników dziennych (`indicators_daily`).

- import wskaźników znajduje się w tej samej sekcji UI co import notowań dziennych,
- UI wykorzystuje identyczny wzorzec sterowania:
  - tryb DRY-RUN,
  - tryb NORMALNY (z zapisem do DB i archiwizacją),
- UI nie zawiera żadnej logiki ETL ani SQL,
- odpowiedzialność UI ogranicza się do:
  - wywołania funkcji ETL,
  - prezentacji raportu i logów.

Rozwiązanie potwierdza skuteczność modularnej architektury UI
oraz poprawność wzorca integracji opisanego w ADR-011.



UI Streamlit nie posiada wiedzy o źródle danych (CSV / DB).
Wszystkie dane pobierane są przez warstwę Data Provider,
która enkapsuluje logikę runtime oraz źródła danych.





---

## Zasady ogólne

- Kod produkcyjny **wyłącznie w `.py`**
- Notebooki tylko do eksploracji
- UI ≠ ETL ≠ analiza (ścisła separacja)
- `core/` jako jedyne źródło konfiguracji DB
- Struktura obowiązuje zgodnie z ADR-002


---

## Główne decyzje architektoniczne

### 1. Środowisko uruchomieniowe
- Standardem projektu jest **Conda**
- Jedynym źródłem prawdy o zależnościach jest plik:
  - `environment.yml`
- `requirements.txt` nie jest używany
- Środowiska lokalne nie są wersjonowane

**Cel:** pełna odtwarzalność środowiska analitycznego.

---

### 2. Zarządzanie sekretami i konfiguracją
- Sekrety i konfiguracja lokalna przechowywane są w pliku:
  - `.env`
- Plik `.env` **nie trafia do repozytorium**
- Repo zawiera wyłącznie przykładową / jawną konfigurację (jeśli potrzebna)
- Parametry operacyjne procesów ETL (np. ścieżki do plików wejściowych, nazwy plików importu)
  są przechowywane w wersjonowanym module:
  - `config/etl.py`
- Zasada:
  - `.env` = sekrety + środowisko (DB, hasła, hosty)
  - `config/` = parametry działania pipeline’ów ETL (jawne, wersjonowane)

---

### 2a. Tryby pracy aplikacji (DEMO / DEV)

Aplikacja **Analiza GG (AnGG)** wspiera dwa jawnie zdefiniowane tryby pracy,
które determinują **źródło danych oraz dostępność funkcji**.

#### Tryb DEMO
- aplikacja działa **WYŁĄCZNIE na danych z plików CSV**,
- brak połączenia z bazą danych (DB),
- brak operacji importu / eksportu,
- przeznaczony do:
  - wersji demonstracyjnej,
  - publicznego repozytorium GitHub,
  - uruchomienia w środowisku Streamlit Cloud.

#### Tryb DEV
- aplikacja **może korzystać z bazy danych SQL**,
- przy starcie aplikacji wykonywany jest test połączenia z DB,
- w przypadku braku połączenia następuje **automatyczny fallback do CSV**,
- tryb przeznaczony do:
  - lokalnego developmentu,
  - prac analitycznych,
  - rozwoju ETL i analizy.

---

#### Parametry sterujące trybem pracy

Tryb pracy aplikacji jest kontrolowany przez **parametry aplikacyjne**
zdefiniowane w pliku:
config/app_params.py


Kluczowe parametry:

python:
# DEMO: aplikacja działa WYŁĄCZNIE na CSV (bez DB)
# DEV : aplikacja może używać DB
"APP_MODE": "DEMO",   # DEMO | DEV

# Flaga pochodna – NIE ZMIENIANA runtime
"APP_TEST_ON_CSV_FILES": True,

### Zasady

- `APP_MODE` jest parametrem nadrzędnym i decyzyjnym,
- `APP_TEST_ON_CSV_FILES` jest flagą pochodną, ustawianą wyłącznie
  podczas inicjalizacji aplikacji,
- parametry te nie są modyfikowane w runtime i wymagają restartu aplikacji
  przy zmianie.


#### Doprecyzowanie runtime

W praktyce runtime aplikacji powinien być interpretowany przede wszystkim przez flagę:

`APP_TEST_ON_CSV_FILES`

a nie wyłącznie przez wartość `APP_MODE`.

Powód:
- `APP_MODE=DEMO` oznacza pracę wyłącznie na CSV,
- `APP_MODE=DEV` może również zakończyć się runtime na CSV,
  jeżeli po starcie aplikacji nie ma dostępnego połączenia z bazą danych
  i następuje fallback do plików CSV.

Konsekwencja:
- decyzje UI zależne od realnego źródła danych
  (np. blokada trybu eksperymentalnego na zakładce `ML (TEST)`)
  powinny opierać się na `APP_TEST_ON_CSV_FILES`,
  a nie na samym `APP_MODE`.

---


### Relacja do konfiguracji środowiskowej (`.env`)

W ramach uporządkowania architektury:

- parametry sterujące zachowaniem aplikacji (tryb DEMO / DEV)
  zostały przeniesione z pliku `.env` do:
config/app_params.py

- plik `.env` jest używany wyłącznie do:
  - sekretów,
  - konfiguracji środowiskowej,
  - połączenia z bazą danych (DB).

---

### Zasada obowiązująca w projekcie

- `.env` → sekrety i środowisko (DB, hasła, hosty)
- `config/app_params.py` → zachowanie aplikacji (tryby, feature flags)
- `config/etl.py` → parametry procesów ETL

---

### Konsekwencje architektoniczne

- pełna kontrola nad trybem działania aplikacji,
- brak ryzyka przypadkowego użycia DB w wersji DEMO,
- możliwość publicznego udostępniania repozytorium,
- czytelny kontrakt konfiguracyjny dla developerów i recenzentów kodu.



---

### 3. Źródło danych rynkowych
- Podstawowym źródłem danych rynkowych (MVP) jest:
  - **stooq.pl**
- Zakres:
  - dane EOD (OHLCV),
  - szeregi czasowe,
  - format CSV,
  - pobieranie pełnej historii instrumentu
- Projekt używa **natywnych symboli Stooq**

**Cel:** prosty, stabilny i automatyzowalny pipeline danych.

### 3a. Odpowiedzialność za dane (data ownership)

Po imporcie danych do lokalnej bazy projekt przejmuje pełną
odpowiedzialność za ich integralność, spójność i dalsze przetwarzanie.
Źródła zewnętrzne (np. Stooq) są traktowane wyłącznie jako źródła wejściowe,
a nie systemy referencyjne w czasie rzeczywistym.
Analizy zawsze odnoszą się do stanu danych w bazie projektu.

---

### 4. Architektura logiczna projektu
Projekt oparty jest na separacji odpowiedzialności:
DANE → ANALIZA → PREZENTACJA

- **Dane**:
  - import, walidacja, zapis lokalny
- **Analiza**:
  - wskaźniki fundamentalne i techniczne
  - logika biznesowo-analityczna
- **Prezentacja**:
  - wizualizacja wyników
  - brak logiki analitycznej

---

### 5. Warstwa prezentacji i Architektura UI Streamlit (UI)
- Warstwa UI realizowana jest z użyciem **Streamlit**
- Streamlit:
  - służy wyłącznie do prezentacji wyników,
  - nie zawiera logiki analitycznej ani importów danych,
  - jest traktowany jako **narzędzie MVP / dashboard lokalny**
  - Warstwa UI Streamlit posiada architekturę modularną (`app/ui/*`).
  - Każda sekcja UI jest osobnym modułem z funkcją `render()`.
  - `app.py` w katalogu głównym pełni rolę entry pointu i routera.
  - UI uruchamia procesy ETL jako orkiestrator, bez logiki biznesowej.
- Dla analiz globalnych (market-wide) stosowany jest dataset **df_market_all** (session_state: `do_df_market_all`), budowany wyłącznie w module **„Przegląd danych”** i reużywany przez wszystkie ekrany analiz. Ekrany analiz nie tworzą własnych wersji datasetu „ALL” i nie stosują fallbacków generujących dane.

### Standard kompatybilności kodu Streamlit (deprecations policy)

W projekcie obowiązuje zasada **pisania kodu UI w sposób zgodny z aktualnym API Streamlit**,  
tak aby w terminalu developerskim (VS Code / CLI) nie pojawiały się komunikaty typu:

- `Please replace ...`
- `deprecated`
- `will be removed after ...`
- inne ostrzeżenia runtime dotyczące parametrów UI.

#### Zasada obowiązująca

Podczas projektowania lub refaktoryzacji kodu warstwy prezentacji:

- należy stosować **aktualne parametry API Streamlit**,  
- nie wolno stosować parametrów oznaczonych jako *deprecated*,
- należy preferować **docelowe parametry wskazane w komunikatach Streamlit**.

#### Przykład obowiązującego standardu

Zamiast:

python
st.dataframe(df, use_container_width=True)

należy stosować:
st.dataframe(df, width="stretch")

oraz zamiast:
st.dataframe(df, use_container_width=False)

należy stosować:
st.dataframe(df, width="content")

Cel decyzji
- eliminacja warningów runtime w terminalu developerskim,
- zwiększenie trwałości kodu UI względem zmian wersji Streamlit,
- ograniczenie refaktoryzacji technicznej w przyszłości,
- utrzymanie wysokiej jakości UX i stabilności aplikacji.

Zasada ta dotyczy wszystkich nowych zmian w warstwie UI Streamlit
oraz refaktoryzacji istniejących ekranów.



---


### 6. Warstwa bazy danych i bezpieczeństwo

- Dane projektu przechowywane są w lokalnej bazie **MS SQL Server Express**
- Dedykowana baza danych: `AnGG`
- Dostęp aplikacyjny realizowany przez użytkownika SQL:
  - `angg_app`
  - SQL Server Authentication
- Brak zależności od Windows Authentication w aplikacjach
- Model danych:
  - encje referencyjne (`companies`),
  - fakty czasowe (`prices_daily`),
  - dane pochodne / wskaźniki (`indicators_daily`, model wide),
  - staging ETL (`stg_prices_raw`)
  - `companies` jest zasilane jako dane referencyjne (master data) przez proces ETL w trybie INSERT-ONLY,
  z kluczem biznesowym `ticker` oraz idempotentnym uruchamianiem importu.

- Integracja:
  - Python (analiza, ML, ETL)
  - Power BI (wizualizacja)

- Aktualna struktura bazy danych:
  - Aktualna struktura tabel znajduje się w plikach znajdujących się w katalogu: AnGG\import\Struktura tabel w pliku "all_tables.sql". Jeśli potrzebujesz skorzystać z wiedzy o bazie danych, tabelach i połżczeniach to powiedz żebym dostarczył plik.


### 7. Struktura projektu Python

Projekt posiada ustaloną i obowiązującą strukturę katalogów,
opartą o separację odpowiedzialności:

- `documentation` - dokumentacja projektu
- `core` – infrastruktura (konfiguracja, DB),
- `etl` – import i przetwarzanie danych,
- `import` - dane wejściowe (CSV, ZIP, przykłady),
- `analysis` – logika analityczna i modele,
- `app` – aplikacja Streamlit (warstwa robocza),
- `notebooks` – eksperymenty i prototypy,
- `automation` – przyszła automatyzacja procesów.
- `config` – jawna parametryzacja procesów (np. ETL), wersjonowana w repozytorium

Notebooki Jupyter służą wyłącznie do eksploracji i prototypowania.
Kod produkcyjny znajduje się wyłącznie w modułach `.py`.

Struktura ta obowiązuje jako standard architektoniczny projektu
(zgodnie z ADR-002).



## Dokumentacja projektu
- Repozytorium Git zawiera pełną dokumentację:
  - ADR (szczegółowe),
  - BACKLOG,
  - PROJECT_BRIEF,
  - README
- Baza wiedzy GPT zawiera wyłącznie:
  - dokumenty strategiczne i skróty decyzyjne
  - bez szczegółowych implementacji

### Warstwa interpretacyjna i semantyka sygnałów

Projekt zawiera wydzieloną warstwę dokumentacyjną
opisującą **znaczenie biznesowo-analityczne wskaźników i sygnałów**,
niezależnie od ich implementacji technicznej.

Dokument:
- `ADR-008 – Interpretacja wskaźników i sygnałów prob`

definiuje:
- jak rozumieć wskaźniki typu *future* (`fut_imp_*`),
- jak mapują się one na sygnały (`signal_*`),
- w jaki sposób wpływają na rozkład prawdopodobieństwa (`prob`),
- jakie scenariusze rynkowe są uznawane za jakościowe.

Celem tej warstwy jest:
- zapewnienie interpretowalności analiz,
- walidacja logiczna modeli ML,
- ochrona projektu przed „czarną skrzynką decyzyjną”.

---

## Świadome ograniczenia
- Brak analizy intraday / HFT
- Brak handlu automatycznego
- Brak statusu „źródła referencyjnego” danych rynkowych
- Projekt nie jest systemem produkcyjnym
- Automatyczne harmonogramy (scheduler, cron, Airflow) nie są obecnie  elementem architektury – decyzja świadoma, odłożona do etapu stabilizacji logiki analitycznej. Docelowo planowane jest stworzenie automatyzacji importu

---

## Status
- Dokument aktualny
- Zgodny z zaakceptowanymi ADR
- Przeznaczony do dalszego rozszerzania wyłącznie przy zmianie architektury
- Warstwa core projektu została zaimplementowana i obejmuje konfigurację aplikacji oraz centralny mechanizm połączenia z bazą danych, zgodnie z ADR-002.


## Import danych rynkowych (prices_daily)

Import notowań dziennych realizowany jest przez moduł ETL `import_prices_daily`
z możliwością uruchomienia w trybie DRY-RUN.

Proces jest ręcznie inicjowany z poziomu aplikacji Streamlit,
która pełni rolę warstwy orchestracyjnej.


## Import wskaźników dziennych (indicators_daily)

Architektura ETL została rozszerzona o obsługę importu wskaźników dziennych
do tabeli `indicators_daily`.

### Charakterystyka rozwiązania

- import realizowany jest przez osobny moduł ETL:
  - `etl/import_indicators_daily.py`,
- rozwiązanie bazuje na **tych samych wzorcach architektonicznych**
  co import notowań dziennych (`prices_daily`),
- konfiguracja ścieżek i parametrów znajduje się wyłącznie w `config/etl.py`.

### Struktura katalogów

Dla wskaźników przyjęto strukturę analogiczną do notowań:

import/prd/indicators/
├── imported/
│ └── YYYY-MM-DD/
└── logs/


Zapewnia to spójność operacyjną oraz możliwość ponownego użycia
mechanizmów ETL i UI.

### Model danych

- tabela `indicators_daily` przechowuje wiele wskaźników w jednym rekordzie,
- klucz logiczny: `(company_id, trade_date)`,
- poszczególne wskaźniki są zapisywane jako osobne kolumny (np. `mv`, `pb`, `pe`),
- każda aktualizacja wskaźnika aktualizuje pole `modified_at`.

### Polityka aktualizacji wskaźników

Wskaźniki analityczne posiadają jawnie zdefiniowaną
politykę aktualizacji przechowywaną w tabeli `indicators_dictionary`:

- `update_frequency_days` – co ile dni wskaźnik powinien być aktualizowany,
- `last_updated_at` – data ostatniej aktualizacji wskaźnika.

Fundamenty (np. P/E, P/B, MV) są traktowane jako wskaźniki stanowe
i nie są aktualizowane codziennie.
Analizy dzienne korzystają z ostatniej dostępnej wartości wskaźnika.

Wykonana optymalizacja pipeline wskaźników lokalnych
(inkrementalność oparta o wartości NULL, raportowanie wykonania).



---

## Baseline danych historycznych (stan produkcyjny)

Na dzień **2026-01-10** w projekcie **Analiza GG** zakończono proces
importu danych historycznych do bazy danych (dane historyczne obejmują okres od początku notowań danej spółki do 31.12.2025 - nowsze dane będą dogrywane importami dziennymi).

Stan ten jest traktowany jako **punkt odniesienia (baseline)** dla dalszych prac analitycznych
i rozwoju funkcjonalności aplikacji.

### Zakres danych w bazie

- `companies` – **418 rekordów**
  - dane referencyjne spółek (master data),
- `prices_daily` – **1 651 027 rekordów**
  - notowania dzienne (EOD),
- `indicators_daily` – **1 378 043 rekordów**
  - wskaźniki dzienne (MV, PB, PE) w modelu wide.

Dane zostały zaimportowane z wykorzystaniem
stabilnych procesów ETL zintegrowanych z warstwą UI Streamlit,
z obsługą trybu DRY-RUN, archiwizacji i logowania.

### Konsekwencje

- dalszy rozwój projektu nie obejmuje importu pełnej historii danych,
- nowe funkcje projektowane są **na istniejącym zbiorze danych**,
- importy pełnią rolę operacyjną i utrzymaniową.



### Integracja z UI

Import wskaźników jest uruchamiany z poziomu warstwy UI (Streamlit),
z wykorzystaniem tego samego wzorca integracji ETL–UI,
co import notowań dziennych.

### Status

- logika ETL: zaimplementowana i przetestowana,
- tryb DRY-RUN: dostępny i spójny z importem notowań dziennych,
- archiwizacja plików: zaimplementowana (katalog `imported/YYYY-MM-DD`),
- integracja z UI Streamlit: zakończona,
- import wskaźników jest elementem stabilnego pipeline’u operacyjnego projektu.


###  Pipeline wskaźników - wyliczenie

Warstwa analityczna zawiera dedykowany pipeline do wyliczania wskaźników
lokalnych, z obsługą zależności, trybu DRY-RUN oraz zapisu przyrostowego
do tabeli `indicators_daily`. Pipeline może być uruchamiany z CLI,
schedulerów oraz warstwy UI.

Charakterystyka wykonania:

Pipeline wyliczania wskaźników działa w trybie inkrementalnym:

- wskaźniki liczone są sekwencyjnie zgodnie z `INDICATOR_PIPELINE`,
- zapis do bazy danych odbywa się wyłącznie dla wierszy, w których
  kolumna danego wskaźnika ma wartość `NULL`,
- pierwsze uruchomienie produkcyjne (backfill historyczny) jest
  kosztowne czasowo,
- kolejne uruchomienia produkcyjne są krótkie i obejmują jedynie:
  - nowe daty,
  - nowe spółki,
  - brakujące dane.

- `calc_flags` pełni wyłącznie funkcję informacyjną:
  odzwierciedla, które wartości wskaźników są obecne w tabeli (`NOT NULL`).
- bit = 1 → wartość wskaźnika istnieje (kolumna NOT NULL)
- bit = 0 → brak wartości wskaźnika (kolumna NULL)
- `calc_flags` nie są wykorzystywane do sterowania logiką pipeline,
  wyboru rekordów ani podejmowania decyzji obliczeniowych.


Pipeline wspiera dwa tryby wykonania:
- **DRY-RUN** – bez zapisu do bazy danych (test i walidacja),
- **REAL-RUN** – zapis inkrementalny do bazy danych.

Szczegółowe decyzje projektowe opisane są w ADR-005.

Wszystkie wskaźniki, w tym wskaźniki typu *future* (etykiety ex post),
są obsługiwane przez **jeden wspólny pipeline calculated_indicators**.
Projekt nie posiada wydzielonego modułu future.



## Dodanie nowego wskaźnika: procedura
- Dodając nowy wskaźnik, kieruj się procedurą opisaną w pliku ADR:  adr/ADR-006-Dodanie-nowego-wskaznika-procedura.md
- Jeśli nie znasz jego założeń, ZAWSZE (to bardzo ważne), poinformuj mnie o tym, abym ci przesłał jego treść do kontekstu rozmowy.
- Plik przedstawia ustandaryzowaną procedurę dodawania nowych wskaźników giełdowych do projektu *Analiza giełdowa*.
ADR-006 definiuje:
- jednolitą, powtarzalną procedurę importu nowych wskaźników,
- kanoniczną listę plików wymaganych do pracy nad nowym wskaźnikiem,
- zasady wykorzystania istniejącego pipeline wyliczeń,
- rolę i znaczenie mechanizmu `calc_flags` (informacyjnego, nie decyzyjnego),
- obsługę zależności pomiędzy wskaźnikami,
- założenie minimalizacji zmian w architekturze przy dodawaniu kolejnych wskaźników.


---

## Współpraca z AI (ChatGPT + GitHub Copilot)

# Analiza GG – Instrukcja współpracy z ChatGPT

## Rola ChatGPT
Jesteś **architektem aplikacji i systemów analityczno-danych** projektu  
**Analiza GG (AnGG)**.

Twoim zadaniem jest:
- konsultowanie zmian architektonicznych i funkcjonalnych,
- planowanie zakresu prac,
- kontrola spójności systemu,
- wsparcie projektowe **zanim** kod zostanie zmodyfikowany.

ChatGPT = architekt / reviewer / planista zmian  
GitHub Copilot (VS Code) = narzędzie wykonawcze do edycji kodu

---

## Kontekst projektu
- Projekt: **Analiza GG (AnGG)**
- Charakter: analityczno-badawczy (bez rekomendacji inwestycyjnych)
- Architektura: separacja warstw  
  **core / etl / analysis / app / (future: ml)**
- Projekt rozwijany iteracyjnie:
  - ETL i dane referencyjne
  - wskaźniki i analiza
  - moduły analityczne
  - modele ML i eksperymenty

Obowiązujące zasady:
- architektura oparta o ADR (Architecture Decision Records),
- brak „szybkich zmian” bez analizy wpływu,
- czytelna separacja odpowiedzialności między warstwami.

---

## Zasady pracy ChatGPT

1. **Najpierw architektura, potem kod**
   - najpierw analizujesz cel zmiany,
   - mapujesz wpływ na system i warstwy,
   - wskazujesz potencjalne miejsca zmian,
   - dopiero potem przechodzisz do implementacji.

2. **Mapowanie wpływu zamiast zgadywania**
   - identyfikujesz:
     - warstwy systemu,
     - pliki / moduły potencjalnie dotknięte zmianą,
     - elementy obowiązkowe vs opcjonalne.
   - jeśli brakuje kontekstu — wstrzymujesz się.

3. **Jawne instrukcje do VS Code**
   - zawsze wskazujesz dokładnie:
     - jakie pliki należy otworzyć,
     - w jakiej kolejności,
   - pliki muszą być otwarte jako zakładki (nie preview).

4. **Jawne instrukcje do GitHub Copilot**
   - generujesz gotowe prompty do Copilot Chat,
   - ograniczasz Copilota tylko do wskazanego zakresu,
   - preferujesz:
     - pracę plik po pliku,
     - tryb diff (PRZED / PO),
     - brak zmian bocznych.

5. **Kontrola spójności i regresji**
   - po zaplanowaniu zmian:
     - sprawdzasz spójność architektoniczną,
     - zgodność z ADR,
     - ryzyka techniczne i dług technologiczny.
   - wskazujesz checklistę walidacyjną przed uruchomieniem.

---

## Typowy przebieg współpracy

1. Użytkownik opisuje **cel zmiany** (bez kodu).
2. ChatGPT:
   - analizuje zmianę,
   - mapuje wpływ na projekt,
   - wskazuje pliki i kolejność prac.
3. Użytkownik otwiera wskazane pliki w VS Code.
4. ChatGPT generuje **precyzyjne prompty do GitHub Copilot**.
5. Copilot wykonuje zmiany.
6. ChatGPT wspiera walidację, porządkowanie i dokumentację (ADR / BACKLOG).

---

## Zasada nadrzędna
ChatGPT **nie jest narzędziem do „pisania kodu na ślepo”**.  
ChatGPT jest **architektem i systemowym partnerem decyzyjnym** projektu AnGG.


## Wskaźniki typu „future” (etykiety ex post)

Architektura systemu wspiera dodatkową klasę wskaźników typu **`future`**, których celem jest etykietowanie danych historycznych na podstawie przyszłych zachowań ceny.

Cechy wskaźników `future`:
- są liczone wyłącznie na danych historycznych (ex post),
- służą do analiz eksploracyjnych oraz treningu i walidacji modeli ML,
- nie są wykorzystywane operacyjnie jako sygnały decyzyjne,
- zwracają `NaN` w przypadku braku pełnego horyzontu danych.

Wskaźniki `future`:
- są liczone w tym samym pipeline’ie ETL co pozostałe wskaźniki wyliczane,
- są zapisywane w tabeli `indicators_daily`,
- są jednoznacznie oznaczone w słowniku wskaźników jako etykiety przyszłości.

Pierwsze zaimplementowane wskaźniki typu `future`:
- `fut_barrier_rs_20d` – etykieta kierunkowa (czy rynek najpierw potwierdził wzrost, czy zanegował go spadkiem),
- `fut_max_return_20d` – maksymalny potencjał wzrostowy w zdefiniowanym horyzoncie czasowym.

Wskaźniki typu *future* (etykiety opisujące przyszłe zachowanie ceny)
są zaimplementowane w module `calculated_future`.

Architektura jest **celowo identyczna** jak dla `calculated_indicators`:

- Implementacje w `calculated_future/fut/`
- Statyczny rejestr w `calculated_future/registry.py`
- Dispatcher i pipeline nie tworzą rejestrów runtime
- Dane zapisywane do tabeli typu wide (`future_daily`)
- `calc_flags` jako bitmask informujący o wyliczonych future

Celem jest maksymalna przewidywalność, łatwość rozbudowy
oraz spójność mentalna całego systemu analitycznego.


### Batchowy pipeline FUTURE

Wskaźniki typu FUTURE (etykiety / targety) są wyliczane w trybie batchowym,
analogicznie do wskaźników technicznych, z zachowaniem specyfiki horyzontu
czasowego.

Pipeline FUTURE składa się z trzech etapów:

1. **Batch fetch danych cenowych**
   - `fetch_prices_bulk()`
   - jeden odczyt dla wielu spółek
   - chunkowanie po `company_id`

2. **Batch compute**
   - pętla po `company_id`,
   - obliczenia wektorowe,
   - brak dostępu do DB w trakcie obliczeń.

3. **Batch write**
   - INSERT brakujących rekordów do `future_daily`,
   - UPDATE per `future_code`,
   - bitowe oznaczanie `calc_flags` (BIGINT),
   - pełna idempotencja.

Tryb batchowy jest wykorzystywany wyłącznie do backfilli i procesów
hurtowych. Tryb punktowy pozostaje dostępny dla debugowania i bieżących
aktualizacji.





## Globalny kontekst spółki i warstwa interpretacyjna UI

### Rola globalnego kontekstu

Architektura aplikacji AnGG rozróżnia:

- **dane i analizy cząstkowe** (trend, momentum, zmienność, ryzyko, future),
- **warstwę interpretacyjną**, której celem jest szybkie zrozumienie
  *w jakim środowisku rynkowym znajduje się spółka*.

Warstwa interpretacyjna **nie generuje sygnałów transakcyjnych**
i **nie prognozuje przyszłości**.

---

### Globalne podsumowanie sytuacji spółki

Na ekranie „Przegląd danych” wprowadzono wydzieloną sekcję:

**Globalne podsumowanie sytuacji spółki**, która:

- syntetyzuje wnioski z wielu analiz jednospołkowych,
- jest renderowana **na górze widoku analitycznego**,
- korzysta wyłącznie z danych zawartych w `df_market`,
- nie wykonuje niezależnych obliczeń poza regułową agregacją stanu.

Decyzja o umieszczeniu tej sekcji na górze jest **świadomą decyzją UX**:
> najpierw kontekst, potem szczegóły.

---

### Znacznik stanu ogólnego spółki (🟢🟡🔴)

W ramach globalnego podsumowania wprowadzono
**znacznik stanu ogólnego spółki**, liczony regułowo na podstawie:

- trendu długoterminowego,
- momentum,
- zmienności względem historii,
- wolumenu jako potwierdzenia ruchu.

Znacznik przyjmuje wartości:

- 🟢 **kontekst sprzyjający**
- 🟡 **kontekst niejednoznaczny**
- 🔴 **kontekst niesprzyjający**

Znacznik:
- jest **deskryptywny**, nie decyzyjny,
- oparty wyłącznie na danych historycznych,
- służy orientacji poznawczej użytkownika.

---

### Spójne nagłówki sekcji analitycznych

Wszystkie sekcje analiz jednospołkowych stosują jednolity schemat nagłówków:
<TICKER> (<PEŁNA NAZWA>) – <Nazwa sekcji>


Nagłówki:
- mają kolor zgodny z globalnym kontekstem spółki,
- wzmacniają ciągłość poznawczą użytkownika,
- eliminują wrażenie „oderwanych” analiz.

Jest to element **warstwy UX**, nie logiki analitycznej.

---

### Kolejność renderowania vs kolejność interpretacji

Architektura rozróżnia:

- **kolejność renderowania komponentów UI**
- **kolejność logicznej interpretacji informacji przez użytkownika**

Globalny kontekst:
- może być obliczany wcześniej,
- prezentowany wyżej,
- mimo że logicznie korzysta z wyników analiz szczegółowych.

Jest to **celowa decyzja architektoniczna**, a nie ograniczenie techniczne.



##  Selekcja sygnałów ML – podejście rankingowe (ML-01)

Na etapie **ML-01** modele ML są traktowane jako **mechanizmy rankingowe**, a nie klasyfikatory binarne.

Celem selekcji sygnałów jest:
- maksymalizacja **trafności (precision)**,
- minimalizacja liczby **fałszywych alarmów (FP)**,
- akceptacja niskiego recall (pomijanie części prawdziwych zdarzeń),
- brak wymogu generowania sygnałów w każdym okresie.

#### Kanoniczna logika selekcji (ML-01)

Selekcja sygnałów odbywa się dwuetapowo, w obrębie okna czasowego
zdefiniowanego w liczbie sesji handlowych:

1. **Selekcja ilościowa (rankingowa)**  
   Wybór maksymalnie `K` obserwacji o najwyższym score (`prob`).

2. **Selekcja jakościowa (rankingowa)**  
   Odrzucenie dolnej części rankingu poprzez zachowanie wyłącznie
   `top_score_pct` najlepszych obserwacji.

Dopuszczalne jest, że po filtracji:
- liczba sygnałów < `K`,
- liczba sygnałów = 0 (brak wystarczająco jakościowych setupów).

#### Parametry kanoniczne (konfigurowalne)

- `window_sessions` – liczba sesji w oknie rankingowym,
- `max_signals` – maksymalna liczba kandydatów (Top-K),
- `top_score_pct` – procent najlepszych obserwacji uznawanych za jakościowe.

Filtr oparty o **ranking (`top_score_pct`)** został wybrany zamiast
stałego progu prawdopodobieństwa (`min_prob`), ponieważ:
- nie zależy od kalibracji score,
- jest stabilny w różnych reżimach rynkowych,
- wspiera elitarną selekcję setupów.

Rozwiązanie ma charakter **eksperymentalny (ML-01)** i stanowi
przygotowanie pod przyszłą warstwę decyzyjną.

### Warstwa ML (kontrakt datasetów i eksperymenty ML-01)

Warstwa ML działa na kanonicznych datasetach budowanych centralnie:
- `df_market_train`, `df_market_validation`, `df_market_test`,
z globalnym time-based split (TRAIN/VALIDATION/TEST) o niezmiennych rolach.

Modele ML w etapie ML-01 są używane eksploracyjnie i interpretowalnie:
- wyjście modelu jest traktowane jako score / `prob` (ranking),
- selekcja sygnałów odbywa się kanonicznie Top-K → Top-Pct.

Szczegóły: `ADR-012 – Warstwa ML: datasety, eksperymenty ML-01 i prob`.
