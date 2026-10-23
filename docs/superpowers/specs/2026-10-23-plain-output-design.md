# Spec: Zwykly zapis domyslnie, magazyn wersjonowany na zadanie (0.8.0)

**Data:** 2026-10-23
**Status:** projekt do przegladu uzytkownika (decyzje D1-D5 od uzytkownika
2026-10-23, odpowiedzi na p. 7 z 2026-10-23: D9-D11; otwarte: p. 7.2). Po
akceptacji: ADR-048, plan i implementacja.
**Wersja docelowa:** 0.8.0 (wydanie nietagowane; zmiana lamiaca zgodnosc
znaczenia `-o`/`--output` wchodzi przed tagiem)
**Warunek wstepny:** magazyn wersjonowany (ADR-036), katalog komend
(ADR-046), spojnosc CLI i API (ADR-037)
**Zmienia:** ADR-036 (magazyn przestaje byc jedynym celem zapisu komend
danych), ADR-044 D7 i ARCHITECTURE 3.3 (uklad `data/` tylko w trybie
magazynu), ADR-040 (projekty tylko z magazynem)
**Odrzucony wariant:** przeniesienie magazynu do Archiwisty (rozmowa
2026-10-23): rozwiazuje ten sam problem wiekszym kosztem i zrywa zasade
"kazde dzialanie Archiwisty = komenda `kartograf ...`".

---

## 1. Problem

Od 0.8.0 kazda komenda danych zapisuje wylacznie do magazynu
wersjonowanego (ADR-036): `-o` oznacza korzen magazynu, a jeden arkusz NMT
konczy jako

```
<katalog>/nmt/pl_1992_1m_evrf2007/versions/N-34/130/D/d/2/4/2022-05-10_83233_3fa91c2e/N-34-130-D-d-2-4.asc
<katalog>/nmt/pl_1992_1m_evrf2007/versions/N-34/130/D/d/2/4/2022-05-10_83233_3fa91c2e/N-34-130-D-d-2-4.asc.json
<katalog>/nmt/pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc   (dowiazanie twarde)
<katalog>/nmt/pl_1992_1m_evrf2007/versions/.incoming/...
```

Nie ma sposobu, zeby pobrac jeden plik i zapisac go w zwyklym katalogu.
Magazyn wymaga tez systemu plikow z dowiazaniami twardymi (FAT, exFAT,
czesc NAS i klient SMB w macOS odpadaja), wiec na takim dysku nie da sie
pobrac nic. Uzytkownicy biblioteki (Hydrolog: `download_soil`,
`calculate_hsg`) potrzebuja zwyklych plikow.

## 2. Cel

```bash
# Domyslnie: sam plik w podanym katalogu
kartograf elevation download --sheet N-34-130-D-d-2-4 -o ~/dane/nmt
#   -> ~/dane/nmt/N-34-130-D-d-2-4.asc

# Jawnie: magazyn wersjonowany (dzisiejsze zachowanie, bez zmian)
kartograf elevation download --sheet N-34-130-D-d-2-4 --store ~/magazyn
```

Biblioteka: `download_dem(..., output="~/dane/nmt")` albo
`download_dem(..., store="~/magazyn")`.

## 3. Decyzje

**D1. Dwa wykluczajace sie cele zapisu (uzytkownik 2026-10-23).**
Kazda komenda danych przyjmuje dokladnie jeden z:
- `-o`/`--output <KATALOG>` - zwykly zapis (tryb domyslny, p. 4);
- `--store <KATALOG>` - magazyn wersjonowany, zachowanie 0.8.0 bez zmian
  (ADR-036): wersje, dowiazania, sidecary, plany, `.incoming/`.

Podanie obu albo zadnego = blad wejscia przed siecia (ADR-037). W API
parametr `output_dir` zastepuja `output` i `store` (argumenty tylko
nazwane, ADR-044 errata 1). Odrzucone: `-vo` (w typowym CLI to `-v -o`)
i bliźniacze komendy `download-versioned` (podwojenie katalogu komend).

**D2. `-o` to zawsze katalog (uzytkownik 2026-10-23).** Nigdy nazwa
pliku, takze gdy wynikiem jest jeden plik. Kazdy plik trafia bezposrednio
do tego katalogu (plasko, bez drzewa godla, segmentu i `versions/`) pod
swoja nazwa (D9).

**D3. Najpierw pelna lista, potem sprawdzenie, dopiero potem pobieranie
(uzytkownik 2026-10-23).** Kolejnosc:
1. Kartograf ustala dokladnie, co pobierze: liste plikow z nazwami
   (ten sam wybor rekordow, kampanii i kafli co w magazynie).
2. Sprawdza, czy ktorykolwiek z tych plikow juz istnieje w katalogu `-o`,
   oraz czy dwa pliki z listy nie maja tej samej nazwy.
3. Jesli tak - odmowa przed pierwszym bajtem pobrania, komunikat wymienia
   wszystkie kolidujace nazwy. Nic nie jest pobierane ani nadpisywane.
4. Dopiero potem pobieranie. Kazdy plik zapisywany jako `<nazwa>.part`
   i zamieniany na `<nazwa>` przez `os.replace` po pelnym pobraniu; plik
   `.part` po przerwaniu (blad, Ctrl-C) jest usuwany.

Brak flagi nadpisywania: zeby pobrac ponownie, uzytkownik usuwa plik albo
wskazuje inny katalog.

**D4. Bez metadanych poza magazynem (uzytkownik 2026-10-23).** Tryb `-o`
nie zapisuje sidecara `kartograf-meta/1`, dowiazan, `full_sheet/`,
`versions/` ani `.incoming/`, i nie wymaga dowiazan twardych. Wynik
komendy (`--json`, obiekt wyniku w API) nadal wymienia zapisane pliki
(sciezki), bo bez tego skrypt nie wie, co powstalo.

**D5. Zakres i wydanie (uzytkownik 2026-10-23).** Tylko Kartograf;
IMGWTools poza zakresem. Calosc w 0.8.0, przed tagiem.

**D6. Opcje tylko dla magazynu.** `--check-updates`, `--upgrade`,
`--force`, `--plan` (i `update=` w API) maja sens tylko z `--store`;
z `-o` = blad wejscia z podpowiedzia ("aktualizacje dzialaja w magazynie:
uzyj --store"). `--full-sheet` (drugie dowiazanie, ADR-033) - p. 7,
pytanie 2.

**D7. Projekty tylko z magazynem.** `project *` przypina wersje (ADR-040),
wiec przyjmuje wylacznie `--store` (dzisiejsze `-o` projektu zmienia nazwe
na `--store`); `project add` odrzuca komende danych z `-o`.

**D8. Katalog `-o` jest tworzony, jesli nie istnieje** (jak `mkdir -p`).

**D9. Nazwa pliku = ostatni element sciezki z magazynu (uzytkownik
2026-10-23, p. 7.1 wariant A).** Ta sama nazwa, ktora Kartograf nadaje
plikowi w ukladzie `data/` (`N-34-130-D-d-2-4.asc`, `1465.gpkg`,
`<coords>.tif`), znana przed pobraniem (wymog D3). Nazwa pliku na serwerze
zrodla nie jest uzywana.

**D10. Przerwane pobranie bez dodatkowej flagi (uzytkownik 2026-10-23,
p. 7.3).** Pliki pobrane w calosci zostaja; ponowne wywolanie z tym samym
`-o` odmawia (D3), a komunikat wymienia pliki do usuniecia. Bez
`--skip-existing` w 0.8.0.

**D11. HSG poza zakresem (uzytkownik 2026-10-23, p. 7.4).** `calculate_hsg`
/ `soil hsg` zostaja w 0.8.0 bez zmian (tylko magazyn, parametr `store`);
tryb `-o` dla HSG przy pozniejszej zmianie HSG.

## 4. Tryb `-o` w torach pobierania

| Tor | Nazwa pliku w `-o` (D9) |
|---|---|
| Arkusze PL NMT/NMPT/orto | `N-34-130-D-d-2-4.asc` (`.tif`) |
| Wycinki PL/CZ (`--cutout`, WCS, ImageServer) | `<coords>.tif` |
| Arkusze i kafle CZ | `302_5550.tif`, `CTES96.tif`, `CTES96.jpg` + pliki `.jgw` |
| LAZ PL/CZ | nazwa pliku kafla `.laz` |
| Kolekcje (paczki jednostek, obiekty obszaru, pliki krajowe) | `1465.gpkg`, `12.zip`, `<coords>.gpkg`, `cz.zip` |
| Land cover, SoilGrids | `1465.gpkg`, `<coords>.tif` |
| HSG | poza zakresem (D11) |

Wybor danych (rekord skorowidza, kampania, kafle, warianty, limit obszaru)
jest w obu trybach ten sam; roznica dotyczy wylacznie zapisu.

## 5. Zmiany w kodzie (szkic do planu)

1. `catalog/shared.py`: `OUTPUT_DIR` -> dwa parametry `OUTPUT` i `STORE`
   z regula wykluczenia; parser CLI, REST/MCP i dokumentacja komend
   z katalogu (ADR-046) przejmuja zmiane automatycznie.
2. Wspolna sciezka zapisu trybu `-o` (np. `download/plain.py`):
   lista docelowa -> sprawdzenie kolizji -> `.part` + `os.replace`.
   Tory pobierania (ok. 15 modulow, m.in. `download/manager.py`,
   `landcover/manager.py`, `download/collections.py`, `download/cz_*.py`;
   bez `hydrology/hsg.py`, D11) dostaja rozgalezienie: `store` -> obecne
   `commit_version` + `ensure_link`, `output` -> zapis zwykly.
3. Funkcje `download_*`/`download_soil`: `output`/`store` zamiast
   `output_dir` (`calculate_hsg`: tylko `store`, D11); `check_*` (plany aktualizacji) wymagaja `store`.
4. MCP: narzedzia odczytu magazynu bez zmian (ADR-045, ADR-046).
5. Testy: tryb `-o` na kazdym torze (nazwy, kolizje przed siecia,
   przerwanie bez `.part`), wykluczenie `-o`/`--store`, opcje magazynu
   z `-o`; istniejace testy magazynu przechodza na `store=`.

## 6. Skutki

- Archiwista (v0.3, pierwszy zapis) wywoluje komendy z `--store`;
  decyzje Archiwisty bez zmian, adnotacja w jej SPEC 12 przy KB-*.
- Hydrolog dostaje zwykle pliki z `download_soil(output=)`; HSG pozniej (D11).
- Hydrograf (przypiety do 0.7.0) - bez wplywu do aktualizacji zaleznosci.
- Dokumentacja: USAGE (przyklady zaczynaja od `-o`), ARCHITECTURE 1, 3.3,
  4.x, CHANGELOG 0.8.0 (zmiana lamiaca), llms.txt, README.

## 7. Pytania (odpowiedzi uzytkownika 2026-10-23)

1. Nazwa pliku: wariant A -> D9.
2. **Kilka plikow o tej samej nazwie w jednym wywolaniu** (`--all-campaigns`,
   `--full-sheet`, kilka rekordow arkusza): uzytkownik - kolizje beda
   nagminne, wiec zmiana logiki na **pobieranie najnowszego pelnego
   arkusza**. Do doprecyzowania (OTWARTE):
   - a) czy regula dotyczy tylko trybu `-o`, czy takze `--store`
     (dzis domyslnie: najnowszy rekord arkusza, takze niepelny, ADR-028;
     najnowszy pelny tylko jako drugie dowiazanie `--full-sheet`, ADR-033);
   - b) co, gdy arkusz nie ma zadnego pelnego rekordu (tylko czesciowe):
     najnowszy czesciowy z ostrzezeniem, czy pominiecie arkusza z bledem;
   - c) `--all-campaigns` i `--full-sheet` z `-o`: blad z podpowiedzia
     `--store` (propozycja), bo w `-o` zawsze jest jeden plik na arkusz.
3. Przerwane pobranie: bez `--skip-existing` -> D10.
4. HSG: poza zakresem -> D11.
