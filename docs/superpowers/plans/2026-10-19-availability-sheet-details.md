# Plan: Szczegoly arkuszy i kampanii w raporcie dostepnosci - KD-1, KD-2

**Spec:** `docs/superpowers/specs/2026-10-19-availability-sheet-details-design.md`
**Galaz:** `feat/availability-sheet-details` (z `develop`)
**Wykonawca:** jedna sesja, bez subagentow (zmiana w jednym module i jego
CLI; wspolny kontrakt pol)

## Zadania

**T1. Model (`kartograf/download/availability.py`).**
- `AvailabilityRecord`, `AvailabilityCampaign` (frozen dataclass, spec D2,
  D3); `AvailabilityCombination` + `full_m2`, `sheet_records`,
  `campaign_coverage` (na koncu, po `download_hint`); docstringi klas
  i modulu.
- Eksport w `kartograf/__init__.py` (`__all__`).

**T2. Pomiar (`_measure`).**
- Zwraca na grupe `missing`, `uncovered` i `missing` kazdej kampanii
  (rekordy `TAK` z `campaign`); jeden `rasterize` na kampanie w pasie.
- `_check_pl`: `full_m2 = land_px - missing`, kampanie: `land_px -
  missing_c`, `complete_c = missing_c == 0`.

**T3. Rekordy (`_combination`).**
- NMT/NMPT: `_selected_records(rows)` - najnowszy wg (`date`, `published`,
  `url`) i najnowszy `TAK`, gdy najnowszy nie jest `TAK` (ta sama regula
  co `_needs_full_sheet`, ktora korzysta z tej funkcji).
- LAZ: `select_newest_cover` na kaflach grupy (`_Entry` -> `LazTile`)
  i obszarze zadania (jeden wielokat LAZ).
- Kolejnosc: arkusz, potem od najnowszego.

**T4. CZ.** `_uncovered_m2` -> `_frames_m2(sheets, system_crs, area)`;
`uncovered_m2 = _frames_m2(missing)`, `full_m2 = _frames_m2(present)`;
`sheet_records = campaign_coverage = ()`.

**T5. CLI `--details`** (`cli/availability_cmd.py`): `share_text(part,
whole)` (w dol, `<1%`), linie spec D4; docstring modulu.

**T6. Testy.**
- `tests/test_availability.py`: `full_m2` (PL kompletna/niekompletna/zero,
  CZ), `sheet_records` == URL-e planu `check_data` z podpowiedzi (Krakow,
  Pomorze 2023 5 m z `--full-sheet`, LAZ Pomorze 2025), `campaign_coverage`.
- `tests/test_json_contract.py`: klucze `AvailabilityCombination`, nowe
  typy zagniezdzone.
- `tests/test_cli_availability.py`: linie `--details` (spec D4) i formater
  udzialu `share_text`.

**T7. Dokumentacja.** ARCHITECTURE 4.9 (algorytm PL pkt 6-7, CZ pkt 5),
USAGE (pola JSON raportu, przyklad biblioteczny), SCOPE i PRD (lista
eksportow), DECISIONS (ADR-047 + indeks; CRLF), CHANGELOG `[0.8.0]`
Dodane, PROGRESS (sesja, KD-1/KD-2 wdrozone).

**T8. Weryfikacja.** `scripts/gate.sh` zielony; smoke: `kartograf elevation
availability` na nagranych odpowiedziach nie ma sieci, wiec skrypt
jednorazowy drukuje `--details` i JSON kombinacji Pomorze 2023 5 m
z `RecordedIndex` (bez sieci); opcjonalnie na zywo (Krakow, `--details`,
`--output` niepotrzebne - raport niczego nie zapisuje).

## Przeglad wlasny przed wdrozeniem (2026-10-19)

- Zgodnosc z Archiwista SPEC 6.4: "pelne" = `complete` i `campaign_coverage`
  ma pozycje `complete`; "pelne · N" = kampanie `sheet_records`;
  "czesciowe · X%" = `full_m2 / land_m2` - wszystkie wejscia sa w raporcie.
- Ryzyko: LAZ `sheet_records` per uklad arkuszy (spec D2, ograniczenie
  opisane); NMT/NMPT dokladne (test z planem `check_data`).
- Koszt: `rasterize` na kampanie i pas - kombinacje maja zwykle 1-3
  kampanie; bez zmian w zapytaniach sieciowych i cache.
- Zastrzezen blokujacych brak.
