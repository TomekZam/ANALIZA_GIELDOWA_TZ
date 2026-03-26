# ADR-008 – Interpretacja wskaźników, etykiet future i sygnałów probabilistycznych (prob)

## Status
Proposed / Living Document

## Data
2026-01-25

## Charakter dokumentu
**Biznesowo-analityczny (nie techniczny)**  

Dokument opisuje **znaczenie, interpretację i sposób rozumienia wskaźników oraz sygnałów**
w projekcie *Analiza GG*, ze szczególnym naciskiem na:

- wskaźniki typu **future** (etykiety historyczne),
- przejście od etykiet do sygnałów **probabilistycznych (`prob`)**,
- poprawną interpretację czasową i decyzyjną sygnałów.

Dokument ma charakter **otwarty (living document)** i będzie rozwijany iteracyjnie
w kolejnych rozmowach.

Dokument **nie opisuje implementacji technicznej** ani strategii inwestycyjnych.

---

## 1. Cel biznesowy

Celem niniejszego ADR jest ujednolicenie **rozumienia semantycznego**:

- czym są poszczególne wskaźniki i sygnały w systemie,
- do czego **służą**, a do czego **nie powinny być używane**,
- jak interpretować je w kontekście:
  - analizy historycznej,
  - feature engineering,
  - sygnałów bieżących opartych o prawdopodobieństwo.

Dokument pełni rolę **wspólnego punktu odniesienia mentalnego**
dla dalszego rozwoju analizy, ML oraz interpretacji wyników.

---

## 2. Podstawowy podział pojęciowy (kluczowy)

W projekcie *Analiza GG* rozróżniamy trzy fundamentalnie różne byty:

1. **Wskaźniki opisowe (features)**  
   Opisują *aktualny stan rynku* w dniu `t`.

2. **Etykiety future (labels)**  
   Opisują *co wydarzyło się po dniu `t`* w określonym horyzoncie.

3. **Sygnały probabilistyczne (`prob`)**  
   Opisują *jak bardzo dzisiejszy stan rynku przypomina sytuacje,
   które historycznie prowadziły do określonego zdarzenia*.

Mylenie tych pojęć prowadzi do błędów interpretacyjnych
(np. look-ahead bias).

---

## 3. Wskaźniki typu future – jak je rozumieć

### 3.1. Czym są etykiety future

Wskaźniki takie jak:

- `fut_signal_20`
- `fut_signal_20_hyb`

są **etykietami historycznymi (future labels)**:

- odnoszą się do dnia `t`,
- są liczone na podstawie zdarzeń z okresu `t+1 … t+20`,
- stają się znane **dopiero po upływie pełnego horyzontu czasowego**.

Ich podstawowa rola:

> **Odpowiedzieć na pytanie:  
> „Czy decyzja podjęta w dniu `t` była jakościowo dobra
> w perspektywie kolejnych 20 dni?”**

Nie są to sygnały operacyjne ani sygnały bieżące.

---

### 3.2. Konsekwencje czasowe

- Ostatnie 19 dni danych zawsze mają wartość `NULL` – jest to **zachowanie poprawne**.
- Pojawienie się etykiety w bazie danych **nie oznacza, że sygnał jest aktualny dziś**.
- Etykieta była „ważna” w dniu `t`, którego dotyczy,
  a nie w dniu, w którym została obliczona.

---

## 4. Różnica semantyczna między `fut_signal_20` a `fut_signal_20_hyb`

### 4.1. `fut_signal_20` – interpretacja inwestycyjna (kontekst rynku)

`fut_signal_20` jest **etykietą kontekstową**, a nie sygnałem akcyjnym.
Opisuje on **stan rynku**, a nie moment decyzji.

### Znaczenie semantyczne

Interpretacja biznesowa:

> „Rynek w kolejnych 20 dniach **nie zaprzeczył kierunkowi**,  
> który był widoczny w dniu `t`.”

Oznacza to, że:
- impuls lub trend **utrzymał się**,
- nie doszło do istotnego zanegowania kierunku,
- rynek zachowywał się spójnie z wcześniejszym ruchem.

`fut_signal_20` **nie mówi**, że w tym miejscu należało kupić lub sprzedać.
Mówi jedynie, że **granie w tym kierunku nie było błędem kontekstowym**.

---

#### Jak inwestycyjnie NIE interpretować `fut_signal_20`

`fut_signal_20` **nie powinien być interpretowany jako**:
- sygnał wejścia,
- sygnał timingowy,
- powód do natychmiastowego działania.

Reagowanie bezpośrednio na każdy `fut_signal_20` prowadziłoby do:
- overtradingu,
- reagowania „po fakcie”,
- braku przewagi decyzyjnej.

---

#### Jak inwestycyjnie interpretować `fut_signal_20`

Poprawna interpretacja inwestycyjna:

> „Rynek znajduje się w stanie,  
> w którym **historycznie opłacało się myśleć w tym kierunku**.”

Typowe zastosowania:
- filtr kierunku (long vs short),
- kontekst trendowy,
- informacja: „czy w ogóle warto szukać impulsów po tej stronie rynku”.

W praktyce:
- `fut_signal_20 = +1` → **nie graj przeciwko rynkowi**,
- `fut_signal_20 = -1` → **nie łap dołków wbrew trendowi**.

`fut_signal_20` odpowiada na pytanie:
> „Czy rynek *pozwalał* na sensowne granie w tym kierunku?”

---

### 4.2. `fut_signal_20_hyb` – interpretacja inwestycyjna (moment decyzyjny)

`fut_signal_20_hyb` jest **etykietą jakościowego impulsu**.
W przeciwieństwie do `fut_signal_20` nie opisuje stanu rynku,
lecz **moment, w którym wydarzyło się coś istotnego**.

#### Znaczenie semantyczne

Interpretacja biznesowa:

> „Po okresie osłabienia, konsolidacji lub pauzy  
> pojawił się **nowy, statystycznie istotny impuls**.”

Cechy charakterystyczne:
- sygnał jest **rzadki**,
- wymaga spełnienia dodatkowych warunków (istotność, reset referencji),
- filtruje przypadkowe ruchy i szum.

`fut_signal_20_hyb` wskazuje **moment zmiany dynamiki**, a nie jej trwanie.

---

#### Dlaczego `fut_signal_20_hyb` jest „gold label”

W praktyce historycznej `fut_signal_20_hyb` oznacza:

- miejsca, w których rynek **znowu „ruszył”**,
- impulsy, które miały sensowną kontynuację,
- sytuacje, które inwestorzy często opisują intuicyjnie jako:
  „rynek się obudził”, „znowu dostał energii”.

To sprawia, że:
- `fut_signal_20_hyb` jest idealną etykietą:
  - dla ML,
  - dla analizy setupów,
  - dla badania jakości momentów wejścia.

---

#### Jak inwestycyjnie interpretować `fut_signal_20_hyb`

Poprawna interpretacja inwestycyjna:

> „W tym miejscu **pojawiał się moment decyzyjny**,  
> który historycznie często prowadził do sensownego ruchu.”

Typowe interpretacje:
- potencjalne wejście po korekcie,
- re-entry w istniejącym trendzie,
- dołożenie do pozycji (pyramiding),
- moment zwiększonej uwagi inwestycyjnej.

Ważne:
- `fut_signal_20_hyb` **nie jest gwarancją sukcesu**,
- jest wskazaniem **zwiększonego prawdopodobieństwa jakościowego ruchu**.

---

### 4.3. Wspólne użycie `fut_signal_20` i `fut_signal_20_hyb`

Największą wartość informacyjną sygnały te mają **razem**, a nie osobno.

#### Relacja kontekst → akcja

| Stan | Interpretacja |
|----|-------------|
| `fut_signal_20 = +1`, `fut_signal_20_hyb = NaN` | Trend trwa, brak nowego impulsu |
| `fut_signal_20 = +1`, `fut_signal_20_hyb = +1` | **Nowy impuls w zgodnym trendzie** |
| `fut_signal_20 = NaN`, `fut_signal_20_hyb = +1` | Wczesny impuls, brak pełnego kontekstu |
| `fut_signal_20 = -1`, `fut_signal_20_hyb = +1` | Impuls przeciwny do kontekstu (wysokie ryzyko) |

#### Kluczowa obserwacja

- `fut_signal_20` odpowiada na pytanie:
  > „Czy w ogóle warto myśleć w tym kierunku?”
- `fut_signal_20_hyb` odpowiada na pytanie:
  > „Czy **to jest moment**, w którym historycznie coś się działo?”

Ta relacja stanowi **fundament przejścia do sygnałów `prob`**,
gdzie:
- `fut_signal_20` jest częścią **kontekstu (feature)**,
- `fut_signal_20_hyb` jest **zdarzeniem, którego prawdopodobieństwo próbujemy oszacować**.





---

## 5. Dlaczego etykiety future nie są sygnałami bieżącymi

Etykiety future:

- zawierają informację z przyszłości,
- są znane dopiero po fakcie,
- **nie mogą być używane bezpośrednio do reagowania dziś**.

Użycie ich jako sygnałów bieżących prowadziłoby do:

- look-ahead bias,
- nierealistycznych wyników,
- błędnych wniosków decyzyjnych.

---

## 6. Przejście od etykiet future do sygnałów `prob`

### 6.1. Idea biznesowa

Sygnał `prob` odpowiada na pytanie:

> **„Jak bardzo dzisiejszy stan rynku przypomina
> historyczne sytuacje, po których często pojawiał się
> jakościowy impuls?”**

Nie przewiduje on ceny.
Rozpoznaje **konfigurację rynku**.

---

### 6.2. Jaką informację model ma w dniu dzisiejszym

W dniu `T` dostępne są wyłącznie informacje znane w tym dniu:

- ceny historyczne do dnia `T`,
- wskaźniki techniczne i kontekstowe (trend, momentum, zmienność, wolumen),
- brak jakiejkolwiek wiedzy o przyszłości.

Jest to dokładnie ten sam zestaw informacji,
który posiadałby inwestor w dniu `T`.

---

### 6.3. Mechanizm powstawania `prob`

Proces logiczny:

1. Model uczy się na danych historycznych:
   - **X(t)** – cechy rynku w dniu `t`,
   - **Y(t)** – etykieta `fut_signal_20_hyb(t)`.

2. Model identyfikuje konfiguracje cech,
   które **często prowadziły do `hyb = 1`**.

3. Dla dnia dzisiejszego `T` model oblicza:


### 6.4. `prob` – interpretacja inwestycyjna (co to znaczy, a czego nie)

Sygnał `prob` jest **sygnałem bieżącym**, ale **nie binarnym**.
Nie odpowiada na pytanie *„czy rynek wzrośnie”*,
lecz na pytanie:

> **„Jak bardzo dzisiejszy stan rynku przypomina
> historyczne sytuacje, po których często pojawiał się
> jakościowy impuls (`fut_signal_20_hyb = 1`)?”**

`prob` jest miarą **podobieństwa kontekstowego**, a nie pewności wyniku.

---

#### Czym `prob` NIE jest

`prob` **nie jest**:
- gwarancją ruchu,
- prognozą ceny,
- sygnałem typu „kup / sprzedaj”,
- informacją, że impuls już się wydarzył.

Traktowanie `prob` jako obietnicy prowadzi do
błędnych decyzji i nadmiernej pewności.

---

#### Czym `prob` JEST

`prob` jest:
- oceną **statystycznej zgodności** obecnej sytuacji rynkowej
  z historycznymi sytuacjami zakończonymi impulsem,
- warstwą pośrednią między analizą a decyzją,
- syntetycznym sygnałem łączącym wiele cech rynku naraz.

Interpretacja biznesowa:

> „Rynek znajduje się w fazie,
> która **często (ale nie zawsze)** prowadziła do
> jakościowego ruchu w określonym kierunku.”

---

### 6.5. `prob` jako sygnał bieżący (warstwa decyzyjna)

W przeciwieństwie do etykiet future,
`prob` jest **dostępny w dniu dzisiejszym (`T`)**
i może być używany jako sygnał operacyjny **bez look-ahead bias**.

`prob` pełni rolę **regulatora intensywności reakcji**, a nie jej kierunku.

Przykładowa interpretacja jakościowa:

- niskie `prob` → brak przewagi, obserwacja,
- średnie `prob` → zwiększona czujność,
- wysokie `prob` → warunki sprzyjające decyzji.

W praktyce inwestycyjnej `prob` odpowiada na pytanie:

> „Czy **dzisiaj** warto poświęcić temu rynkowi uwagę
> i rozważyć działanie, jeśli pojawi się dodatkowe potwierdzenie?”

---

### 6.6. Relacja `fut_signal_20`, `fut_signal_20_hyb` → `prob`

Sygnał `prob` jest **logicznym kolejnym krokiem**
po `fut_signal_20` i `fut_signal_20_hyb`.

Relacja semantyczna:

- `fut_signal_20`  
  → **czy rynek był w sprzyjającym kontekście**
- `fut_signal_20_hyb`  
  → **gdzie historycznie pojawiał się moment jakościowy**
- `prob`  
  → **jak bardzo dzisiejsza sytuacja przypomina te momenty**

Można to ująć skrótowo:

> `fut_signal_20` = kontekst  
> `fut_signal_20_hyb` = zdarzenie historyczne  
> `prob` = bieżące podobieństwo do tego zdarzenia

W tym sensie:
- `fut_signal_20` często pełni rolę **feature’u kontekstowego**,
- `fut_signal_20_hyb` jest **etykietą uczącą**,
- `prob` jest **produktem końcowym dla analizy bieżącej**.

---

### 6.7. Najczęstsze błędy interpretacyjne `prob`

Najczęstsze błędy, których należy unikać:

1. **Traktowanie `prob` jako pewności**
   - wysokie `prob` ≠ „rynek na pewno ruszy”.

2. **Ignorowanie kontekstu**
   - `prob` bez uwzględnienia trendu, reżimu rynku
     prowadzi do błędnych decyzji.

3. **Reagowanie binarne**
   - `prob` nie powinno być interpretowane jako sygnał 0/1,
     lecz jako skala.

4. **Oderwanie od czasu**
   - `prob` nie mówi *kiedy* nastąpi impuls,
     lecz *czy jesteśmy w fazie*, w której często następował.

Poprawna interpretacja `prob` wymaga zawsze
połączenia go z kontekstem rynkowym
oraz innymi elementami analizy.



-------------



## 7. Interpretacja wskaźników bazowych z tabeli `indicators_daily`

Niniejszy rozdział opisuje **znaczenie biznesowo-analityczne wskaźników, które są już zaimplementowane i wyliczane w aplikacji ANGG**. Dane znajdują się w tabeli `indicators_daily`.

Wskaźniki te:
- **nie są sygnałami decyzyjnymi same w sobie**,
- pełnią rolę **features**,
- stanowią podstawę do:
  - interpretacji rynku,
  - budowy etykiet future,
  - obliczania sygnałów probabilistycznych (`prob`).

---

## 7.1. Wskaźniki trendu i kontekstu

### SMA(20) – `sma_20`

**Znaczenie:**
- krótkoterminowy trend ceny,
- wygładzenie szumu dziennego.

**Interpretacja:**
> „Gdzie znajduje się cena względem krótkiego trendu?”

Typowe wnioski:
- cena powyżej SMA(20) → krótkoterminowa przewaga popytu,
- cena poniżej SMA(20) → presja podażowa / korekta.

Rola w systemie:
- kontekst krótkoterminowy,
- pomocniczy feature dla momentum i impulsów.

---

### SMA(200) – `sma_200`

**Znaczenie:**
- długoterminowy trend rynku,
- filtr reżimu rynku.

**Interpretacja:**
> „Czy rynek jest strukturalnie w trendzie wzrostowym czy spadkowym?”

Typowe wnioski:
- cena powyżej SMA(200) → rynek w reżimie wzrostowym,
- cena poniżej SMA(200) → rynek w reżimie spadkowym.

Rola w systemie:
- **market regime filter**,
- silny feature kontekstowy dla `fut_signal_20` i `prob`.

---

### EMA(12), EMA(26) – `ema_12`, `ema_26`

**Znaczenie:**
- dynamiczne średnie kroczące,
- szybciej reagują na zmiany niż SMA.

**Interpretacja:**
> „Jak zmienia się dynamika trendu w krótszym i średnim horyzoncie?”

Typowe obserwacje:
- EMA(12) powyżej EMA(26) → dodatnia dynamika,
- rosnący dystans EMA(12)–EMA(26) → przyspieszenie trendu.

Rola w systemie:
- feature dynamiki,
- budulec dla wskaźników momentum i jakości impulsu.

---

## 7.2. Wskaźniki momentum i siły rynku

### Momentum 12M – `momentum_12m`

**Znaczenie:**
- długoterminowa siła względna rynku,
- klasyczny wskaźnik momentum (12 miesięcy).

**Interpretacja:**
> „Czy rynek w ostatnim roku realnie zyskiwał czy tracił?”

Typowe wnioski:
- dodatnie momentum → rynek w fazie wzrostowej,
- ujemne momentum → rynek strukturalnie słaby.

Rola w systemie:
- selekcja rynków / spółek,
- feature wysokiego poziomu dla ML,
- silny predyktor kontekstu przyszłych impulsów.

---

### RSI(14) – `rsi_14`

**Znaczenie:**
- relatywna siła ruchu ceny,
- wskaźnik oscylacyjny (0–100).

**Interpretacja:**
> „Czy rynek jest krótkoterminowo rozgrzany czy wyprzedany?”

Typowe zakresy:
- RSI > 70 → wykupienie,
- RSI < 30 → wyprzedanie.

Ważne:
- RSI **nie jest sygnałem transakcyjnym sam w sobie**,
- w trendach może długo pozostawać w skrajnych strefach.

Rola w systemie:
- feature napięcia rynku,
- informacja pomocnicza dla momentu impulsu (`fut_signal_20_hyb`).

---

## 7.3. Wskaźniki zmienności i ryzyka

### Volatility(20D) – `volatility_20d`

**Znaczenie:**
- krótkoterminowa zmienność logarytmicznych zwrotów,
- miara ryzyka i „energii” rynku.

**Interpretacja:**
> „Jak bardzo rynek się waha w krótkim okresie?”

Typowe obserwacje:
- niska zmienność → konsolidacja / zbieranie energii,
- wysoka zmienność → emocjonalna faza rynku.

Rola w systemie:
- kluczowy feature dla:
  - jakości impulsów,
  - Sharpe Ratio,
  - filtracji szumu.

---

## 7.4. Wskaźniki jakości zwrotu

### Sharpe Ratio (20D) – `sharpe_20d`

**Znaczenie:**
- relacja średniego zwrotu do ryzyka (zmienności),
- uproszczona wersja bez stopy wolnej od ryzyka.

**Interpretacja:**
> „Czy rynek wynagradzał ryzyko w ostatnim okresie?”

Typowe wnioski:
- wysoki Sharpe → ruch uporządkowany, „czysty”,
- niski / ujemny Sharpe → chaos, brak jakości trendu.

Rola w systemie:
- feature jakości trendu,
- pomocniczy filtr dla impulsów,
- ważny sygnał kontekstowy dla `prob`.

---

## 7.5. Wskaźniki fundamentalne (syntetyczne)

### Earnings Yield – `earnings_yield`

**Znaczenie:**
- odwrotność wskaźnika P/E,
- syntetyczna miara „rentowności” spółki.

**Interpretacja:**
> „Jaką stopę zysku generują zyski spółki
> względem jej ceny rynkowej?”

Typowe wnioski:
- wysoki earnings yield → spółka relatywnie tania,
- niski earnings yield → spółka droga / wzrostowa.

Ważne:
- wskaźnik **nie uwzględnia dynamiki zysków**,
- powinien być interpretowany w kontekście trendu i momentum.

Rola w systemie:
- feature fundamentalny,
- element kontekstu długoterminowego,
- uzupełnienie analizy technicznej.

---


## 7.6. Wskaźniki dynamiki i struktury trendu

### MACD Line – `macd_line`

**Znaczenie:**
- różnica pomiędzy EMA(12) i EMA(26),
- miara **kierunku i siły zmiany trendu**.

**Interpretacja:**
> „Czy krótkoterminowa dynamika ceny
> jest silniejsza od średnioterminowej?”

Typowe wnioski:
- dodatni MACD → przewaga momentum wzrostowego,
- ujemny MACD → przewaga momentum spadkowego.

Rola w systemie:
- feature dynamiki trendu,
- podstawa do dalszych komponentów MACD,
- element rozpoznawania fazy impulsu.

---

### MACD Signal – `macd_signal`

**Znaczenie:**
- wygładzona (EMA 9) wersja `macd_line`,
- miara **stabilności i potwierdzenia dynamiki**.

**Interpretacja:**
> „Czy obserwowana zmiana dynamiki
> ma charakter trwały czy chwilowy?”

Typowe wnioski:
- zbliżanie się MACD do sygnału → osłabienie impulsu,
- oddalanie się → wzmacnianie impulsu.

Rola w systemie:
- feature potwierdzający,
- filtr szumu krótkoterminowego.

---

### MACD Histogram – `macd_hist`

**Znaczenie:**
- różnica pomiędzy `macd_line` a `macd_signal`,
- tempo zmian dynamiki (akceleracja).

**Interpretacja:**
> „Czy dynamika rynku przyspiesza czy hamuje?”

Typowe wnioski:
- rosnący histogram → przyspieszenie impulsu,
- malejący histogram → wygasanie impulsu.

Rola w systemie:
- feature wczesnego ostrzegania,
- bardzo użyteczny w analizie momentu impulsu (`fut_signal_20_hyb`).

---

## 7.7. Wskaźniki wolumenu i przepływu kapitału

### Average Volume (20D) – `average_volume_20d`

**Znaczenie:**
- średni wolumen z 20 sesji,
- punkt odniesienia dla bieżącej aktywności rynku.

**Interpretacja:**
> „Czy obecny obrót jest niski, normalny czy podwyższony
> względem ostatnich tygodni?”

Typowe wnioski:
- wolumen powyżej średniej → zwiększone zainteresowanie,
- wolumen poniżej średniej → brak zaangażowania.

Rola w systemie:
- normalizacja wolumenu,
- feature kontekstowy dla impulsów.

---

### OBV (On-Balance Volume) – `obv`

**Znaczenie:**
- skumulowany przepływ wolumenu zależny od kierunku ceny,
- proxy **napływu i odpływu kapitału**.

**Interpretacja:**
> „Czy kapitał napływa do rynku,
> nawet jeśli cena jeszcze tego w pełni nie pokazuje?”

Typowe obserwacje:
- rosnący OBV przy płaskiej cenie → akumulacja,
- spadający OBV przy stabilnej cenie → dystrybucja.

Rola w systemie:
- feature potwierdzający ruch ceny,
- wskaźnik rozbieżności cena ↔ wolumen.

---

## 7.8. Wskaźniki ceny ważonej wolumenem

### VWAP (20D) – `vwap_20d`

**Znaczenie:**
- średnia cena ważona wolumenem z 20 dni,
- miara „uczciwej ceny” transakcyjnej.

**Interpretacja:**
> „Czy obecna cena jest wysoka czy niska
> względem średniej ceny, po której faktycznie handlowano?”

Typowe wnioski:
- cena powyżej VWAP → przewaga kupujących,
- cena poniżej VWAP → przewaga sprzedających.

Rola w systemie:
- feature referencyjny ceny,
- kontekst dla short-term mean reversion i momentum.

---

## 7.9. Wskaźniki zmienności rzeczywistej

### ATR (14) – `atr_14`

**Znaczenie:**
- średni rzeczywisty zakres ruchu ceny,
- miara **faktycznej zmienności**, niezależna od kierunku.

**Interpretacja:**
> „Jak szeroko rynek faktycznie się porusza
> z dnia na dzień?”

Typowe wnioski:
- rosnący ATR → faza emocjonalna / impuls,
- niski ATR → konsolidacja / zbieranie energii.

Rola w systemie:
- feature ryzyka krótkoterminowego,
- kontekst dla jakości impulsów.

---

## 7.10. Wskaźniki ryzyka i jakości trendu

### Max Drawdown (252D) – `max_drawdown_252d`

**Znaczenie:**
- największe obsunięcie kapitału w ostatnim roku,
- miara **ryzyka historycznego**.

**Interpretacja:**
> „Jak głębokie straty musiałby zaakceptować inwestor,
> trzymając ten instrument w ostatnich 12 miesiącach?”

Typowe wnioski:
- duży drawdown → niestabilny, ryzykowny rynek,
- mały drawdown → rynek uporządkowany.

Rola w systemie:
- feature długoterminowego ryzyka,
- filtr jakości instrumentów.

---

### Trend Quality Score (60D) – `tqs_60d`

**Znaczenie:**
- miara jakości trendu w 60-dniowym oknie,
- relacja nachylenia trendu do szumu (reszt).

**Interpretacja:**
> „Czy rynek porusza się w sposób uporządkowany,
> czy raczej chaotyczny?”

Typowe wnioski:
- wysoki TQS → trend czysty, czytelny,
- niski TQS → rynek szarpany, losowy.

Rola w systemie:
- feature jakości trendu,
- bardzo silny sygnał kontekstowy dla `prob`
  i interpretacji `fut_signal_20_hyb`.

---

## 7.11. Uwagi końcowe

Wskaźniki opisane w tym rozdziale:
- **nie są sygnałami transakcyjnymi**,
- opisują dynamikę, jakość i ryzyko rynku,
- wzmacniają interpretację:
  - momentu impulsu,
  - jakości trendu,
  - wiarygodności sygnałów probabilistycznych.
- **nie są sygnałami decyzyjnymi**,
- stanowią **język opisu rynku**,
- są podstawą do:
  - etykiet future,
  - sygnałów `prob`,
  - dalszych analiz i ML.




## 8. Które wskaźniki są kluczowe dla `prob` (feature v1)

Nie wszystkie wskaźniki mają równą wartość informacyjną
w kontekście budowy sygnału probabilistycznego (`prob`).

Celem feature v1 **nie jest maksymalna liczba wskaźników**,
lecz **uchwycenie kluczowych aspektów stanu rynku**:

- kontekst trendu,
- energia / napięcie rynku,
- jakość i stabilność ruchu,
- ryzyko krótkoterminowe.

---

### 8.1. Kluczowe grupy informacyjne

Dla `prob` potrzebujemy **co najmniej jednego feature’u z każdej grupy**.

#### A. Kontekst trendu (czy rynek „pozwala” na impuls)

Reprezentatywne wskaźniki:
- `sma_200`
- `ema_50`
- `fut_signal_20` (jako feature kontekstowy, nie sygnał)

Znaczenie:
> „Czy rynek znajduje się w reżimie,
> w którym historycznie pojawiały się impulsy?”

---

#### B. Dynamika i momentum (czy rynek się rozpędza)

Reprezentatywne wskaźniki:
- `momentum_12m`
- `macd_line`
- `macd_hist`

Znaczenie:
> „Czy siła rynku rośnie, maleje, czy jest neutralna?”

---

#### C. Energia / napięcie rynku (czy coś się „zbiera”)

Reprezentatywne wskaźniki:
- `volatility_20d`
- `atr_14`
- `rsi_14`

Znaczenie:
> „Czy rynek jest w fazie kompresji,
> czy już w fazie rozładowania?”

---

#### D. Jakość ruchu (czy ruch ma sens)

Reprezentatywne wskaźniki:
- `sharpe_20d`
- `tqs_60d`
- `max_drawdown_252d`

Znaczenie:
> „Czy rynek porusza się w sposób uporządkowany,
> czy chaotyczny i ryzykowny?”

---

#### E. Wolumen i potwierdzenie (czy stoi za tym kapitał)

Reprezentatywne wskaźniki:
- `average_volume_20d`
- `obv`
- `vwap_20d`

Znaczenie:
> „Czy ruch ceny jest wspierany przez realny obrót?”

---

### 8.2. Minimalny zestaw feature v1 (propozycja)

Minimalny, sensowny zestaw startowy:

- `sma_200`
- `momentum_12m`
- `macd_hist`
- `volatility_20d`
- `sharpe_20d`
- `tqs_60d`
- `obv`

Ten zestaw:
- pokrywa wszystkie kluczowe grupy informacyjne,
- jest relatywnie nisko skorelowany,
- dobrze wspiera estymację `prob`.

---

### 8.3. Rola feature v1 w interpretacji `prob`

`prob` nie jest predykcją ceny.
Jest **syntetyczną oceną stanu rynku**.

Feature v1 odpowiada na pytanie:
> „Czy obecna konfiguracja rynku
> historycznie często prowadziła do impulsu jakościowego?”

Im lepiej dobrane features,
tym bardziej `prob` odzwierciedla **faktyczne fazy rynku**,
a nie przypadkowy szum.



## 9. Czego NIE łączyć razem (anty-korelacje)

Jednym z największych błędów w budowie feature setów
jest **nadmiar informacji pozornie różnych,
ale w rzeczywistości opisujących to samo**.

Prowadzi to do:
- przeuczenia modeli,
- fałszywego poczucia pewności,
- niestabilnych predykcji `prob`.

---

### 9.1. Redundancja średnich kroczących

Nie należy jednocześnie używać:
- `sma_20` + `ema_20` + `ema_12`

Powód:
- wszystkie opisują ten sam krótkoterminowy trend,
- różnią się jedynie szybkością reakcji.

Rekomendacja:
> Wybierz **jedną reprezentację** dla danego horyzontu.

---

### 9.2. Nadmiar wskaźników momentum

Nie należy łączyć:
- `momentum_12m`
- `macd_line`
- `macd_hist`
- `rsi_14`

…bez selekcji.

Powód:
- wszystkie mierzą **ten sam aspekt siły rynku**,
- model dostaje wielokrotnie tę samą informację.

Rekomendacja:
> Jeden wskaźnik momentum + jeden akceleracji w zupełności wystarczą.

---

### 9.3. Podwójne miary zmienności

Nie należy traktować jako niezależnych:
- `volatility_20d`
- `atr_14`

Powód:
- oba mierzą zmienność,
- różnią się skalą, nie semantyką.

Rekomendacja:
> Jeden z nich jako feature,
> drugi ewentualnie jako wsparcie interpretacyjne.

---

### 9.4. Mylenie jakości z kierunkiem

Nie należy traktować:
- `sharpe_20d`
- `tqs_60d`

…jako wskaźników kierunku.

Powód:
- mierzą **porządek i jakość**, nie stronę rynku.

Rekomendacja:
> Łączyć je z kontekstem trendu, a nie używać samodzielnie.

---

### 9.5. Anty-pattern: „wszystko naraz”

Najczęstszy błąd:
> „Skoro mamy wskaźniki, użyjmy ich wszystkich.”

Skutek:
- `prob` przestaje być czytelne,
- model reaguje na szum,
- trudna interpretacja wyników.

Zasada:
> **Każdy feature musi wnosić nową informację semantyczną.**



## 10. Dane źródłowe – tabele `companies` i `prices_daily` w kontekście `prob`

Sygnał `prob` bazuje wyłącznie na danych
dostępnych **w dniu analizy (`T`)**.

Kluczowe tabele źródłowe to:
- `companies`
- `prices_daily`

---

### 10.1. Tabela `companies`

Tabela `companies` opisuje **kontekst strukturalny instrumentu**.

Dostępne kolumny:
- `company_id` – klucz główny
- `ticker` – identyfikator rynkowy
- `company_name` – nazwa spółki
- `market` – rynek notowań
- `is_active` – status aktywności
- `created_at` – data dodania

Znaczenie dla `prob`:
- filtrowanie instrumentów aktywnych,
- segmentacja rynków (market regime),
- grupowanie danych do analiz porównawczych.

Tabela ta **nie zawiera informacji czasowych o cenie**,
ale jest kluczowa dla poprawnej selekcji danych.

---

### 10.2. Tabela `prices_daily`

Tabela `prices_daily` jest **głównym źródłem informacji rynkowej**.

Dostępne kolumny:
- `company_id`
- `trade_date`
- `open_price`
- `high_price`
- `low_price`
- `close_price`
- `volume`
- `source_ticker`
- `created_at`

Znaczenie dla `prob`:
- wszystkie wskaźniki techniczne
  są pochodnymi danych z tej tabeli,
- `close_price` jest podstawą większości feature’ów,
- `volume` zasila wskaźniki wolumenu i potwierdzenia,
- sekwencja `trade_date` definiuje kontekst czasowy.

---


### 10.3. Tabela `indicators_dictionary` – słownik semantyczny wskaźników

Tabela `indicators_dictionary` pełni rolę **centralnego słownika wiedzy
o wskaźnikach wykorzystywanych w systemie ANGG**.

Nie przechowuje ona danych liczbowych,
lecz **opisuje znaczenie, pochodzenie i sposób interpretacji wskaźników**.

Jest to kluczowa tabela łącząca:
- warstwę danych,
- warstwę analityczną,
- warstwę interpretacyjną (biznesową).

---

#### Rola tabeli w kontekście `prob`

W kontekście budowy i interpretacji sygnałów probabilistycznych (`prob`)
tabela `indicators_dictionary`:

- definiuje **jak rozumieć każdy feature**,
- pozwala na **kontrolę spójności semantycznej**,
- umożliwia świadomy dobór wskaźników do feature setów,
- zapobiega błędnej interpretacji wskaźników future jako sygnałów bieżących.

---

#### Kluczowe kolumny i ich znaczenie

- `indicator_code`  
  Techniczny identyfikator wskaźnika (używany w kodzie i bazie danych).

- `indicator_name`  
  Czytelna nazwa wskaźnika (do prezentacji i dokumentacji).

- `description`  
  Krótki opis znaczenia wskaźnika.

- `description_full`  
  Pełny opis semantyczny wskaźnika, w tym:
  - co mierzy,
  - w jakim horyzoncie,
  - do czego powinien być używany.

- `category`  
  Kategoria logiczna wskaźnika, np.:
  - `technical`
  - `trend_short_term`
  - `trend_long_term`
  - `risk`
  - `volume_indicator`
  - `future_signal`
  - `future_barrier`

  Kategoria ta jest kluczowa dla:
  - grupowania wskaźników,
  - wykrywania redundancji,
  - budowy feature v1 / v2.

- `source`  
  Informacja o pochodzeniu wskaźnika (np. `calculated`).

- `is_active`  
  Flaga określająca, czy wskaźnik jest aktywnie używany w systemie.

- `introduced_at`  
  Data wprowadzenia wskaźnika – istotna przy analizach historycznych
  i porównywaniu modeli.

- `update_frequency_days`  
  Częstotliwość aktualizacji wskaźnika (np. dzienna).

- `update_policy_comment`  
  Opis polityki aktualizacji (np. „Aktualizacja dzienna”).

---

#### Znaczenie kategorii wskaźników

Pole `category` w `indicators_dictionary` jest **kluczowym elementem
zarządzania wiedzą o wskaźnikach**.

Przykłady:

- `future_signal`, `future_barrier`  
  → wskaźniki **etykietujące dane historyczne**,  
  **nigdy nieużywane bezpośrednio w `prob`**.

- `trend_*`, `technical`, `volume_indicator`, `risk`  
  → wskaźniki **opisowe (features)**,
  potencjalnie wykorzystywane w budowie `prob`.

Dzięki temu podziałowi:
- łatwo oddzielić **labels** od **features**,
- zapobiec look-ahead bias,
- zachować czystość semantyczną modeli.

---

#### `indicators_dictionary` jako kontrakt semantyczny

Tabela ta pełni rolę **kontraktu semantycznego** pomiędzy:

- obliczeniami wskaźników,
- analizą danych,
- interpretacją wyników,
- przyszłym ML.

Każdy nowy wskaźnik:
- powinien być opisany w `indicators_dictionary`,
- powinien mieć jasno określoną kategorię,
- powinien dawać się jednoznacznie zaklasyfikować jako:
  - feature,
  - label (future),
  - wskaźnik pomocniczy.

---

#### Znaczenie dla rozwoju systemu

Dzięki `indicators_dictionary`:

- system pozostaje **czytelny i skalowalny**,
- nowe wskaźniki nie zaburzają interpretacji istniejących,
- dokumentacja (ADR-017) i dane pozostają spójne.

Tabela ta jest **jednym z filarów zarządzania wiedzą w ANGG**,
a nie jedynie metadanymi technicznymi.



---


### 10.4. Zasada kluczowa (bardzo ważna)

W kontekście `prob`:

> **Używane są wyłącznie dane,
> które były znane w dniu `T`.**

Oznacza to:
- brak użycia danych future,
- brak przesuwania etykiet,
- brak „uśredniania przyszłości”.

Ta zasada gwarantuje,
że `prob` jest sygnałem bieżącym,
a nie retrospektywną iluzją.





## 11. Jak dodanie nowego wskaźnika wpływa na `prob`

Dodanie nowego wskaźnika do systemu ANGG
nie jest neutralne dla sygnałów probabilistycznych (`prob`).

Każdy nowy wskaźnik:
- zmienia przestrzeń informacyjną modelu,
- wpływa na sposób interpretacji rynku,
- może poprawić lub pogorszyć jakość `prob`.

Dlatego dodanie wskaźnika należy rozumieć
nie jako operację techniczną,
lecz jako **zmianę semantyki decyzyjnej systemu**.

---

### 11.1. `prob` jako funkcja zestawu cech

Sygnał `prob` można rozumieć jako:
prob = f(features)


Oznacza to, że:
- **zmiana zestawu features = zmiana funkcji `prob`**,
- nawet jeśli etykiety (`fut_signal_20_hyb`) pozostają te same.

W praktyce:
> Ten sam rynek, ten sam dzień,
> ale inny zestaw wskaźników
> → inna ocena prawdopodobieństwa.

---

### 11.2. Co realnie zmienia nowy wskaźnik

Dodanie nowego wskaźnika może:

1. **Dodać nowy wymiar informacji**  
   (np. jakość trendu, ryzyko, wolumen).

2. **Wzmocnić istniejący sygnał**  
   (potwierdzić to, co inne wskaźniki już sugerowały).

3. **Zaburzyć równowagę informacyjną**  
   (jeśli jest redundantny lub silnie skorelowany).

4. **Zmienić interpretację `prob`**  
   (prob zaczyna reagować na inne aspekty rynku).

Dlatego każdy wskaźnik wpływa nie tylko na wynik,
ale też na **sens tego wyniku**.

---

### 11.3. Kategorie wpływu wskaźnika na `prob`

Wpływ nowego wskaźnika zależy od jego **kategorii semantycznej**.

#### A. Wskaźniki kontekstowe (trend, regime)

Przykłady:
- `sma_200`
- `ema_50`
- `fut_signal_20` (jako feature)

Wpływ:
- stabilizują `prob`,
- zmniejszają liczbę fałszywych sygnałów,
- powodują, że `prob` silniej reaguje
  tylko w „właściwych” reżimach rynku.

---

#### B. Wskaźniki momentum i dynamiki

Przykłady:
- `macd_hist`
- `momentum_12m`
- `rsi_14`

Wpływ:
- zwiększają czułość `prob`,
- przyspieszają reakcję na zmiany rynku,
- ale mogą zwiększyć zmienność `prob`.

Ryzyko:
- nadmierna reaktywność,
- „nerwowe” zachowanie sygnału.

---

#### C. Wskaźniki jakości i ryzyka

Przykłady:
- `sharpe_20d`
- `tqs_60d`
- `max_drawdown_252d`

Wpływ:
- wygładzają `prob`,
- poprawiają jego interpretowalność,
- ograniczają sygnały w chaotycznych warunkach.

Efekt biznesowy:
> `prob` zaczyna premiować **jakość**, a nie sam ruch.

---

#### D. Wskaźniki wolumenowe

Przykłady:
- `obv`
- `average_volume_20d`
- `vwap_20d`

Wpływ:
- poprawiają wiarygodność `prob`,
- pozwalają odróżnić „ruch ceny” od „ruchu z kapitałem”.

Efekt:
- mniej sygnałów przypadkowych,
- więcej sygnałów potwierdzonych obrotem.

---

### 11.4. Ryzyko dodawania wskaźników redundantnych

Dodanie wskaźnika,
który **nie wnosi nowej informacji semantycznej**,
powoduje:

- przeuczenie modelu,
- sztuczne zawyżenie pewności (`prob`),
- niestabilność w czasie.

Typowe przykłady:
- kilka średnich o podobnym horyzoncie,
- wiele wskaźników momentum naraz,
- duplikowanie zmienności (ATR + volatility).

Zasada:
> **Każdy wskaźnik musi odpowiadać na inne pytanie o rynek.**

---

### 11.5. Jak świadomie dodawać nowy wskaźnik

Przed dodaniem nowego wskaźnika należy odpowiedzieć na pytania:

1. **Jaką nową informację wnosi?**
2. **Do której kategorii należy?**
3. **Czy nie dubluje istniejących features?**
4. **Jak zmieni zachowanie `prob`?**
5. **Czy zmienia interpretację biznesową sygnału?**

Jeśli nie potrafimy odpowiedzieć na te pytania,
wskaźnik nie powinien być używany w `prob`.

---

### 11.6. Zasada nadrzędna

Dodanie nowego wskaźnika to nie „więcej danych”,
lecz **zmiana definicji tego, co uznajemy za istotny stan rynku**.

Dlatego:

> **`prob` zawsze odzwierciedla nie tylko rynek,
> ale też nasze rozumienie rynku.**

Świadome zarządzanie wskaźnikami
jest kluczowe dla jakości i wiarygodności `prob`.



## 12. Wskaźniki fut_imp_* – interpretacja wartości i horyzontów czasowych

### 12.1 Wskaźniki `fut_imp_*` – interpretacja wartości (mapowanie barier → kod bitowy)

Rodzina `fut_imp_*` koduje wynik kilku wskaźników typu `fut_barrier_*` w postaci liczby całkowitej.
Każdy `fut_barrier_Ap_Bp_Hd` zwraca wartość:
- `+1` → w horyzoncie `H` sesji jako pierwsze wystąpiło **+A%**
- `-1` → w horyzoncie `H` sesji jako pierwsze wystąpiło **-B%**
- `0`  → w horyzoncie `H` nie wystąpiło ani +A% ani -B%

`fut_imp_*` to suma wyników poszczególnych `fut_barrier_*` przemnożonych przez wagi bitowe.

---

# 1) `fut_imp_2`

Informacja o impulsie w horyzoncie 2 sesji
- +64 - jako pierwszy wystąpi wzrost +20%
- -64 - jako pierwszy wystąpi spadek -12%

### Definicja (mapowanie)
- `t1 = fut_barrier_20p_12p_2d`
- `fut_imp_2 = t1 * 64`

### Co oznaczają wartości

| Wartość `fut_imp_2` | Co znaczy | Interpretacja progi / horyzont |
|---:|---|---|
| `+64` | `t1 = +1` | W ciągu **2 sesji** jako pierwsze wystąpił **wzrost +20%** |
| `0` | `t1 = 0` | W ciągu **2 sesji** nie wystąpiło ani **+20%**, ani **-12%** |
| `-64` | `t1 = -1` | W ciągu **2 sesji** jako pierwsze wystąpił **spadek -12%** |

> Uwaga: dla `fut_imp_2` jedyna waga to `64`, więc inne wartości nie występują (poza NULL/NaN wynikającym z braku pełnego horyzontu).

---

# 2) `fut_imp_20`

Suma informacji o impulsie w horyzoncie 20 sesji
- +32 - jako pierwszy wystąpi wzrost +100%
- -32 - jako pierwszy wystąpi spadek -50%      
- +16 - jako pierwszy wystąpi wzrost +50%
- -16 - jako pierwszy wystąpi spadek -20%  
- +8 - jako pierwszy wystąpi wzrost +20%
- -8 - jako pierwszy wystąpi spadek -12%          
Opisuje siłę i spójność impulsu, nie jego kierunek.

### Definicja (mapowanie)
- `t2 = fut_barrier_100p_50p_20d`  (waga `32`)
- `t3 = fut_barrier_50p_20p_20d`   (waga `16`)
- `t4 = fut_barrier_20p_12p_20d`   (waga `8`)

Wzór:
- `fut_imp_20 = (t2 * 32) + (t3 * 16) + (t4 * 8)`

### Jak czytać `fut_imp_20` (zasada dekodowania)

Każda wartość `fut_imp_20` jest sumą składników:
- `+32` / `-32` / `0` → wynik bariery **( +100% vs -50% ) w 20d**
- `+16` / `-16` / `0` → wynik bariery **( +50% vs -20% ) w 20d**
- `+8` / `-8` / `0`   → wynik bariery **( +20% vs -12% ) w 20d**

Interpretacja znaku:
- dodatni składnik oznacza „w tym horyzoncie najpierw padła bariera wzrostowa”
- ujemny składnik oznacza „w tym horyzoncie najpierw padła bariera spadkowa”
- zero oznacza „żadna z barier nie została trafiona w 20d”

### Pełna tabela wartości (wszystkie kombinacje)

| `t2` | `t3` | `t4` | `fut_imp_20` | Interpretacja (20 sesji) |
|---:|---:|---:|---:|---|
| +1 | +1 | +1 | **+56** | Najpierw padły progi wzrostowe: **+100%**, **+50%**, **+20%** |
| +1 | +1 | 0  | **+48** | **+100%** i **+50%**, a dla (+20/-12) brak rozstrzygnięcia |
| +1 | +1 | -1 | **+40** | **+100%**, **+50%**, ale dla (+20/-12) najpierw **-12%** |
| +1 | 0  | +1 | **+40** | **+100%** oraz **+20%**, a (+50/-20) bez rozstrzygnięcia |
| +1 | 0  | 0  | **+32** | Tylko: najpierw **+100%** (w 20d) |
| +1 | 0  | -1 | **+24** | **+100%**, ale dla (+20/-12) najpierw **-12%** |
| +1 | -1 | +1 | **+24** | **+100%**, ale dla (+50/-20) najpierw **-20%**, a (+20/-12) najpierw **+20%** |
| +1 | -1 | 0  | **+16** | **+100%**, ale dla (+50/-20) najpierw **-20%** |
| +1 | -1 | -1 | **+8**  | **+100%**, ale niższe bariery rozstrzygnięte spadkowo (**-20%**, **-12%**) |
| 0  | +1 | +1 | **+24** | Najpierw **+50%** i **+20%** (w 20d) |
| 0  | +1 | 0  | **+16** | Tylko: najpierw **+50%** |
| 0  | +1 | -1 | **+8**  | **+50%**, ale dla (+20/-12) najpierw **-12%** |
| 0  | 0  | +1 | **+8**  | Tylko: najpierw **+20%** |
| 0  | 0  | 0  | **0**   | W 20d brak trafienia progów (+100/-50, +50/-20, +20/-12) |
| 0  | 0  | -1 | **-8**  | Tylko: najpierw **-12%** |
| 0  | -1 | +1 | **-8**  | **-20%**, ale dla (+20/-12) najpierw **+20%** |
| 0  | -1 | 0  | **-16** | Tylko: najpierw **-20%** |
| 0  | -1 | -1 | **-24** | Najpierw **-20%** i **-12%** |
| -1 | +1 | +1 | **0**   | Konflikt: najpierw **-50%** (wysoka bariera) ale niższe wzrostowo (**+50%**, **+20%**) |
| -1 | +1 | 0  | **-8**  | **-50%** oraz **+50%**, (+20/-12) bez rozstrzygnięcia |
| -1 | +1 | -1 | **-16** | **-50%** oraz **+50%**, a dodatkowo **-12%** |
| -1 | 0  | +1 | **-24** | **-50%** oraz **+20%** |
| -1 | 0  | 0  | **-32** | Tylko: najpierw **-50%** |
| -1 | 0  | -1 | **-40** | **-50%** oraz **-12%** |
| -1 | -1 | +1 | **-40** | **-50%**, **-20%**, ale dla (+20/-12) najpierw **+20%** |
| -1 | -1 | 0  | **-48** | **-50%** i **-20%** |
| -1 | -1 | -1 | **-56** | Najpierw progi spadkowe: **-50%**, **-20%**, **-12%** |

#### Jak interpretować „mieszane” wartości (konflikty)
Wartości typu `+40`, `0`, `-8` mogą wynikać z tego, że różne bariery rozstrzygają się w różne strony.
Biznesowo oznacza to:
- rynek miał **silne wybicia** na pewnym poziomie,
- ale w innych progach pojawiała się **kontr-dynamika**,
- czyli sytuacja jest mniej „czysta” niż przypadki skrajne (`+56` lub `-56`).

---

# 3) `fut_imp_60`

Suma informacji o impulsie w horyzoncie 60 sesji 
- +4 - jako pierwszy wystąpi wzrost +50%
- -4 - jako pierwszy wystąpi spadek -20%   
- +2 - jako pierwszy wystąpi wzrost +20%
- -2 - jako pierwszy wystąpi spadek -12%      
Opisuje siłę i spójność impulsu, nie jego kierunek.

### Definicja (mapowanie)
- `t5 = fut_barrier_50p_20p_60d`  (waga `4`)
- `t6 = fut_barrier_20p_12p_60d`  (waga `2`)

Wzór:
- `fut_imp_60 = (t5 * 4) + (t6 * 2)`

### Pełna tabela wartości

| `t5` | `t6` | `fut_imp_60` | Interpretacja (60 sesji) |
|---:|---:|---:|---|
| +1 | +1 | **+6** | Najpierw **+50%** oraz **+20%** (w 60d) |
| +1 | 0  | **+4** | Tylko: najpierw **+50%** |
| +1 | -1 | **+2** | **+50%**, ale dla (+20/-12) najpierw **-12%** |
| 0  | +1 | **+2** | Tylko: najpierw **+20%** |
| 0  | 0  | **0**  | Brak trafienia progów w 60d |
| 0  | -1 | **-2** | Tylko: najpierw **-12%** |
| -1 | +1 | **-2** | **-20%**, ale dla (+20/-12) najpierw **+20%** |
| -1 | 0  | **-4** | Tylko: najpierw **-20%** |
| -1 | -1 | **-6** | Najpierw **-20%** oraz **-12%** |

---

# 4) `fut_imp_120`

Suma informacji o impulsie w horyzoncie 120 sesji  
- +1 - jako pierwszy wystąpi wzrost +50%
- -1 - jako pierwszy wystąpi spadek -20%          
Opisuje siłę i spójność impulsu, nie jego kierunek.

### Definicja (mapowanie)
- `t7 = fut_barrier_50p_20p_120d` (waga `1`)
- `fut_imp_120 = t7 * 1`

### Co oznaczają wartości

| Wartość `fut_imp_120` | Co znaczy | Interpretacja progi / horyzont |
|---:|---|---|
| `+1` | `t7 = +1` | W ciągu **120 sesji** jako pierwsze wystąpił **wzrost +50%** |
| `0` | `t7 = 0` | W ciągu **120 sesji** nie wystąpiło ani **+50%**, ani **-20%** |
| `-1` | `t7 = -1` | W ciągu **120 sesji** jako pierwsze wystąpił **spadek -20%** |

---

## 5) Podsumowanie „co oznacza znak i wartość”

- znak `+` oznacza, że **pierwsza została trafiona bariera wzrostowa** w danym horyzoncie,
- znak `-` oznacza, że **pierwsza została trafiona bariera spadkowa** w danym horyzoncie,
- wartość bezwzględna i jej składniki mówią **które progi** (np. 100/50, 50/20, 20/12) zostały rozstrzygnięte i w jaką stronę.

Wskaźniki `fut_imp_*` nie mówią „ile % dokładnie”, tylko:
> „czy i na jakich poziomach progowych rynek w danym horyzoncie rozstrzygnął się wzrostowo/spadkowo”.


### 12.2. `fut_imp_20` jako klasa jakości impulsu

Wskaźnik `fut_imp_20` może być interpretowany nie tylko
jako suma kodów barier,
ale również jako **klasa jakości impulsu cenowego**
w horyzoncie 20 sesji.

Taka interpretacja jest szczególnie przydatna
w analizach probabilistycznych (`prob`)
oraz w procesie uczenia modeli ML.

---

**Przykłady sygnałów typu "impuls":**
a) `fut_signal_2`
Sygnał wzmocnienia impulsu w horyzoncie 2 sesji
- +1 - wzmocnią się wzrosty
- -1 - pogłębią się spadki    
Czy rynek pozwalał na sensowne granie w tym kierunku?
Binarny i niepowtarzający się w kolejnych sesjach sygnał kierunkowy.   

b) `fut_signal_20`
Sygnał wzmocnienia impulsu w horyzoncie 20 sesji
- +1 - wzmocnią się wzrosty
- -1 - pogłębią się spadki   
Czy rynek pozwalał na sensowne granie w tym kierunku? 
Binarny i niepowtarzający się w kolejnych sesjach sygnał kierunkowy.          

c) `fut_signal_60`
Sygnał wzmocnienia impulsu w horyzoncie 60 sesji  
- +1 - wzmocnią się wzrosty
- -1 - pogłębią się spadki       
Czy rynek pozwalał na sensowne granie w tym kierunku? 
Binarny i niepowtarzający się w kolejnych sesjach sygnał kierunkowy.           

d) `fut_signal_120`
Sygnał wzmocnienia impulsu w horyzoncie 120 sesji  
- +1 - wzmocnią się wzrosty
- -1 - pogłębią się spadki          
Czy rynek pozwalał na sensowne granie w tym kierunku? 
Binarny i niepowtarzający się w kolejnych sesjach sygnał kierunkowy.         

e) `fut_signal_20_hyb`
Sygnał hybrydowy 20D.
Uwzględnia zarówno klasyczny sygnał fut_signal_20, jak i kontynuację trendu.
Sygnał mówi: Czy w tym miejscu pojawił się nowy, jakościowy impuls, a nie tylko kontynuacja stanu rynku?
Dodatkowo `fut_signal_20_hyb` wymaga wcześniejszego osłabienia / pauzy, resetu referencji, braku bezpośredniego powtórzenia impulsu.
Dlatego `fut_signal_20_hyb` jest rzadszy, ale bardziej wartościowy niż `fut_signal_20`.
Binarny i niepowtarzający się w kolejnych sesjach sygnał kierunkowy.



#### 12.2.1. Idea klasy jakości impulsu

`fut_imp_20` łączy wyniki trzech barier:

- `+100% / -50%`
- `+50% / -20%`
- `+20% / -12%`

Wartość wskaźnika informuje:
- **na ilu poziomach cenowych rynek się rozstrzygnął**,
- **czy rozstrzygnięcia były spójne kierunkowo**.

Na tej podstawie można wyróżnić
**klasy jakości impulsu**.

---

#### 12.2.2. Impulsy „czyste” (wysoka jakość)

Wartości:
- `+56`  (32 + 16 + 8)
- `+48`  (32 + 16)
- `+32`  (32)
- `-32`
- `-48`
- `-56`

**Charakterystyka:**
- rozstrzygnięcie nastąpiło **spójnie w jednym kierunku**,
- brak konfliktów pomiędzy progami,
- rynek wykazał **czytelną dominację popytu lub podaży**.

**Interpretacja biznesowa:**
> „W horyzoncie 20 dni rynek zachowywał się jednoznacznie
> i konsekwentnie trendowo.”

Znaczenie dla `prob`:
- bardzo silna etykieta ucząca,
- wysoka przydatność do identyfikacji setupów jakościowych.

---

#### 12.2.3. Impulsy „mieszane” (średnia jakość)

Wartości:
- `+24`, `+16`, `+8`
- `-8`, `-16`, `-24`

**Charakterystyka:**
- rozstrzygnięcia na różnych progach były **niejednoznaczne**,
- występowały konflikty: część barier wzrostowych,
  część spadkowych.

**Interpretacja biznesowa:**
> „Rynek wykonał ruch,
> ale jego struktura była wewnętrznie niespójna.”

Znaczenie dla `prob`:
- sygnał potencjalny, ale o **niższej wiarygodności**,
- wymaga silniejszego potwierdzenia kontekstowego
  (trend, wolumen, jakość).

---

#### 12.2.4. Brak impulsu (niska jakość)

Wartość:
- `0`

**Charakterystyka:**
- żadna z barier nie została rozstrzygnięta,
- rynek poruszał się w zakresie lub losowo.

**Interpretacja biznesowa:**
> „Brak istotnego impulsu w horyzoncie 20 dni.”

Znaczenie dla `prob`:
- słaba etykieta ucząca,
- zazwyczaj niskie wartości `prob`.

---

#### 12.2.5. Znaczenie dla modeli i `prob`

Interpretowanie `fut_imp_20` jako klasy jakości impulsu pozwala:

- rozróżnić **ruch** od **impulsu jakościowego**,
- uczyć model nie tylko *czy* był impuls,
  ale *jak dobrej był jakości*,
- stabilizować `prob`
  poprzez premiowanie impulsów czystych
  i deprecjonowanie mieszanych.

W tym sensie `fut_imp_20`
jest nie tylko etykietą kierunku,
ale również **etykietą jakości zdarzenia rynkowego**.


### 12.3. Jak `fut_imp_20` mapuje się na `fut_signal_20` i `fut_signal_20_hyb`

Wskaźnik `fut_imp_20` jest **bazową etykietą ilościowo-jakościową**,
na podstawie której budowane są wyższe poziomy semantyczne:

- `fut_signal_20` – etykieta **kontekstu trendowego**
- `fut_signal_20_hyb` – etykieta **momentu jakościowego impulsu**

Każdy z tych sygnałów wykorzystuje `fut_imp_20`
w **innym celu i w inny sposób**.

---

#### 12.3.1. Rola `fut_imp_20` w budowie `fut_signal_20`    

`fut_signal_20` odpowiada na pytanie:

> „Czy w horyzoncie 20 dni rynek **nie zaprzeczył kierunkowi**,
> który był widoczny w dniu `t`?”

W tym kontekście `fut_imp_20` jest interpretowany **agregacyjnie**,
bez analizy jakości impulsu.

Typowa logika semantyczna:

- `fut_imp_20 > 0`  
  → `fut_signal_20 = +1`  
  *(rynek w kolejnych 20 dniach zachowywał się wzrostowo)*

- `fut_imp_20 < 0`  
  → `fut_signal_20 = -1`  
  *(rynek w kolejnych 20 dniach zachowywał się spadkowo)*

- `fut_imp_20 = 0`  
  → `fut_signal_20 = NaN / 0`  
  *(brak czytelnego kontekstu trendowego)*

+1 - wzmocnią się wzrosty
-1 - pogłębią się spadki  

**Kluczowe:**
- `fut_signal_20` **nie rozróżnia jakości impulsu**,
- liczy się **kierunek i brak zanegowania**.

Dlatego zarówno:
- `+56`, `+24`, `+8`  
jak i
- `-56`, `-24`, `-8`  

mogą prowadzić do tego samego `fut_signal_20`,
o ile znak jest jednoznaczny.

---

#### 12.3.2. Rola `fut_imp_20` w budowie `fut_signal_20_hyb`

`fut_signal_20_hyb` odpowiada na inne pytanie:

> „Czy w tym miejscu pojawił się
> **nowy, jakościowy impuls**, a nie tylko kontynuacja stanu rynku?”

W tym przypadku `fut_imp_20` jest interpretowany
**selektywnie i jakościowo**.

Typowa logika semantyczna:

- **Impulsy czyste (wysoka jakość)**  
  `fut_imp_20 ∈ { +56, +48, +32, -32, -48, -56 }`  
  → **kandydat do `fut_signal_20_hyb = ±1`**

- **Impulsy mieszane (średnia jakość)**  
  `fut_imp_20 ∈ { +24, +16, +8, -8, -16, -24 }`  
  → zazwyczaj **odrzucone** lub wymagające dodatkowych warunków

- **Brak impulsu**  
  `fut_imp_20 = 0`  
  → **brak `fut_signal_20_hyb`**

Dodatkowo `fut_signal_20_hyb` wymaga:
- wcześniejszego osłabienia / pauzy,
- resetu referencji,
- braku bezpośredniego powtórzenia impulsu.

Dlatego `fut_signal_20_hyb` jest:
- **rzadszy** niż `fut_signal_20`,
- znacznie bardziej **selektywny**.

---

#### 12.3.3. Relacja hierarchiczna: `fut_imp_20` → `signal_*`

Można to ująć w formie hierarchii semantycznej:
fut_imp_20
↓
fut_signal_20 (kierunek / kontekst)
↓
fut_signal_20_hyb (moment / jakość)


- `fut_imp_20`  
  → „co faktycznie wydarzyło się w 20 dni”

- `fut_signal_20`  
  → „czy granie w tym kierunku miało sens”

- `fut_signal_20_hyb`  
  → „czy to był moment, który się wyróżniał”

---

#### 12.3.4. Znaczenie dla `prob`

W kontekście sygnałów probabilistycznych:

- `fut_signal_20` pełni rolę **feature’u kontekstowego**,
- `fut_signal_20_hyb` jest **zdarzeniem docelowym (label)**,
- `fut_imp_20` jest **źródłem semantycznej prawdy historycznej**.

Model uczący `prob`:
- **nie widzi** `fut_imp_20` bezpośrednio,
- uczy się na relacji:
  > *konfiguracja cech → wystąpienie `fut_signal_20_hyb`*.

Dlatego poprawne i spójne mapowanie
`fut_imp_20 → fut_signal_20 → fut_signal_20_hyb`
jest **krytyczne dla jakości `prob`**.

---

#### 12.3.5. Kluczowa zasada interpretacyjna

> **Nie każdy `fut_imp_20 ≠ 0` powinien prowadzić do `fut_signal_20_hyb`.**  
>  
> `fut_signal_20_hyb` opisuje **moment wyjątkowy**,  
> a nie każdą poprawną kontynuację trendu.

To rozróżnienie:
- chroni przed nadetykietowaniem,
- zwiększa jakość etykiet,
- bezpośrednio poprawia stabilność `prob`.


### 12.4. Jak `fut_signal_20` i `fut_signal_20_hyb` wpływają na rozkład `prob`

Sygnał probabilistyczny (`prob`) nie jest generowany w próżni.
Jego rozkład i interpretacja są silnie zależne od tego,
czy w danym miejscu historycznie występował:

- jedynie **kontekst trendowy** (`fut_signal_20`),
- czy też **moment jakościowego impulsu** (`fut_signal_20_hyb`).

Oba sygnały wpływają na `prob` w odmienny sposób.

---

#### 12.4.1. `fut_signal_20` jako regulator poziomu bazowego `prob`

`fut_signal_20` pełni rolę **filtra kontekstowego**.

Odpowiada na pytanie:
> „Czy rynek znajduje się w reżimie,
> w którym historycznie **częściej** pojawiały się impulsy jakościowe?”

Wpływ na rozkład `prob`:

- `fut_signal_20 = +1`
  - cały rozkład `prob` przesunięty **w górę**,
  - wyższe wartości średnie,
  - większa gęstość w przedziale średnich prawdopodobieństw.

- `fut_signal_20 = -1`
  - analogiczne przesunięcie w dół (dla impulsów spadkowych),
  - `prob` faworyzuje scenariusze spadkowe.

- `fut_signal_20 = 0 / NaN`
  - rozkład spłaszczony,
  - `prob` bliskie wartości losowych,
  - brak przewagi kierunkowej.

**Kluczowe:**
`fut_signal_20` **nie tworzy pików** w `prob`,
a jedynie ustala **poziom bazowy i asymetrię rozkładu**.

---

#### 12.4.2. `fut_signal_20_hyb` jako źródło pików w rozkładzie `prob`

`fut_signal_20_hyb` reprezentuje **rzadkie, ale bardzo informacyjne zdarzenia**.

Odpowiada na pytanie:
> „Czy w tej konfiguracji rynku
> historycznie pojawiał się **nowy, jakościowy impuls**?”

Wpływ na rozkład `prob`:

- obserwacje prowadzące do `fut_signal_20_hyb = 1`
  - tworzą **górne ogony rozkładu**,
  - odpowiadają za najwyższe wartości `prob`,
  - są nośnikiem „pewności” modelu.

- brak `fut_signal_20_hyb`
  - powoduje, że `prob` rzadko osiąga skrajne wartości,
  - nawet przy sprzyjającym kontekście (`fut_signal_20 = 1`).

W praktyce:
> **Wysokie `prob` jest statystycznie niemożliwe
> bez historycznego wsparcia w `fut_signal_20_hyb`.**

---

#### 12.4.3. Relacja łączna: kontekst vs zdarzenie

Wpływ obu sygnałów można ująć w formie macierzy semantycznej:

| `fut_signal_20` | `fut_signal_20_hyb` | Typowy rozkład `prob` | Interpretacja |
|------------|-----------------|-----------------------|---------------|
| +1 | 1 | Wysoki, skupiony, prawoskośny | Najlepsze środowisko decyzyjne |
| +1 | 0 | Średni, szeroki | Trend sprzyja, brak momentu |
| 0  | 1 | Rzadki, niestabilny | Impuls bez kontekstu |
| 0  | 0 | Płaski, losowy | Brak przewagi |
| -1 | 1 | Wysoki (dla short) | Silny impuls spadkowy |
| -1 | 0 | Średni / niski | Trend przeciwny |

---

#### 12.4.4. Konsekwencje dla interpretacji `prob`

Z tego wynikają kluczowe zasady interpretacyjne:

1. **Wysokie `prob` bez `fut_signal_20_hyb` jest podejrzane**
   - często oznacza nadmierne dopasowanie do kontekstu.

2. **`fut_signal_20` bez `fut_signal_20_hyb` daje „ciepłe, ale nie gorące” `prob`**
   - dobre do obserwacji, niekoniecznie do działania.

3. **Najwyższe `prob` powstają tylko tam,
   gdzie kontekst i moment są zgodne**.

---

#### 12.4.5. Znaczenie dla ML i stabilności `prob`

Dzięki temu podziałowi ról:

- `fut_signal_20`
  - stabilizuje model,
  - redukuje losowość,
  - odpowiada za „kształt tła” rozkładu.

- `fut_signal_20_hyb`
  - nadaje ostrość,
  - odpowiada za selektywność,
  - tworzy sygnały o wysokiej wartości decyzyjnej.

W efekcie `prob`:
- nie jest binarne,
- nie jest losowe,
- ma **interpretowalną strukturę rozkładu**.

---

#### 12.4.6. Zasada nadrzędna

> **`prob` nie przewiduje impulsu.  
> `prob` mierzy, jak bardzo obecna sytuacja
> przypomina historyczne miejsca,
> w których impulsy faktycznie występowały.**

`fut_signal_20` i `fut_signal_20_hyb`
definiują, **jak wyglądają te miejsca w danych**.


### 12.5. Przykładowe scenariusze: `fut_imp` → `signal` → `prob`

Poniższe scenariusze mają charakter **walidacyjny**.
Ich celem nie jest pokazanie „idealnych setupów”,
lecz sprawdzenie, czy przejście:
fut_imp → fut_signal_20 → fut_signal_20_hyb → prob


jest logiczne, spójne i interpretowalne.

---

#### Scenariusz 1: Czysty impuls wzrostowy w trendzie

**Dane historyczne:**
- `fut_imp_20 = +56`
- `fut_signal_20 = +1`
- `fut_signal_20_hyb = +1`

**Interpretacja future:**
- rynek w ciągu 20 dni rozstrzygnął się wzrostowo
  na wszystkich progach (+20%, +50%, +100%),
- impuls był spójny i jakościowy.

**Oczekiwany wpływ na `prob`:**
- wysokie wartości `prob`,
- wyraźny pik w górnym ogonie rozkładu,
- stabilna predykcja (niska wariancja).

**Walidacja logiczna:**
> Najlepszy możliwy przypadek – kontekst + moment + jakość.

---

#### Scenariusz 2: Kontynuacja trendu bez nowego impulsu

**Dane historyczne:**
- `fut_imp_20 = +16`
- `fut_signal_20 = +1`
- `fut_signal_20_hyb = 0`

**Interpretacja future:**
- rynek rósł,
- ale brak jednoznacznego, nowego impulsu jakościowego,
- raczej kontynuacja niż punkt decyzyjny.

**Oczekiwany wpływ na `prob`:**
- `prob` w przedziale średnim,
- brak skrajnych wartości,
- sygnał „sprzyjające środowisko, brak triggera”.

**Walidacja logiczna:**
> `prob` nie powinno być wysokie tylko dlatego,
> że trend trwa.

---

#### Scenariusz 3: Impuls bez kontekstu trendowego

**Dane historyczne:**
- `fut_imp_20 = +32`
- `fut_signal_20 = 0`
- `fut_signal_20_hyb = +1`

**Interpretacja future:**
- wystąpił wyraźny impuls wzrostowy,
- ale nie był on osadzony w stabilnym trendzie.

**Oczekiwany wpływ na `prob`:**
- rozkład niestabilny,
- możliwe lokalnie wysokie `prob`,
- ale z dużą wariancją i niską powtarzalnością.

**Walidacja logiczna:**
> System widzi „coś się wydarzyło”,
> ale nie ma pewności, że to środowisko się powtórzy.

---

#### Scenariusz 4: Mieszany impuls – konflikt barier

**Dane historyczne:**
- `fut_imp_20 = +24`
- `fut_signal_20 = +1`
- `fut_signal_20_hyb = 0`

**Interpretacja future:**
- część barier wzrostowych została trafiona,
- inne rozstrzygnęły się spadkowo,
- impuls był niespójny.

**Oczekiwany wpływ na `prob`:**
- `prob` umiarkowane lub niskie,
- brak wyraźnych pików,
- system „nie ufa” temu wzorcowi.

**Walidacja logiczna:**
> Mieszana struktura future
> nie powinna prowadzić do silnych sygnałów.

---

#### Scenariusz 5: Czysty impuls spadkowy (symetria)

**Dane historyczne:**
- `fut_imp_20 = -56`
- `fut_signal_20 = -1`
- `fut_signal_20_hyb = -1`

**Interpretacja future:**
- rynek jednoznacznie spadkowy,
- spójny impuls jakościowy.

**Oczekiwany wpływ na `prob`:**
- wysokie `prob` dla scenariusza short,
- analogiczna struktura jak w scenariuszu 1,
- zachowana symetria modelu.

**Walidacja logiczna:**
> Brak symetrii long/short byłby sygnałem błędu modelowego.

---

#### Scenariusz 6: Brak impulsu – rynek losowy

**Dane historyczne:**
- `fut_imp_20 = 0`
- `fut_signal_20 = 0`
- `fut_signal_20_hyb = 0`

**Interpretacja future:**
- brak istotnych rozstrzygnięć,
- rynek boczny lub chaotyczny.

**Oczekiwany wpływ na `prob`:**
- rozkład płaski,
- `prob` bliskie wartości losowej,
- brak przewagi decyzyjnej.

**Walidacja logiczna:**
> System powinien „nic nie widzieć”
> tam, gdzie faktycznie nic się nie wydarzyło.

---

#### 12.5.1. Jak używać tych scenariuszy w praktyce

Scenariusze te mogą służyć do:

- testów regresji semantycznej (`czy prob zachowuje się tak samo po zmianach`),
- walidacji nowych wskaźników,
- sanity-checków modeli ML,
- interpretacji nietypowych wyników `prob`.

Jeśli model generuje wysokie `prob`
w scenariuszach 4 lub 6,
oznacza to **problem z feature setem lub etykietami**.

---

#### 12.5.2. Zasada końcowa

> **Każde wysokie `prob` powinno dać się
> przypisać do jednego z „dobrych” scenariuszy.**

Jeśli nie potrafimy tego zrobić,
oznacza to, że system przestał być interpretowalny.




---

## 13. Kontekst zbiorczy vs prognoza (ważne rozróżnienie)

W aplikacji *Analiza GG* wprowadzono pojęcie
**globalnego kontekstu spółki**, prezentowanego w UI
jako znacznik stanu ogólnego (kolorowy box).

### Czym jest kontekst zbiorczy

Kontekst zbiorczy:
- opisuje **aktualny stan rynku na podstawie danych historycznych**,
- łączy informacje o trendzie, momentum, zmienności, wolumenie i ryzyku,
- jest formą **syntezy interpretacyjnej**, a nie sygnałem.

### Czym NIE jest

Kontekst zbiorczy:
- ❌ nie jest prognozą przyszłych cen,
- ❌ nie jest rekomendacją inwestycyjną,
- ❌ nie jest sygnałem kup/sprzedaj,
- ❌ nie mówi *co zrobić*.

Opisuje wyłącznie:
> „W jakim środowisku rynkowym spółka znajduje się **teraz**,
> patrząc przez pryzmat danych historycznych.”

### Znaczenie dla interpretacji analiz

Globalny kontekst:
- pomaga interpretować wyniki analiz cząstkowych,
- ustawia „ramę mentalną” dla wykresów i wskaźników,
- zapobiega nadinterpretacji pojedynczych sygnałów.

Jest to narzędzie **orientacyjne**, nie decyzyjne.
