# SCOPE.md - Zakres Projektu Kartograf
**Narzędzie do Pobierania Danych NMT z GUGiK**

**Wersja:** 1.0  
**Data:** 2026-01-15  
**Status:** MVP Definition

---

## 1. Cel Projektu

**Kartograf** to narzędzie do pobierania Numerycznego Modelu Terenu (NMT) z zasobów Głównego Urzędu Geodezji i Kartografii (GUGiK) dla Polski. 

### 1.1 Problem

Pobieranie danych NMT z GUGiK wymaga:
- Znajomości systemu godeł map topograficznych
- Ręcznego nawigowania przez interfejs webowy
- Pobierania arkuszy jeden po drugim
- Ręcznej organizacji pobranych plików

### 1.2 Rozwiązanie

Kartograf automatyzuje ten proces oferując:
- **Parser godeł** - walidacja i parsowanie godeł map
- **Hierarchia arkuszy** - automatyczne określanie arkuszy nadrzędnych i podrzędnych
- **Automatyczne pobieranie** - pobieranie wielu arkuszy jedną komendą
- **Organizacja plików** - automatyczna struktura katalogów odzwierciedlająca hierarchię

### 1.3 Użytkownicy

1. **Główny użytkownik (Piotr)** - deweloper HydroLOG potrzebujący danych NMT
2. **Specjaliści GIS** - pracownicy urzędów gmin potrzebujący danych topograficznych
3. **Inni deweloperzy** - wykorzystanie jako biblioteka w innych projektach

---

## 2. Zakres MVP

### 2.1 Core Functionality - IN SCOPE ✅

#### 2.1.1 Parser Godła
```python
# Funkcjonalności:
✅ Parsowanie godeł w układach 1992 i 2000
✅ Obsługa skal: 1:1 000 000 do 1:10 000
✅ Walidacja poprawności godła
✅ Automatyczna detekcja układu (domyślnie 1992)
✅ Ekstrakcja komponentów (pas, słup, subdivisions)

# Przykład:
parser = SheetParser("N-34-130-D-d-2-4", uklad="1992")
# → scale: "1:10000", components: {...}
```

#### 2.1.2 Hierarchia Arkuszy
```python
# Funkcjonalności:
✅ Ścieżka w górę - wszystkie arkusze nadrzędne do 1:1M
✅ Ścieżka w dół - wszystkie arkusze podrzędne do zadanej skali
✅ Walidacja spójności hierarchii

# Przykład:
hierarchy_up = parser.get_hierarchy_up()
# → [1:10000, 1:25000, 1:50000, ..., 1:1M]

descendants = parser.get_all_descendants("1:10000")
# → wszystkie arkusze 1:10k zawarte w bieżącym arkuszu
```

#### 2.1.3 Pobieranie NMT z GUGiK
```python
# Funkcjonalności:
✅ Pobieranie dla pojedynczego godła
✅ Pobieranie dla hierarchii (godło → wszystkie w dół do skali)
✅ Obsługa formatów: GeoTIFF (domyślny), Arc/Info ASCII Grid, XYZ
✅ Retry logic dla failed requests (3 próby)
✅ Progress tracking (ile pobranych / ile total)
✅ Resumowanie przerwanych pobrań (skip już pobranych)

# Przykład:
manager = DownloadManager(output_dir="./data")
paths = manager.download_hierarchy(
    godlo="N-34-130-D",
    target_scale="1:10000",
    format="GTiff"
)
# → lista ścieżek do pobranych plików
```

#### 2.1.4 Organizacja Plików
```
# Struktura katalogów:
data/
├── N-34/                     # Pas + Słup
│   ├── 130/                  # Podział 1:200k
│   │   ├── D/                # Podział 1:100k
│   │   │   ├── d/            # Podział 1:50k
│   │   │   │   ├── 2/        # Podział 1:25k
│   │   │   │   │   ├── 4/    # Podział 1:10k
│   │   │   │   │   │   ├── N-34-130-D-d-2-4.tif
│   │   │   │   │   │   ├── N-34-130-D-d-2-4.asc
│   │   │   │   │   │   └── N-34-130-D-d-2-4.xyz

✅ Hierarchiczna struktura katalogów
✅ Nazwa pliku = pełne godło + rozszerzenie
✅ Różne formaty w tym samym katalogu
```

#### 2.1.5 CLI Interface
```bash
# Funkcjonalności:
✅ Parsowanie i wyświetlenie informacji o godle
✅ Pobieranie pojedynczego arkusza
✅ Pobieranie hierarchii
✅ Wybór formatu pliku
✅ Wybór katalogu docelowego

# Komendy:
kartograf parse N-34-130-D-d-2-4                    # info o godle
kartograf download N-34-130-D --scale 1:10000       # pobierz hierarchię
kartograf download N-34-130-D-d-2-4 --format AAIGrid # jeden arkusz
```

#### 2.1.6 Python API (Biblioteka)
```python
# Funkcjonalności:
✅ Import jako biblioteka
✅ Obiektowy interfejs (SheetParser, DownloadManager)
✅ Type hints
✅ Docstrings

# Przykład użycia w HydroLOG:
from kartograf import SheetParser, DownloadManager

parser = SheetParser("N-34-130-D")
manager = DownloadManager(output_dir="./nmt_data")
manager.download_hierarchy(parser, target_scale="1:10000")
```

---

### 2.2 Architecture - IN SCOPE ✅

#### 2.2.1 Moduły
```
src/kartograf/
├── core/                  # Logika główna
│   ├── sheet_parser.py    # Parser godła
│   └── hierarchy.py       # Operacje na hierarchii
├── providers/             # Providery danych
│   ├── base.py            # Abstrakcyjna klasa Provider
│   └── gugik.py           # Implementacja dla GUGiK
├── download/              # Download management
│   ├── manager.py         # Zarządzanie pobieraniem
│   └── storage.py         # Organizacja plików
└── cli/                   # CLI interface
    └── commands.py        # Komendy argparse
```

#### 2.2.2 Zależności
```
Python 3.12+
requests       # HTTP client
argparse       # CLI (stdlib)
typing         # Type hints (stdlib)
dataclasses    # Data structures (stdlib)
logging        # Logging (stdlib)
pathlib        # Path operations (stdlib)
```

---

### 2.3 Testing - IN SCOPE ✅

```python
# Pokrycie kodu:
✅ Minimum 80% dla core logic (sheet_parser, gugik, manager)
✅ Opcjonalnie < 80% dla CLI

# Typy testów:
✅ Unit tests - wszystkie moduły
✅ Integration tests - download flow
✅ Mock HTTP responses dla testów

# Test framework:
✅ pytest
✅ pytest-cov (coverage)
✅ unittest.mock (mocking)
```

---

### 2.4 Documentation - IN SCOPE ✅

```markdown
✅ README.md - quick start, podstawowe przykłady
✅ SCOPE.md - ten dokument
✅ PRD.md - funkcjonalności, user stories
✅ IMPLEMENTATION_PROMPT.md - dla AI assistants
✅ DEVELOPMENT_STANDARDS.md - standardy kodowania
✅ Docstrings - wszystkie public funkcje/klasy
✅ Type hints - wszędzie
```

---

## 3. Out of Scope - MVP ❌

### 3.1 Funkcjonalności Zaawansowane - FUTURE 🔮

```python
# Te funkcje będą w przyszłych wersjach:

❌ Pobieranie po bounding box (zamiast godła)
   # Przykład:
   # manager.download_for_bbox(
   #     bbox=[50.0, 19.0, 51.0, 20.0],
   #     scale="1:10000"
   # )

❌ Automatyczne mozaikowanie (merge wielu arkuszy)
   # Wymaga GDAL/rasterio

❌ Pobieranie równoległe (multi-threading)
   # MVP: sekwencyjne pobieranie

❌ GUI interface (okienkowy)
   # MVP: tylko CLI + Python API

❌ Websocket progress notifications
   # MVP: console progress

❌ Inteligentna detekcja układu z geometrii arkusza
   # MVP: użytkownik podaje układ lub domyślnie 1992

❌ Cache dla metadanych arkuszy
   # MVP: każde wywołanie parsuje od zera

❌ Pobieranie innych danych niż NMT (ortofotomapy, LIDAR, etc.)
   # MVP: tylko NMT
```

### 3.2 Optymalizacje - FUTURE 🔮

```python
❌ Async/await dla HTTP requests
   # MVP: synchroniczne requests

❌ Connection pooling
   # MVP: pojedyncze requesty

❌ Kompresja pobranych plików
   # MVP: pliki jak z serwera

❌ Automatyczne usuwanie starych wersji
   # MVP: append only (nie kasuje)
```

### 3.3 Integracje - FUTURE 🔮

```python
❌ Integracja z PostGIS (import do bazy)
   # MVP: tylko pliki na dysku

❌ Upload do cloud storage (S3, GCS)
   # MVP: tylko lokalny filesystem

❌ Webhook notifications po zakończeniu
   # MVP: synchroniczne wykonanie

❌ REST API server
   # MVP: tylko biblioteka + CLI
```

---

## 4. Założenia i Ograniczenia

### 4.1 Założenia

```
✅ Użytkownik ma dostęp do internetu
✅ Serwery GUGiK są dostępne i działają
✅ Użytkownik ma wystarczająco miejsca na dysku
✅ Python 3.12+ zainstalowany
✅ Użytkownik zna układ współrzędnych lub używa domyślnego (1992)
```

### 4.2 Ograniczenia MVP

```
⚠️ Jeden format na wywołanie (nie można pobrać GeoTIFF + ASCII jednocześnie)
⚠️ Brak weryfikacji poprawności pobranych plików (integrity check)
⚠️ Brak inteligentnej kolejki priorytetowej (FIFO)
⚠️ Timeout dla pojedynczego arkusza: 30s (nie konfigurowalne)
⚠️ Max 3 próby retry (nie konfigurowalne)
⚠️ Brak statystyk pobierania (ile MB, średni czas, etc.)
```

### 4.3 Limity Techniczne

```
📊 Maksymalna liczba arkuszy na wywołanie: Bez limitu*
   * Ale może być czasochłonne dla dużych hierarchii

📊 Maksymalny rozmiar pojedynczego pliku: ~50MB
   (typowy rozmiar arkusza NMT 1:10k)

📊 Request timeout: 30s

📊 Retry delay: 1s, 2s, 4s (exponential backoff)
```

---

## 5. Success Criteria MVP

### 5.1 Funkcjonalne

```
✅ Parser poprawnie parsuje wszystkie godła z zakresu 1:1M - 1:10k
✅ Hierarchia poprawnie generuje ścieżki w górę i w dół
✅ DownloadManager pobiera pliki NMT z GUGiK
✅ Pliki organizowane w poprawnej strukturze katalogów
✅ CLI pozwala na podstawowe operacje bez kodu Python
✅ Może być używany jako biblioteka w HydroLOG
```

### 5.2 Jakościowe

```
✅ Pokrycie testami ≥ 80% dla core logic
✅ Wszystkie public funkcje mają docstrings
✅ Type hints wszędzie
✅ Kod zgodny z black + flake8
✅ Dokumentacja kompletna i aktualna
```

### 5.3 Performance

```
✅ Parsowanie godła < 0.1s
✅ Pobieranie arkusza < 30s (network dependent)
✅ Generowanie hierarchii dla 256 arkuszy < 1s
```

---

## 6. Roadmap Poza MVP

### Wersja 1.1 - Optymalizacje
- Pobieranie równoległe (multi-threading)
- Connection pooling
- Cache dla metadanych

### Wersja 1.2 - BBox Support
- Pobieranie po bounding box
- Automatyczne mozaikowanie (wymaga GDAL)

### Wersja 2.0 - Advanced
- GUI interface
- Pobieranie innych danych (ortofotomapy, LIDAR)
- Integration z PostGIS

---

## 7. Zmiany w Zakresie

| Data | Wersja | Zmiana | Autor |
|------|--------|--------|-------|
| 2026-01-15 | 1.0 | Initial scope definition | Piotr |

---

**Ważne:**  
Ten dokument definiuje TYLKO zakres MVP. Wszystkie funkcje "Out of Scope" mogą być dodane w przyszłych wersjach po dokładnej analizie i planowaniu.

**Pytania lub propozycje zmian?**  
Otwórz issue z tagiem `scope-change` i opisz proponowaną zmianę wraz z uzasadnieniem.

---

**Wersja dokumentu:** 1.0  
**Data ostatniej aktualizacji:** 2026-01-15  
**Status:** Approved - MVP Definition  

---

*Scope freeze po zatwierdzeniu tego dokumentu. Zmiany wymagają uzasadnienia i approval.*
