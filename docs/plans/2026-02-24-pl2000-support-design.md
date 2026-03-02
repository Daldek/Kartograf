# Design: Wsparcie godlowania PL-2000 w Kartografie

**Data:** 2026-02-24
**Status:** Zatwierdzony

## Kontekst

GUGiK udostepnia czesc danych NMT (np. N/NE od Poznania) z godlami w ukladzie PL-2000.
Przyklad URL: `https://opendata.geoportal.gov.pl/NumDaneWys/NMT/77247/77247_1336074_6.179.12.20.asc`

Obecna implementacja `SheetParser` obsluguje wylacznie godla PL-1992 (format `N-34-130-D-d-2-4`).
PL-2000 uzywa zupelnie innego formatu (`6.179.12.20`) i innego ukladu wspolrzednych (EPSG:2176-2179).

## Architektura: Kompozycja (Strategy Pattern)

`SheetParser` pozostaje publicznym API (backward compatible). Wewnetrznie deleguje do
`_Parser1992` lub `_Parser2000` na podstawie auto-detekcji formatu godla.

### Nowe pliki

```
kartograf/core/
├── sheet_parser.py      # SheetParser (fasada) — rozszerzony o auto-detekcje
├── parser_1992.py       # _Parser1992 — wyekstrahowana logika PL-1992
├── parser_2000.py       # _Parser2000 — nowa logika PL-2000
└── geometry.py          # bez zmian
```

### Auto-detekcja formatu

- Kropki + same cyfry → PL-2000 (`6.179.12`, `6.179.12.20`)
- Myslniki + litery → PL-1992 (`N-34-130-D-d-2-4`)
- Brak kolizji miedzy formatami
- Jawny parametr `uklad` walidowany pod zgodnosc z formatem

## PL-2000 — model danych

### Komponenty godla

| Komponent | Nazwa | Zakres | Przyklad |
|-----------|-------|--------|----------|
| `strefa` | Strefa merydianowa | 5, 6, 7, 8 | `6` |
| `pas` | Numer pasa (wiersz) | 3 cyfry | `179` |
| `slup` | Numer slupa (kolumna) | 2 cyfry | `12` |
| `ark_5k` | Podzial 1:5k | 1-4 (2x2) | `3` |
| `ark_2k` | Podzial 1:2k | 01-25 (5x5) | `20` |
| `ark_1k` | Podzial 1:1k | 1-4 (2x2) | `2` |
| `ark_500` | Podzial 1:500 | 1-4 (2x2) | `1` |

### Hierarchia skal

```
6.179.12                 1:10000   (5 km x 8 km)
 ├─ 6.179.12.1           1:5000    (2.5 km x 4 km)     2x2
 ├─ 6.179.12.01          1:2000    (1 km x 1.6 km)      5x5
 │   ├─ 6.179.12.01.1    1:1000    (500 m x 800 m)      2x2
 │   │   └─ 6.179.12.01.1.1  1:500 (250 m x 400 m)     2x2
```

1:5k i 1:2k dziela ten sam arkusz 1:10k niezaleznie.
Detekcja: 1 cyfra po 3. komponencie = 1:5k, 2 cyfry = 1:2k.

### Regex

```python
PATTERNS_2000 = {
    "1:10000": r"^([5-8])\.(\d{1,3})\.(\d{1,2})$",
    "1:5000":  r"^([5-8])\.(\d{1,3})\.(\d{1,2})\.([1-4])$",
    "1:2000":  r"^([5-8])\.(\d{1,3})\.(\d{1,2})\.(\d{2})$",
    "1:1000":  r"^([5-8])\.(\d{1,3})\.(\d{1,2})\.(\d{2})\.([1-4])$",
    "1:500":   r"^([5-8])\.(\d{1,3})\.(\d{1,2})\.(\d{2})\.([1-4])\.([1-4])$",
}
```

### Numeracja

Kwadranty 2x2 (1:5k, 1:1k, 1:500):
```
+---+---+
| 1 | 2 |
+---+---+
| 3 | 4 |
+---+---+
```

Siatka 5x5 (1:2k): 01-25, wiersz po wierszu od NW.

## Obliczanie BBox

### Uklady wspolrzednych

| Strefa | Poludnik osiowy | EPSG | False Easting |
|--------|----------------|------|---------------|
| 5 | 15E | 2176 | 5 500 000 m |
| 6 | 18E | 2177 | 6 500 000 m |
| 7 | 21E | 2178 | 7 500 000 m |
| 8 | 24E | 2179 | 8 500 000 m |

### Formuly — godlo → BBox (1:10k)

```python
X_nw = pas * 5000 + 4_920_000       # Northing (metry)
Y_nw = slup * 8000 + 332_000        # Easting w strefie (metry)
Y_nw_full = strefa * 1_000_000 + Y_nw  # Pelny Easting z prefixem strefy

BBox(min_x=Y_nw_full, min_y=X_nw, max_x=Y_nw_full+8000, max_y=X_nw+5000, crs=ZONE_EPSG[strefa])
```

### Podzialy — offset wewnatrz arkusza

- 1:5k (2x2): offset row*2500, col*4000
- 1:2k (5x5): offset row*1000, col*1600 (row, col = divmod(ark-1, 5))
- 1:1k (2x2): offset row*500, col*800
- 1:500 (2x2): offset row*250, col*400

### Wymiary arkuszy

```python
SHEET_DIMENSIONS_2000 = {
    "1:10000": (5000, 8000),
    "1:5000":  (2500, 4000),
    "1:2000":  (1000, 1600),
    "1:1000":  (500,  800),
    "1:500":   (250,  400),
}
```

### Transformacja CRS

`get_bbox(crs=...)`: natywny CRS strefy (domyslny), EPSG:2180, EPSG:4326 — via pyproj.

## Integracja z pobieraniem

### find_sheets_2000_for_bbox

```python
def find_sheets_2000_for_bbox(
    bbox: BBox,
    target_scale: str = "1:10000",
    zone: int | None = None,
) -> list[str]:
```

Algorytm: bbox → WGS84 → okreslenie stref → transformacja do EPSG strefy →
obliczenie zakresu pas/slup → generacja godol → drazenie do target_scale.

### find_sheets_for_bbox — rozszerzenie

```python
def find_sheets_for_bbox(
    bbox: BBox,
    target_scale: str = "1:10000",
    system: str = "1992",
) -> list[str]:
```

Domyslnie `"1992"` — pelna kompatybilnosc wsteczna.

### FileStorage

Nowy podkatalog: `nmt_2000_1m/` ze struktura `strefa/pas/slup/[podzialy]/plik.asc`.

## CLI

### Auto-detekcja godla

```bash
kartograf parse 6.179.12.20       # auto → PL-2000
kartograf download 6.179.12       # auto → PL-2000
kartograf download N-34-130-D     # auto → PL-1992
```

### Nowe parametry

- `--bbox-crs`: rozszerzony o EPSG:2176-2179
- `--system {1992,2000}`: dla --geometry i --bbox (domyslnie 1992)

### Parse output dla PL-2000

Dodatkowe pola: Strefa, Natywny CRS.

## Obsluga bledow

| Blad | Wyjatek |
|------|---------|
| Nieprawidlowa strefa (nie 5-8) | `ValidationError` |
| ark_2k poza 1-25 | `ValidationError` |
| Kwadrant poza 1-4 | `ValidationError` |
| Brak dopasowania regex | `ParseError` |
| Konflikt uklad/format | `ValidationError` |

Istniejace wyjatki `ParseError` i `ValidationError` wystarczaja.

## Testy

Szacunkowo ~150-200 nowych testow:
- Parsing wszystkich skal, normalizacja, edge cases
- BBox: obliczenia metryczne, transformacje CRS
- Hierarchia: parent/children/descendants
- find_sheets_2000_for_bbox
- Integracja CLI: auto-detekcja, parse, download
- Kompatybilnosc wsteczna: istniejace testy PL-1992 bez zmian
