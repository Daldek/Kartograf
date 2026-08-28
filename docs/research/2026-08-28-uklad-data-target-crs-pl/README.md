# Artefakty sesji: uklad data/ per produkt + --target-crs dla PL (2026-08-28)

Zapis procesu wdrozenia planu
`docs/superpowers/plans/2026-08-28-uklad-data-i-target-crs-pl.md`
(12 zadan TDD + finalny review calej galezi + fala naprawcza).
Skopiowane z gitignorowanego workspace'u SDD, zeby nie przepadly —
w etapie 1 ledger zaginal razem z workspace'em.

| Plik | Co zawiera |
|---|---|
| `sdd-ledger.md` | Dziennik sesji: dispatche, wyniki review, **wszystkie rulingi kontrolera** z kosztem pomylki, pozycje zaparkowane |
| `preflight-report.md` | Audyt planu PRZED implementacja (~90 konkretow sprawdzonych na zywym repo; 1 blokujacy, 4 wazne, 12 drobnych) |
| `final-review-fix-brief.md` | Lista N-01..N-11 z finalnego review calej galezi, z dowodami i rulingami |
| `final-review-fix-report.md` | Raport fali naprawczej: 11/11 zamkniete, 21 dowodow mutacyjnych |

## Co warto stad zapamietac

1. **Defekt miedzyzadaniowy wychodzi dopiero w finalnym review.** Zapas zrodla
   wycinka (`_PL_WARP_MARGIN_PX`) dzialal w torze `--bbox`, ale nie w
   `--geometry` — 8,4 % pikseli `nodata` przy 0 % obok. Zaden review per
   zadanie nie mogl tego zobaczyc.
2. **Testy trzeba weryfikowac mutacja, nie lektura.** W tej galezi szesc
   testow nie bronilo niczego; kazdy wykryto dopiero przez celowe zepsucie
   kodu. M.in. mutacja usuwajaca poszerzony bbox z selekcji arkuszy
   przechodzila 1775/1775.
3. **Dokumentacja klamie czesciej, niz kod.** Osiem razy dokument, komentarz,
   help albo gotowy tekst planu opisywal zachowanie, ktorego kod nie mial
   (m.in. obietnica maskowania nodata do geometrii, rozmiar arkusza zawyzony
   2,4x i rozniesiony po trzech plikach, tabela migracji ze sztywnym
   `pl_1992` tam, gdzie kod ma `{uklad}`).
