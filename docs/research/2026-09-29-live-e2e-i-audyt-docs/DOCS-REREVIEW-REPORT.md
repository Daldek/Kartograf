# DOCS-REREVIEW — niezalezny przeglad fali poprawek dokumentacji (Kartograf, 2026-09-29)

Zakres: `152c31e..515f275` (12 commitow), galaz `develop`, HEAD `515f275`. Repo Kartografu
i Hydrografu tylko czytane (`git status --short` Kartografu czysty przed i po; zmienione
wylacznie ignorowane cache narzedzi `.mypy_cache`/`.ruff_cache`/`__pycache__`). Pliki tymczasowe tylko
w katalogu z `mktemp -d` w scratchpadzie sesji. Bez sieci, bez subagentow.

## Werdykt: POPRAWKI POTRZEBNE

**1 BLOKUJACE, 2 WAZNE, 12 DROBNE.** Kod bez zmian zachowania (AST), pliki K1/K2/K6
nietkniete, brama zielona, backlog "Do naprawy" kompletny (21 ID dokladnie raz), CRLF
w `DECISIONS.md` zachowane, odsylacze do raportow tylko do nazw z listy. Do poprawy:

- **RR-1 (BLOKUJACE):** CLAUDE.md (i SCOPE, ARCHITECTURE) twierdzi, ze na granicach z krajami
  spoza rejestru `auto` == `pl` — sprzeczne z przycinaniem S3 opisanym dwa zdania wczesniej
  (Osinow Dolny na granicy PL-DE: auto 6,2 km / 4 arkusze, `--country pl` 8,9 km / 6 arkuszy, L5).
- **RR-2 (WAZNE):** ARCHITECTURE 4.3 krok 6 — "1,1-2,3 m przy granicy" (K2) nie pochodzi z raportow
  i zaniza zachodni odcinek granicy PL-CZ (~3,1-3,4 m wg roznicy EPSG:1622-4829; L4: Karkonosze 2,72 m).
- **RR-3 (WAZNE):** S4 "gdy GetCapabilities zawiedzie, NMPT nie pobiera sie wcale" (DECISIONS,
  PROGRESS x2) — falsz w ogolnosci: arkusze z warstw 2025/2024 nadal sie pobieraja (symulacja).

---

## Wyniki pkt 1-9

### 1. Kod bez zmian zachowania — PASS

- Skrypt AST ze zlecenia (`.venv/bin/python <mktemp>/ast_check.py` z katalogu repo):
  12 plikow `IDENTYCZNE` (`__init__.py`, `cli/download_cmd.py`, `core/sheet_parser.py`,
  `download/cutout.py`, `download/manager.py`, `download/storage.py`, `exceptions.py`,
  `providers/pl/gugik.py`, `sources/descriptor.py`, `sources/registry.py`, `sources/sidecar.py`,
  `transport/mosaic.py`), `kartograf/cli/_parser.py` — `ROZNE` (spodziewane).
- `_parser.py`: AST z zamaskowanymi wartosciami WSZYSTKICH argumentow `help=`/`description=`/
  `epilog=` (68 w BASE i 68 w HEAD) oraz bez docstringow — **identyczny**; kazda z 68 wartosci
  to `ast.Constant` (literal) w obu wersjach; rozni sie 9 literalow: `help` i `description`
  subkomendy `download`, `help` dla `--bbox`, `--target-crs`, `--scale`, `--force`,
  `--vertical-crs`, `--product` i `help` subkomendy `landcover`. `choices`, `default`,
  `metavar`, komunikaty runtime — bez zmian.
- `--help` wszystkich 13 (sub)komend: exit 0 (brak pulapki `%` w argparse; zadnego `%`
  w nowych napisach pomocy).
- `git diff --stat 152c31e..515f275 -- kartograf/providers/pl/gugik_laz.py kartograf/providers/cuzk kartograf/transform/crs.py`
  -> **puste**. Testy (`tests/`) nie zmienione (brak w `--stat`).

### 2. Prawdziwosc — 3 znaleziska istotne + 12 drobnych

CLAUDE.md (wszystkie nowe/zmienione zdania) i README "Znane problemy" (calosc) sprawdzone
zdanie po zdaniu; reszta szeroko (lista nizej). Migracja 0.6.1 -> 0.7.0 w CHANGELOG
sprawdzona importami (`kartograf.providers.pl.{bdot10k,gugik,gugik_nmpt,gugik_orto,gugik_laz}`
i `kartograf.providers.base` — OK; stare `kartograf.providers.{bdot10k,gugik,gugik_nmpt,
gugik_orto,gugik_laz,landcover_base}` — `ModuleNotFoundError`), `git show v0.6.1:...`
(`nmt_1m`/`nmt_5m` bez pionu w sciezce, brak sidecarow, domyslny EVRF2007, PL-2000 dzielone
po kropkach) i pomiarami (`vertical_crs_code("EVRF2007") == "EPSG:5621"`, `import kartograf`
laduje `rasterio`, `NoCoverageError` podklasa `DownloadError`, `_get_teryt_for_point` istnieje).
Znaleziska: RR-1..RR-3 oraz DROBNE RR-4..RR-15.

### 3. Znane bledy — PASS (z RR-3, RR-14)

- `docs/PROGRESS.md:165-194` — tabela: 21 ID (K1-K6, S1-S5, N1-N9, H1), wagi zgodne
  z `KNOWN-BUGS.md`.
- `docs/PROGRESS.md:989-991` — "#### Do naprawy — ..." jako pierwsza podsekcja "## Backlog";
  `grep` checkboxow w zakresie 991-1158: kazde z 21 ID **dokladnie raz** (`- [ ] **K1**` ...);
  K2 (`:1019`) i K6 (`:1057`) z "Wymaga odmrozenia toru CZ (ADR-024) — decyzja uzytkownika".
- Odsylacze `plik:linia` w backlogu sprawdzone na HEAD (45, wszystkie): K1 `gugik_laz.py:363-369,
  :464-465, :482-497, :385-388`; K2 `crs.py:192, :236`, `KNOWN_PATHS`; K3 `gugik.py:643-647,
  :604-622`; K4 `gugik.py:599-622, :607, :612-622`, `gugik_orto.py:376-384`; K5 j.w.; K6
  `client.py:142`, `_tile_grid`; S1 `gugik.py:541, :594, :300`; S2 `download_cmd.py:863-919,
  :869, :918-919, :540-550, :1159-1161`; S3 `:284-344, :322-327, :517`; S4 `gugik_nmpt.py:83-86`;
  S5 `mosaic.py:324, :265-271`; N1 `gugik.py:455`; N2 `cutout.py:609`; N3 `client.py:139-147`;
  N4 `manager.py:329, :516, :548`, `cutout.py:568, :714`; N5 `test_pl2000_verification.py:456-457,
  :474, :482`; N6 `download_cmd.py:86`, `manager.py:211`, `cutout.py:572, :705`; N7
  `download_cmd.py:1324-1326`; N8 `sidecar.py:112`, `registry.py:77`; N9 `cutout.py:482, :581`;
  H1 `gugik.py:599-602` — trafiaja w opisany kod. **Jedyny chybiony:** K6
  `providers/cuzk/client.py:37-38` (RR-11; stale sa w liniach 36-37).
- Zadne zachowanie z KNOWN-BUGS nie jest opisane jako zamierzone; ID zgodne z opisami (sprawdzone
  wszystkie wzmianki "znany blad <ID>" w dokumentach biezacych i docstringach). Rozjazdy tresci:
  S4 zawyzony (RR-3 — ten sam zawyzony opis jest w `KNOWN-BUGS.md`); N9 w dokumentach
  ("przy jawnym `estimate_pl_cutout_bytes`", `PROGRESS.md:193`) precyzyjniejszy niz
  w KNOWN-BUGS ("przy typowym uzyciu") i zgodny z kodem (CLI liczy `cutout.estimated_bytes`,
  `download_cmd.py:1034`) i z L7 — uwaga do KNOWN-BUGS, nie do fali.

### 4. Odsylacze do raportow — PASS (z RR-12)

`grep` dokumentow biezacych i kodu: katalog `docs/research/2026-09-29-live-e2e-i-audyt-docs/`
przywolany w ARCHITECTURE:10, CHANGELOG:723, DECISIONS:449, :705, :913, :1264, PROGRESS:102,
:170, :922, :996; nazwy plikow: `KNOWN-BUGS.md`, `DOCS-FIX-REPORT.md`,
`hydrograf-uwagi-migracyjne.md`, `L1..L7-*-report.md`, `D1-*`, `D2-*` — **wszystkie z listy**.
W dodanych liniach zero `.superpowers/`, `/tmp/`, `e2e-data/` (istniejace wzmianki tylko
w historycznych, datowanych sekcjach PROGRESS/ADR — poza zakresem). Kotwice README
(`#znane-problemy-070-dev`, `docs/PROGRESS.md#znane-bledy-testy-na-zywo-2026-09-29`) zgodne
z naglowkami (`README.md:198`, `PROGRESS.md:165`). Nieprecyzyjne wskazanie "surowe body
w raportach L3, L4, L5" — RR-12.

### 5. Liczby — PASS (poza RR-2, RR-10)

Sprawdzone (zrodlo -> wynik), ponad 40:
1861 passed / 8 deselected (pomiar); 92,92 % (pomiar `--cov`, `COVERAGE_FILE` poza repo);
84 arkusze 1 m k+0,5 (L2 S21: 76 + 8); 7721 B / 554 B (surowe `L3 gfi/*.body`: 7721, 8887,
8911, 554 B); 1836/2394 arkuszy, 688/732 z danymi, 36,4 s / 108,7 s, 1037-1039 MiB, 9 fd,
6,58x przy 63 % nodata, 1206/1398 MiB, 103,2 x 76,6 km, 22 z 688 i ~3,7 km, 6,7-6,9 ms/arkusz,
13-21 % (L7); 2,3 m / 0,38 m, (-2,26; +0,61) / (+0,38; -0,03), Cheb 5,00 / Cieszyn 1,15 /
Praga 3,15 / Karkonosze 2,72 / Brno 0,98 m, 1,25 / 4,92 m, ~8 Mpx, ~5,5 x 5,5 km, 22 Mpx
(1800 x 12300, 3 kafle), 293 MiB, 5000 x 2500 i 3000 x 3000 = HTTP 500, 2,0004 m, 93 % nodata
kafla 302_5550, faza (0,4; 1,88), ~200 / ~118 m, 310-350 m, -0,19..+0,14 m, -0,55 m (Olza),
5,2 km², +0,11..+0,15 m (L4 U7: 0,111-0,144; EPSG:5202 ma nachylenie 0,026" po szerokosci —
"rosnaco S->N" potwierdzone); 1,1-4,9 m (KNOWN-BUGS; pomiar 1,13-4,87); 21 % i 4,2 m (L2 S16,
BUG-L2-1); 5,2 m (L3 #10); 426 km (L1); 209 km (L1 — tylko przyklady z bboxem, RR-10);
13-50 %, 39 z ~294 (L5), ~50 % (L1), 72/72, Hel 4/4 (L3), Karkonosze 3/3 (L4); 82 % (L6:
81,6 %); 766 px, 0,59-0,88 px i 9 z 9 (L1 F1), 0,55-0,70 px (L2 S24); 2 z 12 (L4 U1); 48 arkuszy
(L2 S23 — patrz RR-9); 9 cm i 1 px (L2 pkt 5-6); 1/12 i 0/12 (L2 S26); 18 vs 6, 12 vs 8,
2,69 z 8,865 km (L5); 20 mln i 14,3 mln px (L2, L3); 0,13-3,3 mm, 2,76 mm / 0,25 m, 0,31-0,33 mm /
18 mm, 0,004 mm, 0,13 m (L2 pkt 4.3); 2,97 mm / 0,15 m (L3); 0,17 m (L5 G: 0,165); 9 godel
i 16 zamiast 4 (pomiar; 16 arkuszy 1:10000 z roznych regionow — zawsze 9); 39 nazw `__all__` (pomiar;
lista PRD 5 == `__all__`, IMPLEMENTATION_PROMPT 5 == `__all__` bez `__version__`); 32 pliki
testowe (pomiar); PASS/UWAGA/FAIL raportow w PROGRESS:106-114 (L1 8/5/7, L2 21/5/6, L3 7/4/3,
L4 10/4/4, L5 7/5/2, L7 4; L6 9/1 — wyliczone z sekcji raportu, spojne); 220 niewypchnietych
(pomiar, = 208 + 12).

### 6. Spojnosc miedzy dokumentami — UWAGI (RR-1, RR-2, RR-4, RR-5, RR-6)

- S2 (tryb listy, `--workers 1` vs `> 1`): CLAUDE.md:355-361, README.md:226-231,
  ARCHITECTURE.md:426-437, SCOPE.md:393-397, PROGRESS.md:181 i :1070-1079 — spojne;
  obejscie `--target-crs` bez zastrzezenia "tylko nmt/1992" (RR-6).
- S3 (przycinanie `auto`): spojne w CLAUDE/README/ARCH/SCOPE/PROGRESS/DECISIONS/docstringu, ale
  trzy dokumenty dodaja sprzeczne "`auto` == `pl`" (RR-1); tryb `--geometry` bez `--target-crs`
  nieobjety (RR-5).
- N4 (`missing_sheets` przy pominieciu, `parent_request`): spojne (CLAUDE.md:344-349,
  README.md:149-150, :191, ARCH:45-49, :372-373, :421-422, SCOPE.md:384-392, docstringi
  `cutout.py:548-550, :673-677`).
- R5 w wycinku vs brak w trybie listy: spojne (CLAUDE.md:322-329, README.md:66-72, ARCH 4.3 krok 4,
  SCOPE.md:374-383, `--target-crs` help, ADR-027).
- K6: spojne, ale wszedzie z niedokladna regula "~5,5 x 5,5 km ... takze po kafelkowaniu" (RR-4).
- K2: "1-5 m" spojne w CLAUDE/README/SCOPE/ARCH 1 i 4.4/PROGRESS; wyjatek ARCH 4.3 krok 6 (RR-2).
- K1: spojne (CLAUDE.md:158, README.md:50, :207-210, :291, SCOPE.md:163-164, PRD.md:237-240,
  ARCH 4.7, ADR-021 errata, PROGRESS, `--product` help); "209 km" uogolnione (RR-10).
- N6: spojne (CLAUDE.md:369, ARCH:395-401, IMPLEMENTATION_PROMPT:281, ADR-019, PROGRESS:23);
  drobna nieprecyzyjnosc ADR-019 (RR-13).

### 7. Hydrograf — PASS (z RR-15)

Sprawdzone w repo Hydrografu (tylko odczyt): `backend/requirements.txt:52` (`@v0.6.1`);
`docs/PROGRESS.md:55` (`/data/nmt/nmt_5m/`, 3233 arkusze, 4,5 GB), `:1383-1386`, `:1388-1391`
(`archive/nmt_5m`); `backend/scripts/download_dem.py:297` (`default="../data/nmt/"`);
`backend/core/config.py:55` (`dem_dir = "/data/nmt"`); `backend/scripts/bootstrap.py:1079`
(`nmt_dir.glob("*.asc")` przy zapisie przez `DownloadManager(output_dir=cache/nmt)` do
hierarchii — nierekurencyjny glob faktycznie nic nie znajdzie); `backend/scripts/download_landcover.py:342`
(`from kartograf.providers.bdot10k import ...`); `docs/integrations/KARTOGRAF.md:211, :298,
:335, :414-423, :439-448, :450-459 ("gugik.py ok. :81-85"), :530-547`; `docs/DECISIONS.md:1236,
:1239-1241, :1248-1249`; `docs/SCOPE.md:431` (PIG); `README.md:96`,
`docs/IMPLEMENTATION_PROMPT.md:47`, `docs/CROSS_PROJECT_ANALYSIS.md:297` -> nieistniejacy
`KARTOGRAF_INTEGRATION.md` (`git status`: `D docs/KARTOGRAF_INTEGRATION.md`, `?? docs/integrations/`);
cache: `cache/nmt/nmt_1m` = 523 pliki z `cellsize 5.00`, `nmt_5m` = 1454. Po stronie Kartografa:
podwojne `nmt` (`DownloadManager(output_dir="/data/nmt", resolution="5m").storage.get_path(...)`
-> `/data/nmt/nmt/pl_1992_5m_evrf2007/...`), importy Hydrografu dzialaja w 0.7.0, warstwy 1 m
EVRF2007 = 2026/2025/2024/2023iStarsze, 5 m bez zmian, `create_nmt_provider(session=, cache=)` —
wszystko zgodne. Drobna nieprecyzyjnosc B4 — RR-15.

### 8. Forma — PASS

- README: wszystkie dodane linie z diakrytykami (jedyny ASCII to cytat nazwy naglowka PROGRESS
  w tekscie odsylacza — celowe). SCOPE (dopiski) z diakrytykami.
- Pliki ASCII (CLAUDE, ARCHITECTURE, CHANGELOG, DECISIONS, PROGRESS, DEVELOPMENT_STANDARDS,
  IMPLEMENTATION_PROMPT, kod): zero nowych liter z diakrytykami (poza docstringiem
  `sheet_parser.py`, ktory juz byl z diakrytykami, i istniejacym slowem "punktow" w PROGRESS:10).
- `docs/DECISIONS.md` CRLF: BASE 1144 CRLF / 0 LF, HEAD 1316 CRLF / 0 LF; wszystkie 175 dodanych
  linii z `\r`. Zadnych zmian konca pliku ("No newline" = 0).
- Pozostalosci robocze: w dodanych liniach zero `TODO`, "kontroler", `/tmp`; "agentow" 3 razy
  w dzienniku sesji PROGRESS (`:95`, `:161`, `:1065` — opis metody i mozliwej przyczyny zerwan,
  wymagany briefem fali; wczesniejsze wpisy sesyjne PROGRESS uzywaja tego slownictwa) — nie
  traktuje tego jako pozostalosci.

### 9. Brama — PASS

- `.venv/bin/python -m pytest tests/ -q -m "not live" -p no:cacheprovider` -> **1861 passed,
  8 deselected** (27,4 s); z `--cov` (plik `.coverage` poza repo) -> 92,92 %.
- `.venv/bin/python -m ruff check kartograf/ tests/` -> `All checks passed!`;
  `.venv/bin/python -m ruff format --check kartograf/ tests/` -> `87 files already formatted`.
- mypy: BASE (`git archive 152c31e | tar -x -C "$(mktemp -d)"`, uruchomienie
  `/home/claude-agent/workspace/Kartograf/.venv/bin/python -m mypy kartograf/` z tego katalogu) —
  `Found 32 errors in 9 files`; HEAD — `Found 32 errors in 9 files`;
  `grep -E "error:" | sed -E 's/:[0-9]+: /: /' | sort` -> 32 = 32, `diff` **pusty**.

---

## Tabela znalezisk

| ID | Waga | plik:linia (HEAD) | Temat |
|---|---|---|---|
| RR-1 | BLOKUJACE | CLAUDE.md:311-313; SCOPE.md:423-425; ARCHITECTURE.md:877-881 | "`auto` == `pl`" na granicach z krajami spoza rejestru vs przycinanie S3 |
| RR-2 | WAZNE | ARCHITECTURE.md:721-723 | K2: "ok. 1,1-2,3 m przy granicy" — liczba spoza raportow, zanizona |
| RR-3 | WAZNE | DECISIONS.md:412-414; PROGRESS.md:183, :1090-1092 | S4: "NMPT nie pobiera sie wcale" — falsz w ogolnosci |
| RR-4 | DROBNE | README.md:223-225; CLAUDE.md:269-271; SCOPE.md:367-369; ARCHITECTURE.md:846-848; PROGRESS.md:179, :1053-1055 | K6: regula "~5,5 x 5,5 km ... takze po kafelkowaniu" |
| RR-5 | DROBNE | CLAUDE.md:306-310; SCOPE.md:418-421; ARCHITECTURE.md:869-875; DECISIONS.md:726-728 | S3 nie dotyczy PL `--geometry` bez `--target-crs` |
| RR-6 | DROBNE | README.md:229-231; CLAUDE.md:360-361; SCOPE.md:397 | obejscie S2 (`--target-crs`) tylko dla `--product nmt`, system 1992 |
| RR-7 | DROBNE | ARCHITECTURE.md:51-53, :74-75, :393-395 | precyzja: polityka transformacji, "regula (3) wybiera", S1 "kazde nowym polaczeniem" |
| RR-8 | DROBNE | DECISIONS.md:1265-1267; ARCHITECTURE.md:579-582 | "0 pikseli rozbieznych" uogolnione (Cieszyn A2, PL-UA/BY/RU) |
| RR-9 | DROBNE | ARCHITECTURE.md:625-626 | "48 arkuszy ... pod Wegrowem i Leba" |
| RR-10 | DROBNE | PRD.md:239-240; PROGRESS.md:1004-1005 | "209 km" uogolnione na przyklady z godlem (~370 km) |
| RR-11 | DROBNE | PROGRESS.md:1055 | `client.py:37-38` -> `:36-37` |
| RR-12 | DROBNE | PROGRESS.md:146 | "surowe body w raportach L3, L4, L5" |
| RR-13 | DROBNE | DECISIONS.md:379 | `.kartograf_cache.db` tworzy tez `kartograf cache ...` |
| RR-14 | DROBNE | PROGRESS.md:1009-1021 (brak wpisu) | falszywy komunikat runtime `download_cmd.py:1643-1644` nieodnotowany w backlogu |
| RR-15 | DROBNE | hydrograf-uwagi-migracyjne.md:123-125 | `no_coverage` to podzbior `failed`, nie "osobno" |

### RR-1 — BLOKUJACE — "`auto` == `pl`" przeczy przycinaniu S3

- **Cytaty:**
  - `CLAUDE.md:311-313`: "Na granicach z krajami spoza rejestru (DE, SK, UA, BY, LT, RU) `auto` ==
    `pl` bez komunikatu (poza pasem wewnatrz prostokata CZ, np. Nysa ponizej 51,06°N)."
  - `docs/SCOPE.md:423-425`: "Na granicach z krajami spoza rejestru (DE, SK, UA, BY, LT, RU) auto działa
    jak --country pl, bez komunikatu (poza pasem wewnątrz prostokąta CZ)"
  - `docs/ARCHITECTURE.md:877-881`: "... wiec na granicach z DE, SK, UA, BY, LT i RU `auto` dziala jak
    `pl`, bez komunikatu — poza pasem wewnatrz prostokata CZ (Saksonia ponizej 51,06°N, pas Bogatyni,
    Opolszczyzna), gdzie CUZK dostaje zapytanie ..."
- **Dowod:** we wszystkich trzech miejscach zdanie wczesniej stoi, ze `auto` przycina czesc zadania do
  prostokata kraju, a jawne `--country pl` nie przycina (CLAUDE.md:306-310 z przykladem "na zachod od
  14,07°E" — to granica PL-DE). Kod: `_country_bbox` (`kartograf/cli/download_cmd.py:317-331` —
  `if not auto: return bbox`, dalej przyciecie do `extent_wgs84`), `_dispatch_area` (`:476-478`).
  L5 I/J (Osinow Dolny, granica PL-DE): `auto` — lista 4 arkusze, wycinek 6,175 km (2,69 km zadania
  pominiete, inna nazwa pliku); `--country pl` — lista 6, wycinek 8,865 km. Krawedzie prostokata PL
  (14,07°E, 49,00°N, 24,20°E) leza przy granicach DE, SK i UA, wiec bbox przygraniczny wychodzacy za nie
  daje pod `auto` inny wynik niz `--country pl`. Dodatkowo: "Opolszczyzna" nie lezy na granicy
  z krajem spoza rejestru (to przyklad N2 dla obszaru PL w prostokacie CZ), a "Nysa ponizej 51,06°N"
  czyta sie jak miasto Nysa (pogranicze CZ) — chodzi o Nyse Luzycka.
- **Poprawka:**
  - CLAUDE.md:311-313: "Na granicach z krajami spoza rejestru (DE, SK, UA, BY, LT, RU) `auto` odpytuje
    tylko PL, bez komunikatu — ale z przycieciem z pkt (4), wiec nie zawsze jak `--country pl`
    (np. Osinow Dolny, na zachod od 14,07°E); wyjatek: pas wewnatrz prostokata CZ (Nysa Luzycka
    ponizej 51,06°N, pas Bogatyni), gdzie dochodzi zapytanie do CUZK (N2)."
  - SCOPE.md:423-425: "Na granicach z krajami spoza rejestru (DE, SK, UA, BY, LT, RU) auto odpytuje tylko
    PL, bez komunikatu (z przycięciem jak wyżej, więc nie zawsze jak --country pl; poza pasem wewnątrz
    prostokąta CZ)".
  - ARCHITECTURE.md:877-881: "... `auto` odpytuje tylko PL, bez komunikatu (z przycieciem opisanym
    wyzej, wiec nie zawsze jak `--country pl`) — poza pasem wewnatrz prostokata CZ (Saksonia i Nysa
    Luzycka ponizej 51,06°N, pas Bogatyni), gdzie CUZK dostaje zapytanie i oddaje raster w 100 % nodata
    z kodem 0, bez komunikatu (N2; tak samo dla obszarow PL w prostokacie CZ, np. Opolszczyzny)."

### RR-2 — WAZNE — K2: "ok. 1,1-2,3 m przy granicy"

- **Cytat:** `docs/ARCHITECTURE.md:721-723`: "tresc wycinka w EPSG:5514 jest przesunieta wzgledem czeskiej
  o ok. 1,1-2,3 m przy granicy (znany blad K2)".
- **Dowod:** zakresu nie ma w raportach (L2 BUG-L2-4: Cieszyn 1,15 m, Klodzko 1,96 m; L4: roznica
  1622-4829 Karkonosze 2,72, Kudowa/Nachod 2,15, Cieszyn 1,15 m; L4 S6 na zywo Karkonosze 2,3 m).
  Pomiar re-review (pyproj offline, `TransformerGroup("EPSG:4156", "EPSG:4258")`, operacje "S-JTSK to
  ETRS89 (1)" i "(3)", odleglosc GRS80): Jaworzynka 1,13; Cieszyn 1,15; Raciborz 1,22; Glucholazy 1,59;
  Miedzylesie 1,64; Kudowa 2,15; Karkonosze 2,73; Swieradow 3,09; Bogatynia/Hradek 3,39 m (Cheb 4,87 m).
  "2,3 m" zaniza zachodni odcinek granicy (Izery, Worek Turoszowski) o ~1 m — istotne dla R6.
- **Poprawka:** "o ok. 1,1-3,4 m wzdluz granicy PL-CZ (roznica EPSG:1622 - EPSG:4829: Cieszyn 1,15 m,
  Kudowa 2,15 m, Karkonosze 2,72 m — na zywo 2,3 m wzgledem DMR 5G, rejon Bogatyni ~3,4 m)".
- **Pobocznie (opcjonalnie):** PROGRESS.md:1011-1012 (i KNOWN-BUGS) "1,1-4,9 m" vs DECISIONS.md:919
  "Cheb (`302_5550`) 5,00 m" (L4) — ujednolicic na "1,1-5,0 m" albo "1-5 m".

### RR-3 — WAZNE — S4: "NMPT nie pobiera sie wcale"

- **Cytaty:** `docs/DECISIONS.md:412-414` "gdy GetCapabilities zawiedzie, NMPT nie pobiera sie wcale
  (znany blad S4)"; `docs/PROGRESS.md:183` "bez GetCapabilities NMPT sie nie pobiera";
  `docs/PROGRESS.md:1090-1092` "gdy GetCapabilities zawiedzie, NMPT nie pobiera sie wcale ("brak
  pokrycia niepewny")". (Ten sam opis w `KNOWN-BUGS.md`, S4.)
- **Dowod:** `_get_opendata_url` zwraca URL z pierwszej warstwy, ktora go ma (`providers/pl/gugik.py:571-622`);
  zaszyta lista NMPT (`gugik_nmpt.py:83-86`: 2025, 2024, 2023, 2022iStarsze) zawiera dwie istniejace
  warstwy (L1 BUG-L1-9: GetCapabilities = 2026, 2025, 2024, 2023iStarsze). Symulacja offline
  (sesja-atrapa: 2023/2022iStarsze -> `LayerNotDefined`, `_fetch_wms_layers` -> `ConnectionError`):
  arkusz w 2025 -> URL, w 2024 -> URL, tylko w 2023iStarsze albo tylko w 2026 -> `DownloadError`
  "2 z 4 warstw nie odpowiedzialo ... brak pokrycia niepewny". L1 zaobserwowal porazke dla arkusza
  z edycja 2023 (M-34-76-A-a-1-1).
- **Poprawka (DECISIONS, PROGRESS x2, takze KNOWN-BUGS przed skopiowaniem):** "gdy GetCapabilities
  zawiedzie, nie pobieraja sie arkusze NMPT spoza warstw 2025/2024 (najnowsza edycja w 2023iStarsze
  albo 2026 — "brak pokrycia niepewny")".

### RR-4 — DROBNE — K6: regula "~5,5 x 5,5 km ... takze po kafelkowaniu"

- **Cytat:** `README.md:223-225` "obszar większy niż ok. 5,5 × 5,5 km nie przechodzi, także po
  kafelkowaniu" (analogicznie CLAUDE.md:269-271, SCOPE.md:367-369, ARCHITECTURE.md:846-848,
  PROGRESS.md:179, :1053-1055).
- **Dowod:** kafelkowanie dopiero powyzej 15000 x 4100 px, rownymi czesciami
  (`providers/cuzk/client.py:139-147`, `_tile_grid` `:257-300`); limit dotyczy pikseli POJEDYNCZEGO
  zapytania (L4 sondy: 2500x2500 i 3000x2500 OK, 4096x2047 = 500). Stad: pas 3,6 x 24,6 km przeszedl
  (L4 S3b, 3 kafle po 7,38 Mpx); 5 km E-W x 10 km N-S (2500 x 5000 px -> 2 kafle 2500 x 2500) przejdzie
  (wniosek z kodu i sond L4); 10 km E-W x 5 km N-S (5000 x 2500 px, bez kafelkowania, 12,5 Mpx) — HTTP 500.
- **Poprawka:** "realnie serwer odrzuca (HTTP 500) zapytania > ~8 Mpx, a kafle tnie dopiero powyzej
  15000 x 4100 px — obszar 2 m zblizony do kwadratu wiekszy niz ~5,5 x 5,5 km (albo np. 10 x 5 km
  wydluzony W-E) nie przechodzi (K6)".

### RR-5 — DROBNE — S3 a `--geometry` bez `--target-crs`

- **Cytat:** `CLAUDE.md:306-310` (w punkcie "Dla `--bbox`/`--geometry` znaczy to"): "(4) czesc zadania
  kazdego kraju jest przycinana do jego prostokata — obszar poza WSZYSTKIMI prostokatami (...) znika
  bez komunikatu"; tak samo SCOPE.md:418-421, ARCHITECTURE.md:869-875, DECISIONS.md:726-728.
- **Dowod:** `_download_pl_geometry` (`download_cmd.py:1742-1748`, `:1760-1763`) — bez `--target-crs`
  arkusze PL wyznacza sama geometria, przyciety `bbox` nie jest uzywany; nic nie "znika" (przyciecie
  dziala na czesc CZ i na wycinek PL).
- **Poprawka:** dopisac "(w trybie `--geometry` bez `--target-crs` arkusze PL wyznacza sama geometria —
  przyciecie dotyczy tam tylko czesci CZ)".

### RR-6 — DROBNE — obejscie S2 tylko dla NMT, system 1992

- **Cytat:** `README.md:229-231` "Obejście: `--target-crs EPSG:2180` (arkusze bez danych stają się nodata
  z ostrzeżeniem `Warning:`)"; CLAUDE.md:360-361 "Przy morzu i na granicach uzywaj `--target-crs
  EPSG:2180`"; SCOPE.md:397 "na morzu i na granicach: --target-crs EPSG:2180".
- **Dowod:** tryb listy (i S2) dotyczy tez nmpt/orto, a `_resolve_pl_sentinels`
  (`download_cmd.py:152-167`) odrzuca `--target-crs` z `--product nmpt|orto|laz` i z `--system 2000`.
- **Poprawka:** dopisac "(tylko `--product nmt`, system 1992)".

### RR-7 — DROBNE — ARCHITECTURE: precyzja sekcji 1 i 4.1

- `ARCHITECTURE.md:51-53` "Transformacje, ktore przesuwaja TRESC rastra albo opuszczaja uklady czeskie
  (EPSG:5514/3045), przechodza wylacznie przez `kartograf/transform/crs.py`." — `_bbox_to_wgs84`
  (`download_cmd.py:233-257`) liczy domyslnym transformerem pyproj takze bbox w EPSG:5514/3045
  (rozpoznanie kraju `:270`, przyciecie galezi CZ w `_country_bbox` `:320-331`), a tor LAZ z plikiem
  geometrii w ukladzie czeskim — `get_overall_bbox(..., target_crs="EPSG:2180")` (`:1188-1190`).
  Poprawka: "... przechodza przez `transform/crs.py` — poza obwiednia do rozpoznania kraju/przyciecia
  w WGS84 (`_bbox_to_wgs84`) i obwiednia pliku geometrii w torze LAZ".
- `ARCHITECTURE.md:74-75` "Regula (3) wybiera najdokladniejsza operacje" — regula (3) filtruje, wybor to
  `min(candidates, key=accuracy)` (`transform/crs.py:236`). Poprawka: "Sposrod operacji, ktore
  przeszly reguly (1)-(3), wybierana jest najdokladniejsza (`min` po `accuracy`), bez sprawdzenia jej
  obszaru uzycia".
- `ARCHITECTURE.md:393-395` "bez wstrzyknietej sesji kazde idzie nowym polaczeniem (znany blad S1)" —
  nowa `requests.Session` jest na kazde wywolanie `_get_opendata_url`, czyli na arkusz
  (`gugik.py:541`); zapytania warstw jednego arkusza dziela sesje (docstring `gugik.py:503-505`,
  KNOWN-BUGS S1 "nowe polaczenie per arkusz"). Poprawka: "bez wstrzyknietej sesji kazdy arkusz
  dostaje nowa sesje (nowe polaczenie)".

### RR-8 — DROBNE — "0 pikseli rozbieznych" uogolnione

- `DECISIONS.md:1265-1267`: "Cel EPSG:2180: 0 pikseli rozbieznych z arkuszem zawierajacym srodek piksela
  (1 m i 5 m, bbox calkowity i ulamkowy, morze i pogranicza)". L4 S1b (Cieszyn A2, pogranicze):
  "0 rozbieznosci poza zasiegiem 2 arkuszy spoza siatki (9 652 px w ich zasiegu)"; L1 F1 (Krakow):
  sasiedni piksel, 766 px nodata. Punkt "Siatka (R1)" tego uzupelnienia wspomina S5 tylko dla Krakowa.
  Poprawka: dopisac "— poza arkuszami spoza siatki wiekszosci (S5: Krakow 2022, Cieszyn 2 z 12)".
- `ARCHITECTURE.md:579-582`: "Leba, Hel, Slubice, Zgorzelec, trojstyk PL-CZ-DE, Osinow, PL-UA/BY/RU —
  ... 0 pikseli rozbieznych z arkuszami" — L6 (UA/BY/RU) nie porownywal pikseli 1:1 (tylko polozenie
  nodata; UA — niezalezny `merge` = 0 pikseli z danymi). Poprawka: "(0 pikseli rozbieznych: Leba, Hel,
  pogranicze PL-DE; PL-UA/BY/RU — sprawdzone polozenie nodata)".

### RR-9 — DROBNE — "48 arkuszy ... pod Wegrowem i Leba"

- `ARCHITECTURE.md:625-626`: "takze 48 arkuszy kampanii 2022/2024/2025 pod Wegrowem i Leba". 48 arkuszy
  to obszar L2 (okolice Wegrowa, L2 S23); Leba to osobne arkusze L3 (kampanie 2025/2023, faza 5k+2,5 —
  L3 pkt 1 i "Zachowanie" pkt 4). PROGRESS.md:132-133 ma to poprawnie. Poprawka: "48 arkuszy kampanii
  2022/2024/2025 pod Wegrowem (L2) oraz arkusze w Lebie (L3)".

### RR-10 — DROBNE — "209 km" uogolnione

- `PRD.md:239-240` "(przykład wyżej szuka ok. 209 km od podanego obszaru)"; `PROGRESS.md:1004-1005`
  "przyklady LAZ z dokumentacji szukaja ~209 km dalej". L1 BUG-L1-1 liczy 209 km dla przykladow
  z bboxem `530000,382000,533000,386000` (BASE: CLAUDE.md:160, PRD.md:225). Przyklady z godlem
  (`N-34-130-D-d-2-4 --product laz`: CLAUDE.md:159-160, PRD.md:230-231) szukaja ~370 km dalej
  (pomiar: srodek arkusza w EPSG:2180 (771037, 509635), miejsce transponowane sqrt(2)*|E-N| = 369,7 km;
  dla bboxa 208,6 km). Poprawka: "(przyklad z bboxem 530000,382000,... szuka ok. 209 km, a z godlem
  N-34-130-D-d-2-4 — ok. 370 km od podanego obszaru)".

### RR-11 — DROBNE — chybiony `plik:linia`

- `PROGRESS.md:1055` "`providers/cuzk/client.py:37-38` (`MAX_EXPORT_WIDTH/HEIGHT`)" — stale sa
  w `client.py:36-37` (`:38` to `QUERY_PAGE_SIZE`; plik nie zmienial sie od BASE — blad odziedziczony
  po L4). Poprawka: "`providers/cuzk/client.py:36-37`".

### RR-12 — DROBNE — "surowe body w raportach"

- `PROGRESS.md:146` "(surowe body w raportach L3, L4, L5)" — surowe odpowiedzi trafia wylacznie do
  `gfi/` (kopia `L3-morze/gfi/`: 22 pliki, 7721/8887/8911/554 B); body L4/L5 zostaja w `e2e-data/`,
  raporty L4/L5 maja opis (rozmiar, md5), nie body. Poprawka: "(surowe body: `gfi/` w katalogu
  raportow — probki L3; opis odpowiedzi strony CZ i DE: L4 U12, L5 pkt (j))".

### RR-13 — DROBNE — ADR-019: kto tworzy `.kartograf_cache.db`

- `DECISIONS.md:379` "a `.kartograf_cache.db` tworzy w CLI tylko tor CZ (indeks SM5)" — plik zaklada
  tez `kartograf cache stats|clear|path` (`cli/cache_cmd.py:30` `MetadataCache()` ->
  `sqlite3.connect` w CWD, `cache/metadata.py:73-79`). Poprawka: "a z torow pobierania
  `.kartograf_cache.db` tworzy w CLI tylko tor CZ (indeks SM5)".

### RR-14 — DROBNE — falszywy komunikat runtime poza backlogiem

- `kartograf/cli/download_cmd.py:1643-1644` (godlo CZ + `--target-crs`): "tryb godlowy dostarcza dane
  natywne 1:1" — falsz dla TM33 (warp 5514 -> 3045, K2; D1 ID 2). Brief fali pozwalal zmieniac tylko
  docstringi/komentarze/pomoc, wiec slusznie zostal — ale jest tylko w "Watpliwosciach"
  `DOCS-FIX-REPORT.md`, nie w `PROGRESS.md` "Do naprawy". Poprawka: w checkboxie K2 (`PROGRESS.md:1009-1021`)
  dopisac "komunikat `cli/download_cmd.py:1643-1644` ('tryb godlowy dostarcza dane natywne 1:1')
  falszywy dla TM33 — poprawic razem z K2".

### RR-15 — DROBNE — uwagi dla Hydrografa, B4

- `hydrograf-uwagi-migracyjne.md:123-125` "porazki zbierane w `manager.last_result.failed`, braki danych
  osobno w `last_result.no_coverage`" — `no_coverage` to podzbior `failed` (`download/manager.py:72-74`
  "Subset of ``failed``"; `cutout.py:595-598`). Poprawka: "braki danych (`NoCoverageError`) sa
  w `failed` i dodatkowo w `last_result.no_coverage` (podzbior `failed`)".

---

## Sprawdzone twierdzenia (plik:linia HEAD -> OK + dowod)

**CLAUDE.md** (wszystkie nowe/zmienione zdania)
- :158 K1 "setki km" -> OK (L1: 426 km; przyklady 209/370 km).
- :168 kafel 302_5550 ~93 % nodata -> OK (L4 U9: 93,4 %).
- :171 bez `--vertical-crs` PL EVRF2007, CZ Bpv -> OK (`download_cmd.py:171`, `:1625`; L4 U3).
- :259-263 bbox 4326 = tylko jego arkusze, 2180 -> 9 godel -> OK (pomiar 1/9; 16 arkuszy — zawsze 9).
- :266-271 limit deklarowany 15000x4100, realnie ~8 Mpx (K6) -> OK (`client.py:36-37`, L4 BUG-L4-2; RR-4).
- :278-283 operacja EPSG:4829 (Slowacja) w CZ, 1-5 m (K2) -> OK (pyproj: 4829 "Slovakia" 0,5 m, 1622
  "Czechia" 1,0 m; przypiete 5514->3045 i 2180->5514 zawieraja "S-JTSK to ETRS89 (3)"; L4).
- :283-285 godlo wyznacza zasieg; PL i SM5 1:1, TM33 warp -> OK (`providers/cuzk/dmr.py:520-522`, L4 U11).
- :286-294 prostokat CZ, Saksonia/Bogatynia, N2 kod 0 -> OK (registry `BBox(12.09,48.55,18.86,51.06)`, L5 H).
- :295-310 (1)-(4), `Error:` poza prostokatami -> OK (`download_cmd.py:476-551`, L5 K); (4) — RR-5.
- :322-329 R5 dla CZ/DE/SK/UA/BY/LT/RU, `missing_sheets` != pelne nodata, PL-SK do 82 % -> OK
  (`cutout.py:594-613`, L3, L5, L6).
- :329-332 siatka 1 m k+0,5; 5 m rozne fazy S5 -> OK (L2 S21, L1 F1).
- :333-337 arkusz PL-2000 = blad, zostaje w cache PL-1992, remedium `--system 2000` -> dziecko (K4)
  -> OK (`cutout.py:287-312`, L2 S27-S28).
- :341-344 `--geometry` + 2180 bez sumy i zapasu -> OK (`cutout.py:256-279`).
- :344-349 `Skipped` bez sieci i bez `Warning:`, `skipped=True` z pustym `missing_sheets` (N4),
  `--force` = wszystkie arkusze -> OK (`download_cmd.py:1004-1007`, `cutout.py:567-568, :591-593, :713-714`, L2 S14).
- :355-361 tryb listy S2 -> OK (`download_cmd.py:861-921`, `:540-550`; L3 B3, L5 B1-B2, L6 BUG-1); RR-6.
- :362-369 lista znanych bledow -> OK ("ponow pobranie" = `cutout.py:607`; KNOWN-BUGS).

**README.md**
- :14-16, :50, :207-210, :291 K1 -> OK (L1). :58-63 `Info:` tylko na obszarze obu; Praga/Brno -> GUGiK;
  przed siecia tylko poza prostokatem PL; nmpt/orto -> etap 2; S3 -> OK (`download_cmd.py:494-507, :106-116`).
- :66-72 wycinek, nodata + `Warning:`, granica DE bez flagi = kod 1 -> OK (RR-6).
- :79-82 porazka jednego kraju -> kod 0 + `Warning:` -> OK (`download_cmd.py:540-550`).
- :84-85 `--bbox=` dla 5514 -> OK (argparse; L4 uzywal tej skladni).
- :149-157 pusta krotka przy `skipped` (N4), wyjatki, kroki -> OK (`cutout.py:568, :605-613`, `prepare` TransformError).
- :171-175 `download_sheets`/`expand_sheets`/`no_coverage` -> OK (`manager.py:425-479`, `DownloadResult`).
- :183 N8 -> OK (`sidecar.py:112`, `registry.py:77`). :187 `request` wycinka = obwiednia wyniku -> OK
  (`cutout.py:440-443`, `download_cmd.py:1569-1572`). :191 `parent_request` (wycinek + arkusze
  pobrane, LAZ, N4, biblioteka tylko z `parent_request=`) -> OK (`cutout.py:433-434, :589`, `manager.py:329`).
- :192, :198-235 (Znane problemy: K2, K3/K4, K5, K6, S2, S1) -> OK (L1, L2, L4, KNOWN-BUGS; RR-4, RR-6).
- :252-262 S5, `Skipped`, `--force`, dysk, `Info:` >= 1 GiB, brak limitu -> OK (`download_cmd.py:1004-1041`, `cutout.py:515-532`).
- :263-265, :278, :285 EVRF2007/NMPT/orto: WCS z biblioteki, CLI `--bbox` = arkusze -> OK (`_download_pl_bbox`).
- :270 DMR 4G takze bbox -> OK (`registry` `cz.cuzk.dmr4g`). :273, :286, :291 K2/K6/K5/K4/K1 -> OK.
- :427-429 `pip install -e ".[dev]"` -> OK (`pyproject.toml:51`). :445, :464 8 `live`, 1861, 92,9 % -> OK (pomiar).

**docs/ARCHITECTURE.md**
- :6-11, :45-49 (N4), :80-89 (R6), :175 (`prune_empty_dirs`), :219 (pusty wymiar -> `ValidationError`,
  pomiar), :243 (N8), :247 (fallback `CUZK_NODATA` tylko bbox, `download_cmd.py:1575`), :248 (`request`,
  brak URL/daty, LAZ `extra.url`), :272-275 (`"extra": {}` — `sidecar.py:124`), :364-373 (3.4; kod
  `_resolve_cz_geometry_bbox`/`_geometry_envelope`), :386-388 (zera wiodace — pomiar
  `M-33-036-...` vs `M-33-36-...` -> dwie sciezki), :395-401 (N6; `create_nmt_provider(cache=)`
  w sygnaturze), :404-407 (ASC bez CRS, 0,4 s — L1), :421-437 (S2), :498-504 (storage niewalidowana;
  Osinow/Slubice — L5), :530-533 (L7), :550-560 (K3; 21 %, 4,2 m — L2), :564-571 (7721 B, `LayerNotDefined` — L3),
  :596-610 (S1, K4 — L3, L4, L2), :624-640 (siatki, S5 — L1, L2, L4; RR-9), :660-663 (zakladka 9 cm — L2),
  :664-670 (deskryptory — L7),
  :711-720 (tolerance/XSCALE — L2), :742-747 (N9, L7), :818-824 (TM33 nie 1:1, faza (0,4; 1,88) — L4),
  :839-850 (K6, N3 — L4; RR-4), :869-877 (S3, `Error:` — `download_cmd.py:480-484`), :882-896 (kod 0
  pod auto, `--resolution 1m`, pion, styk — L4, L5), :904-911 (K1, N7 — L1), :1008, :1011, :1014 (indeks ADR) -> OK.

**docs/SCOPE.md**: :6, :64, :81-85 (16 zamiast 4 — pomiar), :97, :104-105, :130, :147-148, :163-164,
:244, :295-296, :315-319, :358-362, :366-370 (RR-4), :376-383, :384-392, :393-397 (RR-6), :405-411,
:418-423 (RR-1, RR-5), :426-438, :548-550, :564-567 -> OK.

**docs/PRD.md**: nota 3.7 (:26-30), :121-122, 3.4 (:237-240; RR-10), 5 (39 nazw == `__all__`, pomiar), 8 (:656-657) -> OK.

**docs/CHANGELOG.md [0.7.0]**: :11-43 (migracja — importy/`git show v0.6.1`/pomiary jak w pkt 2),
:125-130 (9 godel), :189 (Fixed poludnik 19°E istnieje), :229-233 (pomiar `get_raw_path` bez/z `uklad=`),
:302-311 (`_validate_cross_country`, `_pl_only_flags`), :314, :353 (`last_result` kasowane w
`manager.py:314, :399, :479`; `no_coverage`), :427, :529 (errata K2), :664 (84 arkusze), :701 (L3),
:721 -> OK.

**docs/DECISIONS.md**: :46, :58-64 (ADR-003), :193-202 (ADR-010; punkty na 19°E `sheet_parser.py:965-969`,
PL-2000 4 narozniki `parser_2000.py:707+`), :352-356 (ADR-018; domyslne 4/1 — pomiar sygnatur),
:376-381 (ADR-019; RR-13), :404-414 (ADR-020; RR-3), :435-449 (ADR-021 errata — L1, 426 km, mediana
0,000 m), :704-732 (ADR-023 errata), :912-947 (ADR-024 errata — L4, pyproj, `dmr.py:520-522`
`from_origin(min_x, max_y)` + `round`), :1119-1128 (ADR-026; `storage.py:115-121`), :1204-1206 (R5 + OGC),
:1263-1293 (ADR-027; RR-8) -> OK.

**docs/PROGRESS.md**: :7-28 statusy (K3/K4/S1, K3/S4, K5/K4, K1, K4/N8, N6, N5, S4, K2/K6, K3/K4/S1/S5/K2),
:86-163 (sesja; liczby jak w pkt 5), :165-194 (tabela 21 ID), :196-211 (brama — pomiar), :874-881 (pkt 4 A1-4),
:882-886 (pkt 5 -> K1), :919-969 (pkt 12 (a)-(l) — L1-L7), :970-987 (pkt 13-15), :989-1158 (Do naprawy;
RR-11, RR-14), :1204-1207 (A2-7; commit `2856f41` zmienil `logger.debug` -> `warning`), :1286-1288
(E2E kafelkowania — L4 S3b), :1306-1310 (`harmonize_dem` -> K2), :1338-1341 (`densify_pts=21`
w `corine.py:867, :888`, `soilgrids.py:272`) -> OK.

**docs/DEVELOPMENT_STANDARDS.md**: nota 2.2, 6.3 (`-m "not live"`, `addopts` bez `-m` — `pyproject.toml:73`),
7.1 (32 pliki testowe — pomiar; 1861 + 8), 9.4 (odstepstwo praktyki), 10.1, 11.1 (`NoCoverageError`,
`TransformError`/`TransformUnavailableError.remedy` — `crs.py:30-45`), 15 -> OK.

**docs/IMPLEMENTATION_PROMPT.md**: nota 4.2, 5 (== `__all__` bez `__version__`), 6.3, 9 (4/1 workery, N6,
mozaika wycinka, K1), 11 -> OK.

**Kod (docstringi/komentarze/pomoc)**: `__init__.py:1-26` (przyklad `download_pl_cutout` — poprawna
sygnatura), `_parser.py:69-80, :90-91, :122-128, :133-134, :146-148, :160-161, :174-177, :220`,
`download_cmd.py:195-208` (bariera `main` — `cli/commands.py:95-105`), `:294-296`, `:355-357`, `:852-859`,
`:1601`, `:1613-1618`, `sheet_parser.py:995-999`, `cutout.py:335-340, :548-550, :660-695`,
`manager.py:111-114, :146-151, :747-750, :779`, `storage.py:228-229`, `exceptions.py:1-7`,
`gugik.py:9-11, :62-63, :444-447, :499-514, :612-616, :629-632`, `descriptor.py:4-7, :23, :72`,
`registry.py:4-7`, `sidecar.py:4-7`, `mosaic.py:4-7, :99-111, :168-175` -> OK (wobec kodu i L1/L2/L4/L7).

---

## Poza zakresem / uwagi dla kontrolera

- Pliki K1/K2/K6 (nietykalne w tej fali) nadal maja komentarze sprzeczne ze znanymi bledami:
  `gugik_laz.py:363-365` ("Verified live."), `providers/cuzk/dmr.py:86-88` ("Znane operacje z Krovaka
  ... maja 0,5 m"), `transform/crs.py:134-140` (KNOWN_PATHS: "serwerowej CUZK nie uzywamy, gubi datum
  shift") i `:159` ("+0,12..+0,14 m") — do fali naprawczej K1/K2.
- `KNOWN-BUGS.md` (trafi do `docs/research/`): S4 zawyzony (RR-3), K6 z ta sama regula "~5,5 x 5,5 km"
  (RR-4), N9 "przy typowym uzyciu" mniej precyzyjne niz dokumenty (CLI nie liczy
  `estimate_pl_cutout_bytes`; `download_cmd.py:1034`), K2 "1,1-4,9 m" vs L4 "Cheb 5,00 m".
- Dokumenty historyczne (`docs/research/`, `docs/superpowers/`, datowane sekcje PROGRESS/CHANGELOG
  starszych wersji) — nie oceniane.

---

## Re-review rundy poprawek (2dbed85)

Zakres: `515f275..2dbed85` (1 commit, 7 plikow dokumentacji, +154/-76), pakiet
`DOCS-REVIEW-PACKAGE-RR.diff` (zgodny bajt w bajt z `git diff -U10 515f275..2dbed85`),
sekcja 8 `DOCS-FIX-REPORT.md`, pliki robocze `KNOWN-BUGS.md` i `hydrograf-uwagi-migracyjne.md`.
Repo Kartografu i Hydrografu tylko czytane (`git status` czysty, HEAD `2dbed85`).

### Werdykt: RESZTKI — 0 BLOKUJACE, 1 WAZNE (RR-16), 1 DROBNE (RR-17)

Wszystkie RR-1..RR-15 naprawione we wszystkich wskazanych miejscach i prawdziwie; tresc
wykraczajaca poza propozycje (RR-4 pas N-S, RR-5 w ARCHITECTURE, liczby K2 wzdluz granicy)
zgodna z kodem i pomiarem. Nowe: dolna granica K2 "ok. 1-5 m" / "~1,0 m na wschodzie CZ"
jest nieprawdziwa dla wschodnich Moraw (RR-16) i dwa nietrafione szczegoly w notce
"Przy naprawie" K2 (RR-17).

### Tabela RR-1..RR-15

| RR | Wynik | Dowod (linie wg 2dbed85) |
|---|---|---|
| RR-1 | OK | CLAUDE.md:313-319, SCOPE.md:428-433, ARCHITECTURE.md:895-902: "`auto` odpytuje tylko PL ... ale z przycieciem, wiec nie zawsze jak `--country pl`" + Osinow Dolny 6,2 km / 4 arkusze vs 8,9 km / 6 (L5 I/J: 1235 px x 5 m = 6,175 km, 1773 px = 8,865 km; lista auto 4 / pl 6); "Nysa Luzycka", Opolszczyzna przeniesiona do N2; PROGRESS.md:966-968 (bboxy L6 wewnatrz prostokata PL — sprawdzone w L6, sekcja "Zakres") |
| RR-2 | OK | ARCHITECTURE.md:729-735 "1,1-3,4 m wzdluz granicy PL-CZ" — pomiar re-review wzdluz calej granicy: Jaworzynka 1,12 ... trojstyk PL-CZ-DE 3,39, hak frydlancki 3,35 m; L4 S6 2,3 m. (Dolna granica "ok. 1-5 m" dla calych Czech — RR-16) |
| RR-3 | OK | DECISIONS.md:414-419, PROGRESS.md:184, :1114-1122, KNOWN-BUGS S4 — zgodne z symulacja (arkusz w 2025 / 2024 -> URL; tylko 2026 / tylko 2023iStarsze / bez danych -> "brak pokrycia niepewny"; 2026 nie jest odpytywana z listy zaszytej, wiec 2026+2024 -> po cichu 2024); `M-34-76-A-a-1-1` = tylko 2023 (L1 Zakres, BUG-L1-9) |
| RR-4 | OK | README.md:223-228, :275; CLAUDE.md:269-272; SCOPE.md:366-372; ARCHITECTURE.md:858-862; PROGRESS.md:180, :1073-1081; KNOWN-BUGS K6 — patrz (a) |
| RR-5 | OK | CLAUDE.md:310-312, SCOPE.md:426-427, ARCHITECTURE.md:889-892, DECISIONS.md:733-735 — patrz (b) |
| RR-6 | OK | README.md:232-233, CLAUDE.md:368, SCOPE.md:399-400 ("tylko `--product nmt`, system 1992" = `download_cmd.py:152-167`) |
| RR-7 | OK | ARCHITECTURE.md:51-60 (`_bbox_to_wgs84` `download_cmd.py:233-257` wolane z `_countries_for_bbox` na surowym bboxie, takze 5514/3045, i w `_country_bbox` galezi CZ `:320`; `_resolve_laz_bbox` `:1188-1190`), :78-80 (`crs.py:236`), :399-402 (`gugik.py:541`, sesja per wywolanie `_get_opendata_url`) |
| RR-8 | OK | DECISIONS.md:1272-1275 (L4 S1b, L1 F1), ARCHITECTURE.md:586-590 (L3 #1/#4, L5 B/D/F/I/J; L6 — tylko polozenie nodata) |
| RR-9 | OK | ARCHITECTURE.md:632-634 (L2 S23 — 48 arkuszy pod Wegrowem; L3 — Leba) |
| RR-10 | OK | PRD.md:239-241, PROGRESS.md:1005-1008 (pomiar: 208,6 / 369,7 km) |
| RR-11 | OK | PROGRESS.md:1080 `client.py:36-37` (= `MAX_EXPORT_WIDTH/HEIGHT`) |
| RR-12 | OK | PROGRESS.md:146-147 (`gfi/` = probki L3; L4 U12, L5 pkt (j)) |
| RR-13 | OK | DECISIONS.md:379-380 (`cli/cache_cmd.py:30`) |
| RR-14 | OK | PROGRESS.md:1030-1033 (`download_cmd.py:1643-1644` — sprawdzone) |
| RR-15 | OK | hydrograf-uwagi-migracyjne.md:122-127 (`manager.py:72-74` "Subset of ``failed``") |

### Weryfikacja miejsc ponad propozycje

**(a) RR-4 — pas N-S.** Dokumenty mowia "pas N-S szerokosci do ~3,6 km przechodzi (kafle maja
najwyzej 4100 px wysokosci; 3,6 x 24,6 km = 3 kafle po 7,4 Mpx)" — **prawda** jako warunek
wystarczajacy: kod ciecia (`client.py:139-147` warunek per wymiar; `_tile_grid`/`_splits`
`:257-300` — wiersze rowne, najwyzej 4100 px) daje dla szerokosci <= 1800 px kafle <= 1800 x 4100
= 7,38 Mpx, a L4 S3b potwierdza, ze takie kafle przechodza (limit miedzy 7,5 Mpx OK a 8,38 Mpx
HTTP 500 — sondy L4). Symulacja prawdziwym `_tile_grid` (px 2 m): 3,6 x 24,6 km -> 3 x 1800x4100
(7,38 Mpx); **5 x 8 km N-S -> bez ciecia 2500x4000 = 10 Mpx -> HTTP 500** (twierdzenie wykonawcy
prawdziwe); 5,5 x 5,5 -> 7,56 Mpx (granica), 5,7 x 5,7 -> 8,12, 8,3 x 8,3 -> 2 x 8,61, 10 x 10
-> 2 x 12,5, 10 x 5 W-E -> 12,5 Mpx bez ciecia (pada — zgodnie z tekstem). Uwaga (bez znaleziska):
sformulowanie z raportu wykonawcy i zlecenia "pas N-S przechodzi **tylko** do ~3,6 km" jest za
mocne — szersze pasy przechodza, gdy dlugosc wymusza ciecie na male wiersze (5 x 8,3 km -> 2 x
2500x2075 = 5,2 Mpx; 5 x 10 km -> 2 x 6,25 Mpx; 4,2 x 20 km -> 3 x 7,0 Mpx; zaleznosc
niemonotoniczna: 5 x 8 pada, 5 x 10 przechodzi). Dokumenty tego "tylko" nie pisza, wiec OK.

**(b) RR-5 — przycinanie trybu listy `--bbox`.** Prawda: `_dispatch_area` liczy
`part = _country_bbox(bbox, code, auto=auto, ...)` (`download_cmd.py:517`) i przekazuje go do
`_download_pl_bbox(pl_args, part, ...)` (`:529`), ktore wybiera arkusze `find_sheets_for_bbox(bbox,
...)` z przycietego bboxa (`:1115`); wycinek z `--geometry` bierze crop z `part`
(`_download_pl_geometry` -> `_download_pl_cutout(args, bbox, ...)`, `:1754-1755`), a lista
z `--geometry` bez `--target-crs` — `find_sheets_for_geometry(filepath)` bez bboxa (`:1760-1763`).
Na zywo: L5 I — lista auto 4 arkusze (bez `A-c-3-3/-3-4` na zachod od 14,0625°E), `--country pl` 6.

**(c) K2 — pomiary pyproj powtorzone** (ta sama metoda: `TransformerGroup("EPSG:4156", "EPSG:4258",
always_xy=True, allow_ballpark=False)`, operacje "S-JTSK to ETRS89 (1)" i "(3)", odleglosc na GRS80;
wariant "tam przez (1), z powrotem przez (3)" +/- 0,01 m): Cieszyn 1,15; Kudowa 2,15; Karkonosze
(Sniezka) 2,73; Bogatynia/Hradek 3,39; Cheb 4,87; srodek kafla `302_5550` (12,2465°E 50,0786°N z
EPSG:3045) 4,98; zachodni kraniec 12,09°E 5,16 m — liczby wykonawcy odtworzone (roznice 0,01 m
z wyboru punktu). Wzdluz granicy PL-CZ: 1,12 (Jaworzynka) do 3,39 m (trojstyk PL-CZ-DE) —
"1,1-3,4 m" OK. **Dla calych Czech dolna granica nie jest ~1 m** — RR-16.

**(d) Notki "Przy naprawie:" w backlogu PROGRESS** — sprawdzone odsylacze: K1 (:1012-1014)
`gugik_laz.py:363-365` = komentarz "... Verified live." (falszywy wobec K1), `cli/_parser.py:176-177`
= ostrzezenia K1/K5 w pomocy `--product`; K2 (:1030-1038) `cli/download_cmd.py:1643-1644` OK,
`providers/cuzk/dmr.py:86-88` OK, `transform/crs.py:134-140` i `:159` — miejsca trafione, ale patrz
RR-17, `providers/cuzk/dmr.py:54-55` — chybione o linie (RR-17), `:270-271` OK; K4 (:1063-1066)
`download/cutout.py:306-311` = komunikat z "np. z --system 2000" (OK); K5 (:1071-1072)
`cli/_parser.py:176-177` OK; S5 (:1130-1132) `transport/mosaic.py:265-271` = `logger.warning`
"... przepisana najblizszym sasiadem" (OK).

### Nowe znaleziska

| ID | Waga | plik:linia (2dbed85) | Temat |
|---|---|---|---|
| RR-16 | WAZNE | PROGRESS.md:1018-1020; KNOWN-BUGS.md:11 i sekcja "Korekty" (K2); skrocone "1-5 m": CLAUDE.md:283, README.md:211, :275, SCOPE.md:105, ARCHITECTURE.md:82, :832, DECISIONS.md:933, PROGRESS.md:27, :176, hydrograf-uwagi-migracyjne.md:165 | K2: "ok. 1-5 m", "~1,0 m na wschodzie CZ — Ostrawa, Brno" — we wschodnich Morawach roznica 0,1-0,9 m |
| RR-17 | DROBNE | PROGRESS.md:1033-1038 | notka "Przy naprawie" K2: `dmr.py:54-55` -> `:55-56`; "gubi datum shift" w `KNOWN_PATHS` nie jest nieaktualne |

#### RR-16 — WAZNE — dolna granica przesuniecia K2

- **Cytat:** `PROGRESS.md:1017-1020` "tresc CZ po reprojekcji przesunieta o ok. 1-5 m (roznica
  EPSG:1622 - EPSG:4829 policzona pyproj: ~1,0 m na wschodzie CZ — Ostrawa, Brno — do ~5,0 m na
  zachodzie — kafel `302_5550`; ...)"; to samo w `KNOWN-BUGS.md` (wiersz K2 i "Korekty": "zakres
  ... zastapiony 'ok. 1-5 m'"); w wersji skroconej "przesunieta o 1-5 m" w miejscach z tabeli.
- **Dowod (pyproj, metoda jak w (c)):** Zlin 0,14; Uherske Hradiste 0,24; Vsetin 0,38; Valasske
  Mezirici 0,51; Hodonin 0,64; Olomouc 0,74; Breclav 0,89; Frydek-Mistek 0,92; Brno 0,98; Ostrawa
  1,06; Znojmo 1,53; Ceske Budejovice 2,91; Liberec 3,16; Usti n. L. 3,78; Plzen 3,92; Karlowe Wary
  4,49; As 5,06; kraniec zachodni 5,16 m. Siatka 0,25° po prostokacie CZ: minimum 0,11 m przy
  17,60°E 49,10°N (okolice Uherskiego Hradiszcza). Kafle TM33 i `--target-crs` CZ dzialaja w calych
  Czechach, a we wschodnich Morawach roznica jest ponizej nominalnej dokladnosci samej EPSG:1622
  (1,0 m) — K2 jest tam praktycznie pomijalny, a "~1,0 m na wschodzie CZ" i dolne "1" w "1-5 m"
  sa nieprawdziwe. Gorna granica (~5 m na zachodzie) i zakres wzdluz granicy PL-CZ (1,1-3,4 m)
  poprawne. Waga WAZNE, nie BLOKUJACE: jawnie falszywe zdanie jest w PROGRESS/KNOWN-BUGS; w
  CLAUDE.md/README "1-5 m" to przyblizony zakres z zawyzona dolna granica (blad zachowawczy —
  zawyza skutek, nie zmienia mechanizmu ani remedium). Wspolodpowiedzialnosc przegladu: w pierwszym
  przebiegu przyjalem "1-5 m" (punkty L4 bez wschodnich Moraw) i sam podsunalem "1-5 m" jako opcje
  w RR-2 — pomiar siatka zrobilem dopiero teraz.
- **Poprawka:** PROGRESS K2 i KNOWN-BUGS K2 (+ sekcja "Korekty"): "o 0,1-5 m (roznica EPSG:1622 -
  EPSG:4829 policzona pyproj: ~0,1-0,5 m we wschodnich Morawach — Zlin, Uherske Hradiste, Vsetin —
  ~1 m w Brnie i Ostrawie, wzdluz granicy PL-CZ 1,1-3,4 m, ~5 m na zachodzie — kafel `302_5550`,
  As; ...)". Wersje skrocone (CLAUDE.md:283, README.md:211, :275, SCOPE.md:105, ARCHITECTURE.md:82,
  :832, DECISIONS.md:933, PROGRESS.md:27, :176, hydrograf-uwagi:165): "o do ~5 m (wzdluz granicy
  PL-CZ 1,1-3,4 m)" / README: "o maks. ok. 5 m (wzdłuż granicy PL-CZ 1,1-3,4 m)".

#### RR-17 — DROBNE — notka "Przy naprawie" przy K2

- `PROGRESS.md:1037` "`providers/cuzk/dmr.py:54-55`" — zdanie "5514->3045 przesuwa tresc o 1,25 m"
  to `dmr.py:55-56` (linia 54 to "reprojekcja serwerowa ... jest niewiarygodna —", "1,25 m" stoi
  w 56). Poprawka: `:55-56`.
- `PROGRESS.md:1034-1035` zalicza do "nieaktualnych komentarzy" `transform/crs.py:134-140`
  (`KNOWN_PATHS`: "serwerowej CUZK nie uzywamy, gubi datum shift") — ta fraza jest nadal prawdziwa:
  `imageSR=2180` gubi transformacje datum (135 m), co errata ADR-024 (`DECISIONS.md`, "Blad 135 m
  ... pozostaje realnym bledem serwera") i `dmr.py:270-271` utrzymuja. Z K2 zwiazana jest oczekiwana
  dokladnosc 0,5 m par 5514<->2180 w `KNOWN_PATHS` (`crs.py:135-149`; opis `:146-148` nazywa
  "Inverse of S-JTSK to ETRS89 (3)"). Nieprecyzyjnosc pochodzi z mojej listy "Poza zakresem"
  w pierwszym przebiegu. Poprawka: "`transform/crs.py:135-149` (`KNOWN_PATHS` 5514<->2180:
  oczekiwana dokladnosc 0,5 m = operacja slowacka "(3)"; opis "gubi datum shift" dotyczy
  `imageSR=2180` i zostaje)".

### Pliki robocze

- `KNOWN-BUGS.md`: K6 (regula z RR-4, `client.py:36-37`), S4 (RR-3; "Korekty" — 2026+2024 -> po
  cichu 2024, zgodne z kodem), N9 (CLI liczy tylko `cutout.estimated_bytes`, `download_cmd.py:1034`;
  podwojnie placi wolajacy z jawnym `estimate_pl_cutout_bytes` — zgodne z `cutout.py:482-532, :581`
  i L7) — OK; ID i wagi bez zmian. K2 — RR-16 (liczby w "Korektach" zgodne z moim pomiarem, wniosek
  "ok. 1-5 m" nie).
- `hydrograf-uwagi-migracyjne.md`: B4 poprawione (RR-15); reszta bez zmian merytorycznych; C/K2
  "1-5 m" — RR-16 (opcjonalnie).

### Spojnosc, forma, brama

- Te same zdania spojne miedzy CLAUDE.md, README, SCOPE, ARCHITECTURE, PROGRESS (i DECISIONS):
  S3/`auto` na granicach spoza rejestru, RR-5, K6, obejscie S2, S4 (DECISIONS/PROGRESS/KNOWN-BUGS);
  K2 spojne miedzy soba (RR-16 dotyczy wszystkich kopii).
- `docs/DECISIONS.md`: 515f275 1316 CRLF / 0 LF -> 2dbed85 1324 CRLF / 0 LF; wszystkie dodane linie
  z `\r`. Pliki ASCII (CLAUDE, ARCHITECTURE, DECISIONS, PROGRESS): zero nowych liter z diakrytykami;
  dopiski README/SCOPE/PRD z diakrytykami. W dodanych liniach zero `.superpowers/`, `/tmp/`,
  `e2e-data/`, `TODO`, "kontroler"; jedyna nazwa raportu: `L1-centrum-produkty-report.md` (z listy).
- Kod: `git diff --name-only 515f275..2dbed85 -- '*.py'` puste (AST/ruff/mypy bez zmian wzgledem
  pierwszego przegladu); `.venv/bin/python -m pytest tests/ -q -m "not live" -p no:cacheprovider`
  -> 1861 passed, 8 deselected.
