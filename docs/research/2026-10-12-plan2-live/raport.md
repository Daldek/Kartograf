# Weryfikacja na zywo planu 2/3 magazynu wersjonowanego (2026-10-12)

**Zakres:** Task 13 planu `docs/superpowers/plans/2026-10-12-versioned-store-2-laz-cz-cutouts.md`
na galezi `feat/versioned-store` (`07eb8db`). CLI z `.venv`, z korzenia repo,
kazde polecenie z jawnym `--output` w
`<katalog-danych>/kartograf/e2e/2026-10-12-plan2-live/` (udzial SMB bez
`serverino`), polecenia sekwencyjnie. Skrypt `run.sh` i pelny log `log.txt`
leza obok danych (424 MB). Kodu nie zmieniano.

## Wynik

| Krok | Polecenia | Wynik |
|---|---|---|
| 1 LAZ (bbox `487000,637400,487050,637450`, 2 naloty) | pobranie, rerun, `--check-updates --plan`, `--force`, `--all-campaigns` | PASS: `nowa wersja 2024-09-08_81240_3a5ecfd2` -> `lokalna wersja` (zero pobran) -> `aktualne` -> `bez zmian` -> starszy nalot `nowa wersja 2019-04-17_72834_3d99c0d7`, nowszy `lokalna wersja`; licznik `Nowe/.../lokalne`; 2 wersje, kazda sciezka standardowa = ten sam plik (nlink 2) |
| 2 SM5 `CTES96` | pobranie, rerun, `--check-updates`, `--upgrade`, `--force` | PASS: `nowa wersja 2026-10-12_a1e327bb` -> `lokalna wersja` (jedno `HEAD`) -> `aktualne` -> `lokalna wersja` -> `bez zmian`; sidecar wersji `extra.http` = `ETag "d19f2c604d89dc1:0"`, `Last-Modified`, `Content-Length` ZIP; sha256 dowiazania = wersji |
| 3 TM33 `302_5550` | pobranie, rerun, `--upgrade`, `--force` | PASS: rerun `lokalna wersja ... (bez sprawdzania; --check-updates)` bez sieci; `--upgrade` -> `Info: ... niesprawdzona ... --force`; `--force` -> `bez zmian` |
| 3b wycinek CZ (EPSG:5514, 200 x 200 m) | jw. | PASS: jak TM33; `bbox/<wsp>.tif` bez daty, wersja w `versions/bbox/` |
| 4 wycinek PL EPSG:2180 i EPSG:3045 | pobranie, rerun, `--check-updates`, `--force` | PASS: rerun bez zapytan PRG/WCS, `nie da sie sprawdzic bez pobrania`, `--force` = `bez zmian` (bajty powtarzalne). EPSG:3045 `--force` raz `Error:` po 3 x `RemoteDisconnected` hosta GUGiK (kod 1, poprzednia wersja i dowiazanie nietkniete); powtorka: `bez zmian` |
| 5 `--country auto` (Cieszyn, `--target-crs EPSG:3045`) | `--check-updates --plan`, `--upgrade --plan`, rerun | PASS: jeden plan z pozycjami `cz_cutout` i `pl_cutout` (`missing`), `--upgrade --plan` pobral obie, rerun: dwie `lokalna wersja` |
| 6 D24 | zwykly plik `302_5550.tif` + sidecar bez `extra.link`, potem pobranie | PASS: plik zastapiony hardlinkiem do nowej wersji (nlink 2, sidecar dowiazania z `extra.link`) |

## Obserwacje

- `stat` tuz po zapisie na udziale SMB pokazywal czasem nlink 1 dla sciezki
  standardowej (cache atrybutow klienta CIFS); po chwili 2, sha256 rowne,
  sidecar dowiazania `extra.link = hardlink`. Kazdy rerun rozpoznal
  dowiazanie (statusy `lokalna wersja`/`bez zmian`, bez ponownego
  dowiazywania) — przypadek z wczesniejszego smoke'u sie nie powtorzyl.
- Jednostka w raporcie `--check-updates` wycinka to wspolrzedne (pole
  `unit` planu), a w linii statusu pobrania sciezka pod `--output`.
- Host WCS GUGiK zrywa polaczenia (`RemoteDisconnected`) jak w poprzednich
  pomiarach; ponowienia zwykle wystarczaja.
