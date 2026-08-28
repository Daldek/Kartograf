# Raport fali naprawczej (N-01 .. N-11)

Galaz: `develop`. Wejscie: `a9afc3f` (1775 testow PASS, mypy 32, ruff czysty).
Wyjscie: `03b5bac` (**1787 testow PASS**, mypy **32** — zero nowych, ruff
czysty, pokrycie 93 % / 92,74 %, `git status` czysty).

Commity (5, w kolejnosci):

| SHA | Commit |
|---|---|
| `f2bd0e4` | `fix(cli): selekcja arkuszy w --geometry --target-crs obejmuje zapas zrodla` |
| `d0a0572` | `fix(download): segment storage z pionu providera; pusty vertical_crs nie milczy` |
| `eb625d8` | `test(transform): KNOWN_PATHS dla par toru PL (2180->5514, 2180->3045)` |
| `4310896` | `fix(cli): wycinek PL nie kasuje poprzedniego wyniku; kod 1 zamiast tracebacku` |
| `03b5bac` | `docs: teksty zgodne z faktem — siatka wyniku, selekcja arkuszy, korekta osi` |

---

## Tabela: pozycja -> status -> dowod

| Poz. | Status | Dowod |
|---|---|---|
| **N-01** | NAPRAWIONE | `kartograf/cli/download_cmd.py:1980-1993` — przy `cutout.pinned is not None` godla to `sorted(set(godel geometrii) \| set(find_sheets_for_bbox(cutout.bbox_source_2180, target_scale, system=args.system)))`. Nowy test `tests/test_pl_cutout.py::TestGeometryCutout::test_geometry_target_5514_covers_whole_envelope` przed naprawa padal z `ramka nodata: 8756 z 17484 pikseli`, po naprawie zielony. Pkt 2: asercje `sent.min_x < ... / sent.max_x > ...` w `test_target_5514_sidecar_has_pinned_transform`. Pkt 3: `assert find.call_args.args[0] is _BBOX_2180` w `test_without_target_crs_behaviour_unchanged`. Pkt 5: `docs/ARCHITECTURE.md` sekcja 4.3, akapit "W trybie `--geometry` ... **Swiadomy koszt:** ...". Mutacje A/B/C nizej. |
| **N-02** | NAPRAWIONE | `docs/ARCHITECTURE.md` sekcja 4.3 pkt 2 — "i siatka wyniku"/"i siatke" skreslone; wpisany fakt: "Siatki wyniku zapas NIE dotyczy: `warp_to_grid` liczy `width`/`height`/`dst_transform` wylacznie z `bbox_target` ... (zmierzone: 186 x 94 px, `bounds == bbox_target`)". Pomiar zweryfikowany: `transform/raster.py:95-97` liczy z `bbox`, a raster z testu geometry ma `shape=(94, 186)`. |
| **N-03** | NAPRAWIONE | `kartograf/download/manager.py:202-210` — pion segmentu bierze sie z providera. Nowy test `tests/test_download_manager.py::TestDownloadManagerStorageFromDescriptor::test_default_storage_follows_provider_vertical_crs` (pada przed naprawa: `'nmt/pl_{uklad}_1m_evrf2007' == 'nmt/pl_{uklad}_1m_kron86'`). Drugi, blizniaczy do `test_manager_without_descriptor_key_falls_back_to_resolution`: `test_manager_without_descriptor_key_keeps_kron86_in_segment`. Mutacje D/E nizej. |
| **N-04** | NAPRAWIONE | `kartograf/download/storage.py:145-149` — `if self._vertical_crs:` (wybor uzasadniony nizej). Nowy test `tests/test_storage.py::TestFileStorageSegments::test_empty_vcrs_raises_instead_of_dangling_segment` (przed naprawa: `DID NOT RAISE`). Mutacja F nizej. |
| **N-05** | NAPRAWIONE | `kartograf/transform/crs.py:142-156` — dwa `KnownPath`. **Dokladnosci zmierzone samodzielnie** (nie przepisane): `EPSG:2180 -> EPSG:5514` = **0.5**, `EPSG:2180 -> EPSG:3045` = **0.0** (komenda i wynik nizej). Test `tests/test_transform_crs.py::TestKnownPaths::test_pl_cutout_pairs_documented_with_measured_accuracy` wiaze tabele z rzeczywistoscia (przed naprawa: `KeyError: ('EPSG:2180', 'EPSG:5514')`). Mutacje G/H nizej. |
| **N-06** | NAPRAWIONE | Jeden test `tests/test_pl_cutout.py::TestDownloadPlBboxCutout::test_5m_kron86_grid_dataset_vertical_and_segment` z asercjami `ds.res == (5.0, 5.0)`, `dataset == "pl.gugik.nmt_5m"`, `vertical_crs == "EPSG:9651"`, segment `pl_1992_5m_evrf2007`. Zabija WSZYSTKIE cztery mutacje z briefu (N, O, P, Q) plus piata (R, klucz segmentu w `_prepare_pl_cutout`). |
| **N-07** | NAPRAWIONE | Trzy testy: `tests/test_transform_raster.py::TestWarpToGrid::test_failed_warp_writes_only_to_temp_file` (stan W CHWILI awarii: cel nie istnieje, tmp istnieje), `...::test_failed_warp_removes_stale_destination`, oraz `tests/test_pl_cutout.py::TestBuildPlCutout::test_failed_build_keeps_previous_result`. Mutacje I/J/K/T nizej. |
| **N-08** | NAPRAWIONE | `target_path.unlink(missing_ok=True)` usuniete z `_build_pl_cutout` (zostala sama klauzula `finally: tmp.unlink(...)`) — `kartograf/cli/download_cmd.py:1086-1090`. Blizniacze `unlink` w `transform/raster.py:132-134` ZOSTAWIONE zgodnie z rulingiem; analiza roznicy nizej. Semantyka opisana od nowa w `docs/ARCHITECTURE.md` sekcja 4.3 ("Nieudana budowa a poprzedni wynik") i w `docs/CHANGELOG.md`. |
| **N-09** | NAPRAWIONE | `kartograf/cli/download_cmd.py:1171` — `except Exception as e:  # noqa: BLE001` z zachowanym komunikatem `Error: {e}`. Test `tests/test_pl_cutout.py::TestDownloadPlBboxCutout::test_unexpected_raster_error_returns_1` (przed naprawa: `RasterioIOError` wychodzil z `_download_pl_bbox`). Mutacja U nizej. |
| **N-10** | NAPRAWIONE (5/5) | 1. `docs/ARCHITECTURE.md` sekcja 4.3, akapit "Wylaczenia" — godlo odrzuca `cmd_download` (PL, `download_cmd.py:652-658`) / `_cmd_download_cz` (`:1803-1808`), nie `_resolve_pl_sentinels`. 2. `kartograf/cli/_parser.py:69-77` — opis przeszedl ADR-027 (zweryfikowane w `kartograf download --help`). 3. `CLAUDE.md:116-118` i `docs/SCOPE.md:272-274` — "KAZDE `--bbox`/`--geometry` CZ". 4. `docs/ARCHITECTURE.md:51-59` + `kartograf/transform/crs.py:88-96` — axisswap niezaleznie dla zrodla i celu, z wlasnym pomiarem. 5. `kartograf/download/storage.py:41-43, 76-89, 129, 398-402` i `kartograf/download/manager.py:130`. |
| **N-11** | NAPRAWIONE (3/3) | `resampling`: asercja w `test_operation_is_forced` (`tests/test_transform_raster.py:129-132`). `_same_crs`: nowy `test_lowercase_crs_is_the_same_pair` (wolanie z `epsg:2180`/`epsg:5514`). `probe_point`: nowy `tests/test_pl_cutout.py::TestPreparePlCutout::test_probe_point_is_center_of_request` (asercja `policy.probe_point == (530100.0, 382050.0)` + `min_accuracy_m`/`allow_network_grids`). Mutacje L/M/S nizej. |

**Zamkniete: 11 z 11.** Zadna pozycja nie okazala sie niemozliwa ani szkodliwa.

---

## Dowody mutacyjne

Metoda: kopia pliku zrodlowego do scratchpada, mutacja skryptem, uruchomienie
waskiej suity, przywrocenie kopii, `git status`. Wszystkie mutacje przywrocone —
`git status` na koncu pracy czysty (potwierdzone, sekcja "Brama koncowa").

| # | Mutacja (plik) | Test, ktory PADA | Komunikat |
|---|---|---|---|
| A | `download_cmd.py`: `sheet_bbox = bbox if cutout is None else cutout.bbox_source_2180` -> `sheet_bbox = bbox` | `test_target_5514_sidecar_has_pinned_transform` | `530010 = BBox(...).min_x` (zapas nie wszedl do selekcji) |
| B | `download_cmd.py`: zapas dokladany ZAWSZE (takze bez `--target-crs`) | `test_without_target_crs_behaviour_unchanged` | `assert BBox(min_x=530006, ...) is BBox(min_x=530010, ...)` |
| C | `download_cmd.py`: `if cutout.pinned is not None:` -> `if False:` (brak sumy w geometry) | `test_geometry_target_5514_covers_whole_envelope` | `ramka nodata: 8756 z 17484 pikseli` |
| D | `manager.py`: usuniecie `vertical_crs = provider_vertical_crs` | `test_default_storage_follows_provider_vertical_crs` | `'nmt/pl_{uklad}_1m_evrf2007' != 'nmt/pl_{uklad}_1m_kron86'` |
| E | `manager.py`: usuniecie `vertical_crs=vertical_crs` z `FileStorage(...)` | `test_manager_without_descriptor_key_keeps_kron86_in_segment` | j.w. (segment schodzi na domyslne `evrf2007`) |
| F | `storage.py`: `if self._vertical_crs:` -> `if self._vertical_crs is not None:` | `test_empty_vcrs_raises_instead_of_dangling_segment` | `DID NOT RAISE ValidationError` |
| G | `crs.py`: wpis `EPSG:2180 -> EPSG:5514` zmieniony na inna pare | `test_pl_cutout_pairs_documented_with_measured_accuracy` | `KeyError: ('EPSG:2180', 'EPSG:5514')` |
| H | `crs.py`: `expected_accuracy_m` pary `2180 -> 3045` z `0.0` na `0.5` | j.w. | `assert 0.5 == 0.0` |
| I | `raster.py`: zapis wprost do `dst_path`, bez `os.replace` i `finally` | `test_failed_warp_writes_only_to_temp_file` | `polzapisany raster pod finalna sciezka` |
| J | `raster.py`: usuniecie `except BaseException: dst_path.unlink(...)` | `test_failed_warp_removes_stale_destination` | `assert not dst.exists()` (stary plik przezyl) |
| K | `raster.py`: usuniecie `finally: tmp_path.unlink(...)` | `test_failed_warp_writes_only_to_temp_file` | zostal `*.warp.tif` |
| L | `raster.py`: `Resampling.bilinear` -> `nearest` | `test_operation_is_forced` | `<Resampling.bilinear: 1> != Resampling.nearest` |
| M | `raster.py`: `_same_crs` -> `return a == b` | `test_lowercase_crs_is_the_same_pair` | `TransformError: Niespojna para ukladow ... epsg:2180 -> epsg:5514` |
| N | `download_cmd.py`: `_PL_PIXEL_SIZES[args.resolution]` -> `1.0` | `test_5m_kron86_grid_dataset_vertical_and_segment` | 1 failed |
| O | `download_cmd.py`: klucz sidecara zawsze `pl.gugik.nmt_1m` | j.w. | 1 failed |
| P | `download_cmd.py`: `vertical_crs=args.vertical_crs` w sidecarze (surowa flaga) | j.w. | 1 failed |
| Q | `download_cmd.py`: `_prepare_pl_cutout(args, bbox, vertical_crs)` (surowa flaga) | j.w. | 1 failed |
| R | `download_cmd.py`: klucz segmentu w `_prepare_pl_cutout` zawsze `nmt_1m` | j.w. | 1 failed |
| S | `download_cmd.py`: `replace(_PL_HORIZONTAL_POLICY, probe_point=center)` -> sama polityka | `test_probe_point_is_center_of_request` | 1 failed |
| T | `download_cmd.py`: przywrocenie `except BaseException: target_path.unlink(...)` | `test_failed_build_keeps_previous_result` | 1 failed (poprzedni wynik skasowany) |
| U | `download_cmd.py`: `except (ValidationError, TransformError)` | `test_unexpected_raster_error_returns_1` | 1 failed (`RasterioIOError` wychodzi z funkcji) |

Uwaga proceduralna: mutacje G i H uruchomilem najpierw w jednej komendzie
zlozonej — wynik dla H byl wtedy myslacy (pokazal komunikat mutacji G, bo
przywrocenie i heredoc zjadly sie w jednym `bash -c`). Powtorzylem H osobno
i dopiero ten przebieg jest w tabeli.

---

## Pomiary wykonane samodzielnie (nie przepisane z briefu)

1. **Dokladnosci `KNOWN_PATHS`** (`build_pinned_transform` z polityka toru PL:
   `min_accuracy_m=1.0`, `probe_point=(530050.0, 382050.0)`,
   `allow_network_grids=False`):

   ```
   EPSG:5514 0.5 | axis order change (2D) + Inverse of Poland CS92
                 + ETRF2000-PL to ETRS89 (1) + Inverse of S-JTSK to ETRS89 (3)
                 + Krovak East North (Greenwich)
   EPSG:3045 0.0 | axis order change (2D) + Inverse of Poland CS92
                 + ETRF2000-PL to ETRS89 (1) + UTM zone 33N + axis order change (2D)
   ```
   Zgadza sie z briefem co do wartosci i opisu (brief ucial "(Greenwich)").

2. **Korekta osi (N-10.4).** `_is_northing_first`: `EPSG:2180 -> True`,
   `EPSG:3045 -> True`, `EPSG:5514 -> False`. Warp 300x300 stozka
   2180 -> 5514 na siatce 215x215:
   ```
   Z axisswap:            wazne 46225 z 46225
   BEZ czolowego axisswap: wazne 0 z 46225
   ```
   Potwierdza liczbe z briefu (0/46225) i to, ze w torze PL swap wynika
   ze ZRODLA (5514 nie jest northing-first, wiec swapu koncowego tu nie ma).

3. **Rozmiar ramki nodata w `--geometry`** przed naprawa N-01:
   **8756 z 17484 pikseli (50,1 %)** dla zadania 180 x 80 m -> EPSG:5514
   przy geometrii wskazujacej jeden arkusz zachodni. (Brief podawal 8,4 %
   dla innego ustawienia geometrii; moja fixtura jest ostrzejsza — celowo,
   zeby test byl jednoznaczny.)

4. **Siatka wyniku (N-02).** Raster z testu geometry ma `shape=(94, 186)`,
   tj. dokladnie `bbox_target` w metrach; `transform/raster.py:95-97` liczy
   `width`/`height`/`dst_transform` wylacznie z `bbox`. Zapas nie wchodzi.

---

## Decyzje i odstepstwa (kazde swiadome)

1. **N-04, wybor wariantu.** Brief dawal do wyboru `if self._vertical_crs:`
   albo `ValidationError` dla pustego stringu. Wybralem jednolinijkowiec.
   Uzasadnienie: pusty string to "nie podano wymiaru", a nie "wymiar jest
   pusty" — po zmianie `{vcrs}` zostaje nierozwiazane i pilnuje go JUZ
   ISTNIEJACY `_ensure_resolved`, ktory zglasza brakujacy wymiar po nazwie.
   Osobny `ValidationError` w `__init__` dublowalby ten sam komunikat w drugim
   miejscu i wywracalby takze legalne przypadki bez `{vcrs}` w szablonie
   (`orto/pl_{uklad}`), gdzie pusty pion jest nieszkodliwy.

2. **N-03, `isinstance(str)` zamiast golego `getattr`.** Brief podawal
   `vertical_crs = getattr(self._provider, "vertical_crs", vertical_crs)`.
   Dla `Mock(spec=GugikProvider)` (uzywany w kilkunastu testach) atrybut
   zwraca `Mock`, ktory poszedlby do `template.replace("{vcrs}", ....lower())`
   i wywrocilby budowe sciezki. Uzylem tego samego wzorca obronnego, ktory
   linijke nizej stosuje juz `descriptor_key`:
   ```python
   provider_vertical_crs = getattr(self._provider, "vertical_crs", None)
   if isinstance(provider_vertical_crs, str):
       vertical_crs = provider_vertical_crs
   ```
   Dla realnych providerow zachowanie jest identyczne z wersja z briefu.
   Efekt uboczny (zamierzony i przetestowany): `manager.vertical_crs` tez
   raportuje teraz wartosc providera, wiec property, segment i sidecar mowia
   jednym glosem.

3. **N-03, DWA testy zamiast jednego.** Sformulowanie "test blizniaczy do
   `test_manager_without_descriptor_key_falls_back_to_resolution`, ktory pada
   pod ta mutacja" pokrywa mutacje `vertical_crs=` w `FileStorage(...)`, ale
   NIE mutacje samego nadpisania pionu z providera (sciezka deskryptorowa
   wypelnia `{vcrs}` wczesniej). Dodalem oba testy, po jednym na mutacje
   (D i E w tabeli).

4. **N-05, test wiaze tabele z rzeczywistoscia.** Brief prosil o "dwie
   asercje". Zamiast dwoch asercji obecnosci napisalem jeden test, ktory dla
   obu par sprawdza i obecnosc wpisu (`KeyError` = brak), i zgodnosc
   `expected_accuracy_m` z dokladnoscia, ktora NAPRAWDE wybiera polityka.
   Sama obecnosc wpisu nie wychwycilaby regresji doboru operacji, a to jest
   jedyny cel, dla ktorego `KNOWN_PATHS` istnieje (ARCHITECTURE sekcja 5
   pkt 6). Koszt: test jest wrazliwy na zmiane wersji PROJ — ale to jest
   dokladnie ta regresja, ktora ma sygnalizowac.

5. **N-08, `unlink` w `transform/raster.py` — analiza roznicy.** Sprawdzilem:
   jest rownie zbedne co usuniete. `warp_to_grid` pisze do
   `<dst>.<pid>_<tid>.warp.tif` i dopiero `os.replace(tmp, dst_path)` tworzy
   cel; `os.replace` jest atomowe w obrebie systemu plikow, wiec awaria
   w dowolnym momencie (budowa profilu, `reproject`, zamkniecie datasetu)
   zostawia cel nietkniety, a nie polzapisany. Jedyna roznica funkcjonalna
   wobec toru PL jest wiec taka, ze `warp_to_grid` swiadomie kasuje STARY,
   poprawny wynik. Zgodnie z rulingiem ZOSTAWIAM ten kod (lustro
   `providers/cuzk/dmr.py::_warp_to_grid`, ADR-024, nie ruszamy przed
   wydaniem) i przypilnowalem go testem `test_failed_warp_removes_stale_
   destination`, zeby przyszla unifikacja byla swiadoma zmiana, a nie cichy
   dryf. Do backlogu: ujednolicic PL i CZ po wydaniu 0.7.0.

6. **N-01, warunek `cutout.pinned is not None` wziety doslownie.** Suma godel
   nie dziala dla `--target-crs EPSG:2180` (sam crop). Konsekwencja: w tym
   jednym wariancie geometry rzadka geometria nadal daje pasy `nodata`
   miedzy odleglymi obiektami. Uznalem to za rozstrzygniete brzmieniem
   naprawy w briefie i **udokumentowalem jawnie** (ostatnie zdanie akapitu
   geometry w sekcji 4.3: "Dla `--target-crs EPSG:2180` (sam crop, bez warpa)
   sumy nie ma"). Jesli intencja byla szersza (`cutout is not None`), to
   zmiana jednego warunku — patrz USTALENIA pkt 1.

7. **Zakres tekstowy szerszy o dwa miejsca.** (a) `kartograf/transform/crs.py`
   docstring `gdal_operation` powtarzal doslownie blad z N-10.4 ("Dla celu
   northing-first") — poprawilem razem z dokumentem, bo zostawienie kopii
   bledu w kodzie mijaloby sie z celem pozycji. (b) `docs/CHANGELOG.md`:
   wpis 0.7.0 obiecywal semantyke "odswiez albo nic" usunieta w N-08 oraz
   opisywal `--geometry` sprzed N-01; poprawilem takze wpisy o pustym
   `vertical_crs` i o pionie segmentu. Bez tego wydanie wyszloby z CHANGELOG-iem
   opisujacym nieistniejace zachowanie — czyli z osma i dziewiata pozycja tej
   samej klasy, ktora fala naprawcza wlasnie zamyka.

8. **Sekcja "NIE RUSZAC" respektowana w calosci.** `providers/cuzk/`
   nietkniety (jedyny kontakt: import `bbox_to_crs` w tescie, jak dotad),
   `landcover/` nietkniety, `nodata = -9999.0` na sztywno zostaje,
   `_prepare_pl_cutout` dalej sklada sciezke z pominieciem `FileStorage`,
   guard R-12 dalej robi `raise`, duplikacja `warp_to_grid` wzgledem CZ
   zostaje, ADR-005 bez zmian, drobiazgi z triazu nietkniete.

---

## Ustalenia (nie naprawiane, do decyzji kontrolera)

1. **`--target-crs EPSG:2180` + `--geometry` zostaje z ramka nodata.** Argument
   z rulingu ("wynik i tak obejmuje CALA obwiednie, wiec uczciwie ja wypelnic")
   stosuje sie tak samo do sciezki bez warpa — tam crop tez idzie po pelnej
   obwiedni. Zmiana to `cutout.pinned is not None` -> `cutout is not None`
   w `download_cmd.py:1980` plus jedno zdanie w dokumencie. Nie zrobilem tego,
   bo brief podal warunek wprost.

2. **`_finalize_pl_cutout` lapie teraz takze `KeyboardInterrupt`? Nie.**
   `except Exception` swiadomie NIE obejmuje `BaseException`, wiec Ctrl+C dalej
   przerywa zadanie zamiast konczyc je kodem 1. `finally` w `_build_pl_cutout`
   nadal sprzata plik tymczasowy takze przy `KeyboardInterrupt`.

3. **`docs/PROGRESS.md` nie byl aktualizowany** — brief go nie wymienia,
   a jest to plik prowadzony na poziomie sesji, nie fali naprawczej.

4. **Sidecar wycinka a segment przy `--vertical-crs KRON86 --resolution 5m`.**
   Przy okazji N-06 potwierdzone, ze CLI zachowuje sie poprawnie tylko dzieki
   temu, ze fabryka providera koryguje pion; sama flaga `args.vertical_crs`
   pozostaje `"KRON86"` do konca zadania. To dziala, ale znaczy, ze kazde nowe
   uzycie `args.vertical_crs` w torze wycinka bedzie z definicji bledne.
   Kandydat na backlog: rozwiazywac korekte raz, w `_resolve_pl_sentinels`.

---

## Brama koncowa

```
$ .venv/bin/python -m pytest tests/ -q
============================ 1787 passed in 25.41s =============================

$ .venv/bin/python -m ruff format --check kartograf/ tests/
86 files already formatted

$ .venv/bin/python -m ruff check kartograf/ tests/
All checks passed!

$ .venv/bin/python -m mypy kartograf/
Found 32 errors in 9 files (checked 52 source files)      # baseline 32, zero nowych

$ .venv/bin/python -m pytest tests/ -q --cov=kartograf
TOTAL   5591   406   93%
Required test coverage of 60.0% reached. Total coverage: 92.74%

$ git status --short
(pusto)
```

Bilans testow: 1775 -> **1787** (+12 nowych przypadkow: 1 x N-01, 2 x N-03,
1 x N-04, 1 x N-05, 1 x N-06, 3 x N-07 (jeden z nich niesie takze N-08),
1 x N-09, 2 x N-11. Pozostale asercje z briefu — N-01 pkt 2 i 3 oraz N-11
pkt 1 (`resampling`) — doszly do testow JUZ ISTNIEJACYCH, wiec nie zwiekszaja
licznika, ale kazda ma wlasny dowod mutacyjny.)

## Samo-review diffu

- Zmiany zachowania sa cztery i wszystkie sa objete testem, ktory bez nich
  pada: suma godel w `--geometry` (N-01), pion segmentu z providera (N-03),
  pusty `vertical_crs` (N-04), brak kasowania celu (N-08) i szerszy `except`
  (N-09).
- Nie dodalem zadnego testu chodzacego w siec — nowe przypadki albo mockuja
  warstwe pobierania (`_download_godlo_list`, `_create_provider_and_storage`),
  albo licza wylacznie lokalnie (pyproj/rasterio, `allow_network_grids=False`).
- Nie ruszalem podpisow funkcji publicznych. `_run` w `tests/test_pl_cutout.py`
  dostal opcjonalny parametr `provider=` i wspolna stala `_BBOX_2180` —
  zmiana wewnatrz pliku testowego, wszystkie wywolania zaktualizowane.
- `from kartograf.transform.crs import TransformError` w `_finalize_pl_cutout`
  stal sie zbedny po N-09 i zostal usuniety (ruff to potwierdza).
- Komentarze i docstringi po polsku bez diakrytykow tam, gdzie plik juz taki
  jest; `download/storage.py` i `download/manager.py` uzupelnione po angielsku
  zgodnie z jezykiem pliku; `docs/SCOPE.md` z diakrytykami, jak reszta pliku.
