# Format raportu audytu (obowiazkowy)

Plik: .superpowers/sdd/2026-08-22-release-0.7.0-audit/audit/<ID>-report.md

```
# <ID> — <obszar>
Zakres: <pliki/katalogi faktycznie przeczytane w calosci>
Metoda: <co zrobiles: czytanie pelnych plikow, grep, uruchomione komendy>
Nie sprawdzono: <co pominales i dlaczego>

## Ustalenia
### <ID>-1 [Critical|Important|Minor] <krotki tytul>
- Plik: <sciezka>:<linia>
- Twierdzenie: <jedno zdanie, co jest nie tak>
- Dowod: <cytat kodu/dokumentu 1-6 linii; dla bledow logicznych: konkretne wejscie -> zle wyjscie>
- Weryfikacja: <jak to potwierdziles — np. uruchomiony snippet w .venv/bin/python, test, grep; "nie weryfikowano" jesli tylko czytanie>
- Proponowana naprawa: <konkretnie, 1-3 zdania>
- Pewnosc: <wysoka|srednia|niska>

## Pozytywy (krotko, max 5 punktow)
## Podsumowanie liczbowe: C=<n> I=<n> M=<n>
```

Definicje severity:
- Critical: bledny wynik dla uzytkownika, utrata danych, crash na realnej sciezce, naruszenie udokumentowanego kontraktu (sidecar, API publiczne, CLI)
- Important: blad na sciezce brzegowej, niespojnosc kod<->dokumentacja wprowadzajaca w blad, duplikat logiki z rozjazdem zachowania, martwy kod udajacy aktywny
- Minor: styl, nazewnictwo, drobne duplikaty bez rozjazdu, literowki, martwy kod oczywisty

Zasady:
- NIE modyfikuj zadnych plikow sledzonych przez git. Tylko czytasz i piszesz raport. Pliki pomocnicze wylacznie w scratchpadzie.
- Kazde ustalenie Critical/Important musi miec Dowod i Weryfikacje. Lepiej 5 twardych ustalen niz 30 domyslow.
- Nie zglaszaj: braku `--strict` w mypy (swiadoma decyzja, baseline 33 bledow), polskich znakow w docs (ASCII-only jest swiadome w czesci plikow), stylu ruff (przechodzi).
- Jezyk raportu: polski (bez polskich znakow diakrytycznych, jak w repo).
