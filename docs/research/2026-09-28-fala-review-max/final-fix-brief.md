# Fala naprawcza po finalnym review (Kartograf, develop, HEAD fa1f771)

Finalny review calej fali (fable) dal werdykt "With fixes": 0 Critical, 2 Important,
11 Minor. Pelny raport z file:line, dowodami i mutacjami:
`final-review-report.md` (ten katalog) — przeczytaj sekcje Issues (I-1, I-2, m-1..m-11)
i "Mutacje". Ta fala naprawia ponizsza liste — i NIC poza nia. Wspolne zasady:
`IMPLEMENTER_COMMON.md` + `COMMON-CONTEXT.md` (ten katalog) — przeczytaj je najpierw.

Rozstrzygniecia kontrolera (ledger `progress.md`, linie `Ruling:` na koncu) sa wiazace.

## Do zrobienia

### 1. I-1 + m-1 — `--force` i `--workers` toru wycinka PL bronione testem CLI

Kod bez zmian (`kartograf/cli/download_cmd.py`, wywolanie `run_pl_cutout(...)` z
`max_workers=getattr(args, "workers", 4)` i `force=args.force`). Brakuje testu: mutacja
`force=args.force` -> `force=False` przechodzi dzis 312/312, a `--force` na istniejacym
wycinku staje sie cichym no-opem (rc 0, plik nietkniety, "Downloaded to <stary plik>").

Test w `tests/test_pl_cutout.py::TestDownloadPlBboxCutout` (harness `_run` / `_pl_args`,
`self.dm` = mock konstruktora `DownloadManager`):
- zbuduj wycinek raz (albo wyznacz jego `target_path`), nadpisz plik wyniku dummy trescia,
  uruchom CLI z `_pl_args(tmp_path, force=True, workers=3)`;
- asercje: rc == 0; tresc pliku wyniku sie zmienila (przebudowany, poprawny GeoTIFF);
  `manager.download_sheets.call_args.kwargs["skip_existing"] is False`;
  `self.dm.call_args.kwargs["max_workers"] == 3`.
Mutacje (PO commicie, kazda FAIL -> przywroc -> PASS):
  (a) CLI `force=args.force` -> `force=False`;
  (b) CLI `max_workers=getattr(args, "workers", 4)` -> `max_workers=1`;
  (c) biblioteka `run_pl_cutout`: `skip_existing=not force` -> `skip_existing=True`.
Jesli ktoras NIE daje FAIL — popraw test (to jest sens tej pozycji).

### 2. I-2 — raport wyjatku OGC w odpowiedzi 2xx skorowidza to blad warstwy, nie brak pokrycia

`kartograf/providers/pl/gugik.py::GugikProvider._get_opendata_url`. Dzis po
`raise_for_status()` jedynym kryterium jest regex URL; odpowiedz 2xx bez URL = "warstwa
odpowiedziala i nie ma arkusza". Gdy tak odpowiedza wszystkie warstwy -> `NoCoverageError`
-> pod R5 nodata + `missing_sheets` w pliku, ktory kolejne przebiegi pomijaja jako
istniejacy. Realny wyzwalacz: WMS zwraca `ServiceExceptionReport` z HTTP 200 (np.
`LayerNotDefined` przy nieaktualnej nazwie warstwy, gdy GetCapabilities sie nie udal
i `_get_validated_layers` wrocil do nazw zaszytych w kodzie).

Wymaganie (Ruling I-2, wiazace):
- URL w odpowiedzi ZAWSZE wygrywa (obecny blok `if urls: ... return` bez zmian).
- W sciezce "brak URL": jesli body zawiera `ServiceException` albo `ExceptionReport`
  (podciag, wielkosc liter jak w OGC: `ServiceExceptionReport`, `ows:ExceptionReport`)
  -> liczy sie jako porazka transportu tej warstwy: `transport_errors += 1`,
  `last_error = DownloadError(...)` z nazwa warstwy i krotkim wyciagiem z body
  (np. pierwsze ~200 znakow po `strip()`), `logger.warning(...)`, `continue`. Istniejace
  galezie po petli robia reszte: wszystkie warstwy -> "unavailable", czesc -> "brak
  pokrycia niepewny", nigdy `NoCoverageError`.
- BEZ kontroli `Content-Type` i BEZ kontroli pozytywnej ("brak `<html` = blad") —
  realnej pustej odpowiedzi GetFeatureInfo GUGiK nikt nie zapisal; to pozycja checklisty
  live.
- `GugikNmptProvider` dziedziczy `_get_opendata_url` — zweryfikuj na kodzie i napisz
  w raporcie (bez osobnego testu, chyba ze NMPT nadpisuje metode).
Testy w `tests/test_gugik_provider.py` (obok testow `_get_opendata_url`):
  (a) wszystkie warstwy: HTTP 200 + body `<?xml ...?><ServiceExceptionReport ...>
      <ServiceException code="LayerNotDefined">...</ServiceException>
      </ServiceExceptionReport>` -> `DownloadError`, `not isinstance(e, NoCoverageError)`,
      komunikat "unavailable" / "all N layer queries failed";
  (b) jedna warstwa jak w (a), pozostale "czysta pusta" odpowiedz (fixture juz istnieje)
      -> `DownloadError` z "niepewny", nie `NoCoverageError`;
  (c) istniejacy test "wszystkie warstwy bez arkusza -> NoCoverageError" musi dalej
      przechodzic bez zmian.
Mutacja: usun straz -> (a) i (b) FAIL.
Dokumentacja: `docs/CHANGELOG.md` 0.7.0 (`### Fixed` albo dopisek do istniejacego wpisu
R5/"brak pokrycia niepewny" — wybierz, gdzie czytelniej); `docs/ARCHITECTURE.md` 4.3,
krok o R5: jedno-dwa zdania o strazy + pozostala granica ("strona bledu z 200 bez
znacznikow OGC nadal liczy sie jako brak pokrycia — checklista live").

### 3. m-2 — uklad czeski bboxa wycinka niezalezny od wielkosci liter

`kartograf/download/cutout.py::_bbox_to_2180` porownuje `bbox.crs` doslownie
(`== "EPSG:2180"`, `in _CZ_CRS`); wywolanie biblioteczne z `"epsg:5514"` idzie po cichu
niepinowanym transformerem (obejscie ADR-024 w nowym publicznym API). Znormalizuj
porownanie (np. `bbox.crs.strip().upper()` dla obu warunkow; `providers/cuzk/*` nie
modyfikuj). Test (`tests/test_pl_cutout.py`): `prepare_pl_cutout(BBox(..., "epsg:5514"),
"EPSG:2180", ...)` daje `bbox_2180` IDENTYCZNY z wariantem `"EPSG:5514"`; warunek
sensownosci w tescie: sciezka niepinowana (`core/geometry._transform_bbox`) rozni sie od
przypietej o > 0,01 m (zmierz i wpisz do raportu). Mutacja: przywroc doslowne
porownanie -> FAIL.

### 4. m-6 + m-7 — docstringi publicznego API

- `kartograf/download/manager.py`: kazde miejsce, ktore mowi, ze `last_result` ustawia
  wylacznie `download_hierarchy` (reviewer wskazal okolice l. 78, 122-126, 299-302,
  372-377) — popraw zgodnie z kodem (sprawdz, KTORE metody faktycznie ustawiaja
  `last_result`). Jezyk pliku: angielski.
- `kartograf/providers/pl/gugik.py::GugikProvider.download` — sekcja `Raises`:
  `NoCoverageError` (podklasa `DownloadError`) — kiedy dokladnie (wszystkie warstwy
  skorowidza odpowiedzialy bez arkusza; po pkt 2: raport wyjatku OGC to NIE ten przypadek).

### 5. m-8 — komendy testow w CLAUDE.md i README (Ruling m-8)

`CLAUDE.md` (sekcja "Komendy", l. ~130, ~133) i `README.md` (l. ~355, ~358): domyslne
komendy testow z `-m "not live"` (offline, zgodnie z deklaracja "Testy sa offline") +
jedna osobna, jawna linia dla testow sieciowych, np.
`.venv/bin/python -m pytest tests/ -m live   # N testow sieciowych (GUGiK/CUZK) — tylko swiadomie`
— N zmierz (`--collect-only -q -m live`). Nie usuwaj niczego innego z tych sekcji.

### 6. m-9 + m-10 — precyzja `docs/ARCHITECTURE.md`

Kazde zdanie sprawdz na zywym kodzie (numery linii od reviewera moga sie przesunac):
- (a) sekcja 4.3 — "zamienia KAZDY wyjatek przygotowania, selekcji ... na kod 1": CLI
  `_download_pl_cutout` lapie z `prepare_pl_cutout` tylko `TransformError`/
  `ValidationError`, z `select_pl_cutout_sheets` tylko `ValidationError`, wokol
  `run_pl_cutout` — `Exception`; pozostale (nieosiagalne przy wejsciu walidowanym przez
  CLI) ida do bariery `main()` — sprawdz, co ona robi, i opisz zgodnie z faktem.
  Oraz zdania "porazka arkusza nie przerywa listy" / "kazda inna porazka =
  DownloadError": prawdziwe dla rodziny `DownloadError`; w galezi sekwencyjnej
  (`max_workers=1`, domyslne w bibliotece) inny wyjatek (np. `OSError` zapisu) wylatuje
  z `download_sheets`/`run_pl_cutout` bez zmian — sprawdz takze galaz rownolegla
  i opisz obie zgodnie z kodem.
- (b) "Nieudana budowa a poprzedni wynik": cytat E2E (e) dotyczy porazki POBRANIA
  (rzuca przed `build_pl_cutout`), wiec niczego tu nie dowodzi — zastap odwolaniem do
  testow `tests/test_pl_cutout.py::...::test_failed_build_keeps_previous_result`
  i `tests/test_transform_raster.py::...::test_failed_warp_keeps_previous_destination`
  (sprawdz pelne nazwy) albo usun nawias.
- (c) "< 0,5 px" -> "do 0,5 px" (dwa miejsca: `round` half-to-even w `warp_to_grid`
  moze trafic dokladnie 0,5 px); "0 z 80 601" doprecyzuj: bbox calkowity; ulamkowy
  0 z 79 799.
- (d) m-10: w sekcji 2 (graf importow) jedno zdanie: tor PL (`download/cutout.py`)
  importuje `bbox_to_crs` z zamrozonego `providers/cuzk/dmr.py`; przeniesienie do
  `transform/` = etap 2 (wraz z odmrozeniem toru CZ).

## Czego NIE robic

- `docs/PROGRESS.md` — nie dotykaj (zamkniecie fali robi kontroler).
- `kartograf/providers/cuzk/*`, `kartograf/transform/raster.py` — bez zmian.
- Zadnych pozycji spoza listy (m-3, m-4, m-5, m-11 i "ZOSTAW" z triazu sa rozstrzygniete
  jako backlog — ledger).

## Commity (Conventional Commits, polski ASCII; stopka wg Twojego system-remindera)

Pogrupuj logicznie, np.: `test(cli): ...` (1), `fix(gugik): ...` (2), `fix(download): ...`
(3), `docs: ...` (4-6, z CHANGELOG). Mutacje wykonuj PO commicie danej grupy.

## Brama na koniec

`.venv/bin/python -m pytest tests/ -q -m "not live"` (liczba passed/deselected do raportu),
`.venv/bin/python -m ruff check kartograf/ tests/`, `.venv/bin/python -m ruff format --check kartograf/ tests/`,
mypy: diff listy wobec `mypy-baseline.txt` (zero nowych). `git status --short` czysty.

## Raport

Pelny raport: `final-fix-report.md` (ten katalog) — per pozycja: co zmieniono (file:line),
testy RED/GREEN, mutacje (zmiana, komenda, fragment FAIL, PASS po przywroceniu), zmierzone
liczby; brama. Odpowiedz kontrolerowi krotkim kontraktem z `IMPLEMENTER_COMMON.md`.
