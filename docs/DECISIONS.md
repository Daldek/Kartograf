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
