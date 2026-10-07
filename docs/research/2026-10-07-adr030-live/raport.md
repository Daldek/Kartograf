# ADR-030 — weryfikacja na zywo (T12), 2026-10-07

Kod: develop `19100b6` (ADR-030 T1-T11 + poprawki). Dane: `<katalog-danych>/kartograf/e2e/2026-10-07-adr030-kampanie/`
(CIFS SMB 3.1.1, `reparse=nfs`), cache SQLite lokalnie (cwd = repo), `kartograf cache clear` przed krokiem 1.
Straze "bez sieci" sprawdzane z zablokowanym `socket.connect` (wywolanie `main()` CLI w procesie).

## Wynik: 15/15 krokow planu (sekcja 6) PASS + fallback I-1 PASS

| Krok | Wynik |
|---|---|
| 1 newest N-34-139-C-a-3-1 | PASS — plik w `kampanie/2025-10-21_84183/...`, sciezka standardowa = dowiazanie (**hardlink**, patrz O-1), sidecar `extra.link=hardlink`, `link_target` wzgledny, `campaign.id=84183`, `full_sheet=false`, `request={godlo, campaigns: newest}`; `Warning:` E13 |
| 2 powtorka | PASS — `Skipped ...`, plik bez zmian (`ls --full-iso`), 0,4 s |
| 3 `--campaigns all` | PASS — 4 katalogi (73021, 78047, 83233, 84183), `Downloaded 3 campaign files for 1 sheets ... (1 already existed)`, link nadal 84183. Piksele danych: 84183 **41,4 %**, pozostale ~94,6 % (patrz O-2) |
| 4 `--min-year 2026` | PASS — `Error: Najnowsza kampania N-34-139-C-a-3-1 ma date 2025-10-21 — starsza niz min_year=2026 (--min-year)`, kod 1 |
| 5 `all` + `min_year=2024` (biblioteka, refresh) | PASS — GetFeatureInfo tylko 2026/2025/2024, bez `SkorowidzeNMT2023iStarsze`; wynik 84183, 83233 |
| 6 brak migracji | PASS — zwykly plik (nlink 1, bez sidecara) zastapiony dowiazaniem do 84183, sidecar odtworzony |
| 7 usunieta kampania | PASS — przy hardlinku zostaje zwykly plik (nie wiszacy link); rozpoznany po `link_target`, kampania pobrana ponownie i dowiazana |
| 8 orto M-34-90-C-b-4-4 | PASS — newest 84466 (2026-04-25, `Warning:` E13); `all --min-year 2024` -> 84466 + 81437 (RGB), brak CIR, `orto/pl_1992/kampanie/` |
| 9 orto `--min-year 2022` | PASS — odpytane 2026/2025/2024/`Starsze`; wynik 84466, 81437, 76530; 73121 (2019) odfiltrowany |
| 10 wycinek `--target-crs EPSG:2180` | PASS — 16 arkuszy przez dowiazania, `sheet_sources` z URL-ami kampanii (84183/83233/83998), `Warning:` o 4 niepelnych; `--campaigns all` i `--min-year 2024` -> `Error:` kod 1 bez sieci |
| 10a `.xyz` N-33-69-A-d-3-2 | PASS — 5 kampanii, `2019-04-29_72675/.../N-33-69-A-d-3-2.asc` (`ncols`, rasterio `AAIGrid`), 0 plikow `.xyz`, sidecar z URL `.xyz`, link -> `2024-09-23_81025`; kazdy plik w `kampanie/` ma `.meta.json` (N-1) |
| 11 CZ | PASS — `302_5550 --country cz --campaigns all`, `302_5550 --min-year 2020` (auto), bbox w calosci CZ -> `Error: CZ (CUZK) nie ma kampanii ...` kod 1 bez sieci; pogranicze `--campaigns all` -> `Info:` raz, wycinek CZ + 12 plikow kampanii PL (2 arkusze), kod 0 |
| 12 LAZ W2 | PASS — newest: 1 kafel 2025 (3 `covered`); `all`: 4 kafle (2022/PL-2000 x2, 2023, 2025); `min_year=2025`: 1; `--year 2023 --min-year 2024` -> `Error:` kod 1; pobrany kafel ma `request.min_year=2025` |
| 13 CIFS | PASS z zastrzezeniem O-1 — `os.replace`, hardlink, odczyt rasterio przez sciezke standardowa dzialaja na udziale; symlink NIE (limit celu) |
| 14 Hydrograf | PASS — `DownloadManager(out).download_sheet(...)` zwraca sciezke standardowa, rasterio (422, 255), `last_sheet.skipped=True`, `link=hardlink` |
| 15 cache stats | PASS — `Campaign entries: 5` |
| I-1 (dodatkowo) | PASS — siec zablokowana: biblioteka bez cache -> `logger.warning` + lokalna 84183, `skipped=True`, `unverified`; CLI `-q` -> `Warning: ... skorowidz GUGiK niedostepny — uzyto lokalnej kampanii ...`, kod 0 |

## Obserwacje

- **O-1 (wazne dla dokumentacji): udzial CIFS katalog danych przyjmuje cel symlinku najwyzej 77 bajtow** (`reparse=nfs`;
  78+ -> `OSError: [Errno 5] EIO`). Wzgledne cele kampanii maja ~82+ znakow
  (`../../../../../../kampanie/2025-10-21_84183/N-34/139/C/a/3/1/N-34-139-C-a-3-1.asc`), wiec kod schodzi do
  hardlinka (zgodnie z R4/R5) — zachowanie poprawne, ale twierdzenie z ADR/planu "symlink zweryfikowany na SMB 3.1"
  nie dotyczy tego udzialu. Skutek hardlinka: usuniecie katalogu kampanii zostawia zwykly plik (nie wiszacy link) —
  obsluzone (krok 7).
- **O-2: pokrycie 84183 = 41,4 % pikseli danych** (pozostale kampanie ~94,6 %), a `pokrycie-kampanii.md` podawalo
  0,9 % dla N-34-139-C-a-3-1 — rozna metoda pomiaru albo inna miara; wniosek jakosciowy (najnowsza kampania znacznie
  ubozsza) potwierdzony.
- **O-3 (UX, drobne):** CLI wypisuje `Downloading <godlo> (...)...` takze, gdy wynik to `Skipped` albo `Error:`
  (kroki 2, 4) — linia drukowana przed rozwiazaniem rekordu.
- **O-4 (drobne):** `--campaigns all` dla orto (krok 8b) nie powtarza `Warning:` E13 o niepelnej najnowszej
  kampanii (newest go drukuje).
- **O-5:** wycinek z bboxa ramy N-34-139-C-a-3 w EPSG:2180 objal 16 arkuszy (szersza obwiednia WGS84 — znane
  zachowanie `find_sheets_for_bbox`).

Dane: 929 MB na katalog danych (NMT 1 m, 3 arkusze orto, 1 kafel LAZ, wycinki PL/CZ).
