# Dokumentacja po fali naprawczej — 2026-09-30

Zakres: stan kodu po pakietach A1–A3, B1–B3; testy `live` nie były uruchamiane w tej fazie. Historia usterek i wyniki dawnych pomiarów pozostają w raportach `research-*`/`impl-*` oraz CHANGELOG; teksty opisujące bieżący stan nie przedstawiają naprawionych błędów jako aktywnych.

| Plik | Zmiany |
|---|---|
| `docs/CHANGELOG.md` | Fixed osobno dla K1–K6, S1–S5, N1–N9 i H1; migracja wyjątków, cache rekordów, API wycinka, sidecarów, kolor orto, 16 `live`, przestarzałe rastry z operacją „(3)”. |
| `README.md` | Znane problemy: R6, PL-2000 bez arkusza macierzystego, prostokąty krajów i różne fazy NMT 5 m; osobna uwaga migracyjna o starych plikach „(3)”, przykłady API, sidecary i status testów. |
| `CLAUDE.md` | Bieżące ograniczenia CZ/PL, kody R5 listy/hierarchii, clipping `auto`, pin EPSG:1622/1623, W1, cache i pochodzenie, LAZ/orto, struktura modułów i testy `live`. |
| `docs/ARCHITECTURE.md` | 3.2/3.4 sidecar i reużycie arkuszy; 4.2/4.3 wybór rekordu, R5, W1, all_nodata i cache; CZ 4 Mpx/pin/snap, LAZ osie, dyspozycja `auto`, wskazówki transformacji i indeks ADR-028. |
| `docs/SCOPE.md` | Zakres obecnego działania: PL-2000 NoCoverageError, W1/GridMismatchError, R5 listy, CZ 4 Mpx, ostrzeżenia clippingu/nodata, testy. |
| `docs/PRD.md` | Punktowa korekta sekcji LAZ o osi WFS i statusie snapshotu v0.6.1. |
| `docs/DECISIONS.md` | Errata ADR-020/021/023, ADR-024 errata 2, ADR-027 addendum oraz nowy ADR-028: twardy wybór rekordu i `extra.source`. |
| `docs/DEVELOPMENT_STANDARDS.md` | Struktura PL/cache i liczba testów `live`, nota o kontraście `DownloadError`/`NoCoverageError`. |
| `docs/IMPLEMENTATION_PROMPT.md` | Cache rekordów/`--force`, mozaika W1/GridMismatchError i budżet CUZK. |
| `kartograf/cli/_parser.py` | Usunięty ogólny komunikat o znanych błędach z `download --help`; opisy produktów RGB/LAZ bez not K1/K5. |

Weryfikacja: uruchomiono `.venv/bin/python -m kartograf.cli.commands --help` oraz `... download --help`; oba kończą się kodem 0, pomoc `download` nie zawiera ostrzeżeń K1/K5 (proces wypisał ostrzeżenie `runpy` o wcześniejszym imporcie `commands`, niezwiązane z treścią pomocy). Wyszukiwanie aktywnych not o naprawionych błędach w wskazanych plikach nie dało trafień. Brama 2057 testów offline i 32 istniejących ostrzeżeń mypy pochodzi z przekazanego stanu koordynatora, nie była ponawiana przy równoległej aktualizacji dokumentacji.