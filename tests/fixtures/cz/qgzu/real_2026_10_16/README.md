# QGZU-2013 CUZK - prawdziwe odpowiedzi (plan E, E5; 2026-10-16)

Nagrane 2026-10-16 przez `requests` (plik ZIP pobrany w calosci do
`<katalog-danych>`). Feedy bez edycji, obok `.headers.json` (`url`,
`status`, `Content-Type`, `ETag`, `Last-Modified`).

| Plik | Zawartosc |
|---|---|
| `qgzu_service.xml` | `https://atom.cuzk.gov.cz/QGZU/QGZU.xml`: jeden wpis zbioru (`<updated>` 2021-02-22T16:59:17+02:00, kategoria EPSG:4258); link do feedu zbioru na hoscie `atom.cuzk.cz` |
| `qgzu_dataset.xml` | `https://atom.cuzk.cz/QGZU/datasetFeeds/CZ-00025712-CUZK_QGZU_KVAZIGEOID.xml`: jeden plik `https://openzu.cuzk.cz/opendata/QGZU/KVAZIGEOID.zip`, `length` 58 190 406 |
| `files.json` | naglowki `HEAD` pliku (`ETag`, `Last-Modified` 2021-06-30), SHA-256 `aacfba6b...dfa3` (ten sam co 2026-10-15) i lista 18 czlonow (`KvaziGeoid/` i 17 siatek TXT `z<n>_1D_N<lat>E<lon>.txt`) |
