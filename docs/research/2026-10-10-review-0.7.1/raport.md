# Przebieg na zywo galezi `fix/review-0.7.1` (2026-10-10)

Galaz `fix/review-0.7.1` (drobiazgi z review 0.7.1, spec
`docs/superpowers/specs/2026-10-09-review-0.7.1-drobiazgi-design.md`).
CLI z korzenia repo (cache metadanych lokalnie), dane w
`<katalog-danych>/kartograf/e2e/2026-10-10-review-0.7.1/` z jawnym
`--output`. Skrypty biblioteczne jednorazowe, poza repo.

| # | Wywolanie | Wynik | Ocena |
|---|---|---|---|
| 1 | `GugikProvider(resolution="5m")._resolve_sheet("N-34-130-D-d-1-1")` i `-2-4` (bez cache) | `NoCoverageError`, `hints`: `Skorowidz GUGiK ma ten arkusz w NMT 1m EVRF2007 — uzyj --resolution 1m` oraz `... NMT 1m KRON86 — uzyj --resolution 1m --vertical-crs KRON86`; ok. 1,3 s na arkusz | PASS |
| 1a | to samo przed poprawka etykiety | falszywe `Warstwa wariant 1m EVRF2007: rekord ... ma rok 2025 poza partycja warstwy` (parser bral `EVRF2007` z etykiety za rok warstwy) — poprawione (`fix(gugik): etykieta zapytania wariantu bez roku na koncu`), test w `test_variant_hint_for_5m_gap` | naprawione |
| 2 | `GugikProvider(resolution="5m")._resolve_sheet("N-33-46-C-a-1-1")` (arkusz bez rekordu w zadnym wariancie) | `NoCoverageError` bez podpowiedzi wariantu, ok. 1,2 s (koszt zapytan wariantow) | PASS |
| 3 | `kartograf download N-34-130-D-d --resolution 5m --force --output <...>/data -q` | kod 0, 10 z 16 arkuszy; `Warning: GUGiK nie ma danych dla 6 z 16 arkuszy (...) — pominiete (skorowidz GUGiK nie ma tych arkuszy dla wybranego produktu i rozdzielczosci, np. morze, obszar za granica, brak NMT 5 m w czesci kraju); pobrano 10`, dwie linie `Info:` z wariantami 1 m | PASS |
| 4 | to samo bez `--force` (cache metadanych) | kod 0, ten sam `Warning:` i `Info:` z cache, 0,5 s | PASS |
| 5 | `LandCoverManager(provider="bdot10k").download(teryt="0224", keep_raw=True)` dwa razy pod rzad | oba razy GPKG 147 MB, `sha256` sidecara = skrot pliku, `extra.source.raw_file` = `bdot10k_teryt_0224_GPKG.zip`; w katalogu tylko GPKG, ZIP i ich sidecary (bez `*.tmp`) | PASS |
| 6 | WFS PRG z dziesietnym `BBOX` (`294999.5,344999.5,295000.5,345000.5`, `290000.4,340000.6,...`) | HTTP 200, te same kody co dla liczb calkowitych (`0224`; `0208`, `0224`) | PASS |

## Wniosek

Zmiany P1-P10 dzialaja na zywo; jedyny blad wykryty w przebiegu (falszywe
ostrzezenia o roku warstwy w zapytaniu wariantu) poprawiony na galezi
i objety testem.
