# Research — klaster CZ (CUZK): K2, K6, N3, N2

Data: 2026-09-29 (fala naprawcza, faza research). Galaz `develop`, HEAD bez zmian
w `kartograf/`, `tests/`. Decyzje wiazace: `decisions.md` (D1: tor CZ odmrozony
dla K2 + K6, errata ADR-024). Zero sieci: wszystkie dowody policzone OFFLINE
pyproj 3.7.2 / PROJ 9.5.1 (GDAL 3.12.1, rasterio 1.5.0) z `.venv/bin/python`,
`pyproj.network.is_network_enabled() == False`; skrypty jednorazowe w `/tmp`
(nie w repo). Linie kodu wg HEAD.

Streszczenie: **K2 potwierdzony i wyjasniony co do mechanizmu i liczb** (przyczyna:
`min` po dokladnosci w `build_pinned_transform` wybiera slowacka EPSG:4829, 0,5 m,
zamiast czeskiej EPSG:1622, 1,0 m; diagnoza "bledu serwera" z ADR-024 obalona
numerycznie). **Hipoteza naprawy z backlogu (`area_of_interest`) jest
niewystarczajaca i szkodliwa** — zmierzone: z AOI Jaworzynka PROJ nadal stawia
EPSG:4829 na czele, a z AOI na zachod od 14,14°E lista dla 5514 -> 2180 jest
PUSTA. Rekomendacja: jawny pin kroku datum po kodzie EPSG (`DATUM_STEP_PINS`
w `transform/crs.py`, prototyp dziala offline dla wszystkich 8 par). K6, N3, N2:
przyczyny potwierdzone w kodzie; projekt kafelkowania z budzetem pikseli
(prototyp), snap bboxa do kotwicy NW (wspolnej z kaflami i warpem), `Warning:`
dla wyniku w calosci nodata.

---

## 1. K2 — przypieta operacja S-JTSK -> ETRS89 to EPSG:4829 (Slowacja)

### 1.1 Przyczyna potwierdzona na kodzie

`kartograf/transform/crs.py`:

- `:192` — `TransformerGroup(src_crs, dst_crs, always_xy=True, allow_ballpark=False)`
  bez `area_of_interest` (ale patrz 1.1.3: AOI i tak nie rozwiazuje problemu).
- `:196-212` — filtr dokladnosci odrzuca TYLKO `accuracy < 0` i
  `accuracy > policy.min_accuracy_m`; `_HORIZONTAL_POLICY` (`providers/cuzk/dmr.py:89`
  i `download/cutout.py:54`) ma `min_accuracy_m=1.0`, wiec przechodza trzy
  operacje: EPSG:1622 "(1)" 1,0 m (Czechy), EPSG:4829 "(3)" 0,5 m (Slowacja),
  EPSG:4827 "(4)" 1,0 m (Slowacja).
- `:213-231` — probe (`CZ_PROBE_NATIVE`, srodek Czech) odrzuca tylko `inf/NaN`;
  transformacje Helmerta/Molodensky'ego-Badekasa sa globalne i skonczone
  wszedzie, wiec zadna z trzech nie odpada.
- `:236` — `min(candidates, key=lambda c: c[0])` — wygrywa najnizsza DEKLAROWANA
  dokladnosc: 0,5 m = EPSG:4829.

Reprodukcja offline (HEAD, polityki i probe z kodu):

| para | polityka | wynik HEAD |
|---|---|---|
| 5514 -> 2180 | `dmr._HORIZONTAL_POLICY` + `CZ_PROBE_NATIVE` | acc 0.5, `... S-JTSK to ETRS89 (3) + Inverse of ETRF2000-PL to ETRS89 (1) + Poland CS92 ...` |
| 5514 -> 3045 (kafel TM33) | jw. | acc 0.5, `... S-JTSK to ETRS89 (3) + UTM zone 33N ...` |
| 2180 -> 5514 (wycinek PL, ADR-027) | `cutout._HORIZONTAL_POLICY` | acc 0.5, `... Inverse of S-JTSK to ETRS89 (3) + Krovak East North` |
| 3045 -> 5514 (obwiednia bboxa CZ w 3045) | `_ENVELOPE_POLICY` | acc 0.5, `... Inverse of S-JTSK to ETRS89 (3) ...` |
| 4326 -> 5514 (`_country_bbox` CZ pod auto) | `_ENVELOPE_POLICY` | acc 1.0, `Inverse of S-JTSK to WGS 84 (5)` (EPSG:5239, Czechy — poprawne "przypadkiem": PROJ stawia operacje CZ przed SK przy remisie 1,0 m) |
| 5514 -> 4326 (lon/lat dla operacji pionowej) | `_LONLAT_POLICY` | acc 1.0, `S-JTSK to WGS 84 (5)` (EPSG:5239, Czechy) |

Kod EPSG kroku datum czytany z `transformer.to_json_dict()["steps"][i]["id"]`
(`{"authority": "EPSG"|"INVERSE(EPSG)", "code": 4829}`) — to jest wiarygodna
tozsamosc operacji, niezalezna od opisu tekstowego.

Pochodzenie bledu: `docs/research/2026-08-10-czechy-dmr-zabaged.md:290` oznaczyl
"(3) 0,5 m" jako "TAK — najlepsza realnie dostepna", a "(1) 1,0 m" jako "domyslny
wybor PROJ" — tabela nie zawierala kolumny "obszar uzycia"; polityka `min` po
dokladnosci ten wybor utrwalila (ADR-024 "Polityka: ... znane operacje z Krovaka
do 2180/3045 maja 0,5 m" = dokladnosc operacji slowackiej).

#### 1.1.1 Operacje PROJ dla 5514 -> 4258 / 3045 / 2180 (bez AOI i z AOI)

`TransformerGroup(..., always_xy=True, allow_ballpark=False, area_of_interest=...)`,
siec wylaczona. `[unavail]` = operacja wymagajaca siatki nieobecnej lokalnie
(pyproj: `PROJ_GRID_AVAILABILITY_IGNORED`, `PROJ_SPATIAL_CRITERION_PARTIAL_INTERSECTION`).

| cel | AOI | lista (kolejnosc PROJ; acc; krok datum; obszar uzycia calej operacji) |
|---|---|---|
| 4258 | brak | [0] 1.0 **(1) EPSG:1622** Czechia (12.09, 48.58, 18.86, 51.06); [1] 0.5 (3) EPSG:4829 Slovakia (16.84, 47.73, 22.56, 49.61); [2] 1.0 (4) EPSG:4827 Slovakia; unavail: 2x `sk_gku_JTSK03_to_JTSK.tif` |
| 4258 | Karkonosze / kafel 302_5550 / Cieszyn | tylko [0] 1.0 (1) EPSG:1622 |
| 4258 | **Zlin (17.6-17.7E, 49.2N)** | **[0] 0.5 (3) EPSG:4829**, [1] 1.0 (4) EPSG:4827, [2] 1.0 (1) EPSG:1622 |
| 3045 | brak | [0] 1.0 (1)+UTM33N; [1] 0.5 (3)+UTM33N; [2] 1.0 (4)+UTM33N |
| 3045 | Karkonosze / 302_5550 / Cieszyn | tylko (1) |
| 3045 | **Jaworzynka (18.8-18.88E, 49.5-49.56N)** | **[0] 0.5 (3) EPSG:4829**, [1] 1.0 (4), [2] 1.0 (1) |
| 2180 | brak | [0] 7.0 `S-JTSK to WGS 84 (3)`+PL (obszar 14.14-22.56E); [1] 1.0 (1)+ETRF2000-PL+CS92 (obszar CZ∩PL: 14.14, 49.0, 18.86, 51.06); [2] 2.0 `WGS 84 (5)`; [3] 0.5 (3) (obszar 16.84, 49.0, 22.56, 49.61); [4] 1.0 (4) |
| 2180 | Karkonosze / Cieszyn / Praga / Bogatynia / Liberec | [0] 1.0 (1); [1] 2.0 WGS84 (5); [2] 7.0 WGS84 (3) |
| 2180 | **kafel 302_5550 / Cheb (12.2-12.4E)** | **PUSTA LISTA** (obszar zlozonej operacji = CZ ∩ PL = 14.14-18.86E; Cheb lezy poza) |
| 2180 | **Jaworzynka** | **[0] 0.5 (3) EPSG:4829**, [1] 1.0 (4), [2] 7.0 WGS84 (3), [3] 1.0 (1), [4] 2.0 WGS84 (5) |

Metadane operacji (`CoordinateOperation.from_epsg`): EPSG:1622 "S-JTSK to ETRS89
(1)", 1,0 m, Czechia, Helmert 7-par. (570.8, 85.7, 462.8, 4.998", 1.587", 5.261",
3.56 ppm); EPSG:1623 "S-JTSK to WGS 84 (1)", 1,0 m, Czechia — TE SAME parametry
(roznica polozenia 0,1 mm); EPSG:5239 "S-JTSK to WGS 84 (5)", 1,0 m, Czechia,
parametry S-JTSK/05 (roznica wobec 1622: 5-7 cm); EPSG:4829 "S-JTSK to ETRS89
(3)", 0,5 m, Slovakia, Molodensky-Badekas 10-par. (uwaga EPSG: "Replaced by
S-JTSK to ETRS89 (4) (code 4827)" — pyproj mimo `allow_superseded=False` nadal
ja zwraca); EPSG:4827 "(4)", 1,0 m, Slovakia; EPSG:4836 "S-JTSK to WGS 84 (4)",
1,0 m, Slovakia; EPSG:15965 "S-JTSK to WGS 84 (3)", 6,0 m, Czechia; Slovakia.

Ranking wlasny PROJ (bez AOI, `transformers[0]`): 4258 -> (1), 3045 -> (1), ale
2180 -> WGS 84 (3) 7,0 m (najwiekszy obszar) — samo "zaufaj kolejnosci PROJ" nie
jest bezpieczne bez filtra dokladnosci; po filtrze <= 1,0 m pierwsza w kolejnosci
PROJ jest (1) dla wszystkich trzech celow, ale to zalezy od heurystyki
"malejacy obszar", nie od jawnej decyzji.

#### 1.1.2 Roznica polozenia EPSG:1622 − EPSG:4829

Metoda: punkt lon/lat -> S-JTSK odwrotnoscia (1), z powrotem przez (1) i (3);
odleglosc geodezyjna GRS80 oraz roznica w EPSG:2180 i EPSG:3045 (kolumna "w 3045"
odpowiada kaflowi TM33). Wartosci = "gdzie lezy tresc z (1)" minus "gdzie lezy
tresc z (3)".

| punkt | \|d\| geod. [m] | 2180: dE, dN [m] | 3045: dE, dN [m] | backlog / L4 |
|---|---|---|---|---|
| Cieszyn (18.62, 49.76) | 1,16 | −0,03, −1,15 | +0,03, −1,16 | 1,15 |
| Jaworzynka (18.85, 49.53) | 1,13 | −0,38, −1,06 | −0,32, −1,08 | 1,12 |
| Ostrawa (18.28, 49.83) | 1,06 | +0,25, −1,03 | +0,30, −1,02 | 1,04-1,07 |
| Zlin (17.67, 49.22) | 0,14 | +0,11, −0,07 | +0,12, −0,07 | 0,14 |
| Brno (16.61, 49.20) | 0,98 | +0,82, +0,54 | +0,79, +0,59 | 0,98 |
| Kudowa (16.24, 50.44) | 2,16 | +2,09, −0,56 | +2,11, −0,45 | 2,15 |
| Karkonosze (15.74, 50.735) | 2,73 | +2,66, −0,62 | +2,68, −0,48 | 2,72-2,73 (na zywo 2,3 wobec GUGiK; z (1): 0,38) |
| Bogatynia (14.95, 50.90) | 3,34 | +3,32, −0,41 | +3,33, −0,23 | 3,39 |
| Praga (14.42, 50.09) | 3,15 | +3,07, +0,73 | +3,02, +0,89 | 3,15 |
| kafel 302_5550 (12.27, 50.06) | 4,95 | +4,63, +1,79 | **+4,52, +2,03** | 4,97-5,00 |
| As (12.19, 50.22) | 5,06 | +4,80, +1,64 | +4,70, +1,89 | 5,06 |

Liczby z backlogu (0,1-1,0 m Morawy, 1,1-3,4 m wzdluz granicy, ~5 m zachod,
2,3 m Karkonosze na zywo) sa potwierdzone co do 0,05 m.

#### 1.1.3 Hipoteza backlogu (`area_of_interest` z bboxa zadania) — czesciowo bledna

1. **AOI nie rozstrzyga Moraw i Beskidu.** Obszary uzycia EPSG to PROSTOKATY;
   prostokat Slowacji (16.84-22.56E, 47.73-49.61N) obejmuje Zlin, Uherske
   Hradiste, Jaworzynke/Hrcave (obszar C z L4), poludniowe Morawy. Z AOI w tym
   pasie PROJ zwraca obie operacje (obie w calosci zawieraja AOI, remis obszaru),
   a sortuje po dokladnosci — **EPSG:4829 na czele** (tabela 1.1.1, wiersze
   Zlin/Jaworzynka). `min` po dokladnosci wybralby ja tak samo jak dzis.
2. **AOI psuje `--target-crs EPSG:2180` na zachod od 14,14°E.** Obszar zlozonej
   operacji 5514 -> 2180 to przeciecie obszarow krokow (Czechia ∩ Poland =
   14.14-18.86E); AOI Cheb/kafel `302_5550` daje pusta liste ->
   `TransformUnavailableError` tam, gdzie dzis (i po pinie) transformacja jest
   poprawna matematycznie (CS92 to zwykle tmerc, ETRF2000-PL -> ETRS89 to
   operacja zerowa acc 0.0).
3. Sprawdzanie zawierania punktu probe w `area_of_use` kandydata ma te same dwie
   wady (prostokaty; obszar zlozonej operacji).

Wniosek: potrzebna jest tozsamosc KRAJU danych, nie geometria — jawny pin
operacji datum.

#### 1.1.4 Ocena diagnozy ADR-024 ("1,25 m / 4,92 m bledu serwera") — OBALONA

ADR-024 mierzyl `exportImage&imageSR=3045` wzgledem referencji "dane natywne
5514 zreprojektowane lokalnie" — czyli operacja EPSG:4829. Z tabeli 1.1.2
(kolumna 3045):

- Cieszyn (kafle `758_5514`, `760_5514`): (1) − (3) = (+0,03; −1,16) m -> tresc
  policzona operacja czeska lezy 1,16 m na POLUDNIE od referencji 4829; ADR:
  "minimum RMS przy (0; +1,25)", "1,25 m na poludnie" (skan co 0,25 m: 1,16 ->
  1,25). Zgodne.
- `302_5550`: (1) − (3) = (+4,52; +2,03) m; ADR: korekta dE −4,50, dN −2,00,
  4,92 m (skan co 0,25 m). Zgodne co do 0,03 m i znaku.

Serwer CUZK liczyl `imageSR=3045` transformacja czeska (EPSG:1622 lub
rownowazna) i byl POPRAWNY; "fix" ADR-024 zamienil poprawna tresc na przesunieta
o 1-5 m. Blad 135 m dla `imageSR=2180` (brak datum shift; ADR tabela: dE 118,8 /
dN 64,4 = ballpark) pozostaje realny — decyzja (a) ADR-024 (zadania tylko
natywne + lokalny warp z wymuszona operacja) zostaje, bo (i) 2180 jest glownym
celem, (ii) lokalna operacja jest audytowalna (sidecar), (iii) jednolita
sciezka. "Zywa weryfikacja fixu" (RMS 0,016/0,031 m) mierzyla zgodnosc z
referencja zbudowana ta sama operacja — nie mogla wykryc zlej operacji.

#### 1.1.5 Siatki dla CZ w PROJ i polityka sieci

- `PROJ_DATA` = `.venv/.../pyproj/proj_dir/share/proj`: 16 plikow, zadnej siatki
  `cz_*`/`sk_*`; zmienna srodowiskowa `PROJ_DATA` nieustawiona; siec PROJ
  domyslnie wylaczona.
- Dla S-JTSK -> ETRS89 PROJ NIE ZNA zadnej siatki czeskiej — jedyne operacje
  siatkowe to slowackie `sk_gku_JTSK03_to_JTSK.tif` (przez S-JTSK [JTSK03],
  0,051 m); przy `allow_network_grids=True` bylyby dostepne z CDN, ale probe w
  Czechach zwraca `inf` (zweryfikowane w audycie A1-2; KNOWN_PATHS), a po pinie
  odpadaja tez z powodu kroku datum. `cz_cuzk_CR-2005.tif` (CDN) dotyczy tylko
  ETRS89h -> Bpv (4937 -> 8357), nieuzywanej pary. Nic lepszego niz Helmert
  1622 (1,0 m) nie jest osiagalne offline — i to jest poprawna operacja dla
  danych CUZK. Polityka `allow_network_grids=False` dla operacji poziomych
  pozostaje bez zmian.

### 1.2 Proponowana naprawa (D1)

**Jawny pin kroku datum po kodzie EPSG, wewnatrz `build_pinned_transform`,
tabela keyed po CRS.** Prototyp (`/tmp`, ta sama logika co ponizej) daje
EPSG:1622/1623 dla WSZYSTKICH 8 par z udzialem 5514, nie zmienia par bez pinu
(25833 -> 2180: 0.0; 2180 -> 3045: 0.0; 8357 -> 5621: 0.1 `EPSG:5202`),
5514 -> 2180 z probe w Cheb nadal dziala; koszt `to_json_dict()` dla 8 par:
0,15 s lacznie.

`kartograf/transform/crs.py` (obok `KNOWN_PATHS`):

```python
# Datum wspoldzielone przez dwa kraje. Obszary uzycia EPSG to prostokaty, a
# prostokat Slowacji siega po Zlin i Jaworzynke, wiec ani area_of_interest,
# ani ranking PROJ nie odroznia w Morawach transformacji czeskiej od slowackiej
# (zmierzone 2026-09-29: z AOI Jaworzynka PROJ stawia EPSG:4829 na czele).
# Krok datum jest wiec przypiety jawnie do kodow EPSG operacji czeskich (K2).
DATUM_STEP_PINS: dict[int, frozenset[str]] = {
    # S-JTSK / Krovak East North (dane CUZK): "S-JTSK to ETRS89 (1)" i jej
    # blizniak "S-JTSK to WGS 84 (1)" — te same parametry Helmerta (0,1 mm),
    # obszar uzycia Czechy, 1,0 m. Slowackie EPSG:4829/4827/4836 odpadaja.
    5514: frozenset({"EPSG:1622", "EPSG:1623"}),
}
```

Pomocnicze:

```python
def _epsg_code(crs: str) -> int | None:
    """Kod EPSG ukladu (None dla WKT/proj-string bez autorytetu)."""
    try:
        return CRS.from_user_input(crs).to_epsg()
    except Exception:  # noqa: BLE001
        return None

def _operation_codes(transformer) -> frozenset[str]:
    """Kody EPSG krokow operacji (takze odwroconych: INVERSE(EPSG))."""
    doc = transformer.to_json_dict()
    steps = doc.get("steps") or [doc]          # operacja zlozona albo pojedyncza
    codes = set()
    for step in steps:
        ident = step.get("id") or {}
        authority = str(ident.get("authority", ""))
        authority = authority.removeprefix("INVERSE(").removesuffix(")")
        if authority and "code" in ident:
            codes.add(f"{authority}:{ident['code']}")
    return frozenset(codes)
```

W `build_pinned_transform`, po filtrze dokladnosci, PRZED probe (tanio; probe
moze dotykac siatek):

```python
required = DATUM_STEP_PINS.get(_epsg_code(src_crs), frozenset()) | \
           DATUM_STEP_PINS.get(_epsg_code(dst_crs), frozenset())
...
if required and not (_operation_codes(transformer) & required):
    rejected.append((description,
        f"krok datum spoza przypietych {sorted(required)} "
        "(operacja innego kraju dla tego samego datum)"))
    continue
```

Sygnatury `build_pinned_transform`, `TransformPolicy`, `PinnedTransform` — BEZ
zmian. Wybor `min` po dokladnosci zostaje (po pinie jest jeden kandydat na
pare). Zamiast nowego pola polityki: tabela jest niejawna, wiec obejmuje
WSZYSTKICH wolajacych bez zmian u nich — `CuzkDmrProvider._pinned` (tresc,
obwiednia, lon/lat), modulowe `bbox_to_crs` z polityka domyslna (CLI: nazwa
pliku, `_country_bbox`, `_bbox_to_2180` w cutout), `prepare_pl_cutout`
(2180 -> 5514).

Skutki per tor (wszystkie potwierdzone prototypem):

| tor | HEAD | po naprawie |
|---|---|---|
| kafel TM33 (5514 -> 3045) | (3) 0,5 m | (1) EPSG:1622, 1,0 m |
| CZ `--target-crs 2180/3045` | (3) 0,5 m | (1) 1,0 m |
| wycinek PL `--target-crs EPSG:5514` (ADR-027) | Inverse (3) 0,5 m | Inverse (1) 1,0 m |
| obwiednie `bbox_to_crs` 3045/2180 <-> 5514 | (3) | (1) |
| `_country_bbox` 4326 -> 5514, lon/lat 5514 -> 4326 | WGS 84 (5) EPSG:5239 | WGS 84 (1) EPSG:1623 (spojne z 1622 co do 0,1 mm; wobec (5) roznica 5-7 cm, bez znaczenia dla obwiedni i pionu) |
| `--target-crs EPSG:2180` na zachod od 14,14°E | dziala | dziala (bez AOI) |

`_HORIZONTAL_POLICY.min_accuracy_m=1.0` przepuszcza 1,0 m (odrzut tylko `>`) —
bez zmiany. `KNOWN_PATHS`: 5514 -> 2180 `0.5 -> 1.0` (nota: "EPSG:1622 S-JTSK to
ETRS89 (1), Czechy; pin DATUM_STEP_PINS — EPSG:4829 0,5 m to operacja slowacka,
K2"), 2180 -> 5514 `0.5 -> 1.0` (opis zmierzonej sciezki "(3)" -> "(1)"); dodac
5514 -> 3045 (1.0) i 5514 -> 4326 (1.0, EPSG:1623), bo sa uzywane.

Kontrakt widoczny dla wolajacych:

- **Sidecar `.meta.json`** (`transform.horizontal`, CZ i wycinek PL -> 5514):
  `"pinned: ... S-JTSK to ETRS89 (3) ... (0.5 m)"` ->
  `"pinned: ... S-JTSK to ETRS89 (1) ... (1.0 m)"`. Format bez zmian; wartosc
  jest jednoczesnie ZNACZNIKIEM plikow sprzed naprawy ("(3)") — konsument moze
  je rozpoznac. `PinnedTransform.accuracy_m` 0.5 -> 1.0.
- **Tresc rastrow** przesuwa sie o 1-5 m wzgledem plikow z HEAD (to jest
  naprawa). Pliki juz na dysku z operacja (3) NIE sa unieważniane automatycznie:
  `skip_existing` je zostawi (kafle TM33 w `nmt/cz_dmr5g_*/<E>/<N>/`, wycinki
  `nmt/cz_*/bbox/` z `--target-crs`, wycinki `nmt/pl_1992_*/bbox/` w 5514).
  Wycinki natywne 5514 i arkusze SM5 sa poprawne (bez reprojekcji).
- `download_pl_cutout` / Hydrograf: bez zmian sygnatur; zmiana dokladnosci i
  tresci tylko dla `target_crs="EPSG:5514"`.
- CLI: komunikat `cli/download_cmd.py:1642-1645` (i duplikat `:678-682`) "tryb
  godlowy dostarcza dane natywne 1:1" jest falszywy dla TM33 -> "godlo wyznacza
  zasieg i uklad produktu (arkusz SM5 1:1 w EPSG:5514, kafel TM33 na siatce
  EPSG:3045)".
- Komentarze do korekty: `providers/cuzk/dmr.py:53-56` ("5514->3045 przesuwa
  tresc o 1,25 m" -> "1,25 m to roznica operacji 1622/4829, errata ADR-024"),
  `:86-89` ("maja 0,5 m" -> "EPSG:1622, 1,0 m, pin"), `:269-273` (docstring
  `_export_raster`), `transform/crs.py:142-149` (KNOWN_PATHS), `:159`
  (Bpv -> EVRF2007 "+0,12..+0,14 m" -> "+0,11..+0,15 m" wg L4 U7).

### 1.3 Strategia testow offline (failing-before / passing-after)

`tests/test_transform_crs.py`:

- NOWY `TestDatumStepPins::test_5514_pairs_pin_czech_operation` — realne pyproj,
  `TransformPolicy(min_accuracy_m=1.0, allow_network_grids=False, probe_point=CZ_PROBE_NATIVE)`,
  parametryzacja po parach `(5514,2180)`, `(5514,3045)`, `(2180,5514)`,
  `(3045,5514)`, `(5514,4258)`: `"S-JTSK to ETRS89 (1)" in description`,
  `accuracy_m == 1.0`, `"molobadekas" not in gdal_operation()`; FAIL na HEAD
  (dzis "(3)", 0.5).
- NOWY `test_5514_wgs84_pairs_pin_twin_operation` — `(5514,4326)`, `(4326,5514)`:
  `"S-JTSK to WGS 84 (1)"`; FAIL na HEAD (dzis "(5)").
- NOWY `test_pin_reports_rejected_datum_step` — z mockiem grupy: kandydat z
  `to_json_dict.return_value = {"steps": [{"id": {"authority": "EPSG", "code": 4829}}]}`
  odpada z powodem zawierajacym "EPSG:1622"; przy braku kandydatow
  `TransformUnavailableError.rejected` niesie ten powod.
- NOWY `test_pin_ignores_pairs_without_pinned_crs` — `(25833,2180)`, `(8357,5621)`
  bez zmian (juz czesciowo: `test_25833_to_2180_end_to_end_offline`).
- NOWY `test_pinned_operation_moves_content_by_known_offset` — punkt S-JTSK
  Karkonoszy: roznica miedzy wynikiem przypietym a `TransformerGroup` z
  operacja (3) wynosi 2,73 ± 0,05 m (liczby z 1.1.2) — chroni przed cichym
  powrotem do 4829 niezaleznie od opisu.
- DO ZMIANY: `TestGdalOperation::test_operation_carries_datum_step` (`:229-232`)
  asertuje `"molobadekas"` — to przypina WLASNIE bledna operacje; zastapic
  `"helmert" in op and "x=570.8" in op` (parametry 1622) albo asercja po opisie.
- DO ZMIANY: `TestKnownPaths::test_pl_cutout_pairs_documented_with_measured_accuracy`
  (`:152-172`): oczekiwane 0.5 dla 2180 -> 5514 -> 1.0 (naturalny test
  regresyjny: FAIL na HEAD po zmianie KNOWN_PATHS, PASS po naprawie).
- DO ZMIANY (mechanicznie): testy z `_GROUP_PATCH` na parze 5514 -> 2180
  (`:49`, `:82-93`, `:97-108`, `:111-120`, `:127`) — mockowe transformery musza
  miec `to_json_dict.return_value` z krokiem 1622 (rozszerzyc `_mock_transformer`
  o parametr `codes=("EPSG:1622",)`) ALBO przeniesc te generyczne testy na
  pare bez pinu (np. 25833 -> 2180). Rekomendacja: parametr `codes` w helperze
  (jedna linia), bo pin ma byc widoczny w testach polityki.

`tests/test_cuzk_dmr.py`:

- `TestHorizontalReprojection::test_warp_forces_the_pinned_operation` (`:511-544`)
  — sanity `"molobadekas" in expected` -> `"helmert" in expected` (`x=570.8`);
  asercja o `COORDINATE_OPERATION` bez zmian.
- `TestProbePoint::test_horizontal_policy_rejects_operation_returning_inf`
  (`:589-599`) — mocki `_fake_operation` dostaja `to_json_dict` z krokiem 1622
  (helper `_fake_operation(..., codes=...)`); `accuracy_m == 0.5` w asercji to
  wartosc mocka — zostaje.
- NOWY `test_tm33_tile_uses_czech_datum_operation` — `download("302_5550")` z
  `_server_emulator()` (istniejacy fixture): sidecar/`horizontal_transform("EPSG:3045").description`
  zawiera "(1)".

`tests/test_pl_cutout.py:1215-1218`, `tests/test_cli.py:2891-2893`, `:2962`,
`:3089` — mocki `PinnedTransform` z opisem "(3)" i 0.5: zmienic na "(1)"/1.0
(kosmetyka; testy patchuja `build_pinned_transform` w calosci, wiec nie
lamia sie, ale utrwalaja falszywy opis).

Test wycinka PL -> 5514 (`tests/test_pl_cutout.py`): istniejacy test
`prepare_pl_cutout(..., "EPSG:5514")` z realnym pyproj (jesli jest) dostaje
asercje `cutout.pinned.accuracy_m == 1.0` i "(1)" w opisie.

### 1.4 Ryzyka i pozostale pytania projektowe

1. **Gdzie zyje pin: tabela niejawna w `build_pinned_transform` (rekomendacja)
   vs pole `TransformPolicy.required_steps` ustawiane przez wolajacych.**
   Niejawna: jedno miejsce, obejmuje CLI `bbox_to_crs`, cutout i provider bez
   zmian sygnatur; nikt nie zapomni. Jawna: czytelniejsza w miejscu uzycia i
   przyjazna mockom, ale cutout musialby ustawiac pin warunkowo per cel
   (2180 -> 3045 nie ma kroku S-JTSK) i kazdy nowy wolajacy moze go pominac.
   Rekomendacja: niejawna + wpis w `KNOWN_PATHS`/ARCHITECTURE sekcja 5.
2. **Pliki sprzed naprawy w cache uzytkownikow (`skip_existing`).** Opcje:
   (a) tylko dokumentacja + CHANGELOG ("usun/`--force` pliki z sidecarem
   `S-JTSK to ETRS89 (3)`"), (b) `Info:` w CLI, gdy pomijany plik ma sidecar
   z "(3)" (koszt: odczyt JSON przed skipem, dotyczy tylko CZ/`--target-crs`),
   (c) automatyczna przebudowa. Rekomendacja: (a) + (b) dla torow CZ i wycinka
   PL -> 5514 (tani, celowany komunikat); (c) odrzucic (niespodziewany
   transfer).
3. **Tozsamosc ukladu w tabeli: `CRS.from_user_input(...).to_epsg()`
   (rekomendacja) vs porownanie stringu `EPSG:5514`.** `to_epsg()` obsluguje
   `str(ds.crs)` z rasterio i male litery (`_bbox_to_2180` juz normalizuje
   wielkosc liter, m-2); koszt ~ms na pare. WKT bez autorytetu daje `None` ->
   brak pinu (dzis takie wywolania nie istnieja).
4. **Czy do sidecara dopisac kody EPSG operacji** (np. `"pinned: ... [EPSG:1622]
   (1.0 m)")? Opis "(1)" juz identyfikuje operacje; zmiana formatu dotknelaby
   konsumentow. Rekomendacja: nie teraz; ewentualnie osobne pole
   `transform.horizontal_codes` w etapie 2, jesli Hydrograf poprosi.
5. `EPSG:4829` jest w EPSG oznaczona "Replaced by 4827" — pyproj z
   `allow_superseded=False` i tak ja zwraca; nie polegac na tym mechanizmie.

### 1.5 Szacunek zakresu

`transform/crs.py` (tabela + 2 helpery + ~8 linii w petli + KNOWN_PATHS),
`providers/cuzk/dmr.py` (tylko komentarze/docstringi), `cli/download_cmd.py`
(2 komunikaty; opcjonalnie `Info:` z pkt 2), testy: `test_transform_crs.py`,
`test_cuzk_dmr.py`, kosmetyka w `test_cli.py`/`test_pl_cutout.py`; docs:
DECISIONS (errata, sekcja 5), ARCHITECTURE (`:80-84`, `:729-735`, `:832-834`),
README "Znane problemy" (`:212-216`), CHANGELOG, CLAUDE.md, PROGRESS. Kontrakt
publiczny: tylko wartosc `transform.horizontal` w sidecarze i tresc rastrow
(zamierzone).

---

## 2. K6 — realny limit `exportImage` ~8 Mpx, klient tnie dopiero > 15000 x 4100 px

### 2.1 Przyczyna potwierdzona na kodzie

`kartograf/providers/cuzk/client.py`:

- `:36-37` — `MAX_EXPORT_WIDTH = 15000`, `MAX_EXPORT_HEIGHT = 4100` (z metadanych
  ImageServer `maxImageWidth/maxImageHeight`), lacznie 61,5 Mpx na kafel.
- `:139-140` — `width_px/height_px = max(1, round(...))`.
- `:142` — `if width_px <= self.MAX_EXPORT_WIDTH and height_px <= self.MAX_EXPORT_HEIGHT:`
  jedyny warunek (per wymiar); 3000 x 3000 (9 Mpx) idzie jednym zapytaniem.
- `:155-162` + `_tile_grid` (`:257-303`) — `_splits(total_px, max_px)` dzieli
  KAZDY wymiar osobno po `max_w`/`max_h`; zaden budzet iloczynu (10 x 10 km 2 m
  = 5000 x 5000 -> 1 kolumna x 2 wiersze = kafle 5000 x 2500 = 12,5 Mpx ->
  HTTP 500).
- `transport/http.py:42-62` — kazde HTTP 500 jest ponawiane 3x z backoffem
  (1 + 2 s), wiec odrzucone zapytanie kosztuje ~30 s zanim wyjdzie
  `DownloadError`.

Dowody na zywo (L4 BUG-L4-2, sondy curl): 2500 x 2500 (6,25 Mpx, 26 MB, 40 s)
OK, 3000 x 2500 (7,5 Mpx) OK, 6000 x 1000 OK, 4096 x 2047 (8,38 Mpx) 500,
5000 x 2500 500; pas 1800 x 12300 = 3 kafle 1800 x 4100 (7,38 Mpx) OK, szwy bit
w bit. Limit zalezy od liczby pikseli, nie od ksztaltu ani zasiegu (w granicach
sond: szerokosc <= 6000).

Szwy: `_tile_grid` kotwiczy kafle w NW rogu bboxa na wielokrotnosciach
`pixel_size` (`:290-301`); `mosaic_and_crop(tile_paths, bbox, ...)`
(`transport/mosaic.py:324-330`) wola `rasterio.merge(bounds=bbox)`, ktory
kotwiczy siatke wyniku w `(min_x, max_y)` z `round()` liczby pikseli i ta sama
rozdzielczoscia co kafle -> przesuniecia miedzy siatka kafli a siatka wyniku sa
calkowite w pikselach, `merge` kopiuje bloki bez resamplingu — stad szwy bit w
bit (L4 S3b-d). Warunek konieczny: kafle i wynik na tej samej siatce
(zachowany przez projekt nizej).

### 2.2 Proponowana naprawa

Budzet pikseli na kafel + "kwadratowawe" kafle, limity per wymiar z metadanych
zostaja jako twarde sufity:

```python
class CuzkClient:
    MAX_EXPORT_WIDTH = 15000    # metadane ImageServer (maxImageWidth)
    MAX_EXPORT_HEIGHT = 4100    # metadane ImageServer (maxImageHeight)
    # Realny limit serwera to ~8 Mpx na zapytanie (sondy 2026-09-29: 7,5 Mpx OK,
    # 8,38 Mpx HTTP 500), niezalezny od ksztaltu. Budzet z zapasem ~50 %:
    # kafel 4 Mpx generuje sie ~25 s (2500x2500 = 6,25 Mpx: 40 s), czyli
    # z zapasem wobec timeoutu 60 s toru CZ; czas serwera rosnie liniowo
    # z liczba pikseli, wiec wiecej mniejszych kafli nie wydluza pobrania.
    MAX_EXPORT_PIXELS = 4_000_000
```

`export_image` (`:142`): `if width_px <= MAX_W and height_px <= MAX_H and
width_px * height_px <= MAX_PIXELS:`; `_tile_grid(bbox, pixel_size, width_px,
height_px, max_w, max_h, max_px)`:

```python
def _tile_grid(bbox, pixel_size, width_px, height_px, max_w, max_h, max_px):
    # kolumny: szerokosc kafla <= min(max_w, sqrt(max_px)) — ksztalt zblizony
    # do kwadratu (klasa ksztaltow potwierdzona sondami: 2500x2500, 3000x2500),
    # bez nieprzetestowanych pasow 15000 x 260 px
    col_cap = max(1, min(max_w, math.isqrt(max_px)))
    cols = _splits(width_px, math.ceil(width_px / col_cap))
    tile_w = max(size for _, size in cols)
    # wiersze: reszta budzetu na kolumne o najwiekszej szerokosci
    row_cap = max(1, min(max_h, max_px // tile_w))
    rows = _splits(height_px, math.ceil(height_px / row_cap))
    ...  # petla jak dzis (kotwica NW, N->S, W->E)
```

(`_splits` przyjmuje liczbe czesci zamiast `max_px`; podzial rowny jak dzis.)
Prototyp (`/tmp`), budzet 4 Mpx, sumy pikseli = zadanie, kazdy kafel
<= 15000 x 4100 i <= 4 Mpx:

| zadanie (2 m) | px | kafli (pasowy wariant / kwadratowawy) | najwiekszy kafel |
|---|---|---|---|
| L4 S3 10 x 10 km | 5000 x 5000 (25 Mpx) | 7 (5000 x 715) / 9 (1667 x 1667) | 3,58 / 2,78 Mpx |
| L4 S3e 6 x 6 km | 3000 x 3000 (9 Mpx) | 3 (3000 x 1000) / 4 (1500 x 1500) | 3,0 / 2,25 Mpx |
| pas 3,6 x 24,6 km | 1800 x 12300 (22 Mpx) | 6 (1800 x 2050) / 6 | 3,69 Mpx |
| 10 x 5 km W-E | 5000 x 2500 (12,5 Mpx) | 4 / 6 | 3,1 / 2,1 Mpx |
| 30 x 30 km | 15000 x 15000 (225 Mpx) | 57 (15000 x 263) / 64 (1875 x 1875) | 3,96 / 3,5 Mpx |
| 100 x 0,1 km | 50000 x 50 (2,5 Mpx) | 4 (12500 x 50) / 25 (2000 x 50) | 0,6 / 0,1 Mpx |
| 8 x 8 px | — | 1 | — |

Wariant "pasowy" (najpierw pelna szerokosc, potem wiersze) daje mniej zapytan,
ale kafle 15000 x 263 px sa klasa ksztaltu, ktorej nikt nie testowal na
zywo; wariant kwadratowawy (rekomendacja) trzyma sie ksztaltow sprawdzonych.
Liczba zapytan ma drugorzedne znaczenie, bo czas serwera skaluje sie z
pikselami (30 x 30 km: 64 kafle x ~25 s ~ 27 min w obu wariantach).

Bez zmian: `mosaic_and_crop` po stronie natywnej PRZED warpem (ADR-024 d),
`_overwrite_crs`, sprzatanie `.partN.tif`, chunked merge (293 MiB RSS na 22 Mpx).
Warunek `bbox.crs == image_sr` przy kafelkowaniu (`:144-149`) zostaje (tor CZ
zawsze kafelkuje w 5514).

Opcjonalnie (nie wymagane przez K6): `_export_single` po `DownloadError` z
HTTP 500 — nie da sie tego dzis odroznic (`download_to` opakowuje
`RequestException`); zostawic.

Kontrakt: brak zmian API; `CuzkDmrProvider` nie dotyka limitow. Wynik dla
obszarow, ktore dzis przechodza jednym zapytaniem (< 4 Mpx), identyczny co do
siatki (kotwica NW). Dla obszarow 4-8 Mpx wynik staje sie mozaika 2 kafli:
tresc identyczna (szwy bit w bit — serwer probkuje bilinear na tej samej
siatce uslugi niezaleznie od zasiegu zapytania; potwierdzone L4 S3b-d), rozmiar
pliku moze sie roznic (mozaika = GTiff `merge`, bez kafli TIFF serwera —
ADR-024 koszt (a)).

### 2.3 Strategia testow offline (`tests/test_cuzk_client.py`, mock `download_to`)

- Istniejace `test_tiling_above_limits_mosaics` (`:400-452`),
  `test_tiling_fractional_height_keeps_content_aligned` (`:454-518`),
  `test_tiling_corrupted_tile_...` (`:520`), `test_tiling_with_crs_mismatch_raises`
  (`:568`) patchuja `MAX_EXPORT_WIDTH/HEIGHT` na 4/250 — musza dodatkowo
  patchowac `MAX_EXPORT_PIXELS` (np. na duza wartosc), inaczej budzet zmieni
  liczbe kafli i asercje `len(requested) == 4`.
- NOWY `test_pixel_budget_tiles_below_dimension_limits` — bbox 3000 x 3000 px
  (pixel_size 2, zakres 6000 m) z `MAX_EXPORT_PIXELS` spatchowanym na
  4_000_000 i domyslnymi 15000/4100: FAIL na HEAD (jedno zapytanie
  `size=3000,3000`), PASS po naprawie (kazde zadanie `w*h <= 4_000_000`,
  suma = 9 Mpx, wynik 3000 x 3000, bounds = bbox, `*.part*.tif` posprzatane).
  Fake serwer jak w `test_tiling_above_limits_mosaics` (`_write_geotiff` z
  wartoscia = numer kafla) — dodatkowo asercja, ze kazdy piksel wyniku ma
  wartosc kafla, ktory go pokrywa (szwy bez interpolacji).
- NOWY `test_tile_grid_respects_budget_and_covers_request` — czysty test
  `_tile_grid` (parametryzacja: 5000 x 5000, 1800 x 12300, 50000 x 50, 8 x 8):
  kazdy kafel `<= max_w`, `<= max_h`, `w*h <= max_px`; kafle rozlaczne,
  suma pikseli = zadanie, kotwica NW (`tile.max_y` pierwszego wiersza ==
  `bbox.max_y`, `tile.min_x` pierwszej kolumny == `bbox.min_x`).
- NOWY `test_default_budget_is_below_measured_server_limit` —
  `CuzkClient.MAX_EXPORT_PIXELS <= 6_000_000` i `> 0` (straznik przed
  "poprawka" w gore ponad sondy 2026-09-29).
- `tests/test_cuzk_dmr.py::test_server_is_asked_only_for_native_5514` (`:412`)
  patchuje `CuzkClient` w calosci — bez zmian.

### 2.4 Ryzyka i pozostale pytania

1. **Wartosc budzetu: 4 Mpx (rekomendacja) vs 6 Mpx (z briefu).** 6 Mpx: mniej
   zapytan (10 x 10 km: 5 vs 7-9), ale ~40 s/kafel przy timeoucie 60 s toru CZ
   (`_DEFAULT_TIMEOUT`) i 25 % pod urwiskiem 8 Mpx zmierzonym jednego dnia na
   jednym serwerze; 4 Mpx: ~25 s/kafel, 50 % zapasu, ten sam calkowity czas.
   Opcja trzecia: budzet konfigurowalny w konstruktorze `CuzkClient`
   (`max_export_pixels=`) — zbedne dla CLI, przydatne testom; rekomendacja:
   stala klasowa (jak dzis), patchowana w testach.
2. **Ksztalt kafli** (2.2): kwadratowawy (rekomendacja) vs pasowy.
3. **Limit dmr4g (5 m) nieweryfikowany** (L4) — ten sam budzet dla obu uslug;
   ryzyko tylko w strone zbyt malych kafli.
4. **Retry na HTTP 500 z exportImage** — po naprawie odrzucenia z powodu rozmiaru
   nie powinny wystepowac; 500 z innych przyczyn (serwer) warto ponawiac.
   Bez zmian.

### 2.5 Szacunek zakresu

`providers/cuzk/client.py` (stala, warunek, `_tile_grid` ~15 linii),
`tests/test_cuzk_client.py` (4 patche + 3 nowe testy), docs: CLAUDE.md
(akapit K6 w "Ograniczenia": limit 15000 x 4100 -> budzet 4 Mpx, "obszar
> 5,5 x 5,5 km nie przechodzi" usunac), README "Znane problemy", ARCHITECTURE
sekcja CZ, CHANGELOG, errata ADR-024 (d). Bez zmian kontraktu publicznego.

---

## 3. N3 — natywny wycinek CZ (jedno zapytanie) ma piksel 2,0004 m

### 3.1 Przyczyna potwierdzona na kodzie

`providers/cuzk/client.py:139-140` liczy `width_px/height_px = round(zasieg / px)`,
a `:142-147` -> `_export_single(endpoint, bbox, width_px, height_px, ...)` wysyla
NIEZMIENIONY bbox (`:214-217`, `.10g`) z `size=width_px,height_px` -> piksel =
`zasieg / round(zasieg / px)`. Serwer wymusza piksel kwadratowy, wiec zasieg Y
rozjezdza sie z zadaniem. Reprodukcja offline przykladu z CLAUDE.md
(`18.60,49.752,18.65,49.768`, `bbox_to_crs` -> 5514): 1867 x 1033 px, piksel X
**2,000536 m** (L4: 2,000536 — zgodne co do 1e-6), Y 1,999588 m.

Tor kafelkowany (`_tile_grid`, kotwica NW na wielokrotnosciach `px`) i tor z
warpem (`_warp_to_grid`, `from_origin(min_x, max_y)` + `round`) maja piksel
dokladny — niespojnosc trzech sciezek (L4 BUG-L4-6).

### 3.2 Proponowana naprawa

Snap bboxa w `CuzkClient.export_image` PRZED rozgalezieniem na tor pojedynczy /
kafelkowany, do kotwicy NW (wspolnej z `_tile_grid`, `rasterio.merge(bounds=)`
i `_warp_to_grid`):

```python
width_px = max(1, round((bbox.max_x - bbox.min_x) / pixel_size))
height_px = max(1, round((bbox.max_y - bbox.min_y) / pixel_size))
# Siatka wyniku: kotwica NW, dokladnie width_px x height_px pikseli o boku
# pixel_size (jak _tile_grid i _warp_to_grid). Bez tego serwer dostaje
# zasieg niepodzielny przez pixel_size i zwraca piksel np. 2,0005 m (N3).
bbox = BBox(bbox.min_x, bbox.max_y - height_px * pixel_size,
            bbox.min_x + width_px * pixel_size, bbox.max_y, bbox.crs)
```

Tor kafelkowany dostaje ten sam snapped bbox — wynik `merge(bounds=)` jest
identyczny jak dzis (ta sama kotwica i liczba pikseli), wiec zmiana jest dla
niego no-opem; tor pojedynczy zaczyna zwracac piksel dokladnie `px` i zasieg
zgodny z siatka. Krawedz E/S wyniku rozni sie od zadania o <= ½ px — tak jak
juz dzis w torze z warpem (ADR-024 "Konsekwencje", errata: kotwica NW).

Kontrakt: nazwa pliku i `request.bbox` w sidecarze nadal niosa bbox
znormalizowany PRZED snapem (`cli/download_cmd.py:1528-1543`, `:1569-1572`) —
jak w torze z warpem i w wycinku PL (`prepare_pl_cutout` nazywa plik z
`bbox_target`, a `build_pl_cutout` snapuje na zewnatrz do siatki arkuszy).
Nie dotyka `download_bbox` providera ani `bbox_to_crs`.

### 3.3 Strategia testow offline

- `tests/test_cuzk_client.py::test_single_shot_url_params` (`:336-378`) — bbox
  calkowity (302000..304000), asercja `params["bbox"]` bez zmian (snap = no-op).
- NOWY `test_single_shot_snaps_bbox_to_pixel_grid_nw` — bbox `(0, 0, 1000.7, 181.4)`,
  px 2: URL musi niesc `bbox=0,-0.6,1000,181.4` i `size=500,91`; fake serwer
  (jak w `test_tiling_fractional_height_keeps_content_aligned`) zapisuje GeoTIFF
  o zadanym zasiegu i rozmiarze -> `src.res == (2.0, 2.0)`, `src.bounds.top == 181.4`,
  `src.bounds.left == 0`; FAIL na HEAD (URL `bbox=0,0,1000.7,181.4`, `res`
  (2.0014, 1.9934)).
- NOWY `test_tiled_and_single_paths_share_the_grid` — ten sam ulamkowy bbox raz
  z `MAX_EXPORT_PIXELS` duzym (tor pojedynczy), raz malym (kafle): identyczne
  `transform`, `width`, `height` wyniku.

### 3.4 Ryzyka i pytania

1. **Kotwica NW (rekomendacja) vs SW.** NW jest juz kotwica kafli, `merge` i
   obu warpow (audyt A3-1, errata ADR-024) — SW rozjechalaby tor pojedynczy z
   kafelkowanym o < 1 px.
2. **Dociagniecie do siatki USLUGI (faza (0,4; 1,88) m mod 2, L4 U11)** daloby
   piksele natywne 1:1 zamiast bilinear serwera — wymaga metadanych ImageServer
   (origin) i zmienia zasieg kazdego wycinka; poza N3 (etap 2 / R6 chce
   kotwiczyc warp CZ na siatce arkuszy PL). Rekomendacja: nie teraz.
3. **Nazwa pliku ze snapped bboxa?** Spojnosc z torem warpu i PL mowi "nie";
   roznica <= ½ px jest juz udokumentowana. Rekomendacja: bez zmian.

### 3.5 Zakres

`providers/cuzk/client.py` (4 linie w `export_image`), `tests/test_cuzk_client.py`
(2 nowe testy), docs: CLAUDE.md/README (usunac N3 ze znanych bledow), errata
ADR-024 (piksel dokladny w kazdym torze). Bez zmian kontraktu publicznego.

---

## 4. N2 — wynik w 100 % nodata przyjmowany jako sukces bez komunikatu

### 4.1 Przyczyna potwierdzona na kodzie

- `download/cutout.py:609-613` — `if not sheet_paths: raise ValidationError(...)`
  sprawdza tylko, czy JAKIS arkusz sie pobral; arkusze z marginesu 1 px
  (`select_pl_cutout_sheets`, `:258-262`) potrafia nie wnosic ani jednego
  piksela (L4 BUG-L4-5: Karkonosze 5 m, 0/647 424 waznych, kod 0 + `Warning:`
  o 10 arkuszach). `build_pl_cutout` nie liczy waznych pikseli.
- Tor CZ: `cli/download_cmd.py:1554-1580` (`_cz_download_bbox`) i `:1463-1494`
  (`_cz_download_godlo`) po `provider.download_bbox/download` czytaja tylko
  tag nodata (`_read_tif_nodata`, `:1376-1384`) do sidecara; `CuzkDmrProvider`
  zwraca `Path` bez statystyk. Obszar poza pokryciem DMR (PL w prostokacie CZ
  — Raciborz S5; kafel TM33 w Niemczech) = plik samych `-9999`, kod 0, cisza
  (L4 U4).

### 4.2 Proponowana naprawa (`Warning:` bez zmiany kodu wyjscia)

Wspolny helper (nowy, `kartograf/transport/mosaic.py` — obok logiki nodata
mozaiki; alternatywnie `transform/raster.py`):

```python
def has_valid_pixels(path: Path, nodata: float | None) -> bool:
    """Czy raster ma choc jeden piksel spoza nodata/NaN (wczesne wyjscie)."""
    with rasterio.open(path) as src:
        for _, window in src.block_windows(1):
            data = src.read(1, window=window)
            mask = np.isfinite(data)
            if nodata is not None:
                mask &= data != nodata
            if mask.any():
                return True
    return False
```

Koszt: dla rastra z danymi zwykle jeden blok; dla rastra w calosci nodata
pelny odczyt sekwencyjny (30 x 30 km 2 m = 225 Mpx Float32 = 900 MB: rzedu
sekund, pomijalne wobec pobrania). Liczone PO mozaice/warpie, na pliku
wynikowym.

Tor PL (`run_pl_cutout`, `:621-642`): po `build_pl_cutout` ->
`all_nodata = not has_valid_pixels(target, nodata)`; `logger.warning(...)`;
`PlCutoutResult` dostaje pole addytywne `all_nodata: bool = False`; CLI
(`_download_pl_cutout`, `:1060-1070`) drukuje
`Warning: wycinek w calosci nodata — pobrane arkusze nie wnosza zadnego
piksela w obszarze zadania (brak danych GUGiK / obszar poza pokryciem)` i
zwraca 0. Regula `:609-613` (zero pobranych arkuszy = `ValidationError`)
zostaje (patrz 4.4 pkt 1).

Tor CZ (CLI, `_cz_download_bbox` po `:1555` i `_cz_download_godlo` po `:1464`):
`Warning: {target} jest w calosci nodata — obszar poza pokryciem DMR CUZK
(poza granica CZ?)`, kod 0; sprawdzenie best-effort (wyjatek odczytu = brak
ostrzezenia, jak `_read_tif_nodata`), bo mocki providera w `tests/test_cli.py`
nie zapisuja pliku. Provider (biblioteka) bez zmian sygnatury — zob. 4.4 pkt 2.
Pod `--country auto` (Raciborz) ostrzezenie dotyczy czesci CZ, kod 0 jak dotad.

Sidecar: bez zmian (4.4 pkt 3).

### 4.3 Strategia testow offline

- `tests/test_pl_cutout.py` — wzorzec `test_no_coverage_sheet_becomes_nodata_with_record`
  (`:1623`) / `test_all_sheets_without_data_is_an_error` (`:1650`): NOWY
  `test_cutout_entirely_nodata_warns_and_flags_result` — arkusze syntetyczne
  (`_write_sheet_asc`) polozone tak, by pokrywaly tylko margines poza
  `bbox_target` (albo arkusz w 100 % nodata, jak `M-34-74-C-c-2-4` z L4 U1):
  `result.all_nodata is True`, `caplog` ma warning, plik istnieje; FAIL na HEAD
  (`AttributeError`/brak warningu). Kontrola: wycinek z danymi ->
  `all_nodata is False`.
- CLI PL: obok `test_missing_sheet_warns_and_returns_0` (`:794`) NOWY test z
  wynikiem `all_nodata=True` -> `Warning:` w stderr, rc 0.
- `tests/test_cli.py::TestCmdDownloadCz` — wzorzec
  `test_sidecar_nodata_comes_from_geotiff_tag` (`:3312`, provider mock pisze
  prawdziwy GeoTIFF): NOWY `test_bbox_all_nodata_warns_but_returns_0` (raster
  samych −9999 -> `Warning:` w stderr, rc 0, sidecar zapisany) i lustrzany dla
  godla TM33; kontrola: raster z danymi -> brak `Warning:`.
- `tests/test_transport_mosaic.py`: NOWY test `has_valid_pixels` (nodata, NaN,
  jeden wazny piksel w ostatnim bloku, `nodata=None`).

### 4.4 Ryzyka i pytania

1. **Spojnosc z regula `:609-613`** (zero arkuszy = blad, kod 1; zero pikseli
   z arkuszami = `Warning:`, kod 0). Opcje: (a) jak wyzej (rekomendacja — zgodne
   z briefem i z R5: pliki na dysku sa poprawnym wynikiem "brak danych"),
   (b) ujednolicic oba przypadki jako `Warning:` + plik nodata, (c) oba jako
   blad. (b) zmienia istniejacy kontrakt (`ValidationError` w docstringu
   `download_pl_cutout`), (c) lamie sciezke `auto` na pograniczu.
2. **Uzytkownicy biblioteki `CuzkDmrProvider`** nie dostana sygnalu (sprawdzenie
   w CLI). Opcje: (a) tylko CLI (rekomendacja: przeplyw CZ zyje w CLI,
   ADR-023), (b) `logger.warning` w `download_bbox/download` providera (drugi
   odczyt pliku w CLI albo CLI polega na logu), (c) provider zwraca wynik
   strukturalny (zmiana kontraktu `BaseProvider`). Rekomendacja: (a), z nota w
   docstringu providera.
3. **Flaga w sidecarze** (`extra.all_nodata: true`): tania, addytywna,
   przydatna Hydrografowi do pomijania plikow; ale czesciowe nodata nie jest
   raportowane, wiec pole byloby polprawda. Rekomendacja: nie teraz; jesli
   Hydrograf poprosi — `extra.valid_pixel_ratio` liczony przy tej samej
   przebiegu (koszt: pelny odczyt zawsze).

### 4.5 Zakres

`transport/mosaic.py` (helper, ~12 linii), `download/cutout.py` (pole
`PlCutoutResult`, ~6 linii w `run_pl_cutout`, docstringi), `cli/download_cmd.py`
(3 miejsca po ~5 linii), testy: `test_pl_cutout.py`, `test_cli.py`,
`test_transport_mosaic.py`; docs: CLAUDE.md (N2 w "Ograniczenia" i `--country
auto` pkt: "same-nodata z kodem 0, bez komunikatu" -> "z `Warning:`"),
ARCHITECTURE 4.3, README, CHANGELOG. Kontrakt publiczny: `PlCutoutResult`
addytywnie.

---

## 5. Errata ADR-024 (D1) — proponowana tresc

Do wstawienia w `docs/DECISIONS.md` po istniejacej "Errata (2026-09-29, testy na
zywo — znany blad K2)" (`:919-954`), jako "**Errata 2 (fala naprawcza
2026-09-29, decyzja D1: tor CZ odmrozony)**":

1. **Rozstrzygniecie K2.** Potwierdzenie numeryczne: roznica EPSG:1622 −
   EPSG:4829 w EPSG:3045 wynosi kolo Cieszyna (+0,03; −1,16) m i w kaflu
   `302_5550` (+4,52; +2,03) m — to sa, co do 0,1 m i znaku, "1,25 m na
   poludnie" i "dE −4,50 / dN −2,00 (4,92 m)" z tabeli pomiarow ADR-024.
   Serwer liczyl `imageSR=3045` poprawnie; bledna byla lokalna referencja
   (operacja slowacka). Decyzja (a)-(g) ZOSTAJE (135 m dla `imageSR=2180`
   jest realne; operacja lokalna jest audytowalna w sidecarze), ale wybor
   operacji przestaje byc "najlepsza deklarowana dokladnosc": krok datum
   S-JTSK -> ETRS89/WGS 84 jest przypiety jawnie do EPSG:1622/1623
   (`transform/crs.py::DATUM_STEP_PINS`), bo obszary uzycia EPSG sa
   prostokatami i prostokat Slowacji obejmuje Morawy (z AOI Jaworzynka PROJ
   nadal stawia 4829 na czele), a AOI pusci pusta liste dla 5514 -> 2180 na
   zachod od 14,14°E. Sidecar: `transform.horizontal` "(1) ... (1.0 m)";
   pliki z "(3) ... (0.5 m)" pochodza sprzed naprawy (tresc przesunieta
   o 1-5 m) — `--force`/usunac. "Polityka" w (f): 1,0 m zamiast 0,5 m.
   `KNOWN_PATHS` 5514 <-> 2180: 1,0 m. Sekcja "Zywa weryfikacja fixu"
   (0,016/0,031 m, mediana szwu −0,086 m) mierzyla samozgodnosc — nie jest
   dowodem poprawnosci polozenia; dowodem jest pomiar L4 wzgledem NMT GUGiK
   1 m (Karkonosze: (−2,26; +0,61) m z 4829 -> (+0,38; −0,03) m z 1622).
2. **Uzupelnienie (d) — kafelkowanie (K6).** Realny limit `exportImage` to
   liczba pikseli (~8 Mpx; 7,5 OK / 8,38 500), nie 15000 x 4100 z metadanych.
   Klient kafelkuje z budzetem `MAX_EXPORT_PIXELS = 4 Mpx` (kafle
   kwadratowawe, kotwica NW, `merge` bez resamplingu — szwy bit w bit, L4
   S3b-d); limity per wymiar z metadanych zostaja jako sufity.
3. **Uzupelnienie "Konsekwencje" — siatka (N3).** Zasieg jest dociagany do
   kotwicy NW i calkowitej liczby pikseli w KAZDYM torze (pojedyncze zapytanie,
   kafle, warp); tor pojedynczy dawal dotad piksel `zasieg / round(...)`
   (2,0004-2,0005 m). Nazwa pliku i `request.bbox` niosa bbox sprzed snapu
   (roznica <= ½ px na krawedzi E/S).
4. **N2.** Wynik w calosci nodata (obszar poza pokryciem DMR) nie jest bledem
   (kod 0), ale CLI drukuje `Warning:`; wycinek PL analogicznie
   (`PlCutoutResult.all_nodata`).
5. Zdanie z `transform/raster.py:4-7` i ADR-027 ("tor CZ zweryfikowany na zywo
   — nie ruszamy go") traci moc (D1); po naprawie ponowne testy L4 (S-STYK,
   S3, S3e, S6, S2b) — oczekiwane: Karkonosze CZ vs GUGiK <= ~0,4 m, 10 x 10 km
   2 m przechodzi, piksel 2,000 m.

## 6. Minimalny zakres zmian w `providers/cuzk/*`

- `client.py`: `MAX_EXPORT_PIXELS`; warunek w `export_image` (`:142`); snap
  bboxa (`:139-141`, 4 linie); `_tile_grid` (`col_cap`/`row_cap`, `_splits`
  po liczbie czesci) — ~20 linii netto.
- `dmr.py`: ZERO zmian logiki (pin dziala w `transform/crs.py`); tylko
  komentarze `:53-56`, `:86-89`, docstring `:264-278`.
- `sheets.py`, `__init__.py`: bez zmian.
- Poza `providers/cuzk`: `transform/crs.py` (pin), `transport/mosaic.py`
  (helper N2), `download/cutout.py` (N2), `cli/download_cmd.py` (komunikat
  K2 x2, `Warning:` N2 x3).

## 7. Pliki `kartograf/`, ktore dotknie naprawa klastra CZ (kolizje)

| plik | zmiana | ryzyko kolizji z innymi klastrami |
|---|---|---|
| `kartograf/transform/crs.py` | `DATUM_STEP_PINS`, `_epsg_code`, `_operation_codes`, filtr w `build_pinned_transform`, `KNOWN_PATHS` (0.5 -> 1.0, nowe wpisy), komentarz `:159` | niskie (tylko CZ) |
| `kartograf/providers/cuzk/client.py` | K6 + N3 | brak |
| `kartograf/providers/cuzk/dmr.py` | komentarze/docstringi (K2) | brak |
| `kartograf/transport/mosaic.py` | nowy helper `has_valid_pixels` (na koncu modulu) | **S5** (klaster mozaiki edytuje `_snap_outward`/`merge` `:257-271`, `:324`) — dodatek addytywny, koordynowac kolejnosc |
| `kartograf/download/cutout.py` | `PlCutoutResult.all_nodata`, ~6 linii w `run_pl_cutout` po `:621` | **S5/N4/N9/K4** (ten sam modul: `:306-311`, `:482`, `:568-581`, `:609-642`, `:714`) — wysokie; jeden wlasciciel integracji |
| `kartograf/cli/download_cmd.py` | komunikaty `:678-682`, `:1642-1645`; `Warning:` N2 w `_cz_download_bbox`, `_cz_download_godlo`, `_download_pl_cutout` (`~:1060-1070`) | **S2/S3** (`_download_godlo_list`, `_dispatch_area`, `_country_bbox` `:284-347`, `:540-550`, `:863-919`, `:1159-1161`) — inne funkcje, ale ten sam plik |
| `kartograf/transform/raster.py` | tylko docstring `:4-7` (uzasadnienie niewspoldzielenia z CZ traci moc — opcjonalnie) | brak |

Poza `kartograf/`: `docs/DECISIONS.md` (errata ADR-024 §2), `docs/ARCHITECTURE.md`
(`:80-84`, `:729-735`, `:832-834`, sekcja CZ), `README.md` (`:212-216`),
`docs/CHANGELOG.md`, `CLAUDE.md` (Ograniczenia: K2, K6, N2, N3), `docs/PROGRESS.md`
(backlog), testy: `tests/test_transform_crs.py`, `tests/test_cuzk_dmr.py`,
`tests/test_cuzk_client.py`, `tests/test_pl_cutout.py`, `tests/test_cli.py`,
`tests/test_transport_mosaic.py`.
