# Plan: zwykly zapis `-o` domyslnie, magazyn na zadanie `--store` (0.8.0)

**Data:** 2026-10-23
**Status:** projekt do akceptacji uzytkownika
**Spec:** `docs/superpowers/specs/2026-10-23-plain-output-design.md` (D1-D15)
**Decyzja:** ADR-048
**Galaz:** `claude/vigilant-faraday-finqvd` (z `develop`, `8e9bcbb`)
**Brama kazdego kroku:** `scripts/gate.sh` zielony (ruff, format, mypy,
pytest offline); commit na krok.

---

## 0. Wyniki rozpoznania kodu (2026-10-23)

1. **Wspolny szew zapisu.** Prawie kazdy tor zapisuje przez
   `fetch_version` (`download/fetch.py:436`): `use_local` ->
   `new_staging` (`versions/.incoming/...`) -> `fetch(staged)` ->
   `store_file` (`commit_version` + `ensure_link` + sidecar). Wyjatki
   z wlasnym zapisem: arkusze PL (`DownloadManager._download_version`,
   `manager.py:1334`), ortofoto CZ (4 pliki z ZIP, `cz_orto.py:334`),
   BDOT10k (`landcover/manager.py:1742, 1833, 1855`).
2. **Nazwy znane przed pobraniem** we wszystkich torach: `FileSlot.name`
   (`fetch.py:124`) = ostatni element sciezki z magazynu (D9). Arkusze PL:
   rozszerzenie z rekordu skorowidza (po zapytaniu o skorowidz, przed
   transferem).
3. **Fazy wyboru do ponownego uzycia (preflight D3):** arkusze PL -
   `_resolve_chosen` dla wszystkich arkuszy jak w `inspect_sheets`
   (`manager.py:1014`); kolekcje - `_jobs` + `within_volume`; BDOT10k -
   `jobs` + `_bdot_volume`; LAZ - `_selected`; CZ - `_select`,
   `cz_*_area_sheets`; wycinki - `_prepare*` (bez sieci).
4. **Pliki robocze obok celu.** Mozaika z kawalkow (`*.part<i>.tif`),
   `.wcs.tif`, `.native.tif`/`.vshift.tif`, `.tfw` z rozpakowania openzu
   powstaja obok pliku docelowego. Dlatego zapis roboczy trybu `-o`
   odbywa sie w prywatnym podkatalogu `<KATALOG>/.kartograf-<token>/`,
   a nie jako `<nazwa>.part` obok celu (doprecyzowanie D3: ten sam skutek,
   po przerwaniu podkatalog jest usuwany w calosci).
5. **Wybor rekordu PL** (`_resolve_chosen`, `manager.py:1409`) juz dzis
   wylicza najnowszy pelny rekord i flage `no_full`; D12/D13 to zmiana
   wyniku tej funkcji w trybie `-o`.
6. **Skala migracji testow:** `output_dir=` w 721 miejscach (73 pliki),
   `-o`/`--output` w 494 miejscach (24 pliki).

## 1. Kroki

### K1. Parametry, walidacja i API (bez zmiany zapisu)

- `catalog/shared.py`: `OUTPUT_DIR` -> `OUTPUT` (`-o`/`--output`)
  i `STORE` (`--store`), regula "dokladnie jedno"; opisy `--help`
  z regula D12 przy `-o`.
- Bledy wejscia przed siecia (kod 2): oba albo zadne; `--check-updates`,
  `--upgrade`, `--force`, `--plan` z `-o` (D6); `--all-campaigns` z `-o`
  (D14). `Warning:` dla `--full-sheet` z `-o` (D14).
- `project *` i `soil hsg`: tylko `--store` (D7, D11).
- API: `output_dir` -> `output` / `store` (argumenty nazwane) we wszystkich
  funkcjach `download_*`, `download_data`, `check_data` (tylko `store`),
  `download_soil`, `download_landcover`; `calculate_hsg` tylko `store`.
- Migracja testow: mechaniczna zamiana `output_dir=` -> `store=`
  i `-o` -> `--store` w testach magazynu (zachowanie bez zmian), osobny
  commit; nowe testy walidacji.
- Na koncu K1 tryb `-o` jeszcze nie zapisuje: zwraca blad
  `not_implemented` (tymczasowo, usuwany w K5).

### K2. Rdzen zwyklego zapisu `download/plain.py`

- `PlainTarget(name, ...)`, `preflight(targets, directory)`: utworzenie
  katalogu (D8), duplikaty nazw na liscie, pliki juz obecne -> jeden blad
  z pelna lista nazw (D3, D10), przed pierwszym transferem.
- Katalog roboczy `<KATALOG>/.kartograf-<host>_<pid>_<token>/`,
  `fetch_plain(target, fetch)`: pobranie do katalogu roboczego,
  weryfikacja formatu jak dzis, `os.replace` do `<KATALOG>/<nazwa>`;
  sprzatanie przy bledzie, Ctrl-C i SIGTERM (`kartograf.interrupt`).
- Wynik `PlainFile(path, status)`; w dokumencie JSON `files[]`
  ze sciezkami, bez pol wersji.
- Testy jednostkowe: kolizje, duplikaty, przerwanie (brak `.part`
  i katalogu roboczego), istniejacy katalog, brak katalogu.

### K3. Tory jednoplikowe

Wycinki PL (`cutout.py`), ortofoto i true orto (`orto_cutout.py`),
CZ: arkusze, wycinki, warstwice, LAZ (`cz_sheets.py`, `cz_cutout.py`,
`cz_contours.py`, `cz_laz.py`), LAZ PL (`laz.py`). Rozgalezienie przy
`fetch_version`: `store` -> bez zmian, `output` -> `fetch_plain`.
Wyniki wycinkow czytajace dzis sidecar (`_cutout_result`, `_result`)
biora dane z domkniecia `fetch`. Testy na kazdy tor.

### K4. Kolekcje, land cover i gleby

`download/collections.py` (`run_job`, `skip_local=False` w `-o`),
`landcover/manager.py` (BDOT10k: dwa pliki przy `keep_raw` - oba w
`<KATALOG>`; CORINE, SoilGrids, BDOO, ZABAGED, Data50/250), pliki ATOM
(`data.py:1391`). Preflight z `_jobs`/`jobs` przed limitem obszaru.

### K5. Arkusze PL NMT/NMPT/orto

- Preflight: `_resolve_chosen` dla wszystkich arkuszy zadania (rownolegle,
  jak `inspect_sheets`), takze bez granic lat.
- D12: w `-o` wynik = `[najnowszy pelny]`; D13: `no_full` -> pominiecie,
  `Warning:` z arkuszem, najnowszym niepelnym lotem i podpowiedzia
  `--store`, lista pominietych w wyniku (`without_full`).
- D14: lata jak ADR-032 (konflikt = blad zadania).
- Ortofoto ukosne (plik na kierunek), archiwa PL (`_download_pl_archive`).
- Zapis przez `fetch_plain`, bez `commit_version`/`_link`/sidecara;
  powiadomienia po pobraniu czytajace sidecary (`_sheet_sidecar_notices`
  i pokrewne) pomijane w `-o`.

### K6. Ortofoto CZ i `--country auto`

- Ortofoto CZ: ZIP w katalogu roboczym, 4 pliki (`.jpg` + 3 `.jgw`)
  do `<KATALOG>`, preflight wszystkich czterech nazw.
- `--country auto`: jeden preflight nazw PL i CZ przed pierwszym
  transferem (dzis kraje ida po kolei, `data.py:813`).

### K7. Interfejs maszynowy

Dokumenty `kartograf-*/1` (addytywnie: tryb zapisu, `files[]`,
`skipped[]`), katalog komend, MCP (narzedzia pobrania z `output`/`store`;
odczyt magazynu bez zmian), `llms.txt`. Testy zgodnosci CLI = API = MCP.

### K8. Dokumentacja

USAGE (przyklady od `-o`; sekcja o roznicy regul lotu `-o`/`--store`),
ARCHITECTURE 1, 3.3, 4.1 (D12 jawnie), 4.x, CHANGELOG 0.8.0 (zmiana
lamiaca znaczenie `-o` i `output_dir`), README, PROGRESS.

### K9. Weryfikacja

- `scripts/gate.sh` zielony.
- Test na zywo (za zgoda uzytkownika, dane w `<katalog-danych>`): arkusz
  NMT z pelnym lotem, arkusz z niepelnym najnowszym lotem, wycinek,
  BDOT10k powiatu, LAZ, ortofoto CZ; powtorzenie = odmowa bez pobrania;
  Ctrl-C bez pozostalosci; te same zadania z `--store` bez zmian.
- Przeglad diffu przez uzytkownika przed scaleniem do `develop` i tagiem.

## 2. Poza planem

HSG (D11), IMGWTools (D5), jawny wybor kampanii (D15), adnotacja
w Archiwiscie (SPEC 12: komendy z `--store`) - osobno, w repozytorium
Archiwisty.

## 3. Ryzyka

- **Rozmiar zmiany w testach** (K1): mechaniczna zamiana w osobnym
  commicie, zeby przeglad diffu oddzielal ja od zmian logiki.
- **Preflight arkuszy PL bez granic lat** (K5) to nowe zapytania
  o skorowidz przed pobraniem; dzis rekordy sa rozwiazywane arkusz po
  arkuszu w trakcie pobierania. Cache rekordow (ADR-019) ogranicza koszt.
- **Zachowanie `--store` musi zostac bit w bit** - istniejace testy
  magazynu sa siatka bezpieczenstwa i nie moga byc zmieniane poza
  zamiana nazwy parametru.
