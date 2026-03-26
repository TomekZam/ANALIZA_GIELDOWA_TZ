# ADR-002 – Zarządzanie środowiskiem i warstwa prezentacji (Streamlit)

- Status: Accepted
- Data: 2026-01-02
- Zakres: Środowisko uruchomieniowe projektu, warstwa UI

## Kontekst
Projekt „Analiza giełdowa” rozwijany jest w Pythonie, z wykorzystaniem analizy danych
oraz planowaną warstwą prezentacji wyników w formie dashboardu.

Konieczne było:
- ustalenie standardu zarządzania zależnościami,
- rozdzielenie logiki analitycznej od warstwy prezentacji.

## Decyzje

1. **Conda** jest standardowym menedżerem środowiska projektu.
2. Jedynym źródłem prawdy o zależnościach jest plik **`environment.yml`**.
   - `requirements.txt` nie jest używany.
3. Warstwa prezentacji wyników analizy realizowana jest z użyciem **Streamlit**.
4. Streamlit pełni wyłącznie rolę **UI / prezentacyjną**:
   - brak logiki analitycznej w plikach aplikacji Streamlit,
   - analiza danych realizowana w osobnych modułach.

## Konsekwencje
- Środowisko projektu jest w pełni odtwarzalne.
- Repozytorium nie zawiera środowisk lokalnych ani sekretów.
- Architektura projektu zachowuje separację: dane → analiza → prezentacja.

# Git i GitHub jako system kontroli wersji projektu

## Kontekst

Projekt **Analiza GG** rozwijany jest iteracyjnie, z naciskiem na:
- dokumentację decyzji,
- możliwość cofania zmian,
- śledzenie historii rozwoju koncepcji analitycznych,
- przyszłą rozbudowę o kod, dane i automatyzację.

Na wczesnym etapie projektu konieczne było podjęcie decyzji dotyczącej
systemu kontroli wersji oraz sposobu synchronizacji pracy lokalnej z repozytorium zdalnym.

---

## Decyzja

Jako system kontroli wersji projektu przyjęto:

- **Git** – do lokalnego zarządzania historią zmian,
- **GitHub** – jako zdalne repozytorium projektu.

Repozytorium projektu:
- jest prowadzone jako repozytorium prywatne,
- posiada główny branch `main`,
- zawiera dokumentację jako kluczowy artefakt projektu.

---

## Uzasadnienie

Wybór Git + GitHub został dokonany ze względu na:
- powszechność i dojrzałość narzędzia,
- możliwość pracy iteracyjnej i eksperymentalnej,
- pełną historię zmian i decyzji,
- naturalne wsparcie dla dokumentacji (Markdown),
- możliwość przyszłego wykorzystania:
  - branchy,
  - pull requestów,
  - code review,
  - automatyzacji (CI/CD).

---

## Konsekwencje

- Każda istotna zmiana w projekcie jest commitowana.
- Decyzje projektowe są dokumentowane w ADR i wersjonowane.
- Repozytorium stanowi „single source of truth” dla projektu.
- Projekt jest gotowy do skalowania o:
  - kod analityczny,
  - pipeline danych,
  - automatyzację analiz.

---

## Uwagi

- System kontroli wersji nie służy do przechowywania danych wrażliwych.
- Pliki konfiguracyjne zawierające sekrety (np. `.env`) są ignorowane przez Git.






# ADR – Warstwa bazy danych i bezpieczeństwo

- Status: Accepted
- Data: 2026-01-04
- Zakres: Warstwa danych, persistence, bezpieczeństwo dostępu
- Powiązane: ADR-001 (import danych), ADR-002 (środowisko i UI)

---

## Kontekst

Projekt „Analiza giełdowa (AnGG)” wymaga:
- lokalnego, trwałego repozytorium danych rynkowych,
- obsługi importu hurtowego oraz aktualizacji przyrostowych,
- integracji z Python (analiza, ML) oraz Power BI (wizualizacja),
- kontroli dostępu niezależnej od konta systemowego użytkownika.

Dotychczas brakowało formalnej decyzji architektonicznej
dotyczącej warstwy bazy danych oraz modelu bezpieczeństwa.

---

## Decyzja

1. Jako warstwę persistence danych zastosowano:
   **Microsoft SQL Server Express (lokalnie)**.

2. Dane projektu przechowywane są w dedykowanej bazie danych:
   **`AnGG`**.

3. Dostęp aplikacyjny do bazy realizowany jest przez:
   - dedykowany login i user SQL Server: **`angg_app`**,
   - uwierzytelnianie typu **SQL Server Authentication**,
   - brak użycia Windows Authentication w aplikacjach.

4. Użytkownik `angg_app` posiada:
   - pełne uprawnienia w obrębie bazy `AnGG` (`db_owner`),
   - brak uprawnień administracyjnych do instancji serwera.

5. Schemat danych oparto o:
   - klucze zastępcze (surrogate keys) dla encji,
   - klucze logiczne dla faktów czasowych,
   - separację danych referencyjnych, faktów i danych pochodnych.

---

## Struktura logiczna bazy danych

### 1. `companies`
Dane referencyjne spółek.

- `company_id` (PK, INT, IDENTITY)
- `ticker` (VARCHAR, UNIQUE)
- `company_name`
- `market`
- `is_active`
- `created_at`

---

### 2. `prices_daily`
Notowania dzienne (EOD).

- klucz logiczny: **(company_id, trade_date)**
- `open_price`
- `high_price`
- `low_price`
- `close_price`
- `volume`
- `source_ticker` (kolumna techniczna – audyt importu)
- `created_at`

Relacja:
- `prices_daily.company_id → companies.company_id`

---

### 3. `indicators_daily` 
Wskaźniki techniczne / cechy analityczne liczone **per notowanie**.

**Model przechowywania wskaźników (ADR-009)**

Tabela `indicators_daily` opisana zgodnie z ADR-009.

Aktualny model:
- `companies` – dane referencyjne
- `prices_daily` – notowania dzienne (EOD)
- `indicators_daily` – wskaźniki analityczne (model wide (1 rekord = 1 spółka × 1 dzień))
- `stg_prices_raw` – staging ETL
 
---

### 4. `stg_prices_raw`
Tabela stagingowa do importu danych CSV/TXT.

- dane w formacie tekstowym (VARCHAR),
- wykorzystywana wyłącznie w procesie ETL,
- brak relacji biznesowych.

---

### 5. Widok: `vw_prices_with_indicators`

Widok analityczny łączący:
- spółki,
- notowania,
- wskaźniki.

Przeznaczenie:
- Power BI,
- eksploracja danych,
- zapytania analityczne.

---

## Bezpieczeństwo

- Loginy aplikacyjne są niezależne od kont systemowych.
- Hasła nie są przechowywane w repozytorium:
  - wykorzystywane są zmienne środowiskowe (`.env`).
- Uprawnienia serwerowe i bazodanowe są rozdzielone:
  - `sa` / admin → zarządzanie instancją,
  - `angg_app` → praca wyłącznie w bazie `AnGG`.

---

## Konsekwencje

### Pozytywne
- powtarzalność i odtwarzalność środowiska,
- bezpieczna integracja z Python i Power BI,
- brak zależności od konta Windows,
- gotowość pod dalszą automatyzację.

### Ograniczenia
- limit 10 GB (SQL Server Express),
- brak mechanizmów HA / DR (akceptowalne lokalnie).

---

## Status

Decyzja zaakceptowana i wdrożona.
Struktura bazy danych oraz model bezpieczeństwa obowiązują
jako standard projektu.






# ADR – Struktura projektu Python i separacja odpowiedzialności

- Status: Accepted
- Data: 2026-01-04
- Zakres: Struktura repozytorium, organizacja kodu Python, separacja warstw
- Powiązane: ADR-002 (środowisko i UI), ADR-003 (baza danych)

---

## Kontekst

Projekt „Analiza giełdowa (AnGG)” rozwijany jest jako projekt analityczno-badawczy,
który będzie obejmował:

- import danych (ETL),
- analizę danych (wskaźniki, ML),
- warstwę prezentacji (Streamlit),
- automatyzację procesów w przyszłości.

Na wczesnym etapie projektu konieczne było formalne ustalenie:
- struktury katalogów,
- odpowiedzialności poszczególnych warstw,
- zasad organizacji kodu Python,
aby uniknąć chaosu i trudności w dalszym rozwoju projektu.

---

## Decyzja

Przyjęto następującą, obowiązującą strukturę logiczną projektu:

AnGG/
├── app/ # aplikacja Streamlit (UI / backend roboczy)
├── core/ # infrastruktura: konfiguracja, DB
├── etl/ # import danych (startowy i bieżący)
├── analysis/ # wskaźniki, feature engineering, ML
├── notebooks/ # eksperymenty i prototypy (Jupyter)
├── automation/ # przyszłe joby / harmonogramy
├── import/ # dane wejściowe (CSV, ZIP, przykłady)
└── documentation/ # dokumentacja projektu (ADR, backlog, brief)



---

## Zasady architektoniczne

### 1. Separacja odpowiedzialności
- `core`:
  - konfiguracja (`.env`),
  - połączenie z bazą danych,
  - brak logiki biznesowej.
- `etl`:
  - import danych,
  - staging,
  - walidacja i zapisy do DB.
- `import`:
  - miejsce na dane wejściowe (CSV, ZIP, przykłady),
- `analysis`:
  - logika analityczna,
  - wskaźniki,
  - modele ML.
- `app`:
  - Streamlit jako warstwa robocza / prezentacyjna,
  - brak logiki ETL i analitycznej.
- `notebooks`:
  - eksploracja i eksperymenty,
  - kod tymczasowy, nieprodukcyjny.
- `automation`:
  - miejsce na przyszłą automatyzację (scheduler, joby).
- `documentation`:
  - miejsce na dokumentację

  
---

### 2. Zależności między warstwami

Dozwolone kierunki zależności:

- `app` → `core`, `etl`, `analysis`
- `etl` → `core`
- `analysis` → `core`
- `core` → brak zależności

Zabronione:
- importowanie logiki biznesowej do `core`,
- zapytania SQL bezpośrednio w warstwie `app`.

---

### 3. Notebooki (Jupyter)

- Notebooki służą wyłącznie do:
  - eksploracji danych,
  - prototypowania wskaźników.
- Notebooki **nie są częścią aplikacji produkcyjnej**.
- Sprawdzona logika z notebooków powinna być:
  → refaktoryzowana do modułów `.py` w `analysis`.

---

### 4. Organizacja kodu Python

- Każdy moduł ma jedną, jasno określoną odpowiedzialność.
- Unika się plików typu `utils.py` o niejasnym zakresie.
- Entry point aplikacji Streamlit znajduje się w `app/app.py`.

---

## Konsekwencje

### Pozytywne
- czytelna i skalowalna struktura projektu,
- łatwiejsze utrzymanie porządku w kodzie,
- możliwość rozwoju projektu bez refaktoryzacji całej struktury.

### Ograniczenia
- większy narzut organizacyjny na początku projektu,
- konieczność trzymania się ustalonych zasad.

---

## Status

Decyzja zaakceptowana.
Struktura katalogów i zasady organizacji kodu obowiązują
jako standard projektu.






# ADR – Warstwa core: konfiguracja i połączenie z bazą danych

- Status: Accepted
- Data: 2026-01-05
- Zakres: core / konfiguracja / połączenie DB
- Powiązane:
  - ADR-003 – Baza danych i bezpieczeństwo
  - ADR-004 – Struktura projektu Python i separacja odpowiedzialności

---

## Kontekst

Projekt „Analiza giełdowa (AnGG)” osiągnął etap,
w którym konieczne było przejście od decyzji architektonicznych
do realnej implementacji infrastruktury aplikacyjnej.

Brakowało:
- stabilnego mechanizmu konfiguracji aplikacji,
- jednego, centralnego punktu połączenia Python ↔ MS SQL Server,
- empirycznej weryfikacji środowiska uruchomieniowego.

---

## Decyzja

1. Zaimplementowano moduł `core/config.py`, odpowiedzialny za:
   - wczytywanie konfiguracji z pliku `.env`,
   - walidację wymaganych zmiennych środowiskowych,
   - przerywanie działania aplikacji w przypadku braków konfiguracyjnych (fail fast).

2. Zaimplementowano moduł `core/db.py`, który:
   - buduje connection string do MS SQL Server (SQL Server Authentication),
   - udostępnia funkcję `get_engine()` opartą o SQLAlchemy,
   - udostępnia funkcję `test_connection()` do weryfikacji środowiska.

3. Połączenie Python ↔ MS SQL Server Express zostało:
   - uruchomione w środowisku Conda (`analiza_gg`),
   - przetestowane zapytaniem `SELECT 1`,
   - potwierdzone jako stabilne.

---

## Konsekwencje

### Pozytywne
- projekt posiada stabilny fundament infrastrukturalny,
- wszystkie warstwy korzystają z jednego mechanizmu DB,
- sekrety i konfiguracja są odseparowane od repozytorium,
- możliwa jest dalsza implementacja ETL i analizy.

### Ograniczenia
- brak strojenia poolingu połączeń,
- brak mechanizmów retry i obserwowalności (świadomie odłożone).

---

## Status

Decyzja zaakceptowana i zweryfikowana empirycznie.
Warstwa `core` uznana za gotową.


## Centralne parametry aplikacyjne (`config/app_params.py`)

### Status
Accepted (doprecyzowanie decyzji)

### Kontekst

Wraz z rozwojem warstwy UI (Streamlit) oraz logiki analitycznej pojawiła się potrzeba
posiadania **jawnych, wersjonowanych parametrów aplikacyjnych**, które:

- nie są sekretami środowiskowymi,
- nie są parametrami pojedynczego procesu ETL,
- wpływają na **zachowanie aplikacji** (UI / tryby działania),
- powinny być spójne w całym projekcie.

Dotychczas:
- `.env` służył wyłącznie do sekretów i konfiguracji środowiskowej,
- `config/etl.py` zawierał parametry procesów ETL.

Brakowało miejsca na **parametry aplikacyjne** o charakterze globalnym.

---

### Decyzja

Wprowadzono centralne repozytorium parametrów aplikacyjnych:
config/app_params.py


Zasady:

1. `config/app_params.py` zawiera:
   - jawne,
   - wersjonowane,
   - read-only
   parametry aplikacyjne.

2. Parametry aplikacyjne:
   - są dostępne wyłącznie przez funkcję:
     python:
     get_param(name: str) -> Any
     
   - nie są importowane bezpośrednio jako zmienne globalne.

3. Brak parametru:
   - powoduje jawny błąd (`KeyError`),
   - brak wartości domyślnych typu „fallback” (fail fast).

4. `config/app_params.py` **nie zastępuje**:
   - `.env` (sekrety, DB, środowisko),
   - `config/etl.py` (parametry procesów ETL).

---

### Przykładowe zastosowania

- domyślne zachowanie UI (np. DRY-RUN zaznaczony / niezaznaczony),
- limity prezentacyjne (page size, max rows),
- flagi feature’ów (eksperymentalne sekcje UI),
- parametry sterujące trybem pracy aplikacji.

Przykład:

python:
from config.app_params import get_param

dry_run_default = get_param("UI_DEFAULT_DRY_RUN")

## Zasada rozszerzania (ważne)

Jeśli w trakcie dalszych prac projektowych lub analitycznych pojawi się informacja, która:

- ma charakter globalnego parametru aplikacji,
- wpływa na zachowanie UI / analizy / trybu pracy,
- nie jest sekretem ani parametrem ETL,

to należy rozważyć dodanie jej do:
config/app_params.py


W takich przypadkach:

- ChatGPT (asystent architektoniczny projektu) ma obowiązek zaproponować
  umieszczenie tej informacji w `config/app_params.py`,
- decyzja o dodaniu parametru jest świadoma i wersjonowana w repozytorium.

---

## Konsekwencje

### Pozytywne

- jedno źródło prawdy dla parametrów aplikacyjnych,
- brak „magic numbers” i hard-coded flag w UI,
- łatwa kontrola zmian w Git,
- czytelna separacja:
  - `.env` → sekrety / środowisko,
  - `config/etl.py` → ETL,
  - `config/app_params.py` → aplikacja.

### Ograniczenia

- parametry są statyczne w czasie działania aplikacji,
- zmiana wymaga restartu aplikacji (akceptowalne w MVP).






# ADR – Język i nazewnictwo dokumentów ADR

- Status: Accepted
- Data: 2026-01-05
- Zakres: dokumentacja architektoniczna (ADR)
- Powiązane: wszystkie istniejące ADR

---

## Kontekst

Dokumenty ADR w projekcie „Analiza giełdowa (AnGG)” pełnią rolę:
- dokumentacji decyzyjnej,
- narzędzia porządkującego wiedzę projektową,
- notatek roboczych dla właściciela projektu.


---

## Decyzja

1. Od momentu przyjęcia niniejszego ADR:
   - **wszystkie dokumenty ADR mają nazwy w języku polskim**.

2. Dotyczy to:
   - nazw plików (`ADR-XXX-<opis>.md`),
   - tytułów dokumentów (`# ADR-XXX – …`).

3. Językiem dokumentów ADR jest:
   - **język polski**,
   - styl opisowy, techniczny, zrozumiały dla autora projektu.

4. Istniejące dokumenty ADR:
   - podlegają **jednorazowej normalizacji nazw**,
   - bez zmiany ich merytorycznej treści.

---

## Konsekwencje

### Pozytywne
- spójność dokumentacji,
- lepsza czytelność i orientacja,
- jasny standard na przyszłość.

### Ograniczenia
- konieczność zmiany nazw istniejących plików (jednorazowo).

---

## Status

Decyzja zaakceptowana.
Obowiązuje dla wszystkich przyszłych i istniejących dokumentów ADR.


---



## Rozszerzenie: Kontrolki zaawansowanej prezentacji danych

### Decyzja
Warstwa prezentacji Streamlit została rozszerzona o:
- komponent **AG Grid (`streamlit-aggrid`)**,
- centralne słowniki metadanych UI (`column_metadata.py`),
- systemowe grupowanie kolumn.

### Uzasadnienie
Standardowe `st.dataframe` nie spełniało wymagań:
- dynamiczny wybór kolumn,
- duże zbiory danych,
- czytelna eksploracja wskaźników.

AG Grid zapewnia:
- dojrzałą tabelę analityczną,
- wydajność,
- elastyczność UI.

### Konsekwencje
- `streamlit-aggrid` jest zależnością obowiązkową środowiska,
- wszystkie mapowania nazw i grup kolumn są scentralizowane,
- UI nie ingeruje w logikę danych.




## Lista dostępnych kolumn analitycznych (do wykorzystania w analizach)

### Kolumny dostępne w df_market

#### Identyfikacja
- company_id
- ticker
- company_name
- name

#### Notowania (EOD)
- trade_date
- open_price
- high_price
- low_price
- close_price
- volume

#### Fundamenty
- mv
- pe
- pb
- earnings_yield

#### Momentum / ryzyko
- momentum_12m
- volatility_20d
- sharpe_20d
- max_drawdown_252d

#### Trendy
- sma_20, sma_50, sma_200
- ema_12, ema_20, ema_26, ema_50, ema_200

#### Oscylatory
- rsi_14
- macd_line
- macd_signal
- macd_hist

#### Wolumen / zmienność
- average_volume_20d
- obv
- vwap_20d
- atr_14

#### Jakość / scoring
- tqs_60d

#### Future / ML
- fut_imp_2, fut_imp_20, fut_imp_60, fut_imp_120
- fut_signal_2, fut_signal_20, fut_signal_60, fut_signal_120, fut_signal_20_hyb
- fut_barrier_* (różne horyzonty)



## Tryby pracy aplikacji (DEMO / DEV)

Doprecyzowano sposób sterowania trybem pracy aplikacji AnGG.

- tryb DEMO oraz DEV są kontrolowane przez parametry aplikacyjne,
- decyzja o trybie pracy **nie jest podejmowana na podstawie `.env`**,
- `.env` służy wyłącznie do sekretów i konfiguracji środowiskowej.

Szczegóły oraz aktualny kontrakt konfiguracyjny opisane są w:
- `ARCHITECTURE_SUMMARY.md` – sekcja „Tryby pracy aplikacji (DEMO / DEV)”.



## Decyzja: przeniesienie parametru APP_MODE z pliku `.env` do `app_params.py`

### Status
Zaakceptowana

### Kontekst
We wcześniejszych wersjach aplikacji tryb pracy (`APP_MODE=DEMO | DEV`) był konfigurowany
poprzez zmienną środowiskową w pliku `.env`.

W praktyce powodowało to:
- dodatkowy krok konfiguracyjny przy instalacji DEMO,
- ryzyko uruchomienia aplikacji w niezamierzonym trybie (np. DEV zamiast DEMO),
- zależność działania aplikacji od pliku zewnętrznego, który nie był częścią repozytorium.

### Decyzja
Parametr `APP_MODE` został **przeniesiony do pliku konfiguracyjnego aplikacji**
`config/app_params.py` i ustawiony jawnie na wartość:

python
"APP_MODE": "DEMO"

## Wersja DEMO aplikacji

- nie wymaga pliku `.env`,
- działa zawsze w trybie CSV,
- nie inicjalizuje połączenia z bazą danych.

## Uzasadnienie

- uproszczenie instalacji i uruchomienia wersji DEMO,
- eliminacja zależności od zmiennych środowiskowych,
- jednoznaczne, deterministyczne zachowanie aplikacji,
- lepsza czytelność i przewidywalność konfiguracji runtime.

## Konsekwencje

- plik `.env` nie jest wymagany w wersji DEMO,
- zmiana trybu pracy aplikacji wymaga modyfikacji kodu  
  (świadoma decyzja projektowa),
- wersja DEV/PROD może nadal używać innego mechanizmu konfiguracji,  
  jeśli zajdzie taka potrzeba.
