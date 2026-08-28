# Fala naprawcza po finalnym review calej galezi

Werdykt finalnego review: **GOTOWE PO NAPRAWACH**. Ponizej pelna lista do
zamkniecia w JEDNYM przejsciu. Kolejnosc jest sugerowana (od najciezszego).

Stan wejsciowy: **1775 testow PASS, pokrycie 93 %, mypy 32, ruff czysty**
(commit `a9afc3f`). Po Twojej pracy: zero nowych bledow mypy, suita zielona.

Wiazace ograniczenia: testy OFFLINE (conftest przewraca gniazdo spoza
loopbacku); **tor czeski `kartograf/providers/cuzk/` NIETYKALNY** (wolno tylko
importowac `bbox_to_crs`); `landcover/` nietkniety; docs po polsku bez
diakrytykow w plikach, ktore juz tak maja (CLAUDE.md, CHANGELOG, DECISIONS,
PROGRESS, ARCHITECTURE), README i SCOPE maja wlasna konwencje z diakrytykami.

---

## N-01 [KRYTYCZNE] Gwarancja R-01 nie obowiazuje w `--geometry` i nie jest broniona w `--bbox`

**Dowod (dwa niezalezne, oba powtorzone przez reviewera):**
- Mutacja `download_cmd.py:1238`: `sheet_bbox = bbox if cutout is None else
  cutout.bbox_source_2180` -> `sheet_bbox = bbox` przechodzi **1775/1775**.
  Jedyny test R-01 (`tests/test_pl_cutout.py:84`) wola `_build_pl_cutout`
  wprost, podajac juz poszerzony bbox — wiec nie broni SELEKCJI arkuszy.
- W trybie `--geometry` arkusze wybiera `find_sheets_for_geometry`
  (`download_cmd.py:1915`) PRZED zbudowaniem `cutout` (`:1965`), wiec zapas
  nigdy nie wplywa na selekcje. Zmierzone: powrot obwiedni celu do 2180 rosnie
  o ~7,5 % boku na strone dla EPSG:5514 (2 km -> 151 m; 20 km -> **1512 m**),
  ~5,3 % dla EPSG:3045; wynik ma **8,4 % pikseli nodata (1475/17484)**, podczas
  gdy tor `--bbox` ma 0 %.

**Skutek:** ta sama flaga daje kompletny raster w `--bbox` i raster z ramka
dziur w `--geometry`; w `--bbox` regresja przejdzie przez cala suite
niezauwazona.

**RULING KONTROLERA (wiazacy).** To moje wczesniejsze rozstrzygniecie bylo
niepelne: kazalem NIE rozszerzac selekcji w trybie geometry, zeby nie ciagnac
setek arkuszy dla rzadkiej geometrii wieloobiektowej. Pomiar pokazuje, ze
kosztem tej oszczednosci jest ramka nodata na KRAWEDZIACH wyniku — takze tam,
gdzie geometria dochodzi do obwiedni. Poniewaz wynik i tak obejmuje CALA
obwiednie geometrii (tak stanowi dokumentacja tej galezi, po naprawie w Zad. 9),
uczciwym domknieciem tej obietnicy jest wypelnienie jej danymi.

**Naprawa:**
1. W `_download_pl_geometry`, gdy `cutout.pinned is not None`, dolacz do listy
   godel wynik `find_sheets_for_bbox(cutout.bbox_source_2180, ...)` (suma
   mnogosciowa z godlami z geometrii, bez duplikatow, stabilna kolejnosc).
2. Test w `tests/test_pl_cutout.py:304` (tryb bbox):
   `sent = find.call_args.args[0]` + asercje `sent.min_x < bbox.min_x`,
   `sent.max_x > bbox.max_x` i analogicznie dla N/S — to domyka luke w torze
   `--bbox`.
3. Test w `tests/test_pl_cutout.py:345` (sciezka bez `--target-crs`):
   `assert find.call_args.args[0] is bbox` — pilnuje, ze zapas NIE wchodzi,
   gdy flagi nie ma.
4. Test trybu `--geometry` z `--target-crs EPSG:5514` (dzis NIE PRZESZEDLBY —
   patrz triage #206), asertujacy pelne pokrycie wyniku.
5. Jedno zdanie w `docs/ARCHITECTURE.md` (sekcja 4.3): przy rzadkiej geometrii
   wieloobiektowej wypelnienie obwiedni oznacza pobranie arkuszy dla calej
   obwiedni — swiadomy koszt.

---

## N-02 [Wazne] SIODMY przypadek dokumentu opisujacego nieistniejace zachowanie

`docs/ARCHITECTURE.md:367-368` („Ten powiekszony bbox ... steruje cropem
mozaiki **i siatka wyniku**") i `:371-372` („zapas wplywa wylacznie na crop
**i siatke**").

**Dowod:** `download_cmd.py:1158-1165` podaje `bbox_source_2180` jako crop,
a `bbox_target` jako siatke; `transform/raster.py:95-97` liczy
`width/height/dst_transform` wylacznie z `bbox` (= `bbox_target`). Zmierzone:
wynik 186x94 px, `bounds == bbox_target` (z zapasem byloby ~200x115). Dokument
sam sobie przeczy w `:420-423`, gdzie nazwa pliku pochodzi z `bbox_target`.

**Naprawa:** skreslic „i siatka wyniku" / „i siatke" w obu miejscach.

---

## N-03 [Wazne] `DownloadManager` buduje segment z WLASNEGO pionu, a sidecar z providera

`download/manager.py:210,215` vs `:747`.

**Dowod:** `DownloadManager(provider=GugikProvider(vertical_crs="KRON86"))`
pisze do `.../nmt/pl_1992_1m_evrf2007/...`, a sidecar obok podaje `EPSG:9650`.
Mutacja usuwajaca `vertical_crs=vertical_crs` z `FileStorage(...)` w `:211-216`
przechodzi 1775/1775 — `test_default_storage_respects_kron86` nie broni tego,
na co wyglada (sciezka deskryptorowa wypelnia `{vcrs}` wczesniej).

**Skutek:** dane KRON86 i EVRF2007 tego samego arkusza znow trafiaja do JEDNEGO
katalogu — dokladnie problem, ktory ADR-026 mial usunac. Osiagalne z API
biblioteki (uzywa go Hydrograf), nie z CLI.

**Naprawa:** `vertical_crs = getattr(self._provider, "vertical_crs", vertical_crs)`
po utworzeniu providera, PRZED budowa domyslnego storage'u; plus test blizniaczy
do `test_manager_without_descriptor_key_falls_back_to_resolution`, ktory pada
pod ta mutacja.

---

## N-04 [Wazne] `FileStorage(vertical_crs="")` daje cichy segment `nmt/pl_1992_1m_`

`download/storage.py:141-142` (`if self._vertical_crs is not None:`).

**Dowod:** `DownloadManager(provider=..., vertical_crs="")` ->
`/tmp/x/nmt/pl_1992_1m_/N-34/...`. `_ensure_resolved` tego nie lapie (brak
klamry), wiec `ARCHITECTURE.md:190` („Cichy katalog ... nigdy nie powstanie")
jest prawdziwe tylko literalnie o klamrach.

To CZWARTA eskalacja tego samego drobiazgu w tym planie.

**Naprawa:** `if self._vertical_crs:` (jedna linia) albo `ValidationError` dla
pustego stringu — wybierz i uzasadnij; plus test.

---

## N-05 [Wazne] Brak wpisow w `KNOWN_PATHS` dla dwoch nowych par ukladow

`transform/crs.py:131-150`, `tests/test_transform_crs.py:143-150`, wobec reguly
spisanej w `docs/ARCHITECTURE.md:534-535` („wpis w `KNOWN_PATHS` dla kazdej
uzywanej pary ukladow wraz z oczekiwana dokladnoscia").

**Zmierzone:** `EPSG:2180 -> EPSG:5514` acc **0.5** (opis: „axis order change
(2D) + Inverse of Poland CS92 + ETRF2000-PL to ETRS89 (1) + Inverse of S-JTSK
to ETRS89 (3) + Krovak East North"); `EPSG:2180 -> EPSG:3045` acc **0.0**.
`KNOWN_PATHS` ma dzis tylko kierunek odwrotny (5514->2180).

**Skutek:** jedyny mechanizm wychwytujacy regresje doboru operacji nie obejmuje
nowego toru PL. Galaz lamie regule, ktora sama wlasnie spisala.

**Naprawa:** dwa `KnownPath` + dwie asercje w `TestKnownPaths`. **Zmierz
dokladnosci sam** — nie przepisuj powyzszych na slepo.

---

## N-06 [Wazne] Caly przeplyw 5 m w wycinku jest niebroniony

Cztery niezalezne mutacje przechodza 1775/1775:
- `download_cmd.py:1162` (`_PL_PIXEL_SIZES[args.resolution]` -> `1.0`)
- `download_cmd.py:1115` (zawsze klucz `nmt_1m`)
- `download_cmd.py:1172` oraz `:1228`/`:1966`
  (`getattr(provider, "vertical_crs", ...)` -> surowa flaga)

**Skutek:** `--resolution 5m --target-crs EPSG:5514` moglby dac siatke 1 m
z danych 5 m (25x rozmiar pliku), a `--resolution 5m --vertical-crs KRON86` —
wycinek w `pl_1992_5m_kron86/` z `vertical_crs: EPSG:9650`, choc dane sa
EVRF2007. Dla ARKUSZY ta sama klasa bledu JEST broniona
(`test_default_storage_5m_kron86_corrected_to_evrf`,
`test_nmt_5m_kron86_storage_follows_provider_correction`) — asymetria.

**Naprawa:** jeden test `--resolution 5m --vertical-crs KRON86 --target-crs
EPSG:5514` z asercjami: `ds.res == (5.0, 5.0)`, `dataset == "pl.gugik.nmt_5m"`,
`vertical_crs == "EPSG:9651"`, segment `pl_1992_5m_evrf2007`.

---

## N-07 [Wazne] Atomowosc zapisu i sprzatanie po awarii sa nieprzetestowane

`tests/test_transform_raster.py:103-104` (`assert list(tmp_path.glob("*.warp.tif")) == []`
— spelnione takze bez `os.replace`, bo tmp wtedy nie powstaje) oraz `:156`/`:176`
(`assert not dst.exists()` — guard rzuca przed jakimkolwiek zapisem, wiec galaz
`except BaseException` nigdy sie nie wykonuje).

Mutacje, ktore PRZECHODZA: zapis wprost do `dst_path` bez `os.replace`/`finally`;
usuniecie `dst_path.unlink` z `raster.py:132-133`; to samo w `download_cmd.py:1086-1087`.

**Skutek:** przerwany warp moglby zostawic polzapisany GeoTIFF pod finalna
sciezka, ktora `skip_existing` (`download_cmd.py:1232`) uzna potem za wazny
cache — trwale zatruty wynik.

**Naprawa:** `patch("kartograf.transform.raster.reproject", side_effect=RuntimeError)`
+ `pytest.raises` + `assert not dst.exists()` + brak `*.warp.tif`; analogicznie
dla `_build_pl_cutout` przez patch `warp_to_grid`.

---

## N-08 [Wazne] „Odswiez albo nic" moze przyjsc z kodem wyjscia 0 — i jest zbedne

`download_cmd.py:1086-1088`, `transform/raster.py:132-134`, `download_cmd.py:536-546`.

**Dowod:** `--country auto --force --target-crs` na pograniczu; nieudana budowa
wycinka PL kasuje poprzedni plik i zwraca 1, ale skoro CZ sie udalo,
`_dispatch_area` wypisuje `Warning:` i zwraca **0**. ADR-023 pkt 4-5 pisano,
gdy porazka kraju znaczyla „nic nie pobrano", a nie „poprzedni wynik zniszczony".

**Kluczowa obserwacja reviewera:** `target_path.unlink()` w `_build_pl_cutout`
jest **calkowicie zbedne** — obie galezie zapisu sa juz atomowe (`os.replace`
oraz wewnetrzny `os.replace` w `warp_to_grid`), wiec bez tej linii stary plik
przetrwalby, a sciezka sukcesu nie zmienia sie ani o bit.

**RULING KONTROLERA:** usunac `target_path.unlink(missing_ok=True)`
z `_build_pl_cutout:1087`. To zdejmuje utrate danych zamiast ja dokumentowac.
Sprawdz, czy analogiczne `unlink` w `transform/raster.py:132-134` tez jest
zbedne — **jesli TAK, zostaw je mimo to** (to kopia wzorca toru CZ, ktorego
tuz przed wydaniem nie ruszamy) i opisz roznice w raporcie.
Zaktualizowac opis semantyki w `docs/ARCHITECTURE.md` sekcja 4.3.

---

## N-09 [Drobne, do zrobienia] `_finalize_pl_cutout` lapie za waski zbior wyjatkow

`download_cmd.py:1166` (`except (ValidationError, TransformError)`).
`mosaic_and_crop`/`warp_to_grid` moga rzucic `rasterio.errors.RasterioIOError`
(uszkodzony arkusz z cache). Taki wyjatek wychodzi poza petle krajow
`_dispatch_area`, wiec kontrakt czesciowego sukcesu ADR-023 przestaje
obowiazywac.

**Naprawa:** dolozyc `Exception` do klauzuli (z zachowaniem komunikatu).

---

## N-10 [Drobne, do zrobienia] Rozjazdy tekstowe

1. `docs/ARCHITECTURE.md:415-416` przypisuje wylaczenie „`--target-crs`
   z godlem" do `_resolve_pl_sentinels`; funkcja (`download_cmd.py:121-188`)
   sprawdza wylacznie produkt i `--system 2000`, a wariant godlowy odrzuca
   `cmd_download:652-658` (dla CZ `_cmd_download_cz:1796-1801`).
2. `cli/_parser.py:69-74` — `description` subkomendy `download` nie przeszlo
   ADR-027: „Dla PL `--bbox` rozwija sie na arkusze zrodlowe; dla CZ `--bbox`
   zwraca jeden wycinek…". Widoczne w `kartograf download --help`, koliduje
   z `docs/SCOPE.md:339-343` i `CLAUDE.md:261-264` TEJ SAMEJ galezi.
3. `CLAUDE.md:115-118` i `docs/SCOPE.md:272-274` mowia o „KAZDYM `--bbox` CZ",
   pomijajac `--geometry` CZ, ktore tez pisze do `<segment>/bbox/`
   (`download_cmd.py:1864-1872`, `:516-517`). `ARCHITECTURE.md:258-264`
   formuluje to poprawnie.
4. `docs/ARCHITECTURE.md:53-55` przypisuje korekte osi wylacznie „celom"
   northing-first; `transform/crs.py:103-107` wstawia `axisswap` niezaleznie dla
   ZRODLA i celu. W torze PL zrodlem jest EPSG:2180 (northing-first).
   Zmierzone: warp 2180->5514 bez czolowego axisswap daje 0/46225 waznych pikseli.
5. Docstringi `FileStorage` opisuja uklad sprzed ADR-026: `storage.py:41-42`
   („resolution : Resolution subdirectory"), `:77-78` („output_dir/resolution/..."),
   `:81-82` („uses product instead of resolution as subdirectory"), `:83-84`
   (przyklad `subdir="cz_dmr5g"`), `:393` (`list_files` — „Searches within the
   resolution subdirectory", a przeszukuje OBA uklady).
   Dodatkowo `manager.py:130` pokazuje w przykladzie sciezke bez segmentu
   (`PosixPath('data/N-34/130/D/d/2/4/...')`).

---

## N-11 [Drobne, do zrobienia] Trzy male mutacje przezywajace pelna suite

- `Resampling.bilinear` -> `nearest` (`transform/raster.py:128`) przechodzi,
  mimo testu o nazwie `test_nodata_does_not_bleed_into_interpolation`.
  Naprawa: asercja `resampling` w `test_operation_is_forced` albo w tescie nodata.
- `_same_crs` -> `return a == b` (`transform/raster.py:28-40`) przechodzi —
  semantyka `epsg:2180` == `EPSG:2180` nieprzetestowana.
  Naprawa: wywolanie z malymi literami w tescie.
- `replace(_PL_HORIZONTAL_POLICY, probe_point=center)` -> sama polityka
  (`download_cmd.py:1003`) przechodzi. Naprawa: asercja `probe_point`.

---

## NIE RUSZAC (swiadome decyzje kontrolera)

- **Duplikacja `warp_to_grid` wzgledem `providers/cuzk/dmr.py::_warp_to_grid`** —
  swiadoma; wspoldzielenie zlamaloby patch targety testow ADR-024.
- **`nodata = -9999.0` na sztywno w wycinku** (`download_cmd.py:930`, `:1129`) —
  zgodne z litera specu 6.1 pkt 2; do backlogu, nie teraz.
- **`_prepare_pl_cutout` sklada sciezke z pominieciem `FileStorage`** — oba
  miejsca (PL i CZ) wypelniaja wszystkie placeholdery jawnie; do etapu 2.
- **Guard R-12 robi `raise` zamiast `print + return 1`** — dzis nieosiagalny.
- **`LandCoverManager` trzyma martwy `FileStorage`** (`landcover/manager.py:85`) —
  `landcover/` mial pozostac nietkniety; do backlogu.
- **ADR-005 ma ten sam problem statusu co mial ADR-013** — niespojnosc sprzed
  tego planu.
- Drobiazgi z triazu: redundantny import w tescie, `assert "nmt" in parts`,
  polskie wtrety w `storage.py`, `kwds: dict` bez generykow, skrocony docstring
  filtra GDAL, niesymetryczne importy z `transform.crs`.

---

## Weryfikacja wymagana w raporcie

Dla KAZDEJ naprawy z asercja testowa (N-01 pkt 2-4, N-03, N-04, N-05, N-06,
N-07, N-11): **dowod mutacyjny** — pokaz, ze nowy test pada na zepsutym kodzie
i przechodzi na naprawionym, przywroc plik, pokaz czyste `git status`.
To jest wymog twardy: ta galaz miala juz szesc testow, ktore niczego nie
bronily, i wszystkie wykryto dopiero mutacja.

Na koniec: pelna suita, `ruff check`, `ruff format --check`, `mypy kartograf/`
(<= 32, zero nowych), `git status` czysty.
