# Rejestr decyzji — Kartograf

Kazda decyzja architektoniczna lub projektowa jest udokumentowana ponizej.
Format: numer, data, kontekst (dlaczego temat powstal), rozwazone opcje, decyzja, konsekwencje.

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
**Status:** Przyjeta (czesc "bbox = WCS" nieaktualna — patrz korekta 2026-09-29)

**Kontekst:** GUGiK oferuje dwa sposoby pobierania NMT: OpenData (pliki ASC po godle) i WCS (GeoTIFF po bbox). Poczatkowo probowano ujednolicic oba w jednym flow.

**Opcje:**
- A) Jeden interfejs z parametrem `method` — ujednolicone API, ale skomplikowana logika wewnetrzna
- B) Rozdzielenie na `download_sheet(godlo)` → ASC i `download_bbox(bbox)` → GeoTIFF

**Decyzja:** Rozdzielenie (opcja B). Godlo zawsze daje ASC przez OpenData, bbox zawsze daje GeoTIFF przez WCS. Roznne formaty, rozne API, rozne ograniczenia — nie ma sensu ich laczyc.

**Konsekwencje:** Czytelniejszy kod. Uzytkownik jawnie wybiera metode. NMT 5m dziala tylko przez OpenData (WCS niedostepne).

**Korekta (2026-09-29, audyt dokumentacji):** czesc "bbox zawsze daje GeoTIFF
przez WCS" juz nie obowiazuje: CLI rozwija bbox PL na arkusze OpenData,
a jeden GeoTIFF dla bboxa/geometrii buduje z arkuszy wycinek `--target-crs` /
`download_pl_cutout` (ADR-027). WCS zostal tylko w
`DownloadManager.download_bbox` / `GugikProvider.download_bbox` i tylko dla
KRON86 — endpoint EVRF2007 GUGiK wycofal (HTTP 404 od 2026-08), a
`download_bbox` z EVRF2007 konczy sie `ValidationError` przed siecia.

---

## ADR-004: EVRF2007 jako domyslny uklad wysokosciowy

**Data:** 2026-01-21
**Status:** Przyjeta

**Kontekst:** GUGiK oferuje NMT w dwoch ukladach: KRON86 (Kronsztadt, historyczny) i EVRF2007 (European Vertical Reference Frame, aktualny standard). Wczesniej domyslny byl KRON86.

**Opcje:**
- A) Zostawic KRON86 jako domyslny — kompatybilnosc wsteczna
- B) Zmienic na EVRF2007 — aktualny standard, wymagany przez NMT 5m

**Decyzja:** EVRF2007 jako domyslny (opcja B). Jest to aktualny standard geodezyjny w Polsce. KRON86 dostepny jako `--vertical-crs KRON86`.

**Konsekwencje:** Breaking change w v0.3.2. Uzytkownicy uzywajacy KRON86 musza jawnie podac flage. NMT 5m dziala out-of-the-box.

---

## ADR-005: Struktura katalogow NMT rozdzielona wg rozdzielczosci

**Data:** 2026-01-21
**Status:** Przyjeta (uklad katalogow zastapiony przez ADR-013, a nastepnie przez ADR-026)

**Kontekst:** Po dodaniu obslugi NMT 5m, pliki 1m i 5m dla tego samego godla mialy te sama sciezke. Grozi nadpisaniem.

**Opcje:**
- A) Suffix w nazwie pliku (`N-34-130-D-d-2-4_5m.asc`) — proste, ale niespojne z konwencja GUGiK
- B) Podkatalog rozdzielczosci (`data/1m/...`, `data/5m/...`) — czyste rozdzielenie

**Decyzja:** Podkatalog rozdzielczosci (opcja B). Struktura: `data/1m/N-34/130/.../plik.asc` i `data/5m/N-34/130/.../plik.asc`.

**Konsekwencje:** Breaking change — stare sciezki bez `1m/`/`5m/` nie sa kompatybilne. Czyste rozdzielenie, latwe do zrozumienia. FileStorage przyjmuje parametr `resolution`.

**Korekta (2026-08-28):** decyzja "rozdzielczosc jest wymiarem sciezki"
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

**Korekta (2026-09-29, audyt dokumentacji; stan kodu po audycie 0.7.0
i fali review max 2026-09-28):** (a) od audytu 0.7.0 (A1-7) liczy sie
dodatnie pole przeciecia — stykajace sie krawedzie nie sa przecieciem;
(b) bbox w EPSG:2180 jest zamieniany na obwiednie WGS84 z 4 naroznikow i 2
punktow na poludniku osiowym 19°E (tam lezy maksimum szerokosci gornej
krawedzi — fakt 8 fali review max); obwiednia jest szersza niz bbox, wiec
selekcja obejmuje arkusze sasiednie (obwiednia EPSG:2180 arkusza
`N-34-130-D-d-2-4` daje 9 godel, `N-34-130-D` w skali 1:50000 — 16 zamiast
4; w duzym wycinku do ~3,7 km poza zadaniem); (c) `--system 2000` liczy
obwiednie z 4 naroznikow (`core/parser_2000`, backlog).

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
**Status:** Przyjeta (uklad katalogow zastapiony przez ADR-026)

**Kontekst:** Po dodaniu NMPT i Ortofoto, podkatalogi `1m` i `5m` w FileStorage staly sie niejednoznaczne — moglyby oznaczac rozdzielczosc dowolnego produktu. Nowe produkty uzywaja podkatalogow `nmpt` i `orto`.

**Opcje:**
- A) Zostawic `1m`/`5m` — proste, ale niespojne z `nmpt`/`orto`
- B) Zmienic na `nmt_1m`/`nmt_5m` — jednoznaczne, spojne z konwencja product/

**Decyzja:** Opcja B. Struktura: `data/nmt_1m/...`, `data/nmt_5m/...`, `data/nmpt/...`, `data/orto/...`. FileStorage uzywa `_RESOLUTION_SUBDIRS` mapping do tlumaczenia rozdzielczosci na nazwe podkatalogu.

**Konsekwencje:** Breaking change — stare sciezki `data/1m/` i `data/5m/` nie sa kompatybilne. Jednoznaczna struktura. Parametr `product` w FileStorage pozwala na latwe dodawanie nowych produktow.

**Korekta (2026-08-28):** uklad `nmt_1m`/`nmt_5m` zastapiony segmentami
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
**Status:** Przyjeta

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
**Status:** Przyjeta (zastepuje ADR-014)

**Kontekst:** Filtrowanie po kategorii (pt/hydro) w Bdot10kProvider dodane w ADR-014 okazalo sie niepotrzebna komplikacja. Uzytkownik i tak pobiera caly ZIP z GUGiK — filtrowanie po stronie klienta powodowalo utrate danych (np. SW* warstwy pomijane domyslnie). Lepiej pobrac wszystko i pozwolic uzytkownikowi filtrowac w GIS.

**Opcje:**
- A) Zostawic category — backward compatible, ale komplikuje API i domyslnie traci dane
- B) Usunac category, pobierac wszystko — prostsze API, brak utraty danych

**Decyzja:** Opcja B. Usunieto `CATEGORY_FILTERS`, `PT_LAYERS`, `HYDRO_LAYERS`, parametr `category` z metod, argument CLI `--category`. `_extract_gpkg_from_zip()` wyciaga wszystkie pliki GPKG z ZIP i scala je w jeden plik. `get_available_layers()` zwraca wszystkie 15 warstw.

**Konsekwencje:** Breaking change — kod uzywajacy `category="hydro"` musi byc zaktualizowany (parametr jest ignorowany przez `**kwargs`). Prostsze API. Brak utraty danych. 835 testow (z 849 — 14 testow category usunietych).

---

## ADR-017: PL-2000 sheet naming — composition pattern with auto-detection

**Data:** 2026-02-24
**Status:** Przyjeta

**Kontekst:** PL-2000 to inny system godlowania niz PL-1992. PL-2000 uzywa formatu `strefa.pas.slup[.podpodzialki]` (np. `6.179.12.20`), 4 stref merydianowych (EPSG:2176-2179) i skal od 1:10k do 1:500. Wymaga osobnego parsera z inna logika BBox i hierarchii.

**Opcje:**
- A) Dziedziczenie: Parser2000(SheetParser) — problematyczne bo SheetParser jest scisle zwiazany z PL-1992 (pas/slup literowe, inne skale)
- B) Composition: SheetParser deleguje do Parser2000 — loose coupling, auto-detekcja formatu
- C) Osobna klasa bez integracji — brak unified API

**Decyzja:** Opcja B. Composition pattern: `SheetParser` wykrywa format godla przez regex `^[5-8]\.\d` i deleguje do `Parser2000` (lazy import). Auto-detekcja jest przezroczysta — uzytkownik uzywa `SheetParser("6.179.12")` i nie musi wiedziec o Parser2000. BBox w natywnym CRS strefy (EPSG:2176-2179), nie EPSG:2180. `find_sheets_for_bbox(bbox, system="2000")` dispatuje do `find_sheets_2000_for_bbox()`.

**Konsekwencje:** Czysta separacja logiki PL-1992 i PL-2000. Auto-detekcja w SheetParser zachowuje unified API. Nowe eksporty: `Parser2000`, `find_sheets_2000_for_bbox`. CLI: `--system {1992,2000}` pozwala wymusic system. FileStorage: podkatalog `nmt_2000_1m` dla PL-2000 arkuszy.

**Korekta (2026-08-28, ADR-026):** zapowiedziany tu podkatalog `nmt_2000_1m`
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

**Korekta (2026-09-29, audyt dokumentacji):** `max_workers=4` jest domyslne
w CLI (`--workers`), a w bibliotece — 1 (`DownloadManager`,
`download_pl_cutout`, `run_pl_cutout`). Metody zwracaja `list[Path]`,
a strukturalny wynik (`DownloadResult`: succeeded/failed/skipped/no_coverage)
trafia do `DownloadManager.last_result`.

---

## ADR-019: SQLite WAL jako metadata cache

**Data:** 2026-03-03
**Status:** Przyjeta

**Kontekst:** Kazde pobieranie arkusza wymaga request do GUGiK API po URL OpenData. Przy powtarzanych pobieraniach te same URLe sa odpytywane wielokrotnie. Podobnie BDOT10k — mapowanie punkt→TERYT.

**Opcje:**
- A) SQLite z WAL mode — plik lokalny, zero zaleznosci, concurrent reads, TTL
- B) Redis — szybki, ale wymaga serwera, overengineering
- C) Pickle/JSON file — proste, ale brak concurrent access, brak TTL

**Decyzja:** SQLite WAL (A). Zero dodatkowych zaleznosci (sqlite3 w stdlib), WAL mode umozliwia rownoczesne odczyty z ThreadPoolExecutor, TTL 7 dni zapobiega stalym danym, threading.Lock chroni zapisy.

**Konsekwencje:** Nowy modul `kartograf/cache/metadata.py`, `.kartograf_cache.db` w katalogu roboczym, CLI `kartograf cache` do zarzadzania. `prune_expired()` czysci stale wpisy. Optional — providery dzialaja bez cache.

**Uzupelnienie 2026-09-30:** CLI PL podpina `MetadataCache` do NMT/NMPT/orto
poza `--force` (ten tryb omija cache). API wycinka ma `cache=`.
Cache przechowuje `record_cache` (pelny `source` albo potwierdzony
`no_coverage`, TTL 7 dni), a nie same URL-e; `url_cache` jest usuwana
przy otwarciu bazy, `get_url/set_url` zastapiono `get_record/set_record`.
`stats()["record_count"]` i CLI `Record entries` raportuja nowe wpisy.

---

## ADR-020: Walidacja warstw WMS przez GetCapabilities

**Data:** 2026-03-24
**Status:** Przyjeta

**Kontekst:** Hardcoded nazwy warstw WMS w GugikProvider okazaly sie bledne dla NMT 5m — GUGiK zmienil nazwy warstw (np. `SkorowidzeNMT2022` → `SkorowidzeNMT2022iStarsze`, dodal `SkorowidzeNMT2025`). Blad powodowal niepowodzenie wszystkich pobrań NMT 5m. Potrzebny mechanizm wykrywania rozbieznosci miedzy hardcoded a live WMS.

**Opcje:**
- A) Walidacja przy inicjalizacji providera — zapytanie GetCapabilities w `__init__()`, natychmiastowa detekcja
- B) Lazy validation — zapytanie przy pierwszym `_get_opendata_url()`, bez kosztu jesli provider nie jest uzywany
- C) Periodyczna walidacja — cron/timer co N godzin
- D) Brak walidacji — poleganie na hardcoded wartosciach, reczna aktualizacja

**Decyzja:** Lazy validation (opcja B). Nowe metody `_fetch_wms_layers()` (GetCapabilities XML → lista warstw) i `_get_validated_layers()` (porownanie hardcoded z live). Walidacja wykonywana raz, wynik cache'owany in-memory per instancja providera (bez lock — benign duplicate przy concurrent access). Osobny timeout 10s dla GetCapabilities (krotszy niz standardowy 30s). Przy rozbieznosci: warning + auto-aktualizacja do live warstw. Przy bledie GetCapabilities: warning + fallback na hardcoded warstwy.

**Konsekwencje:** Automatyczne wykrywanie zmian warstw WMS bez recznej aktualizacji kodu. Zero kosztu jesli provider nie jest uzywany (lazy). GugikNmptProvider dziedziczy walidacje z GugikProvider bez dodatkowego kodu. GugikOrtoProvider poza zakresem (inna hierarchia dziedziczenia, inny format warstw). 17 nowych testow w `tests/test_wms_layer_validation.py`.

**Aktualizacja (2026-06-24):** GugikOrtoProvider otrzymal wlasna walidacje (`_fetch_wms_layers`/`_get_validated_layers`, wyklucza warianty `Zasiegi`). Nazwy warstw NMT 1m/EVRF2007 i Orto odswiezone (nowe roczniki 2026).

**Aktualizacja (2026-09-29; historia przed fala naprawcza):**
GetFeatureInfo potrafilo zwrocic HTTP 200 z raportem OGC zamiast
prawidlowej pustej odpowiedzi; taki raport oznacza awarie warstwy,
nie `NoCoverageError` (ADR-027). Stary fallback na zaszyte warstwy
mogl zadac nieaktualne nazwy i zgubic nowsze rekordy; ponizsza
errata zastapila te polityke.

**Errata 2026-09-30 (fala naprawcza):** zaszyte `WMS_LAYERS` dla
NMT/NMPT/orto usunieto. Warstwy pochodza tylko z GetCapabilities,
odkrywane lazy i cache'owane per instancja z lockiem; blad pobrania
GetCapabilities nie jest zapamietywany ani zastapiony stara lista.
GetFeatureInfo oczekuje szablonu pustej lub pelnej odpowiedzi
(`var ... = [];`); raport OGC lub bledny szablon to `DownloadError`
bez cichej degradacji do starszej kampanii. Zapytania transportowe
maja 3 proby, a orto korzysta z tego samego parsera rekordow.

---

## ADR-021: LAZ (chmury punktów LIDAR) — discovery przez WFS, area-based

**Data:** 2026-06-24
**Status:** Przyjeta

**Kontekst:** Dodanie pobierania plików LAZ (dane pomiarowe ALS) z GUGiK. Dwa problemy: (1) kafle LAZ są godłowane drobniej niz 1:10000 (np. `M-34-27-B-b-2-1-1`, modul 1:1000), a `SheetParser` parsuje maks. do 1:10000 — godło kafla jest nieparsowalne; (2) usługa **WMS** skorowidzy LAZ (`DanePomNMT/WMS/...`) zwraca HTTP 401, wiec mechanizm WMS GetFeatureInfo (jak w NMT/orto) nie dziala.

**Opcje:**
- A) Rozszerzyc `SheetParser` do 1:1000 (PL-1992 + PL-2000) i pobierac po godle kafla — duzo pracy, a godło i tak jest opaque w URL
- B) Discovery przez **WFS** GetFeature po bbox — usługa otwarta (HTTP 200), feature zawiera `url_do_pobrania` wprost; godło kafla jako etykieta (bez parsowania)
- C) Konstruowanie URL z wzorca `.../{density}/{density}_{id}_{godło}.laz` — wymaga nieprzewidywalnego `id` → niewykonalne
- D) ATOM/CSW — bardziej zlozone i mniej bezposrednie niz WFS

**Decyzja:** Opcja B. `GugikLazProvider` z discovery area-based: godło (≤1:10000) / `--bbox` / `--geometry` → bbox EPSG:2180 → WFS GetFeature (`gugik:SkorowidzDanychPomiarowychLIDAR{rok}`) → kafle z `url_do_pobrania`. Godło kafla jest opaque, bez zmian `SheetParser`; dwie usługi WFS wg układu pionowego, domyślnie newest-per-tile i filtry `--year`/`--min-density`. Historyczna implementacja wysyłała osie EPSG:2180 jako (E,N), co skorygowano w erracie poniżej.

**Konsekwencje:** Brak zmian w `SheetParser`: godlo kafla pozostaje opaque. LAZ ma osobny przeplyw `_cmd_download_laz` (area→WFS→tiles→parallel download). WFS daje rok/gestosc/CRS; roczniki pochodza z GetCapabilities (bez fallbacku listy zaszytej). Wyniki live sprzed naprawy osi potwierdzaly format LASF, a nie poprawne polozenie kafla.

**Errata 2026-09-29 (diagnoza historyczna):** pierwotne
„zweryfikowano live” sprawdzalo niepoprawnie sparowane BBOX i envelope:
`urn:ogc:def:crs:EPSG::2180` wymaga (N,E), a stary klient uzywal
(E,N). Pod Spytkowicami odpowiedz z bledna kolejnoscia kierowala
do Lubuskiego zamiast poprawnego kafla `M-34-76-A-a-1-1-3`.
Ponizsza naprawa zastapila te zalozenia.

**Naprawa 2026-09-30 (K1/N7):** dla WFS `urn:ogc:def:crs:EPSG::2180`
`BBOX` i odczyt `gml:Envelope` uzywaja osi EPSG (N,E);
straz sprawdza, czy przynajmniej jeden zwrocony kafel przecina
zadany obszar (gdy wszystkie sa poza nim, `DownloadError`).
Roczniki pochodza z GetCapabilities (bez `FALLBACK_YEARS`); blad
ktoregokolwiek rocznika po ponowieniach konczy `discover_tiles`
`DownloadError`, nie mylacym wynikiem pustym.

---

## ADR-022: Architektura zrodel wielokrajowych — deskryptory, rejestry, sidecar, twarda polityka transformacji (etap 0)

**Data:** 2026-08-10
**Status:** Przyjeta

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
**Status:** Przyjeta

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
5514 (katalog danych danych). To tworzy jawna asymetrie wzgledem PL: `--bbox` w PL
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
7. **Errata 2026-09-29 (audyt dokumentacji i testy na zywo;
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
     tryb listy/hierarchii ma od 2026-09-30 tolerancje R5 (ADR-027 addendum);
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

---

## ADR-024: Reprojekcja tresci CZ wylacznie lokalnie (zakaz `imageSR` != natywny)

**Data:** 2026-08-11
**Status:** Przyjeta (zastepuje ADR-023, "Ustalenia dodatkowe" pkt 1)

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

**Errata (2026-09-29, pomiary historyczne przed poprawka; raport
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

**Errata 2 (fala naprawcza 2026-09-30, D1: tor CZ odmrozony):**
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
**Status:** Przyjeta (domyka odroczenie z ADR-017; zastepuje uklad ADR-013)

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
`--bbox` lada w `<segment>/bbox/<coords><ext>` (konwencja d68be23, wspolna
PL/CZ). `landcover/` bez zmian.

**Konsekwencje:** BREAKING na dysku (tabela migracji: CHANGELOG 0.7.0
i ARCHITECTURE.md sekcja 3). Nowe zrodlo (np. DE) = nowy wpis deskryptora,
zero zmian w kodzie sciezek. Konsument czytajacy `storage_subdir` wprost
dostaje szablon — pole bylo de facto wewnetrzne; uzyj `resolve_subdir()`.
FileStorage: nowy parametr `vertical_crs` (default "EVRF2007"); nieznany
`product` nadal passthrough (np. testowe `nmt_2000_1m`).

**Uzupelnienie (2026-09-29, audyt dokumentacji; zmiany kodu z fali review max
2026-09-28, zn. 7, 8, 11):** `resolve_subdir` odrzuca pusty/bialy wymiar
(`ValidationError`); dla kafli LAZ `{uklad}` wyznacza `LazTile.uklad`
(kaskada `uklad_xy` -> format godla -> "2000"), przekazywany jawnie
w `FileStorage.get_raw_path(..., uklad=)` — bez `uklad=` obowiazuje regula
formatu godla; `FileStorage(resolution=/product=)` mapuje na KLUCZ
deskryptora zamiast kopii szablonu (jedno zrodlo prawdy). Na zywo
2026-09-29 wszystkie segmenty powstaly zgodnie z tabela (NMT 1 m/5 m,
EVRF2007/KRON86, PL-1992/PL-2000, NMPT, orto, LAZ, CZ dmr5g/dmr4g bpv/evrf2007,
`bbox/`); pochodzenie i zgodnosc rekordu GUGiK reguluje ADR-028.

---

## ADR-027: --target-crs dla PL — scalony wycinek bbox (mozaika + pinned warp)

**Data:** 2026-08-28
**Status:** Przyjeta (errata do ADR-023: target-crs przestaje byc flaga czeska;
uzupelnienia 2026-09-28 na koncu wpisu)

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
(`transform: null`; od 2026-09-28 crop na siatce arkuszy — drugie
uzupelnienie nizej). Fail-fast operacji przed siecia; kazdy failed arkusz =
blad calosci (kod 1; zmienione 2026-09-28 dla arkusza bez danych GUGiK —
uzupelnienie R5 nizej). Nazwa pliku niesie wspolrzedne w ukladzie WYNIKU.
Sidecar pisze CLI (od 2026-09-28 biblioteka, `write_pl_cutout_sidecar` —
drugie uzupelnienie nizej): `horizontal_crs=target`, `transform.horizontal=
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
w trybie bbox i w sumie R-01 ma jeszcze zapas 1 piksela (drugie
uzupelnienie nizej). Wycinek z `--geometry` obejmuje CALA obwiednie
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

**Uzupelnienie 2026-09-28 (R5, review max zn. 2):** arkusz, dla ktorego GUGiK
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

**Uzupelnienie 2026-09-28 (R1, R3, fakty 5-8 planu fali review max):**
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

**Uzupelnienie 2026-09-30 (R5-lista, D3/D8, D4/D5/D9, N2/N4/N9):**
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
**Status:** Przyjeta

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

---

<!-- Szablon nowej decyzji:

## ADR-XXX: Tytul

**Data:** YYYY-MM-DD
**Status:** Przyjeta | Odrzucona | Zastapiona przez ADR-YYY

**Kontekst:** Dlaczego temat powstal.

**Opcje:**
- A) ...
- B) ...

**Decyzja:** Ktora opcja i dlaczego.

**Konsekwencje:** Co z tego wynika.

-->
