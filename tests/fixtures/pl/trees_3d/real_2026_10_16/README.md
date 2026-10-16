# Modele drzew 3D GUGiK - prawdziwe odpowiedzi (plan E, E5; 2026-10-16)

Nagrane 2026-10-16 przez `requests` (jednorazowy skrypt poza repo; pelna
paczka 3063 w `<katalog-danych>`). Pliki:
`https://opendata.geoportal.gov.pl/InneDane/Drzewa3D/LOD1/2023/{woj}/{teryt}.zip`.

| Plik | Zawartosc |
|---|---|
| `files.json` | `trees_<teryt>`: URL i naglowki `HEAD` paczek 2261 (3 408 621 873 B), 3063 (324 674 789 B, z lista 40 czlonow `3063_<godlo 1:500>.gml`, CityGML LoD1, `srsName="EPSG:2180"` bez ukladu wysokosci), 1261, 0202 (3 464 194 350 B), 0208 (24 707 968 358 B); `trees_0224`, `lod2_2023_2261`, `lod1_2024_2261`: HTTP 404 |
| `prg_powiaty_0202_0224.xml` (+ `.headers.json`) | odpowiedz WFS PRG o powiaty obszaru E 334000-337000, N 310000-313000 (zapytanie `discover_teryts_for_bbox`): 0202 i 0224, bez edycji |

Fakty: `HEAD` paczki trwa 0,2-90 s (ok. 3,5 s na GB; 0208: 88 s); paczki
LoD2 i lat innych niz 2023 nie ma (404); nie kazdy powiat ma paczke (0224,
0221: 404).
