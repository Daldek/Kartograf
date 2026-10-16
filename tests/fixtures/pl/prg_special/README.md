# Prawdziwe odpowiedzi PRG - granice specjalne (plan E, E3; 2026-10-16)

Nagrane 2026-10-16 przez `requests` (jednorazowy skrypt poza repo; surowe
odpowiedzi i pelne pliki krajowe w `<katalog-danych>`). Usluga OGC API
Features `https://ogcapi.geoportal.gov.pl/res/ims/maps/PRG/apiFeatures`
(wyjscie tylko CRS84). `<plik>.headers.json`: kod HTTP i `Content-Type`
(konwencja `tests/conftest.py::recorded_response`).

| Plik | Zapytanie | Wynik |
|---|---|---|
| `collections.json` | `/collections?f=json`, przyciete do `id` i `crs` kolekcji | 51 kolekcji, kazda tylko `http://www.opengis.net/def/crs/OGC/1.3/CRS84`: 6 `Granica*` administracyjnych (produkt `admin`, plan C), `GranicaRejonuStatystycznego`, `GranicaObwoduSpisowego` i 43 rodzaje granic specjalnych (sady, prokuratury, policja, PSP, Straz Graniczna, obrona cywilna, skarbowosc, archiwa, Lasy Panstwowe, Wody Polskie, obszary morskie) |
| `sad_rejonowy.json` | `/collections/SadRejonowy/items?f=json&bbox=19.93,50.055,19.945,50.065&limit=10000` (Krakow) | jeden obiekt `MultiPolygon` "Sad Rejonowy dla Krakowa-Srodmiescia w Krakowie" (`id`, `identyfikatorIIP`, `powierzchnia`, `regon`, ...) |
| `komenda_stoleczna_empty.json` | `/collections/KomendaStolecznaPolicji/items`, ten sam obszar | `numberMatched` 0, `features: []` - odpowiedz kolekcji bez obiektow w obszarze |

`packages.json`: pliki krajowe `https://opendata.geoportal.gov.pl/prg/granice/00_granice_specjalne_{shp,xml}.zip`
- naglowki `HEAD` (`application/octet-stream`, bez `ETag`/`Last-Modified`;
SHP 734 171 465 B, GML 757 744 521 B) i listy czlonow ZIP z pelnych plikow:
SHP 183 pliki (45 warstw `K01`...`W12`, m.in.
`R02_Granice_obwodow_spisowych`), GML 45 plikow `.gml` tych samych warstw.

Pomiar czasu `items` dla tego obszaru (2026-10-16): 43 kolekcje 0,4-11 s
(dwie z nich raz zerwaly polaczenie po ok. 260 s, powtorka 4 s),
`GranicaRejonuStatystycznego` 36-38 s, `GranicaObwoduSpisowego` 158-184 s
(w Warszawie, obszar 0,01 x 0,01 st., ponad 400 s). Dlatego obwody spisowe
nie sa czescia wyniku obszaru (ADR-043 errata 1) - sa w plikach krajowych.

Testy: `tests/test_prg_special.py`, `tests/test_parity_e3.py`.
