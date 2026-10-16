# Rejestr decyzji — Kartograf

Kazda decyzja architektoniczna lub projektowa jest udokumentowana ponizej.
Format: numer, data, kontekst (dlaczego temat powstal), rozwazone opcje, decyzja, konsekwencje.

Tresc decyzji opisuje stan w chwili jej podjecia i nie jest modernizowana.
Pozniejsze zmiany faktow i ustalenia dodatkowe sa dopisywane na koncu wpisu
jako erraty `**Errata N (RRRR-MM-DD, zrodlo/powod):**`, numerowane w obrebie
ADR chronologicznie. Szablon nowego wpisu: [Szablon nowego ADR](#szablon-nowego-adr).

**Slownik statusow** (linia `**Status:**` kazdego wpisu):
- `Przyjeta` — decyzja obowiazuje w calosci;
- `Przyjeta — czesciowo zastapiona przez ADR-x (zakres)` — wskazana czesc nie obowiazuje;
- `Przyjeta — uzupelniona przez ADR-x (zakres)` — obowiazuje, pozniejsza decyzja ja rozszerza;
- `Zastapiona przez ADR-x` — nie obowiazuje;
- `Odrzucona` — rozwazona i nieprzyjeta.

Po srednikiu status moze podac relacje odwrotne (`zastepuje ...`, `uzupelnia ...`);
kazda relacja jest zapisana po obu stronach.

## Indeks

| ADR | Tytul | Data | Status |
|---|---|---|---|
| [ADR-001](#adr-001-flat-layout-zamiast-src-layout) | Flat layout zamiast src layout | 2026-01-17 | Przyjeta |
| [ADR-002](#adr-002-auth-proxy-do-izolacji-credentials-clms) | Auth Proxy do izolacji credentials CLMS | 2026-01-18 | Przyjeta |
| [ADR-003](#adr-003-opendata-asc-vs-wcs-geotiff--rozdzielenie-sciezek-pobierania-nmt) | OpenData (ASC) vs WCS (GeoTIFF) — rozdzielenie sciezek pobierania NMT | 2026-01-18 | Przyjeta — czesciowo zastapiona przez [ADR-027](#adr-027---target-crs-dla-pl--scalony-wycinek-bbox-mozaika--pinned-warp) (bbox = WCS GeoTIFF; errata 1) i [ADR-036](#adr-036-magazyn-wersjonowany) (`DownloadManager.download_bbox` usuniete; errata 2) |
| [ADR-004](#adr-004-evrf2007-jako-domyslny-uklad-wysokosciowy) | EVRF2007 jako domyslny uklad wysokosciowy | 2026-01-21 | Zastapiona w 0.8.0 — errata 1 (uklad wysokosci wymagany, bez wartosci domyslnej) |
| [ADR-005](#adr-005-struktura-katalogow-nmt-rozdzielona-wg-rozdzielczosci) | Struktura katalogow NMT rozdzielona wg rozdzielczosci | 2026-01-21 | Przyjeta — czesciowo zastapiona przez [ADR-013](#adr-013-zmiana-nazw-podkatalogow-storage-z-1m5m-na-nmt_1mnmt_5m), a nastepnie [ADR-026](#adr-026-uklad-data-per-produkt--segmenty-i-szablony-w-deskryptorach) (realizacja ukladu katalogow; errata 1) |
| [ADR-006](#adr-006-landcoverprovider-jako-osobna-hierarchia-od-baseprovider) | LandCoverProvider jako osobna hierarchia od BaseProvider | 2026-01-18 | Przyjeta |
| [ADR-007](#adr-007-migracja-z-black--flake8-na-ruff) | Migracja z black + flake8 na ruff | 2026-02-03 | Przyjeta |
| [ADR-008](#adr-008-kondensacja-progressmd-z-785-do-80-linii) | Kondensacja PROGRESS.md z 785 do ~80 linii | 2026-02-03 | Przyjeta |
| [ADR-009](#adr-009-rozbudowanie-development_standards-i-implementation_prompt) | Rozbudowanie DEVELOPMENT_STANDARDS i IMPLEMENTATION_PROMPT | 2026-02-03 | Przyjeta |
| [ADR-010](#adr-010-algorytm-find_sheets_for_bbox--hierarchiczne-przycinanie-bez-wfs) | Algorytm find_sheets_for_bbox — hierarchiczne przycinanie bez WFS | 2026-02-07 | Przyjeta |
| [ADR-011](#adr-011-gugiknmptprovider-dziedziczy-z-gugikprovider) | GugikNmptProvider dziedziczy z GugikProvider | 2026-02-07 | Przyjeta |
| [ADR-012](#adr-012-gugikortoprovider-jako-osobna-klasa-nie-dziedziczy-z-gugikprovider) | GugikOrtoProvider jako osobna klasa (nie dziedziczy z GugikProvider) | 2026-02-07 | Przyjeta |
| [ADR-013](#adr-013-zmiana-nazw-podkatalogow-storage-z-1m5m-na-nmt_1mnmt_5m) | Zmiana nazw podkatalogow storage z 1m/5m na nmt_1m/nmt_5m | 2026-02-07 | Zastapiona przez [ADR-026](#adr-026-uklad-data-per-produkt--segmenty-i-szablony-w-deskryptorach); czesciowo zastepuje [ADR-005](#adr-005-struktura-katalogow-nmt-rozdzielona-wg-rozdzielczosci) (nazwy katalogow) |
| [ADR-014](#adr-014-bdot10k-category-based-extraction-pt-vs-hydro) | BDOT10k category-based extraction (pt vs hydro) | 2026-02-08 | Zastapiona przez [ADR-016](#adr-016-bdot10k--usunięcie-filtrowania-po-kategorii-pobieranie-całego-pliku) |
| [ADR-015](#adr-015-pyshp--sqlite3-zamiast-fiona-dla-czytania-geometrii) | pyshp + sqlite3 zamiast fiona dla czytania geometrii | 2026-02-08 | Przyjeta — uzupelniona przez [ADR-042](#adr-042-silniki-kanalow-unit_package-feature_bbox-atom_files-i-dane-planow-cd) (zapis GPKG przez pyogrio; odczyt obwiedni bez zmian) |
| [ADR-016](#adr-016-bdot10k--usunięcie-filtrowania-po-kategorii-pobieranie-całego-pliku) | BDOT10k — usunięcie filtrowania po kategorii, pobieranie całego pliku | 2026-03-02 | Przyjeta; zastepuje [ADR-014](#adr-014-bdot10k-category-based-extraction-pt-vs-hydro) |
| [ADR-017](#adr-017-pl-2000-sheet-naming--composition-pattern-with-auto-detection) | PL-2000 sheet naming — composition pattern with auto-detection | 2026-02-24 | Przyjeta — uzupelniona przez [ADR-026](#adr-026-uklad-data-per-produkt--segmenty-i-szablony-w-deskryptorach) (wlasne segmenty PL-2000; errata 1) |
| [ADR-018](#adr-018-threadpoolexecutor-dla-rownoleglego-pobierania) | ThreadPoolExecutor dla rownoleglego pobierania | 2026-03-03 | Przyjeta |
| [ADR-019](#adr-019-sqlite-wal-jako-metadata-cache) | SQLite WAL jako metadata cache | 2026-03-03 | Przyjeta — uzupelniona przez [ADR-028](#adr-028-wybor-rekordu-skorowidza-gugik-i-extrasource) (`record_cache` zamiast `url_cache`; errata 1) i [ADR-030](#adr-030-strategie-kampanii-newestall---min-year-i-uklad-kampanie-z-dowiazaniem) (`campaigns_cache`; errata 2) |
| [ADR-020](#adr-020-walidacja-warstw-wms-przez-getcapabilities) | Walidacja warstw WMS przez GetCapabilities | 2026-03-24 | Przyjeta — czesciowo zastapiona przez [ADR-028](#adr-028-wybor-rekordu-skorowidza-gugik-i-extrasource) (warstwy wylacznie z GetCapabilities, bez list zaszytych i fallbacku; errata 3) |
| [ADR-021](#adr-021-laz-chmury-punktów-lidar--discovery-przez-wfs-area-based) | LAZ (chmury punktów LIDAR) — discovery przez WFS, area-based | 2026-06-24 | Przyjeta — czesciowo zastapiona przez [ADR-029](#adr-029-wybor-kafli-laz-wg-pokrycia-obszaru-i-pobieranie-laz-w-bibliotece) (regula newest-per-tile) |
| [ADR-022](#adr-022-architektura-zrodel-wielokrajowych--deskryptory-rejestry-sidecar-twarda-polityka-transformacji-etap-0) | Architektura zrodel wielokrajowych — deskryptory, rejestry, sidecar, twarda polityka transformacji (etap 0) | 2026-08-10 | Przyjeta — uzupelniona przez [ADR-023](#adr-023-silnik-cuzk-polityka-układów-cz-i-evrf20075621-etap-1) (formalny interfejs silnika: `CuzkClient`, (a)) i [ADR-031](#adr-031-jezyk-identyfikatorow--angielski-sidecar-od-070-apicli-do-v100) (angielskie nazwy kluczy sidecara) |
| [ADR-023](#adr-023-silnik-cuzk-polityka-układów-cz-i-evrf20075621-etap-1) | Silnik CUZK, polityka układów CZ i EVRF2007→5621 (etap 1) | 2026-08-11 | Przyjeta — czesciowo zastapiona przez [ADR-024](#adr-024-reprojekcja-tresci-cz-wylacznie-lokalnie-zakaz-imagesr--natywny) (mechanizm pobrania TM33 w (c), Ustalenia dodatkowe pkt 1) i [ADR-027](#adr-027---target-crs-dla-pl--scalony-wycinek-bbox-mozaika--pinned-warp) (`--target-crs` wylacznie dla CZ; Ustalenia dodatkowe pkt 6) i [ADR-038](#adr-038-jawny-tryb-wycinka-i-nazwy-ukladow---cutout---horizontal-crs---sheet-system) (obszar CZ zawsze wycinkiem; teraz `--cutout`); uzupelniona przez [ADR-029](#adr-029-wybor-kafli-laz-wg-pokrycia-obszaru-i-pobieranie-laz-w-bibliotece) ((f).1 obejmuje LAZ) i [ADR-034](#adr-034-wspolny-mechanizm-zapytan-obszarowych-kawalki-na-siatce-zrodla) (kawalkowanie CUZK w `transport/chunks.py`); uzupelnia [ADR-022](#adr-022-architektura-zrodel-wielokrajowych--deskryptory-rejestry-sidecar-twarda-polityka-transformacji-etap-0); errata 2: `--country` wymagane z obszarem, wartosci per kraj (0.8.0) |
| [ADR-024](#adr-024-reprojekcja-tresci-cz-wylacznie-lokalnie-zakaz-imagesr--natywny) | Reprojekcja tresci CZ wylacznie lokalnie (zakaz `imageSR` != natywny) | 2026-08-11 | Przyjeta — uzupelniona przez [ADR-034](#adr-034-wspolny-mechanizm-zapytan-obszarowych-kawalki-na-siatce-zrodla) (wspolne planowanie kawalkow z kotwica NW); zastepuje czesc [ADR-023](#adr-023-silnik-cuzk-polityka-układów-cz-i-evrf20075621-etap-1) (mechanizm pobrania TM33 w (c), Ustalenia dodatkowe pkt 1) |
| [ADR-025](#adr-025-mapowanie-tekstura---hsg-i-kanoniczny-trojkat-usda-audyt-070) | Mapowanie tekstura -> HSG i kanoniczny trojkat USDA (audyt 0.7.0) | 2026-08-22 | Przyjeta |
| [ADR-026](#adr-026-uklad-data-per-produkt--segmenty-i-szablony-w-deskryptorach) | Uklad data/ per produkt — segmenty i szablony w deskryptorach | 2026-08-28 | Przyjeta — uzupelniona przez [ADR-030](#adr-030-strategie-kampanii-newestall---min-year-i-uklad-kampanie-z-dowiazaniem) (pliki w `<segment>/kampanie/`, sciezka standardowa = dowiazanie twarde albo kopia; errata 2) i [ADR-036](#adr-036-magazyn-wersjonowany) (`<segment>/versions/`; errata 3); zastepuje [ADR-013](#adr-013-zmiana-nazw-podkatalogow-storage-z-1m5m-na-nmt_1mnmt_5m) i realizacje ukladu z [ADR-005](#adr-005-struktura-katalogow-nmt-rozdzielona-wg-rozdzielczosci), uzupelnia [ADR-017](#adr-017-pl-2000-sheet-naming--composition-pattern-with-auto-detection) (domyka odroczenie) |
| [ADR-027](#adr-027---target-crs-dla-pl--scalony-wycinek-bbox-mozaika--pinned-warp) | --target-crs dla PL — scalony wycinek bbox (mozaika + pinned warp) | 2026-08-28 | Przyjeta — czesciowo zastapiona przez [ADR-035](#adr-035-wycinki-pl-z-wcs-gugik-z-maska-ladu-prg) (zrodlo wycinka w CLI i `download_pl_cutout`; API arkuszowe usuniete w 0.8.0, errata 2 ADR-035) i [ADR-038](#adr-038-jawny-tryb-wycinka-i-nazwy-ukladow---cutout---horizontal-crs---sheet-system) (nazwa `--target-crs`, wlaczanie wycinka flaga ukladu); uzupelniona przez [ADR-030](#adr-030-strategie-kampanii-newestall---min-year-i-uklad-kampanie-z-dowiazaniem) (tylko przestarzaly tor arkuszowy); zastepuje czesc [ADR-023](#adr-023-silnik-cuzk-polityka-układów-cz-i-evrf20075621-etap-1) (`--target-crs` wylacznie dla CZ) i [ADR-003](#adr-003-opendata-asc-vs-wcs-geotiff--rozdzielenie-sciezek-pobierania-nmt) (bbox = WCS GeoTIFF) |
| [ADR-028](#adr-028-wybor-rekordu-skorowidza-gugik-i-extrasource) | Wybor rekordu skorowidza GUGiK i `extra.source` | 2026-09-30 | Przyjeta — uzupelniona przez [ADR-030](#adr-030-strategie-kampanii-newestall---min-year-i-uklad-kampanie-z-dowiazaniem) (strategie kampanii `newest`/`all`, `--min-year`; regula wyboru `newest` bez zmian; awaria skorowidza: errata 2); czesciowo zastapiona przez [ADR-031](#adr-031-jezyk-identyfikatorow--angielski-sidecar-od-070-apicli-do-v100) (nazwy kluczy `extra.source`); zastepuje czesc [ADR-020](#adr-020-walidacja-warstw-wms-przez-getcapabilities) (zaszyte warstwy i fallback), uzupelnia [ADR-019](#adr-019-sqlite-wal-jako-metadata-cache) (`record_cache`) |
| [ADR-029](#adr-029-wybor-kafli-laz-wg-pokrycia-obszaru-i-pobieranie-laz-w-bibliotece) | Wybor kafli LAZ wg pokrycia obszaru i pobieranie LAZ w bibliotece | 2026-10-07 | Przyjeta — uzupelniona przez [ADR-030](#adr-030-strategie-kampanii-newestall---min-year-i-uklad-kampanie-z-dowiazaniem) (`--campaigns all`/`--min-year` dla LAZ; errata 1) i [ADR-032](#adr-032-wybor-roku-danych-przedzial-lat-zatrzymanie-przy-konflikcie) (przedzial lat i pokrycie referencji; errata 2); zastepuje czesc [ADR-021](#adr-021-laz-chmury-punktów-lidar--discovery-przez-wfs-area-based) (regula newest-per-tile), uzupelnia [ADR-023](#adr-023-silnik-cuzk-polityka-układów-cz-i-evrf20075621-etap-1) ((f).1 obejmuje LAZ) |
| [ADR-030](#adr-030-strategie-kampanii-newestall---min-year-i-uklad-kampanie-z-dowiazaniem) | Strategie kampanii (`newest`/`all`), `--min-year` i uklad `kampanie/` z dowiazaniem | 2026-10-07 | Przyjeta — czesciowo zastapiona przez [ADR-031](#adr-031-jezyk-identyfikatorow--angielski-sidecar-od-070-apicli-do-v100) (nazwy kluczy `extra.campaign`), [ADR-032](#adr-032-wybor-roku-danych-przedzial-lat-zatrzymanie-przy-konflikcie) (przedzial, skan i konflikt; errata 7) i [ADR-036](#adr-036-magazyn-wersjonowany) (uklad `kampanie/`, automatyczne `newest`, kopia zamiast hardlinku; errata 9); uzupelniona przez [ADR-033](#adr-033-drugie-dowiazanie-do-najnowszego-pelnego-lotu-full_sheet---full-sheet) (drugie dowiazanie `full_sheet/`; errata 8); uzupelnia [ADR-026](#adr-026-uklad-data-per-produkt--segmenty-i-szablony-w-deskryptorach) (`kampanie/`), [ADR-027](#adr-027---target-crs-dla-pl--scalony-wycinek-bbox-mozaika--pinned-warp) (wycinek tylko `newest`), [ADR-028](#adr-028-wybor-rekordu-skorowidza-gugik-i-extrasource) (strategie), [ADR-029](#adr-029-wybor-kafli-laz-wg-pokrycia-obszaru-i-pobieranie-laz-w-bibliotece) (LAZ: `all`, `--min-year`) i [ADR-019](#adr-019-sqlite-wal-jako-metadata-cache) (`campaigns_cache`); errata 10: otwarte drobiazgi przegladu zamkniete (M-8: sidecar dowiazania usuwany po awarii zapisu) |
| [ADR-031](#adr-031-jezyk-identyfikatorow--angielski-sidecar-od-070-apicli-do-v100) | Jezyk identyfikatorow — angielski (sidecar od 0.7.0, API/CLI do v1.0.0) | 2026-10-08 | Przyjeta — uzupelniona przez [ADR-037](#adr-037-spojnosc-cli-i-api) (jezyk tekstow dla uzytkownika, Z5); czesciowo zastepuje [ADR-028](#adr-028-wybor-rekordu-skorowidza-gugik-i-extrasource) (nazwy kluczy `extra.source`) i [ADR-030](#adr-030-strategie-kampanii-newestall---min-year-i-uklad-kampanie-z-dowiazaniem) (nazwy kluczy `extra.campaign`); uzupelnia [ADR-022](#adr-022-architektura-zrodel-wielokrajowych--deskryptory-rejestry-sidecar-twarda-polityka-transformacji-etap-0) (konwencja nazw kluczy sidecara `kartograf-meta/1`); errata 1: API/CLI po angielsku w 0.8.0 bez aliasow (pkt 2-3 nieaktualne) |
| [ADR-032](#adr-032-wybor-roku-danych-przedzial-lat-zatrzymanie-przy-konflikcie) | Wybor roku danych: przedzial lat, zatrzymanie przy konflikcie | 2026-10-10 | Przyjeta — uzupelniona przez [ADR-033](#adr-033-drugie-dowiazanie-do-najnowszego-pelnego-lotu-full_sheet---full-sheet) (`--full-sheet` z pkt 4; errata 1); czesciowo zastapiona przez [ADR-036](#adr-036-magazyn-wersjonowany) (pkt 2: D14, pkt 4: D13; errata 3); errata 2: `--all-campaigns`/`all_campaigns` od 0.8.0; uzupelnia [ADR-029](#adr-029-wybor-kafli-laz-wg-pokrycia-obszaru-i-pobieranie-laz-w-bibliotece) (LAZ) i [ADR-030](#adr-030-strategie-kampanii-newestall---min-year-i-uklad-kampanie-z-dowiazaniem) (kampanie PL) |
| [ADR-033](#adr-033-drugie-dowiazanie-do-najnowszego-pelnego-lotu-full_sheet---full-sheet) | Drugie dowiazanie do najnowszego pelnego lotu (`full_sheet/`, `--full-sheet`) | 2026-10-10 | Przyjeta — czesciowo zastapiona przez [ADR-036](#adr-036-magazyn-wersjonowany) (F-U5: `kampanie/`; errata 1); uzupelnia [ADR-030](#adr-030-strategie-kampanii-newestall---min-year-i-uklad-kampanie-z-dowiazaniem) ((d): drugie dowiazanie; errata 8) i [ADR-032](#adr-032-wybor-roku-danych-przedzial-lat-zatrzymanie-przy-konflikcie) (pkt 4: `--full-sheet`; errata 1) |
| [ADR-034](#adr-034-wspolny-mechanizm-zapytan-obszarowych-kawalki-na-siatce-zrodla) | Wspolny mechanizm zapytan obszarowych (kawalki na siatce zrodla) | 2026-10-10 | Przyjeta — uzupelniona przez [ADR-035](#adr-035-wycinki-pl-z-wcs-gugik-z-maska-ladu-prg) (ASC 1 Mpx i NMPT) i [ADR-042](#adr-042-silniki-kanalow-unit_package-feature_bbox-atom_files-i-dane-planow-cd) (kawalki wycinka ortofotomapy; errata 1: zszycie bit w bit tylko dla NMT); uzupelnia [ADR-023](#adr-023-silnik-cuzk-polityka-układów-cz-i-evrf20075621-etap-1) (kawalkowanie CUZK) i [ADR-024](#adr-024-reprojekcja-tresci-cz-wylacznie-lokalnie-zakaz-imagesr--natywny) (kotwica NW) |
| [ADR-035](#adr-035-wycinki-pl-z-wcs-gugik-z-maska-ladu-prg) | Wycinki PL z WCS GUGiK z maska ladu PRG | 2026-10-11 | Przyjeta; czesciowo zastepuje [ADR-027](#adr-027---target-crs-dla-pl--scalony-wycinek-bbox-mozaika--pinned-warp) (zrodlo wycinka w CLI i `download_pl_cutout`), uzupelnia [ADR-034](#adr-034-wspolny-mechanizm-zapytan-obszarowych-kawalki-na-siatce-zrodla) (ASC 1 Mpx i NMPT); errata 1: kawalek ASC NMPT 4 Mpx coverage; errata 2: tor arkuszowy usuniety w 0.8.0; errata 3: W-U3/W-U8 zastapione przez [ADR-036](#adr-036-magazyn-wersjonowany) (D15, plan 2/3) |
| [ADR-036](#adr-036-magazyn-wersjonowany) | Magazyn wersjonowany | 2026-10-12 | Przyjeta — czesciowo zastapiona przez [ADR-042](#adr-042-silniki-kanalow-unit_package-feature_bbox-atom_files-i-dane-planow-cd) (D27: wycinek ortofotomapy w magazynie; errata 2); uzupelniona przez [ADR-037](#adr-037-spojnosc-cli-i-api) (arkusz CZ w publicznym API; errata 1) i [ADR-042](#adr-042-silniki-kanalow-unit_package-feature_bbox-atom_files-i-dane-planow-cd) (D23 miedzy wydaniami, sloty jednostek); czesciowo zastepuje [ADR-030](#adr-030-strategie-kampanii-newestall---min-year-i-uklad-kampanie-z-dowiazaniem) (`kampanie/`, automatyczne `newest`, kopia), [ADR-032](#adr-032-wybor-roku-danych-przedzial-lat-zatrzymanie-przy-konflikcie) (pkt 2 i 4), [ADR-033](#adr-033-drugie-dowiazanie-do-najnowszego-pelnego-lotu-full_sheet---full-sheet) (F-U5), [ADR-035](#adr-035-wycinki-pl-z-wcs-gugik-z-maska-ladu-prg) (W-U3/W-U8) i [ADR-003](#adr-003-opendata-asc-vs-wcs-geotiff--rozdzielenie-sciezek-pobierania-nmt) (`DownloadManager.download_bbox`); uzupelnia [ADR-026](#adr-026-uklad-data-per-produkt--segmenty-i-szablony-w-deskryptorach) (`versions/`; land cover i HSG w ukladzie `data/`) |
| [ADR-037](#adr-037-spojnosc-cli-i-api) | Spojnosc CLI i API | 2026-10-12 | Przyjeta — uzupelniona przez [ADR-038](#adr-038-jawny-tryb-wycinka-i-nazwy-ukladow---cutout---horizontal-crs---sheet-system) (nazwy flag i parametrow ukladow); uzupelnia [ADR-036](#adr-036-magazyn-wersjonowany) (arkusz CZ w publicznym API; errata 1 ADR-036) i [ADR-031](#adr-031-jezyk-identyfikatorow--angielski-sidecar-od-070-apicli-do-v100) (jezyk tekstow dla uzytkownika) |
| [ADR-038](#adr-038-jawny-tryb-wycinka-i-nazwy-ukladow---cutout---horizontal-crs---sheet-system) | Jawny tryb wycinka i nazwy ukladow (--cutout, --horizontal-crs, --sheet-system) | 2026-10-13 | Przyjeta; czesciowo zastepuje [ADR-027](#adr-027---target-crs-dla-pl--scalony-wycinek-bbox-mozaika--pinned-warp) (wlaczanie wycinka PL flaga ukladu, nazwa `--target-crs`) i [ADR-023](#adr-023-silnik-cuzk-polityka-układów-cz-i-evrf20075621-etap-1) (obszar CZ zawsze wycinkiem); uzupelnia [ADR-037](#adr-037-spojnosc-cli-i-api) (nazwy CLI = API) |
| [ADR-039](#adr-039-grupy-komend-cli-wg-typu-danych) | Grupy komend CLI wg typu danych | 2026-10-15 | Przyjeta — uzupelniona przez [ADR-040](#adr-040-manifest-projektu-i-przypiete-wersje) (komenda danych ustawia `_task` dla `project add`), [ADR-042](#adr-042-silniki-kanalow-unit_package-feature_bbox-atom_files-i-dane-planow-cd) (grupy `boundaries`, `cadastre`, `models3d`, `hydro`) i [ADR-043](#adr-043-plan-e-produkty-jednostkowe-arkuszowe-i-krajowe-na-silnikach-cd) (grupy `names`, `maps`, `geodesy`); uzupelnia [ADR-037](#adr-037-spojnosc-cli-i-api) (CLI tylko tlumaczy; jedna komenda = jedna funkcja biblioteki) i [ADR-038](#adr-038-jawny-tryb-wycinka-i-nazwy-ukladow---cutout---horizontal-crs---sheet-system) (nazwy flag); bez aliasow usunietych komend (zasada jak errata [ADR-031](#adr-031-jezyk-identyfikatorow--angielski-sidecar-od-070-apicli-do-v100)) |
| [ADR-040](#adr-040-manifest-projektu-i-przypiete-wersje) | Manifest projektu i przypiete wersje | 2026-10-15 | Przyjeta — uzupelniona przez [ADR-042](#adr-042-silniki-kanalow-unit_package-feature_bbox-atom_files-i-dane-planow-cd) (pozycje komend kolekcji); uzupelnia [ADR-039](#adr-039-grupy-komend-cli-wg-typu-danych) (komenda danych ustawia `_task` dla `project add`) |
| [ADR-041](#adr-041-rejestr-wariantow-produktu-skorowidz-wfs-nmtnmpt-i-raport-dostepnosci) | Rejestr wariantow produktu, skorowidz WFS NMT/NMPT i raport dostepnosci | 2026-10-15 | Przyjeta — uzupelniona przez [ADR-043](#adr-043-plan-e-produkty-jednostkowe-arkuszowe-i-krajowe-na-silnikach-cd) (NMT 100 m w rejestrze wariantow bez ukladu wysokosci) |
| [ADR-042](#adr-042-silniki-kanalow-unit_package-feature_bbox-atom_files-i-dane-planow-cd) | Silniki kanalow (unit_package, feature_bbox, atom_files) i dane planow C/D | 2026-10-15 | Przyjeta — czesciowo zastapiona przez [ADR-043](#adr-043-plan-e-produkty-jednostkowe-arkuszowe-i-krajowe-na-silnikach-cd) (D1: capability kanalu kolekcji unikalna w deskryptorze); uzupelniona przez [ADR-043](#adr-043-plan-e-produkty-jednostkowe-arkuszowe-i-krajowe-na-silnikach-cd) (jednostki arkuszy, kafli i KU, rekord indeksu i sygnal `index`, OGC API Features, wybor kanalu po wartosciach opcji); czesciowo zastepuje [ADR-036](#adr-036-magazyn-wersjonowany) (D27: wycinek ortofotomapy w magazynie; errata 2 ADR-036); uzupelnia [ADR-015](#adr-015-pyshp--sqlite3-zamiast-fiona-dla-czytania-geometrii) (zapis GPKG przez pyogrio), [ADR-034](#adr-034-wspolny-mechanizm-zapytan-obszarowych-kawalki-na-siatce-zrodla) (kawalki wycinka ortofotomapy; errata 1 ADR-034), [ADR-036](#adr-036-magazyn-wersjonowany) (D23 miedzy wydaniami, sloty jednostek), [ADR-039](#adr-039-grupy-komend-cli-wg-typu-danych) (grupy `boundaries`, `cadastre`, `models3d`, `hydro`) i [ADR-040](#adr-040-manifest-projektu-i-przypiete-wersje) (pozycje komend projektu); errata 1-5: D5 i D12-D17 wg kodu planu D (indeks ATOM, HY-NET obszaru 2 warstwy, ZABAGED i RUIAN, ortofoto CZ, wycinek orto) |
| [ADR-043](#adr-043-plan-e-produkty-jednostkowe-arkuszowe-i-krajowe-na-silnikach-cd) | Plan E: produkty jednostkowe, arkuszowe i krajowe na silnikach C/D | 2026-10-16 | Przyjeta; czesciowo zastepuje [ADR-042](#adr-042-silniki-kanalow-unit_package-feature_bbox-atom_files-i-dane-planow-cd) (D1: capability kanalu kolekcji unikalna w deskryptorze); uzupelnia [ADR-042](#adr-042-silniki-kanalow-unit_package-feature_bbox-atom_files-i-dane-planow-cd) (jednostki arkuszy, kafli i KU, tematy plikow krajowych, rekord indeksu i sygnal `index`, OGC API Features, wybor kanalu po wartosciach opcji, `DOWNLOAD_SIZE`), [ADR-039](#adr-039-grupy-komend-cli-wg-typu-danych) (grupy `names`, `maps`, `geodesy`) i [ADR-041](#adr-041-rejestr-wariantow-produktu-skorowidz-wfs-nmtnmpt-i-raport-dostepnosci) (NMT 100 m w rejestrze wariantow bez ukladu wysokosci) |

---

## ADR-001: Flat layout zamiast src layout

**Data:** 2026-01-17
**Status:** Przyjeta

**Kontekst:** Przy starcie projektu trzeba bylo wybrac strukture katalogow. Standardowe opcje to `src/kartograf/` (src layout) albo `kartograf/` (flat layout).

**Opcje:**
- A) `src/` layout — wymusza `pip install -e .` do uruchomienia testow, zapobiega przypadkowemu importowi z CWD
- B) Flat layout — prostszy, mniej konfiguracji, wystarczajacy dla projektow tej skali

**Decyzja:** Flat layout (`kartograf/` w korzeniu). Projekt jest sredniej wielkosci, uzywany w zamknietym ekosystemie (Hydrograf/Hydrolog), nie wymaga izolacji src/.

**Konsekwencje:** Prostsze importy, brak dodatkowej warstwy katalogow. Potencjalny problem z CWD imports — akceptowalny przy pracy z venv.

---

## ADR-002: Auth Proxy do izolacji credentials CLMS

**Data:** 2026-01-18
**Status:** Przyjeta

**Kontekst:** CORINE Land Cover z Copernicus CLMS wymaga OAuth2 RSA (client_id + klucz prywatny). Credentials nie powinny byc widoczne w glownym procesie aplikacji.

**Opcje:**
- A) Bezposredni OAuth2 w CorineProvider — prostsze, ale credentials w pamieci glownego procesu
- B) Auth Proxy — osobny proces HTTP na localhost, credentials izolowane
- C) Zewnetrzny secret manager — overengineering dla tego projektu

**Decyzja:** Auth Proxy (opcja B). Osobny proces (`kartograf/auth/proxy.py`) uruchamiany jako subprocess. Glowna aplikacja komunikuje sie z proxy przez localhost HTTP. Credentials pobierane z macOS Keychain.

**Konsekwencje:** Bezpieczniejsze — credentials nie opuszczaja procesu proxy. Bardziej zlozony kod (2 moduly: proxy.py, client.py). Fallback na WMS (PNG) gdy brak credentials.

---

## ADR-003: OpenData (ASC) vs WCS (GeoTIFF) — rozdzielenie sciezek pobierania NMT

**Data:** 2026-01-18
**Status:** Przyjeta — czesciowo zastapiona przez ADR-027 (bbox = WCS GeoTIFF; errata 1) i ADR-036 (`DownloadManager.download_bbox` usuniete; errata 2)

**Kontekst:** GUGiK oferuje dwa sposoby pobierania NMT: OpenData (pliki ASC po godle) i WCS (GeoTIFF po bbox). Poczatkowo probowano ujednolicic oba w jednym flow.

**Opcje:**
- A) Jeden interfejs z parametrem `method` — ujednolicone API, ale skomplikowana logika wewnetrzna
- B) Rozdzielenie na `download_sheet(godlo)` → ASC i `download_bbox(bbox)` → GeoTIFF

**Decyzja:** Rozdzielenie (opcja B). Godlo zawsze daje ASC przez OpenData, bbox zawsze daje GeoTIFF przez WCS. Roznne formaty, rozne API, rozne ograniczenia — nie ma sensu ich laczyc.

**Konsekwencje:** Czytelniejszy kod. Uzytkownik jawnie wybiera metode. NMT 5m dziala tylko przez OpenData (WCS niedostepne).

**Errata 1 (2026-09-29, audyt dokumentacji):** czesc "bbox zawsze daje GeoTIFF
przez WCS" juz nie obowiazuje: CLI rozwija bbox PL na arkusze OpenData,
a jeden GeoTIFF dla bboxa/geometrii buduje z arkuszy wycinek `--target-crs` /
`download_pl_cutout` (ADR-027). WCS zostal tylko w
`DownloadManager.download_bbox` / `GugikProvider.download_bbox` i tylko dla
KRON86 — endpoint EVRF2007 GUGiK wycofal (HTTP 404 od 2026-08), a
`download_bbox` z EVRF2007 konczy sie `ValidationError` przed siecia.

**Errata 2 (2026-10-12, ADR-036 D27, 0.8.0):** `DownloadManager.download_bbox`
usuniete — pisal plik w korzeniu magazynu, zawsze nadpisywal i dublowal
`download_pl_cutout(EPSG:2180)` bez maski PRG. Wycinek NMT/NMPT w magazynie:
`download_pl_cutout`; surowy WCS (np. ortofotomapa) poza magazynem:
`provider.download_bbox(bbox, path)` (metody providerow zostaja).

---

## ADR-004: EVRF2007 jako domyslny uklad wysokosciowy

**Data:** 2026-01-21
**Status:** Zastapiona w 0.8.0 — errata 1 (uklad wysokosci wymagany, bez wartosci domyslnej)

**Kontekst:** GUGiK oferuje NMT w dwoch ukladach: KRON86 (Kronsztadt, historyczny) i EVRF2007 (European Vertical Reference Frame, aktualny standard). Wczesniej domyslny byl KRON86.

**Opcje:**
- A) Zostawic KRON86 jako domyslny — kompatybilnosc wsteczna
- B) Zmienic na EVRF2007 — aktualny standard, wymagany przez NMT 5m

**Decyzja:** EVRF2007 jako domyslny (opcja B). Jest to aktualny standard geodezyjny w Polsce. KRON86 dostepny jako `--vertical-crs KRON86`.

**Konsekwencje:** Breaking change w v0.3.2. Uzytkownicy uzywajacy KRON86 musza jawnie podac flage. NMT 5m dziala out-of-the-box.

**Errata 1 (2026-10-12, 0.8.0, decyzja uzytkownika):** wartosci domyslnej
ukladu wysokosci nie ma. CLI `--vertical-crs` jest wymagane dla NMT, NMPT
i LAZ (PL: EVRF2007 albo KRON86; NMT 5 m tylko EVRF2007; CZ: Bpv albo
EVRF2007), a w API `vertical_crs` jest wymagane w providerach GUGiK/CUZK,
fabrykach, `FileStorage`, wycinku PL i LAZ. Powod: regula "bez wartosci
domyslnych wplywajacych na dane" (DEVELOPMENT_STANDARDS 11.2) — uklad
wysokosci wybiera dane, wiec wybiera go wolajacy. EVRF2007 pozostaje
ukladem zalecanym (aktualny standard, jedyny dla NMT 5 m).

---

## ADR-005: Struktura katalogow NMT rozdzielona wg rozdzielczosci

**Data:** 2026-01-21
**Status:** Przyjeta — czesciowo zastapiona przez ADR-013, a nastepnie ADR-026 (realizacja ukladu katalogow; errata 1)

**Kontekst:** Po dodaniu obslugi NMT 5m, pliki 1m i 5m dla tego samego godla mialy te sama sciezke. Grozi nadpisaniem.

**Opcje:**
- A) Suffix w nazwie pliku (`N-34-130-D-d-2-4_5m.asc`) — proste, ale niespojne z konwencja GUGiK
- B) Podkatalog rozdzielczosci (`data/1m/...`, `data/5m/...`) — czyste rozdzielenie

**Decyzja:** Podkatalog rozdzielczosci (opcja B). Struktura: `data/1m/N-34/130/.../plik.asc` i `data/5m/N-34/130/.../plik.asc`.

**Konsekwencje:** Breaking change — stare sciezki bez `1m/`/`5m/` nie sa kompatybilne. Czyste rozdzielenie, latwe do zrozumienia. FileStorage przyjmuje parametr `resolution`.

**Errata 1 (2026-08-28, ADR-026):** decyzja "rozdzielczosc jest wymiarem sciezki"
obowiazuje nadal, ale jej realizacja zmieniala sie dwa razy: `1m`/`5m` ->
`nmt_1m`/`nmt_5m` (ADR-013) -> segmenty `nmt/pl_<uklad>_<res>_<vcrs>`
(ADR-026). Parametr `resolution` w `FileStorage` zostal, tyle ze mapuje
dzis na SZABLON segmentu, nie na nazwe katalogu.

---

## ADR-006: LandCoverProvider jako osobna hierarchia od BaseProvider

**Data:** 2026-01-18
**Status:** Przyjeta

**Kontekst:** Dodajac BDOT10k i CORINE, trzeba bylo zdecydowac jak zorganizowac providery. BaseProvider (NMT) i nowe providery (Land Cover) maja rozne interfejsy — NMT pobiera po godle/bbox, Land Cover dodatkowo po TERYT.

**Opcje:**
- A) Rozszerzyc BaseProvider o metody Land Cover — jeden hierarchy, ale NMT nie potrzebuje TERYT
- B) Osobna klasa bazowa LandCoverProvider — czyste rozdzielenie odpowiedzialnosci

**Decyzja:** Osobna hierarchia (opcja B). `BaseProvider` dla NMT, `LandCoverProvider` dla pokrycia terenu. Wspolny interfejs: `download_by_godlo()`, `download_by_bbox()`. Dodatkowy w LC: `download_by_teryt()`.

**Konsekwencje:** Dwie hierarchie providerow. Mozliwa unifikacja w przyszlosci (v0.4+). LandCoverManager dispatuje do odpowiedniego providera.

---

## ADR-007: Migracja z black + flake8 na ruff

**Data:** 2026-02-03
**Status:** Przyjeta

**Kontekst:** Workspace ma zunifikowane standardy (`shared/standards/DEVELOPMENT_STANDARDS.md`) ktore wymagaja ruff. Kartograf uzywal black (formatter) + flake8 (linter) — dwa osobne narzedzia, osobne pliki konfiguracyjne.

**Opcje:**
- A) Zostawic black + flake8 — dziala, ale niezgodne ze standardem workspace
- B) Migrowac na ruff — jedno narzedzie (linter + formatter), konfiguracja w pyproject.toml

**Decyzja:** Migracja na ruff (opcja B). Usunieto `[tool.black]` z pyproject.toml i `.flake8`. Dodano `[tool.ruff]` z regulami `E, F, I, UP, B, SIM`.

**Konsekwencje:** Jedno narzedzie zamiast dwoch. Ruff wykryl 73 problemy w istniejacym kodzie (importy, legacy typing), 63 naprawione automatycznie przez `ruff check --fix`. Pozostalo ~10 bledow B904 (`raise ... from err`).

---

## ADR-008: Kondensacja PROGRESS.md z 785 do ~80 linii

**Data:** 2026-02-03
**Status:** Przyjeta

**Kontekst:** PROGRESS.md narastal kumulatywnie przez 21 etapow. Wiekszosc tresci byla nieaktualna (np. "nastepne kroki" z etapu 5). Plik nie pelnil roli "gdzie jestem teraz".

**Opcje:**
- A) Zostawic — pelna historia, ale trudna do nawigacji
- B) Skondensowac do 4 sekcji (status, checkpointy, ostatnia sesja, backlog) — czytelne "tu i teraz"
- C) Jak B, ale dodac osobny DECISIONS.md dla decyzji — oddzielenie "co teraz" od "dlaczego"

**Decyzja:** Opcja C. PROGRESS.md = biezacy stan. DECISIONS.md = uzasadnienia decyzji. Historia 21 etapow pozostaje w git history. CHANGELOG.md pokrywa zmiany per-release.

**Konsekwencje:** Agent AI czyta PROGRESS.md i od razu wie co robic. Decyzje architektoniczne sa w DECISIONS.md. Szczegoly historyczne dostepne przez `git log` i `git show`.

---

## ADR-009: Rozbudowanie DEVELOPMENT_STANDARDS i IMPLEMENTATION_PROMPT

**Data:** 2026-02-03
**Status:** Przyjeta

**Kontekst:** Przy standaryzacji dokumentacji poczatkowo zdeprecjonowano oba pliki (zastapione krotkimi notatkami). Jednak pelna tresc jest potrzebna — agent AI i deweloperzy potrzebuja szczegolowych instrukcji w kontekscie projektu, a nie tylko odwolan do shared/standards.

**Opcje:**
- A) Krotkie notatki z odwolaniem do shared/standards — minimalne, ale wymaga czytania dwoch zrodel
- B) Rozbudowane wersje wzorowane na shared/standards, ale z przykladami Kartograf — samodzielne dokumenty

**Decyzja:** Opcja B. DEVELOPMENT_STANDARDS.md (722 linii, 15 sekcji) i IMPLEMENTATION_PROMPT.md (284 linii, 11 sekcji) przepisane na nowo z aktualna trescia (v0.3.2, ruff, wszystkie moduly).

**Konsekwencje:** Dokumenty sa samodzielne — nie wymagaja czytania shared/standards. Koszt: trzeba pamietac o aktualizacji obu zrodel gdy standard sie zmieni.

**Errata 1 (2026-10-08, przeglad dokumentacji):** `IMPLEMENTATION_PROMPT.md`
zostal usuniety; jego unikalna tresc (workflow, "Czego NIE robic", typowe
zadania) przeszla do `docs/DEVELOPMENT_STANDARDS.md` (sekcje 15-17).
`DEVELOPMENT_STANDARDS.md` jest odtad glownym zrodlem konwencji i procesu
pracy projektu; `CLAUDE.md` zminimalizowano do krytycznych zasad i
odsylaczy (bez drzewa modulow, przykladow CLI i ograniczen), `README.md`
jest wprowadzeniem do projektu, a szczegoly uzytkowe (przyklady CLI
i biblioteki, wynik pobrania, kampanie, CLMS) leza w `docs/USAGE.md`.
Zasada samodzielnosci DEVELOPMENT_STANDARDS z decyzji obowiazuje dalej;
czesc dotyczaca `IMPLEMENTATION_PROMPT.md` jest nieaktualna.

---

## ADR-010: Algorytm find_sheets_for_bbox — hierarchiczne przycinanie bez WFS

**Data:** 2026-02-07
**Status:** Przyjeta

**Kontekst:** Potrzeba reverse lookup: podaj bbox, otrzymaj liste godel arkuszy. GUGiK nie oferuje WFS do wyszukiwania arkuszy po bbox. Siatka map topograficznych jest czysto matematyczna.

**Opcje:**
- A) WFS query do GUGiK — wymaga sieciowego zapytania, serwis moze byc niedostepny
- B) Brute-force: wygeneruj wszystkie godla, oblicz bbox kazdego, sprawdz przeciecie — O(n) gdzie n = WSZYSTKIE arkusze
- C) Hierarchiczne przycinanie: oblicz matematycznie 1:1M i 1:200k, potem rekurencyjnie drąż z pruningiem — O(n) gdzie n = ZNALEZIONE arkusze

**Decyzja:** Opcja C. Algorytm: (1) floor division dla 1:1M (pas/slup), (2) siatka 12x12 dla 1:200k z clamped row/col, (3) rekurencyjne get_children() + _bboxes_intersect() do docelowej skali. Bez zadnego zapytania sieciowego.

**Konsekwencje:** Dziala offline. Szybkie (~1s dla 1:10k). Zalezy od poprawnosci _calculate_wgs84_bbox() — jesli zmieni sie logika bbox, find_sheets_for_bbox tez sie zmieni. CLI download godlo staje sie opcjonalne (nargs="?").

**Errata 1 (2026-09-29, audyt dokumentacji; stan kodu po audycie 0.7.0
i fali review max 2026-09-28):** (a) od audytu 0.7.0 (A1-7) liczy sie
dodatnie pole przeciecia — stykajace sie krawedzie nie sa przecieciem;
(b) bbox w EPSG:2180 jest zamieniany na obwiednie WGS84 z 4 naroznikow i 2
punktow na poludniku osiowym 19°E (tam lezy maksimum szerokosci gornej
krawedzi — fakt 8 fali review max); obwiednia jest szersza niz bbox, wiec
selekcja obejmuje arkusze sasiednie (obwiednia EPSG:2180 arkusza
`N-34-130-D-d-2-4` daje 9 godel, `N-34-130-D` w skali 1:50000 — 16 zamiast
4; w duzym wycinku do ~3,7 km poza zadaniem); (c) `--system 2000` liczy
obwiednie z 4 naroznikow (`core/parser_2000`, backlog).

**Errata 2 (2026-10-07, parsery — `core/bbox.py`):** obwiednie z errata 1
(b) i (c) liczy teraz jedna funkcja `core/bbox.py::transform_bbox`
(`transform_bounds` z `densify_pts=21` na krawedz) — w `find_sheets_for_bbox`
i `find_sheets_2000_for_bbox`; punkt (c) z backlogu jest domkniety. Regula
dodatniego pola z (a) i szersza obwiednia bboxa EPSG:2180 bez zmian.

---

## ADR-011: GugikNmptProvider dziedziczy z GugikProvider

**Data:** 2026-02-07
**Status:** Przyjeta

**Kontekst:** NMPT (Numeryczny Model Pokrycia Terenu / Digital Surface Model) uzywa tych samych mechanizmow co NMT: WMS skorowidze → OpenData ASC, WCS → GeoTIFF. Rozni sie tylko endpointami, nazwami warstw, coverage IDs i brakiem 5m.

**Opcje:**
- A) Osobna klasa (kopiuj logike z GugikProvider) — duplikacja ~200 linii kodu
- B) Dziedziczenie z GugikProvider — nadpisanie tylko stalych klasowych i __init__

**Decyzja:** Dziedziczenie (opcja B). `GugikNmptProvider(GugikProvider)` nadpisuje `WCS_ENDPOINTS`, `WMS_SKOROWIDZE_ENDPOINTS`, `WMS_LAYERS`, `COVERAGE_IDS`, `SUPPORTED_RESOLUTIONS` i `name`. Zero duplikacji logiki pobierania.

**Konsekwencje:** ~100 linii zamiast ~300. Kazda zmiana w GugikProvider automatycznie propaguje do NMPT. Ryzyko: zmiana w GugikProvider moze zepsuc NMPT — mitygowane przez testy.

---

## ADR-012: GugikOrtoProvider jako osobna klasa (nie dziedziczy z GugikProvider)

**Data:** 2026-02-07
**Status:** Przyjeta

**Kontekst:** Ortofotomapa rozni sie od NMT/NMPT na wiele sposobow: brak vertical CRS, inny format (TIF nie ASC), jeden WMS endpoint (nie rozdzielony na KRON86/EVRF2007), inna struktura warstw (lista zamiast dict-of-dicts).

**Opcje:**
- A) Dziedziczenie z GugikProvider — wymaga hackowania vertical_crs=None, resolution=None, nadpisywania wielu metod
- B) Osobna klasa `GugikOrtoProvider(BaseProvider)` — wlasna implementacja, ~250 linii

**Decyzja:** Osobna klasa (opcja B). Roznice sa zbyt duze zeby dziedziczenie bylo czyste. Duplikacja ~50 linii (_download_with_retry, _make_request, _save_response) jest akceptowalna.

**Konsekwencje:** Czytelny kod bez hackow. Ewentualne wyekstrahowanie wspolnych metod do mixin/helper w przyszlosci. Niezalezna ewolucja od NMT/NMPT.

---

## ADR-013: Zmiana nazw podkatalogow storage z 1m/5m na nmt_1m/nmt_5m

**Data:** 2026-02-07
**Status:** Zastapiona przez ADR-026; czesciowo zastepuje ADR-005 (nazwy katalogow)

**Kontekst:** Po dodaniu NMPT i Ortofoto, podkatalogi `1m` i `5m` w FileStorage staly sie niejednoznaczne — moglyby oznaczac rozdzielczosc dowolnego produktu. Nowe produkty uzywaja podkatalogow `nmpt` i `orto`.

**Opcje:**
- A) Zostawic `1m`/`5m` — proste, ale niespojne z `nmpt`/`orto`
- B) Zmienic na `nmt_1m`/`nmt_5m` — jednoznaczne, spojne z konwencja product/

**Decyzja:** Opcja B. Struktura: `data/nmt_1m/...`, `data/nmt_5m/...`, `data/nmpt/...`, `data/orto/...`. FileStorage uzywa `_RESOLUTION_SUBDIRS` mapping do tlumaczenia rozdzielczosci na nazwe podkatalogu.

**Konsekwencje:** Breaking change — stare sciezki `data/1m/` i `data/5m/` nie sa kompatybilne. Jednoznaczna struktura. Parametr `product` w FileStorage pozwala na latwe dodawanie nowych produktow.

**Errata 1 (2026-08-28, ADR-026):** uklad `nmt_1m`/`nmt_5m` zastapiony segmentami
`nmt/pl_<uklad>_<res>_<vcrs>` — patrz ADR-026.

---

## ADR-014: BDOT10k category-based extraction (pt vs hydro)

**Data:** 2026-02-08
**Status:** Zastapiona przez ADR-016

**Kontekst:** BDOT10k ZIP z GUGiK zawiera ~60 plikow GPKG na powiat, w tym warstwy pokrycia terenu (PT*) i hydrografii (SW*). Dotychczas ekstrakcja filtrowala tylko `_PT` w nazwie pliku. Potrzeba pobierania danych hydrograficznych (rzeki, kanaly, rowy) bez zmiany istniejacego API.

**Opcje:**
- A) Osobny provider `Bdot10kHydroProvider` — duplikacja logiki pobierania, nowy dispatch w LandCoverManager
- B) Parametr `category` w istniejacym Bdot10kProvider — `CATEGORY_FILTERS` mapuje nazwe kategorii na wzorce filtrowania plikow w ZIP
- C) Parametr `layers` z lista warstw — elastyczne, ale wymaga od uzytkownika znajomosci kodow warstw

**Decyzja:** Opcja B. Dodano `CATEGORY_FILTERS = {"pt": ["_PT"], "hydro": ["_SW", "_PTWP"]}`. Parametr `category` (domyslnie `"pt"`) jest przekazywany przez `download_by_teryt()` → `_download_with_retry()` → `_extract_gpkg_from_zip()`. Backward compatible — domyslne zachowanie sie nie zmienia.

**Konsekwencje:** Zero duplikacji kodu. Latwe dodanie nowych kategorii w przyszlosci (np. `"transport"` dla DR* warstw). PTWP jest wspolne dla obu kategorii (pokrycie terenu i hydrografia). CLI: `--category {pt,hydro}` — proste i odkrywalne.

---

## ADR-015: pyshp + sqlite3 zamiast fiona dla czytania geometrii

**Data:** 2026-02-08
**Status:** Przyjeta — uzupelniona przez ADR-042 (zapis GPKG przez pyogrio; odczyt obwiedni bez zmian)

**Kontekst:** Uzytkownik potrzebuje pobierania danych dla obszarow zdefiniowanych plikami SHP/GPKG. Do odczytu geometrii potrzebna jest biblioteka.

**Opcje:**
- A) fiona (OGR bindings) — pelne wsparcie formatow, ale ~150MB surface area, wspoldzieli GDAL z rasterio ale dodaje Python wrapper
- B) pyshp + sqlite3 — pyshp (~100KB, pure Python) dla SHP, sqlite3 (stdlib) + struct.unpack dla GPKG envelope parsing. Zero C dependencies.
- C) geopandas — najwygodniejsze API, ale ogromne zależnosci (pandas, fiona/pyogrio, shapely)

**Decyzja:** Opcja B. Do ekstrakcji per-feature bounding boxow nie potrzeba pelnego OGR. pyshp czyta `.shp` natywnie (shape.bbox). GPKG to SQLite — envelope jest w binarnym naglowku geometrii (GeoPackage Binary: magic + flags + SRS + 4×float64). CRS z `.prj` (WKT) i `gpkg_spatial_ref_sys` (WKT). Transformacja przez pyproj (juz w zaleznosci).

**Konsekwencje:** Minimalne zaleznosci (+1 pakiet ~100KB). Brak wsparcia dla formatow innych niz SHP/GPKG — akceptowalne, bo to jedyne formaty uzywane w polskim GIS workflow. Envelope parsing jest kruchy (zalezy od specyfikacji GeoPackage Binary) ale stabilny i dobrze udokumentowany.

---

## ADR-016: BDOT10k — usunięcie filtrowania po kategorii, pobieranie całego pliku

**Data:** 2026-03-02
**Status:** Przyjeta; zastepuje ADR-014

**Kontekst:** Filtrowanie po kategorii (pt/hydro) w Bdot10kProvider dodane w ADR-014 okazalo sie niepotrzebna komplikacja. Uzytkownik i tak pobiera caly ZIP z GUGiK — filtrowanie po stronie klienta powodowalo utrate danych (np. SW* warstwy pomijane domyslnie). Lepiej pobrac wszystko i pozwolic uzytkownikowi filtrowac w GIS.

**Opcje:**
- A) Zostawic category — backward compatible, ale komplikuje API i domyslnie traci dane
- B) Usunac category, pobierac wszystko — prostsze API, brak utraty danych

**Decyzja:** Opcja B. Usunieto `CATEGORY_FILTERS`, `PT_LAYERS`, `HYDRO_LAYERS`, parametr `category` z metod, argument CLI `--category`. `_extract_gpkg_from_zip()` wyciaga wszystkie pliki GPKG z ZIP i scala je w jeden plik. `get_available_layers()` zwraca wszystkie 15 warstw.

**Konsekwencje:** Breaking change — kod uzywajacy `category="hydro"` musi byc zaktualizowany (parametr jest ignorowany przez `**kwargs`). Prostsze API. Brak utraty danych. 835 testow (z 849 — 14 testow category usunietych).

---

## ADR-017: PL-2000 sheet naming — composition pattern with auto-detection

**Data:** 2026-02-24
**Status:** Przyjeta — uzupelniona przez ADR-026 (wlasne segmenty PL-2000; errata 1)

**Kontekst:** PL-2000 to inny system godlowania niz PL-1992. PL-2000 uzywa formatu `strefa.pas.slup[.podpodzialki]` (np. `6.179.12.20`), 4 stref merydianowych (EPSG:2176-2179) i skal od 1:10k do 1:500. Wymaga osobnego parsera z inna logika BBox i hierarchii.

**Opcje:**
- A) Dziedziczenie: Parser2000(SheetParser) — problematyczne bo SheetParser jest scisle zwiazany z PL-1992 (pas/slup literowe, inne skale)
- B) Composition: SheetParser deleguje do Parser2000 — loose coupling, auto-detekcja formatu
- C) Osobna klasa bez integracji — brak unified API

**Decyzja:** Opcja B. Composition pattern: `SheetParser` wykrywa format godla przez regex `^[5-8]\.\d` i deleguje do `Parser2000` (lazy import). Auto-detekcja jest przezroczysta — uzytkownik uzywa `SheetParser("6.179.12")` i nie musi wiedziec o Parser2000. BBox w natywnym CRS strefy (EPSG:2176-2179), nie EPSG:2180. `find_sheets_for_bbox(bbox, system="2000")` dispatuje do `find_sheets_2000_for_bbox()`.

**Konsekwencje:** Czysta separacja logiki PL-1992 i PL-2000. Auto-detekcja w SheetParser zachowuje unified API. Nowe eksporty: `Parser2000`, `find_sheets_2000_for_bbox`. CLI: `--system {1992,2000}` pozwala wymusic system. FileStorage: podkatalog `nmt_2000_1m` dla PL-2000 arkuszy.

**Errata 1 (2026-08-28, ADR-026):** zapowiedziany tu podkatalog `nmt_2000_1m`
nigdy nie powstal (arkusze PL-2000 ladowaly w `nmt_<res>/` obok PL-1992 —
patrz uwaga w CHANGELOG 0.5.0). Odroczenie domkniete w ADR-026: PL-2000 ma
wlasne segmenty `pl_2000_*`.

---

## ADR-018: ThreadPoolExecutor dla rownoleglego pobierania

**Data:** 2026-03-03
**Status:** Przyjeta

**Kontekst:** Pobieranie hierarchii arkuszy (np. N-34-130-D → 256 arkuszy 1:10000) bylo sekwencyjne, co przy wolnym laczeniu z GUGiK trwalo bardzo dlugo. Potrzebna rownoleglosc.

**Opcje:**
- A) asyncio + aiohttp — pelna asynchronicznosc, wymaga refaktoryzacji calego stacku I/O
- B) ThreadPoolExecutor — proste dodanie do istniejacego kodu, requests jest thread-safe
- C) multiprocessing — osobne procesy, wiekszy narzut, trudniejsze wspoldzielenie stanu

**Decyzja:** ThreadPoolExecutor (B). Requests jest thread-safe, I/O-bound task idealny dla watkow, minimalny refaktoring. `max_workers=4` jako domyslny, konfigurowalny przez CLI `--workers`.

**Konsekwencje:** Wymagane thread-safe temp filenames we wszystkich providerach (pattern `pid_threadid.tmp`). DownloadResult zamiast list[Path] dla structured results. Backward-compatible: `max_workers=1` daje sekwencyjne pobieranie.

**Errata 1 (2026-09-29, audyt dokumentacji):** `max_workers=4` jest domyslne
w CLI (`--workers`), a w bibliotece — 1 (`DownloadManager`,
`download_pl_cutout`, `run_pl_cutout`). Metody zwracaja `list[Path]`,
a strukturalny wynik (`DownloadResult`: succeeded/failed/skipped/no_coverage)
trafia do `DownloadManager.last_result`.

---

## ADR-019: SQLite WAL jako metadata cache

**Data:** 2026-03-03
**Status:** Przyjeta — uzupelniona przez ADR-028 (`record_cache` zamiast `url_cache`; errata 1) i ADR-030 (`campaigns_cache`; errata 2)

**Kontekst:** Kazde pobieranie arkusza wymaga request do GUGiK API po URL OpenData. Przy powtarzanych pobieraniach te same URLe sa odpytywane wielokrotnie. Podobnie BDOT10k — mapowanie punkt→TERYT.

**Opcje:**
- A) SQLite z WAL mode — plik lokalny, zero zaleznosci, concurrent reads, TTL
- B) Redis — szybki, ale wymaga serwera, overengineering
- C) Pickle/JSON file — proste, ale brak concurrent access, brak TTL

**Decyzja:** SQLite WAL (A). Zero dodatkowych zaleznosci (sqlite3 w stdlib), WAL mode umozliwia rownoczesne odczyty z ThreadPoolExecutor, TTL 7 dni zapobiega stalym danym, threading.Lock chroni zapisy.

**Konsekwencje:** Nowy modul `kartograf/cache/metadata.py`, `.kartograf_cache.db` w katalogu roboczym, CLI `kartograf cache` do zarzadzania. `prune_expired()` czysci stale wpisy. Optional — providery dzialaja bez cache.

**Errata 1 (2026-09-30, fala naprawcza, ADR-028):** CLI PL podpina `MetadataCache` do NMT/NMPT/orto
poza `--force` (ten tryb omija cache). API wycinka ma `cache=`.
Cache przechowuje `record_cache` (pelny `source` albo potwierdzony
`no_coverage`, TTL 7 dni), a nie same URL-e; `url_cache` jest usuwana
przy otwarciu bazy, `get_url/set_url` zastapiono `get_record/set_record`.
`stats()["record_count"]` i CLI `Record entries` raportuja nowe wpisy.

**Errata 2 (2026-10-07, review-2 E14 i D16; ADR-030):** `--force` nie
omija juz cache, tylko jego ODCZYT: `MetadataCache(refresh=True)` zapisuje
swiezo wybrany rekord (ADR-028 errata 1); tak samo indeks arkuszy SM5 toru CZ
(`sheet_cache`, TTL 30 dni). ADR-030 dodal tabele `campaigns_cache` (lista
kampanii arkusza, TTL 7 dni).

---

## ADR-020: Walidacja warstw WMS przez GetCapabilities

**Data:** 2026-03-24
**Status:** Przyjeta — czesciowo zastapiona przez ADR-028 (warstwy wylacznie z GetCapabilities, bez list zaszytych i fallbacku; errata 3)

**Kontekst:** Hardcoded nazwy warstw WMS w GugikProvider okazaly sie bledne dla NMT 5m — GUGiK zmienil nazwy warstw (np. `SkorowidzeNMT2022` → `SkorowidzeNMT2022iStarsze`, dodal `SkorowidzeNMT2025`). Blad powodowal niepowodzenie wszystkich pobrań NMT 5m. Potrzebny mechanizm wykrywania rozbieznosci miedzy hardcoded a live WMS.

**Opcje:**
- A) Walidacja przy inicjalizacji providera — zapytanie GetCapabilities w `__init__()`, natychmiastowa detekcja
- B) Lazy validation — zapytanie przy pierwszym `_get_opendata_url()`, bez kosztu jesli provider nie jest uzywany
- C) Periodyczna walidacja — cron/timer co N godzin
- D) Brak walidacji — poleganie na hardcoded wartosciach, reczna aktualizacja

**Decyzja:** Lazy validation (opcja B). Nowe metody `_fetch_wms_layers()` (GetCapabilities XML → lista warstw) i `_get_validated_layers()` (porownanie hardcoded z live). Walidacja wykonywana raz, wynik cache'owany in-memory per instancja providera (bez lock — benign duplicate przy concurrent access). Osobny timeout 10s dla GetCapabilities (krotszy niz standardowy 30s). Przy rozbieznosci: warning + auto-aktualizacja do live warstw. Przy bledie GetCapabilities: warning + fallback na hardcoded warstwy.

**Konsekwencje:** Automatyczne wykrywanie zmian warstw WMS bez recznej aktualizacji kodu. Zero kosztu jesli provider nie jest uzywany (lazy). GugikNmptProvider dziedziczy walidacje z GugikProvider bez dodatkowego kodu. GugikOrtoProvider poza zakresem (inna hierarchia dziedziczenia, inny format warstw). 17 nowych testow w `tests/test_wms_layer_validation.py`.

**Errata 1 (2026-06-24, walidacja orto i roczniki 2026):** GugikOrtoProvider otrzymal wlasna walidacje (`_fetch_wms_layers`/`_get_validated_layers`, wyklucza warianty `Zasiegi`). Nazwy warstw NMT 1m/EVRF2007 i Orto odswiezone (nowe roczniki 2026).

**Errata 2 (2026-09-29, historia przed fala naprawcza):**
GetFeatureInfo potrafilo zwrocic HTTP 200 z raportem OGC zamiast
prawidlowej pustej odpowiedzi; taki raport oznacza awarie warstwy,
nie `NoCoverageError` (ADR-027). Stary fallback na zaszyte warstwy
mogl zadac nieaktualne nazwy i zgubic nowsze rekordy; ponizsza
errata zastapila te polityke.

**Errata 3 (2026-09-30, fala naprawcza):** zaszyte `WMS_LAYERS` dla
NMT/NMPT/orto usunieto. Warstwy pochodza tylko z GetCapabilities,
odkrywane lazy i cache'owane per instancja z lockiem; blad pobrania
GetCapabilities nie jest zapamietywany ani zastapiony stara lista.
GetFeatureInfo oczekuje szablonu pustej lub pelnej odpowiedzi
(`var ... = [];`); raport OGC lub bledny szablon to `DownloadError`
bez cichej degradacji do starszej kampanii. Zapytania transportowe
maja 3 proby, a orto korzysta z tego samego parsera rekordow.

**Errata 4 (2026-10-06, review N3, E10):** "Osobny timeout 10s dla
GetCapabilities" nie obowiazuje: GetCapabilities skorowidza dziedziczy
timeout providera (`DEFAULT_TIMEOUT`: 30 s `GugikProvider` — NMT i NMPT,
60 s `GugikOrtoProvider`) albo `timeout=` przekazany do pobrania — porazka
GetCapabilities konczy caly tor, wiec limit nie moze byc krotszy niz dla
pobrania arkusza. Ponawiane sa tylko bledy transportu (ADR-028 errata 1).
Odkrywanie warstw zyje we wspolnym `SkorowidzLayersMixin`
(`providers/pl/skorowidz.py`: `_fetch_wms_layers`, `_layers`);
`_get_validated_layers` nie istnieje.

---

## ADR-021: LAZ (chmury punktów LIDAR) — discovery przez WFS, area-based

**Data:** 2026-06-24
**Status:** Przyjeta — czesciowo zastapiona przez ADR-029 (regula newest-per-tile)

**Kontekst:** Dodanie pobierania plików LAZ (dane pomiarowe ALS) z GUGiK. Dwa problemy: (1) kafle LAZ są godłowane drobniej niz 1:10000 (np. `M-34-27-B-b-2-1-1`, modul 1:1000), a `SheetParser` parsuje maks. do 1:10000 — godło kafla jest nieparsowalne; (2) usługa **WMS** skorowidzy LAZ (`DanePomNMT/WMS/...`) zwraca HTTP 401, wiec mechanizm WMS GetFeatureInfo (jak w NMT/orto) nie dziala.

**Opcje:**
- A) Rozszerzyc `SheetParser` do 1:1000 (PL-1992 + PL-2000) i pobierac po godle kafla — duzo pracy, a godło i tak jest opaque w URL
- B) Discovery przez **WFS** GetFeature po bbox — usługa otwarta (HTTP 200), feature zawiera `url_do_pobrania` wprost; godło kafla jako etykieta (bez parsowania)
- C) Konstruowanie URL z wzorca `.../{density}/{density}_{id}_{godło}.laz` — wymaga nieprzewidywalnego `id` → niewykonalne
- D) ATOM/CSW — bardziej zlozone i mniej bezposrednie niz WFS

**Decyzja:** Opcja B. `GugikLazProvider` z discovery area-based: godło (≤1:10000) / `--bbox` / `--geometry` → bbox EPSG:2180 → WFS GetFeature (`gugik:SkorowidzDanychPomiarowychLIDAR{rok}`) → kafle z `url_do_pobrania`. Godło kafla jest opaque, bez zmian `SheetParser`; dwie usługi WFS wg układu pionowego, domyślnie newest-per-tile (od 2026-10-07: najnowszy kafel per OBSZAR — ADR-029) i filtry `--year`/`--min-density`. Historyczna implementacja wysyłała osie EPSG:2180 jako (E,N), co skorygowano w erracie poniżej.

**Konsekwencje:** Brak zmian w `SheetParser`: godlo kafla pozostaje opaque. LAZ ma osobny przeplyw `_cmd_download_laz` (area→WFS→tiles→parallel download; od 2026-10-07 pobieranie i sidecar w bibliotece `download/laz.py`, CLI jest nakladka — ADR-029). WFS daje rok/gestosc/CRS; roczniki pochodza z GetCapabilities (bez fallbacku listy zaszytej). Wyniki live sprzed naprawy osi potwierdzaly format LASF, a nie poprawne polozenie kafla.

**Errata 1 (2026-09-29, diagnoza historyczna):** pierwotne
„zweryfikowano live” sprawdzalo niepoprawnie sparowane BBOX i envelope:
`urn:ogc:def:crs:EPSG::2180` wymaga (N,E), a stary klient uzywal
(E,N). Pod Spytkowicami odpowiedz z bledna kolejnoscia kierowala
do Lubuskiego zamiast poprawnego kafla `M-34-76-A-a-1-1-3`.
Ponizsza naprawa zastapila te zalozenia.

**Errata 2 (2026-09-30, naprawa K1/N7):** dla WFS `urn:ogc:def:crs:EPSG::2180`
`BBOX` i odczyt `gml:Envelope` uzywaja osi EPSG (N,E);
straz sprawdza, czy przynajmniej jeden zwrocony kafel przecina
zadany obszar (gdy wszystkie sa poza nim, `DownloadError`).
Roczniki pochodza z GetCapabilities (bez `FALLBACK_YEARS`); blad
ktoregokolwiek rocznika po ponowieniach konczy `discover_tiles`
`DownloadError`, nie mylacym wynikiem pustym.

---

## ADR-022: Architektura zrodel wielokrajowych — deskryptory, rejestry, sidecar, twarda polityka transformacji (etap 0)

**Data:** 2026-08-10
**Status:** Przyjeta — uzupelniona przez ADR-023 (formalny interfejs silnika: `CuzkClient`, (a)) i ADR-031 (angielskie nazwy kluczy sidecara)

**Kontekst:** Decyzja kierunkowa: rozszerzenie o Czechy (pelna parytetowosc produktowa), potem Niemcy i Slowacje (analizy transgraniczne). Research 3 krajow (docs/research/2026-08-10-*) dal 4 realne przypadki do zaprojektowania granic abstrakcji i wykazal pulapki: DE = federacja 17 modeli; SK WCS zwraca wysokosci elipsoidalne (42,3 m odchylki od Bpv); PROJ przy braku sieci cicho zwraca identycznosc (ballpark); siatki transformacyjne obcych krajow zwracaja inf poza swoim obszarem; CZ wypelnia obszar poza granica zerami (bez metadanych 0 m udaje poziom morza). Spec: docs/superpowers/specs/2026-08-10-etap0-zrodla-wielokrajowe-design.md.

**Opcje:**
- A) Dodawac kraje przez rozbudowe istniejacych klas GUGiK-centrycznych
- B) Etap 0: zrodla opisane deklaratywnie (deskryptory jako dane), sidecar metadanych, twarda polityka transformacji, wspolny transport; providery per kraj w providers/<cc>/
- C) Pelna ekstrakcja silnikow transportu (WMS-skorowidz/WCS) juz teraz

**Decyzja:** Opcja B. `sources/` (SourceDescriptor/AccessChannel/rejestr; zero IO), `sources/sidecar.py` (ResultMetadata + `<plik>.meta.json` po kazdym udanym pobraniu — kontrakt dla Hydrografa, ktory scala dane transgraniczne), `transform/crs.py` (TransformerGroup z allow_ballpark=False; odrzucanie operacji o nieznanej dokladnosci — w pyproj accuracy=-1, 0.0 oznacza operacje dokladna i JEST akceptowane; probe na punkcie kontrolnym odrzuca siatki obcych krajow zwracajace inf; isfinite na kazdym wyniku), `transport/http.py` + `transport/mosaic.py`, `core/parser_registry.py`, unifikacja ABC (DataSourceProvider; download_by_admin_unit z aliasami teryt), przenosiny providers/pl/ BEZ shimow (decyzja uzytkownika: Hydrograf/Hydrolog dostosuja importy; stabilna powierzchnia = `from kartograf import ...`). Opcja C odrzucona: jedynym konsumentem WMS-skorowidzow jest GUGiK, ekstrakcja teraz to ryzyko dla ~1060 testow bez zysku; formalny interfejs silnika powstanie w etapie 1 przy CuzkClient.

**Konsekwencje:** Zachowanie identyczne (inwariant ~1060 testow bez zmiany asercji); jedyna zmiana obserwowalna to sidecary `.meta.json`. BREAKING dla glebokich importow (tabela w CHANGELOG). Etap 1 (CZ DMR) buduje na fabryce providerow pl/, deskryptorach i polityce transformacji.

---

## ADR-023: Silnik CUZK, polityka układów CZ i EVRF2007→5621 (etap 1)

**Data:** 2026-08-11
**Status:** Przyjeta — czesciowo zastapiona przez ADR-024 (mechanizm pobrania TM33 w (c), Ustalenia dodatkowe pkt 1) i ADR-027 (`--target-crs` wylacznie dla CZ; Ustalenia dodatkowe pkt 6) i ADR-038 (obszar CZ zawsze wycinkiem; teraz `--cutout`); uzupelniona przez ADR-029 ((f).1 obejmuje LAZ) i ADR-034 (kawalkowanie CUZK w `transport/chunks.py`); uzupelnia ADR-022; errata 2: `--country` wymagane z obszarem, wartosci per kraj (0.8.0)

**Kontekst:** Etap 1 dodaje pierwsze zagraniczne zrodlo danych — CUZK (Czeski
Urzad Zememericky a Katastralni), DMR 5G (2 m, `exportImage`) i DMR 4G (5 m,
pliki openzu + `exportImage`). To pierwszy realny konsument architektury
etapu 0 (deskryptory, sidecar, `transform/crs.py`), wiec kilka decyzji z
etapu 0 oznaczonych jako "odroczone do etapu 1" (formalny interfejs silnika,
jawna selekcja kanalu, probe pod polityka sieci) musialo zostac domknietych.
Rekonesans na zywo (`docs/research/2026-08-11-etap1-rekonesans.md`) i E2E
(`docs/research/2026-08-11-etap1-e2e.md`) zweryfikowaly zalozenia specu i
wymusily kilka korekt (m.in. limit `exportImage` asymetryczny 15000x4100 px,
CRS z `exportImage`/openzu zawsze wymaga nadpisania, `PODIL`/`MAPNAME`
rzeczywiste wartosci CTES96). Konsultacja z uzytkownikiem przy planie
(2026-08-11) rozstrzygnela trzy otwarte pytania specu (`parent_request`,
`--target-crs` + godlo, polimorfizm `PinnedTransform.transform`).

**Decyzje:**

(a) **`CuzkClient` (`kartograf/providers/cuzk/client.py`) jako pierwszy silnik
sterowany deskryptorem.** Metody `query()`, `export_image()`, `fetch_file()`
sa generyczne, parametryzowane URL-em z `AccessChannel.endpoint` (nowe pole
deskryptora) — klient nie zna godel, produktow ani sidecarow (por. docstring
modulu). To realizuje zapowiedz ADR-022 ("formalny interfejs silnika powstanie
w etapie 1 przy CuzkClient"). Mimo to `CuzkClient` **zostaje** w
`providers/cuzk/`, nie w `transport/` — ekstrakcja wspolnego "silnika ArcGIS
REST" (analogicznie do `transport/http.py`/`transport/mosaic.py`) jest
swiadomie odroczona do **drugiego konsumenta** tego samego wzorca (DE/SK maja
podobne API REST/WCS) — jeden konsument nie uzasadnia jeszcze abstrakcji
(zgodnie z odrzuceniem opcji C w ADR-022).

(b) **Przeplyw CZ omija `DownloadManager`** — precedens LAZ (ADR-021).
`CuzkDmrProvider` i CLI (`_cmd_download_cz`) nie wolaja
`download_sheet()`/`download_bbox()`; maja wlasny przeplyw, bo model danych
CZ rozni sie strukturalnie od PL: godlo CZ (TM33 lub SM5) **zawsze** daje
dokladnie jeden plik — nie ma hierarchii arkuszy do rozwijania jak w PL-1992.
API `DownloadManager` pozostaje nietkniete; jedynym punktem styku jest
addytywny parametr `sidecar_extra` (Zad. 13), uzywany przez CLI PL w trybie
`--bbox`/`--geometry` (Zad. 17) do wpiecia wspolnego `parent_request`.

(c) **TM33 w trybie godlowym pobierany w EPSG:3045; asymetria trybu bbox
PL/CZ.** Siatka kafli TM33 (2x2 km, `{E_km}_{N_km}`) jest zdefiniowana w
ETRS89/UTM33N (EPSG:3045, `ParserTM33` — obliczalna matematycznie, wzor jak
`Parser2000`), mimo ze dane DMR 5G leza natywnie w S-JTSK/Krovak (EPSG:5514,
`AccessChannel.horizontal_crs` kanalu `ARCGIS_IMAGE`). *(Mechanizm pobrania
opisany dalej w tym punkcie ZASTAPIONY przez ADR-024: zadanie `exportImage`
idzie w natywnym 5514, a reprojekcje kafla do 3045 wykonuje lokalny warp
przypieta operacja; definicja siatki kafli w 3045 i asymetria bbox PL/CZ
pozostaja aktualne.)* Pobranie godlem zadalo
wiec `exportImage` z `bboxSR=imageSR=3045` — serwer reprojektowal w locie;
"natywny" produkt trybu godlowego CZ to 3045 (definicja siatki kafli), nie
5514 (uklad przechowywania danych CUZK). To tworzy jawna asymetrie wzgledem PL: `--bbox` w PL
zwraca **liste arkuszy** OpenData (wiele plikow po godle, `find_sheets_for_bbox`
+ petla pobran), `--bbox` w CZ zwraca **jeden plik** — bezposredni wycinek
serwerowy `exportImage`, bo CZ nie ma odpowiednika "OpenData po dowolnym
bboxie". Asymetria jest udokumentowana (research krok 5, spec), nie ukrywana.

(d) **EVRF2007 = EPSG:5621 globalnie + mapa rodzina→realizacja** (BREAKING
ograniczony do `vertical_crs_code`). Decyzja uzytkownika 2026-08-11:
`vertical_crs_code("EVRF2007")` zwraca teraz ogolnoeuropejski **EPSG:5621**
(nie polska realizacje EPSG:9651) — bo `EVRF2007` jest teraz nazwa RODZINY
ukladow, wspolna dla PL i CZ (Bpv→EVRF2007 to operacja do 5621, nie do
zadnej realizacji krajowej). Nowa funkcja `resolve_vertical_crs(name, options)`
mapuje nazwe na kod rodziny, ale jesli kanal deklaruje w
`vertical_crs_options` realizacje krajowa (PL: EPSG:9651) zamiast kodu
rodziny, zwraca realizacje. Efekt: sidecary PL nadal niosa faktyczny kod
9651 (tresc bez zmian), a BREAKING dotyczy **wylacznie** bezposrednich wywolan
`vertical_crs_code("EVRF2007")` spoza Kartografu (Hydrograf/Hydrolog, jesli
wolaja funkcje wprost). Mapa starego/nowego kodu — patrz CHANGELOG.

(e) **`Bpv` = EPSG:8357 (Baltic 1957, nie 1977); pionowa 8357→5621 przypieta
operacja 0,1 m; KRON86 nieosiagalny dla CZ.** Natywny uklad wysokosciowy
CUZK to Bpv (Baltický po vyrovnání) = EPSG:8357, realizacja **Baltic 1957**
(potwierdzone przez `vcsWkid` uslug `ImageServer` oraz nazwe operacji PROJ
"Baltic 1957 height to EVRF2007 height (1)") — **nie** Baltic 1977
(EPSG:5705, inna realizacja, latwa do pomylenia z nazwy). Transformacja
8357→5621 jest przypieta operacja EPSG o dokladnosci 0,1 m; offset zmierzony
na zywo (E2E, 64722 pikseli) to **+0,132366 m** (std 2,22e-05), w oczekiwanym
zakresie rekonesansu +0,112..+0,148 m (gradient ~+0,014 m/stopien szerokosci,
rosnacy S→N). Transformacja 8357→9650 (KRON86, polska realizacja
Kronsztadt 86) jest **nieosiagalna** — jedyne sciezki PROJ sa ballpark
(siatki `pl86_2019`/`pl07_2019` nie sa publiczne) i sa twardo odrzucane
przez `allow_ballpark=False` (ADR-022); uzytkownik dostaje
`TransformUnavailableError` z remedium ("zainstaluj siatki recznie do
`PROJ_DATA` albo uzyj EVRF2007 (EPSG:5621)").

(f) **Rozstrzygniecia z konsultacji 2026-08-11 (wiazace):**
1. `extra.parent_request` jest zapisywany **zawsze** w trybie
   `--bbox`/`--geometry` (auto I jawny `--country`), **nigdy** w trybie
   godlowym. Klucz grupowania to identyczny `bbox`+`bbox_crs` — umozliwia
   scenariusz dwuetapowego dociagania drugiego kraju dla tego samego zadania
   (np. najpierw `--country pl`, potem `--country cz` dla tego samego bboxa:
   oba zestawy sidecarow beda mialy ten sam `parent_request` i da sie je
   pogrupowac po stronie Hydrografu).
2. `--target-crs` razem z godlem CZ jest twardym `ValidationError`
   (reprojekcja serwerowa ma sens tylko wzgledem zadanego obszaru
   `--bbox`/`--geometry`; pojedynczy kafel pobrany godlem jest z definicji
   juz-natywnym produktem 1:1 — patrz tez punkt 1 nizej).
3. `PinnedTransform.transform` jest **polimorficzne** (skalary lub tablice
   `numpy`, `np.isfinite` zamiast `math.isfinite`) zamiast osobnej metody
   `transform_grid` — rekonesans (Zad. 1, krok 7d) pokazal, ze
   `math.isfinite` rzuca `TypeError` na `numpy.ndarray`, a transformacja
   pionowa per-piksel calego rastra (Zad. 12) wymaga wywolania tablicowego.

(g) **Sentinele `None` dla `--resolution`/`--vertical-crs`/`--system`
rozwiazywane per kraj.** CLI (`cli/_parser.py`) zmienilo domyslne wartosci
tych trzech flag z twardo zakodowanych PL-owych domyslnych na sentinel
`None`, rozwiazywany dopiero po ustaleniu kraju docelowego (z godla lub
`--country`) — PL i CZ maja rozlaczne domyslne (PL: 1m/EVRF2007/1992 bez
zmian; CZ: 2m/Bpv, `--system` nie dotyczy). Jeden `argparse.ArgumentParser`
obsluguje oba kraje bez duplikowania definicji flag i bez zgadywania kraju
przed jego ustaleniem.

**Ustalenia dodatkowe (domkniecie zobowiazan zebranych w trakcie
implementacji — ledger kontrolera `.superpowers/sdd/2026-08-11-etap1-cz-fundament-dmr/progress.md`
nie zostal zachowany: katalog jest poza gitem, plik utracony; jedyny
przetrwaly zapis tych zobowiazan to ponizsze punkty i PROGRESS.md):**

1. **Semantyka `transform.horizontal` w sidecarach** — **ZASTAPIONA przez
   ADR-024 (2026-08-11)**. Pierwotnie: "reprojekcja zamowiona przez
   uzytkownika (`--target-crs`)", NIE "praca serwera" — kafel TM33 pobrany
   godlem mial `transform: null` (mimo serwerowej reprojekcji 5514→3045
   wewnatrz `exportImage`), a bbox z `--target-crs` mial
   `transform.horizontal = "server:EPSG:<kod>"`. Pomiary z 2026-08-11
   pokazaly, ze "praca serwera" nie jest detalem implementacyjnym, ktory
   mozna przemilczec: reprojekcja serwerowa gubila transformacje datum
   (blad 135 m). Od ADR-024 Kartograf w ogole jej nie uzywa, a pole niesie
   przypieta operacje lokalna z dokladnoscia — dla OBU trybow, takze
   godlowego TM33. Nizej opisana implementacja (`server_crs`
   w `_write_cz_sidecar()`) juz nie istnieje. Bez zmian pozostaje
   rozroznienie po stronie pionowej: autorytatywnym sygnalem
   faktycznej transformacji jest `transform.vertical` (np.
   `"pinned: Bpv->EVRF2007"`), NIE `vertical_source` — `vertical_source`
   opisuje wylacznie **kanal zrodlowy** (`"native"` dla CUZK), wiec zostaje
   `"native"` takze wtedy, gdy `vertical_crs` w sidecarze jest juz po
   przeliczeniu (np. `EPSG:5621` po Bpv→EVRF2007, patrz punkt (e)); to nie
   jest niespojnosc, tylko dwa rozne pola opisujace dwie rozne rzeczy.
2. **Eager import `rasterio` przy `import kartograf`** (eksporty CZ w
   `__init__.py`, Zad. 18): `providers/cuzk/client.py` importuje `rasterio`
   na poziomie modulu (potrzebne do `export_image`/`fetch_file`), a
   `CuzkDmrProvider` importuje `client.py` na poziomie modulu — w efekcie
   zwykle `import kartograf` **po raz pierwszy** laduje eagerly `rasterio`
   (GDAL/PROJ bindings), zmierzony koszt **+55–65 ms** (z ~185 ms do ~244 ms,
   3x pomiar `time.perf_counter()`). To zmiana **failure-domain**: zepsuty
   GDAL/PROJ (np. brakujaca biblioteka natywna w srodowisku Hydrografu/
   Hydrologu) psuje teraz sam `import kartograf`, nie dopiero pierwsze
   wywolanie funkcji rastrowej. Decyzja: zaakceptowano wariant prosty (eager,
   plain top-level import, spojny stylistycznie z reszta `__init__.py` —
   `GugikOrtoProvider`, `Bdot10kProvider` itp. sa eksportowane identycznie),
   NIE wprowadzono lazy-loadingu (`__getattr__`/PEP 562) w `__init__.py` —
   `rasterio` jest i tak twardym, wymaganym zaleznosciem calego pakietu
   (pyproject: `rasterio >= 1.3.0`), wiec to przesuniecie w czasie momentu
   zaladowania, nie nowa zaleznosc; a niemal kazda realna operacja CLI na
   danych CZ i tak natychmiast potrzebuje `rasterio`. **Sciezka przyszlej
   naprawy** (poza zakresem etapu 1): przeniesc `import rasterio`/
   `from rasterio.crs import CRS` w `providers/cuzk/client.py` i `dmr.py` na
   poziom funkcji/metod, analogicznie do wzorca juz stosowanego w
   `hydrology/hsg.py` i `transport/mosaic.py` — przywrocilyby lazy-loading
   bez zmiany publicznego API.
3. **`parent_request.countries` to kraje PROBOWANE, nie pobrane.** Przy
   awarii jednego kraju w trybie `--country auto` (np. CZ zwraca
   `DownloadError`), sidecary pozostalego kraju (PL) nadal niosa
   `countries: ["CZ", "PL"]` — pole opisuje zamiar zadania (ktore kraje
   przecina bbox), nie fakt sukcesu pobrania per kraj. Dodatkowo
   `parent_request.bbox_crs` **rozni sie per tryb dla tego samego pliku
   geometrii**: jawny `--country cz` zapisuje CRS pliku geometrii (np.
   EPSG:5514/3045), a `auto`/jawny `--country pl` zapisuje EPSG:2180 —
   wiec ten sam plik `.shp` uzyty w dwoch wywolaniach CLI (raz `--country cz`,
   raz bez flagi) NIE wyprodukuje identycznego `parent_request` mimo
   identycznego zadania uzytkownika. To znane ograniczenie klucza
   grupowania (punkt f.1) — do ujednolicenia w etapie 2 (patrz tez
   `docs/SCOPE.md`, sekcja ograniczen).
4. **Prostokatne extenty krajow wysylaja zapytania CUZK takze poza faktyczna
   granica CZ.** `CountryProfile.extent_wgs84` dla CZ to prostokat
   `BBox(12.09, 48.55, 18.86, 51.06)` (obwiednia, nie wielokat granicy) —
   kazde zadanie `--country auto` w poludniowej Polsce (lon < 18,86°E, lat <
   51,06°N — pas na zachod od 18,86E i na poludnie od 51,06N - m.in. Opole,
   Walbrzych, Rybnik, poludniowe obrzeza Wroclawia; Krakow, Rzeszow i centrum
   Wroclawia (51,11N) leza poza prostokatem) wysyla zapytanie do CUZK, mimo ze
   bbox realnie lezy w calosci w Polsce. Skutek:
   dodatkowy raster wypelniony `nodata` (`-9999`) + dodatkowy sidecar CZ bez
   uzytecznych danych, a nie blad — ale zbedny ruch sieciowy i plik.
   Wlasciwa naprawa (wielokat granicy administracyjnej zamiast prostokata)
   jest zaplanowana na etap 2 (patrz `docs/SCOPE.md`).
   **Symetria (audyt 0.7.0, ustalenie A3-2):** to samo dzieje sie w druga
   strone — prostokat PL to `BBox(14.07, 49.00, 24.20, 54.90)`, wiec pokrywa
   niemal cale Czechy na wschod od Pilzna i `--country auto` w Pradze, Brnie
   czy Ostrawie odpytuje takze GUGiK. Skutek jest jednak inny niz po stronie
   CZ: brak danych GUGiK to twardy `DownloadError`, nie pusty raster, wiec
   `max(exit_codes)` zamienial poprawnie pobrany raster CZ w kod 1 calego
   polecenia. Od 0.7.0 porazka JEDNEGO kraju przy sukcesie drugiego (tylko
   w trybie `auto` i tylko przy wiecej niz jednym kraju) konczy sie kodem
   wyjscia **0** z ostrzezeniem `Warning:` na stderr; `max(exit_codes)`
   zostaje dla jawnego `--country` (uzytkownik sam wskazal zasieg) i dla
   przypadku, w ktorym padly wszystkie kraje. Informacja o niepelnym pokryciu
   nie ginie: sidecary i tak niosa `parent_request.countries` = kraje
   PROBOWANE (punkt 3).
5. **Addendum 2026-08-22 (audyt przedwydaniowy 0.7.0, ustalenie N6-2): opcje
   tylko-PL rozstrzygaja `--country auto`, zamiast przewracac zadanie.**
   Drugim skutkiem prostokatnych obwiedni (punkt 4) bylo, ze zadanie lezace
   w CALOSCI w Polsce, ale wewnatrz prostokata CZ (pas na zachod od 18,86E i na
   poludnie od 51,06N - m.in. Opole, Walbrzych, Rybnik, poludniowe obrzeza
   Wroclawia; nie cala poludniowa Polska, patrz pkt 4 (Krakow i Rzeszow poza
   prostokatem)), konczylo sie kodem 1, gdy uzytkownik podal
   opcje bez odpowiednika czeskiego: `--product nmpt|orto`, `--system`,
   `--vertical-crs KRON86`, `--resolution 1m` (np. `kartograf download --bbox
   442802,248390,444802,250390 --system 2000` pod Raciborzem ->
   `Error: --system dotyczy tylko PL`). Wzgledem 0.6.1, gdzie `--country`
   w ogole nie istnialo, byla to twarda regresja komend udokumentowanych od
   v0.4.0/v0.5.0. Od 0.7.0 taka opcja ROZSTRZYGA kraj: CLI wypisuje
   `Info: --country auto -> pl (<opcje> dotyczy tylko PL)` na stderr i dalej
   zachowuje sie dokladnie jak jawny `--country pl` — bez przycinania bboxa
   do obwiedni kraju, z `parent_request.countries == ["PL"]`. Rozstrzygniecie
   obejmuje wylacznie obszary FAKTYCZNIE sporne (tryb `auto`, wiecej niz jeden
   kraj, PL wsrod nich): obszar lezacy w calosci w Czechach dostaje nadal
   komunikat o etapie 2, bo tam wybor PL bylby bezsensem, a nie odczytaniem
   intencji. `--product laz` NIE nalezy do tej listy mimo bycia PL-owym — ma
   wlasny przeplyw (`_cmd_download_laz`) z wlasnym guardem transgranicznym
   i nigdy nie dociera do dyspozycji obszarowej. Koszt: bbox przygraniczny
   z `--system 2000` nie dostanie juz czesci czeskiej (dotad nie dostawal
   niczego — kod 1, wiec zmiana jest scisle lepsza), a `-q` nie tlumi
   komunikatu `Info:`, bo idzie on na stderr (jak `Error:`/`Warning:`).
6. **Addendum 2026-08-28 (ADR-027): `--target-crs` przestaje byc flaga
   wylacznie czeska.** W trybie `--bbox`/`--geometry` dziala tez dla PL
   (jeden scalony wycinek), a na pograniczu `--country auto --target-crs`
   daje dwa wycinki w tym samym ukladzie ze wspolnym
   `extra.parent_request`. `--target-crs` NIE dolacza wiec do listy opcji
   rozstrzygajacych kraj z pkt 5 (`_pl_only_flags`) — dziala po obu
   stronach granicy, wiec nie rozstrzyga w zadna strone. Asymetria z punktu
   (c) obowiazuje odtad tylko bez `--target-crs`: z ta flaga bbox PL daje
   jeden scalony wycinek.

**Konsekwencje:** Pelna parytetowosc produktowa DMR miedzy PL i CZ (godlo,
bbox, transformacja pozioma/pionowa opcjonalna). 1381 testow zielonych
(+244 wzgledem stanu po etapie 0), pokrycie ~89%, ruff/mypy bez nowego
dlugu wzgledem baseline, E2E 11/11 PASS na zywych danych CUZK+GUGiK
(`docs/research/2026-08-11-etap1-e2e.md`). BREAKING ograniczone do
`vertical_crs_code()` (funkcja publiczna, ale niszowa — wiekszosc
konsumentow uzywa sidecarow, ktore niosa faktyczny kod bez zmian tresci).
Etap 2 (DMP/Orto/LAZ CZ, wielokat granicy, ujednolicenie `parent_request`)
buduje na tym samym `CuzkClient`/deskryptorach — kolejny konsument moze
uzasadnic ekstrakcje silnika do `transport/` (punkt a).

**Errata 1 (2026-09-29, audyt dokumentacji i testy na zywo;
`docs/research/2026-09-29-live-e2e-i-audyt-docs/`):**
- pkt (f).2: "pojedynczy kafel pobrany godlem jest z definicji
  juz-natywnym produktem 1:1" — od ADR-024 nieaktualne dla TM33: kafel
  TM33 to lokalny warp z EPSG:5514 na siatke EPSG:3045; 1:1 daja arkusz
  SM5 i arkusze PL. Odrzucenie `--target-crs` z godlem zostaje (godlo
  wyznacza zasieg i uklad produktu);
- pkt 3 ("jawny `--country cz` zapisuje CRS pliku geometrii, a `auto`/
  `--country pl` — EPSG:2180"): jawny `--country cz` zapisuje obwiednie
  w ukladzie zadania CZ (EPSG:5514 albo `--target-crs`), a `auto`/`pl` —
  w ukladzie pliku, gdy plik jest w EPSG:5514/3045 (od 2026-09-28, review
  max zn. 4), inaczej w EPSG:2180. Klucze sa zgodne tylko wtedy, gdy oba
  uklady sie pokrywaja (np. plik w EPSG:5514 bez `--target-crs`);
  ograniczenie do ujednolicenia w etapie 2 bez zmian;
- pkt 4: brak danych GUGiK to `NoCoverageError(DownloadError)`;
  wycinek z czesciowym brakiem zapisuje nodata i `extra.missing_sheets`;
  tryb listy/hierarchii ma od 2026-09-30 tolerancje R5 (ADR-027 errata 3);
  wynik CZ calkowicie nodata daje `Warning:` i kod 0, podobnie PL gdy
  pobrane arkusze nie wnosza waznych pikseli;
- przycinanie pod `auto` drukuje `Info:` na stderr o obcietych
  krawedziach i utraconej czesci poza krajami. Nietkniete krawedzie PL
  zachowuja oryginalne wartosci (koniec poszerzania przy round-trip WGS84).
  Nazwa pliku i `request.bbox` niosa przyciecie, oryginal
  `extra.parent_request`; jawny kraj nie przycina. Przy `--geometry`
  bez `--target-crs` arkusze PL wyznacza geometria;
- deklarowany sufit `exportImage` 15000 x 4100 px pozostaje,
  realna granica ~8 Mpx prowadzi do kafelkowania klienta z budzetem
  4 Mpx na zapytanie (ADR-024 errata 2).

**Errata 2 (2026-10-12, 0.8.0, bez wartosci domyslnych):** `--country`
jest wymagane z `--bbox`/`--geometry` (z `--sheet` kraj nadal wynika
z godla). Bez domyslnych PL 1m/EVRF2007 i CZ 2m/Bpv zadanie PL+CZ podaje
`--resolution`/`--vertical-crs` jedna wartoscia dostepna w obu krajach
(`5m`, `EVRF2007`) albo per kraj (`pl=1m,cz=2m`, `pl=EVRF2007,cz=Bpv`;
decyzja uzytkownika 2026-10-12); walidacja kazdego kraju przed siecia.
`Info:` o roznych domyslnych ukladach wysokosci czesci PL i CZ zniknal.
Pkt 5 (flagi PL-only rozstrzygaja `auto` na `pl`) obowiazuje dla
`--product nmpt|orto` oraz zwyklych `--vertical-crs KRON86`
i `--resolution 1m`; `--system` (wymagane dla czesci PL) i wartosci per
kraj kraju nie wybieraja, a zadanie PL+CZ z `--system` nie jest juz
bledem po stronie CZ.

---

## ADR-024: Reprojekcja tresci CZ wylacznie lokalnie (zakaz `imageSR` != natywny)

**Data:** 2026-08-11
**Status:** Przyjeta — uzupelniona przez ADR-034 (wspolne planowanie kawalkow z kotwica NW); zastepuje czesc ADR-023 (mechanizm pobrania TM33 w (c), Ustalenia dodatkowe pkt 1)

**Kontekst:** Analiza szwu PL/CZ na Olzie (Cieszyn / Cesky Tesin) wykryla, ze
`kartograf download --country cz --target-crs EPSG:2180` zwraca raster, ktorego
tresc lezy **135 m obok** prawdy (dE 119 m, dN 64,5 m). Zrodlem nie byla zadna
transformacja Kartografa: reprojekcje wykonywal serwer ArcGIS CUZK
(`exportImage&imageSR=2180`) i robil to **bez transformacji datum**
S-JTSK→ETRS89, czyli dokladnie tak, jak zakazana u nas operacja ballpark.
Ironia architektoniczna: `transform/crs.py` zakazuje ballparku i ten zakaz
dziala — obwiednia zadania liczona lokalnie zgadza sie z pyproj do 0,07 m —
ale sama TRESC pikseli szla sciezka serwerowa, ktora ten sam blad wprowadzala
z powrotem. Zaden sidecar tego nie sygnalizowal (`transform.horizontal =
"server:EPSG:2180"`, bez pola dokladnosci).

Pomiary kontrolne (2026-08-11, `exportImage` vs. dane natywne 5514
zreprojektowane lokalnie przez pyproj/GDAL, dopasowanie przez minimum RMS):

| sciezka | minimum RMS | przesuniecie | ballpark wg pyproj |
|---|---|---|---|
| `imageSR=2180` (`--target-crs`) | 0,041 m przy (−119,0; −64,5) | **135 m** | dE 118,8 / dN 64,4 |
| `imageSR=3045` (godlo TM33) | 0,034 m przy (0; +1,25) | **1,25 m** | dE 115,3 / dN 70,7 |
| natywny 5514 vs natywny 5514 | 0,045 m przy (0; 0) | 0 (kontrola) | — |

Czyli: dla 3045 serwer datum **stosuje** (przesuniecie 135 m nie wystepuje),
ale zostawia systematyczne **1,25 m na poludnie** — powtorzone na dwoch
niezaleznych kaflach (`758_5514`, `760_5514`), przy samozgodnosci eksportow
natywnych 0,045 m. Zrodlo tego 1,25 m pozostaje nieznane (po stronie serwera).

**Korekta liczby (2026-08-11, po zywej weryfikacji fixu):** 1,25 m pochodzi
z pomiaru na dwoch kaflach diagnozy kolo Cieszyna (`758_5514`, `760_5514`).
Niezalezny pomiar na pliku E2E sprzed fixu (`302_5550`, zachodnie Czechy,
zachowany z sesji E2E) dal **4,92 m** przesuniecia tresci wzgledem pliku po
fixie (dE −4,50 m, dN −2,00 m; minimum RMS 0,042 m przy skanie ±30 m) —
prawie 4x wiecej niz kolo Cieszyna. Wniosek: blad serwerowej reprojekcji
5514→3045 byl **zmienny przestrzennie** (rozna realizacja transformacji
datum po stronie serwera CUZK w roznych czesciach kraju), nie stala
globalna — silniejszy argument za Opcja C (reprojekcja lokalna takze dla
sciezki godlowej TM33) niz sugerowalaby sama liczba 1,25 m. Zrodlo:
`seam/verify/verify-report.md`, sekcja 2 ("Dodatkowo: bezposredni pomiar
skutku fixu na tym samym kaflu") — raport odzyskany 2026-08-18 ze scratchpada
sesji: kopia w `docs/research/2026-08-11-adr024-verify-report.md`, oryginal
z pelnymi danymi w niewersjonowanym `seam/` w korzeniu repo.

**Opcje:**
- A) Naprawic tylko `--target-crs`, zostawic godlowa sciezke TM33 na serwerze.
  Odrzucona: 1,25 m to 0,6 piksela DMR 5G, na stoku 20° daje 0,45 m bledu
  wysokosci — tego samego rzedu co caly budzet roznic zmierzony na szwie.
  Zostawialaby tez dwie rozne zasady dla dwoch sciezek tego samego produktu.
- B) Zostawic reprojekcje serwerowa + test kontrolny punktow (serwer vs
  `PinnedTransform`) z twardym bledem przy rozjezdzie. Odrzucona: wykrywa
  problem, ale go nie rozwiazuje — uzytkownik dostaje blad zamiast danych,
  a koszt zadania jest juz poniesiony.
- C) **Reprojekcja lokalna** — wybrana.

**Decyzje:**

(a) **Serwer CUZK dostaje zadania rastrowe WYLACZNIE w ukladzie natywnym**
(`NATIVE_CRS = "EPSG:5514"`). Dotyczy obu sciezek: `--target-crs` i domyslnej
godlowej TM33 (wynik w 3045). Obwiednia zadania to cel przeliczony do 5514
istniejacym `bbox_to_crs()` (probkowanie krawedzi) plus zapas
`_WARP_MARGIN_PX = 4` piksele — pokrywa niepewnosc operacji obwiedniowej
(≤ 2 m) i halo interpolatora na krawedzi.

(b) **Reprojekcja tresci lokalnie przez `rasterio.warp.reproject`, operacja
WYMUSZONA.** Bez wymuszenia GDAL wybiera operacje sam, poza polityka
`transform/crs.py` (zmierzona roznica wzgledem przypietej: srednio 0,08 m,
maks. 1,9 m). Mechanizm: `PinnedTransform.gdal_operation()` zwraca te sama
operacje jako pipeline PROJ dla GDAL-owego `COORDINATE_OPERATION`.

(c) **Korekta kolejnosci osi w `gdal_operation()` jest obowiazkowa.**
`PinnedTransform` powstaje z `always_xy=True` (kolejnosc E-N), a GDAL podaje
operacji wspolrzedne w kolejnosci **autorytatywnej** obu ukladow. Oba realne
cele CZ→PL sa northing-first (`EPSG:2180`: x=north, `EPSG:3045`: N-E), wiec
bez `step proj=axisswap order=2,1` warp daje raster **w calosci nodata** —
cicha awaria, latwa do przeoczenia w potoku. Korekta jest wyliczana z
`CRS.axis_info`, nie zakladana. Sprawdzone alternatywy: `to_wkt()` operacji
(GDAL nakłada wlasna obsluge osi — tez cale nodata) i wyszukanie
autorytatywnej wersji operacji w `TransformerGroup(always_xy=False)`
(nie da sie dopasowac po opisie: normalizacja dokleja "+ axis order change").

(d) **Kafelkowanie i mozaikowanie zostaja po stronie natywnej — przed
warpem.** Limity `exportImage` tna zadanie w 5514, `mosaic_and_crop` sklada
je w jeden raster i dopiero on jest reprojektowany. Odwrotna kolejnosc
(warp per kafel) utrwalilaby szwy: interpolacja na krawedzi kafla nie ma
sasiadow z kafla obok.

(e) **`transform.horizontal` w sidecarze niesie operacje lokalna
z dokladnoscia** — `"pinned: <opis> (<acc> m)"`, symetrycznie do
`transform.vertical`. Zastepuje `"server:EPSG:<kod>"` (bez dokladnosci) i
pojawia sie takze dla kafla TM33, ktory dotad mial `transform: null`.
Konsument sidecara ma dzis sygnal, ze reprojekcja w ogole zaszla i z jaka
dokladnoscia; wczesniej `"server:EPSG:2180"` moglo znaczyc "blad 135 m".

(f) **Fail-fast przed transferem.** Brak bezpiecznej operacji poziomej
przerywa, zanim uzytkownik zaplaci za pobranie — ale **w dwoch roznych
miejscach**, bo uklad docelowy jest znany w dwoch roznych momentach:
- `--target-crs` (tryb bbox/geometry): cel znany przy konstrukcji, wiec
  operacja budowana jest **w konstruktorze providera**, jak pionowa
  Bpv→EVRF2007; CLI tlumaczy wyjatek na komunikat z remedium przy tworzeniu
  providera;
- **godlo TM33**: `target_crs` jest `None` (godlo dostarcza produkt natywny
  dla swojej siatki), a cel — EPSG:3045 — wynika dopiero z godla, wiec
  operacja powstaje w `_export_raster()`, **przed** pierwszym zadaniem HTTP.
  Wyjatek lapie dopiero `_run_cz()` w CLI (wspolny handler `TransformError`
  dla calego przeplywu CZ) i drukuje ten sam komunikat z remedium. To
  zabezpieczenie lezy daleko od miejsca rzucenia, wiec jest przypiete testem
  `test_godlo_without_safe_horizontal_operation_exits_cleanly`.

Polityka: `_HORIZONTAL_POLICY` (`min_accuracy_m=1.0`, bez siatek z CDN) —
ostrzejsza niz obwiedniowa (2 m), bo to jedyna operacja, ktora **przesuwa
piksele**; znane operacje z Krovaka do 2180/3045 maja 0,5 m.

(g) **Wymuszenie operacji musi byc pilnowane osobnym testem.** Sam test
tresci go NIE broni: po usunieciu `COORDINATE_OPERATION` warp nadal dziala
i nadal trafia ~1,0 m od wzorca pyproj, czyli **wewnatrz** tolerancji
1 px (2 m) testu tresci — zmierzone. `TestGdalOperation` sprawdza z kolei
tylko postac stringa, nigdy jego uzycia. Dlatego
`test_warp_forces_the_pinned_operation` (obie sciezki: bbox i godlo)
asertuje wprost, ze do GDAL-a poszla operacja z `gdal_operation()`.

**Konsekwencje:** Kazde pobranie CZ w ukladzie innym niz 5514 kosztuje jedno
lokalne przeprobkowanie (bilinear) i nieco wiekszy transfer (obwiednia
prostokata obroconego wzgledem siatki + margines). Liczba przeprobkowan sie
NIE zmienia — serwer i tak reprojektowal, tylko gorzej i bez sladu w
metadanych. Nodata (`-9999`) nie wchodzi do interpolacji (maska GDAL,
zweryfikowane testem), zapis pozostaje atomowy (tmp + `os.replace`), a wynik
lezy na tej samej siatce co dotad: **rozmiar w pikselach jest identyczny**,
a zasieg — jak dotad — przyklejony do wielokrotnosci `pixel_size` liczonej od
poludniowo-zachodniego naroza zadania (`round()` na liczbie pikseli, dokladnie
jak w `CuzkClient.export_image`), wiec moze roznic sie od zadanego o **≤ ½
piksela** na krawedzi. BREAKING dla konsumentow sidecarow: inna
wartosc `transform.horizontal`, niepuste `transform` dla kafli TM33.
Sciezka SM5 (DMR 4G z openzu) jest nietknieta — pliki przychodza w 5514.
Regula "nie ufaj reprojekcji serwerowej" jest wiazaca takze dla przyszlych
zrodel DE/SK sterowanych serwerowym parametrem ukladu.

**Zywa weryfikacja fixu (2026-08-11, dane CUZK+GUGiK,
`seam/verify/verify-report.md` — kopia:
`docs/research/2026-08-11-adr024-verify-report.md`):** kontrola tresci (dopasowanie do
referencji natywnej 5514 metoda minimum RMS w skanie przesuniec ±2 m/0,25 m)
potwierdza fix na obu sciezkach, minimum dokladnie w (0,0) na obu:
godlo TM33 (`302_5550`, EPSG:3045) — RMS(0,0) = **0,016 m**; bbox
`--target-crs EPSG:2180` — RMS(0,0) = **0,031 m**. Porownanie z NMT PL
w pasie nakladki (szew Olzy) daje mediane CZ−PL = **−0,086 m** przy
korelacji **0,998** (zgodnie z pomiarem diagnozy powyzej: −0,083 m).
Kontrole negatywne (ten sam test na plikach sprzed fixu) odtwarzaja
oryginalne bledy (mediana +1,368 m, korelacja 0,499) — metoda jest wiec
czula na blad tej klasy, a zerowy wynik na plikach po fixie nie jest
artefaktem nieczulosci.

Dwa znane koszty lokalnego warpu, zaobserwowane przy tej weryfikacji —
kandydaci do optymalizacji w etapie 2 (nie blokuja fixu):
(a) **utrata rzadkiego (sparse/tiled) ukladu TIFF serwera** — kafel
93% nodata: 527 KB (serwerowy tiled TIFF, puste kafle pominiete) → 4,0 MB
(lokalny zapis striped/gesty); dla kafli bez nodata roznicy praktycznie
nie ma. Kierunek naprawy: `tiled=True` + kompresja w profilu zapisu warpu;
(b) **halo interpolatora bilinear ~1 piksel na krawedzi waznosci**
(~0,5% pikseli produktu ma referencje juz w nodata; wartosci pozostaja
poprawne, GDAL renormalizuje wagi). Kierunek naprawy: maskowanie przed
interpolacja na krawedzi, jesli konsument liczy dokladna powierzchnie
pokrycia.

**Errata 1 (2026-09-29, pomiary historyczne przed poprawka; raport
`docs/research/2026-09-29-live-e2e-i-audyt-docs/L4-pogranicze-cz-report.md`):**
- **Diagnoza historycznej roznicy 1,25/4,92 m:** lokalny
  `build_pinned_transform` wybieral slowacki EPSG:4829 (0,5 m)
  zamiast czeskiego EPSG:1622 (1,0 m). Serwer poprawnie liczyl
  `imageSR=3045`, lokalna referencja byla zla. Serwerowe
  `imageSR=2180` nadal mylilo datum o ~135 m, dlatego zasada
  lokalnej reprojekcji pozostaje (errata 2 ponizej).
- **Kotwica siatki:** NW zadania, wymiar wynikowy zaokraglany
  do calkowitych pikseli (co najmniej 1), krawedz E/S moze
  odbiegac o do 1/2 px lub bardziej przy bboxie < 1/2 px.

**Errata 2 (2026-09-30, fala naprawcza, D1: tor CZ odmrozony):**
1. **Operacja S-JTSK (K2).** Pomiar roznicy EPSG:1622 − EPSG:4829
   w EPSG:3045: Cieszyn (+0,03; −1,16) m i kafel `302_5550`
   (+4,52; +2,03) m wyjasnia historyczne pomiary 1,25 m i 4,92 m.
   Serwer liczyl `imageSR=3045` poprawnie; mylna byla lokalna
   referencja ze slowacka operacja. Zakaz `imageSR` != 5514 nadal
   obowiazuje (dla 2180 serwer myli sie o ~135 m). Krok datum
   S-JTSK -> ETRS89/WGS 84 jest teraz jawnie przypiety do czeskiego
   EPSG:1622/1623 w `DATUM_STEP_PINS`, przed proba operacji;
   sam AOI PROJ nie wystarcza (prostokat Slowacji obejmuje Morawy,
   a dla zachodu CZ bywa pusta lista 5514 -> 2180).
   Nominalna dokladnosc w `KNOWN_PATHS` 5514 <-> 2180 i w sidecarze
   wynosi 1,0 m (zamiast 0,5 m). Samozgodnosc 0,016/0,031 m
   i mediana szwu −0,086 m nie dowodzily polozenia; niezalezny
   pomiar L4 wzgledem NMT GUGiK pod Karkonoszami dal dla starej
   operacji (−2,26; +0,61) m, a dla EPSG:1622 (+0,38; −0,03) m.
   Stare pliki z sidecarem `S-JTSK to ETRS89 (3)` sa pomijane
   bez przebudowy; CLI sygnalizuje `Info:`, odswiez je `--force`.
2. **Kafelkowanie (K6).** Realna granica serwera to ~8 Mpx,
   niezaleznie od sufitow wymiarowych 15000 x 4100 px.
   `MAX_EXPORT_PIXELS = 4_000_000` dzieli zadanie na zblizone do
   kwadratu kafle z kotwica NW, a `merge` scala je bez resamplingu.
3. **Siatka (N3).** Bbox dociagany do calkowitej liczby pikseli od
   NW przy pojedynczym zapytaniu, kafelkowaniu i warpie: dokladnie
   2 m/5 m na piksel. Nazwa pliku i `request.bbox` zachowuja zasieg
   sprzed snapu (E/S roznia sie do 1/2 px).
4. **Wynik pusty (N2).** Raster calkowicie nodata pozostaje wynikiem
   z kodem 0, ale CLI wyswietla `Warning:`; PL wycinek analogicznie
   (`PlCutoutResult.all_nodata`).
5. Poprzednie stwierdzenie „tor CZ zweryfikowany live — nie ruszamy”
   traci moc. Testy offline sa zielone; ponowne L4 na zywej usludze
   pozostaje brama przed wydaniem, nie dowod wykonany w tej fali.

**Errata 3 (2026-10-07, deduplikacja review D9):** stale z punktow (a)
i (f) zyja w `transform/crs.py`, wspolne dla toru CZ i wycinka PL (ADR-027):
`_WARP_MARGIN_PX` -> `WARP_MARGIN_PX` (nadal 4 px), `_HORIZONTAL_POLICY` ->
`CONTENT_POLICY` (`min_accuracy_m=1.0`, bez siatek z CDN).

---

## ADR-025: Mapowanie tekstura -> HSG i kanoniczny trojkat USDA (audyt 0.7.0)

**Data:** 2026-08-22
**Status:** Przyjeta

**Kontekst:** Audyt przedwydaniowy 0.7.0 (ustalenia A4-4, A4-8, A4-9) pokazal
dwa niezalezne problemy w `kartograf/hydrology/hsg.py`. (1) Progi klasyfikacji
tekstury byly przyblizeniem trojkata USDA, a nie trojkatem USDA: skosne
granice normy (`silt + 1.5*clay`, `silt + 2*clay`, `sand > 52`, `sand > 45`,
`silt < 28`) zastapiono liniami pionowymi/poziomymi (np. `clay <= 15 and
sand >= 70` zamiast `silt + 2*clay < 30`), mimo ze docstring deklarowal
"standard USDA soil texture triangle". Reguly istnialy dodatkowo w **dwoch
kopiach** — lancuch `if/else` w wersji skalarnej i odwrocona kolejnosc masek
w wersji tablicowej — wiec rozjezdzaly sie takze miedzy soba: normalizacja w
float32 dawala na granicy `clay = 15%` inna klase w skalarze niz w tablicy
(16 punktow symplexu, wszystkie zmieniajace HSG A/B), a lancuch skalarny mial
galaz nieosiagalna (`clay >= 40 and silt >= 40` po wczesniejszym bloku
`clay >= 40`). (2) Tablica `TEXTURE_TO_HSG` odbiega od klasycznej tabeli
TR-55, a docstring modulu podawal liste grup zgodna z TR-55 — czyli sprzeczna
z wlasnym kodem. Odstepstwo bylo swiadome (komentarze "Can be A/B depending on
structure", "Can be C/D"), ale nigdzie nieudokumentowane. HSG jest deklarowanym
wejsciem metody SCS-CN dla Hydrologa, wiec obie sprawy zmieniaja lub tlumacza
wynik u konsumenta.

**Opcje:**
- A) Zostawic uproszczone progi i poprawic tylko docstring. Odrzucona: roznica
  nie jest kosmetyczna (patrz liczby w "Konsekwencje"), a dotyczy gleb
  piaszczystych, dominujacych w Polsce.
- B) Poprawic progi osobno w kazdej z dwoch implementacji. Odrzucona: to wlasnie
  duplikacja regul wyprodukowala rozjazd skalar-vs-wektor; dwie kopie znow by
  sie rozjechaly.
- C) Jedna lista regul, wersja wektorowa jako zrodlo prawdy, skalar jako
  wrapper — wybrana.
- D) Przy okazji dociagnac `TEXTURE_TO_HSG` do tabeli TR-55
  (`sandy_loam` = A, `clay_loam`/`silty_clay_loam` = D). Odrzucona w 0.7.0:
  to zmiana produktowa (inne CN u konsumenta), nie naprawa bledu — patrz
  decyzja (b).

**Decyzja:**

(a) **Progi tekstur to kanoniczne reguly USDA** (Soil Survey Manual), trzymane
w jednej liscie `_USDA_RULES` jako pary `(nazwa, predykat)`; predykat dostaje
tablice float64 z udzialami w procentach (po normalizacji do sumy 100) i
zwraca maske. Kolejnosc ma znaczenie — wygrywa pierwsza pasujaca regula:

1. `sand`: `silt + 1.5*clay < 15`
2. `loamy_sand`: `silt + 1.5*clay >= 15 and silt + 2*clay < 30`
3. `sandy_loam`: `(7 <= clay <= 20 and sand > 52 and silt + 2*clay >= 30) or
   (clay < 7 and silt < 50 and silt + 2*clay >= 30)`
4. `silt`: `silt >= 80 and clay < 12`
5. `silt_loam`: `(silt >= 50 and 12 <= clay < 27) or (50 <= silt < 80 and clay < 12)`
6. `loam`: `7 <= clay <= 27 and 28 <= silt < 50 and sand <= 52`
7. `sandy_clay_loam`: `20 <= clay < 35 and silt < 28 and sand > 45`
8. `clay_loam`: `27 <= clay < 40 and 20 < sand <= 45`
9. `silty_clay_loam`: `27 <= clay < 40 and sand <= 20`
10. `sandy_clay`: `clay >= 35 and sand > 45`
11. `silty_clay`: `clay >= 40 and silt >= 40`
12. `clay`: `clay >= 40 and sand <= 45 and silt < 40`

Wersja tablicowa (`classify_usda_texture_array`, ta uzywana przez
`calculate_hsg_by_bbox`) jest zrodlem prawdy: liczy maski i wybiera pierwsza
pasujaca przez `np.select`. Wersja skalarna (`classify_usda_texture`) to
wrapper — te same reguly na tablicy jednoelementowej i `TEXTURE_NAMES[code]`.
Rownowaznosc obu funkcji jest przypieta testem na **calym** symplexie co 1%
(5151 punktow), ktory jednoczesnie dowodzi, ze reguly sa partycja: kazdy punkt
dostaje klase 1-12, `default` w `np.select` nigdy nie jest uzywany.
Normalizacja liczona **w float64** (`_normalize_pct`) — to usuwa rozjazd
float32 na granicy `clay = 15%` (A4-8); `np.divide(..., where=)` usuwa przy
okazji `RuntimeWarning: invalid value encountered in divide` dla pikseli bez
danych. Punkty o sumie 0 dostaja **jawny guard** -> `loam`: po normalizacji
`(0, 0, 0)` spelnia regule 1 (`silt + 1.5*clay = 0 < 15`), wiec bez guardu
byloby to `sand`. Nie jest to fikcja: piksele nodata potoku rastrowego sa
maskowane osobno, ale funkcja publiczna ma zwracac `loam` z decyzji, a nie
przez przypadkowe trafienie reguly.

(b) **`TEXTURE_TO_HSG` zostaje bez zmian** i jest swiadomie lagodniejsze niz
tabela TR-55: `sandy_loam` = B (nie A), `clay_loam` i `silty_clay_loam` = C
(nie D). Uzasadnienie: to klasy przejsciowe, ktorych faktyczna grupa zalezy od
struktury gleby i warunkow odplywu, a nie od samego skladu granulometrycznego;
wybor srodkowej grupy jest konserwatywny dla SCS-CN (nie zaniza odplywu tam,
gdzie gleba jest gorsza niz sugeruje sam sklad, i nie zawyza go dla gleb
piaszczysto-gliniastych). Zmiana tej tablicy zmienia CN u konsumenta
(Hydrolog), wiec jest **decyzja produktowa, nie naprawa** — poza zakresem
0.7.0. Docstring modulu nie powtarza juz listy grup wg TR-55 (byla sprzeczna z
tablica), tylko odsyla tutaj.

**Konsekwencje:** Klasyfikacja tekstury zmienia sie dla czesci obszaru
trojkata, wiec HSG (a przez to CN u konsumenta) zmienia sie dla tych samych
danych wejsciowych. Skutek policzony na siatce symplexu co 1% (5151 punktow,
wersja **tablicowa**, ta uzywana przez `calculate_hsg_by_bbox`), format
"bylo -> jest":

| zmiana HSG | punktow | udzial symplexu | zmiana tekstury |
|---|---|---|---|
| A -> B | 136 | 2,64% | `loamy_sand` -> `sandy_loam` |
| C -> B | 85 | 1,65% | `sandy_clay_loam` -> `loam` (36), `sandy_clay_loam` -> `sandy_loam` (28), `clay_loam` -> `loam` (21) |
| D -> C | 5 | 0,10% | `sandy_clay` -> `clay_loam` |
| **razem** | **226** | **4,39%** | (klasa tekstury zmienia sie dla 427 punktow = 8,29%) |

Kazda zmiana jest o **dokladnie jedna grupe**, w obie strony: 136 punktow
zaostrza sie (A -> B, wiekszy odplyw), 90 lagodnieje (C -> B, D -> C,
mniejszy odplyw). Najwieksza pojedyncza pozycja to gleby piaszczyste, dotad
awansowane z B na A przez pionowa granice `clay <= 15 and sand >= 70`
postawiona w miejsce ukosnej `silt + 2*clay < 30`; sa to gleby dominujace w
Polsce, wiec ta pozycja wazy w praktyce wiecej niz jej 2,64% powierzchni
trojkata.

Konsumenci (Hydrolog: HSG -> CN; Hydrograf: rastry HSG) dostana dla tych
pikseli inny wynik niz w 0.6.x — zgodny z norma. Wpis "Changed" w
`docs/CHANGELOG.md` niesie te sama tabele.

Przypis: raport weryfikacyjny audytu (A4-4) podaje mniejsze liczby — "3,4%,
136 B->A, 35 B->C, 5 C->D", zapisane w druga strone (referencja -> kod) i dla
wersji skalarnej. Roznica 226 vs 176 punktow nie wynika z kierunku zapisu:
tamta referencja byla osobna implementacja regul i inaczej domykala granice
klas. Dwa remisy na granicy rozstrzyga u nas kolejnosc regul z punktu (a):
`clay = 20%` przy `sand > 45` i `silt < 28` idzie do `sandy_loam`, nie do
`sandy_clay_loam` (28 punktow), a `clay = 27%` przy `20 < sand <= 45` idzie do
`loam`, nie do `clay_loam` (22 punkty). Wiazace dla konsumentow sa liczby z
tabeli powyzej — policzone testem wprost na implementacji z punktu (a).

---

## ADR-026: Uklad data/ per produkt — segmenty i szablony w deskryptorach

**Data:** 2026-08-28
**Status:** Przyjeta — uzupelniona przez ADR-030 (pliki w `<segment>/kampanie/`, sciezka standardowa = dowiazanie twarde albo kopia; errata 2) i ADR-036 (`<segment>/versions/`; errata 3); zastepuje ADR-013 i realizacje ukladu z ADR-005, uzupelnia ADR-017 (domyka odroczenie)

**Kontekst:** Plaski uklad `data/` nie kodowal kraju ani ukladow (`nmt_1m/`
obok `cz_dmr5g/`; PL-2000 dzielil katalog z PL-1992; ten sam arkusz w KRON86
i EVRF2007 mial JEDNA sciezke — drugie pobranie: skip albo nadpisanie).
Federacja niemiecka (kilkanascie zrodel DEM, research 2026-08-10) rozsadzilaby
korzen katalogu.

**Opcje** (rozstrzygniecia D1-D8 w sekcji 2 specu
`docs/superpowers/specs/2026-08-28-uklad-data-i-target-crs-pl-design.md`;
ponizej tylko warianty tam nazwane):
- A) Utrzymanie plaskiego ukladu ADR-013 (`nmt_1m/`, `nmpt/`, `orto/`,
  `cz_dmr5g/`) — stan sprzed 0.7.0 opisany w Kontekscie
- B) **Wariant A z D1**: `data/<produkt>/<segment>/...`, `landcover/` bez zmian
  — przyjety
- W obrebie B odrzucono trzy zwezenia: uklad poziomy tylko dla NMT (zakres
  odroczenia z ADR-017) — D2 rozciaga go na WSZYSTKIE produkty PL; dopisek
  ukladu poziomego takze dla CZ — D4 odrzuca jako redundancje (nazwa
  datasetu wyznacza uklad 1:1); rozdzielczosc w kazdym segmencie — D5
  zostawia ja tylko tam, gdzie jest parametrem API (NMT/NMPT)

**Decyzja (D1-D8 zatwierdzone przez uzytkownika 2026-08-28):**
`data/<produkt>/<segment>/...`, segment = `<kraj>_<uklad>[_<wariant>][_<vcrs>]`
lowercase. Uklad poziomy PL zawsze jawnie (`pl_1992`/`pl_2000`); pionowy
zawsze jawnie (`kron86`/`evrf2007`/`bpv`; jedynym produktem bez pionowego
jest orto); CZ bez dopisku poziomego (nazwa datasetu wyznacza uklad 1:1,
natywnie 5514); rozdzielczosc tylko tam, gdzie jest parametrem API
(NMT/NMPT). `SourceDescriptor.storage_subdir` staje sie SZABLONEM
z placeholderami `{uklad}`/`{vcrs}`; `resolve_subdir()` wypelnia przez
`str.replace` (czesciowe wypelnienie legalne, vcrs lowercased), FileStorage
rozwiazuje `{uklad}` per godlo (regula `path_parts`: kropki=2000, inaczej
1992) i waliduje zero klamer (`ValidationError` z nazwa wymiaru). Wycinki
`--bbox` lada w `<segment>/bbox/<coords><ext>` (konwencja ed939a0, wspolna
PL/CZ). `landcover/` bez zmian.

**Konsekwencje:** BREAKING na dysku (tabela migracji: CHANGELOG 0.7.0
i ARCHITECTURE.md sekcja 3). Nowe zrodlo (np. DE) = nowy wpis deskryptora,
zero zmian w kodzie sciezek. Konsument czytajacy `storage_subdir` wprost
dostaje szablon — pole bylo de facto wewnetrzne; uzyj `resolve_subdir()`.
FileStorage: nowy parametr `vertical_crs` (default "EVRF2007"); nieznany
`product` nadal passthrough (np. testowe `nmt_2000_1m`).

**Errata 1 (2026-09-29, audyt dokumentacji; zmiany kodu z fali review max
2026-09-28, zn. 7, 8, 11):** `resolve_subdir` odrzuca pusty/bialy wymiar
(`ValidationError`); dla kafli LAZ `{uklad}` wyznacza `LazTile.uklad`
(kaskada `uklad_xy` -> format godla -> "2000"), przekazywany jawnie
w `FileStorage.get_raw_path(..., uklad=)` — bez `uklad=` obowiazuje regula
formatu godla; `FileStorage(resolution=/product=)` mapuje na KLUCZ
deskryptora zamiast kopii szablonu (jedno zrodlo prawdy). Na zywo
2026-09-29 wszystkie segmenty powstaly zgodnie z tabela (NMT 1 m/5 m,
EVRF2007/KRON86, PL-1992/PL-2000, NMPT, orto, LAZ, CZ dmr5g/dmr4g bpv/evrf2007,
`bbox/`); pochodzenie i zgodnosc rekordu GUGiK reguluje ADR-028.

**Errata 2 (2026-10-07, ADR-030):** w produktach PL z kampaniami (NMT, NMPT,
orto) sciezka `<segment>/<hierarchia>/<godlo>.<ext>` nie jest juz zwyklym
plikiem: prawdziwe pliki leza w `<segment>/kampanie/<data>_<id>/<hierarchia>/`,
a sciezka standardowa to dowiazanie twarde (albo kopia) do najnowszej lokalnej
kampanii (ADR-030 (c), (d), errata 4). Segmenty z tej decyzji bez zmian.

**Errata 3 (2026-10-12, ADR-036):** w 0.8.0 arkusze PL NMT/NMPT/orto leza
jako wersje w `<segment>/versions/<hierarchia>/<etykieta>_<sha8>/`;
sciezka standardowa i `full_sheet/` to wylacznie dowiazania twarde do
wersji (bez kopii). Katalog `kampanie/` z 0.7.x nie jest uzywany. Land
cover i HSG leza w ukladzie `data/` (plan 3/3, ADR-036 D29-D33): segmenty
`landcover/pl_bdot10k_*`, `landcover/eu_corine_<rok>[_preview]`,
`soil/global_soilgrids_<wlasciwosc>_<glebokosc>_<stat>`,
`hsg/global_soilgrids_<glebokosc>_<stat>` (prefiksy w `storage_subdir`
deskryptorow, tokeny tresci lowercase), pod nimi `teryt/<T>`,
`bbox/<wsp>` albo hierarchia godla.

---

## ADR-027: --target-crs dla PL — scalony wycinek bbox (mozaika + pinned warp)

**Data:** 2026-08-28
**Status:** Przyjeta — czesciowo zastapiona przez ADR-035 (zrodlo wycinka w CLI i `download_pl_cutout`; API arkuszowe usuniete w 0.8.0, errata 2 ADR-035) i ADR-038 (nazwa `--target-crs`, wlaczanie wycinka flaga ukladu); uzupelniona przez ADR-030 (tylko przestarzaly tor arkuszowy); zastepuje czesc ADR-023 (`--target-crs` wylacznie dla CZ) i ADR-003 (bbox = WCS GeoTIFF)

**Kontekst:** `--target-crs` istnial tylko dla CZ; scenariusz "obszar
zainteresowania w jednym kraju + dociagniecie danych z drugiego" wymagal
warpa PL po stronie konsumenta — asymetria bez powodu innego niz historia
implementacji.

**Opcje** (D6 specu i jego sekcja 6; ponizej tylko warianty tam nazwane):
- A) Zostawic `--target-crs` flaga wylacznie czeska — stan sprzed 0.7.0
  opisany w Kontekscie
- B) **D6: "TAK, wchodzi w zakres; semantyka »jeden wycinek«"** (spec sekcja
  6) — przyjete
- W obrebie B odrzucono trzy warianty: wspoldzielenie warpa z torem CZ
  (refaktor `providers/cuzk/dmr.py::_warp_to_grid` zamiast osobnego
  `transform/raster.py`) — patrz Konsekwencje; scalanie takze BEZ
  `--target-crs` (spec 6.1: "Bez `--target-crs` zachowanie PL bbox bez
  zmian — lista arkuszy natywnie"); `capability="bbox_raster"` w sidecarze
  z litery spec 6.1 pkt 5 — zastapione przez `sheet_files`, bo kanal
  `bbox_raster` nie opisuje drogi, ktora te dane przyszly

**Decyzja:** `--bbox`/`--geometry` + `--country pl` + `--target-crs`
(produkt nmt) zwraca JEDEN plik `nmt/pl_1992_<res>_<vcrs>/bbox/<coords>.tif`:
arkusze pobieraja sie normalnie do swoich segmentow (dzialaja jako cache,
skip-existing standardowo), potem `mosaic_and_crop` (GTiff+CRS wymuszone —
ASC ich nie niesie) + lokalny warp `warp_to_grid` z WYMUSZONA operacja
`PinnedTransform.gdal_operation()` (maszyneria i pulapki ADR-024, w tym
axisswap dla celow northing-first). `EPSG:2180` = sam crop
(`transform: null`; od 2026-09-28 crop na siatce arkuszy — errata 2
nizej). Fail-fast operacji przed siecia; kazdy failed arkusz =
blad calosci (kod 1; zmienione 2026-09-28 dla arkusza bez danych GUGiK —
errata 1 (R5) nizej). Nazwa pliku niesie wspolrzedne w ukladzie WYNIKU.
Sidecar pisze CLI (od 2026-09-28 biblioteka, `write_pl_cutout_sidecar` —
errata 2 nizej): `horizontal_crs=target`, `transform.horizontal=
"pinned: ..."`, `nodata=-9999`, `extra.parent_request`; kanal
`sheet_files` (fakt: dane z arkuszy OpenData — kanal `bbox_raster` nie
istnieje dla 5m, a dla 1m deklaruje wylacznie KRON86). Wylaczenia 0.7.0:
godlo (produkt natywny 1:1), `--product nmpt|orto` (etap 2), `laz` (chmura
punktow), `--system 2000` (mozaika miedzystrefowa — etap 2). Na obszarze
transgranicznym `--country auto --target-crs` daje DWA wycinki (PL+CZ)
w tym samym ukladzie, wspolny `extra.parent_request`.

Obwiednia zrodla dostaje zapas: obwiednia celu wraca do EPSG:2180 i rosnie
o `WARP_MARGIN_PX = 4` piksele (`download/cutout.py`; do 2026-09-28 stala
CLI `_PL_WARP_MARGIN_PX`) — halo interpolatora, obrot ukladu docelowego.
Ten powiekszony bbox steruje TAKZE selekcja arkuszy w OBU trybach: `--bbox`
wybiera arkusze wprost z niego, a `--geometry` przy warpie bierze SUME godel
geometrii (per obiekt) i godel powiekszonego bboxa (R-01; dla celu EPSG:2180
zapasu nie ma, wiec arkusze wyznacza sama geometria). Od 2026-09-28 selekcja
w trybie bbox i w sumie R-01 ma jeszcze zapas 1 piksela (errata 2
nizej). Wycinek z `--geometry` obejmuje CALA obwiednie
geometrii — nie ma maskowania do obiektow, a `nodata` oznacza wylacznie
brak pobranego arkusza.

**Konsekwencje:** Symetria PL/CZ w trybie bbox; domkniety zalegly punkt
backlogu "Mozaikowanie arkuszy NMT PL". Warp PL to osobna funkcja
`transform/raster.warp_to_grid` — sparametryzowana kopia wzorca CZ, celowo
niewspoldzielona (testy ADR-024 patchuja `providers.cuzk.dmr.reproject`,
tor CZ zweryfikowany live tuz przed wydaniem). Nieudana budowa wycinka NIE
kasuje poprzedniego pliku wyniku (zapis atomowy przez `os.replace`, takze
z `--force`); tor CZ byl tu wyjatkiem i przy awarii kasowal plik docelowy.
(Korekta 2026-10-06, review D8/N7: tor CZ wola teraz ten sam
`transform/raster.warp_to_grid` — kopia `dmr._warp_to_grid` z kasowaniem
pliku usunieta, wynik kafla TM33 i wycinka bit w bit identyczny; nieudany
warp CZ zostawia poprzedni plik jak w PL.)
(Korekta 2026-09-28: wczesniejsze brzmienie tego akapitu i zdania o selekcji
arkuszy w `--geometry` opisywalo odwrotnosc zachowania kodu — review max
2026-08-30, znaleziska 5-6.)

**Errata 1 (2026-09-28, R5, review max zn. 2):** arkusz, dla ktorego GUGiK
nie ma danych (`NoCoverageError` — wszystkie warstwy skorowidza odpowiedzialy
i zadna nie ma arkusza), nie wetuje wycinka: w jego miejscu jest nodata,
CLI wypisuje `Warning:`, a sidecar niesie `extra.missing_sheets` (API
biblioteki: `PlCutoutResult.missing_sheets`). Kazda inna porazka pobrania
(siec, serwer, czesciowa awaria skorowidza — takze odpowiedz 2xx z raportem
wyjatku OGC) nadal przerywa wycinek przed
budowa, kodem 1 — chwilowy blad nie moze zostawic trwalej dziury w pliku,
ktory potem jest pomijany jako istniejacy. Kodem 1 konczy sie tez obszar,
dla ktorego danych nie ma ZADEN arkusz (`ValidationError`, wycinek nie
powstaje). Pod `--country auto` porazka toru PL przy sukcesie CZ to nadal
kod 0 i `Warning:` (ADR-023 pkt 4-5). Zastepuje "kazdy failed arkusz = blad
calosci" (Decyzja wyzej, spec 6.1 pkt 1). Powod: selekcja arkuszy to czysta
matematyka siatki godel, wiec obszar zadania (z zapasem) siega arkuszy spoza
pokrycia GUGiK — na morzu, w dziurach pokrycia 1 m, po czeskiej stronie
bboxa przygranicznego; jeden taki arkusz wetowal dotad caly wycinek, wiec
`--country auto --target-crs` na granicy dawal wtedy sam wycinek CZ.

**Errata 2 (2026-09-28, R1, R3, fakty 5-8 planu fali review max):**
- **Siatka arkuszy (R1, review max zn. 1).** Crop mozaiki jest rozszerzany
  NA ZEWNATRZ do siatki pikseli arkuszy (siatka wiekszosci zrodel, < 1 px na
  strone). Dla `EPSG:2180` wycinek to wiec obszar zadania rozszerzony
  o < 1 px, z wartosciami 1:1 z arkuszy — `transform: null` pozostaje
  prawda, a nazwa pliku niesie wspolrzedne ZADANIA. Przy warpie ten sam
  snap dostaje crop mozaiki (obwiednia zrodla), wiec warp nie dziedziczy
  przesuniecia o ulamek piksela. Powod: arkusze GUGiK 5 m maja narozniki
  pikseli na `5k + 2,5 m` (zmierzone na 1977 arkuszach), a crop kotwiczony
  w rogu zadania przesuwal tresc — dla bboxa na wielokrotnosciach 5 m
  o 0,5 px, z mieszaniem sasiednich kolumn. Selekcja arkuszy (tryb bbox
  i suma R-01) dostaje zapas 1 piksela, zeby przyciagniety crop nie siegal
  arkusza spoza listy. E2E na realnych arkuszach 5 m: 0 z 80 601 pikseli
  rozbieznych z arkuszem zawierajacym srodek piksela. Wycinki zbudowane
  wczesniej maja te same nazwy plikow — przebudowa z `--force` (CHANGELOG).
- **Normalizacja w VRT (fakty 5-6).** Kazdy arkusz trafia do `merge` przez
  VRT z jawnym EPSG:2180 i pasmem Float32, a wejscia sa sortowane: arkusz
  z `.prj` dopisanym przez Hydrograf scala sie z arkuszem bez niego (dotad
  `niezgodne CRS wejsc`), a arkusz z samymi liczbami calkowitymi (GDAL: Int32)
  nie obcina calej mozaiki do liczb calkowitych.
- **Arkusze PL-2000 = glosny blad (fakt 7).** Arkusz we wspolrzednych PL-2000
  (fallback skorowidza GUGiK pod godlem PL-1992) konczy budowe wycinka
  `ValidationError` zamiast cichej dziury nodata; reprojekcja takich arkuszy
  to etap 2.
- **Selekcja przy gornej krawedzi (fakt 8).** `find_sheets_for_bbox`
  z bboxem EPSG:2180 uwzglednia maksimum szerokosci na poludniku osiowym
  19°E — dotad gubila pas przy gornej krawedzi bboxa (6 arkuszy dla bboxa
  szerokiego na 20 km).
- **API biblioteki (R3, review max zn. 12).** Tor zyje w
  `kartograf.download.cutout`: `download_pl_cutout` albo kroki
  `prepare_pl_cutout` -> `select_pl_cutout_sheets` -> `run_pl_cutout`,
  eksport w `kartograf`. CLI jest nakladka (komunikaty, kody wyjscia),
  a sidecar sklada biblioteka (`write_pl_cutout_sidecar`). `run_pl_cutout`
  odrzuca wstrzyknietego providera o innym pionie albo rozdzielczosci niz
  wycinek — segment arkuszy niesie pion FAKTYCZNY (ADR-026).
- **Bez zmian (R2):** R-01 zostaje — dla jednego obiektu i dla bboxa "cala
  obwiednia" i "pierscien" (sam pas zapasu) daja ten sam zbior arkuszy,
  a rzadka geometria wieloobiektowa nie wystepuje w praktyce. **Etap 2
  (R6):** scalanie PL+CZ w jedna ciagla powierzchnie przygraniczna
  (wspolna siatka, EVRF2007 po obu stronach) — po zywym sprawdzeniu, jak
  GUGiK i CUZK przycinaja dane na granicy.
- Rozmiar (zn. 9): bez twardego limitu — plik posredni mozaiki przy warpie
  jest kompresowany, miejsce na dysku sprawdzane przed siecia (dolne
  oszacowanie), a CLI wypisuje `Info:` dla wycinkow >= 1 GiB.

**Errata 3 (2026-09-30, R5-lista, D3/D8, D4/D5/D9, N2/N4/N9):**
- **R5 w liscie i hierarchii.** `NoCoverageError` dla arkusza
  nie wetuje wszystkich pozostalych: niezaleznie od `--workers`
  probowane sa wszystkie, z `DownloadProgress.status="no_coverage"`
  i `Warning:`. Co najmniej jeden plik bez twardych awarii = kod 0;
  wszystkie bez danych albo jakakolwiek twarda awaria = kod 1
  (pelna lista porazek); pojedynczy arkusz bez danych = kod 1.
  Wycinek nadal wypelnia brak nodata i `extra.missing_sheets`.
- **Fazy siatki (D3/D8).** Przy EPSG:2180 `check_source_grid`
  wykrywa arkusze o fazie innej niz dominujaca i zgłasza
  `GridMismatchError(ValidationError)` z `.off_grid` i podpowiedzia
  zmiany celu (kontrakt wartosci 1:1 bez resamplingu). Dla
  EPSG:5514/3045 W1: `warp_to_grid(list[Path])` warpuje kazdy
  arkusz RAZ z jego wlasnej siatki na wynik, bez mozaiki tmp;
  `extra.off_grid_sheets` niesie liste odchylen. Wspolna faza
  zachowuje droge mozaika + warp. Przy skip odczytywane sa
  `missing_sheets` i `off_grid_sheets` z sidecara.
- **Pochodzenie i cache.** `extra.sheet_sources` wycinka mapuje
  godla pobranych arkuszy na `extra.source` wybrane wg ADR-028.
  `download_pl_cutout(cache=)` pozwala bibliotece wykorzystac cache
  rekordow (CLI go podpina, `--force` pomija).
  `PlCutoutResult.all_nodata` sygnalizuje wynik calkowicie pusty
  mimo pobranych arkuszy (`Warning:`, kod 0). Kontrola miejsca na
  dysku liczy brakujace arkusze raz i ponownie uzywa wyniku.

Opis biezacego przeplywu: `docs/ARCHITECTURE.md` sekcja 4.3.

---

## ADR-028: Wybor rekordu skorowidza GUGiK i `extra.source`

**Data:** 2026-09-30
**Status:** Przyjeta — uzupelniona przez ADR-030 (strategie kampanii `newest`/`all`, `--min-year`; regula wyboru `newest` bez zmian; awaria skorowidza: errata 2); czesciowo zastapiona przez ADR-031 (nazwy kluczy `extra.source`); zastepuje czesc ADR-020 (zaszyte warstwy i fallback), uzupelnia ADR-019 (`record_cache`)

**Kontekst:** GetFeatureInfo zwraca wiele rekordow: rozne kampanie, RGB/CIR,
rozdzielczosci 0,5 m i 1 m, arkusze PL-1992/2000 i potomne godla.
Wybor pierwszego URL-a zawierajacego fragment godla podmienial produkt
albo zakres. Awaria nowszej warstwy mogla cicho skierowac do starszej;
same URL-e w cache utrwalalyby niejasna decyzje bez pochodzenia.

**Opcje:**
- A) Pierwszy URL lub cichy fallback do podobnego godla/ukladu.
- B) Twardy filtr rekordu i jawne rozroznienie braku pokrycia od awarii.
- C) Scalanie niekompatybilnych rekordow na poziomie arkusza.

**Decyzja:** B (D4/D5/D9 oraz P2/P3/P7). `providers/pl/skorowidz.py`
parsuje szablon `var ... = [];`, komplet pol i adresy HTTPS z odpowiedzi
GetFeatureInfo; raport OGC lub brak szablonu to `DownloadError`, a nie
brak pokrycia. Zgodnosc wymaga godla jako calego tokenu, poziomego
PL-1992/2000 (dla PL-2000 rowniez strefy), zadanej rozdzielczosci
dokladnie 1 m/5 m i koloru RGB dla orto domyslnie
(`GugikOrtoProvider(color="CIR")` na jawne zadanie). Rekord bez ukladu
lub rozdzielczosci jest odrzucany z ostrzezeniem. Warstwy pochodza
z GetCapabilities, sa odpytywane od najnowszej; kazda probowana
warstwa musi odpowiedziec, pierwszy pasujacy rocznik konczy szukanie
(przy naruszeniu partycji warstwa/rok warning). Wsrod zgodnych
rekordow tej warstwy wygrywa maksymalny `(aktualnosc, dt_pzgik, url)`
bez preferencji `calyArkuszWypelnionyTrescia=TAK`.
Po wszystkich poprawnych pustych/niedopasowanych odpowiedziach
wynik to `NoCoverageError` z podpowiedzia (np. PL-2000 1:10000
z samymi potomkami -> `--scale 1:2000`), a awaria dowolnej
odpytywanej warstwy po 3 probach = `DownloadError`. Cache zapisuje
`{"source": {...}}` albo `{"no_coverage": true}` na TTL 7 dni;
`--force` omija cache zeby sprawdzic aktualny stan skorowidza.

**Konsekwencje:** Arkusz dostaje `extra.source` (URL, warstwa,
aktualnosc, rozdzielczosc i pozostale pola), wycinek PL
`extra.sheet_sources` (mapa godel na source). Schemat `kartograf-meta/1`
pozostaje bez zmiany wersji (pola addytywne), ale konsumenci nie
dostana juz po cichu 0,5 m zamiast 1 m, pliku PL-1992 za PL-2000
ani starszej kampanii po awarii skorowidza: otrzymaja `NoCoverageError`
lub `DownloadError`. `MetadataCache.get_url/set_url` zastapiono
`get_record/set_record`, stara tabela `url_cache` jest usuwana przy
inicjalizacji (ADR-019). Sidecar arkusza PL-2000 deklaruje rzeczywisty
`horizontal_crs` strefy EPSG:2176-2179.

**Errata 1 (2026-10-06, review-2 N4, E14, E17, D16):**
- "po 3 probach" (tu i w errata 3 ADR-020 z 2026-09-30 "Zapytania transportowe
  maja 3 proby"): od ca4d004 ponawiane sa tylko blad sieci, HTTP 429 i 5xx
  (do 3 prob, `Retry-After` wydluza przerwe); inne 4xx (403/404) koncza
  przy pierwszej probie z `DownloadError.status_code`
  (`transport/http.py::is_retryable`).
- "`--force` omija cache": od E14 `--force` otwiera
  `MetadataCache(refresh=True)` — odczyt jest chybieniem, ale swiezo wybrany
  rekord (albo brak pokrycia) jest ZAPISYWANY; od D16 tak samo w torze CZ
  dla indeksu arkuszy SM5.
- "Sidecar arkusza PL-2000 deklaruje rzeczywisty `horizontal_crs` strefy":
  sidecar opisuje uklad PLIKU — GUGiK publikuje czesc arkuszy PL-2000
  strefy 7 we wspolrzednych EPSG:2180; wtedy `horizontal_crs` =
  EPSG:2180, deklaracja rekordu zostaje w `extra.source.uklad`, a CLI
  drukuje `Warning:` (E17).

**Errata 2 (2026-10-07, ADR-030 errata 5):** zdanie z Konsekwencji
"konsumenci nie dostana [...] starszej kampanii po awarii skorowidza" ma
jeden jawny wyjatek: `newest` przy bledzie TRANSPORTU skorowidza (siec,
429, 5xx) i istniejacej lokalnej kampanii arkusza uzywa tej lokalnej
kampanii — z `Warning:` i polem `unverified` w wyniku, nigdy po cichu.
Awaria inna niz transport, `all`, `--min-year`, `--force` albo brak
lokalnej kampanii = `DownloadError` jak dotad.

---

## ADR-029: Wybor kafli LAZ wg pokrycia obszaru i pobieranie LAZ w bibliotece

**Data:** 2026-10-07
**Status:** Przyjeta — uzupelniona przez ADR-030 (`--campaigns all`/`--min-year` dla LAZ; errata 1) i ADR-032 (przedzial lat i pokrycie referencji; errata 2); zastepuje czesc ADR-021 (regula newest-per-tile), uzupelnia ADR-023 ((f).1 obejmuje LAZ)

**Kontekst:** ADR-021 deduplikowal kafle po godle (najnowszy `akt_rok`
per godlo). Kafle PL-1992 i PL-2000 tego samego miejsca maja rozne godla,
wiec E2E 2026-10-06 (C13, obszar w2 w Warszawie, 50 x 50 m) dostal dwa
kafle: 2022/PL-2000:S7 (250 MB) i 2025/PL-1992 (50 MB) — zdublowany obszar,
a "najnowszy rocznik" nie byl gwarantowany per obszar. Ponadto petla puli
watkow, sidecar kafla i porazki kafli zyly tylko w CLI (review-1 D17), a
sidecar LAZ nie niosl `extra.parent_request` (review-2 N15; errata ADR-023
pkt 8 o tym wyjatku usunieta wraz z ta naprawa).

**Opcje:**
- A) Dedup po godle (stan) — nie laczy ukladow ani kampanii o innym ciecu.
- B) Dedup po obwiedni z WFS — obwiednia obroconej ramy (EPSG:2180)
  wystaje poza nia o ~15 m w naroznikach: falszywe "pokrycie".
- C) Zachlanny wybor po ramie kafla (`msGeometry`) od najnowszego roku,
  porownanie w EPSG:2180 z tolerancja krawedzi.
- D) Pobierac wszystko i zostawic wybor uzytkownikowi (`--year`).

**Decyzja:** C. `GugikLazProvider.select_tiles` (i `discover_tiles` =
`select_tiles(...).tiles`) odpytuje roczniki jak dotad, odrzuca kafle
ponizej `--min-density`, a potem `select_newest_cover` przeglada kafle
od najnowszego `akt_rok` (w roku: nowsza `akt_data`, wieksza gestosc,
godlo, URL). Kafel jest pomijany, jesli jego czesc wspolna z obszarem
zadania jest pokryta suma wybranych juz kafli, kazdy powiekszony o
`COVERAGE_TOLERANCE_M` = 1 m; kafel wnoszacy niepokryty kawalek zostaje.
Z `--year` regula dziala w obrebie tego roku. Rama kafla to wielokat
`msGeometry` (osie N,E dla URN, jak envelope), znormalizowany do
wypuklego czworokata (`core/coverage.py`: wierzcholki wspolliniowe do
10 cm usuwane — boki rownoleznikowe arkuszy PL-1992 sa lukami ~3 cm).
Zasady ostroznosci (watpliwosc = pobierz): pokrywa tylko kafel
`czy_ark_wypelniony` != `NIE` (rama arkusza niepelnego nie jest zasiegiem
danych — Wroclaw 2025 ma dwie dostawy NIE tego samego arkusza), i to
wylacznie rama albo tym samym godlem (nigdy obwiednia); kafel bez
geometrii zostaje; kafel, ktorego rama nie przecina obszaru (tylko
obwiednia) jest pomijany jako "outside". Pominiete kafle wraca
`LazTileSelection.superseded` (kafel + kafle pokrywajace); CLI drukuje
je jako `Info:` na stderr (takze z `-q`).

Tolerancja 1 m: ramy kafli roznych ukladow i kampanii nie leza krawedz
w krawedz, a pas wezszy niz 1 m to 2-4 rzedy punktow przy 4-20 p/m2 przy
bledzie polozenia 0,10-0,30 m (`blad_sr_syt`) — nie uzasadnia pobrania
kafla 50-250 MB; jednoczesnie jest 2-3 rzedy wielkosci mniejsza od
kafla (~500-1100 m), wiec nie ukryje realnej luki w nowszej kampanii.

Pobieranie przechodzi do biblioteki: `kartograf.download.laz`
(`download_laz_area`, `run_laz_download`, `write_laz_sidecar`;
`LazDownloadResult` z `downloaded`/`skipped`/`failed`/`superseded`), wzor
`download/cutout.py`. Porazka kafla nie jest wyjatkiem, trafia do
`failed`; CLI tlumaczy ja na `Error:` z pelna lista i kod 1. Sidecar
kafla niesie `extra.parent_request` w trybie `--bbox`/`--geometry`
(ADR-023 (f).1 obejmuje teraz LAZ; `countries` = `["PL"]`).

**Konsekwencje:** Obszar w2 pobiera jeden kafel (2025/PL-1992) zamiast
dwoch; starsze roczniki tylko jawnie (`--year`). Wynik zalezy od obszaru:
obszar wychodzacy poza nowsza kampanie dostanie takze starszy kafel
(caly — LAZ nie jest przycinany). `LazTile` ma nowe pola `footprint`,
`date`, `full_sheet` (addytywne, z wartosciami domyslnymi). Kafle
niepelne (`NIE`) nie wypieraja starszych pelnych — obszar moze wtedy
dostac oba. Biblioteka (Hydrograf) pobiera LAZ bez powielania CLI.

**Errata 1 (2026-10-07, ADR-030 (j)):** "starsze roczniki tylko jawnie
(`--year`)" — takze przez `--campaigns all`: wszystkie kafle, ktorych rama
przecina obszar, bez deduplikacji pokryciowej (kafel przeciety tylko
obwiednia nadal pomijany). `--min-year` jest dolna granica `akt_rok`
(z `newest` wybor wg pokrycia dziala na rocznikach od granicy) i wyklucza
sie z `--year`.

**Errata 2 (2026-10-10, ADR-032):** `--year Y` to przedzial `[Y, Y]`,
`--min-year`/`--max-year` sa domknietymi granicami `akt_rok`; `--year` nie
laczymy z zadna z granic. Przy fladze roku WFS odpytuje WSZYSTKIE roczniki
uslugi, po filtrze `--min-density` i pionu. Wybor referencyjny R =
`select_newest_cover` bez granic roku (wynik, jaki uzytkownik dostalby bez
flagi). Kazdy kafel R spoza przedzialu musi miec swoja czesc wspolna
z obszarem pokryta kaflami z przedzialu wg tej samej reguly ram i tolerancji
1 m. Rozne godla PL-1992/PL-2000 oznaczaja, ze konflikt wyznacza sie
pokryciem, nie rownoscia godla. Brak pokrycia czesci R = `YearRangeError`
z godlem referencyjnym, jego rokiem/ukladem i latami kafli przecinajacych
niepokryty fragment; zero pobran. W2 z `--year 2022` pokrywaja razem dwa
kafle PL-2000 (zaden sam), `--year 2023` ten sam godlo; Wroclaw
(`6.150.13.16.4`) z `--year 2025` to konflikt (rok 2025 ma tam tylko
dostawy `NIE`, referencja 2024 PL-1992 zostaje niepokryta). Rok, w ktorym
niepokryty fragment przecinaja tylko dostawy `NIE`, dostaje w komunikacie
dopisek `(tylko arkusze niepelne)` (decyzja uzytkownika 2026-10-10).
`discover_tiles` przyjmuje `min_year` i `max_year` jak `select_tiles`
(decyzja uzytkownika 2026-10-10, symetria). Fragment
bez kafli w jakimkolwiek roku pozostaje bez ostrzezenia jak dotad.
W samym przedziale `newest` zachowuje wybor ADR-029 (takze dla jawnego
`--campaigns newest`); `all` zachowuje brak deduplikacji pokryciowej.
Rocznik nieobecny w GetCapabilities nadal daje `DownloadError` przed
GetFeature, nie konflikt z konkretnym kaflem. Sidecar kafla dostaje
`request.max_year`/`min_year` i `year` (gdy granice rowne) oraz
`extra.acquisition_date`/`full_sheet`, gdy znane.

---

## ADR-030: Strategie kampanii (`newest`/`all`), `--min-year` i uklad `kampanie/` z dowiazaniem

**Data:** 2026-10-07 (decyzje uzytkownika)
**Status:** Przyjeta — czesciowo zastapiona przez ADR-031 (nazwy kluczy `extra.campaign`), ADR-032 (przedzial, skan i konflikt; errata 7) i ADR-036 (uklad `kampanie/`, automatyczne `newest`, kopia zamiast hardlinku; errata 9); uzupelniona przez ADR-033 (drugie dowiazanie `full_sheet/`; errata 8); uzupelnia ADR-026 (`kampanie/`), ADR-027 (wycinek tylko `newest`), ADR-028 (strategie; regula wyboru `newest` bez zmian), ADR-029 (LAZ: `all`, `--min-year`) i ADR-019 (`campaigns_cache`); errata 10: otwarte drobiazgi przegladu zamkniete (M-8: sidecar dowiazania usuwany po awarii zapisu)

**Kontekst:** Arkusz GUGiK ma czesto kilka kampanii (rozne daty pozyskania,
zlecenia, zrodla: skaning laserowy albo zdjecia lotnicze). Pomiar 2026-10-07
(`docs/research/2026-10-06-e2e-brzegowe-i-review/pokrycie-kampanii.md`):
najnowsza kampania bywa niepelna (N-34-139-C-a-3-1: 0,9 % danych starszej
pelnej kampanii; orto M-34-90-C-b-4-4: 3,2 %), a flaga
`calyArkuszWypelnionyTrescia` nie mierzy skali braku. Pokrycia nie da sie
wyznaczyc przed pobraniem: serwer `opendata.geoportal.gov.pl` nie obsluguje
HTTP Range, a geometria WFS skorowidzow (`.../WFS/Skorowidze`, `msGeometry`)
to rama arkusza, nie zasieg danych (errata w
`docs/research/2026-10-07-pobieraczek.md`). Dzis Kartograf pobiera wylacznie
najnowsza kampanie (ADR-028), plik w sciezce standardowej nie niesie
tozsamosci kampanii, a ponowne uruchomienie pomija istniejacy plik bez
sprawdzenia, czy pojawila sie nowsza kampania. Uzytkownik chce moc pobrac
wszystkie kampanie i skladac je sam (QGIS; uniwersalne narzedzie laczenia
kampanii planowane w 0.7.1).

**Opcje (strategie):**
- `newest` — najnowsza kampania (stan, ADR-028).
- `all` — wszystkie kampanie arkusza spelniajace twardy filtr ADR-028.
- `coverage` — najnowsza o pokryciu >= progu. ODRZUCONA: pokrycie znane
  dopiero po pobraniu (albo przerwanym pobieraniu) — zbedne obciazenie
  infrastruktury GUGiK.
- `mosaic` — najnowsza + starsze tylko w lukach, jeden plik zlozony.
  ODRZUCONA: skladanie kampanii nalezy do uzytkownika/narzedzia 0.7.1.
- Wskazanie konkretnej kampanii (`--campaign <id>`). ODRZUCONE: wymaga
  znajomosci identyfikatorow GUGiK, nikt tego nie uzyje.

**Opcje (uklad plikow wielu kampanii):** A) sufiks w nazwie pliku w
katalogu arkusza; B) najpierw kampania, potem hierarchia arkusza
(`kampanie/<kampania>/<hierarchia>/<godlo>.<ext>`); C) najpierw arkusz, potem
kampania; D) zawsze oryginalna nazwa pliku GUGiK. Wybrane B — jedna dostawa
GUGiK = jeden katalog, ktory w QGIS daje spojna mozaike kampanii (VRT),
a nazwy plikow i hierarchia godel zostaja bez zmian.

**Decyzje:**

(a) **Strategie.** CLI `--campaigns {newest,all}` (domyslnie `newest`);
biblioteka: parametr `campaigns="newest"|"all"` w `DownloadManager` (i
sciezkach, ktore go uzywaja). Dotyczy produktow PL z kampaniami w
skorowidzu: NMT (1 m, 5 m), NMPT, orto — we wszystkich trybach arkuszy:
godlo, lista `--bbox`/`--geometry`, hierarchia godla. Regula wyboru
`newest` = ADR-028 bez zmian (najnowsza `aktualnosc`, potem `dt_pzgik`,
URL; bez preferencji pelnego arkusza). `all` = kazdy rekord, ktory
przechodzi twardy filtr ADR-028 (godlo jako token, uklad, rozdzielczosc,
pion, wariant koloru orto), z kazdej warstwy uslugi.

(b) **`newest` sprawdza, czy jest nowsza kampania.** Kazde uruchomienie
rozwiazuje aktualny rekord najnowszy (z `MetadataCache.record_cache`, TTL 7
dni; po wygasnieciu albo z `--force` — zapytanie do skorowidza). Jesli plik
tej kampanii jest lokalnie — tylko zapewnienie dowiazania (d), bez pobrania.
Jesli nie — pobranie do `kampanie/` i przestawienie dowiazania. Istniejacy
plik w sciezce standardowej nie jest juz powodem pominiecia.

(c) **Tozsamosc kampanii i uklad.** Katalog kampanii `<data>_<id>`:
`<data>` = `aktualnosc` (data POZYSKANIA danych, RRRR-MM-DD), `<id>` =
identyfikator zlecenia — pierwszy segment liczbowy nazwy pliku w URL
(`.../NMT/83233/83233_1744736_<godlo>.asc` -> `83233`), przy braku takiego
segmentu `u<8 znakow sha1(URL)>`. Plik kampanii:
`<segment>/kampanie/<data>_<id>/<hierarchia godla>/<godlo>.<ext>` + sidecar
obok, np. `nmt/pl_1992_1m_evrf2007/kampanie/2025-04-27_83233/N-34/139/C/a/3/1/N-34-139-C-a-3-1.asc`.
Segment (ADR-026) bez zmian, takze wariant orto
(`orto/pl_1992_cir/kampanie/...`). Prawdziwe pliki leza WYLACZNIE w
`kampanie/` — dotyczy obu strategii.

(d) **Sciezka standardowa = dowiazanie do najnowszej kampanii lokalnie.**
`<segment>/<hierarchia>/<godlo>.<ext>` (sciezka z ADR-026, ta sama dla
konsumentow, m.in. Hydrografu) i jej sidecar `.meta.json` wskazuja plik
i sidecar najnowszej kampanii, jaka jest lokalnie — takze niepelnej (zgodnie
z `newest`). Kazde pobranie kampanii nowszej od celu dowiazania (przez
`newest` albo `all`) przestawia dowiazanie atomowo (tymczasowe dowiazanie +
`os.replace`). Metoda wybierana automatycznie, w kolejnosci:
1) dowiazanie symboliczne WZGLEDNE (Linux/macOS; Windows z trybem
dewelopera) — widac, na ktora kampanie wskazuje, `data/` mozna przenosic;
2) dowiazanie twarde (zwykly Windows na NTFS, udzialy bez symlinkow; ten sam
wolumin); 3) kopia + `Warning:` (FAT32/exFAT, inny wolumin). Uzyta metoda:
`extra.link` w sidecarze (`symlink|hardlink|copy`). Zweryfikowano
2026-10-07: symlink, hardlink i atomowa podmiana dzialaja na dysku lokalnym
i na udziale sieciowym CIFS SMB 3.1.1. Dowiazanie wiszace (usunieta
kampania) = plik brakujacy: kontrola istnienia sprawdza CEL, nie link.

(e) **Brak migracji.** Pliki sprzed tej zmiany (zwykle pliki w sciezce
standardowej) sa traktowane jak nieznane: `newest` pobiera najnowsza kampanie
do `kampanie/` i ZASTEPUJE stary plik (oraz jego sidecar) dowiazaniem.
Kartograf nie przenosi starych plikow do `kampanie/` na podstawie sidecarow
— ryzyko brakujacych/niepelnych metadanych; ponowne pobranie jest tanie.

(f) **`--min-year RRRR`** (obie strategie): dolna granica roku z
`aktualnosc` (data pozyskania, nie `dt_pzgik` — roznica dochodzi do roku:
2025-10-21 przyjeta do PZGiK 2026-07-10). `newest --min-year`: gdy najnowsza
kampania jest starsza od granicy — brak pokrycia (`NoCoverageError` z
podpowiedzia: data najnowszej kampanii; w trybie listy status
`no_coverage`/`Warning:` jak R5). `all --min-year`: kampanie od tego roku
wlacznie. Weryfikacja 2026-10-07: 1381 rekordow skorowidza (NMT 1 m/5 m,
NMPT, orto; KRON86/EVRF2007) — `aktualnosc` zawsze pelna data, `aktualnoscRok`
zawsze zgodny.

(g) **Odpornosc na zmiany nazw warstw.** Warstwy pochodza z GetCapabilities
(`LAYER_PATTERN`, bez list zaszytych — ADR-028/S4). Dla `--min-year`: rok
z nazwy warstwy sluzy WYLACZNIE do pominiecia zapytania — warstwa jest
pomijana tylko, gdy nazwa daje jednoznaczny GORNY rok (`2019`,
`2017iStarsze`) mniejszy od granicy. Warstwa bez roku (`Starsze`) albo
o nazwie niepasujacej do wzorca jest odpytywana zawsze. O wyniku decyduje
wylacznie `aktualnosc` rekordu. Warstwa, ktorej nazwa nie pasuje do
`LAYER_PATTERN`, daje ostrzezenie w logu (dzis jest po cichu pomijana —
zmiana schematu nazw nie moze gubic danych bez sladu); czy ma byc
odpytywana zamiast pomijana — rozstrzyga plan po przegladzie
`_fetch_wms_layers`.

(h) **Cache.** `record_cache` (najnowszy rekord) bez zmian semantyki;
`all` potrzebuje listy rekordow arkusza — nowa tabela (np.
`campaigns_cache`, klucz jak `record_cache`, TTL 7 dni, `--force` = refresh
jak E14). Granica `--min-year` NIE wchodzi do klucza: filtr dziala na
liscie/rekordzie po odczycie.

(i) **Sidecar.** Kazdy plik kampanii: `extra.campaign` = {`id`, `date`
(`aktualnosc`), `zgloszenie` (`numerZgloszeniaPracy`), `source`
(`zrDanych`/`zrodloDanych`), `full_sheet`, `dt_pzgik`} obok istniejacego
`extra.source`; `request` zapisuje `campaigns` i `min_year`; `extra.link`
w sidecarze sciezki standardowej.

(j) **Poza zakresem / zachowanie innych torow.** Wycinek PL (`--target-crs`,
ADR-027) z `--campaigns all` = `ValidationError` przed siecia (laczenie
kampanii — narzedzie 0.7.1); wycinek z `newest` bierze arkusze przez
dowiazania jak dotad. CZ (CUZK) nie ma kampanii: jawne `--country cz`
z `all`/`--min-year` = `ValidationError`; pod `--country auto` opcje
dotycza tylko czesci PL (`Info:`). LAZ: `newest` = ADR-029 (wybor wg
pokrycia obszaru); `all` = wylaczenie deduplikacji ADR-029 (wszystkie
roczniki spelniajace filtry), `--min-year` = dolna granica `akt_rok`,
wzajemnie wykluczajace z `--year`; uklad LAZ bez zmian (nazwa pliku =
oryginalna nazwa GUGiK, unikalna per kampania), bez dowiazan.

**Konsekwencje:**
- Konsument (Hydrograf) widzi te same sciezki; GDAL/rasterio ida za
  dowiazaniem. Narzedzia kopiujace `data/` moga kopiowac link zamiast
  danych — opisac w README.
- Uklad `data/` zmienia sie wewnetrznie (ADR-026 + `kampanie/`): `FileStorage`
  musi rozrozniac sciezke standardowa i kampanii; `list_files`/`delete`
  musza obslugiwac dowiazania (delete standardowej = usuniecie linku, nie
  kampanii).
- `newest` wykonuje zapytanie do skorowidza po wygasnieciu cache rekordow
  (7 dni) dla kazdego arkusza — swiadomy koszt aktualnosci danych.
- Pierwsze uruchomienie po wdrozeniu pobiera ponownie arkusze z cache
  (brak migracji, (e)).
- Testy: tozsamosc kampanii z realnych URL (NMT/NMPT/orto), metody
  dowiazan z fallbackiem (symulacja braku uprawnien), atomowa podmiana,
  dowiazanie wiszace, `--min-year` na surowych body (warstwy jednoroczne,
  zbiorcze, `Starsze`, nazwa nieznana), `all` + skip per kampania.


**Errata 1 (2026-10-07, plan `docs/research/2026-10-07-plan-adr030.md`,
weryfikacja `docs/research/2026-10-07-weryfikacja-planu-adr030.md`;
zaakceptowane przez uzytkownika):**
- (g) **[Q1]** Warstwa GetCapabilities o nazwie niepasujacej do
  `LAYER_PATTERN` NIE jest odpytywana (zamiast "odpytywana zawsze"):
  realne GetCapabilities zawieraja `default`, `WMS` i (orto)
  `SkorowidzeOrtofotomapyZasiegi*`, a odpowiedz spoza szablonu skorowidza
  przewraca arkusz (`DownloadError`). Nazwa z rodziny produktu (np.
  `Skorowidz...NMT...`), ktora nie pasuje do wzorca, daje `logger.warning`
  — zmiana schematu nazw nie ginie bez sladu. Warstwa `Starsze` (bez roku)
  pasuje do wzorca i jest odpytywana zawsze.
- (g) **[Q5]** Pomijanie warstw wg roku z nazwy dziala TYLKO w `all`.
  `newest --min-year` odpytuje warstwy jak dotad (od najnowszej), zeby
  `record_cache` nie zalezal od granicy, a komunikat braku podawal date
  najnowszej kampanii.
- (d) **[Q7]** Sidecar sciezki standardowej to ZWYKLY plik (kopia
  sidecara kampanii + `extra.link`, `extra.link_target`), zapisywany
  atomowo — nie dowiazanie: zapis przez symlink nadpisalby sidecar
  kampanii (`write_sidecar`, `_note_reuse`). Dowiazaniem jest tylko plik
  danych.
- (d) Dowiazanie NIGDY nie jest przestawiane na kampanie starsza od
  biezacego celu: przestawienie tylko na klucz `(aktualnosc, dt_pzgik, url)`
  scisle wiekszy niz klucz celu (rowny albo mniejszy = bez zmian). Klucz
  celu pochodzi z sidecara kampanii, a gdy ten jest nieczytelny — z nazwy
  katalogu `<data>_<id>` jako `(data, "", "")`, dolne oszacowanie
  (`download/links.py::campaign_key_of`). [Poprawione 2026-10-08:
  wczesniejsze brzmienie mowilo o porownaniu klucza `<data>_<id>`.]
- (j) **[Q2]** Wycinek PL (`--target-crs`) z `--min-year` = `ValidationError`
  przed siecia, kod 1 — tak jak z `--campaigns all`.
- (j) **[Q9]** Godlo CZ (jednoznacznie czeskie) pod `--country auto`
  z `--campaigns all`/`--min-year` = `Error:`, kod 1 (spojnie z
  `--product nmpt/orto` dla CZ). `Info:` (opcje dotycza tylko czesci PL)
  wylacznie dla obszaru `--bbox`/`--geometry`.
- (c) **[Q3]** Kampania o innym formacie pliku niz domyslny produktu (realnie
  `.xyz`, rekord 72675) jest zapisywana z rozszerzeniem z URL i NIE dostaje
  dowiazania. Gdy taka kampania jest najnowsza pod `newest` — arkusz konczy
  sie porazka (`DownloadError`), plik zostaje w `kampanie/`. (Dzis `.xyz`
  zapisywany jako `.asc` — blad, naprawiony ta zmiana.)
- (i) **[Q8]** `request.min_year` tylko, gdy podany; LAZ: `request.campaigns`
  tylko przy `all`.
- **[Q4]** Wycinek PL z `newest` jest pomijany, gdy plik wyniku istnieje
  (bez sprawdzania nowszych kampanii arkuszy) — odswiezenie przez `--force`.
- **[Q10]** Czesciowa porazka `all` na arkuszu (np. jedna kampania nie do
  pobrania) = twarda porazka arkusza (kod 1); pobrane kampanie zostaja,
  dowiazanie wskazuje najnowsza pobrana.
- **[Q6]** `all` dla orto moze oznaczac ~10 kampanii i GB danych na arkusz —
  bez limitu, opis w dokumentacji i `logger.info` z liczba kampanii.

**Errata 2 (2026-10-07, decyzje uzytkownika do pytan planu N-1..N-3):**
- **[N-1]** Sidecar pliku w `kampanie/` jest OBOWIAZKOWY: nieudany zapis
  sidecara kampanii = porazka pobrania tej kampanii (plik danych usuwany,
  `DownloadError`). Sidecar niesie tozsamosc kampanii. Pozostale sidecary
  (m.in. wycinka) zostaja best-effort. Brak sidecara kampanii jest odtad
  wylacznie skutkiem ingerencji uzytkownika; wtedy klucz kampanii z nazwy
  katalogu `<data>_<id>`. Bez skanowania `kampanie/` w 0.7.0 (ryzyko R21).
- **[N-2] Zastepuje punkt [Q3] errata 1.** Format pliku wynika z pola
  `format` rekordu skorowidza, nie z rozszerzenia URL. Weryfikacja
  2026-10-07: wszystkie 1217 rekordow NMT/NMPT z rundy maja
  `format: "ARC/INFO ASCII GRID"` — takze rekord 72675
  (`72675_858113_N-33-69-A-d-3-2.xyz`), ktorego plik jest siatka AAIGrid
  (naglowek `ncols/nrows/xllcorner`, GDAL `AAIGrid`, 1 m, 92,5 % waznych
  pikseli); rozszerzenie `.xyz` to blad nazwy po stronie GUGiK. Rekordy
  orto nie maja pola `format` (zawsze `.tif`). Zasada: plik zapisywany
  z rozszerzeniem kanonicznym formatu (`.asc` dla ARC/INFO ASCII GRID),
  traktowany jak kazda kampania (dowiazanie jak zwykle), a po pobraniu
  format jest weryfikowany po tresci (naglowek AAIGrid / sygnatura TIFF).
  Rekord o formacie nieobslugiwanym (pole `format` inne niz znane) albo
  plik, ktorego tresc nie zgadza sie z formatem = porazka kampanii
  (`DownloadError` z nazwa formatu), nie ciche zapisanie pod `.asc`.
- **[N-3]** Obszar w calosci czeski pod `--country auto` z
  `--campaigns all`/`--min-year` = `Error:`, kod 1 (opcje kampanii dotycza
  tylko PL; CUZK nie publikuje kampanii w uslugach uzywanych przez
  Kartograf — rozpoznanie katalogu rastrow DMR 5G w toku). `Info:` tylko
  dla obszaru z czescia PL.

**Errata 3 (2026-10-07, decyzja uzytkownika po rozpoznaniu CUZK,
`docs/research/2026-10-07-cuzk-kampanie.md`):** mechanizm kampanii jest
WYLACZNIE dla PL (GUGiK) — bez wspolnej, kraj-niezaleznej abstrakcji
kampanii. CUZK nie udostepnia danych archiwalnych (ImageServer = jeden
raster biezacy; `Metadata/MapServer/20` daje tylko rok ostatniej
aktualizacji per obszar), wiec Czechy zawsze pobieraja najnowsze dane;
opcje kampanii dla CZ = `Error:` (I-3, N-3). Poza zakresem 0.7.0 (kolejne
wydanie): mechanizm aktualizacji danych CZ jako flaga CLI — wymuszenie
calkowicie nowego pobrania kompletu albo pobieranie czesciowe z
porownaniem zmian w metadanych (np. `ROK` z Metadata/20, ATOM `<updated>`,
`Last-Modified` plikow openzu).

**Errata 4 (2026-10-07, decyzja uzytkownika po weryfikacji na zywo T12,
`docs/research/2026-10-07-adr030-live/raport.md`):** sciezka standardowa
jest dowiazaniem WYLACZNIE twardym: metody `hardlink` -> `copy` (+ `Warning:`);
symlink USUNIETY (zastepuje kolejnosc symlink -> hardlink -> kopia z punktu (d)).
Powody: (1) symlink utworzony z Linuksa na udziale SMB (`reparse=nfs` albo
`mfsymlinks`) jest nieczytelny dla klientow Windows, ktorzy beda korzystac
z danych; (2) testowany udzial SMB przyjmowal cel symlinku najwyzej 77 znakow, wiec
czesc arkuszy dostawala symlink (PL-2000, cel 65-72 znaki), a czesc hardlink
(PL-1992, orto, 79-81) — zachowanie zalezne od dlugosci godla; (3) hardlink
dziala bez uprawnien na ext4/btrfs/APFS/NTFS i przez SMB (serwer pokazuje
zwykly plik); kampania lezy zawsze w tym samym segmencie co sciezka
standardowa (ten sam system plikow). Kopia zostaje dla systemow bez
hardlinkow (exFAT/FAT, sshfs/FUSE). `extra.link` = `hardlink|copy`,
`extra.link_target` bez zmian (sciezka wzgledna do pliku kampanii — jedyne
zrodlo celu, bo hardlink nie niesie wskazania). Istniejacy symlink (dane
deweloperskie sprzed wydania) = sciezka nieznana: `newest` zastepuje go
hardlinkiem, bez kodu zgodnosci. Kopiowanie `data/`: `rsync -aH` / `cp -a`
(bez zachowania hardlinkow powstaje duplikat). Errata obejmuje tez
Konsekwencje: ryzyko "narzedzia kopiujace moga kopiowac link zamiast danych"
przechodzi w ryzyko duplikatu (kopiowanie bez `rsync -aH`/`cp -a`), a
"dowiazania wiszacego" z punktu (d) nie ma — usuniety katalog kampanii (albo
brak sidecara standardowego) oznacza brak celu w `extra.link_target`, wiec
plik jest traktowany jak brakujacy i pobierany od nowa; `FileStorage.delete`
sciezki standardowej usuwa tylko te nazwe (plik w `kampanie/` zostaje).

**Errata 5 (2026-10-07, przeglad koncowy T11 (I-1) i poprawki FB; decyzja
uzytkownika, zapis 2026-10-08):** awaria skorowidza pod `newest` nie
przewraca arkusza, ktory ma lokalna kampanie (uzupelnia (b)). Warunki:
strategia `newest`, bez `--min-year`, bez `--force` (biblioteka:
`skip_existing`), `resolve_campaigns` konczy sie bledem TRANSPORTU (siec
albo timeout, HTTP 429, 5xx — `_is_transport_failure` w
`download/manager.py`, polityka `transport/http.py`; NIE `NoCoverageError`,
nie inne 4xx, nie raport OGC ani zly szablon odpowiedzi), a sciezka
standardowa wskazuje istniejaca lokalna kampanie (`linked_campaign(std)`).
Wtedy arkusz jest pomijany z lokalnej kampanii, dowiazanie zostaje bez
zmian, a wynik niesie blad: `SheetFetch.unverified`,
`DownloadResult.unverified` (`{godlo: blad}`). CLI drukuje `Warning: <godlo>:
skorowidz GUGiK niedostepny — uzyto lokalnej kampanii bez sprawdzenia nowszej
(<blad>)` (lista i hierarchia: jedno `Warning:` z liczba arkuszy i godlami),
kod wyjscia bez zmian. Wycinek `--target-crs` (ADR-027):
`PlCutoutResult.unverified` i sidecar `extra.unverified_sheets`
(`{godlo: blad}`), odtwarzane z sidecara przy pominieciu istniejacego wycinka
(CLI powtarza `Warning:` z dopiskiem `(z sidecara istniejacego wycinka)`).
`all`, `--min-year`, `--force`, brak lokalnej kampanii albo blad inny niz
transport = blad jak dotad (ADR-028: bez cichej degradacji; ADR-028
errata 2). Powod: chwilowa awaria GUGiK nie powinna przewracac ponownego
uruchomienia, gdy dane sa juz lokalnie; `Warning:` zachowuje jawnosc.
Biblioteka bez `MetadataCache` pyta skorowidz przy kazdym pobraniu arkusza —
zalecane podpiecie cache (`docs/USAGE.md` sekcja 2).

**Errata 6 (2026-10-09, domkniecie 0.7.1, przeglad dokumentacji):**
zapowiedz "narzedzie skladania kampanii w jedna powierzchnie — 0.7.1"
(Kontekst, opcja `mosaic`, decyzja, (j)) nie zostala zrealizowana: zakres
0.7.1 wyznaczyly wymagania Hydrografa (`docs/PROGRESS.md`, backlog "Do 0.7.1
— wymagania Hydrografa"), a skladanie kampanii nie jest przypisane do
zadnego wydania. Decyzja bez zmian (`mosaic` odrzucona jako strategia
pobierania; skladanie nalezy do uzytkownika albo osobnego narzedzia); stan
planu: `docs/SCOPE.md` 3.1. Komunikat CLI dla `--target-crs` z `--campaigns
all` (j) konczy sie od 0.7.1 na powodzie, bez odeslania do narzedzia.

**Errata 7 (2026-10-10, ADR-032 — wybor roku danych):**
- (f) **Granice i konflikt.** `--year Y` = `--min-year Y --max-year Y`,
  `--max-year U` wybiera lata <= U (bez dolnej granicy), para `[L, U]`
  wlacznie. Rok pochodzi z `aktualnoscRok`, inaczej z `aktualnosc[:4]`;
  `dt_pzgik` nie jest rokiem danych. Dla KAZDEGO przedzialu `newest`
  i `all` sprawdzaja wszystkie arkusze PRZED pobraniem. Arkusz bez
  jakichkolwiek danych = pominiecie z `Warning:` R5; z danymi, ale
  bez roku w przedziale = `YearRangeError(DownloadError)` i koniec
  calego zadania bez pobran przed `Warning:`. Wyjatek niesie
  `sheets` (godlo -> wszystkie dostepne lata), `min_year`, `max_year`
  i `hints`. Komunikat podaje do 20 godel, liste lat i podpowiedz
  JEDNOSTRONNEJ granicy obejmujacej wszystkie konflikty, o ile taka
  istnieje; inaczej bez podpowiedzi. To zastepuje `NoCoverageError`
  i `Warning:` dla samego `--min-year` ze starego (f).
- (g) **Pelny skan, zastepuje [Q5] erraty 1.** Dla kazdego przedzialu
  lista kampanii obejmuje WSZYSTKIE warstwy GetCapabilities:
  pomijanie po gornym roku z nazwy warstwy (`layer_upper_year`,
  `scanned_from`) usuniete. Tylko pelny skan pozwala podac wszystkie
  lata przy konflikcie, rowniez dla `all --min-year`; stare wpisy
  `campaigns_cache` ze `scanned_from` sa chybieniem. Pozostaje [Q1]:
  warstwy spoza `LAYER_PATTERN` nie sa odpytywane.
- (h) **Cache z przedzialem.** Bez granic `newest` nadal uzywa
  `record_cache`. Kazdy przedzial, takze samo `--min-year` z `newest`,
  czyta PELNA liste z `campaigns_cache` (TTL 7 dni); granice nie sa
  czescia klucza. `DownloadManager.check_year_range` odpytuje provider
  raz per arkusz bez granic (`campaigns="all"`), filtruje liste lokalnie
  i zachowuje lata dla sidecara; bledy skorowidza/WFS przerywaja cale
  zadanie przed pobraniem. Fallback lokalnej kampanii I-1 z erraty 5
  dziala tylko BEZ jakiejkolwiek granicy roku.
- (a), (d) **Strategia i dowiazanie (model A, ADR-032 pkt 3).** Flagi
  roku zawezaja dopuszczalne lata, `--campaigns` decyduje o liczbie
  lotow: `newest` (domyslnie, takze jawnie z kazda granica) = jeden
  najnowszy lot w przedziale, `all` = wszystkie loty z przedzialu,
  rowniez kilka w jednym roku. Sciezka standardowa wskazuje najnowszy
  lokalny lot wg `(aktualnosc, dt_pzgik, url)`, rowniez niepelny;
  reguly "nigdy wstecz" (d) nie zmienia ani pokrycie, ani przedzial —
  dowiazanie spoza przedzialu CLI zglasza `Info:`.
- (i) **Sidecar i pomiar.** `request.min_year`/`max_year` tylko gdy
  podane; dodatkowo `request.year`, gdy obie granice sa rowne,
  `request.campaigns` to rozwiazana strategia. W przeplywie z przedzialem
  `extra.available_years` zawiera wszystkie lata arkusza. Przy `all`
  sidecar sciezki standardowej dostaje `extra.flights` (loty od
  najnowszego; `id`, `date`, `full_sheet`, opcjonalnie `coverage`).
  Dla > 1 lotu w przedziale i najnowszego niepelnego (nie TAK)
  po pobraniu mierzy sie udzial waznych pikseli (ASC: bez NODATA,
  orto: nodata albo alfa), zapisuje `extra.coverage` kampanii
  (0..1, 4 miejsca). Orto bez nodata/alfa pozostaje niezmierzone.
  Gdy inny lot ma wieksze pokrycie, sciezka standardowa ma
  `extra.better_coverage` = jego id, a CLI wypisuje `Info:` na stderr
  (rowniez `-q`); dowiazanie nie zmienia celu. Najnowszy pelny =
  bez pomiaru i komunikatu. Przy odswiezeniu `None` usuwa nieaktualne
  `extra.better_coverage`, nie zapisuje `null`. Sidecar `request`
  opisuje pierwsze pobranie pliku (reuse nie nadpisuje go), a
  `extra.parent_request(s)` nie niesie granic roku.
- (j) **[Q2], CZ i wycinek.** `--year`, `--min-year`, `--max-year`
  i `--campaigns all` z wycinkiem PL `--target-crs` = `Error:`
  przed siecia (wycinek z najnowszych kampanii, nazwa bez roku).
  Dla zadania bez PL kazda flaga roku lub `all` = `Error:` (CUZK
  nie publikuje historii); na obszarze PL+CZ pod `--country auto`
  flagi dotycza tylko PL, CZ zostaje biezace i CLI drukuje raz
  `Info:`. Flagi roku nie zwezaja automatycznie zadania do PL.
  LAZ: regula i referencja pokrycia w erracie 2 ADR-029.

**Errata 8 (2026-10-10, ADR-033 — drugie dowiazanie):**
- (d) Obok sciezki standardowej istnieje drugie dowiazanie
  `<segment>/full_sheet/<hierarchia>/<godlo>.<ext>` do najnowszego
  lokalnego lotu zadania z `full_sheet is True` (skorowidz: TAK). Ta sama
  mechanika co sciezka standardowa (`download/links.py::ensure_link`,
  dawniej `ensure_standard_link`; hardlink -> kopia, nigdy wstecz wsrod
  lotow pelnych, sidecar z `extra.link_target`). Regula sciezki
  standardowej bez zmian.
- Konsekwencje dla `FileStorage`: `list_files()` pomija `kampanie/`
  i `full_sheet/`, `delete(godlo)` usuwa oba dowiazania z sidecarami,
  pliki w `kampanie/` zostaja.

**Errata 9 (2026-10-12, ADR-036, 0.8.0):** (1) uklad `kampanie/<data>_<id>/`
zastapiony wersjami `<segment>/versions/<hierarchia>/<data>_<id>_<sha8>/`
(etykieta wersji = dawna nazwa katalogu kampanii); (2) tryb domyslny nie
pobiera juz automatycznie nowszej kampanii przy `newest` — zostaje
lokalna wersja i informacja o nowszej (`--upgrade` / `update="upgrade"`);
(3) errata 4: kopia zamiast hardlinku znika — brak hardlinku to blad
pliku (D22); (4) `--force` pobiera ponownie, ale nie nadpisuje (ta sama
tresc = `unchanged`, inna = nowa wersja). Regula wyboru rekordu i klucz
"najnowszej" bez zmian.

**Errata 10 (2026-10-15, 0.8.0, zamkniecie "Otwarte drobne" z przegladu
T11/FB):** (1) wycinek `--target-crs` przy fallbacku I-1 bez `Warning:` -
nieaktualne: wycinek PL idzie z WCS GUGiK (ADR-035, od 0.8.0 `--cutout`),
bez skorowidza i bez fallbacku I-1 (`PlCutoutResult.unverified` usuniete
razem z torem arkuszowym, errata 2 ADR-035); (2) podwojna linia I-1 w CLI -
naprawione wczesniej (log managera na `debug`, jedno `Warning:`); (3)
`MetadataCache.__del__` `ImportError` przy zamykaniu interpretera -
naprawione w FB (`__del__` bez importow i wyjatkow); (4) M-7 podwojny INFO
liczby kampanii - naprawione (jeden INFO); (5) M-8 nieaktualny sidecar
dowiazania po awarii zapisu - poprawione: gdy zapis `<link>.meta.json` sie
nie uda (`write_link_sidecar`), stary sidecar jest usuwany (`Warning` w
logu), bo opisywalby poprzednia wersje. Dowiazanie bez sidecara to sciezka
nieznana: nastepne uruchomienie odtwarza dowiazanie i sidecar (samonaprawa
bez stanu posredniego, ktory klamie; test
`test_failed_sidecar_write_drops_stale_sidecar_and_heals`).

---

## ADR-031: Jezyk identyfikatorow — angielski (sidecar od 0.7.0, API/CLI do v1.0.0)

**Data:** 2026-10-08 (decyzja uzytkownika)
**Status:** Przyjeta — uzupelniona przez ADR-037 (jezyk tekstow dla uzytkownika, Z5); czesciowo zastepuje ADR-028 (nazwy kluczy `extra.source`) i ADR-030 (nazwy kluczy `extra.campaign`); uzupelnia ADR-022 (konwencja nazw kluczy sidecara `kartograf-meta/1`); errata 1: API/CLI po angielsku w 0.8.0 bez aliasow (pkt 2-3 nieaktualne)

**Kontekst:** Sidecar `<plik>.meta.json` (`kartograf-meta/1`, ADR-022) jest
kontraktem dla konsumentow (Hydrograf), a jego klucze powstawaly
przyrostowo: pola glowne i wiekszosc kluczy `extra` byly angielskie
(`horizontal_crs`, `parent_request`, `sheet_sources`, `full_sheet`), a czesc
polska — kopiowana z nazw pol rekordu GUGiK albo terminow domenowych:
`request.godlo`, `extra.source.{godlo, aktualnosc, aktualnosc_rok, uklad,
zrodlo_danych, numer_zgloszenia, skorowidz, dt_pzgik, kolor}`,
`extra.campaign.{zgloszenie, dt_pzgik}`, LAZ `extra.{godlo_kafla, rok,
gestosc}`, CORINE `extra.uwaga`, CZ `extra.podil`. W jednym slowniku
sasiadowaly `full_sheet` i `aktualnosc`, a ten sam fakt mial dwie nazwy
(`extra.source.numer_zgloszenia` i `extra.campaign.zgloszenie`). Ta sama
mieszanka dotyczy API (`godlo` w sygnaturach, `CampaignRef.zgloszenie`)
i CLI (`--godlo`). Schemat `kartograf-meta/1` nie byl jeszcze wydany
(wchodzi w 0.7.0), wiec zmiana kluczy teraz nie lamie zadnego wydania.
DEVELOPMENT_STANDARDS 9.4 rozstrzygala dotad jezyk docstringow,
komentarzy, commitow i dokumentacji, ale nie identyfikatorow.

**Opcje:**
- A) Zostawic mieszanke — zero kosztu, ale kontrakt sidecara utrwala sie
  w wydaniu 0.7.0 i kazda pozniejsza zmiana wymaga nowej wersji schematu.
- B) Angielskie klucze sidecara teraz, w niewydanym `kartograf-meta/1`;
  API/CLI stopniowo (aliasy), wylacznie angielskie od v1.0.0.
- C) Wszystko naraz (sidecar, API, CLI) w 0.7.0 — jedno lamanie, ale
  Hydrograf/Hydrolog i skrypty uzytkownikow musialyby zmienic wywolania
  bez okresu przejsciowego.

**Decyzja:** B.
1. **0.7.0 — klucze sidecara po angielsku**, schemat zostaje
   `kartograf-meta/1`, bez warstwy zgodnosci (zasada projektu: bez shimow,
   BREAKING w CHANGELOG): `request.godlo` -> `request.sheet` (wszystkie
   tory); `extra.source`: `godlo` -> `sheet`, `aktualnosc` ->
   `acquisition_date`, `aktualnosc_rok` -> `acquisition_year`, `uklad` ->
   `declared_crs`, `zrodlo_danych` -> `data_source`, `numer_zgloszenia` ->
   `survey_work_id`, `skorowidz` -> `index_url`, `dt_pzgik` -> `pzgik_date`,
   `kolor` (orto) -> `color`; `extra.campaign`: `zgloszenie` ->
   `survey_work_id`, `dt_pzgik` -> `pzgik_date`; LAZ: `godlo_kafla` ->
   `tile_sheet`, `rok` -> `year`, `gestosc` -> `nominal_density`; CORINE
   PNG: `uwaga` -> `note`; CZ SM5: `podil` -> `cz_share`;
   `extra.sheet_sources[]` wycinka: `godlo` -> `sheet`, `aktualnosc` ->
   `acquisition_date`. `teryt` zostaje — nazwa wlasna rejestru TERYT, nie
   slowo polskie do tlumaczenia. Wartosci (godla, nazwy warstw, daty, tresc
   `note`) zostaja w postaci zrodlowej. Mapowanie pol rekordu GUGiK na
   klucze sidecara jest w jednym miejscu (`SkorowidzRecord.to_source`).
2. **Kolejne wydania 0.x — angielskie nazwy w API i CLI rownolegle**
   z polskimi (aliasy obok obecnych nazw: parametry, atrybuty dataclass,
   flagi CLI, np. `sheet` obok `godlo`). Polska nazwa dostaje ostrzezenie
   o wycofaniu dopiero, gdy angielska jest dostepna.
3. **Od v1.0.0 wylacznie angielskie identyfikatory** (kod, API, CLI,
   klucze danych); polskie aliasy usuniete.

Zakres jezyka poza identyfikatorami bez zmian: dokumentacja (`docs/`,
`README.md`, `CLAUDE.md`) i commity po polsku, docstringi i komentarze po
angielsku (STANDARDS 9.4); komunikaty CLI dla uzytkownika (`Error:`,
`Warning:`, `Info:`) zostaja po polsku — 9.4 ich nie reguluje, a ta
decyzja dotyczy wylacznie identyfikatorow. STANDARDS 9.4 odsyla tutaj.

**Konsekwencje:**
- BREAKING w 0.7.0: konsument sidecara czyta nowe nazwy (tabela w
  `docs/ARCHITECTURE.md` 3.2 i w CHANGELOG 0.7.0, Breaking Changes).
- Stare lokalne sidecary (sprzed tej decyzji) nie sa migrowane; kod, ktory
  je czyta, traktuje brak nowego klucza jak brak informacji: sidecar
  kampanii bez `extra.campaign.pzgik_date` nie daje klucza dowiazania
  (dolne oszacowanie z nazwy katalogu kampanii, jak bez sidecara); wpisy
  `sheet_sources` bez `sheet` nie licza sie jako niepelne arkusze przy
  pominieciu wycinka; ostrzezenie E17 wymaga `request.sheet`. Odswiezenie:
  `--force`.
- Payload `record_cache`/`campaigns_cache` to ten sam slownik co
  `extra.source`; wpis z polskimi kluczami jest chybieniem cache
  (skorowidz odpytywany ponownie, wpis nadpisany) — bez `KeyError`.
- Etap API/CLI (pkt 2-3) wymaga osobnego planu: lista identyfikatorow
  (`godlo` w sygnaturach i flagach, `SheetFetch.godlo`,
  `CampaignRef.zgloszenie`, `LazTile.godlo` itd.), aliasy z testami obu
  nazw, ostrzezenia o wycofaniu i wpis w CHANGELOG kazdego wydania.
  Nazwy pol surowych odpowiedzi zewnetrznych (rekord GUGiK
  `aktualnoscRok`, `PODIL` CUZK) nie sa identyfikatorami Kartografa
  i sie nie zmieniaja.

**Errata 1 (2026-10-12, 0.8.0, decyzja uzytkownika):** pkt 2-3 decyzji
(aliasy w kolejnych 0.x, usuniecie w v1.0.0) nie obowiazuja. API i CLI
przechodza na angielskie identyfikatory w 0.8.0 jednym ruchem, bez aliasow
i bez ostrzezen o wycofaniu (0.8.0 i tak lamie CLI magazynem
wersjonowanym). Zakres: `godlo` -> `sheet` (`godla` -> `sheets`) we
wszystkich parametrach, atrybutach i nazwach metod (`download_by_sheet`,
`calculate_hsg_by_sheet`, `validate_sheet`, `horizontal_crs_for_sheet`);
`uklad` -> `system` (`SheetParser.system`, `LazTile.system`,
`FileStorage.get_raw_path(system=)`, szablon segmentu `{system}`),
`VALID_UKLADY` -> `VALID_SYSTEMS`; `CampaignRef.zgloszenie` ->
`survey_work_id` (jak klucz sidecara); `WMS_SKOROWIDZE_ENDPOINT(S)` ->
`WMS_INDEX_ENDPOINT(S)`. CLI: `--godlo` -> `--sheet` (`landcover
download`, `soilgrids hsg`), argument pozycyjny `download` -> `--sheet`,
`parse` zostaje pozycyjny (`SHEET`). Domyslna nazwa pliku land cover:
`..._godlo_<arkusz>` -> `..._sheet_<arkusz>`. Bez zmian: `dt_pzgik` (nazwa
pola GUGiK), komunikaty po polsku, nazwy pol surowych odpowiedzi
(`godlo`, `uklad_xy`, `ukladWspolrzednych*`), kolumny wewnetrznego cache
SQLite. Moduly wewnetrzne o polskich nazwach (`providers/pl/skorowidz.py`)
nie sa API publicznym i zostaja.

---

## ADR-032: Wybor roku danych: przedzial lat, zatrzymanie przy konflikcie

**Data:** 2026-10-10 (decyzje uzytkownika 2026-10-09 i 2026-10-10)
**Status:** Przyjeta — uzupelniona przez ADR-033 (`--full-sheet` z pkt 4; errata 1); czesciowo zastapiona przez ADR-036 (pkt 2: D14, pkt 4: D13; errata 3); errata 2: `--all-campaigns`/`all_campaigns` od 0.8.0; uzupelnia ADR-029 (LAZ) i ADR-030 (kampanie PL)

**Kontekst:** `--year` dzialal tylko dla LAZ, a `--min-year` w liscie
arkuszy pozwalal pominac arkusz, ktory mial wylacznie starsze dane.
Najnowsza kampania moze byc niepelna i w jednym roku bywaja liczne
loty. Uzytkownik potrzebuje tego samego wyboru roku NMT, NMPT, orto
i LAZ, weryfikacji calego zadania przed pobraniem i informacji
o dostepnych rocznikach. CUZK nie publikuje historii danych.

**Opcje:**
- A) Tylko `--year` z zatrzymaniem, bez symetrycznej gornej granicy:
  niespojny wynik `--year Y` i pary granic `[Y, Y]`.
- B) Domkniety przedzial z weryfikacja wszystkich arkuszy/kafli przed
  pobraniem i jawnym konfliktem; flagi roku wyznaczaja dopuszczalne
  lata, `--campaigns` liczbe lotow; bez zmiany reguly sciezki
  standardowej.
- C) Pobieranie czesciowe albo dowiazanie do najbardziej pelnego lotu:
  nie gwarantuje zadanego roku dla calego zadania, zmienia klucz
  dowiazania ADR-030 (d) i wymaga pokrycia znanego dopiero po pobraniu.

**Decyzja:** B (U1-U16 specu, w tym errata "model A" z 2026-10-10;
szczegoly i wyjatki w erracie 7 ADR-030 i erracie 2 ADR-029).
1. `--year Y` = zamkniety `[Y, Y]`, `--min-year L` = `[L, +inf)`,
   `--max-year U` = `(-inf, U]`, para = `[L, U]`; kazda granica to
   liczba calkowita 1900..2100, `L <= U`. `--year` z inna granica =
   blad. Rok NMT/NMPT/orto z `aktualnoscRok`, przy braku z
   `aktualnosc[:4]`; brak roku nie spelnia przedzialu. LAZ uzywa
   `akt_rok`. Warianty orto i pozostale twarde filtry ADR-028
   obowiazuja PRZED klasyfikacja rocznikow.
2. Najpierw PELNA lista danych dla kazdego arkusza (wszystkie
   warstwy skorowidza, jedna faza sprawdzania), dopiero potem
   pobieranie. Brak danych w zadnym roku daje pominiecie z
   `Warning:` jak R5. Dane tylko poza przedzialem chocby dla
   jednego arkusza = `YearRangeError(DownloadError)`, `Error:`
   z jego wszystkimi latami i podpowiedzia, zero plikow zadania.
   Podpowiedz jednokierunkowa jest podawana tylko, gdy obejmuje
   KAZDY konfliktowy arkusz; gdy obie obejmuja wszystkie,
   pokazane sa obie, rozdzielone `albo`. Brak wspolnej
   podpowiedzi = tylko lata. Awaria skorowidza/WFS w tej fazie =
   blad calego zadania bez pobran; I-1 (lokalna kampania)
   pozostaje wylacznie dla zadania bez granic.
3. Flagi roku sa tylko filtrem dopuszczalnych lat, a `--campaigns`
   decyduje o liczbie lotow na arkusz (model A): `newest`
   (domyslnie) = jeden, najnowszy lot w przedziale (klucz ADR-028),
   `all` = wszystkie loty z przedzialu do `kampanie/`, takze kilka
   w jednym roku. Kazda kombinacja jest dozwolona; ta sama regula
   dla NMT, NMPT, orto i LAZ. Sciezka standardowa wskazuje
   najnowszy lokalny lot wg ADR-028 i nigdy nie cofa sie na
   starsza kampanie lokalna (ADR-030 (d)); gdy przy przedziale
   wskazuje lot spoza przedzialu, CLI drukuje `Info:`, a biblioteka
   zwraca te informacje w wyniku.
4. Dla > 1 lotu w przedziale z jawnym `all` i niepelnego najnowszego
   mierzone jest po pobraniu pokrycie waznymi pikselami. Gdy inny
   lot ma wieksze pokrycie, CLI drukuje `Info:` na stderr,
   sidecar wskazuje ten lot (`extra.better_coverage`), ale
   dowiazanie pozostaje przy najnowszym. Najnowszy pelny (TAK)
   lub pojedynczy lot = bez pomiaru. Nierozstrzygnieta OPCJA
   na przyszlosc: jawna flaga zmiany reguly dowiazania na
   najnowszy pelny (`--full-sheet`) lub lot z pokryciem powyzej
   progu (`--min-coverage N`); wymagalaby innego klucza
   dowiazania, czasem dodatkowych pobran i rozwiazania kolizji
   z zasada "nigdy wstecz". Nie jest zaimplementowana.
5. LAZ: referencja to wybor wg ADR-029 bez flag roku,
   po filtrach gestosci i pionu. Wybor w przedziale zachowuje
   ADR-029 (`all`: bez deduplikacji); kazdy kafel referencji
   musi miec czesc wspolna z obszarem pokryta kaflami
   z przedzialu z tolerancja 1 m. Konflikt ma lata kafli
   przecinajacych brakujacy fragment i etykiete referencji,
   nie wymaga tego samego godla. Pusty obszar bez kafli
   w ZADNYM roku = brak danych jak dotad, bez ostrzezenia.
6. Wycinek `--target-crs` nie przyjmuje zadnej flagi roku:
   nazwa wycinka nie niesie rocznika i wycinek sklada
   najnowsze kampanie. Zadanie tylko CZ = blad z flagami
   PL przed siecia, obszar PL+CZ pod `auto` = `Info:`
   i biezaca wersja CUZK dla CZ.
7. Sidecary (schemat `kartograf-meta/1`, pola addytywne):
   `request.min_year`/`max_year` gdy podane i `year`
   gdy obie granice rowne, `request.campaigns` to
   rzeczywista strategia arkuszy. `extra.available_years`
   zawiera wszystkie lata arkusza przy zadaniu z przedzialem;
   kampanie z pomiarem maja `extra.coverage` 0..1, a sidecar
   sciezki standardowej przy `all` ma `extra.flights` oraz
   `extra.better_coverage` tylko, gdy starszy lot jest lepszy.
   LAZ: `extra.acquisition_date` i `extra.full_sheet`, gdy
   znane. `request` opisuje pierwotne pobranie, nie ostatnie
   uzycie; `extra.parent_request(s)` nie niesie granic roku.

**Konsekwencje:** Kazdy przedzial wymaga pelnej listy rocznikow
z uslugi, zamiast czesciowego skanu albo tylko `record_cache`
(TTL `campaigns_cache` = 7 dni). `YearRangeError.sheets`,
`.min_year`, `.max_year` i `.hints` sa dostepne w bibliotece.
Odmienny rocznik na jednym arkuszu zatrzymuje cala liste;
`--campaigns all` z przedzialem moze pobrac wiecej danych niz
`newest`. Pokrycie informuje, nie zmienia celu dowiazania.
W 0.8.0 `--campaigns {newest,all}` ma zostac zastapione
przelacznikiem bez wartosci (np. `--all-campaigns`), bo `newest`
jest zawsze domyslne (zmiana lamiaca CLI, backlog "Do 0.8.0").

**Historia:** pierwsza wersja (2026-10-10, przed merge) uzalezniala
strategie od granic: samo `--min-year` = `newest`, gorna granica =
`all`, jawne `newest` z gorna granica = blad. Audyt logiki flag CLI
wykazal asymetrie (`--min-year 1900` = 4 pliki, `--max-year 2100` =
23 na C14), redundancje i rozjazd z LAZ; uzytkownik przyjal model A
(2026-10-10).

**Errata 1 (2026-10-10, ADR-033):** opcja z pkt 4 (`--full-sheet`)
wdrozona BEZ zmiany klucza dowiazania: sciezka standardowa nadal wskazuje
najnowszy lot, a najnowszy pelny lot dostaje drugie dowiazanie
`full_sheet/`. W modelu A `--campaigns` dalej oznacza liczbe lotow
(`newest` = jeden), a `--full-sheet` doklada najwyzej jeden lot na arkusz
— tylko gdy najnowszy w przedziale nie jest pelny; z `all` jest bez
skutku. Przedzial lat filtruje takze lot pelny. `--min-coverage N`
pozostaje poza zakresem.

**Errata 2 (2026-10-12, 0.8.0):** CLI `--campaigns {newest,all}`
zastapiono przelacznikiem bez wartosci `--all-campaigns`, a parametr
biblioteki `campaigns="newest"|"all"` — `all_campaigns: bool = False`
(m.in. `DownloadManager` i pobieranie LAZ). Bez przelacznika / przy
`all_campaigns=False` pobierany jest najnowszy lot; z przelacznikiem /
przy `all_campaigns=True` wszystkie loty w dozwolonym przedziale.
Model A z pkt 3 pozostaje bez zmian: flagi roku filtruja dopuszczalne
lata, przelacznik okresla liczbe lotow. Pole sidecara
`request.campaigns` pozostaje tekstowa strategia `"newest"` lub `"all"`
(schemat `kartograf-meta/1` bez zmiany).

**Errata 3 (2026-10-12, ADR-036, 0.8.0):** pkt 2 — przy niedostepnym
skorowidzu i zakresie lat zadanie nie konczy sie juz zawsze bledem:
gdy KAZDY arkusz ma lokalna wersje z rocznikiem w zakresie, uzywane sa
lokalne wersje z ostrzezeniem; inaczej blad calego zadania bez pobran
(D14; tylko tryb domyslny). Pkt 4 — pokrycie lotu niepelnego jest
mierzone przy zapisie wersji (`extra.coverage` w sidecarze wersji,
D13), nie dopisywane pozniej; lot zadeklarowany jako pelny nie jest
mierzony i przy porownaniu liczy sie jako w pelni pokryty.

---

## ADR-033: Drugie dowiazanie do najnowszego pelnego lotu (`full_sheet/`, `--full-sheet`)

**Data:** 2026-10-10 (decyzje uzytkownika F-U1..F-U5)
**Status:** Przyjeta — czesciowo zastapiona przez ADR-036 (F-U5: `kampanie/`; errata 1); uzupelnia ADR-030 ((d): drugie dowiazanie; errata 8) i ADR-032 (pkt 4: `--full-sheet`; errata 1)

**Kontekst:** Sciezka standardowa wskazuje najnowszy lokalny lot, takze
niepelny (`calyArkuszWypelnionyTrescia = NIE`); E13 tylko o tym ostrzega.
Pomiar 2026-10-07 (577 grup godlo x produkt,
`docs/research/2026-10-06-e2e-brzegowe-i-review/pokrycie-kampanii.md`):
14 arkuszy z niepelnym najnowszym rekordem, w 8 istnieje starszy pelny
lot; pokrycie niepelnego od 0,9 % (NMT N-34-139-C-a-3-1) do 98,9 %.
Pomiar granic 2026-10-10
(`docs/research/2026-10-10-full-sheet-link/granica-pelne-pokrycie.md`):
TAK znaczy "pelne pokrycie w granicach Polski" — 13 plikow TAK, 0 px
nodata po stronie PL; nodata za granica (np. Slubice 75 %) to zagraniczna
czesc ramki. NIE nie mowi o skali braku.

**Opcje:**
- A) Zmiana klucza dowiazania standardowego na najnowszy pelny lot:
  lamie ADR-028/ADR-030 (d) i znaczenie sciezki standardowej dla
  konsumentow (Hydrograf).
- B) Mozaika lotow (nowy + uzupelnienie ze starszego): poza zakresem
  (SCOPE 3.1).
- C) Wybor wg zmierzonego pokrycia (`--min-coverage N`): pokrycie znane
  dopiero po pobraniu.
- D) Drugie dowiazanie obok standardowego do najnowszego lokalnego lotu
  pelnego + flaga dociagajaca ten lot.
- E) Jak D, ale dociaganie domyslne: zmienia liczbe lotow `newest`
  (model A ADR-032).

**Decyzja:** D.
- F-U1: dociaganie tylko z `--full-sheet`
  (`DownloadManager(full_sheet=True)`): gdy najnowszy lot w przedziale
  lat nie jest pelny, zadanie pobiera DODATKOWO najnowszy pelny lot
  z przedzialu (`resolve_campaigns(campaigns="all")`, pierwszy rekord
  `full_sheet is True`). Bez flagi `full_sheet/` powstaje tylko z lotow,
  ktore zadanie i tak ma lokalnie. Z `--campaigns all` flaga bez skutku.
  Sidecar kampanii takiego zadania: `request.full_sheet: true`.
- F-U2: arkusz bez lotu pelnego = brak pliku w `full_sheet/` (bez
  dowiazania "najlepszego" niepelnego); jeden `Warning:` z E13 dzieli
  arkusze na: z `full_sheet/`, bez pelnego lotu w skorowidzu
  (`DownloadResult.without_full`), pelny lot nie pobrany (podpowiedz
  `--full-sheet`).
- F-U3: dowiazanie pelne nigdy wstecz; gdy zostaje przy locie spoza
  przedzialu, `Info:` wspolny z U15
  (`DownloadResult.full_link_outside_range`).
- F-U4: wycinek `--target-crs` sklada sciezki standardowe bez zmian;
  `--full-sheet` z `--target-crs` albo LAZ = `Error:` przed siecia;
  CZ jak inne opcje kampanii (bez PL `Error:`, PL+CZ pod `auto` `Info:`).
- F-U5: jedno angielskie pojecie `full_sheet` (katalog `full_sheet/`,
  flaga `--full-sheet`, parametr `full_sheet=`) — tak nazywa sie juz flaga
  GUGiK w rekordach i sidecarach; robocza nazwa `full_coverage/`
  odrzucona, bo `coverage` w kodzie znaczy pokrycie zmierzone albo brak
  danych. `kampanie/` zostaje (zmiana nazwy to osobna, lamiaca decyzja).
- Kandydaci: wylacznie loty z `full_sheet is True` (NIE i brak flagi =
  nie pelny). I-1 (skorowidz niedostepny) i brak kandydatow zostawiaja
  istniejace dowiazanie pelne bez zmian; `--force` odswieza je jak
  standardowe; porazka dowiazania = porazka arkusza.

**Konsekwencje:** Gdy najnowszy lot jest pelny, oba dowiazania to
hardlinki jednego pliku (bez kosztu miejsca; przy kopii — dwie kopie).
Pierwsze uruchomienie po aktualizacji tworzy `full_sheet/` dla danych
lokalnych, bo przeplyw kampanii przechodzi przez kazdy arkusz takze przy
skip. `--full-sheet` pobiera najwyzej jeden dodatkowy lot na arkusz,
a pelna liste warstw skorowidza czyta tylko dla arkuszy z niepelnym
najnowszym lotem (`campaigns_cache`). `full_sheet/` ufa deklaracji
skorowidza; pelny = w granicach Polski (arkusze graniczne maja nodata
za granica). LAZ nie ma `full_sheet/`. Biblioteka: `SheetFetch.full_link`,
`.full_link_outside_range`, `.no_full_flight`; `DownloadResult.full_links`,
`.full_link_outside_range`, `.without_full`;
`FileStorage.get_full_sheet_path()`.

**Errata 1 (2026-10-12, ADR-036, 0.8.0):** F-U5 — "`kampanie/` zostaje"
nie obowiazuje: `full_sheet/` wskazuje najnowsza lokalna WERSJE lotu
zadeklarowanego jako pelny w `versions/`. Brakujacy najnowszy pelny lot
z zakresu to "brak lokalnej wersji" (tryb domyslny go pobiera).

---

## ADR-034: Wspolny mechanizm zapytan obszarowych (kawalki na siatce zrodla)

**Data:** 2026-10-10
**Status:** Przyjeta — uzupelniona przez ADR-035 (ASC 1 Mpx i NMPT) i ADR-042 (kawalki wycinka ortofotomapy; errata 1: zszycie bit w bit tylko dla NMT); uzupelnia ADR-023 (kawalkowanie CUZK) i ADR-024 (kotwica NW)

**Kontekst:** CUZK dzielil duze zadania `exportImage` przez `_tile_grid`
w kliencie, a GUGiK WCS `download_bbox` wykonywal jedno zapytanie bez
wyrownania do siatki zrodla. Pomiar KRON86 z 2026-10-10
(`docs/research/2026-10-10-wcs-limits/raport.md`) nie wykazal twardego
limitu WCS do 100 Mpx, ale host zrywal polaczenia. Serwer probkuje na
siatke zadania: bbox poza siatka zrodla daje cichy blad geolokalizacji
(tresc przesunieta wzgledem opisu o ulamek piksela). Siatka NMT 1 m
ma krawedzie `k + 0,5` m w dziewieciu zmierzonych rejonach; kawalki
z tej samej siatki skladaja sie bit w bit.

**Opcje:**
- A) Docelowo skladac wycinki PL z plikow arkuszy — odrzucone jako
  docelowa droga wycinkow na rzecz przygotowania zapytan WCS (D-U3);
  istniejacy wycinek nadal sklada arkusze do czasu prac nad (a).
- B) Pobierac kawalki rownolegle — odrzucone przy niestabilnym hoscie
  GUGiK i koszcie ponowienia duzego zapytania.
- C) Wyrownac CZ do siatki uslugi ImageServer — odroczone; pomiar
  CUZK z 2026-09-29, poza zakresem tej zmiany. Zachowano kotwice NW.
- D) Wspolny plan zapytan obszarowych, sekwencyjne pobieranie i skladanie
  na siatce zrodla tam, gdzie jest zmierzona.

**Decyzja:** D. Wewnetrzny modul `kartograf/transport/chunks.py` udostepnia
`GridSpec`, `ChunkLimits`, `Chunk`, `align_bbox`, `plan_chunks` i
`fetch_chunks` dla CUZK i GUGiK WCS, bez znajomosci URL-i i produktow.
Z podana siatka `align_bbox` rozszerza bbox NA ZEWNATRZ do jej linii;
bez siatki (CZ) zachowuje kotwice NW i calkowita liczbe pikseli przez
`round`. `plan_chunks` zachowuje podzial NW, polnoc-poludnie i
zachod-wschod. Budzet CUZK to 4 Mpx na kawalek pod praktycznym limitem
ok. 8 Mpx (oraz sufity 15000 x 4100 px); GUGiK NMT 1 m KRON86 GTiff
to 16 Mpx i do 40000 px na bok — budzet niezawodnosci, NIE limit serwera.
`fetch_chunks` pobiera kawalki sekwencyjnie, sklada je bez resamplingu
i usuwa pliki posrednie; `download_to` ponawia kazdy kawalek osobno.
Odpowiedzi WCS podlegaja `reject_error_document("WCS")`, rowniez przy
jednym zapytaniu. NMPT i orto nie maja zmierzonej siatki: pozostaja przy
jednym zapytaniu bez wyrownania (orto nie mierzono). GeoTIFF NMPT zwraca
RGB uint8 zamiast wysokosci — naprawa z wycinkami WCS w (a) (D-U6).
Pomiar WCS dotyczy tylko KRON86, bo endpoint EVRF2007 jest niedostepny
(D-U5). `mosaic_and_crop` bez `dtype=` odrzuca zrodla o mieszanych
typach pasm przez `ValidationError`, zamiast cicho przyjmowac typ
pierwszego pliku.

**Konsekwencje:** NMT KRON86 `download_bbox` GTiff moze miec zasieg
wiekszy od bboxa zadania o mniej niz 1 px z kazdej strony, a zadania
pow. 16 Mpx dziela sie na kawalki; sidecar zachowuje bbox zadania.
CUZK zachowuje dotychczasowy wynik i parametry zapytan. Wycinki PL
z WCS w (a) moga wykorzystac ten mechanizm (D-U3), ale obecny wycinek
PL nadal sklada arkusze; usuniecie parametrow arkuszowych publicznego
`mosaic_and_crop` pozostaje kandydatem do 0.8.0.

**Errata 1 (2026-10-16, ADR-042 D14, plan D):** "kawalki z tej samej
siatki skladaja sie bit w bit" dotyczy tylko NMT (siatka arkuszy 1 m).
Wycinek ortofotomapy PL w magazynie (`--cutout --coverage --resolution`,
`download/orto_cutout.py`) ma juz zmierzona siatke (DescribeCoverage
2026-10-16: krok 0,1 m obu coverage, Standard i High) i jest dzielony na
kawalki (budzet 4 Mpx pikseli coverage = 200 x 200 m, parzyste rozmiary
kawalkow), ale zszyte kawalki NIE sa rowne bit w bit jednemu zapytaniu
calego obszaru: serwer przeprobkowuje kazde zapytanie we wlasnym zasiegu
(pomiar 2026-10-16: 20 x 20 m przy 0,1 m - 75-93 % pikseli cwiartki
rozne, srednio 4 DN, max 89; 40 x 40 m przy 0,25 m - 70 % pikseli,
srednio 4,4 DN, max 120). Powtorzone to samo zapytanie daje te same
bajty, a kazdy kawalek jest odpowiedzia serwera skopiowana 1:1 (bez
resamplingu), wiec ten sam obszar i piksel daja powtarzalny wynik; inny
podzial na kawalki (inny obszar) moze dac w tym samym miejscu inne
wartosci pikseli. Czesc o orto zdania "NMPT i orto nie maja zmierzonej
siatki: pozostaja przy jednym zapytaniu bez wyrownania" dotyczy juz
tylko surowego `GugikOrtoProvider.download_bbox` bez `coverage` (plik
poza magazynem). Pomiary: `tests/fixtures/pl/orto_wcs/README.md`.

---

## ADR-035: Wycinki PL z WCS GUGiK z maska ladu PRG

**Data:** 2026-10-11
**Status:** Przyjeta; czesciowo zastepuje ADR-027 (zrodlo wycinka w CLI i `download_pl_cutout`), uzupelnia ADR-034 (ASC 1 Mpx i NMPT); errata 1: kawalek ASC NMPT 4 Mpx coverage; errata 2: tor arkuszowy usuniety w 0.8.0; errata 3: W-U3/W-U8 zastapione przez ADR-036 (D15, plan 2/3)

**Kontekst:** Wycinanie PL z mozaiki arkuszy OpenData (ADR-027) wymagalo
skorowidza, pobierania calych arkuszy i obslugi ich roznych faz siatki.
WCS moze odpowiedziec wprost na bbox, ale nie deklaruje nodata: poza
pokryciem oddaje 0,0, ktore jest tez prawdziwa wysokoscia na ladzie
(Zulawy). Zapytanie przesuniete poza siatke arkusza moze po cichu
przesunac geolokalizacje. Raport
`docs/research/2026-10-10-wcs-limits/raport.md` (pkt 2-8) wykazal
niestabilnosc hosta, zgodnosc WCS z arkuszem na siatce 1 m, kompozycje
lotow inna niz wybor ADR-028 i RGB uint8 zamiast wysokosci w NMPT TIFF.
Raport `docs/research/2026-10-11-wcs-cutouts/raport.md` (pkt 1-6)
potwierdzil dzialajacy WCS EVRF2007 przez ASC multipart, siatki 1 m
i 0,5 m, decymacje, koszt ASC i przynaleznosc punktow do PRG.

**Opcje:**
- A) Zostawic wycinki z arkuszy — pewne pochodzenie per kampania,
  ale koszt calych arkuszy i problemy faz siatki.
- B) WCS bez maski — szybka selekcja obszaru, lecz 0,0 na morzu
  i za granica udaje dane.
- C) WCS z zamiana kazdego 0,0 na nodata — gubi poprawne piksele
  o wysokosci 0 m na ladzie, szczegolnie na Zulawach.
- D) WCS z maska ladu PRG — odrzuca piksele spoza ladu,
  zachowujac 0,0 wewnatrz; przyjeta.

**Decyzja:** D, zgodnie z W-U1..W-U11 specu
`docs/superpowers/specs/2026-10-11-wcs-cutouts-design.md`:
- W-U1, W-U6: CLI `--bbox`/`--geometry --target-crs` oraz
  `download_pl_cutout` uzywaja WCS, nie arkuszy. Dawne API arkuszowe
  (`prepare_pl_cutout` + `select_pl_cutout_sheets` + `run_pl_cutout`,
  `build_cutout_from_sheets`, `PlCutoutSheets`) zostaje bez zmian
  zachowania, oznaczone jako przestarzale do usuniecia w 0.8.0;
  `prepare_pl_cutout` przygotowuje takze nowy tor WCS.
- W-U2, W-U7, W-U10: wycinki NMT i NMPT tylko 1 m (KRON86 i
  EVRF2007); 5 m odrzucane. Brak wyboru kampanii i roku.
- W-U3, W-U8: nazwa `<segment>/bbox/<coords>_<YYYYMMDD>.tif`;
  kazdy przebieg ponownie pobiera, nie pomija istniejacego pliku.
  Udany zapis atomowo podmienia plik tego samego dnia, nieudany
  zostawia poprzedni plik i sidecar.
- W-U4: EVRF2007 NMT i oba piony NMPT dostaja wysokosci z
  `image/x-aaigrid` (multipart ASC -> GeoTIFF float32);
  NMT KRON86 zachowuje `image/tiff` float32.
- W-U5, W-U11: przed WCS pobierana maska PRG
  `A00_Granice_panstwa - W02_Morze_terytorialne_RP -
  W03_Morskie_wody_wewnetrzne`, rasteryzowana wedlug srodka
  piksela (`all_touched=False`); poza nia nodata -9999.
  **0,0 na ladzie pozostaje danymi**, nie jest globalnie
  zamieniane na nodata.
- W-U9: bbox zrodla wyrownany NA ZEWNATRZ do siatki arkuszy 1 m
  `GridSpec(1.0, 0.5, 0.5)` przed pobraniem i podzialem na kawalki.
  NMPT o natywnym kroku 0,5 m daje wynik 1 m przez
  `SCALEFACTOR=0.5`; nad lotem 0,5 m to decymacja, nie srednia.
  Kawalki ASC maja limit 1 Mpx pikseli coverage (NMPT 1 m: 0,25 Mpx
  wyniku) i limit odczytu co najmniej 120 s, TIFF 16 Mpx (ADR-034).
  Kazde zapytanie ma parzysta szerokosc i wysokosc (zakres poszerzony
  o najwyzej 1 px na wschod/poludnie, przyciety po zszyciu): przy
  nieparzystym rozmiarze serwer, gdy przeprobkowuje, bierze srodkowy
  wiersz i kolumne z sasiedniego piksela zrodla (weryfikacja na zywo
  `docs/research/2026-10-11-wcs-cutouts-live/raport.md` pkt 3, 5).
  Reprojekcja EPSG:5514/3045 pozostaje lokalna z przypieta operacja.

**Konsekwencje:** WCS prezentuje najnowszy lot obszaru bez
doklejania starszych; nie wybiera najnowszego arkusza dokladnie
1 m wedlug ADR-028. Wycinek moze wiec miec inny lot niz pobrane
arkusze (raport 2026-10-10 pkt 8, 2026-10-11 pkt 4), a zer
wewnatrz maski nie uzupelnia sie starszym lotem. Sidecar opisuje
`bbox_raster`, `extra.source` WCS z `composition="server"`,
`extra.mask` PRG, `zero_pixels`, `all_nodata` i ewentualny
`parent_request`; brak `sheet_sources` w nowym torze.
`download_bbox` EVRF2007 i NMPT zwraca float32 z wysokosciami
na 1-metrowej siatce arkuszy, bez maski PRG i bez nodata.
Parametry arkuszowe `download_pl_cutout` i `mosaic_and_crop`
(`snap_to_source_grid`, `assign_crs`) odchodza w 0.8.0.
Stare decyzje ADR-027 i ADR-034 zachowuja opis stanu w chwili
podjecia; ten ADR okresla nowy tor. Weryfikacja na zywo (raport
2026-10-11-wcs-cutouts-live): wycinki NMT/NMPT obu ukladow = arkusz
tego samego lotu w 100 %; na wybrzezu (Gdynia, Hel, Mierzeja Wislana)
poza maska jest woda o wysokosci WCS ok. 0-0,3 m (mediana), zaden
piksel > 5 m, > 2 m: 0-1048 px na 1 km2; na ladzie zostaje 0-82 px 0,0.

**Errata 1 (2026-10-11, strojenie kawalkow ASC NMPT,
`docs/research/2026-10-11-nmpt-asc-tuning/raport.md`):** limit kawalka
ASC NMPT to 4 Mpx pikseli coverage (1 Mpx wyniku 1 m), nie 1 Mpx
coverage (0,25 Mpx wyniku) z W-U9; NMT EVRF2007 zostaje przy 1 Mpx,
limit odczytu 120 s bez zmian. Zawieszenia hosta (brak bajtu przez
300 s) trafialy kawalki kazdego rozmiaru, a kawalek 4 Mpx coverage
odpowiadal w 15-26 s jak 1 Mpx; mniej kawalkow to mniej ponowien.
Na zywo NMPT 2000 x 1000 px: 2 kawalki, 246 s (dotad 8 kawalkow,
1186 s), bit w bit z jednym zapytaniem.

**Errata 2 (2026-10-11, 0.8.0, warunek wstepny magazynu wersjonowanego
D16):** przestarzaly tor arkuszowy usuniety bez okresu przejsciowego:
`select_pl_cutout_sheets`, `run_pl_cutout`, `build_cutout_from_sheets`,
`PlCutoutSheets`, pola arkuszowe `PlCutoutResult`, parametry arkuszowe
`download_pl_cutout`, `mosaic_and_crop(snap_to_source_grid=,
assign_crs=)` oraz nieuzywany juz `GridMismatchError`. Wycinek PL
powstaje wylacznie z WCS; mozaike arkuszy sklada wywolujacy
(`mosaic_and_crop`, `check_source_grid`).

**Errata 3 (2026-10-12, ADR-036):** W-U3/W-U8 (nazwa z data, pobieranie
przy kazdym uruchomieniu) zastapione decyzja D15 magazynu wersjonowanego:
`bbox/<wsp>.tif` jako dowiazanie do najnowszej wersji, data tylko
w etykiecie wersji, domyslnie lokalna wersja (bez zapytan PRG i WCS),
`--force` pobiera ponownie. Zrealizowane w 0.8.0 (plan 2/3 magazynu);
pliki `<wsp>_<RRRRMMDD>.tif` z 0.7.x nie sa rozpoznawane (D10).

---

## ADR-036: Magazyn wersjonowany

**Data:** 2026-10-12 (spec zaakceptowany 2026-10-11, decyzje D1-D24; rewizje 2026-10-12, D26-D28 i D29-D33)
**Status:** Przyjeta — czesciowo zastapiona przez ADR-042 (D27: wycinek ortofotomapy w magazynie; errata 2); uzupelniona przez ADR-037 (arkusz CZ w publicznym API; errata 1) i ADR-042 (D23 miedzy wydaniami, sloty jednostek); czesciowo zastepuje ADR-030 (`kampanie/`, automatyczne `newest`, kopia), ADR-032 (pkt 2 i 4), ADR-033 (F-U5), ADR-035 (W-U3/W-U8) i ADR-003 (`DownloadManager.download_bbox`); uzupelnia ADR-026 (`versions/`; land cover i HSG w ukladzie `data/`)

**Kontekst:** Do 0.7.x magazyn mogl po cichu nadpisac dane: `--force`
nadpisywal plik kampanii, `newest` automatycznie przestawial sciezke na
nowsza kampanie, sidecar kampanii byl dopisywany (`parent_requests`,
`coverage`), a przy braku hardlinku sciezka standardowa byla kopia.
Nie bylo sposobu sprawdzenia aktualnosci bez pobierania.

**Opcje:**
- A) Zostawic `kampanie/` i dopisac sumy kontrolne.
- B) Wersje identyfikowane trescia (sha256) z niezmiennym sidecarem,
  zapis wylaczny, tryby aktualizacji i plan aktualizacji.

**Decyzja:** B, wg specu
`docs/superpowers/specs/2026-10-08-versioned-store-design.md` (D1-D24):
- uklad `<segment>/versions/<hierarchia>/<etykieta>_<sha8>/<nazwa>`
  (D17), etykieta `<data>_<id>` kampanii / edycja / data pobrania UTC;
- zapis: katalog roboczy `versions/.incoming/<host>_<pid>_<token>/`,
  jeden odczyt (sha256 + pokrycie, D20), `fsync`, wylaczny `os.link`
  (D18, D21), sprzatanie pozostalosci > 24 h (D19); ta sama tresc =
  `unchanged`, ta sama tresc z nowa etykieta kampanii = `relabeled`
  (nowy katalog z hardlinkiem, D23); sidecar wersji pisany raz
  (`extra.version`, `extra.coverage`, D12, D13), publikowany wylacznie;
- sciezka standardowa i `full_sheet/` = wylacznie hardlinki do wersji
  (D22; brak hardlinkow = blad), nigdy wstecz;
- tryby `update`: domyslny (lokalne wersje, brakujace pobierane, nowsza
  kampania tylko zglaszana — D5), `upgrade`, `force` (pobiera, nie
  nadpisuje), `check` = `check_updates` (plan `kartograf-plan/1`,
  niczego nie pobiera); `upgrade(plan)` sprawdza sygnal ponownie;
- skorowidz niedostepny: bez zakresu lat lokalna wersja + ostrzezenie
  (kazda strategia), z zakresem D14.

**Konsekwencje:** Plan 1/3 (2026-10-12) realizuje magazyn dla arkuszy PL
NMT/NMPT/orto (`DownloadManager`, CLI `--sheet`/`--bbox`/`--geometry`
bez `--target-crs`): `versions.py`, `updates.py`, `--check-updates`,
`--upgrade`, `--plan`, statusy wersji w CLI. `kampanie/` z 0.7.x nie
jest migrowany (ponowne pobranie, `Info:`). Plan 2/3 (2026-10-12)
obejmuje pozostale tory `kartograf download`: kafle LAZ, arkusze CZ
(TM33/SM5, przeniesione z CLI do `download/cz_sheets.py`), wycinki CZ
i wycinki PL z WCS w `bbox/<wsp>.tif` bez daty (D15); wspolna polityka
plikow bez kampanii `download/fetch.py`, plan z torem pozycji
(`download/plan.py`, `PlanItem.track`/`unit`), `--check-updates`/
`--upgrade`/`--plan` dla kazdego toru (przy `--country auto` jeden plan
PL i CZ). Plan 3/3 (2026-10-12): land cover (BDOT10k, CORINE, SoilGrids)
i HSG w ukladzie `data/` (D29-D33 nizej). Magazyn wymaga systemu plikow z hardlinkami; gdy system plikow
nie podaje stabilnych numerow i-wezlow (SMB bez `serverino`, `samefile`
falszywe dla hardlinku), dowiazanie potwierdza tresc: obie sciezki maja
wiecej niz 1 link, ten sam rozmiar, a sha256 dowiazania = sha256 z sidecara wersji
(pelny odczyt pliku tylko na takich udzialach). Kopia magazynu: `rsync -aH`.

Decyzje rewizji 2026-10-12 (plan 2/3):
- D26: plik LAZ = wersja per plik (nazwa `<zgloszenie>_<rekord>_<godlo>.laz`
  zmienia sie z nalotem), etykieta `<data>_<zgloszenie>`; wyjatek od D5 —
  nowszy nalot to nowe pliki, pobierane domyslnie, kafel z lokalna wersja
  nie jest pobierany ponownie (tylko `--force`).
- D27: `DownloadManager.download_bbox` usuniete (errata 2 ADR-003).
- D28: `Content-Length` nie jest sygnalem swiezosci.
- Sygnal per kanal dostepu (`AccessChannel.update_signal`, inwentaryzacja
  `docs/research/2026-10-12-signal-inventory/raport.md`):

| Kanal | Sygnal | Etykieta |
|---|---|---|
| arkusze PL NMT/NMPT/orto (skorowidz) | `index` | kampania |
| LAZ (rekord WFS) | `index` | kampania (D26) |
| WCS GUGiK (wycinki PL) | `none` | data pobrania |
| SM5 CUZK (`openzu`) | `http` (`ETag`, `Last-Modified` w `extra.http`) | data pobrania |
| `exportImage` CUZK (TM33, wycinki CZ) | `none` (`ETag` zalezny od zapytania) | data pobrania |
| BDOT10k (paczka powiatu) | `none` | data pobrania |
| SoilGrids (WCS) | `metadata` (wydanie z GetCapabilities, D29) | wydanie, np. `2.0` |
| CORINE CLMS | `metadata` (`characteristics_release_major_version` z katalogu CLMS, D29) | wydanie, np. `V2020_20u1` |
| CORINE podglad WMS (EEA/DLR) | `none` (D31) | data pobrania |
| HSG (pochodna) | zestaw sha256 wejsc (D33) | wydanie wejsc |

  Ta sama tresc pod nowym `ETag` = `relabeled`, pod tym samym albo bez
  sygnalu = `unchanged` (D23 dla `http`). Bez taniego sygnalu: domyslnie
  i przy `--upgrade` lokalna wersja (niesprawdzona, `--force` pobiera).
  Wszystkie mierzone obiekty byly bajtowo powtarzalne, wiec `--force` przy
  niezmienionym zrodle daje "bez zmian".

Decyzje rewizji 2026-10-12 (plan 3/3, weryfikacja
`docs/research/2026-10-12-plan3-spec-check/raport.md`):
- D29: sygnal `metadata` SoilGrids i CORINE = wydanie zrodla: tytul
  GetCapabilities mapy wlasciwosci (`SoilGrids250m 2.0 - Clay content` ->
  `2.0`) i `characteristics_release_major_version` publicznego katalogu
  CLMS (bez credentials). Wydanie jest etykieta wersji (`label_source =
  "edition"`), opis w `extra.edition`. UID-y CLMS 2012/2006/2000 poprawione
  wg katalogu.
- D30: zadna wersja SoilGrids/CORINE nie powstaje bez wydania: wydanie
  niedostepne bez lokalnej wersji = blad pliku; z lokalna wersja domyslnie
  `Warning:` (lokalna niesprawdzona), `--upgrade`/`--force` = blad.
  Porownanie: etykieta lokalnej wersji z wydaniem zrodla (inne wydanie =
  domyslnie informacja, `--upgrade` pobiera); wersja z inna etykieta
  (nie z wydania) jest nieporownywalna. Naglowki HTTP kanalu bez sygnalu
  (`none`) nie rozrozniaja wersji (ta sama tresc innego dnia = `unchanged`).
- D31: podglad CORINE z WMS (bez `CLMS_CREDENTIALS`, takze 1990) to osobny
  produkt w segmencie `eu_corine_<rok>_preview` (kanal WMS, `none`,
  etykieta daty) — nigdy wersja pliku danych CLMS.
- D32: `LandCoverManager` i `HSGCalculator` pisza wylacznie do magazynu
  (`output_dir` = korzen `--output`, bez `output_path`); wynik
  `LandCoverResult`/`LandCoverAreaResult`/`HsgResult` z `VersionedFile`.
  Plik poza magazynem: `provider.download_by_*` i `hsg_from_rasters`.
- D33: HSG liczony z wersji wejsc clay/sand/silt (tabela 4.2, bez katalogu
  tymczasowego i bez `keep_intermediate`); etykieta = wydanie wejsc
  (rozne: posortowane, laczone `+`), `extra.source_files[]` z `sha256`
  i sciezka wersji wejscia; wersja o tym samym zestawie sha256 wejsc jest
  uzywana ponownie (`reused`, bez liczenia), `--force` dotyczy wejsc.
- Segmenty (spec 3.4, lowercase): `landcover/pl_bdot10k_gpkg[_<warstwy>]`,
  `landcover/pl_bdot10k_gpkg_zip` (`keep_raw`), `landcover/pl_bdot10k_shp`,
  `landcover/eu_corine_<rok>[_preview]`,
  `soil/global_soilgrids_<wlasciwosc>_<glebokosc>_<stat>`,
  `hsg/global_soilgrids_<glebokosc>_<stat>`; pod segmentem `teryt/<T>`,
  `bbox/<wsp>` albo hierarchia godla. Tory planu `landcover` i `hsg`.
- Ograniczenia: poprawka danych w obrebie tego samego wydania (bez zmiany
  etykiety) wykrywa tylko `--force`; pobranie CLMS z credentials nie bylo
  sprawdzone na zywo (2026-10-12). HSG o tej samej tresci z innych wejsc
  zostaje wersja z pierwszymi wejsciami w `source_files` (wersje sa
  niezmienne), wiec takie wejscia licza HSG przy kazdym uruchomieniu.

**Errata 1 (2026-10-12, ADR-037, decyzja 9 planu 2/3):** arkusz CZ
(TM33/SM5) ma publiczne API: `download_cz_sheet`/`check_cz_sheet`
(`kartograf/download/cz_sheets.py`, wynik `CzSheetResult`, eksport
w `kartograf/__init__.py`); wczesniejsze "bez publicznego API arkusza CZ"
nie obowiazuje. Tory sa wywolywane przez `download_data`/`check_data`
(spojnosc CLI i API, ADR-037).

**Errata 2 (2026-10-16, ADR-042 D14, plan D):** D27 (i zdanie errata 2
ADR-003 "surowy WCS (np. ortofotomapa) poza magazynem") czesciowo nie
obowiazuje: ortofotomapa PL ma wycinek WCS w magazynie wersji
(`imagery download --product orto --cutout --horizontal-crs EPSG:2180
--coverage standard|high --resolution 0.1m|0.25m|0.5m|1m`,
`download_orto_cutout`/`check_orto_cutout`, segment
`orto/pl_1992_<coverage>_<res>/bbox/`, sygnal `none`, tor planu
`pl_cutout`). Surowe `GugikOrtoProvider.download_bbox` bez `coverage`
zostaje plikiem poza magazynem; `DownloadManager.download_bbox` pozostaje
usuniete.

---

## ADR-037: Spojnosc CLI i API

**Data:** 2026-10-12 (spec `docs/superpowers/specs/2026-10-12-cli-api-consistency-design.md`, plan `docs/superpowers/plans/2026-10-12-cli-api-consistency.md`)
**Status:** Przyjeta — uzupelniona przez ADR-038 (nazwy flag i parametrow ukladow); uzupelnia ADR-036 (arkusz CZ w publicznym API; errata 1 ADR-036) i ADR-031 (jezyk tekstow dla uzytkownika)

**Kontekst:** Audyt 2026-10-12 pokazal, ze to samo zadanie z CLI
i z biblioteki dawalo rozne wyniki: logika danych tylko w CLI (`--country
auto`, walidacja `--system`/`--scale`, `parent_request`, `--geometry`
i `--bbox-crs` poza arkuszami PL, arkusz CZ, BDOT10k z wielu powiatow),
cztery ksztalty wyniku i planu, inny cache metadanych (CLI w cwd,
biblioteka bez), `ValueError` obok `ValidationError` i mieszany jezyk
komunikatow. Hydrograf korzysta z biblioteki, wiec wynik nie mogl zalezec
od sposobu uruchomienia.

**Opcje:**
- A) Biblioteka jako jedyne miejsce decyzji o danych; CLI tylko tlumaczy
  flagi i wypisuje wynik; testy zgodnosci CLI = API.
- B) Zostawic logike w CLI i dopisac jej odpowiedniki w bibliotece (dwa
  zrodla prawdy, rozjazd wraca przy kazdej zmianie).
- C) Biblioteka wola CLI (`main([...])`) - wynik tylko jako tekst.

**Decyzja:** A. Zasady (spec 3):
- Z1. CLI tylko tlumaczy: w `kartograf/cli/` nie wolno walidowac wartosci
  danych, wybierac krajow, arkuszy, skali, kampanii ani powiatow, budowac
  `parent_request` ani czytac sidecarow w celu decyzji. Wolno parsowac
  tekst flag, czytac/zapisywac plik planu, formatowac wynik, wyliczac kod
  wyjscia z pol wyniku i rysowac postep (`tests/test_cli_translation.py`
  `test_cli_imports_no_data_logic`).
- Z2. Para `download`/`check`: kazda publiczna funkcja pobierajaca ma
  blizniaka `check_*` z tymi samymi argumentami (bez `update`, `plan`,
  `workers`, `on_progress`); kazda pobierajaca przyjmuje `update=`
  i `plan=`.
- Z3. Komunikaty o danych powstaja w bibliotece jako
  `Notice(level, code, text)` w polu `notices` wyniku i przez
  `on_notice`; CLI wypisuje `Info:`/`Warning:` na stderr (takze z `-q`).
- Z4. Bledne wejscie = `ValidationError` (`ParseError` dla godel),
  zrodlo = `DownloadError`, cache = `CacheError`; bledy programu zostaja
  wbudowane; `ValidationError` nie dziedziczy z `ValueError`.
- Z5. Pomoc, komunikaty CLI i teksty wyjatkow `KartografError` po polsku,
  wylacznie ASCII; `metavar` po polsku (`GODLO`, `KATALOG`, `PLIK`,
  `ROK`, `NAZWA`, `KOD`, `SKALA`).
- Z6. Wspolny cache metadanych: `cache: MetadataCache | bool = True`
  (`True` = `<cwd>/.kartograf_cache.db`, `False` = bez); `update="force"`
  bez odczytow z cache w tym wywolaniu.
- Z7. Testy zgodnosci (`tests/test_parity.py`,
  `tests/test_parity_landcover.py`): ten sam magazyn bajtowo (pliki,
  sidecary, wersje), statusy, plan, `notices`, typ i tekst bledu, przy
  zamrozonym zegarze (`kartograf/_clock.py`).

Decyzje S1-S6 (spec 7): S1 `download_data`/`check_data` (nazwa `download`
koliduje z podpakietem); S2 kroki wewnetrzne (`prepare_pl_cutout`,
`run_*`, `check_laz_updates`, `check_updates`, `upgrade`) poza API;
S3 `LandCoverManager.download` zawsze `LandCoverAreaResult`
(`download_all_counties`/`download_by_*`/`download_batch` usuniete);
S4 HSG `calculate_hsg`/`check_hsg` z `sheet`/`bbox`/`geometry`, bez
`stat`; S5 `cache: MetadataCache | bool`; S6 teksty wyjatkow po polsku
ASCII (trafiaja do CLI 1:1).

**Konsekwencje:** Wersja 0.8.0 lamie API (CHANGELOG [0.8.0] "Co
zrobic"): `DownloadResult` z wartosci zwracanej zamiast `last_result`,
`check_sheets`/`download_sheets(plan=)`, `workers`, nowe sygnatury
`check_*`, `LandCoverAreaResult`, HSG bez `stat`, teksty komunikatow.
Nowa komenda biblioteki `kartograf.download.data`: `download_data`/
`check_data` -> `DataReport(files, failed, stale, superseded, notices,
ok)`; `ok` jest regula kodu wyjscia CLI (czesciowy sukces `auto` = `ok`
z `Notice`). Nowe flagi R7: `landcover download --layers --keep-raw
--bbox-crs --workers --quiet`, `soilgrids hsg --bbox-crs --quiet`.
Testy zgodnosci wykryly i usunely dwie rozbieznosci: bbox w sidecarze
z liczb calkowitych (biblioteka) vs zmiennoprzecinkowych (CLI) - teraz
zawsze `float` (`core.bbox.bbox_coords`); kolejnosc wyniku arkuszy
rownoleglych zalezna od watkow - teraz kolejnosc zlecenia. Ryzyko Z6:
proces biblioteki z cwd tylko do odczytu dostaje cache wylaczony
z `Notice`. Zmiana CLI bez odpowiednika w bibliotece jest bledem (test
importow CLI i testy zgodnosci).

**Errata 1 (2026-10-13, audyt kodu 0.8.0-dev):** doprecyzowanie realizacji
Z1-Z3: `kartograf/cli/_parser.py:parse_bbox_arg` parsuje cztery liczby
i wywoluje biblioteczne `validate_request_bbox`; `download_data`/`check_data`,
`LandCoverManager.download`/`.check` i `HSGCalculator.calculate_hsg`/
`.check_hsg` waliduja tez bbox i wybory przy wywolaniu bez CLI. Z2
dotyczy funkcji poziomu komendy, nie niskopoziomowych metod providerow;
odpowiedniki `check_*` przyjmuja rowniez `on_notice`. Z3: `SHEET_LIST`
jest `Notice` z biblioteki, ale CLI wyswietla liste arkuszy jako naglowek
na stdout (zamiast `Info:` na stderr); pozostale komunikaty danych
`Notice` ida na stderr, rowniez przy `--quiet`. Dodatkowy komunikat
CLI o zapisaniu pliku `--plan` dotyczy operacji na pliku planu, nie danych.

---

## ADR-038: Jawny tryb wycinka i nazwy ukladow (--cutout, --horizontal-crs, --sheet-system)

**Data:** 2026-10-13
**Status:** Przyjeta; czesciowo zastepuje ADR-027 (wlaczanie wycinka PL flaga ukladu, nazwa `--target-crs`) i ADR-023 (obszar CZ zawsze wycinkiem, bez flagi trybu); uzupelnia ADR-037 (nazwy CLI = API)

**Kontekst:** Uzytkownik zapytal, czy `--horizontal-crs`/`--datum` nie
bylyby czytelniejsze niz `--target-crs`/`--system`. Kod 0.8.0-dev:
`--target-crs` robi dwie rzeczy naraz - podaje uklad wyniku i dla PL
`--bbox`/`--geometry` przelacza pobieranie arkuszy na jeden wycinek z WCS
GUGiK (ADR-027, ADR-035); dla CZ obszar daje zawsze wycinek (`exportImage`,
bez flagi natywnie EPSG:5514). `--system` wybiera uklad godel arkuszy PL
(1992 -> pliki EPSG:2180; 2000 -> pliki w strefie arkusza EPSG:2176-2179),
nie datum (oba uklady maja datum ETRF2000-PL). 0.8.0 i tak lamie CLI/API.

**Opcje:**
- A) Bez zmian nazw; lepsza pomoc i `Info:` o trybie.
- B) Jawna flaga trybu `--cutout`, uklad wycinka `--horizontal-crs`
  (symetria z `--vertical-crs`), uklad godel `--sheet-system`.
- C) Jedna flaga `--horizontal-crs` zamiast `--system` (EPSG:2180 =
  arkusze 1992, EPSG:2176-2179 = arkusze 2000 jednej strefy) - obszar
  PL-2000 w kilku strefach nie mialby wartosci, wycinek EPSG:5514/3045
  nie ma odpowiednika arkuszowego.

**Decyzja:** B (decyzja uzytkownika 2026-10-13), bez aliasow starych nazw:
- D1. `--cutout` / `cutout: bool` wlacza tryb jednego wycinka; tylko
  z `--bbox`/`--geometry` (z `--sheet` blad).
- D2. `--horizontal-crs` / `horizontal_crs=` = uklad wycinka, wymagany
  z `--cutout` (bez wartosci domyslnej, takze natywny CZ:
  `--horizontal-crs EPSG:5514`); bez `--cutout` blad.
- D3. Obszar CZ bez `--cutout` = blad (CUZK nie ma trybu arkuszy dla
  obszaru); `--country auto` z obszarem siegajacym CZ wymaga `--cutout`,
  a wtedy czesc PL tez jest wycinkiem (bez kombinacji arkusze PL +
  wycinek CZ).
- D4. `--sheet-system` / `sheet_system=` zamiast `--system` / `system=`
  w wyborze arkuszy: `download_data`/`check_data`, `find_sheets_for_bbox`,
  `find_sheets_for_geometry`, `SheetParser(sheet_system=)` i
  `SheetParser.sheet_system`. Bez zmian zostaja nazwy niskiego poziomu
  opisujace uklad pliku lub segmentu (`LazTile.system`,
  `FileStorage.get_raw_path(system=)`, szablon `{system}`, klucz cache
  indeksu arkuszy CZ).
- D5. `horizontal_crs=` zamiast `target_crs=` w funkcjach zadania
  (`download_data`/`check_data`, `download_pl_cutout`/`check_pl_cutout`,
  `download_cz_cutout`/`check_cz_cutout`) i w providerze CUZK
  (`create_dmr_provider`, `CuzkDmrProvider`); ogolne funkcje transformacji
  (`transform_bbox`, `get_overall_bbox`) zostaja z `target_crs` (cel
  transformacji, nie tryb zadania).
- D6. Sidecar `kartograf-meta/1` bez zmian (klucz `horizontal_crs` juz
  opisuje uklad pliku; `system` ani `target_crs` nie sa kluczami sidecara).

**Konsekwencje:** Zmiana lamiaca CLI i API w 0.8.0 (CHANGELOG [0.8.0]
"Co zrobic"): stare flagi daja blad argparse, stare argumenty `TypeError`.
Wycinek wymaga trzech flag (`--cutout --horizontal-crs ...` + obszar),
ale tryb i uklad wyniku sa widoczne w komendzie. Pobranie obszaru CZ
wymaga `--cutout` takze dla natywnego ukladu.

---

## ADR-039: Grupy komend CLI wg typu danych

**Data:** 2026-10-15
**Status:** Przyjeta — uzupelniona przez ADR-040 (komenda danych ustawia `_task` dla `project add`), ADR-042 (grupy `boundaries`, `cadastre`, `models3d`, `hydro`) i ADR-043 (grupy `names`, `maps`, `geodesy`); uzupelnia ADR-037 (CLI tylko tlumaczy; jedna komenda = jedna funkcja biblioteki) i ADR-038 (nazwy flag)

**Kontekst:** CLI 0.8.0-dev mialo jedna komende `download` dla NMT, NMPT,
ortofotomapy i LAZ (z flagami dotyczacymi tylko czesci produktow:
`--vertical-crs`, `--resolution`, `--cutout`, `--min-density`),
`landcover` z `--source` obejmujacym takze SoilGrids oraz `soilgrids hsg`.
`--help` jednej komendy mieszal flagi niezwiazane z wybranym produktem,
a `--year` i `--sheet` znaczyly co innego w roznych komendach. Roadmapa
(podprojekt 3) dodaje kolejne typy danych (granice, dzialki, modele 3D,
nazwy, mapy), ktore nie zmieszcza sie w jednej komendzie.

**Opcje:**
- A) Jedna komenda `download` z kolejnymi `--product`; flagi walidowane
  w bibliotece (stan dotychczasowy).
- B) Grupy komend wg typu danych: `kartograf <grupa> <komenda>`; kazda
  grupa ma wlasne flagi i pomoc; nowy typ danych = nowa grupa.
- C) Komenda per produkt (`kartograf nmt`, `kartograf orto`, ...).

**Decyzja:** B (decyzja uzytkownika 2026-10-13, wchodzi do 0.8.0), bez
aliasow starych nazw:
- D1. Grupy 0.8.0: `elevation` (`--product nmt|nmpt|laz`; NMT/NMPT PL,
  DMR CZ, LAZ), `imagery` (`--product orto`), `landcover` (`--source
  bdot10k|corine`), `soil` (SoilGrids, HSG). `parse` i `cache` zostaja
  poza grupami. Komendy grupy: `download`, `list-sources` (kazda grupa),
  `list-layers` (`landcover`, `soil`), `hsg` (`soil`).
- D2. Kazda grupa jest jednym modulem `kartograf/cli/groups/<grupa>.py`
  z `register(subparsers)`; `register_groups` wykrywa moduly przez
  `pkgutil` (alfabetycznie, moduly `_*` sa pomocnicze), wiec nowa grupa to
  jeden nowy modul bez zmian we wspolnym pliku. Wspolne flagi (obszar,
  tryby aktualizacji, `--quiet`, `parse_bbox_arg`) w `cli/_args.py`;
  `cli/_parser.py` zawiera tylko parser glowny, `parse`, `cache` i blad
  usunietych komend.
- D3. Grupa ma tylko swoje flagi: `imagery download` nie przyjmuje
  `--vertical-crs`, `--resolution`, `--cutout`, `--horizontal-crs`,
  `--min-density`; `--country` w `imagery` to `pl|auto` (brak ortofotomapy
  CZ; `cz` dojdzie razem z planem D). Flaga spoza grupy to blad argparse.
  Reguly biblioteki (orto + CZ, orto + wycinek) obowiazuja nadal na
  poziomie `download_data` (ADR-037).
- D4. `--sheet` ma jedna definicje we wszystkich grupach: obszar arkusza
  o tym godle. Gdy zrodlo publikuje produkt w tych arkuszach (NMT, NMPT,
  orto PL; DMR CZ), wynik to pliki arkusza 1:1; inaczej dane z zasiegu
  arkusza (LAZ: kafle, BDOT10k: powiaty, CORINE/SoilGrids/HSG: wycinek).
  Nazwa flagi bez zmian.
- D5. `--year` ma jedna definicje: rok, ktory opisuja dane. `elevation`
  i `imagery`: filtr lotow (najnowszy lot z roku, z `--min-year`/
  `--max-year`); `landcover`: wydanie (CORINE 2018; pozniej rocznik
  BDOT10k z planu C).
- D6. Brak `--product` (albo `--source` w `landcover`) daje komunikat
  wymieniajacy tylko wybory grupy (`options.product_choices()`); wartosc
  dalej waliduje argparse i biblioteka. `soil download` nie ma `--source`
  (jedno zrodlo). `imagery download` zachowuje wymagane `--product orto`
  mimo jednego produktu: grupa dostanie kolejne produkty w planie E (true
  orto, orto ukosna, obrazy intensywnosci), wiec flaga nie zmieni sie
  przy ich dodaniu. `list-sources` wypisuje tabele z rejestru deskryptorow
  (WYBOR, KRAJ, DOSTAWCA, KLUCZ = `dataset` sidecara, NAZWA) bez sieci.
- D7. Usuniete komendy koncza sie bledem parsera (kod 2) z nazwa nowej
  komendy, bez dzialajacego aliasu: `download`, `soilgrids`,
  `landcover ... --source soilgrids`. Biblioteka i sidecar
  `kartograf-meta/1` bez zmian; segmenty `data/` bez zmian.
- D8. Komendy CLI nadal tylko tlumacza na funkcje biblioteki (ADR-037):
  `elevation download` i `imagery download` -> `download_data`/
  `check_data`, `landcover download` i `soil download` ->
  `LandCoverManager`, `soil hsg` -> `HSGCalculator`.
  `kartograf.cli.commands` traci `cmd_landcover`/`cmd_soilgrids`;
  `parse_bbox_arg` jest w `kartograf.cli._args`.

**Konsekwencje:** Zmiana lamiaca CLI w 0.8.0 (CHANGELOG [0.8.0] "Co
zrobic": tabela stara -> nowa komenda). `--help` grupy zawiera tylko
istotne flagi. Nowe produkty dodaja grupy bez zmian w istniejacych;
galezie z nowymi grupami musza uzyc `cli/groups/<grupa>.py` oraz
`add_group`/`add_list_sources` z `kartograf.cli.groups` i flag z
`kartograf.cli._args`. Skrypty wolajace stare komendy (takze
Hydrograf/Hydrolog) trzeba zaktualizowac.

---

## ADR-040: Manifest projektu i przypiete wersje

**Data:** 2026-10-15
**Status:** Przyjeta — uzupelniona przez ADR-042 (pozycje komend kolekcji); uzupelnia ADR-039 (komenda danych ustawia `_task` dla `project add`)

**Kontekst:** Magazyn wersjonowany (ADR-036) jest wspolny dla wielu
projektow, a sciezka standardowa wskazuje najnowsza lokalna wersje, wiec
po kolejnym pobraniu projekt traci informacje, ktorych bajtow uzyl.
Sidecar `kartograf-meta/1` jest niezmiennym opisem pochodzenia pliku,
nie lista projektow, ktore go uzyly (SCOPE 3.3). Podprojekt 2 roadmapy
(manifest projektu) wchodzi do 0.8.0; uzytkownik dal wolna reke co do
architektury (2026-10-15). Magazyn i katalog projektu moga lezec na
udziale sieciowym bez blokad zakresow bajtow - baza SQLite tam odpada.

**Opcje:**
- A) Plik JSON w katalogu projektu: zadania (komenda grupy + opcje danych)
  i przypiete wersje plikow z SHA-256; grupa CLI `project`.
- B) Baza SQLite projektow i plikow w magazynie: blokady na udziale,
  drugie zrodlo prawdy obok sidecarow.
- C) Kopia danych w katalogu projektu i lista polecen: duplikaty, brak
  dowodu tozsamosci wersji.
- D) Wpisy projektow w sidecarach wersji: narusza niezmiennosc sidecara.

**Decyzja:** A. Szczegoly i odrzucone warianty (M1-M12):
`docs/superpowers/specs/2026-10-15-manifest-projektu-design.md`.
- D1. Plik `kartograf-project.json`, schema `kartograf-project/1`,
  angielskie klucze, scisla walidacja: `output_dir` (jeden magazyn
  z `init --output`; sciezka wzgledna zapisana wzgledem katalogu
  projektu) i `tasks[]`: `name`, `command` (komenda danych grupy
  ADR-039), `options` (argumenty funkcji biblioteki w postaci JSON),
  `pinned_at`, `kartograf_version`, `geometry_sha256`, `files[]`
  (`role`, `unit`, `path`, `version`, `label`, `sha256`, `size_bytes`).
- D2. CLI `kartograf project init|add|remove|download|status|verify`,
  `--project KATALOG` domyslnie biezacy katalog; `add NAZWA <grupa>
  <komenda> [opcje]` przyjmuje komende grupy w jej gramatyce; tryby jak
  w grupach: `download --check-updates|--upgrade|--force`. API:
  `init_project`, `open_project`, `add_project_task`,
  `remove_project_task`, `download_project`, `check_project`,
  `project_status`, `verify_project`.
- D3. Zadanie jest przypinane w calosci, tylko po pelnym sukcesie.
  `download` bez trybu nie zmienia przypiec: pobiera zadania niepobrane,
  a brakujace przypiete pliki odtwarza tylko przy identycznym SHA-256.
  Przepiecie wylacznie `--upgrade`/`--force`, zawsze calego zadania.
- D4. `check_project` porownuje przypiecie z planem `check_*` komendy
  przez `PlanItem.local_sha256`; sygnaly zrodel interpretuje wylacznie
  logika ADR-036.
- D5. `verify` = pelny SHA-256 i zgodnosc z sidecarem wersji; `status`
  = istnienie i rozmiar, bez sieci.
- D6. Brak `project availability`: raport dostepnosci (plan A/B) sluzy
  wyborowi wariantu przed `project add`; raport nie jest plikiem danych.
- D7. Zapis atomowy (`os.replace`) pod krotka blokada katalogowa
  (`mkdir`), scalanie per zadanie; bez SQLite i blokad zakresow bajtow;
  operacje projektu domyslnie bez cache metadanych.
- D8. Jedna pozycja na komende danych w `kartograf/project/commands.py`
  i `_task` w parserze komendy (uzupelnienie ADR-039): nowy produkt
  w istniejacej komendzie nie zmienia projektu, nowa grupa (plany C-E)
  dodaje pozycje.

**Konsekwencje:** Jeden plik na projekt jest zrodlem powiazania
projekt -> dane; indeks "ktore projekty uzywaja pliku" mozna zbudowac
lokalnie z manifestow, bez zmiany sidecarow. Przeniesienie projektu
wymaga zachowania wzglednego polozenia magazynu albo korekty jednego
`output_dir`. Odtworzenie bajtow, ktore zrodlo zmienilo albo wycofalo,
wymaga kopii magazynu (z sidecarami); zadanie bez jawnego wariantu
(np. bez `--year`) odtwarza sie bez kopii tylko do publikacji nowszych
danych. System plikow projektu musi wspierac atomowe `mkdir`
i `rename`; magazyn nadal wymaga dowiazan twardych (ADR-036). Kazda
nowa komenda danych wymaga pozycji w tabeli projektu i `_task` (test
zgodnosci). Implementacja:
`docs/superpowers/plans/2026-10-15-manifest-projektu.md`.

---

## ADR-041: Rejestr wariantow produktu, skorowidz WFS NMT/NMPT i raport dostepnosci

**Data:** 2026-10-15
**Status:** Przyjeta — uzupelniona przez ADR-043 (NMT 100 m w rejestrze wariantow bez ukladu wysokosci)

**Kontekst:** Skorowidze GUGiK 2025 maja NMT wylacznie w 0,5 m i 5 m,
a NMPT w 73% w 0,5 m; Kartograf znal tylko NMT 1 m i 5 m oraz NMPT 1 m,
wiec nowe loty byly niewidoczne (luka 0,5 m, spec 1). Rozdzielczosci
i uklady wysokosci byly zaszyte w 7 miejscach (stale `("1m", "5m")`
w `options.py`, providerach NMT/NMPT, `FileStorage`, wycinku, `area.py`
i CLI; regula "5m tylko EVRF2007" trzykrotnie - backlog A5-4). Pelna
inwentaryzacja skorowidzy WFS 2026-10-15 pokazala siatki `.asc` w 0,15;
0,5; 0,6; 1; 5 i 10 m oraz archiwa (XYZ, ASCII NMT, TBD, TIN, TTN, GRD,
DXF, DGN); skorowidz WMS nie ma 10 m, a WFS jest nadzbiorem WMS dla
siatek. Ten sam arkusz ma w WFS pliki w dwoch formatach (18 003 par
warstwa-arkusz NMT EVRF2007, 87 100 NMT KRON86). Raport dostepnosci
(spec 4, K3/K4) potrzebuje jednego indeksu i jednej listy wariantow,
wspolnych z pobieraniem.

**Opcje:**
- A) Rejestr `ProductVariant` w deskryptorach zrodel jako jedyne zrodlo
  wariantow; skorowidz NMT/NMPT z WFS dla pobierania i raportu.
- B) Listy stalych per modul (stan zastany) rozszerzone o nowe
  rozdzielczosci.
- C) Pobieranie arkuszy przez skorowidz WMS (jak dotad), raport z WFS.

**Decyzja:** A. Szczegoly: spec
`docs/superpowers/specs/2026-10-13-katalog-produktow-design.md` (K1-K4,
sekcje 3-4), pomiary `docs/research/2026-10-15-plan-a-b/raport.md`, plan
`docs/superpowers/plans/2026-10-15-plan-a-elevation-pl.md` (decyzje
implementacyjne 1-13).
- R1. Rejestr `kartograf/sources/variants.py`: `ProductVariant` (zrodlo
  = klucz deskryptora i `dataset` sidecara, produkt, kraj, rozdzielczosc
  jako `Decimal`, uklad wysokosci, format, uklady poziome, kanal,
  `IndexRef` uslugi WFS), warianty w `SourceDescriptor.variants`, jeden
  deskryptor na (produkt, format, rozdzielczosc). Rejestr jest jedynym
  zrodlem rozdzielczosci, ukladow wysokosci i formatow dla walidacji
  CLI/API, `--help`, `list-sources`, segmentu magazynu i filtra rekordow
  skorowidza; zaden inny modul nie trzyma takiej listy. Nowa
  rozdzielczosc albo format = wpis rejestru.
- R2. Etykiety K2: `0.15m`, `0.5m`, `0.6m`, `1m`, `5m`, `10m` (archiwa
  takze `15m`-`50m`) z jednej funkcji `resolution_label`; flaga przyjmuje
  wylacznie dokladne etykiety rejestru (`0,5m`, `50cm`, `0.50m` = blad
  z lista etykiet). Etykieta jest czlonem segmentu
  (`nmt/pl_{system}_0.5m_{vcrs}`); klucze i segmenty istniejacych danych
  (`pl.gugik.nmt_1m`, `pl.gugik.nmt_5m`, `pl.gugik.nmpt` = NMPT 1 m) bez
  zmian.
- R3. Siatki ASC we wszystkich rozdzielczosciach inwentaryzacji WFS: NMT
  EVRF2007 0.15m, 0.5m, 0.6m, 1m, 5m, 10m; NMT KRON86 0.5m, 1m; NMPT
  EVRF2007 0.5m, 0.6m, 1m; NMPT KRON86 0.5m, 1m.
- R4. Archiwa GUGiK (`--format` XYZ, ASCII-NMT, TBD, TIN, TTN, GRD, DXF,
  DGN) SA wariantami rejestru i sa pobierane jako pliki zrodlowe:
  oryginalny plik + sidecar, wersje w magazynie (ADR-036), bez konwersji,
  wycinka i mozaiki; segment z tokenem formatu
  (`nmt/pl_{system}_tbd_25m_{vcrs}`), rozszerzenie z pola `format`
  rekordu. `--format` wybiera format pliku; bez flagi = siatka ASC - to
  wybor produktu jawnie opisany w `--help` i dokumentacji, nie ukryta
  wartosc domyslna danych. Archiwa leza na arkuszach roznych skal, wiec
  arkusze archiwum dla obszaru wyznacza skorowidz (rekordy wariantu
  przecinajace obszar, rama zwezona o 1 m, w zakresie lat); `--scale`
  i `--cutout` z archiwum = `Error:`.
- R5. Skorowidz arkuszy NMT/NMPT z WFS
  (`kartograf/providers/pl/skorowidz_wfs.py`): kanal arkuszy
  `TransportKind.WFS` (`update_signal="index"`) zamiast
  `WMS_SHEET_INDEX`; jedno `GetFeature` na arkusz z `TYPENAMES`
  wszystkich typow rocznych uslugi, kolejne strony wylacznie po `next`,
  kazda awaria = `DownloadError` ("wynik bylby niepelny"), nigdy pusty
  wynik. Pobieranie i raport czytaja ten sam indeks tym samym parserem;
  LAZ uzywa tego samego transportu; ortofotomapa zostaje na WMS.
- R6. Twardy filtr rekordu (rozszerzenie ADR-028): format rekordu
  I koncowka sciezki URL musza wskazywac format wariantu
  (`source_format`); rekord niespojny (np. format siatki z URL `.xyz`,
  42 rekordy NMT 2019) nie jest pobierany.
- R7. Wycinek WCS (`--cutout`) tylko 1 m (`pl.gugik.nmt_1m`,
  `pl.gugik.nmpt`): WCS GUGiK daje kompozycje lotow, nie arkusz wg roku
  (ADR-035); `--cutout` z inna rozdzielczoscia = `Error:` przed siecia.
- R8. Raport dostepnosci (`check_availability`, `kartograf elevation
  availability`): kombinacja = (rok, uklad poziomy, etykieta, uklad
  wysokosci, format) wariantu rejestru, LAZ = (rok, uklad poziomy, uklad
  wysokosci); kombinacja jest kompletna, gdy obrysy pelnych arkuszy
  (`TAK`) wg skorowidza pokrywaja obszar przeciety z ladem PRG (siatka
  1 m); archiwa sa kombinacjami do pobrania (format w raporcie,
  podpowiedz z `--format`); `Info:` tylko dla rekordow spoza rejestru
  (niespojnych, z godlem 8-czlonowym). Raport nie pobiera danych.
- R9. Podpowiedz pobrania w raporcie: komenda do wklejenia po
  `kartograf ` albo po `kartograf project add NAZWA ` - bez `--output`
  (ADR-040, spec manifestu 4.10).

**Ograniczenia:** Godla 8-czlonowe ukladu PL-1992 (ASCII NMT 10 m - 215
arkuszy, 1678 rekordow ASC 1 m) sa poza `SheetParser`: nie sa pobierane,
raport pokazuje je jako `Info:`; do zamkniecia w planie E (E1 rozszerza
`SheetParser`). Sygnatury plikow archiwow (ZIP, TTN, Intergraph GRD/DGN,
DXF) sprawdzono na jednej probce na format.

**Konsekwencje:** Zmiany lamiace 0.8.0 (decyzja 12 planu, "Co zrobic"
w CHANGELOG): `--product nmpt` wymaga `--resolution`;
`GugikNmptProvider(..., resolution=)` bez wartosci domyslnej;
`GugikProvider` i `GugikNmptProvider` przyjmuja etykiety i `format`
z rejestru; usuniete bez aliasow: `kartograf.providers.pl.nmt_vertical_crs`,
`require_nmt_vertical_crs`, `NMT_5M_VERTICAL_CRS`,
`GugikProvider.SUPPORTED_RESOLUTIONS`/`SUPPORTED_VERTICAL_CRS`/
`SUPPORTED_VERTICAL_CRS_5M`/`WMS_INDEX_ENDPOINTS`/
`get_supported_resolutions`/`get_supported_vertical_crs_for_resolution`,
`GugikNmptProvider.SUPPORTED_RESOLUTIONS`/`WMS_INDEX_ENDPOINTS`,
`FileStorage.SUPPORTED_RESOLUTIONS`, `GugikLazProvider.WFS_ENDPOINTS`
(zastepstwo: `kartograf.sources.variants.variants(...)`). Sidecary
nowych arkuszy NMT/NMPT: `extra.source.index_url` = adres uslugi WFS,
`extra.source.layer` = typ WFS (`SkorowidzNMT2025`); pliki i segmenty
istniejacych danych bez zmian, sygnal swiezosci arkuszy nadal `index`.
Nowe API raportu: `check_availability`, `AvailabilityReport`,
`AvailabilityCombination`, `AvailabilityArea`. Plan B dopisuje warianty
CZ (uzupelnienie ADR-041).

**Odrzucone:**
- listy stalych per modul (opcja B): kazda nowa rozdzielczosc zmienia
  kilka modulow, a reguly rozjezdzaja sie;
- etykiety `50cm` i `0_5m` (dwie jednostki w jednym parametrze; spec K2);
- archiwa poza pobieraniem (rekomendacja planu przed rewizja) - odrzucone
  decyzja uzytkownika 2026-10-15: archiwa sa jedynym zrodlem 15-50 m
  i czesci rocznikow (np. Krakow 2018);
- WMS dla pobierania i WFS dla raportu (opcja C): dwa indeksy moga dac
  rozne odpowiedzi, a WMS nie ma 10 m ani archiwow;
- prog pokrycia w raporcie: kompletnosc jest binarna wg obrysow arkuszy
  `TAK`, niepokryty lad raport podaje w m2.

**Uzupelnienie (2026-10-15, zakonczenie planu A):**
- R5 doprecyzowane: serwer stronicuje odpowiedz kilku typow niespojnie
  (powtorzenia i braki, nagranie 2026-10-15), jeden typ spojnie;
  odpowiedz kilku typow z atrybutem `next` jest odrzucana i kazdy typ jest
  odpytywany osobno; obiekt powtorzony na kolejnej stronie = `DownloadError`.
- R6 poprawione: 42 rekordy NMT EVRF2007 2019 (kampania 72675, arkusze
  N-33-69) maja format siatki i nazwe pliku `.xyz`, a w srodku AAIGrid
  (naglowki wszystkich 42 plikow sprawdzone na zywo 2026-10-15; 0.7.x je
  pobieralo) - sa siatkami ASC: `FORMATS` przyjmuje dla ASC URL `.asc`
  i `.xyz`, tresc po pobraniu sprawdza `verify_file_format`. Niespojny
  zostaje m.in. format siatki z URL archiwum i archiwum z URL `.asc`.
- R8 doprecyzowane: `Info:` raportu ma kod `index_unsupported` (rekordy
  spoza rejestru: godla 8-czlonowe, format niezgodny z plikiem); z `--sheet`
  pomiar pomija pas 1 m przy ramie arkusza (rama z godla rozni sie od ramy
  GUGiK o centymetry), `--bbox`/`--geometry` mierzone dokladnie; LAZ ma
  obwiednie jak pobieranie LAZ; `--country` wymagane tylko z `--bbox`/
  `--geometry`; cache metadanych trzyma typy WFS, rekordy obszaru
  z obrysami i maske ladu (ponowny raport bez sieci, `--force` pomija cache).
- Manifest (ADR-040): `elevation availability` nie ustawia `_task`
  (`project add` ja odrzuca); `COMMANDS["elevation download"]` ma opcje
  `format`; kazda podpowiedz raportu przechodzi `project add` bez sieci.
- E2E na zywo 2026-10-15 (`docs/research/2026-10-15-plan-a-e2e/raport.md`):
  siatki 0.15m, 0.5m (NMT i NMPT, EVRF2007 i KRON86) i 0.6m pobrane
  z pikselem rownym etykiecie; raporty Krakowa i Pomorza zgodne z pomiarami
  planu; JSON CLI = API; pobrane godla = `sheets_full` kombinacji; raport
  LAZ pyta tylko WFS i PRG; wycinek 1 m bajtowo rowny wycinkowi z `develop`;
  archiwum TBD 25 m pobrane, ZIP kompletny, ponowne uruchomienie lokalne.

**Uzupelnienie: warianty CZ (plan B, 2026-10-15):**
- R1 dla CZ: wiersz rejestru = wiersz tabeli tras planu B
  (`docs/superpowers/plans/2026-10-15-plan-b-elevation-cz.md`, decyzja 2):
  (produkt, rozdzielczosc albo model, uklad wysokosci, system arkuszy
  `sm5`/`tm33`) z kanalem, ktory go obsluguje - plik CUZK
  (`DIRECT_FILES`, sygnal `http`) albo ImageServer z lokalnym warpem na
  siatke kafla (`ARCGIS_IMAGE`, sygnal `none`). `ProductVariant.model`
  (`dmr5g`, `dmr4g`, `dmp1g`, `dmpok`; PL: `None`). Deskryptory:
  `cz.cuzk.dmr5g` (NMT 2m), `cz.cuzk.dmr4g` (NMT 5m), `cz.cuzk.dmp1g`
  (NMPT 2m), `cz.cuzk.dmpok` (NMPT 0.5m) i `cz.cuzk.<model>_laz`; segmenty
  `nmt|nmpt/cz_<model>_<vcrs>`, `laz/cz_<model>_<vcrs>` (model i uklad
  wysokosci wyznaczaja plik - bez ukladu poziomego w segmencie).
  Wycinek CZ nie jest wierszem: to kanal ImageServer deskryptora.
- Trasy: arkusz SM5 = plik S-JTSK (EPSG:5514, Bpv natywnie; EVRF2007 przez
  przypieta operacje Bpv->EVRF2007); kafel TM33 w EVRF2007 = plik ETRS89
  (EPSG:3045, EVRF2007 natywnie wg metadanych CSW zbiorow - bez
  transformacji, sidecar `vertical_crs = EPSG:5621` bez operacji pionowej);
  kafel TM33 w Bpv i kazdy kafel modelu bez plikow rastrowych (DMR 5G,
  DMP 1G: `*-TIFF` = 404) = ImageServer + warp (ADR-024). SM5 dla 2m =
  `Error:` przed siecia. Kanal wybiera `channel_for(klucz, transport,
  uklad poziomy)`: deskryptor ma po jednym kanale plikow na system.
- LAZ CZ: `--model` (API `model=`) wymagane dla `--product laz` w CZ,
  z PL albo innym produktem = `Error:`. Pliki tylko w parach S-JTSK + Bpv
  (arkusze SM5) i ETRS89 + EVRF2007 (kafle TM33): uklad wysokosci wybiera
  pliki obszaru, zla para z godlem = `Error:` przed siecia; chmura punktow
  bez transformacji (plik 1:1 z ZIP).
- Raport CZ (`check_availability(country="cz"|"auto")`): arkusze indeksu
  `KladyMapovychListu` przecinajace obszar (SM5 `PODIL > 0`, TM33
  `IN_CZ`) i `HEAD` kazdego pliku: 200 = arkusz z plikiem, 404 = brak
  pliku (`sheets_missing`), inny blad = `DownloadError`; `published` =
  `Last-Modified`, `size_bytes` = `Content-Length`; bez lat nalotu (CUZK
  ich nie publikuje). Modele bez plikow rastrowych = `Info:`
  `cz_service_only`.
- Odrzucone: zapasowy endpoint `dmp` (alias `dmp_obrazova_korelace`:
  ten sam opis i katalog); ATOM jako sygnal i zrodlo raportu (`<updated>`
  = `Last-Modified`, feed 24-31 MB); nowa flaga `--sheet-system` dla LAZ
  CZ (uklad poziomy wynika z ukladu wysokosci plikow); transformacja chmur
  punktow (zmienia dane zrodlowe, brak przypietej operacji 3D); drugi tor
  wyboru modelu rastra (`--model` dla NMT/NMPT - rastry wybiera
  `--resolution`).

**Uzupelnienie (2026-10-16, zakonczenie planu B):**
- Trasa rastra CZ: `CuzkRasterProvider.route(sheet=None) -> CzRasterRoute`
  (kanal, uklad wyniku, przypiete operacje; `None` = wycinek) - tory arkusza
  i wycinka pisza sidecar z trasy, operacja pionowa powstaje w `route()`
  przed siecia. Wariant rastra wybiera `find_cz_variant`/`cz_variant_error`,
  LAZ `find_cz_laz_variant`/`cz_laz_error` (`sources/variants.py`;
  `find_variant` zostaje dla PL); sygnal pliku `file_signal(sheet)`.
- Arkusze plikow obszaru - jedna regula dla pobrania LAZ i raportu
  (`SheetIndex.file_sheets(system, area)`): SM5 z `PODIL > 0`, TM33 - kafle
  warstwy 26 (`IN_CZ` ma w indeksie jedna wartosc `CZ`, kafli poza CZ
  indeks nie ma); arkusz stykajacy sie z obszarem krawedzia albo
  zachodzacy o mniej niz 1 cm odpada (szum wspolrzednych ArcGIS ok. 1 mm).
- `--country auto` z LAZ: kafle PL z WFS i arkusze CZ wg ukladu wysokosci,
  wspolny `extra.parent_request`; flagi LAZ tylko-PL (`--year`,
  `--min-year`, `--max-year`, `--all-campaigns`, `--min-density`) zawezaja
  `auto` do PL (`Info:`); obszar siegajacy CZ bez `--model` = `Error:`
  z lista modeli i `--country pl`.
- Raport CZ: `HEAD` rownolegle (8 watkow), cache `head|<url>`
  i `cz-sheets|...` jak rekordy skorowidza (`--force` pomija odczyt);
  `uncovered_m2` mierzone w ukladzie raportowanego obszaru (prostokat
  czesci CZ w EPSG:5514, godlo - jego rama; rama kafla TM33 przeniesiona
  wierzcholkami przypieta operacja), wiec nie przekracza `area_m2`;
  `size_bytes = None`, gdy zaden arkusz nie ma pliku; `Info:`
  `cz_service_only` tylko dla czesci CZ z arkuszami indeksu. `auto`:
  czesc niesprawdzona przy drugiej sprawdzonej = `Warning:` `check_failed`,
  `ok=False` (CLI kod 1), obie = blad; flagi roku: `cz` = blad, `auto` =
  zawezenie do PL. Podpowiedzi CZ: raster - polecenie na arkusz, LAZ -
  jedno polecenie obszaru z `--model`; kazda przechodzi
  `validate_data_request` i `project add` bez sieci.
- Istniejace kafle TM33 DMR 4G EVRF2007 z warpu: tryb domyslny zostawia
  lokalna wersje (`Info:` - niesprawdzona), `--force` pobiera plik CUZK
  jako nowa wersje i przepina dowiazanie.
- E2E na zywo 2026-10-16 (`docs/research/2026-10-16-plan-b-e2e/raport.md`):
  DMP OK SM5 5000x4000 px 0,5 m; natywne kafle TM33 DMP OK i DMR 4G
  EVRF2007 z wartosciami 1:1 z ZIP CUZK; DMR 4G TM33 natywnie wobec
  dawnego warpu na tej samej siatce: mediana |roznicy| 0,06 m, p95 0,39 m,
  maks. 1,66 m; wycinek DMP 1G 2 m zgodny geometrycznie z natywnym DMP OK
  (ponizej 1/4 piksela); LAZ CZ arkusza i kafla bajtowo rowne czlonom ZIP;
  wybor arkuszy obszaru = indeks po odsianiu stykajacych sie; raport CZ
  i `auto` bez `GET` plikow, `--json` = API.

---

## ADR-042: Silniki kanalow (unit_package, feature_bbox, atom_files) i dane planow C/D

**Data:** 2026-10-15
**Status:** Przyjeta — czesciowo zastapiona przez ADR-043 (D1: capability kanalu kolekcji unikalna w deskryptorze); uzupelniona przez ADR-043 (jednostki arkuszy, kafli i KU, rekord indeksu i sygnal `index`, OGC API Features, wybor kanalu po wartosciach opcji); czesciowo zastepuje ADR-036 (D27: wycinek ortofotomapy w magazynie; errata 2 ADR-036); uzupelnia ADR-015 (zapis GPKG przez pyogrio; odczyt obwiedni bez zmian), ADR-034 (kawalki wycinka ortofotomapy; errata 1 ADR-034), ADR-036 (D23 miedzy wydaniami, sloty jednostek), ADR-039 (grupy boundaries, cadastre, models3d, hydro) i ADR-040 (pozycje komend projektu); errata 1-5: D5 i D12-D17 wg kodu planu D (indeks ATOM, HY-NET obszaru 2 warstwy, ZABAGED i RUIAN, ortofoto CZ, wycinek orto)

**Kontekst:** Spec katalogu (K5-K7) wymaga, by produkt z raportu byl
wpisem deskryptora i konfiguracja kanalu, nie providerem. Plany C i D
wnosza paczki per jednostka administracyjna (archiwum BDOT10k, modele 3D,
PRG, EGiB), obiekty dla obszaru z WFS i ArcGIS REST (PRG, EGiB, RUIAN,
HY-NET, ZABAGED) i pliki wskazywane feedem ATOM CUZK (ortofoto, ZABAGED
kraj). Rekonesans 2026-10-15 wykazal: bledne linki `next` w obu
serwerach WFS, duplikat obiektu na granicy stron MapServer, kolejnosc osi
zgodna z EPSG u obu dostawcow, zmienne w czasie pole EGiB `DATA` (data
stanu danych powiatu), obiekty wieloczesciowe EGiB jako powtorzone
geometrie, URL-e z rokiem/data w nazwie (tylko z feedu). Krzywe
(`CurvePolygon`) z probki EGiB 2026-10-13 nie wystapily w danych
(pomiar 2026-10-15: same wielokaty liniowe).

**Opcje:**
- A) Provider per produkt (wzorzec `providers/pl/*.py`).
- B) Generyczne silniki sterowane typowanymi parametrami kanalu
  w deskryptorze + jeden orkiestrator kolekcji na magazynie wersji.
- C) Jeden ogolny "pobierz URL" bez typowanych parametrow.

**Decyzja:** B.
- D1. `AccessChannel.params: UnitPackageParams | FeatureBBoxParams |
  AtomFilesParams | WcsCutoutParams | None` (dane bez IO, niemutowalne;
  dwa ostatnie w planie D). Wymagane czlony ZIP sa cecha wariantu
  (`PackageVariant.members`: paczki GML i SHP jednego kanalu roznia sie).
  Silniki: `transport/unit_package.py`, `transport/feature_bbox.py`,
  `transport/atom.py` (plan D), zapis GPKG `transform/gpkg.py`,
  orkiestracja `download/collections.py`. Nowy produkt = deskryptor
  z parametrami kanalu (+ wybor w CLI). Kanal kolekcji ma capability
  unikalna w swoim deskryptorze (wybor kanalu sidecara).
- D2. Rodzaj wyboru wyznacza kanal: `teryt` (2 cyfry = woj., 4 = powiat)
  -> `unit_package` tej jednostki; obszar (`bbox`/`sheet`/`geometry`) ->
  `feature_bbox`, a gdy produkt go nie ma - powiaty z PRG i paczka na
  powiat; `whole_country` -> plik krajowy (`unit_package` jednostki
  `country` albo `atom_files`) wylacznie jawnie, z rozmiarem z `HEAD`/
  feedu w `Notice` przed transferem (K7). Dokladnie jeden wybor; wariant
  (rok, format, LoD, poziom, uklad pliku krajowego) wymagany, gdy zrodlo
  publikuje wiecej niz jeden (K8), a przy jednym przyjmowany tylko rowny
  opublikowanemu. Uklad pliku wybiera `--horizontal-crs` (ADR-038; API
  `horizontal_crs`): wymagany, gdy kanal ma kilka ukladow (pliki krajowe
  CUZK 5514/3045); wynik obszaru jest zawsze w ukladzie natywnym uslugi.
- D3. Kompletnosc `feature_bbox` z liczby, nie z linkow: WFS
  `RESULTTYPE=hits`, ArcGIS `returnCountOnly` -> N; strony
  `STARTINDEX`/`resultOffset` (ArcGIS z `orderByFields`) od 0 co
  `page_size`; `next` ignorowany (MapServer gubi go na stronach
  srodkowych, GeoServer daje go na ostatniej). Petla stron: koniec, gdy
  unikalnych identyfikatorow jest N; za N zaplanowanych pozycji tylko
  dopoki poprzednia strona byla pelna i dodala nowe identyfikatory
  (MapServer powtarza obiekt na granicy stron, wiec ostatni unikalny
  obiekt moze lezec za pozycja N-1: PRG A03, `hits` 39, `COUNT=13` -
  39. obiekt na `STARTINDEX=39`); krotka strona przy mniej niz N
  unikalnych, strona za N bez nowych identyfikatorow albo wiecej niz N
  unikalnych = `DownloadError`. Dedupe po polu identyfikatora kanalu
  (identyczny duplikat pominiety, rozny = `DownloadError`);
  `numberMatched="unknown"` w odpowiedzi `hits` = `DownloadError`; HTML,
  `ExceptionReport`, JSON `error` przy HTTP 200 = `DownloadError`. N = 0
  we wszystkich warstwach = `NoCoverageError` (bez pliku); pusta warstwa
  obok niepustych = warstwa ze schematem bez obiektow. Metadane uslugi
  (`GetCapabilities`, `DescribeFeatureType`, pola warstwy ArcGIS) sa
  pobierane swiezo raz na pobranie, bez cache metadanych: kontrola typu
  i DefaultCRS dotyczy stanu uslugi z chwili pobrania, a uzycie lokalnej
  wersji nie wysyla zadnego zapytania.
- D4. Kolejnosc osi BBOX jest parametrem kanalu z testem na prawdziwej
  odpowiedzi: GUGiK `urn:...:EPSG::2180` = N,E, CUZK EPSG:5514 = X,Y
  (obie zgodne z EPSG); zamiana daje pusty wynik bez bledu.
- D5. Wynik `feature_bbox`: jeden GPKG w ukladzie natywnym uslugi
  (DefaultCRS), pelne geometrie obiektow przecinajacych obszar (bez
  przycinania; obiekt wieloczesciowy - powtorzone `<ms:geom>` EGiB -
  w calosci dzieki `GML_FETCH_ALL_GEOMETRIES=YES`), warstwa na warstwe
  zrodla; bajty deterministyczne w obrebie jednej wersji GDAL (obiekty po
  identyfikatorze, schemat z metadanych uslugi - GML czytany z `XSD=`
  odpowiedzi `DescribeFeatureType`, `WRITE_GFS=NO`, `DOWNLOAD_SCHEMA=NO`
  - i staly `OGR_CURRENT_DATE`). Pola zmienne w czasie niezaleznie od
  obiektow (`drop_fields`; EGiB `DATA` = data stanu danych powiatu
  w usludze zbiorczej, rozna miedzy powiatami i odswiezana nawet co dobe)
  sa poza GPKG - inaczej kazde pobranie bylo nowa wersja - a ich wartosci
  w sidecarze `extra.source.dropped_fields` (pole -> wartosci). GPKG
  skladany na dysku lokalnym (SQLite nie zapisuje na wolumenie
  sieciowym), potem staging magazynu. Nowa zaleznosc `pyogrio` (GDAL
  wektorowy).
- D6. Magazyn i sygnaly: kazdy plik przez `FileSlot` i
  `use_local`/`store_file`/`fetch_version`/`inspect_version`; sygnal =
  `update_signal` kanalu: paczki GUGiK i wszystkie wyniki WFS/REST
  `none`, pliki CUZK `http`, pliki z feedu ATOM `metadata`. Etykieta:
  produkty z wydaniem w segmencie (rocznik BDOT10k, rok modeli 3D) -
  wydanie (`label_source="edition"`), pozostale `downloaded`.
- D7. D23 miedzy wydaniami: `FileSlot.related_roots` - gdy w slocie nie
  ma wersji o tym sha256, szukana jest w slotach pokrewnych (inne wydania
  tego produktu, formatu i jednostki); trafienie = dowiazanie twarde do
  istniejacych danych, status `relabeled`, `same_as` = etykieta
  znalezionej wersji (spec 9.3: identyczne roczniki bez duplikatu).
- D8. Uklad `data/` (rozszerzenie reguly 8): `<grupa>/<kraj>_<zrodlo>
  [_<tokeny>]/{teryt/<T>|bbox/<coords>|country/<kod>}<ext>`; `coords`
  w ukladzie natywnym (`.10g`), tokeny `[a-z0-9.-]`, plik krajowy
  `country/pl` albo `country/cz`; wersje w `<segment>/versions/<ta sama
  hierarchia>/`. Tokeny = wariant tresci (poziom, LoD, rocznik): wynik
  obszaru (zawsze GPKG w ukladzie natywnym) bez tokenu formatu; paczka
  i plik krajowy z tokenem formatu zrodla, gdy produkt ma kilka formatow
  albo takze wynik obszaru, a gdy zrodlo publikuje plik w kilku
  ukladach - takze z kodem EPSG (doprecyzowanie przykladow specu 7:
  `boundaries/pl_prg_<poziom>/bbox/`, `landcover/cz_zabaged/bbox/`,
  `landcover/cz_zabaged_gpkg_5514/country/cz.zip`,
  `models3d/pl_buildings_lod1_<rok>/teryt/` bez formatu - jeden format,
  brak wyniku obszaru). Rozne tresci nigdy nie dziela slotu.
- D9. CLI (uzupelnienie ADR-039): grupy `boundaries`, `cadastre`,
  `models3d` (plan C) i `hydro` (plan D), modul na grupe z `download`
  i `list-sources`; wybor `--product` + `--country pl|cz|auto` (jak
  `elevation`/`imagery`; `landcover` zostaje z `--source`); `--teryt`,
  `--whole-country`, `--level` (granice dla obszaru; nazwy krajowe:
  PL `wojewodztwo|powiat|gmina|jednostka-ewidencyjna|obreb`, CZ
  `kraj|okres|obec|katastralni-uzemi`; z `--country auto` w skladni per
  kraj `pl=gmina,cz=obec` jak `--resolution`), `--lod 1|2`, `--year`,
  `--horizontal-crs` (tylko gdzie plik krajowy ma kilka ukladow; plan D:
  `landcover --source zabaged`). Produkty: `admin` (PRG, RUIAN), `map`
  (EGiB - mapa ewidencyjna), `buildings` (modele 3D), `network`
  (HY-NET). Nowe produkty bez `--layers` (stala zawartosc). Parser
  kazdej komendy `download` ustawia `_handler` i `_task` (ADR-040).
- D10. Biblioteka: `download_collection`/`check_collection`
  (`CollectionReport`: `files` z `UnitFile`, `failed` z `UnitFailure`,
  `stale`, `notices`, `ok`), walidacja bez sieci
  `validate_collection_request`, tor planu `collection`. `landcover
  download` zostaje `LandCoverManager` (ADR-039 D8) i deleguje archiwum
  BDOT10k oraz ZABAGED do silnikow kolekcji.
- D11. Archiwum BDOT10k: `--year 2014..2025` z wymaganym `--format
  GML|SHP` (brak GPKG; z `--year` odrzucone `GPKG`, `--layers`,
  `--keep-raw`), ZIP 1:1, `landcover/pl_bdot10k_<format>_<rok>/teryt/<T>.zip`,
  etykieta = rok, `none`, D7 dla identycznych rocznikow; 404 powiatu
  (zmiana TERYT, brak paczki) = `NoCoverageError` tego powiatu.
- D12 (plan D). `atom_files`: feed uslugi ATOM -> feed zbioru -> link
  `alternate` z `length`; wpis wybierany wyrazeniem regularnym na id
  zbioru (grupy nazwane) albo jedyny zbior + kategoria CRS; wydanie
  (`metadata`) z `<updated>` wpisu; indeks feedu uslugi w MetadataCache
  odswiezany warunkowym GET (ETag).
- D13 (plan D). Ortofoto CZ: `imagery download --product orto
  --country cz` (arkusz albo obszar -> arkusze SM5 z indeksu), czlony
  ZIP bez konwersji pikseli jako `<godlo>.jpg`, `<godlo>.jgw` (S-JTSK),
  `<godlo>.TM33N.jgw`, `<godlo>.TM34N.jgw`, kazdy plik wersjonowany
  w `orto/cz_sjtsk/<hierarchia SM5>/`; etykieta `<rok>_<updated>`,
  sygnal `metadata`. Wzorzec godla SM5 przyjmuje 2 litery (As).
- D14 (plan D). Wycinek ortofotomapy PL z WCS w magazynie (czesciowo
  zastepuje ADR-036 D27): `imagery download --product orto --cutout
  --horizontal-crs EPSG:2180 --coverage standard|high --resolution
  0.1m|0.25m|0.5m|1m`, `orto/pl_1992_<coverage>_<res>/bbox/<coords>.tif`,
  `none`, bez maski ladu, kawalki do 4 Mpx natywnych, konfiguracja
  w `WcsCutoutParams` kanalu WCS; `GugikOrtoProvider.download_bbox`
  zostaje surowym API poza magazynem.
- D15 (plan D). ZABAGED: `landcover download --source zabaged`; obszar
  -> GPKG EPSG:5514 z 22 warstw pokrycia i hydrografii REST (nazwy =
  kody ASCII nazw warstw), `--whole-country --horizontal-crs
  EPSG:5514|EPSG:3045` -> krajowy `ZABAGED-<kod>-gpkg-<data>.zip`
  z feedu (`metadata`); bez mapowania klas na kody BDOT10k.
- D16 (plan D). Grupa `hydro`, `--product network` (HY-NET): obszar ->
  GPKG EPSG:5514 (3 typy WFS), `--whole-country` -> `HY-NET.zip`
  (EPSG:3045 wg feedu, `http`).
- D17 (plan D). RUIAN: `boundaries --product admin --country cz`; obszar
  -> REST warstwy 17/15/12/7, `--whole-country` -> `shp/stat/epsg-5514/1.zip`
  (`http`).

**Konsekwencje:** Kolejne produkty planu E wchodza jako deskryptory
z parametrami (nowy protokol, np. OGC API Features, rozszerza
`FeatureBBoxParams.protocol` razem z pierwszym produktem). `pyogrio`
dochodzi do zaleznosci (ok. 100 MB kola z GDAL obok GDAL `rasterio`).
Wynik WFS/REST jest migawka bez sygnalu: `--check-updates` raportuje
`unverifiable`, nowa tresc daje dopiero `--force`. Pliki krajowe moga
miec inny uklad niz wynik obszaru (HY-NET 3045 vs 5514) - sidecar podaje
faktyczny. Szczegoly i pomiary: `docs/research/2026-10-15-plan-c-d/raport.md`,
plany `docs/superpowers/plans/2026-10-15-plan-c-*.md`, `...-plan-d-*.md`.

**Errata 1 (2026-10-16, plan D Task 2, D12):** indeks feedu uslugi ATOM
lezy w `MetadataCache` (tabela `atom_cache`, klucz = feed + `entry_pattern`)
razem z `ETag` feedu: w TTL (7 dni) bez zapytania; starszy indeks oraz
`--upgrade` i `--check-updates` (`refresh`) wysylaja warunkowy GET
(`If-None-Match`; 304 = indeks bez zmian). Klucz brakujacy w indeksie
z cache albo 404 feedu zbioru = JEDNO odswiezenie indeksu (nieaktualny
cache nie ukrywa nowego rocznika). Feed zbioru (ok. 1,4 KB) jest czytany
zawsze swiezo - jego wpis niesie wydanie. Etykieta wersji = data
`updated` wpisu PLIKU w feedzie zbioru, poprzedzona grupa `year` wzorca,
gdy ja ma (`2024_2025-02-06` ortofoto, `2026-10-04` ZABAGED). Feed uslugi
jest czytany strumieniowo (ORTOFOTO: 23,7 MB, 16 301 wpisow), limit
odczytu 120 s, feed zbioru 60 s. Klucz spoza feedu = `NoCoverageError`;
HTML zamiast feedu, wpis bez dokladnie jednego linku `alternate`, kilka
plikow bez rozstrzygniecia, rozmiar inny niz `length` feedu albo
`Content-Length` = `DownloadError`; uklad spoza kategorii feedu =
`ValidationError` bez sieci. Czlony ZIP (`AtomFilesParams.members`) sa
kopiowane 1:1, najdluzszy sufiks najpierw (`.TM33N.jgw` przed `.jgw`).

**Errata 2 (2026-10-16, plan D Task 3 i test na zywo, D3, D5, D16):**
wynik obszaru HY-NET ma 2 warstwy, `WatercourseLink` i `HydroNode` (nie
3 typy WFS): `WatercourseSeparatedCrossing` nie ma geometrii w GML (to
relacja dwoch odcinkow `net:element`), a GeoServer dla zapytania z BBOX
podaje `hits` 0, choc strony zwracaja obiekty (30 x 30 km: 0 wobec 4,
100 x 100 km: 0 wobec 24) - kompletnosci D3 nie da sie sprawdzic.
Skrzyzowania sa w pliku krajowym (`--whole-country`). Kody i nazwy warstw
GPKG = nazwy typow WFS. `DescribeFeatureType` HY-NET to tylko
`xsd:include` zdalnego schematu INSPIRE: taki XSD nie trafia do GDAL
(D5 "schemat z metadanych uslugi" nie dotyczy tej uslugi) - pola sa
czytane z tresci kazdej strony, warstwa dostaje sume pol stron
w kolejnosci pierwszego wystapienia (brak pola = null, jedno pole o dwoch
typach = `DownloadError`), wiec schemat zalezy od tresci: ten sam typ moze
miec w innym obszarze inne pola (strona z jednym wezlem nie ma
`hydroNodeCategory`). Pusta warstwa bez schematu XSD (0 obiektow typu)
= warstwa z samym polem `gml_id` (geometria `Unknown`), nie schemat bez
obiektow z D3. Usluga przekierowuje domyslny `User-Agent` curla (302) na
PDF z warunkami; Kartograf wysyla `kartograf/<wersja>`. Plik krajowy:
ZIP 1:1 z wymaganym czlonem `.gpkg` (`hydro/cz_hynet_gpkg/country/cz.zip`,
ok. 194 MB), tylko EPSG:3045 (inne `horizontal_crs` = `ValidationError`).
Produkt tylko CZ: `--country pl` = blad, `auto` zaweza do CZ
(`auto_narrowed_to_cz`), `--level` = blad (stala zawartosc).

**Errata 3 (2026-10-16, plan D Task 3, D10, D15, D17):** ZABAGED: 22
warstwy obszaru (id i kody w `registry.py::_ZABAGED_LAYERS`; linie 93
`vodni_tok` i 112 `brehova_cara`, reszta poligony), strona 2000,
`orderByFields=OBJECTID`, id `fid_zbg`. Opis warstwy GPKG
(`gpkg_contents.description`) = nazwa warstwy ArcGIS w pisowni uslugi
z id (`Vodní tok (93)`, RUIAN `Obec (12)`). Plik krajowy = ZIP 1:1 (czlon
`ZABAGED_RESULTS.gpkg`) w `landcover/cz_zabaged_gpkg_<5514|3045>/country/cz.zip`
z warstwami pelnej bazy pod nazwami CUZK (np. `VodniPlocha_c`), innymi niz
kody wyniku obszaru; rozmiar z `length` feedu w `Notice`
`whole_country_size` przed transferem (wydanie 2026-10-04: 5,8 GB
EPSG:5514, 6,7 GB EPSG:3045). `LandCoverManager(output_dir, "zabaged")`
(`COLLECTION_SOURCES`, bez klasy providera): `teryt`, `format`, `layers`,
`keep_raw`, `year` = `ValidationError` z nazwa zrodla (takze
w `validate_request`), `sheet` = blad (obszar CZ: `bbox`/`geometry`),
`horizontal_crs` z obszarem = blad (wynik zawsze EPSG:5514); blad
pobrania jest wyjatkiem, nie pozycja `failed` (jeden plik na zapytanie,
jak CORINE). RUIAN: `kraj`=17 `VyssiUzemneSamospravnyCelek`, `okres`=15
`Okres`, `obec`=12 `Obec`, `katastralni-uzemi`=7 `KatastralniUzemi`
(nazwy warstw GPKG), strona 1000, `orderByFields=objectid`, id `kod`;
plik krajowy `boundaries/cz_ruian_shp/country/cz.zip` (ZIP 1:1, wymagany
czlon `.shp`, ok. 253 MB, `http`). Pod `auto` poziom per kraj
(`{"pl": "gmina", "cz": "obec"}`; jedna wartosc niedostepna w ktoryms
kraju = blad z podpowiedzia `--level pl=<poziom>,cz=<poziom>`);
`--teryt` z `--country cz` i godlo CZ jako obszar kolekcji = blad.
Zapis GPKG (D5) trzyma cala warstwe w pamieci - ryzyko dla bardzo
duzych obszarow.

**Errata 4 (2026-10-16, plan D Task 4, D13):** ortofoto CZ to tylko
aktualny rocznik arkusza (archiwalne ortofoto CUZK sa platne): z
`--country cz` flagi `--year`, `--min-year`, `--max-year`,
`--all-campaigns`, `--full-sheet`, `--sheet-system`, `--scale`,
`--vertical-crs` i `--format` = `ValidationError` (pod `auto` flagi
kampanii i arkuszy dzialaja dla czesci PL); kafel TM33 jako `--sheet` =
blad z podpowiedzia SM5, `--cutout` z CZ = blad. Obszar pod `auto` daje
arkusze PL i arkusze SM5 CZ (dotad `auto_narrowed_to_pl` - orto nie
mialo zrodla CZ); `--resolution` z orto bez `--cutout` = blad dla obu
krajow (piksel arkusza wynika ze zrodla). Sidecar JPEG: `horizontal_crs`
EPSG:5514 i `extra.world_files` = `{".jgw": "EPSG:5514", ".TM33N.jgw":
"EPSG:3045", ".TM34N.jgw": "EPSG:3046"}` (pomiar 2026-10-16 na CTES96,
CTES86 i AS91: poczatek plikow TM = poczatek S-JTSK przeliczony do
EPSG:3045/3046 z dokladnoscia 0,03 m); sidecar kazdego JGW ma
`horizontal_crs` swojego ukladu. JGW nie niesie ukladu - w GIS przypisuje
go uzytkownik (JPEG + `.jgw` = EPSG:5514). Jedno sprawdzenie wydania na
arkusz (jedno `resolve_atom_file`, porazka zapamietana): cztery pliki
dziela wynik, `check_failed` raz na arkusz. Kolejnosc zapisu `.jgw`,
`.TM33N.jgw`, `.TM34N.jgw`, `.jpg`: wersja JPEG zawsze ma pliki JGW, plik
z nieudanym zapisem nie ma wersji (nastepne uruchomienie go dopisuje).
API: `download_cz_orto_sheet`/`check_cz_orto_sheet` (`CzOrtoResult`),
tor planu `cz_orto`, jednostka = godlo.

**Errata 5 (2026-10-16, plan D Task 5, D14):** wycinek ortofotomapy
tylko w EPSG:2180 (obraz nie jest przeprobkowywany lokalnie;
`--horizontal-crs` wymagane, inna wartosc = blad), `--coverage`
i `--resolution` wymagane bez wartosci domyslnych (wybory z kanalow WCS
rejestru), tylko kompozycja RGB, bez wyboru roku (kompozycja serwera).
Zakres jest wyrownany NA ZEWNATRZ do wielokrotnosci piksela, a wynik
sprawdzany (rozmiar, krok, naroznik NW, 3 pasma uint8, EPSG:2180): inna
siatka = `DownloadError` bez wersji. Nieparzysta liczba pikseli 0,25 m
to ulamek pikseli coverage 0,1 m - serwer odpowiada zla siatka albo
HTTP 400 - dlatego kawalki maja parzyste rozmiary. Budzet kawalka
GeoTIFF liczony w pikselach coverage (jak ASC): 4 Mpx = 200 x 200 m
niezaleznie od piksela wyniku; limit odczytu kawalka 300 s (pomiar
2026-10-15: 4 Mpx Standard 64 s, 2000 x 2000 px przy `SCALEFACTOR=0.4`
176 s). Zszyte kawalki NIE sa bit w bit rowne jednemu zapytaniu
(errata 1 ADR-034). High poza obszarami pikseli 10 cm odpowiada HTTP 200
z obrazem 0,0,0: wersja powstaje z `extra.all_nodata: true` i `Notice`
`all_nodata` (ostrzezenie); maski ladu PRG nie ma. Pobranie sprawdza
miejsce na dysku (2 x rozmiar wyniku) i zapowiada `cutout_size` dla
wiecej niz jednego zapytania albo >= 1 GiB. Sidecar: `resolution`
(z deskryptora) = `null`, piksel i wariant w `request.resolution`
i `request.coverage`, `extra.source` = faktyczny endpoint, coverage id,
format, `scalefactor` (piksel inny niz 0,1 m) i `composition: server`;
pola ukladow z pierwszego kanalu `bbox_raster` (Standard i High maja te
same). Nazwa `pl.gugik.orto`: `Ortofotomapa (arkusze wg kampanii; wycinek
WCS Standard i High)`. Pod `auto` `--coverage` i `--resolution` orto
zawezaja zadanie do PL (`auto_narrowed_to_pl`); obszar tylko w CZ =
blad. API: `download_orto_cutout`/`check_orto_cutout`
(`OrtoCutoutResult`), tor planu `pl_cutout`.

---

## ADR-043: Plan E: produkty jednostkowe, arkuszowe i krajowe na silnikach C/D

**Data:** 2026-10-16
**Status:** Przyjeta; czesciowo zastepuje ADR-042 (D1: capability kanalu kolekcji unikalna w deskryptorze); uzupelnia ADR-042 (jednostki arkuszy, kafli i KU, tematy plikow krajowych, rekord indeksu i sygnal `index`, OGC API Features, wybor kanalu po wartosciach opcji, `DOWNLOAD_SIZE`), ADR-039 (grupy `names`, `maps`, `geodesy`) i ADR-041 (NMT 100 m w rejestrze wariantow bez ukladu wysokosci)

**Kontekst:** Plan E (spec katalogu 6, 24 pozycje) dodaje produkty GUGiK
i CUZK, ktorych plik nie jest paczka jednostki TERYT ani wynikiem obszaru
z planow C/D: arkusze map (wizualizacje BDOT10k: link pliku tylko
w GetFeatureInfo WMS; ZTM CUZK: arkusze warstw indeksu
`KladyMapovychListu`), kafle z rekordow WFS (mesh 3D: URL, data i numer
zgloszenia w rekordzie), paczki katastralnich uzemi CZ (KU z RUIAN), pliki
krajowe z kilku tematow (PRNG), pliki bez ZIP (TIFF, PDF, TXT
PL-geoid2021), uslugi OGC API Features (PRNG, granice specjalne PRG) i
produkty z osobna usluga na siec albo feedem na format. Pomiary
2026-10-15/16 (`docs/research/2026-10-15-plan-e/raport.md`, fixtury
`tests/fixtures/pl/{e0,index_records,feature_bbox}/`,
`tests/fixtures/cuzk/real_2026_10_16/`): kazde zapytanie `items` OGC API
PRNG trwa 78-95 s niezaleznie od `limit` (`/collections` ponizej 0,4 s;
OGC API PRG odpowiada w 3,5 s); indeks mesh publikuje przestrzen nazw
`https://www.gugik.gov.pl` (indeksy NMT/NMPT/LAZ `http://`), jeden rekord
na kafel (Krakow: 3884 kafle po ok. 37 MB); GFI wizualizacji BDOT10k poza
zasiegiem warstwy daje 0 B; WFS osnowy grawimetrycznej odpowiada pod
`.../OsnowaGrawimetryczna/WFS` (bez `/WFS` nie), bez `gml:id`; serwery
GUGiK sporadycznie zrywaja polaczenie (`RemoteDisconnected`), ponowienie
odpowiada 200; GUGiK `opendata` nie wysyla `ETag` ani `Last-Modified`,
a plik `latest_exports` RCN jest podmieniany (1261: 236 404 584 B
2026-10-15, 301 623 607 B 2026-10-16).

**Opcje:**
- A) Provider per produkt (mapy, mesh, mapa katastralna CZ).
- B) Rozszerzenie silnikow i orkiestratora planow C/D o jednostki, adres
  z rekordu indeksu i nowe parametry kanalow; produkt = deskryptor.
- C) WMS jako kanal danych (obraz mapy zamiast pliku arkusza).

**Decyzja:** B (bez drugiego silnika i bez providera kopiujacego
pobieranie). A powiela pobieranie, magazyn i sygnaly (zasada planu C);
C daje obraz uslugi zamiast opublikowanego pliku - WMS jest tylko
indeksem (GFI). Kod: Task E0 planu E
(`docs/superpowers/plans/2026-10-15-plan-e-produkty.md`).
- D1. Jednostki `unit_package`: `UnitPackageParams.unit` += `sheet`
  (arkusze obszaru albo arkusz `--sheet`), `tile` (rekordy indeksu WFS
  w obszarze), `ku` (katastralni uzemi CZ: `--ku` 6 cyfr albo KU obszaru
  z warstwy RUIAN `ku_layer`, pole `kod`, `returnGeometry=false`);
  `themes`: plik krajowy z kilku plikow, kazdy temat osobna jednostka
  `country/<kraj>-<temat>` (malymi literami, `_` -> `-`). Tokeny szablonu
  URL += `{sheet}`, `{ku}`, `{theme}`. Sloty (rozszerzenie ADR-042 D8):
  arkusz PL `<segment>/<hierarchia godla>/<godlo>`, arkusz CUZK plasko
  `<segment>/<MAPNOM>`, kafel `<segment>/<strefa>/<modul>` (strefa
  z pola ukladu rekordu: `PL-2000:S7` -> `s7`; bez pola `tile/`), KU
  `<segment>/ku/<kod>`, temat `<segment>/country/pl-<temat>`. `sheet=`
  produktow C/D dalej znaczy obszar arkusza (ADR-039 D4); jednostka
  arkusza powstaje tylko w kanale `unit="sheet"`.
- D2. Siatka arkuszy jest cecha wariantu (`PackageVariant.sheet_grid`,
  skala mapy ma swoja siatke): `SheetGrid(system="1992", parts=N)` -
  seria PL-1992 o N czlonach godla liczona z obwiedni
  (`find_sheets_for_bbox`; etykiety skal `SheetParser` sa o poziom
  drobniejsze niz nomenklatura GUGiK, wiec seria jest nazwana liczba
  czlonow, nigdy etykieta skali; obszar w ukladzie spoza PL-1992/PL-2000/
  WGS84 przechodzi na EPSG:4326); `SheetGrid(system="cuzk", layer, crs)` -
  `MAPNOM` warstwy `KladyMapovychListu` pytanej w jej ukladzie
  (`SheetIndex.sheets_for_bbox(layer, bbox)`, `SheetIndex.sheet(layer,
  mapnom, crs=)`; SM5 i TM33 bez zmian); istnienie `--sheet` CZ jest
  sprawdzane w warstwie po zapytaniu (`ValidationError`). Siatki PL-2000
  nie ma: zaden produkt kolekcji planu E jej nie potrzebuje.
- D3. Rekord indeksu: `UnitPackageParams.index: IndexSource(kind, endpoint,
  parser, unit_field, url_field, label_fields, year_field, zone_field)`,
  warstwa w wariancie (`PackageVariant.index_layer`). `url_template=None`
  = URL z rekordu: jedyny link albo link formatu z `choice`
  (`index_url`). `transport/index_records.py`: `gfi_records` (WMS 1.3.0
  GetFeatureInfo w srodku ramki arkusza, osie N,E; parser `map_links` -
  tabela HTML wizualizacji BDOT10k: godlo, link na format z rozszerzenia,
  data "Stan bazy"; 0 B = brak rekordu) i `wfs_records` (`WfsIndex`: strony
  tylko po `next`, pola po nazwie lokalnej). Wyjatek OGC przy 200, HTML
  bez tabeli, tabela bez daty albo link bez HTTPS = `DownloadError`
  ("wynik bylby niepelny"); pojedynczy nieuzywalny obiekt WFS jest
  pomijany z ostrzezeniem. Jednostka dostaje najnowszy rekord (rok, potem
  etykieta); `year` produktu bez wariantow rocznych jest filtrem rekordow
  (ADR-028), nie wyborem wariantu. Arkusz bez rekordu jest pomijany
  i wypisany w `UNIT_LIST`; zaden arkusz z rekordem = `NoCoverageError`.
- D4. Sygnal `index` w kolekcjach: etykieta rekordu (`label_fields`
  laczone `_`, D29) jest wydaniem wersji (`label_source="edition"`),
  porownywanym przez `fetch_version`/`inspect_version`; `check_collection`
  pyta tylko indeks, nigdy pliku. Kanal kolekcji ma sygnal `index` wtedy
  i tylko wtedy, gdy ma `IndexSource` (test rejestru). LAZ bez zmian.
- D5. Wybor kanalu i wariantu po wartosciach opcji: `download_collection`/
  `check_collection`/`validate_collection_request` dostaja `ku`, `format`,
  `scale`, `sheet_system` i `network` (`str | None`; `teryt`, `ku`,
  `sheet` i te opcje innego typu niz `str` = `ValidationError`, bo kod
  z liczby traci zera wiodace). Dozwolone wartosci sa w deskryptorze
  (K1): `PackageVariant.choice`, `FeatureBBoxParams.choice` (jedna usluga
  WFS na siec), `AtomFilesParams.choice` (jeden feed na format). Z kilku
  kanalow rodzaju wyboru wygrywa ten, ktorego wartosci przyjmuja podane;
  brak wartosci rozrozniajacej = `ValidationError` z lista; jeden kandydat
  jest brany wprost (jego kontrola tresci podaje dozwolone wartosci).
  `FeatureBBoxParams.selection_key` nazywa opcje wyboru warstw przy
  `selection="level"` (`--level`; `network` dla osnow CZ); jeden `code`
  moze nazwac kilka warstw.
- D6. Capability kanalu kolekcji nie musi byc unikalna (czesciowo
  zastepuje ADR-042 D1): kanaly jednego rodzaju (usluga na siec) dziela
  capability. Sidecar czyta uklady z pierwszego kanalu tej capability,
  wiec kanaly, ktore ja dziela, deklaruja te same uklady (test rejestru).
- D7. OGC API Features w `feature_bbox` (`protocol="ogcapi"`,
  `TransportKind.OGC_API_FEATURES`): `/collections?f=json` raz na
  pobranie (brak kolekcji deskryptora = `DownloadError`), pierwsza strona
  `items?f=json&bbox=<CRS84 lon,lat>&limit=<page_size>`, kolejne tylko po
  `rel="next"` z tym samym schematem i hostem. N = `numberMatched`
  pierwszej strony - bez osobnego zapytania o liczbe, bo kazde `items`
  PRNG trwa 78-95 s. Kazda strona: `numberReturned` rowne liczbie
  obiektow i ten sam `numberMatched`; koniec przy N unikalnych `id`;
  wiecej niz N, strona bez nowych `id` albo brak `next` przed N =
  `DownloadError`. Wynik: GPKG w `OGC:CRS84` (jedyny uklad wyjscia uslug
  GUGiK). Wolna usluga deklaruje `FeatureBBoxParams.timeout`;
  pierwszenstwo: jawny `timeout` wywolania, kanal, `SERVICE_TIMEOUT`
  (60 s).
- D8. Pliki bez ZIP: `PackageVariant.file_kind` `zip|tiff|pdf|txt`
  (rozszerzenie `.zip`, `.tif`, `.pdf`, `.txt`), sprawdzane po pierwszych
  bajtach: magia TIFF (klasyczny i BigTIFF), `%PDF-`, tekst bez bajtow NUL
  z pierwsza niepusta linia, ktora nie jest znacznikiem (kodowanie bez
  znaczenia). Dokument HTML/XML zamiast pliku = `DownloadError`, bez
  wersji.
- D9. Rozmiar przed transferem (K9): przed `GET` kazdego pliku jednostki
  `HEAD`; plik ponad 100 MiB dostaje `Notice` `DOWNLOAD_SIZE` (ostrzezenie
  z URL i rozmiarem) w chwili swojego pobrania, takze w produktach C/D
  (jedno `HEAD` wiecej na paczke); plik krajowy dalej
  `WHOLE_COUNTRY_SIZE` (K7). Bez sumy rozmiarow wszystkich jednostek przed
  pierwszym `GET`: liste jednostek podaje `UNIT_LIST`.
- D10. Decyzje produktowe planu E (wykonanie w pakietach E1-E5): nowe grupy
  `names`, `maps` i `geodesy` (ADR-039; `geodesy` = osnowy PL i CZ oraz
  modele quasi-geoidy); nazwy produktow unikalne w kolekcjach; orto ukosna
  `--direction` jako filtr czterech plikow arkusza; 8-czlonowe godla
  PL-1992 w `SheetParser` (E1). NMT 100 m (decyzja uzytkownika
  2026-10-15): uklad wysokosci NIEZNANY - sidecar `vertical_crs: null`
  z adnotacja o zrodle, segment bez tokenu ukladu, `--vertical-crs` dla
  tego wariantu = blad. Mapa katastralna CZ w formacie VKM poza 0.8.0
  (pliki pilota 2026-10-15 odpowiadaly 404); SHP, DXF, DGN i VFK wchodza.

**Odrzucone:** provider per produkt (A); WMS jako kanal danych (C); plik
krajowy dla obszaru (obszar idzie zawsze kanalem obszarowym albo
jednostkami, ADR-042 D2, K7); narzedzie transformacji wysokosci
z quasi-geoida - Kartograf pobiera modele PL i CZ jako dane i nie stosuje
ich do innych danych (PROJ ma oficjalna siatke GUGiK); kanal REST
warstwic CZ (arkusze SM5 1:1 z `http`); GeoParquet RCN; pliku krajowego
BDOO; zapytanie o liczbe obiektow OGC API przed stronami (D7).

**Konsekwencje:** Produkty E1-E5 sa deskryptorami z parametrami (testy
rejestru pilnuja: wariant bez szablonu URL ma indeks, sygnal `index` tylko
z indeksem, tokeny szablonu z jednostki kanalu, siatka arkuszy i warstwa
indeksu w kazdym wariancie, wspolna capability = te same uklady). Kazde
pobranie paczki C/D wysyla jedno `HEAD` wiecej. Obszar duzego miasta daje
tysiace kafli mesh (Krakow: ok. 3884 x 37 MB, ok. 143 GB) - `UNIT_LIST`
pokazuje je przed transferem; ograniczenie nalezy do E5. Pobranie OGC API
PRNG trwa ok. 1,5 min na strone - `page_size` i `timeout` kanalu ustawia
deskryptor (E2). Arkusze CZ leza plasko w `<segment>/`, wiec tysiace
arkuszy daja jeden duzy katalog. Plik `latest_exports` RCN jest
podmieniany bez sygnalu (`none`): nowa tresc daje dopiero `--force`.

---

## Szablon nowego ADR

Kopiuj ponizszy blok przy dodawaniu decyzji: kolejny numer, status ze
slownika na poczatku pliku, nowy wiersz w indeksie i odsylacze po obu
stronach relacji. Erraty dopisuj na koncu wpisu.

```markdown
## ADR-XXX: Tytul

**Data:** RRRR-MM-DD
**Status:** Przyjeta | Przyjeta — czesciowo zastapiona przez ADR-YYY (zakres) | Przyjeta — uzupelniona przez ADR-YYY (zakres) | Zastapiona przez ADR-YYY | Odrzucona

**Kontekst:** Dlaczego temat powstal.

**Opcje:**
- A) ...
- B) ...

**Decyzja:** Ktora opcja i dlaczego.

**Konsekwencje:** Co z tego wynika.

**Errata 1 (RRRR-MM-DD, zrodlo/powod):** Dopisywane pozniej.
```
