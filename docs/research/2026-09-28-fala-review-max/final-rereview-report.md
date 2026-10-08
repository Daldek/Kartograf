# Re-review fali finalnej (84bd0a8..61f60de) — raport re-reviewera (opus)

(Zapis odpowiedzi re-reviewera przekazanej kontrolerowi; rulingi kontrolera do
N-1..N-4 — w `sdd-ledger.md`.)

## Finding Verdicts

1. **I-1 + m-1 (`--force` i `--workers` toru wycinka PL): ADDRESSED.**
   - Test `tests/test_pl_cutout.py:861` `TestDownloadPlBboxCutout::test_force_rebuilds_existing_cutout_and_passes_workers` — asercje z briefu: rc 0, tresc pliku zmieniona i rasterio czyta same 100.0, `download_sheets` z `skip_existing is False`, `self.dm` z `max_workers == 3`.
   - Kod bez zmian: `cli/download_cmd.py:1035-1036`, `download/cutout.py:586-588`.
   - Mutacje (a), (b), (c) powtorzone samodzielnie — kazda daje FAIL.
2. **I-2 (raport wyjatku OGC w odpowiedzi 2xx): ADDRESSED.**
   - URL zawsze wygrywa: straz `providers/pl/gugik.py:601-616` stoi ZA blokiem `if urls:` (`:582-599`), obie galezie bloku zwracaja (`:588` URL z godlem, `:599` fallback); blok zmienil sie tylko z `response.text` na `text` (`:574`).
   - Straz wylacznie negatywna: podciagi `ServiceException`/`ExceptionReport` (`:36`), bez `Content-Type` i bez kontroli pozytywnej; skutek: `transport_errors += 1`, `DownloadError` z warstwa, kodem HTTP i wyciagiem, `logger.warning`, `continue`; galezie po petli (`:624-641`) bez zmian.
   - Jedyne `raise NoCoverageError` (`:643`) osiagalne tylko przy `transport_errors == 0` — kazda warstwa musi przejsc `get` i `raise_for_status`, bez URL i bez znacznika.
   - NMPT dziedziczy straz (`gugik_nmpt.py` definiuje tylko `name`/`__init__`); Orto ma wlasny `_get_opendata_url`, ktory nigdy nie rzuca `NoCoverageError`.
   - Testy: (a) `test_gugik_provider.py:574`, (b) `:605`, (c) `:515` bez zmian, (d) `:629`.
   - Tryby bez `--target-crs`: klase bledu rozroznia tylko wycinek (`no_coverage`) — kody wyjscia bez zmian (grep).
   - CHANGELOG `:639` i ARCHITECTURE `:483-489` zgodne z kodem; wyzwalacz realny: CHANGELOG `:510,523` zapisal od GUGiK "Invalid layer(s)...", a `gugik.py:388` przy nieudanym GetCapabilities wraca do nazw zaszytych w kodzie.
3. **m-2 (wielkosc liter ukladu bboxa): ADDRESSED.** `download/cutout.py:126-133` `crs = bbox.crs.strip().upper()` dla obu warunkow; galaz czeska podaje do `bbox_to_crs` nieznormalizowany bbox — bezpieczne (pyproj normalizuje, wynik z etykieta `EPSG:2180`). Testy `test_pl_cutout.py:291` (`epsg:5514`, `" EPSG:5514 "`, warunek `shift > 0.01`) i `:326`. Niezalezny pomiar: max |przypieta - niepinowana| = 1,0624 m (`max_y`). `"Epsg:5514"`, `"epsg:3045"` — identyczne z wariantem wielkimi literami. `--bbox-crs` ma `choices` wielkimi literami (`_parser.py:92-101`).
4. **m-6 + m-7 (docstringi API): ADDRESSED.** `manager.py:78-80, 124-131, 302-307, 374-385, 457-464` zgodne z kodem (reset `last_result` `:311/:396/:476`, zapis tylko `:619/:720`, `download_bbox` go nie dotyka, sekwencyjnie tylko `NoCoverageError`/`DownloadError` `:587/:604`, pula `except Exception` `:655` -> `failed` bez `no_coverage`). `gugik.py:428-440`: `NoCoverageError` z warunkiem i wylaczeniem raportu OGC.
5. **m-8 (komendy testow): ADDRESSED.** `CLAUDE.md:124-138`, `README.md:355-363`: `-m "not live"` w obu domyslnych komendach + osobna linia `-m live`; 8/1869 zmierzone (`TestPL2000LiveWMS`, WMS GUGiK); `pyproject.toml:73` `addopts` bez `-m`.
6. **m-9 + m-10 (precyzja ARCHITECTURE): ADDRESSED** (jedna uwaga Minor N-3).
   - (a) wstep 4.3 `:401-416` zgodny z `download_cmd.py:976-1042` i bariera `main()` (`commands.py:94-104`); miedzy `_download_pl_cutout` a `main()` nie ma `try`.
   - (a) krok 4 `:470-479`, `:498` — potwierdzone sonda (fake provider z `OSError`): `workers=1` -> `OSError` wylatuje z `download_sheets` (`last_result` None) i z `run_pl_cutout`; `workers=2` -> `failed` = oba arkusze, `no_coverage=[]`, `run_pl_cutout` rzuca `DownloadError "2 z 2 ..."`; domyslne `--workers` w CLI = 4.
   - (b) `:625-629` — oba testy istnieja (`test_pl_cutout.py:191`, `test_transform_raster.py:192`).
   - (c) `:287`, `:580-585` — `max(1, round(...))` od naroznika NW (`raster.py:97-99`, CZ `dmr.py:520-522`); liczby 80 601 / 79 799 zgodne z E2E.
   - (d) `:110-113` — oba importy `bbox_to_crs` wewnatrz funkcji (`cutout.py:131`, `:180`).

## New Breakage in the Fix Diff

Brak Critical i Important. Minor:
- **N-1** — "URL wygrywa" broniony tylko dla URL z tym godlem (test d); mutacja: kopia strazy wewnatrz `if urls:` przed fallbackiem "URL innego arkusza" (`gugik.py:590`) przezywa cala suite (1861 passed). Naprawa: parametr testu z odpowiedzia fallbackowa (URL `6.179.12.20.asc` + znacznik OGC).
- **N-2** — `_OGC_EXCEPTION_TEXT` (`gugik.py:39-41`, `(.*?)</` z DOTALL) kwadratowy bez zadnego `</`: 20 000 x `<ServiceException>` (360 KB) = 49 s; realne ksztalty (WMS 1.1.1/1.3.0, OWS, CDATA, self-closing, HTML, puste body) poprawne, 560 KB HTML w 4 ms. Oslona: `(.{0,2000}?)</` albo prefiks body.
- **N-3** — ARCHITECTURE `:410-412` nawias "(przy wejsciu zwalidowanym przez CLI nie wystepuje...)": `--bbox nan,...`/`inf,...` przechodzi `float()`; `select_pl_cutout_sheets` rzuca `ValueError`/`OverflowError` (`core/sheet_parser.py:1100`) -> bariera `main()`: "Error: ValueError: cannot convert float NaN to integer", rc 1. Zachowanie sprzed fali; opis skutku dokladny.
- **N-4 (nit)** — komentarz `test_pl_cutout.py:302` "Cieszyn (PL)": bbox 18,515-18,530°E / 49,709-49,719°N lezy po stronie CZ, ~8 km WSW od Cieszyna.
- **(nit)** ARCHITECTURE 3.3 `:287` "do 0,5 px" bez zastrzezenia `max(1, ...)` (jest w 4.3 `:583`, do ktorej 3.3 odsyla).

Rozszerzenia implementera poza litera briefu: docstringi "never raise" — prawdziwe (sonda); test (d) wartosciowy (luka N-1); wyciag regexem poprawny (uwaga N-2); kod HTTP w komunikacie, dopisek `max(1, ...)`, zdanie o `addopts` — prawdziwe. "MapServer zwraca raport wyjatku z HTTP 200" nie zapisane dla GUGiK — w docs jako "np.", zgodne z rulingiem.

## Mutacja kontrolna

Kazdy przebieg: odmowa startu przy brudnym drzewie -> mutacja -> pytest z nowym `PYTHONPYCACHEPREFIX=$(mktemp -d)` i `-p no:cacheprovider` -> `git checkout -- <plik>` -> pytest z kolejnym prefiksem -> `git status --short`.

| # | Mutacja | Wynik | Po przywroceniu |
|---|---|---|---|
| 1 | I-2: `gugik.py:608` `if any(...)` -> `if False:` | 2 failed ((a) "Regex pattern did not match ... No NMT 1m data available", (b) "assert not True") | 4 passed, pusty |
| 2 | I-2 M2: straz przed regex URL (rozmiar bez zmian) | 1 failed ((d) "all 1 layer queries failed (last error: warstwa L1: raport wyjatku OGC ... HTTP 200") | 4 passed, pusty |
| 3 | I-1 (a) `force=False` | FAIL "--force nie przebudowal wycinka" | 1 passed, pusty |
| 4 | I-1 (b) `max_workers=1` | FAIL `assert 1 == 3` | 1 passed, pusty |
| 5 | I-1 (c) `skip_existing=True` | FAIL `assert True is False` | 1 passed, pusty |
| 6 | m-2 `crs = bbox.crs` | 2 failed | 3 passed, pusty |
| 7 | N-1: straz w `if urls:` przed fallbackiem | przezywa: 1861 passed | 1861 passed, pusty |

Brama na 61f60de (swiezy pycache): 1861 passed, 8 deselected; ruff check/format czyste; mypy 32, lista `error:` = baseline (roznia sie tylko 3 linie `note:` w nietknietym `auth/proxy.py`, ktorych baseline nie zawiera); diff od 84bd0a8 dla `providers/cuzk`, `transform/raster.py`, `docs/PROGRESS.md` pusty; 6 commitow, bez plikow `.superpowers/`; `git status --short` pusty.

## Out-of-Scope Observations

- Liczby testow w dokumentach nieaktualne: `README.md:334,380`, `CHANGELOG.md:658-663`, `SCOPE.md:497,526` (1854; zmierzone 1861 offline + 8 live) — do zamkniecia fali.
- Checklista live dla I-2 — takze drugi kierunek strazy: jesli realna "pusta" odpowiedz GetFeatureInfo GUGiK (morze / strona czeska) zawiera `ServiceException`/`ExceptionReport`, R5 nigdy nie zadziala (glosno: kod 1, bez dziury — ale wycinki przy wybrzezu i granicy przestalyby powstawac).
- Sprzed fali: `--bbox` z min > max przechodzi prepare i select wycinka bez bledu.
- Sprzed fali: `nan` w `--bbox` z celem 5514 daje mylacy `TransformError` "Brak bezpiecznej operacji...".

## Verdict

**Fix round:** All findings addressed, no new Critical/Important breakage. N-1..N-4 — Minor/nit, do decyzji kontrolera; nie blokuja.
