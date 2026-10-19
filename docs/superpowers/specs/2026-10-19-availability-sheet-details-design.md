# Spec: Szczegoly arkuszy i kampanii w raporcie dostepnosci - KD-1, KD-2 (0.8.0)

**Data:** 2026-10-19
**Status:** decyzja uzytkownika 2026-10-19: spec i plan pisze agent, przeglad
wlasny i wdrozenie w tej samej sesji; ksztalt pol zatwierdza uzytkownik przy
przegladzie diffu galezi
**Galaz:** `feat/availability-sheet-details` (z `develop`, `9393bb9f`)
**Wersja docelowa:** 0.8.0 (wydanie nietagowane; zmiana addytywna schematu
`kartograf-availability/1`, USAGE 9: w obrebie `/1` tylko nowe klucze)
**Warunek wstepny:** raport dostepnosci (ADR-041, plany A i B), dokumenty JSON
(ADR-046)
**Dokumenty zrodlowe:**
- Archiwista `docs/SPEC.md` 6.4 (etykiety pokrycia: "pelne", "pelne · N
  kampanie", "czesciowe · 58%") i 12.4 (KD-1, KD-2) - tylko odczyt
- Archiwista `mockup/tools/build_fixtures.py` (pola proponowane: `full_m2`,
  `sheet_records`, `campaigns_selected`) - tylko odczyt
- ADR-028 (kolejnosc rekordow arkusza), ADR-029 (wybor kafli LAZ), ADR-033
  (`--full-sheet`), ADR-041 (raport dostepnosci)

---

## 1. Problem

Archiwista (SPEC 6.4) wylicza etykiety pokrycia z `AvailabilityCombination`.
Brakuje mu trzech rzeczy, ktore Kartograf liczy wewnetrznie, ale nie oddaje:

1. **KD-2:** udzial ladu w ramach pelnych arkuszy ("czesciowe · 58%").
   `_measure` liczy `missing` (piksele `target` poza ramami rekordow `TAK`),
   ale raport oddaje tylko `complete = missing == 0` i `uncovered_m2`
   (gorna granica).
2. **KD-1a:** rekord, ktory pobierze Kartograf dla kazdego arkusza
   kombinacji (kampania, data lotu, pelny). `campaigns` liczy wszystkie
   rekordy, takze niepelne i te, ktorych pobranie nie wybierze, wiec
   `len(campaigns)` nie daje "N kampanii" etykiety.
3. **KD-1b:** kompletnosc kazdej kampanii z osobna ("pelne" = jedna kampania
   sama pokrywa lad pelnymi arkuszami).

## 2. Zakres

| ID | Co | Gdzie |
|---|---|---|
| KD-2 | `AvailabilityCombination.full_m2: float` | PL i CZ |
| KD-1a | `AvailabilityCombination.sheet_records: tuple[AvailabilityRecord, ...]` | PL (CZ: `()`) |
| KD-1b | `AvailabilityCombination.campaign_coverage: tuple[AvailabilityCampaign, ...]` | PL (CZ: `()`) |
| CLI | `elevation availability --details`: udzial pelnych arkuszy, kampanie z pokryciem, kampanie rekordow do pobrania | `cli/availability_cmd.py` |

Poza zakresem: KD-3 (obrazy PL), KD-4 (wydania produktow jednostkowych),
zmiana tabeli bez `--details`, zmiana `download_hint`, zmiana wyboru rekordow
w pobieraniu.

## 3. Decyzje

**D1. `full_m2` (KD-2).** PL: lad obszaru w ramach rekordow `TAK`
kombinacji, z tej samej siatki 1 m i tego samego `target` co `complete`:
udzial pokrytej czesci `target` przeniesiony na lad i zaokraglony w dol,
`full_m2 = land_px * (target_px - missing) // target_px` (`land_px`, gdy
`missing == 0`). Dla `bbox`/`geometry` `target_px == land_px`, wiec to
dokladnie `land_m2 - missing`; dla zadania `sheet` `target` nie ma pasa
`EDGE_TOLERANCE_M` przy ramie (`_inner`) i pas nie liczy sie ani jako
pokryty, ani jako brak. Skutki: `complete <=> full_m2 == land_m2` bez
wyjatkow, kombinacja samych rekordow `NIE` ma `full_m2 == 0`. LAZ: rekordy =
kafle `TAK`. CZ: czesc prostokata obszaru w ramach arkuszy z plikiem
(`sheets_full`), liczona jak `uncovered_m2` (`_frames_m2`, ta sama funkcja
dla obu pol). W CZ `complete` nie implikuje `full_m2 == land_m2`, gdy
obszar wychodzi poza arkusze indeksu (np. naroznik obszaru poza kaflami
TM33) - CZ nie ma maski ladu, a `complete` znaczy "kazdy arkusz indeksu ma
plik" (bez zmian).

Odrzucone: `target_px - missing` (dla zadania `sheet` kompletna kombinacja
mialaby `full_m2 < land_m2`); `land_px - missing` (pas ramy liczylby sie jako
pokryty: kombinacja samych rekordow `NIE` mialaby `full_m2 > 0`, CLI
pokazaloby `<1%` zamiast `0%`); udzial procentowy w raporcie (zaokraglenie
to decyzja prezentacji - robi je Archiwista i CLI).

**D2. `sheet_records` (KD-1a).** Rekordy indeksu, ktore pobiera polecenie
`download_hint` tej kombinacji, po arkuszu (alfabetycznie), w arkuszu od
najnowszego. Typ:

```python
@dataclass(frozen=True)
class AvailabilityRecord:
    sheet: str                 # godlo arkusza (LAZ: godlo kafla)
    campaign: str | None       # nr_zglosz
    acquisition_date: str | None   # akt_data (RRRR-MM-DD)
    published: str | None      # dt_pzgik
    full_sheet: bool | None    # czy_ark_wypelniony (nazwa jak w SkorowidzRecord, LazTile, sidecarze)
    url: str                   # plik rekordu (identyfikuje rekord jednoznacznie)
```

- NMT/NMPT: najnowszy rekord arkusza w kombinacji w kolejnosci ADR-028
  (`akt_data`, `dt_pzgik`, `url`; `select_sheet_record`) - plik sciezki
  standardowej; gdy ten rekord nie jest `TAK`, a arkusz ma rekord `TAK`
  (podpowiedz ma wtedy `--full-sheet`, ADR-033), takze najnowszy rekord
  `TAK` (plik `full_sheet/`). Ta sama regula co `_needs_full_sheet`.
- LAZ: kafle kombinacji, ktore zostawia `select_newest_cover` (ADR-029)
  na obszarze zadania - ta sama funkcja co pobieranie (kafel niepelny nie
  pokrywa, wiec obok niego zostaje kafel pelny tego samego arkusza).
  Ograniczenia: polecenie pobrania LAZ nie ma ukladu arkuszy, wiec `--year`
  wybiera najnowsze kafle obu ukladow naraz, a kombinacja ma jeden uklad;
  dla roku z kaflami PL-1992 i PL-2000 `sheet_records` moze sie roznic od
  tego, co polecenie zapisze (Krakow 2023: podpowiedz kombinacji PL-2000
  pobiera kafle PL-1992). Opisane w docstringu pola i USAGE (przeglad
  uzytkownika 2026-10-19). Rok, ktory nie pokrywa kafli obszaru, pobranie LAZ
  odrzuca juz dzis (konflikt zakresu lat, `year_range_error`) - wtedy
  `sheet_records` to kafle, ktore wybralaby selekcja.
- CZ: `()` (CUZK nie publikuje rekordow z kampaniami).

Archiwista liczy "N kampanii" z `sheet_records` (np. rozne `campaign`
rekordow `full_sheet`), bez kopii regul wyboru. Odrzucone: slownik arkusz ->
rekord (arkusz z `--full-sheet` ma dwa rekordy; tuple dataclass to konwencja
raportu); `campaigns_selected` z mockupu (wyliczalne z `sheet_records`).

**D3. `campaign_coverage` (KD-1b).** Jedna pozycja na kampanie z `campaigns`
(ta sama kolejnosc):

```python
@dataclass(frozen=True)
class AvailabilityCampaign:
    campaign: str
    complete: bool    # rekordy TAK tej kampanii same pokrywaja lad obszaru
    full_m2: float    # lad w ramach rekordow TAK tej kampanii (D1)
```

Liczone w tym samym przebiegu `_measure` (dodatkowy `rasterize` na kampanie
w pasie). Rekordy bez `nr_zglosz` nie tworza pozycji. Kompletnosc kampanii to
fakt o zrodle (wszystkie rekordy `TAK` kampanii w kombinacji), nie o tym, co
pobierze podpowiedz - to mowi `sheet_records`. CZ: `()`.

**D4. CLI `--details`.** Dla kombinacji PL dochodza linie:

```
    lad w ramach pelnych arkuszy: 98% (85,50 ha)        # tylko niekompletna
    kampanie: DFT.7201.002.2023 (98%), DFT.7201.028.2023 (0%)
    pobierane rekordy: 3 ark., kampanie: DFT.7201.002.2023 (3), DFT.7201.028.2023 (2)
```

Udzial: zaokraglony w dol do pelnego procentu, niezerowy ponizej 1% = `<1%`
(Archiwista SPEC 6.4) - niekompletna kombinacja nigdy nie pokazuje 100%.
`pobierane rekordy`: liczba arkuszy (LAZ: kafli) `sheet_records` i liczba
rekordow na kampanie (rekordy bez kampanii: `bez numeru`); kampania
kompletna sama: `(komplet)`. Tabela i stopka bez zmian.

**D5. JSON i API.** Nowe klucze `full_m2`, `sheet_records`,
`campaign_coverage` na koncu obiektu kombinacji (po `download_hint`; klucze
w kolejnosci pol dataclass); typy zagniezdzone `AvailabilityRecord`,
`AvailabilityCampaign` w kontrakcie kluczy (`tests/test_json_contract.py`).
Eksport z `kartograf` (`__all__`). Schemat pozostaje
`kartograf-availability/1`. Cache (`index_area_cache`) bez zmian: nowe pola
licza sie z tych samych rekordow.

## 4. Testy (sciezki konsumenta)

- `full_m2`: `complete <=> full_m2 == land_m2` i `0 <= full_m2 <= land_m2 -
  uncovered_m2` dla kazdej kombinacji Krakowa i Pomorza; Pomorze 2022 1 m
  (same arkusze pelne): `land_m2 - uncovered_m2`; Pomorze 2025 0.5 m (same
  niepelne): `0.0`; zadanie `sheet` (N-33-58-A-c-1-4): kompletne =
  `land_m2`, same niepelne = `0.0` (pas ramy); CZ: arkusz bez pliku = `0.0`,
  kafel TM33 z plikiem nie obejmuje naroznika obszaru (`complete`, a
  `full_m2 < area_m2`).
- `sheet_records` == rekordy, ktore planuje `check_data` z podpowiedzia
  kombinacji (URL-e pozycji planu): Krakow NMT 2025, Pomorze NMT 2023 5 m
  (`--full-sheet`, dwie kampanie), Krakow LAZ 2025 (63 kafle; podpowiedz
  niekompletnego roku LAZ Pomorza pobranie odrzuca - D2).
- `campaign_coverage`: Pomorze 2023 5 m - dwie kampanie, zadna sama
  kompletna; kampania pelnych rekordow ma `full_m2` kombinacji, kampania
  rekordow niepelnych `0.0`; w arkuszu rekordy od najnowszego, ostatni pelny.
- CLI `--details`: linie D4 (Pomorze 2022 1 m, 2023 5 m); formater udzialu:
  w dol (99,9999% = `99%`), `<1%`, `0%`, `-` bez ladu.
