# Informacje podstawowe
Tytuł projektu: Analiza giełdowa
Typ projektu: Analityka biznesowo‑systemowa / finansowa
Status: w toku
Właściciel merytoryczny: Analityk biznesowo‑systemowy

# Cel projektu
Celem projektu jest zebranie, uporządkowanie oraz analiza informacji o spółkach giełdowych w celu:
- lepszego zrozumienia kondycji finansowej spółek,
- identyfikacji trendów rynkowych widocznych na wykresach,
- oceny atrakcyjności inwestycyjnej spółek na podstawie wskaźników finansowych i technicznych,
- wypracowania powtarzalnego i dobrze udokumentowanego podejścia do analizy giełdowej.
Projekt ma charakter analityczno‑badawczy i może być podstawą do budowy narzędzi, modeli lub aplikacji wspierających analizę.

# Zakres projektu

## W zakresie (IN):
- analiza fundamentalna spółek giełdowych,
- analiza techniczna (trendy, formacje, wolumen, momentum),
- porównywanie spółek w obrębie sektora,
- identyfikacja kluczowych wskaźników (finansowych i rynkowych),
- dyskusja nad metodologiami analizy,
- praca na danych historycznych oraz punktowych danych bieżących,
- projektowanie struktury danych i logiki analitycznej.
- wizualizacja wyników analizy w formie dashboardów (Streamlit),
- projektowanie warstwy prezentacji oddzielonej od logiki analitycznej.
- interpretacja sygnałów probabilistycznych (`prob`)
  w oparciu o historyczne etykiety future i sygnały pochodne,
- budowa interpretowalnej logiki przejścia:
  dane historyczne → sygnały → prawdopodobieństwo → analiza.


## Poza zakresem (OUT):
- rekomendacje inwestycyjne typu „kup/sprzedaj” w sensie doradztwa finansowego,
- handel automatyczny w czasie rzeczywistym,
- analiza intraday o wysokiej częstotliwości.

# Kontekst biznesowy
Projekt ma charakter edukacyjno‑analityczny. Może być wykorzystywany do:
- własnych analiz inwestycyjnych,
- rozwoju kompetencji analitycznych (BA/DA/AI),
- testowania źródeł danych giełdowych,
- przygotowania koncepcji aplikacji analitycznej lub dashboardów.
Projekt kładzie nacisk nie tylko na generowanie sygnałów,
ale również na ich **zrozumienie, walidację i interpretację**,
co zostało udokumentowane w ADR-008.

# Użytkownicy i role
- Analityk – przygotowuje i interpretuje analizy spółek.
- Użytkownik końcowy (ja) – konsumuje wyniki analiz, porównania i wnioski.
- System / narzędzie analityczne – przetwarza dane, liczy wskaźniki, wizualizuje trendy.

# Kluczowe obszary analizy
Fundamentalne:
- przychody, zyski, marże,
- zadłużenie i płynność,
- cash flow,
- wskaźniki: P/E, P/BV, ROE, ROA, EV/EBITDA.
Techniczne:
- trend (krótki/średni/długi termin),
- wsparcia i opory,
- średnie kroczące,
- RSI, MACD, wolumen,
- formacje cenowe.

# Źródła danych (robocze)
- dane giełdowe GPW (spółki i indeksy i rynków zagranicznych ale tylko w obszarze głównych zagranicznych indeksów i kilku kluczowych spółek z rynku w USA),
- notowania historyczne (OHLC),
- raporty finansowe spółek,
- dane sektorowe i makroekonomiczne.
Źródła będą oceniane pod kątem dostępności, kosztu, kompletności i aktualności.

# Założenia i ograniczenia
- Analizy mają charakter informacyjny i edukacyjny.
- Dane mogą pochodzić z różnych źródeł o różnej jakości.
- Preferowane są rozwiązania możliwe do automatyzacji w przyszłości.
- Analiza nie musi działać w czasie rzeczywistym.
- Projekt wykorzystuje środowisko Python zarządzane przez Conda.
- Zależności projektu definiowane są wyłącznie w pliku environment.yml.
- Sekrety i konfiguracja lokalna przechowywane są poza repozytorium (.env).
- Projekt posiada ustalone fundamenty architektoniczne,
opisane w ADR-002 – Fundamenty architektury projektu AnGG
oraz w dokumencie ARCHITECTURE_SUMMARY.md.



# Pozyskiwanie danych źródłowych
- Prowadzimy rozmowy na temat możliwości pozyskania dancyh historycznych i bieżących w zakresie notowań giełdowych, szukając miejsca w internecie z których można pobrać takie dane w postaci zaczytania plików lub zautomatyzowania procesu za pomocą API
- Rozpatrzenie jakie są zasady pobierania tych danych (zakres danych, koszty, ograniczenia, regulamin, ważne blokady uniemożliwiające łatwe pobieranie tych danych),
- Możliwości wykorzystania pobranych informacji na potrzeby ich ewentualnej dalszej analizy za pomocą aplikacji stworzonej z wykorzystaniem języka programowania Python


# Standard pracy z ChatGPT
- Odpowiedzi strukturalne i analityczne.
- Wyraźne oddzielanie faktów od interpretacji.
- Każda większa decyzja → wpis do ADR.
- Otwarte pytania → backlog.

## Źródła danych (v1)
Podstawowym źródłem danych rynkowych (MVP) jest serwis stooq.pl,
zgodnie z ADR-001 – Strategia importu danych i ETL.



# Architecture Decision Records (ADR)

Ten dokument zawiera rejestr decyzji architektonicznych
podjętych w projekcie „Analiza giełdowa”.

---

## Zasada konsolidacji decyzji architektonicznych

Dla każdej zaakceptowanej decyzji architektonicznej (ADR) jej **skrót merytoryczny**
powinien zostać uwzględniony w pliku:

**ARCHITECTURE_SUMMARY.md**

Plik ten pełni rolę:
- skondensowanego przeglądu architektury projektu,
- źródła kontekstu wysokiego poziomu (np. dla AI / onboarding),
- uzupełnienia szczegółowych ADR, bez ich duplikowania.

Szczegóły implementacyjne i pełne uzasadnienia pozostają wyłącznie w plikach ADR.


## ADR-001 – Strategia importu danych i ETL

### Stooq jako podstawowe źródło danych do importu
- Status: Accepted
- Zakres: Dane rynkowe (EOD OHLCV)
- Plik ADR: adr/ADR-001-Strategia_importu_danych_i_ETL.md

**Decyzja**
- Jako podstawowe źródło danych rynkowych projektu (MVP) wybrano **stooq.pl**.

**Zakres danych**
- Dane dzienne (EOD): Open, High, Low, Close, Volume.
- Pełne szeregi czasowe dla:
  - spółek GPW,
  - indeksów giełdowych (GPW i zagranicznych),
  - wybranych instrumentów zagranicznych (akcje, waluty, surowce).

**Format i dostęp**
- Format: CSV
- Dostęp: publiczny, bez autoryzacji
- Transport: HTTP

**Strategia importu**
- Podejście: **„pełna historia + lokalna kontrola danych”**.
- Import polega na:
  - pobraniu pełnej historii instrumentu w jednym pliku CSV,
  - zapisie danych lokalnie,
  - deduplikacji rekordów,
  - identyfikacji i uzupełnianiu luk czasowych po stronie projektu.
- Projekt nie korzysta z inkrementalnych zapytań ani filtrowania zakresów dat po stronie Stooq.

**Import masowy GPW**
- Dane GPW pobierane są jako paczka:
  - `d_pl_txt.zip` (Daily / ASCII).
- Po rozpakowaniu:
  - spółki GPW znajdują się w katalogu `d_pl_txt/data/daily/pl/wse stocks`,
  - każda spółka zapisana jest w osobnym pliku,
  - nazwa pliku (bez rozszerzenia) stanowi **symbol instrumentu**.

**Endpoint danych pojedynczego instrumentu**
- Wykorzystywany wyłącznie endpoint:
  - `https://stooq.com/q/d/l/?s=<symbol>&i=d`
- Endpoint zwraca pełną historię danych dziennych (EOD) i jest stabilny przy pobieraniu całych szeregów.

**Konwencja symboli**
- Projekt używa wyłącznie **natywnych symboli Stooq** (np. `pkn`, `ccc`, `aapl.us`).
- Symbole w formatach GPW / Yahoo / Bloomberg nie są stosowane (skutkują pustą odpowiedzią CSV).

**Metadane**
- Lista tickerów generowana jest lokalnie na podstawie katalogu `wse stocks`.
- Mapowanie `symbol → pełna nazwa spółki` przechowywane jest jako dane referencyjne, oddzielone od danych OHLCV.

**Ograniczenia**
- Brak jawnych danych o splitach i dywidendach.
- Stooq nie posiada statusu oficjalnego źródła referencyjnego.
- Walidacja względem danych GPW przewidziana jako etap kolejny.




### Import spółek do tabeli companies: strategia INSERT-ONLY
- Zakres: Język i nazewnictwo dokumentów ADR
- Decyzja definiuje politykę zasilania danych referencyjnych spółek w tabeli companies w trybie INSERT-ONLY. Import jest idempotentny, oparty o klucz biznesowy ticker i celowo nie aktualizuje istniejących rekordów, minimalizując ryzyko niekontrolowanych zmian danych master.


### Konfiguracja ETL: parametry w `config/`, sekrety w `.env`
- Zakres: Język i nazewnictwo dokumentów ADR
- ADR rozdziela konfigurację środowiskową (sekrety, DB) od parametrów operacyjnych procesów ETL. Sekrety pozostają w .env, natomiast wszystkie jawne parametry ETL (ścieżki, tryby pracy) są wersjonowane w config/, co zwiększa przejrzystość i powtarzalność pipeline’ów.




### Wzorzec integracji UI Streamlit z procesami ETL
- Decyzja definiuje spójny wzorzec uruchamiania procesów ETL z poziomu UI Streamlit. UI pełni rolę orkiestratora, wywołując funkcje ETL bez implementowania logiki biznesowej oraz prezentując parametry, postęp i podsumowanie importów.
- Optymalizacja pipeline wskaźników lokalnych (calc_flags, inkrementalność, raportowanie)
  

### Import notowań dziennych (prices_daily) + UI + DRY-RUN
- Dane historyczne obejmują okres od początku notowań danej spółki do 31.12.2025 - nowsze dane będą dogrywane importami dziennymi
- ADR opisuje pełny mechanizm importu dziennych notowań giełdowych (EOD) do tabeli prices_daily, wraz z obsługą trybu DRY-RUN, logowaniem i archiwizacją plików. Import jest ręcznie inicjowany z UI Streamlit i stanowi bazowy, referencyjny wzorzec dla kolejnych procesów ETL.

### Import wskaźników dziennych (indicators_daily)
- Decyzja formalizuje import wskaźników dziennych do tabeli indicators_daily jako osobny proces ETL, oparty o te same wzorce co import notowań. Definiuje strukturę plików wejściowych, zasady walidacji, nadpisywania danych oraz integrację z UI Streamlit i trybem DRY-RUN.


## ADR-002 – Fundamenty architektury projektu AnGG

### Zarządzanie środowiskiem i warstwa prezentacji (Streamlit)
- Plik: adr/ADR-002-Srodowisko-i-warstwa-prezentacji.md
- ADR definiuje standard środowiska uruchomieniowego projektu (Conda + environment.yml) oraz wybór Streamlit jako warstwy prezentacyjnej. Ustanawia ścisłą separację pomiędzy analizą danych a UI oraz określa, że Streamlit pełni wyłącznie rolę dashboardu / warstwy roboczej, bez logiki analitycznej.

### Fundamenty architektury projektu AnGG
- Status: Accepted
- Zakres:
  - środowisko uruchomieniowe (Conda, environment.yml)
  - struktura projektu Python i separacja odpowiedzialności
  - warstwa core (konfiguracja, DB)
  - model bazy danych i bezpieczeństwo
  - standard dokumentowania decyzji (ADR)
- Plik ADR: adr/ADR-002-Fundamenty-architektury-projektu-AnGG.md

**Opis:**
ADR zbiorczy definiujący fundamenty architektoniczne projektu AnGG.


### Warstwa bazy danych i bezpieczeństwo
- Zakres: Persistence danych, model relacyjny, bezpieczeństwo dostępu
- Opis: Decyzja o użyciu MS SQL Server Express jako lokalnej bazy danych projektu,
  definicja struktury tabel (companies, prices_daily, indicators_daily, staging),
  oraz modelu bezpieczeństwa opartego o dedykowanego użytkownika SQL (`angg_app`).
- Decyzja opisuje wybór MS SQL Server Express jako lokalnej bazy danych projektu oraz logiczny model danych (companies, prices_daily, indicators_daily, staging). Definiuje zasady bezpieczeństwa dostępu, klucze logiczne tabel oraz relacje pomiędzy danymi referencyjnymi, notowaniami i wskaźnikami.

**Struktura logiczna bazy danych:**

1. `companies`
Dane referencyjne spółek.

- `company_id` (PK, INT, IDENTITY)
- `ticker` (VARCHAR, UNIQUE)
- `company_name`
- `market`
- `is_active`
- `created_at`

---

2. `prices_daily`
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

3. `indicators_daily`
Wskaźniki techniczne / cechy analityczne liczone **per notowanie**.

- `indicator_id` (PK, techniczny)
- `company_id`
- `trade_date`
- `indicator_name`
- `indicator_value`
- `calc_version`
- `created_at`

Unikalność logiczna:
- `(company_id, trade_date, indicator_name, calc_version)`

Relacja logiczna:
- jedno notowanie → wiele wskaźników (1:N)

---

4. `stg_prices_raw`
Tabela stagingowa do importu danych CSV/TXT.

- dane w formacie tekstowym (VARCHAR),
- wykorzystywana wyłącznie w procesie ETL,
- brak relacji biznesowych.

---

### Struktura projektu Python i separacja odpowiedzialności
- Zakres: Organizacja kodu Python, struktura katalogów, separacja warstw


### Warstwa core: konfiguracja i połączenie z bazą danych
- Zakres: Warstwa core: konfiguracja i połączenie z bazą danych
- ADR formalizuje strukturę katalogów projektu Python oraz separację odpowiedzialności pomiędzy warstwami: core, etl, analysis, app, notebooks i automation. Stanowi podstawowy kontrakt architektoniczny, który obowiązuje wszystkie kolejne decyzje i implementacje.

### Język i nazewnictwo dokumentów ADR
- Zakres: Język i nazewnictwo dokumentów ADR
- ADR określa standard językowy i nazewniczy dla dokumentów decyzyjnych projektu. Wprowadza spójne konwencje nazewnictwa plików ADR, styl opisu decyzji oraz zasady ich dalszej rozbudowy, co zapewnia czytelność i długoterminową utrzymywalność dokumentacji.

### Środowisko i warstwa prezentacji (konfiguracja trybu DEMO bez `.env`)






## ADR-003 – WOLNA PRZESTRZEŃ NA DOKUMENTACJĘ












## AADR-004 – Model przechowywania wskaźników
- Plik ADR: adr/ADR-004-Model-przechowywania-wskaznikow.md
- rozszerzony o politykę aktualizacji wskaźników
- ADR opisuje przejście z modelu EAV na model wide dla tabeli indicators_daily, w którym wskaźniki są przechowywane jako kolumny. Decyzja znacząco redukuje wolumen danych, upraszcza zapytania analityczne oraz wprowadza słownik wskaźników (indicators_dictionary) jako warstwę metadanych i kontrakt między DB, ETL i UI.
- Optymalizacja pipeline wskaźników lokalnych (calc_flags, inkrementalność, raportowanie)
  


## ADR-005 – Pipeline wskaźników wyliczanych lokalnie (calculated indicators)
- Plik ADR: adr/ADR-005-Pipeline-wskaznikow-wyliczanych.md
- Zakres: ETL wskaźników, DRY-RUN, archiwizacja, integracja z UI
- ADR wprowadza dedykowany pipeline wskaźników wyliczanych lokalnie na podstawie danych rynkowych i innych wskaźników. Definiuje kolejność wyliczeń, obsługę zależności, idempotentny zapis do modelu wide oraz wspólny mechanizm DRY-RUN i raportowania wyników.
- Tryby wykonania pipeline wskaźników (DRY-RUN / REAL-RUN)
- Optymalizacja pipeline wskaźników lokalnych (calc_flags, inkrementalność, raportowanie)
- calc_flags jako kontrakt stanu wyliczenia wskaźnika
- Bezpieczne resetowanie bitów `calc_flags` (BIGINT)



## ADR-006 – Dodanie nowego wskaźnika: procedura
- Plik ADR:  adr/ADR-006-Dodanie-nowego-wskaznika-procedura.md
- Plik przedstawia ustandaryzowaną procedurę dodawania nowych wskaźników giełdowych do projektu *Analiza giełdowa*.
ADR-006 definiuje:
- jednolitą, powtarzalną procedurę importu nowych wskaźników,
- kanoniczną listę plików wymaganych do pracy nad nowym wskaźnikiem,
- zasady wykorzystania istniejącego pipeline wyliczeń,
- rolę i znaczenie mechanizmu `calc_flags`,
- obsługę zależności pomiędzy wskaźnikami,
- założenie minimalizacji zmian w architekturze przy dodawaniu kolejnych wskaźników.



## ADR-007 – Wprowadzenie wskaźników typu „future” do etykietowania danych historycznych
- Plik: ADR-007-Wskazniki-future-etykietowanie-danych-historycznych.md
- Definiuje wskaźniki przyszłości (future labels) służące do analizy ex post i treningu modeli ML.  
- Wprowadza pierwsze wskaźniki: `fut_barrier_rs_20d` (kierunek) oraz `fut_max_return_20d` (potencjał wzrostu).



## ADR-008 – Interpretacja wskaźników, sygnałów i prawdopodobieństwa (`prob`)
- Status: Accepted
- Zakres: Interpretacja biznesowo-analityczna wskaźników, sygnałów i etykiet future
- Plik ADR: adr/ADR-008-Interpretacja-wskaznikow-i-sygnalow-prob.md

**Opis**
ADR-008 dokumentuje sposób interpretacji:
- wskaźników typu *future* (`fut_imp_*`),
- sygnałów pochodnych (`signal_20`, `signal_20_hyb`),
- sygnałów probabilistycznych (`prob`).

Dokument pełni rolę **mostu pomiędzy danymi historycznymi a analizą decyzyjną**
oraz stanowi referencję semantyczną dla walidacji modeli ML i analiz probabilistycznych.




## ADR-009 – Budowa modułu „Przegląd danych i analizy” (pipeline danych, UI, interpretacja)

- **Status:** Accepted  
- **Zakres:**  
  Architektura i zasady działania modułu *Przegląd danych* oraz *Analiza* w aplikacji AnGG,
  obejmujące:
  - sposób ładowania i łączenia danych rynkowych,
  - strukturę i rolę głównych DataFrame’ów,
  - kolejność i odpowiedzialności warstwy UI,
  - zasady interpretacji wyników analiz.

- **Plik ADR:** `adr/ADR-009-Budowa-modulu-przegladu-danych-i-analiz.md`

### Opis decyzji

ADR-009 definiuje **kompletny przepływ danych i logikę prezentacyjną** dla analizy spółek:

- rozdział na:
  - **dane maksymalne** (lewa sekcja – zakres dostępnych danych),
  - **dane robocze / analityczne** (`df_market`) dla jednej spółki,
- zasady budowy zbiorczego DataFrame `df_market` jako:
  - połączenia notowań, wskaźników i metadanych spółki,
  - jedynego źródła danych dla wykresów i analiz,
- separację:
  - logiki obliczeń,
  - logiki interpretacji,
  - logiki prezentacji UI.

ADR opisuje również:
- kolejność renderowania elementów ekranu (kontekst → szczegóły),
- odpowiedzialność poszczególnych sekcji UI,
- brak prognozowania i brak sygnałów transakcyjnych w warstwie analitycznej.


### Globalne podsumowanie sytuacji spółki (rozszerzenie)

ADR-009 został rozszerzony o zasady **Globalnego podsumowania sytuacji spółki**, które:

- prezentuje **syntetyczny kontekst techniczno-rynkowy** spółki,
- znajduje się **na górze widoku analizy**, bezpośrednio pod głównym wykresem,
- korzysta z wyników analiz cząstkowych, ale nie zastępuje ich,
- pełni rolę „mapy mentalnej” aktualnego stanu rynku dla spółki.

Elementem podsumowania jest **znacznik stanu ogólnego spółki**:
- liczony regułowo (scoring),
- oparty wyłącznie na danych historycznych,
- prezentowany jako kolorowy box (zielony / żółty / czerwony),
- jawnie opisany jako **niebędący prognozą ani rekomendacją inwestycyjną**.

### Znaczenie architektoniczne

ADR-009 formalizuje:
- sposób myślenia o analizie jako **kontekście, nie sygnale**,
- UX jako świadomą decyzję architektoniczną,
- jednoznaczną granicę między:
  - danymi,
  - analizą,
  - interpretacją,
  - prezentacją.

Jest to jeden z **centralnych ADR-ów projektu AnGG**.

Formalizuje dataset `df_market_all` budowany wyłącznie na ekranie **„Przegląd danych”** i zakazuje budowania wersji „ALL” w ekranach analiz (Analiza / Analiza v2 / Analiza v3 / kolejne).


## ADR-010 – Instrukcja programu / Zachowanie ekranów aplikacji AnGG


- **Status:** Accepted  
- **Zakres:**  
  Dokumentacja aplikacji dla użytkownika / programisty systemu

- **Plik ADR:** `adr/ADR-010-Instrukcja-programu.md`





## ADR-011 – Analiza danych (warstwa eksploracyjna)

- **Status:** Proposed  
- **Zakres:** Ekran „Analiza danych” w Streamlit: eksploracja relacji cechy → etykiety future, mechanizm insightów, zasady UX, kontrakt `df_market`
- **Plik ADR:** `adr/ADR-011-Analiza-danych.md`

**Opis**
ADR-011 formalizuje ekran „Analiza danych” jako warstwę eksploracyjną:
- działa wyłącznie na `df_market` przygotowanym w „Przegląd danych”,
- wspiera wybór analizowanego targetu `fut_*`,
- uruchamia niezależne analizy bez pipeline’u decyzyjnego,
- zapisuje ustrukturyzowane insighty w `session_state`.





## ADR-012 – Warstwa ML: datasety, eksperymenty ML-01, ranking `prob` i rejestr modeli

- **Status:** Proposed  
- **Zakres:** Kontrakt warstwy ML: time-based split, budowa datasetów, target ML-01, metryki i thresholding, selekcja rankingowa sygnałów (`prob`)
- **Plik ADR:** `adr/ADR-012-ML.md`

**Opis**
ADR-012 definiuje spójny kontrakt warstwy ML:

- globalny podział TRAIN / VALIDATION / TEST oraz niezmienność ról datasetów,
- centralne budowanie datasetów w `app/ml/ml_datasets.py`,
- ML-01 jako etap eksploracyjny,
- kanoniczną selekcję rankingową sygnałów `prob`,
- rejestr artefaktów eksperymentów ML (`.joblib` + `.json`),
- obowiązkowy zapis konfiguracji eksperymentu w metadanych modelu,
  w tym filtrów jakościowych oraz `min_conditions`,
- mechanizm odtwarzania eksperymentów i ewaluacji zapisanych modeli
  na niezależnym zbiorze TEST,
- kontrakt zakładki UI `ML (TEST)` jako warstwy holdout evaluation,
  z rozróżnieniem strict TEST vs tryb eksperymentalny.


