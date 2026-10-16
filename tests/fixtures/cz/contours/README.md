# Prawdziwe odpowiedzi plikow warstwic ZABAGED CUZK (plan E, E1; 2026-10-16)

Nagrane 2026-10-16 przez `requests` (jednorazowy skrypt poza repo; pelne
pliki w `<katalog-danych>`).

Pliki arkuszy SM5: SHP `https://openzu.cuzk.gov.cz/opendata/ZABAGED-vyskopis/epsg-5514/<SM5>.zip`,
DGN `https://openzu.cuzk.gov.cz/opendata/ZABAGED-vyskopis-DGN/epsg-5514/<SM5>.zip`.

`files.json`: naglowki `HEAD` arkusza `CTES96` w obu formatach (`ETag`,
`Last-Modified`, `Content-Length`: SHP 1 580 278 B, DGN 1 429 918 B,
`application/x-zip-compressed`) i lista czlonow ZIP:

- SHP: 8 plikow `CTES96_Vrstevnice.{cpg,dbf,prj,sbn,sbx,shp,shp.xml,shx}`;
- DGN: 3 pliki `CTES96_Vrstevnice.dgn`, `.dgn.xml`, `.prj`.

Nieistniejacy arkusz (`XXXX99.zip`) odpowiada 404 `text/html`. Indeks arkuszy
SM5 (`KladyMapovychListu`, warstwa 24) testy biora z fixtur planu B
(`tests/fixtures/cuzk/klady_sm5_*.json`).

Testy: `tests/test_cz_contours.py`.
