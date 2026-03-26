# ADR-012 – Warstwa ML: datasety, eksperymenty ML-01 i sygnały `prob`

- **Status:** Proposed  
- **Data:** 2026-02-11  
- **Zakres:** Warstwa ML / przygotowanie datasetów / eksperymenty ML-01 / interpretowalne `prob`  
- **Powiązane ADR:**
  - ADR-004 – Model przechowywania wskaźników (wide)
  - ADR-007 – Wskaźniki typu future (etykietowanie danych historycznych)
  - ADR-008 – Interpretacja wskaźników future i sygnałów `prob`
  - ADR-009 – Zasady czytania danych i generowania datasetów
  - ADR-011 – Analiza danych (warstwa eksploracyjna)

---

## 1. Kontekst

Projekt AnGG posiada:
- historyczne notowania i wskaźniki (wide),
- etykiety typu `future` jako label historyczny,
- warstwę semantyczną interpretacji (`ADR-008`).

Kolejnym krokiem jest zbudowanie **spójnej, kontrolowanej warstwy ML**, której celem jest:
- eksploracyjna walidacja relacji *features (t) → labels future*,
- przygotowanie fundamentu pod **interpretowalne sygnały probabilistyczne (`prob`)**,
- ochrona przed błędami metodologicznymi (leakage, look-ahead bias),
- zapewnienie powtarzalności w kolejnych iteracjach ML.

Etap **ML-01** ma charakter **eksploracyjno-analityczny**, nie produkcyjny
i nie stanowi strategii inwestycyjnej.

---

## 2. Cel ADR

Celem ADR-012 jest:
- ustalenie **kanonicznego podziału danych w czasie** (TRAIN/VALIDATION/TEST),
- ustalenie **miejsca i kontraktu budowy datasetów ML**,
- zdefiniowanie **problemu ML** (co model ma, a czego nie ma przewidywać),
- zdefiniowanie **targetu ML-01** oraz podejścia do nierównowagi klas,
- ustalenie zasad oceny modeli (metryki, thresholding),
- przyjęcie kanonicznego podejścia do **selekcji sygnałów jako rankingu (`prob`)**.

---

## 3. Decyzje architektoniczne

### 3.1. Kanoniczny time-based split (TRAIN / VALIDATION / TEST)

**Decyzja:**
Dla ML przyjmujemy **globalny, kanoniczny podział czasowy** na zbiory:
TRAIN, VALIDATION, TEST. Podział jest definiowany raz i obowiązuje
we wszystkich iteracjach ML.

**Definicja datasetów:**
| Dataset | Zakres dat | Rola |
|------|-----------|------|
| TRAIN | 1990-01-01 – 2015-12-31 | nauka relacji |
| VALIDATION | 2016-01-01 – 2019-12-31 | tuning / decyzje ML |
| TEST | 2020-01-01 – 2025-12-31 | symulacja przyszłości |

**Zasady:**
- zakresy są jawne, rozłączne i niezmienne,
- dane raz użyte jako TEST nie mogą pełnić roli TRAIN ani VALIDATION.

---

### 3.2. Miejsce budowy datasetów ML

**Decyzja:**
Kanoniczne datasety ML są budowane **centralnie** w dedykowanej warstwie przygotowania danych:
`app/ml/ml_datasets.py`.

**Zasady:**
- budowa datasetów bazuje wyłącznie na `df_market_all`,
- proces jest wykonywany **lazy (na żądanie)**,
- wynik jest cache’owany w `session_state`,
- budowa datasetów nie jest powielana w poszczególnych ekranach ML.

**Kontrakt użycia:**
Warstwa ML operuje wyłącznie na:
- `df_market_train`
- `df_market_validation`
- `df_market_test`

Filtrowanie po dacie jest dozwolone wyłącznie w warstwie budowy datasetów.

---


### 3.3. Zasady użycia TRAIN/VALIDATION/TEST w ML-01

**Decyzja (ML-01):**
- używane są zbiory: **TRAIN oraz VALIDATION**,
- zbiór **TEST** jest jawnie wydzielony i **pozostaje nieużywany („zamrożony”)**,
  aby zachować niezależny zbiór holdout do końcowej oceny (symulacja przyszłości)
  w kolejnych etapach (ML-02/ML-03) lub przy domknięciu iteracji.

**Uzasadnienie:**
- TRAIN służy do uczenia relacji cechy → etykiety future,
- VALIDATION służy do wyboru modeli / konfiguracji / progów i oceny roboczej,
- TEST pozostaje „czysty” metodologicznie (brak ryzyka dopasowania pod test),
  zgodnie z praktyką projektów ML i chronologią danych.

---

### 3.4. Definicja problemu ML: co przewidujemy

**Decyzja:**
Modele ML nie przewidują cen ani kierunku rynku.
Uczą się zależności:

> **cechy rynku w dniu `t` → jakość przyszłego outcome’u historycznego**

Etykiety typu `future` pełnią rolę **labeli historycznych** i są wykorzystywane wyłącznie do:
- analizy ex post,
- treningu modeli ML,
- budowy `prob`.

Nie są sygnałami bieżącymi ani decyzyjnymi.

---

### 3.5. Target ML-01: agregacja sygnałów future

**Decyzja:**
W ML-01 stosujemy zagregowany target logiczny:

`ANY_fut_signal`

**Definicja:**
Target = 1, jeżeli **którykolwiek** z wybranych sygnałów `fut_signal_*`
przyjmuje wartość pozytywną w danym dniu historycznym.

Przykładowy zbiór:
- `fut_signal_2`
- `fut_signal_20`
- `fut_signal_60`
- `fut_signal_120`
- `fut_signal_20_hyb`

**Uzasadnienie:**
- zwiększenie częstości klasy pozytywnej,
- stabilniejsze metryki,
- uproszczenie problemu na etap eksploracyjny,
- brak naruszenia architektury danych (sygnały źródłowe pozostają dostępne).

---

### 3.6. Nierównowaga klas (class imbalance)

**Decyzja:**
Nierównowaga klas jest **cechą rynku**, a nie błędem danych.

**Zasady:**
- nie usuwamy klasy 0,
- nie robimy losowego downsamplingu.

**Dopuszczalne techniki:**
- wagi klas (`class_weight`),
- cost-sensitive learning,
- analiza progów decyzyjnych,
- interpretacja rankingowa score (`prob`).

---

### 3.7. Metryki dla ML-01

**Decyzja:**
Dobór metryk musi uwzględniać:
- ekstremalnie rzadką klasę pozytywną,
- charakter problemu: wykrywanie zdarzeń.

(W ML-01 metryki służą ocenie porównawczej, nie “produkcyjnej”.)

---

### 3.8. Próg decyzyjny i kalibracja interpretacji

**Decyzja:**
Wyjście modelu ML interpretujemy jako **prawdopodobieństwo / score** zajścia zdarzenia,
a nie decyzję binarną.

**Zasady:**
- próg 0.5 nie jest traktowany jako domyślnie sensowny,
- próg jest parametryzowany,
- analizujemy kompromis precision ↔ recall.

---

### 3.9. Threshold tuning przez Precision–Recall Curve

**Decyzja:**
Strojenie progów odbywa się w oparciu o analizę **Precision–Recall Curve**,
a nie pojedynczą metrykę.
Nie ma jednego “uniwersalnie optymalnego” progu.

---

### 3.10. Feature importance: rola eksploracyjna

**Decyzja:**
Analiza istotności cech ma charakter **pomocniczy i eksploracyjny**.
Celem nie jest wybór “produkcyjnego” feature setu, tylko zrozumienie relacji cech z labelami.

---

### 3.11. Selekcja sygnałów jako ranking (`prob`) – podejście kanoniczne ML-01

**Decyzja:**
W ML-01 `prob` traktujemy **rankingowo**, nie jako predykcję binarną.

Celem jest elitarna selekcja niewielkiej liczby sygnałów o wysokiej jakości:
- wysoka trafność (precision),
- minimalizacja FP,
- dopuszczalny niski recall,
- brak wymogu generowania sygnałów w każdym oknie czasu.

**Kanoniczna kolejność filtrów (ML-01):**
1) **Top-K**: w oknie czasowym wybieramy maksymalnie `K` obserwacji o najwyższym `prob`.  
2) **Top-Pct**: zachowujemy jedynie procent najlepszych obserwacji `top_score_pct`.

Jeśli po filtracji:
- liczba sygnałów < K → poprawne,
- liczba sygnałów = 0 → poprawne (brak jakościowych setupów).

**Parametry kanoniczne (konfigurowalne):**
- `window_sessions` – liczba sesji w oknie rankingowym,
- `max_signals` – maksymalna liczba kandydatów (Top-K), np. {5, 10, 20},
- `top_score_pct` – procent najlepszych obserwacji, np. {0.001, 0.005, 0.01}.

**Odrzucona alternatywa (jako główny filtr):**
- stały próg `min_prob` – odrzucony jako kanoniczny mechanizm selekcji
  ze względu na brak gwarancji kalibracji oraz zmienność w czasie i między modelami.
  `min_prob` może być analizowany pomocniczo.

**Implementacja w UI (ML-01):**
- zakładki eksperymentalne:
  1) Top-K → Top-Pct (wariant kanoniczny)
  2) Top-Pct → Top-K (wariant kontrolny porównawczy)
- obliczenia uruchamiane wyłącznie na żądanie użytkownika,
- agregacja wyników w tabeli obejmującej kombinacje parametrów,
- domyślne sortowanie: (1) precision ↓, (2) liczba sygnałów ↑.

---

### 3.12. Charakter etapu ML-01

**Decyzja:**
ML-01 jest etapem:
- eksploracyjnym,
- badawczym,
- interpretacyjnym,

i nie jest etapem:
- produkcyjnym,
- decyzyjnym,
- strategii inwestycyjnej.

Wyniki ML-01 służą jako:
- wejście do feature engineering,
- fundament pod sygnały `prob`,
- podstawa do kolejnych iteracji ML (ML-02…).

---

## 4. Konsekwencje

### Pozytywne
- spójny i powtarzalny kontrakt ML (datasety, role, brak “przecieków”),
- minimalizacja ryzyka leakage i look-ahead bias,
- przygotowanie pod interpretowalny `prob` (ranking, nie decyzja binarna),
- możliwość bezpiecznej rozbudowy etapów ML bez zmiany fundamentów.

### Ograniczenia / koszty
- “sztywne” role datasetów ograniczają swobodę eksperymentów ad-hoc (celowo),
- ML-01 nie daje “gotowej strategii” – wyniki są eksploracyjne,
- część analiz może być kosztowna obliczeniowo (wymaga uruchamiania na żądanie).

---

## 5. Dalsze kroki
- Uporządkować ekrany ML w UI (ML-01 jako eksperymentalny benchmark),
- Doprecyzować w kolejnych ADR: ML-02 (walidacja, tuning, stabilność w czasie),
- Zdefiniować minimalny kontrakt zapisu/ekspozycji `prob` w aplikacji (jeśli powstanie).





## 6. Plan przygotowania danych i eksperymentów ML (ML-01)

Niniejszy rozdział definiuje **plan działań oraz założenia projektowe**
dla etapu **ML-01**, którego celem jest:

- przygotowanie danych pod przyszłe modele ML,
- walidacja sensowności sygnałów typu `future`,
- zbudowanie fundamentu pod interpretowalne sygnały probabilistyczne (`prob`),
- uniknięcie błędów metodologicznych (look-ahead bias, leakage, niestabilne metryki).

Etap ML-01 ma charakter **eksploracyjno-analityczny**, a nie produkcyjny.
Nie prowadzi do rekomendacji inwestycyjnych ani automatycznych decyzji.

---

### 6.1. Zasada podziału danych w czasie (Time-based split)

**Status:** Accepted (założenia)  

**Decyzja:**

Dla potrzeb etapu **ML-01** oraz kolejnych iteracji ML
przyjęto **kanoniczny, globalny podział czasowy datasetu `df_market_all`**
na trzy zbiory: TRAIN, VALIDATION oraz TEST.

Podział ten jest definiowany **raz** i obowiązuje
we wszystkich etapach rozwoju ML w projekcie AnGG.
Kolejne iteracje ML mogą wykorzystywać różne podzbiory tego podziału,
ale **nie redefiniują ról danych**.

---

#### Kanoniczny podział czasowy

| Zbiór | Zakres dat | Rola | Znaczenie |
|-----|-----------|------|----------|
| TRAIN | 1990-01-01 – 2015-12-31 | trening | nauka relacji cechy → etykiety future |
| VALIDATION | 2016-01-01 – 2019-12-31 | walidacja | tuning modeli i decyzji ML |
| TEST | 2020-01-01 – 2025-12-31 | test | niezależny holdout / symulacja przyszłości |

Dane historyczne w projekcie rozpoczynają się około roku 1990,
co zapewnia wystarczająco długi horyzont do nauki modeli
w różnych reżimach rynkowych.

---

#### Wykorzystanie zbiorów w etapie ML-01

Na etapie **ML-01**:

- wykorzystywane są zbiory:
  - **TRAIN**
  - **VALIDATION**
- zbiór **TEST**:
  - jest jawnie wydzielony,
  - pozostaje **nieużywany („zamrożony”, holdout)**,
  - nie bierze udziału ani w treningu, ani w ocenie roboczej modeli.

Takie podejście:
- jest zgodne z praktyką projektów ML (holdout test),
- eliminuje ryzyko dopasowania decyzji pod zbiór testowy,
- zachowuje TEST jako niezależną „symulację przyszłości” do końcowej oceny.

---

#### Uzasadnienie podziału

- długi zbiór TRAIN (~25 lat) pozwala modelom:
  - uczyć się na różnych reżimach rynkowych,
  - identyfikować stabilniejsze relacje historyczne,
- okres VALIDATION (2015–2020):
  - stanowi naturalny bufor pomiędzy treningiem a testem,
  - obejmuje inny reżim rynkowy niż TRAIN,
- okres TEST (2020–2025):
  - zawiera skrajne warunki rynkowe (m.in. COVID, wysoka zmienność),
  - pełni rolę realistycznej symulacji przyszłości.

Podział ten jest uznany za:
- metodologicznie poprawny,
- adekwatny do charakteru danych giełdowych,
- zgodny z celem etapu ML-01 (eksploracja i przygotowanie pod ML).

---

#### Konsekwencje

- dane raz użyte jako **TEST** nie zmieniają roli w kolejnych etapach ML,
- VALIDATION pozostaje „czysta” dla przyszłego strojenia modeli,
- wyniki ML-01 nie są skażone wiedzą o danych walidacyjnych.


### Kanoniczne datasety ML (TRAIN / VALIDATION / TEST)

**Status:** Accepted / Implemented  

**Decyzja:**

W projekcie AnGG wprowadzono koncepcję **trzech kanonicznych datasetów ML**
opartych o niezmienny podział czasowy:

- `df_market_train`
- `df_market_validation`
- `df_market_test`

Datasety te stanowią **jedyny dopuszczalny interfejs danych**
dla ekranów i modułów ML (ML-01, ML-02, ML-03, …).

Bezpośrednie użycie `df_market_all` w warstwie ML jest zabronione.

---

#### Definicja datasetów

| Dataset | Zakres dat | Rola |
|------|-----------|------|
| TRAIN | 1990-01-01 – 2015-12-31 | nauka relacji |
| VALIDATION | 2016-01-01 – 2019-12-31 | tuning / decyzje ML |
| TEST | 2020-01-01 – 2025-12-31 | symulacja przyszłości |

Zakresy czasowe są:
- jawne,
- rozłączne (brak nakładania),
- niezmienne w kolejnych iteracjach ML.

---

#### Miejsce tworzenia datasetów

Kanoniczne datasety ML są tworzone **centralnie**
w dedykowanej warstwie przygotowania danych ML
(`app/ml/ml_datasets.py`).

Proces ten:
- bazuje wyłącznie na `df_market_all`,
- jest wykonywany **lazy (na żądanie)**,
- jest cache’owany w `session_state`,
- nie jest powielany w poszczególnych ekranach ML.

Dzięki temu:
- koszt obliczeniowy ponoszony jest tylko wtedy,
  gdy użytkownik przechodzi do warstwy ML,
- kolejne ekrany ML mogą być uruchamiane niezależnie od siebie,
- nie istnieje zależność kolejności (np. ML-02 nie wymaga wcześniejszego uruchomienia ML-01).

---

#### Kontrakt architektoniczny

Obowiązują następujące zasady:

- warstwa ML operuje **wyłącznie** na:
  - `df_market_train`
  - `df_market_validation`
  - `df_market_test`
- filtrowanie po dacie jest dozwolone
  **wyłącznie** w warstwie budowy datasetów,
- role datasetów nie mogą być zmieniane pomiędzy iteracjami ML,
- dane raz użyte jako TEST nie mogą pełnić roli TRAIN ani VALIDATION.

Takie podejście eliminuje:
- ryzyko data leakage,
- błędy wynikające z niedopilnowania filtrów czasowych,
- niejawne użycie danych z przyszłości.

---

#### Wykorzystanie datasetów w etapach ML

- **ML-01:**  
  - używa `df_market_train` i `df_market_validation`,  
  - `df_market_test` pozostaje niewykorzystany („zamrożony”, holdout).

- **ML-02 i kolejne:**  
  - wykorzystują pełny zestaw: `df_market_train`, `df_market_validation`, `df_market_test`,  
  - z zasadą: tuning/iteracje na TRAIN+VALIDATION, a TEST tylko do finalnej oceny.


---

### 6.2. Definicja problemu ML i rola etykiet `future`

**Decyzja:**

Modele ML nie przewidują cen ani kierunku rynku,
lecz uczą się zależności:

> *cechy rynku w dniu `t` → jakość przyszłego outcome’u historycznego*

Etykiety typu `future` pełnią rolę **labeli historycznych**
i są wykorzystywane wyłącznie do:
- analizy ex post,
- treningu modeli ML,
- budowy sygnałów probabilistycznych (`prob`).

Nie są sygnałami bieżącymi ani decyzyjnymi.

---

### 6.3. Target ML-01 – agregacja sygnałów future

**Decyzja:**

W etapie ML-01 wprowadzony zostaje **zagregowany target logiczny**:

`ANY_fut_signal`

#### Definicja logiczna

Target przyjmuje wartość `1`, jeżeli **którykolwiek** z wybranych sygnałów
`fut_signal_*` przyjmuje wartość pozytywną w danym dniu historycznym.

Przykładowy zbiór sygnałów:
- `fut_signal_2`
- `fut_signal_20`
- `fut_signal_60`
- `fut_signal_120`
- `fut_signal_20_hyb`

#### Uzasadnienie

- zwiększenie częstości klasy pozytywnej,
- stabilniejsze metryki ML,
- uproszczenie problemu decyzyjnego,
- lepsze dopasowanie do etapu eksploracyjnego,
- brak naruszenia istniejącej architektury danych.

Indywidualne sygnały `fut_signal_*` pozostają dostępne
do analiz szczegółowych i porównań.

---

### 6.4. Nierównowaga klas (class imbalance)

**Decyzja:**

Naturalna nierównowaga klas (`+1` jako zdarzenie rzadkie)
jest **cechą rynku**, a nie błędem danych.

#### Założenia

- brak sztucznego balansowania danych przez usuwanie klasy `0`,
- brak losowego downsamplingu,
- zachowanie rzeczywistego rozkładu rynku.

#### Dopuszczalne techniki

- wagi klas (`class_weight`),
- cost-sensitive learning,
- analiza progów decyzyjnych,
- zmiana interpretacji wyjścia modelu (ranking / score).

---

### 6.5. Metryki oceny modeli ML

**Decyzja:**

Metryka `accuracy` nie jest używana jako główne kryterium oceny modeli ML.

#### Metryki referencyjne

- recall dla klasy pozytywnej (`+1`),
- precision dla klasy pozytywnej (`+1`),
- F1-score,
- Precision–Recall Curve (PR),
- ROC AUC (pomocniczo).

Dobór metryk wynika z:
- ekstremalnie rzadkiej klasy pozytywnej,
- charakteru problemu (wykrywanie zdarzeń).

---

### 6.6. Próg decyzyjny (decision threshold)

**Decyzja:**

Wyjście modelu ML interpretowane jest jako **prawdopodobieństwo**
zajścia zdarzenia historycznego, a nie jako decyzja binarna.

#### Założenia

- domyślny próg 0.5 nie jest uznawany za sensowny,
- próg decyzyjny jest parametryzowany,
- użytkownik analizuje kompromis precision ↔ recall.

#### Cel

- przejście z predykcji binarnej
  do **kontrolowanej interpretacji probabilistycznej**,
- przygotowanie gruntu pod sygnały `prob`.

---

### 6.7. Threshold tuning i Precision–Recall Curve

**Decyzja:**

Strojenie progów decyzyjnych odbywa się w oparciu o analizę
**Precision–Recall Curve**, a nie pojedynczą metrykę.

#### Założenia

- każdy punkt krzywej PR odpowiada innemu progowi decyzyjnemu,
- wybór progu zależy od celu analitycznego,
- brak „jednego optymalnego progu uniwersalnego”.

Etap ten stanowi **most pomiędzy ML a interpretacją decyzyjną**.

---

### 6.8. Interpretacja cech (feature importance)

**Decyzja:**

Analiza istotności cech ma charakter **pomocniczy i eksploracyjny**.

#### Założenia

- istotność cech liczona względem metryk adekwatnych
  do rzadkiej klasy (np. recall, F1, PR),
- brak interpretacji absolutnej (ranking, nie prawda obiektywna),
- analiza stabilności importance w czasie.

Celem nie jest selekcja cech produkcyjnych,
lecz **zrozumienie relacji cech z etykietami future**.

---

### 6.9. Charakter etapu ML-01

**Podsumowanie:**

ML-01 jest etapem:
- eksploracyjnym,
- badawczym,
- interpretacyjnym.

Nie jest etapem:
- produkcyjnym,
- decyzyjnym,
- strategii inwestycyjnej.

Wyniki ML-01 służą jako:
- wejście do feature engineering,
- fundament pod sygnały `prob`,
- podstawa do kolejnych ADR i iteracji ML.



---

### 6.10. Selekcja elitarnych sygnałów (ranking + filtr jakościowy)

#### Status
Proposed / Accepted (eksperymentalne – ML-01)

#### Kontekst

Na etapie **ML-01** celem nie jest maksymalizacja liczby wykrytych zdarzeń,
lecz identyfikacja **niewielkiej liczby najwyższej jakości sygnałów**,
które:

- mają możliwie **wysoką trafność (precision)**,
- generują **minimalną liczbę fałszywych alarmów (FP)**,
- mogą pomijać część prawdziwych zdarzeń (niski recall jest akceptowalny),
- odpowiadają realnym ograniczeniom decyzyjnym (nie da się reagować na wszystko).

W tym celu wyjście modelu ML (`prob`) traktowane jest **rankingowo**,
a nie jako predykcja binarna.

---

#### Decyzja – zasada selekcji

W etapie ML-01 przyjęto następującą **kanoniczną kolejność filtrów**:

1. **Selekcja ilościowa (rankingowa)**  
   W danym oknie czasowym wybierane jest maksymalnie `K`
   obserwacji o najwyższym score (`prob`).

2. **Selekcja jakościowa (rankingowa)**  
   Z powyższego zbioru zachowywany jest jedynie
   określony **procent najlepszych obserwacji** (`top_score_pct`),
   liczony względem rankingu score.

Jeżeli po zastosowaniu obu filtrów:
- liczba sygnałów jest mniejsza niż `K` – jest to zachowanie poprawne,
- liczba sygnałów wynosi `0` – oznacza to brak wystarczająco jakościowych setupów
  w danym okresie.

Nie istnieje wymóg generowania sygnałów w każdym oknie czasowym.

---

#### Uzasadnienie wyboru kolejności

Przyjęta kolejność (Top-K → Top-Pct):

- gwarantuje, że rozważane są wyłącznie **najlepsze kandydaty**,
- eliminuje „dolną część rankingu”, nawet jeśli formalnie mieści się w Top-K,
- umożliwia **elitarną selekcję** (np. 3–5 bardzo dobrych sygnałów zamiast 20 przeciętnych),
- odpowiada praktycznemu scenariuszowi decyzyjnemu:
  > „wolę kilka niemal pewnych sygnałów niż wiele niepewnych”.

---

#### Parametry selekcji (kanoniczne)

Parametry selekcji są **jawnie definiowane w konfiguracji aplikacji**
(np. `app_params.py`) i nie są dobierane automatycznie.

##### 1. Maksymalna liczba kandydatów
text
max_signals ∈ {5, 10, 20}
Znaczenie:
„Ile najlepszych setupów w ogóle biorę pod uwagę w danym okresie.”


3. Filtr jakościowy (rankingowy)
top_score_pct ∈ {0.001, 0.005, 0.01}


##### Znaczenie:
- „Jaki procent najlepszych obserwacji (wg score) uznaję za wystarczająco wysokiej jakości.”

Parametr top_score_pct:
- nie zależy od kalibracji prob,
- działa czysto rankingowo,
- zapewnia porównywalność wyników w różnych reżimach rynkowych.

##### Odrzucone alternatywy

- Stały próg prawdopodobieństwa (min_prob)
Odrzucony jako główny filtr decyzyjny ze względu na:
  - brak gwarancji kalibracji prob,
  - zmienność interpretacji progu w czasie i między modelami.

min_prob może być analizowany pomocniczo, ale nie stanowi kanonicznego mechanizmu selekcji w ML-01.

##### Implementacja w UI (ML-01)

W ramach ekranu ML-01 wprowadzane są dedykowane zakładki eksperymentalne:

1. Selekcja: Top-K → Top-Pct (Quality-First)
Kanoniczny wariant opisany powyżej.
2. Selekcja: Top-Pct → Top-K (wariant kontrolny)
Wariant porównawczy, służący wyłącznie do walidacji hipotez.

Cechy wspólne zakładek:

- obliczenia uruchamiane wyłącznie na żądanie użytkownika (checkbox typu „Przelicz tabelę”),
- brak obliczeń przy samym wejściu na zakładkę,
- prezentacja wyników w zagregowanej tabeli (macierzy), obejmującej wszystkie kombinacje parametrów,
- domyślne sortowanie wyników wg:
  1. precision (malejąco),
  2. liczby wybranych sygnałów (rosnąco).
Pod tabelą prezentowana jest legenda mapująca nazwy techniczne parametrów i kolumn na ich znaczenie biznesowo-analityczne.

#### Metryki raportowane dla kombinacji parametrów

Dla każdej kombinacji (window_sessions, max_signals, top_score_pct) raportowane są m.in.:
- liczba wybranych sygnałów,
- liczba trafień (TP),
- liczba fałszywych alarmów (FP),
- precision,
- pomocniczo: statystyki score (np. średni / minimalny).

Metryki te mają charakter porównawczy i eksploracyjny, a nie produkcyjny.

#### Charakter decyzji

Opisana selekcja:
- nie stanowi strategii inwestycyjnej,
- nie generuje rekomendacji „kup / sprzedaj”,
- jest narzędziem badania jakości rankingów ML oraz przygotowania gruntu pod przyszłą warstwę decyzyjną.

Decyzja obowiązuje wyłącznie etap ML-01 i może zostać zmodyfikowana w kolejnych iteracjach projektu na podstawie wyników empirycznych.



---

## 7. Rejestracja modeli ML i zapis artefaktów eksperymentu

### Status
Accepted / Implemented

### Kontekst

Eksperyment ML-01 generuje wiele konfiguracji modeli
(algorytm, target, parametry rankingu, zestaw filtrów).

Aby zapewnić:

- powtarzalność wyników,
- możliwość odtworzenia eksperymentu,
- kontrolę konfiguracji modelu,
- oddzielenie eksperymentów od runtime aplikacji,

wprowadzono **mechanizm zapisu modeli oraz ich metadanych**.

---

### Decyzja

Modele trenowane w ML-01 mogą być zapisane jako **artefakty eksperymentu**
w katalogu projektu:
app/ml/models/

Zapis obejmuje dwa pliki:
<model>.joblib – zapis pipeline ML
<model>.json – metadane modelu


Przykład:
app/ml/models/test/
20260304_1441__LOGISTICRE__y=S20__w=50__k=3__p=0_001__f=efd65c48.joblib
20260304_1441__LOGISTICRE__y=S20__w=50__k=3__p=0_001__f=efd65c48.json


---

### Zawartość metadanych modelu

Plik `.json` zawiera pełną konfigurację eksperymentu:

- nazwa modelu ML
- target ML
- parametry rankingu
- zestaw filtrów
- metryki VALIDATION
- komentarz użytkownika
- ścieżki do artefaktów

Przykładowe pola:
model_name
target
window_sessions
max_signals
top_score_pct
filters
validation_metrics
model_file
meta_file
user_comment


---

### Ścieżki względne

W metadanych zapisywane są **ścieżki względne względem katalogu projektu**.

Przykład:
app/ml/models/test/model.joblib

Zamiast:
D:...\model.joblib


Pozwala to:

- uruchamiać aplikację w różnych środowiskach
- publikować repozytorium
- wdrażać aplikację w chmurze

bez zależności od lokalnych ścieżek systemowych.

---

### Generator nazwy modelu

Nazwa artefaktu modelu jest generowana automatycznie
na podstawie kluczowych parametrów eksperymentu.

Schemat:
timestamp__MODEL__y=TARGET__w=WINDOW__k=K__p=PCT__f=FILTERHASH

Przykład:
20260304_1441__LOGISTICRE__y=S20__w=50__k=3__p=0_001__f=efd65c48


gdzie:

| element | znaczenie |
|-------|-----------|
| timestamp | czas zapisu modelu |
| MODEL | typ modelu ML |
| y | target |
| w | window_sessions |
| k | max_signals |
| p | top_score_pct |
| f | hash konfiguracji filtrów |

Hash filtrów pozwala na:

- skrócenie nazwy pliku
- jednoznaczną identyfikację konfiguracji filtrów.

---

### Rejestr konfiguracji filtrów

Konfiguracja filtrów użyta w eksperymencie
jest zapisywana w metadanych modelu.

Każdy filtr posiada:

- nazwę techniczną
- skrót
- flagę aktywności

Przykład:
filters:
trend_ema20_ema50: true
trend_ema50_ema200: true
rsi_lt_30: false
macd_gt_0: true


Pozwala to:

- odtworzyć eksperyment,
- analizować wpływ filtrów,
- budować tabelę konfiguracji modeli w UI.

---

### Integracja z UI (ML-01)

Zapis modelu realizowany jest z poziomu UI Streamlit
w zakładce **Ranking (Top-K → Top-Pct)**.

Proces zapisu obejmuje:

1. trening modelu na TRAIN + VALIDATION,
2. zapis pipeline ML (`joblib`),
3. zapis metadanych (`json`),
4. aktualizację listy modeli w UI.

---

### Charakter zapisanych modeli

Modele zapisane w ML-01:

- nie są modelami produkcyjnymi,
- stanowią artefakty eksperymentu,
- służą do analizy i porównań.

Decyzja o wykorzystaniu modeli w runtime aplikacji
może zostać podjęta w kolejnych etapach projektu
(np. ML-02 / ML-03).



---

## 8. Odtwarzanie eksperymentów ML i ewaluacja modeli na zbiorze TEST

### Status
Accepted / Implemented

---

### Kontekst

Modele zapisane w etapie **ML-01** stanowią artefakty eksperymentów
i mogą być wykorzystane do:

- ponownej analizy wyników modelu,
- porównania konfiguracji eksperymentów,
- oceny działania modelu na **nieużywanym wcześniej zbiorze TEST**.

Zbiór TEST jest w architekturze ML **holdout datasetem**
i pozostaje niewykorzystywany w trakcie etapu ML-01
(treningu i walidacji modeli).

Dzięki temu możliwa jest **końcowa, niezależna ocena modelu**.

---

### Decyzja

W projekcie AnGG wprowadzono mechanizm umożliwiający:

1. zapis modelu ML oraz konfiguracji eksperymentu,
2. ponowne wczytanie modelu,
3. odtworzenie procesu selekcji sygnałów,
4. ocenę modelu na zbiorze **TEST**.

Proces ten jest realizowany przez dedykowaną zakładkę UI
(w kolejnych iteracjach ML).

---

### Artefakty eksperymentu

Każdy zapisany model składa się z dwóch plików:
<model>.joblib
<model>.json


- plik `.joblib` zawiera zapisany pipeline ML,
- plik `.json` zawiera metadane eksperymentu.

Artefakty przechowywane są w katalogu:
app/ml/models/

w podkatalogach:
test/
prd/
presentation/

---

### Struktura metadanych eksperymentu

Plik `.json` zawiera konfigurację pozwalającą odtworzyć eksperyment.

Najważniejsze pola:

| pole | znaczenie |
|-----|-----------|
| model_name | typ modelu ML |
| target | target ML |
| feature_cols | lista cech użytych w modelu |
| setup_cfg | konfiguracja pipeline ML |
| rank_selector_id | algorytm selekcji rankingowej |
| rank_params | parametry selekcji rankingowej |
| quality_filters | aktywne filtry jakościowe |
| min_conditions | minimalna liczba warunków filtrów |
| val_summary | metryki VALIDATION |
| model_file | ścieżka do modelu |
| meta_file | ścieżka do metadanych |

Pole `feature_cols` stanowi **kontrakt cech modelu**  
i określa zestaw kolumn użytych przy treningu.

---

### Algorytm selekcji rankingowej

Metadane zawierają pole:
rank_selector_id


które identyfikuje sposób selekcji sygnałów.

Możliwe wartości:
topk_then_toppct
toppct_then_topk


Domyślny wariant stosowany w ML-01:
topk_then_toppct

czyli:

1. selekcja Top-K w oknie czasowym,
2. filtr Top-Pct najlepszych obserwacji.

---

### Proces odtwarzania eksperymentu

Zakładka testująca modele powinna realizować następujący proces.

#### 1. Wybór modelu

Użytkownik wybiera zapisany eksperyment z listy modeli.

#### 2. Wczytanie metadanych

System wczytuje plik `.json`
i odczytuje konfigurację eksperymentu.

#### 3. Wczytanie modelu

Model ładowany jest z użyciem:
joblib.load(model_file)

Pipeline zawiera:

- preprocessing danych
- wytrenowany model ML.

#### 4. Budowa datasetu TEST

Dataset TEST budowany jest w warstwie:
app/ml/ml_datasets.py

z wykorzystaniem kanonicznego podziału czasowego.

#### 5. Przygotowanie danych wejściowych

Na podstawie:
feature_cols

tworzony jest zbiór:
X_TEST = df_market_test[feature_cols]

---

#### 6. Predykcja modelu

Model generuje score:
prob = model.predict_proba(X_TEST)[:,1]

Score interpretowany jest rankingowo.

---

#### 7. Budowa rankingu sygnałów

Ranking sygnałów budowany jest zgodnie z:
rank_selector_id
rank_params

czyli według konfiguracji użytej w eksperymencie ML-01.

---

#### 8. Zastosowanie filtrów jakościowych

Na ranking sygnałów stosowane są filtry:
quality_filters

oraz warunek:
min_conditions

Filtry te mogą wykorzystywać wskaźniki rynku
(np. RSI, MACD, EMA).

---

#### 9. Generacja wyników TEST

Po zastosowaniu filtrów generowane są metryki TEST:

- liczba sygnałów,
- liczba trafień,
- precision,
- statystyki score (`prob`).

Dodatkowo analizowane są wyniki ex-post:
z20
z60
z120

---

### 8.1. Zakładka UI „ML (TEST)” jako mechanizm odtwarzania eksperymentu

W projekcie AnGG wprowadzono dedykowaną zakładkę UI:

`ML (TEST)`

której celem jest:

- wybór zapisanego modelu ML z rejestru artefaktów,
- ponowne wczytanie pipeline ML (`.joblib`),
- odczyt metadanych eksperymentu (`.json`),
- odtworzenie procesu selekcji sygnałów,
- wykonanie ewaluacji wyłącznie na zbiorze `TEST`.

Zakładka ta nie służy do treningu modeli.
Jest narzędziem do:

- analizy artefaktów eksperymentów,
- porównywania konfiguracji,
- końcowej oceny jakości działania modelu na holdout dataset.

---

### 8.2. Zasada metodologiczna: TEST jako strict holdout

Na zakładce `ML (TEST)` obowiązuje zasada:

> wszystkie obliczenia wykonywane są wyłącznie na zbiorze `TEST`.

Oznacza to, że:

- `TRAIN` nie jest używany,
- `VALIDATION` nie jest używany do obliczeń,
- jedynym dopuszczalnym wyjątkiem jest prezentacja metryk `VALIDATE`
  zapisanych wcześniej w metadanych modelu (`json`) jako materiał porównawczy.

Zakładka `ML (TEST)` nie może być używana do strojenia modelu ani do redefinicji
ról datasetów.

---

### 8.3. Kontrakt odtwarzania eksperymentu

Odtwarzanie eksperymentu na zakładce `ML (TEST)` przebiega według kontraktu:

1. użytkownik wybiera zapisany model z katalogu artefaktów,
2. aplikacja wczytuje:
   - pipeline ML z pliku `.joblib`,
   - metadane eksperymentu z pliku `.json`,
3. budowany jest `X_TEST` na podstawie `feature_cols` zapisanych w metadanych,
4. model wylicza `prob` dla obserwacji w zbiorze `TEST`,
5. stosowana jest kanoniczna selekcja rankingowa zapisana w metadanych:
   - `rank_selector_id`
   - `rank_params`
6. stosowane są filtry jakościowe zapisane w metadanych:
   - `quality_filters`
   - `min_conditions`
7. wynik prezentowany jest w UI wraz z diagnostyką ex post.

Zakładka nie odtwarza eksperymentu „przybliżenie”.
Jej celem jest możliwie wierne odtworzenie konfiguracji zapisanej z modelem.

---

### 8.4. Obowiązkowe metadane artefaktu eksperymentu

Aby zapisany model był w pełni odtwarzalny na zakładce `ML (TEST)`,
metadane eksperymentu muszą zawierać co najmniej:

- `model_name`
- `target`
- `feature_cols`
- `rank_selector_id`
- `rank_params`
- `quality_filters`
- `min_conditions`
- `val_summary`
- ścieżkę do pliku modelu (`model_file`)

Szczególnie ważne jest pole:

`min_conditions`

które określa minimalną liczbę spełnionych filtrów jakościowych.

Brak `min_conditions` w metadanych powoduje,
że artefakt nie odtwarza pełnej logiki selekcji `PO`,
a aplikacja może jedynie zastosować interpretację zastępczą
(np. klasyczne AND = liczba aktywnych filtrów).

Wniosek architektoniczny:

> nowe artefakty eksperymentów ML muszą jawnie zapisywać `min_conditions`
> w metadanych `.json`.

---

### 8.5. Rozdzielenie trybu strict TEST i trybu eksperymentalnego

Dla zakładki `ML (TEST)` przyjęto rozdzielenie dwóch trybów pracy:

#### Tryb strict TEST
Domyślny tryb ewaluacyjny:

- parametry selekcji rankingowej są zamrożone,
- filtry jakościowe są wyświetlane w trybie tylko-do-odczytu,
- zakładka służy wyłącznie do przeglądu i oceny zapisanego modelu.

#### Tryb eksperymentalny
Tryb diagnostyczny:

- może odblokowywać edycję filtrów jakościowych,
- nie odblokowuje zmiany parametrów selekcji rankingowej
  (`window_sessions`, `max_signals`, `top_score_pct`),
- jego celem jest analiza wrażliwości i diagnostyka,
  a nie metodologia holdout TEST.

Wyniki uzyskane w trybie eksperymentalnym
nie są traktowane jako „czysta” ocena modelu na TEST.

---

### 8.6. Powiązanie z trybem runtime aplikacji (DEMO / CSV / DEV)

Widoczność funkcji eksperymentalnych zakładki `ML (TEST)`
jest kontrolowana przez runtime aplikacji.

Źródłem prawdy dla runtime nie jest wyłącznie `APP_MODE`,
lecz flaga:

`APP_TEST_ON_CSV_FILES`

Interpretacja:

- `APP_TEST_ON_CSV_FILES = True`
  - aplikacja działa na CSV,
  - obejmuje zarówno jawny tryb `DEMO`,
  - jak i fallback `DEV -> CSV` w przypadku braku połączenia z DB,
  - zakładka `ML (TEST)` działa wtedy jako strict read-only,
  - checkbox „Tryb eksperymentalny” nie jest pokazywany.

- `APP_TEST_ON_CSV_FILES = False`
  - aplikacja działa w runtime DB,
  - dopuszczalne jest pokazanie checkboxa „Tryb eksperymentalny”,
  - ale domyślnie pozostaje on wyłączony.

Decyzja ta zapewnia spójność pomiędzy:
- architekturą trybów pracy aplikacji,
- źródłem danych runtime,
- metodologiczną rolą zakładki `ML (TEST)`.



### Prezentacja wyników w UI

Zakładka TEST powinna prezentować:

#### informacje o modelu

- nazwa modelu
- target
- parametry rankingu
- konfiguracja filtrów
- komentarz użytkownika

---

#### porównanie VALIDATION vs TEST

| metric | VALIDATION | TEST |
|------|------|------|

---

#### ranking sygnałów

Tabela sygnałów powinna zawierać:
date
ticker
prob
z20
z60
z120

---

### Konsekwencje architektoniczne

#### Pozytywne

- pełna reprodukowalność eksperymentów ML,
- możliwość porównywania modeli,
- kontrola konfiguracji eksperymentów.

#### Ograniczenia

- wyniki TEST mogą zależeć od zmian w pipeline budowy datasetów,
- zapis modeli zwiększa liczbę artefaktów projektu.









