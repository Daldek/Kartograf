# Raport fali naprawczej po finalnym review (FIX_BASE fa1f771)

**Status:** DONE_WITH_CONCERNS (uwagi w sekcji "Watpliwosci"; zadna nie blokuje)
**Implementer:** Opus 5.5, praca bezposrednio na `develop`, nic nie pushowane.

## Commity (fa1f771..bbd1cd4)

| SHA | Temat | Pozycja |
|---|---|---|
| 63b612e | test(cli): --force i --workers toru wycinka PL bronione testem CLI | 1 (I-1 + m-1) |
| 5e5763c | fix(gugik): raport wyjatku OGC w odpowiedzi 2xx skorowidza to blad warstwy, nie brak pokrycia | 2 (I-2) |
| 2faf0b5 | fix(download): uklad czeski bboxa wycinka PL niezalezny od wielkosci liter | 3 (m-2) |
| 7e0daa6 | docs(api): last_result i wyjatki DownloadManager, NoCoverageError w GugikProvider.download | 4 (m-6 + m-7) |
| 27701eb | docs: domyslne komendy testow offline (-m "not live") w CLAUDE.md i README | 5 (m-8) |
| bbd1cd4 | docs(architecture): precyzja 4.3 (...) i zaleznosc od bbox_to_crs CZ | 6 (m-9 + m-10) |

Commit 2faf0b5 powstal przez `--amend` pierwszej wersji (065fade, lokalna, nigdy
niepushowana) — powod w pozycji 3 (mutacja, ktora przezyla). Stopki:
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Zaden plik z `.superpowers/`
nie jest w commitach.

## Wazna uwaga procesowa: nieswiezy bytecode przy mutacjach

Pierwszy przebieg mutacji I-2/M2 (przeniesienie bloku strazy przed sprawdzenie URL)
dal po `git checkout` nadal `1 failed`. Przyczyna: mutacja przestawiajaca blok NIE
zmienia rozmiaru pliku, a zapis mutacji i przywrocenie zmiescily sie w tej samej
sekundzie mtime — Python uznal `.pyc` skompilowany z mutacji za aktualny (walidacja
pyc = mtime w sekundach + rozmiar) i wykonal zmutowany kod po przywroceniu.
Kolejny przebieg (inny rozmiar pliku) juz przeszedl. Wszystkie mutacje z tego raportu
POWTORZYLEM skryptem, ktory kompiluje bytecode od nowa w kazdym przebiegu
(`PYTHONPYCACHEPREFIX=$(mktemp -d)`), i przed brama koncowa usunalem in-tree
`__pycache__`. Rekomendacja dla re-reviewerow powtarzajacych mutacje: to samo
(mutacje zmieniajace rozmiar pliku nie sa narazone, przestawiajace/podmieniajace
znak-za-znak — sa).

Skrypt (scratchpad, poza repo): mutacja -> pytest ze swiezym pycache -> `git checkout --
<plik>` -> pytest ze swiezym pycache -> `git status --short` (musi byc pusty; skrypt
przerywa, gdy drzewo jest brudne PRZED mutacja).

---

## 1. I-1 + m-1 — `--force` i `--workers` toru wycinka PL

**Kod bez zmian** (`kartograf/cli/download_cmd.py:1035-1036`, `cutout.py:579` jak w briefie).

**Test:** `tests/test_pl_cutout.py:861`
`TestDownloadPlBboxCutout::test_force_rebuilds_existing_cutout_and_passes_workers` —
harness `_run`/`_pl_args`; plik wyniku (`.../nmt/pl_1992_1m_evrf2007/bbox/530010_382010_530190_382090.tif`)
z dummy trescia `b"II*\x00stary wycinek"`, CLI z `_pl_args(tmp_path, force=True, workers=3)`.
Asercje: `rc == 0`; tresc != dummy; plik otwiera rasterio i ma same `100.0` (dwa plaskie
arkusze pokrywaja bbox — wartosc literalna, nie wyliczona kodem); 
`manager.download_sheets.call_args.kwargs["skip_existing"] is False`;
`self.dm.call_args.kwargs["max_workers"] == 3`.

Na obecnym (poprawnym) kodzie test przechodzi — to straznik wiazania; jego "RED" to mutacje:

| Mutacja (po commicie 63b612e) | Wynik z mutacja | Po `git checkout` |
|---|---|---|
| (a) CLI `force=args.force,` -> `force=False,` | `E AssertionError: --force nie przebudowal wycinka` / `assert b'II*\x00stary wycinek' != b'II*\x00stary wycinek'` — 1 failed | 1 passed, status czysty |
| (b) CLI `max_workers=getattr(args, "workers", 4),` -> `max_workers=1,` | `E assert 1 == 3` — 1 failed | 1 passed, status czysty |
| (c) biblioteka `skip_existing=not force` -> `skip_existing=True` | `E assert True is False` — 1 failed | 1 passed, status czysty |

Komenda: `PYTHONPYCACHEPREFIX=$(mktemp -d) .venv/bin/python -m pytest -q -p no:cacheprovider "tests/test_pl_cutout.py::TestDownloadPlBboxCutout::test_force_rebuilds_existing_cutout_and_passes_workers"`.

## 2. I-2 — raport wyjatku OGC w odpowiedzi 2xx skorowidza

**Zmiana** (`kartograf/providers/pl/gugik.py`):
- `:36-52` — `_OGC_EXCEPTION_MARKERS = ("ServiceException", "ExceptionReport")`,
  `_OGC_EXCEPTION_TEXT` (regex tresci `<ServiceException ...>` / `<ows:ExceptionText>`;
  `\b` odrzuca korzen `<ServiceExceptionReport>`), `_ogc_exception_excerpt(text, 200)` —
  komunikat pierwszego elementu wyjatku, whitespace zwiniety do jednej linii, max 200
  znakow; fallback: poczatek body.
- `:574` `text = response.text` (jedno odczytanie; regex URL bez zmian semantyki).
- `:601-617` — po bloku `if urls: ... return` (bez zmian): brak URL + znacznik w tresci ->
  `transport_errors += 1`, `last_error = DownloadError(f"warstwa {layer}: raport wyjatku
  OGC w odpowiedzi HTTP {status}: {wyciag}", godlo=godlo)`, `logger.warning(...)`,
  `continue`. Galezie po petli bez zmian ("unavailable" / "niepewny"); brak kontroli
  `Content-Type` i kontroli pozytywnej (ruling I-2).
- `:480-492` — docstring `_get_opendata_url` (`Raises`): raport wyjatku OGC nie jest
  odpowiedzia, liczy sie jak nieudane zapytanie warstwy.

**NMPT:** `GugikNmptProvider._get_opendata_url is GugikProvider._get_opendata_url` ->
True, `download` tez; NMPT nie nadpisuje zadnej metody poza `name`/`__init__`
(sprawdzone na zywym kodzie) — straz dziala tam bez zmian. `GugikOrtoProvider` ma
wlasny `_get_opendata_url`, ale nigdy nie rzuca `NoCoverageError` (jedyne
`raise NoCoverageError` w repo: `gugik.py:632`), wiec klasa bledu I-2 go nie dotyczy.

**Testy** (`tests/test_gugik_provider.py`):
- `:459` `_OGC_EXCEPTION_REPORT` — raport w ksztalcie MapServera WMS 1.3.0 z komunikatem
  "Invalid layer(s) given in the LAYERS parameter" (tresc, ktora GUGiK zwracal naprawde
  na GetFeatureInfo o nieaktualna warstwe — CHANGELOG 0.7.0; kodu HTTP i Content-Type
  realnej odpowiedzi nikt nie zapisal — komentarz w fixturze); `:477` fixture 200.
- (a) `:574` `test_ogc_exception_report_on_all_layers_is_service_failure` — 3 warstwy
  z raportem -> `DownloadError` z "unavailable", `not isinstance(NoCoverageError)`,
  "all 3 layer queries failed", w komunikacie "L3" i "Invalid layer(s)", 3 zapytania,
  WARNING z "L1".
- (b) `:605` `test_ogc_exception_on_one_layer_is_uncertain_not_no_coverage` — raport na
  L1, czysta pusta odpowiedz (istniejaca fixture) na L2/L3 -> "niepewny", nie
  `NoCoverageError`.
- (c) istniejacy `test_get_opendata_url_not_found` — bez zmian, przechodzi.
- (d, dodatkowy) `:629` `test_url_in_response_wins_over_exception_marker` — broni rulingu
  "URL zawsze wygrywa" (odpowiedz z URL + `<!-- ServiceExceptionReport -->`).

**RED** (przed implementacja; `pytest tests/test_gugik_provider.py -k "ogc_exception or url_in_response_wins or not_found"`):
```
E   kartograf.exceptions.NoCoverageError: No NMT 1m data available for N-34-130-D-d-2-4 ...
E   AssertionError: Regex pattern did not match.  Expected regex: 'unavailable'
E   AssertionError: assert not True  (+ where True = isinstance(NoCoverageError(...), NoCoverageError))
FAILED ...::test_ogc_exception_report_on_all_layers_is_service_failure
FAILED ...::test_ogc_exception_on_one_layer_is_uncertain_not_no_coverage
================== 2 failed, 2 passed, 43 deselected ==================
```
**GREEN:** `tests/test_gugik_provider.py` — 47 passed.

**Mutacje** (po commicie 5e5763c, swiezy bytecode, ten sam `-k`):

| Mutacja | Wynik z mutacja | Po przywroceniu |
|---|---|---|
| M1 (brief) usun straz: `if any(...)` -> `if False:` | FAILED (a) i (b): `2 failed, 2 passed` (NoCoverageError; "Regex pattern did not match"; "assert not True") | 4 passed, status czysty |
| M2 straz PRZED sprawdzeniem URL (skrypt przenoszacy blok) | FAILED (d): `DownloadError: ... all 1 layer queries failed (last error: warstwa L1: ...url:"https://opendata...` — `1 failed, 3 passed` | 4 passed, status czysty (powtorzone ze swiezym bytecode — patrz uwaga procesowa) |
| M3 naiwny wyciag `_ogc_exception_excerpt(text)` -> `text.strip()[:200]` | FAILED (a): komunikat konczy sie `...xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocat)` — brak "Invalid layer(s)" | 4 passed, status czysty |
| M4 bez `logger.warning` w strazy | FAILED (a): `assert 'L1' in ''` | 4 passed, status czysty |

M3 pokazuje, dlaczego wyciag nie jest "pierwszymi 200 znakami po strip()" z przykladu
briefu (to bylo "np."): w raporcie MapServera to wylacznie deklaracja XML i przestrzenie
nazw, bez komunikatu.

**Dokumentacja:** `docs/CHANGELOG.md:639` (`### Fixed`, osobny wpis: przyczyna, skutek
pod R5, nowe zachowanie, granica "strona bledu z 200 bez znacznikow OGC nadal = brak
arkusza (do sprawdzenia na zywych danych)"); `docs/ARCHITECTURE.md:483` (4.3 krok 4:
straz + URL wygrywa + granica -> checklista live).

## 3. m-2 — uklad czeski bboxa wycinka niezalezny od wielkosci liter

**Zmiana** (`kartograf/download/cutout.py:116-135`): `crs = bbox.crs.strip().upper()`
dla obu warunkow; galaz 2180 zwraca `bbox._replace(crs="EPSG:2180")` (etykieta
kanoniczna — dokladnie to, co dotad dawala transformacja tozsamosciowa dla
`"epsg:2180"`); galaz czeska: `bbox_to_crs(bbox, "EPSG:2180")` jak dotad.
`providers/cuzk/*` nietkniete.

**Pomiar (warunek sensownosci, prosba briefu):** bbox `(-455000, -1117000, -454000,
-1116000)` EPSG:5514 (Cieszyn, strona PL). Przypieta sciezka vs niepinowana
(`core/geometry._transform_bbox`): **max |roznica| = 1,0624 m** (`max_y`; `min_x`
0,0024 m; `min_y`, `max_x` identyczne). Przyczyna zmierzona punktowo: domyslny
transformer pyproj wybiera operacje PER PUNKT — w rogach SW/SE daje to samo co operacja
przypieta (0,0 m), w NW/NE i w srodku ~1,05 m w y. To realnie inna operacja
(hazard ADR-024), nie tylko efekt probkowania krawedzi.

**Testy** (`tests/test_pl_cutout.py`):
- `:291` `test_czech_crs_label_leaves_krovak_by_pinned_operation[epsg:5514 | " EPSG:5514 "]`
  — warunek sensownosci `shift > 0.01` (niepinowana vs przypieta), potem
  `cut.bbox_2180 == ` wynik dla `"EPSG:5514"`.
- `:326` `test_lowercase_2180_label_is_canonical` — `"epsg:2180"` -> `bbox_2180 ==
  BBox(..., "EPSG:2180")` i nazwa pliku.

**RED** (przed zmiana): oba parametry
```
E   AssertionError: assert BBox(min_x=46...s='EPSG:2180') == BBox(min_x=46...s='EPSG:2180')
E     Differing attributes: ['min_x', 'max_y']
E       min_x: 465068.15316368546 != 465068.15554981766...
```
**GREEN:** `tests/test_pl_cutout.py` — 64 passed.

**Mutacje** (po commicie 2faf0b5, swiezy bytecode,
`-k "czech_crs_label or lowercase_2180 or test_target_2180_no_pinned or wgs84_bbox_normalized"`):

| Mutacja | Wynik z mutacja | Po przywroceniu |
|---|---|---|
| (brief) doslowne porownanie: `crs = bbox.crs` | FAILED oba `[epsg:5514]`, `[ EPSG:5514 ]` — `2 failed, 3 passed` | 5 passed, status czysty |
| bez `.strip()`: `crs = bbox.crs.upper()` | FAILED `[ EPSG:5514 ]` — `1 failed, 4 passed` | 5 passed, status czysty |
| galaz 2180: `return bbox._replace(crs=crs)` -> `return bbox` | FAILED `test_lowercase_2180_label_is_canonical` — `1 failed, 4 passed` | 5 passed, status czysty |

**Mutacja, ktora przezyla (znalezisko, naprawione):** pierwsza wersja (065fade)
przekazywala do `bbox_to_crs` bbox ze znormalizowana etykieta. Mutacja "galaz CZ
z nieznormalizowana etykieta" przechodzila 4/4 — pyproj sam akceptuje `"epsg:5514"`,
`" EPSG:5514 "`, `"\tepsg:5514\n"`, `"Epsg:5514"` (wynik identyczny, sprawdzone), wiec
`_replace` w galezi czeskiej byl martwym kodem. Usuniety (commit poprawiony `--amend`
do 2faf0b5); natomiast `_replace` w galezi 2180 ma skutek obserwowalny w publicznym
`PlCutout` — dostal test (`:326`) i mutacja go zabija.

**Dokumentacja:** `docs/CHANGELOG.md:650` (`### Fixed`, z pomiarem 1,06 m i informacja,
ze CLI nie bylo dotkniete — `--bbox-crs` ma `choices` wielkimi literami).

## 4. m-6 + m-7 — docstringi publicznego API

Kazde twierdzenie sprawdzone na zywym kodzie (skrypt z fake providerem, zero sieci):
`download_sheets` ustawia `last_result` (DownloadResult); `download_hierarchy` tez;
`download_sheet` 1:10000 -> None; `download_sheet` PL-2000 -> None (reset z uprzednio
ustawionego wyniku); `download_sheet` 1:25000 (rozwiniecie) -> DownloadResult, 4 arkusze;
`download_bbox` -> `last_result` nietkniety (ten sam obiekt). Zachowanie wyjatkow —
patrz pozycja 6(a).

`kartograf/download/manager.py`:
- `:76-80` `DownloadResult` Notes — "Populated by `download_hierarchy` and
  `download_sheets` (and so by `download_sheet` when it expands a coarser PL-1992 godlo)".
- `:124-131` atrybut klasy `last_result` — reset w `download_sheet`/`download_hierarchy`/
  `download_sheets`; ustawiaja `download_hierarchy` i `download_sheets`; pojedynczy
  arkusz 1:10000/PL-2000 -> None; `download_bbox` go nie dotyka.
- `:302-307` `download_sheet` Notes — ustawia go tylko rozwiniecie do 1:10000.
- `:374-385` `download_hierarchy` Notes — j.w. + doprecyzowanie "Per-sheet failures do
  not raise": dotyczy `DownloadError` (w tym `NoCoverageError`); inny wyjatek (np.
  `OSError` zapisu) sekwencyjnie przerywa pobieranie, w puli watkow trafia do `failed`.
- `:458-464` `download_sheets` — usuniete "without raising" z pierwszej linii i "never
  raise" doprecyzowane jak wyzej (odsylacz do Notes `download_hierarchy`).

`kartograf/providers/pl/gugik.py:426-440` — `GugikProvider.download`, `Raises`:
`NoCoverageError` (podklasa `DownloadError`; wszystkie warstwy odpowiedzialy bez arkusza;
raport wyjatku OGC to nie odpowiedz; manager -> `no_coverage`, wycinek -> nodata,
ADR-027) i `DownloadError` (lookup: wszystkie zapytania padly / czesc padla + reszta bez
arkusza; ASC po wszystkich probach — sprawdzone w `_download_with_retry`).

`kartograf/download/cutout.py:547-553` — docstring `run_pl_cutout`: "kazda inna porazka
arkusza -> DownloadError" bylo nieprawdziwe dla `OSError` przy `max_workers=1`
(zmierzone, pozycja 6a) — doprecyzowane. **To rozszerzenie poza litera briefu** (patrz
Watpliwosci), zrobione, zeby docstring nie przeczyl poprawionej ARCHITECTURE 4.3.

## 5. m-8 — komendy testow

- `CLAUDE.md:126-138` — zdanie, dlaczego flaga jest jawna (`pyproject.toml`: `addopts =
  "-v --tb=short"`, bez `-m` — sprawdzone); `# Testy (offline)` z `-v -m "not live"`;
  `# Testy z pokryciem (offline)` z `-m "not live"`; osobna linia `.venv/bin/python -m
  pytest tests/ -m live   # 8 testow sieciowych (WMS GUGiK) — tylko swiadomie`.
- `README.md:355-361` — to samo w stylu README (`pytest ...`), komentarz "Uruchom
  wszystkie testy" -> "Uruchom testy (offline)" (z `-m "not live"` nie sa juz "wszystkie").
- **N zmierzone:** `.venv/bin/python -m pytest tests/ -m live --collect-only -q` ->
  `8/1869 tests collected (1861 deselected)`. Wszystkie 8 to
  `tests/test_pl2000_verification.py::TestPL2000LiveWMS::test_wms_query_at_bbox_center[...]`
  (zapytania WMS do GUGiK; definicja markera w `pyproject.toml` tez mowi "GUGiK WMS"),
  dlatego napisalem "(WMS GUGiK)", a nie "(GUGiK/CUZK)" z przykladu briefu.
- Komenda z pokryciem uruchomiona doslownie: `1861 passed, 8 deselected`, **Total
  coverage: 92.92%** (`htmlcov/` i `.coverage` sa w `.gitignore`).
- Niczego innego z sekcji nie usunieto.

## 6. m-9 + m-10 — precyzja `docs/ARCHITECTURE.md`

**(a) wstep 4.3 (`:401-416`)** — zamiast "zamienia KAZDY wyjatek przygotowania,
selekcji...": CLI lapie z `prepare_pl_cutout` `TransformError` (z remedium, gdy jest)
i `ValidationError`, z `select_pl_cutout_sheets` `ValidationError`, wokol
`run_pl_cutout` kazdy `Exception`; inny wyjatek przygotowania/selekcji trafia do bariery
`main()` (`cli/commands.py:95-105`): `KartografError` -> `Error: <komunikat>`, inny ->
`Error: <Typ>: <komunikat>` + podpowiedz `KARTOGRAF_DEBUG=1` (z nia — traceback); kod 1,
ale petla krajow przerwana. Sprawdzone: miedzy `_dispatch_area` a `main()` nie ma
innych `except` (`_cmd_download_bbox`/`_cmd_download_geometry` -> `_dispatch_area` bez
`try`); zla `--scale` (brak `choices`) daje `ValidationError` z selekcji (sprawdzone
dla `1:3`, `abc`, `1:2000`, `1:5000`), wiec "przy wejsciu zwalidowanym przez CLI nie
wystepuje". Eksperyment na `main()` (patch `prepare_pl_cutout` -> `RuntimeError`,
bbox przygraniczny `--country auto`, `_run_cz` -> 0): `rc = 1`, CZ wolane,
stderr `Error: RuntimeError: boom` + `Ustaw KARTOGRAF_DEBUG=1...` — czesciowy sukces
przepada, jak opisano.

**(a) krok 4 (`:470-481`, `:498`)** — "Porazka arkusza nie przerywa listy" -> dotyczy
rodziny `DownloadError`; inny wyjatek przy `max_workers=1` wylatuje z `download_sheets`
i `run_pl_cutout` bez zmian (przerywa liste), w puli watkow (`max_workers > 1`, CLI
domyslnie 4 — sprawdzone w `_parser.py`) trafia do `failed` bez `no_coverage` ->
`DownloadError`; w CLI oba warianty lapie `except Exception`. Punkt listy "kazda inna
porazka arkusza" -> "kazdy inny arkusz w `failed`". Eksperyment (fake provider rzucajacy
`OSError(28, ...)`, 2 arkusze):
```
download_sheets workers=1: OSError: [Errno 28] No space left on device (symulacja); last_result=None
run_pl_cutout workers=1: OSError: [Errno 28] No space left on device (symulacja)
download_sheets workers=2: brak wyjatku; failed=['N-34-130-D-d-2-4', 'N-34-130-D-d-2-3'] no_coverage=[]
run_pl_cutout workers=2: DownloadError: 2 z 2 arkuszy nie pobrano (blad pobrania, nie brak danych): ...
```

**(b) "Nieudana budowa a poprzedni wynik" (`:620-630`)** — cytat E2E (e) zastapiony
odwolaniem do `tests/test_pl_cutout.py::TestBuildPlCutout::test_failed_build_keeps_previous_result`
(przerwany warp w `build_pl_cutout`) i
`tests/test_transform_raster.py::TestWarpToGrid::test_failed_warp_keeps_previous_destination`
(sam `warp_to_grid`) — pelne nazwy sprawdzone grepem. Sciezka samego cropu (EPSG:2180)
nie ma osobnego testu "poprzedni wynik przezywa" — nie twierdze, ze ma.

**(c)** `:287` (3.3 pkt 3) i `:580-586` (4.3 krok 6): "< 0,5 px" -> "do 0,5 px"; w kroku 6
wzor `max(1, round(rozpietosc / piksel))` z wyjasnieniem: `round` rozstrzyga remis do
parzystej (dokladnie 0,5 px mozliwe), a bbox wezszy niz pol piksela i tak dostaje 1 px
i odbiega bardziej (BBox to NamedTuple bez walidacji; ta sama regula w CZ
`_warp_to_grid` — sprawdzone tylko odczytem). `:567-569`: "0 z 80 601" -> "0 z 80 601
(bbox calkowity) i 0 z 79 799 (ulamkowy)" — liczby z `task-17-report.md:53-54`.
"33 775 z 80 601" w kroku 4 zostalo (to przypadek c E2E, bbox calkowity — zgodne).

**(d) m-10 sekcja 2 (`:110-113`)** — nowy punkt: `download/cutout.py` (tor PL) importuje
leniwie generyczny `bbox_to_crs` z zamrozonego `providers/cuzk/dmr.py` (ADR-024);
przeniesienie do `transform/` = etap 2 razem z odmrozeniem toru CZ. Importy sprawdzone
na HEAD: `cutout.py:131` (w `_bbox_to_2180`) i `:180` (w `prepare_pl_cutout`), oba
wewnatrz funkcji (leniwe). Naglowek "Dwie uwagi" -> "Trzy uwagi".

---

## Brama koncowa (HEAD bbd1cd4, po usunieciu in-tree `__pycache__`)

- `.venv/bin/python -m pytest tests/ -q -m "not live"` -> **1861 passed, 8 deselected**
  (start: 1854; +7: 1 test CLI, 3 testy GUGiK, 3 testy m-2 — w tym 2 parametry).
- `.venv/bin/python -m ruff check kartograf/ tests/` -> All checks passed!
- `.venv/bin/python -m ruff format --check kartograf/ tests/` -> 87 files already formatted
- `.venv/bin/python -m mypy kartograf/` -> Found 32 errors in 9 files; lista po
  `sed -E 's/:[0-9]+: /: /' | sort` **identyczna** z `mypy-baseline.txt` (zero nowych).
- `git diff --stat fa1f771 -- kartograf/providers/cuzk kartograf/transform/raster.py docs/PROGRESS.md` -> pusto;
  `tests/test_cuzk_client.py tests/test_cuzk_dmr.py` -> 74 passed.
- `git status --short` -> pusty.
- Pokrycie (komenda z CLAUDE.md): 92,92 %.

## Watpliwosci / do decyzji kontrolera

1. **Liczby testow w dokumentach sa po tej fali nieaktualne** i celowo ich nie
   ruszalem (SCOPE jest poza lista, a czesciowa aktualizacja dalaby niespojnosc):
   `README.md:334` ("1854 offline + 8 live"), `README.md:377` ("1854 testy offline"),
   `docs/CHANGELOG.md:641-647` (### Tests), `docs/SCOPE.md:497` i wiersz historii `:526`.
   Zmierzone teraz: **1861 offline (+8 live), pokrycie 92,92 % (= "92,9 %", bez zmian)**.
   Precedens formatu w CHANGELOG: "1716 ... (1708 po 26 zadaniach + 8 w fali naprawczej
   po finalnym review)" -> tu "1861 (1854 po 18 zadaniach + 7 w fali naprawczej)".
   Proponuje dolaczyc do Zakonczenia (PROGRESS i tak dostaje liczby).
2. **Rozszerzenia poza litera briefu** (wszystkie w duchu pozycji, do weta):
   (a) docstringi `download_sheets` i `run_pl_cutout` + zdanie w Notes
   `download_hierarchy` — to samo doprecyzowanie "never raise"/"kazda inna porazka ->
   DownloadError", ktore brief kazal zrobic w ARCHITECTURE (6a); bez tego docstringi
   przeczylyby dokumentacji; (b) test (d) "URL wygrywa" i asercje wyciagu/warningu
   w (a) I-2 — bronia rulingu i wymagan z briefu mutacjami M2-M4; (c) wyciag komunikatu
   wyjatku regexem zamiast "pierwszych ~200 znakow" (przyklad z briefu byl "np.";
   uzasadnienie M3); (d) w komunikacie bledu faktyczny kod HTTP (`response.status_code`);
   (e) m-9c: dopisek o `max(1, ...)`; (f) CLAUDE.md: zdanie o `addopts` bez `-m`.
3. **Twierdzenie "MapServer zwraca raport wyjatku z HTTP 200"** (CHANGELOG, ARCHITECTURE,
   komentarz w kodzie) opiera sie na rulingu I-2 i znanym zachowaniu MapServera oraz na
   tym, ze tresc "Invalid layer(s) given in the LAYERS parameter" z CHANGELOG to komunikat
   MapServera — nie na zapisanej odpowiedzi GUGiK. Sformulowane jako "serwery WMS, np.
   MapServer"; kod HTTP i `Content-Type` realnej odpowiedzi GUGiK nadal do zapisania
   w checkliscie live (razem z pusta odpowiedzia GetFeatureInfo).
4. Proces: nieswiezy `.pyc` przy mutacjach zachowujacych rozmiar pliku (sekcja na
   poczatku) — warto dopisac do wspolnych zasad re-reviewera.
