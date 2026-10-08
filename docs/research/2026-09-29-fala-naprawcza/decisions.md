# Fala naprawcza po testach na zywo 2026-09-29 — rozstrzygniecia uzytkownika

Data: 2026-09-29 (sesja wdrozeniowa). Zrodlo bledow: `docs/PROGRESS.md` Backlog ->
"Do naprawy — testy na zywych danych 2026-09-29"; dowody:
`docs/research/2026-09-29-live-e2e-i-audyt-docs/`.

| ID | Decyzja (wiazaca) |
|---|---|
| D1 | Tor CZ (`providers/cuzk/*`, `transform/crs.py`) ODMROZONY dla K2 + K6. Errata ADR-024 obowiazkowa. Po naprawie ponowne testy na zywo scenariuszy L4. |
| D2 | S2: tryb listy arkuszy (PL `--bbox`/`--geometry` bez `--target-crs`) dostaje tolerancje R5 jak wycinek: `NoCoverageError` = pomin arkusz + `Warning:` + lista brakujacych w podsumowaniu; kod 0 gdy >= 1 plik pobrany; kazda inna porazka (siec) = kod 1 z pelna lista porazek; wszystkie arkusze probowane niezaleznie od `--workers`. |
| D3 | S5: wycinek `--target-crs EPSG:2180` z arkuszy o roznych fazach siatki = BLAD (kod 1) z podpowiedzia innego `--target-crs` (pelny warp). R1 (wartosci 1:1) scisle; komunikat "najblizszym sasiadem" znika. |
| D4 | K4/K5: wybor pliku arkusza ze skorowidza = filtr twardy + najnowsza kampania: odrzucic rekordy niezgodne z zadaniem (rozdzielczosc dokladnie 1 m/5 m, uklad 1992/2000 wg godla, orto: RGB), godlo jako caly token; z pozostalych najnowsza data aktualnosci; brak pasujacych = `NoCoverageError`. Koniec cichego fallbacku PL-2000 -> PL-1992. |
| D5 | K3: sidecar `.meta.json` dostaje `extra.source` (URL zrodlowy, warstwa skorowidza, data aktualnosci, rozdzielczosc) — addytywnie. Zerwane zapytanie warstwy skorowidza = blad z ponowieniami, nie cicha degradacja. |
| D6 | Zakres fali: K1-K6, S1-S5, N1-N9, H1 — wszystko, w tym N6 (`MetadataCache` w torach PL; cache nie moze utrwalac starszej kampanii). |
| D7 | Modele: `task` = GPT-6-astra (limit wyczerpany 2026-09-29 po 3-4 min — 4 agenty research bez wyniku); research przelaczony na Claude (`task.agentModelOverrides`, tylko sesja); przed fala wdrozeniowa sprawdzic, czy limit astry wrocil. |
| D8 | S5 dla `--target-crs` != 2180 (5514/3045): zestawy arkuszy off-grid dostaja **W1** — `warp_to_grid(list[Path])`, kazdy arkusz reprojekcja RAZ ze swojej siatki na siatke wyniku (bez `merge`, bez pliku tmp); zestawy na jednej fazie ida dotychczasowa sciezka (mozaika 1:1 + warp, zweryfikowana live); sidecar `extra.off_grid_sheets` tylko na sciezce W1. Wyjatek dla 2180: `GridMismatchError(ValidationError)` z `.off_grid`. |
| D9 | K4: D4 doslownie — najnowsza `aktualnosc` niezaleznie od `calyArkuszWypelnionyTrescia: NIE` (bez preferencji pelnego arkusza). Remis: `(aktualnosc, dt_pzgik, url)`. |
| D10 | S2: tolerancja R5 obejmuje TAKZE hierarchie godla (`download N-34-130-D --scale 1:10000`) — wspolny finisz `_finish_pl_sheets` dla bbox/geometry/hierarchii; pojedynczy arkusz 1:10000 / PL-2000 bez danych = kod 1 (nic do pobrania); 0 plikow i wszystkie bez danych = kod 1 `Error:`. |
| D11 | S2: `DownloadProgress` dostaje status `no_coverage` (addytywnie), CLI drukuje `∅` zamiast `✗` dla arkusza bez danych. |
| D12 | K2: pliki sprzed naprawy (sidecar `transform.horizontal` z "(3) ... 0.5 m") — CHANGELOG/README + `Info:` w CLI przy pomijaniu takiego pliku (`skip_existing`) w torach CZ i wycinku PL -> 5514; bez automatycznej przebudowy. |

Rozstrzygniecia koordynatora (wg rekomendacji raportow, bez pytania): skorowidz P2 wczesne zakonczenie na pierwszej warstwie z rekordem (+ warning przy naruszeniu partycji), P3 cache negatywny `no_coverage` TTL 7 d, P4 `--force` = `cache=None`, P5 `extra.sheet_sources` w sidecarze wycinka, P6 rekord bez rozdzielczosci/ukladu = odrzucony + warning, P7 straz pozytywna szablonu `var \w+ = [];`, P8 `_get_opendata_url` zostaje nakladka na `_resolve_sheet`, P9 ponowienia WYLACZNIE petla aplikacyjna `get_with_retry` (bez `urllib3.Retry`; dotyczy tez LAZ), P10 GetCapabilities bez memoizacji porazki + lock; CZ: pin niejawny w `build_pinned_transform`, `MAX_EXPORT_PIXELS = 4_000_000` kafle kwadratowawe, snap bboxa kotwica NW, N2 tylko CLI `Warning:` + `PlCutoutResult.all_nodata` (bez pola w sidecarze; zero arkuszy nadal `ValidationError`); CLI: S3 oba komunikaty `Info:` bez pola w sidecarze, koniec poszerzania nietknietych krawedzi PL; N4 `extra.parent_requests` (lista) dla arkuszy reuzytych + `missing_sheets` z sidecara przy pominietym wycinku; N8 uklad z godla z kontrola wspolrzednych pliku; N9 cache transformerow w cutout; orto: bez filtra `wielkoscPiksela`, kwarg `color="RGB"` w bibliotece bez flagi CLI; LAZ: straz "zwrocone, zadne nie przecina" = `DownloadError`, `FALLBACK_YEARS` usuniete, 3 proby.

Artefakty tej fali: `research-<klaster>.md` (skorowidz, orto-laz, cz, cli) w tym katalogu.
