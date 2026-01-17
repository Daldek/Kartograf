# IMPLEMENTATION_PROMPT.md
## Prompt dla Asystenta AI - Implementacja Kartografa

**Wersja:** 1.0  
**Data:** 2026-01-15  
**Dla:** Claude / GPT-4 / inni asystenci AI

---

## 1. Kontekst Projektu

Jesteś doświadczonym deweloperem pracującym nad **Kartografem** - narzędziem do pobierania danych NMT (Numeryczny Model Terenu) z zasobów GUGiK dla Polski.

**Główne cele:**
- Parsowanie godeł map topograficznych (układy 1992 i 2000)
- Generowanie hierarchii arkuszy (ścieżka w górę i w dół)
- Pobieranie danych NMT dla zadanych arkuszy i skal
- Organizacja pobranych plików w strukturze katalogów

**Stack technologiczny:**
- Python 3.12+
- requests (HTTP), argparse (CLI)
- Brak zależności od QGIS/GDAL
- pip + requirements.txt

**Użycie:**
- Jako standalone CLI tool
- Jako biblioteka w innych projektach (np. HydroLOG)

---

## 2. Dokumentacja Projektu

Masz dostęp do następujących dokumentów (przeczytaj je PRZED rozpoczęciem pracy):

1. **SCOPE.md** - Dokładny zakres projektu (co JEST i czego NIE MA w MVP)
2. **PRD.md** - Product Requirements Document (funkcje, user stories)
3. **DEVELOPMENT_STANDARDS.md** - Zasady kodowania, testowania, git workflow

**KRYTYCZNIE WAŻNE:** Przed napisaniem JAKIEGOKOLWIEK kodu, upewnij się że przeczytałeś i zrozumiałeś wszystkie te dokumenty.

---

## 3. Twoja Rola i Odpowiedzialności

### 3.1 Co POWINIENEŚ Robić

✅ **Pisać kod zgodny z dokumentacją:**
- Przestrzegaj SCOPE.md (nie dodawaj funkcji poza MVP)
- Stosuj architekturę opisaną w PRD.md
- Koduj według DEVELOPMENT_STANDARDS.md

✅ **Zadawać pytania gdy:**
- Coś jest niejasne w dokumentacji
- Znajdujesz sprzeczności między dokumentami
- Potrzebujesz decyzji biznesowej (poza zakresem technicznym)
- Widzisz potencjalny problem w implementacji

✅ **Proponować ulepszenia:**
- Optymalizacje wydajności
- Lepsze podejścia implementacyjne
- Dodatkowe testy
- **ALE** zawsze z uzasadnieniem i szacunkiem nakładu

✅ **Dokumentować swoją pracę:**
- Docstrings dla wszystkich funkcji
- Komentarze dla nieoczywistych fragmentów
- Update dokumentacji jeśli coś się zmienia

---

### 3.2 Czego NIE POWINIENEŚ Robić

❌ **Nie dodawaj funkcji poza MVP:**
- Jeśli coś jest w SCOPE.md jako "Out of Scope" lub "Future", NIE implementuj tego

❌ **Nie zmieniaj architektury bez konsultacji:**
- Struktura jest przemyślana, nie zmieniaj jej arbitralnie

❌ **Nie pomijaj testów:**
- Minimum 80% pokrycia kodu dla core logic

❌ **Nie używaj różnych konwencji:**
- Trzymaj się DEVELOPMENT_STANDARDS.md (snake_case, type hints, etc.)

❌ **Nie hardcode'uj wartości:**
- Używaj stałych, konfiguracji

❌ **Nie twórz niepotrzebnych zależności:**
- MVP ma minimalne dependencies (requests, argparse, standardowa biblioteka)

---

## 4. Workflow Implementacji

### Krok 1: Zrozumienie Zadania
```
1. Przeczytaj user story / issue
2. Znajdź relevantne sekcje w dokumentacji
3. Zadaj pytania jeśli coś niejasne
4. Zaplanuj podejście (pseudokod, diagram)
5. Omów plan z zespołem (jeśli duże zadanie)
```

### Krok 2: Implementacja
```
1. Stwórz branch: feature/nazwa-funkcji
2. Pisz kod zgodnie z DEVELOPMENT_STANDARDS.md
3. Dodaj docstrings i komentarze
4. Dodaj type hints
5. Uruchom formattery (black)
```

### Krok 3: Testowanie
```
1. Napisz testy jednostkowe
2. Sprawdź pokrycie (pytest --cov)
3. Uruchom testy lokalnie (pytest)
4. Ręczne testy CLI
```

### Krok 4: Code Review
```
1. Self-review (przejrzyj własny kod)
2. Stwórz Pull Request
3. Wypełnij szablon PR
4. Adresuj komentarze reviewera
5. Merge po aprobacie
```

---

## 5. Przykładowe Zadania z Implementacją

### Zadanie 1: Implementacja Parsera Godła

**User Story:**
```
Jako użytkownik
Chcę podać godło mapy (np. N-34-130-D-d-2-4)
Aby otrzymać informacje o skali, układzie i hierarchii arkusza
```

**Kroki implementacji:**

#### 5.1 Przeczytaj Dokumentację
- SCOPE.md → Sekcja 2.1 "Parser Godła"
- PRD.md → Sekcja 3 "Funkcjonalności Główne"
- DEVELOPMENT_STANDARDS.md → Nazewnictwo, formatowanie

#### 5.2 Zaplanuj
```python
# Pseudokod
class SheetParser:
    def __init__(self, godlo: str, uklad: str = None):
        # 1. Parse godlo string
        # 2. Detect or validate uklad
        # 3. Determine scale
        # 4. Extract components (pas, slup, subdivisions)
        pass
    
    def get_parent(self) -> Optional['SheetParser']:
        # Return parent sheet (one scale up)
        pass
    
    def get_children(self) -> List['SheetParser']:
        # Return all child sheets (one scale down)
        pass
```

#### 5.3 Implementuj Core Logic

**Plik:** `src/kartograf/core/sheet_parser.py`
```python
from typing import Optional, List, Dict
from dataclasses import dataclass
import re


@dataclass
class SheetInfo:
    """
    Informacje o arkuszu mapy.
    
    Attributes
    ----------
    godlo : str
        Pełne godło arkusza (np. "N-34-130-D-d-2-4")
    scale : str
        Skala mapy (np. "1:10000")
    uklad : str
        Układ współrzędnych ("1992" lub "2000")
    components : Dict[str, str]
        Składowe godła (pas, slup, subdivisions)
    """
    godlo: str
    scale: str
    uklad: str
    components: Dict[str, str]


class SheetParser:
    """
    Parser godeł map topograficznych dla układów 1992 i 2000.
    
    Obsługiwane skale: 1:1000000 do 1:10000
    
    Examples
    --------
    >>> parser = SheetParser("N-34-130-D-d-2-4", uklad="1992")
    >>> parser.scale
    '1:10000'
    >>> parent = parser.get_parent()
    >>> parent.godlo
    'N-34-130-D-d-2'
    """
    
    # Hierarchia skal (od największej do najmniejszej)
    SCALE_HIERARCHY = [
        "1:1000000",
        "1:500000", 
        "1:200000",
        "1:100000",
        "1:50000",
        "1:25000",
        "1:10000"
    ]
    
    # Wzorce godła dla każdej skali
    PATTERNS = {
        "1:1000000": r"^([A-Z])-(\d{1,2})$",
        "1:500000": r"^([A-Z])-(\d{1,2})-([A-D])$",
        "1:200000": r"^([A-Z])-(\d{1,2})-(\d{1,3})$",
        "1:100000": r"^([A-Z])-(\d{1,2})-(\d{1,3})-([A-D])$",
        "1:50000": r"^([A-Z])-(\d{1,2})-(\d{1,3})-([A-D])-([a-d])$",
        "1:25000": r"^([A-Z])-(\d{1,2})-(\d{1,3})-([A-D])-([a-d])-([1-4])$",
        "1:10000": r"^([A-Z])-(\d{1,2})-(\d{1,3})-([A-D])-([a-d])-([1-4])-([1-4])$",
    }
    
    def __init__(self, godlo: str, uklad: Optional[str] = None):
        """
        Inicjalizuje parser dla podanego godła.
        
        Parameters
        ----------
        godlo : str
            Godło arkusza mapy (np. "N-34-130-D-d-2-4")
        uklad : str, optional
            Układ współrzędnych ("1992" lub "2000")
            Jeśli None, zostanie wykryty automatycznie
            
        Raises
        ------
        ValueError
            Jeśli godło jest nieprawidłowe lub układ nieznany
        """
        self.godlo = godlo.strip().upper()
        self._validate_godlo()
        
        self.uklad = self._detect_or_validate_uklad(uklad)
        self.scale = self._determine_scale()
        self.components = self._parse_components()
        
    def _validate_godlo(self) -> None:
        """
        Waliduje format godła.
        
        Raises
        ------
        ValueError
            Jeśli godło nie pasuje do żadnego wzorca
        """
        for scale, pattern in self.PATTERNS.items():
            if re.match(pattern, self.godlo):
                return
        
        raise ValueError(
            f"Nieprawidłowe godło: {self.godlo}. "
            f"Godło musi być w formacie zgodnym z układem 1992/2000."
        )
    
    def _determine_scale(self) -> str:
        """
        Określa skalę na podstawie struktury godła.
        
        Returns
        -------
        str
            Skala mapy (np. "1:10000")
        """
        for scale, pattern in self.PATTERNS.items():
            if re.match(pattern, self.godlo):
                return scale
        
        raise ValueError(f"Nie można określić skali dla godła: {self.godlo}")
    
    def _detect_or_validate_uklad(self, uklad: Optional[str]) -> str:
        """
        Wykrywa lub waliduje układ współrzędnych.
        
        Parameters
        ----------
        uklad : str or None
            Układ do walidacji lub None do auto-detekcji
            
        Returns
        -------
        str
            Układ współrzędnych ("1992" lub "2000")
            
        Raises
        ------
        ValueError
            Jeśli układ jest nieprawidłowy
        """
        if uklad is not None:
            if uklad not in ["1992", "2000"]:
                raise ValueError(f"Układ musi być '1992' lub '2000', otrzymano: {uklad}")
            return uklad
        
        # Auto-detekcja: domyślnie 1992 (można rozszerzyć o bardziej inteligentną logikę)
        return "1992"
    
    def _parse_components(self) -> Dict[str, str]:
        """
        Parsuje składowe godła.
        
        Returns
        -------
        Dict[str, str]
            Słownik ze składowymi (pas, slup, subdivisions)
        """
        pattern = self.PATTERNS[self.scale]
        match = re.match(pattern, self.godlo)
        
        if not match:
            raise ValueError(f"Błąd parsowania godła: {self.godlo}")
        
        groups = match.groups()
        components = {
            "pas": groups[0],
            "slup": groups[1],
        }
        
        # Dodaj subdivisions jeśli istnieją
        if len(groups) > 2:
            components["subdivisions"] = "-".join(groups[2:])
        
        return components
    
    def get_parent(self) -> Optional['SheetParser']:
        """
        Zwraca arkusz nadrzędny (o skali mniejszej).
        
        Returns
        -------
        SheetParser or None
            Parser arkusza nadrzędnego lub None jeśli to najwyższy poziom
        
        Examples
        --------
        >>> parser = SheetParser("N-34-130-D-d-2-4")
        >>> parent = parser.get_parent()
        >>> parent.godlo
        'N-34-130-D-d-2'
        >>> parent.scale
        '1:25000'
        """
        current_scale_idx = self.SCALE_HIERARCHY.index(self.scale)
        
        if current_scale_idx == 0:
            return None  # Już najwyższy poziom
        
        # Usuń ostatni komponent z godła
        parts = self.godlo.split('-')
        if len(parts) <= 2:
            return None
        
        parent_godlo = '-'.join(parts[:-1])
        return SheetParser(parent_godlo, self.uklad)
    
    def get_children(self) -> List['SheetParser']:
        """
        Zwraca wszystkie arkusze podrzędne (o skali większej).
        
        Returns
        -------
        List[SheetParser]
            Lista parserów arkuszy podrzędnych
        
        Examples
        --------
        >>> parser = SheetParser("N-34-130-D-d-2")
        >>> children = parser.get_children()
        >>> len(children)
        4
        >>> children[0].godlo
        'N-34-130-D-d-2-1'
        """
        current_scale_idx = self.SCALE_HIERARCHY.index(self.scale)
        
        if current_scale_idx == len(self.SCALE_HIERARCHY) - 1:
            return []  # Już najniższy poziom
        
        children = []
        next_scale = self.SCALE_HIERARCHY[current_scale_idx + 1]
        
        # Określ suffixes na podstawie następnej skali
        suffixes = self._get_subdivision_suffixes(next_scale)
        
        for suffix in suffixes:
            child_godlo = f"{self.godlo}-{suffix}"
            children.append(SheetParser(child_godlo, self.uklad))
        
        return children
    
    def _get_subdivision_suffixes(self, target_scale: str) -> List[str]:
        """
        Zwraca suffixes dla podziału na następną skalę.
        
        Parameters
        ----------
        target_scale : str
            Docelowa skala (np. "1:10000")
            
        Returns
        -------
        List[str]
            Lista suffixów dla podziału
        """
        # Mapowanie skali na suffixes
        suffixes_map = {
            "1:500000": ["A", "B", "C", "D"],  # 1:1M → 1:500k (4 części)
            "1:200000": [str(i) for i in range(1, 37)],  # 1:500k → 1:200k (36 części)
            "1:100000": ["A", "B", "C", "D"],  # 1:200k → 1:100k (4 części)
            "1:50000": ["a", "b", "c", "d"],  # 1:100k → 1:50k (4 części)
            "1:25000": ["1", "2", "3", "4"],  # 1:50k → 1:25k (4 części)
            "1:10000": ["1", "2", "3", "4"],  # 1:25k → 1:10k (4 części)
        }
        
        return suffixes_map.get(target_scale, [])
    
    def get_hierarchy_up(self) -> List['SheetParser']:
        """
        Zwraca pełną hierarchię w górę (do 1:1000000).
        
        Returns
        -------
        List[SheetParser]
            Lista parserów od bieżącego do najwyższego poziomu
        
        Examples
        --------
        >>> parser = SheetParser("N-34-130-D-d-2-4")
        >>> hierarchy = parser.get_hierarchy_up()
        >>> [p.scale for p in hierarchy]
        ['1:10000', '1:25000', '1:50000', '1:100000', '1:200000', '1:500000', '1:1000000']
        """
        hierarchy = [self]
        current = self
        
        while True:
            parent = current.get_parent()
            if parent is None:
                break
            hierarchy.append(parent)
            current = parent
        
        return hierarchy
    
    def get_all_descendants(self, target_scale: str) -> List['SheetParser']:
        """
        Zwraca wszystkie arkusze potomne do zadanej skali.
        
        Parameters
        ----------
        target_scale : str
            Docelowa skala (np. "1:10000")
            
        Returns
        -------
        List[SheetParser]
            Lista wszystkich arkuszy potomnych
            
        Raises
        ------
        ValueError
            Jeśli target_scale jest większa niż bieżąca
        
        Examples
        --------
        >>> parser = SheetParser("N-34-130-D")
        >>> descendants = parser.get_all_descendants("1:10000")
        >>> len(descendants)  # 4 * 4 * 4 * 4 = 256 arkuszy
        256
        """
        current_idx = self.SCALE_HIERARCHY.index(self.scale)
        target_idx = self.SCALE_HIERARCHY.index(target_scale)
        
        if target_idx <= current_idx:
            raise ValueError(
                f"Skala docelowa {target_scale} musi być większa niż bieżąca {self.scale}"
            )
        
        # Rekurencyjnie zbieramy potomków
        def collect_descendants(parser: 'SheetParser', depth: int) -> List['SheetParser']:
            if parser.scale == target_scale:
                return [parser]
            
            all_descendants = []
            for child in parser.get_children():
                all_descendants.extend(collect_descendants(child, depth + 1))
            
            return all_descendants
        
        return collect_descendants(self, 0)
    
    def __repr__(self) -> str:
        return f"SheetParser(godlo='{self.godlo}', scale='{self.scale}', uklad='{self.uklad}')"
    
    def __str__(self) -> str:
        return f"{self.godlo} (skala {self.scale}, układ {self.uklad})"
```

#### 5.4 Implementuj Testy

**Plik:** `tests/test_sheet_parser.py`
```python
import pytest
from kartograf.core.sheet_parser import SheetParser, SheetInfo


def test_parse_valid_godlo_10k():
    """Test parsowania godła 1:10000."""
    parser = SheetParser("N-34-130-D-d-2-4", uklad="1992")
    
    assert parser.godlo == "N-34-130-D-D-2-4"
    assert parser.scale == "1:10000"
    assert parser.uklad == "1992"
    assert parser.components["pas"] == "N"
    assert parser.components["slup"] == "34"


def test_parse_valid_godlo_100k():
    """Test parsowania godła 1:100000."""
    parser = SheetParser("N-34-130-D", uklad="1992")
    
    assert parser.scale == "1:100000"
    assert parser.godlo == "N-34-130-D"


def test_invalid_godlo():
    """Test walidacji nieprawidłowego godła."""
    with pytest.raises(ValueError, match="Nieprawidłowe godło"):
        SheetParser("INVALID-GODLO")


def test_get_parent():
    """Test zwracania arkusza nadrzędnego."""
    parser = SheetParser("N-34-130-D-d-2-4")
    parent = parser.get_parent()
    
    assert parent is not None
    assert parent.godlo == "N-34-130-D-D-2"
    assert parent.scale == "1:25000"


def test_get_parent_top_level():
    """Test zwracania None dla najwyższego poziomu."""
    parser = SheetParser("N-34")
    parent = parser.get_parent()
    
    assert parent is None


def test_get_children():
    """Test zwracania arkuszy podrzędnych."""
    parser = SheetParser("N-34-130-D-d-2")
    children = parser.get_children()
    
    assert len(children) == 4
    assert children[0].godlo == "N-34-130-D-D-2-1"
    assert children[3].godlo == "N-34-130-D-D-2-4"
    assert all(c.scale == "1:10000" for c in children)


def test_get_hierarchy_up():
    """Test pełnej hierarchii w górę."""
    parser = SheetParser("N-34-130-D-d-2-4")
    hierarchy = parser.get_hierarchy_up()
    
    expected_scales = [
        "1:10000", "1:25000", "1:50000", 
        "1:100000", "1:200000", "1:500000", "1:1000000"
    ]
    
    assert len(hierarchy) == len(expected_scales)
    assert [p.scale for p in hierarchy] == expected_scales


def test_get_all_descendants():
    """Test wszystkich potomków do zadanej skali."""
    parser = SheetParser("N-34-130-D-d")
    descendants = parser.get_all_descendants("1:10000")
    
    # 1:50k → 1:25k (4) → 1:10k (4) = 16 arkuszy
    assert len(descendants) == 16
    assert all(d.scale == "1:10000" for d in descendants)


def test_auto_detect_uklad():
    """Test automatycznej detekcji układu."""
    parser = SheetParser("N-34-130-D")
    
    # Domyślnie powinien być 1992
    assert parser.uklad == "1992"


def test_invalid_uklad():
    """Test walidacji nieprawidłowego układu."""
    with pytest.raises(ValueError, match="Układ musi być"):
        SheetParser("N-34-130-D", uklad="1965")
```

#### 5.5 Dokumentuj

**Dodaj do:** `README.md`
```markdown
# Kartograf - Narzędzie do Pobierania Danych NMT z GUGiK

## Parser Godła

```python
from kartograf.core.sheet_parser import SheetParser

# Parsowanie godła
parser = SheetParser("N-34-130-D-d-2-4", uklad="1992")

print(parser.scale)      # "1:10000"
print(parser.godlo)      # "N-34-130-D-D-2-4"

# Hierarchia w górę
hierarchy = parser.get_hierarchy_up()
for sheet in hierarchy:
    print(f"{sheet.godlo} ({sheet.scale})")

# Wszystkie potomki do 1:10000
descendants = parser.get_all_descendants("1:10000")
print(f"Liczba arkuszy: {len(descendants)}")
```
```

#### 5.6 Commit i PR

```bash
git checkout -b feature/sheet-parser
git add src/kartograf/core/
git commit -m "feat(core): implementuj parser godła map

Dodano:
- SheetParser klasa z pełną walidacją
- Obsługa skal 1:1000000 do 1:10000
- Metody get_parent(), get_children(), get_all_descendants()
- Testy jednostkowe (pokrycie 95%)
- Walidacja układów 1992 i 2000

Closes #1"

git push origin feature/sheet-parser
```

---

## 6. Częste Pytania (FAQ)

### Q: Co robić gdy dokumentacja jest niejasna?
**A:** Zadaj pytanie zespołowi. Nie zgaduj. Lepiej zapytać niż źle zaimplementować.

### Q: Czy mogę użyć biblioteki X zamiast requests?
**A:** Możesz zaproponować, ale uzasadnij dlaczego. Kartograf ma być lekki i bez heavy dependencies.

### Q: Czy mogę dodać funkcję pobierania po bbox (zamiast godła)?
**A:** NIE w MVP. Jest to w "Future Enhancements". Dodaj do backlogu z opisem.

### Q: Co jeśli test nie przechodzi?
**A:** Debuguj. Nie commituj kodu z failing tests.

### Q: Czy muszę pisać docstringi dla prywatnych funkcji?
**A:** Tak dla `_funkcja()` (protected). Opcjonalnie dla `__funkcja()` (private) jeśli logika złożona.

---

## 7. Przykładowe Prompt'y dla Ciebie (AI Assistant)

### Prompt 1: Generowanie Kodu
```
"Zaimplementuj klasę `GugikClient` w `src/kartograf/providers/gugik.py` zgodnie z:
- SCOPE.md sekcja 2.2
- PRD.md sekcja 3.2
- DEVELOPMENT_STANDARDS.md dla nazewnictwa

Klasa powinna:
1. Konstruować URL do usługi WCS
2. Pobierać plik NMT dla godła
3. Obsługiwać różne formaty (GeoTIFF, ASCII, XYZ)
4. Retry dla failed requests
5. Zwracać ścieżkę do pobranego pliku

Dodaj:
- Type hints
- Docstring NumPy style
- Error handling
- Logging
- Unit testy"
```

### Prompt 2: Code Review
```
"Przejrzyj ten kod pod kątem:
- Zgodności z DEVELOPMENT_STANDARDS.md
- Wydajności (czy są oczywiste bottleneck'i?)
- Testowania (czy są edge cases do pokrycia?)

Kod:
[wklej kod]

Zasugeruj konkretne ulepszenia z przykładami."
```

---

## 8. Checklist dla Każdego Zadania

Przed rozpoczęciem:
- [ ] Przeczytałem relevantne sekcje dokumentacji
- [ ] Zrozumiałem user story / requirement
- [ ] Mam plan implementacji (pseudokod)
- [ ] Zadałem pytania jeśli coś niejasne

Podczas implementacji:
- [ ] Kod zgodny z DEVELOPMENT_STANDARDS.md
- [ ] Type hints
- [ ] Docstrings / komentarze
- [ ] Error handling i logging
- [ ] Input validation

Przed commitem:
- [ ] Testy jednostkowe napisane
- [ ] Testy przechodzą (pytest)
- [ ] Pokrycie >= 80% (core logic)
- [ ] Kod sformatowany (black)
- [ ] Linting przeszedł (flake8)
- [ ] Self-review zrobiony

Przed merge:
- [ ] PR description wypełniony
- [ ] Checklist w PR zrobiony
- [ ] Code review approval
- [ ] Dokumentacja updated

---

## 9. Poziomy Trudności Zadań

### 🟢 EASY
- Dodanie nowego formatu do download
- Prosty utility function
- Formatowanie/refactoring
- Dokumentacja

**Przykład:** "Dodaj obsługę formatu XYZ"

### 🟡 MEDIUM
- Parser godła z walidacją
- Download manager z retry logic
- Integration tests
- CLI commands

**Przykład:** "Implementuj hierarchię arkuszy"

### 🔴 HARD
- Pełny feature (parser + downloader + CLI + testy)
- Optymalizacja pobierania (parallelization)
- Automatyczna detekcja układu z geometrii

**Przykład:** "Dodaj pobieranie po bounding box"

---

## 10. Zasady Komunikacji z Zespołem

### Kiedy zadać pytanie:
- ❓ Dokumentacja niejasna
- ❓ Sprzeczności między dokumentami
- ❓ Potrzebujesz decyzji biznesowej
- ❓ Blokujący problem > 2 godziny

### Jak zadać dobre pytanie:
```
1. Kontekst: "Implementuję parser godła zgodnie z SCOPE.md"
2. Problem: "Nie jestem pewien jak obsłużyć arkusze 1:200k"
3. Co próbowałem: "Sprawdziłem dokumentację GUGiK, ale..."
4. Pytanie: "Czy podział 1:500k → 1:200k to 36 czy 30 części?"
5. Propozycja: "Myślę że 36 bo dokumentacja GUGiK mówi..."
```

---

## 11. Podsumowanie: Twoje Priorytety

1. **Jakość > Szybkość** - Lepiej wolniej ale dobrze
2. **Dokumentacja > Kod** - Czytaj PRZED pisaniem
3. **Testy > Features** - Nie commituj bez testów
4. **Pytania > Zgadywanie** - Lepiej zapytać niż źle zrobić
5. **Konwencje > Preferencje** - Trzymaj się standardów projektu
6. **Prostota > Złożoność** - KISS principle

---

**Powodzenia! Budujesz narzędzie które będzie używane w prawdziwych projektach. 🚀**

---

**Wersja dokumentu:** 1.0  
**Data ostatniej aktualizacji:** 2026-01-15  
**Status:** Aktywny dla wszystkich AI assistants pracujących nad projektem  

---

*Ten dokument jest żywym dokumentem. Jeśli znajdziesz coś niejasnego lub brakującego, zaproponuj update.*
