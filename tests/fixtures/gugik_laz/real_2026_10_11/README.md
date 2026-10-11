# Surowe odpowiedzi WFS LAZ GUGiK (2026-10-11, okna testow CLI)

Zrodlo: `<katalog-danych>/kartograf/2026-10-11-laz-windows/fixtures-raw/`
(pobrane 2026-10-11 przez `kartograf download --product laz` z sesja
zapisujaca odpowiedzi; zapytania jak w kodzie: osie N,E, `COUNT=1000`,
`STARTINDEX=0`). Pliki zapisane BEZ edycji tresci (`response.content`).
Kazdy zestaw odpowiada DOKLADNIE jednemu oknu zapytania; `wfs_session`
w `tests/test_laz_download.py` sprawdza parametr `BBOX`. GetCapabilities:
`real_2026_10_06/` (tresc identyczna).

- `wgs_EVRF2007_<rok>.xml` — `--bbox` w EPSG:4326 z
  `test_parent_request_keeps_bbox_in_given_crs` (okno EPSG:2180
  `637409.22,487009.99,637440.81,487039.98`, wewnatrz `W2_AREA`). Kafle jak
  dla `W2_AREA`: `7.173.21.06.2` (2022), `N-34-139-A-c-1-1-3-4` (2023, 2025).
- `sheet_EVRF2007_<rok>.xml` — godlo `N-34-139-A-c-1-1` (okno obwiedni
  arkusza `636487.03,486674.85,638684.36,489050.38`). 2022: 24 kafle
  PL-2000:S7, 2023 i 2025: po 33 kafle PL-1992; pozostale lata puste.

Okna obu testow wyboru kafli z `tests/test_laz_coverage.py` (nagrane tego
samego dnia, poza repo) nie odtwarzaja scenariuszy, ktore testy opisywaly:
na wschod od `W2_AREA` kafle 2025 (`N-34-139-A-c-1-1-3-4`, `-4-3`) kryja
obszar, a w rogu SW obwiedni `7.173.21.06.2` usluga sama nie zwraca tego
kafla (filtr po geometrii). Testy zastapione: `W3_BBOX` w
`tests/test_real_gugik_responses.py` (starszy kafel z odkryta czescia) oraz
jawne odtworzenie `test_all_still_drops_outside_tiles`
w `tests/test_laz_campaigns.py` (filtr obrysu po stronie klienta).

Testy: `tests/test_laz_download.py` (`TestCliOnRealWfs`).
