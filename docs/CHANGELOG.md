# Changelog

Wszystkie istotne zmiany w projekcie sa dokumentowane w tym pliku.

Format oparty na [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/),
projekt stosuje [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.0] - 2026-10-17

### Zmiany lamiace (BREAKING)

- Tryb domyslny (bez `--check-updates`/`--upgrade`) nie pyta zrodla
  o plik z lokalna wersja (test na zywo 2026-10-16, errata 3 ADR-036):
  sygnal `http` (arkusze SM5, kafle TM33 DMR 4G, LAZ CZ, warstwice CZ,
  ZTM, paczki KU, pliki krajowe RUIAN/HY-NET) bez `HEAD`, sygnal
  `metadata` (SoilGrids, CORINE CLMS, ortofoto CZ, pliki z feedow ATOM)
  bez sprawdzania wydania, arkusze map BDOT10k bez GetFeatureInfo.
  Linia `lokalna wersja ... (bez sprawdzania; --check-updates)`, w API
  `VersionedFile.unverified == "unchecked"` i `newer = None`. Dotad kazde
  uruchomienie pytalo zrodlo (offline 3 proby i `Warning:`, do 19 s; maps
  offline kod 1) i dopisywalo `dostepna nowsza`. Arkusze PL i kafle LAZ PL
  pytaja skorowidz jak dotad (wybor plikow). Co zrobic: aktualnosc
  sprawdzaj `--check-updates` (`check_*`), nowsza tresc pobieraj
  `--upgrade`; kod czytajacy `VersionedFile.newer` w trybie domyslnym tych
  torow dostaje `None`.
- Linie statusu pobrania i linie `--check-updates` maja jeden podmiot:
  sciezke pliku pod `--output` w kazdym torze (dotad godlo, nazwa pliku
  jednostki z kilkoma plikami, `82707_..._N-34-...laz` w pobraniu LAZ, ale
  godlo w checku, wspolrzedne bbox w checku kolekcji); tak samo linia
  `Error: ... zrodlo zmienilo sie od planu`. Linie projektu: `zadanie:
  jednostka (plik): stan` (dotad `orto_cz: CTES96: ok` cztery razy). Co
  zrobic: skrypty czytajace te linie dopasuj do sciezki pod `--output`
  (biblioteka bez zmian: `VersionedFile.path`, `PlanItem.segment`/
  `hierarchy`/`name`).
- `hsg_statistics()` liczy powierzchnie i procenty dla obszaru zadania
  (`request` sidecara HSG: bbox w EPSG:2180 - przy `--geometry` jej
  obwiednia - albo rama arkusza), nie dla calego rastra: komorka SoilGrids
  na brzegu liczy sie udzialem w obszarze, suma powierzchni = obszar
  (test na zywo 2026-10-17: bbox 2 x 2 km dawal 420,91 ha). Obok grup
  `A`-`D` klucz `nodata` (`percent` = udzial w obszarze); `percent` grup
  to udzial powierzchni z danymi, `count` = komorki stykajace sie
  z obszarem; opisy grup (`description`, `HSG_DESCRIPTIONS`) po polsku.
  Plik bez sidecara z obszarem - caly raster. Co zrobic: kod iterujacy po
  wyniku pomija klucz `nodata` albo iteruje po `HSG_VALUES`; procent liczony
  dotad z pikseli rastra nie jest juz zwracany.
- Pole `product` sidecara w land cover i HSG to wartosc `--product` jak
  w pozostalych grupach (test na zywo 2026-10-17): `bdot10k`, `bdoo`,
  `corine`, `zabaged`, `data50`, `data250` (dotad `landcover`), raster
  `soil hsg` - `hsg` (dotad `soil`; nazwa komendy i katalogu `hsg/`).
  `soil download` (bez `--product`) zostaje `soil`. Pole `product`
  deskryptorow land cover = ta wartosc (grupe wyznacza katalog
  `landcover/`). Co zrobic: kod rozpoznajacy plik po `product ==
  "landcover"` sprawdza `dataset` albo nowa wartosc.
- `UnitFile.unit` wycinka (`download_data(..., cutout=True)`, PL i CZ) to
  wspolrzedne siatki (`<coords>`, jak jednostki obszaru kolekcji), nie
  sciezka pod `output_dir`; linia projektu `zadanie: jednostka (plik)`
  wycinka ma ten sam podmiot co inne zadania (dotad `trueorto:
  true-orto/pl_1992_0.05m/bbox/...tif (...tif): ok`). Linie CLI pobrania
  bez zmian (sciezka pod `--output`). Co zrobic: sciezke wycinka czytaj
  z `UnitFile.file.path`.
- Przeglad spojnosci UX 0.8.0 (bledy wejscia przed siecia, CLI = API):
  - `--layer` bez `--geometry` jest bledem w kazdej komendzie danych
    i w `project add` (dotad wartosc byla po cichu pomijana i zapisywana
    w manifescie). Co zrobic: usun `--layer` (warstwy danych BDOT10k/BDOO
    wybiera `--layers`).
  - LAZ PL odrzuca `--resolution`, `--sheet-system` i `--scale` (jak LAZ
    CZ; dotad pomijane). Co zrobic: usun te flagi z pobran LAZ.
  - Obszar jawnego `--country pl|cz` (`--bbox`, obwiednia `--geometry`)
    lezacy poza obwiednia kraju konczy sie `ValidationError` z ukladem
    obszaru w EPSG:4326 i podpowiedzia `--bbox-crs`/kolejnosci osi (dotad
    "brak obiektow"/"Brak arkuszy" po zapytaniu zrodla). Co zrobic: popraw
    `--bbox-crs` albo wspolrzedne (`names --product world` bez zmian).
  - Komunikat "skorowidz GUGiK niedostepny - uzyto lokalnej wersji"
    (`DownloadManager`) ma kod `CHECK_FAILED` zamiast `UNVERIFIED_LOCAL`;
    `UNVERIFIED_LOCAL` znaczy tylko "lokalna wersja zrodla bez taniego
    sygnalu" (`info`). Co zrobic: kod sprawdzajacy `Notice.code` dla awarii
    skorowidza - `CHECK_FAILED`.
  - CLI nie rozwija skrotow dlugich flag (`--out` nie znaczy `--output`,
    `--lay` nie jest skrotem `--layer`/`--layers`); `--plan` bez
    `--check-updates`/`--upgrade` to `Error:` z kodem 1 (dotad blad parsera,
    kod 2). Co zrobic: pisz pelne nazwy flag.
  - `--sheet` z godlem PL i `--sheet-system` innym niz uklad godla
    (`elevation`/`imagery download`, np. godlo PL-1992 z `--sheet-system
    2000`) to `Error:`/`ValidationError` przed siecia (dotad flaga byla po
    cichu pomijana); zgodna wartosc nadal wolno podac. Co zrobic: usun
    `--sheet-system` (uklad arkuszy wynika z godla).
  - `project init` bez `--output`: `Error:` z kodem 1 jak w komendach
    danych (dotad blad parsera, kod 2); `init_project(output_dir=None)` to
    `ValidationError`. Co zrobic: skrypt sprawdzajacy kod 2 - kod 1.
  - `landcover download` i `landcover list-layers` wybieraja dane przez
    `--product` jak kazda grupa danych (ADR-044; dotad `--source`/`-s`).
    `--source` i `-s` koncza sie bledem parsera (kod 2) z podpowiedzia
    `--product`; `--product soilgrids` (jak dawne `--source soilgrids`)
    wskazuje grupe `soil`. Komunikaty bledow nazywaja `--product <x>`
    (np. `--teryt dziala tylko z --product bdot10k ...`), kolumna WYBOR
    `landcover list-sources` - `--product bdot10k`. Klucz opcji zadania
    projektu `landcover download` to `product` (dotad `source`). Co
    zrobic: w skryptach zamien `--source X`/`-s X` na `--product X`;
    w recznie pisanym `kartograf-project.json` klucz `source` na `product`
    (`project add` zapisuje nowy klucz).
  - `soil hsg --summary` wypisuje statystyki HSG (udzial i powierzchnia
    grup A-D, brak danych) zamiast `--stats` (ADR-044; obok `soil download
    --stat` nazwa myla); `--stats` konczy sie bledem parsera (kod 2)
    z podpowiedzia `--summary`, a `project add ... soil hsg --summary` to
    `Error:` (opcja wypisywania, nie zadania). Co zrobic: w skryptach
    zamien `soil hsg ... --stats` na `--summary`.
  - Wycinek obrazu PL ma jedna pare funkcji dla ortofotomapy i true orto
    (ADR-044 D3): `download_image_cutout`/`check_image_cutout` (wynik
    `ImageCutoutResult`) sa w `kartograf.__all__`, wszystkie argumenty
    nazwane (`bbox=` jak w `download_data`), `coverage` opcjonalne (`None`
    dla true orto; ortofotomapa wymaga go jak dotad); owijki 0.8.0-dev
    `download_orto_cutout`/`check_orto_cutout` i nazwa `OrtoCutoutResult`
    usuniete bez aliasow. Co zrobic: `download_orto_cutout(bbox, ...)` ->
    `download_image_cutout(product="orto", bbox=bbox, ...)` (tak samo
    `check_*`), `OrtoCutoutResult` -> `ImageCutoutResult`.
  - Funkcje pobrania i sprawdzenia z `kartograf.__all__` przyjmuja
    argumenty tylko nazwane, jak `download_data` (test na zywo
    2026-10-17): `bbox=` w `download_pl_cutout`/`check_pl_cutout`,
    `download_cz_cutout`/`check_cz_cutout` i `download_laz_area`/
    `check_laz_area`, `sheet=` w `download_cz_sheet`/`check_cz_sheet`
    i `download_cz_orto_sheet`/`check_cz_orto_sheet` (dotad pierwszy
    argument pozycyjny); argument pozycyjny to `TypeError`. Funkcje
    projektu (`download_project`, `check_project` i reszta rodziny) maja
    pozycyjny tylko katalog projektu. Co zrobic: `download_pl_cutout(bbox,
    ...)` -> `download_pl_cutout(bbox=bbox, ...)`, `download_laz_area(bbox,
    ...)` -> `download_laz_area(bbox=bbox, ...)`,
    `download_cz_sheet("CTES96", ...)` -> `download_cz_sheet(sheet="CTES96",
    ...)`; tak samo pozostale funkcje i ich `check_*`.
  - Stan projektu w API: `get_project_status` zamiast `project_status`
    (ADR-044 D4; czasownik jak `init_project`, `verify_project`), bez
    aliasu; `kartograf project status` bez zmian. Co zrobic: zamien
    `project_status(...)` na `get_project_status(...)`.
- Publiczne API pobran land cover, SoilGrids i HSG to funkcje poziomu
  komendy (ADR-044 D5), bez aliasow: `download_landcover(product=...,
  output_dir=..., teryt=|sheet=|bbox=|geometry=, layer=, update=, plan=,
  workers=, on_notice=, ...)` i `check_landcover` z wyborem zgodnym
  z `landcover download`; `download_soil(output_dir=..., sheet=|bbox=|
  geometry=, property=, depth=, stat=, ...)` i `check_soil` odpowiadajace
  `soil download`; `calculate_hsg(output_dir=..., sheet=|bbox=|geometry=,
  depth=...)` i `check_hsg` z takim samym wyborem (HSG liczy tylko
  SoilGrids `stat="mean"`) oraz `hsg_statistics(path)`. Wyniki
  `LandCoverReport`, `SoilReport` i `HsgReport` maja `files:
  tuple[UnitFile, ...]`, `failed: tuple[UnitFailure, ...]` (bledy
  pojedynczych plikow i jednostek, wtedy `ok=False`), `stale`, `notices`
  i `ok` (komplet danych); `LandCoverReport.raw` to osobne wersje
  oryginalnego ZIP (`keep_raw`), `HsgReport.files[0].file` - raster HSG,
  `HsgReport.inputs` - pobrane clay/sand/silt. BDOT10k z obszaru pobiera
  kazdy powiat. Bledy wejscia (niepoprawne opcje) nadal koncza sie
  `ValidationError`. `LandCoverManager`, `HSGCalculator`,
  `LandCoverResult`, `LandCoverAreaResult`, `LandCoverFailure`
  i `HsgResult` nie sa eksportowane z `kartograf.__all__`. Nie ma
  parametru `timeout` funkcji komend ani `collections.run_request` (limit
  providera/kanalu). Co zrobic: dawne metody zamien na funkcje
  z `kartograf.__all__` - `LandCoverManager(out,
  "bdot10k").download(teryt=t)` -> `download_landcover(product="bdot10k",
  output_dir=out, teryt=t)` (`product=` tylko w land cover; `check` ->
  `check_landcover`), `LandCoverManager(out, "soilgrids").check(...)` ->
  `check_soil(output_dir=out, ...)`, `HSGCalculator(out).calculate_hsg(...)`
  -> `calculate_hsg(output_dir=out, ...)` bez `stat=` (analogicznie
  `check_hsg`), `calc.get_hsg_statistics(path)` -> `hsg_statistics(path)`;
  `result.file` -> `report.files[0].file`, `result.files` ->
  `report.files` (pole `.file`), wersje oryginalnego ZIP z `report.raw`,
  wejscia HSG z `report.inputs`; brak pokrycia jednostki i inne porazki
  czytaj z `report.failed` i `report.ok`, nie z wyjatku obslugi pliku;
  usun przekazywanie `timeout=`.
- Ortofotomapa pod `--country auto` (plan D, ADR-042 D13): obszar przy
  granicy daje arkusze PL i arkusze SM5 CZ (CUZK) zamiast zawezenia do PL
  (`Notice` `auto_narrowed_to_pl` dla samego `--product orto` znika; pliki
  CZ w `orto/cz_sjtsk/`, wspolne `extra.parent_request`). `--resolution`
  z `--product orto` bez `--cutout` jest bledem dla PL i CZ (arkusze maja
  piksel zrodla). Co zrobic: tylko arkusze PL - `--country pl`
  (`country="pl"`); usun `--resolution` z pobran arkuszy ortofotomapy
  (piksel wycinka: `--cutout --coverage ... --resolution ...`).
- CLI w grupach komend wg typu danych (ADR-039, bez aliasow): kazda grupa
  ma wlasne flagi i `--help`, a `list-sources` wypisuje jej zrodla z rejestru
  (bez sieci). Stare komendy koncza sie bledem parsera (kod 2) z nazwa nowej.

  | Dotad | Teraz |
  |---|---|
  | `kartograf download --product nmt\|nmpt\|laz ...` | `kartograf elevation download --product nmt\|nmpt\|laz ...` |
  | `kartograf download --product orto ...` | `kartograf imagery download --product orto ...` (bez `--vertical-crs` i `--min-density`; `--resolution` tylko z `--cutout`; `--country pl\|cz\|auto`) |
  | `kartograf landcover download --source bdot10k\|corine ...` | `kartograf landcover download --product bdot10k\|corine ...` (ADR-044) |
  | `kartograf landcover download --source soilgrids ...` | `kartograf soil download ...` (bez `--source`) |
  | `kartograf landcover list-layers --source soilgrids` | `kartograf soil list-layers` |
  | `kartograf soilgrids hsg ...` | `kartograf soil hsg ...` |
  | `kartograf parse`, `kartograf cache` | bez zmian |

  Nowe: `kartograf <grupa> list-sources` w kazdej grupie danych; brak `--product`
  daje komunikat z produktami tylko tej grupy; `--sheet` i `--year` maja
  w kazdej grupie danych jedna definicje (ADR-039 D4, D5). Biblioteka, sidecar
  i uklad `data/` bez zmian. Python: `kartograf.cli.commands` nie ma
  `cmd_landcover` ani `cmd_soilgrids`, `parse_bbox_arg` jest w
  `kartograf.cli._args`. Co zrobic: w skryptach zamien komendy wg tabeli
  (`--product orto` -> `imagery download`, pozostale produkty ->
  `elevation download`, SoilGrids -> `soil`); kod Python uzywajacy
  funkcji biblioteki nie wymaga zmian.
- NMT i NMPT PL z rejestru wariantow (ADR-041, plan A): rozdzielczosci,
  uklady wysokosci i formaty zna jeden rejestr `kartograf.sources.variants`
  (walidacja CLI i API, `--help`, `list-sources`, segment magazynu, wybor
  rekordu skorowidza); NMPT ma siatki 0.5m, 0.6m i 1m.
  - `elevation download --product nmpt` wymaga `--resolution`;
    `GugikNmptProvider(session=None, *, vertical_crs, resolution,
    format="ASC", cache=None)` - `resolution` bez wartosci domyslnej. Co
    zrobic: dopisz `--resolution 1m` / `resolution="1m"`; dotychczasowe dane
    NMPT 1 m zostaja w segmencie `nmpt/pl_<uklad>_1m_<vcrs>` (klucz
    `pl.gugik.nmpt`).
  - Usuniete bez aliasow: `kartograf.providers.pl.nmt_vertical_crs`,
    `require_nmt_vertical_crs`, `NMT_5M_VERTICAL_CRS`,
    `GugikProvider.SUPPORTED_RESOLUTIONS`, `SUPPORTED_VERTICAL_CRS`,
    `SUPPORTED_VERTICAL_CRS_5M`, `get_supported_resolutions()`,
    `get_supported_vertical_crs_for_resolution()`,
    `GugikNmptProvider.SUPPORTED_RESOLUTIONS`,
    `FileStorage.SUPPORTED_RESOLUTIONS`, `GugikLazProvider.WFS_ENDPOINTS`
    oraz `WMS_SKOROWIDZE_ENDPOINTS` (`GugikProvider`, `GugikNmptProvider`).
    Co zrobic: warianty z `kartograf.sources.variants.variants(product=,
    country=, vertical_crs=, resolution=, system=, format=)` (pola `label`,
    `vertical_crs`, `format`, `source`, `index_ref.endpoint`);
    `GugikProvider.is_wcs_available()` zostaje.
  - Skorowidz arkuszy NMT/NMPT czytany z WFS GUGiK (ten sam indeks co raport
    dostepnosci i LAZ) zamiast WMS GetFeatureInfo; rekord musi miec format
    wariantu w polu `format` i w koncowce URL. Sidecar nowych arkuszy:
    `extra.source.index_url` = adres uslugi WFS, `extra.source.layer` = typ
    WFS (`SkorowidzNMT2025` zamiast warstwy WMS `SkorowidzeNMT2025`); pliki,
    segmenty i sygnal swiezosci (`index`) istniejacych danych bez zmian.
    Co zrobic: nic; skrypty porownujace `extra.source.layer` z nazwa warstwy
    WMS - nowa nazwa.
- Tryb wycinka jest jawny, a nazwy ukladow opisuja ich role (ADR-038,
  bez aliasow). CLI: `--target-crs X` -> `--cutout --horizontal-crs X`
  (`--cutout` wlacza jeden wycinek zamiast arkuszy, `--horizontal-crs` jest
  z nim wymagane, bez `--cutout` to `Error:`), `--system` -> `--sheet-system`.
  Obszar CZ (`--bbox`/`--geometry`, takze czesc CZ pod `--country auto`)
  wymaga `--cutout --horizontal-crs`, natywnie `--horizontal-crs EPSG:5514`
  (dotad wycinek CZ powstawal bez flagi). Pod `auto` obszar PL+CZ nie daje
  juz arkuszy PL obok wycinka CZ: z `--cutout` czesc PL jest wycinkiem WCS
  (tylko 1 m, bez kampanii), arkusze PL daje `--country pl`; `Notice`
  `campaign_opts_pl_only` usuniety (opcje kampanii pod `auto` z CZ to
  teraz `Error:`). Biblioteka: `download_data`/`check_data(...,
  sheet_system=, cutout=False, horizontal_crs=None)` zamiast `system=`,
  `target_crs=`; `download_pl_cutout`/`check_pl_cutout`/`download_cz_cutout`/
  `check_cz_cutout(..., horizontal_crs=)`, `create_cz_raster_provider`/
  `CuzkRasterProvider(horizontal_crs=)`; `SheetParser(sheet, sheet_system=)`
  i `SheetParser.sheet_system`, `find_sheets_for_bbox(...,
  sheet_system)`, `find_sheets_for_geometry(..., sheet_system=)`;
  `SUPPORTED_TARGET_CRS` -> `CUTOUT_CRS`. Podpowiedz braku pokrycia mowi
  `--sheet-system`; wpis cache z podpowiedzia `--system` jest
  odswiezany. Sidecar bez zmian. Co zrobic: w skryptach zamien flagi,
  dopisz `--cutout --horizontal-crs EPSG:5514` do pobran obszaru CZ; w
  kodzie zamien nazwy argumentow i dopisz `cutout=True` przy
  `download_data(horizontal_crs=...)`.
- `DownloadManager.download_sheet`, `download_hierarchy` i
  `download_sheets` zwracaja teraz `DownloadResult` zamiast sciezki lub listy
  sciezek. `result.files[godlo]` zawiera krotke `VersionedFile` (m.in. `path`,
  `version_path`, `label`, `status`), a `result.stale` i `result.notices`
  przekazuja nieaktualne pozycje planu i komunikaty o danych.
  `check_updates(manager, sheets)` -> `manager.check_sheets(sheets)`;
  `upgrade(manager, plan)` -> `manager.download_sheets(sheets, update="upgrade",
  plan=plan)`. Usunieto `last_result`, `last_sheet`, `UpgradeReport` oraz
  eksport `SheetFetch`; `max_workers=` menedzera -> `workers=`, dodano
  `year=` i `on_notice=`. Co zrobic: korzystaj z wartosci zwroconej,
  aktualizuj wywolania metod i odczyty plikow z `result.files`, a komunikaty
  wypisuj z `on_notice` bez ponownego przetwarzania `result.notices`.
- Cache metadanych (Z6, ADR-037): funkcje publiczne (`download_data`,
  `check_data`, tory `download_*`/`check_*`, `download_landcover`/
  `check_landcover`, `download_soil`/`check_soil`, `calculate_hsg`/
  `check_hsg`) przyjmuja `cache: MetadataCache | bool = True` -
  domyslnie ten sam plik co CLI (`<cwd>/.kartograf_cache.db`), dotad
  biblioteka pracowala bez cache. `update="force"` pomija odczyty z cache
  (jak `--force`). Co zrobic: proces w katalogu bez prawa zapisu albo
  testy bez stanu - `cache=False`; wlasny plik - `cache=MetadataCache(...)`.
- Wycinek PL: `download_pl_cutout(*, bbox, horizontal_crs, ...)` i
  `check_pl_cutout(*, bbox, horizontal_crs, ...)` przyjmuja te same
  argumenty wyboru (wszystkie tylko nazwane), `download_pl_cutout` dostaje
  `plan=`, `cache=` (`True` = domyslny cache w cwd) i `on_notice=`;
  `PlCutoutResult.notices` niesie komunikaty o rozmiarze wycinka
  (`cutout_size`, przed pierwszym zapytaniem WCS) i wycinku bez danych
  (`all_nodata`). `prepare_pl_cutout` i `run_pl_wcs_cutout` usunieto,
  `PlCutout` jest krokiem wewnetrznym (poza `__all__`).
  Co zrobic: podawaj `bbox=` i `horizontal_crs=` nazwane;
  `check_pl_cutout(cutout)` -> `check_pl_cutout(bbox=bbox,
  horizontal_crs=..., output_dir=..., vertical_crs=..., product=...)`; plan
  wykonuj przez `download_pl_cutout(..., plan=plan)`.
- CZ: arkusz CZ ma publiczne API `download_cz_sheet(*, sheet, output_dir,
  product, vertical_crs, resolution=None, update, plan, cache, on_notice)`
  i `check_cz_sheet` z tymi samymi argumentami (`CzSheetResult`; arkusz SM5
  tylko NMT `5m` / NMPT `0.5m`, kafel TM33 wymaga etykiety; errata decyzji
  9 planu 2/3, `product` - plan B).
  `check_cz_cutout(*, bbox, output_dir, product, horizontal_crs,
  vertical_crs, resolution)` przyjmuje argumenty `download_cz_cutout` (bez providera
  i `image_crs`); `download_cz_cutout` dostaje `plan=`, `on_notice=`,
  `cache=True` (domyslny cache w cwd). Wyniki CZ maja `notices`
  (`all_nodata` zamiast ostrzezenia w logu). `run_cz_cutout` poza API.
  Co zrobic: `run_cz_cutout(provider, bbox, ...)` ->
  `download_cz_cutout(bbox=bbox, product="nmt", ...)`;
  `check_cz_cutout(provider, bbox, output_dir=, image_crs=)` ->
  `check_cz_cutout(bbox=bbox, output_dir=, product="nmt", horizontal_crs=,
  vertical_crs=, resolution=)`.
- CZ z rejestru wariantow (ADR-041, plan B): `CuzkDmrProvider`
  i `create_dmr_provider` usuniete bez aliasow - w ich miejsce
  `CuzkRasterProvider(product, resolution, session=None, cache=None,
  horizontal_crs=None, *, vertical_crs)` i `create_cz_raster_provider` z ta
  sama sygnatura (`product` = `"nmt"`|`"nmpt"`, model z rejestru:
  NMT `2m` DMR 5G / `5m` DMR 4G, NMPT `0.5m` DMP OK / `2m` DMP 1G);
  `sm5_signal(sheet)` -> `file_signal(sheet)` (plik SM5 i kafla TM33).
  `download_cz_sheet`/`check_cz_sheet`/`download_cz_cutout`/
  `check_cz_cutout` wymagaja `product=`. `GugikLazProvider.download(url,
  ...)` -> `download_tile(url, ...)` (A5-7: `download` providera przyjmuje
  godlo). Kafel TM33 DMR 4G z `--vertical-crs EVRF2007` to gotowy plik
  ETRS89 CUZK (EPSG:3045, bez warpu i operacji pionowej, sygnal `http`);
  wersja z warpu zapisana w magazynie przed ta zmiana zostaje lokalna
  z `Info:` (niesprawdzona; plik 0.7.x w sciezce standardowej jest
  zastepowany przy pierwszym pobraniu). `--country auto` z `--product nmpt`
  nie zaweza sie juz do PL (CZ ma NMPT): obszar PL+CZ z `--resolution
  0.5m` (DMP OK) wymaga `--cutout`, a wycinek PL ma tylko 1 m. Co zrobic:
  `CuzkDmrProvider(res, ...)`/`create_dmr_provider(res, ...)` ->
  `CuzkRasterProvider("nmt", res, ...)`/`create_cz_raster_provider("nmt",
  res, ...)`, `sm5_signal` -> `file_signal`; dopisz `product="nmt"` w torach
  CZ; `GugikLazProvider.download` -> `download_tile`; kafle TM33 DMR 4G
  EVRF2007 z magazynu sprzed tej zmiany odswiez `--force`; arkusze NMPT PL
  0.5m przy granicy pobieraj z `--country pl`.
- LAZ: `download_laz_area` przyjmuje `bbox` w dowolnym obslugiwanym CRS
  (uklady CZ tylko przez przypieta operacje), `plan=`, `cache=True`,
  `on_notice=` (`laz_superseded` zamiast wypisywania przez CLI) i
  `workers=` zamiast `max_workers=`; nowy blizniak `check_laz_area` z tymi
  samymi argumentami. `on_progress` dostaje `(0, total)` przed pierwszym
  kaflem. `run_laz_download` i `check_laz_updates` poza API. Co zrobic:
  `max_workers=` -> `workers=`; `check_laz_updates(selection, ...)` ->
  `check_laz_area(bbox=bbox, output_dir=..., vertical_crs=..., ...)`; plan
  wykonuj przez `download_laz_area(..., update="upgrade", plan=plan)`.
- CLI `elevation download` i `imagery download` tylko tlumacza flagi na
  `download_data`/`check_data` (opis w Dodane): bledy wejscia to
  `ValidationError` z tekstem jak w CLI, komunikaty o danych
  (`Info:`/`Warning:`) powstaja w bibliotece jako `Notice` (m.in.
  przyciecie `auto`, brak pokrycia, dowiazania spoza zakresu); stopnie
  w komunikatach przyciecia jako `st.N`/`st.E` (ASCII). W podsumowaniu
  `bledy:` liczy nieudane czesci zadania (arkusze bez danych GUGiK to
  `Warning:`, nie blad). Co zrobic: skrypty dopasowujace wyjscie CLI -
  nowe teksty; skrypty wolajace CLI przez `subprocess` moga przejsc na
  `download_data` z tymi samymi wartosciami (`resolution={"pl": "1m",
  "cz": "2m"}` zamiast `pl=1m,cz=2m`).
- `kartograf landcover download` i `kartograf soil hsg`: brak albo kilka
  wyborow obszaru to blad biblioteki `Podaj dokladnie jeden wybor: ...`
  (land cover/HSG) lub `Podaj wybor obszaru: ...` /
  `Podaj dokladnie jeden wybor obszaru: ...` (`download_data`) zamiast
  angielskich komunikatow; nowe flagi tych komend - Dodane. Co zrobic:
  patrz Jezyk (Z5) nizej.
- Sidecar: wspolrzedne `request.bbox` i `extra.parent_request.bbox` zawsze
  jako liczby zmiennoprzecinkowe (`770000.0`), takze dla `BBox` z liczb
  calkowitych - ten sam plik z CLI i z biblioteki. Co zrobic: nic
  (porownanie wartosci liczbowych bez zmian); porownania tekstowe sidecarow
  musza przyjac zapis `.0`.
- Jezyk (Z5): pomoc wszystkich komend, komunikaty CLI, teksty `Notice`
  i bledow `KartografError` po polsku i wylacznie w ASCII. Zmienione m.in.:
  `Invalid bbox format` -> `Nieprawidlowy bbox`, `Must provide one of` /
  `Specify only one of` -> `Podaj wybor obszaru` /
  `Podaj dokladnie jeden wybor obszaru` (`download_data`),
  `File not found` -> `Brak pliku`, `Unsupported ...`/`Invalid ...` ->
  `Nieobslugiwany ...`/`Nieprawidlowy ...`, `Found N sheets ...` ->
  `Znaleziono arkuszy w skali ...`, `Downloading ...` -> `Pobieranie ...`;
  etykiety tych linii `(resolution: 1m)`, `(CZ, resolution: 5m)`,
  `(product: orto)`, `(format: TTN, resolution: -)` -> `(rozdzielczosc:
  1m)`, `(CZ, rozdzielczosc: 5m)`, `(produkt: orto)`, `(format: TTN,
  rozdzielczosc: -)`, hierarchia `Pobieranie 25 arkuszy z 7.171.21 to
  1:2000` -> `... z 7.171.21 w skali 1:2000`, `Pobieranie CZ bbox (2m,
  EPSG:5514)` -> `Pobieranie wycinka CZ (rozdzielczosc: 2m, EPSG:5514)`
  (testy na zywo 2026-10-16/17);
  wyjscie `parse` (`Godlo:`, `Skala:`, `Uklad:`, `Czlony:`, `Hierarchia`,
  `Arkusze potomne`), `cache stats` (`Wpisy rekordow:` ...), komunikaty
  `sheet_parser` bez polskich znakow (`Nieprawidlowe godlo`), opisy warstw
  BDOT10k (`Tereny lesne`), `metavar` (`GODLO`, `KATALOG`, `PLIK`, `ROK`,
  `NAZWA`, `KOD`, `SKALA`); ikony paska postepu ASCII: `>` pobieranie,
  `+` pobrano, `o` pominieto, `x` blad, `0` brak danych (bylo `↓ ✓ ○ ✗ ∅`).
  Co zrobic: skrypty dopasowujace teksty CLI albo `str(wyjatek)` - nowe
  brzmienie; lepiej typ wyjatku (`ValidationError`) i kod wyjscia.

- Biblioteka: bledne wartosci wejscia providerow, magazynu, wycinka LAZ
  i skali docelowej arkuszy zglaszaja `ValidationError` (podklasa
  `KartografError`), a nie `ValueError`; CLI nie przechwytuje juz
  `ValueError` jako bledu uzytkownika. Co zrobic: zmien
  `except ValueError` na `except ValidationError` dla bledow argumentow;
  nie obejmuj nim bledow wewnetrznych niezmiennikow programu.
- Usunieto arkuszowy tor wycinkow PL: `PlCutoutSheets`,
  `select_pl_cutout_sheets`, `run_pl_cutout`, `build_pl_cutout`,
  `build_cutout_from_sheets` oraz powiazane funkcje do estymacji miejsca,
  zapisu sidecara i odtwarzania pominietych wycinkow. `PlCutoutResult`
  nie zawiera juz pol arkuszowych (`sheet_paths`, `missing_sheets`,
  `off_grid_sheets`, `partial_sheets`, `unverified`). Co zrobic:
  dla wycinka NMT/NMPT 1 m uzyj `download_pl_cutout`; dla mozaiki arkuszy
  pobierz arkusze osobno i scal je samodzielnie przez `mosaic_and_crop`.
- `download_pl_cutout` nie przyjmuje juz ignorowanych parametrow
  `geometry`, `layer`, `scale`, `max_workers`, `force`, `on_progress`;
  `cache` zostal przywrocony jako parametr wspolnego cache metadanych.
  Co zrobic: przekaz obwiednie geometrii jako `bbox`; wybor
  arkuszy, kampanii i 5 m realizuj przez pobieranie arkuszy bez
  `--cutout`.
- `mosaic_and_crop` nie przyjmuje juz `snap_to_source_grid` ani
  `assign_crs`; `dtype=` i owijanie zrodel w VRT pozostaja. Co zrobic:
  sprawdz siatke przez `check_source_grid`, a w razie potrzeby
  wyrownaj obszar i przelicz rastry we wlasnym kodzie; CRS zrodel
  przygotuj przed scaleniem, bez przypisywania go przez mozaike.
- `GridMismatchError` usuniety z `kartograf` i `kartograf.exceptions` —
  zglaszal go tylko usuniety tor arkuszowy (EPSG:2180 z arkuszy o roznej
  fazie siatki). Co zrobic: usun obsluge tego wyjatku; faze siatki
  wlasnych zrodel sprawdza `check_source_grid(...).off_grid`.
- CLI: godlo podaje sie flaga `--sheet` (ADR-031 errata 1, bez aliasow):
  `kartograf download N-34-130-D-d-2-4` (0.7.x) -> `kartograf elevation
  download --sheet N-34-130-D-d-2-4 ...` (ortofotomapa: `imagery
  download`; takze godla PL-2000 i CZ, np. `--sheet 302_5550`);
  `landcover download --godlo` -> `--sheet`, `soilgrids hsg --godlo` ->
  `soil hsg --sheet`. `kartograf parse` przyjmuje godlo pozycyjnie jak
  dotad (w pomocy: `GODLO`). Co zrobic: dopisz `--sheet` przed godlem
  (nazwy komend: tabela grup wyzej), zamien `--godlo` na `--sheet`.
- Biblioteka: polskie identyfikatory publicznego API zastapione
  angielskimi, bez aliasow (ADR-031 errata 1). `godlo` -> `sheet`,
  `godla` -> `sheets` we wszystkich parametrach i atrybutach (m.in.
  `SheetParser.sheet`, `DownloadProgress.sheet`,
  `LazTile.sheet`, `DownloadError.sheet`/`NoCoverageError.sheet`,
  `DownloadManager.download_sheet(sheet)`, `check_year_range(sheets)`,
  `MetadataCache.get_record(..., sheet)`, `LandCoverManager.download(sheet=)`,
  `download_all_counties(sheet=)`); metody `download_by_godlo` ->
  `download_by_sheet` (`LandCoverManager`, `LandCoverProvider`,
  `Bdot10kProvider`, `CorineProvider`, `SoilGridsProvider`),
  `HSGCalculator.calculate_hsg_by_godlo` -> `calculate_hsg_by_sheet`,
  `BaseProvider.validate_godlo` -> `validate_sheet`,
  `horizontal_crs_for_godlo` -> `horizontal_crs_for_sheet`. `uklad` ->
  `system` (`Parser2000.system`, `ParserTM33.system`, `LazTile.system`,
  `FileStorage.get_raw_path(..., system=)`,
  `SourceDescriptor.resolve_subdir(system=)`, szablon segmentu `{system}`
  zamiast `{uklad}`), w `SheetParser` `sheet_system` (`SheetParser(sheet,
  sheet_system=)`, `.sheet_system`, ADR-038), `SheetParser.VALID_UKLADY` ->
  `VALID_SYSTEMS`, `CampaignRef.zgloszenie` -> `survey_work_id`,
  `GugikOrtoProvider.WMS_SKOROWIDZE_ENDPOINT` -> `WMS_INDEX_ENDPOINT`
  (`WMS_SKOROWIDZE_ENDPOINTS` NMT i NMPT usuniete - wpis o rejestrze
  wariantow wyzej). Co zrobic: zamien nazwy w wywolaniach i odczytach
  atrybutow.
  Klucze sidecara i wartosci (godla) bez zmian.
- CLI i biblioteka: `--campaigns {newest,all}` oraz parametr
  `campaigns="newest"|"all"` zastapiono przelacznikiem `--all-campaigns`
  i parametrem `all_campaigns: bool = False` (arkusze PL i LAZ).
  Domyslnie pobierany jest najnowszy lot; przelacznik wybiera wszystkie
  loty w zakresie lat. Model A i tekstowe wartosci `request.campaigns`
  w sidecarze (`"newest"`/`"all"`) pozostaja bez zmian (parametr
  `FileStorage.list_files(campaigns=)` — patrz magazyn wersjonowany nizej).
  Co zrobic: `--campaigns all` zamien na `--all-campaigns`,
  `--campaigns newest` usun; `campaigns="all"` zamien na
  `all_campaigns=True`, a `campaigns="newest"` usun lub zamien na
  `all_campaigns=False`; wlasciwosc `DownloadManager.campaigns` ->
  `DownloadManager.all_campaigns` (bool).
- Bez wartosci domyslnych wplywajacych na dane (CLI i API; DEVELOPMENT_STANDARDS
  11.2, ADR-004 errata 1, ADR-023 errata 2). Brak wartosci: CLI `Error:`
  z lista dopuszczalnych wartosci (kod 1, przed siecia); API:
  `TypeError` dla wymaganych argumentow sygnatury, `ValidationError`
  dla brakujacych opcji warunkowych (m.in. `year` CORINE, `depth` HSG).
  - CLI `elevation download` i `imagery download`: wymagane `--product`
    (elevation: nmt|nmpt|laz|contours; imagery: orto|intensity|true-orto|
    oblique-orto), `--output`,
    `--country` z `--bbox`/`--geometry` (pl|cz|auto; z `--sheet` kraj
    z godla), `--vertical-crs` dla nmt/nmpt/laz (PL EVRF2007|KRON86, CZ
    Bpv|EVRF2007), `--resolution` dla NMT i NMPT tam, gdzie jest wybor (PL:
    etykiety rejestru wariantow, np. 0.5m|1m|5m - wpis o rejestrze wyzej;
    CZ TM33 i obszar: NMT 2m|5m, NMPT 0.5m|2m; wycinek `--cutout` i arkusz SM5 maja
    jedna wartosc i moga ja pominac), `--sheet-system` dla PL
    `--bbox`/`--geometry` bez `--cutout` (1992|2000), `--horizontal-crs`
    z `--cutout`. `--resolution` i `--vertical-crs`
    przyjmuja jedna wartosc albo pary per kraj (`pl=1m,cz=2m`,
    `pl=EVRF2007,cz=Bpv`); jedna wartosc musi pasowac kazdemu krajowi
    zadania. `--scale`: PL-1992 zawsze 1:10000 — `--scale` z zadaniem
    PL-1992 to `Error:`; PL-2000 wymaga `--scale` (1:5000|1:2000|1:1000|1:500)
    z `--bbox`/`--geometry --sheet-system 2000` i z godlem 1:10000. Zniknal
    `Info:` o roznych domyslnych ukladach wysokosci czesci PL i CZ;
    `--sheet-system` nie
    przelacza juz `--country auto` na PL. Podpowiedz braku pokrycia dla
    PL-1992 nie podaje `--scale`.
  - CLI `landcover download`: wymagane `--product` (w 0.7.x `--source`),
    `--output`, `--year` (corine); `landcover list-layers --product`;
    `soil download`: `--property`/`--depth`/`--stat`; `soil hsg`:
    `--output` i `--depth`.
    Dla BDOT10k `--format` domyslnie wybiera `GPKG` (bez `--year`); dla
    innych zrodel jest bledem.
  - API: `DownloadManager(output_dir, provider, *, ...)` — oba wymagane,
    parametry `vertical_crs` i `resolution` usuniete (decyduje provider);
    `FileStorage(output_dir, *, resolution, vertical_crs, ...)`, metody
    `get_path/exists/delete/get_full_sheet_path/get_campaign_path/get_size/
    write_atomic` z wymaganym `ext`, `list_files(pattern, *, versions=False)`;
    `MetadataCache(db_path, ...)`; `GugikProvider(*, vertical_crs, resolution)`,
    `GugikNmptProvider(*, vertical_crs, resolution)`, `GugikLazProvider(*, vertical_crs)`,
    `GugikOrtoProvider(*, color)`, `create_nmt_provider(vertical_crs,
    resolution)`, `CuzkRasterProvider(product, resolution, ...,
    *, vertical_crs)`, `create_cz_raster_provider(product, resolution,
    ..., *, vertical_crs)`;
    `download_pl_cutout(*, bbox, horizontal_crs, output_dir,
    vertical_crs, product)` — parametr `resolution` usuniety (wycinek tylko
    1 m), a `prepare_pl_cutout` usuniety; `download_laz_area(*, bbox,
    output_dir, vertical_crs, ...)`; wewnetrzny `run_laz_download` usuniety;
    `find_sheets_for_bbox(bbox, target_scale, sheet_system)`,
    `find_sheets_2000_for_bbox(bbox, target_scale)`,
    `find_sheets_for_geometry(filepath, target_scale, ..., *, sheet_system)`;
    `download_landcover(product=..., output_dir=...)`,
    `download_soil(output_dir=..., property=..., depth=..., stat=...)`;
    `CorineProvider.download_by_bbox/download_by_sheet(..., *, year)`;
    `SoilGridsProvider.download_by_bbox(..., *, property, depth, stat)`;
    `calculate_hsg(output_dir=..., depth=..., ...)`.
  Co zrobic: podaj jawnie wartosci, ktore dotad byly domyslne (CLI: `--product
  nmt -o ./data --resolution 1m --vertical-crs EVRF2007`, z obszarem
  `--country pl --sheet-system 1992`; CZ `--resolution 2m --vertical-crs Bpv`;
  pogranicze `--resolution pl=1m,cz=2m --vertical-crs pl=EVRF2007,cz=Bpv`;
  usun `--scale` z zadan PL-1992). Biblioteka: przekaz provider
  i katalog do `DownloadManager`, `product` i `output_dir` do
  `download_landcover`, sciezke do `MetadataCache` (CLI uzywa
  `.kartograf_cache.db` w katalogu biezacym).
- Magazyn wersjonowany dla arkuszy PL NMT/NMPT/orto (ADR-036;
  spec `docs/superpowers/specs/2026-10-08-versioned-store-design.md`):
  - Uklad: `<segment>/kampanie/<data>_<id>/...` -> `<segment>/versions/<hierarchia>/<data>_<id>_<sha8>/<godlo>.<ext>`
    (wersja niezmienna, sidecar pisany raz). Brak migracji: `kampanie/`
    nie jest czytany (CLI drukuje raz `Info:`). Co zrobic: pobierz dane
    ponownie (np. tym samym poleceniem); stary katalog `kampanie/` mozna
    usunac recznie.
  - Tryb domyslny nie pobiera juz automatycznie nowszej kampanii przy
    `newest`: zostaje lokalna wersja, a CLI dopisuje `; dostepna nowsza
    <etykieta> (--upgrade)` i `Info:` (`DownloadResult.newer`). Co zrobic:
    `--upgrade` / `update="upgrade"`, gdy chcesz nowsza kampanie.
  - `--force` pobiera ponownie i odswieza cache metadanych, ale niczego
    nie nadpisuje: ta sama tresc = `bez zmian`, inna = nowa wersja obok
    starej. `--force`, `--upgrade` i `--check-updates` wykluczaja sie.
    Co zrobic: nie lacz `--force`, `--upgrade` i `--check-updates`.
  - Biblioteka: `download_sheet/download_hierarchy/download_sheets(...,
    skip_existing=)` -> `update: None | "upgrade" | "force"`. Co zrobic:
    `skip_existing=False` zamien na `update="force"`, `skip_existing=True`
    usun.
  - Hardlinki wymagane: sciezka standardowa i `full_sheet/` to wylacznie
    dowiazania twarde do wersji; kopia zamiast hardlinku znika (system
    plikow bez hardlinkow = blad arkusza). `SheetFetch.link`,
    `DownloadResult.copied` i CLI `Warning: hardlink niedostepny ...`
    usuniete. Co zrobic: trzymaj dane na ext4/NTFS/SMB; kopiuj magazyn
    przez `rsync -aH`.
  - `extra.parent_requests` usuniete (sidecar wersji jest niezmienny;
    `parent_request` = zadanie, ktore utworzylo wersje). `extra.coverage`
    liczone przy zapisie dla kazdego lotu niepelnego, nigdy dopisywane;
    lot pelny nie ma pomiaru. Co zrobic: grupuj pliki zadania po
    `parent_request`.
  - `FileStorage.get_campaign_path` usuniete, `list_files(campaigns=)` ->
    `list_files(versions=)` (True = pliki wersji). Co zrobic: wersje
    arkusza czytaj z `FileStorage.get_versions_root(sheet)` albo
    `list_files(..., versions=True)`.
  - Provider bez kampanii (atrapy, obce providery): plik tez jest wersja
    (etykieta = data pobrania UTC); jego sidecar jest obowiazkowy (bez
    deskryptora: sidecar okrojony), porazka zapisu = blad arkusza. Co
    zrobic: nic.
  - CLI (`elevation download`, `imagery download`): zamiast `Downloaded to`,
    `Skipped ... already exists` i `Downloaded
    N files ...` jedna linia na plik (`<godlo>: nowa wersja
    <etykieta>_<sha8>` / `nowa etykieta ... (plik identyczny z
    <etykieta>)` / `bez zmian
    ...` / `lokalna wersja ...`) i podsumowanie `Nowe: N, nowa etykieta:
    N, bez zmian: N, lokalne: N, bledy: N`. Co zrobic: skrypty parsujace
    wyjscie przestaw na nowe linie albo na biblioteke.
  - Awaria skorowidza bez granicy roku: lokalna wersja dla kazdej
    strategii (dotad tylko `newest`); z granica roku gdy KAZDY arkusz ma
    lokalna wersje z zakresu — lokalne wersje z ostrzezeniem (dotad zawsze
    blad zadania). Tylko tryb domyslny. Co zrobic: nic.
- Magazyn wersjonowany dla LAZ, arkuszy i wycinkow CZ oraz wycinkow PL
  z WCS (ADR-036):
  - LAZ: kafel = wersja w `laz/<segment>/versions/<hierarchia>/<data>_<zgloszenie>_<sha8>/<plik>.laz`,
    sciezka standardowa = hardlink, sidecar wersji obowiazkowy. Kafel
    z lokalna wersja nie jest pobierany ponownie; nowszy nalot (inne
    pliki) pobiera sie domyslnie (D26). `run_laz_download`/
    `download_laz_area(force=)` -> `update=None|"upgrade"|"force"`,
    `LazDownloadResult.downloaded`/`.skipped` -> `.files`
    (`VersionedFile`, status `new`/`unchanged`/`relabeled`/`local`) i
    `.stale`. Co zrobic: `force=True` zamien na `update="force"`, liczniki
    licz z `result.files` po `status`.
  - Arkusze CZ (TM33, SM5) i wycinek CZ: wersje w `<segment>/versions/`,
    `bbox/<wsp>.tif` i sciezka arkusza to hardlinki. SM5 zapisuje
    `ETag`/`Last-Modified` w `extra.http` i domyslnie robi jedno `HEAD`
    na plik z lokalna wersja (nowsza tresc tylko zglaszana, `--upgrade`
    pobiera). `run_cz_cutout`/`download_cz_cutout(force=)` -> `update=`,
    `CzCutoutResult.path`/`.skipped` -> `.file` (`VersionedFile`) i
    `.stale`. Co zrobic: `force=True` -> `update="force"`, sciezke czytaj
    z `result.file.path`, pominiecie z `result.file.status == "local"`.
  - Wycinek PL z WCS: `bbox/<wsp>.tif` bez daty w nazwie jest dowiazaniem
    do wersji w `versions/bbox/<RRRR-MM-DD>_<sha8>/`; domyslnie i przy
    `--upgrade` lokalna wersja bez zapytan PRG i WCS (dotad kazde
    wywolanie pobieralo), `--force` pobiera ponownie (ta sama tresc =
    bez zmian). Pliki `<wsp>_<RRRRMMDD>.tif` z 0.7.x nie sa rozpoznawane.
    `PlCutoutResult.path`/`.skipped` -> `.file` i `.stale`;
    `run_pl_wcs_cutout(today=)` -> `now=` (+ `update=`, `plan=`),
    `download_pl_cutout(..., update=)`; `dated_cutout_path` usuniete. Co
    zrobic: sciezke czytaj z `result.file.path`; ponowne pobranie tylko
    przez `update="force"`/`--force`; stare pliki z data usun recznie.
  - Stary zwykly plik 0.7.x w sciezce LAZ/CZ/wycinka jest zastepowany
    dowiazaniem do nowej wersji przy pierwszym pobraniu (D24). Co zrobic:
    nic (kopie poza magazynem nie sa ruszane).
  - `download_cz_cutout`, `download_cz_sheet`, `download_pl_cutout`: pole
    `file` wyniku jest `None` tylko z `plan=`, gdy plan nie wykonuje tego
    pliku i nie ma wersji lokalnej. Co zrobic: przy wykonaniu planu
    sprawdz `result.file is None`.
  - `PlanItem.sheet` -> `PlanItem.unit`, nowe pole `track` (`pl_sheet`,
    `laz_tile`, `cz_sheet`, `pl_cutout`, `cz_cutout`); `PlanItem`/
    `UpdatePlan` w `kartograf.download.plan` (eksport z `kartograf` bez
    zmian), `UpdateMode` w `kartograf.download.fetch`. Schemat planu
    zostaje `kartograf-plan/1`. Co zrobic: `item.sheet` -> `item.unit`;
    importy z `kartograf.download.updates`/`manager` przestaw na
    `kartograf`.
  - `DownloadManager.download_bbox` usuniete (D27, errata 2 ADR-003). Co
    zrobic: wycinek NMT/NMPT w magazynie — `download_pl_cutout(bbox=bbox,
    horizontal_crs="EPSG:2180", ...)`; surowy WCS (np. ortofotomapa)
    poza magazynem — `provider.download_bbox(bbox, path)`.
  - CLI `elevation download` (LAZ, CZ i wycinki): zamiast `Downloaded to ...`/`Skipped ...`
    jedna linia statusu na plik (`<arkusz|sciezka wycinka|plik LAZ>:
    nowa wersja ...` / `lokalna wersja ...`), dla LAZ podsumowanie
    licznikow; plik bez taniego sygnalu (TM33, wycinki) dostaje
    `(bez sprawdzania; --check-updates)`. Co zrobic: skrypty parsujace
    wyjscie przestaw na nowe linie.
  - Sidecar: `downloaded_at` z mikrosekundami (porzadek dwoch pobran
    w tej samej sekundzie). Co zrobic: parsery ISO 8601 bez zmian.
- Magazyn wersjonowany dla land cover i HSG (ADR-036 D29-D33):
  - Uklad: pliki `bdot10k_..._teryt_<T>.gpkg`, `corine_<rok>_sheet_<godlo>.png`,
    `soilgrids_<wl>_<gl>_<stat>_bbox_<wsp>.tif`, `hsg_<godlo>_<gl>.tif`
    -> segmenty spec 3.4 z wersjami: `landcover/pl_bdot10k_gpkg[_<warstwy>]/teryt/<T>.gpkg`
    (`keep_raw`: `landcover/pl_bdot10k_gpkg_zip/teryt/<T>.zip`, SHP:
    `landcover/pl_bdot10k_shp/teryt/<T>.zip`), `landcover/eu_corine_<rok>/...tif`
    (CLMS), `landcover/eu_corine_<rok>_preview/...png` (podglad WMS bez
    credentials), `soil/global_soilgrids_<wl>_<gl>_<stat>/...tif`,
    `hsg/global_soilgrids_<gl>_<stat>/...tif`; pod segmentem `teryt/<T>`,
    `bbox/<wsp>` (EPSG:2180, jak wycinki) albo hierarchia godla. Brak
    migracji. Co zrobic: pobierz ponownie do katalogu magazynu (`--output`)
    i czytaj sciezke z linii statusu / `report.files[0].file.path`; stare
    pliki usun recznie.
  - Land cover, SoilGrids i HSG pisza wylacznie do magazynu:
    `output_path` usuniety, `output_dir` wymagany, `keep_intermediate`
    usuniety (wejscia clay/sand/silt to wersje SoilGrids w magazynie).
    Wynik to raport `LandCoverReport`, `SoilReport` lub `HsgReport`
    (wewnetrzne dawne `LandCoverResult`/`LandCoverAreaResult`/`HsgResult`
    nie sa publiczne). Co zrobic: `download_landcover(product=...,
    output_dir=<korzen magazynu>, teryt=|sheet=|bbox=|geometry=)` bez
    `output_path`, pliki z `report.files`, surowy ZIP w `report.raw`;
    `calculate_hsg(output_dir=<korzen magazynu>, bbox=bbox, depth=...)`
    zwraca raster w `report.files[0].file`, wejscia w `report.inputs`.
    Plik poza magazynem: `provider.download_by_*(..., output_path)`
    albo `hsg_from_rasters`.
  - Land cover i SoilGrids nie pobieraja ponownie istniejacego pliku:
    tryb domyslny bierze lokalna wersje bez zapytania o wydanie; sygnal
    bez taniego sprawdzenia daje `(bez sprawdzania; --check-updates)`.
    `--check-updates`/`--upgrade` sprawdzaja wydanie SoilGrids i CORINE CLMS,
    `--upgrade` pobiera nowsza tresc. Nowe wersje sa etykietowane wydaniem
    (`2.0`, `V2020_20u1`), bez wydania nie powstaja. Co zrobic: ponowne
    pobranie — `--force` / `update="force"`, nowsze wydanie — `--upgrade`.
  - `download_landcover` nie przerywa na pierwszym bledzie powiatu:
    `LandCoverReport.failed` zawiera jego `UnitFailure`; CLI wypisuje
    `Error: <TERYT>: ...` dla kazdego bledu i konczy kodem 1. Co zrobic:
    sprawdzaj `report.failed` i `report.ok` zamiast lapac wyjatek pliku.
  - `extra.source.raw_file` (BDOT10k `keep_raw`) zastapione
    `extra.source_files` (`name`, `file` = sciezka wersji ZIP wzgledem
    `--output`, `sha256`). Sidecar HSG: `extra.source_files` z `file`,
    `sha256`, `label` wejsc; `request` = wybor (bez `bbox` przy arkuszu).
    Co zrobic: czytaj `extra.source_files[].file` (sciezka wzgledem
    `--output`) i `sha256` zamiast `extra.source.raw_file`.
  - CLI `landcover download` i `soil hsg`: zamiast `Downloaded to:` /
    `HSG raster saved to:` linia statusu na plik (sciezka wzgledem
    `--output`); `soil hsg --output` tylko katalog magazynu (`.tif` =
    `Error:`), `--keep-intermediate` usuniete. Co zrobic: skrypty parsujace
    wyjscie przestaw na linie statusu.
  - `SourceDescriptor.storage_subdir` jest zawsze `str` (land cover:
    prefiks segmentu); `CorineProvider.CLMS_DATASET_UIDS`/
    `CLMS_RASTER_DOWNLOAD_IDS` 2012/2006/2000 zmienione na identyfikatory
    z katalogu CLMS. Co zrobic: nic.
- Typy argumentow biblioteki sprawdzane na wejsciu, bez konwersji
  (STANDARDS 11.2, `kartograf/download/arguments.py`): `download_data`/
  `check_data`, `download_landcover`/`check_landcover` (takze `year`
  archiwum BDOT10k), `calculate_hsg`/`check_hsg`,
  `download_collection`/`check_collection`, `check_availability`,
  `DownloadManager` i `download_laz_area`/`check_laz_area` daja
  `ValidationError` przed siecia dla liczby podanej jako napis
  (`year="2018"`, `timeout="120"`, `workers="4"`, `min_density="10"`,
  `lod="1"`), liczby niecalkowitej lub `bool` tam, gdzie oczekiwano `int`
  (`year=2018.0`), przelacznika innego niz `True`/`False` (`cutout`,
  `all_campaigns`, `full_sheet`, `keep_raw`, `whole_country`, `force`),
  `timeout <= 0` i `layers` podanego jako napis (`"SWRS,PTWP"` byl czytany
  znak po znaku); `download_collection`/`check_collection`/
  `validate_collection_request` przyjmuja `teryt`, `sheet`, `ku`, `format`,
  `scale`, `sheet_system` i `network` tylko jako `str` (ADR-043 D5: kod
  podany liczba traci zera wiodace, np. `0208`). Dotad czesc z nich dzialala
  przypadkiem, czesc konczyla sie poznym `ValueError` z `urllib3` albo
  `TypeError`. Flagi CLI bez zmian. Co zrobic: przekazuj `int` (`timeout`
  takze `float`), `True`/`False`, kody jako `str` (`teryt="1261"`)
  i liste/krotke kodow (`layers=["SWRS", "PTWP"]`).
- Przeglad UX 0.8.0, pomoc CLI: `hydro download` nie ma `--workers`/`-w`
  (obszar to jeden GeoPackage, plik krajowy - jeden plik; flaga nic nie
  zmieniala); `--country` kolekcji oferuje tylko kraje produktow grupy
  i `auto` (`hydro`: `cz`, `auto`; `models3d`: `pl`, `auto`) - `hydro
  --country pl` i `models3d --country cz` to blad parsera (kod 2) zamiast
  bledu biblioteki. `list-sources` ma kolumne `KATALOG` (katalog plikow pod
  `--output`), a `WYBOR` - komplet wymaganych flag zrodla (`--country`
  takze dla PL w `elevation`/`imagery`, `--vertical-crs EVRF2007|KRON86`,
  `landcover --year` BDOO i CORINE; `soil`: `--property --depth --stat`).
  Co zrobic: usun `-w`/`--workers` z polecen `hydro download` (w projekcie:
  `project download --workers` dziala jak dotad); skrypty czytajace
  `list-sources` po kolumnach - uwzglednij `KATALOG` i nowe flagi `WYBOR`.
- Bledy wejscia koncza CLI kodem 2, nie 1 (interfejs dla agentow AI, ADR-046;
  dopisane do przygotowanego wydania 0.8.0 przed tagowaniem):
  `ValidationError`, `ParseError`, `UsageError` i blad skladni parsera (argparse
  konczyl sie 2 juz wczesniej). Kody wyjscia: 0 = ok, 1 = awaria zrodla, sieci
  albo dysku lub `ok: false`, 2 = bledne dane wejsciowe i uzycie, 130 = Ctrl-C.
  Handlery nie drukuja wlasnych `Error:` ani nie zwracaja 1 za brak `--output`,
  `--product` i podobne: zglaszaja `ValidationError` z `option`, a `main` je
  tlumaczy. Tekst bledow bez zmian poza trzema szczegolami: `Remedium:` pod
  bledem przeliczenia ukladow drukuje `main` dla kazdej komendy (dotad tylko
  `elevation`/`imagery download`), nieczytelny plik `--plan` to blad wejscia
  (`option: plan`, kod 2), a blad zapisu planu to `Error: <Typ>: <tekst>` (kod 1).
  Co zrobic: skrypty sprawdzajace `== 1` testuj `!= 0`; 2 oznacza "popraw dane
  wejsciowe", 1 - awarie albo `ok: false` (tabela kodow: USAGE 9.3).
- `AvailabilityReport.to_json()` i `UpdatePlan.to_json()` (plik `--plan`,
  `--check-updates --json`) maja `schema` jako pierwszy klucz (dotad ostatni);
  pole dataclass `schema` obu typow zastapila stala klasy (`AvailabilityReport(
  schema=...)` i `dataclasses.replace(plan, schema=...)` nie dzialaja);
  `UpdatePlan` dostal pola `notices` (komunikaty emitowane przy sprawdzeniu)
  i `ok` (dwa nowe klucze `kartograf-plan/1`), a `UpdatePlan.from_dict` odrzuca
  nieznany schemat. Plany zapisane przez 0.8.0-dev nadal sie wczytuja. Co
  zrobic: czytaj pliki JSON po kluczach, nie po pozycji; nie buduj tych
  raportow z `schema=`.
- `--json` wycisza `Info:` i `Warning:` na stderr: komunikaty sa w polu
  `notices` dokumentu, a `elevation availability --json` przestaje je powielac
  (stderr jest pusty poza wierszami ponowien HTTP). Co zrobic: agenci i skrypty
  czytajace stderr czytaja `notices` z dokumentu.
- Parser CLI powstaje z katalogu komend (`kartograf/catalog/commands/`): znikaja
  moduly `kartograf/cli/groups/*.py`, flagi w `cli/_args.py` oraz funkcje
  `download_task_arguments`, `_download_arguments`, `collection_task`,
  `area_task_arguments`, `landcover_task_arguments`,
  `soil_download_task_arguments` i `soil_hsg_task_arguments`;
  `kartograf.cli.commands` nie eksportuje `format_sheet_info`,
  `format_hierarchy`, `format_children` ani `format_descendants` (jest
  `format_sheet(describe_sheet(...))`), `cmd_cache` przyjmuje `action`, a
  `cmd_landcover_list_layers` i `cmd_soil_list_layers` zastapilo
  `cmd_list_layers`. Zostaja `create_parser`, `main`, `parse_command_line`,
  `removed_command_error` i `_subparsers` (fasada). Co zrobic: kod i testy
  importujace wnetrznosci CLI uzywaja `parse_command(...).options` albo
  `create_parser()`; reczny `argparse.Namespace` handlera musi niesc
  `_command_id`; nowa komenda to deklaracja w katalogu (STANDARDS 17.2).

### Dodane

- Interfejs dla agentow AI, dokumenty JSON (ADR-046, USAGE 9; dopisane do
  przygotowanego wydania 0.8.0 przed tagowaniem): `--json` w kazdej komendzie
  CLI (36 komend-lisci i `catalog`) - stdout to dokladnie jeden dokument
  `kartograf-<rodzaj>/1` (16 schematow, pierwszy klucz `schema`), bez paska
  postepu i linii statusu; blad to `kartograf-error/1` na stdout (takze blad
  skladni), stderr pusty. Dokumenty tworzy biblioteka: kazdy raport ma
  `to_dict()` i `to_json()` (mixin `Document` w `kartograf.serialization`, poza
  `__all__`), a CLI i serwer MCP je tylko drukuja; w obrebie `/1` zmiany sa
  addytywne. Nowe w `kartograf.__all__` (logika `parse`, `list-sources`,
  `list-layers` i `cache` przeniesiona z CLI do biblioteki): `describe_sheet`/
  `SheetInfo`, `find_sheets`/`SheetList`, `list_sources`/`SourceList`,
  `list_layers`/`LayerList`, `get_cache_info`, `get_cache_path` (nie otwiera
  bazy), `clear_cache`/`CacheInfo`, `describe_store`/`StoreOverview`,
  `list_store_entries`/`StoreEntries`, `read_store_sidecar`/`StoreSidecar`,
  `ErrorReport`/`error_report`.

- Stabilne kody bledow z podpowiedzia (ADR-046): kazdy `KartografError` ma
  `code` (snake_case, unikalny), `exit_code`, `hint` i `DETAIL_FIELDS`/
  `details()`; `ValidationError` niesie `option`, `options` i `allowed` (nazwa
  argumentu API, nie flaga); nowa klasa `UsageError` (podklasa `ValidationError`,
  atrybut `command`) to bledne uzycie komendy; `OSError` (brak, uprawnienia,
  odlaczony udzial) ma nowy kod `io_error`, a `KeyboardInterrupt` i inne wyjatki
  `interrupted` i `internal_error` (buduje je `error_report`). `hint` zawiera
  dozwolone wartosci i przyklad komendy z katalogu, a dla bledu z `options` (np. brak
  obszaru) flagi tych opcji i przyklad; plan innego magazynu to `ValidationError` z
  `option="plan"`. Jedna tabela kodow wyjscia
  i bledow: USAGE 9.3 (`tests/test_docs_tables.py` pilnuje jej rownosci z
  katalogiem). Atrybuty sa addytywne: `except ValidationError` lapie tez
  `UsageError`, konstruktory przyjmuja nowe argumenty tylko nazwane.

- Katalog komend (ADR-046): `kartograf catalog [GRUPA [KOMENDA]] [--params]
  [--json]` i `get_catalog(group=, command=, params=, tables=)`
  (`kartograf-catalog/1`): grupy, produkty, komendy, parametry (flaga, argument
  API, rodzaj, wymagalnosc, dozwolone wartosci, zaleznosci), ograniczenia i
  przyklady; domyslnie zwiezly przeglad (ok. 7,6 tys. znakow), reszta na
  zadanie (grupa, komenda, `--params`, `tables=True`). `data_commands()` zwraca
  12 komend danych; typy `Catalog`, `CommandInfo`, `ParamInfo`; `CommandInfo.check_tool`
  (widok `full`) wskazuje narzedzie MCP sprawdzajace komende (`check_updates` albo
  `project_check_updates`). Katalog jest
  jedynym zrodlem prawdy: z deklaracji w `kartograf/catalog/commands/` powstaja
  parser CLI, opcje komend danych projektu i schematy narzedzi MCP, a testy
  kontraktowe pilnuja zgodnosci flag, sygnatur, `COMMANDS` i przykladow.

- Warstwa komend dla Archiwisty (KB-2..KB-5, ADR-046): `parse_command`,
  `validate_command`, `format_command`, `run_command`, `check_command` i
  `CommandCall` - komenda danych jako dane (opcje w postaci JSON opcji zadania
  projektu), walidacja bez sieci i zapisu, wykonanie funkcja komendy i sprawdzenie
  aktualnosci. `parse_command` przyjmuje tez wiersz z poczatkowym `kartograf ` (tak, jak go
  pisze `format_command`).

- Serwer MCP `kartograf-mcp` (ADR-046, USAGE 9.6): opcjonalny extra
  `kartograf[mcp]` (`mcp>=2.3.0,<3`, stdio, takze `python -m kartograf.mcp_server`),
  29 narzedzi 1:1 z komendami katalogu i jedno `check_updates` dla 12 komend danych;
  wynik narzedzia to dokument `--json`, `is_error` = kod wyjscia CLI != 0, schematy
  wejscia z katalogu, sciezki bezwzgledne, bez wartosci domyslnych wplywajacych na
  dane (`output_dir` jawny, `bbox` z `bbox_crs`), postep przez notyfikacje MCP,
  opcje `--tools`, `--allow-dir` (katalog bezwzgledny; wzgledny konczy start bledem uzycia,
  kod 2), `--cache-file`, `--no-cache` (katalog cache, ktorego nie
  da sie utworzyc, daje ostrzezenie i prace bez cache, jak w CLI); `tools/list` ma
  ok. 28,6 tys. znakow. `import kartograf` i CLI nie wymagaja `mcp`; `dev` zawiera
  `mcp`.

- Pliki dla agentow (ADR-046): `kartograf/py.typed` (PEP 561, `Typing :: Typed`;
  `mypy` konsumenta widzi typy biblioteki; cale publiczne API (`kartograf.__all__`)
  ma pelne, precyzyjne adnotacje - `PinnedTransform.transform` ma przeciazenia
  (skalary i tablice numpy), `cache` to `MetadataCache | None`, slowniki to
  `dict[str, Any]`, a `CampaignRef.from_record` przyjmuje protokol
  `IndexRecord`; sprawdza to `tests/test_typing_consumer.py`: `mypy --strict`
  na module konsumenta oraz przeglad `inspect`), `llms.txt` (spis dla agentow, format
  llmstxt.org), `scripts/gate.sh` (jedna komenda bramy: ruff check, ruff format
  --check, mypy, pytest offline; dziala tez z worktree), `python -m kartograf`
  oraz regula dla agentow z innych repozytoriow w `CLAUDE.md` (galaz od `develop`,
  bez merge, tagow i wpisow wydania bez zgody, przeglad przed tagiem).

- Publiczne API odczytu magazynu dla Archiwisty (KA-1..KA-6, ADR-045;
  dopisane do przygotowanego wydania 0.8.0 przed tagowaniem, ARCHITECTURE
  3.3.1): `list_segments` (segmenty `<produkt>/<wariant>`, takze
  nieznane), `iter_store` (strumieniowy skan wersji, obu rodzajow dowiazan
  i problemow; `segment`, `units` - tylko sloty podanych jednostek, bez
  listowania segmentu - i `skip_versions` - znane katalogi wersji bez
  czytania ich sidecarow, do skanu przyrostowego; jeden odczyt sidecara na
  plik, bez `stat` i bez otwierania plikow danych; wywolania rownolegle
  w watkach), `read_sidecar` (tolerancyjny odczyt starszych metadanych
  i kluczy 0.8.0-dev, rok danych nigdy z daty pobrania; blad:
  `InvalidSidecarError`; sidecar bez pola `schema` zapisany przez
  `emit_sidecar` dla providera bez deskryptora jest przyjmowany jak w
  `read_version`; `Sidecar.unit` pliku krajowego z motywem to
  `<kraj>_<motyw>`, np. `pl_miejscowosci`, czyli nazwa przyjmowana przez
  `iter_store(units=...)`), `describe_segment` (ludzka nazwa i zrodlo
  segmentu z rejestru, `known=False` bez zgadywania), `file_footprint`
  (obrys natywny i WGS84 z bboxa zadania, godla, naglowka albo jednostki;
  siec tylko po jawnym `network=True`; arkusz SM5 nieznany indeksowi nie
  ma obrysu, tak jak nieznany TERYT i KU), `link_target` (potwierdzenie celu
  takze na SMB bez stabilnych i-wezlow) i `pinned_transform` (operacja bez
  przyblizen, per watek). Typy `StoreEntry`, `Sidecar`, `SegmentInfo`,
  `Footprint`, `PinnedTransform` i wyjatek `InvalidSidecarError` sa
  w `kartograf.__all__`; `StoreEntry` i `Sidecar` sa niehashowalne. Funkcje nie zapisuja do magazynu; cache i indeks
  konsumenta naleza do jego lokalnego katalogu. Schemat `kartograf-meta/1`
  i uklad dotychczasowych plikow nie zmieniaja sie.
- Odczyt magazynu: rownolegle czesci jednego segmentu i szybszy skan
  (ADR-045, ARCHITECTURE 3.3.1; pomiar Archiwisty v0.1 - najwiekszy segment
  czytany jednym watkiem). `list_partitions(output_dir, segment, *,
  target=32)` dzieli segment na rozlaczne czesci: `"."` (poziom segmentu:
  jego problemy i pliki bezposrednio w nim i w `full_sheet/`),
  `"<katalog>[/<katalog>...]"` (slot i wszystkie sloty pod nim - w sciezce
  standardowej, `full_sheet/` i `versions/`) i `"<katalog>/."` (sam slot
  katalogu dzielonego dalej); `iter_store(..., segment=..., partition=...)`
  czyta jedna czesc, a suma czesci to dokladnie skan segmentu (bez
  powtorzen; czesci w osobnych watkach). `skip_versions` przyjmuje tez
  mapowanie `katalog wersji -> nazwy plikow danych`: taki katalog nie jest
  nawet listowany, wywolujacy reczy za jego zawartosc (zbior dziala jak
  dotad). Skan bez `pathlib` w petli i z tanszym typowaniem sidecara -
  magazyn testowy Archiwisty (50 tys. slotow, SSD): skan przyrostowy 12,4
  -> 6,3 s (z mapowaniem 5,2 s), pelny 20,3 -> 10,1 s, wynik bez zmian
  z jednym zamierzonym wyjatkiem: skan `units` pomija ukryte katalogi wersji
  (`.<etykieta>_<sha8>`) tak jak pelny skan (wczesniej je czytal).

- Odczyt magazynu - zapisane gwarancje dla konsumentow (uwagi Archiwisty):
  stabilnosc klucza zrodla (KA-8: klucz `dataset` niezmienny po wydaniu,
  zmiana nazwy tylko przez tabele aliasow czytnika i `dataset_key`, dostawca
  w polu `provider`; ARCHITECTURE 3.3, regula 10) i bezpieczenstwo watkow
  (`file_footprint` i `pinned_transform` z puli watkow, wspolny `cache`
  jako zwykly `dict`; docstringi, ADR-045, test rownoleglego uzycia).

- `Info:` przed wolnymi uslugami (test na zywo 2026-10-16): wycinek PL
  NMT/NMPT z kilku zapytan WCS podaje szacowany czas (`CUTOUT_SIZE`:
  `... 16 zapytan WCS GUGiK pobieranych po kolei - ok. 7-11 min (25-40 s
  na zapytanie wg pomiaru)`, stala `WCS_REQUEST_SECONDS`), zapytanie
  obszaru PRNG (`names download --product geographic|world`) - zmierzony
  czas odpowiedzi OGC API (`SLOW_SOURCE`, `FeatureBBoxParams.response_note`).
- Przeglad UX 0.8.0, wartosci wejscia: `--country`, `--format`,
  `--vertical-crs` i kody ukladow (`--bbox-crs`, `--horizontal-crs`, uklad
  `BBox`) w dowolnej wielkosci liter (`--country PL`, `--format shp`,
  `--vertical-crs evrf2007`/`bpv`, `epsg:2180`) - CLI i biblioteka (komendy
  danych i funkcje z `bbox`) przyjmuja zapis rejestru; wartosc nieznana
  komunikat podaje tak, jak ja wpisano. `geodesy download --network`
  w skladni per kraj jak `--level` (`pl=horizontal,cz=gnss`; API `network=
  {"pl": ..., "cz": ...}`, manifest: napis albo obiekt per kraj). Opcja
  zrodla jednego kraju (`maps --sheet-system sjtsk|etrs89`, ZTM CZ) dotyczy
  pod `--country auto` czesci tego kraju; dla samego drugiego kraju jest
  bledem z nazwa kraju, ktory ja ma (dotad "nie dotyczy" takze dla
  obszaru przy granicy, ktorego nie dalo sie pobrac). Co zrobic: nic.
- Postep kolekcji: `download_collection(on_progress=)` i pasek postepu
  (jak lista arkuszy: `>` przed transferem, `+` pobrana, `o` lokalna, `x`
  blad) w `boundaries`, `cadastre`, `models3d`, `hydro`, `names`, `maps`
  i `geodesy download`, w zrodlach kolekcji `landcover` (ZABAGED, BDOO,
  Data50, Data250) i plikach NMT 100 m - dla zadania z wieloma
  jednostkami (jedna jednostka: linia statusu i `Warning` z rozmiarem
  duzego pliku); `-q` ukrywa pasek. Projekt przekazuje postep zadaniom
  kolekcji.
- Dokumentacja: USAGE 2 - tabela wszystkich kodow `Notice` (kod, poziom,
  kiedy, komendy); `sheet_list` (`download_data`, naglowek na stdout)
  i `unit_list` (kolekcje, takze arkusze map i archiwow osnow) opisane
  jako dwa wydruki tej samej listy jednostek.
- Mesh 3D, drzewa, osnowy i quasi-geoidy (ADR-043): `models3d download
  --product mesh` (modele siatkowe miast GUGiK: kafle indeksu WFS obszaru,
  ZIP OBJ+MTL+JPG 1:1
  w `models3d/pl_mesh/<strefa>/<plik rekordu>.zip`, uklad z rekordu,
  wysokosci EPSG:9651, etykieta = data i numer zgloszenia pracy, sygnal
  `index` w `--check-updates`; kafel = plik rekordu, `--year` filtruje
  rekordy) i `--product trees` (drzewa CityGML LoD1 2023, paczka powiatu
  0,3-25 GB, `Warning` z rozmiarem przed transferem). Nowa grupa `geodesy`
  (`download`, `list-sources`): `--product control --network ...` - osnowy
  PL (WFS sieci `horizontal`, `vertical`, `gravity`, `magnetic` do GPKG
  obszaru; paczki powiatu sieci poziomej i wysokosciowej `--teryt`;
  archiwa arkuszy 1:100 000 `archive-1942`, `archive-kronsztadt60`) i CZ
  (Bodove pole: `gnss`, `horizontal`, `densification`,
  `horizontal-detailed`, `vertical`, `vertical-detailed`, `gravity`; siec
  = suma jej warstw), `--product geoid --whole-country` - PL-geoid2021 (TXT
  1:1) i QGZU-2013 (ZIP z feedu ATOM, wydanie z feedu). Pozycja manifestu
  `geodesy download` (`network`, `whole_country`). Wartosc opcji dostepna
  tylko w innym wyborze nazywa ten wybor (`--teryt` z `--network gravity`),
  a zadanie PL+CZ bez `--network` podaje wartosci obu krajow i wspolne.
  Przyklady i wyniki live: USAGE 1.11, `docs/research/2026-10-16-plan-e5-e2e/raport.md`.
- Limit obszaru kolekcji (ADR-043 errata 3): obszar (`--bbox`/`--sheet`/
  `--geometry`) w `boundaries`, `cadastre`, `models3d`, `hydro`, `names`,
  `maps`, `geodesy`, w zrodlach kolekcji `landcover` (ZABAGED, BDOO,
  Data50, Data250) i NMT 100 m, ktory pobralby wiecej niz 100 plikow albo
  wiecej niz 10 GB (suma `HEAD`/dlugosci z feedu ATOM; ponad 100 plikow -
  szacunek z 5 plikow), konczy sie `Error:`/`ValidationError` przed
  pierwszym transferem z liczba plikow, rozmiarem i podpowiedzia: zawez
  obszar, wybierz jednostke (`--teryt`, `--ku` - bez limitu) albo wykonaj
  plan z czescia pozycji (`--check-updates --plan PLIK`, potem `--upgrade
  --plan PLIK`). Liczone sa pliki bez lokalnej wersji (`--force`:
  wszystkie, `--upgrade --plan`: pozycje planu); opcji obejscia nie ma.
- BDOO, Data50 i Data250 (ADR-043): trzy produkty `landcover download
  --product`.
  `bdoo` (BDOO GUGiK, 1:250 000): paczka GML wojewodztwa na rocznik
  (`--year` wymagany: 2015, 2021-2026; `--teryt` 2 cyfry, kod powiatu =
  `Error:` z podpowiedzia `--teryt <woj>`; obszar `--bbox`/`--sheet`/
  `--geometry` = paczki wojewodztw jego powiatow z PRG, `Info` z lista,
  wojewodztwo bez paczki w `failed`, `--workers`, linia podsumowania)
  zapisana 1:1 w `landcover/pl_bdoo_<rok>/teryt/<woj>.zip` z etykieta
  rocznika; `--layers` (klasy rocznika, `landcover list-layers --product
  bdoo`) zapisuje ZIP plikow `__OT_<KOD>_<typ>` wybranych klas (czlony
  bajt w bajt, `pl_bdoo_<rok>_<klasy>`), klasa bez pliku w paczce = `Info`
  `classes_absent` (nowy kod `Notice`), brak wszystkich = blad wojewodztwa,
  klasa spoza rocznika = `Error:`. `data50` i `data250` (CUZK): obszar =
  jeden GeoPackage wszystkich warstw obiektowych uslugi REST (69 i 116)
  w EPSG:5514, `--whole-country --horizontal-crs EPSG:5514|EPSG:3045` =
  krajowy ZIP SHP z feedu ATOM 1:1 (wydanie z feedu, rozmiar w `Warning`
  przed transferem). Silniki: `PackageVariant.classes`,
  `UnitPackageParams.class_pattern`; obszar produktu z samymi paczkami
  wojewodztw daje paczki wojewodztw obszaru. Przyklady i wyniki live:
  USAGE 1.5 i 1.9, `docs/research/2026-10-16-plan-e4-e2e/raport.md`.
- Adresy i granice specjalne PRG, RCN, geomorfologia i mapa katastralna CZ
  (ADR-043): grupy `boundaries` i `cadastre` dostaja
  produkty `boundaries download --product addresses|special|geomorphology`
  i `cadastre download --product map --country cz|prices`, flagi
  `--format` (pliki krajowe i formaty mapy katastralnej) oraz `--ku`
  (6 cyfr, tylko CZ). Adresy PRG: punkty i ulice obszaru (GPKG EPSG:2180),
  paczka SHP powiatu (`--teryt` 4 cyfry) albo plik krajowy
  (`--whole-country --format SHP|GML`). Granice specjalne PRG: 44 rodzaje
  z OGC API PRG (GPKG OGC:CRS84) albo plik krajowy SHP/GML; obwody spisowe
  (`GranicaObwoduSpisowego`) nie sa w wyniku obszaru - `Info`
  (`AREA_OMITTED`) wskazuje plik krajowy. Geomorfologia CZ: jednostki
  poziomu `--level` (`subprovincie`...`cast`). RCN: eksport powiatu albo
  wojewodztwa (GPKG z trzema warstwami, rozpakowany z ZIP-a lokalnie,
  kontrola warstw). Mapa katastralna CZ: paczka KU w SHP, DXF, DGN albo VFK
  (KU obszaru z RUIAN; sygnal HTTP); VKM poza 0.8.0. Zadania manifestu
  projektu dla obu grup przyjmuja `format` i `ku`. Przyklady i wyniki live:
  USAGE 1.8 i 1.9, `docs/research/2026-10-16-plan-e3-e2e/raport.md`.
- Nazwy geograficzne i mapy topograficzne (ADR-043): grupy `kartograf
  names` i `kartograf maps` z
  `download`/`list-sources`, wspolna funkcja biblioteki
  `download_collection`/`check_collection` oraz zadania manifestu projektu.
  `names --product geographic --country pl` pobiera PRNG RP jako obszarowy
  GPKG OGC:CRS84 (OGC API Features; duze strony, timeout 180 s) albo dwa
  krajowe ZIP-y GML/SHP/XLSX; `--product world --country pl` pozwala pobierac
  polskie nazwy swiata rowniez poza Polska (obszar i jeden plik krajowy).
  Geonames CUZK (`geographic --country cz`) udostepnia 25 warstw obszaru
  EPSG:5514 albo krajowy ZIP GPKG/FGDB w EPSG:5514/3045 z feedu ATOM
  (wydanie z `updated`, sygnal `metadata`). Obszary nie maja taniego sygnalu.
  `maps --product topographic --country pl` pobiera gotowe arkusze
  wizualizacji BDOT10k w skalach 1:10000/25000/50000/100000 jako TIFF lub
  PDF (data `Stan bazy` z indeksu jako sygnal); `--country cz` pobiera ZTM
  w szesciu skalach, ukladzie arkuszy S-JTSK lub ETRS89 rozpoznawanym
  z godla i formatach TIFF/PDF (S-JTSK takze DGN/SHP; formaty inne niz
  PDF sa ZIP-ami). Arkusze ZTM maja sygnal HTTP; sidecar ma uklad wariantu
  EPSG:5514 lub EPSG:3045. Osobne segmenty magazynu `data/names/`,
  `data/maps/`; przyklady i wyniki live: USAGE 1.10 i raport E2E.
- Warstwice ZABAGED CUZK (ADR-043) w `elevation
  download --product contours --country cz --format SHP|DGN` (`--sheet`
  arkusza SM5, `--bbox`/`--geometry` = arkusze SM5 obszaru z indeksu
  `KladyMapovychListu`): ZIP arkusza z openzu zapisany 1:1 (bez
  rozpakowania i konwersji; czlony i CRC sprawdzane przed zapisem wersji)
  w `contours/cz_zabaged_shp|dgn/<hierarchia SM5>/<godlo>.zip`, sidecar
  z lista czlonow ZIP, `mapname`/`cz_share` z indeksu i `extra.http`;
  sygnal `http` (lokalna wersja po jednym `HEAD`, `--check-updates` bez
  pobrania, tor planu `cz_sheet`). Deskryptory
  `cz.cuzk.zabaged_contours_shp` i `cz.cuzk.zabaged_contours_dgn` (jeden
  format = jeden deskryptor, jak archiwa GUGiK); `--format` wymagane,
  `--vertical-crs` tylko `Bpv` (mozna pominac); `--resolution`, `--cutout`,
  `--horizontal-crs`, `--sheet-system`, `--scale`, flagi roku i lotow =
  `Error:` ("warstwice to arkusze SM5 (wektor) ..."); kafel TM33 = `Error:`.
  `--country auto` dla produktu jednego kraju zaweza obszar do tego kraju
  (`Info:` `auto_narrowed_to_cz`/`auto_narrowed_to_pl`, jak w kolekcjach;
  dotyczy tez intensywnosci, true orto i orto ukosnej, dotad `Error:`),
  a `--country pl` z warstwicami to `Error:` "... dostepny tylko dla CZ".
  Tekst bledu `--format` z innym produktem wymienia `contours (CZ)`.
- Obrazy GUGiK (ADR-043): trzy produkty
  w `imagery download` na torze arkuszy ortofotomapy (kampanie, wersje,
  `--year`/`--all-campaigns`, sygnal `index`): `--product intensity`
  (obrazy intensywnosci LIDAR, `pl.gugik.intensity`, arkusze PL-1992
  i PL-2000, `intensity/pl_<uklad>/...`), `--product true-orto` (prawdziwa
  ortofotomapa wybranych miast, `pl.gugik.true_orto`, arkusze 8-czlonowe
  PL-1992 w `true-orto/pl_1992/...`; `--cutout --horizontal-crs EPSG:2180
  --resolution 0.05m|0.1m|0.25m|0.5m|1m` = wycinek z WCS `True_Orthoimagery`
  w `true-orto/pl_1992_<piksel>/bbox/`, bez `--coverage`) i `--product
  oblique-orto` (ortofotomapa ukosna, `pl.gugik.oblique_orto`, arkusze
  PL-2000; arkusz to cztery pliki kierunkow `<godlo>_n|e|s|w.tif`
  w `oblique-orto/pl_2000/...`, nowa flaga `--direction n,e,s,w` /
  `direction=` w `download_data`/`check_data`, bez flagi wszystkie
  cztery). Produkt z jednym ukladem arkuszy (true orto, orto ukosna) moze
  pominac `--sheet-system`; `--full-sheet` tylko dla orto ukosnej (rekordy
  intensywnosci i true orto nie deklaruja pelnego arkusza). Skorowidze
  obrazow opisuje nowy parametr kanalu `SheetIndexParams` (warstwy, uklady
  arkuszy, kierunki, zasieg); jeden provider `GugikImageProvider`
  (`GugikOrtoProvider` = ortofotomapa z wariantami barw). Manifest
  projektu: opcja `direction` zadania `imagery download`. Linie wyniku
  i `--check-updates` jednostki z kilkoma plikami (kierunki orto ukosnej,
  pliki ortofoto CZ) podaja nazwe pliku (`7.125.11.08_n.tif: aktualne
  ...`, `CTES96.TM33N.jgw`); `elevation availability --product` przyjmuje
  tylko `nmt`, `nmpt`, `laz` (warstwice i NMT 100 m poza raportem).
- NMT 100 m GUGiK (ADR-043 D10; `pl.gugik.nmt_100m`, wariant rejestru bez
  ukladu wysokosci):
  `elevation download --product nmt --resolution 100m --bbox ... --country pl`
  (takze `--sheet`, `--geometry`) pobiera pliki wojewodztw obszaru (wg PRG)
  z feedu ATOM GUGiK do `nmt/pl_1992_100m/teryt/<woj>.zip` - ZIP z plikiem
  XYZ 1:1, wersja = data `updated` wpisu feedu (sygnal `metadata`:
  `--check-updates` czyta tylko feedy), sidecar z `vertical_crs: null`,
  `extra.vertical_crs_note` ("GUGiK nie deklaruje ukladu wysokosci ...")
  i `extra.source` (feed uslugi, feed zbioru, kod wojewodztwa, URL,
  `length`). `--format` mozna pominac (`XYZ` - jedyna wartosc);
  `--vertical-crs`, `--sheet-system`, `--scale`, flagi roku i lotow,
  `--full-sheet`, `--cutout`, `--horizontal-crs`, `--min-density`
  i `--country cz` = `Error:` przed siecia. Silnik `atom_files` dostaje
  grupe `woj` w `AtomFilesParams.entry_pattern` (jednostki wojewodztw
  obszaru) i `force_https` (linki `http://` feedow GUGiK pobierane przez
  `https` tego samego hosta).
- Godla 8-czlonowe PL-1992 (ADR-043 D10)
  w `SheetParser` (cwiartki arkusza 7-czlonowego, numeracja 1-4 jak wyzej:
  `N-34-50-A-c-3-2-3`; etykieta Kartografa `1:5000`, GUGiK: modul 1:2500);
  `find_sheets_for_bbox(..., "1:5000", "1992")` daje godla 8-czlonowe,
  `get_children()` arkusza 7-czlonowego - jego cztery cwiartki, nowe
  `series_scale(liczba_czlonow)` (seria GUGiK po liczbie czlonow, nie po
  etykiecie). `DownloadManager` rozwija godlo grubsze od poziomu arkuszy
  providera (`BaseProvider.sheet_scale`, NMT/NMPT/orto: 7 czlonow), a godlo
  8-czlonowe pobiera jako arkusz: siatki NMT 1 m 2019 publikowane per
  cwiartka (1678 rekordow skorowidza) sa do pobrania przez `--sheet
  <godlo 8-czlonowe>` (podpowiedz `elevation availability`). Rejestr
  archiwow dostaje `ASCII-NMT 10m` EVRF2007 (`pl.gugik.nmt_ascii_nmt_10m`,
  215 arkuszy 8-czlonowych; ZIP zawiera punkty co 0,5 m, skorowidz deklaruje
  10 m). Zamyka ograniczenie ADR-041 (rekordy z godlami 8-czlonowymi nie
  sa juz `Info:` w raporcie dostepnosci).
- Silniki kolekcji (ADR-043 D1-D9): wspolny kontrakt kolekcji dla nowych
  produktow ADR-043 (bez nowych produktow w rejestrze). Biblioteka
  `download_collection`/`check_collection`/`validate_collection_request`
  dostaje `ku` (katastralni uzemi CZ, 6 cyfr; obszar = KU z RUIAN), `format`,
  `scale`, `sheet_system` i `network` (wartosci z deskryptorow: wybor kanalu,
  np. jedna usluga WFS na siec albo jeden feed ATOM na format:
  `FeatureBBoxParams.choice`, `AtomFilesParams.choice`; albo wariantu
  paczki). Nowe jednostki silnika
  `unit_package`: arkusze (seria PL-1992 po liczbie czlonow godla albo warstwa
  indeksu CUZK `KladyMapovychListu` w hierarchii godla), kafle
  z rekordow WFS (najnowszy rekord, `year` jako filtr, katalog ukladu
  `1992/` albo `2000/<strefa>/`), KU (`ku/<kod>`) i tematy pliku krajowego
  (`country/pl_<temat>`); adres pliku z szablonu (`{sheet}`, `{ku}`,
  `{theme}`) albo z rekordu indeksu (GetFeatureInfo tabeli linkow,
  `transport/index_records.py`); pliki bez ZIP (`file_kind` TIFF, PDF, TXT)
  sprawdzane po zawartosci. Sygnal `index` porownuje etykiete rekordu
  (np. data stanu bazy) z wersja lokalna bez pobierania; ma go dokladnie
  kanal z indeksem rekordow. Kanaly jednego rodzaju (usluga na siec) moga
  dzielic capability, jesli deklaruja te same uklady (sidecar). `feature_bbox`
  obsluguje OGC API Features (CRS84, strony po `next`, kontrola
  `numberMatched`/`numberReturned`) z osobnym limitem czasu kanalu
  (`FeatureBBoxParams.timeout`; OGC API PRNG GUGiK odpowiada 78-95 s na
  strone). Plik ponad 100 MiB (paczka lub plik jednostki kolekcji, plik
  ATOM jednostki, arkusz obrazu GUGiK i ortofotomapy) dostaje `Notice`
  `DOWNLOAD_SIZE` z rozmiarem (z `HEAD` albo feedu ATOM) przed swoim
  pobraniem (plik krajowy: `WHOLE_COUNTRY_SIZE`); dlatego przed kazdym
  pobraniem paczki, takze produktow planow C/D, jest jedno zapytanie
  `HEAD`.
- Grupa `hydro` (plan D, ADR-042 D16): `kartograf hydro download --product
  network --country cz` - siec wod HY-NET CUZK. Obszar (`--bbox`/
  `--geometry`) = jeden GeoPackage w EPSG:5514
  (`hydro/cz_hynet/bbox/<coords>.gpkg`) z 2 warstwami: `WatercourseLink`
  (odcinki ciekow) i `HydroNode` (wezly); `WatercourseSeparatedCrossing`
  nie jest warstwa obszaru (bez geometrii w GML, GeoServer podaje dla BBOX
  `hits` 0 mimo obiektow), skrzyzowania sa w pliku krajowym - przypomina
  o tym `Info` (`AREA_OMITTED`) kazdego pobrania obszaru.
  `--whole-country --country cz` = `hydro/cz_hynet_gpkg/country/cz.zip`
  (GeoPackage w EPSG:3045, ok. 194 MB, sygnal `http`); `hydro
  list-sources`; biblioteka `download_collection(product="network", ...)`.
- ZABAGED w `landcover download --product zabaged` (ADR-042 D15): obszar =
  GeoPackage EPSG:5514 z 22 warstwami pokrycia terenu i wod
  (`landcover/cz_zabaged/bbox/<coords>.gpkg`; lista: `landcover list-layers
  --product zabaged`), bez przeliczania klas na kody BDOT10k;
  `--whole-country --horizontal-crs EPSG:5514|EPSG:3045` = krajowy ZIP
  z feedu ATOM 1:1 (`landcover/cz_zabaged_gpkg_<epsg>/country/cz.zip`,
  5,8/6,7 GB, etykieta = data wydania, sygnal `metadata`; warstwy pod
  nazwami CUZK, innymi niz wynik obszaru - `Info` `AREA_OMITTED` przy
  kazdym pobraniu obszaru wskazuje plik krajowy). Biblioteka:
  `download_landcover(product="zabaged", output_dir=..., ...)`.
- RUIAN w `boundaries download --product admin --country cz|auto`
  (ADR-042 D17): `--level kraj|okres|obec|katastralni-uzemi` ->
  `boundaries/cz_ruian_<poziom>/bbox/<coords>.gpkg` (EPSG:5514);
  `--whole-country --country cz` -> `boundaries/cz_ruian_shp/country/cz.zip`
  (SHP, ok. 253 MB, `http`); pod `auto` poziom per kraj
  (`--level pl=gmina,cz=obec`, API `level={"pl": "gmina", "cz": "obec"}`)
  daje osobne pliki PRG i RUIAN.
- Ortofoto CZ w `imagery download --product orto --country cz` (ADR-042
  D13): arkusz SM5 (`--sheet CTES96`, `AS91`) albo obszar (arkusze SM5
  z indeksu CUZK) -> cztery pliki ZIP CUZK 1:1 w
  `orto/cz_sjtsk/<hierarchia SM5>/`: `<godlo>.jpg`, `.jgw` (EPSG:5514),
  `.TM33N.jgw` (EPSG:3045), `.TM34N.jgw` (EPSG:3046); sidecar JPEG z
  `extra.world_files`; tylko aktualny rocznik (archiwalne ortofoto CUZK
  sa platne); wydanie z feedu ATOM (`metadata`, etykieta
  `<rok>_<updated>`, np. `2024_2025-02-06`). Biblioteka:
  `download_cz_orto_sheet`/`check_cz_orto_sheet` (`CzOrtoResult`), tor
  planu `cz_orto`.
- Wycinek ortofotomapy PL w magazynie (ADR-042 D14): `imagery download
  --product orto --country pl --bbox|--geometry --cutout --horizontal-crs
  EPSG:2180 --coverage standard|high --resolution 0.1m|0.25m|0.5m|1m` ->
  `orto/pl_1992_<coverage>_<res>/bbox/<coords>.tif` (RGB z WCS GUGiK, bez
  przeprobkowania, siatka wyrownana do piksela i sprawdzana, kawalki do
  200 x 200 m, sygnal `none`; wycinek w calosci 0,0,0, np. `high` poza
  obszarami 10 cm, to `Error:` bez wersji). Biblioteka:
  `download_image_cutout`/`check_image_cutout(..., product="orto",
  coverage=, resolution=)` (`ImageCutoutResult`; ta sama para dla true
  orto), `download_data(..., coverage=)`.
- Silnik `atom_files` (ADR-042 D12, `kartograf/transport/atom.py`):
  pliki wskazywane feedem ATOM CUZK (feed uslugi -> feed zbioru -> plik),
  wydanie z `updated`, indeks feedu w cache metadanych (`atom_cache`
  z `ETag`, TTL 7 dni, warunkowy GET przy `--upgrade`/`--check-updates`,
  jedno odswiezenie przy brakujacym kluczu albo 404 feedu zbioru).
- NMT/NMPT PL (ADR-041, plan A): siatki NMT 0.15m, 0.5m, 0.6m i 10m oraz
  NMPT 0.5m i 0.6m (pelna lista: `kartograf elevation list-sources`);
  archiwa GUGiK (`--format` XYZ, ASCII-NMT, TBD, TIN, TTN, GRD, DXF, DGN)
  pobierane 1:1 jako pliki zrodlowe z sidecarem i wersjami (bez konwersji,
  wycinka i mozaiki; arkusze archiwum dla obszaru wyznacza skorowidz).
  Raport dostepnosci `kartograf elevation availability` /
  `check_availability` (`AvailabilityReport`, `AvailabilityCombination`,
  `AvailabilityArea`, JSON `kartograf-availability/1`): dla jakich lat,
  ukladow, rozdzielczosci, ukladow wysokosci i formatow obszar ma komplet
  pelnych arkuszy NMT/NMPT albo kafli LAZ wg skorowidza WFS i maski ladu PRG,
  bez pobierania danych; podpowiedz pobrania bez `--output` (tez po
  `kartograf project add NAZWA`). Podpowiedz nie planuje arkusza bez
  rekordu kombinacji: gdy siatka obszaru albo potomkowie godla maja taki
  arkusz (za granica - E2E planu B przy Cieszynie, morze, brak rekordu
  roku), zamiast polecenia obszaru jest po jednym `--sheet` na arkusz
  z rekordem (dotad `--check-updates` z podpowiedzi konczyl sie `Brak
  danych` i kodem 1); stopka PL podaje najwyzej 5 polecen i liczbe
  pozostalych, jak CZ. Opis: `docs/USAGE.md` 1.1 i 1.7.
  Zadanie projektu `elevation download` zapisuje opcje `format`.
- Czechy w `elevation` (plan B, ADR-041): NMPT CZ - DMP OK 0.5m (arkusz
  SM5 i kafel TM33 z plikow CUZK, wycinek z ImageServer) i DMP 1G 2m (kafel
  TM33 i wycinek z ImageServer); kafle TM33 DMR 4G/DMP OK w EVRF2007 jako
  gotowe pliki ETRS89 (EPSG:3045, bez transformacji); chmury punktow LAZ CZ
  czterech modeli: `--product laz --model dmr5g|dmr4g|dmp1g|dmpok` (API
  `model=`), `--vertical-crs Bpv` = arkusze SM5 (EPSG:5514), `EVRF2007` =
  kafle TM33 (EPSG:3045), godlo albo obszar (arkusze z indeksu
  `KladyMapovychListu`), plik `.laz` 1:1 z ZIP w
  `laz/cz_<model>_<vcrs>/`, sygnal `http`, tor planu `cz_laz`.
  `--country auto` z LAZ pobiera kafle PL i arkusze CZ ze wspolnym
  `extra.parent_request`; `--year`/`--min-year`/`--max-year`,
  `--all-campaigns` i `--min-density` zawezaja wtedy zadanie do PL
  (`Info:`). Raport `elevation availability --country cz|auto` /
  `check_availability(country="cz"|"auto")`: kombinacje CZ (model x
  `S-JTSK`/`ETRS89-TM33`) z arkuszy indeksu i jednego `HEAD` na plik
  (data publikacji, rozmiar; bez lat nalotu i bez pobierania plikow),
  404 = arkusz bez pliku, inna awaria = blad; `Notice` `cz_service_only`
  (DMR 5G, DMP 1G bez plikow arkuszy), `AVAILABILITY_COUNTRIES` = `pl`,
  `cz`, `auto`, czesc `auto` niesprawdzona = `CHECK_FAILED` i `ok=False`
  (CLI kod 1). Biblioteka: `CuzkRasterProvider`, `create_cz_raster_provider`,
  `CuzkLazProvider`, `download_cz_laz`/`check_cz_laz`, `CzLazResult`,
  `CzLazFailure` w `__all__`; `download_data`/`check_data(..., model=)`.
  Projekt: `--model` w zadaniu `elevation download`. Opis:
  `docs/USAGE.md` 1.4 i 1.7; E2E: `docs/research/2026-10-16-plan-b-e2e/raport.md`.
- Granice, ewidencja i modele 3D budynkow GUGiK (plan C katalogu, ADR-042):
  grupy CLI `boundaries` (`--product admin`, PRG: obiekty obszaru z WFS
  z wymaganym `--level wojewodztwo|powiat|gmina|jednostka-ewidencyjna|obreb`,
  paczka wojewodztwa `--teryt <2 cyfry>`, plik krajowy `--whole-country`),
  `cadastre` (`--product map`, EGiB: eksport powiatu `--teryt <4 cyfry>`
  albo dzialki i budynki obszaru z uslugi zbiorczej WFS) i `models3d`
  (`--product buildings`, CityGML: `--lod 1 --year 2019|2021|2022|2024`
  albo `--lod 2`, paczka powiatu albo paczki powiatow obszaru z PRG), kazda
  z `download` i `list-sources`, trybami `--check-updates`/`--upgrade`/
  `--force`/`--plan`, `--workers` i `-q`. Pliki w magazynie wersji:
  `<grupa>/<kraj>_<zrodlo>[_<tokeny>]/{teryt/<T>|bbox/<coords>|country/<kod>}`
  (np. `boundaries/pl_prg_gmina/bbox/<coords>.gpkg`,
  `cadastre/pl_egib_gpkg/teryt/1261.gpkg`,
  `models3d/pl_buildings_lod1_2024/teryt/1261.zip`); wynik obszaru to jeden
  GeoPackage w ukladzie uslugi (EPSG:2180) z pelnymi geometriami,
  kompletnosc sprawdzana liczba obiektow uslugi; sygnal swiezosci `none`
  (nowa tresc: `--force`). Opis: `docs/USAGE.md` 1.8, ARCHITECTURE 4.10.
- Archiwum rocznikow BDOT10k: `landcover download --product bdot10k --year
  2014..2025 --format GML|SHP` (stan z poczatku roku) zapisuje oryginalna
  paczke powiatu ZIP 1:1 w `landcover/pl_bdot10k_<format>_<rok>/teryt/<T>.zip`
  z etykieta = rok; identyczne roczniki tego samego powiatu zajmuja miejsce
  raz (status `relabeled`, dowiazanie twarde, ADR-042 D7).
- Biblioteka (ADR-042 D10): `download_collection`/`check_collection`
  i `CollectionReport(files, failed, stale, notices, ok)` w `__all__` (=
  `boundaries`/`cadastre`/`models3d download`, tor planu `collection`),
  walidacja bez sieci `kartograf.download.collections.validate_collection_request`,
  `download_landcover`/`check_landcover(year=, format="GML"|"SHP")` dla archiwum
  BDOT10k; kody `Notice` `unit_list` (powiaty obszaru wg PRG),
  `whole_country_size` (rozmiar pliku krajowego przed transferem)
  i `auto_narrowed_to_cz`; parametry kanalow `AccessChannel.params`
  (`UnitPackageParams`, `PackageVariant`, `FeatureBBoxParams`,
  `FeatureLayer` w `kartograf.sources.descriptor`) i deskryptory
  `pl.gugik.prg`, `pl.gugik.egib`, `pl.gugik.buildings` oraz kanal
  `archive_unit_files` w `pl.gugik.bdot10k`. Projekt (ADR-040): zadania
  `boundaries download`, `cadastre download` i `models3d download`.
  Weryfikacja na zywo: `docs/research/2026-10-15-plan-c-live/raport.md`.
- Projekt (ADR-040): grupa `kartograf project` (`init`, `add`, `remove`,
  `download`, `status`, `verify`) zapisuje zadania i przypiete wersje
  w `kartograf-project.json` (`kartograf-project/1`). `download` odtwarza
  brakujace wersje tylko przy zgodnej sumie SHA-256; `--check-updates`
  odpytuje zrodlo bez pobierania, `--upgrade`/`--force` jawnie przepinaja
  zadania. Publiczne API: `init_project`, `open_project`,
  `add_project_task`, `remove_project_task`, `download_project`,
  `check_project`, `get_project_status`, `verify_project` oraz typy
  `Project`, `ProjectTask`, `PinnedFile`, `ProjectReport`, `TaskResult`,
  `ProjectCheck`, `FileCheck`. Zadania obejmuja kazda komende `download`
  grup danych i `soil hsg` z ich opcjami (m.in. `cutout`,
  `horizontal_crs`, `coverage`, `resolution` w `imagery download`;
  `whole_country`, `horizontal_crs` w `landcover download`).
  `project download --workers N` (API `download_project(workers=)`) pobiera
  pliki kazdego zadania rownolegle (domyslnie jak komenda danych); w `project
  add` `--workers` i `soil hsg --summary` to `Error:` (opcje uruchomienia, nie
  zadania). `status`/`verify`: zadanie nie pobrane to linia `NAZWA: nie
  pobrane (pobierz: kartograf project download NAZWA)` i kod 1 (bez
  `Error:`); podpowiedzi polecen `kartograf project ...` maja `--project
  KATALOG`, gdy projekt nie jest biezacym katalogiem. Opis uzycia:
  `docs/USAGE.md` sekcja 8.
- Biblioteka (ADR-037): `download_data`/`check_data` (`kartograf.download.data`)
  = komendy `kartograf elevation download` i `kartograf imagery download`:
  cala logika komendy (godlo i kraj, `country="auto"` z zawezeniem do PL
  i czesciowym sukcesem, walidacja kazdego kraju przed pobraniem,
  rozwiniecie obszaru PL na arkusze, `parent_request`) jest w bibliotece,
  wynik `DataReport(files, failed, stale, superseded, notices, ok)`.
  W API takze `UnitFile`, `UnitFailure`, `download_cz_sheet`/`check_cz_sheet`,
  `check_laz_area`, `get_overall_bbox`, `transform_bbox`,
  `parent_request_for`; testy zgodnosci CLI = API (`tests/test_parity.py`,
  `tests/test_parity_landcover.py`). CLI: `landcover download` i `soil hsg`
  to jedno wywolanie biblioteki na komende, z nowymi flagami `--bbox-crs`
  (bbox w dowolnym ukladzie z listy) i `--quiet` (bez linii statusu na
  stdout; `Info:`/`Warning:` na stderr zostaja), a w `landcover download`
  takze `--layers KODY` (filtr warstw BDOT10k GPKG, np. `SWRS,PTWP`),
  `--keep-raw` (oryginalny ZIP GUGiK w magazynie) i `--workers N`
  (rownolegle powiaty obszaru BDOT10k, domyslnie 1).
- Walidacja wejscia w bibliotece przed siecia, z tym samym tekstem co CLI
  (ADR-037): `download_data`/`check_data` sprawdzaja `product`, `country`,
  `sheet_system`, `horizontal_crs` (wartosci jak w `--help`) i bbox
  (odwrocony, nieskonczony: `Nieprawidlowy bbox: ...`); bbox (wspolrzedne
  i uklad z listy `--bbox-crs`, nieznany uklad = `ValidationError`) takze
  w `download_pl_cutout`/`check_pl_cutout`, `download_cz_cutout`/
  `check_cz_cutout`, `download_laz_area`/`check_laz_area`,
  `download_landcover`/`check_landcover` i `calculate_hsg`/`check_hsg`
  (katalog `.tif` odrzucony jak w CLI); `resolution`/`vertical_crs`
  innego typu niz tekst albo slownik = `ValidationError`; kod TERYT
  sprawdzany takze w `check`. Bledy wejscia
  wewnatrz czesci kraju sa `ValidationError`, nie pozycja `failed`.
  Komunikaty `nie udalo sie sprawdzic zrodla` i
  `lokalna wersja ... niesprawdzona` land cover i HSG sa `Notice`
  biblioteki; arkusz PL uzyty lokalnie przy niedostepnym skorowidzu daje
  jeden komunikat; `--check-updates` pod `auto` z awaria jednego kraju
  podaje blad z nazwa kraju.
- Biblioteka: `Notice(level, code, text)` w publicznym API oraz
  `kartograf.notices.NoticeSink` (zbieranie komunikatow i przekazanie do
  callbacku); tekst komunikatow ograniczony do ASCII, kody sa stale.
- Biblioteka i CLI: `kartograf.cache.defaults.open_cache(cache, force=...)`
  wspoldzieli domyslna baze metadanych `.kartograf_cache.db` w katalogu
  biezacym (`default_cache_path()`); `cache=False` pomija cache, a `force=True`
  dla przekazanej instancji uzywa osobnego polaczenia bez zmiany jej odczytow.
  Wylaczenie cache jest zglaszane przez `Notice` (`cache_disabled`).
- CLI `elevation download` i `imagery download`: `--check-updates
  [--plan PLIK]` (raport bez pobierania, plan JSON `kartograf-plan/1`),
  `--upgrade [--plan PLIK]` (pobranie
  nowszej tresci; wykonanie planu z kontrola, czy zrodlo nie zmienilo sie
  od planu) — dla kazdego toru: arkusze PL, kafle LAZ PL i CZ (CZ:
  `ETag`/`Last-Modified` pliku), arkusze CZ (SM5 i natywne TM33:
  `ETag`/`Last-Modified`), wycinki CZ i PL (bez taniego sygnalu:
  "nie da sie sprawdzic bez pobrania"); przy `--country auto` jeden plan
  PL i CZ.
- CLI `landcover download`, `soil download` i `soil hsg`: `--check-updates`,
  `--upgrade`, `--force`, `--plan PLIK` (tory planu `landcover` i `hsg`);
  status `uzyta ponownie` (HSG z tych samych wejsc, bez liczenia).
- Biblioteka: `UpdatePlan`, `PlanItem`, `UpdateMode`, `VersionRef`,
  `VersionedFile`, `LandCoverReport`, `SoilReport`, `HsgReport` i `Edition`
  w `__all__` (typy wewnetrzne klas bez eksportu);
  `DownloadManager.check_sheets`, `FileStorage.get_versions_root`,
  `get_versions_base`, `has_legacy_campaigns`, `UpdatePlan.merge`/`items_for`.
  `kartograf.download.fetch` dostarcza `fetch_version`/`inspect_version`,
  `use_local`/`store_file` i sygnal wydania `metadata`; status `reused`
  oznacza HSG z tych samych wejsc bez ponownego liczenia.
- Biblioteka: `check_cz_cutout`/`check_pl_cutout` w `__all__`; kanaly
  `AccessChannel.update_signal`/`channel_signal`, transport
  `response_signal`, `head_signal`, `download_to(on_response=)`,
  `get_with_retry(headers=)`; sidecary `extra.version`, `extra.http`
  (SM5), `extra.edition` i status `relabeled` (ta sama tresc pod nowa
  etykieta; `VersionedFile.same_as` = etykieta najnowszej identycznej
  wersji, w CLI `(plik identyczny z <etykieta>)`).

### Zmienione

- Interfejs dla agentow AI (ADR-046), zmiany istniejacych API i zachowan:
  `calculate_hsg(..., summary=False)` i `HsgReport.summary` (statystyki HSG po
  obliczeniu); `--summary` wola API zamiast `hsg_statistics` w CLI (tekst bez
  zmian, `soil hsg --json --summary` zwraca `summary` w dokumencie).
  `TaskDownload.__call__` (`project/commands.py`) dostaje `plan`, a
  `TaskCommand.options` pochodzi z katalogu: w nowych manifestach klucze opcji
  maja kolejnosc deklaracji (np. `country` zaraz po `product`), a zapis zadania
  przepisuje w niej takze starszy manifest. Handlery CLI nie przekazuja
  nieustawionych flag (`None`, `False`) do funkcji biblioteki (obowiazuja ich
  wartosci domyslne); puste `--bbox ''` i `--geometry ''` to blad wejscia (kod 2),
  jak w `parse_command` i `project add` (dotad ignorowane); `parse` zglasza blad
  przed drukiem godla; `project add` zglasza bledy skladni komendy zadania jako
  `UsageError` (`Error: ...`, kod 2, bez bloku `usage:`); `cache path` w trybie
  tekstowym drukuje sama sciezke bez otwierania bazy, a `cache path --json` to
  `kartograf-cache/1` z `action: "path"`. Tabele `list-sources` i `list-layers`
  oraz wydruk `parse` sa renderowane z dokumentow biblioteki, bez zmian tekstu.
  Co zrobic: testy podmieniajace funkcje biblioteki i czytajace ich `kwargs`
  uwzgledniaja brak nieustawionych flag; nowa komenda to deklaracja w katalogu
  (STANDARDS 17.2).

- Jedna konwencja nazw kluczy zrodel i katalogow `data/` (przeglad UX
  UX-35..40, ADR-044 D7, ARCHITECTURE 3.3 regula 10; pilnuje jej test
  rejestru `TestNamingConvention`): klucz `<kraj>.<dostawca>.<nazwa>`
  z calych slow sciezki `data/`, katalog = `--product` w `elevation`
  i `imagery`, segment `<kraj>_<tokeny>` (`_` miedzy tokenami, `-` w tokenie
  wielowyrazowym, `.` w liczbie), uklad PL `1992`/`2000` i strefa PL-2000
  jako katalog jej numeru, arkusz zawsze w hierarchii godla. Produkty nowe
  w 0.8.0 nazwano wg niej przed wydaniem; segmenty i klucze z wydan
  <= 0.7.2 bez zmian. Zmienione wzgledem wersji deweloperskiej 0.8.0:
  klucze `pl.gugik.true_orto` (bylo `orto_true`), `pl.gugik.oblique_orto`
  (`orto_oblique`), `pl.gugik.buildings` (`buildings_3d`), `pl.gugik.mesh`
  (`mesh_3d`), `pl.gugik.trees` (`trees_3d`), `pl.gugik.control`
  (`prpog`), `pl.gugik.geoid2021` (`quasigeoid`), `cz.cuzk.hynet`
  (`hy_net`), `cz.cuzk.orto` (`ortofoto`), `cz.cuzk.control`
  (`survey_control`), `cz.cuzk.qgzu2013` (`qgzu`); katalogi
  `true-orto/pl_<uklad>/` (bylo `orto/pl_<uklad>_true/`, wycinek
  `true-orto/pl_1992_<piksel>/`), `oblique-orto/pl_2000/`
  (`orto/pl_2000_oblique/`), `cadastre/cz_cadastral-map_<format>/`
  (`cz_km_<format>`), `geodesy/pl_control_<siec>_xls/` (`_package`),
  `geodesy/cz_qgzu2013_bpv/` (`cz_qgzu2013`); kafel mesh
  `models3d/pl_mesh/2000/7/` (`s7/`) i `.../1992/` (`pl1992/`), arkusz ZTM
  `maps/cz_ztm_<skala>_<uklad>_<format>/0510/D/11/0510-D-11.zip` (bylo
  plasko w segmencie), temat pliku krajowego `country/pl_miejscowosci.zip`
  (`pl-miejscowosci.zip`). `--output` w `imagery` opisuje katalog produktu.
  Co zrobic: dane pobrane wersja deweloperska pod dawnymi nazwami nie sa
  migrowane - nastepne pobranie trafia do nowych katalogow (stare usun
  recznie); kod czytajacy `dataset` sidecara albo klucze rejestru uzywa
  nowych kluczy.
- Plan D (ADR-042 D13-D17): `imagery download --country` przyjmuje `cz`
  (ortofoto CZ), `boundaries download --country` - `cz` i `auto` (RUIAN),
  `--level` w skladni per kraj (`pl=gmina,cz=obec`; jedna definicja parsera
  z `--resolution`/`--vertical-crs` w `cli/_args.py`). Nazwa deskryptora
  `pl.gugik.orto`: `Ortofotomapa (arkusze wg kampanii; wycinek WCS
  Standard i High)` (klucz `dataset` bez zmian). `AccessChannel.params`
  ma dwa nowe typy: `AtomFilesParams` i `WcsCutoutParams`.
- Listy produktow `elevation`/`imagery` i zrodel `landcover`
  przeniesiono z parserow CLI do biblioteki (`download/options.py`,
  `landcover/manager.py`): grupy CLI i manifest projektu korzystaja
  z tych samych wyborow (zmiana wewnetrzna).
- Nowa zaleznosc wykonawcza `pyogrio>=0.10` (GDAL wektorowy; kolo z wlasnym
  GDAL, ok. 100 MB obok GDAL `rasterio`): zapis GeoPackage wyniku obszaru
  `boundaries`/`cadastre download` (ADR-042 D5). Co zrobic: zaktualizuj
  instalacje (`pip install -U kartograf` albo `pip install -e .` w repo) -
  `pyogrio` instaluje sie razem z pakietem; bez niego pobranie obiektow
  obszaru konczy sie bledem importu (paczki i pozostale komendy dzialaja).
- `landcover download --format` przyjmuje takze `GML`, wylacznie z `--year`
  (archiwum rocznikow BDOT10k); `--year` przy `--product bdot10k` oznacza
  rocznik archiwum (dotad tylko CORINE). Bez `--year` dziala jak dotad
  (biezace paczki GPKG/SHP); `--format GML` bez `--year` to `Error:`
  z podpowiedzia. Co zrobic: nic.
- Dokumentacja umowy `update="force"` wobec cache providera (USAGE 2,
  ARCHITECTURE, docstringi `DownloadManager`/`LandCoverManager`):
  `force` odswieza cache otwierany przez sama funkcje; provider przekazany
  jako gotowa instancja zachowuje swoj cache (pelne odswiezenie:
  `MetadataCache(refresh=True)`). Zachowanie bez zmian. Co zrobic: nic.
- Przeglad UX 0.8.0, pomoc CLI (UX-15, 23, 26-34, 44): kazde `download`,
  `soil hsg` i `elevation availability` ma w `--help` przyklady polecen
  (sprawdzane testem jak `project add`); `project init/add/remove/download/
  status/verify` i `cache stats/clear/path` maja opisy. Jednolite sekcje
  pomocy (`Produkt i obszar`, `Parametry produktu`, `Wynik i aktualizacja`),
  `--country` zaraz po `--product`, metavary po polsku (`ROZDZIELCZOSC`,
  `UKLAD`, `SKALA`), jeden tekst `--output` (`Katalog magazynu (wymagany):
  pliki w <KATALOG>/<katalog>/...` z katalogiem z rejestru; ten sam w bledzie
  braku `--output`). `maps`: opis i `--sheet-system` mowia, ze uklad arkuszy
  dotyczy tylko ZTM (CZ). `soil list-layers` i pomoc `--property`/`--stat`
  po polsku z jednostkami (jedna mapa opisow). `landcover list-layers` dla
  ZABAGED/Data50/Data250: same nazwy warstw i zdanie, ze `--layers` dotyczy
  tylko BDOT10k i BDOO; lata CORINE z rodzajem danych (1990 - tylko podglad
  WMS). Glowne `kartograf --help` opisuje grupy bez twierdzenia, ze kazda
  ma `download` i `list-sources`. Docstring `kartograf/__init__.py`:
  wszystkie zrodla i grupy kolekcji. Co zrobic: nic.
- `kartograf parse` rozpoznaje godla CZ bez sieci (UX-25): arkusz SM5
  (`CTES96`), kafel TM33 (`302_5550`, z zasiegiem w EPSG:3045) i arkusz ZTM
  (`0510-D-11`, `NM-34-07-1-D-15`) - system, uklad i komendy przyjmujace
  godlo w `--sheet`; `--hierarchy`/`--children`/`--descendants` z godlem CZ
  to `Error:`. Wzorce ZTM w `core.parser_registry.ztm_sheet_system` (jedno
  zrodlo dla `parse` i `maps download --sheet`). Co zrobic: nic.

### Naprawione

- Komunikaty przegladu UX 0.8.0: nieznana flaga zglaszana przez komende
  (jej `usage`) z lista komend, ktore ja maja, i podpowiedzia typowych
  pomylek (`landcover --source`/`-s` -> `--product`, `soil download
  --product` -> `--property`, `hydro --sheet`); `--bbox -447000,...` po
  spacji dziala bez `=`; brak wyboru wymienia wybory produktu w kraju
  zadania (HY-NET CZ bez `--teryt`/`--ku`/`--sheet`, osnowy z wartosciami
  `--network`, CORINE i SoilGrids `--sheet, --bbox albo --geometry`);
  flagi zamiast kluczy rejestru (`--sheet-system`, `--keep-raw`,
  `--teryt`) i nazwa produktu w "nie dotyczy"; zrodla CZ `landcover`
  z godlem PL i `--teryt` 2 cyfr BDOT10k z podpowiedzia; `--layers` bez
  wzgledu na wielkosc liter; systemy godel jako `PL-1992`/`SM5`; poprawna
  odmiana liczebnikow ("2 pliki", "dla 1 arkusza", "Pobieranie kafli
  LAZ"); blad "brak obiektow w obszarze" podaje obszar zadania w ukladzie
  uzytkownika.
- LAZ PL `--sheet`: kafle wybierane z ramy arkusza (w EPSG:2180 obrocony
  czworokat), nie z jej obwiedni, a kafel musi siegac w obszar glebiej niz
  1 m (`tolerance_m`): sasiedzi stykajacy sie z rama krawedzia albo
  naroznikiem (ramy GUGiK zaokraglone do 1 cm) i kafel siegajacy
  w `--bbox` o milimetry nie sa pobierane. Przyklad z USAGE 1.1 (`--sheet
  N-34-130-D-d-2-4`) pobieral 13 kafli (1,83 GB) zamiast 4 (575 MB), arkusz
  1:5000 - 6 kafli zamiast 1 (test na zywo 2026-10-16). To samo w
  `elevation availability --product laz --sheet` (pole i kafle ramy).
  Biblioteka: `download_laz_area`/`check_laz_area(sheet=)` (dokladnie jedno
  z `bbox`/`sheet`, jak `download_cz_laz`), `select_tiles(frame=)`,
  `select_newest_cover`/`select_all_intersecting` z rama jako wielokatem
  EPSG:2180, `select_all_intersecting(tolerance_m=)`. `Info:` o pominietych
  kaflach wymienia tylko kafle pokryte przez nowsze; kafle spoza obszaru
  zostaja w `superseded` z powodem `outside`.
- `--check-updates` (oraz `check_data`, `check_*`, `check_landcover`)
  zawsze pyta zrodlo: cache metadanych jest otwierany w trybie
  odswiezania (odczyt pominiety, wpisy zapisane od nowa) w kazdym torze.
  Dotad arkusze PL (NMT/NMPT/orto), archiwa, pliki NMT 100 m, kolekcje,
  LAZ CZ, arkusze CZ i land cover odpowiadaly z cache (TTL 7 dni) - takze
  offline `aktualne`, a nowy lot opublikowany w tym czasie byl niewidoczny
  (test na zywo 2026-10-16). Bez sieci sprawdzenie konczy sie teraz
  `Error:`. `--upgrade` (`update="upgrade"`) pyta zrodlo tak samo (cache
  w trybie odswiezania, `fetch.refreshes_cache`) - nowy lot jest widoczny
  bez wczesniejszego `--check-updates`. Domyslne pobieranie czyta cache jak
  dotad.
- Wycinek PL `--cutout` w calosci poza ladem (maska PRG: morze, zagranica)
  konczy sie `Error:` (kod 1, `NoCoverageError`) przed pierwszym zapytaniem
  WCS, bez wersji w magazynie - jak tryb arkuszy. Dotad 6 zapytan WCS
  (30 s), plik 16,8 MB samego nodata i kod 0 z `Warning:` (test na zywo
  2026-10-16). `Warning: wycinek w calosci nodata` zostaje dla WCS bez
  danych na ladzie.
- HSG `--summary`: statystyki obszaru zadania - naglowek `Statystyki HSG
  obszaru zadania (grupy: % powierzchni z danymi)`, linie grup z opisem po
  polsku, `Brak danych: <procent>% obszaru zadania (<ha> ha)` i `Obszar
  zadania: <ha> ha`; dotad bbox 2 x 2 km z 19 ze 104 pikseli z danymi
  dawal samo `Grupa B: 100.0%`, a potem 420,91 ha "calego obszaru" (caly
  raster SoilGrids siegajacy poza bbox, test na zywo 2026-10-17).
- Wycinek obrazu PL w calosci 0,0,0 (`imagery download --cutout`,
  `download_image_cutout`): true orto poza miastami uslugi, ortofotomapa
  `high` poza obszarami 10 cm i `standard` bez ortofotomapy konczy sie
  `Error:` (kod 1, `NoCoverageError`, w `download_data` porazka
  `no_coverage` PL) bez wersji w magazynie - jak wycinek PL poza ladem;
  tresc podaje przyczyne i remedium (`zmien --bbox`, przy `high` takze
  `uzyj --coverage standard`). Dotad czarny plik byl nowa wersja
  z `extra.all_nodata` i `Warning:` (true orto z zagniezdzonym nawiasem;
  test na zywo 2026-10-17, Krakow, 19 s). Usluga nie publikuje zasiegu
  wycinka, wiec obraz jest pobierany i sprawdzany przed zapisem wersji;
  `ImageCutoutResult.notices` nie zawiera juz `all_nodata`.
- Mesh 3D `--bbox` (i kazdy produkt kafli indeksu WFS) bez `--check-updates`/
  `--upgrade` drugi raz w tym samym obszarze nie pyta indeksu: rekordy
  obszaru sa w cache metadanych (TTL jak skorowidze arkuszy PL), wiec
  przebieg z lokalnymi kaflami dziala bez sieci. Dotad 3 proby WFS
  `SkorowidzModeleSiatkowe3D` i kod 1 offline (test na zywo 2026-10-17).
  `--check-updates`, `--upgrade` i `--force` pytaja indeks jak dotad.
- `update="check"` w funkcji pobrania wskazuje funkcje planu tego toru
  (`uzyj check_landcover()`, `check_soil()`, `check_hsg()`,
  `check_image_cutout()`, `check_data()`, `check_collection()`, ...);
  dotad zawsze `check_sheets() albo check_*()`.
- `python -m kartograf.cli.commands` nie wypisuje `RuntimeWarning` modulu
  `runpy` (pakiet `kartograf.cli` importuje `main` dopiero przy uzyciu).
- Awaria skorowidza WFS GUGiK w linii `--check-updates` konczy sie faktem
  `- wynik bylby niepelny`, bez `ponow pobranie` (sprawdzenie niczego nie
  pobiera; testy na zywo 2026-10-16/17). Remedium `ponow pobranie` dopisuja
  tylko podsumowania pobrania; dotad podsumowanie kilku arkuszy mialo je
  dwa razy, a ostrzezenie `skorowidz GUGiK niedostepny - uzyto lokalnej
  wersji` radzilo ponowic pobranie, choc plik byl na miejscu.
- Projekt: odtworzenie brakujacej przypietej wersji przy zgodnej SHA-256
  zapisuje bajty pod przypieta wersja (`version`, `label`; dowiazanie
  i sidecar z przypieta etykieta) - manifest sie nie zmienia. Dotad
  odtworzenie innego dnia zmienialo `version`/`label` zadan z etykieta
  daty pobrania (zmiana w manifescie bez zmiany danych).
- Dokumentacja: USAGE 7 - koszt potwierdzania dowiazan na udziale SMB bez
  `serverino` (pelny odczyt pliku przy kazdym uruchomieniu; bez skrotu
  w kodzie) oraz zera SoilGrids w obszarach maskowanych (GeoTIFF bez tagu
  NoData; HSG traktuje je jako brak danych).
- Dokumentacja: USAGE 7 - orto ukosna Krakow 2021 ma w GeoTIFF wlasny opis
  ukladu bez kodu EPSG (GDAL zgaduje EPSG:32634); uklad pliku to EPSG:2178
  jak w sidecarze, z obejsciem bez zmiany pliku.
- CLI (test na zywo 2026-10-16): `kartograf` i `<grupa>` bez komendy
  wypisuja pomoc na stderr z kodem 2 (dotad 0 - skrypt z pomylka
  "przechodzil"); Ctrl-C konczy sie `Error: przerwano (Ctrl-C)` i kodem 130
  zamiast tracebacku; `--check-updates --plan` do nieistniejacego katalogu
  = `Error:` przed siecia (dotad po calym sprawdzeniu zrodla); bez plikow
  (awaria WFS LAZ) brak podsumowania `Nowe: 0, ..., bledy: 0` przeczacego
  linii `Error:`; ponowienia zapytan HTTP to linie `Warning:` z krotka
  przyczyna (`HTTP 503`, `przekroczony czas odpowiedzi`, `brak sieci albo
  DNS`, `zerwane albo odrzucone polaczenie`) zamiast surowego wyjatku
  urllib3 (ok. 500 znakow); pelny wyjatek w lancuchu przyczyn
  (`KARTOGRAF_DEBUG=1`).
- Godla SM5 z dwiema literami (99 arkuszy As, `AS22`...`AS94`):
  `detect_system("AS91")` zwracal uklad PL-1992 (fallback wzorca
  `^[A-Z]{4}[0-9]{2}$`), wiec `--sheet AS91` (DMR 4G) konczyl sie bledem
  godla PL. Teraz `cz_sm5` (`^[A-Z]{2}(?:[A-Z]{2})?[0-9]{2}$`, katalog
  `AS/91`) - takze dla DMR i ortofoto CZ.
- CORINE CLMS 2012/2006/2000: UID-y zbiorow i `@id` rastra nie istnialy
  w katalogu CLMS (`items_total: 0`); poprawione wg katalogu
  (`docs/research/2026-10-12-plan3-spec-check/raport.md`). Pobranie CLMS
  z credentials niesprawdzone na zywo.
- `soilgrids hsg --bbox ... -o <katalog>` pisal `hsg_bbox_<glebokosc>.tif`
  bez wspolrzednych — dwa obszary nadpisywaly jeden plik. Teraz
  `hsg/global_soilgrids_<gl>_<stat>/bbox/<wsp>.tif`.
- Arkusze PL pobierane rownolegle (`workers > 1`): wynik (`DownloadResult`
  listy, `files`) i komunikaty (np. lista arkuszy bez danych GUGiK)
  w kolejnosci zlecenia, nie zakonczenia - to samo zadanie daje zawsze ten
  sam raport (wykryte testem zgodnosci CLI = API).
- `--check-updates --plan PLIK` z katalogiem PLIKU, ktory nie istnieje:
  `Error: nie udalo sie zapisac planu <PLIK>: ...` (kod 1) zamiast
  `Error: FileNotFoundError: ...` z podpowiedzia `KARTOGRAF_DEBUG`
  (weryfikacja na zywo 2026-10-12).
- `landcover download --format` z innym zrodlem niz bdot10k konczy sie
  bledem (dotad byl po cichu pomijany); `download_landcover`/`download_soil`
  bez wymaganej opcji zrodla (`year` CORINE, `property`/`depth`/`stat`
  SoilGrids) albo
  z opcja tylko BDOT10k (`format`, `layers`, `keep_raw`) dla innego zrodla
  daje `ValidationError` z tekstem CLI (dotad `TypeError`). Bez
  angielskich i podwojnych linii logu na stderr (`No data for ...`,
  `Failed to download ...`, podglad CORINE, `Zapytanie WFS GUGiK ...` LAZ,
  logi powielajace `Notice`, porazki powiatow BDOT10k): przyczyna porazki
  jest w tekscie bledu (`Error:`, pole `failed` wyniku).
- Wpis "brak pokrycia" w cache metadanych zapisany przed 0.8.0 (komunikat
  albo podpowiedz z polskimi znakami lub myslnikiem `—`) przerywal
  pobieranie bledem `Tekst komunikatu musi byc zapisany w ASCII` (np.
  `kartograf elevation download --sheet N-34-130-D --resolution 5m ...` z cache
  z 0.7.x). Taki wpis jest teraz traktowany jak brak wpisu i skorowidz jest
  odpytywany ponownie. Co zrobic: nic (opcjonalnie `kartograf cache clear`).
- `landcover download --check-updates --keep-raw` drukowal dwie
  jednakowe linie planu (`0208: do pobrania`) dla GPKG i surowego ZIP tego
  samego TERYT. Linie planu `landcover download`, `soil download` i `soil
  hsg` oznaczaja teraz pozycje sciezka pod `--output`, jak linie statusu
  (`landcover/pl_bdot10k_gpkg/teryt/0208.gpkg: do pobrania`, `soil hsg`:
  zamiast `clay <wsp>` / `hsg <wsp>`). Co zrobic: skrypty parsujace linie
  planu tych komend czytaja sciezke (plik planu JSON bez zmian).
- `--bbox-crs EPSG:2176-2179` (strefy PL-2000) z `--sheet-system 1992`
  konczyl sie `Error: Nieobslugiwany CRS: 'EPSG:2177'. Obslugiwane:
  EPSG:2180, EPSG:4326`, choc uklad jest na liscie `--bbox-crs`.
  `find_sheets_for_bbox(..., sheet_system="1992")` przyjmuje teraz te same
  polskie uklady co PL-2000 (EPSG:2180, EPSG:4326, EPSG:2176-2179); uklady
  CZ zamienia wczesniej `download_data` operacja przypieta.
- Postep pobierania arkusza z kilkoma kampaniami (`--all-campaigns`,
  `--full-sheet`): dotad linie `nowa wersja`/`lokalna wersja` pojawialy sie
  dopiero po calym zadaniu. Biblioteka zglasza zdarzenia `DownloadProgress`
  `campaigns` (lista lotow arkusza: `lokalna`/`do pobrania`) i `campaign`
  (przed pobraniem kazdego lotu, `k/n`); CLI drukuje `  Kampanie <arkusz>
  (do pobrania k z n): ...` i `  Pobieranie <arkusz> <etykieta> (k/n)...`.
  `--upgrade --plan` arkuszy PL raportuje postep jak zwykle pobieranie.
- Postep pobierania powiatow BDOT10k obszaru (`landcover download --bbox/
  --sheet/--geometry`, takze archiwum `--year`): dotad brak jakiegokolwiek
  postepu do konca zadania. `download_landcover(on_progress=)`
  zglasza `DownloadProgress` per powiat jak lista arkuszy (`sheet` = TERYT:
  `downloading` tuz przed transferem przy `--workers 1`, potem `completed`/
  `skipped`/`failed` w kolejnosci ukonczenia); CLI i `project download`
  rysuja ten sam pasek co dla arkuszy. Jeden `--teryt`, CORINE i SoilGrids
  bez zmian (jeden plik).
- Pasek postepu listy arkuszy (i powiatow BDOT10k), ktorego ostatnia
  jednostka byla `o` (lokalna wersja), nie konczyl linii: pierwsza linia
  statusu doklejala sie do paska (weryfikacja na zywo 2026-10-15). Linia
  paska jest teraz zamykana przed liniami statusu i `Error:`.
- Sidecar dowiazania (`<plik>.meta.json` sciezki standardowej) po awarii
  zapisu zostawal stary i opisywal poprzednia wersje (ADR-030 M-8). Teraz
  jest usuwany (ostrzezenie w logu), a nastepne uruchomienie odtwarza
  dowiazanie i sidecar (ADR-030 errata 10).
- Dokumentacja ortofotomapy (SCOPE, PRD, docstring `gugik_orto.py`):
  rozdzielczosc "wg kampanii (np. 25 cm, 10 cm)" zamiast stalego 25 cm
  (README poprawione wczesniej).

## [0.7.2] - 2026-10-11

### Dodane

- CLI: `download --product nmpt --bbox/--geometry --target-crs ...` — wycinek
  NMPT 1 m z WCS GUGiK (dotad `Error:`), segment
  `nmpt/pl_1992_1m_<vcrs>/bbox/`.
- Biblioteka: `run_pl_wcs_cutout(cutout, *, provider=None, parent_request=None,
  today=None)` (w `__all__`) — wycinek PL z WCS GUGiK: siatka arkuszy 1 m,
  maska ladu PL z PRG (`A00_Granice_panstwa` minus
  `W02_Morze_terytorialne_RP` i `W03_Morskie_wody_wewnetrzne`, poza maska
  -9999, 0,0 na ladzie zostaje), nazwa `<wsp>_<RRRRMMDD>.tif`, sidecar
  `capability="bbox_raster"` z `extra.source` (`composition: "server"`)
  i `extra.mask`. `prepare_pl_cutout(product=)` i
  `download_pl_cutout(product=)`: `"nmt"` albo `"nmpt"` (wycinek NMPT 1 m,
  segment `nmpt/pl_1992_1m_<vcrs>/bbox/`). `PlCutoutResult.masked_pixels`
  (piksele poza maska) i `zero_pixels` (0,0 na ladzie; tez
  `extra.zero_pixels`, gdy > 0).
- NMT/NMPT: przy arkuszu bez danych w wybranej rozdzielczosci albo
  ukladzie wysokosci podpowiedz `Info:` o wariancie, w ktorym skorowidz
  GUGiK ma ten arkusz, np. `Skorowidz GUGiK ma ten arkusz w NMT 1m
  EVRF2007 — uzyj --resolution 1m` (biblioteka:
  `NoCoverageError.hints`, `DownloadResult.no_coverage_hints`). Koszt: jedno
  zapytanie skorowidza na wariant (NMT: 2, NMPT: 1) i brakujacy arkusz;
  blad tego zapytania (jedna proba) pomija podpowiedz, a wariant z bledem
  nie jest juz pytany do konca zadania; wynik bez zmian. Wpisy cache braku
  pokrycia sprzed 0.7.2 nie maja tej podpowiedzi do konca TTL (7 dni) —
  odswieza `--force` albo `MetadataCache(refresh=True)`.
- Biblioteka: `DownloadManager(max_year=)` i publiczne
  `check_year_range(godla)` sprawdzaja pelna liste kampanii przed
  pobraniem; `YearRangeError` podaje godla, dostepne lata i podpowiedzi.
  `available_years(godlo)` providerow NMT/NMPT/orto zwraca rosnace lata
  z pelnej listy kampanii arkusza.
  Sidecar kampanii z przedzialem zawiera `request.max_year`, `request.year`
  dla pojedynczego roku i `extra.available_years`.
- NMT/NMPT/orto: po pobraniu kilku lotow arkusza z przedzialu lat,
  gdy najnowszy nie jest pelny, mierzony jest udzial waznych pikseli
  (`extra.coverage` w sidecarze kampanii). Sidecar sciezki standardowej
  otrzymuje liste `extra.flights` i `extra.better_coverage` (ID lotu
  z wiekszym pokryciem, gdy istnieje); biblioteka zwraca ten ID w
  `SheetFetch.better_coverage` i `DownloadResult.better_coverage`.
  Dowiazanie nadal wskazuje najnowszy lot, nie lot o najwiekszym pokryciu.
- Biblioteka LAZ: `select_tiles(max_year=)`, `discover_tiles(min_year=,
  max_year=)` i `download_laz_area(max_year=)` wybieraja kafle z domknietego
  przedzialu. W `Error:` o braku rocznika rok, ktory w niepokrytej czesci
  ma tylko dostawy arkuszy niepelnych (`czy_ark_wypelniony=NIE`), ma
  dopisek `(tylko arkusze niepelne)`.
  Sidecar LAZ zapisuje `request.max_year` (i `request.year`, gdy granice sa
  rowne), a dla znanych wartosci `extra.acquisition_date` i `extra.full_sheet`.
- CLI `download`: `--max-year RRRR` i `--year RRRR` dzialaja dla NMT,
  NMPT, orto oraz LAZ. Flagi roku wyznaczaja tylko dopuszczalne lata,
  a `--campaigns` liczbe lotow na arkusz: domyslnie (`newest`) jeden,
  najnowszy lot z zakresu, `--campaigns all` wszystkie loty z zakresu.
  `--year` jest skrotem obu granic na ten sam rok; brak rocznika dla
  ktoregos arkusza/kafla zatrzymuje zadanie przed pobraniem, podaje
  dostepne lata i podpowiedz. Przy `--campaigns all`, gdy starszy lot ma
  wieksze zmierzone pokrycie niz najnowszy, CLI podaje `Info:` takze z `-q`
  (dowiazanie pozostaje na najnowszym locie).
- CLI i biblioteka: gdy przy granicy roku dowiazanie nadal wskazuje
  lot spoza zadania (dowiazanie nigdy nie cofa sie), CLI podaje
  `Info: N dowiazan wskazuje lokalny lot spoza tego zadania ...` z linia
  `<godlo>: sciezka standardowa|full_sheet/ -> dowiazanie <data>_<id>` na
  dowiazanie; biblioteka: `SheetFetch.link_outside_range`,
  `DownloadResult.link_outside_range` (dla `full_sheet/`: pola
  `full_link_outside_range`).
- NMT/NMPT/orto: drugie dowiazanie
  `<segment>/full_sheet/<hierarchia>/<godlo>.<ext>` do najnowszego
  lokalnego lotu oznaczonego w skorowidzu GUGiK jako pelny
  (`calyArkuszWypelnionyTrescia = TAK`; pelny = w granicach Polski). Ta sama
  mechanika co sciezka standardowa: hardlink bez kosztu miejsca (kopia, gdy
  hardlink niedostepny), nigdy wstecz, sidecar z `extra.link_target`. Gdy
  najnowszy lot jest pelny, oba dowiazania wskazuja ten sam plik.
  `FileStorage.list_files()` pomija `full_sheet/`, `FileStorage.delete()`
  usuwa oba dowiazania (pliki w `kampanie/` zostaja); nowe
  `FileStorage.get_full_sheet_path()`. Biblioteka: `SheetFetch.full_link`,
  `SheetFetch.full_link_outside_range`, `DownloadResult.full_links`,
  `DownloadResult.full_link_outside_range`.
- Biblioteka: `DownloadManager(full_sheet=True)` (wlasciwosc
  `full_sheet`) — gdy najnowszy lot arkusza w przedziale lat nie jest
  pelny, pobiera dodatkowo najnowszy pelny lot z tego przedzialu
  (najwyzej jeden dodatkowy lot na arkusz) i dowiazuje go w `full_sheet/`;
  sciezka standardowa nadal wskazuje najnowszy lot. Sidecar kampanii takiego
  zadania ma `request.full_sheet: true`. Arkusze bez pelnego lotu
  w skorowidzu: `DownloadResult.without_full`. Provider bez kampanii
  z `full_sheet=True` = `ValidationError`.
- CLI `download --full-sheet` (NMT/NMPT/orto PL, takze z flagami roku):
  gdy najnowszy lot arkusza nie jest pelny, pobiera dodatkowo najnowszy
  pelny lot z zakresu i dowiazuje go w `<segment>/full_sheet/`. Podsumowanie
  liczy pliki kampanii (`Downloaded 2 campaign files for 1 sheets ...`).
  `--full-sheet` z `--product laz` albo `--target-crs` = `Error:` przed
  siecia (kod 1); dla CZ jak inne opcje kampanii (`Error:` bez PL, `Info:`
  dla PL+CZ pod `--country auto`). Z `--campaigns all` bez skutku.
- `--geometry` z plikiem GPKG o wielu warstwach bez `--layer` (`download`,
  `landcover download`, `soilgrids hsg`): jeden `Info:` na stderr (takze
  z `-q`) z nazwa uzytej pierwszej warstwy, lista pozostalych i podpowiedzia
  `--layer`. Wybor warstwy bez zmian.
- `--country auto` dla obszaru PL+CZ bez `--vertical-crs`: jeden `Info:` przed
  pobraniem, ze czesc PL jest w EVRF2007, a czesc CZ w Bpv (roznica ok.
  0,11-0,15 m), z podpowiedzia `--vertical-crs EVRF2007` (jeden uklad dla
  obu). Uklady domyslne bez zmian. Obwiednie krajow sa prostokatne, wiec
  komunikat pojawia sie tez dla zadan, w ktorych czesc CZ okaze sie pusta.

### Zmienione

- CLI `download --bbox/--geometry --target-crs` (PL): wycinek z WCS GUGiK
  zamiast mozaiki arkuszy (ADR-035) — siatka arkuszy 1 m, kompozycja lotow
  serwera, nodata -9999 poza ladem PL (maska PRG), nazwa
  `<wsp>_<RRRRMMDD>.tif`, kazde uruchomienie pobiera (bez `Skipped`; `--force`,
  `--workers` i `--scale` bez wplywu). `--resolution 5m --target-crs` =
  `Error:` (kod 1, przed siecia). Zamiast listy arkuszy i komunikatow
  o arkuszach (`Warning:` R5/E13/I-1, `Info:` W1) jest `Info:` o liczbie
  zapytan WCS (gdy > 1 albo wynik >= 1 GiB) i `Warning:`, gdy obszar lezy
  w calosci poza ladem PL. Flagi roku, `--campaigns all` i `--full-sheet`
  z `--target-crs` zostaja `Error:` (nowa tresc). Co zrobic: wycinek 5 m albo
  najnowszy lot arkuszy (ADR-028) — pobierz arkusze bez `--target-crs`
  (albo API arkuszowe); skrypty szukajace pliku po nazwie bez daty — dopasuj
  wzorzec `<wsp>_*.tif`; starsze wycinki bez daty zostaja nietkniete.
- `download_pl_cutout()` pobiera wycinek z WCS GUGiK (`run_pl_wcs_cutout`):
  siatka arkuszy 1 m, kompozycja lotow serwera (nie najnowszy lot ADR-028),
  nodata -9999 poza ladem PL (maska PRG), nazwa z data pobrania
  `<wsp>_<RRRRMMDD>.tif`, kazde wywolanie pobiera (bez `skipped`),
  `resolution="5m"` = `ValidationError`. Parametry arkuszowe `geometry`,
  `layer`, `scale`, `max_workers`, `force`, `on_progress`, `cache` nie maja
  wplywu; wartosc inna niz domyslna daje `DeprecationWarning` (usuniecie
  w 0.8.0). API arkuszowe (`prepare_pl_cutout` -> `select_pl_cutout_sheets`
  -> `run_pl_cutout`, `build_cutout_from_sheets`) dziala bez zmian i jest
  przestarzale (usuniecie w 0.8.0); `run_pl_cutout` z
  `cutout.product="nmpt"` = `ValidationError`. Co zrobic: wycinek z arkuszy
  (najnowszy lot ADR-028, 5 m) — `prepare_pl_cutout` ->
  `select_pl_cutout_sheets` -> `run_pl_cutout`; nie podawaj parametrow
  arkuszowych `download_pl_cutout`; kod szukajacy pliku po nazwie bez daty —
  uzyj `PlCutoutResult.path`.
- `Warning:` o niepelnej najnowszej kampanii (E13) dzieli arkusze: "pelny
  lot w <segment>/full_sheet/", "brak pelnego lotu w skorowidzu" (z flagami
  roku: "... w zakresie lat zadania") i "pelny lot nie pobrany ... — uzyj
  --full-sheet". Komunikaty o opcjach kampanii
  dla CZ wymieniaja `--full-sheet`. Skrypty dopasowujace stary tekst
  trzeba poprawic.
- Komunikat CLI o arkuszach bez danych GUGiK nie zgaduje przyczyny
  "(morze, obszar za granica)": mowi, ze skorowidz GUGiK nie ma tych
  arkuszy dla wybranego produktu i rozdzielczosci, a morze, granice i brak
  NMT 5 m w czesci kraju podaje jako przyklady (sprawdzone na zywo: np.
  `N-34-130-D-d --resolution 5m` — 6 z 16 arkuszy bez 5 m, NMT 1 m jest).
  Skrypty dopasowujace stary tekst trzeba poprawic.
- `--year` z `--product nmt|nmpt|orto` nie jest juz ignorowany: pobiera
  wskazany rocznik albo zwraca `Error:` z lista lat. Co zrobic: usun
  `--year` podawany tylko "na wszelki wypadek" albo wybierz odpowiedni
  przedzial `--min-year`/`--max-year`.
- `--year`/`--max-year` z `--target-crs` zwracaja `Error:` (jak wczesniej
  `--min-year`). Co zrobic: nie podawaj flag roku dla wycinka (wycinek
  z WCS ma kompozycje lotow serwera, bez wyboru roku).
- `--campaigns all --min-year` zawsze odpytuje wszystkie warstwy skorowidza,
  zeby moc podac pelna liste rocznikow. Wpisy `campaigns_cache` ze skanu
  czesciowego sa odpytywane ponownie. Co zrobic: nic (koszt 1-3 zapytan
  GetFeatureInfo wiecej na arkusz raz na 7 dni).
- `DownloadManager(min_year=...)`: arkusz z danymi tylko poza przedzialem
  zatrzymuje cale zadanie (takze liste/hierarchie) przed pobraniem, zamiast
  byc pominietym. Awaria sprawdzenia skorowidza tez zatrzymuje zadanie;
  lokalny fallback bez weryfikacji nadal dziala bez granic roku.
  Co zrobic: dla list z celowym pominieciem starszych arkuszy pobierz bez
  granicy i odfiltruj po `extra.campaign.date`, albo obniz granice.
- `validate_campaign_args(campaigns, min_year, max_year)` ma nowy
  obowiazkowy argument (funkcja wewnetrzna, poza `__all__`). Co zrobic: kod
  wolajacy ja bezposrednio dodaje `max_year`.
- LAZ `--year`/`--min-year`: czesci obszaru dostepne tylko w innych
  rocznikach byly pobierane czesciowo bez komunikatu; teraz zadanie
  zatrzymuje sie przed pobraniem, podaje roczniki kafli i podpowiedz.
  WFS pyta o wszystkie roczniki uslugi takze z `--year`. Co zrobic:
  jesli chcesz swiadomie pobrac mniej danych, zastosuj podpowiedz
  `--min-year`/`--max-year` lub zawez `--bbox`.
- `mosaic_and_crop()` bez `dtype=` przy zrodlach o roznych typach pasm
  (np. ASC int32 obok float32) konczy sie `ValidationError` z lista typow;
  dotad wynik dostawal typ pierwszego zrodla (np. wysokosci float obciete
  do liczb calkowitych bez sladu). Co zrobic: przy mieszanych zrodlach
  podaj `dtype=` (np. `"float32"`).
- `download_bbox()` NMT 1 m KRON86 (GeoTIFF; takze
  `DownloadManager.download_bbox`): zasieg pliku to bbox rozszerzony na
  zewnatrz do siatki zrodla (krawedzie pikseli `k + 0,5` m, < 1 px z kazdej
  strony), a obszar powyzej 16 Mpx jest pobierany kawalkami i skladany bez
  przeprobkowania (ADR-034). Sidecar `request.bbox` = bbox zadania. Co
  zrobic: nic; kto liczyl na zasieg rowny bboxowi, czyta zasieg z pliku.
  Ortofotomapa i PNG/JPEG — jedno zapytanie jak dotad (NMPT: nizej).
- `download_bbox()` NMT 1 m EVRF2007 dziala (dotad `ValidationError`
  o wycofanym endpoincie): wysokosci float32 z WCS `DigitalTerrainModel`
  (`image/x-aaigrid`, zapisywany jako GeoTIFF EPSG:2180) na siatce arkuszy
  1 m; `is_wcs_available()` EVRF2007 = `True`, kanal WCS `pl.gugik.nmt_1m`
  w rejestrze ma oba uklady wysokosci. Co zrobic: nic; kto lapal
  `ValidationError` dla EVRF2007, moze usunac obejscie.
- `download_bbox()` NMPT: rozdzielczosc 1 m (`SCALEFACTOR=0.5`; dotad
  0,5 m) na siatce arkuszy 1 m, kawalkami jak NMT; rejestr `pl.gugik.nmpt`
  ma kanal WCS `bbox_raster`. Co zrobic: nic; wynik odpowiada arkuszom
  NMPT 1 m (nad lotem 0,5 m — piksel 0,5 m o srodku na pelnym metrze).
- `download_bbox()` NMT EVRF2007 i NMPT pobiera kawalki `image/x-aaigrid`
  (NMT do 1 Mpx; NMPT do 4 Mpx pikseli coverage 0,5 m = 1 Mpx wyniku 1 m —
  zawieszenia hosta trafiaja kawalki kazdego rozmiaru, wiec mniej kawalkow
  to mniej ponowien; pomiar `docs/research/2026-10-11-nmpt-asc-tuning/`;
  ASC ok. 20 s/Mpx i ok. 20 MB/Mpx; dluzsze zadanie milczy przed pierwszym
  bajtem dluzej niz timeout odczytu 30 s). KRON86 NMT bez zmian (GeoTIFF,
  16 Mpx). Kazde zapytanie WCS z siatka (NMT, NMPT, takze KRON86) ma
  parzysta szerokosc i wysokosc: zakres wyrownany do siatki jest
  poszerzany o najwyzej 1 px na wschod/poludnie i przycinany po zszyciu
  (przy nieparzystym rozmiarze serwer bierze srodkowy wiersz i kolumne
  z sasiedniego piksela zrodla, gdy przeprobkowuje — NMPT `SCALEFACTOR`,
  NMT 1 m nad lotem 0,5 m; pomiar na zywo 2026-10-11). Kawalek
  `image/x-aaigrid` czeka na pierwszy bajt co najmniej 120 s
  (`WCS_ASC_READ_TIMEOUT`; `timeout` wolajacego, gdy wiekszy): serwer nie
  wysyla nic przed policzeniem calego kawalka (NMPT: 19-106 s na zywo).
  Co zrobic: nic; duze obszary EVRF2007/NMPT trwaja odpowiednio dluzej
  niz KRON86.
- Biblioteka: funkcje geometrii (`get_overall_bbox`, `read_feature_bboxes`,
  `find_sheets_for_geometry`, `read_source_crs`) przy GPKG z wieloma
  warstwami bez `layer=` loguja wybor pierwszej warstwy jako `WARNING`
  (dotad `INFO`, domyslnie niewidoczne). Co zrobic: podaj `layer=`, jesli
  komunikat przeszkadza.

### Naprawione

- Zapytanie o powiaty BDOT10k (WFS PRG) rozszerza obszar na zewnatrz
  z dokladnoscia do milimetra; wczesniej zaokraglenie do pelnych metrow
  moglo pominac powiat stykajacy sie z obszarem w pasie do 0,5 m,
  a `teryt_for_point` pytal raz o sam punkt, raz o kwadrat 2 m.
- WFS PRG: odpowiedz, w ktorej `numberReturned` rozni sie od liczby
  odczytanych kodow powiatow, konczy sie `DownloadError` zamiast cicho
  krotszej listy powiatow (i brakujacego pakietu BDOT10k).
- BDOT10k: opcja `timeout` (`Bdot10kProvider.download_by_bbox/godlo`,
  `LandCoverManager.download_by_bbox/godlo/download_all_counties`)
  dziala tez na zapytanie o powiat w WFS PRG; wczesniej to zapytanie
  mialo zawsze 30 s. Bez `timeout` w menedzerze zostaje 30 s.
- Godla z cyframi spoza ASCII (np. pelnej szerokosci `M-３３-８-A`,
  `6.１４５.２０`, CZ `７３０_５５５５`) sa odrzucane (`ParseError`);
  wczesniej PL-1992 i PL-2000 przechodzily walidacje i trafialy do sciezek
  i sidecarow w innej postaci niz godlo GUGiK. Co zrobic: podac godlo
  cyframi `0-9`.
- BDOT10k `keep_raw=True`: nieudany zapis oryginalnego ZIP przy ponownym
  pobraniu zostawia poprzedni GPKG i jego sidecar bez zmian (scalony GPKG
  zastepuje poprzedni dopiero po zapisie ZIP). Wczesniej poprzedni GPKG
  byl nadpisany, a potem usuniety, i zostawal sidecar bez pliku danych.
- `download_bbox()` NMT/NMPT/ortofotomapy nie zapisuje juz raportu bledu
  WCS (`ows:ExceptionReport`, XML z HTTP 200) jako pliku rastra — to
  `DownloadError`. NMT 1 m z bboxem poza siatka zrodla dawal tresc
  przesunieta o ulamek piksela wzgledem georeferencji (serwer probkuje do
  siatki zadania; pomiar `docs/research/2026-10-10-wcs-limits/raport.md`);
  teraz zadanie jest wyrownane do siatki zrodla.
- `download_bbox()` NMPT zwracal 3-pasmowy RGB uint8 (podglad kolorow)
  zamiast wysokosci; teraz 1 pasmo float32 z wysokosciami (1 m na siatce
  arkuszy, bit w bit z arkuszami NMPT 1 m). Wpis WCS NMT EVRF2007
  wskazywal nieistniejacy endpoint (`DigitalTerrainModelFormatTIFFEVRF2007`,
  HTTP 404) — zastapiony dzialajacym `DigitalTerrainModel`.

## [0.7.1] - 2026-10-09

### Dodane

- Roadmapa do v1.0.0 w dokumentacji (`docs/SCOPE.md` 3.3, `docs/PRD.md`
  sekcja 8): komplet publicznych danych GUGiK, gotowe dane dla kazdego
  produktu, manager danych (magazyn wersjonowany, manifest projektu),
  wtyczka QGIS i GUI webowe.
- Stabilne publiczne API: `get_with_retry`, `make_gugik_session`,
  `mosaic_and_crop`, `check_source_grid` eksportowane z `kartograf`.
- `MetadataCache(strict=True)`: blad SQLite konczy sie `CacheError`
  (nowy wyjatek) zamiast cichego wylaczenia cache.
- Sidecar: `sha256` i `size_bytes` pliku danych na gornym poziomie
  (wszystkie produkty). Sidecar arkusza NMT/NMPT/orto: w `extra.source`
  `height_rmse_m`, `position_rmse_m`, `archive_module`,
  `declared_vertical_crs` z rekordu skorowidza. Wpisy cache rekordow
  sprzed 0.7.1 sa odpytywane ponownie.
- Weryfikacja arkuszy GUGiK (B4): URL rekordu skorowidza musi zawierac
  godlo (NMT, NMPT, orto), a zasieg z naglowka ASC (NMT/NMPT) musi lezec
  w ramie godla (co najmniej 50 % powierzchni pliku, rama w ukladzie
  pliku — arkusze PL-2000 publikowane w EPSG:2180 przechodza);
  rozbieznosc = `DownloadError` arkusza, plik nie zostaje zapisany.
- `discover_teryts_for_bbox(bbox, *, session, cache)` i
  `teryt_for_point(x, y, crs, ...)`: kody TERYT powiatow z WFS PRG GUGiK
  (filtr po geometrii); blad uslugi albo lista obcieta stronicowaniem =
  `DownloadError`, pusta lista tylko przy poprawnej odpowiedzi bez
  obiektow. Odpowiedzi trafiaja do cache metadanych (nowa tabela
  `teryt_bbox_cache`; `cache stats`: `TERYT entries` liczy punkty i
  obszary).
- BDOT10k z wielu powiatow: `LandCoverManager.download_all_counties(bbox=
  | godlo=, layers=)` pobiera pakiet KAZDEGO powiatu przecinajacego obszar
  (TERYT z WFS PRG), opcjonalnie tylko wybrane warstwy (np. `PTWP`,
  `SWRS`); `Bdot10kProvider.download_package` zwraca `Bdot10kPackage`
  (`path`, `teryt`, `url`, `format`; eksport z `kartograf`).
  `LandCoverManager(cache=)` przekazuje cache metadanych providerom
  tworzonym po nazwie (BDOT10k, SoilGrids).
- Sidecar BDOT10k: `extra.source` (`url`, `teryt`, `format`) i `extra.http`
  (`etag`, `last_modified`, `content_length` z odpowiedzi; serwer paczek
  GUGiK podaje dzis tylko `Content-Length`). `keep_raw=True` zachowuje
  oryginalny ZIP GUGiK obok GPKG (pelny pakiet: `bdot10k_teryt_<TERYT>_GPKG.zip`
  bez tokenu warstw, ten sam plik niezaleznie od filtra `layers=`, z wlasnym
  sidecarem; tylko GPKG). `Bdot10kPackage` ma pola `http` i `raw_path`.
- Wycinek CZ w bibliotece: `download_cz_cutout(bbox, output_dir=,
  target_crs=, vertical_crs=, resolution=)` (np. EPSG:2180 + EVRF2007;
  siatka od zadanego obszaru, jak w CLI) i `run_cz_cutout` z wlasnym
  providerem; wynik `CzCutoutResult` z flaga `all_nodata` (takze
  w sidecarze i w logu), sidecar pisze biblioteka. Podzial obszaru na
  kraje: `countries_for_bbox`, `split_bbox_by_country`. CLI (`--bbox`/
  `--geometry` dla CZ) korzysta z tej samej implementacji — komunikaty
  i kody wyjscia bez zmian, sidecar wycinka CZ dostaje
  `extra.all_nodata` (`true`/`false`).
- `build_cutout_from_sheets(sheet_paths, bbox, target_crs, output_path, *,
  resolution, vertical_crs)`: wycinek NMT PL z lokalnych arkuszy bez
  zapytan sieciowych, wynik i sidecar pod sciezka podana przez
  wywolujacego (reguly siatki jak w `download_pl_cutout`). Brakujacy albo
  nieczytelny arkusz i `output_path` rowny arkuszowi wejsciowemu =
  `ValidationError` przed zapisem.
- `hsg_from_rasters(clay, sand, silt, *, bbox, crs, pixel_m, output_path)`:
  HSG z gotowych rastrow SoilGrids (g/kg) na jawnie podanej siatce, bez
  wartosci domyslnych (nodata wejsc tylko z tagu, jak w
  `calculate_hsg_by_bbox`); sidecar z `sha256` warstw wejsciowych
  (`extra.source_files`: `name`, `file`, `sha256`; `extra.source_layers`
  jak w `calculate_hsg_by_bbox` — lista nazw `clay`, `sand`, `silt`).
- Weryfikacja ukladu wysokosci rekordu skorowidza GUGiK (NMT/NMPT): pole
  `ukladWspolrzednychPionowych` musi odpowiadac zadanemu ukladowi
  (`PL-KRON86-NH` dla KRON86, `PL-EVRF2007-NH` dla EVRF2007); inna wartosc
  = `DownloadError` kampanii przed pobraniem pliku (`newest` i `all`, takze
  `GugikProvider.download`). Rekord bez tego pola jest przyjmowany.
  Nowe: `kartograf.download.campaigns.verify_record_vertical_crs`,
  `RECORD_VERTICAL_CRS`, `kartograf.providers.pl.require_nmt_vertical_crs`
  (`nmt_vertical_crs` bez zmian).

### Zmienione

- `DownloadManager.download_sheet()` ustawia `last_result` takze dla
  pojedynczego arkusza (jednoelementowy `DownloadResult`); dotad `None`.
  Co zrobic: kod, ktory po `download_sheet()` traktowal `last_result`
  jako `None`, moze czytac z niego wynik arkusza.
- Udokumentowano: przy kampaniach (`campaigns=`) zrodlem pochodzenia
  arkusza jest sidecar, nie `source_info()` (A12).
- Godla PL-1992 spoza zakresu nomenklatury (pas inny niz M/N, slup spoza
  33-35, arkusz 1:200 000 spoza 1-144, np. `N-34-999-D`) koncza sie
  `ParseError` przed jakimkolwiek zapytaniem sieciowym; dotad trafialy do
  uslug z bboxem `inf` albo poza Polska. Co zrobic: nic, jesli godla sa
  poprawne; kod, ktory dla takich godel oczekiwal `DownloadError` albo
  pustego wyniku, powinien lapac `ParseError` (albo `ValidationError`).
- `ParseError` dziedziczy po `ValidationError` — `except ValidationError`
  lapie tez bledy godel. Co zrobic: gdy kod obsluguje oba wyjatki osobno,
  `except ParseError` musi stac przed `except ValidationError`.
- Liczby w godle PL-1992 sa zapisywane bez zer wiodacych, jak w skorowidzu
  GUGiK (`M-33-036-A` -> `M-33-36-A`) — w sciezce, sidecarze i wyniku,
  takze w nazwach plikow land cover (`..._godlo_M-33-36-A`) i w domyslnej
  nazwie wyniku `kartograf soilgrids hsg --godlo`
  (`hsg_M-33-36-A_<glebokosc>.tif`). Pliki zapisane wczesniej pod godlem
  z zerami wiodacymi nie sa rozpoznawane; pobierz je ponownie.
- `find_sheets_for_bbox` zwraca tylko godla z zakresu nomenklatury PL-1992:
  obszar wychodzacy poza pasy M/N i slupy 33-35 (np. bbox przez 12E)
  daje godla tylko jego polskiej czesci, obszar calkowicie poza zakresem —
  pusta liste (dotad takze godla spoza zakresu, ktore nie maja danych).
  Co zrobic: nic — usuniete godla i tak nie mialy danych; kod, ktory
  traktowal pusta liste jako blad, dostaje ja teraz dla obszaru calkowicie
  poza Polska.
- `kartograf landcover download --source bdot10k` z `--bbox`, `--godlo`
  albo `--geometry` pobiera wszystkie powiaty z obszaru (dotad jeden, ze
  srodka obszaru — reszta obszaru po cichu bez danych) i drukuje linie
  `Downloaded to:` dla kazdego pliku.
- Plik BDOT10k nazywa sie zawsze `bdot10k_teryt_<TERYT>.gpkg` (`.zip` dla
  SHP), takze przy `--bbox`/`--godlo`/`--geometry` — zawiera caly pakiet
  powiatu. Dotychczasowe `bdot10k_bbox_*`/`bdot10k_godlo_*` nie sa
  rozpoznawane; pobierz obszar ponownie. Plik z filtrem warstw nosi ich
  kody w nazwie (`bdot10k_PTWP-SWRS_teryt_<TERYT>.gpkg`).
- `LandCoverManager.download_by_bbox`/`download_by_godlo` dla BDOT10k: obszar
  z kilku powiatow konczy sie `ValidationError` z lista kodow (uzyj
  `download_all_counties`), obszar bez powiatu — `NoCoverageError`; sidecar
  pliku jednego powiatu ma `extra.parent_request` (obszar zadania).
- `Bdot10kProvider.download_by_bbox` (i `LandCoverManager` dla BDOT10k)
  przyjmuje obszar w dowolnym obslugiwanym ukladzie — dotad uklad inny niz
  EPSG:2180 konczyl sie `ValueError`; obszar jest przeliczany do EPSG:2180
  przy zapytaniu PRG. Prywatne `Bdot10kProvider._get_teryt_for_point`
  (WMS GetFeatureInfo) i `WMS_ENDPOINT` usuniete bez zamiennika — uzyj
  `teryt_for_point`/`discover_teryts_for_bbox`.
- Biblioteka: `create_nmt_provider`, `DownloadManager` (bez providera albo
  z providerem bez wlasnego `vertical_crs`) i `download_pl_cutout` przy
  `resolution="5m"` i `vertical_crs="KRON86"` koncza sie `ValidationError`
  (NMT 5 m istnieje tylko w EVRF2007); dotad po cichu zamienialy uklad na
  EVRF2007 z ostrzezeniem w logu. Co zrobic: podaj `vertical_crs="EVRF2007"`
  (albo `resolution="1m"`, gdy potrzebny jest KRON86). CLI — patrz wpis
  nizej (tez blad).
- CLI: `kartograf download ... --resolution 5m --vertical-crs KRON86`
  (NMT PL: godlo, hierarchia, `--bbox`/`--geometry`, wycinek `--target-crs`,
  takze `--country auto`) konczy sie `Error: NMT 5m (PL) jest dostepny tylko
  w EVRF2007 ...` i kodem 1, zanim cokolwiek pojdzie w siec; dotad CLI
  zamienialo uklad na EVRF2007 z komunikatem `Info:` i pobieralo (kod 0).
  `--resolution 5m` bez `--vertical-crs` dziala jak dotad (EVRF2007). Co
  zrobic: pomin `--vertical-crs` albo podaj `--vertical-crs EVRF2007`;
  dla KRON86 uzyj `--resolution 1m`.
- Pobieranie arkuszy NMT/NMPT/orto GUGiK (CLI i `DownloadManager`, takze
  wycinek `--target-crs`) odrzuca rekordy i pliki, ktore w 0.7.0 przechodzily:
  URL rekordu bez godla, plik ASC poza rama godla (B4) oraz rekord NMT/NMPT
  deklarujacy inny uklad wysokosci niz zadany — `DownloadError` arkusza
  (kampanii), plik nie zostaje zapisany. Kontrole rekordu dzialaja przed
  pominieciem juz pobranej kampanii, a `--force` (`skip_existing=False`) ich
  nie wylacza. Co zrobic: sprawdz rekord w skorowidzu GUGiK (geoportal) —
  komunikat podaje godlo i rozbieznosc; to blad danych u zrodla, ktory
  warto zglosic GUGiK; dla innych arkuszy pobieranie trwa dalej (lista:
  porazka arkusza wg R5, `--campaigns all`: pozostale kampanie).
- Komunikat `Error: --campaigns all nie dziala z --target-crs` nie odsyla
  juz do "narzedzia 0.7.1" (skladanie kampanii nie ma przypisanego wydania,
  ADR-030 errata 6); kod wyjscia bez zmian.
- `kartograf download --year RRRR` i `--min-density N` z `--product`
  nmt/nmpt/orto koncza sie `Error:` i kodem 1 przed siecia (dotad opcje byly
  po cichu pomijane: kod 0 i najnowsze dane). Dotyczy wszystkich torow
  (godlo, hierarchia, lista arkuszy, `--bbox`, `--geometry`, `--target-crs`,
  `--country auto`, CZ); `--product laz` bez zmian. Wybor roku dla
  NMT/NMPT/orto bedzie w 0.7.2. Co zrobic: pomin opcje albo — dla roku —
  uzyj `--min-year RRRR` (najnowsza kampania nie starsza niz podany rok;
  tylko PL, bez `--target-crs`; dla zadan wylacznie CZ — CUZK nie ma wyboru
  roku, komunikat kaze pominac `--year`); skrypty przekazujace `--year`/
  `--min-density` do innych produktow niz LAZ musza je usunac.

### Naprawione

- Scalanie paczki BDOT10k nie pomija juz po cichu tabeli o powtorzonej
  nazwie — to `DownloadError`.
- BDOT10k: warstwy paczki sa rozpakowywane strumieniowo (bez wczytywania
  calej warstwy do pamieci), a `keep_raw` zapisuje ZIP bez drugiej kopii
  w pamieci. Blad wejscia-wyjscia przy rozpakowaniu, scalaniu albo zapisie
  ZIP (brak miejsca, brak pamieci) to `DownloadError` (CLI: `Error:` z opisem,
  kod 1), nie goly `OSError`. Nieudany zapis oryginalnego ZIP usuwa juz
  zapisany GPKG — nie zostaje plik danych bez sidecara.
- `cache stats`: `TERYT entries` liczy odpowiedzi PRG z `landcover download`
  (U5).

## [0.7.0] - 2026-10-08

Wydanie wielokrajowe. Najwazniejsze nowosci wzgledem 0.6.1:

- **Czechy (CUZK, etap 1):** NMT DMR 5G (2 m, kafle TM33) i DMR 4G (5 m,
  arkusze SM5) przez godlo albo `--bbox`/`--geometry`; `--country
  {pl,cz,auto}` (domyslnie `auto`) dzieli obszar przygraniczny na osobne
  pliki per kraj ze wspolnym `extra.parent_request`.
- **Nowy produkt LAZ:** chmury punktow LIDAR (ALS) z GUGiK przez WFS
  (`--product laz`), domyslnie najnowszy kafel per obszar (ADR-029).
- **Wycinek PL `--target-crs`:** jeden scalony GeoTIFF NMT dla bboxa albo
  geometrii w EPSG:2180/5514/3045, reprojekcja lokalna przypieta operacja
  (ADR-027); w bibliotece `download_pl_cutout`.
- **Kampanie GUGiK:** `--campaigns {newest,all}` i `--min-year`; pliki
  w `<segment>/kampanie/`, sciezka standardowa to dowiazanie twarde do
  najnowszej kampanii (ADR-030).
- **Nowy uklad `data/` i sidecar `.meta.json`:** segmenty
  `<produkt>/<kraj>_<uklad>[_<wariant>][_<vcrs>]` (ADR-026), obok kazdego
  pobranego pliku metadane CRS/licencja/nodata/zadanie (klucze ADR-031).
- **Niezawodnosc:** jeden transport HTTP (ponowienia tylko siec/429/5xx),
  warstwy skorowidza GUGiK wylacznie z GetCapabilities, jawne
  `NoCoverageError` zamiast cichych zamiennikow, cache metadanych odporny
  na uszkodzenie.

### Zmiany lamiace (BREAKING)

#### Uklad `data/` i pliki wynikowe
- **Nowy uklad `data/`** (ADR-026): segmenty
  `<produkt>/<kraj>_<uklad>[_<wariant>][_<vcrs>]` koduja jawnie kraj, uklad
  poziomy (PL: 1992/2000 — domkniecie odroczonego ADR-017) i pionowy
  (kron86/evrf2007/bpv; orto bez pionowego), np. `nmt/pl_1992_1m_evrf2007/`,
  `orto/pl_1992/`. `<uklad>` wynika z formatu godla KAZDEGO pliku z osobna
  (kropki -> `2000`, myslniki -> `1992`; kafle LAZ — `uklad_xy` kafla).
  Kartograf nie migruje `data/` automatycznie (tabela w "Przejscie
  z 0.6.1"). Katalog `landcover/` bez zmian (nazwy plikow CORINE/SoilGrids
  — nizej). Kanoniczny opis: `docs/ARCHITECTURE.md`
  sekcja 3.
- **Kampanie (ADR-030):** prawdziwe pliki NMT/NMPT/orto PL leza wylacznie
  w `<segment>/kampanie/<data>_<id>/<hierarchia godla>/<godlo>.<ext>`;
  sciezka standardowa `<segment>/<hierarchia>/<godlo>.<ext>` jest
  dowiazaniem twardym (albo kopia) do najnowszej lokalnej kampanii
  (szczegoly w Dodane, "Kampanie GUGiK"). Zwykly plik w sciezce
  standardowej (np. przeniesiony z 0.6.1) jest dla Kartografa nieznany:
  pierwsze uruchomienie pobiera go ponownie do `kampanie/` i zastepuje
  dowiazaniem. Kopiowanie `data/` tylko z zachowaniem hardlinkow
  (`rsync -aH`/`cp -a`), inaczej powstaje duplikat.
- **Domyslne `newest` pyta skorowidz przy kazdym uruchomieniu**, gdy cache
  rekordu (7 dni) wygasl, i pobiera nowsza kampanie, jesli sie pojawila;
  ponowne uruchomienie "bez sieci" dziala tylko w oknie cache.
- `FileStorage.list_files()` domyslnie zwraca sciezki standardowe — bez
  `kampanie/` i bez wiszacych dowiazan (`list_files(campaigns=True)` = tylko
  `kampanie/`).
- **BDOT10k `--format SHP` / `format="SHP"`** zapisuje archiwum ZIP
  z shapefile'ami pod rozszerzeniem `.zip` (np. `bdot10k_teryt_1465.zip`,
  sidecar obok) i zwraca te sciezke (takze przez bbox/godlo); w 0.6.1 ZIP
  trafial pod podana sciezke, zwykle `.gpkg`, ktora udawala GeoPackage.
  CLI drukuje faktyczna sciezke (review N1).
- **`LandCoverManager.download_by_teryt/download_by_bbox/download_by_godlo`
  bez `output_path` nazywaja pliki tak jak `download()`** — bylo
  `CORINE Land Cover_N-34-130-D.gpkg` (spacje, etykieta zrodla), jest
  `corine_2018_godlo_N-34-130-D.<ext>` (wzorzec nizej); rozszerzenie nadaje
  provider (CORINE `.tif`/`.png`, SoilGrids `.tif`). Skrypty skladajace
  sciezke wyniku z nazwy zrodla wymagaja poprawki (A5-2, N14).
- **`soilgrids hsg` nazywa domyslny plik z glebokoscia:**
  `hsg_<godlo>_<depth>.tif` (np. `hsg_N-34-130-D_0-5cm.tif`) i
  `hsg_bbox_<depth>.tif`; bylo `hsg_<godlo>.tif` / `hsg_bbox.tif`, wiec
  kolejne `--depth` po cichu nadpisywaly wynik. Sidecar HSG z `--godlo`
  / `calculate_hsg_by_godlo` zapisuje tez `request.sheet` (obok
  pochodnego `bbox`/`bbox_crs`); `--bbox`/`--geometry` bez `sheet`.
  Skrypty skladajace sciezke wyniku HSG wymagaja poprawki. Statystyka
  (`stat`) nie jest parametrem CLI (zawsze `mean`); w bibliotece nazwe
  pliku wybiera wywolujacy (`output_path`).
- **Nazwy plikow land cover niosa parametry tresci** (U3, cicha utrata
  danych w 0.6.1): `soilgrids ... --property clay`, a potem `--property
  sand` dla tego samego obszaru zapisywaly ten sam plik
  `soilgrids_bbox_<coords>.tif` — drugi wynik po cichu nadpisywal pierwszy;
  tak samo CORINE z innym `--year`. Nowy wzorzec
  `<zrodlo>[_<parametr>...]_<tryb>_<id>.<ext>`, `<zrodlo>` = wartosc
  `--source` (`bdot10k`/`corine`/`soilgrids`), parametry z wartosciami
  domyslnymi wlacznie:
  `soilgrids_<property>_<depth>_<stat>_bbox_<coords>.tif` (np.
  `soilgrids_clay_0-5cm_mean_bbox_770000_509000_772000_511000.tif`),
  `corine_<year>_godlo_N-34-130-D.tif` (`.png` z podgladu WMS); bylo
  `soilgrids_bbox_<coords>.tif` i `corine_land_cover_bbox_<coords>.<ext>`.
  BDOT10k bez zmian (`bdot10k_teryt_1465.gpkg`/`.zip` — format rozroznia
  rozszerzenie). Te same parametry = ta sama sciezka (ponowne pobranie
  nadpisuje jak dotad). Sidecar zapisuje parametry w `request`
  (`property`/`depth`/`stat`, `year`, `format`), a `nodata` wyniku GeoTIFF
  odczytuje z pliku (`null`, gdy plik go nie deklaruje). Pliki z 0.6.1
  (stare nazwy) nie sa rozpoznawane — Kartograf ich nie zmienia ani nie
  czyta.
- **`DownloadManager` bierze segment z providera:** bez jawnego `storage=`
  podkatalog pochodzi z deskryptora providera (bylo: zawsze segment NMT 1m,
  wiec `DownloadManager(provider=GugikNmptProvider())` pisal do katalogu NMT
  i przy `--force` nadpisywal jego pliki; teraz `nmpt/pl_<uklad>_1m_<vcrs>/`,
  A2-2), a uklad pionowy segmentu z PROVIDERA, nie z flagi managera
  `vertical_crs=` (`DownloadManager(provider=GugikProvider(vertical_crs=
  "KRON86"))` pisal do `nmt/pl_1992_1m_evrf2007/` obok sidecara z
  `EPSG:9650`; dotyczy biblioteki, nie CLI).
- **Katalogi wyjsciowe powstaja dopiero przy zapisie:** `LandCoverManager()`
  nie tworzy `output_dir` (domyslnie `./data/landcover`) w konstruktorze,
  a `MetadataCache()` nie tworzy pliku `.kartograf_cache.db` przy
  konstrukcji (szczegoly w Zmienione). Kod zakladajacy istnienie
  `output_dir` zaraz po `LandCoverManager(...)` musi utworzyc go sam.

#### Sidecar `.meta.json`
- **Sidecar jest nowy w 0.7.0** (obok kazdego pobranego pliku, schemat
  `kartograf-meta/1`, opis w Dodane). Klucze sa angielskie (ADR-031) —
  konsumenci czytajacy sidecary z wersji rozwojowych 0.7.0-dev musza
  przejsc na nowe nazwy; schemat zostaje `kartograf-meta/1` (przed 0.7.0 niewydany),
  bez warstwy zgodnosci:

  | Bylo (0.7.0-dev) | Jest |
  |---|---|
  | `request.godlo` (wszystkie tory) | `request.sheet` |
  | `extra.source.godlo` | `extra.source.sheet` |
  | `extra.source.aktualnosc` / `aktualnosc_rok` | `extra.source.acquisition_date` / `acquisition_year` |
  | `extra.source.uklad` | `extra.source.declared_crs` |
  | `extra.source.zrodlo_danych` | `extra.source.data_source` |
  | `extra.source.numer_zgloszenia`, `extra.campaign.zgloszenie` | `survey_work_id` (w obu) |
  | `extra.source.skorowidz` | `extra.source.index_url` |
  | `extra.source.dt_pzgik`, `extra.campaign.dt_pzgik` | `pzgik_date` (w obu) |
  | `extra.source.kolor` (orto) | `extra.source.color` |
  | `extra.godlo_kafla` / `rok` / `gestosc` (LAZ) | `extra.tile_sheet` / `year` / `nominal_density` |
  | `extra.uwaga` (CORINE PNG) | `extra.note` |
  | `extra.podil` (CZ SM5) | `extra.cz_share` |
  | `extra.sheet_sources[]`: `godlo`, `aktualnosc` | `sheet`, `acquisition_date` |

  `teryt` zostaje (nazwa wlasna rejestru). Kanoniczna tabela:
  `docs/ARCHITECTURE.md` 3.2. Skutki dla starych lokalnych danych —
  "Przejscie z 0.6.1", dane z 0.7.0-dev.

#### API biblioteki
- **Glebokie sciezki importu providerow zmienione bez shimow**
  (`from kartograf.providers.bdot10k import Bdot10kProvider` konczy sie
  `ModuleNotFoundError`); publiczne `from kartograf import ...` BEZ zmian.
  Tabela w "Przejscie z 0.6.1".
- **Wrapper `LandCoverProvider.download_by_teryt` zweza pozycyjna arnosc**:
  pozycyjnie przyjmuje tylko `teryt`, `output_path`, `timeout`; kolejny
  argument pozycyjny (np. `format` w `Bdot10kProvider.download_by_admin_unit`
  jako 4. argument) konczy sie `TypeError` — przekazuj go jako keyword
  (`format=...`).
- **`SoilGridsProvider.download_by_teryt()` rzuca `NotImplementedError`** —
  dotad zwracal jako sukces dane dla stalego obszaru 60x60 km wokol srodka
  WOJEWODZTWA (2-cyfrowy prefiks TERYT), identyczne dla kazdej gminy.
  Uzyj `download_by_bbox()` albo `download_by_godlo()` (A4-3).
- **`GugikProvider.download_bbox(vertical_crs="EVRF2007")` konczy sie
  `ValidationError`** z remedium, przed wyjsciem w siec — GUGiK wycofal
  endpoint WCS `DigitalTerrainModelFormatTIFFEVRF2007` (404 takze dla
  GetCapabilities), wiec WCS NMT 1m dziala wylacznie w KRON86; kanal WCS
  deskryptora `pl.gugik.nmt_1m` deklaruje tylko `EPSG:9650` (WCS NMPT nie
  jest tym objety). Wysokosci EVRF2007 z bboxa: `--bbox` (arkusze OpenData)
  albo wycinek `--target-crs`/`download_pl_cutout` (A1-4).
- **`find_sheets_for_bbox()`/`find_sheets_for_geometry()`: stykajace sie
  krawedzie nie sa przecieciem** — liczy sie dodatnie pole przeciecia, wiec
  bbox rowny arkuszowi w jego ukladzie (EPSG:4326 dla PL-1992, strefa
  2176-2179 dla PL-2000) zwraca TYLKO jego arkusze (bbox w EPSG:2180
  przechodzi przez szersza obwiednie WGS84 i zwraca takze sasiadow — np.
  9 godel dla `N-34-130-D-d-2-4`). Tak samo na linii siatki i na granicy
  stref PL-2000 (A1-7, A9-1):

  | zapytanie | bylo | jest |
  |---|---|---|
  | bbox arkusza `N-34-130-D`, `--scale 1:50000` | 9 godel | 4 (`N-34-130-D-a..d`) |
  | bbox arkusza `N-34-130-D-d-2-4` (1:10000) | 4 godla | 1 |
  | bbox arkusza `6.179.12.20` (PL-2000, `--scale 1:2000`) | 9 godel | 1 |
  | punkt / bbox zdegenerowany (<= ~2e-9 jednostki) | `[]` (PL-1992) / 4 godla (PL-2000) | 1 arkusz (ten na E/N od linii siatki) |

- **`find_sheets_for_bbox`/`find_sheets_2000_for_bbox`: walidacja wejscia**
  — nieznana wartosc `system=` konczy sie `ValidationError` zamiast cichego
  fallbacku do PL-1992; bbox odwrocony (`min > max`) albo z NaN/inf —
  `ValidationError` (dotad arkusz-smiec, np. `BBox(10, 10, 5, 5)` ->
  `L-33-1-D-c-4-3`, albo `ValueError`). Bbox-punkt nadal dozwolony.
- **`get_parent()`/`get_children()`/`get_all_descendants()` i `parse
  --hierarchy` dla 1:1000000 <-> 1:500000: poprawna geometria cwiartek** —
  cwiartka liczona z pozycji arkusza 1:200000 w siatce 12x12 (bloki 6x6:
  A = NW, B = NE, C = SW, D = SE), a nie z pasow po 36 kolejnych numerow.
  72 ze 144 arkuszy 1:200000 dostaje innego rodzica niz w 0.6.x,
  a `get_all_descendants()` arkusza 1:500000 zwraca wlasciwa cwiartke
  zamiast poziomego pasa (A1-1).
- **Usuniete publiczne atrybuty i metody klas eksportowanych w `kartograf`**
  (dostep konczy sie `AttributeError`):

  | Usuniete | Zamiast |
  |---|---|
  | `MetadataCache.get_url()` / `set_url()` | `get_record()` / `set_record()` (rekord skorowidza albo potwierdzony brak pokrycia; tabela `url_cache` usuwana przy otwarciu) |
  | `WMS_LAYERS` (`GugikProvider`, `GugikNmptProvider`, `GugikOrtoProvider`) | brak listy zaszytej — warstwy z GetCapabilities (`LAYER_PATTERN` providera) |
  | `GugikProvider.FORMAT_EXTENSIONS` (takze w `GugikNmptProvider`) | `get_file_extension()` (dziedziczone z `BaseProvider`) |
  | `GugikOrtoProvider.OPENDATA_URL_PATTERN` | brak — URL arkusza z rekordu skorowidza |
  | `RETRY_BACKOFF_BASE` (`GugikProvider`, `GugikNmptProvider`, `GugikOrtoProvider`, `Bdot10kProvider`, `CorineProvider`, `SoilGridsProvider`) | `kartograf.transport.http.RETRY_BACKOFF_BASE` (jeden backoff dla wszystkich); `MAX_RETRIES` providerow wskazuje `transport.http.MAX_RETRIES` (3) |
  | `CorineProvider.DLR_YEARS` | brak (martwy kod) |
  | `SoilGridsProvider.TERYT_WMS_ENDPOINT` | brak — `download_by_teryt()` rzuca `NotImplementedError` |

- **Auth proxy: usuniety endpoint `/token` i
  `AuthProxyClient.get_access_token()`** — oddawaly surowy token do procesu
  klienta, co przeczy roli proxy (izolacja credentials, ADR-002). Token
  trafia wylacznie do hostow `*.copernicus.eu` i `*.eea.europa.eu`: `/proxy`
  i `/download` przyjmuja tylko `https` (inny schemat = 403), `/proxy`
  odrzuca (403) kazdy host spoza listy (dotad pobieralo z dowolnego URL-a
  klienta), a `/download` przekazuje zadanie do hosta `https` spoza listy
  BEZ naglowka `Authorization` (presigned `DownloadURL` CLMS bywa na CDN)
  (A4-10).
- **Fasada `kartograf.cli.commands` nie re-eksportuje juz implementacji
  komend** — import z fasady konczy sie `ImportError`; kanoniczne sa moduly
  `cli/*_cmd.py`: publiczne `cmd_landcover_download`,
  `cmd_landcover_list_layers`, `cmd_landcover_list_sources`,
  `cmd_soilgrids_hsg` oraz prywatne `_cmd_download_bbox`,
  `_cmd_download_geometry`, `_download_godlo_list`,
  `_create_provider_and_storage` (z `kartograf.cli.download_cmd`). W fasadzie
  zostaja `main`, `create_parser`, dispatchery `cmd_parse`, `cmd_download`,
  `cmd_landcover`, `cmd_soilgrids`, `cmd_cache`, `create_progress_callback`
  i helpery formatujace `format_*` (A5-1, K9).
- **`NoCoverageError` jest podklasa `DownloadError`** (`except DownloadError`
  lapie oba), a `GridMismatchError` — podklasa `ValidationError`.
- **`import kartograf` laduje eagerly `rasterio`** (GDAL/PROJ) — eksporty CZ
  w `__init__.py` importuja `providers/cuzk/client.py`, ktory importuje
  `rasterio` na poziomie modulu; koszt ok. +60 ms przy imporcie. Zepsuty
  GDAL/PROJ (np. brakujaca biblioteka natywna) psuje sam `import kartograf`,
  nie dopiero pierwsze wywolanie rastrowe — istotne dla Hydrografu/Hydrologu
  (ADR-023, "Ustalenia dodatkowe" pkt 2).

#### CLI i zachowanie
- **Domyslnym krajem jest `--country auto`** — w 0.6.1 opcji `--country` nie
  bylo i kazde zadanie szlo do GUGiK. Dla `--bbox`/`--geometry` bez jawnego
  `--country`: obszar przecinajacy obwiednie dwoch krajow jest pobierany
  z KAZDEGO z nich (osobne pliki i sidecary, wspolny
  `extra.parent_request`); obwiednia CZ jest PROSTOKATNA (siega 18,86 E
  i 51,06 N), wiec zadanie z poludniowej Polski dostaje dodatkowo plik
  i sidecar z CUZK (poza faktyczna granica raster same-nodata z `Warning:`,
  nie blad) — obejscie: jawne `--country pl`. Opcje bez odpowiednika
  czeskiego rozstrzygaja kraj do `pl` (szczegoly w Dodane, "Wybor kraju")
  (A6-3, N6-2; ADR-023 pkt 4-5).
- **Pobranie hierarchii albo listy arkuszy z porazkami konczy sie kodem 1**
  i `Error: N z M arkuszy nie pobrano (blad pobrania, nie brak danych):
  <godla> — ponow pobranie` z pelna lista — bylo: kod 0 mimo
  brakujacych arkuszy; dotyczy godla oraz `--bbox`/`--geometry` (A2-3).
  Sam brak pokrycia czesci arkuszy daje `Warning:` i kod 0 (Dodane, "NMT PL").
- **Brak danych zrodla to `NoCoverageError`, nie cichy zamiennik:** przy
  wyborze arkusza GUGiK zamiast pliku PL-1992 pod godlem PL-2000, pliku
  0,5 m pod zadaniem 1 m albo arkusza potomnego; dla PL-2000 1:10000
  z samymi potomkami podpowiedz `--scale 1:2000`. Awaria warstwy skorowidza
  albo GetCapabilities to `DownloadError` zamiast przejscia do starszej
  kampanii lub zaszytej listy warstw (K3, K4, S4).
- **CLI odrzuca `--product nmpt --resolution 5m` oraz `--product orto
  --vertical-crs ...`** zamiast cicho je ignorowac (V2-N1).
- **Usuniety format `GML`** — `--format GML`, pozycja w `landcover
  list-sources` i `get_supported_formats()`; nigdy nie byl zaimplementowany
  (zadanie konczylo sie plikiem GPKG) (A6-2).
- **Selekcja arkuszy z bboxa EPSG:2180 przecinajacego poludnik 19°E zwraca
  wiecej arkuszy** — obwiednia WGS84 liczona z zageszczonych krawedzi (opis
  w Poprawione); mozliwe arkusze nadmiarowe spoza bboxa.
- **HSG: kanoniczne progi trojkata USDA** (ADR-025) — skosne granice normy
  (`silt + 1.5*clay`, `silt + 2*clay`) zastapily przyblizenia liniami
  pionowymi/poziomymi, reguly stoja w jednym miejscu, wiec
  `classify_usda_texture()` (skalar) i `classify_usda_texture_array()`
  (tablica, uzywana przez `calculate_hsg_by_bbox`) daja identyczne wyniki
  (rownowaznosc przypieta testem na calym symplexie co 1%). Skutek na 5151
  punktach symplexu, "bylo -> jest":

  | zmiana HSG | punktow | udzial symplexu | zmiana tekstury |
  |---|---|---|---|
  | A -> B | 136 | 2,64% | `loamy_sand` -> `sandy_loam` |
  | C -> B | 85 | 1,65% | `sandy_clay_loam` -> `loam` (36), `sandy_clay_loam` -> `sandy_loam` (28), `clay_loam` -> `loam` (21) |
  | D -> C | 5 | 0,10% | `sandy_clay` -> `clay_loam` |
  | **razem** | **226** | **4,39%** | (klasa tekstury zmienia sie dla 427 punktow = 8,29%) |

  Kazda zmiana jest o dokladnie jedna grupe. `TEXTURE_TO_HSG` bez zmian
  (swiadome, udokumentowane odstepstwo od TR-55: `sandy_loam`=B,
  `clay_loam`/`silty_clay_loam`=C) (A4-4, A4-8).
- **HSG: piksele nodata dostaja 0 ("brak danych")**, nie grupe B (szczegoly
  w Poprawione).

### Przejscie z 0.6.1
- **Istniejacy cache `data/` nie jest reuzywany** — arkusze NMT/NMPT/orto
  z 0.6.1 (`nmt_1m/`, `nmt_5m/`, `nmpt/`, `orto/`) zostana pobrane ponownie,
  takze po recznym przeniesieniu do nowych segmentow (zwykly plik w sciezce
  standardowej bez sidecara z `extra.link` jest nieznany, ADR-030). Reczna
  migracja nie oszczedza transferu: zaplanuj miejsce i czas pierwszego
  pobrania, stare katalogi usun po nim. Katalog `landcover/` bez zmian
  (nazwy plikow — punkt nizej). Tabela
  odpowiedniosci katalogow (np. dla wlasnych skryptow czytajacych `data/`):

  | Stara sciezka | Nowa sciezka |
  |---|---|
  | `nmt_1m/` (godla 1992) | `nmt/pl_1992_1m_<vcrs>/` |
  | `nmt_1m/` (godla kropkowe 2000) | `nmt/pl_2000_1m_<vcrs>/` |
  | `nmt_5m/` | `nmt/pl_<uklad>_5m_evrf2007/` |
  | `nmpt/` | `nmpt/pl_<uklad>_1m_<vcrs>/` |
  | `orto/` | `orto/pl_<uklad>/` (CIR: `orto/pl_<uklad>_cir/`, B/W: `orto/pl_<uklad>_bw/`) |
  | `laz/` (tylko 0.7.0-dev) | `laz/pl_<uklad>_<vcrs>/` |
  | `cz_dmr5g/` (tylko 0.7.0-dev) | `nmt/cz_dmr5g_<vcrs>/` |
  | `cz_dmr4g/` (tylko 0.7.0-dev) | `nmt/cz_dmr4g_<vcrs>/` |

  Stare `nmt_5m/`, `nmpt/` i `orto/` trzymaly oba systemy godel razem, wiec
  jeden stary katalog odpowiada dwom segmentom.
- **Pliki CORINE/SoilGrids w `landcover/`** maja nowe nazwy z parametrami
  (`soilgrids_bbox_<coords>.tif` -> `soilgrids_<property>_<depth>_<stat>_bbox_<coords>.tif`,
  `corine_land_cover_bbox_<coords>.tif` -> `corine_<year>_bbox_<coords>.tif`;
  analogicznie `godlo_<godlo>`). Stary plik SoilGrids nie mowi, ktorego
  parametru dotyczy (sidecar go nie zapisal), wiec bezpieczniej pobrac
  ponownie niz zmieniac nazwe; plik CORINE mozna przemianowac recznie,
  jesli rocznik jest znany (w 0.6.1 domyslnie 2018). Skrypty skladajace
  nazwe wyniku powinny brac sciezke zwracana przez `LandCoverManager.download()`
  (CLI: `Downloaded to:`). BDOT10k bez zmian.
- **Importy** — przeniesione moduly providerow (bez shimow); prywatne
  `Bdot10kProvider._get_teryt_for_point()` nadal istnieje:

  | Stary import | Nowy import |
  |---|---|
  | `kartograf.providers.gugik` | `kartograf.providers.pl.gugik` |
  | `kartograf.providers.gugik_nmpt` | `kartograf.providers.pl.gugik_nmpt` |
  | `kartograf.providers.gugik_orto` | `kartograf.providers.pl.gugik_orto` |
  | `kartograf.providers.bdot10k` | `kartograf.providers.pl.bdot10k` |
  | `kartograf.providers.landcover_base` | `kartograf.providers.base` |

  Najprosciej: `from kartograf import Bdot10kProvider` (i pozostale klasy).
- **Jeden raster NMT dla obszaru** — zamiast skladac mozaike samemu (albo
  z `kartograf.transport.mosaic.mosaic_and_crop`, ktore NIE jest
  eksportowane w `kartograf` i jest krokiem wewnetrznym) uzyj
  `kartograf.download_pl_cutout` (EVRF2007/KRON86, 1 m/5 m, cel
  EPSG:2180/5514/3045; arkusz bez danych = nodata + `missing_sheets`);
  z wlasnym providerem, sesja albo `MetadataCache` — kroki
  `prepare_pl_cutout` -> `select_pl_cutout_sheets` ->
  `run_pl_cutout(provider=...)`.
- **Pozostale zmiany widoczne dla konsumenta:** sidecar `<plik>.meta.json`
  obok kazdego pobranego pliku (konsument, np. Hydrograf, czyta klucze
  angielskie ADR-031); `except DownloadError` lapie tez `NoCoverageError`;
  `import kartograf` wymaga dzialajacego `rasterio`; argumenty
  `download_by_teryt` po `timeout` tylko jako keyword; w CLI dla zadan
  z poludniowej Polski podawaj `--country pl`, jesli plik CUZK jest
  niepotrzebny.
- **Dane z wersji rozwojowych 0.7.0-dev** (nie dotyczy uzytkownikow 0.6.1):
  - `laz/`, `cz_dmr5g/`, `cz_dmr4g/` mozna przeniesc wedlug tabeli wyzej —
    sa pomijane po samym istnieniu pliku (bez kampanii); `<vcrs>` odczytaj
    z sidecara (`vertical_crs`). Wczesniejszy plaski uklad wycinkow CZ
    (`cz_dmr5g_<coords>.tif` w korzeniu wyjscia) zastapil
    `<segment>/bbox/<coords>.tif`.
  - Rastry CZ i wycinki PL -> EPSG:5514 z sidecarem `S-JTSK to ETRS89 (3)`
    liczono slowacka operacja EPSG:4829 — moga byc przesuniete o 1-5 m
    (np. 1,25 m na poludnie dla kafli TM33, 4,92 m w zachodnich Czechach).
    CLI drukuje `Info:` przy ich pominieciu, ale nie przebudowuje
    automatycznie: uruchom ponownie z `--force`.
  - Wycinki PL zbudowane przed przyciaganiem cropu do siatki arkuszy maja
    tresc przesunieta o ulamek piksela i te same nazwy plikow — przebuduj
    z `--force` (pobiera ponownie takze arkusze) albo taniej: usun sam plik
    wycinka i uruchom bez `--force` (arkusze z cache zostana uzyte).
  - Sidecary z polskimi kluczami nie sa migrowane: sidecar kampanii bez
    `extra.campaign.pzgik_date` daje klucz dowiazania z nazwy katalogu
    (dolne oszacowanie), wpisy `sheet_sources` bez `sheet` nie licza sie
    jako niepelne arkusze przy pominieciu wycinka, a wpis
    `record_cache`/`campaigns_cache` z polskimi kluczami jest chybieniem
    cache (skorowidz odpytywany ponownie, wpis nadpisany). Odswiezenie
    sidecarow: `--force`.
  - Wpisy cache rekordow sprzed podpowiedzi `NoCoverageError.hints` nie maja
    podpowiedzi do wygasniecia TTL (7 d).
  - Symlink w sciezce standardowej (sprzed errata 4 ADR-030) to sciezka
    nieznana; plik kampanii jest lokalny, wiec `newest` go nie pobiera,
    tylko zastepuje symlink hardlinkiem.

### Dodane

#### Czechy (CUZK, etap 1)
- **`providers/cuzk/`:** `CuzkClient` — pierwszy silnik sterowany
  deskryptorem (URL-e wylacznie z `AccessChannel.endpoint`): `query()`
  z paginacja i filtrem nadmiarowego wyboru po stronie klienta,
  `export_image()` z kafelkowaniem i nadpisaniem CRS, `fetch_file()` (ZIP
  openzu -> TIFF+TFW); `SheetIndex`/`SheetInfo` — indeks arkuszy SM5/TM33
  z KladyMapovychListu (arkusz SM5 po godle: `SheetIndex.sm5_sheet`);
  `CuzkDmrProvider` + fabryka `create_dmr_provider` (jedno miejsce czeskich
  domyslow) — DMR 5G (2 m, godlo TM33) i DMR 4G (5 m, godlo SM5), bbox przez
  `exportImage`; naprawa metadanych CRS w plikach DMR4G-TIFF i w wynikach
  `exportImage`. Tylko `nmt`; `nmpt`/`orto`/`laz` dla CZ to etap 2.
- **`exportImage` natywnie w EPSG:5514:** serwer CUZK dostaje zadania
  wylacznie w ukladzie natywnym (deskryptory `server_reprojection=False`,
  A1-6). Sufit uslugi 15000 x 4100 px, realna bariera ~8 Mpx — klient
  kafelkuje z budzetem 4 Mpx na zapytanie, kafle kotwiczone w narozniku NW
  zadania (ostatni wiersz mozaiki bez `-9999`, szwy bit w bit, bez
  przesuniec tresci miedzy kaflami). Piksel ma dokladnie 2 m/5 m (snap od
  naroza NW, takze dla pojedynczego wycinka); bbox wyniku moze roznic sie
  od zadania o <= pol piksela na krawedziach E/S. Uszkodzony kafel konczy
  sie `DownloadError` z posprzatanym plikiem wynikowym (A3-1, A3-3, K6, N3).
- **Reprojekcja lokalna przypieta operacja (ADR-024):** `--target-crs`
  i kafel TM33 (warp na siatke EPSG:3045; arkusz SM5 jest 1:1) liczy
  `rasterio.warp` z wymuszonym pipeline'em operacji (`COORDINATE_OPERATION`),
  wspolnym z torem PL (`transform/raster.warp_to_grid`). Krok S-JTSK ->
  ETRS89 to czeska EPSG:1622/1623 (1,0 m), nie slowacka EPSG:4829.
  Kafelkowanie i mozaika po stronie natywnej (przed warpem — szwy nie sa
  utrwalane interpolacja), nodata nie wchodzi do interpolacji, zapis
  atomowy; nieudana reprojekcja (takze z `--force`) nie kasuje poprzedniego
  wycinka/kafla. Brak bezpiecznej operacji poziomej przerywa w konstruktorze
  providera, przed transferem; polityki poziome przekazuja `probe_point`,
  wiec lokalna siatka obcego kraju (np. `sk_gku`) zwracajaca `inf` jest
  odrzucana (K2, A1-2).
- **Transformacja pionowa Bpv -> EVRF2007** (opcjonalna, `--vertical-crs
  EVRF2007`): EPSG:8357 -> EPSG:5621, przypieta operacja 0,1 m, offset
  +0,11..+0,15 m rosnacy S->N, liczona per piksel; raster bez
  geotransformacji jest odrzucany (A3-5). `KRON86` dla CZ jest
  nieosiagalny (siatki GUGiK niepubliczne).
- **`core/parser_tm33.py` — `ParserTM33`:** obliczalna siatka kafli TM33
  2x2 km (EPSG:3045, godlo `{E_km}_{N_km}` = naroznik SW; nieparzyste
  kilometry, np. `301_5550`, sa niepoprawne), wzorowana na `Parser2000`;
  w `parser_registry` jako `cz_tm33`/`cz_sm5` (przed fallbackiem pl1992;
  wzorce `CZ_TM33_PATTERN`/`CZ_SM5_PATTERN`).
- **Rejestr:** deskryptory `cz.cuzk.dmr5g`/`cz.cuzk.dmr4g`, `CountryProfile`
  dla CZ (obwiednia prostokatna w EPSG:4326, ADR-023), `all_countries()`;
  `AccessChannel.endpoint` — jedyne zrodlo URL-i silnikow sterowanych
  deskryptorem (kanaly PL maja `endpoint=""`, zrodlem prawdy sa stale
  providerow).
- **Godlo SM5 bez `--resolution` pobiera 5 m** (takze pod `--country
  auto`); jawne `--resolution 2m` z godlem SM5 to `Error:` (kod 1) przed
  utworzeniem providera, bez sieci. Kafel TM33 i `--bbox`/`--geometry` CZ:
  domyslnie 2 m (albo 5 m). Biblioteka: `CuzkDmrProvider`/
  `create_dmr_provider` sa zwiazane z rozdzielczoscia i dla SM5 wymagaja
  `resolution="5m"`.
- **CZ `--bbox`/`--geometry` daje zawsze jeden wycinek**
  `<segment>/bbox/<coords>.tif` (np.
  `nmt/cz_dmr5g_bpv/bbox/-447000_-1114000_-446000_-1113000.tif`); nieudany
  wycinek nie zostawia pustego katalogu `bbox/`.
- **`Downloading ...` w torze CZ dopiero przy starcie transferu** (godlo,
  `--bbox`/`--geometry`, takze pod `auto`): nieznany arkusz SM5, awaria
  zapytania indeksu albo niepoprawny kafel TM33 daja samo `Error:`.
  Biblioteka: `CuzkDmrProvider.download`/`download_bbox` przyjmuja
  keyword-only `on_download: Callable[[], None] | None`, wolany raz, po
  walidacjach, tuz przed pobraniem pliku SM5 / pierwszym `exportImage`.
- **Indeks SM5 w cache:** tabela `sheet_cache` (TTL 30 dni),
  `kartograf cache stats` drukuje `Sheet entries`; `--force` odpytuje indeks
  na nowo i zapisuje go (`MetadataCache(refresh=True)`, D16).
- **Sidecar CZ:** `transform.horizontal = "pinned: <opis operacji>
  (<dokladnosc> m)"` symetrycznie do `transform.vertical` — takze dla kafli
  TM33 pobranych godlem (reprojekcja 5514 -> 3045 jest opisana); sciezka SM5
  (pliki openzu w 5514) bez czesci poziomej; `extra.cz_share`.

#### Wybor kraju (`--country`) i pogranicze
- **`--country {pl,cz,auto}`** (domyslnie `auto`): godlo — kraj z formatu
  godla; obszar — kazdy kraj z przecinajaca sie prostokatna obwiednia
  (pod `auto` przyciety do niej), osobne pliki ze wspolnym
  `extra.parent_request` (oryginalny bbox zadania, jego uklad i
  **probowane** — niekoniecznie pobrane — kraje), bez scalania PL+CZ (R6).
  Tryb godlowy nie dostaje `parent_request`.
- **Opcje tylko-PL rozstrzygaja `auto` do `pl`:** `--product nmpt|orto`,
  `--system`, `--vertical-crs KRON86`, `--resolution 1m` na obszarze
  spornym daja `Info: --country auto -> pl (...)` na stderr (takze z `-q`)
  zamiast kodu 1 (ADR-023 pkt 5, N6-2). Opcje nierozwiazywalne dla kraju
  (`--resolution 2m`/`--vertical-crs Bpv` na obszarze siegajacym PL;
  `--product` inny niz `nmt`, `1m`, `KRON86`, `--system` dla CZ) sa
  odrzucane przed pobraniem z podpowiedzia jawnego `--country`;
  `--product laz` na obszarze siegajacym CZ — `Error:` z podpowiedzia
  `--country pl`. `--target-crs` dziala dla obu krajow i nie rozstrzyga
  wyboru.
- **Przyciecie do obwiedni** drukuje `Info:` tylko, gdy naprawde ogranicza
  pobieranie (`--geometry` bez `--target-crs` wyznacza arkusze PL z calej
  geometrii — bez Info dla PL; czesc CZ bywa przycinana); nietkniete
  krawedzie PL pozostaja oryginalne (bez poszerzenia przez round-trip CRS).
  Wycinki niosa przyciety zasieg w nazwie pliku i `request.bbox`, tryb listy
  `--bbox` wyznacza arkusze z przycietego bboxa (sidecary z `request.sheet`);
  jawne `--country pl` nie przycina. Bbox calkowicie poza obwiedniami =
  `Error:` kod 1 bez sieci (S3).
- **Kody wyjscia:** 0, gdy co najmniej jeden kraj dostarczyl wynik; porazka
  drugiego daje `Warning: czesc <kraj> zadania zakonczyla sie bledem (patrz
  Error wyzej) — pobrano <kraj>; kod 0 (...)` (bez zgadywania przyczyny:
  brak pokrycia albo awaria zrodla); kod 1, gdy padly wszystkie kraje albo
  `--country` bylo jawne (A3-2, ADR-023 pkt 4). Wycinek PL/CZ w calosci
  nodata daje `Warning:` i kod 0 (N2). `Info:`/`Warning:` ida na stderr
  mimo `-q`.
- **`--bbox-crs`** przyjmuje takze `EPSG:5514` (S-JTSK) i `EPSG:3045`
  (ETRS89 / UTM 33N) obok `EPSG:2180`, `EPSG:4326`, `EPSG:2176-2179`
  (ujemne bboxy Krovaka podawaj jako `--bbox=...`). Bbox albo plik geometrii
  w ukladzie czeskim opuszcza Krovaka przypieta operacja, nie domyslnym
  transformerem (dla PL inaczej siatka i nazwa wycinka bylyby przesuniete
  o ~1,2 m); `parent_request.bbox_crs` niesie wtedy uklad pliku.
- **`--target-crs {EPSG:2180,EPSG:5514,EPSG:3045}`** w trybie
  `--bbox`/`--geometry` dla obu krajow (CZ: wycinek `exportImage`, PL:
  scalony wycinek); godlo + `--target-crs` = blad. Na pograniczu `--country
  auto --target-crs` powstaja dwa wycinki PL+CZ ze wspolnym
  `parent_request`. `--vertical-crs {KRON86,EVRF2007,Bpv}`.
- **Domyslne wartosci per kraj:** `--resolution`/`--vertical-crs`/`--system`
  bez podania rozwiazywane dopiero po ustaleniu kraju (PL:
  1m/EVRF2007/1992; CZ: 2m/Bpv, `--system` nie dotyczy).

#### LAZ — chmury punktow LIDAR (ADR-029)
- **`GugikLazProvider`** — pliki `.laz` (dane pomiarowe ALS) przez **WFS**
  (`DanePomiaroweLidarEVRF2007` / `DanePomiaroweLidarKRON86`), discovery
  obszarowe: godlo (<= 1:10000) / `--bbox` / `--geometry` -> bbox EPSG:2180
  -> `discover_tiles()` (WFS GetFeature). BBOX i envelope WFS w kolejnosci
  osi (N,E), straz przeciecia odrzuca kafle spoza obszaru (K1). Kafle sa
  drobniejsze niz 1:10000; godlo kafla jest etykieta (nieparsowalne),
  `url_do_pobrania` brany wprost z WFS. Metadane WFS: `akt_rok`,
  `akt_data`, `char_przestrz` (gestosc), `uklad_xy`, `czy_ark_wypelniony`,
  rama `msGeometry`.
- **Wybor kafli wg pokrycia obszaru** (domyslnie, bez `--year`): kafle od
  najnowszego `akt_rok` (w roku nowsza `akt_data`); starszy kafel jest
  pomijany, gdy jego czesc wspolna z obszarem pokrywaja wybrane juz kafle
  (ramy w EPSG:2180, kazda +1 m tolerancji, `COVERAGE_TOLERANCE_M`), wiec
  PL-1992 i PL-2000 tego samego miejsca sie nie dubluja. Kafel wnoszacy
  niepokryty kawalek zostaje (caly); kafel `czy_ark_wypelniony=NIE` nie
  wypiera starszych; kafel, ktorego rama nie przecina obszaru (tylko
  obwiednia), jest pomijany. `--year` = tylko ten rok, dedup pokryciowy
  w roku. Pominiete kafle: `Info:` na stderr (takze z `-q`), w bibliotece
  `superseded`. Nowy modul `core/coverage.py` (przeciecie, roznica i bufor
  wypuklych wielokatow, bez nowych zaleznosci).
- **Roczniki:** lista lat wylacznie z WFS GetCapabilities
  (`_fetch_available_years`/`_get_available_years`, cache w pamieci tylko
  udanych odpowiedzi; awaria = `DownloadError`). Jawny `--year` sprawdzany
  wobec GetCapabilities danej uslugi przed GetFeature: nieistniejacy rok =
  `rocznik ... nie istnieje w usludze ... (dostepne: ...)` bez sugestii
  ponowienia; awaria discovery rocznika = `DownloadError` z rokiem
  i informacja o niekompletnym wyniku; `No LAZ tiles found` oznacza komplet
  poprawnych odpowiedzi (N7).
- **CLI:** `kartograf download <godlo|--bbox|--geometry> --product laz`
  z flagami `--year`, `--vertical-crs` (domyslnie EVRF2007),
  `--min-density` (gestosc NOMINALNA z WFS — faktyczna bywa kilkukrotnie
  wyzsza, E16), `--campaigns`, `--min-year`; pobieranie rownolegle
  (`--workers`), pomijanie istniejacych plikow. Porazka choc jednego kafla =
  `Error: N z M kafli LAZ nie pobrano ...` z PELNA lista, kod 1 (pobrane
  kafle zostaja).
- **Uklad:** `laz/pl_<uklad>_<vcrs>/<hierarchia godla>/<oryginalna
  nazwa>.laz`, `<uklad>` per kafel z `uklad_xy` (`LazTile.uklad`);
  wartosc nierozpoznana = `ValidationError`, a discovery pomija taki kafel
  z ostrzezeniem w logu (bez zgadywania z formatu godla).
  `FileStorage.get_raw_path(..., uklad=)` — sciezka dla nieparsowalnego
  godla bez `SheetParser`; ten sam segment co CLI daje `uklad=tile.uklad`,
  bez niego uklad wynika z formatu godla.
- **API biblioteki:** `kartograf.download.laz` — `download_laz_area(bbox,
  ...)`, `run_laz_download(selection, ...)`, `LazDownloadResult`
  (`downloaded`/`skipped`/`failed`/`superseded`), `LazTileFailure`,
  `write_laz_sidecar`; `GugikLazProvider.select_tiles(...)` zwraca
  `LazTileSelection` (`tiles`, `superseded` = `SupersededLazTile`),
  a `discover_tiles` = `select_tiles(...).tiles`; `select_tiles` waliduje
  `min_year` jak `DownloadManager`. `LazTile` z polami `footprint` (rama
  w EPSG:2180, osie E,N), `date`, `full_sheet` (z wartosciami domyslnymi).
  Eksporty w `kartograf`: `GugikLazProvider`, `LazTile`, `LazTileSelection`,
  `SupersededLazTile`, `download_laz_area`, `run_laz_download`,
  `LazDownloadResult`, `LazTileFailure`. Porazka kafla nie jest wyjatkiem
  (`result.failed`). Jedna sesja HTTP na watek (`SessionPerThread`),
  sesja wstrzyknieta (`session=`) wygrywa zawsze.
- **Sidecar kafla:** `request.year`/`request.min_density` (gdy podane),
  `extra.tile_sheet`, `extra.year`, `extra.nominal_density`; w trybie
  `--bbox`/`--geometry` `extra.parent_request` (bbox w podanym ukladzie,
  `countries: ["PL"]`). Provider bez `descriptor_key` dostaje
  `pl.gugik.laz`; nieudany zapis loguje `kartograf.sources.sidecar`.

#### Wycinek PL `--target-crs` (ADR-027)
- **CLI:** `--target-crs` z `--bbox`/`--geometry` PL daje jeden scalony
  GeoTIFF `nmt/pl_1992_<res>_<vcrs>/bbox/<coords>.tif` (mozaika arkuszy GUGiK
  + crop + lokalny warp przypieta operacja). Tylko `nmt` i PL-1992;
  czytelne bledy dla godla, `--product nmpt|orto|laz`, `--system 2000`.
- **`EPSG:2180`** = crop na siatce pikseli arkuszy (obszar rozszerzony na
  zewnatrz o < 1 px, wartosci 1:1, `transform: null`, nazwa pliku niesie
  wspolrzedne zadania). Narozniki pikseli arkuszy GUGiK leza w polowie
  miedzy wielokrotnosciami piksela (5 m: 5k + 2,5 m; 1 m: k + 0,5 m), czesc
  arkuszy 5 m kampanii 2022 ma inna faze: arkusze o roznych fazach daja
  `GridMismatchError(ValidationError)` z `.off_grid` i kod 1 z podpowiedzia
  innego `--target-crs`. **Inny cel** — W1: warp kazdego arkusza osobno,
  odchylenia fazy w `extra.off_grid_sheets` (S5).
- **Selekcja arkuszy** (`select_pl_cutout_sheets`) ma zapas 1 piksela (tryb
  bbox i suma R-01); `--geometry` z `EPSG:2180` (bez sumy R-01) zapasu nie
  ma — skrajna kolumna albo wiersz moze byc nodata (`docs/ARCHITECTURE.md`
  4.3). `--geometry` obejmuje CALA obwiednie geometrii bez maskowania,
  a przy reprojekcji arkusze to suma godel geometrii i godel obwiedni
  z zapasem (obwiednia wypelniona danymi; koszt: przy rzadkiej geometrii
  pobieraja sie arkusze calej obwiedni). Arkusz wydany przez skorowidz
  w ukladzie PL-2000 pod godlem PL-1992 konczy budowe bledem z opisem;
  starego arkusza PL-2000 w cache PL-1992 nie miesza sie — usun go i ponow.
- **Braki danych:** arkusz bez danych GUGiK (`NoCoverageError`) = nodata +
  `Warning:` + `extra.missing_sheets` (`PlCutoutResult.missing_sheets`);
  inna awaria pobrania = kod 1; obszar bez danych w zadnym arkuszu =
  `ValidationError`. Wynik w calosci pusty mimo pobranych arkuszy:
  `PlCutoutResult.all_nodata=True`, `Warning:`, `extra.all_nodata: true`
  (E15). Arkusze niepelnej kampanii: `extra.sheet_sources[].full_sheet`,
  `PlCutoutResult.partial_sheets`, pusty wycinek z nich ostrzega
  o niepelnej kampanii, nie o braku danych (E13). Lokalna kampania uzyta
  przy awarii skorowidza: `PlCutoutResult.unverified`,
  `extra.unverified_sheets`, `Warning:` (I-1).
- **Pomijanie istniejacego wyniku:** po samym istnieniu pliku;
  `PlCutoutResult(skipped=True)` odtwarza `missing_sheets`,
  `off_grid_sheets` i `all_nodata` z sidecara (bez czytania rastra), CLI
  powtarza ostrzezenia. Arkusze reuzyte dopisuja `extra.parent_requests`
  bez utraty oryginalnego `parent_request`. `--force` przebudowuje wycinek
  i pobiera ponownie jego arkusze; tanszy rebuild: usun sam wycinek.
- **Kampanie:** wycinek jest zawsze `newest` i czyta arkusze przez
  dowiazania; `--campaigns all` lub `--min-year` z `--target-crs` =
  `Error:` kod 1 przed siecia.
- **Biblioteka** (`kartograf.download.cutout`, eksport w `kartograf`):
  `download_pl_cutout(bbox, target_crs, ..., cache=)` oraz kroki
  `prepare_pl_cutout` (fail-fast, bez sieci; niefaktyczny pion =
  `ValidationError`) -> `select_pl_cutout_sheets` -> `run_pl_cutout`
  (nie przyjmuje `campaigns`), typy `PlCutout`, `PlCutoutSheets`,
  `PlCutoutResult`. CLI jest nakladka na te funkcje. `run_pl_cutout`
  z wstrzyknietym providerem o innym pionie albo rozdzielczosci konczy sie
  `ValidationError` przed pobraniem. Bbox w ukladzie czeskim z etykieta
  malymi literami albo ze spacjami (`"epsg:5514"`) opuszcza Krovaka
  przypieta operacja jak `"EPSG:5514"` (m-2).
- **Mozaika i zasoby:** arkusze owijane w VRT z jawnym EPSG:2180 i Float32
  (arkusz ASC z samymi liczbami calkowitymi nie zamienia mozaiki w Int32,
  arkusze z `.prj` i bez niego sie mieszaja), lista zrodel sortowana;
  zrodla otwierane leniwie (wycinek z > 1024 arkuszy nie konczy sie "Too
  many open files"; limit deskryptorow Linux 1024, macOS 256); plik
  posredni mozaiki kompresowany (deflate, kafle 512 px, BigTIFF gdy
  trzeba). Przed siecia kontrola wolnego miejsca — DOLNE oszacowanie
  (wynik + arkusze bez pliku w sciezce standardowej, policzone wstepnie;
  pod `newest` arkusz z nowsza albo usunieta kampania zostanie pobrany mimo
  dowiazania), `Info:` dla wycinkow >= 1 GiB, bez twardego limitu. Obie
  sciezki zapisu atomowe: nieudana budowa nie niszczy poprzedniego pliku
  i nie zostawia pustego `bbox/`.

#### Kampanie GUGiK (ADR-030)
- **CLI `--campaigns {newest,all}`** (domyslnie `newest`) i **`--min-year
  RRRR`** (1900..2100, inaczej `Error:` bez sieci); tylko PL (GUGiK).
  `newest` = regula ADR-028, rozwiazywana przy kazdym uruchomieniu (siec po
  wygasnieciu cache 7 d), pobiera tylko brakujace kampanie. `all` = KAZDY
  rekord po twardym filtrze ADR-028 ze wszystkich warstw, bez limitu liczby
  kampanii (`logger.info` z liczba, raz na arkusz).
- **`--min-year`** = granica na roku `aktualnosc` (nie `dt_pzgik`), dla obu
  strategii; rekord bez ustalonego roku jej nie spelnia (`all`: pominiety;
  `newest`: `NoCoverageError` "starsza niz min_year" z data tej kampanii,
  lista/hierarchia: status `no_coverage`). Rok z nazwy warstwy sluzy tylko
  w `all` do pominiecia zapytania warstwy (gorny rok < granicy); `Starsze`
  zawsze odpytywane.
- **Uklad:** `<segment>/kampanie/<data>_<id>/<hierarchia godla>/<godlo>.<ext>`
  + `.meta.json`; `<data>` = `aktualnosc` rekordu, `<id>` = pierwszy segment
  liczbowy nazwy pliku w URL, inaczej `u` + 8 znakow hex `sha1(URL)`.
- **Dowiazanie sciezki standardowej:** raz na arkusz po zebraniu kampanii,
  hardlink, a gdy niedostepny — kopia z `Warning: hardlink niedostepny na
  tym systemie plikow — sciezka standardowa jest KOPIA najnowszej kampanii
  dla N arkuszy (...) (extra.link=copy)` (kod bez zmian). Bez symlinkow
  (errata 4: symlink z Linuksa na udziale SMB jest nieczytelny dla klientow
  Windows, a udzialy ograniczaja dlugosc celu). Sidecar sciezki
  standardowej to zwykly plik z `extra.link` (`hardlink`/`copy`)
  i `extra.link_target` (jedyne zrodlo celu). Dowiazanie przestawiane
  tylko na kampanie o kluczu `(aktualnosc, dt_pzgik, url)` scisle wiekszym
  niz klucz biezacego celu (z sidecara, a gdy nieczytelny — z nazwy
  katalogu); inaczej bez zmian (nigdy wstecz). Kontrola istnienia: cel
  z sidecara (`samefile` dla hardlinku); usuniety katalog kampanii albo
  brak sidecara = brak pliku (ponowne pobranie/dowiazanie).
- **Format z pola `format` rekordu** (nie z rozszerzenia URL); plik zawsze
  z rozszerzeniem kanonicznym `.asc`/`.tif` (rekord 72675 z URL `.xyz` to
  AAIGrid = zwykla kampania `.asc`); brak pola (orto, stare wpisy cache) =
  format domyslny produktu. Po pobraniu weryfikacja tresci (naglowek
  AAIGrid / sygnatura TIFF); nieznany format albo niezgodna tresc =
  porazka kampanii (`DownloadError` z nazwa formatu, plik usuniety), nigdy
  ciche `.asc`. Plik kampanii bez sidecara (przerwany przebieg) przechodzi
  weryfikacje tresci przed odtworzeniem sidecara.
- **Sidecar pliku kampanii jest obowiazkowy** (`emit_sidecar(required=True)`,
  zapis atomowy): porazka zapisu = porazka kampanii (plik danych usuniety,
  dowiazanie nieprzestawione); pozostale sidecary best-effort.
  `extra.campaign` = `{id, date, survey_work_id, source, full_sheet,
  pzgik_date}`, `request.campaigns` zawsze, `request.min_year` tylko gdy
  podany.
- **Porazki:** czesciowa porazka `all` na arkuszu (np. niepoprawna
  `aktualnosc` jednej kampanii) = kod 1 z pelna lista, pozostale kampanie
  pobrane, dowiazanie na najnowsza poprawna; porazka dowiazania (nawet
  kopii) = porazka arkusza (kod 1, lista idzie dalej takze przy
  `--workers 1`, pobrane kampanie zostaja). Wyscig bez blokad: rownolegle
  wywolania na tej samej sciezce moga chwilowo zostawic dowiazanie na
  starszej kampanii; kolejne `newest`/`all` je naprawia (pliki
  w `kampanie/` nietkniete).
- **Awaria skorowidza przy `newest` (I-1, errata 5):** blad TRANSPORTU
  rozwiazywania rekordu (siec, HTTP 429/5xx; nie brak pokrycia, nie inne
  4xx ani raport OGC) na arkuszu z istniejaca lokalna kampania nie jest
  porazka — arkusz pominiety z lokalnej kampanii (dowiazanie bez zmian),
  `Warning: <godlo>: skorowidz GUGiK niedostepny — uzyto lokalnej kampanii
  bez sprawdzenia nowszej (...)` na stderr takze z `-q` (lista: jedno
  `Warning:` z godlami), kod bez zmian. `--campaigns all`, `--min-year`,
  `--force` i brak lokalnej kampanii — blad jak dotad.
- **Podsumowanie `all`** (bez `-q`, takze pojedyncze godlo): `Downloaded
  <n> campaign files for <m> sheets to <dir> (<k> already existed)`
  (n = pobrane, k = juz lokalne).
- **CZ i LAZ:** zadanie bez PL (godlo CZ takze pod `auto`, obszar/geometria
  z jawnym `--country cz`, obszar w calosci czeski pod `auto`) z opcjami
  kampanii = `Error: CZ (CUZK) nie ma kampanii — --campaigns all/--min-year
  dotycza tylko PL` (kod 1, bez sieci); obszar pod `auto` z PL i CZ = jedno
  `Info:`, CZ pobierane dalej (biezaca wersja danych CUZK). LAZ:
  `--campaigns all` = wszystkie kafle, ktorych rama przecina obszar, bez
  deduplikacji ADR-029 (kafel przeciety tylko obwiednia pomijany);
  `--min-year` = dolna granica `akt_rok`; `--min-year` i `--year`
  wykluczaja sie (`Error:`); LAZ bez dowiazan.
- **Biblioteka:** `DownloadManager(campaigns=, min_year=)`,
  `DownloadManager.last_sheet` (`SheetFetch`: `godlo`, `path`, `skipped`,
  `downloaded`, `reused`, `link`, `unverified`), `DownloadResult.
  campaign_files`, `reused_campaign_files`, `copied`, `unverified` (godlo ->
  tresc bledu); eksporty `kartograf.CampaignRef`, `kartograf.SheetFetch`;
  moduly `download/campaigns.py` (`CampaignRef`, `validate_campaign_args`,
  `verify_file_format` — `OSError` odczytu jako `DownloadError`)
  i `download/links.py`; `FileStorage.get_campaign_path`,
  `FileStorage.list_files(campaigns=)`. Providery PL: `resolve_campaigns`,
  `download_record`, `record_source`, `_resolve_record(parser, timeout,
  query)`; skorowidz: `select_campaign_records`, `layer_upper_year`,
  `LAYER_FAMILY` (warstwa z rodziny produktu spoza `LAYER_PATTERN` =
  `logger.warning`, nie jest odpytywana). Biblioteka bez `MetadataCache`
  pyta skorowidz przy kazdym `download_sheet` (takze arkusza juz
  pobranego) — przekaz cache providerowi.
- **Cache:** tabela `campaigns_cache` (lista kampanii arkusza, TTL 7 dni,
  `--min-year` poza kluczem; po skanie czesciowym obsluguje tylko granice
  >= granicy skanu, nizsza = ponowny skan), `kartograf cache stats`
  drukuje `Campaign entries`.

#### NMT PL i skorowidz GUGiK
- **`NoCoverageError(DownloadError)`** — zrodlo nie ma danych dla arkusza
  (wszystkie warstwy skorowidza odpowiedzialy); `DownloadResult.no_coverage`
  (podzbior `failed`), podpowiedzi `NoCoverageError.hints` /
  `DownloadResult.no_coverage_hints`.
- **Lista arkuszy PL** (`--bbox`/`--geometry` bez `--target-crs`, takze
  hierarchia godla): brak danych jednego arkusza nie przerywa pozostalych
  (R5 probuje wszystkie, niezaleznie od `--workers`); `NoCoverageError` =
  `Warning:` i `DownloadProgress.status == "no_coverage"` (`∅` w CLI);
  >= 1 plik i tylko braki pokrycia -> kod 0, wszystkie bez danych albo
  twarda awaria -> kod 1 z pelna lista. Pojedynczy arkusz bez danych ->
  kod 1. Podpowiedzi (np. `uzyj --scale 1:2000` dla PL-2000 1:10000) jako
  `Info:` na stderr (bez duplikatow, max 5 linii + "i K innych"), bez
  podsumowania `Downloaded 0 ...` (O-3/O-6/O-7, S2).
- **Wybor rekordu (ADR-028):** twardy filtr godla (caly token), ukladu,
  rozdzielczosci 1 m/5 m, RGB orto i daty; w pierwszej pasujacej warstwie
  wygrywa najnowsza `aktualnosc`, potem `dt_pzgik`, URL, niezaleznie od
  flagi pelnego arkusza (K4). Rekord niepelnego arkusza (`full_sheet:
  false`) wygrywa, gdy jest najnowszy, ale CLI drukuje `Warning:` (tor
  godla, listy i wycinka, takze przy skip), a `extra.source.full_sheet` to
  zapisuje (E13). Podpowiedz `NoCoverageError` o arkuszu w innym ukladzie
  ma postac `<godlo> (<skala>) — uzyj tego godla lub --system X --scale Y`
  (takze orto; D14).
- **Arkusze PL-2000 opublikowane we wspolrzednych EPSG:2180** (zaobserwowane
  w strefie 7, np. `7.125.11.19`, `7.173.21.01`, z niecalkowitym `cellsize`
  0,99937 m): sidecar zapisuje faktyczny uklad pliku (`horizontal_crs:
  EPSG:2180`), deklaracje rekordu w `extra.source.declared_crs`
  (`PL-2000:S7`), plik lezy w segmencie wg godla; CLI drukuje `Warning: N
  arkuszy GUGiK opublikowano w innym ukladzie niz wskazuje godlo: <godlo>
  (godlo: EPSG:2178, plik: EPSG:2180)` na stderr (tor godla, listy
  i hierarchii, takze przy skip i `-q`; fakt czytany z sidecara), kod bez
  zmian; biblioteka loguje to samo przez `kartograf.sources.sidecar` (E17).
  Pozostale arkusze PL-2000 maja w sidecarze EPSG strefy 2176-2179 (N8).
- **Ortofotomapa: wariant koloru w sciezce** — RGB domyslnie
  (`GugikOrtoProvider(color="RGB")`, najnowszy rekord RGB, K5) w
  `orto/pl_<uklad>/`, `color="CIR"` (podczerwien) w `orto/pl_<uklad>_cir/`,
  B/W w `orto/pl_<uklad>_bw/`; nowe `BaseProvider.storage_variant`,
  `FileStorage(variant=...)` (E12).
- **`DownloadManager`:** `download_sheets(godla, ...)`
  i `expand_sheets(godla)` (lista godel, grubsze PL-1992 rozwijane do
  1:10000, duplikaty raz; porazki zbierane w `last_result`); `last_result`
  (`DownloadResult`: succeeded/failed/skipped/no_coverage ostatniego
  `download_hierarchy()`/`download_sheets()`, kasowane na wejsciu do
  `download_sheet()`/`download_hierarchy()`/`download_sheets()`; CLI
  ustala z niego kod wyjscia, A2-5); `sidecar_extra=` (pola scalane do
  `extra` kazdego sidecara, np. `parent_request`); `download_sheet(on_download=)`.
- **Fabryka `create_nmt_provider()`** (`providers/pl/__init__.py`) — jedno
  miejsce polskich domyslow NMT; regula "NMT 5m tylko w EVRF2007" w jednym
  miejscu (`kartograf.providers.pl.nmt_vertical_crs`), skutek: korekta do
  EVRF2007 — CLI (`--resolution 5m --vertical-crs KRON86`) drukuje `Info:`
  na stderr (takze z `-q`), fabryka loguje, `prepare_pl_cutout` odrzuca
  niefaktyczny pion `ValidationError` (D11).
- **Jeden parser wartosci ukladu GUGiK** `sources.registry.parse_pl_uklad`
  (`PL-1992`, `PL-2000:S5..S8`, biale znaki obcinane) dla rekordow
  skorowidza, `horizontal_crs_for_uklad` (sidecar) i `LazTile.uklad`;
  wartosc nietypowa (np. `PL-2000` bez strefy) odrzucana spojnie (rekord
  bez ukladu, kafel LAZ pominiety z ostrzezeniem, `ValidationError`)
  (E11, D3).

#### Sidecar `.meta.json` i uklad `data/`
- **Sidecar `<plik>.meta.json`** po kazdym udanym pobraniu (schemat
  `kartograf-meta/1`: dataset, CRS-y poziomy/pionowy, nodata, licencja,
  `request`, `kartograf_version`, `transform`, `extra`) — kontrakt dla
  Hydrografa. Blad zapisu nie przerywa pobrania (wyjatek: plik kampanii).
  Pola `extra` m.in.: `source` (pochodzenie arkusza), `sheet_sources`,
  `missing_sheets`, `off_grid_sheets`, `all_nodata`, `unverified_sheets`,
  `parent_request`, `parent_requests`, `campaign`, `link`/`link_target`,
  `fallback`, `derived`. Wspolne opakowanie `sources.sidecar.emit_sidecar`
  (format operacji `pinned_label`); `build_metadata(capability=, nodata=)`
  — jawny wybor kanalu po capability i jawne `nodata` (`exportImage` CUZK
  zwraca `noDataValue: null`). Sidecary PL w trybie `--bbox`/`--geometry`
  maja `extra.parent_request` (wspolny klucz grupowania z CZ i LAZ).
- **`kartograf_version` w sidecarze i `kartograf --version`** dla wersji
  `dev` podaja `<wersja>+<krotki SHA>` (np. `0.7.0-dev+6db4408`), przy
  niezacommitowanych zmianach w `kartograf/` z sufiksem `.dirty`
  (`kartograf/_version.py::build_version`, leniwie, cache na proces); bez
  gita albo poza repozytorium — samo `__version__`. Wydania, `__version__`
  i `User-Agent` bez zmian.
- **Uklady pionowe -> kody** (`vertical_crs_code`): `KRON86` = `EPSG:9650`,
  `EVRF2007` = `EPSG:5621` (rodzina, wspolna dla PL i CZ), `EVRF2007-PL` =
  `EPSG:9651` (realizacja polska), `Bpv` = `EPSG:8357` (Baltic 1957, CUZK);
  sidecary PL deklaruja realizacje polska (`resolve_vertical_crs`).
- **Segmenty z deskryptorow:** `SourceDescriptor.storage_subdir` to
  szablon z `{uklad}`/`{vcrs}`, sciezke daje `resolve_subdir(uklad=,
  vertical_crs=)` (czesciowe wypelnienie legalne, vcrs malymi literami);
  `FileStorage(vertical_crs=)` (domyslnie `"EVRF2007"`),
  `FileStorage(subdir=...)`; `{uklad}` rozwiazywany per godlo; nierozwiazany
  placeholder albo pusty wymiar (`vertical_crs=''`, takze przez
  `DownloadManager` z providerem o pustym pionie) = `ValidationError`
  zamiast segmentu `nmt/pl_1992_1m_`. Jedna fabryka segmentu providera
  `download.storage.storage_for_provider` i nazwa wycinka
  `download.storage.bbox_cutout_path` (PL i CZ).

#### Land cover, HSG, CORINE
- **HSG ma sidecar** (`kartograf soilgrids hsg` /
  `HSGCalculator.calculate_hsg_by_bbox`): deskryptor
  `global.isric.soilgrids`, `extra.derived = "hsg"`, warstwy zrodlowe,
  glebokosc, statystyka.
- **CORINE bez credentials CLMS:** sidecar podgladu PNG (WMS) deklaruje
  faktyczny CRS — `EPSG:3857` (EEA Discomap) lub `EPSG:4326` (DLR, rok
  1990) — zamiast `EPSG:3035` (tylko GeoTIFF z CLMS) i niesie
  `extra.fallback = "wms_png"` z `extra.note` "podglad WMS, nie dane".
- **`LandCoverProvider.download_by_admin_unit`/`validate_admin_unit`**
  (kanoniczne) + `download_by_teryt`/`validate_teryt`/`source_url` jako
  dzialajace aliasy zgodnosciowe.

#### Cache metadanych
- **`MetadataCache.get_record/set_record`** — rekord skorowidza
  (`{"source": ...}`) albo potwierdzony brak pokrycia z trescia podpowiedzi
  (`{"no_coverage": true, "message": ..., "hints": ...}`), TTL 7 dni;
  trafienie negatywne odtwarza ten sam `NoCoverageError`.
  `stats()["record_count"]`, `kartograf cache stats` drukuje `Record
  entries`. CLI podpina cache rekordow w torach PL (N6).
- **`MetadataCache(refresh=True)`** — odczyty = chybienie, zapisy normalnie;
  `--force` w torach PL i CZ omija ODCZYT cache, ale zapisuje swiezy wybor,
  wiec kolejny przebieg bez `--force` dostaje nowy rekord (E14, D16).
- Nowe: `MetadataCache.db_path`, `MetadataCache.error`, parametr
  `on_disabled=`, klucze `stats()` `db_exists` i `error` (opis
  w Zmienione).

#### Biblioteka i architektura zrodel
- **`kartograf/sources/`** — deskryptory zrodel jako dane (zero IO przy
  imporcie): `SourceDescriptor`, `AccessChannel`, `TransportKind`,
  `LicenseInfo`, `CountryProfile` + rejestr (`get_source`, `sources_for`,
  `get_country`, `all_countries`, `vertical_crs_code`,
  `resolve_vertical_crs`).
- **`kartograf/transform/crs.py`** — twarda polityka transformacji:
  `TransformerGroup(allow_ballpark=False)`, filtr dokladnosci, probe
  odrzucajacy siatki obcych krajow (`inf`), kontrola `isfinite`,
  `TransformError`/`TransformUnavailableError` z remedium, `KNOWN_PATHS`;
  `PinnedTransform` niesie pare ukladow (`src_crs`/`dst_crs`), przyjmuje
  skalary lub tablice `numpy` i udostepnia `gdal_operation()` (pipeline PROJ
  dla `COORDINATE_OPERATION` z korekta kolejnosci osi — cel northing-first
  bez `axisswap` dawal raster w calosci nodata); `build_pinned_transform`
  wykonuje probe wewnatrz kontekstu `network.set_network_enabled(...)`;
  wspolne `CONTENT_POLICY` i `WARP_MARGIN_PX` dla torow PL i CZ (D9).
- **`kartograf.transform.raster.warp_to_grid`** — lokalna reprojekcja rastra
  (pojedyncza mozaika albo lista arkuszy, W1) z wymuszona operacja
  przypieta (ADR-024).
- **`kartograf/transport/`** — `download_to()` i `get_with_retry()` (opis
  w Zmienione, "Transport HTTP") oraz `mosaic_and_crop()` (rasterio.merge +
  przyciecie, propagacja nodata; wynik zapisywany przez
  `merge(dst_path=...)` — szczyt pamieci ~1,06x rozmiaru rastra, A3-4;
  opcje `dst_kwds=`, `snap_to_source_grid=`, `assign_crs=`, `dtype=`,
  domyslnie wylaczone — uzywa ich wycinek PL; zrodlo spoza siatki
  wiekszosci = ostrzezenie w logu). `check_source_grid`, `has_valid_pixels`.
- **`kartograf.core.bbox`:** `BBox` (`kartograf.BBox`,
  `core.sheet_parser.BBox`, `core.geometry.BBox` to ta sama klasa),
  `validate_bbox`, `transform_bbox` (gesta obwiednia: 21 punktow na
  krawedz, cache transformerow, operacja przypieta przez `transformer=` —
  duck typing), `is_czech_crs`; `transform/bbox.py::envelope_from_2180`
  dla CORINE/SoilGrids (D19).
- **`kartograf/core/parser_registry.py`** — rejestr systemow godel (literal
  `SYSTEMS`: pl2000, cz_tm33, cz_sm5, fallback pl1992; `detect_system`
  zawsze zwraca `SheetSystem`); `SheetParser` i `FileStorage` deleguja do
  rejestru (wyniki identyczne).
- **CLI podzielone na moduly** `cli/_parser.py`, `parse_cmd.py`,
  `download_cmd.py`, `landcover_cmd.py`, `soilgrids_cmd.py`, `cache_cmd.py`;
  `cli/commands.py` to fasada z entry pointem `main` (bez zmian).
- **`KARTOGRAF_DEBUG=1`** — pelny traceback zamiast skroconego `Error: ...`
  dla kazdego wyjatku docierajacego do bariery `main` (takze
  `KartografError`; N1-1, N17).

### Zmienione

#### Transport HTTP
- **Jeden transport dla wszystkich providerow:** pliki GUGiK
  (NMT/NMPT/orto/LAZ/BDOT10k), CORINE, SoilGrids i CUZK pobiera
  `transport.http.download_to` z hakami `validate=` (CORINE/SoilGrids:
  `reject_error_document` — raport XML/HTML WMS/WCS bez ponowien) i `save=`
  (BDOT10k GPKG: rozpakowanie ZIP); zapytania (skorowidz, WFS LAZ, TERYT
  BDOT10k, `CuzkClient.query`) — `get_with_retry` (opcjonalne `params=`).
  Zastepuje szesc kopii petli pobierania w providerach (D1).
- **Polityka ponowien:** max 3 proby (`MAX_RETRIES`, niekonfigurowalne),
  ponawiane tylko bledy sieci, HTTP 429 i 5xx; inne 4xx (np. 404 przy
  blednej nazwie pokrycia WCS) koncza od razu z komunikatem `HTTP <kod>
  (bez ponowien)`. Naglowek `Retry-After` (sekundy albo data HTTP) wydluza
  przerwe, max 60 s (`MAX_RETRY_AFTER`). Jeden backoff: 2 s, potem 4 s
  (`backoff_delay`). `DownloadError.status_code` niesie kod HTTP ostatniej
  proby (dotad `None`). Bledy tresci (JSON, raport OGC) nie sa ponawiane.
  Zapytanie TERYT BDOT10k i indeks CUZK sa ponawiane (dotad jedna proba).
  Nowe: `is_retryable`, `retry_wait`, `http_status`, `http_failure`
  (N5, N9).
- **Zapis atomowy przez `os.replace`** (takze scalanie GPKG BDOT10k) zamiast
  `Path.rename` — na Windows `--force` nad pobranym arkuszem padal na
  `FileExistsError`. Katalog docelowy powstaje dopiero po udanej odpowiedzi
  HTTP (nieudane pobranie nie zostawia pustego katalogu).
- **Komunikaty `DownloadError` po polsku** (`HTTP 404 (bez ponowien)`,
  `po 3 probach`); blad pobrania pliku NMT/NMPT/orto podaje nazwe pliku
  z URL, nie godlo (`84183_1852496_N-34-139-C-a-3-1.asc (OpenData): HTTP
  404`).
- **Sesje:** jedna sesja HTTP na watek (`transport.http.SessionPerThread`,
  `make_gugik_session`: keep-alive, `User-Agent: kartograf/<wersja>`) we
  wszystkich providerach GUGiK, BDOT10k, CORINE (takze zapytania CLMS
  w trybie bezposrednim) i SoilGrids — zamiast nowej, niezamykanej
  `requests.Session()` na kazde wywolanie; providery trzymaja
  `self._sessions` (D2). Zapytania GetCapabilities/GetFeatureInfo
  skorowidza z sesja per watek i ponowieniami (S1).

#### NMT PL i skorowidz GUGiK
- **Warstwy skorowidza (NMT/NMPT/orto) wylacznie z GetCapabilities** —
  wspolne `skorowidz._fetch_wms_layers` z `LAYER_PATTERN` providera (orto:
  `SkorowidzeOrtofotomapy<rok>`/`Starsze`, bez wariantow `Zasiegi`),
  warstwy roczne malejaco, zbiorcze i `Starsze` na koncu, cache w pamieci
  tylko udanych odpowiedzi. Bez list zaszytych i bez fallbacku: awaria
  GetCapabilities = `DownloadError`. GetCapabilities ma timeout providera
  (30 s NMT/NMPT, 60 s orto albo `timeout=` z `download()`) zamiast
  zaszytych 10 s (N3, E10).
- **Diagnoza awarii skorowidza:** awaria wszystkich warstw = niedostepnosc
  uslugi, nie "brak pokrycia dla godla" (A2-9); czesciowa awaria przy braku
  arkusza w pozostalych = "brak pokrycia niepewny" (`DownloadError`, kod 1).
  Odpowiedz bedaca raportem wyjatku OGC (`ServiceExceptionReport`,
  `ows:ExceptionReport`, np. `LayerNotDefined` z HTTP 200) albo uszkodzony
  szablon GetFeatureInfo to nieudane zapytanie warstwy, nie brak arkusza
  (dotad dawaly falszywy `NoCoverageError`, a w wycinku nodata, ktore
  kolejne przebiegi pomijaly); URL w odpowiedzi nadal wygrywa, strona HTML
  bez znacznikow OGC (pusty szablon MapServera) to brak arkusza (I-2, N1).
- **`DownloadManager.download_sheet` zwraca (i opisuje sidecarem) sciezke
  zwrocona przez provider** — jak `download_hierarchy`/`download_sheets`;
  wczesniej sciezke docelowa managera. Tryb sekwencyjny i rownolegly maja
  jedna tresc "pobierz arkusz" (`_fetch_sheet`) i jeden raport postepu
  (`downloading` tylko sekwencyjnie) (D10).
- **Listy godel rozwijanych do hierarchii** (`--bbox`/`--geometry`)
  pobierane sekwencyjnie, rownoleglosc wewnatrz kazdej hierarchii — znika
  zwielokrotnienie watkow (dotad do `--workers`^2 zadan do GUGiK) (A2-3).
- **`DownloadManager` z providerem znajacym swoj pion** nie loguje korekty
  "5m tylko EVRF2007" (pion pochodzi z providera); CLI z `--resolution 5m
  --vertical-crs KRON86` tworzy provider skorygowany przez
  `create_nmt_provider` (D11).

#### Cache metadanych
- **Plik otwierany leniwie:** `MetadataCache()` nie tworzy
  `.kartograf_cache.db` przy konstrukcji — plik i schemat powstaja przy
  pierwszym zapisie (`set_*`); odczyty na braku pliku to chybienie,
  `stats()` zwraca zera (klucz `db_exists`), `clear()`/`vacuum()`/`close()`
  nic nie tworza. `kartograf cache path|stats|clear` w katalogu bez bazy jej
  nie tworza (`Database size: - (file not created yet)`). Otwarcie (WAL,
  tabele, migracja starej bazy — usuniecie `url_cache`) pod istniejacym
  lockiem.
- **Uszkodzony cache nie blokuje pobierania:** blad SQLite przy otwarciu,
  odczycie albo zapisie (smieci zamiast bazy, ucieta baza, brak uprawnien,
  `database is locked`) wylacza cache na reszte zycia instancji — odczyty
  to chybienie, zapisy no-op, `stats()` zwraca zera i klucz `error`
  (`MetadataCache.error`); jedno ostrzezenie na instancje (`logger.warning`
  albo `on_disabled=`), bez wyjatku, thread-safe. CLI pobierania drukuje
  ``Warning: cache metadanych nieczytelny (<sciezka>): <blad> — praca bez
  cache; uzyj `kartograf cache clear` albo usun plik`` (stderr, takze
  z `-q`; kod wedlug wyniku pobrania), a przy blokadzie przez inny proces
  `Warning: cache metadanych zablokowany przez inny proces (...)` bez rady
  usuniecia. `kartograf cache clear` usuwa nieczytelny plik z `-wal`/`-shm`
  (`Usunieto nieczytelny plik cache: <sciezka>`, kod 0; brak prawa albo
  blokada = `Error:`, kod 1), `cache stats` drukuje ``Error: cache
  nieczytelny: <sciezka> (<blad>) — uzyj `kartograf cache clear` `` (kod 1),
  `cache path` bez zmian. Wczesniej lista arkuszy konczyla sie porazka
  KAZDEGO arkusza (`file is not a database`, kod 1).

#### Land cover, HSG, BDOT10k
- **Katalog wyjsciowy land cover powstaje dopiero przy zapisie pliku**
  (`download_to` po udanej odpowiedzi): `LandCoverManager()` i `kartograf
  landcover list-layers` nie zostawiaja katalogow; BDOT10k, CORINE
  i SoilGrids nie tworza go przed zapytaniem (nieudane pobranie, np.
  HTTP 404, nie zostawia pustego katalogu).
- **HSG: katalog wyjsciowy dopiero przy zapisie** — `kartograf soilgrids
  hsg` i `HSGCalculator.calculate_hsg_by_bbox`/`_by_godlo` tworza katalog
  tuz przed zapisem rastra (brakujacy plik `--geometry` albo blad SoilGrids
  nie zostawia pustego `./data/hsg`).
- **`Bdot10kProvider.DEFAULT_TIMEOUT` = 120 s** jako domyslna wartosc
  `download_by_admin_unit/godlo/bbox` (zapytanie TERYT 30 s) (N11).
- **BDOT10k GPKG skladany w lokalnym katalogu tymczasowym** i przenoszony
  do celu kopia obok + `os.replace` (udzialy sieciowe SMB/CIFS bez blokad
  zakresow bajtow konczyly SQLite `database is locked`); sprzatanie takze
  przy wyjatku.
- **CORINE i SoilGrids:** obwiednia bboxa z EPSG:2180 przez
  `envelope_from_2180` (wynik bez zmian, D19).

#### CLI
- **`Downloading <godlo> ...`** drukowane dopiero przy starcie pobrania
  (`download_sheet(on_download=)`), nie przy `Skipped`/`Error:`;
  pojedyncze godlo pominiete jako istniejace drukuje `Skipped <godlo> -
  already exists at ...` zamiast `Downloaded to` (decyduje
  `manager.last_sheet.skipped`); `Error:` nie poprzedza pusta linia, gdy
  pasek postepu nie wystartowal.
- **Teksty `--help`** opisuja CZ/CUZK, warstwy SW w BDOT10k, SoilGrids, LAZ,
  HSG, `sheet_cache`, kampanie; `--scale` po polsku z odeslaniem do
  `docs/USAGE.md` 1.6, `--resolution` opisuje SM5 (tylko 5m) vs TM33/bbox
  (2m domyslnie lub 5m) (A6-13).
- Wewnetrznie: jeden helper bledu transformacji (`Error: ... Remedium:
  ...`, `_print_transform_error`, D6) i jeden naglowek listy arkuszy
  (`_print_sheet_list`, D15); tresc komunikatow bez zmian.

#### Pakiet i zaleznosci
- **`pyproject.toml`:** wersja dynamiczna z `kartograf.__version__`
  (usuniety rozjazd `0.6.1` vs `0.7.0-dev`; `dynamic = ["version"]`);
  `[tool.setuptools.packages.find] include = ["kartograf*"]` (`tests/` poza
  dystrybucja); opis i keywords o CUZK/DMR/LAZ (A6-4, A6-5, A6-6).
- **Licencja jako wyrazenie SPDX (PEP 639):** `license = "MIT"` +
  `license-files = ["LICENSE"]`, bez klasyfikatora licencji, prawdziwe
  `authors`; build-system `setuptools>=77.0.3` (bez `wheel`) — build bez
  izolacji wymaga setuptools >= 77, dystrybucje maja `Metadata-Version:
  2.4` z `License-Expression: MIT` i LICENSE w `dist-info/licenses/`,
  upload na PyPI wymaga twine >= 6.x.
- **Paczka zrodlowa (sdist) z kompletnymi testami:** `MANIFEST.in`
  (`graft tests`) dolacza `tests/conftest.py`, `tests/__init__.py`
  i `tests/fixtures/` — testy offline przechodza z rozpakowanego sdist
  (wheel nadal bez `tests/`). Klasyfikator `Programming Language :: Python
  :: 3.13`.

#### Jakosc kodu i brama
- **Brama:** testy offline (`pytest tests/ -m "not live"`), prog pokrycia
  `fail_under` w `pyproject.toml`, `ruff check .` i `ruff format --check .`
  na calym repo (takze skrypty `docs/research/`), `mypy kartograf/ tests/`
  bez bledow. `.claude/` w `.gitignore` i poza ruff/mypy. Testy `live`
  wymagaja sieci i nie naleza do bramki (`pytest -m live`, tylko swiadomie).
- **mypy bez bledow:** poprawki wylacznie typujace, bez `# type:
  ignore`/`cast`; widoczny skutek: brak `private_key` w poswiadczeniach
  CLMS konczy sie jawnym komunikatem (proxy: `None` + log, tryb
  bezposredni: `DownloadError`) zamiast bledu z PyJWT. `affine` w
  `ignore_missing_imports`. Usuniety `from __future__ import annotations`
  (Python 3.12; odwolania wprzod w `core/sheet_parser.py` w cudzyslowie).
- **Testy offline:** `tests/conftest.py` przewraca kazdy test otwierajacy
  gniazdo spoza loopbacku (wyjatek: marker `live`) i stubuje GetCapabilities
  skorowidza; testy odkrywania warstw wylaczaja stub markerem
  `real_wms_layers`. Fixtury z surowych odpowiedzi serwerow
  (`tests/fixtures/gugik_skorowidz/`, `gugik_laz/`, `gugik_asc/`, `cuzk/`).
  Naprawy maja testy przypinajace (RED przed poprawka, GREEN po); testy
  `live` WMS PL-2000 sprawdzaja prawdziwe rekordy/CRS (N5).
- **Wycinek PL zweryfikowany offline na realnych arkuszach 5 m:** cel
  EPSG:2180 bez rozbieznosci wartosci wzgledem arkusza zawierajacego srodek
  piksela; cel EPSG:5514 zgodny z niezaleznym warpem GDAL kazdego arkusza
  (odchylenia przy szwach — `docs/ARCHITECTURE.md` 4.3).
- **Deduplikacja wewnetrzna** (bez zmiany zachowania): `GugikWcsMixin`
  (`providers/pl/wcs.py`: `WCS_FORMATS`, `_construct_wcs_url`,
  `get_supported_formats` dla NMT/NMPT i orto), `validate_godlo`
  w `SkorowidzLayersMixin`, `skorowidz.coverage_hints`, wspolne
  `warp_to_grid` w torze CZ (D8, D13, D14). Usunieta nieosiagalna galaz
  `--product laz` w dyspozycji obszarowej i martwe fallbacki
  `getattr(args, "vertical_crs", "KRON86")` (N5-1).

#### Dokumentacja
- Nowe `docs/ARCHITECTURE.md` (architektura, kontrakty danych, uklad
  `data/`) i `docs/USAGE.md` (przewodnik: przyklady CLI i biblioteki, wynik
  pobrania, kampanie, CLMS, znane problemy; 1.6 "Kiedy `--scale` jest
  niezbedne": skala docelowa = skala arkuszy GUGiK, PL-1992 bez flagi,
  PL-2000 zwykle `--scale 1:2000`). Przyklady bez zbednego `--scale
  1:10000` przy godle PL-1992, `kartograf download CTES96` bez
  `--resolution`.
- `docs/DEVELOPMENT_STANDARDS.md` (15-17) glownym zrodlem konwencji
  (`IMPLEMENTATION_PROMPT.md` usuniety); `README.md` skrocony do
  wprowadzenia; `CLAUDE.md` ograniczony do zasad krytycznych i odsylaczy;
  indeks ADR wylacznie w `docs/DECISIONS.md` (errata 1 ADR-009).
- Dokumentacja zgodna z zachowaniem: ponowienia tylko dla sieci/429/5xx,
  arkusz za granica w trybie listy = `Warning:` i kod 0, lista timeoutow,
  krawedz `cli -> transport` w ARCHITECTURE 2, docstringi
  `LandCoverManager`/`MetadataCache`/`download_pl_cutout` (N2, N4, N10,
  N13, N16). Raporty weryfikacji na zywo w `docs/research/` (etap 1 CZ,
  pogranicza i pas morski, przypadki brzegowe, kampanie ADR-030).

### Usuniete

#### API biblioteki, CLI i providery
- Martwy kod CLMS/Keychain w `providers/corine.py` (`KEYCHAIN_SERVICE`,
  `get_credentials_from_keychain`, `save_credentials_to_keychain`,
  `get_clms_credentials`) — credentials czyta wylacznie podproces auth
  proxy; `CorineProvider.DLR_YEARS` (A5-1).
- Zaszyte `WMS_LAYERS` i fallback na nie (takze przestarzale warstwy NMPT)
  — warstwy z GetCapabilities; `GugikProvider.FORMAT_EXTENSIONS`
  i nadpisanie `get_file_extension`, `GugikOrtoProvider.OPENDATA_URL_PATTERN`,
  atrybuty `RETRY_BACKOFF_BASE` providerow, `SoilGridsProvider.TERYT_WMS_ENDPOINT`
  (tabela w BREAKING).
- `MetadataCache.get_url/set_url` i tabela `url_cache` (usuwana przy
  otwarciu bazy).
- Endpoint `/token` auth proxy i `AuthProxyClient.get_access_token()`.
- Format `GML` (A6-2).
- Re-eksporty implementacji komend z fasady `cli/commands.py` (BREAKING).
- Modul `kartograf.providers.landcover_base` (klasy w
  `kartograf.providers.base`) i stare moduly providerow poza
  `providers/pl/`.
- Prywatne `core.geometry._transform_bbox` (4 narozniki) — zastepuje je
  `core.bbox.transform_bbox` (K6).

#### Pakiet i dokumentacja
- `requirements.txt` i `requirements-dev.txt` — jedynym zrodlem zaleznosci
  jest `pyproject.toml`.
- `IMPLEMENTATION_PROMPT.md` (tresc w `docs/DEVELOPMENT_STANDARDS.md`).

### Poprawione

#### Parsery i selekcja arkuszy
- **Selekcja arkuszy z obwiedni miedzy ukladami:** `SheetParser.get_bbox`,
  `Parser2000.get_bbox`, selekcja PL-1992/PL-2000 i czytniki SHP/GPKG
  (`read_feature_bboxes`/`get_overall_bbox`/`find_sheets_for_geometry`)
  licza obwiednie jedna funkcja `core.bbox.transform_bbox` (21 punktow na
  krawedz) zamiast 4 naroznikow: bbox EPSG:2180 przez poludnik 19°E nie
  gubi pasa przy gornej krawedzi (dla bboxa 20 km pomijano 6 arkuszy; za
  cene mozliwych arkuszy nadmiarowych), arkusze grube przez 19°E (np.
  `N-34`) maja poprawna dolna krawedz (-468 m), obiekt SHP/GPKG przez 19°E
  nie traci ~65 m na polnocy, `find_sheets_for_bbox(..., system="2000")`
  z bboxa WGS84 przez poludnik osiowy strefy (15/18/21/24°E) nie gubi
  wiersza arkuszy (np. 16 zamiast 8). Arkusze 1:10000 bez zmian (1e-6 m).
  To samo dla wycinka PL i selekcji kafli LAZ z bboxa WGS84 (`min_y`
  wycinka nizej o ~479 m) oraz rozpoznawania krajow pod `auto`.
- **Wydajnosc:** `SheetParser.get_bbox("EPSG:2180")` buduje transformer raz
  na proces (200 wywolan: 1371 ms -> 8 ms); czytniki SHP/GPKG — jeden
  transformer na warstwe.
- **Biale znaki wokol godla:** `detect_system`, `path_parts`,
  `SheetIndex.sm5_sheet` i `CuzkDmrProvider.download` obcinaja je spojnie
  z parserami; CLI obcina pozycyjne godlo `download`/`parse` (`kartograf
  download " 302_5550"` nie trafia do toru PL z mylacym `Nieprawidlowe godlo
  PL-1992`).
- **`kartograf parse 6`:** sam numer strefy PL-2000 (5-8) daje komunikat, ze
  to strefa, z najgrubszym formatem `strefa.pas.slup` (np. `6.179.12`),
  takze z jawnym `uklad=` w `SheetParser`; ogolny blad godla podaje formaty
  PL-1992 i PL-2000 z przykladami.
- **`--geometry`:** punktowe SHP daja bbox zdegenerowany zamiast
  `AttributeError`; GPKG bez obwiedni w naglowku czyta punkt z WKB (takze
  Z/M i EWKB z flaga SRID), pusta geometria pomijana, nieobslugiwany typ =
  `ValidationError` zamiast cichego pominiecia rekordu (A1-3, A1-5).

#### CLI
- **Walidacja bboxa w CLI:** `kartograf download --bbox` (PL, CZ, LAZ),
  `landcover download --bbox` i `soilgrids hsg --bbox` parsuja bbox jednym
  `cli._parser.parse_bbox_arg` — bbox odwrocony, NaN/inf albo zla liczba
  wartosci = `Error: Invalid bbox format: <powod>. Expected: ...` na stderr
  i kod 1 (dotad arkusz-smiec, pobieranie albo `Error: ValueError`;
  podpowiedz nie idzie na stdout) (K7b).
- **`kartograf landcover download`** z blednym `--property`/`--depth`/
  `--stat` (SoilGrids) albo `--year` (CORINE) konczy sie `Error: <tresc>`
  i kodem 1 przed siecia, bez `ValueError:` i podpowiedzi `KARTOGRAF_DEBUG`
  (N8).
- **`main()` ma bariere na wyjatki:** blad spoza `KartografError` =
  `Error: <Typ>: <komunikat>` z podpowiedzia `KARTOGRAF_DEBUG=1` i kod 1
  zamiast tracebacku (N1-1).

#### NMT PL i skorowidz GUGiK
- **Parser rekordow skorowidza** rozpoznaje URL-e `.ASC` niezaleznie od
  wielkosci liter (H1).
- **Nieaktualne nazwy warstw skorowidza** (NMT 1m/EVRF2007, orto) — zaszyte
  listy z 0.6.1 zawieraly warstwy wycofane (np. `SkorowidzeNMT2023`; roczne
  warstwy orto 2018..2023 scalone w `SkorowidzeOrtofotomapyStarsze`), nie
  znaly nowych rocznikow (2026), a orto dostawalo "Invalid layer(s) given
  in the LAYERS parameter"; usunieta przyczyna (warstwy z GetCapabilities).

#### Cache i storage
- **`MetadataCache`:** odczyty pod tym samym lockiem co zapisy (rownolegle
  odczyty potrafily oddac wiersz innego klucza, A2-1); `__del__` nie
  importuje i nie rzuca przy zamykaniu interpretera (`ImportError:
  sys.meta_path is None`).
- **`FileStorage.delete()`** usuwa takze sidecar `.meta.json`.

#### Land cover, HSG, CORINE, auth proxy
- **`Bdot10kProvider`** zwraca sciezke faktycznie zapisanego pliku `.gpkg`
  (sidecar nie laduje obok nieistniejacego pliku, A2-6).
- **`CLMS_CREDENTIALS` jest czytane:** zmienna trafia do podprocesu auth
  proxy (przed Keychain), wiec CORINE GeoTIFF dziala takze na Linux
  i Windows — dotad jedynym zrodlem byl Keychain macOS (A4-1).
- **Auth proxy i klient:** urwany strumien nie dokleja odpowiedzi 502 do
  ciala rastra (pobranie bez `Content-Length` ramkowane jako chunked),
  `download_file()` pisze przez plik tymczasowy i sprawdza
  `Content-Length` (bylo: `True` i uszkodzony GeoTIFF, A4-2); start proxy
  i singleton pod lockiem, uchwyt podprocesu i watek drenujacy stderr jako
  stan klasowy (dwa watki nie startuja dwoch proxy, rownolegly CORINE nie
  miesza GeoTIFF z PNG); po `kill()` podproces odbierany (`wait`, bez
  zombie), strumieniowana odpowiedz `/download` zamykana; brak credentials
  nie uruchamia podprocesu (`AuthProxyClient.is_available()` = False poza
  macOS), odczyt portu z timeoutem, stderr drenowany (N4-1, A4-11, A4-13,
  A4-14).
- **SoilGrids i CORINE:** obwiednia bboxa przez `transform_bounds()` zamiast
  dwoch naroznikow (zamawiany obszar byl o ~10% za waski); CORINE liczy
  proporcje obrazu WMS z obwiedni metrycznej (galaz DLR 1990 tracila 1,7x
  rozdzielczosci pionowej) (A4-7).
- **HSG:** piksele nodata (`-32768`, `NaN`, wartosc nodata rastra) dostaja
  0 ("brak danych"), nie grupe B (A4-5); `soilgrids hsg --stats` liczy
  powierzchnie geodezyjnie dla rastrow EPSG:4326 (bylo `0.00 ha`, A4-6).

## [0.6.1] - 2026-03-24

### Fixed
- **NMT 5m: naprawione nazwy warstw WMS**
  - `WMS_LAYERS["5m"]["EVRF2007"]`: `SkorowidzeNMT2022` → `SkorowidzeNMT2022iStarsze`
  - Usunieta nieistniejaca warstwa `SkorowidzeNMT2021iStarsze`
  - Dodana brakujaca warstwa `SkorowidzeNMT2025`
  - Bledne nazwy powodowaly brak wynikow przy pobieraniu NMT 5m mimo dostepnosci danych

### Added
- **Walidacja warstw WMS przez GetCapabilities**
  - `_fetch_wms_layers()` — pobiera liste dostepnych warstw z WMS GetCapabilities
  - `_get_validated_layers()` — porownuje hardcoded warstwy z live WMS, auto-aktualizacja przy rozbieznosci
  - Lazy validation: tylko przy pierwszym wywolaniu `_get_opendata_url()`
  - Graceful fallback: jesli GetCapabilities niedostepne, uzywa hardcoded warstw
  - Warning logowany przy wykryciu rozbieznosci miedzy hardcoded a live
  - In-memory cache per instancja providera (bez lock, benign duplicate OK)
  - Osobny timeout 10s dla GetCapabilities
  - Dziala dla GugikProvider (NMT) i GugikNmptProvider (NMPT) przez dziedziczenie
  - GugikOrtoProvider nieobslugiwany (inna hierarchia dziedziczenia)

### Tests
- **1007 testow** (+17 nowych)
  - Nowy `tests/test_wms_layer_validation.py` — 17 testow dla walidacji warstw WMS

---

## [0.6.0] - 2026-03-03

### Added
- **Parallel downloads with ThreadPoolExecutor**
  - `DownloadManager(max_workers=4)` — configurable thread pool for hierarchy downloads
  - `DownloadResult` dataclass — structured results with succeeded/failed/skipped tracking
  - `_download_hierarchy_parallel()` — concurrent sheet downloads with progress callbacks
  - `LandCoverManager.download_batch()` — parallel batch download for land cover data
  - CLI: `--workers`/`-w` flag on `kartograf download` (default: 4)
  - Thread-safe temp filenames in all providers (`pid_threadid.tmp` pattern)
- **SQLite metadata cache (MetadataCache)**
  - `kartograf/cache/metadata.py` — SQLite WAL mode, TTL 7 days, thread-safe writes
  - URL cache for GUGiK OpenData lookups (NMT, NMPT, Orto)
  - TERYT cache for BDOT10k point-to-TERYT resolution
  - `prune_expired()` — automatic cleanup of stale entries
  - Integrated with GugikProvider, GugikNmptProvider, GugikOrtoProvider, Bdot10kProvider
  - CLI: `kartograf cache stats|clear|path`
- **PL-2000 BBox verification tests**
  - 67 new tests: reference values, hierarchy consistency, live WMS, edge cases
  - `@pytest.mark.live` marker for GUGiK WMS integration tests
- **Public API: eksport MetadataCache i DownloadResult**
  - `from kartograf import MetadataCache, DownloadResult`

### Tests
- **990 testow** (+155 nowych)

---

## [0.5.0] - 2026-03-02

### Added
- **PL-2000 sheet naming system — full support**
  - `Parser2000` class for parsing PL-2000 godla (format `zone.row.column[.subdivisions]`)
  - 5 skal: 1:10000, 1:5000, 1:2000, 1:1000, 1:500
  - 4 strefy merydianowe: 5 (EPSG:2176), 6 (EPSG:2177), 7 (EPSG:2178), 8 (EPSG:2179)
  - BBox calculation z transformacja CRS (pyproj)
  - Hierarchia: get_parent(), get_children(), get_all_descendants(), get_hierarchy_up()
  - `find_sheets_2000_for_bbox()` — BBox to PL-2000 godla lookup
- **SheetParser auto-detekcja PL-1992 vs PL-2000**
  - `SheetParser("6.179.12")` automatycznie rozpoznaje PL-2000
  - `SheetParser("N-34-130-D")` automatycznie rozpoznaje PL-1992
  - Walidacja zgodnosci uklad/format
- **find_sheets_for_bbox: parametr system="1992"|"2000"**
  - `find_sheets_for_bbox(bbox, system="2000")` zwraca godla PL-2000
  - `find_sheets_for_geometry()` rowniez obsluguje parametr system
- **CLI: pelna obsluga PL-2000**
  - `kartograf parse 6.179.12.20` — auto-detekcja, wyswietla strefe i CRS
  - `kartograf download --bbox ... --system 2000` — pobieranie z godlami PL-2000
  - `--bbox-crs` rozszerzony o EPSG:2176-2179
- **FileStorage: obsluga sciezek PL-2000**
  - Struktura katalogow: `nmt_2000_1m/6/179/12/20/6.179.12.20.asc`
    (uwaga 2026-08-22: podkatalog `nmt_2000_1m` nie zostal zrealizowany —
    arkusze PL-2000 ladowaly w `nmt_<res>/` obok PL-1992, patrz ADR-017
    i docstring `FileStorage`; rozdzielenie katalogow odlozone.
    **Domkniete w 0.7.0** — ADR-026 dal PL-2000 wlasne segmenty
    `nmt/pl_2000_<res>_<vcrs>/`; patrz Breaking Changes 0.7.0)
- **Public API: eksport Parser2000 i find_sheets_2000_for_bbox**
  - `from kartograf import Parser2000, find_sheets_2000_for_bbox`

### Removed
- **BDOT10k: usunięto filtrowanie po kategorii (--category pt/hydro)**
  - Pobierany jest cały plik BDOT10k bez podziału na kategorie
  - Usunięto stałe `PT_LAYERS`, `HYDRO_LAYERS`, `CATEGORY_FILTERS`
  - Usunięto parametr `category` z `download_by_teryt()`, `_download_with_retry()`, `_extract_gpkg_from_zip()`
  - Usunięto argument CLI `--category`
  - `_extract_gpkg_from_zip()` wyciąga i scala wszystkie warstwy GPKG z ZIP
  - `get_available_layers()` zwraca wszystkie 15 warstw (PT* + SW*)

### Fixed
- **download_sheet(): PL-2000 sub-10k godla pobierane bezposrednio**
  - Godla PL-2000 w skalach 1:5000, 1:2000, 1:1000, 1:500 sa teraz pobierane
    jako pojedyncze pliki, bez proby rozwijania do 1:10000
- **CLI: dynamiczne etykiety skal**
  - `format_hierarchy()` — naglowek "from current to X" zamiast hardcoded "1:1000000"
  - `format_children()` — "finest scale X" zamiast hardcoded "1:10000"

### Tests
- **835 testow** (+199 nowych; w trakcie prac bylo 849 — 14 testow
  `--category` usunieto w tej samej wersji razem z flaga, ADR-016)

---

## [0.4.1] - 2026-02-08

### Fixed
- **BDOT10k: rtree spatial indices preserved during GPKG merge**
  - After merging multiple GPKG files, only the base (first) file kept its rtree index
  - New `_copy_rtree_index()` method copies rtree virtual table, data, and `gpkg_extensions` entry
  - All merged layers now retain spatial indices for fast spatial queries

### Added
- **Geometry file selection (`--geometry FILE`)**
  - Support for SHP (via pyshp) and GPKG (via sqlite3 + envelope parsing) input files
  - Per-feature bbox extraction for precise tile selection (not entire file bbox)
  - `find_sheets_for_geometry()` — public API for geometry → godla lookup
  - `get_overall_bbox()` — union bbox for landcover/soilgrids
  - CRS auto-detection from .prj (SHP) and gpkg_spatial_ref_sys (GPKG)
  - New dependency: `pyshp>=2.3.0`
- **CLI: `--geometry` and `--layer` for all download commands**
  - `kartograf download --geometry area.shp` — NMT tiles intersecting features
  - `kartograf download --geometry area.gpkg --layer catchments` — GPKG layer selection
  - `kartograf landcover download --source bdot10k --geometry area.shp`
  - `kartograf soilgrids hsg --geometry area.shp`

### Tests
- **636 testow** (+62 nowych)
  - 31 testow `test_geometry.py`: envelope parsing, SHP/GPKG reading, CRS transform, find_sheets_for_geometry, get_overall_bbox
  - 12 testow CLI geometry: download/landcover/soilgrids --geometry, mutual exclusivity
  - 5 testow `TestBdot10kRtreeIndex`: merge preserves indices, no geometry, no index, extensions copied, base preserved

---

## [0.4.0] - 2026-02-07

### Added
- **NMPT (Numeryczny Model Pokrycia Terenu / Digital Surface Model)**
  - `GugikNmptProvider` — dziedziczy z GugikProvider, nadpisuje endpointy NMPT
  - Tylko rozdzielczość 1m, vertical CRS: KRON86 lub EVRF2007
  - Download: godło → OpenData ASC, bbox → WCS GeoTIFF
- **Ortofotomapa (Standard Resolution, 25cm)**
  - `GugikOrtoProvider` — osobna klasa, format TIF
  - Brak vertical CRS (2D RGB), 9 warstw WMS (2018-2025+starsze)
  - Download: godło → OpenData TIF, bbox → WCS GeoTIFF
- **CLI `--product {nmt,nmpt,orto}` — wybór produktu w komendzie download**
  - `kartograf download N-34-130-D-d-2-4 --product nmpt` — pobiera NMPT
  - `kartograf download --bbox ... --product orto` — pobiera ortofoto
  - Domyślnie: nmt (bez zmian)
- **`find_sheets_for_bbox()` — reverse lookup: bbox → godła arkuszy**
  - Algorytm hierarchicznego przycinania (matematyczny, bez WFS)
  - Obsługa EPSG:2180 i EPSG:4326
  - Dowolna skala docelowa (1:1M do 1:10k)
  - Zoptymalizowane wyszukiwanie 1:200k (siatka 12x12)
- **CLI `kartograf download --bbox` — pobieranie NMT dla bbox**
  - `--bbox min_x,min_y,max_x,max_y` — współrzędne bbox
  - `--bbox-crs {EPSG:2180,EPSG:4326}` — CRS bbox (domyślnie EPSG:2180)
  - `godlo` staje się opcjonalny (godlo XOR --bbox)
  - Automatyczne wykrywanie arkuszy i pobieranie w pętli
- **Automatyczne rozwijanie godeł do 1:10000 w `download_sheet()`**
  - `download_sheet("N-34-130-D-d-2")` (1:25000) → automatycznie pobiera 4 arkusze 1:10000
  - `download_sheet("N-34-130-D-d")` (1:50000) → pobiera 16 arkuszy 1:10000
  - Dla godeł 1:10000 zachowanie bez zmian (pojedynczy plik)
  - Nowy parametr `on_progress` — callback postępu przy rozwijaniu hierarchii
  - Zwracany typ: `Path` (1:10000) lub `list[Path]` (coarser scales)
  - CLI dostosowane — wyświetla liczbę pobranych plików przy rozwijaniu

### Tests
- **574 testow, pokrycie 83.95% (cel 80% osiagniety)**
  - Nowy `tests/test_gugik_nmpt.py` — 21 testow dla GugikNmptProvider
  - Nowy `tests/test_gugik_orto.py` — 25 testow dla GugikOrtoProvider
  - Nowy `tests/test_auth_client.py` — 30 testow dla AuthProxyClient
  - Nowy `tests/test_auth_proxy.py` — 24 testy dla CLMSCredentials, ProxyHandler
  - Rozszerzony `tests/test_cli.py` — +12 testow (product CLI), +11 testow (landcover/soilgrids CLI)
  - Rozszerzony `tests/test_storage.py` — +8 testow (product storage)
  - Rozszerzony `tests/test_download_manager.py` — +3 testy (default_ext)
  - Rozszerzony `tests/test_landcover.py` — +38 testow
  - Rozszerzony `tests/test_hsg.py` — +6 testow

### Fixed
- Poprawiony komunikat błędu przy braku pokrycia NMT 5m — zamiast technicznego "No ASC file found in any WMS layer" wyświetla czytelną informację o braku pokrycia danego obszaru w GUGiK

### Changed
- **FileStorage: podkatalogi `1m`/`5m` → `nmt_1m`/`nmt_5m`**
  - Nowy parametr `product` w FileStorage (np. product="nmpt", product="orto")
  - Struktura: `data/nmt_1m/...`, `data/nmt_5m/...`, `data/nmpt/...`, `data/orto/...`
- **DownloadManager: dynamiczne rozszerzenie pliku**
  - `_default_ext` pobierane z `provider.default_extension` zamiast hardcoded `.asc`
- **BaseProvider: nowa property `default_extension`** (domyślnie `.asc`)
- Migracja z black + flake8 na ruff (pyproject.toml)
- Usuniecie .flake8, dodanie .editorconfig
- Standaryzacja dokumentacji wg shared/standards
- Przepisanie CLAUDE.md (7 sekcji, ~148 linii)
- Przepisanie PROGRESS.md (4 sekcje, skondensowane z 785 linii)
- Rozbudowanie DEVELOPMENT_STANDARDS.md (722 linii, 15 sekcji wg shared/standards)
- Rozbudowanie IMPLEMENTATION_PROMPT.md (284 linii, 11 sekcji, aktualny kontekst v0.3.2)
- Aktualizacja README.md, PRD.md, SCOPE.md
- Auto-naprawa kodu przez `ruff check --fix` (63 poprawki: importy, type annotations)

### Added
- Konfiguracja ruff (linter + formatter) w pyproject.toml
- Plik .editorconfig
- Sekcja [project.optional-dependencies] dev w pyproject.toml
- docs/DECISIONS.md — rejestr 9 decyzji architektonicznych (ADR)

### Removed
- Plik .flake8 (konfiguracja pokryta przez ruff)
- Sekcja [tool.black] z pyproject.toml

---

## [0.3.2] - 2026-01-21

### Changed - Storage Structure and Default Vertical CRS

- **Domyślny układ wysokościowy zmieniony na EVRF2007**
  - `GugikProvider`: domyślny `vertical_crs` zmieniony z `"KRON86"` na `"EVRF2007"`
  - `DownloadManager`: domyślny `vertical_crs` zmieniony z `"KRON86"` na `"EVRF2007"`
  - CLI: `--vertical-crs` domyślnie `EVRF2007`
  - Kronsztadt 86 (KRON86) jest przestarzały i dostępny jako opcja legacy

- **Nowa struktura katalogów z rozdzielczością**
  - `FileStorage`: nowy parametr `resolution` (domyślnie `"1m"`)
  - Pliki NMT są teraz rozdzielone według rozdzielczości:
    ```
    data/1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc   # dla 1m
    data/5m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc   # dla 5m
    ```
  - `DownloadManager` automatycznie przekazuje `resolution` do `FileStorage`
  - Domyślne rozszerzenie pliku zmienione z `.tif` na `.asc`

### Breaking Changes

- **Struktura katalogów** - pliki NMT są teraz zapisywane w podkatalogu `1m/` lub `5m/`
  - Stara ścieżka: `data/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc`
  - Nowa ścieżka: `data/1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc`

- **Domyślny vertical_crs** - zmieniony z `KRON86` na `EVRF2007`
  - Aby używać starego układu: `--vertical-crs KRON86`

**Przykłady użycia:**
```bash
# Pobierz NMT 1m (EVRF2007 domyślnie)
kartograf download N-34-130-D-d-2-4
# → data/1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc

# Pobierz NMT 5m
kartograf download N-34-130-D-d-2-4 --resolution 5m
# → data/5m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc

# Użyj starego układu Kronsztadt (legacy)
kartograf download N-34-130-D-d-2-4 --vertical-crs KRON86
```

---

## [0.3.1] - 2026-01-21

### Added - NMT Resolution Selection

- **Wybór rozdzielczości NMT** - Obsługa danych NMT w dwóch rozdzielczościach
  - `1m` (GRID1) - wysoka rozdzielczość, domyślna
  - `5m` (GRID5) - niższa rozdzielczość, tylko dla EVRF2007

- **GugikProvider** - Nowy parametr `resolution`
  - `GugikProvider(resolution="5m", vertical_crs="EVRF2007")`
  - Nowe endpointy WMS dla 5m: `SheetsGrid5mEVRF2007`
  - Automatyczna walidacja: 5m wymaga EVRF2007
  - Nowe metody: `get_supported_resolutions()`, `is_wcs_available()`
  - `download_bbox()` rzuca ValueError dla 5m (WCS niedostępne)

- **DownloadManager** - Nowy parametr `resolution`
  - `DownloadManager(resolution="5m")` - automatycznie wymusza EVRF2007

- **CLI** - Nowa opcja `--resolution`
  - `kartograf download N-34-130-D --resolution 5m`
  - Skrót: `-r 5m`

**Ograniczenia 5m:**
- Dostępne tylko w układzie EVRF2007
- Brak obsługi WCS (download_bbox) - tylko arkusze OpenData

**Przykłady użycia:**
```bash
# Pobierz NMT 1m (domyślnie)
kartograf download N-34-130-D-d-2-4

# Pobierz NMT 5m
kartograf download N-34-130-D-d-2-4 --resolution 5m

# Pobierz hierarchię w 5m
kartograf download N-34-130-D --scale 1:10000 -r 5m
```

### Changed

- **Testy** - 365 testów (18 nowych dla resolution)

### Fixed - Cross-Project Compatibility (2026-01-21)

- **Public API exports** - Uzupełniono brakujące eksporty w głównym module
  - Dodano `SoilGridsProvider` do `kartograf/__init__.py`
  - Dodano `HSGCalculator` do `kartograf/__init__.py`
  - Teraz możliwy import: `from kartograf import SoilGridsProvider, HSGCalculator`

### Fixed - QA Review (2026-01-21)

- **Synchronizacja wersji** - Ujednolicono wersję we wszystkich plikach
  - `pyproject.toml`: 0.3.0 → 0.3.1
  - `kartograf/__init__.py`: 0.3.0-dev → 0.3.1
  - `README.md`: zaktualizowano status i liczbę testów

- **Synchronizacja zależności** - Uzupełniono brakujące zależności
  - `pyproject.toml`: dodano `rasterio>=1.3.0`, `numpy>=1.24.0`
  - `requirements.txt`: dodano `PyJWT[crypto]>=2.8.0`

- **Testy** - Naprawiono test wersji w `test_integration.py`

- **Dokumentacja** - Dodano sekcję QA Review do `PROGRESS.md`

---

## [0.3.0] - 2026-01-18

### Added - SoilGrids i Hydrologic Soil Groups (HSG)

- **SoilGridsProvider** - Provider dla ISRIC SoilGrids (dane glebowe)
  - Globalne dane glebowe w rozdzielczości 250m
  - WCS Endpoint: `https://maps.isric.org/mapserv`
  - **11 parametrów glebowych:**
    - `bdod` - Gęstość objętościowa (kg/dm³)
    - `cec` - Pojemność wymiany kationowej (cmol/kg)
    - `cfvo` - Fragmenty gruboziarniste (%)
    - `clay` - Zawartość gliny (%)
    - `nitrogen` - Azot całkowity (g/kg)
    - `ocd` - Gęstość węgla organicznego (kg/m³)
    - `ocs` - Zasób węgla organicznego (t/ha)
    - `phh2o` - pH w H2O
    - `sand` - Zawartość piasku (%)
    - `silt` - Zawartość pyłu (%)
    - `soc` - Węgiel organiczny (g/kg)
  - **6 głębokości:** 0-5cm, 5-15cm, 15-30cm, 30-60cm, 60-100cm, 100-200cm
  - **5 statystyk:** mean, Q0.05, Q0.5, Q0.95, uncertainty
  - Transformacja CRS: EPSG:2180 → WGS84

- **HSGCalculator** - Kalkulacja Hydrologic Soil Groups dla metody SCS-CN
  - `kartograf/hydrology/hsg.py` - moduł hydrologiczny
  - Klasyfikacja tekstury gleby wg trójkąta USDA (12 klas)
  - Mapowanie tekstury do HSG (A, B, C, D)
  - **Grupy hydrologiczne:**
    - A - wysoka infiltracja (piasek, piasek gliniasty)
    - B - umiarkowana infiltracja (glina piaszczysta, glina)
    - C - wolna infiltracja (glina ilasta)
    - D - bardzo wolna infiltracja (ił)
  - Automatyczne pobieranie clay/sand/silt z SoilGrids
  - Statystyki pokrycia dla każdej grupy HSG

- **CLI soilgrids** - Nowe komendy CLI
  - `kartograf landcover download --source soilgrids --property <param> --depth <głębokość>`
  - `kartograf landcover list-layers --source soilgrids`
  - `kartograf soilgrids hsg --godlo <godło>` - kalkulacja HSG
  - Opcje HSG: `--depth`, `--output`, `--keep-intermediate`, `--stats`

**Przykłady użycia:**
```bash
# Pobierz węgiel organiczny
kartograf landcover download --source soilgrids --godlo N-34-130-D --property soc

# Pobierz zawartość gliny
kartograf landcover download --source soilgrids --godlo N-34-130-D --property clay --depth 15-30cm

# Oblicz HSG dla metody SCS-CN
kartograf soilgrids hsg --godlo N-34-130-D --stats
```

### Added - Land Cover (Pokrycie Terenu)

- **LandCoverProvider** - Nowa abstrakcja dla providerów danych pokrycia terenu
  - Metody: `download_by_teryt()`, `download_by_bbox()`, `download_by_godlo()`
  - Wspólny interfejs dla różnych źródeł danych

- **Bdot10kProvider** - Provider dla BDOT10k (GUGiK)
  - Pobieranie paczek powiatowych przez TERYT
  - Pobieranie przez WMS GetFeatureInfo dla URL paczki
  - Pobieranie przez godło arkusza (konwersja na bbox)
  - **12 warstw pokrycia terenu (PT*):**
    - PTGN - Grunty nieużytkowe
    - PTKM - Tereny komunikacyjne
    - PTLZ - Tereny leśne
    - PTNZ - Tereny niezabudowane
    - PTPL - Place
    - PTRK - Roślinność krzewiasta
    - PTSO - Składowiska
    - PTTR - Tereny rolne
    - PTUT - Uprawy trwałe
    - PTWP - Wody powierzchniowe
    - PTWZ - Tereny zabagnione
    - PTZB - Tereny zabudowane
  - Automatyczne scalanie warstw PT* z ZIP do jednego GeoPackage
  - Format wyjściowy: GeoPackage (.gpkg), SHP

- **CorineProvider** - Provider dla CORINE Land Cover (Copernicus)
  - Europejska klasyfikacja pokrycia terenu (44 klasy)
  - Dostępne lata: 1990, 2000, 2006, 2012, 2018
  - **Trzy źródła danych (w kolejności priorytetu):**
    1. **CLMS API** - GeoTIFF z kodami klas (wymaga OAuth2)
    2. **EEA Discomap WMS** - Podgląd PNG (lata 2000-2018)
    3. **DLR WMS** - Fallback dla 1990
  - OAuth2 RSA authentication dla CLMS API
  - Przechowywanie credentials w macOS Keychain (serwis: `clms-token`)

- **LandCoverManager** - Zarządzanie pobieraniem danych pokrycia terenu
  - Dispatch do odpowiedniego providera
  - Obsługa wielu metod selekcji obszaru

- **CLI landcover** - Nowe komendy CLI
  - `kartograf landcover download --source bdot10k --teryt <kod>`
  - `kartograf landcover download --source corine --year <rok> --godlo <godło>`
  - `kartograf landcover list-sources`
  - `kartograf landcover list-layers --source bdot10k`

### CLMS API Authentication - Auth Proxy

CorineProvider używa **Auth Proxy** dla bezpiecznej autentykacji CLMS API:

**Architektura bezpieczeństwa:**
```
CorineProvider → localhost HTTP → AuthProxy (subprocess) → Keychain → CLMS API
```

- Credentials (klucz prywatny RSA) są izolowane w osobnym procesie
- Główna aplikacja nigdy nie widzi credentials
- Tylko odpowiedzi API są przekazywane do aplikacji

**Nowe moduły:**
- `kartograf/auth/proxy.py` - serwer HTTP izolujący credentials
- `kartograf/auth/client.py` - klient automatycznie uruchamiający proxy

**Konfiguracja:**
1. Zarejestruj się na https://land.copernicus.eu
2. Wygeneruj API credentials (JSON)
3. Zapisz do Keychain:
   ```bash
   security add-generic-password -a "$USER" -s "clms-token" -w '<json_credentials>'
   ```

**Tryby pracy:**
```python
# Domyślny (bezpieczny) - używa proxy
provider = CorineProvider()

# Bezpośredni (dla testów) - credentials widoczne
provider = CorineProvider(clms_credentials={...}, use_proxy=False)
```

**Uwaga:** Jeśli credentials nie są skonfigurowane, CorineProvider automatycznie używa WMS (podgląd PNG zamiast GeoTIFF z kodami klas).

### Dependencies

- Dodano `PyJWT[crypto]>=2.8.0` - JWT generation dla OAuth2
- Dodano `rasterio>=1.3.0` - przetwarzanie rastrów GeoTIFF
- Dodano `numpy>=1.24.0` - operacje na tablicach

### Technical Details

- 347 testów (42 dla landcover, 28 dla soilgrids, 34 dla HSG)
- Formatowanie: black, flake8

### Sources

- BDOT10k: https://www.geoportal.gov.pl/en/data/topographic-objects-database-bdot10k/
- CORINE Land Cover: https://land.copernicus.eu/en/products/corine-land-cover
- EEA Discomap: https://image.discomap.eea.europa.eu
- DLR EOC: https://geoservice.dlr.de/eoc/land/wms
- ISRIC SoilGrids: https://soilgrids.org/
- SoilGrids Documentation: https://docs.isric.org/globaldata/soilgrids/

---

## [0.2.0] - 2026-01-18

### Changed - Nowa architektura pobierania

**Uproszczona logika pobierania:**
- **Godło → OpenData (ASC)** - pobieranie arkusza przez godło zawsze daje plik ASC
- **BBox → WCS (GeoTIFF)** - pobieranie przez bounding box daje GeoTIFF/PNG/JPEG

**Zmiany API:**
- `download_sheet(godlo)` - zawsze pobiera ASC (usunięto parametr `format`)
- `download_hierarchy(godlo, target_scale)` - pobiera wszystkie arkusze jako ASC
- `download_bbox(bbox, filename, format)` - **nowa metoda** dla pobierania przez bbox
- Usunięto `construct_url()` z publicznego API
- `DownloadManager` nie przyjmuje już parametru `format` w konstruktorze

### Added

- **Pobieranie ASC przez OpenData** - Automatyczne wyszukiwanie URL przez WMS GetFeatureInfo
  - Zapytania do warstw: `SkorowidzeNMT2019`, `SkorowidzeNMT2018`, `SkorowidzeNMT2017iStarsze`
  - Pobieranie z `opendata.geoportal.gov.pl`

- **SheetParser.get_bbox()** - Obliczanie bounding box arkusza
  - Obsługiwane CRS: `EPSG:2180` (PL-1992), `EPSG:4326` (WGS84)
  - Transformacja współrzędnych przez `pyproj`

- **BBox** - Nowy typ danych w public API

- **GugikProvider.download_bbox()** - Pobieranie przez bounding box z WCS

### Dependencies

- Dodano `pyproj>=3.6.0` do wymagań

### Technical Details

- 245 testów

## [0.1.0] - 2026-01-17

### Added

- **SheetParser** - Parser for Polish topographic map sheet identifiers (godlo)
  - Support for scales 1:1,000,000 to 1:10,000
  - Support for "1992" coordinate system layout
  - Hierarchy navigation: `get_parent()`, `get_children()`, `get_hierarchy_up()`
  - Descendant enumeration: `get_all_descendants(target_scale)`
  - Special handling for 1:500k to 1:200k division (36 sheets per section)

- **DownloadManager** - Coordinated download of NMT data
  - Single sheet download: `download_sheet(godlo)`
  - Hierarchy download: `download_hierarchy(godlo, target_scale)`
  - Progress callbacks with `DownloadProgress` dataclass
  - Skip existing files option for resumable downloads
  - Missing sheets detection: `get_missing_sheets()`

- **GugikProvider** - Integration with GUGiK WCS service
  - GeoTIFF and Arc/Info ASCII Grid format support
  - Retry logic with exponential backoff (3 attempts)
  - 30-second timeout per request

- **FileStorage** - Hierarchical file storage management
  - Automatic directory structure based on godlo components
  - Atomic writes (temp file + rename)
  - Path generation: `data/N-34/130/D/d/2/4/N-34-130-D-d-2-4.tif`

- **CLI** - Command-line interface
  - `kartograf parse <godlo>` - Display sheet information
  - `kartograf parse <godlo> --hierarchy` - Show hierarchy to 1:1M
  - `kartograf parse <godlo> --children` - Show direct children
  - `kartograf download <godlo>` - Download single sheet
  - `kartograf download <godlo> --scale <scale>` - Download hierarchy
  - Options: `--format`, `--output`, `--force`, `--quiet`

- **Public API** - Clean imports from main module
  - `from kartograf import SheetParser, DownloadManager`
  - All exceptions: `KartografError`, `ParseError`, `ValidationError`, `DownloadError`
  - Providers: `BaseProvider`, `GugikProvider`

- **Test Coverage** - 97% coverage with 235 tests
  - Unit tests for all modules
  - Integration tests for complete workflows

### Technical Details

- Python 3.12+ required
- Single dependency: `requests>=2.31.0`
- Project structure follows src layout
- Configured with black, flake8, pytest

[0.8.0]: https://github.com/Daldek/Kartograf/compare/v0.7.2...v0.8.0
[0.7.2]: https://github.com/Daldek/Kartograf/compare/v0.7.1...v0.7.2
[0.7.1]: https://github.com/Daldek/Kartograf/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/Daldek/Kartograf/compare/v0.6.1...v0.7.0
[0.6.1]: https://github.com/Daldek/Kartograf/compare/4cec5d87b9aad1ffdb59693ec7163c7c97540983...v0.6.1
[0.6.0]: https://github.com/Daldek/Kartograf/compare/v0.5.0...4cec5d87b9aad1ffdb59693ec7163c7c97540983
[0.5.0]: https://github.com/Daldek/Kartograf/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/Daldek/Kartograf/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/Daldek/Kartograf/compare/402d8091dc02dfacb77619950fc06504bea6d7ec...v0.4.0
[0.3.2]: https://github.com/Daldek/Kartograf/compare/v0.3.1...402d8091dc02dfacb77619950fc06504bea6d7ec
[0.3.1]: https://github.com/Daldek/Kartograf/releases/tag/v0.3.1
[0.3.0]: https://github.com/Daldek/Kartograf/releases/tag/v0.3.0
[0.2.0]: https://github.com/Daldek/Kartograf/releases/tag/v0.2.0
[0.1.0]: https://github.com/Daldek/Kartograf/releases/tag/v0.1.0
