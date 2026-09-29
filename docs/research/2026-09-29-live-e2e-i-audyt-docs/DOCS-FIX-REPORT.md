# DOCS-FIX — fala poprawek dokumentacji po testach na zywo i audycie (2026-09-29)

**Status: WYKONANE.** Galaz `develop`, start HEAD 6985765, koniec HEAD f577d1c
(12 commitow, niewypchniete; `origin/develop..develop` = 220). Kod bez zmian zachowania — w plikach `.py`
zmienione wylacznie docstringi, komentarze i napisy pomocy CLI (dowod nizej).
Repo Hydrografu nietkniete (tylko odczyt). `.superpowers/` i `e2e-data/` nie
commitowane. Subagenty nie byly uruchamiane.

Liczby: **D1 35** — 33 NAPRAWIONE, 2 OZNACZONE (N4), 0 ODRZUCONE, 0 POMINIETE;
**D2 55** — 50 NAPRAWIONE, 4 OZNACZONE (N6, K3, S2, K3), 0 ODRZUCONE,
1 POMINIETE (D2-54: plik K1); **Hydrograf 11 + 2 obserwacje** — przeniesione do
`hydrograf-uwagi-migracyjne.md` (ten katalog). Razem 90 znalezisk Kartografa:
83 naprawione, 6 oznaczone jako znany blad, 1 pominiete, 0 odrzuconych
(zadne twierdzenie audytorow nie okazalo sie falszywe; w kilku miejscach
proponowany tekst byl nieprecyzyjny i zostal skorygowany — kolumna "Uwagi",
np. D1-8, D1-13, D2-15).

Dodatkowe wymaganie kontrolera (backlog "Do naprawy"): **ZROBIONE** — sekcja
`docs/PROGRESS.md:991` "#### Do naprawy — testy na zywych danych 2026-09-29
(przed wydaniem 0.7.0)" na poczatku "## Backlog": checkbox dla KAZDEGO ID
z `KNOWN-BUGS.md` (K1-K6, S1-S5, N1-N9, H1 oznaczone "hipoteza — do
weryfikacji"; linie 1000-1151), kazdy z waga, skutkiem, `plik:linia`
(wg HEAD po fali) i nazwa raportu; K2 i K6 z dopiskiem "Wymaga odmrozenia toru
CZ (ADR-024) — decyzja uzytkownika". Tabela "Znane bledy" w sekcji sesji
(`docs/PROGRESS.md:165`) ma po jednym zdaniu i odsyla do tej podsekcji.
Pozycje istniejacego backlogu oznaczone "-> ID": tryb listy na
`download_sheets` + tolerancja braku pokrycia (-> S2), A2-7 fallback `urls[0]`
(-> K4), `extra.off_grid_sheets` (-> S5), `bbox_to_crs` z odmrozeniem toru CZ
(-> K2), `harmonize_dem` (-> K2), E2E kafelkowania `exportImage` (odhaczone,
-> K6), komunikat PL-2000 z remedium `--system 2000` (-> K4), API wycinka
z wstrzykiwanym providerem (obejscie S1/N6). Istniejacy podpunkt backlogu nie
dublowal zadnego opisu — pelne opisy zyja tylko w "Do naprawy".

## 1. Commity (od 6985765)

| Commit | Zakres |
|---|---|
| 57ef96b `docs(api)` | docstringi/komentarze/`--help` (13 plikow `.py`) |
| 45bf901 `docs(claude)` | CLAUDE.md |
| 81147fb `docs(readme)` | README.md (sekcja "Znane problemy (0.7.0-dev)") |
| b64903f `docs(scope,prd)` | SCOPE 3.11, PRD 3.7 |
| dc19103 `docs(architecture)` | ARCHITECTURE.md |
| 2b1fd26 `docs(decisions)` | DECISIONS.md (CRLF zachowane) |
| 7b54fcf `docs(changelog)` | CHANGELOG.md [0.7.0] |
| 3921bfc `docs(standards)` | DEVELOPMENT_STANDARDS 2.2, IMPLEMENTATION_PROMPT 4.2 |
| aa1bb8e `docs(progress)` | PROGRESS.md |
| f7b673e `docs` | drobne (polskie znaki README, zawijanie SCOPE) |
| 1b30f13 `docs` | precyzja opisu S1/S2 (README, CLAUDE.md, PROGRESS) |
| f577d1c `docs(progress)` | odsylacz do raportu fali w katalogu raportow |

Stopka kazdego commita: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## 2. Brama

- `.venv/bin/python -m pytest tests/ -q -m "not live" -p no:cacheprovider` ->
  **1861 passed, 8 deselected** (przed fala i po niej; takze po commicie kodu).
- `ruff check kartograf/ tests/` -> All checks passed; `ruff format --check` ->
  87 files already formatted.
- `mypy kartograf/` -> **32 errors in 9 files**; lista `plik: komunikat` (bez
  numerow linii) identyczna z baseline zmierzonym na 6985765 (`diff` pusty).
- Zero zmian zachowania: AST kazdego zmienionego pliku `.py` po usunieciu
  docstringow identyczny z HEAD 6985765 (12 plikow); w `cli/_parser.py`
  roznia sie WYLACZNIE argumenty `help=`/`description=` (AST z zamaskowanymi
  tymi argumentami identyczny). Testy pomocy CLI (`CUZK`, `SoilGrids`,
  `--scale`, `--product`) przechodza.
- Nie zmieniane: `providers/pl/gugik_laz.py`, `providers/cuzk/*`,
  `transform/crs.py` (pliki K1/K2/K6 — brief, zasada 2).

## 3. Znaleziska D1 (35)

Linie wg HEAD f577d1c (PROGRESS: jak w commicie f577d1c).

| ID | Status | Gdzie (plik:linia) | Uwagi |
|---|---|---|---|
| 1 | NAPRAWIONE | docs/PRD.md:531 (39 nazw), :555-562 (7 nazw wycinka), :591 (`NoCoverageError`), nota 3.7 :26 | zweryfikowane: `len(kartograf.__all__) == 39` |
| 2 | NAPRAWIONE | kartograf/cli/_parser.py:69, :71-80 | TM33 = warp 5514 -> 3045 (`providers/cuzk/dmr.py:306`). Komunikaty BLEDOW `download_cmd.py:680` (PL — prawdziwy) i `:1644` (CZ, "dane natywne 1:1") to napisy runtime, nie pomoc — poza zakresem zasady 2, zostawione (do decyzji przy naprawie K2); docstring `_cmd_download_cz` poprawiony (D2-46) |
| 3 | NAPRAWIONE | docs/SCOPE.md:431-437 | zgodne z `_resolve_cz_geometry_bbox`/`_geometry_envelope` |
| 4 | NAPRAWIONE | README.md:253-257, docs/SCOPE.md:384-392 | |
| 5 | OZNACZONE (N4) | README.md:149-151 | pusta krotka przy `skipped` = znany blad N4; tekst nie opisuje tego jako zamierzone |
| 6 | NAPRAWIONE | README.md:67-73 | przyklady z celem EPSG:2180 (bez K2) |
| 7 | NAPRAWIONE | docs/PRD.md:22 | bez liczb (odsylacz do SCOPE 6.2) |
| 8 | NAPRAWIONE | README.md:58-66 | doprecyzowane: blad przed siecia poza prostokatem PL; komunikat o etapie 2 tylko dla nmpt/orto (dla `--resolution 1m`/`--system`/KRON86 — blad walidacji) |
| 9 | NAPRAWIONE | CLAUDE.md:283-285 | |
| 10 | NAPRAWIONE | kartograf/cli/_parser.py:146-148 | |
| 11 | NAPRAWIONE | CLAUDE.md:344-349 | z nota N4 |
| 12 | NAPRAWIONE | README.md:171-175 | |
| 13 | NAPRAWIONE | README.md:80-82, docs/SCOPE.md:374-383, :426-430 | doprecyzowane wzgledem D1: `TransformError` z `_country_bbox` nie jest "porazka jednego kraju" — przerywa petle krajow kodem 1 (`download_cmd.py:516-519`, backlog "TransformError w petli krajow"); tekst mowi o braku danych albo awarii zrodla |
| 14 | NAPRAWIONE | README.md:152-156 | |
| 15 | NAPRAWIONE | README.md:187 | |
| 16 | OZNACZONE (N4) | README.md:191 | arkusze z cache bez `parent_request` = N4 |
| 17 | NAPRAWIONE | README.md:261-264 | |
| 18 | NAPRAWIONE | docs/PRD.md:120-122 | |
| 19 | NAPRAWIONE | docs/PRD.md:656-657 | |
| 20 | NAPRAWIONE | docs/SCOPE.md:95-99 | |
| 21 | NAPRAWIONE | docs/SCOPE.md:293-296 | |
| 22 | NAPRAWIONE | docs/SCOPE.md:244 | |
| 23 | NAPRAWIONE | docs/SCOPE.md:548-550 (6.1), :564-567 (6.2) | 6.2 z wynikami testow na zywo 2026-09-29 |
| 24 | NAPRAWIONE | README.md:258-260, docs/SCOPE.md:389-392 | |
| 25 | NAPRAWIONE | CLAUDE.md:340-344 | |
| 26 | NAPRAWIONE | kartograf/cli/_parser.py:122-130 | |
| 27 | NAPRAWIONE | README.md:121, :192, :250-260, :445, :464; docs/SCOPE.md:59-64, :313-319, :374-392, :557-558 | wskazane dopiski falowe z polskimi znakami |
| 28 | NAPRAWIONE | kartograf/__init__.py:1-26 | przyklad `download_pl_cutout` z celem EPSG:2180 |
| 29 | NAPRAWIONE | docs/SCOPE.md:79-85, :354-357; CLAUDE.md:259-263 | zmierzone: 1/9 (1:10000) i 4/16 (1:50000) dla EPSG:4326/2180 |
| 30 | NAPRAWIONE | README.md:429 | `pyproject.toml:51` extras `dev` |
| 31 | NAPRAWIONE | kartograf/cli/_parser.py:69, :220 | |
| 32 | NAPRAWIONE | README.md:278, :285 | |
| 33 | NAPRAWIONE | README.md:85-86, kartograf/cli/_parser.py:91-92 | |
| 34 | NAPRAWIONE | kartograf/cli/_parser.py:161 | "+0,11..+0,15 m, rosnaco S->N" (L4 U7: 0,111-0,144 w CZ) |
| 35 | NAPRAWIONE | README.md:270 | |

D1 "Obserwacje poza zakresem": CHANGELOG:263-267 = D2-24 (naprawione);
ARCHITECTURE 224/248 = D2-07; ARCHITECTURE 62-67 = D2-03; docstring
`_build_parent_request` = D2-45; komunikaty runtime "dane natywne 1:1" i remedium
`ValidationError` z `download_bbox` — POMINIETE (napisy runtime, nie pomoc CLI,
zasada 2); `kartograf/download/__init__.py` bez `DownloadResult` i nazw wycinka
w `__all__` — POMINIETE (zmiana eksportow = zmiana zachowania `import *`).

## 4. Znaleziska D2 (55)

| ID | Status | Gdzie (plik:linia) | Uwagi |
|---|---|---|---|
| D2-01 | OZNACZONE (N6) | docs/ARCHITECTURE.md:395-401 | falsz usuniety; takze DECISIONS ADR-019 :376, IMPLEMENTATION_PROMPT, PROGRESS status |
| D2-02 | NAPRAWIONE | docs/ARCHITECTURE.md:51-57 | + nota K2 o wyborze operacji (:74-78) |
| D2-03 | NAPRAWIONE | docs/ARCHITECTURE.md:80-89 | |
| D2-04 | OZNACZONE (K3) | docs/ARCHITECTURE.md:554-560 | liczby z L2 (21 % pikseli) |
| D2-05 | OZNACZONE (S2) | docs/ARCHITECTURE.md:426-437 | |
| D2-06 | NAPRAWIONE | docs/ARCHITECTURE.md:366-374 | + N4 |
| D2-07 | NAPRAWIONE | docs/ARCHITECTURE.md:248, :272-274 | |
| D2-08 | NAPRAWIONE | docs/ARCHITECTURE.md:219-221 | |
| D2-09 | NAPRAWIONE | docs/ARCHITECTURE.md:45-49 | |
| D2-10 | NAPRAWIONE | docs/ARCHITECTURE.md:247 | |
| D2-11 | NAPRAWIONE | docs/ARCHITECTURE.md:175-176 | |
| D2-12 | NAPRAWIONE | docs/ARCHITECTURE.md:386-388 | zmierzone: `M-33-036-...` i `M-33-36-...` -> dwie sciezki |
| D2-13 | NAPRAWIONE | docs/ARCHITECTURE.md:498-499 | |
| D2-14 | NAPRAWIONE | docs/ARCHITECTURE.md:977-979 | |
| D2-15 | NAPRAWIONE | docs/DECISIONS.md:46 (status), :58-64 | data korekty 2026-09-29 (dzien audytu), nie 2026-09-28 jak w propozycji |
| D2-16 | NAPRAWIONE | docs/DECISIONS.md:193-202 | |
| D2-17 | NAPRAWIONE | docs/DECISIONS.md:711-717 | errata ADR-023 pkt 7, bez przepisywania pkt 3 |
| D2-18 | NAPRAWIONE | docs/DECISIONS.md:718-725 | + S2, N2 |
| D2-19 | NAPRAWIONE | docs/DECISIONS.md:701-703 | |
| D2-20 | NAPRAWIONE | docs/DECISIONS.md:942-947 | w erracie ADR-024 (nie przepisano Konsekwencji) |
| D2-21 | NAPRAWIONE | docs/DECISIONS.md:1119-1128 | |
| D2-22 | NAPRAWIONE | docs/DECISIONS.md:352-356 | |
| D2-23 | NAPRAWIONE | docs/DECISIONS.md:404-414 (ADR-020), :1205-1206 (R5) | + S4 i wyniki (j) |
| D2-24 | NAPRAWIONE | docs/CHANGELOG.md:302-311 | "ZASTAPIONE" (ADR-027, ADR-023 pkt 5); przyklady z kodu (`--resolution 2m`, `Bpv`) |
| D2-25 | NAPRAWIONE | docs/CHANGELOG.md:314-315 | |
| D2-26 | NAPRAWIONE | docs/CHANGELOG.md:229-233 | zmierzone: bez `uklad=` -> `laz/pl_1992_*` |
| D2-27 | NAPRAWIONE | docs/CHANGELOG.md:317-322, :424-428 | |
| D2-28 | NAPRAWIONE | docs/CHANGELOG.md:352-356 | |
| D2-29 | NAPRAWIONE | docs/CHANGELOG.md:125-130, :189-190 | |
| D2-30 | OZNACZONE (K3) | docs/PROGRESS.md:1022 (Backlog "Do naprawy", K3) | pozycja backlogu = K3 |
| D2-31 | NAPRAWIONE | docs/PROGRESS.md:1204-1207 | + "-> K4" |
| D2-32 | NAPRAWIONE | docs/PROGRESS.md:1337-1341 | zmierzone: `transform_bounds(densify_pts=21)` w corine/soilgrids |
| D2-33 | NAPRAWIONE | docs/PROGRESS.md:970-973 | |
| D2-34 | NAPRAWIONE | docs/PROGRESS.md:878-881 | |
| D2-35 | NAPRAWIONE | docs/PROGRESS.md:883-886 | + K1 (obserwacja byla objawem bledu) |
| D2-36 | NAPRAWIONE | docs/PROGRESS.md:1306-1310 | |
| D2-37 | NAPRAWIONE | docs/DEVELOPMENT_STANDARDS.md:334 | + wersja 2.2 |
| D2-38 | NAPRAWIONE | docs/DEVELOPMENT_STANDARDS.md:292-302, :503, :788-789; IMPLEMENTATION_PROMPT 6.3/11 | takze IMPLEMENTATION_PROMPT (D2 sekcja 5) |
| D2-39 | NAPRAWIONE | docs/DEVELOPMENT_STANDARDS.md:621-627 | |
| D2-40 | NAPRAWIONE (odnotowane) | docs/DEVELOPMENT_STANDARDS.md:483-489 | rozjazd standard/praktyka opisany jako do decyzji wlasciciela — nie rozstrzygalem kierunku |
| D2-41 | NAPRAWIONE | docs/DEVELOPMENT_STANDARDS.md:327 | |
| D2-42 | NAPRAWIONE | kartograf/download/manager.py:111-114, :146-152, :747-750, :779 | |
| D2-43 | NAPRAWIONE | kartograf/providers/pl/gugik.py:9-11, :62-63, :444-447, :501-514 | Notes o K3/K4/S1 jako znanych bledach (nie zamierzone) |
| D2-44 | NAPRAWIONE | kartograf/cli/download_cmd.py:196-205 | |
| D2-45 | NAPRAWIONE | kartograf/cli/download_cmd.py:355-357 | |
| D2-46 | NAPRAWIONE | kartograf/cli/download_cmd.py:1601, :1614-1618 | |
| D2-47 | NAPRAWIONE | kartograf/cli/download_cmd.py:849-860 | + S2 (+ S3 w `_country_bbox` :294-296) |
| D2-48 | NAPRAWIONE | kartograf/download/cutout.py:660-696 | Returns/Raises + N4 (+ N4 w `run_pl_cutout` docstring) |
| D2-49 | NAPRAWIONE | kartograf/download/storage.py:228-229 | |
| D2-50 | NAPRAWIONE | kartograf/sources/descriptor.py:4-7, :22, :71; kartograf/sources/registry.py:4-7 | |
| D2-51 | NAPRAWIONE | kartograf/exceptions.py:4-7 | |
| D2-52 | NAPRAWIONE | kartograf/transport/mosaic.py:4-7 | + limit exportImage deklarowany vs realny (K6) |
| D2-53 | NAPRAWIONE | kartograf/core/sheet_parser.py:995-999 | zmierzone: 9 godel |
| D2-54 | POMINIETE | — | `providers/pl/gugik_laz.py` to plik bledu K1 (brief, zasada 2); poprawka przykladu razem z naprawa K1 |
| D2-55 | NAPRAWIONE | kartograf/sources/sidecar.py:4-7 | |

D2 sekcja 5 (obserwacje): SCOPE:378-380 i README:156 — naprawione w D1-3/D1-15;
IMPLEMENTATION_PROMPT:200/305 — naprawione (D2-38); pamiec sesji uzytkownika
(`MEMORY.md`, poza repo: `_laz_uklad`/`_storage_for`, "`_bboxes_intersect()`
uzywa `<`", liczby testow; do tego z L2: `N-34-130-D-d-2` to okolice Siemiatycz,
nie Bialystok, `N-34-141-A-a-1` okolice Wegrowa, nie Warszawa) — nie moja
dziedzina, do odswiezenia przez kontrolera/uzytkownika.

Hydrograf H-01..H-11 oraz S-1/S-2: przeniesione (zweryfikowane na kodzie
Kartografa i dokumentach Hydrografu) do `hydrograf-uwagi-migracyjne.md`;
dodatkowo znalezione przy weryfikacji: `output_dir=/data/nmt` Hydrografu da
w 0.7.0 podwojne `nmt` (`/data/nmt/nmt/pl_1992_5m_evrf2007/...`, zmierzone),
a `bootstrap.py:1079` szuka plikow nierekurencyjnym `glob("*.asc")`.

## 5. Poprawki spoza list D1/D2 (znalezione przy weryfikacji)

- `docs/DECISIONS.md` ADR-021 — errata K1: "os EPSG:2180 dla WFS zweryfikowana
  live" byla falszem (weryfikacja kolowa, L1 + test A/B kontrolera).
- `docs/DECISIONS.md` ADR-023 pkt 7 — errata (f).2 "kafel godlem = produkt 1:1"
  (TM33 jest warpem), S3 ciche przyciecie, limit `exportImage` (K6).
- `docs/DECISIONS.md` ADR-024 — errata K2 (brief), ADR-019 — N6.
- `docs/PROGRESS.md` "Nastepne kroki" pkt 2(c) — przestroga "blad serwerowej
  reprojekcji 1,25/4,92 m" opatrzona errata K2.
- `kartograf/transport/mosaic.py:102-111, :168-175` i `download/cutout.py:335-340`
  — docstringi twierdzily, ze tresc arkusza spoza siatki idzie "najblizszym
  sasiadem" i ze arkusze jednego produktu leza na jednej siatce (falsz na zywo
  — S5); poprawione z nota S5. Komunikat `logger.warning` (`mosaic.py:265-271`)
  to napis runtime — zostawiony (S5 w backlogu).
- `docs/IMPLEMENTATION_PROMPT.md` — Public API bez 8 nazw (jak D1-1), workery,
  N6, mozaikowanie wycinka.
- `kartograf/providers/pl/gugik.py:612-616, :629-632` — komentarze: fallback
  = K4; "(checklista live)" -> wynik testow na zywo (j).
- README/ARCHITECTURE: `horizontal_crs` pliku PL-2000 = EPSG:2180 (N8).
- CHANGELOG [0.7.0] Fixed: errata "1,25 m" (K2), siatka 1 m potwierdzona,
  straz OGC sprawdzona na zywo; nowa pozycja "Przejscie z 0.6.1 — co zrobic".

## 6. Fakty z L1-L7 dopisane do dokumentow

| Fakt | Gdzie |
|---|---|
| Faza siatki 1 m = k + 0,5 m w 84 arkuszach (EVRF2007 2019-2025, KRON86 2011-2018); `off_grid_sheets` dla 1 m zbedne | PROGRESS (fakty, pkt 12(f), backlog), ARCHITECTURE 4.3 krok 5, ADR-027 uzup. 2026-09-29, CHANGELOG Fixed, CLAUDE.md, mosaic/cutout docstringi |
| 5 m: 5k + 2,5 w cache Hydrografu, pod Wegrowem (48) i w Lebie; kampania 2022 pod Krakowem — kazdy arkusz inna faza (S5), Cieszyn 2/12 | PROGRESS, ARCHITECTURE 4.3 krok 5, ADR-027, SCOPE 2.1, README |
| Styk PL/CZ: GUGiK ~200 m w glab CZ, CUZK ~118 m w glab PL, pas ~310-350 m bez szczeliny, dziura Karkonosze 5 m 5,2 km², roznice -0,19..+0,14 m, trojstyk 0,17 m, Olza -0,55 m, siatki niewspolne | PROGRESS, ARCHITECTURE 4.6, SCOPE 3.1, ADR-027 |
| Odpowiedzi skorowidza: pusta = szablon MapServera 200 `text/html` 7721 B bez OGC; zla warstwa = 200 `text/xml` `LayerNotDefined`; straz I-2 w obie strony | PROGRESS, ARCHITECTURE 4.3 krok 4, ADR-020, CHANGELOG Fixed, komentarz `gugik.py` |
| Duzy wycinek: 1836/2394 arkuszy, 688/732 z danymi, 36 s / 109 s, ~1 GiB RSS, 9 fd, `ulimit -n 256` bit w bit, kompresja 6,58x, selekcja do ~3,7 km poza zadaniem, N9 | PROGRESS, ARCHITECTURE 4.3 kroki 3, 5, 7, ADR-010, ADR-027 |
| GUGiK zrywal 13-50 % polaczen (mozliwy wplyw 9 agentow z jednego IP); sesja z `Retry` 72/72 | PROGRESS, ARCHITECTURE 4.3 krok 4 (S1) |
| R5 potwierdzone: morze (Leba, Hel), granice CZ/DE/UA/BY/RU; `missing_sheets` != nodata (kampania 2025 przycina rastry, PL-SK do 82 %); woda ~0 m przy brzegu | PROGRESS, ARCHITECTURE 4.3 krok 4, CLAUDE.md, SCOPE 3.2, README (tabela sidecara), ADR-027 |
| Tryb listy bez R5 (S2); `auto` przycina do prostokata (S3); granice spoza rejestru = `pl`; Saksonia/Bogatynia w prostokacie CZ (N2); bbox poza prostokatami = blad bez sieci; kod 0 pod auto nie gwarantuje pliku z kazdego kraju | CLAUDE.md, README, SCOPE 3.2, ARCHITECTURE 4.2/4.6, ADR-023 errata |
| Obwiednia bboxa EPSG:4326 w 2180 przy 14°E: Osinow 18 vs 6 arkuszy, Slubice 12 vs 8 | ARCHITECTURE 4.3 krok 1 |
| Warp GDAL: `tolerance` 0,125 px + XSCALE; liczby 2,76 mm / 0,31 mm / 0,004 mm; 5 m do 0,13 m; zaleznosc od bboxa | ARCHITECTURE 4.3 krok 6, PROGRESS (fakty, backlog warp) |
| Zakladka arkuszy 5 m: wygrywa pierwszy w sortowaniu, nie najnowszy (do 9 cm), szew kampanii 1 px nodata | ARCHITECTURE 4.3 krok 5 |
| Sidecar arkusza bez URL/daty kampanii (LAZ ma `extra.url`); ASC bez CRS; ponowne uruchomienie bez sieci 0,4 s; LAZ zawsze odpytuje WFS (N7) | ARCHITECTURE 3.2/4.1/4.7 |
| exportImage: kafelkowanie 22 Mpx dziala, realny limit ~8 Mpx (K6), piksel 2,0004 m (N3), exportImage zawsze pochodna serwera (faza siatki DMR 5G (0,4; 1,88)), TM33 nie 1:1 | ARCHITECTURE 4.4/4.5, CLAUDE.md, SCOPE, README, ADR-023 errata, `--help` |
| K2: 4829 vs 1622, roznice 1622-4829 (Cheb 5,00 m, Cieszyn 1,15 m...), Karkonosze (-2,26; +0,61) vs (+0,38; -0,03) | ADR-024 errata, ARCHITECTURE 1/4.4/4.3 krok 6, CLAUDE.md, README, SCOPE, CHANGELOG Fixed, PROGRESS |
| EVRF2007 - Bpv +0,11..+0,15 m | `--vertical-crs` help |
| Pogranicze bez `--vertical-crs`: PL EVRF2007 + CZ Bpv; `--resolution 1m` pod auto zawsze PL; kafel `302_5550` ~93 % nodata | CLAUDE.md (przyklady), ARCHITECTURE 4.6 |
| Etykiety skal (7-czlonowe = "1:10000" / GUGiK 1:5000) w `--scale` | `--help` |
| Wyniki per pozycja checklisty (a)-(j), (k) PL-DE, (l) inne granice | PROGRESS "Nastepne kroki" pkt 12 |

## 7. Watpliwosci

1. **Komunikaty runtime** (`download_cmd.py:1644` "tryb godlowy dostarcza dane
   natywne 1:1" dla CZ, remedium PL-2000 "`--system 2000`" w `cutout.py`,
   ostrzezenie "najblizszym sasiadem" w `mosaic.py`) sa nieprawdziwe albo
   mylace, ale to napisy runtime — brief pozwala tylko na docstringi,
   komentarze i pomoc CLI, wiec zostawione do fali naprawczej (K2, K4, S5).
2. **Ostrzezenie w `--help` dla `--product`** (K1/K5): dopisalem je, bo LAZ
   pobiera zle dane po cichu, a uzytkownik CLI moze nie czytac README;
   napis trzeba usunac przy naprawie.
3. **Status "⚠️ Gotowy (znane bledy)"** w tabeli statusu PROGRESS — nowy
   znacznik w legendzie; jesli kontroler woli zachowac tylko dotychczasowe
   ikony, to czysto kosmetyczna zmiana.
4. **Numer "Nastepne kroki" pkt 15** (decyzja o naprawie) zamiast
   przenumerowania — zeby nie psuc odsylaczy "pkt 12-14" w dokumentach;
   pkt 13 wprost "czeka na decyzje z pkt 15".
5. **Oryginalne brzmienie checklisty pkt 12 (a)-(j)** zastapione statusami
   (kazdy status powtarza nazwe pozycji); pelny tekst sprzed zmiany jest
   w historii gita (6985765).
6. **D2-40** (jezyk docstringow i commitow): odnotowane jako rozjazd do decyzji
   wlasciciela — nie wybralem kierunku za niego.

## 8. Runda poprawek po przegladzie (RR-1..RR-15)

**Status: WYKONANE.** Zrodlo: `DOCS-REREVIEW-REPORT.md` (1 BLOKUJACE, 2 WAZNE,
12 DROBNE). Jeden commit **f52593a** `docs: poprawki po przegladzie fali
dokumentacji (RR-1..RR-15)` na f577d1c (niewypchniety; `origin/develop..develop`
= 221). Wynik: **15 NAPRAWIONE, 0 ODRZUCONE** — kazde znalezisko potwierdzone
w kodzie albo pomiarem; w trzech miejscach tekst poszedl dalej niz propozycja
(kolumna "Uwagi"). Zero zmian w `.py`, dokumenty historyczne nietkniete.

### 8.1 Tabela (plik:linia wg f52593a)

| RR | Waga | Werdykt | Gdzie | Uwagi |
|---|---|---|---|---|
| RR-1 | BLOKUJACE | NAPRAWIONE | CLAUDE.md:314-320; SCOPE.md:429-434; ARCHITECTURE.md:895-903; PROGRESS.md:967-968 | brzmienie wg propozycji + liczby L5 I/J (pod `auto` 6,2 km / 4 arkusze, z `--country pl` 8,9 km / 6); "Nysa" -> "Nysa Luzycka"; Opolszczyzna przeniesiona do N2 jako obszar PL w prostokacie CZ; dodatkowo PROGRESS pkt 12 (l): "`auto` == `pl`" -> "`auto` odpytal tylko PL" |
| RR-2 | WAZNE | NAPRAWIONE | ARCHITECTURE.md:729-735; pobocznie PROGRESS.md:1018-1022 i KNOWN-BUGS K2 | "1,1-3,4 m wzdluz granicy PL-CZ" z punktami pyproj (metoda w 8.2); "1,1-4,9 m" ujednolicone na "ok. 1-5 m" z rozbiciem wschod/zachod/granica |
| RR-3 | WAZNE | NAPRAWIONE | DECISIONS.md:414-419; PROGRESS.md:184, :1114-1123; KNOWN-BUGS S4 | wg symulacji przegladu + wniosek z kodu (`gugik.py:571-622` — wygrywa pierwsza warstwa z URL-em): arkusz z edycja 2026 i starsza w 2025/2024 dostaje po cichu te starsza |
| RR-4 | DROBNE | NAPRAWIONE | README.md:223-228, :275; CLAUDE.md:270-273; SCOPE.md:366-372; ARCHITECTURE.md:857-863; PROGRESS.md:180, :1073-1083; KNOWN-BUGS K6 | ponad propozycje: "pas N-S przechodzi" tylko do ~3,6 km szerokosci — `_splits` daje kafle najwyzej 4100 px wysokosci (1800 x 4100 = 7,4 Mpx, L4 S3b); pas 5 x 8 km N-S (2500 x 4000 px, bez ciecia, 10 Mpx) nie przejdzie, wiec samo "pas wydluzony N-S" byloby falszywe |
| RR-5 | DROBNE | NAPRAWIONE | CLAUDE.md:311-313; SCOPE.md:426-428; ARCHITECTURE.md:889-892; DECISIONS.md:732-734 | ARCHITECTURE wymienia, co jest przycinane: czesc CZ, PL `--bbox` (lista i wycinek), wycinek z `--geometry` (`_download_pl_geometry`, `download_cmd.py:1731-1763`) |
| RR-6 | DROBNE | NAPRAWIONE | README.md:232-233; CLAUDE.md:368; SCOPE.md:398-399 | — |
| RR-7 | DROBNE | NAPRAWIONE | ARCHITECTURE.md:51-60, :78-80, :399-402 | wyjatki polityki (`_bbox_to_wgs84` takze dla bboxa w 5514/3045; `_resolve_laz_bbox` -> `get_overall_bbox(..., "EPSG:2180")`) sprawdzone w kodzie; wybor = `min` po `accuracy`; sesja per arkusz, zapytania warstw jednego arkusza dziela ja |
| RR-8 | DROBNE | NAPRAWIONE | DECISIONS.md:1273-1274; ARCHITECTURE.md:588-590 | — |
| RR-9 | DROBNE | NAPRAWIONE | ARCHITECTURE.md:633-634 | — |
| RR-10 | DROBNE | NAPRAWIONE | PRD.md:239-241; PROGRESS.md:1006-1008 | pomiar powtorzony: srodek godla (771037, 509635) -> 369,7 km; bbox (531500, 384000) -> 208,6 km |
| RR-11 | DROBNE | NAPRAWIONE | PROGRESS.md:1080 | `client.py:36-37` |
| RR-12 | DROBNE | NAPRAWIONE | PROGRESS.md:146-147 | — |
| RR-13 | DROBNE | NAPRAWIONE | DECISIONS.md:379-380 | — |
| RR-14 | DROBNE | NAPRAWIONE | PROGRESS.md:1030-1033 (checkbox K2) | — |
| RR-15 | DROBNE | NAPRAWIONE | hydrograf-uwagi-migracyjne.md:122-127 (B4) | `no_coverage` = podzbior `failed` (`download/manager.py:72-74`) |

Tabela faktow w sekcji 6 tego raportu ("granice spoza rejestru = `pl`") opisuje
stan sprzed tej rundy — skorygowane przez RR-1.

### 8.2 K2 — metoda pomiaru

pyproj z `.venv` (skrypt w scratchpadzie sesji, bez sieci):
`TransformerGroup("EPSG:4156", "EPSG:4258", always_xy=True,
allow_ballpark=False)` daje trzy operacje: "S-JTSK to ETRS89 (1)" = EPSG:1622
(Czechy, 1,0 m), "(3)" = EPSG:4829 (Slowacja, 0,5 m), "(4)" (1,0 m); regula
`crs.py` (`min` po `accuracy`) wybiera (3). Przesuniecie = odleglosc
geodezyjna na GRS80 miedzy wynikami (1) i (3) dla tego samego punktu (wariant
"tam przez (1), z powrotem przez (3)" daje te same liczby +/- 0,01 m).
Granica PL-CZ: Jaworzynka 1,13; Cieszyn 1,15; Raciborz 1,35; Glucholazy 1,60;
Miedzylesie 1,64; Kudowa 2,16; Karkonosze (Sniezka) 2,73; Swieradow 3,12;
Bogatynia/Hradek 3,40 m. Wnetrze CZ: Brno 0,98; Ostrawa 1,06; Praga 3,15;
Cheb 4,87; kafel `302_5550` 4,98 (L4: 5,00); zachodni kraniec (12,09°E)
5,15 m. Stad "1,1-3,4 m" przy granicy i "ok. 1-5 m" dla calych Czech.

### 8.3 Backlog "Do naprawy" (pkt 3 zlecenia, bez nowych ID)

Dopisane jako "Przy naprawie:" w istniejacych checkboxach `docs/PROGRESS.md`:

- **K1** (:1011-1013): komentarz `gugik_laz.py:363-365` ("Verified live.")
  falszywy; usunac ostrzezenie K1 z pomocy `--product` (`cli/_parser.py:176-177`)
  i noty "znany blad K1" z dokumentacji.
- **K2** (:1030-1038): komunikat `cli/download_cmd.py:1643-1644` ("tryb godlowy
  dostarcza dane natywne 1:1" — falsz dla TM33, RR-14); komentarze
  `providers/cuzk/dmr.py:86-88`, `transform/crs.py:134-140` (`KNOWN_PATHS`)
  i `:159` ("+0,12..+0,14 m", zmierzone 0,11-0,15 m); **ponad liste
  przegladu:** "5514->3045 przesuwa tresc o 1,25 m" w `dmr.py:54-55`
  i `:270-271` (diagnoza ADR-024 do weryfikacji razem z K2).
- **K4** (:1063-1066): remedium `download/cutout.py:306-311` ("np. z --system
  2000") prowadzi do arkusza-dziecka.
- **K5** (:1071-1072): usunac ostrzezenie K5 z pomocy `--product`.
- **S5** (:1129-1132): `logger.warning` "... przepisana najblizszym sasiadem"
  (`transport/mosaic.py:265-271`).
- **K6**: w `providers/cuzk/client.py` brak komentarza sprzecznego z K6
  (`MAX_EXPORT_*` bez komentarza, docstring `:127` "kafelkowanie nad limitem"
  mowi o limicie deklarowanym) — nic ponad istniejace `:36-37`, `:142`,
  `_tile_grid`.

### 8.4 Pliki robocze (nie commitowane)

- `KNOWN-BUGS.md`: wiersze K2 (ok. 1-5 m z rozbiciem), K6 (regula z RR-4, pas
  N-S do ~3,6 km, `client.py:36-37`), S4 (RR-3), N9 ("przy typowym uzyciu" ->
  warunek: wolajacy liczy `estimate_pl_cutout_bytes` sam; CLI uzywa
  `cutout.estimated_bytes`, `download_cmd.py:1034`); dopisana sekcja
  "## Korekty po przegladzie (2026-09-29)" (metoda i liczby K2, uzasadnienia
  K6/S4/N9). ID i wagi bez zmian; historia opisow nie przepisana.
- `hydrograf-uwagi-migracyjne.md`: B4 (RR-15), dluga linia zawinieta.

### 8.5 Brama

- `.venv/bin/python -m pytest tests/ -q -m "not live" -p no:cacheprovider` ->
  **1861 passed, 8 deselected** (28,1 s).
- `git diff --stat f577d1c..f52593a` -> 7 plikow, wylacznie dokumentacja
  (CLAUDE.md, README.md, docs/ARCHITECTURE.md, docs/DECISIONS.md, docs/PRD.md,
  docs/PROGRESS.md, docs/SCOPE.md), +154/-76; zero `.py` (ruff/mypy bez
  zmian — nie dotyczy).
- `docs/DECISIONS.md`: 1324 CRLF / 0 LF (przed runda 1316 / 0), plik konczy
  sie CRLF.
- Pliki ASCII (CLAUDE, ARCHITECTURE, DECISIONS, PROGRESS): w dodanych liniach
  tylko "—" i "°" (juz obecne w tych plikach); README/SCOPE/PRD z diakrytykami;
  zadna dodana linia nie zaczyna sie od ">" (ryzyko cytatu w Markdown).

### 8.6 Watpliwosci

1. **K2 — zakres zalezy od punktu**: Cheb 4,87 m (przeglad), `302_5550`
   5,00 m (L4), skraj zachodni 5,15 m — dlatego "ok. 1-5 m", a nie
   "1,1-5,0 m".
2. **RR-4 szerzej niz propozycja** (pas N-S tylko do ~3,6 km) i **RR-5
   w ARCHITECTURE** (przycinany jest tez tryb listy `--bbox`) — zgodne
   z kodem (`_splits` w `client.py:278-283`, `_dispatch_area` w `download_cmd.py:460`), ale to tresc
   spoza tekstu przegladu.
3. **Nota K2 o `dmr.py:54-55`/`:270-271`** (1,25 m jako "blad serwera") —
   dopisana ponad liste przegladu; te komentarze przecza erracie ADR-024 tak
   samo jak te, ktore przeglad wymienil.
