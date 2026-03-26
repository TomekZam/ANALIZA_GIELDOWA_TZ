# ADR-010 – Instrukcja programu / Zachowanie ekranów aplikacji AnGG

## Status
Proposed

## Data
2026-01-31

## Charakter dokumentu
**Instrukcyjno-architektoniczny (operacyjny)**

Dokument opisuje **jak działa aplikacja AnGG z perspektywy użytkownika i backendu jednocześnie**:
- co robią poszczególne ekrany,
- jakie operacje są wykonywane po stronie aplikacji,
- jak akcje użytkownika wpływają na:
  - zapytania do bazy danych,
  - ładowanie i transformację DataFrame,
  - zasilanie tabel i wykresów.

Dokument ma charakter:
- **praktycznej instrukcji obsługi dla autora projektu**,
- „przypominajki architektonicznej” po dłuższej przerwie,
- spoiwa pomiędzy UI, backendem i warstwą danych.

Nie zastępuje:
- ADR-ów technicznych,
- dokumentacji ETL,
- dokumentacji pipeline wskaźników.

Uzupełnia je, pokazując **jak wszystko działa razem w aplikacji**.

---

## Zakres ADR

ADR-010 dokumentuje:
- zachowanie ekranów aplikacji Streamlit,
- przepływ danych pomiędzy UI a backendem,
- cykl życia DataFrame w `session_state`,
- zależności: **akcja użytkownika → backend → DF → widok**.

Każdy ekran aplikacji powinien mieć w tym dokumencie **osobny rozdział**.

---

# Ogólny przepływ pracy w aplikacji

Aplikacja działa według stałego schematu:

1. **Home**
   - opis aplikacji,
   - aktualny snapshot rynku (ostatnie notowania),
   - informacja o źródle danych (CSV / SQL),
   - wskazanie rekomendowanej ścieżki pracy.

2. **Przegląd danych**
   - wybór zakresu danych (tickery, daty),
   - jawne załadowanie danych do `session_state`,
   - eksploracja notowań i wskaźników jednej spółki.

3. **Analiza danych**
   - analiza sygnałów future,
   - korelacje wskaźników z etykietami wzrostów,
   - ranking cech predykcyjnych,
   - przygotowanie intuicji statystycznej i hipotez pod ML.

4. **Machine Learning**
   - przygotowanie datasetów predykcyjnych (TRAIN / VALIDATION / TEST),
   - wybór sygnału jako zmiennej target,
   - selekcja cech numerycznych do modelu,
   - trenowanie i porównanie modeli klasyfikacyjnych,
   - analiza jakości predykcji oraz symulacja wyników inwestycyjnych,
   - zapis i ponowne wykorzystanie wytrenowanych modeli.

---

# Ekran – Home

## Cel ekranu

Ekran **Home** pełni rolę strony startowej aplikacji i lekkiego wprowadzenia do pracy z systemem.

Jego zadania:
- przedstawienie krótkiego opisu idei aplikacji,
- pokazanie rekomendowanej kolejności pracy,
- zaprezentowanie szybkiego snapshotu rynku,
- wskazanie aktywnego źródła danych.

Ekran nie służy do pracy analitycznej w pełnym zakresie i **nie inicjuje pełnego ładowania danych historycznych** dla kolejnych ekranów.

---

## Rekomendowany sposób pracy

Na ekranie startowym użytkownik otrzymuje prostą ścieżkę pracy:

> **zobacz sygnał → zrozum sygnał → spróbuj go przewidzieć**

W praktyce oznacza to przejście przez aplikację w tej kolejności:

1. **Przegląd danych**
   - zobacz sygnał i jego kontekst na wykresach,
   - sprawdź zakres danych, kompletność i zachowanie kursu.

2. **Analiza danych**
   - sprawdź, z jakimi wskaźnikami i warunkami rynkowymi sygnał może być powiązany,
   - zbuduj intuicję statystyczną.

3. **Machine Learning**
   - przetestuj, czy analizowany sygnał da się przewidywać na podstawie danych historycznych.

---

## Snapshot rynku – logika działania

Tabela startowa:
- pokazuje **ostatnie dostępne notowania** dla spółek z parametru `LOAD_TICKERS`,
- jest ładowana automatycznie przy pierwszym wejściu na ekran,
- jest przechowywana w:

`session_state["df_last_load_tickers"]`

Snapshot:
- ma charakter **informacyjny**,
- pozwala szybko sprawdzić, czy dane są dostępne,
- nie ustala jeszcze globalnego zakresu danych analitycznych,
- nie ładuje pełnych danych historycznych dla kolejnych ekranów.

---

## Znaczenie architektoniczne ekranu Home

Ekran **Home**:
- jest lekkim punktem wejścia do aplikacji,
- nie wykonuje pełnego pipeline danych,
- nie buduje `df_market`,
- nie buduje `df_market_all`,
- nie stanowi źródła prawdy dla ekranów analitycznych.

Jego rola jest:
- orientacyjna,
- instrukcyjna,
- nawigacyjna.

---

# Ekran – Przegląd danych

## Cel ekranu

Ekran „Podgląd danych” pełni rolę **centralnego punktu wejścia do pracy z danymi**.

Jego zadania:
- zdefiniowanie **globalnego zakresu danych**, na którym pracuje aplikacja,
- załadowanie danych z bazy lub źródła plikowego (kontrolowany moment IO),
- prezentacja:
  - snapshotu rynku (ostatnie notowania),
  - danych jednej spółki do dalszej analizy,
- zasilenie kolejnych ekranów i wykresów.

Kluczowa zasada architektoniczna:

> **Lewy panel = ładowanie danych (DB / IO)**  
> **Prawy panel = praca analityczna (pandas, bez DB)**

---

## Lista kluczowych DataFrame (punkt odniesienia)

### DataFrame globalne – maksymalny zakres danych (lewa sekcja)

| session_state key | Logical name | Rola |
|------------------|-------------|------|
| `do_df_companies` | `df_companies` | Słownik spółek (master data) |
| `do_df_prices_daily` | `df_prices` | Notowania dzienne (OHLCV) |
| `do_df_indicators_daily` | `df_ind` | Wskaźniki techniczne |
| `do_df_indicators_dictionary` | `df_ind_dict` | Słownik wskaźników |
| `do_df_market_all` | `df_market_all` | Cały rynek / zbiorczy DF do analiz globalnych |

Te DF:
- są ładowane **jednorazowo przyciskiem**,
- stanowią **maksymalny zakres danych dostępnych w aplikacji**,
- są współdzielone przez kolejne widoki.

---

### DataFrame robocze / analityczne (prawa sekcja)

| session_state key | Logical name | Rola |
|------------------|-------------|------|
| `do_df_market_view` | `df_market` | Zbiorczy DF dla 1 spółki (analiza, wykresy) |
| *(lokalny)* | `df_table` | Widok tabelaryczny jednej spółki |
| `df_last_load_tickers` | — | Snapshot rynku – ostatni dzień notowań |

---

## Kolejność zdarzeń i operacji (logika działania ekranu)

### Krok 0 – Wejście na ekran

Przy pierwszym wejściu:
- inicjalizowany jest `session_state`,
- ustawiane są domyślne wartości:
  - tickery (`LOAD_TICKERS`),
  - zakres dat (`LOAD_DATE_FROM / TO`),
- **żadne dane nie są jeszcze ładowane z DB**.

Celem jest szybkie wejście na ekran bez kosztów IO.

---

### Krok 1 – Checkbox „Wszystkie dostępne firmy”

Checkbox wpływa **wyłącznie na zakres dostępności**, nie na dane robocze.

#### OFF (domyślnie)
- tickery = `LOAD_TICKERS`,
- daty = parametry konfiguracyjne,
- brak zapytań do DB.

#### ON
- pobierana jest pełna lista spółek,
- wyznaczany jest rzeczywisty zakres dat dostępnych w bazie.

Efekt:
- aktualizacja **maksymalnego zakresu dostępnych danych**:
  - listy wszystkich dostępnych spółek (zakres referencyjny),
  - zakresu dat dostępnych w źródle danych.

Checkbox **nie decyduje**, jakie spółki zostaną faktycznie załadowane —
ustala jedynie **górny limit dostępności**, widoczny w polu „Dostępne firmy”.

**Nie powstają jeszcze żadne DataFrame z danymi rynkowymi.**

---

### Krok 2 – Pola „Dostępne firmy” oraz „Data od / do”

Pola te pełnią **różne role semantyczne**:

- **„Dostępne firmy”**  
  – pole informacyjne (read-only),  
  – pokazuje **maksymalny zakres spółek**, które aplikacja *może* załadować,  
  – jego zawartość **nie zmienia się** w wyniku filtrowania ani ładowania danych.

- **„Data od / Data do”**  
  – definiują zakres czasowy dostępnych danych,  
  – są wspólne zarówno dla zakresu dostępnego, jak i roboczego.

Faktyczne sterowanie tym, **jakie spółki zostaną załadowane**, odbywa się
dopiero poprzez pole **„Filtr firm”**.

Zmiany w tych polach są „tanie” obliczeniowo.

---

### Krok 2a – Pole „Filtr firm”

Pole **„Filtr firm”** wprowadza **roboczy filtr spółek** i zmienia
sposób działania ekranu w porównaniu do wcześniejszych wersji aplikacji.

Rola pola:
- pozwala użytkownikowi wskazać **podzbiór spółek** do faktycznego załadowania,
- działa **niezależnie** od pola „Dostępne firmy”.

Zasady działania:
- jeżeli pole „Filtr firm” jest **puste**:
  - przy ładowaniu danych używany jest **pełny zakres dostępnych firm**
    widoczny w polu „Dostępne firmy”,
- jeżeli pole zawiera listę tickerów:
  - ładowane są **wyłącznie wskazane spółki**.

Ważne rozróżnienie semantyczne:
- **„Dostępne firmy”** = zakres *możliwy* (referencyjny, niezmienny),
- **„Filtr firm”** = zakres *roboczy* (zmienny, kontrolowany przez użytkownika),
- przycisk „Załaduj dane…” **nigdy nie modyfikuje** pola „Dostępne firmy”.

---

### Krok 3 – Przycisk  
### „Załaduj dane by wyświetlić wykres z analizą”

To **kluczowy moment aplikacji**.

Przycisk „Załaduj dane…”:
- **nie zmienia** zakresu dostępnych firm,
- **nie modyfikuje** zawartości pola „Dostępne firmy”,
- ładuje dane **wyłącznie na podstawie**:
  - zawartości pola „Filtr firm” (jeśli niepuste),
  - lub pełnej listy dostępnych firm (jeżeli filtr jest pusty).

Dopiero ten przycisk:
- wykonuje zapytania do DB,
- ładuje dane do pamięci,
- ustala globalny kontekst danych.

#### Kolejność operacji:

1. **Mapowanie ticker → company_id**
   - techniczny krok przygotowawczy.

2. **Ładowanie maksymalnego zakresu danych (DB / CSV):**

   Kolejność jest istotna i jawna:

   - `df_companies`
   - `df_prices`
   - `df_ind`
   - `df_ind_dict`

   Te DF trafiają do `session_state` i są **źródłem prawdy** dla dalszej pracy.

3. **Snapshot rynku**
   - tworzony jest `df_last_load_tickers`,
   - zawiera:
     - po 1 rekordzie na spółkę,
     - dane z ostatniego dostępnego dnia notowań.

   Ten DF zasila tabelę:
   > „Notowania z [data]”

4. **Budowa zbiorczej ramki rynku**
   - na bazie załadowanych danych możliwe jest zbudowanie `df_market_all`,
   - DF ten zasila ekran **Analiza danych** i później moduł **Machine Learning**.

---

### Krok 4 – Wybór jednej spółki

Na podstawie już załadowanych DF:

- `df_prices`
- `df_ind`
- `df_companies`

tworzony jest:

`df_market = dane jednej spółki`

Cechy `df_market`:
- 1 spółka,
- pełna historia w wybranym zakresie,
- ceny + wskaźniki,
- dane po merge notowań i wskaźników,
- **brak zapytań do DB** (czysty pandas).

Jest to **kanoniczny DataFrame analityczny** aplikacji dla pracy na pojedynczej spółce.

---

### Krok 5 – Tabela danych (`df_table`)

`df_table`:
- jest pochodną `df_market`,
- zwykle:
  - posortowany malejąco po dacie,
  - ograniczony do potrzeb UI,
- nie jest przechowywany w `session_state`.

Służy wyłącznie prezentacji danych.

---

## Podsumowanie przepływu danych (schemat mentalny)

UI:
- Dostępne firmy (zakres maksymalny)
- Filtr firm (zakres roboczy)
- Daty
↓
[PRZYCISK LOAD]
↓
df_companies
df_prices
df_ind
df_ind_dict ← globalny zakres danych
↓
df_last_load_tickers → snapshot rynku
↓
df_market_all → analizy globalne / ML
↓
[wybór spółki]
↓
df_market → analiza / wykresy
↓
df_table → tabela

---

Wprowadzenie pola „Filtr firm” rozdziela pojęcia:
- **zakres dostępny** (informacyjny, stały),
- **zakres roboczy** (zmienny, kontrolowany przez użytkownika).

To rozdzielenie jest celowe i zapobiega utracie kontekstu danych
oraz umożliwia łatwy powrót do pełnego widoku bez ponownej konfiguracji ekranu.

---

## Wnioski architektoniczne

- Moment kosztowny (DB / IO) jest **jawny i kontrolowany**.
- Analiza odbywa się wyłącznie na danych już załadowanych.
- `df_market` jest:
  - naturalnym wejściem do wykresów,
  - stabilnym kontraktem danych dla widoku jednej spółki.
- `df_market_all` jest:
  - źródłem analiz globalnych,
  - bazą dla budowy datasetów ML,
  - wspólną ramką dla EDA i modelowania.

---

## Uwagi na przyszłość

- Przy dużej liczbie tickerów możliwe jest:
  - cache’owanie danych,
  - lazy loading.
- `df_last_load_tickers` może być rozwinięty w:
  - screening,
  - rankingi,
  - heatmapy rynku.

---

# Ekran – Analiza danych

## Warunek wstępny – załadowanie danych

Ekran **Analiza danych** może działać wyłącznie po wcześniejszym załadowaniu danych na ekranie **Przegląd danych**.  
To na ekranie *Przegląd danych* następuje:
- wybór zakresu danych (spółki, daty),
- wczytanie notowań i wskaźników,
- zbudowanie pełnej ramki danych rynkowych.

Po poprawnym załadowaniu danych są one zapisywane w `session_state` i udostępniane kolejnym ekranom aplikacji.

Jeżeli dane nie zostały wcześniej załadowane, ekran **Analiza danych** wyświetla komunikat informacyjny i nie wykonuje żadnych obliczeń.

---

## Źródło danych używane w analizie

Na ekranie **Analiza danych** dane z `session_state` są kopiowane lub budowane do ramki:

`df_market_all`

Jest to zbiorcza ramka danych obejmująca:
- wszystkie spółki wybrane w *Przeglądzie danych*,
- wszystkie dostępne dni notowań,
- ceny, wolumeny oraz wskaźniki techniczne,
- wskaźniki typu *future* (`fut_signal_*`).

Wszystkie analizy na tym ekranie są wykonywane **wyłącznie** na podstawie `df_market_all`.  
Ekran **Analiza danych** nie komunikuje się bezpośrednio z bazą danych ani z plikami CSV.

---

## Cel ekranu „Analiza danych”

Ekran służy do **globalnej analizy historycznej (EDA)** sygnałów typu *future* w skali całego rynku.

Celem analizy jest:
- zrozumienie, jak często dany sygnał występował w historii,
- identyfikacja cech rynku, które **towarzyszyły** wystąpieniom sygnału,
- porównanie sytuacji z sygnałem **+1** do losowego przypadku rynkowego,
- przygotowanie wiedzy i cech wejściowych pod dalsze analizy oraz modele ML.

Ekran **nie generuje sygnałów inwestycyjnych** i nie służy do bieżącego podejmowania decyzji.

---

## Wybór sygnału do analizy

Na górze ekranu użytkownik wybiera sygnał z listy dostępnych kolumn `fut_signal_*`.

Wybrany sygnał:
- musi być wskaźnikiem typu *future*,
- jest traktowany jako **etykieta historyczna**,
- rozróżnia obserwacje na:
  - *Brak sygnału*,
  - *Sygnał +1* (sytuacje zakończone wzrostem w zadanym horyzoncie).

Dla wybranego sygnału wyświetlane jest:
- podsumowanie statystyczne (liczba obserwacji, liczba sygnałów +1),
- **baseline** – bezwarunkowe prawdopodobieństwo sygnału +1 w rynku.

Baseline stanowi punkt odniesienia dla wszystkich dalszych analiz.

---

## Tabela „Sygnały (ostatnie wystąpienia)”

Ekran prezentuje tabelę z ostatnimi wystąpieniami sygnału +1:
- ticker i nazwa spółki,
- data wystąpienia sygnału,
- cena zamknięcia,
- wartość sygnału.

Tabela służy jako punkt nawigacyjny:
- umożliwia wybór konkretnej spółki,
- pozwala przejść do ekranu **Przegląd danych** w celu analizy zachowania kursu i wskaźników w czasie.

---

## Zakładki analityczne

Analiza jest podzielona na logiczne zakładki, wszystkie bazujące na tym samym `df_market_all` i wybranym sygnale.

### Analiza EDA
Globalna analiza eksploracyjna:
- częstość sygnału (baseline),
- rozkład sygnału w czasie (per rok),
- porównanie cech: *Brak sygnału* vs *Sygnał +1*,
- analiza braków danych.

Zakładka pełni rolę sanity-check i wstępnego rozpoznania danych.

### Rozkład cechy
Dla wybranej cechy prezentowane są:
- histogramy rozkładu wartości,
- osobno dla obserwacji bez sygnału i z sygnałem +1.

Celem jest wizualna ocena, czy rozkłady różnią się pomiędzy klasami.

### Para cech (scatter)
Dwa wykresy punktowe dla tej samej pary cech:
- osobno dla *Brak sygnału*,
- osobno dla *Sygnał +1*.

Zakładka umożliwia identyfikację klastrów i zależności pomiędzy cechami.

### Para cech → hit-rate (koszyki)
Obie cechy dzielone są na koszyki (kwantyle).
Prezentowana jest:
- heatmapa warunkowego prawdopodobieństwa `P(+1 | koszyk X, koszyk Y)`,
- tabela najlepszych konfiguracji wraz z lift względem baseline.

Zakładka służy do badania **warunkowych przewag statystycznych**.

### Ranking cech
Automatyczne rankingi:
- pojedynczych cech,
- par cech,

na podstawie najlepszego koszyka (kwantyla) i liftu względem baseline.

Ranking wskazuje cechy potencjalnie użyteczne w dalszej analizie lub modelach ML.

### Hit-rate globalny
Prezentuje udział sygnałów +1 w całym rynku dla najlepszych koszyków.
Zakładka ma charakter pomocniczy i porównawczy.

### Korelacje cech
Macierz korelacji pomiędzy cechami:
- pomaga identyfikować redundancję informacji,
- wspiera selekcję cech przed modelowaniem.

---

## Zakres analiz wykonywanych na ekranie

Na ekranie **Analiza danych** wykonywane są operacje typu EDA (Exploratory Data Analysis) na całym rynku.

Obejmują one m.in.:
- analizę częstości występowania sygnałów typu `fut_signal_*`,
- porównanie rozkładów wybranych wskaźników:
  - dla obserwacji z sygnałem +1,
  - dla obserwacji bez sygnału,
- wizualizację zależności pomiędzy parami cech (scatter),
- analizę skuteczności sygnału w różnych przedziałach wartości wskaźników (heatmapy),
- ranking najlepszych kombinacji warunków rynkowych zwiększających prawdopodobieństwo wystąpienia sygnału.

---

## Charakter obliczeń

Obliczenia na tym ekranie:
- są wykonywane wyłącznie w pamięci (pandas / numpy),
- wykorzystują mechanizmy cache Streamlit (`st.cache_data`),
- nie powodują ponownych zapytań do źródła danych,
- mogą wykonywać kosztowne operacje statystyczne:
  - binning kwantylowy (`qcut`),
  - grupowania,
  - budowę macierzy korelacji,
  - próbkowanie danych do wizualizacji.

Celem jest uzyskanie **globalnej intuicji statystycznej** przed przejściem do modelowania ML.

---

## Charakter analizy

Analiza na tym ekranie:
- jest **analizą historyczną (ex post)**,
- bazuje na etykietach future,
- służy do budowy wiedzy statystycznej,
- nie stanowi rekomendacji inwestycyjnej ani sygnału operacyjnego.

Wyniki należy interpretować jako:
- zależności statystyczne,
- hipotezy do dalszej walidacji,
- materiał wejściowy pod modele machine learning.

---

# Ekran – Machine Learning

## Rola ekranu

Ekran **Machine Learning** stanowi osobny etap pracy z aplikacją.

Nie służy już do samej eksploracji danych, lecz do:
- budowy datasetów predykcyjnych,
- testowania przewidywalności sygnałów,
- porównywania modeli,
- selekcji sygnałów rankingowych,
- oceny użyteczności modeli w warunkach zbliżonych do decyzyjnych.

Moduł ML korzysta z danych przygotowanych wcześniej na ekranie **Przegląd danych** oraz z wiedzy zebranej na ekranie **Analiza danych**.

---

## Warunek wstępny – przygotowane dane rynkowe

Ekran **Machine Learning** może działać wyłącznie po wcześniejszym:
- załadowaniu danych na ekranie **Przegląd danych**,
- przygotowaniu zbiorczej ramki rynku `df_market_all`.

To oznacza, że ML:
- nie pracuje bezpośrednio na surowych zapytaniach do bazy,
- nie powinien samodzielnie inicjować pełnego procesu pobierania danych,
- zakłada istnienie gotowego kontekstu danych w `session_state`.

Jeżeli dane nie zostały wcześniej przygotowane, ekran ML powinien traktować to jako brak warunku wejściowego.

---

## Źródło danych dla ML

Bazą do budowy datasetów ML jest zbiorczy DF rynku:

`df_market_all`

Ramka ta zawiera:
- ceny,
- wolumen,
- wskaźniki techniczne,
- wskaźniki i etykiety typu *future*,
- identyfikatory rekordów biznesowych:
  - `ticker`,
  - `company_name`,
  - `trade_date`,
  - `company_id`.

Na tej podstawie budowane są kanoniczne datasety ML:
- `df_market_train`,
- `df_market_validation`,
- `df_market_test`.

Podział ma charakter **time split**, co oznacza, że dane są dzielone chronologicznie, a nie losowo.

---

## Cel ekranu

Ekran **Machine Learning** pełni rolę laboratorium eksperymentów predykcyjnych.

Jego zadania:
- wybór sygnału jako zmiennej target (`y`),
- dobór zestawu cech wejściowych (`X`),
- przygotowanie pipeline preprocessingu,
- trenowanie i szybkie porównywanie modeli,
- ocena jakości predykcji,
- zapis modeli i ich metadanych,
- wykorzystanie score modelu do selekcji sygnałów rankingowych.

---

## Główne etapy pracy w module ML

### Etap 1 – wybór targetu

Targetami są wybrane kolumny sygnałowe typu `fut_signal_*`, ale ich lista w UI nie wynika wyłącznie z prostego `startswith`, tylko z konfiguracji aplikacji.

Wybrany target:
- musi istnieć w danych,
- jest binaryzowany do postaci:
  - `1` dla wystąpienia sygnału +1,
  - `0` w przeciwnym przypadku.

To zapewnia spójne traktowanie problemu jako **klasyfikacji binarnej**.

---

### Etap 2 – wybór i filtrowanie cech

Przed zbudowaniem modelu tworzona jest lista kolumn ignorowanych.

Z modelowania wyłączane są zwykle:
- kolumny techniczne,
- identyfikatory,
- pola tekstowe,
- kolumny cenowe nieużywane w danym eksperymencie,
- inne sygnały future,
- kolumny, które mogłyby prowadzić do przecieku informacji.

Następnie z pozostałych kolumn wybierane są **cechy numeryczne**, które realnie zawierają dane.

Efekt:
- model otrzymuje spójny zestaw cech liczbowych,
- target nigdy nie trafia do `X`,
- selekcja cech odbywa się w sposób fail-soft: tylko dla kolumn istniejących w danych.

---

### Etap 3 – budowa datasetów TRAIN / VALIDATION / TEST

Po przygotowaniu targetu i cech budowane są trzy główne zbiory:
- **TRAIN** – do uczenia modeli,
- **VALIDATION** – do porównań modeli i strojenia decyzji,
- **TEST** – do końcowego sprawdzenia jakości na danych odseparowanych czasowo.

Ważne założenie:
- cechy używane w VALIDATION i TEST muszą być zgodne z cechami wyznaczonymi wcześniej na TRAIN.

Dzięki temu:
- nie „podglądamy przyszłości” przy budowie zestawu cech,
- zachowujemy poprawność eksperymentu czasowego.

---

### Etap 4 – preprocessing

Moduł ML pozwala na budowę pipeline preprocessingu, który może obejmować:
- imputację braków danych,
- skalowanie (`StandardScaler`),
- transformację rozkładów (`PowerTransformer`),
- częściowe radzenie sobie z niezbalansowanymi klasami.

Preprocessing:
- jest częścią pipeline modelowego,
- powinien być liczony konsekwentnie dla TRAIN i stosowany później do VALIDATION / TEST,
- ma ograniczać wpływ braków danych i różnic skali pomiędzy cechami.

---

### Etap 5 – trenowanie i porównanie modeli

W module ML porównywane są m.in. modele:
- Logistic Regression,
- Random Forest,
- Gradient Boosting,
- DummyClassifier jako baseline.

Ocena modeli może wykorzystywać:
- accuracy,
- precision,
- recall,
- F1,
- ROC-AUC,
- metryki pomocnicze związane z selekcją sygnałów.

Celem nie jest wyłącznie „najwyższa skuteczność klasyfikacyjna”, ale znalezienie modelu, który daje użyteczny ranking rekordów i sensowną jakość sygnałów.

---

### Etap 6 – interpretacja i wybór modelu

Porównanie modeli służy do:
- odrzucenia modeli słabszych od baseline,
- znalezienia modeli stabilniejszych,
- wyboru modelu do dalszych eksperymentów rankingowych.

Na tym etapie użytkownik nie podejmuje jeszcze ostatecznej decyzji inwestycyjnej, lecz wybiera model, który:
- najlepiej rozróżnia przypadki pozytywne,
- daje sensowny score `prob`,
- ma potencjał do dalszej selekcji sygnałów.

---

## Zapis i ponowne wykorzystanie modeli

Moduł przewiduje zapis modeli i metadanych do katalogów projektowych.

Zapis obejmuje m.in.:
- plik modelu,
- plik meta,
- parametry eksperymentu,
- target,
- użyte filtry jakościowe,
- metryki validation.

Znaczenie architektoniczne:
- model przestaje być jednorazowym wynikiem sesji,
- może zostać później ponownie załadowany,
- możliwe staje się porównywanie wielu modeli zapisanych historycznie.

To buduje zalążek **rejestru modeli** i pozwala przejść od eksperymentu jednorazowego do kontrolowanego workflow ML.

---

## Ekran / moduł ML-01 – selekcja rankingowa sygnałów (Top-K → Top-Pct)

### Cel ekranu (Tab 2 w ML-01)

Tab 2 służy do:
- porównania 27 konfiguracji selekcji sygnałów na zbiorze **VALIDATION**,
- wybrania jednej konfiguracji,
- zbudowania na jej podstawie małego zbioru sygnałów „PRZED” (a potem filtrowania jakościowego do „PO”).

W tej zakładce sygnały powstają na bazie rankingowego score modelu:
- `prob` = przewidywane przez model **prawdopodobieństwo klasy pozytywnej** (`y=1`) dla rekordu (ticker, trade_date),
- `y_true` = prawda historyczna (0/1) w VALIDATION.

---

## Dane wejściowe (ranking VALIDATION)

Po treningu modelu w ML-01 budowany jest DataFrame rankingowy dla VALIDATION:
- `df_val_rank_full` = metadane rekordu + `y_true` + `prob`.

Ten DF jest cache’owany w `session_state` i stanowi wejście do tabeli grid.

Architektonicznie oznacza to, że:
- najpierw powstaje model,
- potem model generuje score,
- dopiero na końcu wynik score jest używany do selekcji sygnałów.

---

## Jak działa selekcja sygnałów (kanoniczne Top-K → Top-Pct)

Selekcja wykonywana jest **osobno w kolejnych oknach sesji**.

### Krok 1 — podział osi czasu na okna (`window_sessions`)
- `window_sessions` = liczba **unikalnych sesji (`trade_date`)** w jednym oknie.
- Oś czasu VALIDATION jest dzielona na kolejne okna po `window_sessions` sesji.
- Każdy rekord dostaje `window_id` na podstawie numeru sesji.

> `window_sessions` to **rozmiar okna w sesjach**, a nie „liczba sygnałów”.

---

### Krok 2 — selekcja w każdym oknie (ranking po `prob`)

Dla każdego `window_id`:
1. Sortujemy rekordy w oknie malejąco po `prob`.
2. Wyliczamy limit „Top-%” jako limit liczbowy:
   - `N_okna` = liczba rekordów w oknie,
   - `pct_limit = floor(N_okna * top_score_pct)`
3. Łączymy ograniczenia:
   - `final_k = min(max_signals, pct_limit)`
4. Bierzemy `final_k` najlepszych rekordów z okna (`head(final_k)`).

**Interpretacja parametrów:**
- `max_signals` (Top-K) = maksymalna liczba sygnałów wybieranych **w jednym oknie**.
- `top_score_pct` (Top-%) = ułamek 0–1 ograniczający **liczbę rekordów** w oknie (np. 0.001 = 0.1%, 1.0 = 100%).

To nie jest próg wartości `prob` typu „>= 0.999”, tylko limit liczbowy zależny od `N_okna`.

> Efekt uboczny: przy bardzo małym Top-% i małych oknach może zajść `pct_limit = 0`,
> co powoduje brak sygnałów w danym oknie, a nawet w całym VALIDATION.

---

### Krok 3 — zsumowanie wyników po oknach

`N wybranych` (`n_selected`) to **łączna liczba sygnałów ze wszystkich okien**:
- suma `final_k` po wszystkich `window_id`.

To tłumaczy, dlaczego `N wybranych` może być np. 20, mimo że Top-K = 3:
- Top-K to limit **per okno**,
- a `N wybranych` jest sumą po wszystkich oknach.

---

## Jak liczone są metryki w tabeli grid

Dla sygnałów wybranych w danej konfiguracji (po zsumowaniu po oknach):
- `TP` = liczba wybranych sygnałów z `y_true = 1`,
- `FP` = liczba wybranych sygnałów z `y_true = 0`,
- `Precyzja` = `TP / (TP + FP)` (ułamek 0–1),
- `Wykrywalność (Recall)` = `TP / (TP + FN)` względem całego VALIDATION (ułamek 0–1),
- `+1 VAL` = liczba wszystkich pozytywnych przypadków w całym VALIDATION.

Statystyki score:
- `Śr/Min/Max prawdop.` to statystyki `prob` w wybranych sygnałach (ułamek 0–1).

---

## Zyski ex post w tabeli grid (kolumny „Zysk … (%)”)

Dla każdej konfiguracji liczone są średnie stopy zwrotu dla wybranych sygnałów:
- `Zysk 20 (%)`,
- `Zysk 60 (%)`,
- `Zysk 120 (%)`,
- `Zysk do końca (%)`.

Są to średnie zwroty **w %** (punkty procentowe), liczone jako:

`(future / base - 1) * 100`

Te metryki:
- nie są gwarancją skuteczności przyszłej,
- mają charakter historyczny,
- pomagają ocenić, czy ranking modelu przekłada się na lepszy profil ex post niż losowy wybór rekordów.

---

## Cache i wydajność

Tabela grid (27 kombinacji) jest kosztowna obliczeniowo, więc wynik jest cache’owany w `session_state`.

Dzięki temu:
- zmiany filtrów i checkboxów w tej zakładce nie przeliczają gridu od nowa,
- koszt obliczeń jest ponoszony tylko wtedy, gdy zmieni się kontekst:
  - model,
  - target,
  - dane wejściowe.

---

## Znaczenie architektoniczne modułu ML

Moduł **Machine Learning**:
- stanowi ostatni etap workflow aplikacji,
- nie zastępuje EDA,
- nie powinien być używany bez wcześniejszej analizy danych,
- opiera się na tym samym źródle danych, ale pracuje na innym poziomie abstrakcji.

Jego celem jest odpowiedź na pytanie:

> **czy sygnał, który historycznie da się opisać statystycznie, da się także przewidywać modelowo?**

---

# Podsumowanie aplikacji – cel i zastosowanie analizy

Aplikacja **Analiza Giełdowa (AnGG)** jest narzędziem analitycznym służącym do **eksploracji danych rynkowych w ujęciu historycznym, kontekstowym i statystycznym**. Jej głównym celem nie jest generowanie sygnałów inwestycyjnych, lecz **budowa wiedzy o rynku** na podstawie rzeczywistych danych historycznych.

---

## Do czego służy aplikacja

Aplikacja umożliwia:
- eksplorację historycznych notowań spółek giełdowych,
- analizę zachowania wskaźników technicznych i fundamentalnych w czasie,
- badanie relacji pomiędzy ceną a wskaźnikami,
- identyfikację powtarzalnych konfiguracji rynkowych,
- analizę sytuacji, które historycznie poprzedzały wzrosty lub spadki cen,
- ocenę jakości i stabilności sygnałów typu *future*,
- przygotowanie danych i cech wejściowych pod dalsze analizy oraz modele ML.

Aplikacja działa na rzeczywistych danych historycznych i pozwala analizować rynek w sposób:
- **przekrojowy (globalny)**,
- **szczegółowy (pojedyncze spółki)**.

---

## Do czego może przydać się analiza

Analiza realizowana w aplikacji może być wykorzystana m.in. do:

- **lepszego zrozumienia rynku**  
  Pozwala zobaczyć, w jakich warunkach rynkowych pojawiały się wzrosty lub spadki oraz jakie cechy rynku im towarzyszyły.

- **walidacji intuicji inwestycyjnych**  
  Umożliwia sprawdzenie, czy powszechne przekonania (np. dotyczące RSI, momentum, trendu) mają potwierdzenie w danych historycznych.

- **analizy jakości wskaźników**  
  Pomaga ocenić, które wskaźniki:
  - rzeczywiście różnicują sytuacje rynkowe,
  - są stabilne w czasie,
  - niosą informację ponad losowy przypadek (baseline).

- **budowy wiedzy statystycznej**  
  Analiza odpowiada na pytania typu:
  - „Jak często dany sygnał występował w historii?”
  - „Jakie cechy zwiększały prawdopodobieństwo wzrostu?”
  - „Czy dana konfiguracja cech dawała przewagę statystyczną?”

- **przygotowania danych pod machine learning**  
  Wyniki analizy pomagają:
  - wybierać sensowne cechy (feature selection),
  - ograniczać redundancję informacji,
  - definiować etykiety (*future labels*),
  - budować zbiory treningowe i walidacyjne.

---

## Ważne ograniczenia interpretacyjne

- Analiza ma charakter **ex post** (oparta na danych historycznych).
- Wskaźniki typu *future* są **etykietami historycznymi**, a nie sygnałami bieżącymi.
- Aplikacja **nie generuje rekomendacji inwestycyjnych**.
- Wyniki analizy należy traktować jako:
  - źródło wiedzy,
  - materiał do dalszej walidacji,
  - punkt wyjścia do budowy modeli i strategii.

---

## Podsumowanie

**Analiza Giełdowa (AnGG)** jest narzędziem do:

> **rozumienia rynku, a nie jego przewidywania wprost**.

Jej największą wartością jest:
- porządkowanie wiedzy,
- oddzielenie faktów od intuicji,
- tworzenie solidnych podstaw pod zaawansowane analizy i modele predykcyjne.

---

## Instrukcja instalacji i uruchomienia – wersja DEMO (tryb CSV)

### Wymagania wstępne
- System operacyjny: Windows 64-bit
- Zainstalowana Anaconda (Individual Edition)

---

### 1. Instalacja Anaconda

1. Wejdź na stronę:
   https://www.anaconda.com/download
2. Pobierz **Anaconda Individual Edition** dla Windows 64-bit
3. Uruchom instalator:
   - wybierz **Just Me**
   - pozostaw domyślne ustawienia
   - zakończ instalację

### 2. Uruchomienie Anaconda Prompt

1. Otwórz menu **Start**
2. Uruchom:
   **Anaconda Prompt**


### 3. Przejście do katalogu projektu

W Anaconda Prompt:
cd <ścieżka_do_katalogu_z_projektem>\AnGG_DEMO_v01

W katalogu muszą znajdować się pliki:

- `environment_demo_min.yml`
- `app.py`

Plik `.env` **nie jest wymagany** w wersji DEMO.


### 4. Utworzenie środowiska Conda

Jeśli środowisko już istnieje:

bat
conda env remove -n angg_demo_01

Utworzenie środowiska:
conda env create -f environment_demo_min.yml

### 5. Aktywacja środowiska

conda activate angg_demo_01

### 6. Uruchomienie aplikacji

streamlit run app.py


### 7. Dostęp do aplikacji

Aplikacja będzie dostępna pod adresem:
http://localhost:8501

Zatrzymanie aplikacji:
Ctrl + C



Instalacja aplikacji w środowisku Streamlit Cloude, nie korzysta z pliku `environment_demo_min.yml`. Wykorzystuje plik `requirements.txt`. Przykładowe pliki dla wersji DEMO znajdują się w katalogu:
AnGG\demo


### Uwagi końcowe

- aplikacja działa w trybie DEMO (CSV),
- połączenie z bazą danych nie jest wymagane,
- tryb pracy aplikacji jest konfigurowany statycznie w app_params.py.





---

## Relacje z innymi ADR

- ADR-003 – architektura UI Streamlit  
- ADR-004 – model danych wskaźników  
- ADR-009 – zasady czytania danych  
- ADR-008 – interpretacja wskaźników i sygnałów

ADR-010 nie dubluje tych dokumentów – **opisuje ich wspólne działanie w aplikacji**.

