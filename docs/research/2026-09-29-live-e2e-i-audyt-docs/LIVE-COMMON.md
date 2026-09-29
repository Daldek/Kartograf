# Wspolne zasady testow na zywych danych (Kartograf, 2026-09-29)

**Kontekst.** Galaz `develop`, HEAD 6985765 — stan po fali naprawczej "review max": wycinek PL `--target-crs` jako API biblioteki (`kartograf.download.cutout`: `download_pl_cutout`, kroki `prepare_pl_cutout` -> `select_pl_cutout_sheets` -> `run_pl_cutout`); R5: arkusz, dla ktorego GUGiK nie ma danych (`NoCoverageError`) = nodata + `Warning:` na stderr + `extra.missing_sheets` w sidecarze, kazda inna porazka pobrania = kod 1; wycinek EPSG:2180 na siatce pikseli arkuszy (wartosci 1:1); arkusze w mozaice przez VRT (EPSG:2180, Float32); arkusz GUGiK we wspolrzednych PL-2000 = blad z opisem; straz: odpowiedz 2xx skorowidza z raportem wyjatku OGC = blad warstwy; `LazTile.uklad`; szablony segmentow `data/` z rejestru. Testy repo sa OFFLINE — **po tej fali nikt nie pobieral z ZYWYCH uslug GUGiK/CUZK**. Uzytkownik pyta, czy pobieranie dziala na realnych danych: w centrum kraju, w pasie morskim i na pograniczach (PL-CZ, PL-DE — danych niemieckich NIE obslugujemy — i inne).

**Dokumenty referencyjne** (czytaj tylko potrzebne fragmenty): `CLAUDE.md` (sekcje "Uklad data/", "Ograniczenia": `--country auto`, `--target-crs` dla PL, CZ), `docs/ARCHITECTURE.md` (sekcja 3: uklad `data/`, sidecar; 4.3: wycinek PL), `docs/PROGRESS.md` ("Nastepne kroki" pkt 12 — checklista live (a)-(j)). Prostokaty krajow (`sources/registry.py`): PL 14,07-24,20°E / 49,00-54,90°N; CZ 12,09-18,86°E / 48,55-51,06°N (prostokat, nie wielokat granicy).

## Srodowisko
- Repo `/home/claude-agent/workspace/Kartograf` jest dla Ciebie **TYLKO DO ODCZYTU**: zadnych zmian w kodzie, testach, dokumentacji; zadnych commitow; `git status` repo ma zostac czysty.
- CLI: `/home/claude-agent/workspace/Kartograf/.venv/bin/kartograf`; Python: `/home/claude-agent/workspace/Kartograf/.venv/bin/python` (`import kartograf` dziala).
- Twoj katalog roboczy: `/home/claude-agent/workspace/Kartograf/e2e-data/2026-09-29-live/<ID>/` (gitignored; utworz). **KAZDE polecenie uruchamiaj z tego katalogu** (`cd`), bo cache metadanych `.kartograf_cache.db` powstaje w biezacym katalogu — izolacja od innych agentow dzialajacych rownolegle. Dane: `-o ./data`. Skrypty pomocnicze tez tam.
- `/tmp` to tmpfs (RAM) — nie zapisuj tam rastrow.
- Siec dziala (skorowidze WMS GUGiK i ArcGIS REST CUZK odpowiadaja).

## Kultura wobec uslug publicznych
- Male obszary: od kilku do kilkudziesieciu arkuszy. Testy obszarowe glownie 5 m (~1,3 MB/arkusz); 1 m tylko tam, gdzie potrzebne (arkusz 1 m ~30-40 MB).
- `--workers 2` (nie wiecej). Bez petli odpytujacych endpointy. Lacznie <= ~3 GB pobran na agenta.
- Rownolegle pracuje kilku agentow na tych samych uslugach — przy 5xx/timeoutach odczekaj i ponow raz; zapisz to w raporcie (to tez wynik).

## Metoda
1. Zanim uznasz cos za blad: sprawdz dostepnosc danych na WMS. Pokrycie 1 m i 5 m sie NIE pokrywa (np. N-34-130-D-d-2 Bialystok: 1 m jest, 5 m nie; N-34-141-A-a-1 Warszawa: 1 m EVRF2007 nie ma, 5 m jest; M-34-76-A-a-1 Krakow: oba).
2. Sprawdzaj TRESC, nie tylko kod wyjscia: rasterio (CRS, bounds wobec zadania, piksel, faza siatki, udzial i polozenie nodata), sidecar `<plik>.meta.json` (`horizontal_crs`, `vertical_crs`, `transform`, `request`, `extra.missing_sheets`, `extra.parent_request`), drzewo `data/` (segmenty wg CLAUDE.md "Uklad data/").
3. Wycinek EPSG:2180: wartosci 1:1 z arkuszy (srodek piksela wycinka -> arkusz, ktory go zawiera). EPSG:5514/3045: porownanie z niezaleznym warpem albo co najmniej punktowo (transformacja punktu + odczyt z arkusza).
4. Zapisuj: dokladne polecenia, kod wyjscia, stderr (linie `Info:`/`Warning:`/`Error:`), czas, liczbe arkuszy, rozmiary.
5. Znaleziony blad: minimalna reprodukcja (polecenie, wynik, oczekiwane) + hipoteza file:line. **NIE naprawiaj.**
6. Oceniaj tez z perspektywy uzytkownika: czy komunikaty i wynik sa zrozumiale; czego brakuje w dokumentacji (fakty zachowania, ktore warto opisac).

## Raport
- Pelny raport: `/home/claude-agent/workspace/Kartograf/.superpowers/sdd/2026-09-29-live-e2e-i-docs/<ID>-report.md`. Sekcje: Zakres (obszary z bboxami/godlami i uzasadnieniem wyboru), Wyniki per scenariusz (PASS / FAIL / UWAGA + dowod), Bledy (reprodukcja), Zachowanie do udokumentowania, Odpowiedzi na pozycje checklisty, Surowe artefakty (sciezki).
- Odpowiedz kontrolerowi krotko (<= 15 linii): status, liczba scenariuszy PASS/FAIL/UWAGA, najwazniejsze bledy (jedno zdanie kazdy), sciezka raportu.
- Nie uruchamiaj subagentow.
