# Plan B — `elevation` CZ: DMP OK, DMP 1G, DMR 4G ETRS89 (TM33), LAZ CZ i raport dostepnosci CZ — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Data:** 2026-10-15

**Goal:** W grupie `elevation` dla CZ (CUZK): NMPT CZ - DMP OK 0,5 m (arkusze
SM5 i kafle TM33 z plikow `openzu`, wycinek z ImageServer) i DMP 1G 2 m
(kafel TM33 i wycinek z ImageServer); NMT CZ - kafle TM33 DMR 4G z plikow
ETRS89 z wysokosciami EVRF2007 natywnie; chmury punktow LAZ CZ czterech
modeli (DMR 5G, DMR 4G, DMP 1G, DMP OK) dla arkusza i obszaru; raport
`elevation availability --country cz|auto` (arkusze i pliki dla obszaru,
bez lotow); wszystko z rejestru wariantow planu A, w magazynie wersji
z sidecarem i sygnalem `http`.

**Architecture:** Warianty CZ jako wpisy rejestru (`ProductVariant` z planu A,
`model`, `systems`, kanal) w deskryptorach `cz.cuzk.*`; trasa (plik SM5 /
plik TM33 / ImageServer z warpem / wycinek) wynika z wariantu i kodu arkusza.
`CuzkDmrProvider` -> `CuzkRasterProvider` (produkt i rozdzielczosc z
rejestru; endpointy kanalow wybierane po `(transport, horizontal_crs)`).
Nowy provider `CuzkLazProvider` (`kartograf/providers/cuzk/laz.py`) i tor
`kartograf/download/cz_laz.py` (`download_cz_laz`/`check_cz_laz`, sciezka
wersji jak arkusz SM5). `check_availability` (plan A) dostaje galaz CZ:
indeks `KladyMapovychListu` + `HEAD` plikow (rozmiar, `Last-Modified`).

**Spec:** `docs/superpowers/specs/2026-10-13-katalog-produktow-design.md`
(K1, K3, K6, K8; 4.3; 6 plan B; 7); pomiary
`docs/research/2026-10-15-plan-a-b/raport.md` sekcja 3 oraz
`docs/research/2026-10-13-katalog-produktow/probki.md` (wiersze
`cz.cuzk.atom.DMP*`, `DMR*`, `cz.cuzk.img.*`).

**Wersja docelowa:** 0.8.0. **ADR:** bez nowego numeru - sekcja
"Uzupelnienie: warianty CZ (plan B)" w ADR-041 (rejestr i raport sa jedna
decyzja; numery 042+ naleza do planow C-E).

**Warunek wstepny:** plan A scalony do `develop` (rejestr
`kartograf/sources/variants.py`, `ProductVariant.systems/channel`,
`AvailabilityReport` z polami CZ, komenda `elevation availability`,
`index_area_cache`). Kod wyjsciowy: `develop` po planie A; przed startem
sprawdz symbole z sekcji "Fakty" (plan A mogl przesunac linie;
zmiana nazwy symbolu = zatrzymaj sie i opisz roznice koordynatorowi).

---

## Weryfikacja specu wzgledem kodu i pomiarow (2026-10-15)

1. **Dzis CZ = tylko NMT:** `kartograf/download/options.py:72`
   `CZ_ONLY_NMT` ("--product {product} dla CZ bedzie dostepny w etapie 2"),
   uzywane w `kartograf/download/data.py:420`, `:477`, `:564`, `:1243`;
   `kartograf/download/data.py:546-549` (`_validate_cross_country`: produkt
   inny niz `nmt` tylko PL); LAZ `auto` z CZ = blad `:1253-1261`.
2. **Rozdzielczosc wybiera model:** `kartograf/providers/cuzk/dmr.py:58`
   `_RESOLUTION_KEYS = {"2m": "cz.cuzk.dmr5g", "5m": "cz.cuzk.dmr4g"}`,
   `kartograf/providers/cuzk/__init__.py:35-38` i `dmr.py:118-133` - listy
   `2m/5m`; `kartograf/download/cz_sheets.py:53` `RESOLUTION_CZ`, `:69-90`
   `cz_sheet_resolution` (SM5 tylko 5m). Dla NMPT CZ te sama zasada:
   `0.5m` = DMP OK, `2m` = DMP 1G - etykiety K2 jak w PL.
3. **Kafel TM33 to dzis warp z ImageServer (Bpv)** (`dmr.py:219-262`
   `download`, `:292-363` `_export_raster`): CUZK publikuje gotowe kafle
   TM33 DMR 4G i DMP OK w ETRS89/TM33N z wysokosciami EVRF2007 (EPSG:5621,
   metadane CSW, raport 3.3), a DMR 5G i DMP 1G - tylko jako LAZ i ImageServer
   (`DMR5G-TIFF`, `DMP1G-TIFF` = 404).
4. **Dwa kanaly plikow w jednym deskryptorze:** `channel_signal`
   (`kartograf/sources/registry.py:389-406`) i `_endpoint_for`
   (`dmr.py:588-596`) biora PIERWSZY kanal danego transportu - przy SM5
   (EPSG:5514) i TM33 (EPSG:3045) potrzebny wybor po `(transport,
   horizontal_crs)`.
5. **DMP OK ImageServer:** `dmp_obrazova_korelace` i `dmp` maja ten sam opis
   i katalog (raport 3.1) - jeden endpoint `dmp_obrazova_korelace`, bez
   zapasowego.
6. **Pliki `openzu`:** ZIP z `.tif`+`.tfw` (TIFF bez CRS - nadawany
   z kanalu, jak dzis `_assign_crs(output_path, "EPSG:5514")`, `dmr.py:598`)
   albo z jednym `.laz`; `ETag`/`Last-Modified` zawsze (sygnal `http`); brak
   arkusza = 404 HTML. `CuzkClient.fetch_file(..., unzip_single=".tif")`
   (`kartograf/providers/cuzk/client.py:109-149`) obsluguje oba przypadki
   (`unzip_single=".laz"` dla LAZ; `_extract_zip_pair` wymaga dokladnie
   jednego pliku z rozszerzeniem).
7. **Lat nalotu CZ nie ma:** ImageServer `/query` bez dat, ATOM
   `<updated>` = `Last-Modified` pliku (raport 3.1, 3.4) - raport CZ podaje
   date publikacji z `HEAD`, nie rok danych (spec 4.3 zaktualizowany:
   bez ATOM).
8. **Indeks arkuszy gotowy:** `SheetIndex.sm5_sheets_for_bbox` i
   `tm33_tiles_for_bbox` (`kartograf/providers/cuzk/sheets.py:114-136`,
   "foundation of stage 2: LAZ/Orto") - dzis nieuzywane w torze pobierania.
9. **Backlog A5-7:** `GugikLazProvider.download(url, ...)` lamie LSP
   wzgledem `BaseProvider.download(godlo, ...)` - zmiana na `download_tile`
   "razem z etapem 2 (LAZ CZ)" (`docs/PROGRESS.md`, backlog po audycie 0.7.0).
10. **Plan aktualizacji:** `kartograf/download/plan.py:27-29` `Track` nie
    ma toru LAZ CZ - nowy `"cz_laz"`.

## Global Constraints

Jak w planie A (Python z `.venv` z korzenia worktree, TDD, testy offline z
fixtur prawdziwych odpowiedzi, brama przed kazdym commitem, Conventional
Commits po polsku autor `Daldek <git@debever.pl>` bez `Co-Authored-By`, CRLF
w `docs/DECISIONS.md`, dane na zywo tylko w `<katalog-danych>` z jawnym
`--output`, bez wartosci domyslnych wplywajacych na dane, CLI tylko
tlumaczy). Dodatkowo:

- ADR-024: tresc CZ reprojektowana wylacznie lokalnie przypieta operacja;
  plik natywny (SM5 5514/Bpv, TM33 3045/EVRF2007) bez reprojekcji.
- Chmury punktow nie sa transformowane (ani poziomo, ani pionowo): uklad
  pliku LAZ = uklad publikacji CUZK.

## Decyzje implementacyjne

1. **Warianty CZ w rejestrze** (`ProductVariant` planu A + nowe pole
   `model: str | None` - CZ: `dmr5g`, `dmr4g`, `dmp1g`, `dmpok`; PL: `None`).
   Kanaly z `horizontal_crs` i natywnym `vertical_crs_options`;
   endpointy `https://openzu.cuzk.gov.cz/opendata/<P>/epsg-<5514|3045>/{sheet}.zip`
   i `https://ags.cuzk.gov.cz/arcgis2/rest/services/<usluga>/ImageServer`:

   | Klucz | Produkt, etykieta | Kanaly (transport, uklad, wysokosci natywnie) | `storage_subdir` |
   |---|---|---|---|
   | `cz.cuzk.dmr5g` | nmt 2m | ImageServer `dmr5g` (5514, Bpv) | `nmt/cz_dmr5g_{vcrs}` (bez zmian) |
   | `cz.cuzk.dmr4g` | nmt 5m | pliki `DMR4G-TIFF` 5514 Bpv; **NOWY** pliki `DMR4G-TIFF` 3045 EVRF2007; ImageServer `dmr4g` | `nmt/cz_dmr4g_{vcrs}` (bez zmian) |
   | `cz.cuzk.dmpok` (NOWY) | nmpt 0.5m | pliki `DMPOK-TIFF` 5514 Bpv i 3045 EVRF2007; ImageServer `dmp_obrazova_korelace` | `nmpt/cz_dmpok_{vcrs}` |
   | `cz.cuzk.dmp1g` (NOWY) | nmpt 2m | ImageServer `dmp1g` (5514, Bpv) | `nmpt/cz_dmp1g_{vcrs}` |
   | `cz.cuzk.dmr5g_laz` (NOWY) | laz | pliki `DMR5G` 5514 Bpv i 3045 EVRF2007 | `laz/cz_dmr5g_{vcrs}` |
   | `cz.cuzk.dmr4g_laz` (NOWY) | laz | pliki `DMR4G` 5514/3045 | `laz/cz_dmr4g_{vcrs}` |
   | `cz.cuzk.dmp1g_laz` (NOWY) | laz | pliki `DMP1G` 5514/3045 | `laz/cz_dmp1g_{vcrs}` |
   | `cz.cuzk.dmpok_laz` (NOWY) | laz | pliki `DMPOK-LAZ` 5514/3045 | `laz/cz_dmpok_{vcrs}` |

   Kanal plikow: `update_signal="http"`, `capabilities={"sheet_files"}`;
   ImageServer: `"none"`, `{"bbox_raster"}`. `_COUNTRIES["CZ"].dataset_keys`
   (`registry.py:369-374`) - wszystkie klucze `cz.`. Nazwy deskryptorow z
   nazwa modelu ("DMP OK - Digitalni model povrchu z obrazove korelace (0,5 m)").
2. **Trasa wariantu (tabela, jedno zrodlo prawdy dla CLI/API/raportu):**

   | Zadanie | Kod/obszar | `--vertical-crs` | Kanal | Uwagi |
   |---|---|---|---|---|
   | nmt 5m, nmpt 0.5m | arkusz SM5 | Bpv | plik 5514 | natywnie |
   | nmt 5m, nmpt 0.5m | arkusz SM5 | EVRF2007 | plik 5514 + przypieta transformacja Bpv->EVRF2007 | jak dzis DMR 4G |
   | nmt 2m, nmpt 2m | arkusz SM5 | - | brak | `Error:` "SM5 sa tylko dla 5m (DMR 4G) / 0.5m (DMP OK); 2m: kafel TM33 albo --cutout" |
   | nmt 5m, nmpt 0.5m | kafel TM33 | EVRF2007 | plik 3045 | natywnie, **zmiana dla DMR 4G** (dzis warp) |
   | nmt 5m, nmpt 0.5m | kafel TM33 | Bpv | ImageServer + warp na siatke 3045 | jak dzis |
   | nmt 2m, nmpt 2m | kafel TM33 | Bpv / EVRF2007 | ImageServer + warp (+ transformacja) | jak dzis DMR 5G |
   | nmt, nmpt | obszar + `--cutout` | Bpv / EVRF2007 | ImageServer | jak dzis; obszar CZ bez `--cutout` = blad jak dzis |
   | laz (model) | arkusz SM5 / obszar | Bpv | plik 5514 | SM5 + EVRF2007 = `Error:` "LAZ w S-JTSK jest w Bpv; EVRF2007: kafle TM33" |
   | laz (model) | kafel TM33 / obszar | EVRF2007 | plik 3045 | TM33 + Bpv = `Error:` symetrycznie |
   | laz | `--cutout` | - | brak | `Error:` jak dzis dla PL |

   Obszar LAZ CZ: arkusze z `SheetIndex` - Bpv -> `sm5_sheets_for_bbox`
   (obszar w EPSG:5514), EVRF2007 -> `tm33_tiles_for_bbox` (EPSG:3045, kafle
   z `IN_CZ` = prawda). Uklad poziomy wynika z ukladu wysokosci (pliki CUZK
   sa publikowane tylko w tych parach) - bez nowej flagi `--sheet-system`.
3. **Wybor modelu LAZ CZ:** nowa flaga `--model dmr5g|dmr4g|dmp1g|dmpok`
   (API `model=`), wymagana dla `--product laz`, gdy zadanie obejmuje CZ;
   z PL albo innym produktem = `Error:` ("--model dotyczy tylko --product laz
   w CZ"). Wartosci i opisy z rejestru: "dmr5g (teren, DMR 5G), dmr4g (teren,
   siatka 5 m), dmp1g (powierzchnia, DMP 1G), dmpok (powierzchnia, korelacja
   obrazowa)". Rastry CZ wybiera nadal `--resolution` (bez drugiej drogi).
4. **Provider rastrow CZ:** `CuzkRasterProvider(product, resolution,
   session=None, cache=None, horizontal_crs=None, *, vertical_crs)` zastepuje
   `CuzkDmrProvider` (nazwa klamalaby dla DMP); `create_cz_raster_provider(product,
   resolution, session=None, cache=None, horizontal_crs=None, *, vertical_crs)`
   zastepuje `create_dmr_provider`. Warianty CZ to wiersze trasy z decyzji 2:
   po jednym na (produkt, rozdzielczosc albo model, uklad wysokosci, system
   `sm5`/`tm33`) z kanalem `DIRECT_FILES` (plik) albo `ARCGIS_IMAGE` (warp);
   `find_variant(product=, country="CZ", resolution=, vertical_crs=,
   system=)` (system z kodu arkusza: `sm5`/`tm33`; parametr `system` istnieje
   od planu A, dla PL filtruje `("1992", "2000")`). Wycinek nie jest wierszem rejestru:
   to kanal `ARCGIS_IMAGE` deskryptora (jak WCS w PL). Endpoint kanalu z nowej
   funkcji `registry.channel_for(key, transport, horizontal_crs) -> AccessChannel`
   (blad, gdy brak albo niejednoznaczny); `channel_signal` dostaje
   `horizontal_crs`. Natywny uklad wysokosci = `channel.vertical_crs_options`;
   zadany spoza nich = przypieta transformacja (jak dzis). `download(sheet, ...)` wybiera trase z decyzji 2;
   wysokosc pliku TM33 EVRF2007 bez `_apply_vertical_shift`, sidecar bez
   przypietej operacji pionowej, `vertical_crs="EPSG:5621"`.
   **Realizacja (2026-10-16):** trase opisuje `CuzkRasterProvider.route(sheet=None)
   -> CzRasterRoute(channel, horizontal_crs, horizontal, vertical)` (kanal,
   uklad wyniku i przypiete operacje; `None` = wycinek); tory arkusza i wycinka
   pisza sidecar z trasy. Operacja pionowa powstaje w `route()` (przed siecia),
   nie w konstruktorze - kafel TM33 EVRF2007 z pliku jej nie ma. Sygnal pliku:
   `file_signal(sheet)` (dawne `sm5_signal`). Wariant CZ wybiera
   `find_cz_variant`/`cz_variant_error` (`sources/variants.py`), nie
   `find_variant` planu A.
5. **Tor arkusza CZ:** `download_cz_sheet(sheet, *, output_dir, product,
   vertical_crs, resolution=None, update=None, plan=None, cache=True,
   on_notice=None, on_download=None)` i `check_cz_sheet` - nowe wymagane
   `product` (dzis domyslnie NMT); `cz_sheet_resolution` ->
   `cz_sheet_variant(sheet, product, resolution, vertical_crs) -> ProductVariant`
   (SM5: jedyna rozdzielczosc produktu z plikami SM5 moze byc pominieta;
   TM33: wymagana). Sygnal i `capability` z kanalu trasy (plik = `http`
   i `sheet_files`; warp = `none` i `bbox_raster`); `extra.mapname`/`cz_share`
   dla SM5 jak dzis (`write_sidecar` w `_run_cz_sheet`, `cz_sheets.py:219-270`).
6. **Wycinek CZ:** `download_cz_cutout(bbox, *, output_dir, product,
   horizontal_crs, vertical_crs, resolution, ...)` i `check_cz_cutout` -
   nowe wymagane `product`; ImageServer z wariantu.
7. **LAZ CZ:** `CuzkLazProvider(model, session=None, cache=None, *,
   vertical_crs)` (`kartograf/providers/cuzk/laz.py`): `descriptor_key`,
   `sheets(area) -> list[SheetInfo]` (decyzja 2), `download(sheet, output_path,
   timeout=..., *, on_download=None, on_response=None)` (`fetch_file(...,
   unzip_single=".laz")`), `file_signal(sheet) -> dict` (`head_signal`).
   Tor `kartograf/download/cz_laz.py`: `download_cz_laz(*, model, vertical_crs,
   output_dir, sheet=None, bbox=None, update=None, plan=None, parent_request=None,
   workers=4, cache=True, on_notice=None, on_progress=None) -> CzLazResult`
   i `check_cz_laz(...)` z tymi samymi argumentami wyboru -> `UpdatePlan`;
   `CzLazResult(files: tuple[VersionedFile, ...], failed: tuple[CzLazFailure, ...],
   stale: tuple[PlanItem, ...], notices: tuple[Notice, ...])`. Polityka plikow
   jak arkusz SM5 (`fetch_version`, sygnal `http`, etykieta `downloaded`), tor
   planu `"cz_laz"`, sciezka `laz/cz_<model>_<vcrs>/<hierarchia godla>/<godlo>.laz`
   (`path_parts`: `CTES/96`, `760/5518`), sidecar: `dataset`, `request.sheet`,
   uklad poziomy pliku (EPSG:5514/3045), pionowy natywny (EPSG:8357/5621),
   `extra.http`, SM5 `extra.mapname`/`cz_share`, obszar `extra.parent_request`.
   Blad pliku nie przerywa pozostalych (jak `download_laz_area`).
8. **`download_data`:** `model: str | None = None` w sygnaturze i `_SELECTION`
   (`kartograf/download/data.py:372-392`); CZ obsluguje `nmpt` i `laz`;
   `--country auto` z LAZ dzieli obszar na kraje (PL: kafle WFS, CZ: arkusze
   wg decyzji 2); flagi tylko-PL LAZ (`--year`, `--min-year`, `--max-year`,
   `--all-campaigns`, `--min-density`) w `auto` zawezaja do PL istniejacym
   `AUTO_NARROWED_TO_PL` (`download/area.py::pl_only_flags`, rejestr z planu A
   + flagi LAZ); brak `--model` przy obszarze siegajacym CZ = `Error:`
   ("obszar siega CZ: podaj --model ... albo --country pl"). Usun
   `CZ_ONLY_NMT` i galezie z punktu 1 weryfikacji.
9. **Raport CZ (`check_availability(country="cz"|"auto")`):** dla produktu -
   warianty CZ z kanalem plikow (NMT: DMR 4G SM5/TM33; NMPT: DMP OK SM5/TM33;
   LAZ: 4 modele x SM5/TM33). Kombinacja = wariant x uklad (`horizontal`
   `S-JTSK` albo `ETRS89-TM33`): arkusze indeksu przecinajace czesc CZ
   obszaru (SM5: `PODIL > 0`; TM33: `IN_CZ`), `HEAD` kazdego pliku (rownolegle,
   `workers=8`, cache `MetadataCache.get_index_area/set_index_area` z kluczem `"head|<url>"`, TTL 7 dni,
   `force` pomija odczyt); `sheets_full` = 200, `sheets_missing` = 404,
   `complete` = brak `sheets_missing` i co najmniej jeden arkusz, `uncovered` =
   `bool(sheets_missing)`, `uncovered_m2` = suma przeciec ram brakujacych
   arkuszy z obszarem, `published` = min/max `Last-Modified` (RRRR-MM-DD),
   `size_bytes` = suma `Content-Length`, `year`/`acquisition_dates`/`campaigns`
   = `None`/`None`/`()`. Modele bez plikow rastrowych (DMR 5G, DMP 1G) -
   jedna `Notice("info", CZ_SERVICE_ONLY, ...)`: "DMR 5G (2m) i DMP 1G (2m)
   sa dla calego CZ jako wycinek (--cutout) i LAZ (--product laz --model ...)".
   Inny blad niz 404 (5xx, timeout) = `DownloadError` (nie "brak pliku").
   `auto`: czesci PL i CZ wg `split_bbox_by_country` (`download/countries.py:156`);
   kraj, ktory nie mogl byc sprawdzony, przy drugim sprawdzonym =
   `Notice` `CHECK_FAILED` i `ok=False` (jak `download_data` `auto`); oba = blad.
   `areas`: CZ `crs="EPSG:5514"`, `area_m2` = czesc obszaru w CZ (prostokat
   czesci), `land_m2` = `area_m2` (CZ nie ma maski ladu w raporcie).
   **Realizacja (2026-10-16):** czesc CZ w ukladzie kazdego systemu arkuszy
   jak sciezka LAZ obszaru w `download_data` - `auto`: `country_bbox(...,
   cz_crs=<5514|3045>)` z oryginalu, `cz`: bbox/obwiednia geometrii przez
   `bbox_to_crs`; regula arkuszy `SheetIndex.file_sheets(system, obszar)`
   (wspolna z `CuzkLazProvider.sheets`), w cache pod `"cz-sheets|<system>|
   <obszar w mm>"`. Godlo CZ = rama arkusza (SM5 z indeksu po nazwie, TM33
   z godla), arkusze drugiego systemu z obwiedni ramy. `CZ_SERVICE_ONLY`
   per produkt (nmt: DMR 5G, nmpt: DMP 1G; tekst wymienia tez kafel TM33
   z uslugi). Flagi roku tylko PL: `cz` (i godlo CZ) = `ValidationError`,
   `auto` z obszarem w obu krajach = `AUTO_NARROWED_TO_PL`, obszar tylko
   w CZ = `ValidationError`. CLI: `ok=False` = kod wyjscia 1 (raport czesci
   PL drukowany).
10. **Podpowiedzi CZ (bez `--output`):** raster SM5/TM33 - po jednej komendzie
    na arkusz (`elevation download --product nmpt --sheet CTES96 --resolution
    0.5m --vertical-crs Bpv`), CLI pokazuje 5 i liczbe pozostalych (jak
    `MAX_HINT_LINES`, `download/data.py:105`), JSON wszystkie; LAZ - jedna
    komenda obszaru (`elevation download --product laz --country cz --model
    dmr5g --vertical-crs Bpv --bbox ...`).
    **Realizacja (2026-10-16):** kolejnosc flag jak w podpowiedziach PL
    (obszar, potem wariant): `elevation download --product laz --country cz
    --bbox=... --bbox-crs EPSG:5514 --model dmr5g --vertical-crs Bpv`; zadanie
    z godlem CZ - LAZ tez po komendzie na arkusz (godlo siega tylko swojego
    systemu); stopka CLI: kompletne kombinacje CZ, po 5 polecen.
11. **Zmiany API (0.8.0, z "Co zrobic"):** `CuzkDmrProvider` ->
    `CuzkRasterProvider(product, ...)`, `create_dmr_provider` ->
    `create_cz_raster_provider(product, ...)`; `download_cz_sheet`/`check_cz_sheet`/
    `download_cz_cutout`/`check_cz_cutout` z wymaganym `product`;
    `download_data(..., model=)`; `GugikLazProvider.download(url, ...)` ->
    `download_tile(url, ...)` (A5-7); nowe eksporty: `CuzkRasterProvider`,
    `create_cz_raster_provider`, `CuzkLazProvider`, `download_cz_laz`,
    `check_cz_laz`, `CzLazResult`, `CzLazFailure`.
12. **Kafle TM33 DMR 4G EVRF2007 w istniejacych magazynach:** ten sam segment
    i godlo; lokalna wersja z warpu (sygnal `none`, bez `extra.http`) zostaje
    w trybie domyslnym (`Info:` "lokalna wersja niesprawdzona"); `--force`
    pobiera plik CUZK jako nowa wersje (inna tresc) i przepina dowiazanie.
    CHANGELOG "Co zrobic": odswiez kafle TM33 DMR 4G EVRF2007 `--force`.

## Review Focus

1. **Trasa z jednej tabeli:** `test_route_table` parametryzowany wierszami
   decyzji 2 (CLI i API: ten sam kanal, ten sam blad).
2. **Natywny EVRF2007 bez transformacji:** kafel TM33 z pliku 3045 nie
   przechodzi `_apply_vertical_shift`, sidecar bez operacji pionowej;
   SM5 EVRF2007 nadal z przypieta operacja (`test_tm33_file_is_native_evrf2007`,
   `test_sm5_evrf2007_still_transformed`).
3. **LAZ bez transformacji:** zla para uklad/system = `Error:` przed siecia;
   plik LAZ 1:1 z ZIP (`test_laz_file_bytes_equal_zip_member`).
4. **404 != awaria:** w raporcie 404 = arkusz bez pliku, 5xx/timeout =
   `DownloadError`; w pobieraniu 404 = blad tego arkusza z podpowiedzia
   indeksu (jak dzis `_download_sm5`).
5. **Raport bez pobran:** tylko `HEAD` i zapytania indeksu
   (`test_cz_availability_never_gets_files`).

---

## Mapa plikow

| Plik | Zmiana |
|---|---|
| `kartograf/sources/variants.py` | `ProductVariant.model`; `variants(..., model=)` |
| `kartograf/sources/registry.py` | deskryptory z decyzji 1; `channel_for`; `channel_signal(..., horizontal_crs)` |
| `kartograf/providers/cuzk/dmr.py` -> `kartograf/providers/cuzk/raster.py` | `CuzkRasterProvider` (trasa, kanaly, TM33 z pliku) |
| `kartograf/providers/cuzk/laz.py` (NOWY) | `CuzkLazProvider` |
| `kartograf/providers/cuzk/__init__.py` | `create_cz_raster_provider`, eksporty |
| `kartograf/download/cz_sheets.py` | `product`, `cz_sheet_variant`, sygnal z kanalu |
| `kartograf/download/cz_cutout.py` | `product` |
| `kartograf/download/cz_laz.py` (NOWY) | `download_cz_laz`, `check_cz_laz`, `CzLazResult`, `CzLazFailure` |
| `kartograf/download/plan.py` | `Track` + `"cz_laz"` |
| `kartograf/download/options.py` | teksty CZ z rejestru, `--model`, usuniete `CZ_ONLY_NMT` |
| `kartograf/download/data.py` | `model`, dyspozycja CZ `nmpt`/`laz`, `auto` dla LAZ |
| `kartograf/download/area.py` | `pl_only_flags` + flagi LAZ PL |
| `kartograf/download/availability.py` | galaz CZ i `auto` |
| `kartograf/download/laz.py`, `kartograf/providers/pl/gugik_laz.py` | `download_tile` (A5-7) |
| `kartograf/notices.py` | `CZ_SERVICE_ONLY` |
| `kartograf/cli/groups/elevation.py`, `kartograf/cli/download_cmd.py`, `kartograf/cli/availability_cmd.py` | `--model`, `--country cz/auto` w `availability`, teksty |
| `kartograf/__init__.py` | eksporty z decyzji 11 |
| `tests/fixtures/cuzk/real_2026_10_1x/` (NOWE) | odpowiedzi `HEAD`, `KladyMapovychListu`, male ZIP-y (Task 1) |
| `tests/test_cuzk_raster.py` (z `test_cuzk_dmr.py`), `tests/test_cuzk_laz.py`, `tests/test_cz_laz.py` (NOWE), `tests/test_cz_sheets.py`, `tests/test_cz_cutout.py`, `tests/test_availability.py`, `tests/test_parity.py`, `tests/test_cli.py`, `tests/test_gugik_laz.py`, `tests/test_laz_download.py`, `tests/test_sources_registry.py` | Task 2-7 |
| `docs/DECISIONS.md` (CRLF), `docs/CHANGELOG.md`, `docs/USAGE.md`, `docs/ARCHITECTURE.md`, `docs/SCOPE.md`, `docs/PRD.md` | Task 8 |

## Fakty o obecnym kodzie (zweryfikowane 2026-10-15 na `bcdf37d`, przed planem A)

- Rejestr CZ: `kartograf/sources/registry.py:276-310` `cz.cuzk.dmr5g`,
  `:312-360` `cz.cuzk.dmr4g` (kanaly `DIRECT_FILES` SM5 z `endpoint=".../DMR4G-TIFF/epsg-5514/{sheet}.zip"`
  i `ARCGIS_IMAGE`), `:369-374` `_COUNTRIES["CZ"]`, `:389-406` `channel_signal`.
- Provider: `kartograf/providers/cuzk/dmr.py:97` `CuzkDmrProvider`,
  `:100-170` `__init__` (fail-fast transformacji `:146-150`, kanaly `:156-170`),
  `:197-210` `horizontal_transform`, `:219-262` `download`, `:264-290`
  `download_bbox`, `:292-363` `_export_raster`, `:377-383` `sm5_signal`,
  `:385-398` `_sm5_url`, `:400-424` `_download_sm5`, `:470` `_apply_vertical_shift`,
  `:557` `bbox_to_crs`, `:588` `_endpoint_for`, `:598` `_assign_crs`;
  fabryka `kartograf/providers/cuzk/__init__.py:20-45`.
- Klient i indeks: `kartograf/providers/cuzk/client.py:109-149` `fetch_file`,
  `:265-320` `_extract_zip_pair`; `kartograf/providers/cuzk/sheets.py:62-69`
  `SheetInfo` (`podil`, `in_cz`), `:72-136` `SheetIndex`.
- Tor arkusza: `kartograf/download/cz_sheets.py:53` `RESOLUTION_CZ`, `:69-90`
  `cz_sheet_resolution`, `:93-116` `_sheet_slot`, `:118-121` `_signal`,
  `:150-273` `_run_cz_sheet`, `:276-284` `_sheet_provider`, `:287-308`
  `check_cz_sheet`, `:310-359` `download_cz_sheet`.
- Wycinek: `kartograf/download/cz_cutout.py:280-301` `_cz_provider`,
  `:304-333` `check_cz_cutout`, `:336-393` `download_cz_cutout`.
- Dyspozycja: `kartograf/download/data.py:404-433` `_execute`
  (`:418-422` CZ tylko NMT), `:449-540` `_dispatch_area`, `:543-556`
  `_validate_cross_country`, `:559-574` `_download_geometry`, `:1170-1233`
  `_download_cz`, `:1236-1308` `_download_laz`.
- Walidacja: `kartograf/download/options.py:46-49` `VERTICAL_CRS_CZ`, `:72`
  `CZ_ONLY_NMT`, `:227-259` `cz_option_error`, `:262-275` `require_cz_cutout`.
- LAZ PL: `kartograf/download/laz.py:110-198` (`laz_version_ref`, `laz_slot`,
  `write_laz_sidecar`), `:226-350` `_run_laz_download`, `:426-585`
  `check_laz_area`/`download_laz_area`; `kartograf/providers/pl/gugik_laz.py:959-1000`
  `download(url, ...)`.
- Plan i wersje: `kartograf/download/plan.py:27-30` `Track`/`TRACKS`;
  `kartograf/download/fetch.py:85` `FileSlot`, `:116` `VersionedFile`,
  `:344` `fetch_version`, `:399` `inspect_version`.
- Testy: `tests/test_cuzk_dmr.py` (114-145 wybor rozdzielczosci, 353
  `test_sm5_with_2m_resolution_rejected`, 1105 `test_tm33_sheet_warps_then_shifts_vertically`),
  `tests/test_cz_sheets.py` (405, 433), `tests/test_cz_cutout.py`,
  `tests/test_cuzk_sheets.py`, `tests/test_cuzk_client.py`, `tests/test_cli.py`
  (testy z tekstem "etapie 2": 6436, 6465, 6474, 7004), `tests/test_parity.py`
  (`test_cz_sheet` 110-137, `test_cz_cutout` 140-176, `test_cz_sm5_sheet` 585).

---

### Task 1: Fixtury CUZK (live, swiadomie)

**Files:** Create `tests/fixtures/cuzk/real_2026_10_1x/` + `README.md`.

- [ ] **Step 1: Nagranie** (throwaway skrypt poza repo):
  - naglowki `HEAD` (status, `ETag`, `Last-Modified`, `Content-Length`,
    `Content-Type`) dla `CTES96` (SM5) i `760_5518` (TM33) wszystkich
    produktow z tabeli decyzji 1 (wartosci referencyjne: raport 3.2) oraz
    jednego 404 (`DMR5G-TIFF/epsg-5514/CTES96.zip`) i nieistniejacego arkusza;
  - `KladyMapovychListu` warstwy 24 i 26 dla bboxa
    `-447000,-1114000,-446000,-1113000` (EPSG:5514) i odpowiadajacego w 3045
    (jak dzisiejsze fixtury `tests/test_cuzk_sheets.py`; dopisz, czego brak);
  - male prawdziwe ZIP-y: `DMR4G-TIFF/epsg-3045/760_5518.zip` (59 KB),
    `DMR4G/epsg-3045/760_5518.zip` (LAZ, 14 KB), `DMR4G/epsg-5514/CTES96.zip`
    (LAZ, 181 KB) - pliki danych w fixturach tylko dla tych trzech (najmniejsze);
    wieksze (DMP OK) tylko naglowki;
  - `ImageServer?f=json` dla `dmp_obrazova_korelace` i `dmp1g` (pixel 0,5/2 m).
- [ ] **Step 2: Commit** - `test(fixtures): odpowiedzi CUZK dla DMP OK, DMP 1G, TM33 i LAZ`

### Task 2: Warianty CZ w rejestrze i wybor kanalu

**Files:** `kartograf/sources/{variants,registry}.py`, `tests/test_variants.py`,
`tests/test_sources_registry.py`, `docs/DECISIONS.md` (uzupelnienie ADR-041).

- [ ] **Step 1: Test RED:** `test_cz_registry_matches_publication`
  (zbior `(product, label|model, vertical_crs, system, transport)` wariantow
  CZ = tabela decyzji 1-2); `test_channel_for_by_crs` (`cz.cuzk.dmr4g`:
  `DIRECT_FILES` + EPSG:3045 -> endpoint `DMR4G-TIFF/epsg-3045`, + EPSG:5514
  -> `epsg-5514`; brak kanalu = `ValidationError`); `test_channel_signal_by_crs`;
  `test_cz_model_values` (`variants(product="laz", country="CZ")` daje modele
  `dmr5g, dmr4g, dmp1g, dmpok`).
- [ ] **Step 2: Implementacja** wg decyzji 1 i 4 (`ProductVariant.model`,
  `channel_for`, `channel_signal(key, transport, horizontal_crs=None)` - bez
  `horizontal_crs` dziala tylko, gdy kanal jest jeden).
- [ ] **Step 3: ADR-041 - sekcja "Uzupelnienie: warianty CZ (plan B,
  <data>)"** (CRLF): modele CZ i trasy (decyzja 2), natywny EVRF2007
  plikow ETRS89, `--model` dla LAZ CZ, raport CZ bez lat (HEAD, nie ATOM),
  odrzucone (fallback `dmp`, ATOM, nowa flaga `--sheet-system` dla LAZ,
  transformacja chmur punktow).
- [ ] **Step 4: Brama i commit** - `feat(sources): warianty CZ (DMP OK, DMP 1G, TM33 ETRS89, LAZ) w rejestrze`

### Task 3: `CuzkRasterProvider` - DMP OK, DMP 1G, kafle TM33 z plikow

**Files:** `kartograf/providers/cuzk/dmr.py` -> `raster.py` (git mv),
`kartograf/providers/cuzk/__init__.py`, `kartograf/download/{cz_sheets,cz_cutout,data}.py`,
`kartograf/__init__.py`; testy `tests/test_cuzk_dmr.py` -> `tests/test_cuzk_raster.py`,
`tests/test_cz_sheets.py`, `tests/test_cz_cutout.py`.

- [ ] **Step 1: Test RED** (fixtury Task 1, atrapy sesji):
  `test_route_table` (wiersze rastrow z decyzji 2 przez `download_cz_sheet`
  i `download_cz_cutout`: kanal/URL zapytania albo `ValidationError` przed
  siecia); `test_tm33_file_is_native_evrf2007` (DMR 4G `760_5518` EVRF2007:
  plik z `epsg-3045`, wartosci 1:1 z ZIP, CRS EPSG:3045, sidecar
  `vertical_crs = EPSG:5621`, bez `pinned_transforms.vertical`,
  `capability = sheet_files`, `extra.http` z `ETag`); `test_sm5_evrf2007_still_transformed`
  (SM5 + EVRF2007 = plik 5514 + operacja pionowa jak dzis);
  `test_tm33_bpv_still_warp` (DMR 4G TM33 Bpv = ImageServer + warp, sygnal
  `none`); `test_dmp_ok_endpoints` (`dmp_obrazova_korelace`, nigdy `dmp`);
  `test_dmp1g_sm5_rejected_with_hint`; `test_existing_tm33_warp_kept_locally`
  (magazyn z wersja z warpu: tryb domyslny = `local` + `Info:`, `--force` =
  nowa wersja z pliku, dowiazanie przepiete).
- [ ] **Step 2: Implementacja** wg decyzji 2, 4-6, 12: `CuzkRasterProvider`,
  `create_cz_raster_provider`, `cz_sheet_variant`, `product` w torach arkusza
  i wycinka, `_signal` z kanalu trasy, `horizontal_crs` sidecara z kanalu.
- [ ] **Step 3: Przepisz testy usuwanego zachowania:** `tests/test_cuzk_dmr.py`
  114-145 (wybor przez rozdzielczosc -> przez wariant), 353 (tekst z
  rejestru), 1105 (`test_tm33_sheet_warps_then_shifts_vertically` -> wariant
  TM33 Bpv albo 2m, bo TM33 5m EVRF2007 nie jest juz warpem);
  `tests/test_cz_sheets.py` 405/433 (`product` wymagane).
- [ ] **Step 4: Brama i commit** - `feat(cz)!: DMP OK, DMP 1G i natywne kafle TM33 (EVRF2007) z plikow CUZK`

### Task 4: LAZ CZ (provider, tor, A5-7)

**Files:** Create `kartograf/providers/cuzk/laz.py`, `kartograf/download/cz_laz.py`,
`tests/test_cuzk_laz.py`, `tests/test_cz_laz.py`; Modify `kartograf/download/plan.py`
(`Track`), `kartograf/download/laz.py`, `kartograf/providers/pl/gugik_laz.py`
(`download_tile`), `tests/test_gugik_laz.py`, `tests/test_laz_download.py`.

- [ ] **Step 1: Test RED:** `test_laz_file_bytes_equal_zip_member`
  (`DMR4G/epsg-5514/CTES96.zip` -> `laz/cz_dmr4g_bpv/CTES/96/CTES96.laz`
  identyczny z czlonem ZIP, sidecar EPSG:5514/EPSG:8357, `extra.http`,
  `extra.mapname`, `cz_share`); `test_laz_tm33_evrf2007` (`760_5518`,
  EPSG:3045/EPSG:5621); `test_laz_wrong_pair_rejected` (SM5+EVRF2007,
  TM33+Bpv: `ValidationError` przed siecia z podpowiedzia); `test_laz_area_sheets`
  (obszar `-447000,-1114000,-446000,-1113000` Bpv: arkusze z warstwy 24,
  EVRF2007: kafle z warstwy 26 z `IN_CZ`); `test_laz_404_is_sheet_failure`
  (jeden arkusz 404 -> `failed` z podpowiedzia, pozostale zapisane);
  `test_cz_laz_check_and_upgrade_plan` (`check_cz_laz` bez pobran, pozycje
  toru `cz_laz`, `--upgrade` z planem pobiera tylko `missing`/`newer`, zmieniony
  `ETag` = `stale`); `test_laz_tile_rename` (PL `download_tile(url, ...)`
  dziala, `download` nie istnieje - test zachowania toru LAZ PL bez zmian).
- [ ] **Step 2: Implementacja** wg decyzji 7 i 11 (A5-7: `GugikLazProvider.download_tile`,
  wywolanie w `kartograf/download/laz.py`). Zamknij A5-7 w backlogu przy
  integracji (koordynator).
- [ ] **Step 3: Brama i commit** - `feat(cz): chmury punktow LAZ CUZK (DMR 5G/4G, DMP 1G/OK) w magazynie wersji`

### Task 5: `download_data` i CLI dla CZ (`nmpt`, `laz`, `--model`)

**Files:** `kartograf/download/{options,data,area}.py`, `kartograf/cli/groups/elevation.py`,
`kartograf/cli/download_cmd.py`, `tests/test_cli.py`, `tests/test_cli_translation.py`,
`tests/test_input_errors.py`, `tests/test_parity.py`.

- [ ] **Step 1: Test RED:** `test_cz_nmpt_sheet_and_cutout` (CLI = API,
  `tests/test_parity.py` scenariusze `test_cz_nmpt_sm5` i `test_cz_dmp1g_cutout`);
  `test_cz_laz_sheet_and_area` (scenariusz zgodnosci `test_cz_laz_area`);
  `test_model_rules` (`--model` bez `--product laz`, z `--country pl`,
  brak `--model` dla obszaru CZ i `auto` z CZ: `Error:` z lista modeli z
  rejestru); `test_auto_laz_split` (`auto` PL+CZ: kafle PL z WFS i arkusze
  CZ, wspolny `parent_request`, `--year` -> zawezenie do PL z `Info:`);
  `test_no_stage2_messages` (zadnego "etapie 2"; testy `tests/test_cli.py`
  6436, 6465, 6474, 7004 przepisane na nowe zachowanie: produkt dostepny);
  `test_help_cz_from_registry` (`--resolution` w `--help` wymienia CZ
  `nmt: 2m, 5m; nmpt: 0.5m, 2m`; `--model` z opisami modeli);
  `test_list_sources_cz` (wiersze `cz.cuzk.dmpok`, `cz.cuzk.dmp1g`,
  `cz.cuzk.*_laz` z WYBOR, np. `--product laz --country cz --model dmpok`);
  zaktualizuj `test_pl_only_flags_from_registry` z planu A: `--product nmpt
  --resolution 0.5m` (DMP OK) i `2m` (DMP 1G) nie zawezaja juz `auto` do PL,
  `nmpt 1m`/`0.6m` nadal zawezaja (wynik z rejestru, bez zmiany kodu
  `pl_only_flags`).
- [ ] **Step 2: Implementacja** wg decyzji 3, 8, 10: `model` w `_download_arguments`
  (`kartograf/cli/download_cmd.py:366-392`), `download_data`/`check_data`
  i `_SELECTION`; `cz_option_error` z rejestru (produkt, etykieta, uklad,
  model); usun `CZ_ONLY_NMT`; `_download_laz` dzieli kraje; teksty CLI
  (`VERTICAL_CRS_CZ`: "Bpv (natywny dla S-JTSK/SM5 i uslug ImageServer),
  EVRF2007 (natywny dla plikow ETRS89/TM33; z Bpv przypieta transformacja)").
- [ ] **Step 3: Smoke offline:** `python -m kartograf.cli.commands elevation
  download --help`, `... elevation list-sources`.
- [ ] **Step 4: Brama i commit** - `feat(cli)!: elevation CZ - nmpt, laz i --model`

### Task 6: Raport dostepnosci CZ i `auto`

**Files:** `kartograf/download/availability.py`, `kartograf/cli/availability_cmd.py`,
`kartograf/cli/groups/elevation.py` (`--country cz|auto` w `availability`),
`kartograf/notices.py`, `tests/test_availability.py`, `tests/test_cli_availability.py`,
`tests/test_parity.py`.

- [ ] **Step 1: Test RED** (fixtury Task 1): `test_cz_nmpt_combinations`
  (DMP OK S-JTSK i ETRS89-TM33: `sheets_full`, `published` z `Last-Modified`,
  `size_bytes` = suma `Content-Length`, `year is None`; `Notice`
  `CZ_SERVICE_ONLY` o DMP 1G); `test_cz_missing_file_is_incomplete` (404 jednego
  arkusza -> `sheets_missing`, `complete=False`, `uncovered_m2` > 0);
  `test_cz_server_error_is_error` (503 -> `DownloadError`, nie `missing`);
  `test_cz_laz_eight_combinations`; `test_auto_both_countries` (bbox
  przygraniczny Cieszyn/Cesky Tesin: `areas` PL i CZ, kombinacje obu krajow,
  `ok=True`); `test_auto_one_country_failed` (blad CZ przy sprawdzonym PL:
  `ok=False`, `CHECK_FAILED`); `test_cz_availability_never_gets_files`
  (tylko `HEAD` na `openzu`, zadnego `GET`); `test_cz_hints` (raster: komenda
  na arkusz bez `--output`; LAZ: jedna komenda obszaru; kazda przechodzi
  walidacje `download_data`); `test_cz_json_cli_equals_api` (zgodnosc,
  zamrozony zegar).
- [ ] **Step 2: Implementacja** wg decyzji 9-10 (tabela CLI: kolumny MODEL,
  UKLAD, ROZDZ., WYSOKOSCI, FORMAT, ARKUSZE (sa/brak), PUBLIKACJA, ROZMIAR,
  KOMPLET; dla CZ bez kolumny ROK - naglowek "CUZK nie publikuje lat nalotu;
  daty = publikacja pliku").
- [ ] **Step 3: Brama i commit** - `feat(api): raport dostepnosci CZ i --country auto`

### Task 7: Integracja z manifestem projektu (krok warunkowy)

Sprawdz `git ls-tree develop kartograf/project/commands.py`.

- [ ] **Jesli manifest scalony:** `--model` to nowa flaga danych `elevation
  download` - dopisz `"model"` do `COMMANDS["elevation download"].options`
  (`kartograf/project/commands.py`), upewnij sie, ze `options_to_json`/
  `options_from_json` przenosza napis bez zmian; `test_task_options_equal_parser_data_flags`
  i `test_options_json_roundtrip` zielone; test zadania projektu LAZ CZ
  (`project add t elevation download --product laz --country cz --model dmr4g
  --vertical-crs Bpv --sheet CTES96` + `project download t` na atrapie
  providera -> przypiecie `laz/cz_dmr4g_bpv/CTES/96/CTES96.laz`);
  `elevation availability --country cz` nadal odrzucane przez `project add`.
- [ ] **Jesli nie:** nic w kodzie; w opisie dla koordynatora: plan manifestu
  musi miec `model` w opcjach `elevation download` (jego test zgodnosci z
  parserem to wymusi).
- [ ] **Commit (jesli byly zmiany)** - `feat(project): --model w zadaniu elevation download`

### Task 8: Dokumentacja

- [ ] **ADR-041:** sekcja uzupelnienia (Task 2) z wynikami E2E.
- [ ] **CHANGELOG `[0.8.0] - Unreleased`:** Dodane - DMP OK, DMP 1G, LAZ CZ,
  natywne kafle TM33, raport CZ/auto; Zmienione (BREAKING) z "Co zrobic" -
  decyzje 11 i 12 (`CuzkRasterProvider`, `create_cz_raster_provider`,
  `product` w torach CZ, `download_tile`, kafle TM33 DMR 4G EVRF2007 `--force`).
- [ ] **USAGE:** 1.4 (CZ: tabela produktow i tras z decyzji 2, przyklady DMP
  OK SM5/TM33, DMP 1G wycinek, LAZ CZ arkusz/obszar, `--model`), 1.7 (raport
  CZ i `auto`), 2 (biblioteka: `download_cz_laz`, `product` w `download_cz_sheet`),
  4.3 (tor `cz_laz` w planie aktualizacji).
- [ ] **ARCHITECTURE:** 2 (moduly `providers/cuzk/raster.py`, `laz.py`,
  `download/cz_laz.py`), 3.3 (segmenty `nmpt/cz_dmpok_*`, `nmpt/cz_dmp1g_*`,
  `laz/cz_<model>_*`; regula 1 - CZ nadal bez ukladu poziomego w segmencie,
  bo model + uklad wysokosci wyznaczaja plik), 4.4-4.6 (trasy, `auto` LAZ),
  4.7 (LAZ CZ), 4.9 (raport CZ).
- [ ] **SCOPE:** 2.2 (CZ: produkty), 3.1 (etap 2: DMP/LAZ zrobione; ortofoto
  i ZABAGED - plan D), 3.3 (podprojekt 3: plan B).
- [ ] **PRD:** 3.9 (CZ), 5 (Public API).
- [ ] **Commit** - `docs: plan B - CZ (DMP OK, DMP 1G, TM33, LAZ, raport)`

### Task 9: Brama i E2E na zywo

Dane: `<katalog-danych>/kartograf/e2e/2026-10-xx-plan-b/` (jawne `--output`).
Raport: `docs/research/2026-10-xx-plan-b-e2e/raport.md`.

- [ ] **Brama** (liczby do raportu).
- [ ] **E2E-1 DMP OK SM5:** `elevation download --product nmpt --sheet CTES96
  --resolution 0.5m --vertical-crs Bpv` -> `nmpt/cz_dmpok_bpv/CTES/96/CTES96.tif`,
  5000x4000 px (2,5 x 2 km), piksel 0,5 m, EPSG:5514, sidecar `extra.http`;
  drugi przebieg = `local` (jeden `HEAD`).
- [ ] **E2E-2 DMP OK TM33 EVRF2007:** `--sheet 760_5518 --vertical-crs
  EVRF2007` -> plik `epsg-3045` 1:1 (4000x4000 px), bez operacji pionowej.
- [ ] **E2E-3 DMR 4G TM33 EVRF2007:** natywny plik zamiast warpu - porownaj
  z warpem z `develop` (max roznica wartosci, siatka identyczna);
  `--force` na magazynie z warpem przepina dowiazanie.
- [ ] **E2E-4 DMP 1G:** kafel TM33 Bpv (warp z `dmp1g`) i wycinek `--cutout
  --horizontal-crs EPSG:5514` (piksel 2 m).
- [ ] **E2E-5 LAZ CZ:** `--product laz --country cz --model dmr5g
  --vertical-crs Bpv --sheet CTES96` (sha256 pliku `.laz` = sha256 czlonu
  ZIP pobranego recznie; `probki.md` podaje sume ZIP `a1090300beba`), TM33 `760_5518` EVRF2007,
  obszar kilku arkuszy (`--bbox=-447000,-1114000,-444000,-1113000
  --bbox-crs EPSG:5514`; liczba arkuszy = odpowiedz indeksu warstwy 24),
  bledy par uklad/system przed siecia.
- [ ] **E2E-6 raport:** `elevation availability --product nmpt --country cz
  --bbox=-447000,-1114000,-446600,-1113600 --bbox-crs EPSG:5514`, `--product
  laz` (8 kombinacji), `--country auto` dla bboxa przygranicznego (PL+CZ);
  `--json` = API; czas.
- [ ] **Raport E2E i commit** - `docs(research): E2E planu B (CZ)`.

## Kryteria zamkniecia

- Kazdy wiersz tabeli decyzji 2 dziala z CLI i API (albo konczy sie
  `Error:` przed siecia z podpowiedzia), CLI = API w scenariuszach parytetu.
- Natywne pliki TM33 bez transformacji; SM5 EVRF2007 z przypieta operacja;
  LAZ 1:1 z ZIP, bez transformacji.
- Raport CZ i `auto` bez pobran plikow; 404 odroznione od awarii.
- `CZ_ONLY_NMT` i komunikaty "etapie 2" usuniete; A5-7 zamkniete.
- Brama zielona; E2E opisane; ADR-041 (uzupelnienie), CHANGELOG, USAGE,
  ARCHITECTURE, SCOPE, PRD zaktualizowane.
