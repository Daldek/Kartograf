# Surowe odpowiedzi skorowidza GUGiK (runda E2E 2026-10-06)

Zrodlo: `<katalog-danych>/kartograf/e2e/2026-10-06-brzegowe/`
(zapytania GetFeatureInfo `text/html` do warstw skorowidzow, pobrane 2026-10-06).
Pliki skopiowane BEZ edycji tresci; tylko wybrany podzbior rundy.

- `nmt/<godlo>/<prefiks>__<warstwa>.body` — z `a/raw/recon/<godlo>/`
  (prefiks: `nmt1_evr` NMT 1 m EVRF2007, `nmt1_krn` NMT 1 m KRON86,
  `nmt5_evr` NMT 5 m, `nmpt_evr` NMPT EVRF2007). Przypadki: C1b
  (M-34-66-B-a-2-1), C3 (M-33-57-C-b-4-2), C6 (M-34-64-D-d-2-3, 6.129.30,
  5.167.25), C9 (N-33-69-A-d-3-2 `.xyz`, N-33-115-C-d-2-2 `.ASC`),
  C9a (N-33-59-C-a-1-3, godlo malymi literami), C10g (N-33-77-A-d-2-2).
- `nmt/c14/<godlo>_EVRF2007_<warstwa>.html` — z `b/raw/C14/`: cztery arkusze
  N-34-139-C-a-3-{1..4} z roznych kampanii (C14).
- `orto/<godlo>_<warstwa>.html` — z `b/raw/C12/`: N-34-139-A-c-1-1,
  M-34-90-C-b-4-4, 7.173.21.01 (C12: RGB/CIR, token godla, niepelny arkusz
  2026, PL-2000). Pliki `7.173.21.01_*` poza `Starsze` sa bajtowo rowne
  plikom N-34-139-A-c-1-1 (ten sam punkt zapytania).

Testy: `nmt/` - prawdziwe rekordy `SkorowidzRecord` dla kampanii i wyboru
arkusza (`tests/test_campaigns.py`, `tests/test_manager_campaigns.py`; od
0.8.0 pobieranie NMT/NMPT czyta skorowidz WFS, ADR-041, a odpowiedzi WFS sa
w `tests/fixtures/gugik_wfs/`); `orto/` - `tests/test_real_gugik_responses.py`,
`tests/test_provider_campaigns.py`.
- `caps/ORTO_WMS_SkorowidzeWgAktualnosci.xml` — surowe GetCapabilities WMS
  ortofotomapy (ADR-030, rodzina nazw warstw) z `b/raw/C12/caps.xml` (poza
  warstwami skorowidza: `default`, `WMS`, `SkorowidzeOrtofotomapyZasiegi*`).
  GetCapabilities WMS NMT/NMPT usunieto w 0.8.0 (nieuzywane po przejsciu
  na WFS). Testy: `tests/test_wms_layer_validation.py`.
