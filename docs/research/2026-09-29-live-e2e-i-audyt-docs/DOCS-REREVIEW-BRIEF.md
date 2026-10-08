# Przeglad fali poprawek dokumentacji (Kartograf, 2026-09-29) — zlecenie recenzenta

**Kontekst.** Repo `/home/claude-agent/workspace/Kartograf`, galaz `develop`. Po testach na zywych
danych (raporty `L1`..`L7-*-report.md`) i audycie dokumentacji (`D1`, `D2`) agent wykonal fale
poprawek DOKUMENTACJI: 12 commitow `152c31e..515f275` (BASE `152c31e`, HEAD `515f275`).
Wszystkie pliki ponizej leza w katalogu tego zlecenia:
`/home/claude-agent/workspace/Kartograf/.superpowers/sdd/2026-09-29-live-e2e-i-docs/`.

- wymagania fali: `DOCS-FIX-BRIEF.md`; raport wykonawcy: `DOCS-FIX-REPORT.md`;
- pakiet recenzji (log, stat, `diff -U10` calej fali): `DOCS-REVIEW-PACKAGE.diff` (4809 linii — czytaj
  partiami);
- zrodla prawdy: kod na HEAD; fakty z testow na zywo w `L1`..`L7-*-report.md`; audyty
  `D1-docs-uzytkownik-report.md`, `D2-docs-architektura-report.md`; lista bledow KODU `KNOWN-BUGS.md`
  (K1-K6, S1-S5, N1-N9, H1 — w tej fali swiadomie NIE naprawiane w kodzie; dokumenty maja je oznaczac,
  a nie opisywac bledne zachowanie jako zamierzone).

**Twoja rola: niezalezny recenzent.** Repo TYLKO DO ODCZYTU: zero edycji, zero commitow, zero
`git worktree`/`stash`/`checkout` (jedyny plik, ktory piszesz, to raport ponizej). Repo Hydrografu
`/home/claude-agent/workspace/Hydrograf` — tylko odczyt. Siec niepotrzebna. Nie uruchamiaj subagentow.
Pliki tymczasowe tylko w katalogu z `mktemp -d`.

## Co sprawdzic

1. **Kod bez zmian zachowania.** Uruchom skrypt AST (nizej) — kazdy zmieniony plik `.py` musi byc
   IDENTYCZNY po usunieciu docstringow (komentarze nie trafiaja do AST). Dla pliku "ROZNE"
   (spodziewany: `kartograf/cli/_parser.py`) wykaz, ze roznice to wylacznie literaly napisow
   w argumentach `help=`/`description=`/`epilog=`; kazda inna roznica (np. komunikat runtime,
   `choices`, domyslna wartosc) = znalezisko BLOKUJACE. Pliki bledow K1/K2/K6 nietkniete:
   `git diff --stat 152c31e..515f275 -- kartograf/providers/pl/gugik_laz.py kartograf/providers/cuzk kartograf/transform/crs.py`
   musi byc puste.
2. **Prawdziwosc.** Kazde NOWE lub ZMIENIONE twierdzenie o zachowaniu w diffie (dokumenty
   i docstringi) zweryfikuj na kodzie HEAD (`plik:linia`) albo w raporcie L/D (fakty z testow na
   zywo). CLAUDE.md (steruje kazda sesja agenta) i sekcje "Znane problemy" README sprawdz W CALOSCI;
   reszte probkuj szeroko, z priorytetem: CHANGELOG `[0.7.0]` (uwagi migracyjne 0.6.1 -> 0.7.0 —
   przeniesione moduly sprawdz importem, np. `.venv/bin/python -c "import kartograf.providers.pl.bdot10k"`,
   i ze stara sciezka nie istnieje), DECISIONS (erraty; ADR-024/K2 — liczby zgodne z L4
   i KNOWN-BUGS; ADR-021/K1), ARCHITECTURE, SCOPE, PRD, DEVELOPMENT_STANDARDS, IMPLEMENTATION_PROMPT,
   PROGRESS.
3. **Znane bledy.** Zadne zachowanie z `KNOWN-BUGS.md` nie jest opisane jako zamierzone lub
   projektowe; kazda wzmianka niesie ID zgodne z `KNOWN-BUGS.md` i tresc zgodna z jego opisem.
   `docs/PROGRESS.md`: tabela "Znane bledy" oraz podsekcja
   "#### Do naprawy — testy na zywych danych 2026-09-29 (przed wydaniem 0.7.0)" na poczatku
   "## Backlog" — kazde ID (K1-K6, S1-S5, N1-N9, H1) dokladnie raz jako checkbox; K2 i K6 z dopiskiem
   o odmrozeniu toru CZ (ADR-024); odsylacze `plik:linia` trafiaja w opisany kod na HEAD (sprawdz
   co najmniej 10).
4. **Odsylacze do raportow.** Dokumenty biezace odsylaja do
   `docs/research/2026-09-29-live-e2e-i-audyt-docs/<nazwa>` (katalog powstanie po tym review).
   Kontroler skopiuje tam DOKLADNIE te nazwy: `README.md`, `sdd-ledger.md`, `LIVE-COMMON.md`,
   `DOCS-COMMON.md`, `L1-centrum-produkty-report.md`, `L2-wycinki-siatka-report.md`,
   `L3-morze-report.md`, `L4-pogranicze-cz-report.md`, `L5-pogranicze-de-report.md`,
   `L6-inne-granice-report.md`, `L7-duzy-wycinek-report.md`, `D1-docs-uzytkownik-report.md`,
   `D2-docs-architektura-report.md`, `KNOWN-BUGS.md`, `DOCS-FIX-BRIEF.md`, `DOCS-FIX-REPORT.md`,
   `hydrograf-uwagi-migracyjne.md`, `DOCS-REREVIEW-BRIEF.md`, `DOCS-REREVIEW-REPORT.md`, `gfi/`
   (surowe odpowiedzi GetFeatureInfo). Zglos kazdy odsylacz do nazwy spoza tej listy oraz kazda
   sciezke `.superpowers/`, `/tmp/` lub `e2e-data/` podana w dokumencie biezacym jako miejsce, gdzie
   czytelnik ma cos znalezc.
5. **Liczby.** Kazda liczba wprowadzona w diffie pochodzi z raportu L/D/KNOWN-BUGS albo z pomiaru —
   sprawdz co najmniej 20 (np. 1861/8 testow, 92,9 %, 84 arkusze, 7721 B / 554 B, 1836/2394 arkuszy,
   36,4 s / 108,7 s, ~1 GiB, 2,3 m / 0,38 m, 1,1-4,9 m, 1,25/4,92 m, 13-50 %, 82 %, 766 px, 0,88 px,
   ~5,5 x 5,5 km, ~8 Mpx, 22 Mpx, 310-350 m, -0,19..+0,14 m, 21 %, 4,2 m, 5,2 m, 426 km, 2,0004 m).
6. **Spojnosc miedzy dokumentami.** To samo zachowanie opisane tak samo w CLAUDE.md, README,
   ARCHITECTURE, SCOPE, PRD i PROGRESS — co najmniej: tryb listy bez `--target-crs` (S2, zachowanie
   `--workers 1` vs `> 1`), `--country auto` i przycinanie do prostokata (S3), `missing_sheets`
   i pominiety wycinek (N4), R5 w wycinku, limit `exportImage` (K6), operacja S-JTSK (K2), LAZ (K1),
   `MetadataCache` (N6).
7. **Hydrograf.** Twierdzenia `hydrograf-uwagi-migracyjne.md` o kodzie, dokumentacji i cache
   Hydrografu — sprawdz co najmniej 5 w repo Hydrografu (tylko odczyt).
8. **Forma.** Pliki pisane bez polskich znakow zostaja bez nich (README ma diakrytyki — tam ich
   brak to usterka); `docs/DECISIONS.md` ma konce linii CRLF — porownaj liczbe linii CRLF i LF
   w BASE i HEAD (`git show 152c31e:docs/DECISIONS.md | grep -c $'\r$'`, analogicznie HEAD i
   `grep -vc $'\r$'`); brak pozostalosci roboczych w dokumentach biezacych (TODO, "kontroler",
   "agent", sciezki `/tmp`).
9. **Brama.** `.venv/bin/python -m pytest tests/ -q -m "not live" -p no:cacheprovider` (oczekiwane
   1861 passed, 8 deselected); `.venv/bin/python -m ruff check kartograf/ tests/` i
   `.venv/bin/python -m ruff format --check kartograf/ tests/`; mypy: lista bledow bez numerow linii
   na HEAD vs BASE — BASE rozpakuj przez `git archive 152c31e | tar -x -C "$(mktemp -d)"` i uruchom
   `.venv/bin/python -m mypy kartograf/` (sciezka do venv absolutna) z tego katalogu; porownaj
   `grep -E "error:" | sed -E 's/:[0-9]+: /: /' | sort` (oczekiwane 32 = 32, `diff` pusty).

Skrypt AST (pkt 1) — uruchom z katalogu repo:

```python
import ast, subprocess
BASE, HEAD = "152c31e", "515f275"
files = subprocess.run(
    ["git", "diff", "--name-only", f"{BASE}..{HEAD}", "--", "*.py"],
    capture_output=True, text=True, check=True,
).stdout.split()

def strip(src):
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            node.body = node.body[1:] or [ast.Pass()]
    return ast.dump(tree)

for f in files:
    old = subprocess.run(["git", "show", f"{BASE}:{f}"], capture_output=True, text=True, check=True).stdout
    new = subprocess.run(["git", "show", f"{HEAD}:{f}"], capture_output=True, text=True, check=True).stdout
    print(f, "IDENTYCZNE" if strip(old) == strip(new) else "ROZNE")
```

## Raport

Zapisz `DOCS-REREVIEW-REPORT.md` w katalogu tego zlecenia:

- **werdykt:** CZYSTO albo POPRAWKI POTRZEBNE;
- wyniki pkt 1-9 (polecenie + wynik);
- **tabela znalezisk:** ID (`RR-1`, `RR-2`, ...), waga — BLOKUJACE (falsz w CLAUDE.md, README lub
  docstringu API; bledne zachowanie opisane jako zamierzone; zmiana zachowania kodu), WAZNE (falsz
  albo niespojnosc w innym dokumencie biezacym; martwy odsylacz), DROBNE (forma, precyzja) — oraz
  `plik:linia` (HEAD), cytat, dowod (`plik:linia` kodu / raport / wynik polecenia) i proponowany
  tekst poprawki;
- lista sprawdzonych twierdzen (`plik:linia` -> OK + dowod), zeby bylo widac zakres;
- dokumenty historyczne (`docs/research/`, `docs/superpowers/`, datowane sekcje PROGRESS
  i CHANGELOG starszych wersji) poza zakresem — nie zglaszaj ich tresci.

Odpowiedz kontrolerowi krotko (<= 10 linii): werdykt, liczba znalezisk per waga, najwazniejsze.
