# Plan E / E2 — weryfikacja end-to-end (2026-10-16)

## Warunki i zakres

Uruchomiono rzeczywiste komendy `kartograf names download` i `kartograf maps
download` na gałęzi `feat/plan-e2` z katalogu głównego repozytorium, przez Python
środowiska `.venv`. Dane i sidecary zapisano w jawnym katalogu poza
repozytorium; poniższy `<katalog-danych>` oznacza lokalizację danych, nie
jest ścieżką do umieszczenia w projekcie. Zapytania sieciowe dotyczyły usług
GUGiK i CUZK; żadna z poniższych prób nie korzystała z atrap HTTP.

## Pobrania

| Komenda / wariant (każda z `-o <katalog-danych>`) | Rzeczywisty wynik i pomiar |
|---|---|
| `names download --product geographic --country pl --bbox 19.93,50.055,19.945,50.065 --bbox-crs EPSG:4326` | PRNG RP: jeden GPKG, 9 obiektów, OGC:CRS84. Odpowiedź API trwała ok. 79 s (limit czasu kanału 180 s). |
| `names download --product world --country pl --bbox=-74.02,40.69,-73.92,40.79 --bbox-crs EPSG:4326` | Polskie nazwy świata: jeden GPKG, 7 obiektów w rejonie Nowego Jorku, OGC:CRS84 — obszar nie został przycięty do Polski. |
| `names download --product geographic --country pl --whole-country --format SHP` | Dwa oryginalne archiwa ZIP: `pl-miejscowosci.zip` (20 701 275 B) i `pl-obiekty-fizjograficzne.zip` (29 419 852 B). |
| `names download --product geographic --country cz --bbox=-452000,-1112000,-450000,-1110000 --bbox-crs EPSG:5514` | Geonames REST: jeden GPKG, 25 warstw; 14 obiektów w 8 niepustych warstwach, EPSG:5514. |
| `names download --product geographic --country cz --whole-country --format GPKG --horizontal-crs EPSG:5514` | Oryginalny ZIP 36 209 564 B, człon `GEONAMES_RESULTS.gpkg`; `ogrinfo /vsizip/` potwierdził 25 warstw i EPSG:5514. Etykieta wydania ATOM: `2026-09-30`. |
| `maps download --product topographic --country pl --sheet M-34-064-D-d-1 --scale 1:10000 --format TIFF` | TIFF 66 592 473 B, `gdalinfo`: 5279 × 5470, 4 pasma, EPSG:2180. Kanoniczne godło w slocie: `M-34-64-D-d-1`; data `Stan bazy`: `2026-05-27`. |
| `maps download --product topographic --country pl --sheet M-34-064 --scale 1:100000 --format PDF` | PDF 29 406 436 B, `pdfinfo`: jedna strona formatu A1; data `Stan bazy`: `2025-01-31`. |
| `maps download --product topographic --country cz --sheet 0510-D-11 --scale 1:10000 --format TIFF` | ZIP 13 959 425 B: `0510D11.tif` i `0510D11.tfw`; `gdalinfo /vsizip/` potwierdził 10001 × 8001 pikseli, 0,5 m/piksel i georeferencję TFW; sidecar EPSG:5514. |
| `maps download --product topographic --country cz --sheet NM-34-07-1-D-15 --scale 1:10000 --format PDF` | PDF 7 666 214 B, jedna strona; sidecar wariantu ETRS89: EPSG:3045. |

Dla wszystkich dziewięciu wywołań wynik zakończył się sukcesem; przy każdym
pliku wynikowym odczytano sidecar `kartograf-meta/1` i potwierdzono klucz zbioru
oraz układ poziomy (`OGC:CRS84`, `EPSG:5514`, `EPSG:2180` albo `EPSG:3045`
zgodnie z wariantem). GeoPackage sprawdzono przez `ogrinfo`/`pyogrio`,
rastry przez `gdalinfo`, dokumenty przez `pdfinfo`.

## Drugi przebieg i aktualizacje

Powtórzenie tych samych pobrań użyło zapisanych wersji bez powielania plików.
Następnie `--check-updates` (bez pobierania treści) zwróciło:

- mapę BDOT10k 1:10000 TIFF: `aktualne (2026-05-27)` według indeksu;
- ZTM ETRS89 PDF: `aktualne (2026-10-16)` według nagłówka HTTP;
- krajowe Geonames GPKG5514: `aktualne (2026-09-30)` według feedu ATOM;
- PRNG RP (obszar i paczki krajowe): `nie da sie sprawdzic bez pobrania`,
  ponieważ źródło nie ogłasza taniego sygnału świeżości.

## Wnioski techniczne

- PRNG obszaru używa osi długość/szerokość; kraj pochodzenia produktu `world`
  nie ogranicza jego zasięgu przestrzennego.
- PDF i TIFF wizualizacji BDOT10k mają niezależne sloty; data `Stan bazy`
  zależy od skali. PDF to gotowa publikacja, nie eksport obiektów BDOT10k.
- TIFF ZTM jest oryginalną paczką z georeferencją w `.tfw` (nie rozpakowujemy
  jej w magazynie); PDF pozostaje pojedynczym `.pdf`. Układ arkusza ETRS89
  jest rozpoznawany z godła i oznaczony w sidecarze jako EPSG:3045.
- Odpowiedź PRNG OGC API bywa wolna nawet dla małego obszaru; limit czasu
  zapisany w deskryptorze wynosi 180 s na żądanie.
