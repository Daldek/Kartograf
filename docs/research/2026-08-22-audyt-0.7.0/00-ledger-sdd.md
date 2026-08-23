# SDD ledger — plan: docs/superpowers/plans/2026-08-22-release-0.7.0-audit.md
Base: f4324037874038d9f6e3f916d22550c94e4dfa26 (develop f432403), branch fix/release-0.7.0-audit
Ruling: praca na galezi fix/release-0.7.0-audit w tym samym drzewie (bez worktree) — .venv jest w korzeniu repo, worktree nie mialby srodowiska; implementery dzialaja sekwencyjnie — koszt jesli zle: konflikt z recznymi zmianami usera w tym samym drzewie (working tree byl czysty).
Ruling: faza A (audyt) = rownolegle agenty read-only, NIE SDD task loop; SDD task loop dopiero w fazie B na zadaniach z konsolidacji — koszt jesli zle: brak review per-agent audytu (mitigacja: weryfikacja ustalen przed planem B).
Faza A: dispatch 2026-08-22 — A1 core/transform/transport/sources (opus), A2 providers/pl+download+cache (opus), A3 cuzk+cli (opus), A4 corine/soilgrids/landcover/hsg/auth (opus), A5 jakosc/duplikaty/martwy kod (opus), A6 docs top-level (opus), A7 docs historyczne (opus), A8 testy/pokrycie (opus), A9 docstringi (sonnet). Raporty: audit/A<n>-report.md
A9: done C=0 I=5 M=2
A7: done C=0 I=6 M=6
A2: done C=3 I=6 M=7 (C: MetadataCache read race; DownloadManager provider= bez storage=; download_hierarchy polyka bledy/exit 0) — DO WERYFIKACJI
A4: done C=7 I=7 M=6 (C: CLMS_CREDENTIALS nie czytane; download_file True przy urwanym pobraniu; soilgrids --teryt srodek wojewodztwa; USDA progi; nodata!=0 -> HSG B; hsg stats w deg^2; bbox 2 narozniki) — DO WERYFIKACJI
A5: done C=1 I=7 M=10 (C: CLMS_CREDENTIALS martwy blok — zbiezne z A4-1)
A6: done C=3 I=12 M=7 (C: README --bbox --product orto blad; --format GML traceback; CHANGELOG brak --country auto default)
A1: done C=4 I=5 M=8 (C: get_parent/children 200k<->500k; brak probe_point CZ (sprzeczne z E2E?); punktowy SHP AttributeError; deskryptor nmt_1m WCS martwy) — DO WERYFIKACJI
A3: done C=1 I=4 M=8 (C: kafelkowanie exportImage gubi dolny wiersz) — DO WERYFIKACJI
A8: done C=0 I=7 M=7 (pokrycie 89.53%)
Faza A zakonczona: lacznie C=19 I=59 M=61. Zbieznosci: A4-1=A5-1 (CLMS_CREDENTIALS), A1-4=A2-8=A9-3 (WCS EVRF2007 martwy), A5-8=A6-11 (PRD API), A4-4~A4-9 (USDA).
Faza A' (weryfikacja adwersarialna): dispatch V1..V7 (wszystkie opus): V1->A1, V2->A2, V3->A3, V4->A4, V5->A5, V6->A6+A9, V7->A7+A8. Raporty: audit/<ID>-verify.md. Reguła: naprawa 0.7.0 tylko gdy lokalna, testowalna, ryzyko<=srednie; duze refaktory odlozyc.
V5: done — A5-2 TAK(S), A5-1/3/6/8 DOCS-ONLY, A5-4/5/7 odlozyc; martwy kod 17 pozycji potwierdzonych; N5-1 [Important] martwa galaz laz w _create_provider_and_storage (TAK,S). CLMS_CREDENTIALS: nie czytane NIGDZIE (corine ani proxy) -> README/CLAUDE.md klamia
V2: done — A2-1 CONFIRMED mocno (read race cached_statements; TAK S, uwaga nierekurencyjny Lock), A2-2 TAK S (--force NMPT nadpisuje NMT), A2-3 TAK S/M, A2-5 TAK M (bez zmiany typu zwracanego), A2-6 TAK S, A2-9 TAK S, A2-8 DOCS-ONLY, A2-4/A2-7 odlozyc; V2-N1 [Important] CLI ignoruje --resolution dla nmpt / --vertical-crs dla orto (TAK S)
V3: done — A3-1 CONFIRMED Critical (kafelkowanie: przesuniecie tresci -1.4..+0.6 m, gubiony wiersz; TAK S), A3-2 TAK S (kod wyjscia 1 = blad; odpytanie PL = ADR-023), A3-3 TAK S, A3-4 TAK S, A3-5 DOWNGRADE Minor TAK S; N3-2 E2E nigdy nie dotknelo kafelkowania -> test jednostkowy z ulamkowa wysokoscia + krok E2E przed 0.7.0
V4: done — A4-1/2/3/5/8/10/11/13/14 TAK S, A4-4 TAK M (USDA, ryzyko srednie), A4-6 TAK S/M, A4-7 TAK S/M (srednie), A4-9 DOCS-ONLY, A4-12 odlozyc; N4-1 [Important] AuthProxyClient bez Lock -> rownolegly CORINE miesza GeoTIFF/PNG (TAK S)
V7: done — A7-1..6 DOCS-ONLY (erraty), A8-1 TAK S-M (21 testow wysyla realne HTTP), A8-2 TAK S, A8-5 TAK S, A8-6 TAK S, A8-3/4 odlozyc (dlug sprzed 0.6), A8-7 DOCS-ONLY; N7-1 jednorazowe 19 failed w testach ADR-024 (TransformError) — hipoteza: zbieg z eksperymentem V1 (siatka sk_gku tymczasowo w ~/.local/share/proj, mtime 13:33; cache.db ma chunki sk_gku z 12:56) => jesli tak, to A1-2 jest REALNE; N7-2 DEVELOPMENT_STANDARDS 10.1 komenda nie egzekwuje progow (DOCS-ONLY)
V6: done — kod: A6-2 TAK S (GML phantom: CLI+help+get_supported_formats+base.py), A6-4 TAK S (pyproject wersja/autor/opis), A6-5 TAK S (tests w dystrybucji), A6-13 TAK S (--help teksty), A9-1 TAK S (walidacja system); DOCS-ONLY: A6-1/3/7/8/9/10/11/12/14/15, A9-2/3/4/5; A6-6 Minor. N6-1 [Critical] bbox 419000,230000,426000,237000 z README/PRD lezy w CZ (Opawa) — podmienic w 5 miejscach. N6-2 [Important] --country auto w SW Polsce odrzuca --vertical-crs KRON86 i --system 2000 (regresja vs 0.6.1).
Ruling (N6-2): pod --country auto, gdy uzytkownik podal flagi tylko-PL (--system, --vertical-crs KRON86, --product != nmt), auto rozwiazuje sie do `pl` z komunikatem informacyjnym (bez bledu), zamiast odpytywac CUZK i padac — bo zaden z tych wariantow nie ma odpowiednika CZ w etapie 1, wiec intencja "PL" jest jednoznaczna — koszt jesli zle: uzytkownik z bboxem przygranicznym i --system 2000 nie dostanie czesci CZ (ale dzis dostaje exit 1, wiec to scisle lepsze); do odnotowania w ADR-023 (addendum) i CHANGELOG.
V1: done — A1-1 TAK S (200k<->500k), A1-2 TAK M (probe_point w politykach CZ; V1 odtworzyl z tymczasowa siatka sk_gku => wyjasnia N7-1), A1-3 TAK S, A1-4 TAK S/M, A1-5 TAK M, A1-6 TAK S, A1-7 TAK S (srednie), A1-8/9 DOCS-ONLY; N1-1 [Important] main() bez bariery na wyjatki spoza KartografError (TAK S)
Faza A' zakonczona. 0 REFUTED. ~46 napraw kodu/testow, ~27 DOCS-ONLY, ~8 odlozonych (A2-4, A2-7, A4-12, A5-4, A5-5, A5-7, A8-3, A8-4).
Ruling (wersja): w tej galezi wersja zostaje 0.7.0-dev (pyproject zsynchronizowany z __init__); bump na 0.7.0 + data CHANGELOG = osobny krok po zadaniu licencyjnym usera — koszt jesli zle: jeden dodatkowy commit.
Ruling (pyproject authors/license): NIE ruszac w audycie — user zapowiedzial zadanie licencyjne; placeholder "Piotr <piotr@example.com>" zglosic userowi.
Ruling (A4-4 USDA): naprawic wg normy USDA (zmiana wynikow HSG dla Hydrologa) + wpis "Changed" w CHANGELOG z opisem skutku — koszt jesli zle: konsument HSG dostaje inne klasy dla ~3% pikseli (ale zgodne z norma).
Ruling (A1-7 krawedzie): bbox rowny dokladnie arkuszowi zwraca ten jeden arkusz; stykanie sie krawedzi NIE jest przecieciem na zadnym poziomie hierarchii — koszt jesli zle: bbox konczacy sie dokladnie na granicy arkusza nie dostanie sasiada (dotad dostawal 9 zamiast 4, wiec nadmiar).
Ruling (odlozone): A2-4, A2-7, A4-12, A5-3/4/5/6/7, A8-3/4 => wpis w docs/PROGRESS.md "Backlog po audycie 0.7.0" (DOCS-ONLY w fazie B), nie naprawiamy przed wydaniem.
Faza B: plan pisze agent fable (z 7 verify + 9 report), pre-flight scan planu agent opus.
Plan fazy B: 26 zadan w docs/superpowers/plans/2026-08-22-release-0.7.0-audit.md (fable, 1248 linii).
Ruling (zad. 8, A4-3): SoilGridsProvider.download_by_teryt -> NotImplementedError zamiast naprawy lookupu powiatow (dzis zwraca dane dla stalego 60x60 km wokol srodka wojewodztwa jako sukces; brak offline zrodla bbox powiatow) — BREAKING w CHANGELOG — koszt jesli zle: uzytkownik soilgrids --teryt traci (pozorna) funkcje; remedium --bbox/--godlo.
Ruling (zad. 17, A3-2): auto-split: porazka jednego kraju + sukces drugiego => kod 0 + Warning na stderr; wszystkie kraje padly lub jawny --country => jak dotad — koszt jesli zle: realna awaria PL na pasie przygranicznym maskowana kodem 0 (ostrzezenie + sidecar parent_request.countries lagodza).
Ruling (zad. 21, A6-4/6): usuniecie requirements.txt/requirements-dev.txt (zero odwolan poza historycznym CHANGELOG:579; DEVELOPMENT_STANDARDS 7.2 "wszystko w pyproject") + wersja dynamiczna attr kartograf.__version__ — koszt jesli zle: CI/uzytkownik z `pip install -r requirements.txt` (nieudokumentowane) — odtworzyc z git.
Pre-flight scan planu: agent opus -> audit/preflight.md
Plan commit: a88a73a
Pre-flight: 13 defektow (audit/preflight.md). Rulingi:
Ruling P-1: zad.5 warunek `isinstance(key, str)` zamiast `is not None` (Mock(spec=...).descriptor_key to Mock) — koszt jesli zle: provider z niestringowym kluczem pominiety (nie istnieje).
Ruling P-2: zad.19 fixture WMS: side_effect lambda endpoint, timeout=10 dla NMT; return_value dla orto; usunac zdanie o sumie list.
Ruling P-3: zad.6 guard np.where(total>0, np.select(...), loam).
Ruling P-4: zad.6/22 liczby w ADR-025/CHANGELOG = wynik WERSJI TABLICOWEJ policzony przez implementera w tescie (wstepnie 226 pkt/4,39%: 136 A->B, 85 C->B, 5 D->C), format "bylo -> jest".
Ruling P-5: zad.13 model opus; guard EVRF2007 PO walidacji formatu/CRS; lista testow do przepiecia w briefie.
Ruling P-6/P-7/P-9/P-10/P-12: przyjete literalnie (asercja allclose; usunac zamknieta liste scope'ow; product in ("nmpt","orto"); punkt PL (637000, 487000) EPSG:2180; dwie stale EPS: 1e-7 deg PL-1992, 1e-3 m PL-2000).
Ruling P-8: zad.21 dopisac fakty (pyproject 0.6.1 dzis; brak setuptools w .venv) — weryfikacja pakietu (build sdist/wheel) -> Checklista release.
Ruling P-11: kanoniczna liczba testow = jeden przebieg po zad.21, zapisany w ledgerze, briefy 22/23/26 dostaja ja od kontrolera.
Ruling P-13: bez reorderu; Global Constraint (g) rozszerzony: kazdy nowy test musi przechodzic z odcieta siecia (implementer moze sprawdzic przez HTTPS_PROXY=http://127.0.0.1:9); zad.19 krok 1: liczba FAILED moze sie roznic od 20 — naprawic wszystkie.
Plan po pre-flight: 63c5d1f. Faza B start.
BASE zad.1: 63c5d1fd84b42cc92331184c5912980dd00ce94e
Task 1: implementer DONE (8956bfb, b05c8f6, c6f1ae1; 1405 passed, ruff OK, mypy 33); concerns: noqa BLE001 dekoracyjne, dst_kwds redundantne, N3-2 E2E kafelkowania przed tagiem -> Checklista release. Review dispatched (opus).
Task 1: minor (deferred): test uszkodzonego kafla nie cwiczy galezi unlink (fixture pada w rasterio.open) — wzmocnic fixture (truncate poprawnego GeoTIFF); mosaic_and_crop moze zostawic obciety plik przy bledzie merge (dodac try/except unlink); noqa BLE001 dekoracyjne (client.py:185); dst_kwds redundantne. Release checklist: E2E kafelkowania z wynikiem >16 Mpx (sciezka chunkowana merge(dst_path)).
Task 1: complete (commits 63c5d1f..c6f1ae1, review clean, 4 minor deferred)
BASE zad.2: c6f1ae1
Task 2: implementer DONE (57657a5; 1553 passed, ruff OK, mypy 33). Review dispatched (opus).
Task 2: minor (deferred): docstringi 3 testow (test_sheet_parser.py:410/428/437) koduja stara numeracje sekcji; mieszane diakrytyki w docstringach sheet_parser.py:449-457. CHANGELOG (zad.22): zmiana get_parent/get_children 1:1M/1:500k.
Task 2: complete (commits c6f1ae1..57657a5, review clean, 2 minor deferred)
BASE zad.3: 57657a5
Task 3: implementer DONE (dfec122, f17d625; 1558 passed (kontroler), ruff OK, mypy 33); concern: galaz not is_rectilinear bez testu. Review dispatched (opus).
Task 3: review -> 1 Important (brak testu probe dla modulowej bbox_to_crs pinned=None, sciezka CLI). minor (deferred): test_horizontal_policy_probe_is_cz_native_center tautologiczny (dodac asercje geograficzna approx (15.5,49.8)); probe dla pary raster->4326 tylko `is not None`; galaz not is_rectilinear bez testu (OK); probe ignorowany dla zbuforowanej pary (etap 2).
Task 3: fix round 1/5 dispatched (FIX_BASE f17d625)
Task 3: fix round 1/5 (1 addressed, 0 open — test probe modulowej bbox_to_crs; commit 930e345)
Task 3: complete (commits 57657a5..930e345, review clean after round 1, 4 minor deferred)
BASE zad.4: 930e345
Task 4: implementer DONE (d059b56; 1561 passed, ruff OK, mypy 33). Review dispatched (opus).
Task 4: minor (deferred): rename _write_lock -> _lock (chroni tez odczyty); docstring "after construction"; get_sheet docstring mix PL/EN.
Task 4: complete (commits 930e345..d059b56, review clean, 3 minor deferred)
BASE zad.5: d059b56
Task 5: implementer DONE (04c38f3, bbc2f0b; 1563 passed, ruff OK, mypy 33); concerns: download_sheet pojedynczy arkusz nie ustawia last_result (zad.16 uwzglednic); A1-9 docs (CHANGELOG:342/ADR-017) sprawdzic w zad.22. Review dispatched (opus).
Task 5: review -> 1 Important (brak resetu last_result na wejsciu download_hierarchy). minor (deferred): Notes obiecuje zbieranie bledow takze w trybie sekwencyjnym (A2-4 odlozone — dopisac zdanie o max_workers<=1); status completed/skipped z path None nie trafia do zadnego licznika (else failed); duplikacja zliczania w 2 petlach (plan-mandated, etap 2). Docs: CHANGELOG (zad.22) — DownloadManager(provider=NMPT) pisze do nmpt/. Zad.16: last_result moze byc None (download_sheet 1:10000 nie ustawia).
Task 5: fix round 1/5 dispatched (FIX_BASE bbc2f0b)
Task 5: fix round 1/5 (1 addressed czesciowo — reset tylko w download_hierarchy; commit 2ac131d)
Ruling (Task 5): last_result resetowany TAKZE na wejsciu do download_sheet (publiczny punkt wejscia; sciezka 1:10000 omija download_hierarchy) — koszt jesli zle: zaden (reset jest idempotentny).
Task 5: fix round 2/5 dispatched
Task 5: fix round 2/5 (commit 5c7601a; re-review dispatched on bbc2f0b..5c7601a)
Task 5: fix round 2/5 (1 addressed, 0 open; commits 2ac131d, 5c7601a). minor (deferred): download_bbox nie dotyka last_result (obserwacja na przyszlosc).
Task 5: complete (commits d059b56..5c7601a, review clean after round 2, 4 minor deferred)
BASE zad.6: 5c7601a
Task 6: implementer DONE (685c582, 88acf65; 1595 passed 0 warn, ruff OK, mypy 33; P-4 liczby potwierdzone 226/4.39%). Review dispatched (opus).
Task 6: minor (deferred): DECISIONS.md:867 przypis ADR-025 "21 punktow" -> 22 (28+22=50=226-176); dopisac 2 punkty kontrolne domkniec do CANONICAL_CONTROL_POINTS: (20,60,20,"sandy_loam"), (27,30,43,"loam"); _normalize_pct anotacje parametrow; test symplexu 5151 wywolan skalara (+0.5 s, OK). Zad.22: wpis Changed HSG z tabela z ADR-025 Konsekwencje (ruling A4-4).
Task 6: complete (commits 5c7601a..88acf65, review clean, 4 minor deferred)
BASE zad.7: 88acf65
Task 7: implementer DONE (d523fd8, f6d0b5d; 1599 passed, ruff OK, mypy 33). Review dispatched (opus).
Task 7: minor (deferred): test_hsg.py:661 rel=0.02 za luzne (asercja row_areas[0]<row_areas[-1] lub rel=1e-3); percent w pikselach vs area_ha geodezyjne (plan-mandated; kiedys pct z area_m2); linia 517 all-zero redundantna przy nodata=0; brak anotacji src w _geographic_row_cell_areas; O(height) Geod OK.
Task 7: complete (commits 88acf65..f6d0b5d, review clean, 5 minor deferred)
BASE zad.8: f6d0b5d
Task 8: implementer DONE (6c292aa, eb1b5c4; 1605 passed, ruff OK, mypy 33); concern 4: galaz DLR/1990 4326 HEIGHT z proporcji stopni (100x61 px dla 10x10 km = ~164 m/px pion) — podejrzenie regresji rozdzielczosci. Review dispatched (opus).
Task 8: review -> 1 Important (galaz CORINE DLR/1990 4326: HEIGHT z proporcji w stopniach = 165-174 m/px pionowo, regresja vs BASE ~100 m/px).
Ruling (Task 8, konflikt z planem): wzor briefu `height_px = width_px * (tb[3]-tb[1])/(tb[2]-tb[0])` jest poprawny tylko dla 3857; stosujemy propozycje recenzenta — proporcje ZAWSZE z obwiedni 3857 (`aspect_bounds`), `target_bounds` wg CRS galezi (3857 dla EEA, 4326 dla DLR); test przypinajacy year=1990 HEIGHT 98..102 dla 10x10 km — koszt jesli zle: galaz DLR dostaje HEIGHT z innego ukladu niz BBOX, ale proporcja gruntowa jest wlasciwa (zweryfikowane snippetem recenzenta: 100x100 -> 101/101 m/px).
Task 8: minor (deferred): width_px z bboxa zrodlowego (106 m/px zamiast 100; plan-mandated; docelowo oba wymiary z obwiedni); warunek year in EEA_YEARS w 2 miejscach bez CRS w krotce; cap 4096 lamie proporcje per os (A4-20 backlog).
Task 8: fix round 1/5 dispatched (FIX_BASE eb1b5c4)
Task 8: fix round 1/5 (1 addressed, 0 open; commit eecdc73)
Task 8: complete (commits f6d0b5d..eecdc73, review clean after round 1, 3 minor deferred)
BASE zad.9: eecdc73
Task 9: implementer DONE (d3e93a8, ef5695f, a625877; 1614 passed, ruff OK, mypy 33); Release checklist: zywa weryfikacja CORINE GeoTIFF z credentials — host presigned DownloadURL vs allowlista copernicus.eu/eea.europa.eu. Review dispatched (opus).
Task 9: review -> 1 Important (plan-mandated: upstream bez Content-Length => klient 200 + czesciowe cialo; protocol HTTP/1.0 ramowanie zamknieciem).
Ruling (Task 9, konflikt z planem): framing domykamy w PROXY (HTTP/1.1 + Transfer-Encoding: chunked gdy upstream bez Content-Length; terminal 0\r\n\r\n tylko po udanej petli) — nie przenosimy na klienta; Minor 2 (Content-Encoding + Content-Length upstreamu przekazywane, a iter_content oddaje zdekompresowane bajty) PODNIESIONY do rundy, bo zad.10 (kontrola liczby bajtow) by na tym padal: strumieniowac surowe bajty (`resp.raw.stream(..., decode_content=False)`) i przekazywac oba naglowki spojnie — koszt jesli zle: proxy ramkuje chunked po swojemu (wiecej kodu w handlerze), ale test socket-level to przypina.
Task 9: minor (deferred): brak resp.close()/finally na sciezce urwania (dodac w rundzie jesli trywialne); docstring client.py Path bez importu.
Task 9: fix round 1/5 dispatched (FIX_BASE a625877)
Task 9: fix round 1/5 (commit 7ed3e8f; re-review dispatched a625877..7ed3e8f). Wejscie dla zad.10: (a) przy chunked brak Content-Length — brakujacy terminal chunk rzuca ChunkedEncodingError (RequestException) -> klient lapie i kasuje .tmp; (b) Content-Length = bajty SKOMPRESOWANE — kontrola dlugosci po stronie klienta tylko gdy brak Content-Encoding albo porownanie na surowych bajtach (resp.raw).
Task 9: fix round 1/5 (3 addressed, 0 open; commit 7ed3e8f). minor (deferred): chunked bez sprawdzenia request_version (klient HTTP/1.0 — nieosiagalne); BrokenPipeError z wfile.write do handle_error (pre-existing); testy podmieniaja ProxyHandler.credentials bez przywrocenia (wzorzec pre-existing).
Task 9: complete (commits eecdc73..7ed3e8f, review clean after round 1, 5 minor deferred)
BASE zad.10: 7ed3e8f
Task 10: implementer DONE (fe177e9, 49c0d8c; 1627 passed, ruff OK, mypy 33); odstepstwo: Content-Length pomijany przy Content-Encoding != identity (zgodne z wejsciem kontrolera). Review dispatched (opus).
Task 10: minor (deferred): [KANDYDAT do fali finalnej] __new__ singletonu poza lockiem + _proxy_process per instancja (dwa watki -> dwa podprocesy; double-checked lock w __new__ lub stan klasowy); kill() bez wait() (zombie) w _fail_proxy i _cleanup; resp stream=True niezamykany (with ... as resp); _fail_proxy nie zeruje _stderr_thread; literowka commitu fe177e9. test_is_available_with_env_creds_starts_proxy = straznik (nie RED).
Task 10: complete (commits 7ed3e8f..49c0d8c, review clean, 6 minor deferred)
BASE zad.11: 49c0d8c
Task 11: implementer DONE (c66975c, 801f3b1; 1634 passed, ruff OK, mypy 33). Review dispatched (opus).
Task 11: review -> 2 Important (flaga empty GPKG ignorowana -> NaN bbox/traceback; EWKB SRID bit zdejmowany bez przeskoku 4 B -> smieci). Ruling: EWKB SRID obslugiwany przez przeskok 4 bajtow (coord_off = offset+9 gdy bit 0x20000000) — koszt jesli zle: zaden (wariant rzadki w GPKG, ale kod deklaruje obsluge). minor (deferred): test rozjazdu endiannosci naglowek GPB vs WKB; walidacja bajtu kolejnosci WKB (not in (0,1) -> None); fixtura punktowa w 4326 dla sciezki transformacji.
Task 11: fix round 1/5 dispatched (FIX_BASE 801f3b1)
Task 11: fix round 1/5 (commit 7249066; re-review dispatched). Ruling: straznik empty na poziomie funkcji (pomija tez blob sprzeczny empty+envelope) — OK.
Task 11: fix round 1/5 (2 addressed, 0 open; commit 7249066)
Task 11: complete (commits 49c0d8c..7249066, review clean after round 1, 3 minor deferred)
BASE zad.12: 7249066
Task 12: implementer DONE (0737732, 281ed06, cc49b67; 1660 passed, ruff OK, mypy 33). Ruling: komunikat ValidationError z diakrytykami OK (spojnosc z plikiem); import _EDGE_TOL do parser_2000 OK. Zad.22: Changed — krawedzie/punkt w find_sheets_for_bbox, walidacja system. Review dispatched (opus).
Task 12: review -> 1 Important (plan-mandated: prog degeneracji <= _EDGE_TOL vs nakladka > _EDGE_TOL => bbox szer. (1e-9, 2e-9] deg cicho []). Ruling: prog degeneracji `> 2*_EDGE_TOL` w obu plikach + test; Minor 2 (punkt na poludniku granicy stref PL-2000 -> []) DOLACZONY do rundy (ruling punkt->1 arkusz obejmuje granice stref; rozszerzyc bbox_wgs84 przed detekcja stref) — koszt jesli zle: punkt na 19.5E dostaje arkusz strefy wschodniej (konwencja). minor (deferred): duplikat _expand_degenerate w parser_2000 (mozna importowac z eps); raport: bledna przeslanka ASCII parser_2000.py.
Task 12: fix round 1/5 dispatched (FIX_BASE cc49b67)
Task 12: fix round 1/5 (commit bf1f3e5; re-review dispatched)
Task 12: fix round 1/5 (2 addressed, 0 open; commit bf1f3e5). minor (deferred): _axis_overlaps nadal <= _EDGE_TOL (celowe); zad.22 CHANGELOG: bbox <= ~2e-9 jednostki traktowany jak punkt.
Task 12: complete (commits 7249066..bf1f3e5, review clean after round 1, 3 minor deferred)
BASE zad.13: bf1f3e5
Task 13: implementer DONE_WITH_CONCERNS (6e25022, 619679d, 22d08a6; 1670 passed, ruff OK, mypy 33); concern: guard przez atrybut WITHDRAWN_WCS_VERTICAL_CRS (NMT: EVRF2007; NMPT: ()), dotkniety gugik_nmpt.py. Review dispatched (opus).
Task 13: minor (deferred): gugik_orto.py:392 brak strazy na pusta liste warstw (all 0 failed); czesciowa awaria -> komunikat brak pokrycia bez info o k/n padlych (plan-mandated); 4xx liczone jako transport_error (OK); tresc ValidationError hardcoded EVRF2007/GugikProvider (uzyc self); manager.download_bbox docstring Raises bez ValidationError (zadanie docs).
Task 13: complete (commits bf1f3e5..22d08a6, review clean, 5 minor deferred)
BASE zad.14: 22d08a6
Task 14: implementer DONE (e972fbb, 3da41a1; 1674 passed, ruff OK, mypy 33). Review dispatched (sonnet).
Task 14: complete (commits 22d08a6..3da41a1, review clean, 0 minor)
BASE zad.15: 3da41a1
Task 15: implementer DONE (648fbf0; 1677 passed, ruff OK, mypy 33). Review dispatched (sonnet).
Task 15: minor (deferred): _generate_output_path nie roznicuje year/property/depth/format (pre-existing, kolizje plikow -> backlog zad.26); asymetria patcha _write_sidecar w tescie. Zad.22: BREAKING nazwy plikow download_by_* (CORINE Land Cover_N-34-130-D.gpkg -> corine_land_cover_godlo_N-34-130-D.gpkg).
Task 15: complete (commits 3da41a1..648fbf0, review clean, 2 minor deferred)
BASE zad.16: 648fbf0
Task 16: implementer DONE (9a8f229, 5ccdeb7, 8803981; 1680 passed, ruff OK, mypy 33); concerns: ValidationError z _create_provider_and_storage poza try (nieosiagalne); laz + resolution/vertical-crs nadal przechodzi (poza briefem). Review dispatched (opus).
Task 16: review -> 1 Important (plan-mandated getattr(manager,"last_result",None) martwy fallback + falszywy komentarz). Ruling: `summary = manager.last_result` wprost. Ruling (luka nieprzypisana, A2-3 w trybie --bbox/--geometry): `_download_godlo_list` akumuluje `last_result.failed` po KAZDYM download_sheet (petla nadpisuje last_result) i zwraca exit 1 z podsumowaniem, gdy jakikolwiek arkusz hierarchii padl — dolaczone do rundy 1 zad.16 — koszt jesli zle: bbox z grubym --scale konczy sie 1 zamiast 0 przy czesciowej porazce (pozadane). minor (deferred): getattr(args,"product","nmt") martwy fallback (3 miejsca); ValidationError z _create_provider_and_storage poza try (nieosiagalne dzis); --product orto --resolution 5m cicho przechodzi (no-op).
Task 16: fix round 1/5 dispatched (FIX_BASE 8803981)
Task 16: fix round 1/5 (commit aa23bfd; mypy 32). Ruling: listy godel z rozwinieciem hierarchii pobierane sekwencyjnie w _download_godlo_list (last_result wspoldzielony, nie thread-safe; hierarchia sama rownolegli na max_workers) — koszt jesli zle: brak rownoleglosci miedzy godlami grubymi (ale znika max_workers^2). Zmiana sygnatury _download_godlo_list (prywatna) OK. Kolejnosc komunikatu Error przed "Downloaded N files" — minor deferred. Re-review dispatched (opus).
Task 16: fix round 1/5 (2 addressed, 0 open; commit aa23bfd). minor (deferred): docstring summary _download_godlo_list niescisla; kolejnosc Error/Downloaded w trybie obszarowym; test_bbox_leaf_scale_stays_parallel nie pinuje rownoleglosci; no-op except-raise w puli (pre-existing). Zad.22: kody wyjscia CLI (godlo + obszar) + sygnatura _download_godlo_list.
Task 16: complete (commits 648fbf0..aa23bfd, review clean after round 1, 7 minor deferred). mypy baseline teraz 32.
BASE zad.17: aa23bfd
Task 17: implementer DONE_WITH_CONCERNS (b80b63b, 77690b1, 551b2e7; 1690 passed, ruff OK, mypy 32). Ruling (doprecyzowanie N6-2): auto->pl TYLKO gdy `len(countries) > 1 and "PL" in countries` (bbox w obu obwiedniach); bbox w calosci w CZ + flagi PL -> nadal blad "etap 2"; bbox tylko PL -> bez Info — koszt jesli zle: zaden (przypadek regresji pokryty identycznie). Zad.22: A6-3 tresc CHANGELOG o auto musi opisac nowa semantyke (auto->pl + czesciowy sukces). Review dispatched (opus).
Task 17: minor (deferred): tresc Warning orzeka "brak danych" (moze byc awaria serwera) — sformulowanie neutralne; TransformError w petli krajow -> 1 mimo czesciowego sukcesu (pre-existing, etap 2); em-dash w DECISIONS.md (plik juz mial); brak testu geometry + flaga PL (kod wspolny); sekwencja Info->Error przy --system+--target-crs (kosmetyka).
Task 17: complete (commits aa23bfd..551b2e7, review clean, 5 minor deferred)
BASE zad.18: 551b2e7
Task 18: implementer DONE (e6ca139, e190818; 1702 passed, ruff OK, mypy 32). Review dispatched (sonnet).
Task 18: minor (deferred): noqa BLE001 dekoracyjne (plan-mandated); --teryt help nie wspomina SoilGrids (generyczny, OK).
Task 18: complete (commits 551b2e7..e190818, review clean, 1 minor deferred)
BASE zad.19: e190818
Task 19: implementer DONE (cbaf1b4, 1205bcc; 1706 passed 0 warn; offline 1698 + 8 live). Review dispatched (opus).
Task 19: minor (deferred): [KANDYDAT do fali finalnej] blokada nie obejmuje socket.getaddrinfo (CI bez DNS -> cichy fallback) i sieci PROJ (pyproj.network.set_network_enabled) — dodac do conftest; connect_ex nieobjety (teoretyczne); snapshot WMS_LAYERS w fixture (przeniesc do fake_fetch); testy A8-5 pinuja wynik, nie galaz. Commit cbaf1b4 mowi 21 (faktycznie 20).
Task 19: complete (commits e190818..1205bcc, review clean, 5 minor deferred)
BASE zad.20: 1205bcc
Task 20: implementer DONE (6c22ac6; 1707 passed, ruff OK, mypy 32). Review dispatched (sonnet).
Task 20: complete (commits 1205bcc..6c22ac6, review clean, 1 minor redakcyjny)
BASE zad.21: 6c22ac6
Task 21: implementer DONE_WITH_CONCERNS (e37ffec, 4676008 — 2 commity przez blad pathspec, OK; 1708 passed, ruff OK, mypy 32). CHANGELOG wpis w briefie. Review dispatched (sonnet).
Task 21: complete (commits 6c22ac6..4676008, review clean, 2 minor: 2 commity; AST-readability __version__ zweryfikowana symulacja — build z setuptools do Checklisty release)
KANONICZNY PRZEBIEG po zad.21 (HEAD 4676008): 1708 passed (1708 collected), pokrycie 93% (5349 stmts, 397 miss), ruff check OK, ruff format OK, mypy 32 bledow w 9 plikach (baseline bylo 33).
BASE zad.22: 4676008
Task 22: implementer DONE_WITH_CONCERNS (c215ad0; +262/-55; 49/49 ID). Ruling: szosty naglowek Removed OK; przydzial sekcji wg briefu OK; ASCII-izacja 12 linii LAZ/orto OK. Review dispatched (opus).
Task 22: review -> 2 Important (Removed: "cmd_* bez zmian" a 4 z 9 usunietych to cmd_*; "21 testow" -> 20). Ruling: dolaczyc Minor 3 (tabela: bylo `[]` tylko PL-1992, PL-2000 bylo 4) i Minor 6 (odsylacze z Breaking Changes do: kod wyjscia 1 czesciowej hierarchii, katalog NMPT bez storage=, domyslne --country auto). Ruling: em-dash/strzalki w [0.7.0] OK (styl pliku); szosty naglowek Removed OK; _fetch_wms_layers w Tests OK; pokrycie 93% zostaje (ksztalt poprzedniego wpisu). minor (deferred): format ID w Added/Tests bez prefiksu "audyt 0.7.0:"; meta-uzasadnienie A6-16.
Task 22: fix round 1/5 dispatched (FIX_BASE c215ad0)
Task 22: fix round 1/5 (commit a282399; re-review dispatched)
Task 22: fix round 1/5 (4 addressed, 0 open; commit a282399). minor (deferred): etykieta A2-3 przy 2 wpisach (Changed i Fixed).
Task 22: complete (commits 4676008..a282399, review clean after round 1, 3 minor deferred)
BASE zad.23: a282399
Task 23: implementer DONE_WITH_CONCERNS (c5921f6, 2e2b1f5). Ruling: bbox 771000,509000,772000,510000 (wnetrze N-34-130-D-d-2-4) zamiast wartosci briefu OK. Do zad.24/25: A6-14 w docs/SCOPE.md:296 i docs/DECISIONS.md:576-577 (Krakow/Rzeszow -> Opole/Walbrzych/Rybnik). Review dispatched (opus).
Task 23: minor (deferred): [KANDYDAT do fali finalnej] README tabela sidecara: horizontal_crs (TM33 -> 3045; --target-crs -> zadany), transform = slownik osi; README auto->pl bez kwalifikatora "obszar sporny"; sekcja Funkcjonalnosci/NMT bez "(WCS: tylko KRON86)".
Task 23: complete (commits a282399..2e2b1f5, review clean, 4 minor deferred)
BASE zad.24: 2e2b1f5
Task 24: implementer DONE_WITH_CONCERNS (083c113, 2955a50, 85ebc29). Concern: timeouty BDOT10k (metody timeout=120 vs DEFAULT_TIMEOUT=60) i SoilGrids (bbox 120 / godlo 60) — CLAUDE.md:222 po zad.23 moze byc nieprecyzyjny -> do weryfikacji przez recenzenta, korekta w fali finalnej. Backlog (zad.26): deskryptor pl.gugik.nmpt bez kanalu WCS mimo dzialajacego download_bbox. Review dispatched (opus).
Task 24: minor (deferred): [KANDYDAT do fali finalnej] SCOPE.md:296-298 timeouty ("60 s selekcja przez godlo w Land Cover" — BDOT10k godlo = 120; CORINE TERYT = 120); IMPLEMENTATION_PROMPT.md:118 "/ 30s (WMS TERYT)" nieosiagalne (dziedziczy 120); PRD §5 eksporty CZ bez sekcji 3.x (odeslac do SCOPE 2.2); download_by_teryt alias wolany przez manager (backlog zad.26). [KANDYDAT do fali finalnej] CLAUDE.md:223-224 timeouty niezgodne (BDOT10k 120; SoilGrids 120 bbox / 60 godlo; LAZ 30 discovery / 60 kafle).
KANONICZNA TABELA TIMEOUTOW (z kodu, recenzent zad.24): NMT/NMPT 30 s; Ortofoto 60 s; LAZ 30 s discovery WFS / 60 s kafle; BDOT10k 120 s (wszystkie download_by_*, _get_teryt_for_point dziedziczy 120); CORINE 60 s (TERYT 120 s); CUZK 60 s; SoilGrids 120 s bbox / 60 s godlo; HSG 120 s.
Task 24: complete (commits 2e2b1f5..85ebc29, review clean, 4 minor deferred)
BASE zad.25: 85ebc29
Task 25: implementer DONE (5eaf744; 8 plikow). Review dispatched (sonnet).
Task 25: review -> 1 Important (rozszerzenie zakresu: korekta ilustracji A6-14 takze w ADR-023 pkt 5/addendum l.596-601). Ruling: ZAAKCEPTOWANE — brief 17 (Krok 6) odsylal korekte pkt 5 do zad.25, brief 25 mowil "nie dublowac"; sprzecznosc materialow, tresc poprawna i zgodna z CLAUDE.md/extent_wgs84; bez rundy — koszt jesli zle: zaden.
Task 25: complete (commits 85ebc29..5eaf744, review clean po rulingu, 0 minor)
BASE zad.26: 5eaf744
Task 26: implementer DONE (5aa09ff, 16d35ed). Pokrycie <80%: corine.py 54%, base.py 73% (auth/proxy.py 86%). A4-12 pominiety (rozwiazany w zad.8). Review dispatched (sonnet).
Task 26: review -> 1 Important (PROGRESS.md:483-487 "62 commity ... w tym zadanie 26" — faktycznie 64; rozklad 17 docs). Ruling: dolaczyc 2 Minor (tabela Status ~89%/1402 -> 93%/1708; DEVELOPMENT_STANDARDS 8.3 baseline 33 -> 32).
Task 26: fix round 1/5 dispatched (FIX_BASE 16d35ed)
Task 26: fix round 1/5 (commits e5728da, f10388c; re-review dispatched)
Task 26: fix round 1/5 (3 addressed, 0 open; commits e5728da, f10388c)
Task 26: complete (commits 5eaf744..f10388c, review clean after round 1)
WSZYSTKIE 26 ZADAN ZAMKNIETE. HEAD f10388c. Finalny review calej galezi (fable) dispatched na f432403..f10388c.
FINAL REVIEW (fable, audit/final-review.md): NEEDS ONE FIX WAVE. 0 Critical; I-1 __new__ singletonu proxy (N4-1 niedomkniety); I-2 allowlista moze blokowac presigned DownloadURL; I-3 timeouty CLAUDE/SCOPE/IMPL; I-4 README tabela sidecara; I-5 falszywe liczby. Global Constraints (a)-(l) wszystkie OK; suite deterministyczna (3 przebiegi), 0 DNS.
Ruling (F-2): IMPLEMENTOWAC — /download na host https spoza allowlisty forwarduje BEZ Authorization (token nie opuszcza allowlisty; presigned URL nie wymaga tokena; proxy nie zyskuje uprawnien, klient jest lokalny) — koszt jesli zle: proxy staje sie lokalnym relayem pobran https bez tokena (to samo, co klient moze zrobic sam); CHANGELOG + docstring.
Ruling (F-6): dolaczyc (neutralna tresc Warning).
Fala naprawcza: 1 implementer (opus), FIX_BASE f10388c.
Fala naprawcza: DONE_WITH_CONCERNS (3ee4315, 9c83390, a60053a, 2efcefc, 5dbd99c; 1716 testow (1708 + 8 live deselected -> lacznie 1716 collected), ruff OK, mypy 32). Ruling: liczba testow 1716 w docs OK. Re-review dispatched (opus).
