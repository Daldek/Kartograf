# Surowe odpowiedzi skorowidza GUGiK (2026-10-10: wybor roku ortofotomapy)

Zrodlo: zapytania GetFeatureInfo `text/html` wyslane 2026-10-10 przez
Kartograf (punkt zapytania jak `SkorowidzLayersMixin._query_bbox`: kwadrat
20 m wokol srodka arkusza, EPSG:2180, osie N,E). Pliki zapisane BEZ edycji
tresci (`response.content`). Odpowiedzi NMT z tej rundy (podpowiedz
wariantu P10 po WMS) usunieto w 0.8.0: NMT/NMPT czytaja skorowidz WFS
(ADR-041, `tests/fixtures/gugik_wfs/`).

## Orto: dwa loty RGB o tej samej wielkosci piksela w jednym roku

- `orto/N-33-130-D-d-1-4_<warstwa>.html` — skorowidz ortofotomapy
  (`SkorowidzeOrtofotomapy2026`, `2025`, `2024`, `Starsze`) dla arkusza
  N-33-130-D-d-1-4 (Poznan), punkt zapytania wg `_query_bbox`. W 2025 dwa
  loty RGB 0,25 m: `83982` (2025-09-09, NIE) i `83832` (2025-04-26, TAK).
  Pliki zapisane BEZ edycji tresci, 2026-10-10.

Testy: `tests/test_provider_campaigns.py`
(`test_orto_year_2025_two_rgb_flights_same_pixel_newest_first`).
