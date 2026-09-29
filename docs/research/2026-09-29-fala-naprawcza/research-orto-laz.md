# Research — klaster orto + LAZ (K5, K1, N7)

Data: 2026-09-29, galaz `develop`, HEAD `2e25c18` (drzewo czyste). Faza: wylacznie
research przyczyn i projekt naprawy — zadnych zmian w `kartograf/`, `tests/`,
`docs/` poza tym raportem. Zero zapytan sieciowych do GUGiK; dowody z kodu,
testow offline, raportu `L1-centrum-produkty-report.md` i surowych artefaktow
`e2e-data/2026-09-29-live/L1-centrum-produkty/` (gitignored, obecne lokalnie).

Decyzje wiazace: `decisions.md` (D4 filtr twardy + najnowsza kampania, D5
`extra.source`, D6 pelny zakres). Kontrakt wspolnego modulu skorowidza
uzgodniony z klastrem skorowidz (`ResearchSkorowidz2`, wlasciciel
`gugik.py`/`skorowidz.py`/`manager.py::_write_sidecar`/`base.py::source_info`/
`transport/http.py::make_gugik_session`) — nazwy ponizej sa identyczne z jego
raportem.

---

## K1 — LAZ: discovery WFS z zamienionymi osiami (KRYTYCZNY)

### 1. Przyczyna potwierdzona na kodzie

Hipoteza z backlogu (`PROGRESS.md:1042-1054`) **potwierdzona w calosci**, z jednym
uzupelnieniem: to nie tylko "zamiana w zapytaniu i w odczycie" — to zamiana
**po obu stronach spojnie**, przez co jedyny mechanizm obronny (`_intersects`)
jest slepy.

**(a) Zapytanie — `kartograf/providers/pl/gugik_laz.py:363-369`:**

```python
# WFS expects the bbox in the same axis order as Kartograf's BBox
# (min_x, min_y, max_x, max_y) with the urn CRS appended; the returned
# gml:Envelope corners are in that same (x, y) frame. Verified live.
bbox_param = (
    f"{bbox.min_x},{bbox.min_y},{bbox.max_x},{bbox.max_y},"
    "urn:ogc:def:crs:EPSG::2180"
)
```

`BBox` Kartografu to (x=E, y=N). `urn:ogc:def:crs:EPSG::2180` ma osie EPSG
**(Northing, Easting)** — potwierdzone lokalnie `pyproj`:
`CRS("EPSG:2180").axis_info -> [('Northing','north'), ('Easting','east')]`.
Serwer WFS 2.0 stosuje dla formy `urn:` kolejnosc EPSG (dowod na zywo L1 pkt 4:
`BBOX=235100,536400,235300,536600,urn:...` (N,E) -> `M-34-76-A-a-1-1-3` Spytkowice;
`BBOX=536400,235100,536600,235300,urn:...` (E,N) — to, co wysyla Kartograf ->
`N-33-127-A-a-2-3-4` Lubuskie, `logs/B3_wfs_axis_test.log`). Komentarz
"Verified live" jest falszywy (ADR-021 errata juz to stwierdza; weryfikacja z
2026-06-24 byla kolowa).

**(b) Odczyt envelope — `gugik_laz.py:453-465`:**

```python
if lc is not None and lc.text:
    lower = tuple(float(v) for v in lc.text.split())
...
if lower and upper and len(lower) == 2 and len(upper) == 2:
    min_x, min_y = lower
    max_x, max_y = upper
```

`gml:Envelope srsName="urn:ogc:def:crs:EPSG::2180"` ma narozniki w porzadku
(N, E). Dowod z surowej odpowiedzi (L1, `B3_wfs_axis_test.log:3`): kafel
`N-33-127-A-a-2-3-4` ma `lowerCorner '535970.42 234660.93'`; obwiednia arkusza
`N-33-127-A-a-2-3` z `SheetParser` w EPSG:2180 to
`min_x=233604.24, min_y=535970.417, max_x=235843.28, max_y=538400.81` — pierwsza
liczba naroznika (535970.42) jest **rowna `min_y` (northing)** arkusza, wiec
pierwsza wartosc to N, druga E. Kod czyta ja jako `min_x`.

**(c) Filtr — `gugik_laz.py:481-496` (`_intersects`)** dziala na tak samo
zamienionych wspolrzednych po obu stronach, wiec przepuszcza kafel transponowany
i **odrzucilby kafel poprawny**. Reprodukcja offline (sesja-atrapa, fixture
w RZECZYWISTEJ ramce serwera "N E", bbox Spytkowice `536400,235100,536600,235300`):

```
server answer to CORRECT (N,E) query  -> discover_tiles -> []            # poprawny kafel ODRZUCONY
server answer to TODAY's (E,N) query  -> discover_tiles -> [('N-33-127-A-a-2-3-4', 535970.42, 234660.93, ...)]
BBOX param sent today: 536400,235100,536600,235300,urn:ogc:def:crs:EPSG::2180
```

Transpozycja liczbowo (pyproj, offline): srodek bboxa `(E,N)=(536500,235200)` =
19.509°E 49.983°N; te same liczby po zamianie = 15.086°E 52.629°N (426 km).

**(d) Testy utrwalaja blad.** `tests/test_gugik_laz.py`:
- helper `_feature(godlo, year, lower, upper)` (`:66-90`) wpisuje
  `<gml:lowerCorner>{lower[0]} {lower[1]}` z krotkami podanymi jako (E,N)
  (`_TILE_A = ... (530500, 382500), (531000, 383000)` przy
  `QUERY_BBOX = BBox(530000, 382000, 533000, 386000)`), czyli fixture udaje
  serwer zwracajacy (E,N) — niezgodnie z rzeczywistoscia;
- `test_bbox_param_uses_native_axis_order` (`:306-311`) **asertuje bledna
  kolejnosc**: `"BBOX=530000.0%2C382000.0%2C533000.0%2C386000.0%2Curn"`;
- `test_tile_attributes_parsed` (`:296-304`: `a.min_x == 530500`),
  `test_parses_and_filters_outside_tiles`, `test_min_density_filter`,
  `test_newest_per_godlo_dedup`, `test_pagination_follows_pages` zaleza od
  helpera (przejda po jego poprawieniu, bo krotki pozostaja (x,y)).
- `tests/test_cli.py::TestLazCli._fake_tiles` (`:2477-2503`) buduje `LazTile`
  wprost (x,y) — bez zmian.

### 2. Proponowana naprawa

**Zapytanie (`_query_layer`):** kolejnosc osi EPSG dla formy `urn:`:

```python
# urn:ogc:def:crs:EPSG::2180 = osie EPSG (Northing, Easting) — WFS 2.0
# (potwierdzone na zywo 2026-09-29, L1 BUG-L1-1; BBox Kartografu jest (E, N))
bbox_param = (
    f"{bbox.min_y},{bbox.min_x},{bbox.max_y},{bbox.max_x},"
    "urn:ogc:def:crs:EPSG::2180"
)
```

**Dlaczego nie "jawne `EPSG:2180` w (E,N)":** raport L1 testowal WYLACZNIE forme
`urn:` (obie kolejnosci); dla formy skroconej `EPSG:2180` nie ma dowodu na
zywo. Konwencja serwerow (GeoServer, tabela "Axis ordering": `EPSG:xxxx` =
lon/lat "assumption", `urn:ogc:def:crs:EPSG::xxxx` = EPSG "strict";
MapServer: "for WFS 2.0 [srsName] will always be reported with the
urn:ogc:def:crs:EPSG:: syntax") oznacza, ze **odpowiedz i tak przyjdzie w
`urn:` (N,E)**, wiec parser envelope musi obslugiwac (N,E) niezaleznie od
formy zapytania. Zamiana formy zapytania na `EPSG:2180` dodalaby drugie,
niezweryfikowane zalozenie ("assumption") bez zysku. Rekomendacja: `urn:` +
(N,E) — wariant sprawdzony na zywo po obu stronach. Precedens w kodzie:
WMS 1.3.0 w `gugik.py:534-539` juz wysyla `y,x` dla EPSG:2180.

**Odczyt envelope (`_feature_to_tile`):** kolejnosc wg `srsName` envelope, nie
"na slowo":

```python
_EPSG2180_NORTH_EAST = ("urn:ogc:def:crs:EPSG::2180", "http://www.opengis.net/def/crs/EPSG/0/2180")

def _corner_xy(text: str, srs_name: str | None) -> tuple[float, float]:
    a, b = (float(v) for v in text.split()[:2])
    # urn:/URI = porzadek EPSG (N, E); legacy "EPSG:2180" = (E, N); brak = ramka zadania (urn)
    if srs_name is None or srs_name in _EPSG2180_NORTH_EAST:
        return b, a
    return a, b
```

`LazTile.min_x/min_y/max_x/max_y` zachowuja semantyke (x=E, y=N w EPSG:2180)
— zmiana jest wewnatrz parsera; docstring `LazTile` bez zmian.

**Filtr `_intersects`:** logika bez zmian (dziala na poprawnych x/y), ale
docstring "safety net against WFS axis-order quirks" -> prawdziwa straz:
w `_query_layer` po stronie:

```python
returned, kept = 0, 0
for tile in self._parse_features(root):
    returned += 1
    if self._intersects(tile, bbox):
        kept += 1
        yield tile
if returned and not kept:
    raise DownloadError(
        f"WFS {layer}: serwer zwrocil {returned} kafli, zaden nie przecina "
        f"zadanego bboxa — niezgodnosc kolejnosci osi (zglos blad)"
    )
```

Uzasadnienie: serwer filtruje BBOX po geometrii, wiec obwiednia KAZDEGO
zwroconego kafla przecina bbox; "N zwroconych, 0 przecinajacych" jest mozliwe
tylko przy regresji osi (po jednej stronie). Ta straz wykrylaby K1 przy
pierwszym uruchomieniu na zywo — zamiast cichego zlego wyniku byl by kod 1.
Kafle bez geometrii (NaN) nadal liczone jako `kept` (bez zmian).

**Porzadki:** komentarz `gugik_laz.py:363-365` (falszywe "Verified live");
`cli/_parser.py:176-177` — usunac zdanie o K1 (i K5, patrz nizej) z pomocy
`--product`; docstring modulu `gugik_laz.py:29` (przyklad `BBox(530469, 382961,
...)` jest (E,N) — poprawny, zostaje). Dokumentacja "znany blad K1": `README.md:14-16,
207-210, 294`; `CLAUDE.md:158, 371`; `docs/PRD.md:238-241`; `docs/SCOPE.md:163-164`;
`docs/PROGRESS.md:10, 199, 919-921, 962-965, 1042-1054`; `docs/ARCHITECTURE.md:1030`
(errata w tabeli ADR); `docs/IMPLEMENTATION_PROMPT.md:283`; `docs/DECISIONS.md`
ADR-021 errata (`:440-454`) — dopisac akapit "Naprawa (data): BBOX i envelope
w porzadku EPSG (N,E) dla `urn:`; straz 'zwrocone, zadne nie przecina'";
`docs/CHANGELOG.md` (Fixed). Po naprawie obowiazkowo **test na zywo**: bbox
Spytkowice `536400,235100,536600,235300` -> oczekiwany `M-34-76-A-a-1-1-3`
(2023, `77518_1352498_...laz`); przyklad z CLAUDE.md `--bbox 530000,382000,533000,386000`
ma znalezc kafle pod 19.45°E 51.32°N.

Kontrakt dla wolajacych: bez zmian sygnatur (`discover_tiles`, `LazTile`);
zmienia sie TRESC wyniku (wlasciwe kafle) i pojawia sie nowy `DownloadError`
(straz). Sidecar LAZ bez zmian (`extra.godlo_kafla/rok/gestosc/url`;
opcjonalnie, trywialnie: `extra.warstwa = "SkorowidzDanychPomiarowychLIDAR<rok>"`
dla symetrii z D5 — nieblokujace).

### 3. Strategia testow offline (`tests/test_gugik_laz.py`)

- Helper `_feature()` — emitowac ramke serwera: `<gml:lowerCorner>{lower[1]}
  {lower[0]}</gml:lowerCorner>` (krotki nadal (x,y) = (E,N)), z komentarzem
  "urn:...EPSG::2180 = (N, E)". Dzieki temu istniejace testy parsowania i
  filtra stana sie failing-before (dzis parser zamienia osie) / passing-after.
- `test_bbox_param_uses_native_axis_order` -> **usunac** (pinuje blad) i
  zastapic `test_bbox_param_epsg_axis_order_north_east`:
  `"BBOX=382000.0%2C530000.0%2C386000.0%2C533000.0%2Curn"` w URL.
- Nowy test z danymi na zywo (L1): bbox `BBox(536400, 235100, 536600, 235300)`;
  member `M-34-76-A-a-1-1-3`, `akt_rok 2023`, `char_przestrz "4 p/m2"`,
  `uklad_xy PL-1992`, `lowerCorner "234772 535830"`, `upperCorner "235938 536958"`
  (N E — z `B3_wfs_axis_test.log:8`) -> `discover_tiles` zwraca ten kafel z
  `min_x == 535830`, `min_y == 234772`, `max_x == 536958`, `max_y == 235938`
  (dzis: `[]`, dowod w sekcji 1c).
- Nowy test strazy: ten sam bbox, member `N-33-127-A-a-2-3-4` z `lowerCorner
  "535970.42 234660.93"`, `upperCorner "537185.43 235780.44"` (odpowiedz serwera
  na dzisiejsze zapytanie) -> `pytest.raises(DownloadError, match="kolejnosci osi")`
  (dzis: kafel zwrocony — failing-before).
- Test parsera `srsName`: envelope z `srsName="EPSG:2180"` (legacy) czytany
  (E,N); bez `srsName` — (N,E); `TestIntersects` bez zmian.
- `tests/test_cli.py::TestLazCli` — bez zmian (mock providera).

### 4. Ryzyka i pozostale pytania projektowe

- **Straz "zwrocone, zadne nie przecina": wyjatek czy ostrzezenie?** (a) `DownloadError`
  (kod 1) — rekomendacja: to jedyny sygnal regresji osi, a cichy zly wynik jest
  gorszy od bledu; (b) `logger.warning` + pusty wynik — ukrylby regresje jak
  dzis; (c) warning + zwrot kafli — najgorsze. Rekomendacja (a).
- **Forma CRS w zapytaniu:** rozstrzygniete wyzej (urn + (N,E)); ryzyko resztkowe:
  GUGiK zmieni stack na taki, ktory dla `urn:` daje (E,N) — wtedy straz (a) da
  jasny blad zamiast zlych danych.
- **Weryfikacja na zywo jest obowiazkowa** (nie da sie domknac K1 offline —
  fixture odtwarza odpowiedz serwera z 2026-09-29).

### 5. Szacunek zakresu

`kartograf/providers/pl/gugik_laz.py` (~30 linii: `_query_layer`, `_feature_to_tile`,
nowy `_corner_xy`, komentarze), `kartograf/cli/_parser.py:176-177` (help),
`tests/test_gugik_laz.py` (helper + 1 usuniety + 3-4 nowe testy), dokumentacja
(11 miejsc wyzej) + ADR-021 (dopisek) + CHANGELOG. Kontrakt publiczny: brak
zmian sygnatur; nowy przypadek `DownloadError` z `discover_tiles` (straz).

---

## K5 — orto: CIR zamiast RGB, najstarsze zdjecie w "Starsze" (WYSOKI; D4 + D5)

### 1. Przyczyna potwierdzona na kodzie

`kartograf/providers/pl/gugik_orto.py:373-384`:

```python
urls = self.OPENDATA_URL_PATTERN.findall(response.text)   # r'url:"(https://[^"]+)"'
if urls:
    for found_url in urls:
        if godlo in found_url:            # podciag, pierwszy w kolejnosci HTML
            ...; return found_url
    logger.debug(f"Found OpenData URL (no exact match): {urls[0]}")
    self._cache_url(godlo, urls[0]); return urls[0]   # cichy fallback: dowolny arkusz
```

Wybor = **pierwszy URL w kolejnosci strony**, bez `kolor`, `aktualnosc`,
`ukladWspolrzednych`; petla warstw (`:350`) konczy sie na pierwszej warstwie
z jakimkolwiek URL. Struktura odpowiedzi (surowy HTML `logs/01_orto_2024_featureinfo.html:231-235`
i `02_orto_entries_M-34-76-A-a-1-1.log`) — rekordy `skorDo5cm.push({...})`
z polami (nazwy DOKLADNE):

| pole | przyklady (M-34-76-A-a-1-1) |
|---|---|
| `url` | `https://opendata.geoportal.gov.pl/ortofotomapa/81422/81422_1368112_M-34-76-A-a-1-1.tif` |
| `godlo` | `M-34-76-A-a-1-1`, `7.124.07.24`, `M-34-76-A-a-1` (arkusz nadrzedny 1:10000, 1997) |
| `aktualnosc` | `2024-06-21` (ISO, sortowalny leksykalnie) |
| `aktualnoscRok` | `2024` |
| `wielkoscPiksela` | `0.25`, `0.75` (1997) |
| `ukladWspolrzednych` | `PL-1992`, `PL-2000:S7` (**inna nazwa niz w NMT**: `ukladWspolrzednychPoziomych`) |
| `kolor` | `CIR`, `RGB`, `B/W` |
| `calyArkuszWyeplnionyTrescia` | `TAK` (literowka GUGiK — tak w HTML) |
| `modulArchiwizacji` | `1:5000`, `1:2000`, `1:10000` |
| `rozmiarPlikuMB`, `zrodloDanych`, `numerZgloszeniaPracy`, `dt_pzgik` | `36`, `Zdj. cyfrowe`, `DFT.7201.014.2024`, `2025-04-14` |

Kolejnosc rekordow w HTML: warstwa 2024: `[0] CIR 81422`, `[1] RGB 81423`
(numer pracy CIR < RGB — systematycznie, tak samo 2025: 83854 CIR < 83855 RGB,
`08_orto_pick_1.log`); warstwa `Starsze`: **rosnaco po dacie** — `[0] 1997
M-34-76-A-a-1 (0.75 m)`, `[1] 2003 B/W`, ..., `[9] 2022 CIR`. Strona sortuje
rekordy JS-em (`compare()` po `aktualnosc` malejaco, `:166-183` HTML) dopiero
w przegladarce — regex widzi surowa kolejnosc. Stad: (i) B2 = CIR
(`81422_1368112`), (ii) symulacja B5 = `17_21794` (2003, B/W) zamiast
`76530_1087101` (2022-06-03 RGB), (iii) B4: godlo PL-2000 `7.124.07.24` ->
pierwsza warstwa z URL-em (2024) nie ma tego tokenu -> fallback `urls[0]` =
CIR PL-1992, cisza (poziom DEBUG), a prawdziwy `64878_364829_7.124.07.24.tif`
(2015 RGB, `Starsze` `[5]`) nigdy nie jest osiagany.

Dodatkowo `_cache_url` (`:407-410`) utrwala TEN wybor pod kluczem
`(godlo, "orto", "none", "orto")` na 7 dni — po podpieciu `MetadataCache` (N6)
zla decyzja bylaby trwala; klucz nie niesie ani koloru, ani daty.

### 2. Proponowana naprawa (D4 + D5)

Orto **konsumuje** wspolny modul klastra skorowidz
`kartograf/providers/pl/skorowidz.py` (wlasciciel: skorowidz; nazwy uzgodnione):

- `SkorowidzRecord` (frozen): `url, godlo, aktualnosc, dt_pzgik, layer, uklad
  ("1992"|"2000"|None — znormalizowany z "PL-1992"/"PL-2000:S7"), zone,
  resolution_m (orto: z `wielkoscPiksela`), full_sheet (orto: z literowki
  `calyArkuszWyeplnionyTrescia`), raw: dict` (`raw["kolor"]`).
  **Wymaganie do parsera (z surowego HTML):** uklad orto czytac z
  `ukladWspolrzednych`, NMT z `ukladWspolrzednychPoziomych`.
- `parse_skorowidz_records(text, layer)`, `select_sheet_record(records, *, godlo,
  uklad, resolution_m=None, predicate=None)` — filtr twardy `rec.godlo == godlo`
  (caly token — konczy fallback PL-2000 -> PL-1992 i dopasowanie arkusza
  nadrzednego `M-34-76-A-a-1` do `M-34-76-A-a-1-1`), `rec.uklad == uklad`,
  potem max po (`aktualnosc`, `dt_pzgik`, `url`).
- `query_skorowidz_layers(session, endpoint, layers, godlo, bbox_query, timeout,
  retries)` — wszystkie warstwy z ponowieniami; porazka warstwy = `DownloadError`
  (K3/D5, koniec `continue`).
- `SourceInfoMixin` (`_remember_source(godlo, record)`, `source_info(godlo)`)
  + `BaseProvider.source_info()` (domyslnie `None`); `DownloadManager._write_sidecar`
  dopisuje `extra["source"] = provider.source_info(godlo)` gdy `dict`.

`GugikOrtoProvider` po zmianie:

```python
class GugikOrtoProvider(SourceInfoMixin, BaseProvider):
    DEFAULT_COLOR = "RGB"
    def __init__(self, session=None, cache=None, color: str = DEFAULT_COLOR): ...

    def _get_opendata_url(self, godlo, timeout=DEFAULT_TIMEOUT) -> str:
        records = query_skorowidz_layers(self._session, self.WMS_SKOROWIDZE_ENDPOINT,
                                         self._get_validated_layers(), godlo, query_bbox, timeout)
        uklad = SheetParser(godlo).uklad
        rec = select_sheet_record(records, godlo=godlo, uklad=uklad, resolution_m=None,
                                  predicate=lambda r: r.raw.get("kolor") == self._color)
        if rec is None:
            same_sheet = [r for r in records if r.godlo == godlo and r.uklad == uklad]
            variants = ", ".join(f"{r.raw.get('kolor')} {r.aktualnosc}" for r in same_sheet)
            hint = (f" (available variants: {variants})" if same_sheet
                    else ". This area may not have orthophoto coverage in GUGiK.")
            raise NoCoverageError(f"No {self._color} orthophoto for {godlo}{hint}", godlo=godlo)
        self._remember_source(godlo, rec)      # -> source_info(godlo) = rec.to_source() | {"kolor": ...}
        self._cache_url(godlo, rec.url)        # patrz pytanie N6 nizej
        return rec.url
```

Regula: **RGB (filtr twardy, D4) + najnowsza `aktualnosc`** sposrod rekordow
z godlem jako calym tokenem i ukladem zgodnym z formatem godla; `wielkoscPiksela`
NIE jest filtrem (orto nie ma flagi rozdzielczosci, deskryptor
`resolution=None`) — trafia do `extra.source.resolution_m` (pytanie 4a).
Bez nowej flagi CLI; kwarg konstruktora `color="RGB"` jest trywialny i daje
bibliotece hak (CIR dla NDVI) bez rozszerzania `_parser.py`.

Wynik dla danych L1: `M-34-76-A-a-1-1` -> `81423_1371958_...` (2024-06-21 RGB);
symulacja "Starsze" -> `76530_1087101_...` (2022-06-03 RGB); `7.124.07.24` ->
`64878_364829_7.124.07.24.tif` (2015-04-23 RGB, PL-2000:S7) — koniec B4;
godlo PL-1992 nigdy nie dostanie rekordu PL-2000 i odwrotnie.

**Sidecar (D5, addytywnie):** `extra.source = rec.to_source()` =
`{"url","layer","godlo","aktualnosc","dt_pzgik","uklad","resolution_m","skorowidz"}`
+ orto dopisuje `"kolor": "RGB"`. Schemat `kartograf-meta/1` bez zmiany wersji
(pole dokladane; `docs/ARCHITECTURE.md` 3.2 wiersz `extra` + zdanie w wierszu
`request` "Sidecar arkusza PL nie zapisuje URL-a ani daty kampanii" — do
aktualizacji).

**Kontrakt dla wolajacych:** `download(godlo, path)` bez zmian; nowy przypadek
`NoCoverageError` (podklasa `DownloadError` — zgodne wstecz; tryb listy pod D2
pominie arkusz z `Warning:`, wycinek nie dotyczy orto); zerwana warstwa =
`DownloadError` zamiast cichego przejscia do starszej (K3). CLI: `--product orto`
pobiera RGB; komunikat `Downloading <godlo> (resolution: 1m)...`
(`download_cmd.py:756`) dla orto jest mylacy — poprawic razem (dla orto bez
"resolution"). Hydrograf nie uzywa orto (CLAUDE.md: NMT, Land Cover) — bez wplywu.
`--help` (`_parser.py:177`) — usunac zdanie o K5. Dokumentacja: `README.md:223,
289`, `docs/SCOPE.md:147-148`, `docs/PROGRESS.md:9, 203, 963, 1110-1115`, CHANGELOG.

### 3. Strategia testow offline (`tests/test_gugik_orto.py`, `tests/test_download_manager.py`)

Fixture'y dzisiejsze (`{url:"..."}` bez `push(`, `:83-86`, `:233-237`) nie sa
rekordami skorowidza — po przejsciu na `parse_skorowidz_records` przestana
dawac URL; zastapic je rekordami 1:1 z `01_orto_2024_featureinfo.html:231-235`
(CIR + RGB 2024) i 10 rekordami "Starsze" z `02_orto_entries_M-34-76-A-a-1-1.log:5-14`
(zapisanymi jako `skorDo5cm.push({...})`; `gfi/` w docs nie ma probki orto —
przy wdrozeniu skopiowac surowy HTML do `tests/fixtures/` albo inline).
Testy failing-before / passing-after:

- `test_picks_rgb_not_first_record`: warstwa 2024 [CIR, RGB] -> URL `81423_1371958`
  (dzis `81422_1368112`); `source_info` zawiera `kolor == "RGB"`, `aktualnosc == "2024-06-21"`, `layer == "SkorowidzeOrtofotomapy2024"`.
- `test_starsze_picks_newest_not_oldest`: warstwy 2026/2025/2024 puste, Starsze
  10 rekordow -> `76530_1087101` (dzis `17_21794`, 2003 B/W).
- `test_pl2000_godlo_gets_pl2000_record`: `7.124.07.24` -> `64878_364829_7.124.07.24.tif`
  (dzis CIR PL-1992 z 2024).
- `test_pl1992_godlo_never_takes_pl2000_or_parent_sheet`: `M-34-76-A-a-1-1` nie
  dostaje `7.124.07.24` ani `M-34-76-A-a-1` (1997) — `select_sheet_record` token.
- `test_only_cir_and_bw_raises_nocoverage_with_variants`: rekordy tylko CIR/B-W ->
  `NoCoverageError`, komunikat wymienia `CIR 2024-06-21`.
- `test_newer_layer_failure_is_error_not_older_campaign` (K3 dla orto): warstwa
  2025 rzuca `ConnectionError`, 2024 ma RGB -> `DownloadError` (dzis: URL z 2024).
- `test_download_manager_writes_extra_source` (manager): provider-atrapa z
  `source_info()` -> sidecar `extra.source.url/kolor`; provider bez metody (Mock) ->
  brak klucza.
- Istniejace `test_get_opendata_url_success/_not_found/_all_layers_transport_error/
  _tries_all_layers` — dostosowac fixture'y do formatu `push(`; asercja
  "unavailable ... all 3 layer queries failed" zalezy od semantyki
  `query_skorowidz_layers` (klaster skorowidz) — do uzgodnienia w tym samym PR.

### 4. Ryzyka i pozostale pytania projektowe

- **(a) `wielkoscPiksela` jako filtr dla orto?** Opcje: (1) brak filtra, najnowsza
  RGB, piksel w `extra.source.resolution_m` — rekomendacja (produkt nie ma flagi
  rozdzielczosci; wszystkie rekordy L1 dla godla 1:5000 maja 0.25; miejski
  0.05/0.10 m, gdyby sie pojawil pod tym samym godlem, jest nowszy i lepszy);
  (2) twardo 0.25 ("Standard Resolution" z opisu produktu) — odrzuciloby
  nowsze, drobniejsze zdjecia i nie ma dowodu, ze GUGiK publikuje je pod
  godlami 1:5000; (3) preferencja 0.25 z fallbackiem — zlozonosc bez potrzeby.
- **(b) Arkusz bez zadnego RGB** (tylko B/W 1997-2003 albo tylko CIR) —
  `NoCoverageError` wg D4 (rekomendacja; komunikat wymienia dostepne warianty),
  alternatywa: fallback na B/W z `Warning:` — sprzeczna z D4 ("filtr twardy").
- **(c) Cache URL (N6, wlasciciel: skorowidz/CLI):** klucz `url_cache(godlo,
  resolution, vertical_crs, product)` nie niesie koloru ani daty; po podpieciu
  cache orto powinno albo (1) trzymac zserializowany `to_source()` (JSON w
  kolumnie `url`, klucz `resolution="RGB"` jako slot wariantu) — rekomendacja,
  bo `extra.source` musi byc dostepne takze przy trafieniu w cache; albo (2)
  nie cache'owac orto wcale (4 zapytania GetFeatureInfo per arkusz sa tanie).
  Wymaga decyzji wlasciciela N6.
- **(d) Kwarg `color`** — czy w ogole (D4 mowi "bez nowej flagi CLI, chyba ze
  trywialna"): rekomendacja: kwarg biblioteczny tak (1 linia), flaga CLI nie.

### 5. Szacunek zakresu

`kartograf/providers/pl/gugik_orto.py` (`_get_opendata_url` ~50 linii ->
~35; `OPENDATA_URL_PATTERN` do usuniecia; import `skorowidz`), zaleznosc od
`skorowidz.py`, `base.py::source_info`, `manager.py::_write_sidecar`,
`transport/http.py::make_gugik_session` (klaster skorowidz), `cli/_parser.py:177`,
`cli/download_cmd.py:756` (komunikat), testy orto + manager, `ARCHITECTURE.md`
3.2, README/SCOPE/PROGRESS/CHANGELOG. Kontrakt publiczny: addytywny (`extra.source`,
`NoCoverageError`, kwarg `color`).

---

## N7 — LAZ: "No LAZ tiles found" przy awarii sieci; czesciowa awaria = wynik niepelny z kodem 0 (NISKI)

### 1. Przyczyna potwierdzona na kodzie

- `gugik_laz.py:383-388`: `except requests.RequestException: logger.warning(...);
  return` — generator warstwy konczy sie cicho, rocznik znika z wyniku;
  `:390-394` `ET.ParseError` -> tak samo; `:396-399` `ExceptionReport` -> `return`
  ("skip quietly") — takze dla jawnie podanego `--year`.
- `gugik_laz.py:269-277` (`_get_available_years`): awaria GetCapabilities ->
  `FALLBACK_YEARS` (`:159-162`), lista konczy sie na 2025, a usluga ma 2026
  (L1 BUG-L1-5) — rocznik 2026 nie jest odpytywany bez zadnego bledu.
- `discover_tiles` (`:339-351`) nie wie, ile roczników odpowiedzialo; zwraca
  to, co zebrano.
- `cli/download_cmd.py:1318-1326`: `DownloadError` -> `Error:` kod 1 (dobrze),
  ale provider go nie rzuca; pusty wynik -> `"Error: No LAZ tiles found for the
  given area."` — jedyny komunikat takze przy 9 z 9 zerwanych zapytaniach
  (B3b: stderr = 9 x `WFS GetFeature failed ...` + ten blad). Dowod czesciowej
  awarii z kodem 0: `B3_laz_bbox.err` = `WFS GetFeature failed for
  SkorowidzDanychPomiarowychLIDAR2026: RemoteDisconnected`, `B3_laz_bbox.meta`
  exit 0.

Hipoteza backlogu potwierdzona; dodatkowo: `FALLBACK_YEARS` jest cicha
degradacja tego samego rodzaju (nie tylko GetFeature).

### 2. Proponowana naprawa

Zasada (N7 + D5 "zerwane zapytanie = blad z ponowieniami, nie cicha degradacja"):
**discovery jest wszystko-albo-nic**: kazde zapytanie WFS (GetCapabilities,
kazda strona GetFeature kazdego rocznika) ma ponowienia; porazka po
ponowieniach = `DownloadError` z nazwa rocznika; `discover_tiles` nie zwraca
wyniku czesciowego.

- Sesja: `self._session = session or make_gugik_session()` (fabryka klastra
  skorowidz w `transport/http.py`: `HTTPAdapter(max_retries=Retry(total=3,
  backoff_factor=1, status_forcelist=(500,502,503,504), allowed_methods=("GET",)))`
  — `RemoteDisconnected`/reset to bledy odczytu, ponawiane dla GET). Ta sama
  sesja do GetCapabilities (dzis dedykowana `requests.Session()` w
  `_fetch_available_years:234` — tez do podmiany; test patchuje
  `kartograf.providers.pl.gugik_laz.requests.Session` — do zmiany na fabryke).
- `_query_layer`: `except requests.RequestException as e: raise DownloadError(
  f"WFS GetFeature dla rocznika {year} ({layer}) nie powiodl sie po ponowieniach:
  {e} — wynik bylby niepelny, ponow pobranie")`; `ET.ParseError` -> `DownloadError`
  ("odpowiedz WFS nieczytelna"); `ExceptionReport` -> `DownloadError` z trescia
  `ows:ExceptionText` (dla `--year` = "rocznik nie istnieje w usludze <vcrs>";
  dla roczników z GetCapabilities = niespojnosc serwera — tez blad, nie cisza).
- `_get_available_years`: bez fallbacku — awaria GetCapabilities po ponowieniach
  = `DownloadError`; `FALLBACK_YEARS` **usunac** (martwa lista, juz nieaktualna;
  `discover_tiles` i tak nie dziala offline); in-memory cache lat zostaje.
- CLI `_cmd_download_laz`: `except (ValueError, DownloadError)` bez zmian (kod 1,
  `Error: <tresc>`); `"No LAZ tiles found"` zostaje TYLKO dla prawdziwie pustego
  wyniku (wszystkie roczniki odpowiedzialy) — dopisac podpowiedz "(sprawdz
  obszar/--year/--vertical-crs; wszystkie roczniki odpowiedzialy)". Ostrzezenia
  ponowien bez pelnego URL-a (dzis ~500 znakow na linie, L1 "Drobne").
- Straz osi z K1 (`DownloadError`) wpisuje sie w te sama regule.

Kontrakt: `discover_tiles` **rzuca `DownloadError`** przy awarii WFS (dzis: cicho
`[]`/wynik czesciowy) — zmiana zachowania publicznej klasy (`kartograf.GugikLazProvider`,
docstring "Raises" do uzupelnienia); `FALLBACK_YEARS` znika z API klasy (CHANGELOG,
"Breaking"). CLI: kod 1 + komunikat sieciowy zamiast "No LAZ tiles found";
brak wyniku czesciowego z kodem 0. Sidecar bez zmian.

### 3. Strategia testow offline (`tests/test_gugik_laz.py`, `tests/test_cli.py`)

- `test_network_error_returns_empty` (`:379-384`) -> **usunac** (pinuje blad),
  zastapic `test_network_error_raises_download_error` (`pytest.raises(DownloadError,
  match="2024")`).
- `test_exception_report_skipped` (`:374-377`) -> `..._raises_with_server_text`
  (`match="Unknown type name"`).
- Nowy `test_partial_year_failure_returns_nothing`: `side_effect=[odp. 2024 z kaflem,
  ConnectionError dla 2023]`, `_available_years = [2024, 2023]` -> `DownloadError`,
  zaden kafel (dzis: 1 kafel, brak bledu).
- `TestAvailableYears`: testy fallbacku (`test_fallback_years_distinct_per_crs`
  i test "GetCapabilities failed -> fallback") -> usunac; nowy: awaria
  GetCapabilities -> `DownloadError`; `test_fetch_years_descending` zostaje
  (patch fabryki sesji zamiast `requests.Session`).
- Ponowienia: sesja-atrapa z licznikiem wywolan nie pokaze `Retry` urllib3
  (adapter zyje w prawdziwej sesji) — test fabryki `make_gugik_session()` po
  stronie klastra skorowidz (`adapter.max_retries.total == 3`); w LAZ tylko
  "porazka -> wyjatek".
- `tests/test_cli.py`: `test_laz_no_tiles_found_errors` (`:2605-2622`) zostaje
  (pusty wynik nadal kod 1); nowy `test_laz_wfs_failure_reports_network_error`:
  `discover_tiles.side_effect = DownloadError("WFS GetFeature ...")` -> kod 1,
  stderr zawiera "WFS", nie zawiera "No LAZ tiles".

### 4. Ryzyka i pozostale pytania projektowe

- **Odpornosc vs. scislosc.** Przy ~50 % zrywanych polaczen (stan GUGiK 2026-09-29)
  i 3 probach P(porazka zapytania) ~ 0,125; discovery bez `--year` to 1 + ~9
  zapytan -> P(co najmniej jedna porazka) ~ 1 - 0,875^10 ~ 74 % — komenda
  konczy sie kodem 1 czesciej niz sukcesem w taki dzien. Opcje: (1) `Retry(total=3)`
  z fabryki (spojnie z NMT) i akceptacja kodu 1 z jasnym "ponow" — rekomendacja
  (zla polowa wyniku bez komunikatu jest gorsza; czesc zerwan byla efektem 9
  agentow z jednego IP); (2) wieksza liczba ponowien tylko dla WFS (`total=5`,
  `backoff_factor=1` -> do ~30 s) — rozwazyc, jesli test na zywo po naprawie
  nadal daje kod 1; (3) zapytanie zbiorcze wielu roczników w jednym GetFeature
  (WFS 2.0 `TYPENAMES` z lista) — mniej zapytan, ale niezweryfikowane na
  tym serwerze i zmienia parsowanie; nie teraz.
- **Podwojne ponowienia pobran kafli:** `_download_with_retry` (3 proby) na
  sesji z `Retry(total=3)` daje do 3 x 4 prob dla kafla 40 MB. Opcje: (1)
  zostawic (rzadkie, tylko przy awarii) — rekomendacja na te fale; (2)
  przepiac pobranie kafli na `transport/http.py::download_to` (usuwa
  `_download_with_retry`/`_make_request`/`_save_response`, ~60 linii) — czystsze,
  ale poza N7; do rozwazenia przy wdrozeniu, jesli klaster skorowidz robi to
  samo dla NMT.
- **`ExceptionReport` jako blad** takze dla roczników z GetCapabilities — ryzyko
  falszywych bledow przy chwilowej niespojnosci serwera; alternatywa (warning +
  pominiecie tego rocznika) jest dokladnie cicha degradacja N7. Rekomendacja: blad.

### 5. Szacunek zakresu

`kartograf/providers/pl/gugik_laz.py` (~40 linii: sesja, `_get_available_years`,
`_query_layer`, usuniecie `FALLBACK_YEARS`), `kartograf/cli/download_cmd.py:1316-1326`
(komunikaty), `tests/test_gugik_laz.py` (2 usuniete, 3-4 nowe, patch sesji),
`tests/test_cli.py` (1 nowy), CHANGELOG (Breaking: `FALLBACK_YEARS`, `discover_tiles`
rzuca). Zaleznosc: `make_gugik_session()` z klastra skorowidz.

---

## Kolizje miedzy klastrami — pliki `kartograf/`, ktore dotknie naprawa tego klastra

| plik | zakres zmian tego klastra | inny klaster w tym pliku |
|---|---|---|
| `kartograf/providers/pl/gugik_laz.py` | K1 (BBOX, envelope, straz), N7 (sesja, wyjatki, `FALLBACK_YEARS`) | — |
| `kartograf/providers/pl/gugik_orto.py` | K5: `_get_opendata_url` na `skorowidz.py`, `SourceInfoMixin`, kwarg `color`, `NoCoverageError` | K4 (skorowidz) — orto jest wymieniony w K4; uzgodnione: wlasciciel `gugik_orto.py` = ten klaster, parser/petla/mixin = skorowidz |
| `kartograf/cli/_parser.py:174-177` | usuniecie ostrzezen K1/K5 z pomocy `--product` | CLI (S2/S3 nie dotykaja `--product`) |
| `kartograf/cli/download_cmd.py` | `_cmd_download_laz` (`:1316-1326` komunikaty), `:756` komunikat orto | CLI: `_download_godlo_list`, `_dispatch_area`, `_country_bbox` (S2/S3, N4) — inne funkcje, ten sam plik: scalac w jednym PR albo sekwencyjnie |
| `kartograf/providers/pl/skorowidz.py` (nowy) | konsument | **wlasciciel: skorowidz** |
| `kartograf/providers/base.py` (`source_info`) | konsument | **wlasciciel: skorowidz** |
| `kartograf/download/manager.py::_write_sidecar` | konsument (`extra.source`) | **wlasciciel: skorowidz** (D5); CLI (N4 skip/sidecar) |
| `kartograf/transport/http.py::make_gugik_session` | konsument (LAZ) | **wlasciciel: skorowidz** (S1) |
| `kartograf/cache/metadata.py` | pytanie 4c (klucz cache orto) | N6 (skorowidz/CLI) |

Docs dotkniete: `README.md`, `CLAUDE.md`, `docs/PRD.md`, `docs/SCOPE.md`,
`docs/PROGRESS.md`, `docs/ARCHITECTURE.md` (3.2 `extra`, tabela ADR-021),
`docs/DECISIONS.md` (ADR-021 dopisek o naprawie), `docs/IMPLEMENTATION_PROMPT.md:283`,
`docs/CHANGELOG.md`.
