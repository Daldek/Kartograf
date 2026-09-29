# Artefakty sesji: testy na zywych danych + audyt dokumentacji (2026-09-29)

Uzytkownik zapytal, czy pobieranie przetestowano na realnych danych (centrum kraju, pas
morski, pogranicza — nie tylko PL-CZ, takze PL-DE, gdzie danych niemieckich nie
obslugujemy) i czy zaktualizowano cala dokumentacje dotknieta falami 2026-08-28
(uklad `data/` + `--target-crs` PL) i 2026-09-28 (fala review max + wycinek PL
w bibliotece). Nie byly. Sesja: 7 agentow testow na zywo (L1-L7) i 2 audytorow
dokumentacji (D1, D2) rownolegle, potem jedna fala poprawek DOKUMENTACJI (12 commitow
`57ef96b..f577d1c`), jej niezalezny przeglad, runda poprawek (`f52593a`) i re-review
(resztki poprawione przez kontrolera w `fb3cede`). **Kod bez zmian zachowania** — bledy kodu
zebrane w `KNOWN-BUGS.md`, w repo zyja jako backlog "Do naprawy — testy na zywych danych
2026-09-29" w `docs/PROGRESS.md` (naprawa = nastepna fala).

Pliki skopiowane z gitignorowanego workspace'u SDD
(`.superpowers/sdd/2026-09-29-live-e2e-i-docs/`); `sdd-ledger.md` to jego `progress.md`.
Pobrane rastry, kafle i skrypty agentow (8,6 GB) zostaly w gitignorowanym
`e2e-data/2026-09-29-live/` — tu tylko surowe odpowiedzi skorowidza (`gfi/`).

| Plik | Co zawiera |
|---|---|
| `sdd-ledger.md` | Dziennik sesji: dispatche, wyniki kazdego agenta, rulingi kontrolera z kosztem pomylki, decyzje uzytkownika |
| `LIVE-COMMON.md` | Wspolne zasady agentow testow na zywo: repo tylko do odczytu, osobny katalog roboczy per agent (`.kartograf_cache.db` powstaje w CWD), `--workers 2`, male obszary, sprawdzenie pokrycia przed uznaniem bledu, weryfikacja tresci |
| `DOCS-COMMON.md` | Wspolne zasady audytorow dokumentacji; kategorie FALSZ / NIEAKTUALNE / BRAK / NIEPRECYZYJNE / NIESPOJNE |
| `L1-centrum-produkty-report.md` | Spytkowice k. Krakowa: godla PL-1992 (1 m EVRF2007/KRON86, 5 m, rozwijanie 1:25000/1:50000), PL-2000, NMPT, orto, LAZ, lista `--bbox`, `pytest -m live` — 8 PASS / 5 UWAGA / 7 FAIL |
| `L2-wycinki-siatka-report.md` | Wycinki 2180/5514/3045 (1 m k. Siemiatycz, 5 m k. Wegrowa), bbox calkowity/ulamkowy, `--force`, biblioteka vs CLI; faza siatki 1 m w 12 miastach (84 arkusze) — 21 PASS / 5 UWAGA / 6 FAIL |
| `L3-morze-report.md` | Leba (5 m, 1 m, cel 5514), Hel, bbox nad morzem, Rozewie; (j) surowe odpowiedzi skorowidza i straz raportu wyjatku OGC — 7 PASS / 4 UWAGA / 3 FAIL |
| `L4-pogranicze-cz-report.md` | Cieszyn, Karkonosze, Beskid Slaski, Raciborz; godla TM33/SM5; styk danych PL/CZ (dane do R6); kafelkowanie `exportImage` — 10 PASS / 4 UWAGA / 4 FAIL |
| `L5-pogranicze-de-report.md` | Slubice, Zgorzelec, trojstyk PL-CZ-DE, Sieniawka, Osinow Dolny, Berlin — 7 PASS / 5 UWAGA / 2 FAIL |
| `L6-inne-granice-report.md` | PL-SK, PL-UA, PL-BY, PL-LT, PL-RU x tryb listy / wycinek — 9 PASS / 1 UWAGA |
| `L7-duzy-wycinek-report.md` | Offline, cache Hydrografu: N-33-118..132 (103 x 77 km), 1836/2394 arkuszy, cele 2180/5514, `ulimit -n 256` — 4 PASS |
| `D1-docs-uzytkownik-report.md` | Audyt README, CLAUDE.md, SCOPE, PRD, `--help`, `__all__` — 35 znalezisk |
| `D2-docs-architektura-report.md` | Audyt ARCHITECTURE, DECISIONS, CHANGELOG, PROGRESS, DEVELOPMENT_STANDARDS, docstringow — 55 znalezisk + 11 w dokumentach Hydrografu |
| `KNOWN-BUGS.md` | Lista bledow KODU: K1-K6 (wysokie/krytyczne), S1-S5 (srednie), N1-N9 (niskie), H1 (hipoteza) — z dowodami i pochodzeniem; zrodlo backlogu "Do naprawy" w PROGRESS |
| `DOCS-FIX-BRIEF.md`, `DOCS-FIX-REPORT.md` | Fala poprawek dokumentacji (opus): zasady (falszywe twierdzenia zwiazane z bledem oznaczone "znany blad <ID>", pliki K1/K2/K6 nietykane) i tabela WSZYSTKICH znalezisk D1/D2 -> naprawione / oznaczone / pominiete |
| `hydrograf-uwagi-migracyjne.md` | Co zmienic w Hydrografie (pinuje 0.6.1) przy przejsciu na Kartograf 0.7.0: katalogi cache, importy, dokumentacja |
| `DOCS-REREVIEW-BRIEF.md`, `DOCS-REREVIEW-REPORT.md` | Niezalezny przeglad fali dokumentacji (opus): AST kodu bez docstringow, prawdziwosc twierdzen, odsylacze, liczby, spojnosc, brama — 15 usterek (1 blokujaca: "`auto` == `pl`" na granicach spoza rejestru vs przycinanie S3), naprawione w `f52593a` (sekcja 8 `DOCS-FIX-REPORT.md`); na koncu re-review rundy: 2 resztki (dolna granica K2, odsylacze), poprawione przez kontrolera w `fb3cede` (ruling w `sdd-ledger.md`) |
| `gfi/` | Surowe odpowiedzi GetFeatureInfo skorowidza NMT (L3 (j)): morze/lad x 1 m/5 m x kazda warstwa + nieistniejaca warstwa; `index.json` — URL, status HTTP, Content-Type, rozmiar, znaczniki OGC |

## Co warto stad zapamietac

1. **Zielona suita offline nie mowila nic o zywych uslugach.** Szesc powaznych bledow kodu
   (K1-K6), wiekszosc SPRZED fal 2026-08-28/09-28 — stary kod pobierania nie byl
   systematycznie sprawdzany na zywo. Tor wycinka PL z ostatniej fali przeszedl bez
   zarzutu (0 rozbieznych pikseli na mln pikseli, R5 przy morzu i na kazdej granicy).
2. **Weryfikacja kolowa.** LAZ (K1) wysyla bbox WFS w kolejnosci (E,N) i tak samo odwrotnie
   czyta envelope, wiec wlasny filtr "potwierdza" kafle z miejsca oddalonego o ~426 km.
   Wyszlo dopiero w niezaleznym A/B wobec uslugi (kontroler, 2026-09-29).
3. **Diagnoza ADR-024 najpewniej bledna.** Roznice 1,25 m / 4,92 m przypisane serwerowi CUZK
   odpowiadaja roznicy operacji EPSG:1622 (Czechy) - EPSG:4829 (Slowacja); przypieta byla
   operacja slowacka (K2). Zanim uzna sie serwer za winny, sprawdzic obszar uzycia wlasnej
   operacji odniesienia (`area_of_use` w pyproj).
4. **Przeslanki z danych probnych nie sa uniwersalne.** Faza siatki 5 m = 5k + 2,5 m (1977
   arkuszy z cache Hydrografu) nie obowiazuje w kampanii 2022 pod Krakowem (S5); siatka 1 m
   = k + 0,5 m w 84 arkuszach.
5. **GUGiK zrywal 13-50 % polaczen** przy 9 agentach z jednego IP; biblioteka bez ponowien
   (S1) zamienia to w porazki albo — przy kolejnych warstwach skorowidza — w cicho starsze
   dane (K3). Przy nastepnych testach na zywo mniej rownoleglosci.
