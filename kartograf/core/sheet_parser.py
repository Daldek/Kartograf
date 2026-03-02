"""
Parser godeł map topograficznych dla układów 1992 i 2000.

This module provides the SheetParser class for parsing Polish topographic
map sheet identifiers (godła) and extracting information about scale,
coordinate system, and sheet components.
"""

from __future__ import annotations

import math
import re
from typing import NamedTuple

from pyproj import Transformer

from kartograf.exceptions import ParseError, ValidationError


def _is_pl2000_format(godlo: str) -> bool:
    """Check if godlo uses PL-2000 dot-separated numeric format."""
    return bool(re.match(r"^[5-8]\.\d", godlo))


class BBox(NamedTuple):
    """Bounding box z współrzędnymi i układem odniesienia."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float
    crs: str


class SheetParser:
    """
    Parser godeł map topograficznych dla układów 1992 i 2000.

    Obsługiwane skale: 1:1000000 do 1:10000

    Attributes
    ----------
    godlo : str
        Znormalizowane godło arkusza (np. "N-34-130-D-d-2-4")
    scale : str
        Skala mapy (np. "1:10000")
    uklad : str
        Układ współrzędnych ("1992" lub "2000")
    components : Dict[str, str]
        Składowe godła (pas, slup, oraz opcjonalne subdivisions)

    Examples
    --------
    >>> parser = SheetParser("N-34-130-D-d-2-4", uklad="1992")
    >>> parser.scale
    '1:10000'
    >>> parser.components
    {'pas': 'N', 'slup': '34', 'arkusz_200k': '130', 'arkusz_100k': 'D',
     'arkusz_50k': 'd', 'arkusz_25k': '2', 'arkusz_10k': '4'}
    """

    # Hierarchia skal (od największej do najmniejszej)
    SCALE_HIERARCHY = [
        "1:1000000",
        "1:500000",
        "1:200000",
        "1:100000",
        "1:50000",
        "1:25000",
        "1:10000",
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

    # Nazwy komponentów dla każdej grupy w regex
    COMPONENT_NAMES = [
        "pas",
        "slup",
        "arkusz_200k",
        "arkusz_100k",
        "arkusz_50k",
        "arkusz_25k",
        "arkusz_10k",
    ]

    # Dozwolone układy współrzędnych
    VALID_UKLADY = ("1992", "2000")

    def __init__(self, godlo: str, uklad: str | None = None):
        """
        Inicjalizuje parser dla podanego godła.

        Parameters
        ----------
        godlo : str
            Godło arkusza mapy (np. "N-34-130-D-d-2-4")
        uklad : str, optional
            Układ współrzędnych ("1992" lub "2000").
            Jeśli None, zostanie ustawiony domyślnie na "1992".

        Raises
        ------
        ParseError
            Jeśli godło jest nieprawidłowe lub nie pasuje do żadnego wzorca.
        ValidationError
            Jeśli układ jest nieprawidłowy.

        Examples
        --------
        >>> parser = SheetParser("N-34-130-D", uklad="1992")
        >>> parser.scale
        '1:100000'
        """
        if not isinstance(godlo, str):
            raise ParseError(f"Godło musi być stringiem, otrzymano: {type(godlo)}")

        cleaned = godlo.strip()
        if not cleaned:
            raise ParseError("Godło nie może być puste")

        # Auto-detect PL-2000 format (dots + digits only, starts with 5-8)
        if _is_pl2000_format(cleaned):
            from kartograf.core.parser_2000 import Parser2000

            if uklad is not None and uklad != "2000":
                raise ValidationError(
                    f"Godło '{cleaned}' ma format PL-2000, ale podano uklad='{uklad}'"
                )
            self._pl2000 = Parser2000(cleaned)
            self._original_godlo = cleaned
            self._godlo = self._pl2000.godlo
            self._uklad = "2000"
            self._scale = self._pl2000.scale
            self._components = self._pl2000.components
        else:
            if uklad is not None and uklad == "2000":
                raise ValidationError(
                    f"Godło '{cleaned}' ma format PL-1992, ale podano uklad='2000'"
                )
            self._pl2000 = None
            self._original_godlo = cleaned

            # Normalizacja godła (zachowuj małe litery dla arkuszy 50k i mniejszych)
            self._godlo = self._normalize_godlo(self._original_godlo)

            # Walidacja i ustawienie układu
            self._uklad = self._validate_uklad(uklad)

            # Określenie skali i walidacja formatu
            self._scale = self._determine_scale()

            # Parsowanie komponentów
            self._components = self._parse_components()

    def _normalize_godlo(self, godlo: str) -> str:
        """
        Normalizuje godło do standardowego formatu.

        Litera pasa (pierwsza) i litery arkuszy 100k są uppercase.
        Litery arkuszy 50k i mniejszych są lowercase.

        Parameters
        ----------
        godlo : str
            Oryginalne godło

        Returns
        -------
        str
            Znormalizowane godło
        """
        parts = godlo.split("-")
        if len(parts) < 2:
            return godlo  # Zwróć bez zmian, walidacja zgłosi błąd

        normalized = []

        for i, part in enumerate(parts):
            if i == 0:
                # Pas literowy - zawsze uppercase
                normalized.append(part.upper())
            elif i == 3:
                # Arkusz 100k (A-D) - uppercase
                normalized.append(part.upper())
            elif i == 4 and len(part) == 1 and part.upper() in "ABCD":
                # Arkusz 50k (a-d) - lowercase
                normalized.append(part.lower())
            else:
                # Pozostałe części bez zmian
                normalized.append(part)

        return "-".join(normalized)

    def _validate_uklad(self, uklad: str | None) -> str:
        """
        Waliduje układ współrzędnych.

        Parameters
        ----------
        uklad : str or None
            Układ do walidacji lub None dla domyślnego

        Returns
        -------
        str
            Układ współrzędnych ("1992" lub "2000")

        Raises
        ------
        ValidationError
            Jeśli układ jest nieprawidłowy
        """
        if uklad is None:
            return "1992"  # Domyślny układ

        if uklad not in self.VALID_UKLADY:
            raise ValidationError(
                f"Nieprawidłowy układ: '{uklad}'. "
                f"Dozwolone wartości: {', '.join(self.VALID_UKLADY)}"
            )

        return uklad

    def _determine_scale(self) -> str:
        """
        Określa skalę na podstawie struktury godła.

        Returns
        -------
        str
            Skala mapy (np. "1:10000")

        Raises
        ------
        ParseError
            Jeśli godło nie pasuje do żadnego wzorca
        """
        for scale, pattern in self.PATTERNS.items():
            if re.match(pattern, self._godlo):
                return scale

        raise ParseError(
            f"Nieprawidłowe godło: '{self._original_godlo}'. "
            f"Godło musi być w formacie zgodnym z układem 1992/2000."
        )

    def _parse_components(self) -> dict[str, str]:
        """
        Parsuje składowe godła.

        Returns
        -------
        Dict[str, str]
            Słownik ze składowymi godła
        """
        pattern = self.PATTERNS[self._scale]
        match = re.match(pattern, self._godlo)

        if not match:
            raise ParseError(f"Błąd parsowania godła: {self._godlo}")

        groups = match.groups()
        components = {}

        for i, value in enumerate(groups):
            components[self.COMPONENT_NAMES[i]] = value

        return components

    @property
    def godlo(self) -> str:
        """Zwraca znormalizowane godło arkusza."""
        return self._godlo

    @property
    def scale(self) -> str:
        """Zwraca skalę mapy."""
        return self._scale

    @property
    def uklad(self) -> str:
        """Zwraca układ współrzędnych."""
        return self._uklad

    @property
    def components(self) -> dict[str, str]:
        """Zwraca słownik ze składowymi godła."""
        return self._components.copy()

    def __repr__(self) -> str:
        """Zwraca reprezentację obiektu do debugowania."""
        return (
            f"SheetParser(godlo='{self._godlo}', "
            f"scale='{self._scale}', uklad='{self._uklad}')"
        )

    def __str__(self) -> str:
        """Zwraca czytelną reprezentację arkusza."""
        return f"{self._godlo} (skala {self._scale}, układ {self._uklad})"

    def __eq__(self, other: object) -> bool:
        """Porównuje dwa parsery na podstawie godła i układu."""
        if not isinstance(other, SheetParser):
            return NotImplemented
        return self._godlo == other._godlo and self._uklad == other._uklad

    def __hash__(self) -> int:
        """Zwraca hash obiektu."""
        return hash((self._godlo, self._uklad))

    # =========================================================================
    # Metody hierarchii
    # =========================================================================

    # Mapowanie skal na suffiksy dla dzieci
    _CHILD_SUFFIXES = {
        "1:1000000": ["A", "B", "C", "D"],  # 1:1M → 1:500k (4 części)
        "1:500000": None,  # 1:500k → 1:200k (36 części, wymaga specjalnej logiki)
        "1:200000": ["A", "B", "C", "D"],  # 1:200k → 1:100k (4 części)
        "1:100000": ["a", "b", "c", "d"],  # 1:100k → 1:50k (4 części)
        "1:50000": ["1", "2", "3", "4"],  # 1:50k → 1:25k (4 części)
        "1:25000": ["1", "2", "3", "4"],  # 1:25k → 1:10k (4 części)
    }

    def get_parent(self) -> SheetParser | None:
        """
        Zwraca arkusz nadrzędny (o skali mniejszej).

        Returns
        -------
        SheetParser or None
            Parser arkusza nadrzędnego lub None jeśli to najwyższy poziom (1:1M)

        Examples
        --------
        >>> parser = SheetParser("N-34-130-D-d-2-4")
        >>> parent = parser.get_parent()
        >>> parent.godlo
        'N-34-130-D-d-2'
        >>> parent.scale
        '1:25000'
        """
        if self._pl2000 is not None:
            p = self._pl2000.get_parent()
            return SheetParser(p.godlo) if p is not None else None

        current_scale_idx = self.SCALE_HIERARCHY.index(self._scale)

        if current_scale_idx == 0:
            return None  # Już najwyższy poziom (1:1M)

        # Specjalna logika dla 1:200k → 1:500k
        if self._scale == "1:200000":
            return self._get_parent_from_200k()

        # Dla pozostałych skal: usuń ostatni komponent
        parts = self._godlo.split("-")
        if len(parts) <= 2:
            return None

        parent_godlo = "-".join(parts[:-1])
        return SheetParser(parent_godlo, self._uklad)

    def _get_parent_from_200k(self) -> SheetParser:
        """
        Zwraca arkusz nadrzędny 1:500k dla arkusza 1:200k.

        Arkusze 1:200k są numerowane 1-144 w obrębie 1:1M.
        Każdy arkusz 1:500k (A, B, C, D) zawiera 36 arkuszy 1:200k.

        A: 1-36, B: 37-72, C: 73-108, D: 109-144

        Returns
        -------
        SheetParser
            Parser arkusza 1:500k
        """
        arkusz_num = int(self._components["arkusz_200k"])
        # Oblicz sekcję: 1-36→A, 37-72→B, 73-108→C, 109-144→D
        section_idx = (arkusz_num - 1) // 36
        section_letter = ["A", "B", "C", "D"][section_idx]

        parent_godlo = (
            f"{self._components['pas']}-{self._components['slup']}-{section_letter}"
        )
        return SheetParser(parent_godlo, self._uklad)

    def get_children(self) -> list[SheetParser]:
        """
        Zwraca wszystkie arkusze podrzędne (o skali większej).

        Returns
        -------
        List[SheetParser]
            Lista parserów arkuszy podrzędnych.
            Pusta lista jeśli to najniższy poziom (1:10k).

        Examples
        --------
        >>> parser = SheetParser("N-34-130-D-d-2")
        >>> children = parser.get_children()
        >>> len(children)
        4
        >>> children[0].godlo
        'N-34-130-D-d-2-1'
        """
        if self._pl2000 is not None:
            children = self._pl2000.get_children()
            return [SheetParser(c.godlo) for c in children]

        current_scale_idx = self.SCALE_HIERARCHY.index(self._scale)

        if current_scale_idx == len(self.SCALE_HIERARCHY) - 1:
            return []  # Już najniższy poziom (1:10k)

        # Specjalna logika dla 1:500k → 1:200k (36 arkuszy)
        if self._scale == "1:500000":
            return self._get_children_from_500k()

        # Dla pozostałych skal: dodaj suffiksy
        suffixes = self._CHILD_SUFFIXES.get(self._scale, [])
        children = []

        for suffix in suffixes:
            child_godlo = f"{self._godlo}-{suffix}"
            children.append(SheetParser(child_godlo, self._uklad))

        return children

    def _get_children_from_500k(self) -> list[SheetParser]:
        """
        Zwraca 36 arkuszy 1:200k dla arkusza 1:500k.

        Numeracja:
        A: 1-36, B: 37-72, C: 73-108, D: 109-144

        Returns
        -------
        List[SheetParser]
            Lista 36 parserów arkuszy 1:200k
        """
        section_letter = self._components["arkusz_200k"]  # A, B, C, or D
        section_idx = ["A", "B", "C", "D"].index(section_letter)
        start_num = section_idx * 36 + 1
        end_num = start_num + 36

        children = []
        for num in range(start_num, end_num):
            child_godlo = f"{self._components['pas']}-{self._components['slup']}-{num}"
            children.append(SheetParser(child_godlo, self._uklad))

        return children

    def get_hierarchy_up(self) -> list[SheetParser]:
        """
        Zwraca pełną hierarchię w górę (do 1:1000000).

        Returns
        -------
        List[SheetParser]
            Lista parserów od bieżącego do najwyższego poziomu (włącznie).
            Pierwszy element to bieżący arkusz, ostatni to arkusz 1:1M.

        Examples
        --------
        >>> parser = SheetParser("N-34-130-D-d-2-4")
        >>> hierarchy = parser.get_hierarchy_up()
        >>> len(hierarchy)
        7
        >>> hierarchy[0].scale, hierarchy[-1].scale
        ('1:10000', '1:1000000')
        """
        if self._pl2000 is not None:
            h = self._pl2000.get_hierarchy_up()
            return [SheetParser(x.godlo) for x in h]

        hierarchy = [self]
        current = self

        while True:
            parent = current.get_parent()
            if parent is None:
                break
            hierarchy.append(parent)
            current = parent

        return hierarchy

    def get_all_descendants(self, target_scale: str) -> list[SheetParser]:
        """
        Zwraca wszystkie arkusze potomne do zadanej skali.

        Parameters
        ----------
        target_scale : str
            Docelowa skala (np. "1:10000")

        Returns
        -------
        List[SheetParser]
            Lista wszystkich arkuszy potomnych w docelowej skali

        Raises
        ------
        ValidationError
            Jeśli target_scale nie jest prawidłową skalą
        ValueError
            Jeśli target_scale jest mniejsza lub równa bieżącej skali

        Examples
        --------
        >>> parser = SheetParser("N-34-130-D-d")
        >>> descendants = parser.get_all_descendants("1:10000")
        >>> len(descendants)  # 4 * 4 = 16 arkuszy
        16
        >>> all(d.scale == "1:10000" for d in descendants)
        True
        """
        if self._pl2000 is not None:
            desc = self._pl2000.get_all_descendants(target_scale)
            return [SheetParser(d.godlo) for d in desc]

        if target_scale not in self.SCALE_HIERARCHY:
            raise ValidationError(
                f"Nieprawidłowa skala: '{target_scale}'. "
                f"Dozwolone: {', '.join(self.SCALE_HIERARCHY)}"
            )

        current_idx = self.SCALE_HIERARCHY.index(self._scale)
        target_idx = self.SCALE_HIERARCHY.index(target_scale)

        if target_idx <= current_idx:
            raise ValueError(
                f"Skala docelowa {target_scale} musi być większa "
                f"(bardziej szczegółowa) niż bieżąca {self._scale}"
            )

        # Rekurencyjnie zbieramy potomków
        def collect_descendants(parser: SheetParser) -> list[SheetParser]:
            if parser.scale == target_scale:
                return [parser]

            all_descendants = []
            for child in parser.get_children():
                all_descendants.extend(collect_descendants(child))

            return all_descendants

        return collect_descendants(self)

    # =========================================================================
    # Metody obliczania bounding box
    # =========================================================================

    # Wymiary arkuszy w minutach kątowych (szerokość geo., długość geo.)
    # Obliczone na podstawie hierarchii podziału
    _SHEET_DIMENSIONS = {
        "1:1000000": (240.0, 360.0),  # 4° × 6°
        "1:500000": (120.0, 180.0),  # 2° × 3°
        "1:200000": (20.0, 30.0),  # 20' × 30' (36 na 1:500k)
        "1:100000": (10.0, 15.0),  # 10' × 15' (4 na 1:200k)
        "1:50000": (5.0, 7.5),  # 5' × 7.5' (4 na 1:100k)
        "1:25000": (2.5, 3.75),  # 2.5' × 3.75' (4 na 1:50k)
        "1:10000": (1.25, 1.875),  # 1.25' × 1.875' (4 na 1:25k)
    }

    # Mapowanie liter na pozycje w siatce 2×2 (row, col) - 0-indexed
    # A/a/1 = NW (góra-lewo), B/b/2 = NE (góra-prawo)
    # C/c/3 = SW (dół-lewo), D/d/4 = SE (dół-prawo)
    _QUADRANT_POSITIONS = {
        "A": (0, 0),
        "B": (0, 1),
        "C": (1, 0),
        "D": (1, 1),
        "a": (0, 0),
        "b": (0, 1),
        "c": (1, 0),
        "d": (1, 1),
        "1": (0, 0),
        "2": (0, 1),
        "3": (1, 0),
        "4": (1, 1),
    }

    def get_bbox(self, crs: str | None = None) -> BBox:
        """
        Oblicza bounding box arkusza w zadanym układzie współrzędnych.

        Parameters
        ----------
        crs : str, optional
            Docelowy układ współrzędnych.
            Domyślnie: "EPSG:2180" dla PL-1992, natywny CRS strefy dla PL-2000.
            Obsługiwane: "EPSG:2180", "EPSG:4326", "EPSG:2176"-"EPSG:2179"

        Returns
        -------
        BBox
            NamedTuple z polami: min_x, min_y, max_x, max_y, crs

        Examples
        --------
        >>> parser = SheetParser("N-34-130-D-d-2-4")
        >>> bbox = parser.get_bbox("EPSG:4326")
        >>> print(f"SW: ({bbox.min_x}, {bbox.min_y})")
        """
        if self._pl2000 is not None:
            return self._pl2000.get_bbox(crs=crs)

        # Default CRS for PL-1992
        if crs is None:
            crs = "EPSG:2180"

        # Oblicz bbox w WGS84 (stopnie)
        south, north, west, east = self._calculate_wgs84_bbox()

        if crs == "EPSG:4326":
            return BBox(
                min_x=west, min_y=south, max_x=east, max_y=north, crs="EPSG:4326"
            )

        if crs == "EPSG:2180":
            # Transformacja WGS84 → PL-1992
            transformer = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)

            # Transformuj wszystkie 4 rogi i znajdź min/max
            corners_wgs84 = [
                (west, south),  # SW
                (west, north),  # NW
                (east, south),  # SE
                (east, north),  # NE
            ]

            corners_2180 = [
                transformer.transform(lon, lat) for lon, lat in corners_wgs84
            ]

            min_x = min(c[0] for c in corners_2180)
            max_x = max(c[0] for c in corners_2180)
            min_y = min(c[1] for c in corners_2180)
            max_y = max(c[1] for c in corners_2180)

            return BBox(
                min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y, crs="EPSG:2180"
            )

        raise ValidationError(
            f"Nieobsługiwany układ współrzędnych: {crs}. "
            "Obsługiwane: EPSG:2180, EPSG:4326"
        )

    def _calculate_wgs84_bbox(self) -> tuple:
        """
        Oblicza bounding box w WGS84 (stopnie).

        Returns
        -------
        tuple
            (south_lat, north_lat, west_lon, east_lon) w stopniach
        """
        # Podstawowe współrzędne arkusza 1:1M
        pas = self._components["pas"]
        slup = int(self._components["slup"])

        # Pas: A=0, B=1, ..., N=13
        row_1m = ord(pas) - ord("A")

        # Współrzędne 1:1M
        south_1m = row_1m * 4.0  # 4° na pas
        north_1m = south_1m + 4.0
        west_1m = (slup - 31) * 6.0  # Słup 31 = 0°E
        east_1m = west_1m + 6.0

        if self._scale == "1:1000000":
            return (south_1m, north_1m, west_1m, east_1m)

        # 1:500k - podział 2×2 w 1:1M
        if self._scale in (
            "1:500000",
            "1:200000",
            "1:100000",
            "1:50000",
            "1:25000",
            "1:10000",
        ):
            south, north, west, east = self._apply_500k_subdivision(
                south_1m, north_1m, west_1m, east_1m
            )
        else:
            south, north, west, east = south_1m, north_1m, west_1m, east_1m

        return (south, north, west, east)

    def _apply_500k_subdivision(
        self, south: float, north: float, west: float, east: float
    ) -> tuple:
        """Aplikuje podział dla 1:500k i mniejszych skal."""

        # 1:500k - arkusz_200k zawiera literę A-D (mylące nazewnictwo w COMPONENT_NAMES)
        if "arkusz_200k" in self._components:
            letter = self._components["arkusz_200k"]

            # Jeśli to litera A-D, to jest podział 1:500k
            if letter in "ABCD":
                row, col = self._QUADRANT_POSITIONS[letter]
                height = (north - south) / 2.0
                width = (east - west) / 2.0
                north = north - row * height
                south = north - height
                west = west + col * width
                east = west + width

                if self._scale == "1:500000":
                    return (south, north, west, east)

            # Jeśli to liczba, to jest numer arkusza 1:200k (1-144)
            elif letter.isdigit() or (len(self._components.get("arkusz_200k", "")) > 1):
                arkusz_num = int(self._components["arkusz_200k"])
                return self._apply_200k_subdivision(
                    south_1m=south,
                    north_1m=north,
                    west_1m=west,
                    east_1m=east,
                    arkusz_num=arkusz_num,
                )

        return (south, north, west, east)

    def _apply_200k_subdivision(
        self,
        south_1m: float,
        north_1m: float,
        west_1m: float,
        east_1m: float,
        arkusz_num: int,
    ) -> tuple:
        """
        Oblicza bbox dla arkusza 1:200k i mniejszych.

        Arkusze 1:200k są numerowane 1-144 w siatce 12×12 w obrębie 1:1M.
        """
        # Pozycja w siatce 12×12 (numeracja od góry-lewej, wierszami)
        row = (arkusz_num - 1) // 12  # 0-11
        col = (arkusz_num - 1) % 12  # 0-11

        # Wymiary pojedynczego arkusza 1:200k w stopniach
        height = (north_1m - south_1m) / 12.0  # 4°/12 = 20'
        width = (east_1m - west_1m) / 12.0  # 6°/12 = 30'

        # Oblicz bbox (arkusze numerowane od góry, więc row=0 to północ)
        north = north_1m - row * height
        south = north - height
        west = west_1m + col * width
        east = west + width

        if self._scale == "1:200000":
            return (south, north, west, east)

        # 1:100k - podział arkusza 1:200k na 4 części (A-D)
        if "arkusz_100k" in self._components:
            letter = self._components["arkusz_100k"]
            row_q, col_q = self._QUADRANT_POSITIONS[letter]
            q_height = height / 2.0
            q_width = width / 2.0
            north = north - row_q * q_height
            south = north - q_height
            west = west + col_q * q_width
            east = west + q_width

            if self._scale == "1:100000":
                return (south, north, west, east)

        # 1:50k - podział arkusza 1:100k na 4 części (a-d)
        if "arkusz_50k" in self._components:
            letter = self._components["arkusz_50k"]
            row_q, col_q = self._QUADRANT_POSITIONS[letter]
            q_height = (north - south) / 2.0
            q_width = (east - west) / 2.0
            north = north - row_q * q_height
            south = north - q_height
            west = west + col_q * q_width
            east = west + q_width

            if self._scale == "1:50000":
                return (south, north, west, east)

        # 1:25k - podział arkusza 1:50k na 4 części (1-4)
        if "arkusz_25k" in self._components:
            num = self._components["arkusz_25k"]
            row_q, col_q = self._QUADRANT_POSITIONS[num]
            q_height = (north - south) / 2.0
            q_width = (east - west) / 2.0
            north = north - row_q * q_height
            south = north - q_height
            west = west + col_q * q_width
            east = west + q_width

            if self._scale == "1:25000":
                return (south, north, west, east)

        # 1:10k - podział arkusza 1:25k na 4 części (1-4)
        if "arkusz_10k" in self._components:
            num = self._components["arkusz_10k"]
            row_q, col_q = self._QUADRANT_POSITIONS[num]
            q_height = (north - south) / 2.0
            q_width = (east - west) / 2.0
            north = north - row_q * q_height
            south = north - q_height
            west = west + col_q * q_width
            east = west + q_width

        return (south, north, west, east)


# =========================================================================
# Standalone functions: bbox → godła lookup
# =========================================================================


def _bboxes_intersect(a: BBox, b: BBox) -> bool:
    """
    Sprawdza czy dwa bounding boxy się przecinają.

    Parameters
    ----------
    a, b : BBox
        Bounding boxy do sprawdzenia (powinny być w tym samym CRS)

    Returns
    -------
    bool
        True jeśli boxy się przecinają
    """
    return not (
        a.max_x < b.min_x or a.min_x > b.max_x or a.max_y < b.min_y or a.min_y > b.max_y
    )


def _transform_bbox_to_wgs84(bbox: BBox) -> BBox:
    """
    Transformuje BBox z EPSG:2180 do EPSG:4326.

    Parameters
    ----------
    bbox : BBox
        Bbox w EPSG:2180

    Returns
    -------
    BBox
        Bbox w EPSG:4326 (min_x=west_lon, min_y=south_lat, ...)
    """
    transformer = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)

    corners_2180 = [
        (bbox.min_x, bbox.min_y),  # SW
        (bbox.min_x, bbox.max_y),  # NW
        (bbox.max_x, bbox.min_y),  # SE
        (bbox.max_x, bbox.max_y),  # NE
    ]

    corners_4326 = [transformer.transform(x, y) for x, y in corners_2180]

    min_lon = min(c[0] for c in corners_4326)
    max_lon = max(c[0] for c in corners_4326)
    min_lat = min(c[1] for c in corners_4326)
    max_lat = max(c[1] for c in corners_4326)

    return BBox(
        min_x=min_lon, min_y=min_lat, max_x=max_lon, max_y=max_lat, crs="EPSG:4326"
    )


def find_sheets_for_bbox(
    bbox: BBox,
    target_scale: str = "1:10000",
    system: str = "1992",
) -> list[str]:
    """
    Znajduje godła arkuszy pokrywających podany bounding box.

    Algorytm: hierarchiczne przycinanie — oblicza matematycznie arkusze 1:1M
    i 1:200k, potem rekurencyjnie zawęża do docelowej skali.

    Parameters
    ----------
    bbox : BBox
        Bounding box w EPSG:2180 lub EPSG:4326
    target_scale : str
        Docelowa skala (default: "1:10000")
    system : str
        Układ współrzędnych: "1992" (PL-1992) lub "2000" (PL-2000).
        Default: "1992" — pełna kompatybilność wsteczna.

    Returns
    -------
    list[str]
        Posortowana lista godeł arkuszy pokrywających bbox

    Raises
    ------
    ValidationError
        Jeśli target_scale jest nieprawidłowa lub CRS nieobsługiwany
    """
    if system == "2000":
        from kartograf.core.parser_2000 import find_sheets_2000_for_bbox

        return find_sheets_2000_for_bbox(bbox, target_scale)

    if target_scale not in SheetParser.SCALE_HIERARCHY:
        raise ValidationError(
            f"Nieprawidłowa skala: '{target_scale}'. "
            f"Dozwolone: {', '.join(SheetParser.SCALE_HIERARCHY)}"
        )

    if bbox.crs not in ("EPSG:2180", "EPSG:4326"):
        raise ValidationError(
            f"Nieobsługiwany CRS: '{bbox.crs}'. Obsługiwane: EPSG:2180, EPSG:4326"
        )

    # Normalizuj do WGS84
    wgs_bbox = _transform_bbox_to_wgs84(bbox) if bbox.crs == "EPSG:2180" else bbox

    target_idx = SheetParser.SCALE_HIERARCHY.index(target_scale)

    # --- Krok 1: Znajdź arkusze 1:1M ---
    sheets_1m = _find_1m_sheets(wgs_bbox)

    if target_idx == 0:  # 1:1000000
        return sorted(sheets_1m)

    # --- Krok 2: Znajdź arkusze 1:500k ---
    if target_idx == 1:  # 1:500000
        result = []
        for godlo_1m in sheets_1m:
            result.extend(_find_children_intersecting(godlo_1m, wgs_bbox))
        return sorted(result)

    # --- Krok 3: Znajdź arkusze 1:200k (zoptymalizowane) ---
    sheets_200k = []
    for godlo_1m in sheets_1m:
        sheets_200k.extend(_find_200k_sheets(godlo_1m, wgs_bbox))

    if target_idx == 2:  # 1:200000
        return sorted(sheets_200k)

    # --- Krok 4: Rekurencyjnie drąż do docelowej skali ---
    current_sheets = sheets_200k
    current_scale_idx = 2  # 1:200000

    while current_scale_idx < target_idx:
        next_sheets = []
        for godlo in current_sheets:
            next_sheets.extend(_find_children_intersecting(godlo, wgs_bbox))
        current_sheets = next_sheets
        current_scale_idx += 1

    return sorted(current_sheets)


def _find_1m_sheets(wgs_bbox: BBox) -> list[str]:
    """
    Znajduje arkusze 1:1M przecinające bbox (WGS84).

    Parameters
    ----------
    wgs_bbox : BBox
        Bbox w EPSG:4326 (min_x=west, min_y=south, max_x=east, max_y=north)

    Returns
    -------
    list[str]
        Lista godeł 1:1M
    """
    south, north = wgs_bbox.min_y, wgs_bbox.max_y
    west, east = wgs_bbox.min_x, wgs_bbox.max_x

    # Pas: row = floor(lat / 4), litera = chr(ord('A') + row)
    min_row = max(0, math.floor(south / 4.0))
    max_row = max(0, math.floor((north - 1e-10) / 4.0))
    # Jeśli north jest dokładnie na granicy (np. 56.0), to należy do pasa niżej
    if north == math.floor(north / 4.0) * 4.0 and north > south:
        max_row = max(0, int(north / 4.0) - 1)

    # Słup: slup = floor(lon / 6) + 31
    min_slup = math.floor(west / 6.0) + 31
    max_slup = math.floor((east - 1e-10) / 6.0) + 31
    if east == math.floor(east / 6.0) * 6.0 and east > west:
        max_slup = int(east / 6.0) + 31 - 1

    result = []
    for row in range(min_row, max_row + 1):
        pas = chr(ord("A") + row)
        for slup in range(min_slup, max_slup + 1):
            result.append(f"{pas}-{slup}")

    return result


def _find_200k_sheets(godlo_1m: str, wgs_bbox: BBox) -> list[str]:
    """
    Znajduje arkusze 1:200k w obrębie arkusza 1:1M przecinające bbox.

    Optymalizacja: oblicza matematycznie zakres wierszy/kolumn w siatce 12x12.

    Parameters
    ----------
    godlo_1m : str
        Godło arkusza 1:1M (np. "N-34")
    wgs_bbox : BBox
        Bbox w EPSG:4326

    Returns
    -------
    list[str]
        Lista godeł 1:200k
    """
    parser_1m = SheetParser(godlo_1m)
    bbox_1m = parser_1m.get_bbox(crs="EPSG:4326")

    north_1m = bbox_1m.max_y
    south_1m = bbox_1m.min_y
    west_1m = bbox_1m.min_x
    east_1m = bbox_1m.max_x

    height_200k = (north_1m - south_1m) / 12.0
    width_200k = (east_1m - west_1m) / 12.0

    # Oblicz zakres wierszy (od góry)
    min_row = max(0, math.floor((north_1m - wgs_bbox.max_y) / height_200k))
    max_row = min(11, math.floor((north_1m - wgs_bbox.min_y - 1e-10) / height_200k))

    # Oblicz zakres kolumn (od lewej)
    min_col = max(0, math.floor((wgs_bbox.min_x - west_1m) / width_200k))
    max_col = min(11, math.floor((wgs_bbox.max_x - west_1m - 1e-10) / width_200k))

    # Clamp ranges
    min_row = max(0, min(11, min_row))
    max_row = max(0, min(11, max_row))
    min_col = max(0, min(11, min_col))
    max_col = max(0, min(11, max_col))

    pas = godlo_1m.split("-")[0]
    slup = godlo_1m.split("-")[1]

    result = []
    for row in range(min_row, max_row + 1):
        for col in range(min_col, max_col + 1):
            arkusz_num = row * 12 + col + 1
            godlo = f"{pas}-{slup}-{arkusz_num}"
            # Weryfikacja przecięcia (na wypadek edge case'ów)
            sp = SheetParser(godlo)
            sb = sp.get_bbox(crs="EPSG:4326")
            if _bboxes_intersect(wgs_bbox, sb):
                result.append(godlo)

    return result


def _find_children_intersecting(godlo: str, wgs_bbox: BBox) -> list[str]:
    """
    Znajduje dzieci arkusza, które przecinają bbox.

    Parameters
    ----------
    godlo : str
        Godło arkusza nadrzędnego
    wgs_bbox : BBox
        Bbox w EPSG:4326

    Returns
    -------
    list[str]
        Lista godeł dzieci przecinających bbox
    """
    parser = SheetParser(godlo)
    children = parser.get_children()

    result = []
    for child in children:
        child_bbox = child.get_bbox(crs="EPSG:4326")
        if _bboxes_intersect(wgs_bbox, child_bbox):
            result.append(child.godlo)

    return result
