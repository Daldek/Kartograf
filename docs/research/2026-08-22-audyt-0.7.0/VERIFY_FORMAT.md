# Format raportu weryfikacji (obowiazkowy)

Plik: .superpowers/sdd/2026-08-22-release-0.7.0-audit/audit/<ID>-verify.md

Dla KAZDEGO ustalenia [Critical] i [Important] z raportu <ID>-report.md (ustalenia [Minor] pomin):

```
### <ID>-<n> — <tytul z raportu>
- Werdykt: CONFIRMED | REFUTED | DOWNGRADE(<nowa severity>) | DESIGN-DECISION
- Reprodukcja: <dokladna komenda/snippet ktory uruchomiles i jego wynik (skrot 1-5 linii); "nie da sie offline" jesli tak>
- Uzasadnienie: <1-3 zdania. Dla REFUTED: co audytor przeoczyl. Dla DOWNGRADE: dlaczego nizsza severity. Dla DESIGN-DECISION: jaka decyzja projektowa (ADR/CLAUDE.md/spec) to tlumaczy i czy mimo to wymaga zmiany docs.>
- Naprawa przed wydaniem 0.7.0: TAK | NIE (odlozyc) | DOCS-ONLY
- Zakres naprawy (tylko dla TAK/DOCS-ONLY): <pliki; 1-3 zdania co zmienic; jaki test to przypina; szacunek: S (<30 linii) / M / L; ryzyko regresji: niskie/srednie/wysokie>
```

Na koncu:
```
## Tabela
| ID | Werdykt | Naprawa 0.7.0 | Rozmiar | Ryzyko |
## Nowe ustalenia przy okazji (max 3, tylko jesli Critical/Important i z dowodem)
```

Zasady werdyktow:
- Domyslnie jestes SCEPTYKIEM: ustalenie jest CONFIRMED tylko gdy sam odtworzyles blad (snippet/test/komenda) albo dla docs — sam porownales tekst z kodem. "Wyglada na prawde" = nie wystarcza; wtedy uruchom reprodukcje.
- Sprawdz kontekst decyzji: docs/DECISIONS.md (ADR-001..024), CLAUDE.md sekcja "Ograniczenia", docs/SCOPE.md. Jesli zachowanie jest SWIADOMA decyzja — werdykt DESIGN-DECISION (ale jesli docs o tym milcza lub klamia — Naprawa=DOCS-ONLY).
- "Naprawa przed wydaniem: TAK" tylko gdy: blad jest realny, naprawa jest lokalna i testowalna, ryzyko regresji <= srednie. Duze refaktory (np. ujednolicenie retry we wszystkich providerach, zmiana hierarchii wyjatkow, zmiana publicznego API) => NIE (odlozyc) z uzasadnieniem, nawet jesli ustalenie jest sluszne.
- NIE modyfikuj plikow w repo. Tylko czytasz, uruchamiasz snippety offline (`.venv/bin/python`, `.venv/bin/python -m pytest ... -p no:cacheprovider`, `.venv/bin/kartograf --help`), piszesz raport. Pliki tymczasowe tylko w scratchpadzie.
- Jezyk: polski bez diakrytykow.
