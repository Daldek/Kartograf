# Deduplikacja download/CLI/sidecar/landcover — implementacja (2026-10-07)

Galaz `refactor/dedup-download` (worktree `Kartograf-dedup-download`), baza
`0f5e4f4`. Zrodlo znalezisk: `review-1-duplikacje.md` — D7, D10, D11, D14,
D15, D18. Poza zakresem (inni agenci / osobna ocena): LAZ w
`cli/download_cmd.py` (sidecar i pula LAZ), deduplikacja providerow
i transportu (D1, D2, D8, D9, D13, D19), parsery godel i `--bbox` (D4, D5,
D12).

Zasada pracy: najpierw potwierdzenie, ze znalezisko jest aktualne na bazie;
refaktoryzacja bez zmiany zachowania, chyba ze kopie juz sie rozjechaly
(wtedy wybor poprawnej kopii + test padajacy na starej); po kazdym kroku
pelna suita offline, ruff; dla kazdego ujednoliconego miejsca mutacja
helpera pokazujaca, ze padaja testy WSZYSTKICH dawnych torow (brakujace
testy dopisane, zanim mutacja zostala uznana).

## Wynik koncowy

- `pytest tests/ -m "not live"`: **2244 passed** (baza 2216; +28 nowych
  przypadkow), 16 deselected (`live`).
- `ruff check kartograf/ tests/`: All checks passed; `ruff format --check`:
  92 files already formatted.
- `mypy kartograf/`: 32 bledy; lista bez numerow linii (`sed -E
  's/:[0-9]+:/:/' | sort`) **identyczna** z baza `0f5e4f4` (`diff` pusty).
- Bilans linii `kartograf/`: +487 / -492 (netto -5; usunieta tresc
  zastapiona glownie docstringami nowych helperow), `tests/`: +483 / -4,
  `docs/`: ARCHITECTURE (D11), CHANGELOG, ten raport.

| D | commit | kod (+/-) | testy (+/-) |
|---|---|---|---|
| D18 | `5f66954` | +56 / -37 | +105 / -3 |
| D11 | `e9e12ff` | +51 / -27 | +82 / -0 |
| D10 | `5be434c` | +136 / -237 | +76 / -0 |
| D7 | `076263e` | +170 / -142 | +135 / -0 |
| D15 | `795c17c` | +21 / -19 | +30 / -1 |
| D14 | `cadb928` | +53 / -30 | +55 / -0 |

## D18 — storage providera (5 miejsc, nie 4)

- **Aktualnosc:** potwierdzone; piate miejsce znalezione w torze godla CZ
  (`_cz_download_godlo`: `FileStorage(subdir=descriptor.resolve_subdir(...))`).
- **Przed:** CLI `_create_provider_and_storage` (3 galezie: `product="nmpt"`,
  `product="orto"` + wariant, `resolution=`), `DownloadManager.__init__`
  (deskryptor + wariant), `run_pl_cutout` i `estimate_pl_cutout_bytes`
  (`resolution=`), tor CZ (deskryptor).
- **Po:** `download/storage.py::storage_for_provider(output_dir, provider=None,
  *, resolution, vertical_crs)` — segment z deskryptora providera (bez
  `descriptor_key`: szablon NMT wg `resolution`), pion FAKTYCZNY providera
  (`str`) wygrywa z argumentem, wariant `storage_variant` na koncu segmentu.
  Wszystkie 5 miejsc wola fabryke.
- **Roznice zachowan:** brak w sciezkach (segmenty sprawdzone testami). CLI
  nmpt/orto ma teraz `FileStorage` z `subdir=` zamiast `product=` —
  prywatne `_product`/`repr` sie roznia; 3 asercje `storage._product == ...`
  w `TestCreateProviderAndStorage` zastapione MOCNIEJSZYMI `storage._subdir
  == "<pelny szablon>"`.
- **Nowe testy:** `TestStorageForProvider` (5), `TestCutoutSize::
  test_estimate_default_storage_is_sheet_segment_of_vertical`,
  `TestLibraryApi::test_default_sheet_storage_follows_provider_vertical`
  (dwa ostatnie: domyslny storage wycinka bez wstrzykniecia — wczesniej
  niebronione).
- **Mutacja** (fabryka ignoruje deskryptor, wariant i pion providera):
  31 failed — `TestCmdDownloadCz` 11 (CZ), `TestDownloadManagerStorageFromDescriptor`
  6 + `TestOrtoVariantStorage` 4 (manager), `TestCreateProviderAndStorage` 4
  (CLI), `TestLibraryApi` 1 + `TestCutoutSize` 1 (wycinek: run i estimate),
  `TestStorageForProvider` 4.

## D11 — regula "5m => EVRF2007"

- **Aktualnosc:** potwierdzone 4 miejsca: `GugikProvider.__init__`
  (`ValueError`), `create_nmt_provider` (warning + korekta),
  `DownloadManager.__init__` (warning + korekta), `prepare_pl_cutout`
  (`ValidationError`). CLI `--resolution 5m --vertical-crs KRON86` korygowalo
  po cichu (tylko log).
- **Wybor skutku:** CLAUDE.md ("NMT 5m (PL) dostepne tylko w ukladzie
  EVRF2007"), ARCHITECTURE sekcja 3 ("korekte 5m => EVRF2007 robi
  `download_pl_cutout`, a w CLI fabryka providera") i CHANGELOG (korekta
  przez fabryke w CLI) opisuja KOREKTE, nie blad — wiec skutkiem jest
  korekta, a w CLI jawna (`Info:` na stderr, jak inne rozstrzygniecia
  `--country auto`). Twardy blad zostaje tylko tam, gdzie wejscie z definicji
  jest juz pionem faktycznym (`prepare_pl_cutout`) — udokumentowane API.
- **Po:** `providers/pl/__init__.py::nmt_vertical_crs(resolution,
  vertical_crs, *, log=True)` — jedyne miejsce reguly i komunikatu logu.
  Fabryka i `DownloadManager` (tylko gdy provider nie zna swojego pionu)
  wolaja z logiem; `prepare_pl_cutout` porownuje wynik `log=False`
  i rzuca `ValidationError`; CLI `_resolve_pl_sentinels` (tylko
  `--product nmt`; LAZ tez przechodzi przez sentinele) koryguje `args`
  z `Info: NMT 5m (PL) jest dostepny tylko w EVRF2007 — --vertical-crs
  KRON86 zamieniony na EVRF2007`. Trzy obejscia
  `getattr(provider, "vertical_crs", ...)` w CLI ("zeby manager nie
  ostrzegal drugi raz") zastapione wprost `args.vertical_crs`.
- **Roznice zachowan:** (1) CLI drukuje `Info:` (nowe, zamierzone);
  (2) `DownloadManager(provider=<provider z pionem str>, resolution="5m",
  vertical_crs="KRON86")` nie loguje juz ostrzezenia — argument
  `vertical_crs` jest wtedy ignorowany na rzecz pionu providera (tak bylo
  i przedtem, tylko z mylacym logiem).
- **Nie zrobione:** `GugikProvider.__init__` nadal rzuca `ValueError` dla
  5m+KRON86 (straz bezposredniej konstrukcji providera; providery poza
  zakresem tego agenta, a zmiana typu wyjatku to A5-5 z backlogu).
- **Nowe testy:** `test_pl_5m_kron86_corrected_with_info` (pada na starej
  kopii: brak `Info:`), `test_pl_1m_kron86_no_correction`,
  `test_5m_rule_only_for_nmt` (LAZ), `test_rule_without_log_is_silent`.
- **Mutacja** (`nmt_vertical_crs` zwraca pion bez zmian): 8 failed —
  fabryka (`TestCreateNmtProviderFactory` 2), manager
  (`TestDownloadManagerStorageFromDescriptor` 1, `TestDownloadManagerBasic`
  1), `prepare_pl_cutout` (`TestLibraryApi::test_prepare_rejects_bad_params`),
  CLI wycinek (`TestDownloadPlBboxCutout` 1), CLI Info
  (`TestCountryDispatch` 1, `TestCreateProviderAndStorage` 1).

## D10 — "pobierz jeden arkusz" w `DownloadManager`

- **Aktualnosc:** potwierdzone: `download_sheet`, `_download_single_sheet_task`
  (tylko pula) i `_download_hierarchy_sequential` (wlasna kopia), plus
  trzy galezie `DownloadProgress` w puli i dwie kopie finalizacji
  (`last_result`, log podsumowania).
- **Rozjazd znaleziony:** `download_sheet` ignorowal sciezke zwrocona przez
  `provider.download` (zwracal i opisywal sidecarem sciezke docelowa
  managera), tryby listy uzywaly sciezki providera. Wybrana: sciezka
  providera (kontrakt `BaseProvider.download -> Path` pobranego pliku; 2 z 3
  kopii). Test `test_every_mode_returns_provider_path[sheet|list_seq|
  list_parallel]` pada na starej kopii dla `[sheet]`.
- **Po:** `_fetch_sheet(godlo, skip_existing, on_download=None) -> (Path,
  skipped)` — jedyna tresc (sciezka, skip + `_note_reuse`, pobranie,
  sidecar); `_download_single_sheet_task` = `_fetch_sheet` + mapowanie
  `DownloadError`/`NoCoverageError` na status; `_record` (wynik) i `_emit`
  (postep) wspolne; `_download_many` z petla sekwencyjna i pula.
  `download_hierarchy`/`download_sheets` wolaja `_download_many`.
- **Zachowane swiadomie:** `downloading` tylko w trybie sekwencyjnym
  (CLI pokazuje `↓`; callback `on_download` wolany tuz przed pobraniem),
  `OSError` sekwencyjnie przerywa liste, w puli liczy sie jako `failed`
  (udokumentowane w `download_hierarchy`/`run_pl_cutout`).
- **Inne drobne:** log `Skipping`/`Downloading` (INFO) teraz takze w trybach
  listy; provider zwracajacy `None` w trybie sekwencyjnym nie trafia juz do
  `succeeded` (zachowanie puli).
- **Nowe testy:** `test_every_mode_returns_provider_path` (3),
  `test_progress_reports_final_status_and_message_per_sheet[1|4]` (koncowy
  status i komunikat kazdego arkusza w obu trybach — przechodzi na starej
  kopii, wiec broni ekwiwalencji).
- **Mutacje:** (1) `_fetch_sheet` bez zapisu sidecara: 23 failed, m.in.
  `test_every_mode_returns_provider_path` we wszystkich 3 trybach,
  `TestReuseNotedInSidecar` `[1]` i `[3]`; (2) `_record` liczy skipped jako
  succeeded: `TestDownloadHierarchyLastResult[1]` i `[4]`; (3) `_emit` gubi
  komunikat: przed nowym testem **0 failed**, po — 2 (`[1]` i `[4]`).

## D7 — sidecar: opakowania, format `transform`, nazwa wycinka

- **Aktualnosc:** potwierdzone (numery linii przesuniete): opakowania
  best-effort w `DownloadManager._write_sidecar`,
  `LandCoverManager._write_sidecar`, `cutout.write_pl_cutout_sidecar`,
  `_write_cz_sidecar` i `_write_laz_sidecar` (LAZ — poza zakresem); format
  `pinned: ... (... m)` w wycinku PL i torze CZ; nazwa `bbox/<coords>`
  w `prepare_pl_cutout` i `_cz_download_bbox` (trzecia kopia formatu
  w `cuzk/client.py` dla parametru URL — provider, nie ruszana). CZ,
  wycinek i landcover nadpisywaly `meta.horizontal_crs` po
  `build_metadata`.
- **Po:** `sources/sidecar.py::emit_sidecar(descriptor_key, data_path, *,
  request, vertical_crs, horizontal_crs, pinned_transforms, extra,
  capability, nodata)` — jedyne `try/except` + ostrzezenie i jedyny guard
  "klucz deskryptora nie `str` -> brak sidecara"; `pinned_transforms`
  (`{"horizontal": PinnedTransform|None, ...}`) formatuje `pinned_label`
  (wpisy `None` pomijane, pusto -> `transform: null`); `horizontal_crs`
  idzie do `build_metadata`. `download/storage.py::bbox_cutout_path(output_dir,
  subdir, bbox, extension)` — nazwa wycinka PL i CZ. Opakowania managerow,
  wycinka i CZ zostaly cienkie (kontekst toru: `source_info`, fallback
  CORINE PNG, `extra` wycinka, operacje CZ).
- **Roznice zachowan:** tresc sidecarow i sciezki bez zmian. Log
  ostrzezenia idzie z loggera `kartograf.sources.sidecar` (tekst ten sam).
  `source_info(godlo)` (manager) i `provider.horizontal_transform(...)` (CZ)
  sa wyliczane PRZED `emit_sidecar`, czyli poza `try` — oba sa odczytem
  cache wypelnionego przez wlasnie zakonczone pobranie (ten sam klucz), wiec
  nie rzucaja; gdyby jednak rzucily, pobranie zakonczy sie bledem zamiast
  ostrzezeniem. `PinnedTransform.sidecar_label` (propozycja review) nie
  powstal: testy CZ podstawiaja atrapy operacji (`Mock` z `description`
  i `accuracy_m`), a funkcja modulu dziala na kazdym obiekcie z tymi polami.
- **Nowe testy:** `TestEmitSidecar` (4), awaria budowy sidecara nie przerywa
  pobrania w landcover i wycinku PL (wczesniej broniona tylko w managerze
  i CZ), dokladny format `pinned:` w wycinku PL, nazwa wycinka UTM
  (`EPSG:3045`, northing 7 cyfr) w `TestPreparePlCutout`.
- **Mutacje:** (1) `emit_sidecar` przepuszcza wyjatek: 5 failed —
  manager, landcover, wycinek PL, CZ, `TestEmitSidecar` (przed nowymi
  testami: tylko manager i CZ); (2) `pinned_label` bez dokladnosci: 5 failed
  — CZ 3, wycinek PL 1, unit 1 (przed: tylko CZ); (3) `bbox_cutout_path`
  z `.6g`: 3 failed — CZ 2, wycinek PL 1 (przed: tylko CZ).
- **Dla agenta LAZ:** `_write_laz_sidecar` moze wolac `emit_sidecar(key if
  isinstance(key, str) else "pl.gugik.laz", target, request=...,
  vertical_crs=..., horizontal_crs=..., extra=...)` — nie zmienione tutaj.

## D15 — naglowek listy arkuszy

- **Aktualnosc:** potwierdzone (`_download_pl_cutout`,
  `_download_pl_sheet_list`); tresc identyczna (wycinek drukowal
  `(resolution: X)`, lista `_product_label(product, resolution)`, ktore dla
  `nmt` daje to samo).
- **Po:** `_print_sheet_list(godla, target_scale, *, what, label)`.
- **Nowe testy:** `test_download_bbox_sheet_list_header` (lista) i
  `test_sheet_list_header` (wycinek), po 12 godel (skrot `3 + ... + 2`).
- **Mutacje:** naglowek bez nawiasow i skrot bez `...`: przed nowymi testami
  **0 failed** (wyjscie nie bylo bronione), po — po 2 failed (oba tory).

## D14 — podpowiedzi `NoCoverageError`

- **Aktualnosc:** potwierdzone (`GugikProvider._no_coverage`,
  `GugikOrtoProvider._no_coverage`); przed praca sprawdzone, ze rownolegla
  deduplikacja providerow nie dotyka tych metod.
- **Rozjazd znaleziony:** podpowiedz "inny uklad" w orto byla krotsza:
  `Skorowidz ma ten obszar w PL-1992: <godlo> — uzyj tego godla`, w NMT:
  `... <godlo> (<skala>) — uzyj tego godla lub --system 1992 --scale
  <skala>`. Wybrana pelna (NMT): `--system`/`--scale` dzialaja dla orto tak
  samo (lista arkuszy przez `DownloadManager`), a skala pomaga wybrac
  arkusz. Test `test_providers_share_hints[orto]` pada na starej kopii.
- **Po:** `skorowidz.coverage_hints(parser, records)` (potomek PL-2000,
  inny uklad) i `skorowidz.no_coverage_error(parser, message, hints)`
  (sortowanie, `"; "`, `godlo=`). W providerach zostaja tylko podpowiedzi
  wlasne: filtr i podpowiedz rozdzielczosci (NMT), warianty koloru (orto).
- **Mutacje:** (1) podpowiedz potomka bez `--scale`: 5 failed — helper,
  `[nmt]`, `[orto]`, `TestNoCoverageHintsOnRealBodies` (NMT, surowe body),
  `TestSkorowidzRegression` (NMT); (2) odwrocona kolejnosc podpowiedzi:
  `[nmt]` i `[orto]`.

## Uwagi z przebiegu

- Katalog scratchpad sesji jest wspoldzielony z rownoleglymi agentami:
  skrypt mutacji `mut.sh` zostal w trakcie przebiegu nadpisany przez agenta
  providerow (ta sama nazwa pliku), a mutacja D10 nie zostala cofnieta przez
  skrypt. Plik odtworzony z kopii i sprawdzony `diff`-em (jedyna roznica =
  mutowana linia), dalsze mutacje w prywatnym podkatalogu `dd/`. Na
  worktree providerow nie mialo to wplywu (jego czesc skryptu odwolywala sie
  do niezdefiniowanej zmiennej i nie wykonala zapisu).
- Baseline mypy policzony ponownie z `git archive 0f5e4f4` (plik bazowy
  w scratchpadzie mogl byc nadpisany tak samo).
