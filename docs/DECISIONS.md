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
**Status:** Przyjeta

**Kontekst:** GUGiK oferuje dwa sposoby pobierania NMT: OpenData (pliki ASC po godle) i WCS (GeoTIFF po bbox). Poczatkowo probowano ujednolicic oba w jednym flow.

**Opcje:**
- A) Jeden interfejs z parametrem `method` — ujednolicone API, ale skomplikowana logika wewnetrzna
- B) Rozdzielenie na `download_sheet(godlo)` → ASC i `download_bbox(bbox)` → GeoTIFF

**Decyzja:** Rozdzielenie (opcja B). Godlo zawsze daje ASC przez OpenData, bbox zawsze daje GeoTIFF przez WCS. Roznne formaty, rozne API, rozne ograniczenia — nie ma sensu ich laczyc.

**Konsekwencje:** Czytelniejszy kod. Uzytkownik jawnie wybiera metode. NMT 5m dziala tylko przez OpenData (WCS niedostepne).

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
**Status:** Przyjeta

**Kontekst:** Po dodaniu obslugi NMT 5m, pliki 1m i 5m dla tego samego godla mialy te sama sciezke. Grozi nadpisaniem.

**Opcje:**
- A) Suffix w nazwie pliku (`N-34-130-D-d-2-4_5m.asc`) — proste, ale niespojne z konwencja GUGiK
- B) Podkatalog rozdzielczosci (`data/1m/...`, `data/5m/...`) — czyste rozdzielenie

**Decyzja:** Podkatalog rozdzielczosci (opcja B). Struktura: `data/1m/N-34/130/.../plik.asc` i `data/5m/N-34/130/.../plik.asc`.

**Konsekwencje:** Breaking change — stare sciezki bez `1m/`/`5m/` nie sa kompatybilne. Czyste rozdzielenie, latwe do zrozumienia. FileStorage przyjmuje parametr `resolution`.

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
**Status:** Przyjeta

**Kontekst:** Po dodaniu NMPT i Ortofoto, podkatalogi `1m` i `5m` w FileStorage staly sie niejednoznaczne — moglyby oznaczac rozdzielczosc dowolnego produktu. Nowe produkty uzywaja podkatalogow `nmpt` i `orto`.

**Opcje:**
- A) Zostawic `1m`/`5m` — proste, ale niespojne z `nmpt`/`orto`
- B) Zmienic na `nmt_1m`/`nmt_5m` — jednoznaczne, spojne z konwencja product/

**Decyzja:** Opcja B. Struktura: `data/nmt_1m/...`, `data/nmt_5m/...`, `data/nmpt/...`, `data/orto/...`. FileStorage uzywa `_RESOLUTION_SUBDIRS` mapping do tlumaczenia rozdzielczosci na nazwe podkatalogu.

**Konsekwencje:** Breaking change — stare sciezki `data/1m/` i `data/5m/` nie sa kompatybilne. Jednoznaczna struktura. Parametr `product` w FileStorage pozwala na latwe dodawanie nowych produktow.

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

**Decyzja:** Opcja B. `GugikLazProvider` z discovery area-based: godło (≤1:10000) / `--bbox` / `--geometry` → bbox EPSG:2180 → WFS GetFeature (`gugik:SkorowidzDanychPomiarowychLIDAR{rok}`) → kafle z `url_do_pobrania`. Spojny schemat wejscia z NMT/NMPT/orto (te same tryby, finest = 1:10000); jedyna roznica wynika z danych GUGiK — jedno godło 1:10000 = wiele kafli LAZ. Godło kafla **nie jest parsowane** (opaque label) → `FileStorage.get_raw_path()` buduje sciezke bez `SheetParser`. Dwie usługi WFS wg ukladu wysokosciowego (EVRF2007 domyslnie, KRON86 legacy). Domyslnie newest-per-tile (dedup po godle), flagi `--year`/`--vertical-crs`/`--min-density`. Os EPSG:2180 dla WFS (`BBOX=min_x,min_y,max_x,max_y,urn:...EPSG::2180`) zweryfikowana live; dodatkowo client-side post-filter przeciecia kafla z bbox.

**Konsekwencje:** Brak zmian w `SheetParser` (parser pozostaje przy 1:10000, spojnie z NMT/orto). LAZ omija `DownloadManager.download_sheet` — wlasny przeplyw `_cmd_download_laz` (area→WFS→tiles→parallel download). WFS daje metadane (rok/gestosc/CRS) za darmo. Zaleznosc od nazw feature-type `LIDAR{rok}` zlagodzona przez GetCapabilities + fallback `FALLBACK_YEARS`. 41 nowych testow; E2E zweryfikowane (pliki z magic `LASF`).

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
`AccessChannel.horizontal_crs` kanalu `ARCGIS_IMAGE`). Pobranie godlem zada
wiec `exportImage` z `bboxSR=imageSR=3045` — serwer reprojektuje w locie;
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
implementacji — patrz `.superpowers/sdd/2026-08-11-etap1-cz-fundament-dmr/progress.md`):**

1. **Semantyka `transform.horizontal` w sidecarach = "reprojekcja zamowiona
   przez uzytkownika (`--target-crs`)", NIE "praca serwera".** Kafel TM33
   pobrany godlem jest serwerowo reprojektowany 5514→3045 wewnatrz
   `exportImage` (dane leza natywnie w Krovaku), a mimo to jego sidecar ma
   `transform: null` — bo z perspektywy uzytkownika godlo CZ zawsze
   dostarcza natywny produkt 1:1 (uklad zdefiniowany schematem kafli, patrz
   punkt c). Bbox z `--target-crs EPSG:3045`/`EPSG:2180` ma
   `transform.horizontal = "server:EPSG:<kod>"` — bo tam uzytkownik jawnie
   zazadal ukladu innego niz natywny dla danego trybu. Implementacja:
   `_write_cz_sidecar()` (`cli/download_cmd.py`) ustawia `transform.horizontal`
   TYLKO gdy `server_crs` (jawnie zadany `--target-crs`) rozni sie od
   natywnego ukladu kanalu przed nadpisaniem — nie od faktycznego SR danych
   zrodlowych na serwerze. Decyzja: sidecar opisuje **zadanie transformacji
   wzgledem natywnego produktu trybu**, nie wewnetrzna mechanike serwera —
   spojne z rola sidecara jako kontraktu dla Hydrografu (co dostal, nie jak
   to policzono).
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
   kazde zadanie `--country auto` w poludniowej Polsce (lon < 18,86°E,
   lat < 51,06°N — pas siegajacy np. okolic Krakowa/Rzeszowa) wysyla
   zapytanie do CUZK, mimo ze bbox realnie lezy w calosci w Polsce. Skutek:
   dodatkowy raster wypelniony `nodata` (`-9999`) + dodatkowy sidecar CZ bez
   uzytecznych danych, a nie blad — ale zbedny ruch sieciowy i plik.
   Wlasciwa naprawa (wielokat granicy administracyjnej zamiast prostokata)
   jest zaplanowana na etap 2 (patrz `docs/SCOPE.md`).

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
