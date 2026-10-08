# Artefakty sesji: fala naprawcza po review max + wycinek PL w bibliotece (2026-09-28)

Zapis procesu wdrozenia planu
`docs/superpowers/plans/2026-09-28-fala-review-max-i-wycinek-biblioteczny.md`
(18 zadan team-driven SDD + pre-flight planu + finalny review calej fali + fala
finalna + re-review). Spec: raport review max
`docs/research/2026-08-28-uklad-data-target-crs-pl/2026-08-30-code-review-max.md`
+ rozstrzygniecia uzytkownika R1-R6 i fakty 1-11 w planie. Skopiowane
z gitignorowanego workspace'u SDD przed jego usunieciem (w etapie 1 ledger
przepadl razem z workspace'em).

| Plik | Co zawiera |
|---|---|
| `sdd-ledger.md` | Dziennik sesji: dispatche, wyniki review, **wszystkie rulingi kontrolera** z kosztem pomylki, drobiazgi odlozone i zaparkowane |
| `preflight-report.md` | Symulacja CALEGO planu na kopii repo przed Zad. 1: P-01..P-21 (2 blokujace, 5 waznych, 14 drobnych) — poprawki naniesione na plan (dbc5926) |
| `task-reports/task-N-report.md` | Raporty implementerow Zad. 1-17: RED/GREEN, dowody mutacyjne, pomiary, rundy poprawek |
| `e2e/` | Skrypty i wyniki E2E offline na realnych arkuszach 5 m (Zad. 17): `e2e_pl_cutout.py` (scenariusze a-f), `e2e_warp_diagnostics.py` (skala resamplingu GDAL), `*.json` — zrodlo liczb w ARCHITECTURE 4.3, ADR-027 i PROGRESS |
| `final-review-brief.md` | Zlecenie finalnego review calej fali: nazwane ryzyka A-G, obowiazkowy triaz ledgera |
| `final-review-report.md` | Finalny review (fable): 0 Critical / 2 Important / 11 Minor; triaz odlozonych drobiazgow (NAPRAW TERAZ / ZOSTAW / NIEAKTUALNE) z uzasadnieniami |
| `final-fix-brief.md`, `final-fix-report.md` | Fala finalna (opus, 6 commitow 84bd0a8..61f60de): test `--force`/`--workers` CLI, straz raportu wyjatku OGC w odpowiedzi 2xx, uklad czeski bez wzgledu na wielkosc liter, docstringi, komendy testow offline, precyzja ARCHITECTURE; uwaga o nieswiezym `.pyc` przy mutacjach |
| `final-rereview-report.md` | Re-review fali finalnej (opus): 6/6 naprawione, 7 mutacji (w tym wlasna, ktora przezyla — N-1), 4 drobiazgi zaparkowane |

## Co warto stad zapamietac

1. **Przeslanka raportu review byla falszywa, a blad powazniejszy, niz zmierzyl.**
   Raport zakladal arkusze GUGiK "kotwiczone na calkowitych wielokrotnosciach
   piksela"; pomiar 1977 realnych arkuszy 5 m pokazal narozniki na 5k + 2,5 m,
   wiec przesuniecie o 0,5 px dotyczylo takze bboxow o CALKOWITYCH
   wspolrzednych. Siatke bierzemy z transformacji zrodel, nie z zalozen.
2. **Pomiar na realnych danych wyciagnal piec defektow spoza raportu** (Int32,
   `CRS mismatch` przy `.prj` Hydrografu, poludnik osiowy 19°E, arkusze PL-2000
   pod godlem PL-1992, polpikselowa siatka) — zadnego nie bylo widac na
   syntetycznych fixturach z calkowitymi, stykajacymi sie arkuszami.
3. **Finalny review znow znalazl to, czego review per zadanie nie widzial**:
   wiazanie `--force` z CLI do biblioteki bez testu (mutacja przechodzila
   312/312 — `--force` bylby cichym no-opem akurat tam, gdzie CHANGELOG kaze
   go uzyc) i odpowiedz bledu OGC z HTTP 200 liczona jako brak pokrycia (pod R5:
   trwala dziura nodata).
4. **Proces mutacyjny ma dwie pulapki:** `git checkout` na niezacommitowanej
   pracy skasowal implementacje (Zad. 3 — od tej pory mutacje wylacznie PO
   commicie), a mutacja zachowujaca rozmiar pliku i przywrocenie w tej samej
   sekundzie uruchamiaja nieswiezy `.pyc` (walidacja po mtime w sekundach +
   rozmiarze) — przebiegi mutacyjne z `PYTHONPYCACHEPREFIX=$(mktemp -d)`.
