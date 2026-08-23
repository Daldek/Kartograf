# A7 — dokumentacja historyczna i badawcza (specs / plans / research)

Zakres: przeczytane w calosci — `docs/superpowers/specs/*.md` (3 pliki),
`docs/superpowers/plans/*.md` (6 plikow; pominiety `2026-08-22-release-0.7.0-audit.md`
zgodnie z zadaniem), `docs/research/*.md` (8 plikow). Jako baza porownawcza przeczytane
w calosci: `docs/DECISIONS.md` ADR-022/023/024 (l. 379-762) i `docs/CHANGELOG.md` sekcja
`[0.7.0]`.

Metoda:
- pelne czytanie 17 plikow docelowych (bloki kodu w wielkich planach czytane osobno przez
  filtr `awk` na blokach ``` — zeby proza i kod byly przejrzane rozlacznie, bez pominiec);
- grep za starymi wartosciami uniewaznionymi przez ADR-023/024 i CHANGELOG Breaking:
  `9651`, `imageSR`, `server:`, `server_crs`, `server_reprojection`, `serwerow`,
  `landcover_base`, `providers[/.]gugik`, `providers[/.]bdot10k`, `KRON86`;
- skan danych wrazliwych: `bearer|token|secret|password|api[_-]?key|/Users/|/home/` oraz
  regex adresow e-mail;
- weryfikator linkow: skrypt Pythona wyciagajacy z backtickow sciezki `*.md|py|toml|json|...`
  i sprawdzajacy istnienie z prefiksami `''`, `kartograf/`, `docs/`, `docs/superpowers/`;
- weryfikacja twierdzen wobec kodu i testow: `.venv/bin/python -m pytest`,
  `python -c "import ..."`, `grep` po `kartograf/` i `tests/`.

Nie sprawdzono:
- `docs/superpowers/plans/2026-08-22-release-0.7.0-audit.md` — jawnie wylaczony z zakresu;
- zgodnosci liczbowej pomiarow geodezyjnych w raportach (RMS, offsety, percentyle) — brak
  danych zrodlowych (`seam/`, `e2e-data/` nie istnieja w tym checkoutcie, sa w `.gitignore`);
- plikow poza moim obszarem (`README.md`, `docs/SCOPE.md`, `docs/PRD.md`, `docs/PROGRESS.md`,
  `CLAUDE.md`, kod) — inni audytorzy.

## Ustalenia

### A7-1 [Important] Spec etapu 1 twierdzi, ze `parent_request` NIE powstaje przy jawnym `--country` — odwrotnie niz ADR-023(f)(1) i kod
- Plik: `/home/claude-agent/workspace/Kartograf/docs/superpowers/specs/2026-08-11-etap1-cz-fundament-dmr-design.md`:495-498 oraz :580-581
- Twierdzenie: dwa miejsca specu opisuja brak `extra.parent_request` przy jawnym
  `--country pl|cz`, co zostalo uniewaznione decyzja z konsultacji 2026-08-11 (ADR-023,
  "Rozstrzygniecia", pkt f.1) i faktycznym zachowaniem 0.7.0, a naglowkowa errata
  (3 punkty) tego nie obejmuje.
- Dowod — spec (l. 495-498):
  ```
  (`bbox`/`bbox_crs` = oryginalne zadanie uzytkownika PRZED podzialem na kraje;
  `countries` = kraje faktycznie przeciete). Przy jawnym `--country pl|cz`
  i w trybie godlowym pola nie ma (jedno zadanie = jeden kraj, grupowac nie ma
  czego).
  ```
  spec (l. 580-581): "`extra.parent_request` w sidecarach OBU krajow przy auto i **jego brak
  przy jawnym `--country`**".
  ADR-023 (`docs/DECISIONS.md`:~460): "`extra.parent_request` jest zapisywany **zawsze**
  w trybie `--bbox`/`--geometry` (auto I jawny `--country`), **nigdy** w trybie godlowym."
- Weryfikacja: uruchomione
  `.venv/bin/python -m pytest tests/test_cli.py -k "explicit_cz_bbox_gets_parent_request or geometry_explicit_cz_gets_parent_request"`
  → **2 passed**; testy asertuja `parent["countries"] == ["CZ"]` dla wywolania z jawnym
  `--country cz`. Dodatkowo `kartograf/cli/download_cmd.py:1332` buduje
  `_build_parent_request(bbox, ("CZ",))` na sciezce jawnego kraju. Plan etapu 1
  (`2026-08-11-etap1-cz-fundament-dmr.md`:32) jawnie oznacza to jako "Korekta gwarancji
  ... z sekcji 9 specu" — czyli rozjazd byl znany, ale nie zostal odnotowany po stronie specu.
- Proponowana naprawa: dopisac 4. punkt do naglowkowej erraty specu etapu 1: "`extra.parent_request`
  powstaje **zawsze** w trybie `--bbox`/`--geometry` (takze przy jawnym `--country`) — sekcje 5.9
  i 8 opisuja stan sprzed rozstrzygniecia z konsultacji 2026-08-11; patrz ADR-023 pkt (f)1".
- Pewnosc: wysoka

### A7-2 [Important] Errata researchu CZ odwraca rekomendacje reprojekcji serwerowej tylko w 3 wskazanych miejscach — sekcja ZABAGED (`outSR=2180`) i tabela ograniczen zostaly bez adnotacji
- Plik: `/home/claude-agent/workspace/Kartograf/docs/research/2026-08-10-czechy-dmr-zabaged.md`:216, :231, :365
- Twierdzenie: errata (l. 7-16) wylicza konkretnie "sekcja 4.2 ..., sekcja 9 ... i wniosek 3",
  wiec nieoznaczone rekomendacje reprojekcji serwerowej CUZK w sekcji 5.2 B (ZABAGED, etap 3)
  i w tabeli ograniczen (sekcja 8) czytaja sie jak zweryfikowane i nadal wazne — mimo ze
  dotycza tego samego mechanizmu (serwerowy parametr ukladu na ArcGIS CUZK), ktory ADR-024
  zakazal jako gubiacy transformacje datum.
- Dowod (l. 216 i 231, sekcja 5.2 B — dostep do ZABAGED):
  ```
  - **`outSR=2180` — reprojekcja po stronie serwera dziala**
  ...
  **Wniosek:** ArcGIS REST jest lepszy od WFS (wiekszy limit + reprojekcja).
  ```
  (l. 365, tabela "Ograniczenia"): "Transformacja pozioma | brak otwartej siatki dla CZ;
  najlepiej 0,5 m (Helmert) **lub reprojekcja serwerowa**".
  ADR-024, "Konsekwencje": "Regula 'nie ufaj reprojekcji serwerowej' jest wiazaca takze dla
  przyszlych zrodel ... sterowanych serwerowym parametrem ukladu."
- Weryfikacja: grep `imageSR|outSR|serwerow` po pliku + porownanie z lista miejsc wskazanych
  w erracie (4.2 = l. 141-143, 9 = l. 395-397, wniosek 3 = l. 395); l. 216/231/365 nie sa
  w erracie wymienione i nie maja adnotacji w tym samym akapicie. Nie weryfikowano pomiarowo,
  czy MapServer ZABAGED gubi datum tak samo jak `exportImage` — dlatego znalezisko dotyczy
  kompletnosci erraty, nie samego faktu.
- Proponowana naprawa: rozszerzyc punkt 1 erraty o "sekcja 5.2 B (`outSR` dla ZABAGED) i
  tabela w sekcji 8" z jednym zdaniem: "przed uzyciem `outSR` w etapie 3 trzeba zweryfikowac
  TRESC (pomiar wzgledem referencji natywnej 5514), bo siostrzana usluga `exportImage` gubila
  datum shift — ADR-024".
- Pewnosc: srednia

### A7-3 [Important] `2026-08-11-adr024-seam-report.md` nie ma zadnej adnotacji o naprawie — caly dokument opisuje w czasie terazniejszym blad usuniety w 0.7.0
- Plik: `/home/claude-agent/workspace/Kartograf/docs/research/2026-08-11-adr024-seam-report.md`:12-17, :83, :312, :330-340
- Twierdzenie: raport diagnostyczny stwierdza, ze `--target-crs EPSG:2180` dla CZ zwraca raster
  przesuniety o ~135 m i ze sidecar niesie `transform.horizontal="server:EPSG:2180"`; oba fakty
  sa nieaktualne od fixu ADR-024, a dokument nie zawiera ani erraty, ani jednego odwolania do
  ADR-024 (grep `ADR-024` po pliku: **0 trafien**).
- Dowod (l. 12-17, sekcja "0. Wniosek nadrzedny (czytaj najpierw)"):
  ```
  **`--target-crs EPSG:2180` dla zrodel CZ zwraca raster przesuniety poziomo o ~135 m.**
  ... Kartograf ten wynik przyjmuje bez weryfikacji i opisuje w sidecarze jako
  `transform.horizontal="server:EPSG:2180"`, bez pola dokladnosci.
  ```
  l. 330: "**`--target-crs` dla CZ nie nadaje sie obecnie do scalania.** Do czasu naprawy ..."
  l. 338: "**Sidecar musi niesc dokladnosc transformacji poziomej**" — oba wymagania sa juz
  zrealizowane.
- Weryfikacja: `grep -n "ADR-024\|errat\|Adnotacja" docs/research/2026-08-11-adr024-seam-report.md`
  → brak trafien (dla porownania: `2026-08-11-etap1-e2e.md` i `2026-08-11-etap1-rekonesans.md`
  taka adnotacje maja). `grep -rn "server:" kartograf/` → jedyne trafienie to komentarz
  historyczny w `kartograf/cli/download_cmd.py:1039`; produkcyjny format buduje
  `download_cmd.py:1063` jako `f"pinned: {pinned.description} ({pinned.accuracy_m} m)"`.
- Proponowana naprawa: dodac naglowkowa errate (wzor: pozostale dokumenty ADR-024): "Errata
  (2026-08-18): opisany tu blad zostal naprawiony w 0.7.0 — ADR-024; sidecar niesie dzis
  `pinned: ... (acc m)`, a serwer CUZK dostaje zadania wylacznie w natywnym EPSG:5514.
  Wnioski 7.1 i 7.2 sa zrealizowane. Dokument zachowany jako diagnoza."
- Pewnosc: wysoka

### A7-4 [Important] `2026-08-11-adr024-bugfix-report.md` — nieaktualna liczba 1,25 m i zastrzezenie "fix nie zweryfikowany na zywo", bez erraty
- Plik: `/home/claude-agent/workspace/Kartograf/docs/research/2026-08-11-adr024-bugfix-report.md`:10-11, :30-32, :197-203, :309-311
- Twierdzenie: raport podaje blad sciezki godlowej jako stale "+1,25 m" i konczy sie
  zastrzezeniem, ze fix nie byl uruchomiony na zywych danych; oba twierdzenia zostaly
  uniewaznione przez `2026-08-11-adr024-verify-report.md` i przez ADR-024 (sekcje "Korekta
  liczby" i "Zywa weryfikacja fixu"), a raport nie ma zadnej adnotacji.
- Dowod (l. 10-11): "**Odpowiedz: NIE tak samo — bledu datum (135 m) tam nie ma, ale jest
  wlasne, systematyczne przesuniecie 1,25 m.**"; (l. 197-201): "**Fix nie zostal zweryfikowany
  na zywych danych.** ... **Rekomendacja przed mergem: powtorzyc punkty 1 i 4 macierzy E2E**";
  (l. 309-311): "Zastrzezenie nr 1 z pierwszej rundy nadal aktualne".
  Kontra — `2026-08-11-adr024-verify-report.md`:140-142: "to **4,92 m, nie 1,25 m** — blad
  serwerowej sciezki 3045 jest **zmienny przestrzennie**", oraz :13-14 (punkty 1 i 4: PASS na
  zywych danych). ADR-024 przejal obie korekty ("Korekta liczby (2026-08-11) ..." i
  "Zywa weryfikacja fixu (2026-08-11) ...").
- Weryfikacja: `grep -n "ADR-024\|errat\|Adnotacja"` po pliku → trafienia wylacznie w tresci
  merytorycznej (l. 62, 188, 240, 287, 299, 302), zadnej adnotacji korygujacej; porownanie
  z ADR-024 w `docs/DECISIONS.md` (sekcje "Korekta liczby" i "Zywa weryfikacja fixu") czytane
  w calosci. Nie weryfikowano pomiarow (brak `seam/`).
- Proponowana naprawa: naglowkowa errata: "Errata (2026-08-18): (a) liczba 1,25 m dotyczy
  wylacznie kafli kolo Cieszyna — pomiar na `302_5550` dal 4,92 m, blad serwerowy byl zmienny
  przestrzennie (verify-report sekcja 2, ADR-024 'Korekta liczby'); (b) Zastrzezenie 1
  ('fix nie zweryfikowany na zywo') zostalo zamkniete — patrz
  `docs/research/2026-08-11-adr024-verify-report.md`, oba punkty PASS."
- Pewnosc: wysoka

### A7-5 [Important] Design PL-2000 opisuje moduly/klasy, ktore nigdy nie powstaly (`parser_1992.py`, `_Parser1992`, `_Parser2000`)
- Plik: `/home/claude-agent/workspace/Kartograf/docs/superpowers/plans/2026-02-24-pl2000-support-design.md`:17, :24-25
- Twierdzenie: zatwierdzony design deklaruje ekstrakcje PL-1992 do `kartograf/core/parser_1992.py`
  i nazwy prywatne `_Parser1992`/`_Parser2000`; zrealizowano inaczej (ADR-017: publiczny
  `Parser2000` w `parser_2000.py`, logika PL-1992 zostaje w `SheetParser`) i dokument nie ma erraty.
- Dowod (l. 16-25):
  ```
  `SheetParser` pozostaje publicznym API (backward compatible). Wewnetrznie deleguje do
  `_Parser1992` lub `_Parser2000` na podstawie auto-detekcji formatu godla.
  ...
  ├── parser_1992.py       # _Parser1992 — wyekstrahowana logika PL-1992
  ├── parser_2000.py       # _Parser2000 — nowa logika PL-2000
  ```
  Plan implementacji tego samego dnia (`2026-02-24-pl2000-implementation.md`:7) mowi wprost
  odwrotnie: "keeping PL-1992 logic in place internally. This avoids risky extraction of
  working PL-1992 code" — czyli spec i plan sa sprzeczne, bez adnotacji po zadnej stronie.
- Weryfikacja: uruchomione
  `.venv/bin/python -c "import kartograf.core.parser_1992"` →
  `ModuleNotFoundError: No module named 'kartograf.core.parser_1992'`;
  `grep -n "^class" kartograf/core/parser_2000.py` → `49:class Parser2000:`;
  `ls kartograf/core/` → `geometry.py parser_2000.py parser_registry.py parser_tm33.py sheet_parser.py`.
  ADR-017 ("Decyzja: Opcja B ... deleguje do `Parser2000`") potwierdza wybrany wariant.
- Proponowana naprawa: dopisac naglowkowa errate: "Errata: zrealizowano wg ADR-017 —
  `parser_1992.py` nie powstal (logika PL-1992 zostala w `SheetParser`), a klasa PL-2000 jest
  publiczna i nazywa sie `Parser2000` (`kartograf/core/parser_2000.py`)."
- Pewnosc: wysoka

### A7-6 [Important] Spec etapu 0 dokumentuje `transform.horizontal = "server:EPSG:2180"` jako kontrakt sidecara etapu 1+ — errata naglowkowa tego punktu nie wymienia
- Plik: `/home/claude-agent/workspace/Kartograf/docs/superpowers/specs/2026-08-10-etap0-zrodla-wielokrajowe-design.md`:341-342
- Twierdzenie: sekcja 6.3 (kontrakt `ResultMetadata`, jedyna zmiana obserwowalna etapu 0)
  pokazuje docelowa wartosc pola `transform.horizontal` w formacie `"server:EPSG:2180"`;
  CHANGELOG 0.7.0 wymienia zmiane tego formatu jako **Breaking Change**, a trzypunktowa errata
  naglowkowa (l. 12-23) obejmuje tylko regule reprojekcji, mapowanie 9651→5621 i procent nodata.
- Dowod (l. 341-342):
  ```
  transform: dict | None  # etap 0: None; etap 1+: {"horizontal": "server:EPSG:2180",
                          #   "vertical": "pinned: Baltic 1957 -> EVRF2007 (0.1 m)"}
  ```
  CHANGELOG `[0.7.0]` / Breaking Changes: "**Sidecary CZ: `transform.horizontal` zmienia format
  i zakres** (ADR-024). Bylo `\"server:EPSG:<kod>\"` ..., jest `\"pinned: <opis operacji>
  (<dokladnosc> m)\"`". Siostrzana errata w specu etapu 1 (l. 14-22) TEN punkt wymienia wprost
  ("sidecar `server:EPSG:*`"), etapu 0 — nie.
- Weryfikacja: `grep -rn "server:" kartograf/` → tylko komentarz historyczny
  (`cli/download_cmd.py:1039`); faktyczny format buduje `cli/download_cmd.py:1063`
  (`f"pinned: {pinned.description} ({pinned.accuracy_m} m)"`). Errata etapu 0 przeczytana
  w calosci — 3 punkty, zaden nie dotyczy formatu pola sidecara.
- Proponowana naprawa: dopisac 4. punkt erraty specu etapu 0: "Przyklad `transform.horizontal =
  \"server:EPSG:2180\"` w sekcji 6.3 jest nieaktualny — od ADR-024 pole niesie
  `\"pinned: <opis> (<acc> m)\"` (BREAKING, patrz CHANGELOG 0.7.0)."
- Pewnosc: srednia

### A7-7 [Minor] Zerwany link wewnetrzny w planie PL-2000
- Plik: `/home/claude-agent/workspace/Kartograf/docs/superpowers/plans/2026-02-24-pl2000-implementation.md`:11
- Twierdzenie: odwolanie `docs/plans/2026-02-24-pl2000-support-design.md` wskazuje na katalog,
  ktory nie istnieje (dokument lezy w `docs/superpowers/plans/`).
- Dowod: `**Design doc:** \`docs/plans/2026-02-24-pl2000-support-design.md\``
- Weryfikacja: skrypt weryfikatora linkow (prefiksy `''`, `kartograf/`, `docs/`,
  `docs/superpowers/`) — jedyny nieistniejacy link `.md` w calym obszarze A7.
- Proponowana naprawa: `docs/superpowers/plans/2026-02-24-pl2000-support-design.md`.
- Pewnosc: wysoka

### A7-8 [Minor] Plany v0.6 wskazuja sciezki providerow sprzed przenosin z etapu 0
- Plik: `/home/claude-agent/workspace/Kartograf/docs/superpowers/plans/2026-03-03-v06-implementation-plan.md`:615, 814, 1148, 1421, 1480, 1531, 1561, 1775, 1788 oraz
  `/home/claude-agent/workspace/Kartograf/docs/superpowers/plans/2026-03-03-v06-parallel-cache-verification-design.md`:186, 195, 289, 298
- Twierdzenie: oba dokumenty odsylaja do `kartograf/providers/gugik.py`,
  `kartograf/providers/gugik_nmpt.py`, `kartograf/providers/gugik_orto.py`,
  `kartograf/providers/bdot10k.py` (oraz do `kartograf/cli/commands.py` jako miejsca funkcji
  `cmd_*`), a od etapu 0 pliki te zyja w `kartograf/providers/pl/` i `kartograf/cli/*_cmd.py`
  (BREAKING w CHANGELOG 0.7.0). Brak jakiejkolwiek noty datujacej.
- Dowod: `- Modify: \`kartograf/providers/gugik.py\` (line 583-588, \`_make_request\`)`
- Weryfikacja: weryfikator linkow — 14 nieistniejacych sciezek `.py` w tych dwoch plikach;
  `ls kartograf/providers/` potwierdza obecnosc katalogu `pl/` i brak `gugik*.py` w korzeniu.
- Proponowana naprawa: jedna linia naglowkowa w obu plikach: "Status: WYKONANY (v0.6.0).
  Sciezki modulow sa z 2026-03-03 — od etapu 0 (0.7.0) providery polskie zyja w
  `kartograf/providers/pl/`, a komendy CLI w `kartograf/cli/*_cmd.py` (patrz CHANGELOG 0.7.0,
  Breaking Changes)."
- Pewnosc: wysoka

### A7-9 [Minor] Design v0.6 opisuje tabele `bbox_cache`, ktora nigdy nie powstala
- Plik: `/home/claude-agent/workspace/Kartograf/docs/superpowers/plans/2026-03-03-v06-parallel-cache-verification-design.md`:254-263, :272
- Twierdzenie: schema `MetadataCache` w designie zawiera trzecia tabele `bbox_cache` i metody
  `get_bbox()`/`set_bbox()`; zaimplementowano tylko `url_cache` i `teryt_cache` (a w etapie 1
  doszla `sheet_cache`, o innym przeznaczeniu).
- Dowod: `CREATE TABLE IF NOT EXISTS bbox_cache (...)` + `- Metody: get_url(), set_url(),
  get_teryt(), set_teryt(), get_bbox(), set_bbox()`
- Weryfikacja: `grep -n "CREATE TABLE" kartograf/cache/metadata.py` →
  `url_cache` (l.86), `teryt_cache` (l.99), `sheet_cache` (l.110);
  `python -c "from kartograf.cache.metadata import MetadataCache; print(hasattr(MetadataCache,'get_bbox'), hasattr(MetadataCache,'set_bbox'))"`
  → `False False`.
- Proponowana naprawa: jedno zdanie w tej samej sekcji: "(`bbox_cache` ostatecznie nie
  powstal — zakres zawezono do `url_cache`/`teryt_cache`; ADR-019, CHANGELOG 0.6.0)."
- Pewnosc: wysoka

### A7-10 [Minor] Odwolania do niewersjonowanych raportow ze scratchpada bez wskazania odzyskanych kopii
- Plik: `/home/claude-agent/workspace/Kartograf/docs/research/2026-08-11-etap1-e2e.md`:33 oraz
  `/home/claude-agent/workspace/Kartograf/docs/research/2026-08-11-adr024-bugfix-report.md`:4
- Twierdzenie: oba dokumenty odsylaja do `seam/verify/verify-report.md` i `seam-report.md`,
  ktore nie istnieja w repo (`seam/` jest w `.gitignore`, l. 70-71); kopie odzyskane
  2026-08-18 leza w `docs/research/2026-08-11-adr024-{verify,seam}-report.md`. W e2e.md
  wyjasnienie pojawia sie dopiero 60 linii nizej (l. 95-97), w bugfix-report — wcale.
- Dowod (e2e.md l. 33): "**oba PASS**, patrz `seam/verify/verify-report.md`
  (scratchpad sesji weryfikacyjnej)"; (bugfix-report l. 4): "Zgloszenie: `seam-report.md`
  (analiza szwu PL/CZ na Olzie)."
- Weryfikacja: `ls -d seam e2e-data` → brak; `grep -nE "seam|e2e" .gitignore` → `seam/`,
  `e2e-data/`; kopie potwierdzone przez `ls docs/research/`.
- Proponowana naprawa: dopisac w obu miejscach "(kopia:
  `docs/research/2026-08-11-adr024-verify-report.md` / `...-seam-report.md`)".
- Pewnosc: wysoka

### A7-11 [Minor] Zamkniete zastrzezenia w verify-report nie sa oznaczone jako zamkniete
- Plik: `/home/claude-agent/workspace/Kartograf/docs/research/2026-08-11-adr024-verify-report.md`:289-295, :296-301
- Twierdzenie: Zastrzezenie 3 ("warto dopisac jedno zdanie" o zmiennosci przestrzennej bledu)
  i Zastrzezenie 4 ("liczby w `docs/research/2026-08-11-etap1-e2e.md` ... warto odswiezyc")
  zostaly juz wykonane, ale dokument nie odnotowuje tego.
- Dowod (l. 299-301): "liczby w `docs/research/2026-08-11-etap1-e2e.md` dla punktow 1 i 4 sa
  juz nieaktualne — dokument warto odswiezyc"
- Weryfikacja: `docs/research/2026-08-11-etap1-e2e.md` ma dzis adnotacje
  `[po bugfixie ADR-024: ...]` przy punktach 1 i 4 (l. 60, 63, 89-97, 113-115, 180-184,
  191-194); ADR-024 ma sekcje "Korekta liczby (2026-08-11, po zywej weryfikacji fixu)"
  z liczba 4,92 m — czyli oba postulaty zrealizowane.
- Proponowana naprawa: dopisac przy obu zastrzezeniach "(zrealizowane 2026-08-11/18 — patrz
  ADR-024 'Korekta liczby' i adnotacje w e2e.md)".
- Pewnosc: wysoka

### A7-12 [Minor] Bezwzgledne sciezki srodowiska wykonania i publiczny SHARE_ID w dokumentach
- Plik: `/home/claude-agent/workspace/Kartograf/docs/research/2026-08-11-etap1-e2e.md`:47, 52, 205, 310;
  `.../2026-08-11-adr024-seam-report.md`:6, 36; `.../2026-08-11-adr024-verify-report.md`:4, 53, 149, 233;
  `.../2026-08-10-niemcy-dgm-atkis.md`:114, 326;
  `/home/claude-agent/workspace/Kartograf/docs/superpowers/plans/2026-03-03-v06-implementation-plan.md`:88-91;
  `.../2026-08-10-etap0-zrodla-wielokrajowe.md`:61; `.../2026-08-11-etap1-cz-fundament-dmr.md`:4299
- Twierdzenie: dokumenty zawieraja bezwzgledne sciezki `/home/claude-agent/...` i sciezki
  scratchpada sesji (`/tmp/claude-1001/...-f27c5cce-.../scratchpad/seam`) oraz publiczny
  SHARE_ID Nextcloud Saksonii; **nie znaleziono zadnych credentiali, tokenow API, hasel ani
  adresow e-mail** — to jedynie szum srodowiskowy, nie wyciek.
- Dowod: `K=/home/claude-agent/workspace/Kartograf/.venv/bin/kartograf` (e2e:47);
  `https://geocloud.landesvermessung.sachsen.de/public.php/dav/files/JCcXyifaNdLDnxZ/dgm1_33410_5654_2_sn_tiff.zip`
  (niemcy:326 — sam dokument ostrzega na l. 140, ze SHARE_ID sa rotowane).
- Weryfikacja: `grep -rniE "bearer|token|secret|password|api[_-]?key|/Users/|/home/"` +
  regex adresow e-mail po calym obszarze A7 — zero trafien na credentiale/e-maile;
  nazwa `claude-agent` to konto agenta, nie tozsamosc uzytkownika.
- Proponowana naprawa: opcjonalnie zamienic `/home/claude-agent/workspace/Kartograf` na
  `<repo>` / `$REPO` w cytowanych komendach; sciezki scratchpada (seam-report:6,
  verify-report:4) usunac lub zastapic "katalog roboczy sesji (poza repo)". Nie blokuje wydania.
- Pewnosc: wysoka

## Inwentarz errat

| Plik | Naglowkowa errata | Uniewaznione twierdzenia bez erraty (linie) |
|---|---|---|
| `docs/superpowers/specs/2026-03-24-wms-layer-validation-design.md` | nie (adnotacje inline 2026-08-18: l.20, l.130) | brak |
| `docs/superpowers/specs/2026-08-10-etap0-zrodla-wielokrajowe-design.md` | **tak** (l.12-23, 3 pkt) | l.341-342 — `transform.horizontal="server:EPSG:2180"` jako kontrakt sidecara (A7-6) |
| `docs/superpowers/specs/2026-08-11-etap1-cz-fundament-dmr-design.md` | **tak** (l.14-28, 3 pkt) | l.495-498, l.580-581 — brak `parent_request` przy jawnym `--country` (A7-1) |
| `docs/superpowers/plans/2026-02-24-pl2000-implementation.md` | nie | l.11 (zerwany link, A7-7); l.7 `_Parser2000` (nazwa faktyczna: `Parser2000`); l.1540 nn. — `kartograf/cli/commands.py` jako miejsce `cmd_*` (A7-8) |
| `docs/superpowers/plans/2026-02-24-pl2000-support-design.md` | nie | l.17, l.24-25 — `parser_1992.py`/`_Parser1992`/`_Parser2000` (A7-5) |
| `docs/superpowers/plans/2026-03-03-v06-implementation-plan.md` | nie | l.615, 814, 1148, 1421, 1480, 1531, 1561, 1775, 1788 — sciezki `providers/gugik*.py`, `providers/bdot10k.py` (A7-8) |
| `docs/superpowers/plans/2026-03-03-v06-parallel-cache-verification-design.md` | nie | l.186, 195, 289, 298 — stare sciezki providerow; l.204, 305, 309 — `cli/commands.py` (A7-8); l.254-263, 272 — `bbox_cache`/`get_bbox`/`set_bbox` (A7-9) |
| `docs/superpowers/plans/2026-08-10-etap0-zrodla-wielokrajowe.md` | **tak** (l.3) | brak — l.399 (9651) i l.1282 (KNOWN_PATHS) sa wprost wymienione w erracie |
| `docs/superpowers/plans/2026-08-11-etap1-cz-fundament-dmr.md` | **tak** (l.3) | brak — l.3179/3423/3435/3567 (`server_crs`), l.4362, l.4444 (asercja E2E) sa wprost wymienione w erracie |
| `docs/research/2026-08-10-czechy-dmr-zabaged.md` | **tak** (l.7-21, 2 pkt) | l.216, l.231 — `outSR=2180` dla ZABAGED; l.365 — "lub reprojekcja serwerowa" w tabeli ograniczen (A7-2) |
| `docs/research/2026-08-10-niemcy-dgm-atkis.md` | nie (nie wymaga) | brak — dokument sam rekomenduje "pobierac natywnie i reprojektowac lokalnie" (l.78), zgodnie z ADR-024 |
| `docs/research/2026-08-10-slowacja-dmr-zbgis.md` | **tak** (l.8-13) | brak — errata zawiera ogolny wymog "zweryfikowac pomiarem TRESCI", ktory pokrywa tez l.47, 67, 257, 272, 336 |
| `docs/research/2026-08-11-adr024-bugfix-report.md` | nie | l.10-11, l.30-32 — "1,25 m" jako stala; l.197-203, l.309-311 — "fix nie zweryfikowany na zywo" (A7-4); l.4 — odwolanie `seam-report.md` (A7-10) |
| `docs/research/2026-08-11-adr024-seam-report.md` | **nie (0 odwolan do ADR-024 w calym pliku)** | l.12-17, l.83, l.312, l.330-340 — caly opis bledu i wnioski 7.1/7.2 w czasie terazniejszym (A7-3) |
| `docs/research/2026-08-11-adr024-verify-report.md` | nie (nie wymaga — opisuje stan po fixie) | l.289-295, l.296-301 — zastrzezenia 3 i 4 juz zrealizowane, bez adnotacji (A7-11) |
| `docs/research/2026-08-11-etap1-e2e.md` | **tak** (blok adnotacji l.10-39 + inline `[po bugfixie ADR-024: ...]` w krokach 1 i 4) | brak; l.33 — odwolanie do scratchpada bez kopii (A7-10) |
| `docs/research/2026-08-11-etap1-rekonesans.md` | nie (adnotacja inline l.246 przy Kroku 5) | brak |

## Pozytywy (krotko)
1. Audyt z 2026-08-18 pokryl **najwazniejsze** miejsca: oba plany etapow 0/1 i oba specy
   maja naglowkowe erraty odsylajace do ADR-023/024, a `etap1-e2e.md` dostal wzorcowa
   dwuwarstwowa adnotacje (blok naglowkowy + inline `[po bugfixie ADR-024: ...]` przy
   kazdej nieaktualnej liczbie) — stan sprzed fixu zachowany celowo jako punkt odniesienia.
2. Kryterium daty weryfikacji endpointow (d) spelnione w **8/8** plikach research: kazdy ma
   date w naglowku plus jawna legende metody (`[T]`/`[OK]`/`[DOC]`, "zweryfikowane na zywo").
3. Zero danych wrazliwych: grep za `bearer|token|secret|password|api_key`, `/Users/` i regex
   adresow e-mail nie dal ani jednego trafienia na credentiale; jedyne "tokeny" to opis
   paywalla BKG (`wcs_dgm1__{{uuid}}` — placeholder) i publiczny SHARE_ID Saksonii.
4. Linki wewnetrzne w praktyce zdrowe: jeden zerwany link `.md` na 17 plikow; reszta trafien
   weryfikatora to sciezki modulow sprzed przenosin etapu 0, nie literowki.
5. Research DE (`2026-08-10-niemcy-dgm-atkis.md`) **wyprzedzil** ADR-024: juz 2026-08-10
   zaleca "pobierac natywnie i reprojektowac lokalnie" (l.78) oraz twardy zakaz ballparku
   z kontrola `isinf` (l.248-249) — nie wymaga zadnej erraty.

## Podsumowanie liczbowe: C=0 I=6 M=6
