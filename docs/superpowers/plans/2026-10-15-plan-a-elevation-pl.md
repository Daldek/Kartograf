# Plan A — `elevation` PL: rejestr wariantow, siatki NMT/NMPT we wszystkich rozdzielczosciach, skorowidz WFS i raport dostepnosci — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Data:** 2026-10-15

**Goal:** Jedna definicja wariantow produktu (rejestr K1) dla walidacji CLI/API,
`--help`, `list-sources`, segmentu magazynu i wyboru rekordu skorowidza;
arkusze NMT i NMPT GUGiK we WSZYSTKICH rozdzielczosciach publikowanych jako
siatka `ARC/INFO ASCII GRID` (NMT EVRF2007: 0.15m, 0.5m, 0.6m, 1m, 5m, 10m;
NMT KRON86: 0.5m, 1m; NMPT EVRF2007: 0.5m, 0.6m, 1m; NMPT KRON86: 0.5m, 1m);
rekordy arkuszy NMT/NMPT ze skorowidza WFS (ten sam indeks dla pobierania
i raportu); `check_availability` + `kartograf elevation availability`
(raport kompletu pelnych arkuszy/kafli PL dla NMT, NMPT i LAZ, bez
pobierania danych).

**Architecture:** Nowy modul danych `kartograf/sources/variants.py`
(`ProductVariant`, `IndexRef`, zapytania o warianty, etykiety K2) zasilany
deskryptorami (`SourceDescriptor.variants`); jeden deskryptor na (produkt,
rozdzielczosc). Nowy klient skorowidza WFS `kartograf/providers/pl/skorowidz_wfs.py`
(GetCapabilities, `GetFeature` z wieloma `TYPENAMES`, `BBOX` N,E, stronicowanie
`next`, mapowanie pol WFS na `SkorowidzRecord`, obrys arkusza) - uzywany przez
NMT/NMPT (zamiast WMS `GetFeatureInfo`), raport dostepnosci i LAZ (wspolny
transport WFS zamiast kopii w `gugik_laz.py`). Ortofotomapa zostaje na WMS.
Nowy modul `kartograf/download/availability.py` (API raportu, rasteryzacja
na siatce 1 m z maska ladu PRG), nowa komenda `kartograf elevation availability`
(`kartograf/cli/availability_cmd.py`). Regula "5m tylko EVRF2007", "NMPT tylko
1m" i listy `("1m", "5m")` znikaja z kodu - sa danymi rejestru.

**Spec:** `docs/superpowers/specs/2026-10-13-katalog-produktow-design.md`
(zaakceptowany 2026-10-13, wersja docelowa 0.8.0) - K1-K4, K8, sekcje 3, 4,
6.1, 7, 8. Pomiary do tego planu:
`docs/research/2026-10-15-plan-a-b/raport.md` (pelna inwentaryzacja WFS,
WMS a WFS, czasy zapytan, nazwy plikow) oraz
`docs/research/2026-10-13-katalog-produktow/{raport,probki,pokrycie}.md`.

**Wersja docelowa:** 0.8.0 (razem z manifestem projektu i planami B-E; bez
wydania posredniego). **ADR:** ADR-041 (numer przydzielony przez
koordynatora; tekst dopisywany w Task 2 i uzupelniany w Task 8).

**Kod wyjsciowy:** `develop` `bcdf37d` (grupy CLI ADR-039 scalone w `dd5641b`;
spec, plan i ADR-040 manifestu projektu scalone, KOD manifestu moze jeszcze
nie byc na `develop` - kroki warunkowe w Task 7). Przed startem:
`git log --oneline -5 develop` i sprawdzenie numerow linii z sekcji "Fakty"
(przesuniecia linii nie zmieniaja planu; zmiana symbolu = zatrzymaj sie i
opisz roznice koordynatorowi).

---

## Weryfikacja specu wzgledem kodu i pomiarow (2026-10-15)

1. **Rozdzielczosci siatek (rozstrzyga "wszystkie rozdzielczosci"):** pelna
   inwentaryzacja WFS (raport 1.1) - siatki `.asc` istnieja w 0,15; 0,5; 0,6;
   1; 5 i 10 m (nie tylko 0,5/1/5). NMT 5 m jako siatka istnieje wylacznie
   w EVRF2007; w KRON86 siatki NMT sa tylko 0,5 m i 1 m. Rejestr zawiera
   dokladnie te kombinacje.
2. **Formaty archiwalne poza zakresem pobierania:** WFS zawiera tez
   `ASCII XYZ GRID`, `ASCII NMT`, `ASCII TBD`, `ESRI TIN`, `Intergraph TTN/GRD`,
   warstwice DXF/DGN (raport 1.2; m.in. jedyne zrodlo 15-50 m, czesc
   arkuszy 1:25000, inne nazwy plikow). Spec przed rewizja obejmowal 0,5 m
   i istniejace siatki; rewizja 2026-10-15 (spec 3.2) obejmuje wszystkie
   siatki z inwentaryzacji, a archiwa zostaja poza pobieraniem - raport
   dostepnosci wypisuje je jako `Info:` (decyzja 7). Pytanie do uzytkownika
   w raporcie koncowym planowania (rekomendacja: nie w 0.8.0).
3. **Skorowidz WMS nie ma 10 m, raport musi uzyc WFS:** WMS
   `SkorowidzeUklad{EVRF2007,KRON86}` ma siatki 0,15-1 m, `SheetsGrid5mEVRF2007`
   ma 5 m, zaden nie ma 10 m; WFS jest nadzbiorem WMS dla siatek (te same URL
   dla `M-33-59-D-a-2-1`, `M-34-64-D-d-2-1`), a jedno zapytanie `GetFeature`
   z `TYPENAMES` wszystkich warstw rocznych trwa 0,7 s (17 warstw KRON86).
   Pobieranie przechodzi na WFS (decyzja 4), zeby raport i pobieranie mialy
   jeden indeks.
4. **Ten sam arkusz w dwoch formatach:** w 18 003 (NMT EVRF2007) i 87 100 (NMT
   KRON86) parach warstwa-arkusz ten sam arkusz ma pliki w dwoch formatach
   (`.asc` + `.xyz.zip` tego samego zgloszenia, tez dwa rozne archiwa).
   Dzis WMS pokazuje tylko siatki; po przejsciu na WFS format musi byc twardym
   filtrem jak rozdzielczosc (ADR-028): `format == "ARC/INFO ASCII GRID"`
   I sciezka URL konczaca sie `.asc` albo `.xyz` (errata 2026-10-15, Task 9:
   42 rekordy NMT 2019 kampanii 72675 z URL `.xyz` maja w srodku AAIGrid -
   naglowki wszystkich sprawdzone na zywo - wiec sa siatkami, jak w 0.7.x;
   ADR-041 uzupelnienie R6).
5. **Serwer ignoruje `FILTER`** (raport 1, `RESULTTYPE=hits`) - filtry po
   stronie klienta; stronicowanie wylacznie po atrybucie `next`,
   `numberReturned` musi zgadzac sie z liczba obiektow (jak PRG P6).
6. **Kod z zaszytymi wariantami (do usuniecia):**
   `kartograf/download/options.py:41` `RESOLUTION_PL`, `:42-45`
   `VERTICAL_CRS_PL` (tekst "nie dla NMT 5m"), `:143-162` listy `("1m", "5m")`
   i "nmpt tylko 1m", `:180-190` `require_nmt_vertical_crs`, `:446-470`
   `resolve_pl_options` (domysle 1m dla NMPT);
   `kartograf/providers/pl/__init__.py:28-68` `NMT_5M_VERTICAL_CRS`,
   `nmt_vertical_crs`, `require_nmt_vertical_crs`;
   `kartograf/providers/pl/gugik.py:90` `SUPPORTED_RESOLUTIONS`, `:105-114`
   `WMS_INDEX_ENDPOINTS`, `:142-143` `SUPPORTED_VERTICAL_CRS(_5M)`, `:177-196`
   walidacja w `__init__`, `:206` `descriptor_key = f"pl.gugik.nmt_{resolution}"`,
   `:312` i `:320` `float(self._resolution[:-1])`, `:340-411` `_variant_hints`
   po WMS, `:532-555` `get_supported_resolutions`/`get_supported_vertical_crs_for_resolution`;
   `kartograf/providers/pl/gugik_nmpt.py:48` `SUPPORTED_RESOLUTIONS = ["1m"]`,
   `:63-74` `WMS_INDEX_ENDPOINTS`, `:86`, `:113-131` (`resolution="1m"` na
   sztywno); `kartograf/download/storage.py:66` `SUPPORTED_RESOLUTIONS`,
   `:132-137` `_RESOLUTION_SOURCES`/`_PRODUCT_SOURCES`;
   `kartograf/download/cutout.py:220` klucze deskryptorow na sztywno;
   `kartograf/download/area.py:133-149` `pl_only_flags` (`nmpt`, `1m`,
   `KRON86` na sztywno); `kartograf/cli/groups/elevation.py:30-37`
   (`_source_choice` z `source.resolution`) i `:94-105` (tekst `--resolution`).
   Regula "5m tylko EVRF2007" jest w trzech miejscach - backlog A5-4 zamykany
   tym planem.
7. **`campaign_extension`** (`kartograf/download/campaigns.py:337-353`) zna
   tylko `ARC/INFO ASCII GRID -> .asc` - po filtrze z punktu 4 zostaje bez
   zmian. `verify_record_url` (`:511-527`) dziala dla nazw siatek
   (`<id>_<n>_<godlo>.asc`) - bez zmian.
8. **P10 (podpowiedz wariantu, decyzja uzytkownika 2026-10-09)** zostaje:
   inne rozdzielczosci arkusza przychodza w tej samej odpowiedzi WFS (bez
   dodatkowych zapytan), inny uklad wysokosci = jedno zapytanie WFS do drugiej
   uslugi (ta sama polityka co dzis: jedna proba, usluga z bledem pomijana do
   konca zycia providera).
9. **Pomiar oczekiwanych wynikow raportu (2026-10-15, siatki `.asc`, siatka
   1 m, PRG):** Krakow NMT EVRF2007: 2025, 2024, 2023, 2022, 2019 PL-1992 1m
   kompletne (6 TAK); 2023 i 2021 PL-2000 1m kompletne (15 TAK); 2019 5m
   kompletna (6 TAK); rocznik 2018 ma tylko archiwa (XYZ 1 m x4, XYZ 5 m x2,
   TBD 25 m x2) - nie jest kombinacja. Pomorze (lad 863 767 m2): NMT EVRF2007
   2025 0.5m - 4 NIE (`N-33-58-A-c-1-3`, `-1-4`, `-2-3`, `-3-1`), brak
   niepokrytego ladu; 2022 1m - 3 TAK, niepokryte 8 782 m2; NMPT EVRF2007
   2025 0.5m - 4 NIE. Spec 4.4 zaktualizowany do tych wartosci (rocznik 2018
   jako archiwa zamiast "2018 1 m niekompletna").

## Global Constraints

- Python z `.venv` uruchamiany Z KORZENIA worktree: `.venv/bin/python -m pytest`,
  `-m ruff`, `-m mypy`, CLI `python -m kartograf.cli.commands ...`.
- TDD: kazdy krok "Test RED" - test zachowania, uruchom, zobacz porazke z
  WLASCIWEGO powodu, dopiero potem implementacja. Bez testow okablowania,
  kopii stalych ani tekstu zrodla (STANDARDS 10).
- Testy offline; fixtury z prawdziwych odpowiedzi (Task 1). Sieci uzywaj tylko
  w swiadomych krokach live (Task 1 nagranie fixtur, Task 9 E2E); dane do
  `<katalog-danych>` z jawnym `--output`, nigdy repo ani `/tmp`; sciezki
  katalogu danych nie zapisuj w repo.
- Identyfikatory i docstringi po angielsku, komunikaty dla uzytkownika po
  polsku w ASCII (Z5), `ValidationError` przed siecia, `DownloadError` dla
  awarii zrodla (STANDARDS 11). CLI tylko tlumaczy (ADR-037).
- Brak wartosci domyslnych wplywajacych na dane: `--resolution` wymagane tam,
  gdzie wariant ma >1 rozdzielczosc (NMT i NMPT PL); jedyna dopuszczalna
  wartosc (wycinek 1m) moze byc pominieta (STANDARDS 11.2).
- Brama przed kazdym commitem zadania: `pytest tests/ -m "not live" -q`,
  `ruff check .`, `ruff format --check .`, `mypy kartograf/ tests/`.
  Commity Conventional po polsku, autor `Daldek <git@debever.pl>`, bez
  `Co-Authored-By`. `docs/DECISIONS.md` - zachowaj CRLF.
- Testy, ktore przypinaja usuwane zachowanie, usuwaj albo przepisuj na nowa
  intencje (lista w zadaniach) - bez podwojnych sciezek i aliasow.

## Decyzje implementacyjne

1. **Etykieta K2:** `0.15m`, `0.5m`, `0.6m`, `1m`, `5m`, `10m`. Wartosc w
   rejestrze to `Decimal` (`Decimal("0.5")`), etykieta z jednej funkcji
   `resolution_label(value) -> str` = `format(value.normalize(), "f") + "m"`
   (`Decimal("10").normalize()` to `1E+1` - stad `format(..., "f")`).
   Parsowanie flagi: wylacznie etykiety obecne w rejestrze (dokladny napis);
   `0,5m`, `50cm`, `0.50m` = `ValidationError` z lista etykiet. Etykieta jest
   tez czlonem segmentu (`nmt/pl_1992_0.5m_evrf2007`).
2. **Model rejestru** (`kartograf/sources/variants.py`, dane bez IO):

   ```python
   @dataclass(frozen=True)
   class IndexRef:
       """WFS sheet index of a variant: one service per product and height system."""
       endpoint: str      # https://mapy.geoportal.gov.pl/wss/service/PZGIK/NumerycznyModelTerenuEVRF2007/WFS/Skorowidze
       layer_prefix: str  # "SkorowidzNMT" -> feature types gugik:SkorowidzNMT<year>

   @dataclass(frozen=True)
   class ProductVariant:
       source: str                   # descriptor key = sidecar `dataset` ("pl.gugik.nmt_0_5m")
       product: str                  # "nmt" | "nmpt" | "laz"
       country: str                  # "PL" (plan B: "CZ")
       resolution_m: Decimal | None  # None: LAZ
       vertical_crs: str             # CLI name: "EVRF2007" | "KRON86" (plan B: "Bpv")
       format: str                   # "ASC" (plan B: "TIFF", "LAZ")
       systems: tuple[str, ...]      # PL: ("1992", "2000"); plan B: ("sm5",) / ("tm33",)
       channel: TransportKind        # PL sheets: TransportKind.WFS
       index_ref: IndexRef | None    # PL: skorowidz WFS; CZ: None (indeks KladyMapovychListu)

       @property
       def label(self) -> str | None: ...   # resolution_label(resolution_m)
   ```

   `SourceDescriptor.variants: tuple[ProductVariant, ...] = ()` (nowe pole,
   `kartograf/sources/descriptor.py:79-95`). Funkcje w `variants.py`:
   `variants(*, product=None, country=None, vertical_crs=None, resolution=None,
   system=None) -> tuple[ProductVariant, ...]` (kolejnosc rejestru; `system`
   filtruje `systems`),
   `resolution_label(value: Decimal) -> str`,
   `parse_resolution(label: str) -> Decimal | None` (`None` = nie etykieta K2),
   `source_format(record_format: str, url: str) -> str | None`
   (`"ARC/INFO ASCII GRID"` + URL `.asc` -> `"ASC"`, inaczej `None`).
   Spec 3.1 mial `horizontal: str` - zastapione krotka `systems` (PL: oba
   uklady; dostepnosc ukladu jest faktem skorowidza, nie rejestru; CZ w planie
   B wiaze uklad z kanalem).
3. **Zawartosc rejestru PL (z inwentaryzacji 2026-10-15):** jeden deskryptor na
   (produkt, rozdzielczosc); kanal arkuszy `AccessChannel(transport=WFS,
   update_signal="index", capabilities={"sheet_files"}, vertical_crs_options=...)`
   zamiast `WMS_SHEET_INDEX`; kanal WCS bez zmian tylko przy 1 m.

   | Klucz (`dataset`) | Produkt | Etykieta | Uklady wysokosci (`IndexRef`) | `storage_subdir` | WCS |
   |---|---|---|---|---|---|
   | `pl.gugik.nmt_0_15m` (NOWY) | nmt | 0.15m | EVRF2007 | `nmt/pl_{system}_0.15m_{vcrs}` | nie |
   | `pl.gugik.nmt_0_5m` (NOWY) | nmt | 0.5m | EVRF2007, KRON86 | `nmt/pl_{system}_0.5m_{vcrs}` | nie |
   | `pl.gugik.nmt_0_6m` (NOWY) | nmt | 0.6m | EVRF2007 | `nmt/pl_{system}_0.6m_{vcrs}` | nie |
   | `pl.gugik.nmt_1m` | nmt | 1m | EVRF2007, KRON86 | `nmt/pl_{system}_1m_{vcrs}` (bez zmian) | tak |
   | `pl.gugik.nmt_5m` | nmt | 5m | EVRF2007 | `nmt/pl_{system}_5m_{vcrs}` (bez zmian) | nie |
   | `pl.gugik.nmt_10m` (NOWY) | nmt | 10m | EVRF2007 | `nmt/pl_{system}_10m_{vcrs}` | nie |
   | `pl.gugik.nmpt_0_5m` (NOWY) | nmpt | 0.5m | EVRF2007, KRON86 | `nmpt/pl_{system}_0.5m_{vcrs}` | nie |
   | `pl.gugik.nmpt_0_6m` (NOWY) | nmpt | 0.6m | EVRF2007 | `nmpt/pl_{system}_0.6m_{vcrs}` | nie |
   | `pl.gugik.nmpt` | nmpt | 1m | EVRF2007, KRON86 | `nmpt/pl_{system}_1m_{vcrs}` (bez zmian) | tak |
   | `pl.gugik.laz` | laz | - | EVRF2007, KRON86 | bez zmian | - |

   `IndexRef` NMT: `.../NumerycznyModelTerenu{EVRF2007|KRON86}/WFS/Skorowidze`,
   prefiks `SkorowidzNMT`; NMPT: `.../NumerycznyModelPokryciaTerenu{EVRF2007|KRON86}/WFS/Skorowidze`,
   `SkorowidzNMPT`; LAZ: `.../DanePomiaroweLidar{EVRF2007|KRON86}/WFS/Skorowidze`,
   `SkorowidzDanychPomiarowychLIDAR` (dzis `GugikLazProvider.WFS_ENDPOINTS`,
   `kartograf/providers/pl/gugik_laz.py:476-484` - przeniesione do rejestru).
   `pl.gugik.nmpt` zostaje kluczem 1 m (istniejace sidecary); nowe klucze
   wg katalogu (`pl.gugik.nmt_0_5m`). Pole `SourceDescriptor.resolution`
   (sidecar `resolution`) = etykieta.
4. **Skorowidz NMT/NMPT z WFS:** `kartograf/providers/pl/skorowidz_wfs.py`
   (NOWY): `WfsIndex(session_factory, endpoint, layer_prefix, *, timeout, retries)`
   z `feature_types() -> list[str]` (GetCapabilities, wzorzec
   `^(?:gugik:)?<prefix>(\d{4})$`, najnowsze najpierw, nazwa rodziny spoza
   wzorca = `logger.warning`, brak typow = `DownloadError`; jak ADR-020 errata)
   i `features(bbox_2180, types) -> Iterator[ET.Element]` (`GetFeature`,
   `TYPENAMES` = wszystkie podane typy w JEDNYM zapytaniu, `SRSNAME` i `BBOX`
   w URN `EPSG::2180` z osiami N,E, `COUNT=1000`, kolejne strony wylacznie po
   `next` z tej samej uslugi, `numberReturned` != liczba obiektow =
   `DownloadError`, `ExceptionReport`/HTML przy 200 = `DownloadError`;
   kazdy blad z dopiskiem "wynik bylby niepelny" - nigdy pusty wynik).
   `parse_index_feature(elem, layer) -> SkorowidzRecord` mapuje pola WFS na
   klucze `raw` uzywane dzis przez `SkorowidzRecord.to_source`
   (`kartograf/providers/pl/skorowidz.py:72-97`) i `CampaignRef.from_record`:
   `url_do_pobrania`->`url`, `godlo`->`sheet` (kanoniczne `SheetParser`),
   `akt_data`->`aktualnosc`, `akt_rok`->`aktualnoscRok`, `dt_pzgik`,
   `uklad_xy`->`ukladWspolrzednychPoziomych`, `uklad_h`->`ukladWspolrzednychPionowych`,
   `char_przestrz`->`charakterystykaPrzestrzenna` (i `resolution_m` przez
   `_metres`), `czy_ark_wypelniony`->`calyArkuszWypelnionyTrescia`,
   `nr_zglosz`->`numerZgloszeniaPracy`, `zrodlo_danych`->`zrodloDanych`,
   `format`, `blad_sr_wys`->`bladSredniWysokosci`,
   `blad_sr_syt`->`bladSredniPolozenia`, `modul_archiwizacji`->`modulArchiwizacji`;
   `layer` = typ obiektu (`SkorowidzNMT2025`). Obrys arkusza (`msGeometry`)
   w osobnej funkcji `feature_footprint(elem)` (przeniesione `_footprint`,
   `_corner_xy`, `_time_position`, `_localname` z `gugik_laz.py:1003-1061`).
   NMT/NMPT: `WfsSkorowidzLayersMixin(SkorowidzLayersMixin)` nadpisuje
   `_layers()` (jedna grupa = wszystkie typy roczne uslugi wariantu) i
   `_query_layer()` (WFS w kwadracie 20 m w srodku arkusza - ten sam
   `_query_bbox`, `skorowidz.py:470-476`); `_resolve_record`/`_resolve_all`/
   `resolve_campaigns`/cache bez zmian. Ortofotomapa zostaje na
   `SkorowidzLayersMixin` (WMS). LAZ przechodzi na `WfsIndex` (transport,
   lata z GetCapabilities, obrysy) z zachowaniem selekcji kafli.
5. **Twardy filtr rekordu (ADR-028 + format):** `SkorowidzQuery.predicate`
   wariantu = `source_format(record.format, record.url) == variant.format`;
   `resolution_m = float(variant.resolution_m)`; system/strefa jak dzis.
   Rekordy odrzucone filtrem formatu sa widoczne tylko w podpowiedziach braku
   pokrycia ("skorowidz ma dla arkusza tylko archiwum <format> <rozdz.> -
   Kartograf pobiera siatki ASC").
6. **Podpowiedzi braku pokrycia (P10 po WFS):** `_no_coverage` dostaje
   wszystkie rekordy arkusza z tej samej odpowiedzi; dla rekordow siatki innej
   rozdzielczosci z rejestru: "Skorowidz GUGiK ma ten arkusz w NMT 0.5m
   EVRF2007 - uzyj --resolution 0.5m" (bez sieci); inny uklad wysokosci: jedno
   zapytanie WFS do uslugi drugiego ukladu (wszystkie typy, jedna proba,
   usluga z bledem pomijana do konca zycia providera - zasady dzisiejszego
   `_variant_hints`); wariant spoza rejestru (archiwum) - jedna linia
   informacyjna. Tekst podpowiedzi bez godla (CLI scala identyczne linie).
7. **Raport dostepnosci (spec 4, K3/K4):** kombinacje = siatki z rejestru
   i kafle LAZ; klucz kombinacji PL: (rok warstwy, uklad PL-1992|PL-2000,
   etykieta, uklad wysokosci, format); LAZ: (rok, uklad, uklad wysokosci).
   Rekordy spoza rejestru (archiwa, niespojne) nie sa kombinacjami: jedna
   `Notice("info", INDEX_ARCHIVE, ...)` z lista "format rozdzielczosc (lata):
   liczba arkuszy" (np. `ASCII TBD 25.0 m (2018): 2`). Kompletnosc: siatka 1 m
   wyrownana do pelnych metrow na obwiedni obszaru w EPSG:2180, srodki
   pikseli (`all_touched=False`), pasy wierszy do 4 Mpx (jak
   `LandMask.apply`, `kartograf/providers/pl/prg.py:193-231`):
   `target = obszar & lad` (A00 = 1, W02/W03 = 0), `complete` <=> brak
   pikseli `target` poza suma obrysow arkuszy `TAK` kombinacji;
   `uncovered_m2` = piksele `target` poza obrysami jakichkolwiek arkuszy
   kombinacji (`TAK` i `NIE`). Bez progu (decyzja 9.5). Arkusz z rekordem
   `TAK` w kombinacji jest w `sheets_full`; arkusz wylacznie z `NIE` - w
   `sheets_partial`. Obszar (ten sam, ktory pokrywa pobieranie): `sheet` =
   rama godla jako wielokat w EPSG:2180 (narozniki w ukladzie godla,
   krawedzie zageszczone; PL-2000 nie jest prostokatem w EPSG:2180),
   `bbox` = obwiednia `download/area.py::bbox_to_2180(bbox)` (jak
   `_download_pl_bbox`), `geometry` = obiekty warstwy pliku w EPSG:2180
   (jak `_download_pl_geometry`; `layer` jak w `download_data`).
8. **Podpowiedz pobrania (`download_hint`):** krotka komend do wklejenia po
   `kartograf ` albo po `kartograf project add NAZWA ` - BEZ `--output`
   (spec manifestu 4.10, decyzja koordynatora 2026-10-15). NMT/NMPT:
   `elevation download --product nmt --country pl --bbox <jak w zadaniu>
   [--bbox-crs X] --sheet-system 1992 --resolution 1m --vertical-crs EVRF2007
   --year 2025`; PL-2000 dodaje `--scale` - po jednej komendzie na skale
   arkuszy kombinacji; `--full-sheet`, gdy w ktoryms arkuszu najnowszy rekord
   roku jest `NIE`, a pelny rekord tego roku istnieje. `--sheet` z zadania
   zamiast `--bbox ... --country pl --sheet-system ...`; `--geometry PLIK
   [--layer L] --country pl` dla geometrii. LAZ: `elevation download --product
   laz --country pl <obszar> --vertical-crs EVRF2007 --year 2024`.
9. **JSON:** `AvailabilityReport.to_json()` = `json.dumps(asdict(...),
   ensure_ascii=False, indent=2) + "\n"` jak `UpdatePlan.to_json`
   (`kartograf/download/plan.py:71-75`); schemat `kartograf-availability/1`;
   `checked_at` z `kartograf._clock` (zamrazany w testach). CLI `--json` drukuje
   dokladnie ten tekst.
10. **Cache:** nowa tabela `index_area_cache` w `MetadataCache`
    (`kartograf/cache/metadata.py:249-317`) z metodami
    `get_index_area(key: str) -> object | None` i `set_index_area(key: str,
    payload: object)` (payload JSON); klucz sklada wolajacy:
    `"wfs|<endpoint>|<typy>|<bbox w mm>"` -> lista rekordow z obrysami
    (plan B: `"head|<url>"` -> naglowki pliku), TTL jak rekordy
    (`DEFAULT_TTL_SECONDS`, 7 dni); `check_availability(cache=..., force=...)`
    przez `open_cache(cache, force=force, on_notice=...)`
    (`kartograf/cache/defaults.py:18-58`). Obrysy w cache, zeby ponowny raport
    nie odpytywal sieci.
11. **Zakres kraju w planie A:** `country="pl"`; inna wartosc =
    `ValidationError` z lista dostepnych krajow raportu (dzis `pl`). Plan B
    dopisuje `cz` i `auto` (spec 4.3) bez zmiany ksztaltu raportu - pola CZ
    (`sheets_missing`, `size_bytes`, `published` z `Last-Modified`) sa w modelu
    od razu (PL: puste/`None`).
12. **Publiczne API (zmiany lamiace 0.8.0, z "Co zrobic"):**
    `GugikNmptProvider(session=None, *, vertical_crs, resolution, cache=None)`
    (`resolution` wymagane); `GugikProvider(..., resolution=)` przyjmuje
    etykiety NMT z rejestru; usuniete: `kartograf.providers.pl.nmt_vertical_crs`,
    `require_nmt_vertical_crs`, `NMT_5M_VERTICAL_CRS`,
    `GugikProvider.SUPPORTED_RESOLUTIONS`/`SUPPORTED_VERTICAL_CRS_5M`/
    `WMS_INDEX_ENDPOINTS`/`get_supported_resolutions`/
    `get_supported_vertical_crs_for_resolution`, `GugikNmptProvider.SUPPORTED_RESOLUTIONS`,
    `FileStorage.SUPPORTED_RESOLUTIONS`, `GugikLazProvider.WFS_ENDPOINTS`
    (zastepstwo: `kartograf.sources.variants.variants(...)`).
    `GugikProvider.is_wcs_available()` zostaje (z rejestru: kanal WCS).
    Nowe eksporty `kartograf/__init__.py`: `check_availability`,
    `AvailabilityReport`, `AvailabilityCombination`, `AvailabilityArea`.
    Sidecary nowych arkuszy NMT/NMPT: `extra.source.index_url` = adres WFS,
    `extra.source.layer` = typ WFS (`SkorowidzNMT2025`); reszta pol bez zmian.
13. **Archiwa GUGiK pobierane jako pliki zrodlowe (decyzja uzytkownika
    2026-10-15, zastepuje punkt 2 "Weryfikacji" i "archiwa poza zakresem"
    w decyzjach 5, 7 i ADR-041):** formaty skorowidza inne niz siatka ASC sa
    wariantami rejestru i sa pobierane 1:1 (oryginalny plik + sidecar,
    wersje w magazynie, bez konwersji, wycinka i mozaiki). Pelny skan
    skorowidzy 2026-10-15 (wszystkie rekordy, `<katalog-danych>`):
    tokeny `--format`: `ASC` (siatka, bez flagi), `XYZ` (ASCII XYZ GRID),
    `ASCII-NMT`, `TBD`, `TIN`, `TTN`, `GRD`, `DXF`, `DGN`
    (`kartograf/sources/variants.py::FORMATS`: rozszerzenie z pola `format`
    rekordu, akceptowane konce URL). Deskryptory per (produkt, format,
    rozdzielczosc), np. `pl.gugik.nmt_tbd_25m`, segment
    `nmt/pl_{system}_tbd_25m_{vcrs}`, plik `<godlo>.zip|.ttn|.grd|.dxf|.dgn`.
    Rejestr archiwow: NMT XYZ 1m (E,K), 5m (E); ASCII-NMT 0.5m, 1m (E), 5m
    (E,K); TBD 1, 5, 10, 15, 20, 25m (E,K), 30, 40, 50m (K); TIN, TTN (K,
    bez rozdzielczosci); GRD 5m, DXF 25m, DGN 25m (K); NMPT XYZ 0.5m, 1m (K).
    ASCII NMT 10 m (215 rekordow) i 1678 rekordow ASC 1 m maja godla
    8-czlonowe spoza `SheetParser` - nie sa pobierane (Info w raporcie).
    Archiwa leza na arkuszach roznych skal (6-czlonowe 1:25000 i
    7-czlonowe, PL-2000), wiec arkusze zadania archiwum (`--sheet` = rama
    godla, `--bbox`, obwiednie obiektow `--geometry`) wyznacza skorowidz:
    rekordy wariantu z WFS przecinajace obszar (rama zwezona o 1 m -
    sasiad stykajacy sie krawedzia nie liczy sie), w zakresie lat; dalej
    zwykly tor arkuszy (kampanie, wersje, `full_sheet/`). `--scale` i
    `--cutout` z archiwum = `Error:`; `--sheet-system` jak dla siatek.
    B4 (`verify_record_url`) akceptuje nazwy archiwow (`.xyz.zip`,
    `.zip.zip`, `_asc.zip`, `_tin.zip`, prefiks `NMT-`, godlo bez
    separatorow); weryfikacja tresci: ZIP (kompletny katalog), sygnatury
    TTN, Intergraph (GRD/DGN), DXF; bez pomiaru pokrycia. `availability`
    pokazuje archiwa jako kombinacje do pobrania (kolumna FORMAT, podpowiedz
    z `--format`); `Info:` tylko dla rekordow spoza rejestru (niespojne,
    godla 8-czlonowe).

## Review Focus

1. **Jeden indeks:** pobieranie arkusza i raport bior rekordy z tej samej
   uslugi WFS i tego samego parsera (`parse_index_feature`); test
   `test_report_sheets_equal_download_selection` (Task 6).
2. **Twardy filtr formatu:** archiwum tego samego zgloszenia nigdy nie trafia
   do pobrania ani do kombinacji; rekord `.asc`/`.xyz` niespojny odrzucony
   (`test_format_filter_rejects_archives_and_inconsistent_url`, Task 4).
3. **Rejestr jedynym zrodlem:** zadna lista rozdzielczosci/ukladow poza
   rejestrem - sprawdzane zachowaniem, nie tekstem zrodla:
   `test_help_lists_registry_labels`, `test_every_registry_variant_validates`,
   `test_unknown_label_lists_registry` porownuja CLI/API z `variants()`
   (Task 4).
4. **Bez pobrania danych w raporcie:** atrapa sesji odrzuca kazdy URL
   `opendata.geoportal.gov.pl` (`test_availability_never_downloads`, Task 5).
5. **Awaria != brak danych:** blad warstwy, strony `next`, PRG = `DownloadError`;
   pusta, poprawna odpowiedz = raport bez kombinacji (`ok=True`), Task 5.
6. **Wycinek 1 m bez zmian:** `--cutout --resolution 0.5m` = `Error:` przed
   siecia, bajty wycinka 1 m identyczne z dzisiejszymi (testy `tests/test_pl_cutout.py`
   bez zmian merytorycznych), Task 4.

---

## Mapa plikow

| Plik | Zmiana |
|---|---|
| `kartograf/sources/variants.py` (NOWY) | `IndexRef`, `ProductVariant`, `variants`, `resolution_label`, `parse_resolution`, `source_format` |
| `kartograf/sources/descriptor.py` | `SourceDescriptor.variants` |
| `kartograf/sources/registry.py` | nowe deskryptory NMT/NMPT, kanaly WFS z wariantami, `IndexRef` LAZ, `_COUNTRIES["PL"]` bez zmian (liczone z kluczy) |
| `kartograf/providers/pl/skorowidz_wfs.py` (NOWY) | `WfsIndex`, `parse_index_feature`, `feature_footprint`, `WfsSkorowidzLayersMixin` |
| `kartograf/providers/pl/skorowidz.py` | `_matches` bez zmian; `coverage_hints`/`no_coverage_error` przyjmuja rekordy WFS |
| `kartograf/providers/pl/gugik.py`, `gugik_nmpt.py` | wariant z rejestru, WFS, P10 po WFS, bez stalych rozdzielczosci |
| `kartograf/providers/pl/__init__.py` | usuniete `nmt_vertical_crs`, `require_nmt_vertical_crs`, `NMT_5M_VERTICAL_CRS`; `create_nmt_provider` z rejestru |
| `kartograf/providers/pl/gugik_laz.py` | transport WFS z `WfsIndex`, endpoint z rejestru; `LazTile`, selekcja bez zmian |
| `kartograf/download/options.py` | teksty i walidacja `--resolution`/`--vertical-crs` z rejestru; NMPT wymaga `--resolution` |
| `kartograf/download/area.py` | `pl_only_flags` z rejestru |
| `kartograf/download/storage.py` | `FileStorage` wybiera deskryptor przez rejestr |
| `kartograf/download/cutout.py` | klucz deskryptora wycinka z rejestru (wariant z kanalem WCS) |
| `kartograf/download/data.py` | `_create_provider_and_storage` przekazuje `resolution` do NMPT |
| `kartograf/download/availability.py` (NOWY) | `check_availability`, `AvailabilityReport`, `AvailabilityCombination`, `AvailabilityArea` |
| `kartograf/providers/pl/prg.py` | `LandMask.burn(transform, shape) -> np.ndarray` (wspolne z `apply`) |
| `kartograf/cache/metadata.py` | tabela `index_area_cache`, `get_index_area`/`set_index_area` |
| `kartograf/notices.py` | `INDEX_ARCHIVE` |
| `kartograf/cli/groups/elevation.py` | podkomenda `availability`; teksty `--resolution` z rejestru; `_source_choice` z rejestru |
| `kartograf/cli/availability_cmd.py` (NOWY) | `cmd_availability` (tlumaczenie flag, tabela, `--details`, `--json`) |
| `kartograf/__init__.py` | eksporty raportu |
| `tests/fixtures/gugik_wfs/real_2026_10_1x/` (NOWE) | prawdziwe odpowiedzi WFS (Task 1) |
| `tests/test_variants.py` (NOWY), `tests/test_skorowidz_wfs.py` (NOWY), `tests/test_availability.py` (NOWY), `tests/test_cli_availability.py` (NOWY) | nowe testy |
| `tests/test_sources_registry.py`, `tests/test_gugik_provider.py`, `tests/test_gugik_nmpt.py`, `tests/test_storage.py`, `tests/test_download_manager.py`, `tests/test_cli.py`, `tests/test_gugik_laz.py`, `tests/test_real_gugik_responses.py`, `tests/test_parity.py`, `tests/test_cli_translation.py`, `tests/test_input_errors.py` | przepisanie testow usuwanego zachowania (lista w zadaniach) |
| `docs/DECISIONS.md` (CRLF), `docs/CHANGELOG.md`, `docs/ARCHITECTURE.md`, `docs/USAGE.md`, `docs/SCOPE.md`, `docs/PRD.md` | Task 8 |

## Fakty o obecnym kodzie (zweryfikowane 2026-10-15 na `bcdf37d`)

- Grupa CLI: `kartograf/cli/groups/elevation.py:27` `PRODUCTS`, `:30-37`
  `_source_choice`, `:40-247` `register` (podkomendy `download`, `list-sources`;
  `download.set_defaults(_handler=partial(cmd_download, products=PRODUCTS))`
  `:245`); rejestracja grup `kartograf/cli/groups/__init__.py:23-27`
  (`register_groups`), `:30-38` `add_group`, `:41-81` `add_list_sources`
  (tabela z `sources_for(product=)`, kolumna WYBOR z `choice`). Handler
  `kartograf/cli/download_cmd.py:366-392` `_download_arguments`, `:395-409`
  `cmd_download`, `:412-444` `_cmd_download`; wspolne flagi
  `kartograf/cli/_args.py:37` `add_update_flags`, `:65` `add_area_flags`,
  `:89` `add_quiet`, `:105` `parse_bbox_arg`.
- Walidacja: `kartograf/download/options.py:124-224` `pl_option_error`,
  `:299-397` `validate_request`, `:446-470` `resolve_pl_options`,
  `:473-475` `pl_target_scale`; API `kartograf/download/data.py:245-318`
  `download_data`, `:321-369` `check_data`, `:372-392` `_SELECTION`, `:404-433`
  `_execute`, `:589-616` `_create_provider_and_storage` (NMPT bez
  `resolution`, `:596-599`).
- Skorowidz: `kartograf/providers/pl/skorowidz.py:55-139` `SkorowidzRecord`
  (`to_source` 72-97), `:224-251` `_matches` (filtr ADR-028),
  `:258-307` `select_sheet_record`/`select_campaign_records`, `:364-373`
  `SkorowidzQuery` (`predicate`), `:436-817` `SkorowidzLayersMixin`
  (`_resolve_record` 504-559, `_resolve_all` 561-633, `resolve_campaigns`
  635-694, `available_years` 696-713, `_fetch_wms_layers` 753-804, `_layers`
  806-817), `:820` `coverage_hints`, `:849` `no_coverage_error`.
- Providery: `kartograf/providers/pl/gugik.py:51` `GugikProvider`,
  `:152-206` `__init__`, `:237-290` `download`, `:296-314` `_skorowidz_query`,
  `:316-338` `_no_coverage`, `:340-411` `_variant_hints`, `:417-515`
  `download_bbox` (WCS, `:481-486` blokada 5m), `:557-572` `is_wcs_available`;
  `kartograf/providers/pl/gugik_nmpt.py:25-131` `GugikNmptProvider`;
  `kartograf/providers/pl/__init__.py:71-89` `create_nmt_provider`;
  `kartograf/providers/pl/gugik_laz.py:450-1001` `GugikLazProvider`
  (`WFS_ENDPOINTS` 476-481, `_get_wfs_xml` 538-569, `_fetch_available_years`
  575-612, `_query_layer` 806-860 - stronicowanie po `PAGE_SIZE`, nie `next`,
  `_feature_to_tile` 873-937), helpery `:1003-1061`.
- Magazyn: `kartograf/download/storage.py:66-127` `FileStorage.__init__`,
  `:132-137` mapy kluczy, `:159-180` `_subdir`, `:632-669` `storage_for_provider`
  (segment z `provider.descriptor_key`); sidecar `resolution` z
  `descriptor.resolution` (`kartograf/sources/sidecar.py:244`).
- Kampanie i wersje: `kartograf/download/campaigns.py:33` `FILE_FORMATS`,
  `:337-353` `campaign_extension`, `:356-379` `verify_file_format`,
  `:511-527` `verify_record_url`, `:530-566` `verify_sheet_extent`;
  `kartograf/download/manager.py:1213-1274` `_select`, `:1135-1176`
  `_download_version`.
- Wycinek: `kartograf/download/cutout.py:72` `PIXEL_SIZE = 1.0`, `:147-233`
  `_prepare_pl_cutout` (`:220` klucze na sztywno), `:235-238`
  `_cutout_descriptor_key`, `:380` `check_pl_cutout`, `:564` `download_pl_cutout`.
- PRG: `kartograf/providers/pl/prg.py:187-231` `LandMask` (`apply`),
  `:234-263` `fetch_land_mask(area, *, session=None, timeout=30)`.
- Cache: `kartograf/cache/metadata.py:69` `MetadataCache`, `:249-317`
  `_create_tables`, `:319-488` rekordy/kampanie, `:626-677` `get_sheet`/`set_sheet`;
  `kartograf/cache/defaults.py:18` `open_cache`.
- Notices: `kartograf/notices.py:7-27` kody, `:31` `Notice`, `:43` `NoticeSink`.
- Zgodnosc CLI = API: `tests/parity.py` (`run_both`, `assert_same_store`,
  `assert_notices_printed`), `tests/test_parity.py` (scenariusze, `frozen_clock`),
  `tests/test_cli_translation.py:252` `test_cli_imports_no_data_logic`.

---

### Task 1: Fixtury z prawdziwych odpowiedzi WFS (live, swiadomie)

**Files:**
- Create: `tests/fixtures/gugik_wfs/real_2026_10_1x/` (data nagrania w nazwie)
  + `README.md` fixtury (zrodlo, zapytanie, data, co przycieto)

- [ ] **Step 1: Nagranie** (throwaway skrypt poza repo, `requests`, zapisuje
  odpowiedzi 1:1; tylko metadane, zero plikow danych):
  - `GetCapabilities` czterech uslug NMT/NMPT (`...{Terenu,PokryciaTerenu}{EVRF2007,KRON86}/WFS/Skorowidze`);
    przytnij do `FeatureTypeList` (reszta dokumentu nieuzywana) - zaznacz w README;
  - `GetFeature` arkusza (kwadrat 20 m w srodku ramy, wszystkie typy uslugi
    w jednym `TYPENAMES`): NMT EVRF2007 `N-33-58-A-c-1-4` (0.5m 2025),
    `M-34-64-D-d-2-1` (1m/5m `.asc` + XYZ + TBD 25 m + ASCII NMT),
    `N-33-69-A-d-1-3` (rekord `ARC/INFO ASCII GRID` z URL `.xyz`),
    `N-33-77-B-c-3-3` (0.6m i 0.5m i 1m), `7.159.25.12.2` (0.15m),
    `6.125.25` (5m i 10m PL-2000); NMT KRON86 `6.130.26.07.1.2` (0.5m),
    `M-34-64-D-d-2-1` (1m 2012/2017 + XYZ); NMPT EVRF2007 `N-33-58-A-d-1-2`
    (0.5m), `N-33-77-B-c-3-3` (0.6m, 0.5m); arkusz na morzu
    `N-33-46-C-c-3-2` (2026-10-15: `numberReturned=0`, `numberMatched=unknown`)
    - odpowiedz pusta, poprawna;
  - `GetFeature` obszaru (wszystkie typy, `COUNT=1000`): Krakow
    (E 565000-569000, N 242000-246000) dla czterech uslug NMT/NMPT i LAZ
    EVRF2007; Pomorze (E 339000-343000, N 744800-747000) dla czterech uslug
    NMT/NMPT i LAZ EVRF2007; jedno zapytanie z `COUNT=5` (Krakow NMT EVRF2007)
    nagrane z dwiema kolejnymi stronami `next` (test stronicowania);
  - PRG `fetch_land_mask` dla obu obszarow - jesli `tests/fixtures/gugik_prg/`
    nie ma A00/W02/W03 dla tych prostokatow, nagraj je tym samym zapytaniem co
    `kartograf/providers/pl/prg.py:234-263`;
  - jedna odpowiedz bledu: `ExceptionReport` (np. nieistniejacy `TYPENAMES`).
- [ ] **Step 2: Kontrola** - dla kazdej odpowiedzi obszarowej porownaj liczby
  z raportem `docs/research/2026-10-15-plan-a-b/raport.md` i z punktem 9
  sekcji "Weryfikacja" (kombinacje Krakow/Pomorze). Roznica (GUGiK opublikowal
  nowy lot) = zapisz nowe wartosci w README fixtury i uzyj ich w testach Task 5;
  nie poprawiaj testow "pod" stare liczby.
- [ ] **Step 3: Commit** - `test(fixtures): prawdziwe odpowiedzi WFS skorowidzy NMT/NMPT/LAZ i PRG dla planu A`

### Task 2: Rejestr wariantow (`variants.py`) i ADR-041

**Files:**
- Create: `kartograf/sources/variants.py`, `tests/test_variants.py`
- Modify: `kartograf/sources/descriptor.py` (pole `variants`),
  `kartograf/sources/registry.py` (deskryptory z decyzji 3),
  `tests/test_sources_registry.py`, `docs/DECISIONS.md`

- [ ] **Step 1: Test RED** (`tests/test_variants.py`):
  `test_label_round_trip` (`Decimal("0.15")`->`0.15m`, `0.5`->`0.5m`,
  `10`->`10m`, `parse_resolution("10m") == Decimal("10")`, `parse_resolution`
  dla `0,5m`, `50cm`, `0.50m`, `5` -> `None`);
  `test_pl_registry_matches_inventory` (zbior `(product, label, vertical_crs)`
  z `variants(country="PL")` dokladnie rowny tabeli decyzji 3, z LAZ jako
  `("laz", None, "EVRF2007")` i `("laz", None, "KRON86")` - to kontrakt
  produktu z inwentaryzacji, nie kopia stalej);
  `test_variant_source_is_descriptor` (kazdy wariant: `get_source(v.source)`
  istnieje, `descriptor.product == v.product`, `descriptor.resolution ==
  v.label`, `resolve_vertical_crs(v.vertical_crs, kanal.vertical_crs_options)`
  w opcjach kanalu arkuszy);
  `test_source_format_requires_asc_url` (`("ARC/INFO ASCII GRID", ".../x.asc")`
  -> `"ASC"`; ten sam format z URL `.xyz` -> `None`; `ASCII XYZ GRID`,
  `ASCII TBD`, `ESRI TIN` -> `None`);
  `test_wcs_only_for_1m` (kanal `WCS` maja dokladnie `pl.gugik.nmt_1m`
  i `pl.gugik.nmpt`).
- [ ] **Step 2: Implementacja** - `variants.py` wg decyzji 1-2; rejestr wg
  decyzji 3 (pomocnicza funkcja w `registry.py` budujaca warianty deskryptora
  z listy ukladow wysokosci i `IndexRef`, zeby `source` nie byl przepisywany
  recznie); kanal arkuszy NMT/NMPT: `TransportKind.WFS`, `update_signal="index"`;
  `vertical_crs_options` deskryptora tylko dla ukladow z wariantem (0.15m:
  `("EPSG:9651",)`). Nazwy (`SourceDescriptor.name`) np. "Numeryczny Model
  Terenu 0,5 m (siatka ASC)". Bez IO przy imporcie.
- [ ] **Step 3: Test zgodnosci rejestru** (`tests/test_sources_registry.py`):
  przepisz `test_nmt_1m_entry_values` (208), `test_nmt_1m` (291), `test_nmt_5m`
  (337), `test_nmpt` (351), `test_nmpt_wcs_channel_matches_provider` (323) na
  intencje "segment i kanaly kazdego wariantu sa spojne z providerem
  zbudowanym z tego wariantu" (parametryzacja po `variants(country="PL")`);
  usun asercje pinujace `WMS_SHEET_INDEX` dla NMT/NMPT.
- [ ] **Step 4: ADR-041 w `docs/DECISIONS.md`** (CRLF; wiersz w indeksie +
  sekcja): kontekst (luka 0,5 m, listy rozdzielczosci w 7 miejscach, raport
  dostepnosci), decyzja (rejestr `ProductVariant` w deskryptorach; etykiety K2;
  siatki ASC we wszystkich rozdzielczosciach z inwentaryzacji; archiwa poza
  zakresem; skorowidz NMT/NMPT z WFS - pobieranie i raport na jednym indeksie;
  twardy filtr formatu; wycinek WCS 1 m; raport = komplet pelnych arkuszy wg
  skorowidza na ladzie PRG; podpowiedz bez `--output`), konsekwencje (zmiany
  API z decyzji 12), odrzucone (lista stalych per modul; `50cm`; pobieranie
  archiwow "jak leci" z rozszerzeniem z rekordu; WMS dla pobierania i WFS dla
  raportu; prog pokrycia). Status "Przyjeta". Odnosniki: spec, raport pomiarow.
- [ ] **Step 5: Brama i commit** - `feat(sources): rejestr wariantow produktu (ADR-041) i deskryptory siatek NMT/NMPT`

### Task 3: Klient skorowidza WFS i LAZ na wspolnym transporcie

**Files:**
- Create: `kartograf/providers/pl/skorowidz_wfs.py`, `tests/test_skorowidz_wfs.py`
- Modify: `kartograf/providers/pl/gugik_laz.py`, `tests/test_gugik_laz.py`
  (tylko testy przypinajace prywatne metody transportu)

- [ ] **Step 1: Test RED** (`tests/test_skorowidz_wfs.py`, fixtury Task 1,
  atrapa sesji zwracajaca pliki po parametrach):
  `test_feature_types_newest_first` (GetCapabilities NMT KRON86 -> 17 typow
  2019..2000); `test_one_request_for_all_types` (jedno `GetFeature` z
  `TYPENAMES` wszystkich typow, `BBOX` w kolejnosci N,E + URN);
  `test_paging_follows_next` (nagrane strony `COUNT=5`: wszystkie obiekty,
  zadnej powtorki, drugie zapytanie = URL z `next`);
  `test_number_returned_mismatch_is_error`; `test_exception_report_is_error`
  (komunikat z "wynik bylby niepelny"); `test_empty_answer_is_empty`
  (odpowiedz morza: pusta lista, bez bledu);
  `test_parse_maps_fields_to_record` (rekord `N-33-58-A-c-1-4`: `resolution_m
  == 0.5`, `system == "1992"`, `full_sheet`, `raw["format"]`,
  `to_source()["survey_work_id"] == nr_zglosz`, `layer == "SkorowidzNMT2025"`);
  `test_footprint_in_east_north` (obrys arkusza w EPSG:2180 E,N pokrywa rame
  `SheetParser(godlo).get_bbox(crs="EPSG:2180")` z dokladnoscia 1 m).
- [ ] **Step 2: Implementacja `WfsIndex`, `parse_index_feature`,
  `feature_footprint`** wg decyzji 4 (retry: `get_with_retry`, sesja na watek
  `SessionPerThread` jak w providerach).
- [ ] **Step 3: LAZ na `WfsIndex`** - `GugikLazProvider` bierze endpoint
  i prefiks z rejestru (`variants(product="laz", country="PL",
  vertical_crs=...)`), lata z `WfsIndex.feature_types()`, obiekty z
  `WfsIndex.features(bbox, [typ_roku])` (zapytanie per rocznik zostaje - selekcja
  per rok), `_feature_to_tile` na helperach z `skorowidz_wfs.py`; kontrola
  "zaden kafel nie przecina bboxa = niezgodnosc osi" zostaje. Usun
  `WFS_ENDPOINTS`, `_get_wfs_xml`, wlasne stronicowanie po `PAGE_SIZE`.
  Wszystkie testy `tests/test_gugik_laz.py`, `tests/test_laz_download.py`,
  `tests/test_laz_campaigns.py`, `tests/test_laz_coverage.py` zielone bez
  zmiany asercji zachowania (atrapy sesji moga wymagac odpowiedzi z `next`
  zamiast pelnej strony - to zmiana atrapy, nie asercji).
- [ ] **Step 4: Brama i commit** - `refactor(pl): wspolny klient skorowidza WFS (NMT/NMPT/LAZ)`

### Task 4: Arkusze NMT/NMPT z rejestru i WFS - walidacja, provider, magazyn, wycinek

**Files:**
- Modify: `kartograf/providers/pl/{__init__,gugik,gugik_nmpt,skorowidz}.py`,
  `kartograf/providers/pl/skorowidz_wfs.py` (`WfsSkorowidzLayersMixin`),
  `kartograf/download/{options,area,storage,cutout,data,manager}.py`,
  `kartograf/cli/groups/elevation.py`
- Test: `tests/test_gugik_provider.py`, `tests/test_gugik_nmpt.py`,
  `tests/test_real_gugik_responses.py`, `tests/test_storage.py`,
  `tests/test_download_manager.py`, `tests/test_input_errors.py`,
  `tests/test_cli.py`, `tests/test_pl_cutout.py`, `tests/test_cli_translation.py`,
  `tests/test_parity.py`

- [ ] **Step 1: Test RED - wybor rekordu** (fixtury Task 1; atrapa sesji WFS):
  `test_select_0_5m_2025` (`GugikProvider(vertical_crs="EVRF2007",
  resolution="0.5m")`, `N-33-58-A-c-1-4` -> URL `84020_1844081_...asc`);
  `test_nmpt_0_5m` (`GugikNmptProvider(..., resolution="0.5m")`,
  `N-33-58-A-d-1-2` -> `84018_...`); `test_kron86_0_5m_pl2000`
  (`6.130.26.07.1.2` -> `70042_814868_...asc`); `test_0_15m_and_10m_pl2000`;
  `test_format_filter_rejects_archives_and_inconsistent_url`
  (`M-34-64-D-d-2-1` 5m: wybrany `.asc` 2019, nigdy `ASCII NMT`/XYZ;
  `N-33-69-A-d-1-3` 1m: rekord z URL `.xyz` odrzucony);
  `test_campaigns_and_year_range_from_wfs` (KRON86 `M-34-64-D-d-2-1`
  1m: `--all-campaigns` = 2017 i 2012 `.asc`, `max_year=2016` -> 2012);
  `test_no_coverage_hints_other_resolution_without_network` (NMT 1m EVRF2007
  dla arkusza tylko 0.5m: komunikat z "uzyj --resolution 0.5m"; do uslugi
  EVRF2007 dokladnie jedno zapytanie); `test_no_coverage_hint_other_vertical_crs_one_query` (P10: jedna
  proba do uslugi KRON86; awaria tej uslugi = brak podpowiedzi, brak bledu,
  kolejny arkusz jej nie odpytuje); `test_archive_only_sheet_hint`
  (arkusz z samym XYZ: podpowiedz o archiwum, bez godla w tekscie).
- [ ] **Step 2: Test RED - walidacja, CLI = API, `--help`**:
  `test_every_registry_variant_validates` (dla kazdego wariantu PL:
  `validate_data_request`/`download_data` z atrapa providera przechodzi bez
  `ValidationError`); `test_unknown_label_lists_registry` (`--resolution 2m`
  dla NMT PL: `Error:` z lista etykiet z `variants()` - porownanie z rejestrem,
  nie z napisem w tescie); `test_kron86_5m_message_from_registry` (NMT 5m
  KRON86: `Error:` z "dostepne w KRON86: 0.5m, 1m"); `test_nmpt_requires_resolution`
  (`--product nmpt` bez `--resolution`: `Error:` z 0.5m, 0.6m, 1m; API
  `ValidationError` z tym samym tekstem); `test_cutout_only_1m`
  (`--cutout --resolution 0.5m` dla NMT i NMPT: `Error:` przed siecia z
  podpowiedzia "arkusze bez --cutout"; brak `--resolution` z `--cutout` = 1m);
  `test_help_lists_registry_labels` (`elevation download --help` zawiera
  kazda etykiete PL z rejestru); `test_list_sources_has_every_variant_source`
  (`elevation list-sources`: wiersz dla kazdego klucza z rejestru, WYBOR np.
  `--product nmpt --resolution 0.5m`); `test_pl_only_flags_from_registry`
  (`--country auto` z `--resolution 0.5m` dla NMT -> zawezenie do PL, dla
  NMPT tez - do czasu planu B).
- [ ] **Step 3: Test RED - magazyn i sidecar**: `test_segment_from_variant`
  (0.5m -> `nmt/pl_1992_0.5m_evrf2007/N-33/58/A/c/1/4/N-33-58-A-c-1-4.asc`,
  wersja `<akt_data>_84020_<sha8>`, sidecar `dataset == "pl.gugik.nmt_0_5m"`,
  `resolution == "0.5m"`, `extra.source.layer == "SkorowidzNMT2025"`);
  `test_filestorage_public_constructor_accepts_registry_labels`
  (`FileStorage(out, resolution="0.5m", vertical_crs="EVRF2007")` i
  `product="nmpt", resolution="0.6m"`); `test_cutout_descriptor_from_registry`.
- [ ] **Step 4: Implementacja**:
  - `variants.py`: funkcja `find_variant(*, product, country, resolution,
    vertical_crs, system=None) -> ProductVariant` rzucajaca `ValidationError` z tekstami
    nazywajacymi flagi CLI (teksty skladane w `options.py` - jedno miejsce
    komunikatow; `variants.py` zwraca dane);
  - `options.py`: `RESOLUTION_PL` -> `resolution_text(country, product)`
    i `vertical_crs_text(country)` z rejestru (np. "nmt: 0.15m*, 0.5m, 0.6m*,
    1m, 5m*, 10m*; nmpt: 0.5m, 0.6m*, 1m (* tylko EVRF2007)"); `pl_option_error`
    sprawdza istnienie wariantu (produkt, etykieta, uklad); NMPT bez
    `--resolution` = blad; wycinek: wariant musi miec kanal WCS (1m) -
    `resolve_pl_options` uzupelnia 1m tylko dla `--cutout`;
  - providery: `GugikProvider.__init__` -> `self.variant = find_variant(...)`,
    `descriptor_key = variant.source`; `GugikNmptProvider` z wymaganym
    `resolution`; `WfsSkorowidzLayersMixin` zamiast WMS dla NMT/NMPT;
    `_skorowidz_query` z `variant.index_ref.endpoint`, `float(variant.resolution_m)`
    i predykatem formatu; P10 wg decyzji 6; `download_bbox` - wariant bez WCS =
    `ValidationError`; usun stale z decyzji 12;
  - `providers/pl/__init__.py`: usun `nmt_vertical_crs`,
    `require_nmt_vertical_crs`, `NMT_5M_VERTICAL_CRS` (z `__all__`),
    `create_nmt_provider` waliduje przez `find_variant`;
  - `storage.py`: `FileStorage(resolution=, product=)` szuka deskryptora przez
    `variants(product=product or "nmt", country="PL", resolution=...)`
    (produkt bez wariantow - orto/laz - przez `sources_for(country="PL",
    product=...)`, dokladnie jeden deskryptor); usun `SUPPORTED_RESOLUTIONS`,
    `_RESOLUTION_SOURCES`, `_PRODUCT_SOURCES`;
  - `cutout.py:220` i `_cutout_descriptor_key` -> wariant 1m produktu z kanalem
    WCS; `PIXEL_SIZE`, siatka, WCS bez zmian;
  - `area.py::pl_only_flags` -> produkt/etykieta/uklad bez wariantu CZ
    w rejestrze (w planie A CZ ma tylko `nmt` 2m/5m z `cz.cuzk.*`: `nmpt`
    i etykiety inne niz 2m/5m pozostaja PL-only, wynik zachowania jak dzis
    dla `1m`/`nmpt`/`KRON86`);
  - `data.py:596-599`: `GugikNmptProvider(vertical_crs=..., resolution=...)`;
  - `cli/groups/elevation.py`: tekst `--resolution` z `options.py`
    (`resolution_text`), `_source_choice` z `variants()` (`--product nmt
    --resolution 0.5m`; NMPT tez z `--resolution`).
- [ ] **Step 5: Przepisz/usun testy usuwanego zachowania** (intencja, nie
  kopia): `tests/test_gugik_provider.py` - `test_supported_resolutions` (177),
  `test_supported_vertical_crs_for_1m`/`_5m` (186, 194), `test_resolution_5m_requires_evrf2007`
  (165, przepisz na blad z rejestru), `test_get_opendata_url_uses_correct_endpoint_for_1m`/`_5m`
  (1009, 1022 - endpoint WFS wariantu), testy P10 na WMS (959-1005) na WFS;
  `tests/test_gugik_nmpt.py` - `test_resolution_is_1m` (47), `test_wms_endpoints_are_nmpt`
  (118); `tests/test_download_manager.py` - `test_5m_kron86_raises_with_remedy`
  (925, tekst z rejestru), `TestCreateNmtProviderFactory`;
  `tests/test_cli.py` - `TestNmt5mKron86Rejected` (1939-2090, przepisz na
  komunikat z rejestru), testy `RESOLUTION_PL`; `tests/test_storage.py` -
  `test_resolution_subdir_nmt_1m`/`_5m` (452, 459), `test_product_skips_resolution_validation`
  (435); `tests/test_real_gugik_responses.py` - testy fixtur WMS NMT/NMPT
  (`real_2026_10_06`, `real_2026_10_10`) zastap fixturami WFS (Task 1);
  fixtury WMS orto zostaja. Usun fixtury WMS NMT/NMPT, ktorych nic juz nie
  czyta.
- [ ] **Step 6: Selektywne uruchomienie** testow tego zadania + pelna brama;
  smoke: `python -m kartograf.cli.commands elevation download --help`
  i `... elevation list-sources` (wartosci z rejestru).
- [ ] **Step 7: Commit** - `feat(elevation)!: NMT/NMPT we wszystkich rozdzielczosciach siatek GUGiK ze skorowidza WFS`

### Task 5: Raport dostepnosci - biblioteka

**Files:**
- Create: `kartograf/download/availability.py`, `tests/test_availability.py`
- Modify: `kartograf/providers/pl/prg.py` (`LandMask.burn`), `kartograf/cache/metadata.py`
  (`index_area_cache`), `kartograf/notices.py` (`INDEX_ARCHIVE`),
  `kartograf/__init__.py` (eksporty), `tests/test_metadata_cache.py`
  (tabela `index_area_cache`: zapis, odczyt, TTL, `refresh`)

Kontrakt (decyzje 7-11):

```python
def check_availability(
    *,
    product: str,                       # "nmt" | "nmpt" | "laz"
    country: str,                       # plan A: "pl"
    sheet: str | None = None,
    bbox: BBox | None = None,
    geometry: str | Path | None = None,
    layer: str | None = None,           # warstwa pliku geometrii (jak download_data)
    year: int | None = None,
    min_year: int | None = None,
    max_year: int | None = None,
    cache: MetadataCache | bool = True,
    force: bool = False,                # pomija odczyt cache metadanych (jak --force)
    on_notice: Callable[[Notice], None] | None = None,
) -> AvailabilityReport

@dataclass(frozen=True)
class AvailabilityArea:
    country: str                        # "PL"
    crs: str                            # "EPSG:2180"
    bounds: tuple[float, float, float, float]
    area_m2: float                      # obszar zadania w tym kraju
    land_m2: float                      # PL: lad PRG (A00 - W02 - W03); plan B: CZ

@dataclass(frozen=True)
class AvailabilityCombination:
    country: str                        # "PL"
    product: str
    source: str                         # klucz deskryptora (sidecar `dataset`)
    year: int | None                    # rok warstwy skorowidza (PL); CZ: None
    acquisition_dates: tuple[str, str] | None   # min/max akt_data
    published: tuple[str, str] | None   # PL: min/max dt_pzgik; CZ: Last-Modified
    campaigns: tuple[str, ...]          # nr_zglosz (posortowane)
    horizontal: str                     # "PL-1992" | "PL-2000"
    resolution: str | None              # etykieta K2; LAZ: None
    vertical_crs: str                   # "EVRF2007" | "KRON86"
    format: str                         # "ASC" | "LAZ"
    densities: tuple[int, ...]          # LAZ: gestosci pkt/m2; inaczej ()
    complete: bool
    sheets_full: tuple[str, ...]        # godla z rekordem TAK
    sheets_partial: tuple[str, ...]     # godla wylacznie NIE
    sheets_missing: tuple[str, ...]     # CZ (plan B): arkusze indeksu bez pliku; PL: ()
    uncovered: bool
    uncovered_m2: float
    size_bytes: int | None              # CZ (plan B); PL: None
    download_hint: tuple[str, ...]      # komendy po `kartograf ` bez --output

@dataclass(frozen=True)
class AvailabilityReport:
    request: dict                       # product, country, wybor obszaru (jak sidecar request), lata
    checked_at: str
    areas: tuple[AvailabilityArea, ...]
    combinations: tuple[AvailabilityCombination, ...]   # rok malejaco, potem uklad, rozdz.
    notices: tuple[Notice, ...]
    ok: bool                            # True; plan B: False, gdy czesc auto nie zostala sprawdzona
    schema: str = "kartograf-availability/1"

    def to_json(self) -> str: ...
```

- [ ] **Step 1: Test RED - kryteria specu 4.4 na fixturach** (atrapa sesji
  z odpowiedziami Task 1, zamrozony zegar):
  `test_krakow_complete_combinations` (NMT EVRF2007 PL-1992 1m 2025, 2024,
  2023, 2022, 2019 kompletne po 6 TAK; PL-2000 1m 2023 i 2021 kompletne po
  15 TAK; 5m 2019 kompletna; brak kombinacji 2018; `Notice` `INDEX_ARCHIVE`
  wymienia XYZ 1 m i 5 m, TBD 25 m z roku 2018 i ASCII NMT 5 m z 2019);
  `test_pomorze_partial_and_uncovered` (NMT 2025 0.5m: `complete=False`,
  `sheets_partial` = 4 godla z punktu 9, `uncovered=False`; 2022 1m:
  `sheets_full` 3, `uncovered_m2` w [8 700, 8 900], `complete=False`; lad
  `land_m2` w [863 000, 864 500]; morze nie zmienia wyniku - ten sam test dla
  obszaru obcietego do ladu daje to samo `uncovered_m2`);
  `test_nmpt_and_kron86_from_their_services` (Krakow NMPT KRON86 0.5m 2017
  i 2012 kompletne); `test_laz_full_tiles_only` (LAZ: kombinacje rok/uklad,
  `densities`, `complete` liczony tylko z kafli TAK; kafle NIE w
  `sheets_partial`).
- [ ] **Step 2: Test RED - kontrakt**: `test_availability_never_downloads`
  (sesja rzuca na `opendata.geoportal.gov.pl`); `test_failure_is_error_not_empty`
  (ExceptionReport warstwy, przerwana strona `next`, blad PRG -> `DownloadError`;
  pusta poprawna odpowiedz -> `combinations == ()`, `ok=True`);
  `test_year_bounds_select_layers` (`year=2025` = jedno zapytanie z jednym
  typem; `min_year` > ostatni rok uslugi = `ValidationError` z lista lat jak
  `download_data`); `test_input_errors_same_as_download_data` (dwa wybory
  obszaru, brak wyboru, zly bbox, nieznany produkt, `country="cz"` w planie A:
  ten sam typ i tekst co `validate_data_request`/`download_data`, gdzie dotyczy);
  `test_cache_and_force` (drugi raport bez sieci; `force=True` odpytuje i
  nadpisuje cache); `test_hint_without_output_and_full_sheet`
  (podpowiedz zaczyna sie od `elevation download`, nie zawiera `--output`/`-o`;
  `--full-sheet`, gdy najnowszy rekord roku jest NIE, a pelny istnieje;
  PL-2000 z `--scale` per skala); `test_hint_runs_validation`
  (kazda podpowiedz przeparsowana `create_parser()` i przepuszczona przez
  `validate_data_request` z `output_dir` testu - poprawna);
  `test_json_round_trip_and_order` (`to_json` deterministyczny, kombinacje
  rok malejaco).
- [ ] **Step 3: Implementacja** wg kontraktu i decyzji 7-10: obszar ->
  wielokaty EPSG:2180 wg decyzji 7 (`sheet`: rama z naroznikow w ukladzie
  godla, krawedzie zageszczone co 10 m; `bbox`: `bbox_to_2180`; `geometry`:
  obiekty warstwy z `kartograf.core.geometry`), maska ladu przez
  `fetch_land_mask(obwiednia)`
  + `LandMask.burn(...)` (wydzielone z `apply`, `apply` uzywa `burn`),
  skorowidze: dla `nmt`/`nmpt` obie uslugi (EVRF2007, KRON86) z
  `IndexRef` rejestru, typy z zakresu lat, `WfsIndex.features(obwiednia, typy)`;
  dla `laz` - uslugi LAZ z rejestru. Grupowanie rekordow w kombinacje,
  rasteryzacja w pasach, podpowiedzi, `Notice` archiwow. Cache surowych
  rekordow z obrysami w `index_area_cache`. `ValidationError` przed siecia;
  awarie `DownloadError`.
- [ ] **Step 4: Brama i commit** - `feat(api): check_availability - komplet pelnych arkuszy NMT/NMPT/LAZ PL wg skorowidza`

### Task 6: `kartograf elevation availability` (CLI) i zgodnosc CLI = API

**Files:**
- Create: `kartograf/cli/availability_cmd.py`, `tests/test_cli_availability.py`
- Modify: `kartograf/cli/groups/elevation.py`, `tests/test_parity.py`,
  `tests/test_cli_translation.py`

- [ ] **Step 1: Test RED**: `test_table_sorted_and_footer` (Krakow: lata
  malejaco, kolumny ROK, NALOT, UKLAD, ROZDZ., WYSOKOSCI, FORMAT, ARKUSZE
  (TAK/NIE), KOMPLET; komorka "nie: 4 niepelne" / "nie: brak arkuszy dla
  0,88 ha"; stopka z najnowsza kompletna kombinacja: "Pobranie (dodaj --output
  KATALOG): kartograf <hint>" i "W projekcie: kartograf project add NAZWA
  <hint>"); `test_details_lists_partial_and_uncovered`; `test_json_equals_api`
  (stdout `--json` == `check_availability(...).to_json()` bajtowo, zamrozony
  zegar, ta sama atrapa sesji); `test_exit_codes` (brak danych - kod 0 z
  komunikatem "brak arkuszy siatek dla obszaru"; awaria zrodla - `Error:`,
  kod 1; zla flaga - `Error:`/argparse jak `download`);
  `test_notices_on_stderr` (`Info:` archiwow); `test_cli_imports_no_data_logic`
  rozszerzony o `availability_cmd` (`tests/test_cli_translation.py:252`).
- [ ] **Step 2: Zgodnosc CLI = API** (`tests/test_parity.py`):
  scenariusz `test_availability_json` (Pomorze NMT, `--json`) i
  `test_pl_sheet_0_5m` (arkusz NMT 0.5m: magazyn, sidecar, statusy, `Notice`
  przez CLI i API identyczne - wzorem `test_pl_sheet` 60-90); dopisz oba do
  tabeli scenariuszy w docstringu modulu. Oraz
  `test_report_sheets_equal_download_selection` (`tests/test_availability.py`):
  atrapa WFS odpowiada na zapytania arkuszy wycinkiem nagranej odpowiedzi
  obszaru Krakowa (filtr obiektow po `BBOX` zapytania); `check_data` z
  argumentami z `download_hint` najnowszej kompletnej kombinacji -> godla
  pozycji planu = `sheets_full` tej kombinacji, etykiety rekordow z jej roku.
- [ ] **Step 3: Implementacja**: `elevation availability` w `register`
  (`kartograf/cli/groups/elevation.py`): `--product` (te same `PRODUCTS`),
  `--country` (`pl`; plan B dopisuje), `add_area_flags(...)` (`--sheet`,
  `--bbox`, `--bbox-crs`, `--geometry`, `--layer`), `--year/--min-year/--max-year`,
  `--details`, `--json`, `--force` (opis: "pomin cache metadanych"); bez
  `--output`, trybow, `--workers` i `-q` (raport jest wynikiem komendy;
  `Info:`/`Warning:` na stderr jak w `download`). `set_defaults(_handler=
  cmd_availability)` - bez `_task` (to nie komenda danych, ADR-040/spec
  manifestu 4.10). `cmd_availability` tylko tlumaczy flagi i formatuje
  `AvailabilityReport` (liczby w ha/km2 z przecinkiem dziesietnym jak
  `download/area.py::_deg`).
- [ ] **Step 4: Smoke** (offline, z korzenia worktree):
  `python -m kartograf.cli.commands elevation availability --help` i
  `... elevation --help` (lista komend: download, list-sources, availability).
- [ ] **Step 5: Brama i commit** - `feat(cli): kartograf elevation availability (raport dostepnosci PL)`

### Task 7: Integracja z manifestem projektu (krok warunkowy)

Sprawdz, czy `kartograf/project/commands.py` istnieje na `develop` w chwili
wykonania (`git ls-tree develop kartograf/project/commands.py`).

- [ ] **Jesli istnieje (manifest scalony przed planem A):**
  - `elevation availability` nie ustawia `_task` - dopisz przypadek do
    testu manifestu `test_add_rejects_non_data_commands`
    (`tests/test_project_cli.py`): `kartograf project add t elevation
    availability --product nmt --country pl --bbox ...` = `Error:` z lista
    dozwolonych komend, manifest bez zmian;
  - plan A nie dodaje flag danych do `elevation download` - test
    `test_task_options_equal_parser_data_flags` ma zostac zielony bez zmian
    pozycji `COMMANDS["elevation download"]`; jesli nie jest - roznica to blad
    w Task 4 (nowa flaga danych), nie w manifescie;
  - test zadania projektu z wariantem 0.5m: `project add t elevation download
    --product nmt --sheet N-33-58-A-c-1-4 --resolution 0.5m --vertical-crs
    EVRF2007` + `project download t` na atrapie providera -> przypiecie pliku
    `nmt/pl_1992_0.5m_evrf2007/...` (wzorem testow `tests/test_project_download.py`);
  - podpowiedz raportu wklejona po `kartograf project add NAZWA` - test
    `test_hint_accepted_by_project_add` (parser `project add` + walidacja,
    bez sieci).
- [ ] **Jesli nie istnieje:** nic w kodzie; w opisie commita/PR zaznacz dla
  koordynatora, ze plan manifestu (Task 8 "Integracja z planami A-E") obejmie
  `availability` (bez `_task`) i nowe etykiety bez zmian w projekcie.
- [ ] **Commit (jesli byly zmiany)** - `test(project): availability poza komendami danych, zadanie NMT 0.5m`

### Task 8: Dokumentacja i ADR

**Files:** `docs/DECISIONS.md` (CRLF), `docs/CHANGELOG.md`, `docs/USAGE.md`,
`docs/ARCHITECTURE.md`, `docs/SCOPE.md`, `docs/PRD.md`; `docs/PROGRESS.md`
wg polecenia koordynatora (domyslnie wpis sesji na koniec).

- [ ] **ADR-041:** uzupelnij o wyniki E2E (Task 9) i ostateczne nazwy symboli.
- [ ] **CHANGELOG `[0.8.0] - Unreleased`:** Dodane - siatki NMT/NMPT 0.15m,
  0.5m, 0.6m, 10m (lista z rejestru), `elevation availability`/`check_availability`,
  `kartograf.sources.variants`; Zmienione (BREAKING) z "Co zrobic":
  `--product nmpt` wymaga `--resolution` ("dopisz --resolution 1m"),
  `GugikNmptProvider(..., resolution=)`, usuniete symbole z decyzji 12
  ("uzyj kartograf.sources.variants.variants()"), skorowidz NMT/NMPT z WFS
  (sidecar `extra.source.index_url`/`layer`; "nic - pliki te same"),
  `GugikLazProvider.WFS_ENDPOINTS` usuniete; Naprawione - brak.
- [ ] **USAGE:** 1.1 (przyklady 0.5m NMT i NMPT, NMPT z `--resolution`),
  1.3 (wycinek tylko 1m - komunikat), NOWA 1.7 "Raport dostepnosci
  (`elevation availability`)" (Krakow/Pomorze z prawdziwym wydrukiem z E2E,
  `--details`, `--json`, podpowiedz bez `--output` i z `project add`), 2
  (biblioteka: `check_availability`), 7 (znane problemy: archiwa GUGiK poza
  pobieraniem; raport nie mierzy tresci arkuszy NIE).
- [ ] **ARCHITECTURE:** 2 (moduly `sources/variants.py`,
  `providers/pl/skorowidz_wfs.py`, `download/availability.py`,
  `cli/availability_cmd.py`), 3.1 (`SourceDescriptor.variants`, rejestr),
  3.3 (segmenty `pl_<uklad>_<etykieta>_<vcrs>` z nowymi etykietami), 4.1
  (rekordy NMT/NMPT z WFS, filtr formatu, P10 po WFS), NOWA 4.9 "Raport
  dostepnosci" (algorytm, cache, podpowiedz), 5 (nowa rozdzielczosc = wpis
  rejestru).
- [ ] **SCOPE:** 2.1 i 2.3 (rozdzielczosci z rejestru), 2.9 (komenda
  `availability`), 2.10 (API raportu), 3.3 (wiersz podprojektu 3 - plan A
  wykonany).
- [ ] **PRD:** 3.1, 3.2 (rozdzielczosci, raport), 5 (Public API).
- [ ] **Commit** - `docs: ADR-041, CHANGELOG i dokumentacja planu A (warianty, WFS, availability)`

### Task 9: Brama i E2E na zywo (swiadomie)

Dane wylacznie do `<katalog-danych>/kartograf/e2e/2026-10-xx-plan-a/`
(jawne `--output`), cache metadanych w korzeniu worktree. Raport:
`docs/research/2026-10-xx-plan-a-e2e/raport.md` (bez sciezki katalogu danych).

- [ ] **Brama:** pelne `pytest -m "not live"`, `ruff check .`,
  `ruff format --check .`, `mypy kartograf/ tests/` - liczby do raportu.
- [ ] **E2E-1 NMT 0.5m:** `elevation download --product nmt --sheet
  N-33-58-A-c-1-4 --resolution 0.5m --vertical-crs EVRF2007 -o <dir>` ->
  `nmt/pl_1992_0.5m_evrf2007/N-33/58/A/c/1/4/N-33-58-A-c-1-4.asc`, 4202x2600 px,
  piksel 0,5 m, sha256 = `f5f7c69bd748...` z `probki.md` (o ile GUGiK nie
  podmienil pliku - wtedy zapisz nowa sume), wersja `2025-..._84020_<sha8>`.
- [ ] **E2E-2 NMPT 0.5m:** `--product nmpt --sheet N-33-58-A-d-1-2
  --resolution 0.5m --vertical-crs EVRF2007` -> 4191x2364 px, piksel 0,5 m
  (`probki.md`: `5e2cdf7e29f1`).
- [ ] **E2E-3 KRON86 0.5m i 0.6m/0.15m:** `6.130.26.07.1.2` KRON86 0.5m;
  `N-33-77-B-c-3-3` EVRF2007 0.6m; `7.159.25.12.2` EVRF2007 0.15m - pliki,
  piksel z naglowka ASC rowny etykiecie.
- [ ] **E2E-4 bledy przed siecia:** `--cutout --resolution 0.5m`, NMT 5m
  KRON86, `--product nmpt` bez `--resolution`, `--resolution 0,5m` - `Error:`
  kod 1, katalog wyniku pusty.
- [ ] **E2E-5 raport:** `elevation availability --product nmt --country pl
  --bbox 565000,242000,569000,246000` i Pomorze (E 339000-343000,
  N 744800-747000): wyniki zgodne z punktem 9 sekcji "Weryfikacja" (albo
  z nowymi faktami GUGiK - opisz); `--json` vs API (skrypt wolajacy
  `check_availability` z tymi samymi argumentami: identyczny JSON przy tym
  samym cache); czas obu raportow.
- [ ] **E2E-6 raport = pobranie:** podpowiedz najnowszej kompletnej kombinacji
  Krakowa (z `-o <dir>`) - zbior pobranych godel = `sheets_full` kombinacji,
  etykiety wersji = rok kombinacji.
- [ ] **E2E-7 LAZ:** `--product laz` dla Pomorza - kombinacja 2025 ma kafle
  NIE i nie jest kompletna (dodatek `pokrycie.md`); raport niczego nie
  pobiera (`du` katalogu wyniku = 0).
- [ ] **E2E-8 wycinek 1m bez zmian:** wycinek NMT 1m `--cutout
  --horizontal-crs EPSG:2180` z `probki.md` (`nmpt_wcs`/`nmt_wcs`) - ta sama
  siatka i wartosci co przed zmiana (porownanie z wersja z `develop`).
- [ ] **Raport E2E i commit** - `docs(research): E2E planu A (warianty NMT/NMPT, availability)`.

## Kryteria zamkniecia

- Wszystkie siatki z rejestru pobieralne z CLI i API; zadna lista
  rozdzielczosci/ukladow poza rejestrem; `--help`, `list-sources`, walidacja
  i komunikaty z rejestru.
- Pobieranie i raport na jednym skorowidzu WFS; archiwa pobierane jako
  pliki zrodlowe i liczone jako kombinacje z formatem (decyzja 13); `Info:`
  tylko dla rekordow spoza rejestru.
- Raport: kryteria specu 4.4 (wartosci z punktu 9 albo udokumentowane nowe
  fakty), bez pobran, JSON CLI = API, podpowiedz bez `--output`.
- Wycinek 1m bez zmian zachowania; LAZ bez zmian zachowania na wspolnym
  transporcie WFS.
- Brama zielona; E2E opisane; ADR-041, CHANGELOG, USAGE, ARCHITECTURE,
  SCOPE, PRD zaktualizowane. Plan B moze dopisac CZ do rejestru i raportu
  bez zmiany ksztaltu typow.
