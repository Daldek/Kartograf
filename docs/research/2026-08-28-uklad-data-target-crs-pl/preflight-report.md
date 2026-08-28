# Pre-flight — uklad data/ + --target-crs PL

**Audyt:** 2026-08-28, galaz `develop` @ `ae6d072`
**Plan:** `docs/superpowers/plans/2026-08-28-uklad-data-i-target-crs-pl.md` (3073 linie, 12 zadan)
**Spec:** `docs/superpowers/specs/2026-08-28-uklad-data-i-target-crs-pl-design.md` (350 linii)
**Pomiary wlasne:** `mypy kartograf/` = **33 bledy** (potwierdzone, ostatni to
`cli/download_cmd.py:1347`); pelnej suity NIE uruchamialem (zgodnie z zakresem).

Podsumowanie: **1 BLOKUJACY, 4 WAZNE, 12 DROBNYCH.** Warstwa mechaniczna planu
(numery linii, sygnatury, patch targety, slice'y sciezek) jest w **99 % zgodna
z repo** — sprawdzilem ~90 konkretow, rozjechane sa 4. Jeden defekt merytoryczny
(D-01) dotyczy samego projektu wycinka PL i najtaniej naprawic go PRZED
implementacja.

---

## 1. Defekty

### D-01 [BLOKUJACY] Wycinek PL nie ma zapasu po stronie zrodla — wynik ma nodata na krawedziach i kliny w rogach (asymetria z CZ)

- **Zadanie:** Zad. 8, Step 5b (`_prepare_pl_cutout` / `_build_pl_cutout`)
- **Co mowi plan:**
  ```python
  bbox_target = bbox_to_crs(bbox_2180, args.target_crs)
  ...
  mosaic_and_crop(sheet_paths, bbox_2180, tmp, nodata=_PL_NODATA, dst_kwds=...)
  warp_to_grid(tmp, target_path, bbox_target, pixel_size, pinned, src_crs="EPSG:2180", ...)
  ```
  czyli: **crop dokladnie do `bbox_2180`**, a warp do siatki `bbox_target`
  = OBWIEDNI obrazu `bbox_2180` w ukladzie docelowym.
- **Co jest w kodzie (wzorzec CZ, ktory plan deklaruje kopiowac):**
  `kartograf/providers/cuzk/dmr.py:92`
  ```python
  _WARP_MARGIN_PX = 4
  # Zapas obwiedni zadania natywnego w pikselach: pokrywa niepewnosc operacji
  # obwiedniowej (<= 2 m) i halo interpolatora bilinear (1 px) na krawedziach.
  ```
  `kartograf/providers/cuzk/dmr.py:310-320`
  ```python
  def _native_request_bbox(self, bbox: BBox) -> BBox:
      """Obwiednia zadania natywnego: cel przeliczony do 5514 plus zapas."""
      native = self._bbox_to_crs(bbox, NATIVE_CRS)
      margin = _WARP_MARGIN_PX * self._pixel_size
      return BBox(native.min_x - margin, ..., NATIVE_CRS)
  ```
  CZ idzie **od siatki docelowej do zrodla + margines**, wiec siatka wyniku jest
  w calosci pokryta danymi. Plan PL idzie **odwrotnie** (od zrodla do obwiedni),
  wiec pokrycie jest z definicji niepelne.
- **Skala zjawiska (pomiar wlasny, `bbox_to_crs` z repo):** dla przykladu,
  ktory plan sam dopisuje do CLAUDE.md
  (`--bbox 530000,382000,533000,386000 --target-crs EPSG:5514`):
  ```
  bbox_target (5514) = 3300.9 x 4223.5 m   (zadanie 3000 x 4000 m)
  back-envelope(2180) = 529696.7..533303.4 / 381772.5..386227.5
  overshoot: 303 m w X, 227 m w Y na kazda strone
  ```
  czyli ~**9 % powierzchni wyniku to puste kliny narozne o glebokosci do 300 m**,
  a dodatkowo halo bilinear zjada ~1 px z krawedzi FAKTYCZNIE zadanego obszaru
  (dokladnie ten efekt, ktory `_WARP_MARGIN_PX` neutralizuje po stronie CZ).
- **Skutek jesli nie naprawione:** ship w 0.7.0 rastrow PL z pustymi rogami
  i utrata skrajnego piksela zadanego obszaru; scenariusz specu 6.2 („dwa
  wycinki gotowe do nalozenia" na pograniczu) daje CZ w pelni wypelniony,
  a PL dziurawy — dokladne przeciwienstwo deklarowanej symetrii (spec 1 pkt 2,
  6.1). Zadne z testow planu tego nie wykryje: `test_target_5514_content_lt_1px`
  sprawdza tylko polozenie wierzcholka, `test_grid_matches_bbox_and_profile`
  tylko wymiary siatki.
- **Proponowana poprawka (minimalna):** dodac stala `_PL_WARP_MARGIN_PX = 4`
  i w `_build_pl_cutout` (galaz `pinned is not None`) ciac mozaike nie do
  `bbox_2180`, lecz do `bbox_to_crs(bbox_target, "EPSG:2180")` powiekszonego
  o `_PL_WARP_MARGIN_PX * pixel_size` (lustro `_native_request_bbox`); selekcje
  arkuszy w `_download_pl_bbox` oprzec na tym samym powiekszonym bboxie, zeby
  zapas mial pokrycie. Dopisac test: „kazdy piksel siatki wyniku odpowiadajacy
  punktowi wewnatrz zadanego bboxa ma wartosc != nodata".

---

### D-02 [WAZNY] „PELNA lista" churnu w Zad. 2 Step 5 pomija `tests/test_storage.py:427`

- **Zadanie:** Zad. 2, Step 5
- **Co mowi plan:** „PELNA lista miejsc, ktore pekaja (zweryfikowana na repo
  2026-08-28 — jesli pada cos poza nia, to przeoczony konsument)"; wymienia
  `:326, :350, :390, :397-405, :434, :602-607`.
- **Co jest w kodzie:** `tests/test_storage.py:422-427`
  ```python
  def test_resolution_subdir_nmt_1m(self, tmp_path):
      """Test that resolution='1m' maps to 'nmt_1m' subdirectory."""
      storage = FileStorage(tmp_path, resolution="1m")
      path = storage.get_path("N-34-130-D", ".asc")

      assert "/nmt_1m/" in str(path)
  ```
  To **blizniak** wymienionego `:434` (`assert "/nmt_5m/" in str(path)`) i pada
  dokladnie tak samo. Grep kontrolny (sekcja 4) potwierdza, ze to JEDYNE
  brakujace miejsce — reszta listy jest kompletna i trafna.
- **Skutek:** Zad. 2 Step 5 konczy sie czerwona suita mimo wykonania calej listy;
  deklaracja kompletnosci traci wiarygodnosc dla wykonawcy (ryzyko, ze zacznie
  szukac „przeoczonego konsumenta" w kodzie zamiast poprawic asercje).
- **Poprawka:** dopisac do listy `:427` -> `assert "/nmt/pl_1992_1m_evrf2007/" in str(path)`.

---

### D-03 [WAZNY] `TestBorderTwoCutouts` (Zad. 9 Step 1b) wola `main()` bez izolacji cwd — zasmieca korzen repo `.kartograf_cache.db`

- **Zadanie:** Zad. 9, Step 1b
- **Co mowi plan:** test wola `main(["download", "--bbox", ...])` bez `-q`
  i bez zadnej fixture; klasa nie ma odpowiednika `_isolate_cache`.
- **Co jest w kodzie:** `tests/test_cli.py:3697-3702` (klasa `TestAutoSplitBBox`)
  ```python
  @pytest.fixture(autouse=True)
  def _isolate_cache(self, tmp_path, monkeypatch):
      """MetadataCache laduje w cwd — poza repo i katalogiem wyjsciowym."""
      cwd = tmp_path / "cwd"
      cwd.mkdir()
      monkeypatch.chdir(cwd)
  ```
  a `kartograf/cli/download_cmd.py:1424` (`_cmd_download_cz`) bezwarunkowo robi
  `cache = MetadataCache()`. `tests/conftest.py` NIE izoluje cwd (izoluje tylko
  siec).
- **Skutek:** kazde uruchomienie nowego pliku `tests/test_pl_cutout.py` tworzy
  `.kartograf_cache.db` w korzeniu repo (stan wspoldzielony miedzy testami,
  zlamana konwencja, ktora repo juz jawnie stosuje).
- **Poprawka:** przeniesc fixture `_isolate_cache` (kopia z `TestAutoSplitBBox`)
  do `TestBorderTwoCutouts` w `tests/test_pl_cutout.py`.

---

### D-04 [WAZNY] Zad. 11 Step 7: druga weryfikacja („zero trafien" w CHANGELOG) jest z gory falszywa

- **Zadanie:** Zad. 11, Step 7
- **Co mowi plan:**
  ```
  Run: sed -n '8,519p' docs/CHANGELOG.md | grep -n "nmt_1m\|nmt_5m\|cz_dmr5g\b\|laz/<"
  Expected: zero trafien
  ```
- **Co jest w kodzie:** `docs/CHANGELOG.md:62`
  ```
    `pl.gugik.nmt_1m` deklaruje juz tylko `EPSG:9650`. Dotad zapytanie
  ```
  To **klucz deskryptora**, nie sciezka — dokladnie ten sam wyjatek, ktory plan
  poprawnie przewiduje w PIERWSZYM grepie („jedyne dozwolone trafienie to klucz
  deskryptora `pl.gugik.nmt_1m`"), ale w drugim juz nie. Uruchomienie grepa dzis
  daje 5 trafien (offsety sed 55/115/208/239/423 = linie 62/122/215/246/430);
  po poprawkach Step 2c-2d zostaje trafienie z linii 62.
- **Skutek:** wykonawca dostaje falszywy alarm w bramie dokumentacyjnej i moze
  „poprawic" poprawny klucz deskryptora w CHANGELOG-u (regresja tresci).
- **Poprawka:** dopisac `| grep -v "pl.gugik.nmt_1m"` albo zmienic Expected na
  „jedyne trafienie: `pl.gugik.nmt_1m` w linii 62 (klucz zrodla, nie sciezka)".

---

### D-05 [WAZNY] Zad. 11 Step 6: numery linii w `docs/PROGRESS.md` sa nieaktualne o ~58 linii (plan przesunal je wlasnym commitem)

- **Zadanie:** Zad. 11, Step 6
- **Co mowi plan:** „W backlogu A1-9 (linie ~683-686) oznacz jako wykonane".
- **Co jest w kodzie:** `docs/PROGRESS.md:741-744`
  ```
  - [ ] A1-9 — rozdzielenie katalogow PL-2000 (`nmt_2000_<res>` wg ADR-017)
        odlozone — zmienilaby uklad katalogow istniejacych uzytkownikow
        (`skip_existing` polega na dzisiejszych sciezkach); dzis wspolny
        `nmt_2000_1m`.
  ```
  Weryfikacja przyczyny: `git show 6cb662d:docs/PROGRESS.md | grep -n "A1-9"`
  -> `683`. Commit `ae6d072` („docs(progress): sesja 2026-08-28") wstawil sekcje
  sesji i przesunal backlog o 58 linii JUZ PO napisaniu planu.
- **Skutek:** nie zlamie niczego (plan cytuje tresc, wiec zakotwiczenie dziala),
  ale to jedyny blok planu, ktorego numeracja rozjechala sie systemowo —
  pozostale odwolania do PROGRESS („Nastepne kroki", „## Backlog") sa przesuniete
  tak samo i nie zostaly przeliczone.
- **Poprawka:** w Zad. 11 Step 6 zastapic numery linii kotwicami tekstowymi
  (`- [ ] A1-9`, `## Backlog`, „Nastepne kroki") albo przeliczyc na 741-744.

---

### D-06 [DROBNY] Dwie linie testow z Zad. 2 Step 6 przekraczaja `line-length = 88` (ruff E501)

- **Zadanie:** Zad. 2, Step 6 (`tests/test_sources_registry.py`)
- **Co mowi plan:**
  - nmpt (292): `assert d.resolve_subdir(vertical_crs="EVRF2007") == FileStorage(tmp_path, product="nmpt")._subdir` — **105 znakow**
  - laz (314): `assert d.resolve_subdir(vertical_crs="EVRF2007") == FileStorage(tmp_path, product="laz")._subdir` — **104 znaki**
- **Co jest w kodzie:** `pyproject.toml:55` `line-length = 88`, `pyproject.toml:58`
  `select = ["E", "F", "I", "UP", "B", "SIM"]` (E501 aktywne).
- **Skutek:** `ruff check` w Zad. 2 Step 9 pada; `ruff format --check` tez.
- **Poprawka:** rozbic na dwie linie (`storage = FileStorage(...)` + `assert`),
  jak zrobiono dla nmt_1m/nmt_5m.

### D-07 [DROBNY] Komentarz `_APEX_2180 = (530050.0, 382050.0)  # okolice Cieszyna (pas przygraniczny)` jest faktycznie bledny

- **Zadanie:** Zad. 7 Step 1 i Zad. 8 Step 1 (dwa pliki testowe)
- **Co mowi plan:** `# EPSG:2180, okolice Cieszyna (pas przygraniczny — realny teren celu 5514)`
- **Pomiar:** `Transformer.from_crs("EPSG:2180","EPSG:4326").transform(530050, 382050)`
  -> **(19.4312 E, 51.3043 N)** — okolice Piotrkowa Trybunalskiego, ~200 km od
  granicy CZ. Pas przygraniczny (Cieszyn) to w Krovaku ~(-447000, -1114000),
  czyli 2180 ~ (480000, 200000) — patrz `tests/test_cli.py:2909`.
- **Skutek:** funkcjonalnie nic (operacja 2180->5514 istnieje i ma 0,5 m
  w tym punkcie — zweryfikowane), ale komentarz uzasadniajacy wybor punktu
  trafia do dwoch nowych plikow testowych jako trwala dezinformacja.
- **Poprawka:** usunac wzmianke o Cieszynie albo zmienic punkt na faktycznie
  przygraniczny.

### D-08 [DROBNY] Zad. 3 Step 2: „Expected: FAIL" dla dwoch testow, a pada tylko jeden

- **Co mowi plan:** „Step 2: Uruchom — musza padac ... Expected: FAIL — `_subdir`
  konczy sie `_evrf2007` w tescie KRON86".
- **Stan:** `test_default_storage_5m_kron86_corrected_to_evrf` oczekuje
  `nmt/pl_{uklad}_5m_evrf2007`, a po Zad. 2 manager przekazuje surowy szablon
  i `FileStorage` wypelnia `{vcrs}` swoim defaultem `EVRF2007` — czyli test jest
  ZIELONY jeszcze przed Zad. 3.
- **Skutek:** falszywe RED w cyklu TDD; test jest wylacznie regresja (co jest OK,
  ale plan powinien to powiedziec — robi tak swiadomie w Zad. 9 Step 2).

### D-09 [DROBNY] `_resolved_subdir`: warunek `system is not None` jest martwy

- **Co mowi plan (Zad. 2 Step 3e):**
  `uklad = "2000" if system is not None and system.id == "pl2000" else "1992"`
- **Co jest w kodzie:** `kartograf/core/parser_registry.py:118-126` — ostatni
  zarejestrowany system to `pl1992` z `detect=lambda godlo: True  # fallback`,
  wiec `detect_system()` nigdy nie zwraca `None`.
- **Skutek:** martwa galaz (rubryka review: martwy kod). Repo ma precedens
  (`download_cmd.py:610-613` robi to samo z komentarzem „None tylko gdyby rejestr
  byl pusty") — jesli zostaje, warto ten komentarz powtorzyc. Uboczna korzysc:
  linia ma 86 znakow, wiec po skroceniu przestaje ocierac sie o limit.

### D-10 [DROBNY] `_prepare_pl_cutout` buduje operacje przypieta DWA razy

- **Co mowi plan (Zad. 8 Step 5b):** najpierw `build_pinned_transform("EPSG:2180",
  args.target_crs, TransformPolicy(min_accuracy_m=1.0, probe_point=center, ...))`,
  potem `bbox_to_crs(bbox_2180, args.target_crs)` — a `bbox_to_crs`
  (`providers/cuzk/dmr.py:577-582`) buduje **wlasna** operacje, gdy `pinned=None`.
- **Skutek:** dwa przebiegi `TransformerGroup` (kosztowne) i dwie polityki
  (1,0 m vs `_ENVELOPE_POLICY` 2,0 m) dla tej samej pary ukladow. Funkcja
  przyjmuje `pinned` jako 3. argument — wystarczy go podac.
- **Poprawka:** `bbox_to_crs(bbox_2180, args.target_crs, pinned)`.

### D-11 [DROBNY] Polityka transformacji wycinka PL jako literal zamiast stalej

- **Co mowi plan:** `TransformPolicy(min_accuracy_m=1.0, probe_point=center, allow_network_grids=False)`
  wpisane inline, z komentarzem „polityka jak `_HORIZONTAL_POLICY` toru CZ".
- **Co jest w kodzie:** `kartograf/providers/cuzk/dmr.py:89`
  `_HORIZONTAL_POLICY = TransformPolicy(min_accuracy_m=1.0, allow_network_grids=False)`
  — CZ ma na to nazwana stala.
- **Skutek:** rubryka review „magic number bez stalej"; rozjazd limitu miedzy
  torami PL i CZ przy przyszlej zmianie.

### D-12 [DROBNY] `_download_pl_geometry(..., bbox=None)` + `--target-crs` = `AttributeError` bez guardu

- **Zadanie:** Zad. 9 Step 3a
- **Stan:** nowy parametr jest opcjonalny („stare wywolania pozycyjne dzialaja"),
  ale galaz `cutout` bezwarunkowo wola `_prepare_pl_cutout(args, bbox, ...)`,
  ktore od razu czyta `bbox.crs`. Dzis nieosiagalne (jedyny wolajacy —
  `_dispatch_area:497-498` — zawsze poda `bbox=part`), ale to utajony traceback
  zamiast komunikatu CLI.
- **Poprawka:** `if args.target_crs is not None and bbox is None: raise ValidationError(...)`
  albo uczynic parametr wymaganym.

### D-13 [DROBNY] Wycinek buduje sciezke z pominieciem walidatora `_ensure_resolved`

- **Zadanie:** Zad. 8 Step 5b
- **Stan:** `target_path = Path(args.output) / subdir / "bbox" / f"{coords}.tif"`
  — omija `FileStorage`, wiec kontrakt „zero klamer w segmencie" (spec 4,
  Zad. 2 Produces) nie obowiazuje na tej sciezce. Dzis bezpieczne (oba wymiary
  podane jawnie), ale to jedyne miejsce w kodzie budujace segment poza
  `FileStorage` — identyczny wzorzec ma juz `_cz_download_bbox:1346-1351`.

### D-14 [DROBNY] Komentarz przy `if failed_sheets: return 1` sugeruje zachowanie zalezne od flagi

- **Zadanie:** Zad. 8 Step 5c
- **Co mowi plan:**
  ```python
  if failed_sheets:
      # z --target-crs: wycinek wymaga kompletu pokrycia (spec 6.1 pkt 1)
      return 1
  ```
- **Co jest w kodzie:** `kartograf/cli/download_cmd.py:981-983` — ten `return 1`
  istnieje juz dzis i dziala BEZ wzgledu na `--target-crs`. Komentarz sugeruje
  warunkowosc, ktorej nie ma.

### D-15 [DROBNY] Zad. 10 dokumentuje ADR-026/027, ktore powstaja dopiero w Zad. 11

- **Zadanie:** Zad. 10 Step 1 sekcja 6 („Indeks ADR — lista ADR-001..ADR-027")
- **Stan:** `docs/DECISIONS.md` ma dzis ADR-001..ADR-025 (`grep "^## ADR-"`:
  linie 8..802; 925 to naglowek WEWNATRZ komentarza-szablonu). Zad. 11 Step 1
  dopiero je dopisuje. Kolejnosc zadan powoduje, ze `ARCHITECTURE.md` przez
  jeden commit odsyla do nieistniejacych ADR-ow.
- **Uwaga poboczna:** plan mowi „skopiuj naglowki z `docs/DECISIONS.md` ... linie
  DECISIONS.md:8-925" — zakres 8-925 wciaga naglowek szablonu `## ADR-XXX: Tytul`
  (linia 925, wewnatrz `<!-- ... -->`). Zawezic do 8-802.

### D-16 [DROBNY] Rozjazd plan-vs-spec nieodnotowany w „Odstepstwach": tabela sidecara w README

- **Spec 10.3:** „README.md: ... tabela sidecara (wiersz dla wycinka PL)".
- **Plan Zad. 11 Step 4:** „Zadnych nowych wierszy — sidecar nie ma pola
  `capability`" (poprawia zamiast tego tresc wierszy `horizontal_crs`/`transform`).
- **Weryfikacja:** `ResultMetadata` (`kartograf/sources/sidecar.py:23-42`)
  faktycznie NIE ma pola `capability` — decyzja planu jest merytorycznie
  sluszna, ale to rozjazd z litera specu poza sekcja „Odstepstwa od litery specu",
  wiec review nie ma go gdzie zobaczyc.

### D-17 [DROBNY] Drobne przesuniecia numeracji (bez wplywu na wykonanie)

| Miejsce w planie | Plan | Repo |
|---|---|---|
| `test_sources_registry.py` `TestDescriptorProviderConsistency` | 237-334 | **236**-334 |
| `docs/DECISIONS.md` ADR-023 pkt 5 „ZACZYNA sie na linii" | 597 | **596** |
| `docs/SCOPE.md` ostatni wiersz historii `\| 2026-08-22 \| 3.8 \|` | ~488 | **487** |
| `docs/SCOPE.md` stopka `**Wersja dokumentu:**` | ~492-493 | **491-492** |
| spec 12 „`storage_subdir` uzywany w download_cmd.py x3" | x3 | **x2** (1262, 1348) |

---

## 2. Tabela interfejsow miedzy zadaniami

| Zadanie A | Zadanie B | Wspolny plik / interfejs | Produkuje | Konsumuje | Werdykt |
|---|---|---|---|---|---|
| 1 | 2 | `SourceDescriptor.resolve_subdir` | `(*, uklad=None, vertical_crs=None) -> str`, `str.replace`, `.lower()`, `ValueError` gdy `storage_subdir is None` | CZ CLI: `resolve_subdir(vertical_crs=provider.vertical_crs)`; asercje rejestru | **ZGODNY** |
| 1 | 3 | j.w. | j.w. | `get_source(key).resolve_subdir(vertical_crs=vertical_crs)` (po korekcie 5m=>EVRF2007, `manager.py:189-195`) | **ZGODNY** |
| 1 | 5 | j.w. | j.w. | `resolve_subdir(uklad=_laz_uklad(tile), vertical_crs=args.vertical_crs)` | **ZGODNY** |
| 1 | 8 | j.w. | j.w. | `resolve_subdir(uklad="1992", vertical_crs=<provider>)` — `uklad` twardo, bo `--system 2000` odrzucone | **ZGODNY** |
| 2 | 3 | `FileStorage(vertical_crs=)` (5. param kw, default `"EVRF2007"`) | `_subdir` = szablon z wypelnionym `{vcrs}` | manager przekazuje `vertical_crs=` + gotowy subdir | **ZGODNY** |
| 2 | 4 | j.w. | j.w. | `FileStorage(..., vertical_crs=getattr(provider,"vertical_crs", vertical_crs))` | **ZGODNY** (fabryka `create_nmt_provider` faktycznie koryguje 5m=>EVRF2007, `providers/pl/__init__.py:36-41`) |
| 2 | 5 | `FileStorage(subdir=)` bez klamer + `_ensure_resolved` | `ValidationError` przy nierozwiazanym `{...}` | subdir juz w pelni rozwiazany przez `resolve_subdir` | **ZGODNY** |
| 2 | 8, 9 | budowa sciezki wycinka | `_ensure_resolved` w `FileStorage` | wycinek sklada `Path(args.output)/subdir/"bbox"/...` **poza** `FileStorage` | ZGODNY funkcjonalnie, patrz **D-13** |
| 6 | 8 | `mosaic_and_crop(dst_kwds=)` | `dict\|None` scalane nad `nodata` | `{"driver": "GTiff", "crs": "EPSG:2180"}` | **ZGODNY** — zweryfikowane empirycznie: wejscia AAIGrid (`crs=None`, `res=(1,1)`) daja GTiff/EPSG:2180/nodata -9999, `bounds == (1,1,7,3)` |
| 7 | 8 | `warp_to_grid(src, dst, bbox, pixel_size, pinned, *, src_crs, nodata)` | funkcja modulowa | wywolanie 1:1 z `bbox_target`, `_PL_PIXEL_SIZES[...]`, `src_crs="EPSG:2180"`, `nodata=_PL_NODATA` | **ZGODNY** |
| 7 | 8 | pokrycie siatki wyniku danymi | siatka = `bbox_target` | zrodlo = crop do `bbox_2180` | **ROZJAZD — D-01** |
| 8 | 9 | `_PlCutout`, `_prepare_pl_cutout`, `_finalize_pl_cutout` | dataclass frozen + 3 funkcje | tryb geometry wola je 1:1, dokladajac `bbox=` | ZGODNY, patrz **D-12** |
| 8 | 9 | usuniecie krotki `PL + target_crs` z `_validate_cross_country` | Zad. 8 Step 4a (a nie Zad. 9) | Zad. 9 zaklada, ze juz usunieta | **ZGODNY** — plan swiadomie przesuwa to do Zad. 8 i uzasadnia (testy `main()` z Zad. 8 ida przez `_dispatch_area`) |
| 8 | tryb godlowy | walidacja „target-crs tylko z bbox/geometry" | wstawka pod `download_cmd.py:625-626` | — | **ZGODNY** — zweryfikowane: linia 625 `if _resolve_pl_sentinels(args):` lezy w `if has_godlo:` (8 spacji), a 632-634 to juz `if has_geometry:`; ostrzezenie planu jest trafne |
| 8 | LAZ | walidacje `--target-crs` w `_resolve_pl_sentinels` | 2 nowe checki | `_cmd_download_laz` wola sentinele (`download_cmd.py:1091`) PRZED reszta | **ZGODNY** — `test_non_nmt_rejected[laz]` zadziala, mimo ze LAZ omija `_dispatch_area` |
| 8 | 6 | `_PL_PIXEL_SIZES` vs faktyczna rozdzielczosc arkuszy | `{"1m":1.0,"5m":5.0}` | brak sprawdzenia zgodnosci z `res` mozaiki | DROBNY — `mosaic_and_crop` i tak odrzuca niezgodne `res` wejsc |
| 2 | 3 (sekwencja) | LAZ miedzy commitami | `laz/pl_<uklad>_evrf2007` (default FileStorage) | Zad. 5 domyka | **ZGODNY** — plan odnotowuje efekt uboczny; warto dodac, ze przez ten commit takze `{uklad}` bierze sie z formatu godla, a nie z `uklad_xy` kafla |

---

## 3. Weryfikacja cytatow (per zadanie)

Legenda: ZGODNY = pod wskazana linia jest dokladnie to, co plan mowi.

| Zad. | Cytat planu | Stan w repo | Werdykt |
|---|---|---|---|
| 1 | `descriptor.py` — pole `auth`, „linia ~81" | `descriptor.py:80` `auth: str = "none"` | ZGODNY |
| 1 | „`pytest` jest juz importowany w tym pliku" | `test_sources_registry.py` uzywa `pytest.raises` (:78) | ZGODNY |
| 1 | `ValueError, match="test.key"` | `re.search("test.key", "Zrodlo 'test.key' nie ma...")` trafia | ZGODNY |
| 2 | `registry.py:93,114,134,153,173,264,311` = `storage_subdir=` | dokladnie te 7 linii (grep) | ZGODNY |
| 2 | `descriptor.py:76` komentarz pola | `storage_subdir: str \| None  # None dla zrodel LandCoverManagera` | ZGODNY |
| 2 | `download_cmd.py:1262` `FileStorage(args.output, subdir=descriptor.storage_subdir)` | identycznie | ZGODNY |
| 2 | `download_cmd.py:1346-1351` blok `target = (Path(args.output) / descriptor.storage_subdir / "bbox" / ...)` | identycznie | ZGODNY |
| 2 | `test_storage.py:326` `expected_parts = ["nmt_1m", ...]` | identycznie | ZGODNY |
| 2 | `test_storage.py:350` `common_parent = tmp_path / "nmt_1m" / ...` | identycznie | ZGODNY |
| 2 | `test_storage.py:390` `assert "nmt_1m" in parts` | identycznie | ZGODNY |
| 2 | `test_storage.py:397-405` spacer `expected_parts = ["orto", ...]` | literal na **:398** | ZGODNY |
| 2 | `test_storage.py:434` `assert "/nmt_5m/" in str(path)` | identycznie | ZGODNY |
| 2 | `test_storage.py:602-607` oba asserty `TestSubdirOverride.test_none_keeps_legacy_behavior` | def :602, asserty :603-608 | ZGODNY |
| 2 | „`test_storage.py:427`" | **NIE WYSTEPUJE W PLANIE**, a pada | **ROZJAZD (D-02)** |
| 2 | „`TestFileStorageGetRawPath` (:556-575) — slice'y liczone OD KONCA, indeksy sie nie zmieniaja" | :558 `parts[-8:-1]`, :573 `parts[-6:-1]`, :556/:575 `"laz" in parts` | ZGODNY (analiza trafna) |
| 2 | „`FileStorage(subdir="cz_dmr5g")` literal (test_storage:588)" | :588 identycznie | ZGODNY |
| 2 | „`TestFileStoragePL2000` — `product="nmt_2000_1m"` to passthrough" | :442..:539, passthrough dziala | ZGODNY |
| 2 | `test_sources_registry.py:151,190,212` | `== "nmt_1m"`, `== "cz_dmr5g"`, `== "cz_dmr4g"` | ZGODNY |
| 2 | `test_sources_registry.py:~74` (`test_descriptor_frozen`) | :74 `storage_subdir="nmt_1m",` | ZGODNY (zmiana opcjonalna — deskryptor lokalny, nie z rejestru) |
| 2 | `TestDescriptorProviderConsistency (237-334)`, punkty 247/279/292/305/314/331 | klasa od **236**; wszystkie 6 numerow asercji dokladne | ZGODNY (klasa off-by-one, D-17) |
| 2 | `test_cuzk_dmr.py:1016-1017` | `storage = FileStorage(tmp_path, subdir=d.storage_subdir)` / `assert storage._subdir == d.storage_subdir` | ZGODNY |
| 2 | `test_download_manager.py:137,155,167,176` = `"nmpt"/"orto"/"nmt_5m"/"nmt_1m"` | identycznie; :188 (`"custom"`) slusznie pominiete | ZGODNY |
| 2 | `test_integration.py:92` `common_parent = test_data_dir / "nmt_1m" / ...` | identycznie | ZGODNY |
| 2 | test_cli.py CZ: 2825, 2833, 2867, 2885, 2892(-2919), 2939, 3057, 3062, 3074, 3097, 3120, 3213 | grep `cz_dmr5g\|cz_dmr4g` daje **dokladnie te 12** linii (literal bboxa na :2909) | ZGODNY — lista KOMPLETNA |
| 2 | „`_cz_provider_mock` ustawia `vertical_crs = "Bpv"`, test_cli.py:2774" | :2774 identycznie | ZGODNY |
| 2 | „WYJATEK: `provider.vertical_crs = "EVRF2007"` na linii ~3086" | :3086 identycznie (`test_evrf2007_transform_lands_in_sidecar`) | ZGODNY |
| 3 | `manager.py:200-210` galaz `storage is None` | :200-209 dokladnie w cytowanej postaci | ZGODNY |
| 3 | `manager.py:170-173` docstring `storage` | „comes from the provider's source descriptor (`storage_subdir`)" na :171-173 | ZGODNY |
| 3 | „korekta 5m=>EVRF2007 w liniach 189-195" | :189-195 identycznie | ZGODNY |
| 4 | `download_cmd.py:60-90` `_create_provider_and_storage` | :60-90 dokladnie | ZGODNY |
| 4 | „testy fabryki, okolice 1086-1107" i „`_create_provider_and_storage` NIE jest importowane na poziomie modulu" | `TestCreateProviderAndStorage` od :1065; kazdy test robi `from kartograf.cli.commands import ...` lokalnie | ZGODNY |
| 5 | `download_cmd.py:1071-1185` `_cmd_download_laz` | dokladnie | ZGODNY |
| 5 | „zamien (linia ~1125-1126) `provider = GugikLazProvider(...)` / `storage = FileStorage(output_dir, product="laz")`" | :1125-1126 dokladnie | ZGODNY |
| 5 | „w `_fetch` (linia ~1145) `target = storage.get_raw_path(...)`" | :1145 dokladnie; `storage` nie jest uzywane nigdzie indziej | ZGODNY |
| 5 | „komunikat `to {output_dir / 'laz'}` zostaje" | :1177 | ZGODNY |
| 5 | „fixtury maja `crs="PL-2000:S6"`", `test_laz_writes_sidecar_next_to_tile` ~2585-2625 | `_fake_tiles` :2441-2465 z `crs="PL-2000:S6"`; test :2586-2626, szuka przez `rglob` | ZGODNY |
| 5 | `LazTile(godlo, url, year, density, crs, min_x, min_y, max_x, max_y)` | `gugik_laz.py:81-89` dokladnie te pola | ZGODNY |
| 6 | `transport/mosaic.py:19-60` | funkcja `mosaic_and_crop` :19-60 | ZGODNY |
| 6 | „`rasterio.merge.merge(dst_kwds=)` (istniejace)", „ASC-owego helpera na pewno nie ma" | `_write_tile` (GTiff) :17-40; brak ASC | ZGODNY |
| 7 | „wzorzec `providers/cuzk/dmr.py::_warp_to_grid`, linie 500-561" | def na :500, `bbox_to_crs` na :564 | ZGODNY |
| 7 | „`PinnedTransform.gdal_operation()`, `.transform`, `.description`, `.accuracy_m`" | `transform/crs.py:57-108` | ZGODNY |
| 7 | „operacja 2180->5514 jest w PROJ bez siatek zewnetrznych" | zmierzone: acc **0,5 m**, opis `axis order change (2D) + Inverse of Poland CS92 + ... + Krovak East North`; 3045 i 2180 tez dostepne (0,0 m) | ZGODNY |
| 8 | `_validate_cross_country (:347-401)` + cytowana krotka | :347-401; krotka `("PL" in countries and getattr(args,"target_crs",None) is not None, ...)` na :391-394 | ZGODNY |
| 8 | `_resolve_pl_sentinels (:111-166)` + blok do usuniecia | :111-166; blok `if getattr(args,"target_crs",None) is not None:` na :160-165, tresc 1:1 | ZGODNY |
| 8 | „chodzi o `if _resolve_pl_sentinels(args): return 1` WEWNATRZ `if has_godlo:` (:625-626, 8 spacji), a NIE o 632-634" | :625-626 w `if has_godlo:`; :629 `if product == "laz":`, :633 `if has_geometry:` | ZGODNY — ostrzezenie trafne i wartosciowe |
| 8 | `_download_pl_bbox (:897-985)` | dokladnie | ZGODNY |
| 8 | `_parser.py:110-117` (help `--target-crs`) | blok `add_argument("--target-crs", ...)` = linie **110-117** | ZGODNY |
| 8 | `test_cli.py:3369-3399` (2 testy) i `:4191-4199` | `test_pl_godlo_with_target_crs_rejected` :3369-3381 (`assert "natywnie"` :3381); `test_pl_bbox_with_target_crs_rejected` :3383-3399; `test_border_bbox_with_target_crs_rejected_before_any_download` dekorator :4191, def :4192-4199 | ZGODNY |
| 8 | „`_download_godlo_list` zwraca `(all_paths, failed_sheets)`; sciezki obejmuja tez arkusze skipniete" | `download_cmd.py:755-761` sygnatura; `manager.py:301-303` zwraca `target_path` przy skipie | ZGODNY |
| 8 | „`bbox_to_crs` istniejaca, generyczna: probkuje krawedzie" | `providers/cuzk/dmr.py:564-598`, `_EDGE_SAMPLES = 9` | ZGODNY |
| 8 | „`_print_transform_error` (istniejacy: drukuje blad + Remedium, zwraca 1)" | `download_cmd.py:196-203` | ZGODNY |
| 8 | „`meta.horizontal_crs = ...` / `meta.transform = ...`" | `ResultMetadata` to `@dataclass(kw_only=True)` — mutowalna (`sidecar.py:23`) | ZGODNY |
| 8 | test: `payload["vertical_crs"] == "EPSG:9651"` dla kanalu `sheet_files` + `vertical_crs="EVRF2007"` | `resolve_vertical_crs("EVRF2007", ("EPSG:9650","EPSG:9651"))`: 5621 -> rodzina -> **9651** (`registry.py:383-391`) | ZGODNY |
| 8 | test: `cut.target_path.name.startswith("-")` dla 5514 | 2180(530010,382010) -> 5514 ~ (-376776, -945224) | ZGODNY |
| 8 | test: `400000 < cut.bbox_2180.min_x < 700000` dla bboxa WGS84 18.60/49.75 | zmierzone: `min_x = 471193` | ZGODNY |
| 8 | „usuniecie blokady krzyzowej nie psuje `test_auto_with_*_resolves_to_pl`, bo `_pl_only_flags` nigdy nie zawieral target-crs" | `download_cmd.py:404-428` — brak `target_crs` | ZGODNY |
| 9 | `_dispatch_area (:497-498)` | :497 `if filepath is not None:`, :498 `rc = _download_pl_geometry(pl_args, filepath, parent_request)` | ZGODNY |
| 9 | `_download_pl_geometry (:1533-1620)` | dokladnie | ZGODNY |
| 9 | „patch `kartograf.core.geometry.find_sheets_for_geometry` — ta sama konwencja co testy geometry w test_cli.py" | import lokalny :1541; test_cli patchuje tak w 8 miejscach (:1425, :1807, ...) | ZGODNY |
| 9 | `_CZ_FACTORY_PATCH = "kartograf.providers.cuzk.create_dmr_provider"` | `test_cli.py:2801` | ZGODNY |
| 9 | „obwiednie: CZ 12.09..18.86E / 48.55..51.06N, PL 14.07..24.20E / 49.00..54.90N" | `test_sources_registry.py:181` potwierdza CZ; `_BBOX = "18.80,49.70,18.801,49.7005"` lezy w obu | ZGODNY |
| 9 | „`--resolution 5m` nie rozstrzyga `--country auto` do PL" | `_pl_only_flags` reaguje tylko na `1m` (:426) | ZGODNY |
| 11 | „DECISIONS.md: wstaw PRZED linia 923 (`<!-- Szablon nowej decyzji:`), bo `## ADR-XXX` z 925 lezy juz w komentarzu" | :923 i :925 dokladnie | ZGODNY — ostrzezenie trafne |
| 11 | „koniec ADR-013 (~230)", „koniec ADR-017 (~299)", „`## ADR-024:` linia 635" | ADR-013 :215 (ADR-014 :232), ADR-017 :285 (ADR-018 :303, „Konsekwencje" :299), ADR-024 :635 | ZGODNY |
| 11 | „ADR-023 pkt 5 ZACZYNA sie na linii 597" | faktycznie **596** | ROZJAZD (D-17) |
| 11 | CHANGELOG: `[0.7.0]` 8-518, Breaking :10, Added :126, Changed :244, wpis d68be23 :245-250, korekty :122/:215/:430, 0.5.0 :595-599 | wszystkie dokladne (`[0.6.1]` zaczyna sie na :519) | ZGODNY |
| 11 | README: :160, :179, :186, :190, tabela sidecara :136-147 (`horizontal_crs` :139, `transform` :146), struktura :294-312, stopka :353 | wszystkie dokladne | ZGODNY |
| 11 | SCOPE: 2.2 linie 92-93; drzewo `transform/` na **371-372**, NIE 396 (`storage.py`); `_parser.py` :405 | :371 `├── transform/`, :372 `│   └── crs.py`, :396 `│   └── storage.py`, :405 `├── _parser.py` | ZGODNY — ostrzezenie trafne co do znaku |
| 11 | PROGRESS: „backlog A1-9 (linie ~683-686)" | faktycznie **741-744** | **ROZJAZD (D-05)** |
| 12 | „README.md:353 (stopka)" | `**Wersja 0.7.0-dev** ... 1716 testow, pokrycie 93%` | ZGODNY |
| 12 | „`DEVELOPMENT_STANDARDS.md`: jesli wymienia liczbe plikow testowych" | :323 `├── tests/  # 30 plikow testowych + conftest.py + fixtures/ (1716 testow)`; `ls tests/test_*.py` = **30** | ZGODNY (uwaga: na tej samej linii jest tez liczba testow) |
| Global | „Baseline: 33 bledy mypy, znika `download_cmd.py:1347`" | zmierzone: **33**, ostatni to `download_cmd.py:1347: Unsupported operand types for "/" ("Path" and "None")`; `resolve_subdir() -> str` go usuwa | ZGODNY |

---

## 4. Kompletnosc list churnu

### 4.1 Stare literaly sciezkowe w `tests/` i `kartograf/`

Grep: `nmt_1m|nmt_5m` (bez `pl.gugik.nmt_*`) + `cz_dmr5g|cz_dmr4g` + `"nmpt"|"orto"|"laz"` + `nmt_2000_1m`.

**`tests/test_storage.py` — pelna klasyfikacja (13 trafien):**

| Linia | Tresc | Los po zmianie | W planie? |
|---|---|---|---|
| 326 | `expected_parts = ["nmt_1m", ...]` | PEKA | TAK |
| 350 | `common_parent = tmp_path / "nmt_1m" / ...` | PEKA | TAK |
| 372-373 | `"nmpt" in parts`, `"nmt_1m" not in parts` | przechodzi (373 staje sie trywialnie prawdziwe) | TAK (tylko 372) |
| 381 | `"orto" in parts` | przechodzi | TAK |
| 390 | `"nmt_1m" in parts` | PEKA | TAK |
| 398 | `expected_parts = ["orto", ...]` | PEKA | TAK |
| **427** | **`assert "/nmt_1m/" in str(path)`** | **PEKA** | **NIE — D-02** |
| 434 | `assert "/nmt_5m/" in str(path)` | PEKA | TAK |
| 442-539 | `product="nmt_2000_1m"` (9 miejsc) | przechodzi (passthrough) | TAK (jawnie „nie ruszaj") |
| 492 | `product="nmt_1m"` | przechodzi (passthrough) | TAK |
| 556, 575 | `"laz" in parts` | przechodzi | TAK („nie ruszaj") |
| 558, 573 | `parts[-8:-1]`, `parts[-6:-1]` | przechodzi (slice od konca) | TAK („nie ruszaj") |
| 588, 592, 599, 611 | `subdir="cz_dmr5g"` / `subdir="wlasny"` | przechodzi (override bez klamer) | TAK |
| 602-608 | `nmt_1m` / `nmpt` w `test_none_keeps_legacy_behavior` | PEKA | TAK |

**`tests/test_cli.py` — CZ:** grep `cz_dmr5g|cz_dmr4g` daje **dokladnie 12** linii
(2825, 2833, 2867, 2885, 2909, 2939, 3057, 3062, 3074, 3097, 3120, 3213).
Lista planu (Step 8) pokrywa **wszystkie 12**, w tym rozroznia jedyny przypadek
`cz_dmr5g_evrf2007` (:3097) i poprawnie identyfikuje 3 testy, ktore SAME tworza
plik pod stara sciezka (3062, 3074, 3120) oraz asercje `not ... .exists()`
(3057), ktora bez poprawki stalaby sie trywialna. **Lista kompletna i trafna.**

**Pozostale pliki:**

| Plik:linia | Tresc | Wplyw | W planie? |
|---|---|---|---|
| `test_sources_registry.py:74,151,190,212,247,279,292,305,314` | asercje `storage_subdir` | PEKA | TAK (wszystkie) |
| `test_sources_registry.py:331` | `storage_subdir is None` (landcover) | przechodzi | TAK („BEZ ZMIAN") |
| `test_cuzk_dmr.py:1016-1017` | `subdir=d.storage_subdir` | PEKA | TAK |
| `test_download_manager.py:137,155,167,176` | `_subdir ==` | PEKA | TAK |
| `test_download_manager.py:188` | `_subdir == "custom"` | przechodzi | slusznie pominiete |
| `test_download_manager.py:584,595-689` | `_product == "orto"`, `product="nmt_2000_1m"` | przechodzi | n/d |
| `test_integration.py:92` | `test_data_dir / "nmt_1m" / ...` | PEKA | TAK |
| `test_gugik_laz.py:397` | `out = tmp_path / "laz" / "N-33" / ...` | przechodzi — **sciezka budowana recznie**, nie przez `FileStorage` | slusznie pominiete |
| `test_metadata_cache.py` (`"nmpt"`, `"orto"`) | klucze produktu w cache, nie sciezki | przechodzi | slusznie pominiete |
| `test_parallel_download.py:186,418` | `FileStorage(tmp_path)` po obu stronach | przechodzi | TAK (Zad. 3 Step 4 to przewiduje) |
| `tests/test_sidecar.py` | tylko klucze `pl.gugik.nmt_1m` | przechodzi | n/d |

**Kod produkcyjny:** `_subdir` konsumowany wylacznie w `storage.py:160` (`get_path`),
`:196` (`get_raw_path`), `:358` (`list_files`) — plan pokrywa wszystkie trzy.
`storage_subdir` czytany wprost w `manager.py:208`, `download_cmd.py:1262`,
`download_cmd.py:1348` — plan pokrywa wszystkie trzy (spec mowil „x3 w
download_cmd", faktycznie x2 + x1 w managerze).

### 4.2 Miejsca, ktore plan kaze ruszyc, a ruszone byc NIE powinny

Nie znalazlem zadnego. Lista „Miejsca, ktore mimo pozorow NIE wymagaja zmiany"
(Zad. 2 Step 5) jest w 100 % poprawna — sprawdzilem kazda pozycje osobno,
w szczegolnosci nietrywialne uzasadnienie slice'ow `parts[-8:-1]` / `parts[-6:-1]`
(segment wchodzi PRZED hierarchie godla, wiec indeksy od konca sie nie zmieniaja).

### 4.3 Dokumentacja

`grep -rn "nmt_1m|nmt_5m|cz_dmr5g|cz_dmr4g|laz/|nmpt/|orto/" README.md CLAUDE.md docs/SCOPE.md`:
- `README.md:160,179,186,190` — 4 sciezki, wszystkie w planie (Zad. 11 Step 4)
- `CLAUDE.md:217` — `pl.gugik.nmt_1m` (klucz zrodla, nie sciezka) — plan poprawnie
  wskazuje jako jedyny dozwolony wyjatek
- `docs/SCOPE.md:316` — „nmpt/orto/laz w etapie 2" (wyliczenie produktow) — nie
  jest sciezka, nie wymaga zmiany, nie trafia tez do grepa Step 7
- **`nmt_2000_1m` w dokumentacji:** `docs/CHANGELOG.md:596-597` (historia 0.5.0,
  ma juz uwage — plan slusznie zostawia) i `docs/PROGRESS.md:744` (A1-9 — plan
  domyka). **W `CLAUDE.md` faktycznie NIE MA** — Odstepstwo #3 potwierdzone.

---

## 5. Punkty czyste (sprawdzone, bez zastrzezen)

**Odstepstwa od litery specu — wszystkie 6 zweryfikowane jako faktycznie uzasadnione:**

1. **`capability="sheet_files"` zamiast `"bbox_raster"`** — POTWIERDZONE dwoma
   dowodami: (a) `registry.py:104-118` — `pl.gugik.nmt_5m` ma JEDEN kanal
   z `capabilities=frozenset({"sheet_files"})`, wiec
   `_select_channel_by_capability` (`sidecar.py:68-77`) rzucilby `KeyError`;
   (b) `registry.py:80-90` — kanal WCS `bbox_raster` w `nmt_1m` ma
   `vertical_crs_options=("EPSG:9650",)`, wiec `resolve_vertical_crs("EVRF2007", ...)`
   zwrocilby `EPSG:5621` zamiast `EPSG:9651` (sprawdzone na `registry.py:383-391`).
2. **Kopia `warp_to_grid` zamiast refaktoryzacji CZ** — POTWIERDZONE:
   `tests/test_cuzk_dmr.py:496` i `:527` patchuja doslownie
   `"kartograf.providers.cuzk.dmr.reproject"`.
3. **CLAUDE.md nie zawiera `nmt_2000_1m`** — POTWIERDZONE grepem (sekcja 4.3).
4. **Kaskada `_laz_uklad` szersza niz spec 5.5** — spojna z testami planu
   (`crs="EPSG:2180"` -> format godla -> `1992`); zachowanie dla
   `PL-2000*`/`PL-1992*`/`None` identyczne ze specem.
5. **Selekcja arkuszy z bboxa zadania, crop z bboxa 2180** — zgodne z dzisiejszym
   `_download_pl_bbox:917` (`find_sheets_for_bbox(bbox, ...)` dostaje bbox
   w ukladzie zadania); nie zmienia toru bez `--target-crs`.
6. **Walidacje w `_resolve_pl_sentinels` zamiast `_dispatch_area`** — POTWIERDZONE
   przesledzeniem wszystkich 4 przeplywow PL: godlo (`:625`), bbox (`:910`),
   geometry (`:1543`), LAZ (`:1091`) wolaja sentinele; `_pl_only_flags:420-427`
   faktycznie rozstrzyga `nmpt`/`orto`/`--system` do PL przed pobraniem.

**Poprawnosc mechaniki (przeliczona recznie / uruchomiona):**

- `resolve_subdir` — wszystkie 6 testow Zad. 1 przechodza pod implementacja Step 3.
- `FileStorage` — wszystkie 12 testow `TestFileStorageSegments` przeliczone:
  `parts[-10:-8]` / `parts[-8:-6]` w `test_laz_segment_by_identifier` **zgadzaja
  sie** (`_pl1992_path_parts("N-33-131-B-a-1-1-4")` = 7 czesci,
  `_pl2000_path_parts("6.162.34.02.3")` = 5 czesci); `match="vcrs"` trafia w
  `re.findall(r"\{(\w+)\}", ...)`; `test_orto_segment_no_vcrs` z `vertical_crs=None`
  konczy sie sukcesem, bo szablon orto nie ma `{vcrs}`; `test_list_files_spans_both_uklady`
  dziala z nowym cialem `list_files`.
- `mosaic_and_crop(dst_kwds=)` — **uruchomione na zywo** na dwoch syntetycznych
  ASC-ach: `crs_set == {"None"}`, `res_set == {(1.0,1.0)}`, wynik `driver=GTiff`,
  `crs.to_epsg()==2180`, `nodata==-9999.0`, `bounds == (1.0,1.0,7.0,3.0)`.
  Test z Zad. 6 przejdzie.
- `build_pinned_transform("EPSG:2180", X, TransformPolicy(1.0, probe, no-network))`
  — **uruchomione offline** dla X ∈ {2180 (0,0 m), 3045 (0,0 m), 5514 (0,5 m)};
  wszystkie 3 wartosci z `choices` `--target-crs` sa osiagalne bez siatek z sieci.
- Warstwa walidacji Zad. 8 — przesledzone wszystkie 5 przypadkow
  `TestTargetCrsValidations` (godlo, nmpt, orto, laz, system 2000); w kazdym
  komunikat pada zanim cokolwiek trafi do sieci, a wczesniejsze checki sentineli
  (`nmpt`+5m, `orto`+vertical) nie przechwytuja ich przedwczesnie.
- `TestBorderTwoCutouts` — przesledzony caly przeplyw: `_countries_for_bbox` ->
  `("CZ","PL")`, `_validate_cross_country` przechodzi po usunieciu krotki,
  `_country_bbox` daje CZ w 2180 (bo `cz_crs = target_crs`) i PL w 4326,
  `_prepare_pl_cutout` normalizuje 4326->2180, segmenty
  `nmt/pl_1992_5m_evrf2007` i `nmt/cz_dmr4g_evrf2007` zgadzaja sie z asercjami,
  syntetyczny arkusz (300x300 m przy 5 m pikselu) pokrywa bbox. **Test przejdzie**
  — jedyny problem to brak izolacji cwd (D-03).
- `_write_cz_sidecar` (`download_cmd.py:1199-1248`) — stub `_cz_provider()` planu
  dostarcza wszystko, czego funkcja wymaga (`descriptor_key`, `vertical_crs`,
  `vertical_transform`, `horizontal_transform(...)`).
- Typowanie: nowe cialo `_subdir` przechodzi zawezenia mypy (`if self._subdir_override:`,
  `elif self._product:`); `_PRODUCT_SUBDIRS.get(str, str) -> str`. Nie widze
  zrodla nowego dlugu mypy poza usunietym `:1347`.
- Ruff: poza D-06 zadna z cytowanych linii implementacji nie przekracza 88 znakow
  (`rc = _download_pl_geometry(..., bbox=part)` ma dokladnie 88).

**Global Constraints — bez konfliktow:** galaz `develop` ✓; `landcover/`
(`storage_subdir=None` w `registry.py:191,210,230`) nietkniety ✓; brak shimow ✓;
segmenty lowercase ✓; docstringi w `storage.py`/`manager.py` po angielsku,
a plan dopisuje angielskie fragmenty ✓.
