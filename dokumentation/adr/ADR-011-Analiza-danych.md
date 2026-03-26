# ADR-011 – Analiza danych (warstwa eksploracyjna pod ML)

- **Status:** Proposed  
- **Data:** 2026-01-31  
- **Zakres:** Analiza danych / warstwa eksploracyjna / UI Streamlit  
- **Powiązane ADR:**
  - ADR-002 – Środowisko i warstwa prezentacji (Streamlit)
  - ADR-003 – Architektura warstwy UI Streamlit
  - ADR-004 – Model przechowywania wskaźników (wide)
  - ADR-007 – Wskaźniki typu future (etykietowanie danych)
  - ADR-008 – Interpretacja wskaźników future i sygnałów prob
  - ADR-009 – Zasady czytania danych i generowania datasetów

---

## 1. Kontekst

Projekt **Analiza giełdowa (AnGG)** osiągnął etap, w którym:
- dostępna jest pełna baza danych historycznych (prices + indicators),
- istnieją wskaźniki typu **future** (`fut_barrier`, `fut_imp`, `fut_signal`, w tym `fut_signal_20_hyb`),
- możliwa jest analiza pojedynczych spółek.

Kolejnym krokiem jest przygotowanie **warstwy eksploracyjnej całej bazy danych**, której celem jest:
- identyfikacja analogii historycznych,
- zrozumienie relacji: *cechy rynku → etykiety future*,
- świadome przygotowanie gruntu pod przyszłe modele ML (`prob`).

W tym celu projektowany jest ekran **„Analiza danych”** w aplikacji Streamlit.

Kontrakt jednostki obserwacji ML
- W całym projekcie AnGG jednostką obserwacji jest rekord typu (spółka, dzień); różnice pomiędzy df_market i df_market_all dotyczą wyłącznie zakresu danych, nie struktury.

---

## 2. Cel ADR

Celem niniejszego ADR jest:
- formalne zdefiniowanie roli i zakresu ekranu „Analiza danych”,
- ustalenie źródła danych i kontraktu DataFrame,
- określenie sposobu uruchamiania analiz i ich niezależności,
- zaprojektowanie mechanizmu podsumowania wyników eksploracji,
- zapewnienie spójności architektonicznej i UX z resztą aplikacji.

---

## 3. Decyzje architektoniczne

## 3.1. Definicja `df_market`

**Decyzja:**

`df_market` jest kanonicznym datasetem analitycznym używanym na ekranie  
**„Analiza danych”**.

### Definicja

- **1 wiersz = 1 spółka × 1 dzień**
- zawiera:
  - dane cenowe (OHLCV),
  - wszystkie wskaźniki opisowe (techniczne / fundamentalne),
  - wszystkie wskaźniki typu **future** (`fut_*`).

### Konsekwencje

- brak pracy bezpośrednio na tabelach SQL,
- brak łączenia wielu DataFrame’ów w warstwie UI,
- pełna zgodność z modelem **wide** (ADR-004),
- naturalny input pod przyszłe ML.

---

## 3.2. Miejsce budowy datasetu

**Decyzja:**

`df_market` jest budowany **wyłącznie** na ekranie **„Podgląd danych”**.

### Ekran „Analiza danych”:

- nie ładuje danych samodzielnie,
- nie zmienia zakresu danych,
- działa wyłącznie na już przygotowanym `df_market`.

Jeżeli `df_market` **nie istnieje** w `session_state`, analiza nie jest dostępna.

Dodatkowo, dla analiz globalnych (market-wide) obowiązuje analogiczna zasada dla datasetu **df_market_all** (session_state: `do_df_market_all`). Dataset ten jest budowany wyłącznie w module **„Przegląd danych”**. Ekrany analiz nie mogą tworzyć własnych wersji datasetu „ALL” ani stosować fallbacków generujących dane market-wide.


---

## 3.3. Wybór analizowanego sygnału future

**Decyzja:**

Przed rozpoczęciem analiz użytkownik **jawnie wybiera**, który sygnał `fut_*`
jest analizowany.

### Przykłady

- `fut_signal_20_hyb` (domyślny),
- `fut_signal_20`,
- wybrane `fut_barrier_*`,
- `fut_imp_*`.

### Znaczenie

- ten sam schemat analiz może być użyty dla różnych sygnałów,
- możliwe jest porównywanie:
  - „na co reaguje dany sygnał”,
  - „jakie cechy są istotne dla różnych etykiet future”,
- pełna zgodność z podejściem ML  
  (**target wybierany jawnie**).

---

## 3.4. Charakter analiz – brak pipeline’u decyzyjnego

**Decyzja:**

Analizy na ekranie **„Analiza danych”** są:

- niezależne od siebie,
- uruchamiane jawnie przyciskiem,
- zawsze pracujące na tym samym `df_market`.

### Wynik jednej analizy

- jest natychmiast prezentowany,
- **nie wpływa automatycznie** na kolejne analizy,
- nie zmienia danych wejściowych innych sekcji.

### Uzasadnienie

- zachowanie interpretowalności,
- brak ukrytej logiki,
- eksploracja zamiast optymalizacji.

---

## 3.5. Lokalizacja i rola kodu UI

**Decyzja:**

Ekran **„Analiza danych”** jest zaimplementowany w pliku:


app/ui/analysis_view.py

### Rola pliku
- orkiestracja UX,
- zarządzanie session_state,
- wywoływanie funkcji analitycznych,
- renderowanie wyników.

### Plik nie zawiera
- ciężkiej logiki obliczeniowej,
- transformacji danych,
- kodu ML.


## 4. Zakres analiz dostępnych na ekranie

Ekran **„Analiza danych”** obejmuje następujące klasy analiz:

### 4.1. Kontekst datasetu

- liczba obserwacji,
- liczba spółek,
- zakres dat,
- rozkład wybranego sygnału `fut_*`.

Celem tej sekcji jest szybka walidacja:
- skali danych,
- kompletności,
- sensowności rozkładu etykiet future.

---

### 4.2. Analiza rozkładów cech

- porównanie rozkładów cech warunkowo na wybrany `fut_*`,
- wizualizacje:
  - histogramy,
  - boxploty,
- statystyki opisowe:
  - percentyle,
  - różnice median.

Celem jest ocena:
- czy dana cecha w ogóle różnicuje przyszłość,
- w jakim kierunku działa zależność.

---

### 4.3. Analiza konfiguracji (setupów)

- definiowanie logicznych kombinacji cech
  (np. RSI, trend, zmienność, wolumen),
- obliczanie:
  - liczby przypadków,
  - hit-ratio względem wybranego `fut_*`,
- ocena stabilności setupów w czasie.

Celem jest identyfikacja:
- sensownych konfiguracji rynkowych,
- potencjalnych interakcji cech.

---

### 4.4. Analogie historyczne

- wyszukiwanie podobnych dni w przestrzeni cech,
- analiza przyszłych outcome’ów dla analogii,
- agregaty statystyczne (np. udział pozytywnych przypadków).

Analiza ta stanowi:
- proto-podejście do sygnałów `prob`,
- bez użycia modeli ML.

---

### 4.5. Stabilność w czasie

- analiza trwałości zależności w różnych okresach,
- rolling windows,
- podział na lata lub reżimy rynkowe,
- identyfikacja driftu cech i zależności.

Celem jest odróżnienie:
- stabilnych relacji,
- przypadkowych korelacji historycznych.

---

## 5. Mechanizm podsumowania wyników

### 5.1. Gromadzenie insightów

**Decyzja:**

Każda analiza pozostawia po sobie ustrukturyzowany insight,
zapisywany w `session_state` aplikacji.

Zakres pojedynczego insightu obejmuje m.in.:

- nazwę cechy lub setupu,
- analizowany sygnał `fut_*`,
- kierunek zależności,
- siłę efektu,
- stabilność w czasie,
- liczność obserwacji.

Insighty te nie są rekomendacjami,
lecz zapisem wiedzy eksploracyjnej.

---

### 5.2. Podsumowanie końcowe

Na końcu ekranu **„Analiza danych”** prezentowane jest podsumowanie obejmujące:

- ranking cech i setupów względem wybranego `fut_*`,
- mapy zależności (np. heatmapy),
- automatyczne, opisowe wnioski.

Podsumowanie:
- nie zawiera rekomendacji inwestycyjnych,
- ma charakter informacyjno-analityczny.

---

## 6. UX i spójność wizualna

**Decyzja:**

Ekran **„Analiza danych”** zachowuje spójność UX
z ekranem **„Podgląd danych”**.

Zasady:

- umiarkowana wielkość czcionek,
- niewielkie odstępy między sekcjami,
- wysoka gęstość informacji,
- brak elementów prezentacyjnych typu „hero”.

Charakter ekranu:

> narzędzie analityczne,  
> nie dashboard marketingowy.

---

## 7. Konsekwencje

### 7.1. Pozytywne

- spójna, interpretowalna warstwa eksploracyjna,
- pełna gotowość danych i logiki pod ML,
- brak look-ahead bias,
- możliwość porównywania różnych sygnałów `fut_*`,
- naturalne przejście:
  eksploracja → feature engineering → ML.

---

### 7.2. Ograniczenia

- brak automatycznej optymalizacji,
- brak rekomendacji inwestycyjnych,
- ciężkie obliczenia wymagają świadomego uruchamiania przez użytkownika.

---

## 8. Status dalszych prac

- implementacja ekranu **„Analiza danych”** zgodnie z niniejszym ADR,
- wybór i implementacja zestawu analiz MVP,
- rozwój mechanizmu gromadzenia insightów,
- aktualizacja `ARCHITECTURE_SUMMARY.md` po akceptacji ADR.


Powiązanie z ML: Szczegóły ML-01 i warstwy ML opisuje ADR-012.
