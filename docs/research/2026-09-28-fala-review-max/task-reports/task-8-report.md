# Zad. 8: Wycinek PL jako API biblioteki (`kartograf/download/cutout.py`) — raport implementacji

Commit: `ad9e056` (na `2290be5`)
`refactor(download): wycinek PL jako API biblioteki (download/cutout.py), CLI jako nakladka`
Pliki (8): `kartograf/download/cutout.py` (nowy, +453), `kartograf/cli/download_cmd.py` (+92/-332),
`kartograf/cli/_parser.py`, `kartograf/__init__.py`, `tests/test_pl_cutout.py`, `docs/CHANGELOG.md`, `README.md`, `CLAUDE.md`.
`tests/test_cli.py` — BEZ zmian: `grep "_build_pl_cutout|_finalize_pl_cutout|_prepare_pl_cutout|_PlCutout|_PL_NODATA|_PL_PIXEL" tests/`
trafial wylacznie `tests/test_pl_cutout.py`; jedyny test CLI na torze PL+`--target-crs`
(`test_border_bbox_with_target_crs_runs_both_countries`) patchuje caly `_download_pl_bbox` — nietkniety przez refaktor.

## Co zrobiono

1. **`kartograf/download/cutout.py`** — kod z briefu (Step 1), tresciowo 1:1: stale `PL_NODATA`, `PIXEL_SIZES`,
   `SUPPORTED_TARGET_CRS`, `WARP_MARGIN_PX` (+ prywatne `_HORIZONTAL_POLICY`, `_CZ_CRS`, `_VERTICAL_CRS`); frozen
   dataclassy `PlCutout` (+ `pixel_size`), `PlCutoutSheets`, `PlCutoutResult`; funkcje `_bbox_to_2180`,
   `prepare_pl_cutout`, `select_pl_cutout_sheets`, `build_pl_cutout` (parametr cropu `crop_bbox_2180`, zn. 14),
   `write_pl_cutout_sidecar`, `run_pl_cutout`, `download_pl_cutout` — sygnatury, komunikaty, progi doslownie.
   Odejscia wylacznie redakcyjne (lista nizej, pkt A1-A4).
2. **`kartograf/cli/download_cmd.py`** — usuniety caly blok `# Wycinek PL --target-crs (ADR-027)` (`_PL_NODATA`,
   `_PL_PIXEL_SIZES`, `_PL_WARP_MARGIN_PX`, `_PL_HORIZONTAL_POLICY`, `_PlCutout`, `_prepare_pl_cutout`,
   `_build_pl_cutout`, `_write_pl_cutout_sidecar`, `_finalize_pl_cutout`; 259 linii), w jego miejscu
   `_download_pl_cutout(args, bbox, parent_request, geometry=None) -> int` (kod z briefu Step 2a + A5, A6).
   `_download_pl_bbox`: po sentinelach `if args.target_crs is not None: return _download_pl_cutout(...)`; selekcja
   wprost z `bbox`, zero `cutout`/finalize. `_download_pl_geometry(args, filepath, parent_request, bbox: BBox)` —
   `bbox` WYMAGANY, po sentinelach dyspozycja do nakladki (`geometry=filepath`); usuniety martwy guard
   `bbox is None` i caly blok wycinka/R-01 (zn. 13). Wspolny ogon obu workerow: komentarz o kodzie wyjscia
   odswiezony (tryb listy arkuszy, bez `--target-crs`). Usuniete importy: `dataclass`, `replace`,
   `PinnedTransform`, `TransformPolicy` (po refaktorze wystepowaly juz tylko w linii importu).
3. **`kartograf/cli/_parser.py`** — `from kartograf.download.cutout import SUPPORTED_TARGET_CRS`,
   `choices=list(SUPPORTED_TARGET_CRS)` (ten sam zestaw i kolejnosc co dotad; `test_target_crs_default_none_and_choices`
   zielony) + komentarz A7.
4. **`kartograf/__init__.py`** — import 7 nazw z `kartograf.download.cutout` i sekcja `# Download (wycinek PL, ADR-027)`
   w `__all__` (`PlCutout`, `PlCutoutResult`, `PlCutoutSheets`, `download_pl_cutout`, `prepare_pl_cutout`,
   `run_pl_cutout`, `select_pl_cutout_sheets`). Cyklu importow brak (cutout importuje tylko core/download/exceptions/
   transform; `_parser.py` i tak laduje pakiet przez `__version__`).
5. **Testy** (`tests/test_pl_cutout.py`) — przepiecie wg Step 3 + P-04 + P-12 i nowa klasa `TestLibraryApi` (Step 4
   doslownie; `ruff format` zawinal 3 linie). Szczegoly nizej.
6. **Docs** — CHANGELOG `### Added` (bullet z briefu, na gorze sekcji — ten sam wzorzec "najnowsze na gorze" co
   Zad. 6/7), README (przyklad z briefu na koncu bloku `#### Jako biblioteka Python`), CLAUDE.md (linia drzewa pod
   `download/`, wyrownana do kolumny sasiadow — w briefie o 1 spacje za duzo).

## Przepiecie testow (asercje zachowane)

`git diff tests/test_pl_cutout.py | grep -E "^[-+]\s+assert"` — ZADNA linia `assert` nie zostala usunieta ani zmieniona
(same dodane w `TestLibraryApi`); jedyna zmieniona asercja mockowa: `dl.assert_not_called()` ->
`manager.download_sheets.assert_not_called()` (wg briefu).

- Importy: `_build_pl_cutout`/`_prepare_pl_cutout` -> `build_pl_cutout`/`prepare_pl_cutout` z `kartograf.download.cutout`.
- `TestBuildPlCutout`: `_build_pl_cutout(` -> `build_pl_cutout(` (te same argumenty pozycyjne);
  `test_target_5514_full_coverage_from_source_bbox` — `argparse.Namespace` zastapiony jawnym
  `prepare_pl_cutout(bbox, "EPSG:5514", output_dir=str(tmp_path), resolution="1m", vertical_crs="EVRF2007")`.
- `TestPreparePlCutout`: helper `_args` usuniety (tworzyl Namespace tylko po to, by go rozpakowac); kazde
  `_prepare_pl_cutout(self._args(tmp_path[, target_crs=X]), bbox, V)` ->
  `prepare_pl_cutout(bbox, X, output_dir=str(tmp_path), vertical_crs=V)`, X domyslnie `EPSG:5514` jak w `_args`,
  rozdzielczosc = domyslne `1m` (jak w `_args`). Trzeci argument przeniesiony WPROST (P-12):
  `test_vertical_kron86_lands_in_kron86_segment` wola `vertical_crs="KRON86"`.
- `_CUT = "kartograf.download.cutout"` obok `_DL`.
- `TestDownloadPlBboxCutout._run` — doslownie z briefu (zwraca `rc, manager, find`; tego ksztaltu uzywaja briefy Zad. 10/11).
  `test_target_5514_sidecar_has_pinned_transform`: `_dl` -> `_manager` (kosmetyka).
  `test_unexpected_raster_error_returns_1`: patch `f"{_CUT}.build_pl_cutout"`.
- `test_without_target_crs_behaviour_unchanged` — wlasne patche `_DL` (P-04, kod z briefu), asercje bez zmian; dopisane
  zdanie w docstringu, czemu nie `_run`.
- `TestGeometryCutout` (3 testy) i `TestBorderTwoCutouts`: `f"{_DL}.find_sheets_for_bbox"` -> `f"{_CUT}..."`,
  `f"{_DL}.DownloadManager"` + `_download_godlo_list` -> `patch(f"{_CUT}.DownloadManager", return_value=manager)`
  z managerem mockiem budowanym inline (`download_sheets.return_value`/`side_effect`, `last_result = DownloadResult()`;
  ten sam uklad co wariant pogranicza w briefie Zad. 10). `test_geometry_target_5514_covers_whole_envelope`:
  `manager.download_sheets.side_effect = lambda godla, **kw: [sheets[g] for g in godla]` (P-12).
  `_create_provider_and_storage` zostaje na `_DL`.
- Docstring `test_cli_geometry_target_crs_reaches_worker` odswiezony (P-12): zamiast "guard R-12" — `bbox` jest wymagany;
  bez `bbox=part` wycinek nie powstaje, kod 1 (zweryfikowane mutacja M11: `assert 1 == 0`; `main()` zamienia `TypeError`
  z brakujacego argumentu na kod 1 barierą ostatniej szansy).
- Czy ktorys przepiety test stracil zeby? **Nie** — kazdy test wycinka CLI zostal zlapany przez co najmniej jedna mutacje
  (M3, M4, M7-M12, M14-M16 ponizej).

## RED / GREEN

RED (testy przepiete + `TestLibraryApi`, modulu brak):
```
.venv/bin/python -m pytest tests/test_pl_cutout.py -q
E   ModuleNotFoundError: No module named 'kartograf.download.cutout'
ERROR tests/test_pl_cutout.py  — 1 error during collection
```
Stan posredni (modul jest, CLI jeszcze nie nakladka, eksportow brak): `11 failed, 22 passed` —
7x `AttributeError: 'types.SimpleNamespace' object has no attribute 'default_extension'` (CLI budowal jeszcze prawdziwy
`DownloadManager` z `_DL`, patche `_CUT` go nie dotykaly), 2x `assert 1 == 0`, `ImportError: cannot import name
'download_pl_cutout' from 'kartograf'`, `AssertionError: assert ('PlCutout' in [...])`.

GREEN: `tests/test_pl_cutout.py` — `33 passed` (27 dotychczasowych + 6 nowych: e2e, eksporty, 4x parametryzacja).

Pelna suita offline:
```
.venv/bin/python -m pytest tests/ -q -m "not live"
1812 passed, 8 deselected in 26.25s
```
Punkt startowy (zmierzony na `2290be5` przed praca): 1806 passed. +6 = dokladnie `TestLibraryApi`. Dodatkowo
`tests/test_cuzk_client.py tests/test_cuzk_dmr.py tests/test_cli.py`: `331 passed`.

## ruff / mypy

- `ruff check kartograf/ tests/`: pierwszy przebieg 3x E501 (2 w linii testu z briefu, 1 w `download_pl_cutout`); po
  `ruff format kartograf/ tests/` (2 pliki, wylacznie zawiniecia): `All checks passed!`; `ruff format --check`:
  `87 files already formatted`.
- `mypy kartograf/`: `Found 32 errors in 9 files (checked 53 source files)` (53 = +1 nowy modul). Diff listy wzgledem
  `mypy-baseline.txt` (obie strony `sed -E 's/:[0-9]+: /: /' | sort`, `comm`): **0 nowych, 0 zniknietych**.
- Brief: "`_download_pl_geometry` z wymaganym `bbox` — mypy pokaze wolajacych bez argumentu" — potwierdzone mutacja M11:
  `kartograf/cli/download_cmd.py:521: error: Missing positional argument "bbox" in call to "_download_pl_geometry"  [call-arg]`
  (33 bledy). Jedyny wolajacy (`_dispatch_area`) podaje `bbox=part` — mypy czysty.

## Dowody mutacyjne (wszystkie PO commicie `ad9e056`; przywracanie `git checkout -- <plik>`)

Driver: skrypt w scratchpadzie — asercja, ze kotwica mutacji wystepuje dokladnie tyle razy, ile trzeba -> mutacja ->
skupiony test (`pytest -q -p no:cacheprovider <testy>`) -> `git checkout -- <plik>` -> ten sam test -> `git status --short`.
Kazdy wiersz: FAIL pod mutacja, PASS po przywroceniu, `git status` czysty.

| # | Mutacja (produkcja) | Test(y) | Wynik pod mutacja (fragment) |
|---|---|---|---|
| **M1** (brief 1) | `run_pl_cutout` i `download_pl_cutout`: usuniety skrot `if not force and cutout.target_path.exists(): return ...skipped=True` (2 wystapienia) | `TestLibraryApi::test_download_pl_cutout_end_to_end_skip_and_force` | 1 failed: `AssertionError: assert (False)` / `where False = PlCutoutResult(...).skipped` (drugie wywolanie nie jest `skipped`) |
| **M2** (brief 2) | `run_pl_cutout`: `skip_existing=not force` -> `skip_existing=force` | j.w. | 1 failed: `assert ['N-34-130-D-...-130-D-d-2-4'] == [...]` / `Right contains 2 more items` (force nie pobiera ponownie: 2 pobrania zamiast 4) |
| **M3** (brief 3) | `select_pl_cutout_sheets`: `find_sheets_for_bbox(cutout.bbox_source_2180, ...)` -> `cutout.bbox_2180` (tryb bbox i suma R-01, 2 wystapienia) | caly `tests/test_pl_cutout.py` | **2 failed, 31 passed**: `TestDownloadPlBboxCutout::test_target_5514_sidecar_has_pinned_transform` i `TestGeometryCutout::test_geometry_target_5514_covers_whole_envelope`, oba `AssertionError: assert 530010 < 530010` (asercja `sent.min_x < _BBOX_2180.min_x`) — przepiete testy selekcji dalej gryza |
| **M4** (brief 4) | CLI `_download_pl_cutout`: `run_pl_cutout(...)` bez `parent_request=parent_request` | `test_creates_cutout_and_sidecar`, `test_cli_geometry_target_crs_reaches_worker`, `test_two_cutouts_share_parent_request` | 3 failed, kazdy `KeyError: 'parent_request'` |
| M5 | `__init__.py`: `"run_pl_cutout"` usuniete z `__all__` | `TestLibraryApi::test_public_exports` | 1 failed (`AssertionError`) |
| M6a | `prepare_pl_cutout`: `if target_crs not in SUPPORTED_TARGET_CRS:` -> `if False:` | `test_prepare_rejects_bad_params` | 1 failed, 3 passed: `[kwargs0]` (`EPSG:4326`) |
| M6b | `prepare_pl_cutout`: walidacja `resolution` -> `if False:` (tylko w prepare) | j.w. | 1 failed: `[kwargs1]` (`2m`) |
| M6c | `prepare_pl_cutout`: walidacja `vertical_crs` -> `if False:` (tylko w prepare) | j.w. | 1 failed: `[kwargs3]` (`Bpv`) |
| M6d | `prepare_pl_cutout`: regula `5m and != EVRF2007` -> `if False:` | j.w. | 1 failed: `[kwargs2]` (`5m`+`KRON86`) |
| M7 | CLI: usuniety skrot "plik istnieje" w `_download_pl_cutout` (biblioteka zachowuje swoj) | `test_skip_existing_short_circuits_before_download` | 1 failed (`find.assert_not_called()` — selekcja szla przed skrotem biblioteki) |
| M8 | `run_pl_cutout`: `if failed:` -> `if False:` | `test_failed_sheet_returns_1_and_no_cutout` | 1 failed |
| M9 | CLI: `except Exception` -> `except (DownloadError, ValidationError)` | `test_unexpected_raster_error_returns_1` | 1 failed (`RasterioIOError` przecieka) |
| M10 | `select_pl_cutout_sheets`: suma R-01 `if cutout.pinned is not None:` -> `if False:` | `test_geometry_target_5514_covers_whole_envelope` | 1 failed |
| M11 | `_dispatch_area`: `_download_pl_geometry(..., bbox=part)` bez `bbox=part` | `test_cli_geometry_target_crs_reaches_worker` | 1 failed: `assert 1 == 0`; mypy: `Missing positional argument "bbox"` |
| M12 | `_download_pl_bbox`: usunieta dyspozycja do `_download_pl_cutout` | klasa `TestDownloadPlBboxCutout` | 6 failed, 1 passed (zostaje tylko test toru bez flagi) |
| M14 | `_download_pl_bbox`: `if args.target_crs is not None:` -> `if True:` | `test_without_target_crs_behaviour_unchanged` | 1 failed |
| M15 | CLI: `vertical_crs=getattr(provider, "vertical_crs", ...)` -> surowa flaga `args.vertical_crs` | `test_5m_kron86_grid_dataset_vertical_and_segment` | 1 failed |
| M16 | `run_pl_cutout`: `cutout.pixel_size` -> `1.0` | j.w. | 1 failed |

Po kazdej: `PRZYWROCONE -> rc=0 ... passed; git status: (czysto)`.

Dodatkowo (bez testu, dowod kosmetyki — patrz A5): mutacja usuwajaca `print()` przed `Downloaded to` + skrypt demo
(`_download_pl_bbox` bez `-q`, oba arkusze juz w cache -> ostatni status `skipped`, ktory `create_progress_callback`
drukuje z `end=""`): pod mutacja (= wersja z briefu)
`[==============================] 2/2 ○ N-34-130-D-d-2-4                        Downloaded to <tmp>/nmt/...tif` (sklejone
w jednej linii); po przywroceniu `...N-34-130-D-d-2-4                        \nDownloaded to <tmp>/nmt/...tif`.

## Odejscia od briefu (wszystkie bez zmiany zachowania) i decyzje

- **A1** `write_pl_cutout_sidecar`: lokalny alias `pinned = cutout.pinned` — linia f-stringu z `cutout.pinned.*` miala
  ~100 znakow nawet po formatowaniu (E501); semantyka identyczna.
- **A2** `_bbox_to_2180`: docstring doprecyzowany — CLI podaje bbox juz po `_country_bbox`, ktory opuszcza uklady
  czeskie przypieta operacja, wiec galaz `_CZ_CRS` dotyczy wywolan bibliotecznych (w briefie: "znormalizowany", co dla
  PL/WGS84 nie jest prawda — `_country_bbox` zostawia je w ukladzie zadania).
- **A3** `select_pl_cutout_sheets`: w docstringu dopisane zdanie o swiadomym koszcie sumy R-01 (rzadka geometria
  wieloobiektowa -> arkusze calej obwiedni) — ta wiedza zyla w usuwanym komentarzu CLI; ARCHITECTURE 4.3/R2 to potwierdzaja.
- **A4** Zawiniecia E501 w kodzie z briefu (`ruff format`), bez zmian tresci.
- **A5** `_download_pl_cutout`: **zachowany pusty `print()` przed `Downloaded to`** (brief go pomija). Stary przeplyw
  mial `print()` + `Downloaded N files to` + `Building cutout...` + `Downloaded to`; zamierzona zmiana (b) usuwa DWIE
  wymienione linie, nie separator. Bez niego podsumowanie skleja sie z paskiem postepu, gdy ostatni arkusz jest
  `skipped` (arkusze wycinka to cache — typowy przypadek); dowod wyzej.
- **A6** Docstring `_download_pl_cutout`: brief mowi "Kazdy blad = kod 1 ... nigdy traceback" — nieprecyzyjne:
  `select_pl_cutout_sheets` lapie tylko `ValidationError`, a `_create_provider_and_storage` jest poza `try` (po
  sentinelach dla `nmt` nie ma jak rzucic). Wpisano dokladnie: bledy przygotowania (`TransformError`/`ValidationError`),
  selekcji (`ValidationError`) i KAZDY blad pobrania/budowy -> kod 1 z komunikatem. (Traceback i tak zatrzymuje bariera
  ostatniej szansy w `main()`; lokalne lapanie chroni kontrakt czesciowego sukcesu ADR-023.)
- **A7** `_parser.py`: komentarz przy `choices` — stala toru PL ogranicza teraz takze `--target-crs` toru CZ (provider
  CZ buduje operacje dynamicznie dla dowolnego ukladu), wiec rozszerzenie zestawu po jednej stronie wymaga walidacji
  per kraj.
- **A8** Testy: helper `_args` w `TestPreparePlCutout` i Namespace w `TestBuildPlCutout` zastapione jawnymi wywolaniami
  API (wzor z briefu `prepare_pl_cutout(bbox, args.target_crs, output_dir=..., resolution=args.resolution or "1m",
  vertical_crs=vcrs)` zastosowany z podstawionymi wartosciami). Asercje bez zmian.

## Analiza zachowania (co jest identyczne, co nie)

Identyczne (tor wycinka CLI): sentinele i wylaczenia (`nmpt/orto/laz`, `--system 2000`) przed dyspozycja; provider/
storage z `_create_provider_and_storage`; fail-fast operacji przed siecia z tym samym komunikatem (`_print_transform_error`);
skrot "plik istnieje" (`Skipped - already exists at ...`, kod 0) przed selekcja; selekcja z `bbox_source_2180`
(`system="1992"` = jedyna wartosc osiagalna po sentinelach z `--target-crs`); ten sam komunikat "Found N sheets ..."; ten
sam `DownloadManager` (pion faktyczny providera, `resolution`, `max_workers`, `sidecar_extra={"parent_request": ...}`);
ta sama budowa (crop po `bbox_source_2180`, piksel `PIXEL_SIZES[res]`, atomowy zapis — poprzedni plik przezywa awarie),
ten sam sidecar; `Downloaded to <plik>`; kody wyjscia. Tor BEZ `--target-crs` (lista arkuszy bbox/geometry) — bez zmian
(ta sama kolejnosc: provider -> selekcja -> manager -> `_download_godlo_list`).

Zamierzone (z briefu): (a) porazka arkusza -> `Error: <n> of <m> sheets failed: <lista> (wycinek wymaga kompletu arkuszy)`
(wszystkie nieudane z `download_sheets`, zamiast pierwszego wyjatku z puli watkow albo `_report_failed_sheets`), kod 1;
(b) bez linii `Downloaded N files to` i `Building cutout from N sheets`; postep to jedna lista (np. przy `--scale 1:25000`
licznik 1..N po wszystkich lisciach zamiast osobno per godlo); (c) `--geometry`: przygotowanie -> skrot -> selekcja.

**Poza lista briefu (do oceny reviewera):**
1. `--geometry` + warp: kontrola "No sheets found for the given geometry" jest teraz PO sumie R-01 (dotad PRZED). Gdy
   geometria sama nie daje arkuszy, a obwiednia z zapasem daje — dotad blad, teraz wycinek. Osiagalne tylko dla
   zdegenerowanej geometrii (np. punkty dokladnie na krawedzi arkusza: `_bboxes_intersect` liczy dodatnie pole /
   polotwarte przedzialy); zgodne z obietnica R-01 "cala obwiednia". Kod z briefu (doslownie).
2. `download_pl_cutout` tworzy providera PRZED skrotem "plik istnieje" (kolejnosc z briefu) — bez sieci (konstruktor
   `GugikProvider` tylko waliduje; walidacja `ValidationError` idzie wczesniej, wiec jego `ValueError` jest nieosiagalny).
3. `_CZ_CRS` porownuje napisy doslownie (`"EPSG:5514"`, `"EPSG:3045"`); CLI tam nie dociera (Krovak opuszczony w
   `_country_bbox` przez `wkid()`), ale wywolanie biblioteczne z inna pisownia (np. `"epsg:5514"`) pojdzie niepinowanym
   `_transform_bbox`. Kod z briefu; kandydat na `wkid()` przy okazji Zad. 9-12.

## Dokumentacja, ktorej swiadomie NIE ruszalem

Po tym commicie przestaja istniec nazwy cytowane w: `docs/ARCHITECTURE.md` 4.3 (l. 360-361 `_prepare_pl_cutout` ->
`_download_pl_bbox`/`_download_pl_geometry` -> `_finalize_pl_cutout`; l. 370 `_PL_WARP_MARGIN_PX`; l. 404
`_build_pl_cutout`) i `docs/DECISIONS.md:1035` (`_PL_WARP_MARGIN_PX`). Brief Zad. 8 nie obejmuje tych plikow, a Zad. 17
przepisuje 4.3 w calosci (API `kartograf.download.cutout`) i uzupelnia ADR-027 (Zad. 10/17) — zostawiam im, zeby nie
mnozyc edycji. `docs/PROGRESS.md`/`docs/research`/plany — zapis historyczny, bez zmian. Wzmianki o usunietych liniach
wyjscia (`Building cutout`) w dokumentacji uzytkowej: brak (grep).

## Samoocena i watpliwosci

- Refaktor zgodny z briefem; wszystkie 4 mutacje briefu + 13 dodatkowych lapane; suita 1812/1812, ruff czysty, mypy = baseline.
- Watpliwosci do decyzji kontrolera: A5 (swiadome odejscie od kodu CLI briefu — zachowany separator), pkt 1 i 3 z
  "Poza lista briefu", przestarzale nazwy w ARCHITECTURE 4.3/DECISIONS (odlozone do Zad. 17).
- Brak testu na separator z A5 (kosmetyka wyjscia) — dowod tylko demo; jesli kontroler chce, test na stdout jest tani.

---

# Runda poprawek 1 (review Zad. 8)

Commit: `6bc1c19` (na `ad9e056`)
`fix(download): run_pl_cutout odrzuca providera niezgodnego z wycinkiem; testy reuse cache/sidecar/5m`
Pliki: `kartograf/download/cutout.py` (+26/-1), `tests/test_pl_cutout.py` (+118/-1), `docs/CHANGELOG.md` (+3/-1).

## Zmiany

1. **Znalezisko 1 (IMPORTANT)** — `kartograf/download/cutout.py`: nowa `_require_matching_provider(cutout, provider)`;
   dla `attr in ("vertical_crs", "resolution")`: gdy `getattr(provider, attr, None)` jest `str` i rozni sie od wartosci
   wycinka -> `ValidationError("Provider niezgodny z wycinkiem: <attr> providera <x>, wycinka <y> — przygotuj wycinek
   (prepare_pl_cutout) z pionem i rozdzielczoscia providera")`. Idiom `isinstance(str)` jak w `manager.py:205-214`
   (Mock/SimpleNamespace bez tych atrybutow nie sa porownywane — patrz mutacja odwrotna F1c). Wywolanie: PIERWSZA
   instrukcja `run_pl_cutout` (`if provider is not None: ...`), wiec przed skrotem "plik istnieje", fabryka, `FileStorage`,
   `DownloadManager`, pobraniem i `mkdir` (sama `FileStorage.__init__` katalogow nie tworzy — `mkdir` tylko w metodach
   `storage.py:291,343`). Przed skrotem swiadomie: niezgodny provider to blad wywolujacego — ujawniany deterministycznie,
   a nie dopiero wtedy, gdy wyniku jeszcze nie ma. Docstring `run_pl_cutout` + zdanie w bullecie CHANGELOG.
   Tor CLI i `download_pl_cutout` kontroli nie wyzwalaja: provider i wycinek powstaja z tych samych, skorygowanych
   wartosci (`create_nmt_provider(vertical_crs, resolution)` -> `prepare_pl_cutout(resolution=..., vertical_crs=provider.vertical_crs)`).
   Poza zakresem (jak w `DownloadManager`): wstrzyknieta `storage` nie jest walidowana wobec wycinka.
2. **(A)** nowy `TestLibraryApi::test_rebuild_reuses_cached_sheets`: pierwszy `download_pl_cutout`, `first.path.unlink()`
   (arkusze zostaja), drugi z `force=False` -> `provider.calls` == tylko pierwszy przebieg, wynik nie `skipped`, plik
   odbudowany, `sheet_paths` z 2 arkuszami. Osobny test zamiast dopisania kroku do testu e2e: przy jednej koncowej
   asercji liczby pobran w tescie e2e mutacja M2 (`skip_existing=force`) dawalaby 2 + 0 + 2 = 4 pobrania — tyle samo co
   poprawny kod — i przestalaby byc lapana. Osobny test lapie A i M2 (sprawdzone ponizej).
3. **(B)** `TestDownloadPlBboxCutout._run`: `patch(f"{_CUT}.DownloadManager", return_value=manager) as dm`, mock klasy
   zapisany w `self.dm` (docstring `_run`); zwrot `(rc, manager, find)` bez zmian (Zad. 10/11 rozpakowuja trojke, takze
   przez `TestDownloadPlBboxCutout()._run(...)` — wtedy `self.dm` laduje na tymczasowej instancji, bez skutkow).
   `test_creates_cutout_and_sidecar` dostal `assert self.dm.call_args.kwargs["sidecar_extra"] == {"parent_request": _PARENT}`.
4. **(C)** nowy `TestLibraryApi::test_5m_request_follows_factory_vertical_rule`: `download_pl_cutout(..., resolution="5m",
   vertical_crs="KRON86")`, fabryka zapatchowana providerem, jakiego zwraca prawdziwa fabryka dla tej pary (EVRF2007, 5m,
   `pl.gugik.nmt_5m`, arkusze 5 m); asercje: `factory.assert_called_once_with(vertical_crs="KRON86", resolution="5m")`
   (surowe parametry ida do fabryki — jedynego miejsca regul PL) i `result.path.parent == tmp/nmt/pl_1992_5m_evrf2007/bbox`
   + plik istnieje.
5. **(D)** nowy `TestDownloadPlBboxCutout::test_error_lists_all_failed_sheets` (CLI, `capsys`): `failed=["N-1", "N-2"]`
   -> kod 1, oba godla w stderr, brak katalogu `bbox`. Sprawdzam tylko godla, NIE brzmienie komunikatu — Zad. 10 zmienia
   tekst (`"{n} z {total} arkuszy nie pobrano ...: {', '.join(fatal)}"`), dalej z pelna lista. Istniejacy
   `test_failed_sheet_returns_1_and_no_cutout` (`failed=["N-2"]`) zostaje bez zmian — brief Zad. 10 go wymienia.

## RED / GREEN

RED (testy przed poprawka, `-k "rejects_provider or rebuild_reuses or 5m_request_follows or lists_all_failed or creates_cutout_and_sidecar"`):
```
FAILED ...::TestLibraryApi::test_run_rejects_provider_not_matching_cutout[vertical_crs-KRON86]
FAILED ...::TestLibraryApi::test_run_rejects_provider_not_matching_cutout[resolution-5m]
E   Failed: DID NOT RAISE <class 'kartograf.exceptions.ValidationError'>
2 failed, 4 passed, 32 deselected
```
(niezgodny provider po cichu budowal wycinek; testy luk A-D bronia zachowania juz poprawnego — ich dowodem sa mutacje nizej).
GREEN: `tests/test_pl_cutout.py` — `38 passed` (33 + 5 nowych). Pelna suita offline:
```
.venv/bin/python -m pytest tests/ -q -m "not live"
1817 passed, 8 deselected in 26.58s
```
(1812 + 5). `ruff check`: `All checks passed!`; `ruff format --check`: `87 files already formatted` (format bez zmian);
`mypy kartograf/`: `Found 32 errors in 9 files (checked 53 source files)`, diff listy wzgledem baseline: 0 nowych, 0 zniknietych.

## Dowody mutacyjne (PO commicie `6bc1c19`; przywracanie `git checkout -- kartograf/download/cutout.py`)

Kazda mutacja uruchomiona na `tests/test_pl_cutout.py tests/test_cli.py` (295 testow) — lista FAILED pokazuje, ze pod
mutacjami A-D pada WYLACZNIE nowy/zmieniony test (stary zestaw je przepuszczal, zgodnie z review).

| # | Mutacja | Pod mutacja | Fragment |
|---|---|---|---|
| **F1** | usuniete `if provider is not None: _require_matching_provider(...)` | 2 failed, 293 passed: `test_run_rejects_provider_not_matching_cutout[vertical_crs-KRON86]`, `[resolution-5m]` | `Failed: DID NOT RAISE <class 'kartograf.exceptions.ValidationError'>` |
| F1b | kontrola tylko pionu (`for attr in ("vertical_crs",)`) | 1 failed: `[resolution-5m]` | `DID NOT RAISE` |
| F1c (odwrotna) | bez `isinstance(actual, str)` | 9 failed (harness CLI i testy geometrii/pogranicza z `SimpleNamespace(vertical_crs=...)`) | `Error: Provider niezgodny z wycinkiem: resolution providera None, wycinka 1m ...`, `assert 1 == 0` — straz `str` jest konieczna |
| **A** | `skip_existing=not force` -> `skip_existing=False` | 1 failed, 294 passed: `test_rebuild_reuses_cached_sheets` | `assert ['N-34-130-D-...-130-D-d-2-4'] == [...]` (4 pobrania zamiast 2); test e2e przechodzi — luka potwierdzona |
| **B** | `sidecar_extra=None` w `run_pl_cutout` | 1 failed, 294 passed: `test_creates_cutout_and_sidecar` | `assert None == {'parent_request': {'bbox': [530010.0, ...], 'countries': ['PL']}}` |
| **C** | `download_pl_cutout`: `vertical_crs=provider.vertical_crs` -> `vertical_crs=vertical_crs` | 1 failed, 294 passed: `test_5m_request_follows_factory_vertical_rule` | `ValidationError: NMT 5m jest dostepny wylacznie w EVRF2007` |
| **D** | komunikat: `', '.join(failed)` -> `failed[0]` | 1 failed, 294 passed: `test_error_lists_all_failed_sheets` | `Error: 2 of 2 sheets failed: N-1 (wycinek wymaga kompletu arkuszy)` — brak `N-2` |

Po kazdej: `PRZYWROCONE -> 295 passed; git status: (czysto)`.
Kontrolnie caly zestaw M1-M16 z pierwszej rundy powtorzony na `6bc1c19`: wszystkie `[OK]` (M3: 2 failed, 36 passed;
M12: 7 failed, 1 passed — dochodzi nowy test D z tej klasy), drzewo czyste.

## Watpliwosci

- Kontrola stoi PRZED skrotem "plik istnieje" (niezgodny provider -> blad takze, gdy wycinek juz jest) — swiadomie,
  opis wyzej; jesli kontroler woli "skip wygrywa", to jedna linia do przesuniecia (test F1 i tak zostaje zielony, bo
  wycinka w nim nie ma).
- Briefy Zad. 10/11/13 edytuja `run_pl_cutout` punktowo (blok porazek, kontrola miejsca po `storage`, `try` wokol
  budowy) — poczatku funkcji nie podmieniaja, wiec kontrola przezyje; ich providery testowe (`EVRF2007`/`1m` przy
  wycinku 1m EVRF2007) ja przechodza.
