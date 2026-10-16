# Surowe odpowiedzi WFS LAZ GUGiK (2026-10-16, test na zywo wydania 0.8.0)

Zrodlo: `<katalog-danych>/fix-live-0.8.0/laz-raw/` (pobrane 2026-10-16
przez `GugikLazProvider.select_tiles` z sesja zapisujaca odpowiedzi;
zapytania jak w kodzie: osie N,E, `COUNT=1000`, `STARTINDEX=0`). Pliki
zapisane BEZ edycji tresci (`response.content`). GetCapabilities:
`real_2026_10_06/` (tresc identyczna 2026-10-16).

- `sheet4_EVRF2007_<rok>.xml` — godlo `N-34-130-D-d-2-4` (Krakow, przyklad
  z USAGE 1.1; okno obwiedni arkusza w EPSG:2180
  `769911.09,508419.16,772163.73,510851.57`). Tylko 2025 ma kafle: 13 kafli
  1:5000 PL-1992 - 4 kafle arkusza (`N-34-130-D-d-2-4-1..4`) i 9 sasiadow,
  ktorych rama styka sie z rama arkusza (czesc wspolna 0-17 m2, naroznik
  `N-34-131-C-c-3-1-1` zachodzi na obwiednie o 4,6 mm). Pozostale lata puste.

Test na zywo (P2-1): wybor z obwiedni dawal 13 kafli (1,83 GB), z ramy
arkusza wynikaja 4 kafle.

Testy: `tests/test_laz_download.py` (`_WINDOWS["sheet4"]`).
