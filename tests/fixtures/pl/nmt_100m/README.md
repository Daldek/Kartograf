# Prawdziwe odpowiedzi ATOM NMT 100 m GUGiK (plan E, E1; 2026-10-16)

Nagrane 2026-10-16 przez `requests` (jednorazowy skrypt poza repo; surowe
odpowiedzi i pelny plik w `<katalog-danych>`). Cialo kazdej odpowiedzi bez
edycji; obok `<plik>.headers.json` z kodem HTTP i `Content-Type` (konwencja
`tests/conftest.py::recorded_response`).

| Plik | Zapytanie | Wynik |
|---|---|---|
| `service_feed.xml` | `https://mapy.geoportal.gov.pl/wss/service/ATOM/httpauth/atom/GUGIK_NMT100` | feed uslugi: 16 wpisow, `<id>` = adres feedu zbioru z `spatial_dataset_identifier_code=NMT100_<TERYT woj.>`; linki `rel="alternate"` (feed zbioru) sa `http://` |
| `dataset_12.xml`, `dataset_24.xml` | `https://...GUGIK_NMT100?spatial_dataset_identifier_code=NMT100_12&spatial_dataset_identifier_namespace=PL.PZGiK.205` (i `_24`) | feed zbioru: jeden wpis, link `application/zip` z `length` (malopolskie 7 619 580 B, slaskie 5 706 284 B), `<updated>` 2019-05-14T00:00:00Z, kategoria EPSG:2180 |

`files.json`: plik wojewodztwa 12 - adres z feedu (`http://`) i ten sam adres
przez `https://` (ten byl pytany), naglowki `HEAD` (`Content-Length`
7 619 580, `application/zip`; bez `ETag` i `Last-Modified`), lista czlonow
ZIP (jeden `malopolskie.txt`, 37 949 687 B) i poczatek tego czlonu (XYZ
z BOM, wiersze CRLF). Testy skladaja z niego maly ZIP - pelny plik nie
trafia do repozytorium.

Fakty z nagrania: feed uslugi i feed zbioru odpowiadaja 200 przez `https`
(0,1-0,4 s), plik tez (7,7 s). Ani feed, ani rekord CSW nie podaja ukladu
wysokosci (decyzja P1 uzytkownika: uklad nieznany). Czlon ZIP ma date
2025-09-25, wpis feedu - 2019-05-14.

Testy: `tests/test_nmt_100m.py`, `tests/test_atom.py`.
