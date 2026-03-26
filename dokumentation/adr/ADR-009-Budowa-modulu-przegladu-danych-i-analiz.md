# ADR-009: Zasady czytania danych i generowania datasetów w aplikacji AnGG

## Status

Proposed

## Kontekst

Aplikacja AnGG umożliwia pracę zarówno w trybie testowym (na plikach CSV), jak i produkcyjnym (na bazie danych SQL). W zależności od dostępności połączenia z bazą oraz ustawień parametrów środowiskowych, źródło danych jest wybierane automatycznie na etapie uruchamiania aplikacji.

## Decyzja

### 1. Zasady czytania danych

- **Tryb testowy (CSV):**  
  Jeżeli parametr `APP_TEST_ON_CSV_FILES` jest ustawiony na `True` lub nie ma połączenia z bazą SQL, dane są pobierane z plików CSV znajdujących się w katalogu określonym przez parametr `LOAD_DATA_WSE_PATH`.
- **Tryb produkcyjny (baza SQL):**  
  Jeżeli połączenie z bazą SQL jest dostępne i parametr `APP_TEST_ON_CSV_FILES` jest ustawiony na `False`, dane są pobierane bezpośrednio z bazy danych SQL, z wykorzystaniem istniejącej warstwy połączeń (SQLAlchemy).

W obu trybach struktura danych (nazwy kolumn, typy) jest identyczna, co umożliwia bezproblemowe przełączanie źródła danych bez konieczności zmian w logice aplikacji.

### 2. Zasady generowania danych na ekranie "Przegląd danych"

Na ekranie "Przegląd danych" obowiązują następujące zasady:

- **Górne pole "Dostępne firmy":**
  - Odpowiada za globalny zakres danych dostępnych w aplikacji.
  - Lista tickerów jest pobierana z parametru `LOAD_TICKERS` lub, po zaznaczeniu opcji "Wszystkie dostępne firmy", generowana dynamicznie na podstawie wszystkich dostępnych firm w źródle danych.
  - Powiązany DataFrame: **df_companies** (pełny zakres danych firmowych).

- **Dolne pole "Firmy podlegające analizie":**
  - Pozwala użytkownikowi zawęzić zakres danych do wybranych tickerów (podzbiór globalnego zakresu).
  - Wartość domyślna jest synchronizowana z górnym polem po zmianie trybu lub źródła danych, ale użytkownik może ją dowolnie edytować.
  - Powiązany DataFrame: **df_filtered_companies** (podzakres danych firmowych, zgodny z wybranymi tickerami i ewentualnie innymi filtrami).

- **Tabela "Firmy":**
  - Wyświetla dane z DataFrame **df_filtered_companies**.
  - Ten DataFrame jest wykorzystywany jako źródło danych dla kolejnych kontrolek i widoków w aplikacji (np. dalsze analizy, wykresy, eksporty).

### 3. Przepływ danych

1. Po uruchomieniu aplikacji wybierane jest źródło danych (CSV lub SQL).
2. Tworzony jest DataFrame **df_companies** na podstawie globalnego zakresu tickerów.
3. Użytkownik może zawęzić zakres w polu "Tickery do filtrowania (podzakres)", co generuje DataFrame **df_filtered_companies**.
4. DataFrame **df_filtered_companies** jest wykorzystywany w tabeli "Firmy" oraz przekazywany do kolejnych komponentów aplikacji.

## Konsekwencje

- Umożliwiono łatwe przełączanie źródła danych bez zmian w logice UI.
- Użytkownik ma pełną kontrolę nad zakresem analizowanych danych.
- Spójność struktury danych pozwala na łatwą rozbudowę aplikacji o kolejne widoki i analizy.


## Aktualizacja

### Zmiany
- Moduł `data_view.py` został zastąpiony przez `data_overview.py`.
- UI przestało samodzielnie:
  - wyliczać zakresy dat,
  - filtrować dane źródłowe,
  - wykonywać operacje typu MIN/MAX na danych rynkowych.
- UI pełni wyłącznie rolę:
  - orkiestratora stanu,
  - warstwy walidacji wejścia użytkownika,
  - inicjatora pobrań danych.

### Aktualny kontrakt
- Całość dostępu do danych (CSV/DB, cache, zakresy dat) realizowana jest przez `data_provider.py`.
- UI nie posiada bezpośredniej wiedzy o źródle danych ani strukturze zapytań.


## Rozszerzenie: Moduł „Przegląd danych” – warstwa tabelaryczna (Streamlit)

### Status
Accepted

### Kontekst
W ramach rozwoju modułu „Przegląd danych” konieczne było:
- umożliwienie eksploracji dużych zbiorów notowań i wskaźników,
- rozdzielenie nazw technicznych (DB) od nazw prezentowanych użytkownikowi,
- zapewnienie skalowalności widoku tabeli (wiele grup wskaźników),
- zachowanie jednego, spójnego DataFrame do dalszych analiz i wykresów.

### Decyzje architektoniczne

#### 1. Jeden główny DataFrame analityczny (`df_market`)
Wprowadzono **jeden zbiorczy DataFrame `df_market`**, który:
- powstaje na podstawie **jednej spółki + zakresu dat**,
- łączy dane z:
  - `companies`,
  - `prices_daily`,
  - `indicators_daily`,
- **nie jest sortowany globalnie** (istotne dla wykresów),
- stanowi **single source of truth** dla:
  - tabel,
  - wykresów,
  - analiz.

Dodatkowo:
- kolumna `trade_date` jest normalizowana do **daty bez czasu**,
- usuwane są kolumny techniczne ETL (`created_at*`, `calc_flags`, `ticker_y`),
- tworzona jest kolumna prezentacyjna:
  - `name = "{ticker} ({company_name})"`.

---

#### 2. Rozdzielenie warstw: dane vs prezentacja
- `df_market` **zawsze zawiera komplet danych** (notowania + wskaźniki),
- widok tabeli (`df_table`) jest:
  - pochodną `df_market`,
  - sortowaną **lokalnie** (najnowsze notowania na górze),
  - filtrowaną wyłącznie na potrzeby UI.

---

#### 3. Centralne mapowanie nazw kolumn (DB → UI)
Wprowadzono dedykowany słownik mapowań nazw kolumn:

**Plik:** `app/ui/column_metadata.py`

python
COLUMN_LABELS = {
    "trade_date": "Data",
    "open_price": "Otwarcie",
    "high_price": "Maksimum",
    "low_price": "Minimum",
    "close_price": "Zamknięcie",
    "volume": "Wolumen",
    "mv": "Kapitalizacja",
    "pe": "P/E",
    "pb": "P/B",
    "earnings_yield": "Stopa zwrotu z zysków",
    ...
}

## Zasady mapowania nazw kolumn (DB → UI)

- Mapowanie nazw odbywa się **wyłącznie w warstwie UI**
- Logika analityczna **zawsze operuje na nazwach technicznych (DB)**
- Brak wpisu w słowniku mapowań → **fallback do nazwy DB**
- Słownik mapowań jest **współdzielony** przez:
  - tabele,
  - wykresy,
  - moduł **„Analiza”**



## 4. Grupowanie kolumn – podejście systemowe

Wprowadzono **system grup logicznych kolumn**, niezależny od konkretnego ekranu UI.

COLUMN_GROUPS = {
    "core": {
        "label": "Notowania",
        "columns": [...],
        "default": True,
    },
    "fundamentals": {
        "label": "Fundamenty",
        "columns": [...],
    },
    "momentum": {
        "label": "Momentum / ryzyko",
        "columns": [...],
    },
    ...
}

### Dostępne grupy

- **Notowania (CORE)**
- **Fundamenty**
- **Momentum / ryzyko**
- **Trendy (SMA / EMA)**
- **Oscylatory**
- **Wolumen / zmienność**
- **Jakość / scoring**
- **Future: sygnały / impact**
- **Future: bariery**

### Sterowanie widokiem

- checkboxy nad tabelą,
- grupa **CORE** zawsze dostępna jako fallback,
- łatwe rozszerzanie o nowe grupy bez modyfikacji logiki UI.

---

## 5. Kontrola tabeli – AG Grid

Do prezentacji danych zastosowano:

- **`streamlit-aggrid` (AG Grid)**

Zapewnia pełne wsparcie dla:

- sortowania,
- filtrowania,
- paginacji,
- dynamicznego wyboru kolumn,
- mapowania nagłówków (DB → UI).

### Formatowanie wartości

- wartości pieniężne / wskaźniki:
  - **do 2 miejsc po przecinku** (standard),
  - **maks. 6 miejsc po przecinku** dla danych o wysokiej precyzji,
- **brak modyfikacji danych źródłowych** – formatowanie wyłącznie w warstwie prezentacji.


### Lista datafield dostępnych do wykorzystania

To są obiekty "df" uzupełniane danymi na ekranie "Podgląd danych" które można wykorzystać w ekranach do budowania tabel, wykresów, analiz, przewidywań, Machine Learning:

Klucz session_state          | Nazwa logiczna   | Rola                               

Pierwsze 4 DF = maksymalny zakres danych (lewa sekcja):
do_df_companies              |   df_companies   | Słownik spółek (master data)   - wszystkie dostępne ograniczone parametrem "LOAD_TICKERS"    
do_df_prices_daily           |   df_prices      | Notowania dzienne (OHLCV + ticker) - wszystkie dostępne ograniczone parametrem "LOAD_TICKERS"
do_df_indicators_daily       |   df_ind         | Wskaźniki techniczne - wszystkie dostępne ograniczone parametrem "LOAD_TICKERS"            
do_df_indicators_dictionary  |   df_ind_dict    | Słownik wskaźników - wszystkie dostępne                 

Ostatni DF = zakres roboczy / analityczny (prawa sekcja):
do_df_market_view            |   df_market      | Zbiorczy DF do wizualizacji łączący dane z kilku df (df_companies + df_prices + df_ind) - wszystkie dostępne ograniczone parametrem "LOAD_TICKERS"   
Powstaje z prawego filtra: jedna spółka + filtry daty (połączenie danych 1 firmy, notowań + wskaźników)
---------------------------- |   df_table       | Tabela dla jednej firmy powstała z df_market na potrzeby widoku tabeli (posortowana malejąco)
---------------------------- | df_last_load_tickers | Lista notowań z ostatniego dostępnego dnia dla spółek z parametru "LOAD_TICKERS"




---

## Konsekwencje architektoniczne

### Pozytywne

- jeden spójny model danych dla analiz i wizualizacji,
- pełna kontrola nad widokiem tabel,
- brak duplikacji logiki mapowania nazw,
- gotowość pod rozbudowę wykresów, analiz oraz modułów ML.

### Ograniczenia

- szeroki DataFrame (wide table) → większe zużycie pamięci,
- część logiki prezentacyjnej pozostaje w Streamlit (świadome i akceptowalne).


---

## Rozszerzenie: Globalne podsumowanie sytuacji spółki (UI)

### Status
Accepted

### Kontekst

Wraz z rozbudową analiz jednospołkowych pojawiła się potrzeba
zaprezentowania **syntetycznego, wysokopoziomowego kontekstu spółki**,
dostępnego **natychmiast po załadowaniu danych**, bez konieczności
przeglądania wszystkich wykresów i sekcji analitycznych.

Użytkownik potrzebuje:
- szybkiego „złapania kontekstu” spółki,
- jasnej informacji *w jakim środowisku rynkowym znajduje się spółka*,
- bez mieszania tego z prognozą lub sygnałem transakcyjnym.

---

### Decyzja

Wprowadzono **Globalne podsumowanie sytuacji spółki** jako
wydzieloną sekcję UI:

- renderowaną **bezpośrednio pod głównym wykresem cenowym**,
- przed szczegółowymi analizami i tabelą notowań,
- opartą wyłącznie na danych zawartych w `df_market`.

Sekcja ta:
- syntetyzuje wnioski z wielu analiz (trend, momentum, zmienność, wolumen, ryzyko),
- nie wykonuje własnych obliczeń niezależnych od analiz cząstkowych,
- pełni rolę **mentalnej mapy sytuacji**, a nie narzędzia decyzyjnego.

---

### Znacznik stanu ogólnego spółki (kolorowy box)

W ramach globalnego podsumowania wprowadzono **znacznik stanu ogólnego spółki**
prezentowany jako kolorowy box (`st.success / st.warning / st.error`).

Znacznik:
- jest liczony regułowo (scoring),
- bazuje wyłącznie na danych historycznych,
- opisuje **aktualny kontekst techniczno-rynkowy**.

❗ **Znacznik NIE jest prognozą ani rekomendacją inwestycyjną.**

#### Znaczenie kolorów

- **🟢 Zielony – kontekst sprzyjający**  
  Trend i momentum są spójne, zmienność i ryzyko są relatywnie pod kontrolą.
  Historycznie bardziej uporządkowane środowisko.

- **🟡 Żółty – kontekst niejednoznaczny**  
  Sygnały są mieszane lub rynek znajduje się w fazie przejściowej.
  Wymaga ostrożniejszej interpretacji.

- **🔴 Czerwony – kontekst niesprzyjający**  
  Trend jest słabszy, a ryzyko lub zmienność mogą być podwyższone.
  Historycznie trudniejsze środowisko decyzyjne.

---

### Dlaczego globalne podsumowanie jest na górze ekranu

Choć technicznie podsumowanie korzysta z wyników analiz szczegółowych,
zostało **świadomie umieszczone na górze widoku**:

- obliczenia wykonywane są wcześniej w kodzie,
- prezentacja nie musi odpowiadać kolejności renderowania analiz,
- UX faworyzuje **najpierw kontekst, potem szczegóły**.

Jest to **świadoma decyzja UX**, a nie ograniczenie architektoniczne.

---

### Konsekwencje

- Użytkownik otrzymuje natychmiastowy kontekst spółki.
- UI zachowuje spójność interpretacyjną (brak sygnałów akcyjnych).
- Globalne podsumowanie staje się punktem odniesienia
  dla dalszych analiz wizualnych.





# Kontrakt danych / UI Streamlit / Analizy globalne (market-wide)

**Powiązane ADR:**
- ADR-003 – Architektura warstwy UI Streamlit
- ADR-009 – Budowa modułu przeglądu danych i analiz
- ADR-011 – Analiza danych (warstwa eksploracyjna pod ML)

## 1. Kontekst

W aplikacji Analiza GG występują dwa podstawowe typy analiz:

- analizy dla pojedynczej spółki, pracujące na datasetach ograniczonych do jednej spółki i zakresu dat,
- analizy globalne (market-wide), pracujące na danych wszystkich spółek, np.:
  - globalna EDA sygnałów,
  - porównania rozkładów cech,
  - rankingi cech,
  - analizy hit-rate i baseline.

Analizy globalne wymagają jednego, spójnego datasetu typu:  
**„1 wiersz = 1 spółka × 1 dzień”**, zawierającego dane cenowe, wskaźniki oraz metadane spółki.

Dotychczas w projekcie istniało ryzyko, że różne ekrany analiz budują własne wersje datasetu „ALL”, co prowadziło do:
- niespójnych joinów,
- brakujących kolumn (np. `ticker`),
- duplikacji logiki,
- błędów regresji przy rozbudowie analiz.

## 2. Decyzja

Wprowadzona zostaje zasada **single source of truth** dla analiz globalnych:

- dataset **df_market_all** jest budowany wyłącznie na ekranie **„Przegląd danych”**,
- wszystkie ekrany analiz (Analiza, Analiza v2, Analiza v3 oraz kolejne) **nie mają prawa**:
  - budować własnych wersji datasetu „ALL”,
  - wykonywać fallbacków generujących dane market-wide.

Jeśli `df_market_all` nie istnieje w `session_state` lub jest pusty, ekran analizy:
- przerywa renderowanie analiz,
- wyświetla komunikat informujący o konieczności załadowania danych w **„Przeglądzie danych”**.

## 3. Definicja i kontrakt df_market_all

### 3.1. Definicja

`df_market_all` to kanoniczny dataset market-wide spełniający następujące warunki:
- granularność: **1 spółka × 1 dzień**,
- zawiera:
  - dane cenowe (OHLCV lub ich podzbiór),
  - dane wskaźników (model wide),
  - metadane spółki,
  - datę notowania.

Dataset jest przygotowany w pełni do analiz eksploracyjnych (EDA) oraz dalszego wykorzystania w ML.

### 3.2. Minimalny wymagany zestaw kolumn

- `company_id`
- `trade_date`
- `close_price` (lub równoważna kolumna ceny zamknięcia)
- `ticker`
- `company_name`

Pozostałe kolumny (wskaźniki, sygnały future, cechy pomocnicze) są zależne od zakresu załadowanych danych.

### 3.3. Kontrakt przechowywania w session_state

Dataset `df_market_all` jest przechowywany w `session_state` pod kluczem:
- `do_df_market_all`

Ekrany analiz mają wyłącznie prawo **odczytu** tego obiektu.

## 4. Konsekwencje

### 4.1. Pozytywne

- jedno źródło prawdy dla analiz globalnych,
- brak duplikacji logiki łączenia tabel i czyszczenia danych,
- stabilniejsza architektura UI i analiz,
- mniejsze ryzyko błędów typu „brak kolumny ticker”,
- lepsze przygotowanie pod dalszy rozwój EDA i ML.

### 4.2. Ograniczenia

- `df_market_all` może być datasetem dużym (wiele spółek × wiele dni),
- wymaga świadomego ładowania danych na ekranie **„Przegląd danych”**,
- ekrany analiz muszą respektować brak danych i nie wykonywać fallbacków.

## 5. Wskazania implementacyjne (nienormatywne)

Jeżeli w przyszłości potrzebny będzie inny wariant danych globalnych (np. wybrana giełda, sektor lub filtr branżowy), powinien on powstać jako osobny, jawny dataset (np. `df_market_all_filtered`) również budowany wyłącznie w module **„Przegląd danych”**.



