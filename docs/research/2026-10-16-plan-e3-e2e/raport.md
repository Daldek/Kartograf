# Plan E / E3 — weryfikacja end-to-end (2026-10-16)

## Warunki i zakres

Uruchomiono rzeczywiste komendy `kartograf boundaries download` i `kartograf
cadastre download` na gałęzi `feat/plan-e3` z katalogu głównego repozytorium,
przez Python środowiska `.venv`. Dane, sidecary i logi zapisano w jawnym
katalogu poza repozytorium; `<katalog-danych>` oznacza lokalizację danych, nie
jest ścieżką do umieszczenia w projekcie. Zapytania dotyczyły usług GUGiK
i CUZK; żadna z prób nie korzystała z atrap HTTP.

## Pobrania

| Komenda / wariant (każda z `-o <katalog-danych>`) | Rzeczywisty wynik i pomiar |
|---|---|
| `boundaries --product addresses --country pl --bbox 566000,243500,566500,244000` | Jeden GPKG EPSG:2180: 198 punktów adresowych i 26 ulic, tyle samo co `hits` usługi WFS KIN. |
| `boundaries --product addresses --teryt 1261` | Paczka SHP powiatu 1:1. Drugie uruchomienie: `lokalna wersja`, bez zapytań. |
| `boundaries --product addresses --teryt 12` | `Error:` z listą wyborów (paczek województw adresów nie ma), kod 1. |
| `boundaries --product addresses --country pl --whole-country --format SHP` | `Warning:` przed transferem: 563 815 148 B; ZIP zapisany. Bez `--format`: `Error: --format wymagane: SHP, GML`. |
| `boundaries --product addresses --country pl --whole-country --format GML` | `Warning:` 804 071 557 B (`PRG-punkty_adresowe.zip`); ZIP zapisany. |
| `boundaries --product special --country pl --bbox 19.93,50.055,19.945,50.065 --bbox-crs EPSG:4326` (Kraków) | 243 s, 44 warstwy, 61 obiektów, OGC:CRS84; jedno ponowienie po przekroczeniu czasu (limit kanału 120 s); `Info:` o pominiętych obwodach spisowych. |
| to samo, obszar w Warszawie (`21.0,52.22,21.01,52.23`) | 109 s; `Info:` jak wyżej. |
| `boundaries --product special --teryt 1261` | `Error:` (granice specjalne nie mają paczek powiatów). |
| `boundaries --product special --country pl --whole-country --format SHP` | `Warning:` 734 171 465 B; ZIP zapisany. |
| `boundaries --product geomorphology --country cz --level celek` (2 x 2 km) | 1 obiekt, EPSG:5514. Bez `--level`: `Error:` z listą siedmiu poziomów. |
| `boundaries --product geomorphology --country cz --level okrsek` (20 x 20 km) | 9 obiektów, EPSG:5514. |
| `cadastre --product prices --teryt 1201` | GPKG RCN; powiat 1201 (ok. 9,7 MB w ZIP). Kod `126` to `Error:` (województwo 2 cyfry albo powiat 4). |
| `cadastre --product prices --teryt 1261` | `Warning:` 301 623 607 B (duży plik); GPKG po rozpakowaniu zajmuje ok. 1,1 GB. |
| `cadastre --product map --ku 623164 --format SHP\|DXF\|DGN\|VFK` | Cztery paczki ZIP 1:1 w osobnych segmentach `cadastre/cz_km_<format>/ku/`. |
| `cadastre --product map --country cz --format SHP --bbox=-452000,-1112000,-450000,-1110500 --bbox-crs EPSG:5514` | `Info:` z trzema KU wg RUIAN (652954, 696137, 753521) i trzy paczki. |
| `cadastre --product map --ku 999999 --format SHP` | `Error: ... (HTTP 404)`, kod 1. |
| `cadastre --product map --ku 623164 --country pl --format SHP` | `Error:` (`--ku` dotyczy CZ). Bez `--format`: `Error:` z listą formatów. |

## Drugi przebieg i aktualizacje

- Mapa katastralna CZ, obszar: `--check-updates` → `aktualne (2026-10-16)`
  dla trzech KU (sygnał HTTP); kolejne uruchomienie → `lokalne: 3`, bez
  pobierania.
- Granice specjalne (obszar) i RCN: `--check-updates` → `nie da sie sprawdzic
  bez pobrania`; kolejne uruchomienie używa lokalnej wersji. `Info:` o obwodach
  spisowych pojawia się także wtedy.

## Granice specjalne: pomiar kolekcji

Odpytanie każdej kolekcji PRG osobno (strona `items`): 43 z 45 odpowiedzi 200,
`GranicaObwoduSpisowego` w 157,9 s; dwa zapytania (`ProkuraturaRejonowa`,
`Nadlesnictwo`) zerwane po ok. 260 s (`Connection reset by peer`).
Pierwsza próba obszaru z limitem 60 s, z kolekcją obwodów
spisowych, zakończyła się `Error:` po trzech próbach. Decyzja koordynatora:
obwody spisowe poza wynikiem obszaru (44 kolekcje), `Info` `AREA_OMITTED`
i limit kanału 120 s (ADR-043 errata 1). Obszar trwa 2–4 min; usługa
sporadycznie przekracza czas albo zrywa połączenie, a ponowienie zwykle
pomaga.

## VKM (P2)

`HEAD https://services.cuzk.gov.cz/vkm/ku/aktualni/<KU>.zip`: 200 dla KU
737950, 692450 i 619116; 404 dla KU 623164 (stan 2026-10-16). Format VKM
pozostaje poza 0.8.0 (backlog PROGRESS).

## Ryzyka

- Rozpakowanie RCN idzie w lokalnym katalogu tymczasowym; powiat 1261 to
  ok. 1,1 GB, a województwo szacunkowo ok. 1,8 GB (szacunek, nie pomiar).
  Gdy katalog tymczasowy jest w pamięci (tmpfs), wskaż większy (`TMPDIR`).
- `HY-NET` (sekcja 1.9 USAGE) nie ma analogicznego `Info` o pominiętych
  skrzyżowaniach; zaplanowane w przeglądzie spójności wydania.
