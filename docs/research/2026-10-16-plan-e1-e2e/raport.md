# Plan E / E1 — weryfikacja end-to-end (2026-10-16)

## Warunki i zakres

Rzeczywiste komendy `kartograf elevation download` i `kartograf imagery
download` uruchomione na gałęzi `feat/plan-e1` (kod worktree, Python z `.venv`,
`python -m kartograf.cli.commands`). Dane zapisano w jawnym katalogu poza
repozytorium (`<katalog-danych>`). Zapytania szły do usług GUGiK i CUZK, bez
atrap HTTP.

## Pobrania (każde z `-o <katalog-danych>`)

| Komenda / wariant | Wynik i pomiar |
|---|---|
| `elevation download --product nmt --resolution 100m --country pl --bbox 564000,241000,570000,247000 --bbox-crs EPSG:2180` | `Info:` województwa obszaru wg PRG: `12`; `nmt/pl_1992_100m/teryt/12.zip` (ZIP 7,6 MB, jeden plik XYZ 37 949 687 B), wersja `2019-05-14`, 10 s. Sidecar: `pl.gugik.nmt_100m`, EPSG:2180, `vertical_crs: null`, `extra.vertical_crs_note`, `extra.source`. |
| `elevation download --product contours --format SHP --sheet CTES96` | `contours/cz_zabaged_shp/CTES/96/CTES96.zip`, 8 plików (4 121 872 B po rozpakowaniu w liście `unzip -l`), 2 s. Sidecar: `cz.cuzk.zabaged_contours_shp`, EPSG:5514, wysokości EPSG:8357 (Bpv), `extra.members`, `extra.http`, `mapname`, `cz_share`. |
| `elevation download --product contours --format DGN --sheet CTES96` | `contours/cz_zabaged_dgn/CTES/96/CTES96.zip`, 3 pliki, 2 s; osobny segment. |
| `elevation download --product contours --format SHP --country cz --bbox=-448500,-1113500,-446500,-1112500 --bbox-crs EPSG:5514` | Lista arkuszy SM5 z indeksu: `CTES86`, `CTES96`; CTES86 nowa wersja (8 plików), CTES96 lokalna; `extra.parent_request` w sidecarze CTES86. |
| `imagery download --product intensity --sheet M-34-64-D-d-1-4` | `intensity/pl_1992/M-34/64/D/d/1/4/M-34-64-D-d-1-4.tif`, wersja `2025-04-28_83138` (najnowszy lot), 41 s; `gdalinfo`: 9061 x 9373 px, 1 pasmo, piksel 0,25 m, EPSG:2180. |
| `imagery download --product true-orto --sheet N-34-50-A-c-3-2-3` | `Warning:` przed `GET`: plik 296 853 152 B (ok. 297 MB, `HEAD`); `orto/pl_1992_true/N-34/50/A/c/3/2/3/N-34-50-A-c-3-2-3.tif`, wersja `2020-05-21_73912`, 135 s; 20372 x 23306 px, 3 pasma, piksel 0,05 m, EPSG:2180. |
| `imagery download --product true-orto --country pl --bbox 470100,740100,470200,740200 --bbox-crs EPSG:2180 --cutout --horizontal-crs EPSG:2180 --resolution 0.05m` | Wycinek WCS `True_Orthoimagery`: `orto/pl_1992_true_0.05m/bbox/470100_740100_470200_740200.tif`, 2000 x 2000 px, 3 pasma, piksel 0,05 m, EPSG:2180, 15 s. |
| `imagery download --product oblique-orto --sheet 7.125.11.08 --direction n` | `Warning:` 301 669 662 B (ok. 302 MB); `orto/pl_2000_oblique/7/125/11/08/7.125.11.08_n.tif` (+ dowiązanie `full_sheet/`), wersja `2021-10-03_78945`, 107 s; 32000 x 20000 px, 3 pasma, piksel 0,05 m. Sidecar: EPSG:2178; `gdalsrsinfo -e` pliku: EPSG:32634 (patrz Wnioski). |

## Drugi przebieg i aktualizacje

- NMT 100 m: drugi przebieg `12: lokalna wersja 2019-05-14` (bez pobrania);
  `--check-updates`: `12: aktualne (2019-05-14)` (tylko feedy ATOM).
- Warstwice: drugi przebieg DGN `CTES96: lokalna wersja 2026-10-16` (jedno
  `HEAD`, `ETag`); `--check-updates` SHP: `CTES96: aktualne (2026-10-16)`.
- Orto ukośna `--check-updates` (bez `--direction`): linie po pliku -
  `7.125.11.08_n.tif: aktualne (2021-10-03_78945)`, `_e`, `_s`, `_w`:
  `do pobrania`.

## Błędy przed siecią (katalog wyniku nie powstał)

- `--product contours` bez `--format`: `Error: --format wymagane dla --product contours: SHP, DGN`;
- `--resolution 5m` z warstwicami: `Error: --resolution nie dotyczy --product contours: warstwice to arkusze SM5 (wektor) - bez rozdzielczosci, lotow i wycinka`;
- warstwice z `--country pl`: `Error: --product contours jest dostepny tylko dla CZ`;
- `--coverage high` z true orto: `Error: --coverage 'high': --product true-orto ma jedna usluge WCS wycinka (...) - bez --coverage`.

## Wnioski

- Wszystkie pobrania zakończone kodem 0; ZIP-y 1:1 (warstwice 8/3 pliki, NMT
  100 m jeden plik XYZ), obrazy z liczbą pasm i pikselem zgodnymi z raportem E.
- Do wyjaśnienia (EZ): plik orto ukośnej `7.125.11.08_N.tif` GDAL rozpoznaje
  jako EPSG:32634 (UTM 34N), a sidecar i godło PL-2000 strefy 7 dają
  EPSG:2178; ostrzeżenie E17 (`sheet_crs_mismatch`) się nie pojawiło. Trzeba
  sprawdzić georeferencję pliku GUGiK (geokeys, współrzędne narożników)
  i regułę E17 dla orto ukośnej.
