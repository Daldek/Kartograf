# Prog "pelnego pokrycia" - pomiar na danych (2026-10-13)

**Pytanie (decyzja 9.5 specu):** czy prog 99,9% wystarczy, zeby raport
dostepnosci wykrywal braki danych na krawedziach, czy potrzebne jest 100%
z tolerancja 1 piksela.

**Metoda:** skorowidz WFS `NumerycznyModelTerenuEVRF2007` (wszystkie
warstwy roczne) dla dwoch bboxow EPSG:2180; poligony arkuszy
zrasteryzowane (`rasterio.features.rasterize`, srodki pikseli) do maski
"pokrycie wg skorowidza"; pobrane wszystkie arkusze kombinacji, mozaika
(`rasterio.merge`), maska "sa dane" (wartosc != -9999); maska ladu PL
z PRG (`providers/pl/prg.py::fetch_land_mask`, ta sama co w wycinkach
ADR-035). Pliki: `<katalog-probek>/pokrycie/`.

## Wyniki

| Obszar (EPSG:2180, E/N) | Kombinacja | Arkusze (`czy_ark_wypelniony`) | Pokrycie bboxa wg skorowidza | Pokrycie bboxa danymi | Brak danych na ladzie w zasiegu skorowidza |
|---|---|---|---|---|---|
| Krakow 565000-569000 / 242000-246000, piksel 1 m | 2025, 1 m, PL-1992 | 6 x TAK | 100,0000% | 100,0000% | 0 px |
| Pomorze 339000-343000 / 744800-747000, piksel 0,5 m | 2022, 1 m, PL-1992 | 3 x TAK | 65,4602% | 57,7891% | 0 px (roznica = morze) |
| jw. | 2025, 0,5 m, PL-1992 | 4 x NIE | 100,0000% | 9,2931% | 294 830 px = 8,53% ladu |
| jw. | 2022, 0,5 m, PL-1992 | 1 x TAK, 3 x NIE | 100,0000% | 32,2303% | (nie liczono) |

Dodatkowo w Krakowie: kombinacje 2019/2022-2025 1 m i 2019 5 m maja
pokrycie wg skorowidza dokladnie 100,0000%; 2018 (1 m: 58,38%; 5 m i 25 m:
41,62%) - skorowidz zawiera tez rekordy 25 m.

## Wnioski

1. **Na krawedziach arkuszy nie ma brakow.** Mozaika 6 arkuszy TAK
   (Krakow) ma 100% danych; arkusze TAK na Pomorzu maja 0 pikseli bez
   danych na ladzie. Szczeliny miedzy poligonami skorowidza przy
   rasteryzacji 0,5-1 m: brak. Tolerancja 1 piksela nie jest potrzebna
   dla styku arkuszy.
2. **Prog wzgledny 99,9% jest szkodliwy:** 0,1% bboxa 4x4 km to 16 000 m2
   (np. pas 4 m wzdluz calego boku albo dziura 126x126 m) - raport
   nazwalby to "pelne". Poprawne dane daja dokladnie 100%, wiec prog
   nie jest potrzebny.
3. **Prawdziwe braki sa wewnatrz arkuszy `NIE` i skorowidz ich nie
   pokazuje:** poligon arkusza `NIE` to caly arkusz (pokrycie wg
   skorowidza 100%), a dane pokrywaja 91,5% ladu. Bez pobrania pliku
   (albo lokalnej wersji z `extra.coverage`, ADR-033/ADR-036 D13) nie da
   sie policzyc pokrycia takiej kombinacji.
4. **"Pelny arkusz" znaczy "pelny w granicach Polski"** (ADR-033):
   arkusze TAK nie maja danych nad morzem - pokrycie trzeba liczyc
   wzgledem ladu PL (maska PRG), inaczej bbox przy brzegu nigdy nie
   bedzie "pelny".

## Rekomendacja (do specu, K4)

- Pokrycie = ulamek pikseli **ladu PL** w obszarze (maska PRG) objetych
  arkuszami kombinacji; "pelne" = 100% (bez progu i bez tolerancji).
- Arkusz `NIE`: pokrycie z `extra.coverage` lokalnej wersji, jesli
  istnieje; w przeciwnym razie kombinacja z takim arkuszem ma status
  "pelnosc nieznana (arkusze niepelne: N)" zamiast liczby.
- Opcja `--measure` (pobiera arkusze `NIE` do magazynu i mierzy tresc,
  jak ADR-033) - do rozstrzygniecia w planie A.

## Dodatek: zasieg z kafli LAZ tej samej kampanii (opcje `--measure`)

Sprawdzone 2026-10-13 dla obszaru Pomorze i NMT 2025 0,5 m
(`DFT.7201.024.2024`): skorowidz LAZ (`SkorowidzDanychPomiarowychLIDAR2025`)
ma 21 kafli tego zgloszenia (11 `NIE`, 10 `TAK`). Suma poligonow kafli
pokrywa 100% ladu (kafle `NIE` to tez pelne poligony), a sama suma kafli
`TAK` daje 65,7% ladu przy faktycznych 91,5% danych NMT; 66 759 px
kafli `TAK` nie ma danych NMT. Kafle LAZ nie sa wiarygodnym zasiegiem
NMT/NMPT ani dolna granica pokrycia.
