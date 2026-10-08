# Review fali naprawczej — 2026-09-30

Zrodlo: `agent://ReviewFala` (5 znalezisk, bez blokujacych).

| Znalezisko | Skutek przed poprawka |
|---|---|
| LAZ `--year` nieistniejacy | GetFeature dla nieistniejacej warstwy konczyl sie `ExceptionReport` z mylaca sugestia ponowienia. |
| S3 `Info:` dla geometrii | PL wyznaczal arkusze z calej geometrii, lecz CLI niezgodnie z prawda informowalo o przycieciu PL i utracie obszaru. |
| Negatywny cache skorowidza | Ponowne wywolanie gubilo podpowiedz `NoCoverageError` o rozdzielczosci, ukladzie, potomku lub wariancie orto. |
| Dwie petle wyboru arkusza | NMT i orto powielaly ten sam kod cache/warstw/wyboru/bledu. |
| Testy `LAYER_PATTERN` | Dwa testy przypinaly stala wyrazenia regularnego NMPT zamiast zachowania GetCapabilities. |

## Poprawki po review

1. **LAZ `--year`:** `discover_tiles` sprawdza jawny rok przez GetCapabilities wybranego ukladu przed GetFeature i podaje dostepne lata bez `ponow pobranie`. Test `test_unknown_year_reports_available_years_without_retry` byl czerwony przed zmiana (brak wyjatku); test nieczytelnej odpowiedzi istniejacego rocznika nadal sprawdza realny blad WFS.
2. **S3 `Info:`:** PL w `--geometry` bez `--target-crs` nie generuje komunikatu o przycieciu/utracie; CZ nadal informuje o przycieciu, a lista arkuszy PL z `--bbox` mowi o `request.godlo`, nie `request.bbox`. Testy `test_geometry_auto_clipping_does_not_print_pl_info`, `test_geometry_auto_informs_only_clipped_cz` i `test_rozewie_clips_only_north_edge_and_informs` obejmuja te sciezki.
3. **Cache negatywny:** wspolna petla zapisuje `{"no_coverage": true, "message": ...}` i odtwarza pelna tresc `NoCoverageError` przy trafieniu bez sieci. Testy `test_negative_cache_preserves_resolution_hint` i `test_negative_cache_preserves_variant_hint` byly czerwone przed zmiana (utrata podpowiedzi), po zmianie przechodza.
4. **Skorowidz:** jedna petla `_resolve_record` w `SkorowidzLayersMixin` obsluguje oba providery; NMT/NMPT i orto przekazuja klucz cache, endpoint, filtry i funkcje `_no_coverage`. Dotychczasowe testy providerow i walidacji warstw przechodza bez zmiany wyboru kampanii.
5. **NMPT:** usunieto `test_layer_pattern_is_nmpt` i `test_pattern_accepts_only_nmpt_names`; pozostaja behawioralne `test_fetch_wms_layers_returns_only_nmpt` i test filtrowania warstw GetCapabilities.

Weryfikacja po zmianie: testy jednostkowe dotknietych providerow (199 passed), scenariusze auto bbox/geometry CLI (45 passed); ogolnoprojektowa brama wykonywana po scaleniu zmian.
