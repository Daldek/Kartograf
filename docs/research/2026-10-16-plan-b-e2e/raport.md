# E2E planu B na zywo (2026-10-16): `elevation` CZ - DMP OK, DMP 1G, TM33, LAZ, raport CZ i `auto`

Galaz `feat/plan-b-elevation-cz`. CLI z korzenia worktree
(`python -m kartograf.cli.commands`), cache metadanych w korzeniu worktree,
dane wylacznie w `<katalog-danych>` (jawne `-o`). Plan:
`docs/superpowers/plans/2026-10-15-plan-b-elevation-cz.md` (Task 9),
decyzje: ADR-041 z uzupelnieniami planu B. Kroki E2E-1..4 wykonano na
`416f6ba`, E2E-5 na `416f6ba` i powtorzono wybor arkuszy (`--check-updates`)
na `0949f2e`, E2E-6 na `0949f2e` (poprawki raportu z `6bdd73e` nie zmieniaja
wynikow ponizej - wszystkie kombinacje maja pliki). Sumy kontrolne paczek ZIP
pobranych recznie (`curl`) porownano z
`docs/research/2026-10-13-katalog-produktow/probki.md`.

## Brama (`6bdd73e`)

`pytest tests/ -m "not live"`: 4642 passed, 18 deselected (ok. 123 s);
`ruff check .` czysto; `ruff format --check .` 210 plikow bez zmian;
`mypy kartograf/ tests/` 0 bledow w 208 plikach.

## Wyniki

| Krok | Polecenie (skrot) | Wynik |
|---|---|---|
| E2E-1 DMP OK SM5 | `elevation download --product nmpt --sheet CTES96 --resolution 0.5m --vertical-crs Bpv` | `nmpt/cz_dmpok_bpv/CTES/96/CTES96.tif`, 5000x4000 px (2,5 x 2 km), piksel 0,5 m, EPSG:5514, wszystkie piksele wazne; sidecar `dataset cz.cuzk.dmpok`, `vertical_crs EPSG:8357` (natywnie), `extra.http` (`ETag`, `Last-Modified`), `mapname` "Český Těšín 9-6", `cz_share 0.99`, sha256 `8948044c...`. Drugi przebieg: `CTES96: lokalna wersja 2026-10-16` (jedno `HEAD`, 1,6 s) |
| E2E-2 DMP OK TM33 EVRF2007 | `--sheet 760_5518 --resolution 0.5m --vertical-crs EVRF2007` | `nmpt/cz_dmpok_evrf2007/760/5518/760_5518.tif`, 4000x4000 px, 0,5 m, EPSG:3045, `vertical_crs EPSG:5621`, `transform: null` (bez operacji pionowej); wartosci i geotransformacja identyczne z czlonem ZIP `DMPOK-TIFF/epsg-3045/760_5518.zip` (sha256 ZIP `ccfdfe2d344e` = `probki.md`; TIFF w ZIP bez CRS - nadany z kanalu). Kafel lezy w wiekszosci w PL: 1 387 835 waznych pikseli. `--check-updates`: `aktualne` (0,9 s) |
| E2E-3 DMR 4G TM33 EVRF2007 | `--product nmt --sheet 760_5518 --resolution 5m --vertical-crs EVRF2007` | natywny plik 400x400 px, 5 m, EPSG:3045, wartosci = czlon ZIP `DMR4G-TIFF/epsg-3045/760_5518.zip` (`cf1ac841fc31` = `probki.md`). Porownanie z warpem z `develop` (`06ab962`, ta sama siatka - identyczna transformacja i wymiary): 13 865 wspolnych waznych pikseli, mediana \|roznicy\| 0,061 m, p95 0,394 m, maks. 1,657 m, srednia roznica -0,017 m. Magazyn z warpem: tryb domyslny zostawil lokalna wersje z `Info:` o braku weryfikacji (sygnal `none`), `--force` pobral plik CUZK jako nowa wersje `c906b905` i przepial dowiazanie (decyzja 12) |
| E2E-4 DMP 1G | kafel `--sheet 760_5518 --resolution 2m --vertical-crs Bpv`; wycinek `--bbox=-447000,-1114000,-446600,-1113600 --bbox-crs EPSG:5514 --resolution 2m --cutout --horizontal-crs EPSG:5514` | kafel: 1000x1000 px, 2 m, EPSG:3045, przypieta operacja pozioma S-JTSK -> ETRS89 (1,0 m), wysokosci Bpv natywnie, `--check-updates`: `nie da sie sprawdzic bez pobrania`. Wycinek: 200x200 px, 2 m, EPSG:5514, granice rowne bboxowi, 0 pikseli nodata, 266,1-298,2 m. Geometria wycinka: drugi wycinek `-449000,-1113400,-448000,-1112400` (500x500 px) porownany z natywnym DMP OK `CTES96` usrednionym 4x4 do 2 m - minimum odchylenia (MAD 0,235 m) przy przesunieciu 0, maksimum korelacji gradientow w odleglosci 0,5 m od zera (przy +-2 m wyraznie nizsze); mediana roznicy DMP 1G - DMP OK 0,30 m (inne modele). Wycinek lezy na siatce zrodla z dokladnoscia lepsza niz 1/4 piksela. `--sheet CTES96 --resolution 2m`: `Error:` przed siecia z podpowiedzia (kafel TM33 albo `--cutout`) |
| E2E-5 LAZ CZ arkusz | `--product laz --country cz --model dmr5g --vertical-crs Bpv --sheet CTES96`; to samo `EVRF2007 --sheet 760_5518` | `laz/cz_dmr5g_bpv/CTES/96/CTES96.laz` sha256 `5e939b94...` = czlon ZIP `DMR5G/epsg-5514/CTES96.zip` (sha256 ZIP `a1090300beba` = `probki.md`), sidecar EPSG:5514 / EPSG:8357, `extra.http`, `mapname`, `cz_share 0.99`; 2,5 s. `laz/cz_dmr5g_evrf2007/760/5518/760_5518.laz` `8bce02ba...` = czlon ZIP (`c230efd38e14` = `probki.md`), EPSG:3045 / EPSG:5621; 1,4 s |
| E2E-5 LAZ CZ obszar | `--bbox=-450000,-1114000,-444000,-1113000 --bbox-crs EPSG:5514`, Bpv i EVRF2007 | Bpv: 2 arkusze SM5 (`CTES86` nowa wersja, `CTES96` lokalna). Indeks (warstwa 24, zapytanie reczne) zwrocil 6 arkuszy: `CTES87`, `CTES97`, `OSTR07` stykaja sie z dolna krawedzia, `OSTR06` zachodzi na 0,7 mm (tolerancja 1 cm) - odrzucone. EVRF2007: 6 kafli TM33 (`756_5514`, `756_5516`, `758_5514`, `758_5516`, `760_5514`, `760_5516`) z 7 zwroconych przez warstwe 26 (`760_5518` poza obwiednia); 4,1 s. Mniejszy bbox `-447000..-444000`: 1 arkusz (`CTES86`) i 1 kafel (`760_5516`) - wschodnia czesc lezy w PL. `--check-updates`: wszystkie `aktualne` |
| E2E-5 bledy przed siecia | SM5 + EVRF2007; TM33 + Bpv; obszar CZ bez `--model`; `--model` z PL; `--model` z `nmt`; `--cutout` z LAZ | kazde `Error:` i kod 1, np. `Error: LAZ CZ - arkusze SM5 (S-JTSK) sa tylko w Bpv, podano --vertical-crs EVRF2007 (chmury punktow bez transformacji); EVRF2007: kafle TM33 (ETRS89), np. 760_5518, albo obszar (--bbox/--geometry)`; `Error: --model wymagane dla --product laz w CZ: dmr5g (teren, DMR 5G), dmr4g (teren, siatka 5 m), dmp1g (powierzchnia, DMP 1G), dmpok (powierzchnia, korelacja obrazowa)` |
| E2E-5 LAZ `auto` | `--product laz --country auto --bbox 18.615,49.740,18.640,49.755 --bbox-crs EPSG:4326 --model dmr4g --vertical-crs pl=EVRF2007,cz=Bpv --check-updates` | jeden plan: 8 kafli PL (2024, `Info:` o 11 kaflach zastapionych nowszymi) i 4 arkusze CZ (`CTES86`, `CTES87`, `CTES96`, `CTES97`) - te same, co w raporcie E2E-6; 3,2 s. Z `--year 2024`: `Info: --country auto -> pl (--year dotyczy tylko PL)` i tylko kafle PL. Bez `--model`: `Error: obszar siega CZ: podaj --model ... albo --country pl` |
| E2E-6 raport NMPT CZ | `elevation availability --product nmpt --country cz --bbox=-447000,-1114000,-446600,-1113600 --bbox-crs EPSG:5514` | obszar 16,00 ha; DMP OK S-JTSK 0.5m Bpv TIFF 1/0, publikacja 2025-10-10, 16,7 MB, komplet; DMP OK ETRS89-TM33 0.5m EVRF2007 TIFF 1/0, 2026-08-20, 29,6 MB, komplet; `Info:` `cz_service_only` o DMP 1G; podpowiedzi `--sheet CTES86 ... --vertical-crs Bpv` i `--sheet 760_5516 ... --vertical-crs EVRF2007`. 1,3 s z `--force`, 0,6 s z cache |
| E2E-6 raport LAZ CZ | to samo z `--product laz` | 8 kombinacji (4 modele x S-JTSK/ETRS89-TM33), wszystkie kompletne; DMP 1G publikacja 2023-06-12, pozostale 2025-2026; rozmiary od 42,5 kB (DMR 4G) do 182,2 MB (DMP OK); 8 polecen obszaru z `--model`; 1,3 s. Zapytania (opakowanie `requests.Session.request`, `--force`, bbox E2E-5): 2 x `GET` indeksu `ags.cuzk.gov.cz`, 32 x `HEAD` `openzu` (4 modele x 8 arkuszy), 0 x `GET` plikow |
| E2E-6 raport NMT CZ `--details` | `--product nmt --country cz --bbox=-450000,-1114000,-444000,-1113000 --bbox-crs EPSG:5514 --details` | DMR 4G S-JTSK 2/0 (`CTES86`, `CTES96`), ETRS89-TM33 6/0 - te same arkusze, co pobranie LAZ dla tego obszaru; `--details` wypisuje wszystkie polecenia, stopka 5 + `... pozostale polecenia: 1`; `Info:` o DMR 5G |
| E2E-6 raport `auto` | `--country auto --bbox 18.615,49.740,18.640,49.755 --bbox-crs EPSG:4326`, NMPT i LAZ | tabele PL i CZ w jednym raporcie: NMPT PL 1,77 km2 (5 kombinacji, najnowsza kompletna 2024 0.5m EVRF2007), CZ 3,49 km2 (DMP OK S-JTSK 4/0, 169,1 MB; TM33 2/0, 67,6 MB); LAZ PL 4 kombinacje (2024 12 pkt/m2 8/0) i 8 kombinacji CZ; 6,1-6,6 s. Zapytania LAZ `auto` z `--force`: 7 x `GET` WFS/PRG GUGiK, 2 x `GET` indeksu CUZK, 24 x `HEAD` `openzu`, 0 x `GET` plikow. `--json` (bez `checked_at`, ten sam cache) = `check_availability(...).to_json()` (12 kombinacji). `--year 2023` z `auto`: `Info: --country auto -> pl ...` i tylko tabela PL; z `--country cz`: `Error: CZ (CUZK) nie publikuje lat nalotu ...` |

## Uwagi

- Pole `area_m2` czesci CZ w raporcie `auto` to prostokat czesci w EPSG:5514
  (decyzja 9 planu: CZ bez maski ladu), wiec obejmuje tez terytorium PL
  przy granicy: bbox Cieszyna ma ok. 3,0 km2, czesc PL 1,77 km2 (lad PL),
  czesc CZ 3,49 km2. Arkusze CZ wybiera ten sam prostokat co pobranie,
  wiec raport i pobranie sa zgodne (E2E-5 `auto`).
- Indeks `KladyMapovychListu` zwraca arkusze stykajace sie z obszarem
  krawedzia i zachodzace o ulamki milimetra (szum wspolrzednych ArcGIS);
  filtr klienta z tolerancja 1 cm daje wynik zgodny z geometria (E2E-5).
- Kafel TM33 przy granicy (`760_5518`) jest w wiekszosci nodata - zgodnie
  z plikiem CUZK (wartosci 1:1 z ZIP).
- Podpowiedz PL raportu dla obszaru przy granicy (`--country pl` albo czesc
  PL w `auto`) to polecenie obszaru: na bboxie Cieszyna raport podaje 2024
  0.5m jako komplet (3/0), a `--check-updates` z tej podpowiedzi planuje
  4 arkusze - czwarty (`M-34-74-C-c-2-2`) lezy w CZ i nie ma rekordu GUGiK
  (`nie udalo sie sprawdzic: Brak danych NMPT 0.5m ...`, kod 1); arkusze
  PL sa poprawne. To zachowanie planu A (pobranie siatki arkuszy calego
  prostokata), plan B go nie zmienia - do decyzji koordynatora.
