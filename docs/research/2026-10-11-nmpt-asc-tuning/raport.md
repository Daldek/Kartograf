# Strojenie kawalkow ASC NMPT (WCS GUGiK)

**Data:** 2026-10-11 (16:35-17:55)
**Backlog:** "Do 0.7.2" — strojenie kawalkow ASC NMPT (z
`docs/research/2026-10-11-wcs-cutouts-live/raport.md` pkt 4-5)
**Srodowisko:** jednorazowe skrypty `requests` + `rasterio` z `.venv`;
skrypty, log `probe.jsonl` i rastry poza repo (katalog wskazany przez
uzytkownika). Host w trakcie pomiaru NIE byl spokojny (zawieszenia
i zerwania polaczen przez caly przebieg).

## 1. Pierwszy bajt w funkcji rozmiaru kawalka

Zapytania `image/x-aaigrid` na siatce arkuszy 1 m (`k + 0,5`), kwadraty
500/1000/1414/2000 px wyniku, kazde w innym miejscu (krok 2,5 km),
kolejnosc losowa, sekwencyjnie, timeout odczytu 300 s. NMPT
z `SCALEFACTOR=0.5` (4 piksele coverage na piksel wyniku). Przerwane po
28 z 36 zapytan (limit czasu sesji).

| Kawalek (Mpx coverage) | NMT EVRF2007 | NMPT EVRF2007 | NMPT KRON86 |
|---|---|---|---|
| 0,25 | 13,9 s; HANG | — | — |
| 1 | 17,1 s; CE x2 | HANG; CE x2 | 26,9 s; 11,3 s; CE |
| 2 | 30,2 s; 51,4 s; HANG | — | — |
| 4 | HANG x2 | 25,6 s; HANG | 15,2 s; HANG x2 |
| 8 | — | 103,6 s; 62,6 s; CE | HANG |
| 16 | — | CE | 42,2 s (calosc 167,7 s, 82 MB) |

HANG = brak bajtu przez 300 s (`ReadTimeout`), CE = `ConnectionError` po
ok. 10 s. Razem: 11 odpowiedzi, 9 zawieszen, 8 zerwan.

- Zawieszenia trafiaja kawalki kazdego rozmiaru (od 0,25 do 8 Mpx); 9 z 20
  zapytan bez zerwania. Nie ma rozmiaru, ponizej ktorego host nie wisi.
- Udane kawalki 4 Mpx coverage: pierwszy bajt 15-26 s, jak 1 Mpx
  (11-27 s). 8 Mpx: 63-104 s — za blisko limitu 120 s.
- Po pierwszym bajcie transfer ok. 20 MB/Mpx wyniku, 3-26 s na kawalek
  do 2 Mpx.

## 2. Wniosek i zmiana

Kazdy kawalek to osobne "losowanie" zawieszenia, ktore kosztuje
`WCS_ASC_READ_TIMEOUT` = 120 s, a 3 nieudane proby kawalka koncza cale
zadanie. Przy stalym prawdopodobienstwie zawieszenia mniej kawalkow
oznacza mniej ponowien i mniejsza szanse porazki zadania. Budzet NMPT
0,25 Mpx wyniku (1 Mpx coverage) dawal 4 razy wiecej kawalkow niz
4 Mpx coverage przy takim samym czasie odpowiedzi.

- `GugikNmptProvider.WCS_CHUNK_LIMITS_AAIGRID`: 4 Mpx pikseli coverage
  = 1 Mpx wyniku 1 m (dotad 1 Mpx coverage z `GugikWcsMixin`).
- NMT EVRF2007 bez zmian (1 Mpx; oba zapytania 4 Mpx zawisly — za malo
  danych, decyzja uzytkownika).
- `WCS_ASC_READ_TIMEOUT` bez zmian (120 s): pierwszy bajt NMPT 1 Mpx
  coverage dochodzil do 106 s (raport live 2026-10-11 pkt 5), nizszy
  limit przerywalby poprawne zapytania.

## 3. Weryfikacja na zywo

`GugikNmptProvider(vertical_crs="EVRF2007").download_bbox` obszaru
567100,5-569100,5 x 243000,5-244000,5 (2000 x 1000 px, jak raport live
pkt 4):

| Wariant | Kawalki | Czas | Ponowienia |
|---|---|---|---|
| przed zmiana (raport live pkt 4) | 8 x 0,25 Mpx | 1186 s | 7 z 8 kawalkow |
| po zmianie | 2 x 1000 x 1000 px | 246 s | 1 (kawalek 2/2, `Read timed out` 120 s) |
| jedno zapytanie (kontrola) | 1 | 205 s | 1 |

Wynik kawalkami = jedno zapytanie bit w bit (2 000 000 / 2 000 000 px,
ta sama transformacja; wysokosci 193,83-289,26 m).
