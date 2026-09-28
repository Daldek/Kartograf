# Finalny review calej fali (Kartograf, develop, 0bf3d9f..fa1f771)

Jestes Senior Code Reviewerem. Oceniasz CALA fale naprawcza (18 zadan, 22 commity),
nie pojedyncze zadanie — kazde zadanie przeszlo juz wlasny review. Twoja wartosc
dodana to to, czego review per zadanie NIE mogl zobaczyc: defekty miedzyzadaniowe,
zgodnosc calosci z rozstrzygnieciami R1-R6, zgodnosc kodu z dokumentacja, triaz
odlozonych drobiazgow.

## Co zostalo zbudowane

Fala naprawcza po review max z 2026-08-30 (15 znalezisk w torze wycinka PL
`--target-crs` i ukladzie `data/`) + wycinek PL jako API biblioteki:
- `transport/mosaic.py`: leniwe otwieranie zrodel (limit deskryptorow), crop na
  siatce zrodel (`snap_to_source_grid=`, siatka wiekszosci + ostrzezenie),
  normalizacja zrodel przez VRT w `/vsimem/` (`assign_crs=`, `dtype=`).
- `core/sheet_parser.py`: obwiednia WGS84 z poludnikiem osiowym (fakt 8).
- `exceptions.NoCoverageError(DownloadError)`, `gugik._get_opendata_url`
  (trojstan: brak pokrycia / niepewny / usluga niedostepna), `DownloadResult.no_coverage`,
  `DownloadManager.expand_sheets()/download_sheets()`.
- NOWY `download/cutout.py` (API: `prepare_pl_cutout` -> `select_pl_cutout_sheets` ->
  `run_pl_cutout`, `download_pl_cutout`, `build_pl_cutout`, `write_pl_cutout_sidecar`,
  kontrola dysku, R5 missing_sheets, odrzut arkuszy PL-2000, sprzatanie `bbox/`);
  CLI `_download_pl_cutout` jako cienka nakladka.
- CLI: obwiednia geometrii w ukladzie czeskim (`_geometry_envelope`), sprzatanie
  pustych katalogow w torze CZ (tylko CLI), LAZ przez `LazTile.uklad` +
  `FileStorage.get_raw_path(uklad=)`.
- `storage.py`: `prune_empty_dirs`, szablony segmentow z rejestru; `descriptor.py`:
  pusty wymiar -> `ValidationError`.
- Dokumentacja: ARCHITECTURE 4.3 przepisana, ADR-027 uzupelnienia, CLAUDE.md,
  CHANGELOG, README (przyklad biblioteki), SCOPE.

## Wejscia (czytaj w tej kolejnosci)

1. `COMMON-CONTEXT.md` (w tym katalogu) — R1-R6, fakty 1-11, Global Constraints.
   To wiazaca soczewka. R1-R6 sa decyzjami uzytkownika i sa nadrzedne wobec raportu
   review max tam, gdzie sie roznia.
2. Spec: `docs/research/2026-08-28-uklad-data-target-crs-pl/2026-08-30-code-review-max.md`
   (15 znalezisk z file:line — czego fala miala dotyczyc).
3. Plan (argument specu; czytaj sekcje, ktorych potrzebujesz, nie musisz calosci):
   `docs/superpowers/plans/2026-09-28-fala-review-max-i-wycinek-biblioteczny.md` —
   "Przeglad zadan", "Poza zakresem", "Review Focus", "Zakonczenie".
4. Pakiet diffu calej fali (bez planu i raportow research):
   `review-final-0bf3d9f..fa1f771.diff` (~354 KB — czytaj partiami, powiedz w raporcie,
   ze tak zrobiles). Commity:
   `git log --oneline 0bf3d9f..fa1f771` w `/home/claude-agent/workspace/Kartograf`.
5. Ledger: `progress.md` — WSZYSTKIE linie `Ruling:`, `minor (deferred)`,
   `DEFERRED-LOAD-BEARING`, `note`. Raporty zadan: `task-N-report.md` (wedlug potrzeby).

## Stan bramy jakosci przy fa1f771 (zmierzony przez implementera Zad. 17, nie powtarzaj)

`.venv/bin/python -m pytest tests/ -q -m "not live"`: 1854 passed, 8 deselected;
pokrycie 92,87 %; ruff check + format czyste; mypy 32 bledy = baseline (diff listy pusty).
E2E offline na realnych arkuszach 5 m (skrypty w `e2e/`) odtworzone niezaleznie przez
reviewera Zad. 17.

## Czego szukasz (nazwane ryzyka — jedna skupiona kontrola na ryzyko, w raporcie:
ryzyko + co sprawdziles + wynik)

A. **Defekty miedzyzadaniowe w torze wycinka PL** — kompozycja: selekcja (+1 px, suma
   R-01, poludnik osiowy) -> kontrola dysku -> `download_sheets` -> klasyfikacja R5
   -> odrzut PL-2000 -> mozaika (sort, snap, VRT, kompresja przy warpie, `tiled=False`
   przy owijaniu) -> warp -> sidecar -> sprzatanie. Czy kolejnosc krokow w
   `run_pl_cutout` / `download_pl_cutout` / CLI `_download_pl_cutout` jest spojna
   i czy kazdy wyjatek konczy sie wlasciwie (biblioteka: wyjatek; CLI: kod 1, nigdy
   traceback; `--country auto`: czesciowy sukces = kod 0 + `Warning:`).
B. **R5 end-to-end**: czy KAZDA droga do `NoCoverageError` to naprawde "wszystkie
   warstwy odpowiedzialy i zadna nie ma arkusza". Ledger ma pozycje
   DEFERRED-LOAD-BEARING (odpowiedz 2xx bez URL, np. OGC ServiceExceptionReport /
   strona bledu proxy z HTTP 200 -> dzis NoCoverageError -> trwala dziura nodata).
   Oceń, czy to Critical/Important przed checklista live, i jaka straz jest wlasciwa
   (sprawdz na kodzie `_get_opendata_url` i testach, jak wyglada "czysta pusta"
   odpowiedz GetFeatureInfo w fixturach).
C. **Wspolny `mosaic_and_crop` a tor CZ**: tor CZ jest zamrozony
   (`providers/cuzk/*` bez zmian). Czy wywolanie CZ (`providers/cuzk/client.py`, bez
   nowych parametrow) zachowuje sie identycznie jak przed fala (leniwe zrodla to jedyna
   zmiana, ktora go dotyczy).
D. **Kod vs dokumentacja**: ARCHITECTURE 4.3, ADR-027 (+ uzupelnienia 2026-09-28),
   CLAUDE.md (punkty o `--target-crs`, drzewo modulow, uklad data/), CHANGELOG 0.7.0,
   README (przyklad biblioteki), SCOPE. Kazde twierdzenie o zachowaniu, ktore wybierzesz
   do sprawdzenia, weryfikuj na zywym kodzie (w tej galezi dokumenty klamaly czesciej
   niz kod — w historii projektu 8 razy).
E. **Zgodnosc z Global Constraints**: tor CZ i `transform/raster.py` bez zmian
   (`git diff 0bf3d9f..fa1f771 --stat -- kartograf/providers/cuzk kartograf/transform/raster.py`);
   brak shimow zgodnosciowych; semantyka, ktorej nie wolno zmienic (lista w
   COMMON-CONTEXT); CHANGELOG mowi o przebudowie z `--force`.
F. **Konsument biblioteki — Hydrograf** (tylko odczyt: `/home/claude-agent/workspace/Hydrograf`,
   NIE modyfikuj niczego, takze cache): jedna kontrola — czy Hydrograf importuje/uzywa
   czegos, co fala zmienila albo usunela (np. prywatne `_laz_uklad`, `_PL_*` z CLI,
   `FileStorage._*_SUBDIRS`, sygnatura `mosaic_and_crop`, tresc komunikatu "No NMT ...
   data available", semantyka `DownloadManager`). Wynik: lista trafien albo "brak".
G. **Testy**: czy nowe testy bronia zachowania (nie mockow) w miejscach kompozycji
   z punktu A — szczegolnie tam, gdzie testy CLI mockuja `DownloadManager` (MagicMock
   omija `expand_sheets`/kontrole dysku). Wskaz luki, ktore realnie moga przepuscic
   regresje, nie teoretyczne.

## Triaz odlozonych drobiazgow z ledgera (OBOWIAZKOWY)

Dla KAZDEJ linii `minor (deferred)` i `DEFERRED-LOAD-BEARING` w `progress.md`
(oraz minorow review Zad. 17 na koncu ledgera) daj jedna linie:
`<zadanie>: <skrot> -> NAPRAW TERAZ | ZOSTAW (backlog) | JUZ NIEAKTUALNE — <powod>`.
"NAPRAW TERAZ" = przed checklista live / wydaniem 0.7.0 (fala naprawcza zaraz po
Twoim review naprawi wszystko z tej kategorii jednym dispatchem).

## Mutacje

Zasada projektu: znalezisko o tescie, ktory "niczego nie broni", udowodnij mutacja
(zmien kod produkcyjny, skupiony test -> PASS mimo zepsucia; przywroc
`git checkout -- <plik>`, `git status` czysty). Mozesz wykonac kilka kontrolowanych
mutacji; kazda przywroc przed nastepna. Poza tym drzewo robocze, indeks i HEAD tylko
do odczytu. Na koniec `git status --short` MUSI byc pusty (poza katalogiem
`.superpowers/`, ktory jest ignorowany).

## Zasady

- Nie uruchamiaj subagentow. Rob wszystko sam; jesli diff jest za duzy na jeden
  przebieg, rob przebiegi i powiedz to.
- Spec to dokument wizji: dla zachowania, o ktorym milczy, oceniaj wg oczekiwan
  rozsadnej osoby uzywajacej narzedzia (uzytkownik pobiera godla albo bboxy, takze
  przygraniczne PL/CZ; Hydrograf wola biblioteke).
- Kalibracja: Critical = zle dane/utrata danych/zepsuta funkcja; Important = wada
  architektury, zle obsluzony blad, luka testowa realnie przepuszczajaca regresje,
  dokument opisujacy zachowanie odwrotne do kodu; reszta Minor. Rzecz wymuszona przez
  plan, ktora uwazasz za defekt — oznacz "plan-mandated".
- "Declined to judge": przed werdyktem wypisz kazde zachowanie, ktore rozwazyles
  i odlozyles jako poza planem/specem, po jednej linii z powodem.

## Wyjscie

Pelny raport zapisz do `final-review-report.md` (w tym katalogu) w formacie:
### Strengths / ### Issues (#### Critical / #### Important / #### Minor — kazdy:
file:line, co jest zle, dlaczego to wazne, jak naprawic) / ### Nazwane ryzyka A-G
(co sprawdzone, wynik) / ### Triaz ledgera / ### Mutacje (co, wynik) /
### Declined to judge / ### Recommendations / ### Assessment
(**Ready to merge?** Yes | No | With fixes + 1-2 zdania).

Zwroc w odpowiedzi TYLKO: werdykt, liczby (Critical/Important/Minor), po jednej linii
na kazde Critical/Important, liczbe pozycji NAPRAW TERAZ z triazu, i potwierdzenie
czystego `git status`.
