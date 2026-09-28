# Zad. 1: Dokumentacja zgodna z kodem — `--force` i selekcja arkuszy R-01 — raport

## Co zrobiono

Docs-only, bez kodu i testow (zgodnie z brief: "dowody mutacyjne" nie dotycza tego zadania).
Wykonano Step 1-6 z briefu:
1. Zweryfikowano na zywym kodzie wszystkie twierdzenia z briefu.
2. Podmieniono akapit w `CLAUDE.md` (semantyka `--force`).
3. Podmieniono akapit "Decyzja" w `docs/DECISIONS.md` (ADR-027, selekcja arkuszy R-01).
4. Podmieniono akapit "Konsekwencje" w `docs/DECISIONS.md` (ADR-027, semantyka `--force` + adnotacja korekty).
5. `grep` na bledne sformulowania poza `docs/research/`/`docs/superpowers/` — brak wynikow.
6. Commit na `develop`.

## Step 1 — weryfikacja faktow na kodzie (szczegoly)

Wszystkie twierdzenia briefu **potwierdzone doslownie** na kodzie — zadna korekta tekstu nie byla potrzebna.

**Tor PL nie kasuje poprzedniego wyniku:**
- `kartograf/cli/download_cmd.py:1042-1091` (`_build_pl_cutout`): zapisuje do `tmp` (nazwa
  `<target>.<pid>_<tid>.mosaic.tif`), potem albo `os.replace(tmp, target_path)` (cel EPSG:2180)
  albo woła `warp_to_grid(tmp, target_path, ...)`. Blok `finally` kasuje WYLACZNIE `tmp`
  (`tmp.unlink(missing_ok=True)`) — brak jakiegokolwiek `target_path.unlink`.
- `kartograf/transform/raster.py:70-137` (`warp_to_grid`): pisze do `tmp_path`
  (`<dst>.<pid>_<tid>.warp.tif`), `os.replace(tmp_path, dst_path)` w `try`, `finally` kasuje
  WYLACZNIE `tmp_path.unlink(missing_ok=True)` — zadnego czyszczenia `dst_path`. Docstring
  (linie 78-81) i komentarz w `finally` (135-137) wprost potwierdzaja: "awaria NIE kasuje
  `dst_path`".
- Testy potwierdzajace behawior (przeczytane, nie tylko po nazwie):
  - `tests/test_pl_cutout.py::TestBuildPlCutout::test_failed_build_keeps_previous_result`
    (linia 145): patchuje `warp_to_grid` na `RuntimeError`, sprawdza ze `target.read_bytes()`
    to nadal poprzedni wynik i ze nie zostal `*.mosaic.tif`.
  - `tests/test_transform_raster.py::test_failed_warp_keeps_previous_destination` (linia 192):
    patchuje `reproject` na `RuntimeError`, sprawdza `dst.exists()` ORAZ `dst.read_bytes() ==
    previous` (nie tylko `exists()` — docstring testu explicite to podkresla) i brak
    `*.warp.tif`.

**Tor CZ KASUJE plik docelowy przy awarii (odwrotnie niz PL):**
- `kartograf/providers/cuzk/client.py:182-192`: przy wyjatku z `mosaic_and_crop`
  (`except Exception as e:`) jest `output_path.unlink(missing_ok=True)` przed `raise
  DownloadError(...)`.
- `kartograf/providers/cuzk/dmr.py:500-561` (`_warp_to_grid`): `except BaseException:` (linia
  557) -> `dst_path.unlink(missing_ok=True)` (linia 558) -> `raise`.

**R-01 (selekcja arkuszy w `--geometry` przy warpie = suma):**
- `kartograf/cli/download_cmd.py:1958-1993` (tryb `--geometry`): `cutout =
  _prepare_pl_cutout(...)`; jesli `cutout.pinned is not None` (czyli target_crs != EPSG:2180),
  `godlo_list` staje sie `sorted(set(godlo_list) | set(find_sheets_for_bbox(
  cutout.bbox_source_2180, target_scale, system=args.system)))` — dokladnie suma godel
  geometrii (juz policzonych wczesniej per obiekt) i godel powiekszonego bboxa. Jesli `pinned
  is None` (cel EPSG:2180), ten blok w ogole sie nie wykonuje — `godlo_list` zostaje z samej
  geometrii.
- `kartograf/cli/download_cmd.py:943-1039` (`_PlCutout`/`_prepare_pl_cutout`) potwierdza
  asymetrie zapasu: gdy `args.target_crs == "EPSG:2180"` -> `pinned = None`,
  `bbox_source_2180 = bbox_2180` (BEZ zapasu). Gdy `target_crs != "EPSG:2180"` -> `pinned`
  budowany, `bbox_source_2180` dostaje `margin = _PL_WARP_MARGIN_PX * pixel_size` na kazda
  strone. To dokladnie potwierdza klauzule briefu "dla celu EPSG:2180 zapasu nie ma, wiec
  arkusze wyznacza sama geometria".
- Dla trybu `--bbox` (linia 1226-1243): `sheet_bbox = bbox if cutout is None else
  cutout.bbox_source_2180` — ZAWSZE `bbox_source_2180` gdy jest `--target-crs`, niezaleznie od
  `pinned` (bo `bbox_source_2180` juz samo w sobie koduje "z zapasem albo bez", patrz wyzej).
  To potwierdza "`--bbox` wybiera arkusze wprost z niego [powiekszonego bboxa]".

Wniosek: teksty zamiany z briefu (Step 2-4) sa scisle zgodne z kodem — zastosowano je BEZ
zmian.

## Zmiany

### `CLAUDE.md` (linie ~297-298 -> 297-300)
Stare zdanie twierdzilo, ze `--force` przy nieudanej budowie wycinka kasuje TAKZE poprzedni
plik ("odswiez albo nic", jak w torze CZ) — to jest ODWROTNOSC prawdy: kod PL nigdy nie kasuje
`target_path` przy awarii (zapis atomowy `os.replace`), a to wlasnie tor CZ kasuje plik
docelowy przy awarii. Podmieniono na tekst z briefu (doslownie, Step 2) opisujacy prawdziwe
zachowanie i kontrastujacy je z torem CZ.

### `docs/DECISIONS.md`, ADR-027 "Decyzja" (linie ~1036-1038 -> 1036-1040)
Stare zdanie twierdzilo, ze w trybie `--geometry` "arkusze dalej wyznacza sama geometria per
obiekt, a zapas wplywa wylacznie na crop i siatke" — czyli ze R-01 (suma godel geometrii +
godel powiekszonego bboxa) NIE zachodzi. To tez jest odwrotnosc kodu (patrz Step 1 wyzej).
Podmieniono na tekst z briefu (doslownie, Step 3) opisujacy R-01: `--bbox` wybiera arkusze
wprost z powiekszonego bboxa, `--geometry` przy warpie bierze sume, a dla celu EPSG:2180 (bez
warpu) zapasu nie ma wiec o selekcji decyduje sama geometria.

### `docs/DECISIONS.md`, ADR-027 "Konsekwencje" (linie ~1046-1048 -> 1048-1053)
Ta sama odwrotnosc semantyki `--force` co w CLAUDE.md, w akapicie Konsekwencji. Podmieniono na
tekst z briefu (doslownie, Step 4), ktory dodatkowo dopisuje adnotacje korekty z data i
odniesieniem do review max 2026-08-30 (znaleziska 5-6).

## Step 5 — grep bledne sformulowania poza historia

```
$ grep -rn "odswiez albo nic\|kasuje TAKZE\|wplywa wylacznie na crop" CLAUDE.md README.md docs/ --include=*.md | grep -v "docs/research/\|docs/superpowers/"
```
Wynik: brak (0 linii) — zgodnie z oczekiwaniem briefu. Sformulowania nadal wystepuja w
`docs/research/2026-08-28-uklad-data-target-crs-pl/2026-08-30-code-review-max.md` (raport
historyczny — poza zakresem, bez zmian, jak nakazuje brief) oraz w
`docs/superpowers/plans/2026-09-28-fala-review-max-i-wycinek-biblioteczny.md` (plan tej fali,
edytowany rownolegle przez inny agent — nie dotykany).

## Pliki zmienione

- `/home/claude-agent/workspace/Kartograf/CLAUDE.md`
- `/home/claude-agent/workspace/Kartograf/docs/DECISIONS.md`

`git status --porcelain` po commicie: pusty (czysto).

## Testy / ruff / mypy

Nie dotyczy — zadanie czysto dokumentacyjne, zero zmian w `kartograf/` ani `tests/`. Zgodnie z
IMPLEMENTER_COMMON.md dowody mutacyjne i pelna suita nie sa wymagane dla tego zadania (brak
kodu/testow do zepsucia). Nie uruchamiano pytest/ruff/mypy.

## Commit

```
f76b860 docs: semantyka --force i selekcja arkuszy R-01 zgodne z kodem (CLAUDE.md, ADR-027)
```
(2 pliki zmienione, 15 insercji, 8 usuniec). Stopka `Co-Authored-By: Claude Opus 5.5
<noreply@anthropic.com>` wg wyraznej instrukcji kontrolera (nadpisuje domyslna stopke
Sonnet z tego srodowiska dla tego zadania).

## Samoocena i watpliwosci

- Wszystkie trzy podmiany tekstu sa DOSLOWNE z briefu (zero korekt) — weryfikacja na kodzie
  (Step 1) potwierdzila kazde zdanie briefu co do joty, wiec nie bylo potrzeby odstepstwa od
  brzmienia z briefu (co brief dopuszczal w razie rozbieznosci).
  Kotwice linii w briefie (`CLAUDE.md:297-298`, `DECISIONS.md:1034-1040` /`1046-1048`) okazaly
  sie scisle trafne — bez przesuniec.
- Plik `docs/superpowers/plans/2026-09-28-fala-review-max-i-wycinek-biblioteczny.md`
  (edytowany rownolegle przez innego agenta) nie byl dotykany ani stage'owany — `git add`
  ograniczony do `CLAUDE.md docs/DECISIONS.md` zgodnie z instrukcja kontrolera.
- Brak watpliwosci co do tresci zmiany. Jedyna rzecz do odnotowania: R2 (COMMON-CONTEXT) mowi,
  ze "rzadka geometria wieloobiektowa" jest poza zakresem fali (bez zmian w kodzie) — ale to
  zadanie i tak nie dotyka kodu, wiec nie ma to wplywu na Zad. 1.
