# Surowe odpowiedzi WFS LAZ GUGiK (2026-10-10, wybor roku)

Zrodlo: `<katalog-danych>/kartograf/2026-10-10-year-range/fixtures-raw/`
(pobrane 2026-10-10 przez `GugikLazProvider.select_tiles`, zapytania jak w
kodzie: osie N,E, `COUNT=1000`, `STARTINDEX=0`). Pliki zapisane BEZ edycji
tresci (`response.content`). Kazdy zestaw odpowiada DOKLADNIE jednemu oknu
zapytania; pomocnik `laz_session` w `tests/test_real_gugik_responses.py`
sprawdza parametr `BBOX`.

- `caps_EVRF2007.xml`, `caps_KRON86.xml` — GetCapabilities (lata warstw;
  tresc identyczna z `real_2026_10_06/`).
- `w2_<EVRF2007|KRON86>_<rok>.xml` — GetFeature obszaru `W2_BBOX`
  (`637200,486900,637500,487100`, EPSG:2180, 300 x 200 m w Warszawie).
  2022: DWA kafle PL-2000:S7 (`7.173.21.06.1`, `7.173.21.06.2`), razem
  pokrywaja obszar; 2023 i 2025: `N-34-139-A-c-1-1-3-4` (PL-1992);
  KRON86: 2012 i 2018. Pozostale pliki (~820 B) to puste kolekcje.
  Zestaw `real_2026_10_06/` byl nagrany dla mniejszego okna C13
  (`637400,487000,637450,487050`) — dla `W2_BBOX` brakowalo w nim kafla
  `7.173.21.06.1`.
- `wro_EVRF2007_<rok>.xml` — GetFeature obszaru `WRO_BBOX`
  (`367331,369020,367381,369070`, 50 x 50 m w srodku arkusza
  `6.150.13.16.4`, Wroclaw). 2025: dwie dostawy NIE tego samego arkusza
  (`84048_1847378`, `84169_1850670`); PL-1992 `M-33-35-A-c-4-4-3-2`
  w 2019, 2022 i 2024 (TAK).
- `w3_EVRF2007_<rok>.xml` — GetFeature obszaru `W3_BBOX`
  (`627706,479258,628006,479558`, 300 x 300 m na zachod od Warszawy) na
  dwoch arkuszach PL-1992: `N-34-138-B-c-4-4-4-4` (2023, 2025) i
  `N-34-138-D-a-2-2-2` (tylko 2019). `--year 2019` i `--year 2025` daja
  konflikt na 1 z 2 kafli referencji (podpowiedz `--min-year` albo
  `--max-year`).

Testy: `tests/test_real_gugik_responses.py` (`TestLazDiscoveryOnRealWfs`),
`tests/test_laz_campaigns.py`.
