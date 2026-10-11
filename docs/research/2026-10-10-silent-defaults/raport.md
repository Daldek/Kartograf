# Weryfikacja na zywo: ciche wartosci domyslne (d), ADR-034

**Data:** 2026-10-10
**Galaz:** `feat/silent-defaults` (Task 1-6 planu
`docs/superpowers/plans/2026-10-10-silent-defaults.md`)
**Srodowisko:** `.venv/bin/kartograf` i jednorazowe skrypty z `.venv` z korzenia
repo; wyniki w katalogu danych wskazanym przez uzytkownika (ponizej `<out>`,
sciezka nie jest zapisywana w repo). Plik GPKG testu d2 na dysku lokalnym poza
repo: SQLite na udziale SMB konczy sie `database is locked` przy tworzeniu
pliku (ograniczenie udzialu, nie Kartografa).

## Wyniki

| # | Scenariusz | Oczekiwane | Wynik |
|---|---|---|---|
| 1 | `DownloadManager(vertical_crs="KRON86").download_bbox(480000,450000,486000,456000)` | wyrownanie do `k + 0,5`, kawalki, wynik = jedno zapytanie WCS | 6001 x 6001 px, zasieg `479999.5..486000.5` x `449999.5..456000.5`; 4 kawalki (2 x 2, 16 Mpx); 135 s; jedno zapytanie tego samego bboxa: 120 s; **`np.array_equal` = True**, transformy rowne; sidecar `request.bbox` = zadanie |
| 1b | powtorka 1 po poprawce kafelkowania wyniku | jw., bez ostrzezenia GDAL | dwa kawalki zerwane (`RemoteDisconnected`), ponowione po 2 s — ponowienie per kawalek dziala; wynik `tiled=True`, bit w bit z jednym zapytaniem; bez `BLOCKXSIZE can only be used with TILED=YES` |
| 2 | wynik WCS vs arkusze OpenData KRON86 1 m | bit w bit | pokryte pomiarem `docs/research/2026-10-10-wcs-limits/raport.md` pkt 4 i 8 (te same siatki i obszar co krok 1); kawalkowanie nie zmienia tresci (krok 1) |
| 3 | CUZK `download --bbox 17.90,49.70,18.04,49.79 --bbox-crs EPSG:4326 --country cz` na `develop` (przed Task 2) i na galezi | identyczny wynik | 5473 x 5437 px (29,8 Mpx -> kawalki 4 Mpx); ta sama nazwa pliku, transform, CRS, nodata -9999; **piksele identyczne** |
| 4 | `download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326` (auto) | `Info:` d1 | `Info: --country auto bez --vertical-crs: czesc PL w EVRF2007, czesc CZ w Bpv (rozne uklady wysokosci, roznica ok. 0,11-0,15 m); jeden uklad dla obu: --vertical-crs EVRF2007`; kod 0 |
| 4b | jw. z `--vertical-crs EVRF2007` | bez `Info:` | brak komunikatow `Info:`/`Warning:`; kod 0 |
| 5 | `download --geometry two_layers.gpkg --country pl --vertical-crs KRON86` (warstwy `zlewnia`, `punkty`) | jedno `Info:` d2, arkusz z pierwszej warstwy | jedno `Info:` (po poprawce odmiany: `two_layers.gpkg: liczba warstw 2, uzyto pierwszej 'zlewnia' (pozostale: punkty); inna warstwa: --layer NAZWA`); pobrany `M-34-2-A-b-4-3` (obszar `zlewnia`); kod 0 |
| 5b | jw. z `--layer punkty` | bez `Info:`, arkusz drugiej warstwy | brak `Info:`; pobrany `M-34-51-A-c-1-1` (obszar `punkty`); kod 0 |

## Poprawki wynikajace z weryfikacji i review

- Krok 1: wynik z kawalkow paskowych (GeoTIFF WCS: `blockxsize` = szerokosc,
  bez `tiled`) dawal ostrzezenie GDAL przy zapisie mozaiki; `fetch_chunks`
  zapisuje taki wynik w kafelkach 256 x 256 (kawalki kafelkowane CUZK bez
  zmian) — commit `fix(transport): ...`.
- Krok 5: "ma 2 warstw" -> "liczba warstw 2" (odmiana) — commit
  `fix(cli): odmiana ...`.
- Review galezi (reviewer, bez blokerow): `download --product laz --geometry`
  omijal `Info:` d2 (surowy `WARNING` biblioteki) — poprawione; testy
  odrzucenia `ows:ExceptionReport` dla NMPT i orto; docstringi `layer`
  funkcji geometrii — commit `fix(cli): Info o warstwie GPKG takze dla LAZ ...`.
