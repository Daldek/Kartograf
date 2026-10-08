# Surowe odpowiedzi WFS LAZ GUGiK (runda E2E 2026-10-06)

Zrodlo: `<katalog-danych>/kartograf/e2e/2026-10-06-brzegowe/b/raw/C13/`
(pobrane 2026-10-06). Pliki skopiowane BEZ edycji i bez przycinania.

- `caps_EVRF2007.xml`, `caps_KRON86.xml` — GetCapabilities (lata warstw).
- `w2_<EVRF2007|KRON86>_<rok>.xml` — GetFeature obszaru "w2" (kafle
  `7.173.21.06.2` PL-2000:S7 2022 oraz `N-34-139-A-c-1-1-3-4` PL-1992
  w 2023/2025; KRON86: 2012 i 2018 z `format` = `LAS` mimo `.laz`).
  Pliki ~820 B to puste kolekcje lat bez kafli w tym obszarze.

Testy: `tests/test_real_gugik_responses.py` (C13).
