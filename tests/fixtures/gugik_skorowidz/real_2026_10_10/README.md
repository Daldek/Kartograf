# Surowe odpowiedzi skorowidza GUGiK (2026-10-10, podpowiedz wariantu P10)

Zrodlo: zapytania GetFeatureInfo `text/html` wyslane 2026-10-10 przez
Kartograf (punkt zapytania jak `SkorowidzLayersMixin._query_bbox`: kwadrat
20 m wokol srodka arkusza, `BBOX=511593.03002549475,764527.8579266416,
511613.03002549475,764547.8579266416`, EPSG:2180, osie N,E). Pliki zapisane
BEZ edycji tresci (`response.content`).

Arkusz `N-34-130-D-d-1-1` (U1 z testu przed 0.7.1): brak w skorowidzu NMT
5 m, jest w NMT 1 m EVRF2007 i KRON86.

- `nmt/N-34-130-D-d-1-1/nmt5_evr__<warstwa>.body` — NMT 5 m EVRF2007
  (`SheetsGrid5mEVRF2007`), po jednej warstwie; wszystkie bez rekordow.
- `nmt/N-34-130-D-d-1-1/nmt1_evr__all.body` — NMT 1 m EVRF2007
  (`SkorowidzeUkladEVRF2007`), jedno zapytanie ze wszystkimi warstwami w
  `LAYERS`/`QUERY_LAYERS` (`SkorowidzeNMT2026,2025,2024,2023iStarsze`):
  4 rekordy (2025, 2024, 2023, 2022).
- `nmt/N-34-130-D-d-1-1/nmt1_krn__all.body` — NMT 1 m KRON86
  (`SkorowidzeUkladKRON86`), jedno zapytanie ze wszystkimi warstwami
  (`SkorowidzeNMT2019,2018,2017iStarsze`): 1 rekord.

Rozpoznanie 2026-10-10: zapytanie z kilkoma warstwami po przecinku zwraca
rekordy wszystkich warstw w jednej odpowiedzi (porownane z zapytaniami per
warstwa dla 1 m EVRF2007: te same 4 pliki) — podpowiedz wariantu wysyla
jedno zapytanie na wariant.

Testy: `tests/test_real_gugik_responses.py` (`TestVariantHintOnRealBodies`).
