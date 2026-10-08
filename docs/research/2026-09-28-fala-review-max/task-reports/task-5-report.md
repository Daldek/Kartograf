# Zad. 5 — raport implementacji

Selekcja arkuszy nie gubi pasa przy gornej krawedzi bboxa na poludniku 19°E (fakt 8).

## Co zrobiono

Zmieniono `_transform_bbox_to_wgs84()` w `kartograf/core/sheet_parser.py` (przed
zmiana: linie 927-959, dokladnie jak cytowane w briefie — bez rozbieznosci
file:line). Funkcja liczyla obwiednie WGS84 bboxa EPSG:2180 z 4 naroznikow.
W PUWG 1992 rownolezniki sa lukami: wzdluz linii stalego `y` szerokosc
geograficzna jest najwieksza na poludniku osiowym (`x = 500 000 m`, 19°E),
wiec dla bboxa przecinajacego ten poludnik prawdziwe maksimum szerokosci na
gornej krawedzi wypadalo POZA probka 4 naroznikow — obwiednia byla za niska
i `find_sheets_for_bbox`/`find_sheets_for_geometry` gubily arkusze dotykajace
prawdziwej gornej krawedzi bboxa.

Naprawa (doslownie wg brief): gdy `bbox.min_x < 500_000 < bbox.max_x`, do
listy punktow transformowanych do WGS84 dochodza dwa dodatkowe punkty na
poludniku osiowym (`(500000, min_y)` i `(500000, max_y)`); obwiednia to nadal
min/max po wszystkich transformowanych punktach. Stala modulowa
`_PL1992_CENTRAL_X = 500_000.0` nad funkcja, docstring rozszerzony o
uzasadnienie geometryczne (dlaczego dolna krawedz i osie pionowe nie
potrzebuja dodatkowych punktow).

Zaimplementowano dokladnie kod z brief (Step 3) — bez odstepstw.

## RED — test padajacy

Dodano `test_top_edge_across_central_meridian_keeps_sheets` w
`TestFindSheetsForBBox` (`tests/test_sheet_parser.py`), tresc dokladnie wg
brief (Step 1), po istniejacym `test_roundtrip_single_sheet_all_scales`
(koniec klasy, przed sekcja "Testy auto-detekcji PL-1992 vs PL-2000").

Komenda:
```
.venv/bin/python -m pytest tests/test_sheet_parser.py::TestFindSheetsForBBox::test_top_edge_across_central_meridian_keeps_sheets -v
```

Wynik PRZED implementacja (RED), fragment:
```
E   AssertionError: assert {'N-34-134-B-d-3-2', 'N-34-134-B-d-4-1', 'N-34-134-B-d-4-2', 'N-34-135-A-c-3-2', 'N-34-135-A-c-3-1', 'N-34-135-A-c-4-1'} <= {...50 elementow bez tych szesciu...}
  Extra items in the left set:
  'N-34-135-A-c-3-2'
  'N-34-134-B-d-3-2'
  'N-34-134-B-d-4-1'
  'N-34-134-B-d-4-2'
  'N-34-135-A-c-3-1'
  'N-34-135-A-c-4-1'
1 failed in 0.45s
```
Dokladnie 6 brakujacych godel, zgodnie z pre-flight.

## GREEN

Po implementacji (Step 3 z briefu):
```
.venv/bin/python -m pytest tests/test_sheet_parser.py::TestFindSheetsForBBox::test_top_edge_across_central_meridian_keeps_sheets -v
...
tests/test_sheet_parser.py::TestFindSheetsForBBox::test_top_edge_across_central_meridian_keeps_sheets PASSED [100%]
1 passed in 0.27s
```

Pelny plik testowy:
```
.venv/bin/python -m pytest tests/test_sheet_parser.py -v
...
290 passed in 1.16s
```
Wszystkie 289 istniejacych testow w pliku przeszly bez zmian — zaden istniejacy
test nie mial bboxa przecinajacego x=500000 w sposob ujawniajacy nadmiarowa
selekcje (Step 4 z briefu: nic do aktualizacji/analizy, zero regresji).

## Zmierzona nadmiarowa selekcja (Step 4 z briefu — weryfikacja, nie zgadywanie)

Brief mowil "zmierzone w pre-flight +4 arkusze dla bboxa uzytego w testach
tego zadania" — zweryfikowalem to niezaleznie live (monkeypatch starej vs
nowej `_transform_bbox_to_wgs84` na tym samym bboxie):

```
old count: 50
new count: 60
gained (in new, not old): ['N-34-134-B-c-4-2', 'N-34-134-B-d-3-1',
  'N-34-134-B-d-3-2', 'N-34-134-B-d-4-1', 'N-34-134-B-d-4-2',
  'N-34-135-A-c-3-1', 'N-34-135-A-c-3-2', 'N-34-135-A-c-4-1',
  'N-34-135-A-c-4-2', 'N-34-135-A-d-3-1']
lost (in old, not new): []
```

10 zyskanych = 6 wymaganych (z testu) + 4 nadmiarowe
(`N-34-134-B-c-4-2`, `N-34-134-B-d-3-1`, `N-34-135-A-c-4-2`,
`N-34-135-A-d-3-1`). Sprawdzilem `_bboxes_intersect()` tych 4 wzgledem
oryginalnego bboxa EPSG:2180 — wszystkie `False` (nie przecinaja go naprawde;
lezna tuz na polnoc od `bbox.max_y=480161`, np. `min_y=480161.7-480164.9`).
Potwierdza to dokladnie opis z briefu/CHANGELOG: naprawiona obwiednia WGS84
jest szersza niz prawdziwe przeciecie krzywej gornej krawedzi, wiec lapie
dodatkowe arkusze tuz za prawdziwa krawedzia. Zero utraconych arkuszy.
Liczba "+4" z briefu — potwierdzona pomiarem, nie tylko przepisana.

## Dowod mutacyjny

Mutacja (Step 5 z briefu, wykonana PO commicie `8c124fc`, bezpiecznie
przywracalna przez `git checkout --`): usuniety blok `if bbox.min_x <
_PL1992_CENTRAL_X < bbox.max_x: points_2180 += [...]` w
`_transform_bbox_to_wgs84` — powrot do samych 4 naroznikow.

Komenda:
```
.venv/bin/python -m pytest tests/test_sheet_parser.py::TestFindSheetsForBBox::test_top_edge_across_central_meridian_keeps_sheets -v
```

FAIL (fragment):
```
E   AssertionError: assert {'N-34-134-B-d-4-2', 'N-34-135-A-c-3-2', ...} <= {...bez tych 6...}
  Extra items in the left set:
  'N-34-135-A-c-3-2'
  'N-34-134-B-d-4-1'
  'N-34-135-A-c-3-1'
  'N-34-135-A-c-4-1'
  'N-34-134-B-d-3-2'
  'N-34-134-B-d-4-2'
1 failed in 0.31s
```

Przywrocenie: `git checkout -- kartograf/core/sheet_parser.py` (bezpieczne —
praca byla juz zacommitowana w `8c124fc`).

Po przywroceniu:
- `git status --short` → pusty (czyste drzewo)
- test ponownie PASSED (1 passed in 0.27s)

Mutacja powoduje FAIL dokladnie tam, gdzie oczekiwano — test broni realnej
zmiany zachowania.

## Pliki zmienione

- `kartograf/core/sheet_parser.py` — `_transform_bbox_to_wgs84`: dodana stala
  `_PL1992_CENTRAL_X`, rozszerzony docstring, dodane punkty na poludniku
  osiowym gdy bbox go przecina.
- `tests/test_sheet_parser.py` — nowy test
  `test_top_edge_across_central_meridian_keeps_sheets` w
  `TestFindSheetsForBBox`.
- `docs/CHANGELOG.md` — nowy wpis w `### Fixed` sekcji `[0.7.0] - Unreleased`
  (tresc dokladnie wg Step 6 briefu), dopisany po istniejacym wpisie o
  "Too many open files" (review max, zn. 3), przed `### Tests`.

Zaden inny plik nie zostal dotkniety (`git diff --stat` po dodaniu do
stage: 3 pliki, 69 wstawien, 8 usuniec).

## Pelna suita, ruff, mypy

Pelna suita offline (po implementacji, przed commitem i ponownie po
mutacji/przywroceniu):
```
.venv/bin/python -m pytest tests/ -q -m "not live"
===================== 1796 passed, 8 deselected in ~25-27s ======================
```
1796 = baseline 1795 (wg notatki kontrolera) + 1 nowy test. 8 deselected =
testy `live` (zgodnie z Global Constraints).

Ruff:
```
.venv/bin/python -m ruff check kartograf/ tests/
```
Pierwszy przebieg: 1 blad E501 (linia 89 znakow w nowym tescie, > 88) —
zgodnie z ostrzezeniem z IMPLEMENTER_COMMON.md ("kod z planu nie zawsze jest
ruff-clean"). Naprawione przez `ruff format kartograf/ tests/` (auto-zawiniecie
wyrazenia `inside = (...)` w nawiasy/wieksza liczbe linii) — bez recznej
zmiany logiki. Po ponownym uruchomieniu:
```
All checks passed!
```
```
.venv/bin/python -m ruff format --check kartograf/ tests/
86 files already formatted
```
Po autoformacie ponownie uruchomiono `pytest tests/test_sheet_parser.py -q`
→ 290 passed (formatowanie nie zmienilo zachowania).

Mypy:
```
.venv/bin/python -m mypy kartograf/
Found 32 errors in 9 files (checked 52 source files)
```
Diff listy bledow (normalizacja `sed -E 's/:[0-9]+: /: /' | sort`, tylko
linie `error:`) wzgledem
`.superpowers/sdd/2026-09-28-fala-review-max-i-wycinek-biblioteczny/mypy-baseline.txt`:
**identyczne, zero nowych, zero usunietych** (32/32).

Obserwacja poboczna (nie blad, do wiadomosci): biezacy przebieg mypy
dorzuca 3 linie `note: ... kartograf/auth/proxy.py: By default the bodies of
untyped functions are not checked ...` (reprodukowalne, dwa kolejne
uruchomienia dawaly po 3), ktorych NIE ma w `mypy-baseline.txt`. To notatki
informacyjne (nie `error:`, nie wliczaja sie do "Found N errors"), dotycza
pliku spoza zakresu tego zadania (`kartograf/auth/proxy.py`, nie dotkniety
tu) i sa deterministyczne w obu przebiegach — najprawdopodobniej artefakt
tego, jak zostal przechwycony `mypy-baseline.txt` (np. filtr do samych
`error:`), a nie regresja z tej zmiany. Zgloszone dla przejrzystosci, zgodnie
z zasada "dokumentacja klamie czesciej niz kod" — nie jest to nowy blad wg
kryterium bramki (lista `error:` identyczna).

## Commit

```
8c124fc fix(core): selekcja arkuszy uwzglednia poludnik osiowy przy gornej krawedzi bboxa
```
3 pliki wg briefu (`kartograf/core/sheet_parser.py`, `tests/test_sheet_parser.py`,
`docs/CHANGELOG.md`), stopka `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`
wg system-remindera atrybucji. Mutacja wykonana PO tym commicie, przywrocona
`git checkout --`, `git status` czysty na koniec.

## Samoocena i watpliwosci

- Implementacja i test sa doslowne wg briefu (Step 1 i Step 3) — zero
  odstepstw od podanego kodu poza wymuszonym przez ruff zawinieciem jednej
  linii (czysto kosmetyczne, bez zmiany logiki/wartosci).
- Kotwice file:line z briefu (`sheet_parser.py:927-959`, test "ok. l. 995")
  okazaly sie dokladne, nie tylko przyblizone — brak rozbieznosci do
  odnotowania.
- Nadmiarowa selekcja (+4 arkusze) zostala zweryfikowana niezaleznie (nie
  tylko przepisana z briefu) — patrz sekcja wyzej; potwierdzona jako znana,
  nieszkodliwa (arkusze nie przecinaja bboxa, ale sa sasiadami tuz za
  krawedzia) i zgodna z decyzja kontrolera (nie naprawiac w tym zadaniu).
- Jedyna niepewnosc: 3 dodatkowe linie `note:` z mypy dot. `auth/proxy.py`
  nieobecne w baseline.txt — opisane wyzej, oceniam jako nieistotne dla
  bramki (lista `error:` identyczna 32/32), ale zglaszam zamiast przemilczec.
- `--system 2000` (PL-2000, `parser_2000.py`) ma osobna funkcje obwiedni i
  NIE byl w zakresie tego zadania (brief i CHANGELOG jawnie to zaznaczaja
  jako backlog) — nie dotykalem tego kodu.
