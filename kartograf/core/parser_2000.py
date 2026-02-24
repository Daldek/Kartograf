"""
Parser godel map topograficznych dla ukladu PL-2000.

This module provides the Parser2000 class for parsing Polish topographic
map sheet identifiers (godla) in PL-2000 coordinate system.
PL-2000 uses dot-separated numeric format: zone.row.column[.subdivisions]
(e.g., 6.179.12, 6.179.12.20).
"""

import re

from pyproj import Transformer

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ParseError, ValidationError

# Hierarchia skal PL-2000 (od najgrubszej do najdrobniejszej)
SCALE_HIERARCHY_2000 = ["1:10000", "1:5000", "1:2000", "1:1000", "1:500"]

# Wymiary arkuszy w metrach (wysokosc N-S, szerokosc E-W)
SHEET_DIMENSIONS_2000 = {
    "1:10000": (5000, 8000),
    "1:5000": (2500, 4000),
    "1:2000": (1000, 1600),
    "1:1000": (500, 800),
    "1:500": (250, 400),
}

# Mapowanie strefy na EPSG
ZONE_EPSG = {
    5: "EPSG:2176",
    6: "EPSG:2177",
    7: "EPSG:2178",
    8: "EPSG:2179",
}

# Obsługiwane CRS dla get_bbox
_SUPPORTED_CRS = {
    "EPSG:2176",
    "EPSG:2177",
    "EPSG:2178",
    "EPSG:2179",
    "EPSG:2180",
    "EPSG:4326",
}


class Parser2000:
    """
    Parser godel map topograficznych dla ukladu PL-2000.

    Obslugiwane skale: 1:10000 do 1:500

    Attributes
    ----------
    godlo : str
        Znormalizowane godlo arkusza (np. "6.179.12")
    scale : str
        Skala mapy (np. "1:10000")
    uklad : str
        Uklad wspolrzednych (zawsze "2000")
    components : dict[str, str]
        Skladowe godla (strefa, pas, slup, oraz opcjonalne ark_5k/ark_2k/ark_1k/ark_500)
    zone : int
        Numer strefy (5-8)
    native_crs : str
        Natywny CRS strefy (np. "EPSG:2177")

    Examples
    --------
    >>> parser = Parser2000("6.179.12")
    >>> parser.scale
    '1:10000'
    >>> parser.zone
    6
    >>> parser.native_crs
    'EPSG:2177'
    """

    # Wzorce godla dla kazdej skali
    PATTERNS_2000 = {
        "1:10000": r"^([5-8])\.(\d{1,3})\.(\d{1,2})$",
        "1:5000": r"^([5-8])\.(\d{1,3})\.(\d{1,2})\.([1-4])$",
        "1:2000": r"^([5-8])\.(\d{1,3})\.(\d{1,2})\.(\d{2})$",
        "1:1000": r"^([5-8])\.(\d{1,3})\.(\d{1,2})\.(\d{2})\.([1-4])$",
        "1:500": r"^([5-8])\.(\d{1,3})\.(\d{1,2})\.(\d{2})\.([1-4])\.([1-4])$",
    }

    # Nazwy komponentow per skala (porzadek = grupy regex)
    _COMPONENT_NAMES = {
        "1:10000": ("strefa", "pas", "slup"),
        "1:5000": ("strefa", "pas", "slup", "ark_5k"),
        "1:2000": ("strefa", "pas", "slup", "ark_2k"),
        "1:1000": ("strefa", "pas", "slup", "ark_2k", "ark_1k"),
        "1:500": ("strefa", "pas", "slup", "ark_2k", "ark_1k", "ark_500"),
    }

    # Pozycje kwadrantow 2x2: {quadrant: (row, col)}
    _QUADRANT_POSITIONS = {
        1: (0, 0),  # NW
        2: (0, 1),  # NE
        3: (1, 0),  # SW
        4: (1, 1),  # SE
    }

    def __init__(self, godlo: str):
        """
        Inicjalizuje parser dla podanego godla PL-2000.

        Parameters
        ----------
        godlo : str
            Godlo arkusza mapy (np. "6.179.12", "6.179.12.15")

        Raises
        ------
        ParseError
            Jesli godlo jest nieprawidlowe lub nie pasuje do zadnego wzorca.
        ValidationError
            Jesli ark_2k jest poza zakresem 01-25.
        """
        if not isinstance(godlo, str):
            raise ParseError(f"Godlo musi byc stringiem, otrzymano: {type(godlo)}")

        godlo = godlo.strip()
        if not godlo:
            raise ParseError("Godlo nie moze byc puste")

        # Odrzuc format PL-1992 (myslniki)
        if "-" in godlo:
            raise ParseError(
                f"Nieprawidlowe godlo PL-2000: '{godlo}'. "
                f"Format PL-1992 (z myslnikami) nie jest obslugiwany przez Parser2000."
            )

        self._godlo = godlo
        self._scale = self._determine_scale()
        self._components = self._parse_components()
        self._validate_components()

    def _determine_scale(self) -> str:
        """
        Okresla skale na podstawie struktury godla.

        Returns
        -------
        str
            Skala mapy (np. "1:10000")

        Raises
        ------
        ParseError
            Jesli godlo nie pasuje do zadnego wzorca
        """
        for scale, pattern in self.PATTERNS_2000.items():
            if re.match(pattern, self._godlo):
                return scale

        raise ParseError(
            f"Nieprawidlowe godlo PL-2000: '{self._godlo}'. "
            f"Godlo musi byc w formacie: strefa.pas.slup[.subdivisions]"
        )

    def _parse_components(self) -> dict[str, str]:
        """
        Parsuje skladowe godla.

        Returns
        -------
        dict[str, str]
            Slownik ze skladowymi godla
        """
        pattern = self.PATTERNS_2000[self._scale]
        match = re.match(pattern, self._godlo)

        if not match:
            raise ParseError(f"Blad parsowania godla: {self._godlo}")

        names = self._COMPONENT_NAMES[self._scale]
        return dict(zip(names, match.groups(), strict=True))

    def _validate_components(self) -> None:
        """
        Waliduje skladowe godla.

        Raises
        ------
        ValidationError
            Jesli ark_2k jest poza zakresem 01-25
        """
        if "ark_2k" in self._components:
            ark_2k = int(self._components["ark_2k"])
            if ark_2k < 1 or ark_2k > 25:
                ark_val = self._components["ark_2k"]
                raise ValidationError(
                    f"Nieprawidlowy numer arkusza 1:2000: {ark_val}. "
                    f"Dozwolone wartosci: 01-25."
                )

    # =========================================================================
    # Wlasciwosci
    # =========================================================================

    @property
    def godlo(self) -> str:
        """Zwraca godlo arkusza."""
        return self._godlo

    @property
    def scale(self) -> str:
        """Zwraca skale mapy."""
        return self._scale

    @property
    def uklad(self) -> str:
        """Zwraca uklad wspolrzednych (zawsze '2000')."""
        return "2000"

    @property
    def components(self) -> dict[str, str]:
        """Zwraca slownik ze skladowymi godla (kopia)."""
        return self._components.copy()

    @property
    def zone(self) -> int:
        """Zwraca numer strefy (5-8)."""
        return int(self._components["strefa"])

    @property
    def native_crs(self) -> str:
        """Zwraca natywny CRS strefy (np. 'EPSG:2177')."""
        return ZONE_EPSG[self.zone]

    # =========================================================================
    # Rownosc i hashing
    # =========================================================================

    def __eq__(self, other: object) -> bool:
        """Porownuje dwa parsery na podstawie godla."""
        if not isinstance(other, Parser2000):
            return NotImplemented
        return self._godlo == other._godlo

    def __hash__(self) -> int:
        """Zwraca hash obiektu."""
        return hash(self._godlo)

    def __repr__(self) -> str:
        """Zwraca reprezentacje obiektu do debugowania."""
        return (
            f"Parser2000(godlo='{self._godlo}', "
            f"scale='{self._scale}', uklad='2000')"
        )

    def __str__(self) -> str:
        """Zwraca czytelna reprezentacje arkusza."""
        return f"{self._godlo} (skala {self._scale}, uklad 2000)"

    # =========================================================================
    # BBox
    # =========================================================================

    def get_bbox(self, crs: str | None = None) -> BBox:
        """
        Oblicza bounding box arkusza w zadanym ukladzie wspolrzednych.

        Parameters
        ----------
        crs : str, optional
            Docelowy uklad wspolrzednych (default: natywny CRS strefy).
            Obslugiwane: EPSG:2176-2179, EPSG:2180, EPSG:4326.

        Returns
        -------
        BBox
            NamedTuple z polami: min_x, min_y, max_x, max_y, crs

        Raises
        ------
        ValidationError
            Jesli CRS jest nieobslugiwany.

        Examples
        --------
        >>> parser = Parser2000("6.179.12")
        >>> bbox = parser.get_bbox()
        >>> bbox.crs
        'EPSG:2177'
        """
        if crs is None:
            crs = self.native_crs

        if crs not in _SUPPORTED_CRS:
            raise ValidationError(
                f"Nieobslugiwany uklad wspolrzednych: {crs}. "
                f"Obslugiwane: {', '.join(sorted(_SUPPORTED_CRS))}"
            )

        # Oblicz bbox w natywnym CRS strefy
        south, north, west, east = self._calculate_native_bbox()
        native_crs = self.native_crs

        if crs == native_crs:
            return BBox(
                min_x=west, min_y=south, max_x=east, max_y=north, crs=crs
            )

        # Transformacja do docelowego CRS
        return self._transform_bbox(south, north, west, east, native_crs, crs)

    def _calculate_native_bbox(self) -> tuple[float, float, float, float]:
        """
        Oblicza bounding box w natywnym CRS strefy PL-2000.

        Returns
        -------
        tuple[float, float, float, float]
            (south, north, west, east) w metrach
        """
        strefa = int(self._components["strefa"])
        pas = int(self._components["pas"])
        slup = int(self._components["slup"])

        # Bazowe wspolrzedne 1:10000
        south = pas * 5000 + 4_920_000
        north = south + 5000
        west = strefa * 1_000_000 + slup * 8000 + 332_000
        east = west + 8000

        if self._scale == "1:10000":
            return (south, north, west, east)

        # Podpodzial 1:5000 (2x2 w 10k)
        if self._scale == "1:5000":
            q = int(self._components["ark_5k"])
            return self._apply_quadrant(south, north, west, east, q, 2500, 4000)

        # Podpodzial 1:2000 (5x5 w 10k)
        ark_2k = int(self._components["ark_2k"])
        row, col = divmod(ark_2k - 1, 5)
        # Wiersze liczone od gory (row=0 to polnoc)
        south_2k = north - (row + 1) * 1000
        north_2k = north - row * 1000
        west_2k = west + col * 1600
        east_2k = west_2k + 1600

        if self._scale == "1:2000":
            return (south_2k, north_2k, west_2k, east_2k)

        # Podpodzial 1:1000 (2x2 w 2k)
        q_1k = int(self._components["ark_1k"])
        south_1k, north_1k, west_1k, east_1k = self._apply_quadrant(
            south_2k, north_2k, west_2k, east_2k, q_1k, 500, 800
        )

        if self._scale == "1:1000":
            return (south_1k, north_1k, west_1k, east_1k)

        # Podpodzial 1:500 (2x2 w 1k)
        q_500 = int(self._components["ark_500"])
        return self._apply_quadrant(
            south_1k, north_1k, west_1k, east_1k, q_500, 250, 400
        )

    def _apply_quadrant(
        self,
        south: float,
        north: float,
        west: float,
        east: float,
        quadrant: int,
        height: float,
        width: float,
    ) -> tuple[float, float, float, float]:
        """
        Oblicza bbox kwadranta w siatce 2x2.

        Parameters
        ----------
        south, north, west, east : float
            Bbox rodzica
        quadrant : int
            Numer kwadranta (1-4)
        height : float
            Wysokosc kwadranta w metrach
        width : float
            Szerokosc kwadranta w metrach

        Returns
        -------
        tuple[float, float, float, float]
            (south, north, west, east)
        """
        row, col = self._QUADRANT_POSITIONS[quadrant]
        new_north = north - row * height
        new_south = new_north - height
        new_west = west + col * width
        new_east = new_west + width
        return (new_south, new_north, new_west, new_east)

    @staticmethod
    def _transform_bbox(
        south: float,
        north: float,
        west: float,
        east: float,
        src_crs: str,
        dst_crs: str,
    ) -> BBox:
        """
        Transformuje bbox z src_crs do dst_crs za pomoca pyproj.

        Transformuje wszystkie 4 rogi i bierze min/max.

        Parameters
        ----------
        south, north, west, east : float
            Bbox w src_crs
        src_crs : str
            Zrodlowy CRS
        dst_crs : str
            Docelowy CRS

        Returns
        -------
        BBox
            Bbox w docelowym CRS
        """
        transformer = Transformer.from_crs(src_crs, dst_crs, always_xy=True)

        corners = [
            (west, south),  # SW
            (west, north),  # NW
            (east, south),  # SE
            (east, north),  # NE
        ]

        transformed = [transformer.transform(x, y) for x, y in corners]

        min_x = min(c[0] for c in transformed)
        max_x = max(c[0] for c in transformed)
        min_y = min(c[1] for c in transformed)
        max_y = max(c[1] for c in transformed)

        return BBox(
            min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y, crs=dst_crs
        )
