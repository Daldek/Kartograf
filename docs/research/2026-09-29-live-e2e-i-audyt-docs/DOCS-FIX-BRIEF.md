# Fala poprawek dokumentacji po testach na zywo i audycie (Kartograf, 2026-09-29)

**Kontekst.** Galaz `develop`, HEAD 152c31e. Uzytkownik zapytal, czy CALA dokumentacja dotknieta
zmianami (uklad `data/` + `--target-crs` PL, fala "review max" z wycinkiem PL w bibliotece) jest
aktualna, i zlecil testy na zywych danych (centrum, morze, pogranicza PL-CZ, PL-DE i inne).
Wyniki (wszystko w tym katalogu `.superpowers/sdd/2026-09-29-live-e2e-i-docs/`):
- audyt dokumentacji: `D1-docs-uzytkownik-report.md` (35 znalezisk), `D2-docs-architektura-report.md`
  (55 znalezisk Kartografu + 11 dotyczacych dokumentacji Hydrografu);
- testy na zywo: `L1`..`L7-*-report.md` (sekcje "Zachowanie do udokumentowania" i odpowiedzi na
  checkliste PROGRESS pkt 12 (a)-(j));
- lista znanych bledow KODU: `KNOWN-BUGS.md` (K1-K6, S1-S5, N1-N9, H1) — **czekaja na decyzje
  uzytkownika; w tej fali NIE naprawiasz kodu.**

Twoje zadanie: jedna fala poprawek DOKUMENTACJI, po ktorej dokumenty biezace mowia prawde o kodzie
i o wynikach testow na zywo. Repo: `/home/claude-agent/workspace/Kartograf`. Hydrograf — NIE ruszasz.

## Zasady

1. **Znaleziska D1/D2:** kazde zweryfikuj na ZYWYM kodzie (audytor mogl sie mylic) i:
   - popraw tekst (propozycje audytorow to punkt wyjscia, nie wyrocznia), albo
   - jesli dotyczy zachowania objetego bledem z `KNOWN-BUGS.md`: NIE opisuj blednego zachowania jako
     zamierzonego i NIE przepisuj opisu projektu, ktory zmieni naprawa — usun/popraw falszywe
     twierdzenie i dodaj krotka note "znany blad <ID> (testy na zywo 2026-09-29) — PROGRESS, 'Znane
     bledy'", albo
   - odrzuc z dowodem (plik:linia / wynik polecenia), jesli audytor sie myli.
   Dokumenty historyczne (`docs/research/`, `docs/superpowers/`, datowane sekcje PROGRESS/CHANGELOG
   starszych wersji) zostaw.
2. **Pliki kodu:** wolno zmieniac WYLACZNIE tekst (docstringi, komentarze, napisy pomocy CLI
   w `kartograf/cli/_parser.py`) — zero zmian zachowania. NIE ruszaj plikow zwiazanych z bledami
   K1/K2/K6 (`kartograf/providers/pl/gugik_laz.py`, `kartograf/providers/cuzk/*`,
   `kartograf/transform/crs.py`) — ich komentarze zmieni fala naprawcza.
3. **`docs/PROGRESS.md`:** nowa podsekcja na gorze "Ostatnia sesja": "Testy na zywych danych
   + audyt dokumentacji (2026-09-29)": co przetestowano (obszary, tryby; PASS/FAIL/UWAGA per raport),
   zmierzone fakty (m.in. faza siatki 1 m = k+0,5 w 84 arkuszach; 5 m = 5k+2,5 w cache Hydrografu
   i w Lebie, ale rozne fazy w kampanii 2022 pod Krakowem; styk PL/CZ: GUGiK ~200 m w glab CZ,
   CUZK ~118 m w glab PL, pas wspolny ~310-350 m, roznice wysokosci -0,19..+0,14 m, trojstyk
   mediana 0,17 m; pusta odpowiedz GetFeatureInfo = szablon MapServera HTTP 200 text/html bez
   znacznikow OGC, zla warstwa = HTTP 200 text/xml `LayerNotDefined` — straz I-2 potwierdzona
   w obie strony; duzy wycinek 1836/2394 arkuszy: 36 s / 109 s, ~1 GiB RSS, 9 fd, `ulimit -n 256`
   bit w bit; GUGiK zrywal 13-50 % polaczen podczas testow — mozliwy wplyw 9 agentow z jednego IP),
   podsekcja **"Znane bledy (testy na zywo 2026-09-29)"** = tabela z `KNOWN-BUGS.md` (ID, waga, jedno
   zdanie, odsylacz do raportu w `docs/research/2026-09-29-live-e2e-i-audyt-docs/` — kontroler
   skopiuje tam raporty pod tymi samymi nazwami). "Nastepne kroki": pkt 12 — status kazdej pozycji
   (a)-(j) z wynikiem i odsylaczem; dopisz pozycje dla pogranicza PL-DE i pozostalych granic
   (wykonane) oraz nowa pozycje "decyzja uzytkownika o naprawie K1-K6/S1-S5 przed wydaniem 0.7.0";
   pkt 13 (wydanie) — czeka na te decyzje. Backlog: pozycje, ktore stały sie znanymi bledami, oznacz
   odsylaczem do ID (bez duplikowania opisu).
4. **README.md:** krotka sekcja "Znane problemy (0.7.0-dev)" z bledami widocznymi dla uzytkownika
   (K1 — nie uzywac `--product laz` do czasu naprawy; K2 — przesuniecie danych CZ 1-5 m; K3/K4 —
   mozliwa starsza lub inna edycja arkusza; K5 — orto CIR; K6 — duzy bbox CZ; S2 — tryb listy na
   morzu/granicy konczy sie kodem 1) — rzeczowo, bez dramatyzowania; plus poprawki z D1.
5. **CLAUDE.md:** poprawki z D1/D2 (m.in. falszywe "1:1 w trybie godlowym TM33", limit
   `exportImage` — "deklarowany 15000 x 4100; realnie ~8 Mpx — znany blad K6"), fakty o zachowaniu
   na pograniczach (PL-DE, SK/UA/BY/LT/RU: arkusze po stronie obcej -> `missing_sheets` w wycinku,
   kod 1 w trybie listy — S2; `auto` przycina do prostokata kraju — S3) — zwiezle, CLAUDE.md
   steruje kazda sesja; nie rozdmuchuj.
6. **docs/DECISIONS.md:** ADR-024 — errata 2026-09-29 (roznice 1,25 m / 4,92 m przypisane serwerowi
   CUZK odpowiadaja roznicy EPSG:1622 - EPSG:4829; wybor operacji do rewizji — K2); ADR-023/027
   i pozostale — wg D2. Nie przepisuj ADR-ow, dopisuj datowane errata/uzupelnienia.
7. **docs/CHANGELOG.md [0.7.0]:** usun sprzecznosci (np. wpis etapu 1 o odrzucaniu `--target-crs`
   z PL — oznacz jako zastapiony przez ADR-027); dodaj w sekcji migracji/Breaking wyrazne uwagi dla
   uzytkownikow 0.6.1 (m.in. Hydrograf): stare katalogi `nmt_5m/`/`nmt_1m/` -> nowe segmenty (co zrobic
   z istniejacym cache), import `kartograf.providers.bdot10k` -> `kartograf.providers.pl.bdot10k`
   (i inne przeniesione moduly), publiczne `download_pl_cutout` zamiast skladania `mosaic_and_crop`;
   zweryfikuj na kodzie. Bez sekcji "Known issues" w CHANGELOG (znane bledy zyja w PROGRESS/README).
8. **docs/ARCHITECTURE.md, docs/SCOPE.md, docs/PRD.md:** wg D1/D2 + fakty z testow (zachowanie na
   pograniczach i przy morzu, R5 w wycinku vs brak tolerancji w trybie listy, faza siatki 1 m).
9. **Uwagi dla Hydrografa** (D2, 11 pozycji): NIE zmieniaj repo Hydrografu. Zapisz je jako plik
   `hydrograf-uwagi-migracyjne.md` w katalogu tego briefu (kontroler skopiuje do `docs/research/`)
   — co w dokumentacji/kodzie Hydrografu trzeba zmienic przy przejsciu na Kartograf 0.7.0.
10. Liczby wpisuj tylko zmierzone (z raportow albo wlasnym pomiarem). Polski bez diakrytykow tam,
    gdzie plik tak pisze; README ma diakrytyki.

## Brama i commity

- `.venv/bin/python -m pytest tests/ -q -m "not live"` (zielono; teksty pomocy CLI moga byc
  sprawdzane w testach), `ruff check` + `ruff format --check` na `kartograf/ tests/`, mypy bez nowych
  bledow (32 = baseline; porownaj liste `plik: komunikat`).
- Commity Conventional Commits (np. `docs(progress): ...`, `docs: ...`), pogrupowane logicznie,
  stopka `Co-Authored-By:` wg instrukcji atrybucji z TWOJEGO system-remindera. Nie commituj
  `.superpowers/` ani `e2e-data/`. Nie pushuj.

## Raport

`DOCS-FIX-REPORT.md` (ten katalog): tabela WSZYSTKICH znalezisk D1 i D2 -> NAPRAWIONE (plik:linia) /
OZNACZONE jako znany blad (ID) / ODRZUCONE (dowod) / POMINIETE (powod); lista faktow z L1-L7 dopisanych
do dokumentow; commity; brama. Odpowiedz kontrolerowi krotko (<= 15 linii): status, commity, liczby
(naprawione/oznaczone/odrzucone/pominiete), watpliwosci. Nie uruchamiaj subagentow.
