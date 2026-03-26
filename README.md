# Analiza GG

Projekt **Analiza GG** to inicjatywa analityczno-badawcza poświęcona analizie spółek giełdowych
z wykorzystaniem **analizy fundamentalnej i technicznej**.

Celem projektu jest wypracowanie **uporządkowanego, powtarzalnego i dobrze udokumentowanego
podejścia do analizy giełdowej**, które w przyszłości może stanowić podstawę do budowy
narzędzi analitycznych, modeli lub dashboardów.

> Projekt ma charakter edukacyjny i analityczny.  
> Nie stanowi doradztwa inwestycyjnego ani rekomendacji typu „kup / sprzedaj”.

---

## Zakres projektu

### W zakresie (IN)
- analiza fundamentalna spółek giełdowych,
- analiza techniczna (trendy, formacje, wolumen, momentum),
- porównywanie spółek w obrębie sektorów,
- identyfikacja i interpretacja kluczowych wskaźników finansowych i rynkowych,
- praca na danych historycznych (EOD),
- projektowanie logiki analitycznej i struktury danych,
- dokumentowanie decyzji architektonicznych i analitycznych.

### Poza zakresem (OUT)
- rekomendacje inwestycyjne w rozumieniu doradztwa finansowego,
- handel automatyczny i systemy transakcyjne,
- analiza intraday o wysokiej częstotliwości.

---

## Struktura repozytorium

.
├─ README.md # Opis projektu
├─ environment.yml # Definicja środowiska (Python / analiza danych)
├─ Dokumentacja/
│ ├─ README.md # Wprowadzenie do dokumentacji
│ ├─ PROJECT_BRIEF.md # Cel, zakres i kontekst projektu
│ ├─ BACKLOG.md # Otwarte pytania i pomysły
│ └─ adr/ # Decyzje architektoniczne (ADR)
│ ├─ ADR_INDEX.md
│ ├─ ADR-001-Stooq-import.md
│ └─ ADR_TEMPLATE.md
└─ .gitignore


---

## Dokumentacja

Pełna dokumentacja projektu znajduje się w katalogu [`Dokumentacja/`](Dokumentacja).

Najważniejsze artefakty:
- **PROJECT_BRIEF.md** – definicja celu, zakresu i założeń projektu,
- **BACKLOG.md** – pytania otwarte, pomysły i kierunki dalszych prac,
- **adr/** – decyzje architektoniczne i techniczne podejmowane w projekcie.

Każda istotna decyzja projektowa:
- jest zapisywana w ADR,
- ma jasno opisany kontekst, uzasadnienie i konsekwencje.

---

## Źródła danych (MVP)

Na etapie MVP podstawowym źródłem danych rynkowych jest:
- **stooq.pl**  
  (zgodnie z decyzją udokumentowaną w ADR-001)

Projekt zakłada możliwość weryfikacji i rozszerzenia źródeł danych w kolejnych iteracjach.

---

## Status projektu

- Status: **w toku**
- Charakter: analityczno-badawczy
- Repozytorium: prywatne
- Główne artefakty: dokumentacja, decyzje architektoniczne, backlog

---

## Zasady pracy

- wyraźne oddzielanie danych, interpretacji i wniosków,
- brak rekomendacji inwestycyjnych,
- decyzje → ADR,
- pytania i pomysły → BACKLOG,
- iteracyjny rozwój projektu.

---

