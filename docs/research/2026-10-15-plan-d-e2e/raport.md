# Plan D - testy na zywo (E2E) CLI, 2026-10-16

Galaz `feat/plan-d-cz-data` (Taski 1-7), CLI uruchamiane z korzenia worktree
(`python -m kartograf.cli.commands ...`), magazyn `<katalog-danych>`, cache
metadanych lokalnie. Ujemne wspolrzedne EPSG:5514 podawane jako `--bbox=...`
(argparse traktuje `-460000,...` po spacji jak flage).

## Pobrania (pierwsze uruchomienie)

| Polecenie (skrot) | Wynik |
|---|---|
| `landcover download --source zabaged --bbox=-460000,-1120000,-450000,-1110000 --bbox-crs EPSG:5514` | nowa wersja `landcover/cz_zabaged/bbox/-460000_-1120000_-450000_-1110000.gpkg`; GPKG: 22 warstwy, razem 21 890 obiektow, EPSG:5514 (`ogrinfo -so`; ten sam obszar przez API: ok. 25 s) |
| `boundaries download --product admin --country cz --level obec --bbox=-470000,-1130000,-440000,-1100000 --bbox-crs EPSG:5514` | nowa wersja `boundaries/cz_ruian_obec/bbox/...gpkg`; warstwa `Obec` 68 obiektow (= `returnCountOnly`, rekonesans: 68) |
| `boundaries download --product admin --country auto --level pl=gmina,cz=obec --bbox 18.5,49.6,18.8,49.9 --bbox-crs EPSG:4326` | CZ: nowa wersja `cz_ruian_obec`; PL: blad uslugi PRG WFS (`RESULTTYPE=hits` gmin: HTTP 400 z trescia "Internal Server Error", bez ponowien), kod wyjscia 1, plik CZ zostal. Powtorka: CZ lokalna, PL nowa wersja `pl_prg_gmina` - blad przejsciowy GUGiK |
| `hydro download --product network --country cz --bbox=-470000,-1130000,-440000,-1100000 --bbox-crs EPSG:5514` | nowa wersja `hydro/cz_hynet/bbox/...gpkg`: `WatercourseLink` 3783, `HydroNode` 3509 (= `hits`); ok. 18 s |
| `hydro download --product network --country cz --whole-country` | `Warning: network CZ: plik krajowy .../HY-NET.zip - 194208037 B (ok. 194 MB)` przed transferem; nowa wersja `hydro/cz_hynet_gpkg/country/cz.zip` |
| `imagery download --product orto --country cz --sheet CTES96` | 4 nowe wersje (`CTES96.jgw`, `.TM33N.jgw`, `.TM34N.jgw`, `.jpg`), etykieta `2024_2025-02-06`; JPEG 63 868 659 B, 20000 x 16000 px, piksel 0,125 m, 3 pasma (`gdalinfo` z `.jgw`) |
| `imagery download --product orto --country cz --sheet AS91` | 4 nowe wersje, etykieta `2025_2026-02-24` (godlo dwuliterowe, katalog `AS/91`) |
| `imagery download --product orto --country cz --bbox=-448500,-1113500,-446500,-1112500 --bbox-crs EPSG:5514` | `Znaleziono arkuszy SM5 (CUZK): 2` (CTES86, CTES96); CTES86 4 nowe wersje, CTES96 4 lokalne |
| `imagery download --product orto --country pl --bbox 566000,243000,566200,243200 --cutout --horizontal-crs EPSG:2180 --coverage standard --resolution 0.25m` | nowa wersja `orto/pl_1992_standard_0.25m/bbox/566000_243000_566200_243200.tif`, sha `d419683e` - ten sam co w pomiarze galezi wycinka (800 x 800 px, 3 pasma uint8, EPSG:2180) |
| jw. `--coverage high --resolution 0.1m` | nowa wersja `orto/pl_1992_high_0.1m/...tif`, sha `786b6425` - jak w pomiarze galezi wycinka (2000 x 2000 px) |

## Powtorki, sprawdzenia, `--force`

- Powtorka kazdego polecenia = wersje lokalne bez transferu (ZABAGED, RUIAN,
  HY-NET obszar i kraj, CTES96, AS91, oba wycinki).
- `--check-updates`: HY-NET kraj `aktualne (2026-10-16)` (ten sam `ETag`),
  CTES96 i obszar CTES86+CTES96 `aktualne (2024_2025-02-06)`, plik krajowy
  ZABAGED EPSG:5514 `do pobrania (2026-10-04)` (wydanie z feedu ATOM, bez
  pobierania pliku).
- `--country auto` dla orto (`--bbox 18.55,49.70,18.65,49.76 --bbox-crs
  EPSG:4326 --sheet-system 1992 --check-updates`): 22 arkusze SM5 CZ i 16
  arkuszy PL w jednym planie (bez zawezenia do PL); arkusze PL lezace po
  stronie CZ bez ortofotomapy PL-1992 = `nie udalo sie sprawdzic`
  (zachowanie toru PL bez zmian), kod wyjscia 1.
- `--force` wycinka standard 0,25 m: `bez zmian` (ta sama tresc).

## Bledy (bez sieci, przed pobraniem)

- `--sheet CTES96 --year 2024 --country cz`: `--year dotyczy tylko PL - CUZK
  publikuje tylko aktualny rocznik arkusza ortofoto CZ ...`.
- `--sheet 302_5550 --country cz` (kafel TM33): `ortofoto CZ ma arkusze SM5
  (np. CTES96, AS91); kafle TM33 sa tylko dla NMT`.
- `--cutout` bez `--coverage`: `--coverage wymagane z --cutout --product
  orto: standard (...), high (...)`; `--horizontal-crs EPSG:5514` -
  argparse: `invalid choice (choose from EPSG:2180)`.
- `boundaries --country auto --level gmina`: `--level gmina: nieznany poziom
  admin (CZ); ... --level pl=<poziom>,cz=<poziom>`.

## Wnioski i znaleziska

1. **HY-NET `WatercourseSeparatedCrossing`** (wczesny test API przed E2E):
   GeoServer odpowiada na `RESULTTYPE=hits` z `BBOX` liczba 0, choc strony
   z tym samym `BBOX` daja obiekty (30 x 30 km: 0 wobec 4; 100 x 100 km: 0
   wobec 24; caly kraj bez `BBOX`: 532), a typ nie ma geometrii w GML
   (relacja dwoch odcinkow). Pobranie obszaru konczylo sie bledem
   kompletnosci - wynik obszaru ma teraz `WatercourseLink` i `HydroNode`,
   skrzyzowania sa w pliku krajowym (ADR-042 errata 2).
2. Usluga PRG WFS zwrocila raz HTTP 400 "Internal Server Error" dla
   zapytania `hits`; Kartograf nie ponawia 4xx - powtorka polecenia
   pobrala brakujacy plik (pliki innych krajow zostaja).
3. Plik krajowy ZABAGED (5,8 GB) pobierany swiadomie w tle (API, ten sam
   magazyn): po ok. 35 min 3,6 GB, przerwane na koniec sesji - pelnego
   pobrania nie potwierdzono; rozmiar z feedu i etykieta wydania
   potwierdzone `--check-updates` i testami offline.
4. Log E2E zapisywany przez dopisywanie (`>>`) do pliku na dysku danych
   gubil czasem cale wyjscie procesu (tez ostrzezenia Pythona); te same
   polecenia z wyjsciem do terminala albo potoku drukuja poprawnie -
   powtorki sprawdzone recznie. Czasy w tabeli z pomiarow przez API.
