# Poczatki prawdziwych archiwow NMT GUGiK (2026-10-15, plan A)

Zrodlo: pliki OpenData GUGiK
(`https://opendata.geoportal.gov.pl/NumDaneWys/NMT/<id>/<plik>`) wskazane
polem `url_do_pobrania` rekordow skorowidza WFS NMT KRON86
(`NumerycznyModelTerenuKRON86/WFS/Skorowidze`; te same rekordy sa w
`tests/fixtures/gugik_wfs/real_2026_10_15/sheet_nmt_kron86_<godlo>.xml`).
Pelne pliki pobrane 2026-10-15 w pomiarze planu A (poza repo, kopia
w `<katalog-danych>`).

Przyciecie: kazdy plik to PIERWSZE 512 bajtow oryginalu bez edycji
(`data[:512]`), reszta odcieta. Nazwa = nazwa pliku z URL z wstawka `.head`
przed rozszerzeniem (jak `tests/fixtures/gugik_asc/`).

| Plik | `format` rekordu | Godlo, warstwa | Oryginal | Poczatek pliku |
|---|---|---|---|---|
| `4543_360776_N-34-58-D-c-3.head.ttn` | `Intergraph TTN` | `N-34-58-D-c-3`, `SkorowidzNMT2000` | 2 769 279 B | `TTN\x04` i data zapisu (2004) |
| `4641_410597_M-34-10-B-a-1.head.grd` | `Intergraph GRD`, 5.00 m | `M-34-10-B-a-1`, `SkorowidzNMT2009` | 4 316 036 B | element IGDS typu 9: `08 09` |
| `4512_376571_N-33-103-B-b-4.head.dgn` | `Warstwice DGN`, 25.0 m | `N-33-103-B-b-4`, `SkorowidzNMT2004` | 2 977 792 B | DGN v7 (IGDS): `C8 09` |
| `4506_363954_M-33-24-B-b-1.head.dxf` | `Warstwice DXF`, 25.0 m | `M-33-24-B-b-1`, `SkorowidzNMT2004` | 2 882 646 B | `  0`, `SECTION`, `HEADER`, `$ACADVER` `AC1009` (CRLF) |

Archiwa ZIP (`.xyz.zip`, `.zip.zip`, `_asc.zip`, `_tin.zip`, `.zip`) nie maja
tu plikow: testy buduja w pamieci maly kompletny ZIP i jego obciety poczatek
(bez katalogu centralnego).

Testy: `tests/test_campaigns.py` (`verify_file_format`).
