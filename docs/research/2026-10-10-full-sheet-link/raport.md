# Weryfikacja na zywo: `full_sheet/` i `--full-sheet` (ADR-033)

**Data:** 2026-10-10
**Galaz:** `feat/full-sheet-link` (commity Task 1-5 planu
`docs/superpowers/plans/2026-10-10-full-sheet-link.md`)
**Srodowisko:** CLI `.venv/bin/kartograf` z korzenia repo, jawne `--output`
w katalogu danych wskazanym przez uzytkownika (udzial SMB, poza repo
i `/tmp`; sciezka nie jest zapisywana w repo — ponizej `<out>`).

## Wyniki

| # | Polecenie | Oczekiwane | Wynik |
|---|---|---|---|
| 1 | `download N-34-139-C-a-3-4` | `full_sheet/` = ten sam inode co standard | najnowszy lot 83998 (2026-04-05, TAK); `stat -c %i`: standard i `full_sheet/` = 6506, `st_nlink` 3 (kampania + 2 dowiazania); bez `Warning:` |
| 2 | `download N-34-139-C-a-3-1` | 1 plik, `Warning:` z podpowiedzia | 1 plik (`kampanie/2025-10-21_84183`), brak `full_sheet/`; `Warning: ... pelny lot nie pobrany: N-34-139-C-a-3-1 — uzyj --full-sheet` |
| 3 | `download N-34-139-C-a-3-1 --full-sheet` | 84183 + 83233, `full_sheet/` -> 83233 | `Downloaded 1 campaign files for 1 sheets ... (1 already existed)` (84183 z kroku 2); standard = inode 84183, `full_sheet/` = inode 83233; `extra.link_target` -> `kampanie/2025-04-27_83233/...`; sidecar 83233 `request.full_sheet: true`; `Warning: ... pelny lot w <segment>/full_sheet/: N-34-139-C-a-3-1` |
| 4 | powtorka 3 | Skipped, ten sam `Warning:`, bez pobrania | `Skipped N-34-139-C-a-3-1 - already exists at <out>/...`; identyczny `Warning:`; kod 0 |
| 5 | `download M-34-90-C-b-4-4 --product orto --full-sheet` | 84466 + 81437, `full_sheet/` -> 81437 | `Downloaded 2 campaign files for 1 sheets ... (0 already existed)`; standard = inode `2026-04-25_84466`, `full_sheet/` = inode `2024-06-26_81437`; `Warning:` z `full_sheet/` |
| 6a | `download N-34-139-C-a-3-1 --product laz --full-sheet` | `Error:` przed siecia | `Error: --full-sheet dziala tylko z NMT/NMPT/orto (podano laz) ...`, kod 1, katalog wyjscia nie powstal |
| 6b | `download --bbox 530000,382000,533000,386000 --country pl --target-crs EPSG:2180 --full-sheet` | `Error:` przed siecia | `Error: --full-sheet nie dziala z --target-crs ...`, kod 1 |

## Uwagi

- Plan (Task 2, F1) podawal dla N-34-139-C-a-3-4 najnowszy lot 84183;
  skorowidz (nagrania 2026-10-06 i stan na zywo) ma nowszy pelny lot 83998
  (2026-04-05). Testy offline uzywaja 83998.
- Krok 3 nie pobral 84183 ponownie (lokalny z kroku 2), stad
  "1 campaign files ... (1 already existed)" zamiast "2 campaign files"
  ze scenariusza F3 specu (ten wariant zakladal czysty katalog; offline
  `test_flag_fetches_full_flight_and_warns_once` sprawdza 2 pliki).
- Krok 5 wypisal ostrzezenie loggera
  `Warstwa SkorowidzeOrtofotomapyStarsze: nieprawidlowe godlo
  'M-34-90-C-b-4-4-4'` — pochodzi z pelnej listy warstw skorowidza
  (`_resolve_all`), ktora `--full-sheet` czyta dla arkusza z niepelnym
  najnowszym lotem; to samo ostrzezenie daje `--campaigns all`. Rekord
  odrzucony, wynik poprawny.
- Hardlinki na udziale SMB dzialaja (ten sam inode, `st_nlink` rosnie).
