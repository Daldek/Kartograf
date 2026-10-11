# Spec: Wycinki PL (`--target-crs`) z WCS GUGiK (a) i naprawa NMPT `download_bbox`

**Data:** 2026-10-11
**Status:** ZATWIERDZONY przez uzytkownika 2026-10-11; decyzje w sekcji 0;
pomiary M1-M3 wykonane 2026-10-11
(`docs/research/2026-10-11-wcs-cutouts/raport.md`).
**Wersja docelowa:** 0.7.2 (galaz `feat/wcs-cutouts` z `develop`)
**Dokumenty zrodlowe:**
- backlog `docs/PROGRESS.md` "Do 0.7.2" pozycja (a) i "NMPT `download_bbox`
  zwraca RGB uint8" (decyzje 2026-10-09 i 2026-10-10)
- pomiar `docs/research/2026-10-10-wcs-limits/raport.md` (KRON86: limity,
  siatka, brak nodata, kompozycja lotow, NMPT RGB)
- sonda na zywo 2026-10-11 (sekcja 1.3) i pomiar
  `docs/research/2026-10-11-wcs-cutouts/raport.md` (siatki arkuszy 1 m
  i 0,5 m, WCS vs arkusze bit w bit, ASC, maska PRG)
- ADR-024 (bez serwerowej reprojekcji tresci, operacje pinned), ADR-027
  (wycinek PL z arkuszy — czesciowo odwracany), ADR-030 errata 1 i 5,
  ADR-032 P6 (wycinki bez flag roku), ADR-034 (`transport/chunks.py`)

---

## 0. Decyzje uzytkownika

| # | Decyzja | Sekcja |
|---|---|---|
| W-U1 | **Zrodlo wycinka PL = WCS GUGiK**, nie mozaika arkuszy OpenData (odwraca ADR-027 w CLI; nowy ADR-035). (2026-10-09) | 2, 4 |
| W-U2 | **Wycinki bez flag roku i kampanii** (jak dzis, ADR-032 P6); **wycinki 5 m znikaja** (WCS ma tylko 1 m NMT); **ponowienia obowiazkowe** (host niestabilny). (2026-10-09) | 3.4, 4.6 |
| W-U3 | **Data pobrania w nazwie pliku wycinka.** (2026-10-09) | 4.4 |
| W-U4 | **Naprawa NMPT `download_bbox` (RGB uint8 -> wysokosci) razem z (a)**; obsluga odpowiedzi multipart `image/x-aaigrid` powstaje raz. (2026-10-10) | 5 |
| W-U5 | **Nodata = maska ladu PL z PRG:** `A00_Granice_panstwa` minus `W02_Morze_terytorialne_RP` minus `W03_Morskie_wody_wewnetrzne`; poza maska -9999, wewnatrz wartosci serwera bez zmian (takze 0,0). (2026-10-11) | 6 |
| W-U6 | **CLI i `download_pl_cutout` przechodza na WCS; API arkuszowe zostaje** (`prepare_pl_cutout`/`select_pl_cutout_sheets`/`run_pl_cutout`/`build_cutout_from_sheets`, `PlCutoutSheets`) bez zmian zachowania, oznaczone w dokumentacji jako przestarzale; usuniecie w 0.8.0 razem z parametrami arkuszowymi `mosaic_and_crop`. (2026-10-11) | 7 |
| W-U7 | **Zakres: NMT i NMPT** — wycinki `--product nmpt --target-crs` wchodza do (a). (2026-10-11) | 3, 8 |
| W-U8 | **Kazde uruchomienie pobiera** — wycinek WCS nie ma skip-existing (serwer moze zmienic kompozycje). (2026-10-11) | 4.4 |
| W-U9 | **Zakres zapytania wyrownany NA ZEWNATRZ do siatki arkuszy przed pobraniem** — dane WCS porownywalne z arkuszami 1:1, bez bledu przesuniecia; dotyczy tez NMPT (rozdzielczosc wyniku inna niz krok coverage). (2026-10-11) | 3.2, 4.1 |
| W-U10 | **Wycinki tylko 1 m** (siatka `k + 0,5`); 0,5 m — moze pozniej. (2026-10-11) | 3.2 |
| W-U11 | **0,0 wewnatrz ladu zostaje danymi** — zamiana na nodata zrobilaby duzy problem na Zulawach; `M-33-57-C-b-4-2` pokazal, ze 0,0 w WCS to obszar za granica (lot 2025 przyciety do granicy), ktory lapie maska PRG. (2026-10-11) | 6.2 |

## 1. Kontekst i fakty

### 1.1 Dzis (kod `develop` `82a9eff`)

| Element | Dzis | Gdzie |
|---|---|---|
| Tor CLI | `_download_pl_bbox` -> przy `--target-crs` `_download_pl_cutout`: `prepare_pl_cutout` -> skip istniejacego -> `select_pl_cutout_sheets` -> `run_pl_cutout` (arkusze przez `DownloadManager.download_sheets`, R5, `build_pl_cutout`: `check_source_grid`, `mosaic_and_crop`, `warp_to_grid`) | `cli/download_cmd.py:1765-1920`, `download/cutout.py` |
| Straze | `--target-crs` tylko `--product nmt` (`_resolve_pl_sentinels` :409-416), bez `--system 2000`; flagi roku/`--campaigns all`/`--full-sheet` = `Error:` (`_reject_campaign_opts_with_target_crs` :332-370) | `cli/download_cmd.py` |
| Nazwa | `bbox_cutout_path(output_dir, subdir, bbox_target, ".tif")` -> `<segment>/bbox/<wsp>.tif`; istniejacy plik bez `--force` = `skipped` | `download/cutout.py` |
| Sidecar | `write_pl_cutout_sidecar`: `capability="sheet_files"`, `nodata=-9999`, `extra.{parent_request, missing_sheets, sheet_sources, off_grid_sheets, all_nodata, unverified_sheets}` | `download/cutout.py:508-569` |
| WCS NMT | `GugikProvider.WCS_ENDPOINTS`: KRON86 `DigitalTerrainModelFormatTIFF` / `DTM_PL-KRON86-NH_TIFF` (float32, dziala); EVRF2007 `DigitalTerrainModelFormatTIFFEVRF2007` / `DTM_PL-EVRF2007-NH_TIFF` (404 — taki endpoint nie istnieje); `WITHDRAWN_WCS_VERTICAL_CRS = ("EVRF2007",)` | `providers/pl/gugik.py:98-139` |
| WCS NMPT | `DigitalSurfaceModel` / `DSM_PL-<v>-NH`, `image/tiff` = RGB uint8 (blad), `WCS_GRID = None` | `providers/pl/gugik_nmpt.py:51-97` |
| Kawalki | `GugikWcsMixin._download_wcs`: przy `WCS_GRID` `align_bbox` -> `plan_chunks` (`WCS_CHUNK_LIMITS` 16 Mpx) -> `fetch_chunks`; kazdy kawalek `download_to(retries=MAX_RETRIES, validate=reject_error_document("WCS"))` | `providers/pl/wcs.py` (ADR-034) |
| Rejestr | `pl.gugik.nmt_1m` kanal WCS `bbox_raster` tylko EPSG:9650 (KRON86) z notatka o 404; `pl.gugik.nmpt` tylko `sheet_files` | `sources/registry.py:77-148` |
| PRG | `providers/pl/prg.py`: WFS `AdministrativeBoundaries`, warstwa powiatow, `download_to` z ponowieniami, walidacja `FeatureCollection` | — |

### 1.2 Pomiar 2026-10-10 (KRON86; raport pkt)

- Brak nodata; poza pokryciem, na morzu i w brakujacych arkuszach **0,0**;
  0,0 wystepuje tez w danych waznych (Leba: 4233 px lustra wody) (pkt 3, 8).
- WCS = kompozycja lotow serwera, nie najnowszy lot ADR-028 (Zulawy: 7-14 cm
  roznicy; Terespol: 1,1 mln px waznych w arkuszu = 0,0 w WCS) (pkt 8).
  Uzupelnienie 2026-10-11 (raport 2026-10-11 pkt 4): WCS pokazuje
  najnowszy lot obszaru i nie dokleja starszych; `M-33-57-C-b-4-2`: 0,0
  w WCS tam, gdzie lot 2025 jest przyciety do granicy panstwa, a lot 2023
  ma pas za granica.
- Siatka NMT 1 m: krok 1 m, krawedzie `k + 0,5` m w 9 rejonach; bbox poza
  siatka = cichy blad geolokalizacji (pkt 4, 7). Kawalki skladaja sie bit
  w bit (pkt 5).
- Brak limitu do 100 Mpx; ok. 3 s/Mpx, 4 MB/Mpx; host zrywa polaczenia,
  ponowienie przechodzi (pkt 2).
- NMPT `image/tiff` = RGB uint8; wysokosci tylko `image/x-aaigrid`
  (multipart), naglowek ASC bez `NODATA_value`; w probce wartosci parami
  (tresc 1 m na siatce 0,5 m) (pkt 6).

### 1.3 Sonda na zywo 2026-10-11 (20 x 20 px od (480000,5; 450000,5))

| Endpoint / coverage | `image/tiff` | `image/x-aaigrid` |
|---|---|---|
| `NMT/GRID1/WCS/DigitalTerrainModel` / `DTM_PL-EVRF2007-NH` | 200, RGB 3 x uint8 | 200, `multipart/related; boundary=wcs`: `result.asc` + `result.asc.aux.xml` + `result.prj`; `xllcorner 480000.5` |
| `NMT/GRID1/WCS/DigitalTerrainModel` / `DTM_PL-KRON86-NH` | 200, RGB 3 x uint8 | 200, multipart jw. |
| `NMT/GRID1/WCS/DigitalTerrainModelFormatTIFF` / `DTM_PL-KRON86-NH_TIFF` | 200, float32, 1 pasmo, nodata brak | — |
| `NMPT/GRID1/WCS/DigitalSurfaceModel` / `DSM_PL-EVRF2007-NH` | 200, RGB 3 x uint8 | 200, multipart jw. |
| `NMT/GRID1/WCS/DigitalTerrainModelFormatTIFFEVRF2007` (wpis biblioteki) | **404** | — |

- **WCS EVRF2007 dziala** (backlog: "tymczasowo niedostepny" — nieaktualne);
  wysokosci EVRF2007 sa tylko w `image/x-aaigrid`.
- DescribeCoverage: NMT EVRF2007 715202 x 697593 px, krok 1 m (jak KRON86);
  NMPT EVRF2007 1430403 x 1395186 px, krok 0,5 m; `nilValues` puste.
- PRG `A00_Granice_panstwa`: 1 obiekt, 1 poligon, ok. 73 tys. wierzcholkow,
  2,0 MB GML, 2,2 s; obwiednia (N,E) 133223-797228 / 171698-861895 —
  obejmuje morze terytorialne (lad konczy sie ok. N 774 km pod Rozewiem).
  `W02_Morze_terytorialne_RP`: 1 obiekt, 33 kB; `W03_Morskie_wody_wewnetrzne`:
  1 obiekt (MultiSurface), 1,2 MB.

### 1.4 Pomiar 2026-10-11 (raport 2026-10-11)

- **Siatki arkuszy:** 1 m — krawedzie `k + 0,5` m; 0,5 m (loty EVRF2007
  od 2023) — krawedzie `k + 0,25` m. Srodki pikseli na wielokrotnosciach
  kroku; siatki 1 m i 0,5 m sie nie zagniezdzaja (pkt 2). Warstwy
  skorowidza "1m" zawieraja arkusze 0,5 m (Kartograf je pomija, filtr
  dokladnie 1 m).
- **Zapytanie na siatce arkusza = tresc arkusza bit w bit** we wszystkich
  zbadanych parach: NMT EVRF2007 1 m i 0,5 m, NMT KRON86 1 m (TIFF i ASC),
  NMPT EVRF2007 0,5 m (2 arkusze), NMPT KRON86 1 m; przesuniecie < 1/2 px —
  te same wartosci opisane obok, 1/2 px — inne wartosci (pkt 3).
- **Rozdzielczosc wyniku != krok coverage:** NMPT 1 m = `SCALEFACTOR=0.5`
  na siatce 1 m — bit w bit z arkuszem NMPT 1 m; zapytanie 1 m nad
  trescia 0,5 m (NMT i NMPT) = dokladna decymacja: piksel 0,5 m o srodku
  na pelnym metrze, bez usredniania (pkt 3).
- **ASC:** ok. 20,5 B/px, ok. 20 s/Mpx; pierwszy bajt po 7 s (1 Mpx)
  i 25 s (4 Mpx); 16 Mpx NMPT nie zaczyna odpowiedzi w 60 s; zawieszenia
  600-1200 s bez zerwania polaczenia (pkt 5).
- **PRG:** `BBOX` nie przycina geometrii (`A00` zawsze 2 MB); `W02`/`W03`
  poza wybrzezem = 0 obiektow. Maska `A00 - W02 - W03` rozdziela lad
  i morze w punktach kontrolnych (Leba, Gdynia, Sopot, Hel, Zatoka Pucka,
  Zalew Wislany, Mierzeja Wislana) (pkt 6).

## 2. Cel i zakres

Wycinek PL `--bbox`/`--geometry` + `--target-crs` (NMT 1 m i NMPT, oba
uklady wysokosci) to jedno pobranie z WCS GUGiK na siatce zrodla
(kawalki ADR-034), maska ladu PL (nodata -9999), lokalny crop (EPSG:2180)
albo pinned warp (EPSG:5514/3045, ADR-024/027 bez zmian), sidecar
opisujacy zrodlo WCS. Biblioteka: `download_pl_cutout` ten sam tor;
`download_bbox` NMT EVRF2007 i NMPT zwraca wysokosci float32.

### 2.1 Poza zakresem

- Usuniecie API arkuszowego i parametrow `snap_to_source_grid`/`assign_crs`
  z `mosaic_and_crop` (W-U6: 0.8.0).
- Wycinki ortofotomapy, `--system 2000`, LAZ — dalej `Error:`.
- Wybor lotu przez WCS (serwer nie daje wyboru; kompozycja serwera,
  sekcja 6.3).
- Wypelnianie 0,0 wewnatrz ladu PL danymi z arkuszy — tylko slad
  `extra.zero_pixels` (sekcja 6.2).
- Wycinki 0,5 m (W-U10).
- Maskowanie do geometrii `--geometry` (jak dzis: wycinek = obwiednia).

## 3. Zrodla WCS per produkt

### 3.1 Tabela

| Produkt / uklad | Endpoint | Coverage | Format | Krok coverage | Zapytanie (siatka wyniku 1 m, W-U9) |
|---|---|---|---|---|---|
| NMT KRON86 | `.../NMT/GRID1/WCS/DigitalTerrainModelFormatTIFF` | `DTM_PL-KRON86-NH_TIFF` | `image/tiff` (float32) | 1 m | bez skalowania |
| NMT EVRF2007 | `.../NMT/GRID1/WCS/DigitalTerrainModel` | `DTM_PL-EVRF2007-NH` | `image/x-aaigrid` | 1 m | bez skalowania |
| NMPT KRON86 / EVRF2007 | `.../NMPT/GRID1/WCS/DigitalSurfaceModel` | `DSM_PL-<v>-NH` | `image/x-aaigrid` | 0,5 m | `SCALEFACTOR=0.5` |

- KRON86 NMT zostaje przy `image/tiff` (4 B/px, ok. 3 s/Mpx, bez
  parsowania tekstu; TIFF i ASC daja te same wartosci — raport pkt 3);
  `image/x-aaigrid` tylko tam, gdzie TIFF nie niesie wysokosci.
- Wpis biblioteki EVRF2007 (`DigitalTerrainModelFormatTIFFEVRF2007`,
  `DTM_PL-EVRF2007-NH_TIFF`) zastapiony wierszem z tabeli;
  `WITHDRAWN_WCS_VERTICAL_CRS` NMT -> `()` (atrybut zostaje — mechanizm
  na przyszle wycofania); komunikat `ValidationError` o 404 znika.
- Format i skalowanie sa wlasciwoscia pary (produkt, uklad), nie
  parametrem wolajacego: atrybuty providera `WCS_HEIGHT_FORMAT: dict[str,
  str]` (uklad -> `"GTiff"` albo `"AAIGrid"`) i `WCS_NATIVE_STEP: float`
  (NMT 1,0, NMPT 0,5); `SCALEFACTOR = WCS_NATIVE_STEP / krok wyniku`
  dopisywany do URL, gdy != 1. Uzywane przez tor wycinka i przez
  `download_bbox(format="GTiff")` (sekcja 5).

### 3.2 Siatka zapytania = siatka arkuszy 1 m (W-U9, W-U10)

- Kazde zapytanie wycinka i `download_bbox` (GTiff) idzie na siatce
  arkuszy 1 m: `GridSpec(step=1.0, origin_x=0.5, origin_y=0.5)` dla NMT
  i NMPT (`WCS_GRID` NMPT: dzis `None` -> ta siatka). Zakres wyrownany NA
  ZEWNATRZ (`align_bbox`, < 1 px na strone) przed podzialem na kawalki;
  kawalki na tej samej siatce (ADR-034).
- Skutek: wycinek EPSG:2180 jest porownywalny z arkuszem 1 m piksel
  w piksel (ten sam lot = te same wartosci, raport pkt 3); nad lotem
  0,5 m wynik to dokladna decymacja arkusza 0,5 m (piksel o srodku na
  pelnym metrze). Dla 5514/3045 wyrownany jest obszar zrodlowy w 2180
  (z zapasem `WARP_MARGIN_PX`), potem pinned warp jak dzis.
- `WCS_GRID` opisuje siatke WYNIKU (1 m), nie krok coverage: `align_bbox`
  i `plan_chunks` bez zmian (`pixel_size == grid.step` = 1 m), a krok
  coverage NMPT (0,5 m) uwzglednia tylko URL (`SCALEFACTOR=0.5`,
  `_construct_wcs_url`). Sprawdzenie w implementacji: kawalki NMPT
  z `SCALEFACTOR=0.5` skladaja sie bit w bit z jednym zapytaniem (jak
  raport 2026-10-10 pkt 5 dla NMT).

### 3.3 Limity kawalkow ASC

`image/x-aaigrid` to ok. 20,5 B/px i ok. 20 s/Mpx, a serwer milczy przed
pierwszym bajtem tym dluzej, im wieksze zadanie (1 Mpx: 7 s, 4 Mpx: 25 s;
raport pkt 5). `GugikProvider.DEFAULT_TIMEOUT` (30 s) jest timeoutem
odczytu, wiec `WCS_CHUNK_LIMITS` dla AAIGrid = **1 Mpx** (pierwszy bajt
ok. 7 s, calosc ok. 20-25 s, ok. 20 MB); TIFF bez zmian (16 Mpx). Limit
wybierany po formacie zapytania (`WCS_CHUNK_LIMITS_BY_FORMAT` albo pole
w `WCS_HEIGHT_FORMAT` — w planie).

### 3.4 Ponowienia

Bez zmian mechanizmu: kazdy kawalek `download_to(retries=MAX_RETRIES)`
(sieciowe, 429, 5xx), `reject_error_document("WCS")`. Dodatkowo walidacja
tresci po pobraniu (sekcja 5.2) — niezgodny rozmiar albo naroznik ASC to
`DownloadError` bez zapisu wyniku (nie ponawiany: blad serwera
deterministyczny).

## 4. Tor wycinka WCS

### 4.1 Przeplyw

```
prepare_pl_cutout(bbox, target_crs, product=, resolution=, vertical_crs=)  # bez sieci, jak dzis
  -> bbox_source_2180 (zapas WARP_MARGIN_PX dla warpa; 2180: bez zapasu)
run_pl_wcs_cutout(cutout, provider=, parent_request=, today=)
  1. maska ladu PL dla bbox_source_2180 (PRG, sekcja 6)       -> DownloadError = brak wycinka
  2. provider._download_wcs(bbox_source_2180, tmp_2180, height format)  # wyrownanie NA ZEWNATRZ do siatki arkuszy 1 m (3.2) + kawalki
  3. maska -> nodata -9999 (piksel poza A00\(W02+W03)), float32
  4. EPSG:2180: plik z kroku 2 = wynik (bbox_2180 rozszerzony do siatki k+0,5)
     inne: warp_to_grid(PinnedTransform.gdal_operation()) jak dzis
  5. zapis atomowy (tmp + os.replace) pod nazwa z data (4.4), sidecar (4.5)
```

- Selekcja arkuszy, `DownloadManager`, R5, `GridMismatchError`,
  `off_grid_sheets`, `unverified_sheets`, kontrola miejsca dla arkuszy —
  nie dotycza toru WCS (jedna siatka, jedno zrodlo).
- Kontrola miejsca: wynik float32 + plik roboczy 2180 (`estimated_bytes`
  x 2 + kawalki) — `ValidationError` przed siecia, gdy dysku na pewno
  zabraknie (jak dzis dla arkuszy).
- `--geometry`: `bbox` = obwiednia geometrii (jak dzis), bez maskowania
  do obiektow.

### 4.2 Biblioteka (addytywnie, W-U6)

- `prepare_pl_cutout(..., product: str = "nmt")`; `PlCutout.product: str =
  "nmt"` (nowe pole z wartoscia domyslna na koncu). Tor WCS przyjmuje
  tylko `resolution="1m"` (W-U10); `"5m"` = `ValidationError`.
- Nowa publiczna `run_pl_wcs_cutout(cutout, *, provider=None,
  parent_request=None, today: date | None = None) -> PlCutoutResult`
  (w `__all__`); `provider` musi pasowac do produktu i ukladu
  (`_require_matching_provider` rozszerzone o produkt).
- `download_pl_cutout(..., product: str = "nmt")`: tor WCS (`prepare` ->
  `run_pl_wcs_cutout`). Parametry arkuszowe zostaja w sygnaturze (0.7.2 nie
  lamie API): `geometry`, `layer`, `scale`, `max_workers`, `on_progress`,
  `cache`, `force` — bez wplywu; podanie wartosci innej niz domyslna daje
  `DeprecationWarning` z nazwa parametru i "usuniety w 0.8.0".
  `resolution="5m"` = `ValidationError` z podpowiedzia: arkusze 5 m przez
  `prepare_pl_cutout` -> `select_pl_cutout_sheets` -> `run_pl_cutout`.
- `PlCutoutResult`: nowe pole `masked_pixels: int = 0` (piksele poza maska
  ladu) i `zero_pixels: int = 0` (piksele 0,0 wewnatrz maski, 6.2); pola
  arkuszowe zostaja puste; `skipped` zawsze `False` w torze WCS.
- `run_pl_cutout(product="nmpt")` niemozliwe — `run_pl_cutout` z
  `cutout.product != "nmt"` = `ValidationError` (arkuszowy wycinek NMPT
  nigdy nie istnial).

### 4.3 CLI

- `--target-crs` z `--product nmpt` dozwolone; `orto`/`laz` dalej
  `Error:` (tresc bez "w 0.7.0 ... etap 2" dla nmpt).
- `--resolution 5m --target-crs` = `Error:`, kod 1, przed siecia:
  `wycinki --target-crs sa tylko 1 m (WCS GUGiK); arkusze 5 m: pomin
  --target-crs; wycinek: --resolution 1m` (tresc w planie).
- `_download_pl_cutout` wola tor WCS; znikaja: lista arkuszy, info GiB
  arkuszy, `Warning:` R5/E13/I-1 dla wycinka, `--workers` (nie dotyczy).
  Zostaje `Info:` o rozmiarze wyniku i liczbie kawalkow.
- `--force` z `--target-crs`: bez skutku dla wycinka PL (W-U8), bez
  komunikatu; czesc CZ pod `--country auto` zachowuje dzisiejsza obsluge
  `--force`.
- `--country auto --target-crs`: czesc PL torem WCS, CZ bez zmian (dwa
  wycinki, wspolny `extra.parent_request`, ADR-027).
- Kod wyjscia: blad WCS/PRG = 1 (pod `auto` przy sukcesie CZ: 0
  + `Warning:`, ADR-023 pkt 4-5, bez zmian).

### 4.4 Nazwa pliku i ponowne uruchomienie

- `<segment>/bbox/<wsp>_<RRRRMMDD>.tif`, `<wsp>` jak dzis
  (`bbox_cutout_path`, uklad wyniku), data = dzien pobrania (czas
  lokalny; `today=` w bibliotece dla testow).
- Kazde uruchomienie pobiera (W-U8). Ten sam dzien = ta sama nazwa: nowy
  wynik zastepuje poprzedni atomowo dopiero po udanej budowie (nieudany
  bieg zostawia poprzedni plik i sidecar). Inny dzien = nowy plik; starsze
  zostaja.
- Pliki wycinkow arkuszowych sprzed 0.7.2 (bez daty) zostaja nietkniete.
- Segment: NMT jak dzis (`nmt/pl_1992_1m_<vcrs>/bbox/`), NMPT
  `nmpt/pl_1992_1m_<vcrs>/bbox/` (z `resolve_subdir` deskryptora).

### 4.5 Sidecar wycinka WCS

- Deskryptor `pl.gugik.nmt_1m` albo `pl.gugik.nmpt`; `capability=
  "bbox_raster"`; `horizontal_crs=target`, `pinned_transforms` jak dzis;
  `nodata=-9999`; `request` = bbox w ukladzie wyniku (jak dzis).
- `extra.source = {"service": "WCS", "endpoint", "coverage", "format",
  "composition": "server"}` — kampanii/roku brak (kompozycja serwera,
  6.3); `extra.mask = {"source": "PRG", "layers": ["A00_Granice_panstwa",
  "-W02_Morze_terytorialne_RP", "-W03_Morskie_wody_wewnetrzne"],
  "masked_pixels": N}`; `extra.zero_pixels` (gdy > 0); `extra.all_nodata`
  (jak dzis, gdy wycinek w calosci poza maska); `extra.parent_request`.
- Rejestr: kanal WCS `pl.gugik.nmt_1m` z obydwoma ukladami
  (`_PL_VERTICAL_BOTH`) bez notatki o 404; `pl.gugik.nmpt` dostaje kanal
  WCS `bbox_raster` (oba uklady, notatka: wysokosci tylko AAIGrid).

### 4.6 Komunikaty

- Bez `Info:` o pikselach 0,0 na ladzie (W-U11: to w wiekszosci prawdziwe
  wysokosci, np. Zulawy — komunikat bylby szumem); liczba tylko
  w sidecarze (`extra.zero_pixels`) i w `PlCutoutResult.zero_pixels`.
- `Warning:` gdy `all_nodata` (obszar poza ladem PL), kod 0 (jak N2).

## 5. `download_bbox` NMT/NMPT (biblioteka)

### 5.1 Zachowanie

- `GugikProvider.download_bbox(format="GTiff")` dla EVRF2007 i
  `GugikNmptProvider.download_bbox(format="GTiff")`: wynik = GeoTIFF float32
  z wysokosciami (pobrany jako AAIGrid, przepisany do GTiff z EPSG:2180),
  na siatce arkuszy 1 m (3.2) i kawalkowany jak NMT KRON86 (ADR-034).
  `nodata` brak (jak dzis dla KRON86 — maska ladu tylko w wycinku; zmiana
  semantyki `download_bbox` poza zakresem).
- NMPT `download_bbox`: rozdzielczosc 1 m (`SCALEFACTOR=0.5`), zgodna
  z arkuszami NMPT 1 m i z deskryptorem `pl.gugik.nmpt` (dotad 0,5 m RGB).
- `format="PNG"/"JPEG"` bez zmian (podglad).
- CHANGELOG `### Naprawione`: NMPT `download_bbox` zwracal RGB uint8;
  `### Zmienione`: NMT EVRF2007 `download_bbox` dziala (dotad
  `ValidationError` o 404).

### 5.2 Odpowiedz multipart `image/x-aaigrid`

- Nowy modul `kartograf/transport/aaigrid.py` (bez wiedzy o uslugach):
  `extract_multipart_asc(path_in, path_asc)` — strumieniowo z pliku
  (odpowiedz pobierana `download_to` na dysk; ASC moze miec setki MB), boundary
  z naglowka `Content-Type`, czesc `Content-Type: image/x-aaigrid`;
  brak takiej czesci = `DownloadError` z poczatkiem tresci.
  `asc_to_gtiff(path_asc, path_tif, *, crs="EPSG:2180", expect: Chunk)` —
  sprawdza `ncols/nrows == chunk.width/height` i `xllcorner/yllcorner` ==
  naroznik kawalka (tolerancja `_GRID_TOL_PX`), zapisuje float32 z CRS
  wymuszonym (`.prj` ESRI ignorowany, jak `assign_crs` arkuszy), bez nodata.
- `download_to` dostaje `Content-Type` odpowiedzi (dzis go nie zwraca)
  — szczegol w planie (np. walidator tresci wolany z naglowkami).
- `GugikWcsMixin._download_wcs`: `fetch_one` dla AAIGrid = pobranie do
  `<part>.mime` -> `extract_multipart_asc` -> `asc_to_gtiff` -> usuniecie
  plikow posrednich; reszta (`plan_chunks`, `fetch_chunks`) bez zmian.

## 6. Maska ladu PL (W-U5)

### 6.1 Zrodlo i budowa

- `providers/pl/prg.py`: `land_mask_geometries(session, timeout) ->
  LandMask` — trzy zapytania WFS GetFeature (`A00_Granice_panstwa`,
  `W02_Morze_terytorialne_RP`, `W03_Morskie_wody_wewnetrzne`), parsowanie
  GML 3.2 (`Polygon`/`MultiSurface`, `posList` w kolejnosci osi (N,E)
  dla `urn:ogc:def:crs:EPSG::2180` -> (E,N)) do slownikow GeoJSON; bez
  nowej zaleznosci (bez shapely). Walidacja jak `teryts_for_area`:
  `FeatureCollection`, `numberReturned` == liczba obiektow; `A00` >= 1
  obiekt, inaczej `DownloadError`.
- `W02`/`W03` pytane z `BBOX` obszaru (poza wybrzezem 0 obiektow, 1 kB —
  raport pkt 6) — 0 obiektow to poprawna odpowiedz (brak morza
  w obszarze); `A00` bez `BBOX` (serwer i tak zwraca caly poligon).
- Rasteryzacja na siatce pliku 2180 (`rasterio.features.rasterize`):
  A00 = 1, potem W02 i W03 = 0; kryterium srodka piksela
  (`all_touched=False`); piksel 0 -> -9999.
- Pobranie maski przed WCS (A00 2 MB, ok. 2 s; W02/W03 przy wybrzezu do
  1,2 MB) — awaria PRG nie marnuje dlugiego pobrania. Bez cache w 0.7.2
  (jedna maska na bieg; cache — gdy pomiar pokaze potrzebe).
- Timeout: `GugikProvider.DEFAULT_TIMEOUT`, ponowienia `MAX_RETRIES`.

### 6.2 Czego maska nie rozwiazuje (swiadomie)

- 0,0 wewnatrz ladu PL zostaje danymi (W-U11): prawdziwe 0 m (Zulawy,
  brzeg, lustro wod przybrzeznych). W `M-33-57-C-b-4-2` 0,0 w WCS lezy za
  granica (lot 2025 przyciety do granicy, raport 2026-10-11 pkt 4) —
  lapie je maska. Terespol (raport 2026-10-10 pkt 8, arkusz graniczny)
  nie byl sprawdzony wzgledem `A00`; jesli tam sa dziury wewnatrz PL,
  zostaja jako 0,0. Slad: `extra.zero_pixels`.
- Granica PRG przecina piksele rzek granicznych — piksel ze srodkiem za
  granica = nodata, choc WCS moze tam miec dane.
- Lustro W03 (Zatoka Gdanska, zalewy) staje sie nodata.

### 6.3 Kompozycja lotow

Wycinek WCS nie jest odpowiednikiem `--campaigns newest` ADR-028: WCS
pokazuje najnowszy lot obszaru bez doklejania starszych (pas lotu 2023
za granica w `M-33-57-C-b-4-2`), a w Zulawach ma inny lot niz arkusze
"2017 i starsze" (raport 2026-10-10 pkt 8); Kartograf na arkuszach
wybiera najnowszy lot DOKLADNIE 1 m (pomija loty 0,5 m), WCS pokazuje lot
0,5 m zdecymowany do 1 m (raport 2026-10-11 pkt 3). ADR-035 i USAGE
opisuja to wprost; sidecar `extra.source.composition = "server"`.
Uzytkownik potrzebujacy lotu ADR-028 pobiera arkusze (bez `--target-crs`)
albo API arkuszowe.

## 7. Dokumentacja i decyzje

- **ADR-035** (CRLF): wycinek PL z WCS; zastepuje ADR-027 w czesci
  "zrodlo = arkusze" dla CLI i `download_pl_cutout`; status ADR-027:
  "czesciowo zastapiona przez ADR-035 (zrodlo wycinka); API arkuszowe do
  0.8.0". Opcje: arkusze (dzis), WCS bez maski, WCS + 0,0 jako nodata,
  WCS + maska PRG (przyjete). Siatka arkuszy 1 m (W-U9), tylko 1 m
  (W-U10), 0,0 na ladzie zostaje (W-U11); fakty z obu raportow WCS.
- ARCHITECTURE 4.3 (przepisany), 4.2 (`download_bbox` NMPT/EVRF2007,
  AAIGrid), 3.1 (rejestr), 3.2 (pola sidecara), 2 (`transport/aaigrid.py`);
  USAGE (wycinki, data w nazwie, kompozycja serwera, maska, NMPT);
  SCOPE 2 (ograniczenia: 1 m, bez roku, kompozycja serwera); PRD 3.11;
  `--help` `--target-crs`; CHANGELOG `[0.7.2]` (`Dodane`: NMPT
  `--target-crs`, `run_pl_wcs_cutout`, `product=`; `Zmienione`: zrodlo
  wycinka, nazwa z data, brak skip, 5 m `Error:`, `DeprecationWarning`
  parametrow arkuszowych — kazdy z "Co zrobic"; `Naprawione`: NMPT
  `download_bbox`, wpis EVRF2007).
- PROGRESS: backlog "Do 0.8.0" — usuniecie API arkuszowego wycinka
  i parametrow arkuszowych `mosaic_and_crop`, parametrow bez wplywu
  `download_pl_cutout`.

## 8. Testy (offline)

- Fixtury z SUROWYCH odpowiedzi (nagranie w implementacji, male okna):
  multipart AAIGrid NMT EVRF2007 i NMPT (`SCALEFACTOR=0.5`), odpowiedz
  `M-33-57-C-b-4-2` przy granicy; GML PRG: `A00` w calosci (2 MB, serwer
  nie przycina — raport pkt 6), `W02`/`W03` z `BBOX` okna przybrzeznego
  i pusta odpowiedz dla okna w glebi ladu.
- Przypadki: (1) multipart bez czesci ASC / ASC o zlym rozmiarze albo
  narozniku = `DownloadError`, wynik nie powstaje; (2) kawalki AAIGrid
  skladaja sie bit w bit z jednym zapytaniem (NMT i NMPT ze
  `SCALEFACTOR`); (2a) zakres poza siatka arkuszy rozszerzony na
  zewnatrz do `k + 0,5`, naroznik pliku na siatce; (3) maska:
  piksel morza W02, zalewu W03, za granica = -9999, ladu = wartosc
  serwera, 0,0 na ladzie zostaje i liczy sie w `zero_pixels`; (4) awaria
  PRG przed WCS = brak zapytan WCS i brak pliku; (5) ten sam dzien —
  nieudany bieg zostawia poprzedni plik; (6) CLI: 5 m + `--target-crs`,
  `nmpt --target-crs`, `orto --target-crs`; (7) `download_pl_cutout`
  `DeprecationWarning` dla parametru arkuszowego, `resolution="5m"`
  `ValidationError`; (8) sidecar: `capability`, `extra.source`,
  `extra.mask`; (9) NMPT `download_bbox` = 1 pasmo float32.
- Testy toru arkuszowego (`tests/test_pl_cutout.py`) zostaja dla API
  arkuszowego; testy CLI wycinka przechodza na tor WCS.

## 9. Pomiary

Wykonane 2026-10-11 (`docs/research/2026-10-11-wcs-cutouts/raport.md`):
siatki arkuszy 1 m i 0,5 m, WCS vs arkusze bit w bit (NMT/NMPT,
KRON86/EVRF2007), NMPT `SCALEFACTOR`, ASC (rozmiar, czas, pierwszy bajt,
zawieszenia), PRG (`BBOX`, punkty kontrolne wybrzeza), `M-33-57-C-b-4-2`
wzgledem granicy.

Do sprawdzenia w implementacji (nie zmieniaja projektu):
- linia brzegu `A00 - W02 - W03` wzgledem pikseli NMT (Gdynia, Hel,
  Mierzeja Wislana) — przekroje mialy rozdzielczosc 300-500 m;
- kawalki NMPT z `SCALEFACTOR=0.5` bit w bit z jednym zapytaniem;
- test na zywo wycinka (NMT EVRF2007, NMT KRON86, NMPT) z porownaniem
  z arkuszami 1 m tego samego lotu — raport wydania.

## 10. Otwarte

Brak.
