# Implementacja E18: testy regresyjne na surowych odpowiedziach GUGiK

Galaz `test/fixtures-2026-10-06`. Kod w `kartograf/` bez zmian (`git diff kartograf/` pusty).
Testy: `tests/test_real_gugik_responses.py` (28 testow). Suita offline: 2153 passed.

## Fixtury (kopie bez edycji, zrodlo `<katalog-danych>/kartograf/e2e/2026-10-06-brzegowe/`)

| Katalog w repo | Zrodlo | Pliki | Rozmiar | Przypadki |
|---|---|---|---|---|
| `tests/fixtures/gugik_skorowidz/real_2026_10_06/nmt/<godlo>/` | `a/raw/recon/<godlo>/` | 9 godel (4 lub 3 warstwy kazde) | ok. 440 KB | C1b, C3, C6, C6f/g, C9, C9a, C10g |
| `.../nmt/c14/` | `b/raw/C14/` | 16 HTML (4 arkusze x 4 warstwy) | ok. 130 KB | C14 |
| `.../orto/` | `b/raw/C12/` | 12 HTML (3 godla x 4 warstwy) | ok. 130 KB | C12 |
| `tests/fixtures/gugik_laz/real_2026_10_06/` | `b/raw/C13/` | 19 `w2_*.xml` + 2 `caps_*.xml` | 132 KB | C13 |

Lacznie 85 plikow z README (skorowidz 708 KB, LAZ 132 KB). Zaden plik nie przekroczyl 100 KB,
wiec WFS nie byl przycinany. README w kazdym katalogu opisuje zrodlo, date i przypadki.

## Testy i dowody mutacyjne

Mutacje wykonywane tymczasowo w `kartograf/` (skrypt: podmiana tekstu, pytest, `git checkout`),
liczba oznacza ile testow padlo. Wszystkie mutacje wywrocily co najmniej jeden test.

| ID | Mutacja kodu produkcyjnego | Plik | Padlo |
|---|---|---|---|
| M1 | wybor najstarszej kampanii (`>` -> `<` w porownaniu krotek) | skorowidz.py | 11 |
| M2 | `dt_pzgik` przed `aktualnosc` w kluczu wyboru | skorowidz.py | 1 |
| M3 | usuniecie filtra rozdzielczosci | skorowidz.py | 3 |
| M4 | godlo rekordu jako prefiks zadania (`startswith`) zamiast calego tokenu | skorowidz.py | 4 |
| M22 | odwrotnie: rodzic pasuje do zadania potomka (`godlo.startswith(record.godlo)`) | skorowidz.py | 1 |
| M5 | brak normalizacji godla rekordu (`SheetParser(...).godlo`) | skorowidz.py | 1 |
| M6 | preferencja pelnego arkusza (pomijanie `full_sheet is False`) | skorowidz.py | 5 |
| M7 | filtr rozszerzenia URL (tylko `.asc`) w parserze | skorowidz.py | 8 |
| M8 | `to_source` gubi `full_sheet` | skorowidz.py | 5 |
| M9 | warstwy od najstarszej zamiast od najnowszej | skorowidz.py | 14 |
| M10 | brak podpowiedzi w tresci `NoCoverageError` | gugik.py | 3 |
| M11 | brak podpowiedzi "ma ten arkusz w X m" | gugik.py | 1 |
| M12 | brak podpowiedzi o arkuszu w PL-1992 | gugik.py | 1 |
| M13 | brak podpowiedzi o potomku PL-2000 (`--scale`) | gugik.py | 2 |
| M14 | orto: brak filtra koloru (`predicate=None`) | gugik_orto.py | 1 |
| M15 | orto: `extra.source.kolor` nie zapisywany | gugik_orto.py | 2 |
| M16 | LAZ: dedup zostawia najstarszy rok | gugik_laz.py | 3 |
| M17 | LAZ: brak filtra `min_density` | gugik_laz.py | 1 |
| M18 | LAZ: `year` ignorowany | gugik_laz.py | 1 |
| M19 | LAZ: nazwa pliku z formatu (`.las`) zamiast z URL | gugik_laz.py | 1 |
| M20 | LAZ: `PL-2000*` -> uklad "1992" | gugik_laz.py | 1 |
| M21 | LAZ: KRON86 odpytuje endpoint EVRF2007 | gugik_laz.py | 2 |

Mapowanie test -> mutacje, ktore go wywracaja:

| Test | Przypadek | Mutacje |
|---|---|---|
| test_c1b_several_campaigns_in_one_layer_newest_wins | C1b (77381) | M1 |
| test_c3_layer_2025_only_half_metre_falls_through_to_1m_older_layer | C3 (78954_1462161) | M1, M3, M9 |
| test_c3_pooled_records_pick_resolution_by_request | C3 | M1, M3 |
| test_c6_two_records_of_same_pl2000_sheet_newest_wins | C6 (77912) | M1 |
| test_c6_pl1992_sheet_in_same_body_ignores_pl2000_records | C6 | M9 |
| test_campaign_date_beats_dt_pzgik | N-33-69-A-d-3-2 (81025 mimo pozniejszego dt_pzgik 81616) | M1, M2, M9 |
| test_c9_xyz_record_is_parsed_but_never_decides | C9 `.xyz` | M1, M7 |
| test_c9_uppercase_asc_record_is_available_but_loses_to_newer_layer | C9 `.ASC` | M6, M7, M9 |
| test_c9a_lowercase_godlo_in_record_is_normalised | C9a | M5, M9 |
| test_c6f_pl2000_1_10000_hints_descendant_scale_and_pl1992_sheet | C6f | M4, M10, M12, M13 |
| test_c6g_pl2000_kron86_hint_points_to_1_2000 | C6g | M4, M9, M10, M13 |
| test_c10g_nmpt_only_half_metre_names_the_resolution | C10g | M3, M10, M11 |
| test_c12_cir_comes_from_2024_when_newer_layer_has_only_rgb | C12 CIR 2024 0,25 m | M7, M9, M14, M15 |
| test_c12_rgb_comes_from_2025_at_5_cm | C12 RGB 2025 0,05 m | M7, M9, M15 |
| test_c12_token_parent_request_never_takes_child_records | C12 token | M4, M7 |
| test_c12_token_child_request_never_takes_parent_record | C12 token | M1, M7, M22 |
| test_c12_record_with_full_sheet_false_wins_adr_028 | C12 ADR-028 | M6, M7, M8, M9 |
| test_c12_pl2000_sheet_takes_own_record_not_descendants | C12 (75063) | M1, M4, M7 |
| test_c14_each_sheet_gets_its_own_newest_campaign (4 parametry) | C14 | M1/M6/M8/M9 (a-3-1, a-3-3), M8/M9 (a-3-2, a-3-4) |
| test_c14_four_sheets_four_distinct_sources_two_prefixes | C14 | M1, M6, M9 |
| test_c13_evrf2007_two_tiles_in_two_horizontal_systems | C13 | M16, M20 |
| test_c13_year_2023_returns_the_single_older_tile | C13 `--year` | M18 |
| test_c13_min_density_13_drops_the_12_p_m2_tile | C13 | M17 |
| test_c13_kron86_returns_2018_tile_not_2012 | C13 KRON86 | M16, M21 |
| test_c13_las_format_in_wfs_still_yields_dot_laz_filename | C13 `LAS` | M16, M19, M21 |

Poprawki po pierwszym przebiegu mutacji: test "ten sam godlo 2023 i 2025" (asercja tylko
na liste odpytanych lat) nie wywrocil zadna sensowna mutacja, wiec go usunieto (dedup
broni test dwoch kafli, M16). Test "potomek nie bierze rodzica" przechodzil pod M22
(rodzic ma starsza aktualnosc), przepisany na pule rekordow samego rodzica: wynik `None`.

## Czego nie dalo sie przetestowac i dlaczego

- C12-f (CIR i RGB dziela sciezke), Warning o niepelnym arkuszu (E13), `--force` zapis cache
  (E14), komunikaty skip (E15), `year`/`min_density` w sidecarze LAZ (E16), parser ukladu
  (D3): wymagaja zmian kodu, robi je agent naprawczy (poza zakresem).
- Remis `aktualnosc` rozstrzygany `dt_pzgik`/URL: brak remisu w danych na zywo; sam kolejny klucz
  (`dt_pzgik` przed `aktualnosc`) jest chroniony przez test N-33-69-A-d-3-2.
- C6b/C6h (plik PL-2000 w wspolrzednych EPSG:2180, E17): to zachowanie sidecara przy
  prawdziwym naglowku `.asc` (11 MB per plik na katalog danych); kopiowanie naglowkow odpada,
  a asercja wymaga zapisu pliku przez manager. Test selekcji rekordu 77912 jest (C6).
- C14 `missing_sheets`/`off_grid_sheets`/`all_nodata` w wycinku: wymaga rastra i mozaiki,
  w fixturach tylko skorowidz; testowane jest tylko pochodzenie arkuszy (`sheet_sources`).
- C11 (`xllcorner`, `NODATA_value`, niecalkowity `cellsize`): pliki ASC sa duze, naglowki
  nie ma w `raw/`; poza zakresem tej fali.
- Sidecar i sciezka pliku LAZ/orto: testy ida do poziomu providera (rekord/kafel),
  nie przez CLI/managera.
