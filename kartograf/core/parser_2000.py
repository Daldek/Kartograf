"""
Parser godel map topograficznych dla ukladu PL-2000.

This module provides the Parser2000 class for parsing Polish topographic
map sheet identifiers (godla) in PL-2000 coordinate system.
PL-2000 uses dot-separated numeric format: zone.row.column[.subdivisions]
(e.g., 6.179.12, 6.179.12.20).
"""

import math
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
        return f"Parser2000(godlo='{self._godlo}', scale='{self._scale}', uklad='2000')"

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
            return BBox(min_x=west, min_y=south, max_x=east, max_y=north, crs=crs)

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

    # =========================================================================
    # Hierarchia
    # =========================================================================

    def get_parent(self) -> "Parser2000 | None":
        """
        Zwraca rodzica arkusza (grubsza skala).

        Returns
        -------
        Parser2000 | None
            Rodzic lub None jesli 1:10000 (najgrubsza skala).

        Examples
        --------
        >>> Parser2000("6.179.12.15.2").get_parent().godlo
        '6.179.12.15'
        """
        if self._scale == "1:10000":
            return None

        # 1:5000 -> 1:10000 (usun ark_5k — ostatni segment)
        # 1:2000 -> 1:10000 (usun ark_2k — ostatni segment)
        # 1:1000 -> 1:2000 (usun ark_1k — ostatni segment)
        # 1:500  -> 1:1000 (usun ark_500 — ostatni segment)
        parent_godlo = self._godlo.rsplit(".", 1)[0]
        return Parser2000(parent_godlo)

    def get_children(self, scale: str | None = None) -> list["Parser2000"]:
        """
        Zwraca dzieci arkusza (drobniejsza skala).

        Parameters
        ----------
        scale : str, optional
            Skala dzieci. Istotne tylko dla 1:10000, ktore ma dwie sciezki:
            - "1:5000" -> 4 dzieci (siatka 2x2)
            - "1:2000" -> 25 dzieci (siatka 5x5) — domyslnie

        Returns
        -------
        list[Parser2000]
            Lista dzieci posortowana wg godla.

        Examples
        --------
        >>> [c.godlo for c in Parser2000("6.179.12").get_children(scale="1:5000")]
        ['6.179.12.1', '6.179.12.2', '6.179.12.3', '6.179.12.4']
        """
        if self._scale == "1:10000":
            if scale is None:
                scale = "1:2000"
            if scale == "1:5000":
                # 2x2: kwadrenty 1-4
                return [Parser2000(f"{self._godlo}.{q}") for q in range(1, 5)]
            if scale == "1:2000":
                # 5x5: arkusze 01-25
                return [Parser2000(f"{self._godlo}.{i:02d}") for i in range(1, 26)]
            return []

        if self._scale == "1:2000":
            # 2x2: kwadrenty 1-4
            return [Parser2000(f"{self._godlo}.{q}") for q in range(1, 5)]

        if self._scale == "1:1000":
            # 2x2: kwadrenty 1-4
            return [Parser2000(f"{self._godlo}.{q}") for q in range(1, 5)]

        # 1:5000 i 1:500 to liscie — brak dzieci
        return []

    def get_all_descendants(self, target_scale: str) -> list["Parser2000"]:
        """
        Zwraca wszystkich potomkow na docelowej skali.

        Parameters
        ----------
        target_scale : str
            Docelowa skala (np. "1:1000").

        Returns
        -------
        list[Parser2000]
            Lista potomkow posortowana wg godla.

        Raises
        ------
        ValidationError
            Jesli target_scale jest grubsza niz biezaca skala lub
            jesli sciezka do target_scale nie istnieje (np. 1:5000 -> 1:2000).

        Examples
        --------
        >>> len(Parser2000("6.179.12").get_all_descendants("1:1000"))
        100
        """
        if target_scale == self._scale:
            return [self]

        # Sprawdz czy target_scale jest drobniejsza
        if target_scale not in SCALE_HIERARCHY_2000:
            raise ValidationError(
                f"Nieznana skala: {target_scale}. "
                f"Dozwolone: {', '.join(SCALE_HIERARCHY_2000)}"
            )

        # Znajdz indeksy w hierarchii
        current_idx = SCALE_HIERARCHY_2000.index(self._scale)
        target_idx = SCALE_HIERARCHY_2000.index(target_scale)

        if target_idx < current_idx:
            raise ValidationError(
                f"Skala docelowa {target_scale} jest grubsza niz "
                f"biezaca skala {self._scale}."
            )

        # Specjalny przypadek: z 1:10000 do 1:5000 — galaz 5k
        if self._scale == "1:10000" and target_scale == "1:5000":
            return self.get_children(scale="1:5000")

        # Specjalny przypadek: z 1:5000 nie mozna isc dalej (liscie)
        if self._scale == "1:5000" and target_scale != "1:5000":
            raise ValidationError(
                f"Arkusz 1:5000 nie ma potomkow w skali {target_scale}. "
                f"Galaz 1:5000 jest niezalezna i nie ma drobniejszych podzialkow."
            )

        # Rekurencyjnie: rozwin dzieci az do target_scale
        children = self.get_children()
        if not children:
            raise ValidationError(
                f"Arkusz {self._godlo} ({self._scale}) nie ma potomkow "
                f"w skali {target_scale}."
            )

        if children[0].scale == target_scale:
            return sorted(children, key=lambda p: p.godlo)

        # Rekurencja
        result = []
        for child in children:
            result.extend(child.get_all_descendants(target_scale))
        return sorted(result, key=lambda p: p.godlo)

    def get_hierarchy_up(self) -> list["Parser2000"]:
        """
        Zwraca lancuch od biezacego arkusza do 1:10000.

        Returns
        -------
        list[Parser2000]
            Lista od self (pierwszy) do 1:10000 (ostatni).

        Examples
        --------
        >>> [p.scale for p in Parser2000("6.179.12.15.2").get_hierarchy_up()]
        ['1:1000', '1:2000', '1:10000']
        """
        chain = [self]
        current = self
        while True:
            parent = current.get_parent()
            if parent is None:
                break
            chain.append(parent)
            current = parent
        return chain

    # =========================================================================
    # BBox — metody prywatne
    # =========================================================================

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

        return BBox(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y, crs=dst_crs)


# =========================================================================
# Standalone functions: bbox → godła lookup (PL-2000)
# =========================================================================

# Zakresy dlugosci geograficznej dla stref PL-2000
_ZONE_LON_RANGES = {
    5: (13.5, 16.5),
    6: (16.5, 19.5),
    7: (19.5, 22.5),
    8: (22.5, 25.5),
}


def _bboxes_intersect_2000(a: BBox, b: BBox) -> bool:
    """
    Sprawdza czy dwa bounding boxy sie przecinaja.

    Uzywa `<` (nie `<=`) — stykajace sie krawedzie = intersect,
    zgodnie z konwencja z PL-1992 (sheet_parser.py).

    Parameters
    ----------
    a, b : BBox
        Bounding boxy do sprawdzenia (powinny byc w tym samym CRS)

    Returns
    -------
    bool
        True jesli boxy sie przecinaja
    """
    return not (
        a.max_x < b.min_x or a.min_x > b.max_x or a.max_y < b.min_y or a.min_y > b.max_y
    )


def _determine_zones_for_bbox(bbox_wgs84: BBox) -> list[int]:
    """
    Okreslenie stref PL-2000 przecinanych przez bbox w WGS84.

    Parameters
    ----------
    bbox_wgs84 : BBox
        Bbox w EPSG:4326 (min_x=west_lon, max_x=east_lon)

    Returns
    -------
    list[int]
        Lista numerow stref (5-8) posortowana rosnaco
    """
    west_lon = bbox_wgs84.min_x
    east_lon = bbox_wgs84.max_x

    zones = []
    for zone_num, (zone_west, zone_east) in _ZONE_LON_RANGES.items():
        # Strefa przecina bbox jesli zakresy dlugosci sie nakladaja
        if west_lon < zone_east and east_lon > zone_west:
            zones.append(zone_num)

    return sorted(zones)


def _transform_bbox_to_wgs84(bbox: BBox) -> BBox:
    """
    Transformuje BBox z dowolnego obslugiwanego CRS do WGS84 (EPSG:4326).

    Parameters
    ----------
    bbox : BBox
        Bbox w obslugiwanym CRS

    Returns
    -------
    BBox
        Bbox w EPSG:4326
    """
    if bbox.crs == "EPSG:4326":
        return bbox

    transformer = Transformer.from_crs(bbox.crs, "EPSG:4326", always_xy=True)

    corners = [
        (bbox.min_x, bbox.min_y),  # SW
        (bbox.min_x, bbox.max_y),  # NW
        (bbox.max_x, bbox.min_y),  # SE
        (bbox.max_x, bbox.max_y),  # NE
    ]

    transformed = [transformer.transform(x, y) for x, y in corners]

    min_lon = min(c[0] for c in transformed)
    max_lon = max(c[0] for c in transformed)
    min_lat = min(c[1] for c in transformed)
    max_lat = max(c[1] for c in transformed)

    return BBox(
        min_x=min_lon, min_y=min_lat, max_x=max_lon, max_y=max_lat, crs="EPSG:4326"
    )


def _transform_bbox_to_zone_crs(bbox_wgs84: BBox, zone: int) -> BBox:
    """
    Transformuje BBox z WGS84 do natywnego CRS strefy PL-2000.

    Parameters
    ----------
    bbox_wgs84 : BBox
        Bbox w EPSG:4326
    zone : int
        Numer strefy (5-8)

    Returns
    -------
    BBox
        Bbox w EPSG:2176-2179
    """
    dst_crs = ZONE_EPSG[zone]
    transformer = Transformer.from_crs("EPSG:4326", dst_crs, always_xy=True)

    corners = [
        (bbox_wgs84.min_x, bbox_wgs84.min_y),  # SW
        (bbox_wgs84.min_x, bbox_wgs84.max_y),  # NW
        (bbox_wgs84.max_x, bbox_wgs84.min_y),  # SE
        (bbox_wgs84.max_x, bbox_wgs84.max_y),  # NE
    ]

    transformed = [transformer.transform(x, y) for x, y in corners]

    min_x = min(c[0] for c in transformed)
    max_x = max(c[0] for c in transformed)
    min_y = min(c[1] for c in transformed)
    max_y = max(c[1] for c in transformed)

    return BBox(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y, crs=dst_crs)


def find_sheets_2000_for_bbox(
    bbox: BBox,
    target_scale: str = "1:10000",
    zone: int | None = None,
) -> list[str]:
    """
    Znajduje godla arkuszy PL-2000 pokrywajacych podany bounding box.

    Parameters
    ----------
    bbox : BBox
        Bounding box w dowolnym obslugiwanym CRS
        (EPSG:2176-2179, EPSG:2180, EPSG:4326)
    target_scale : str
        Docelowa skala (default: "1:10000").
        Obslugiwane: 1:10000, 1:5000, 1:2000, 1:1000, 1:500
    zone : int | None
        Jesli podano, ogranicza wyszukiwanie do tej strefy (5-8).
        Jesli None, automatyczna detekcja na podstawie bbox.

    Returns
    -------
    list[str]
        Posortowana lista godel arkuszy PL-2000 pokrywajacych bbox

    Raises
    ------
    ValidationError
        Jesli target_scale jest nieprawidlowa lub CRS nieobslugiwany
    """
    if target_scale not in SCALE_HIERARCHY_2000:
        raise ValidationError(
            f"Nieprawidlowa skala: '{target_scale}'. "
            f"Dozwolone: {', '.join(SCALE_HIERARCHY_2000)}"
        )

    # Krok 1: Transformuj do WGS84 dla detekcji strefy
    bbox_wgs84 = _transform_bbox_to_wgs84(bbox)

    # Krok 2: Okresl strefy
    zones = [zone] if zone is not None else _determine_zones_for_bbox(bbox_wgs84)

    if not zones:
        return []

    # Krok 3: Dla kazdej strefy znajdz arkusze 1:10k
    all_godla: set[str] = set()

    for z in zones:
        zone_crs = ZONE_EPSG[z]

        # Transformuj bbox do CRS strefy
        if bbox.crs == zone_crs:
            zone_bbox = bbox
        else:
            zone_bbox = _transform_bbox_to_zone_crs(bbox_wgs84, z)

        # Oblicz zakres row/col dla 1:10k
        min_row = math.floor((zone_bbox.min_y - 4_920_000) / 5000) - 1
        max_row = math.floor((zone_bbox.max_y - 4_920_000) / 5000) + 1
        min_col = math.floor((zone_bbox.min_x - z * 1_000_000 - 332_000) / 8000) - 1
        max_col = math.floor((zone_bbox.max_x - z * 1_000_000 - 332_000) / 8000) + 1

        # Clamp do rozsadnych wartosci (pas >= 0, slup >= 0)
        min_row = max(0, min_row)
        min_col = max(0, min_col)

        # Krok 4: Dla kazdego kandydata sprawdz przeciecie
        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                godlo_10k = f"{z}.{row}.{col}"

                # Sprobuj utworzyc Parser2000 — jesli godlo nieprawidlowe, pomin
                try:
                    p = Parser2000(godlo_10k)
                except (ParseError, ValidationError):
                    continue

                sheet_bbox = p.get_bbox()

                if _bboxes_intersect_2000(zone_bbox, sheet_bbox):
                    if target_scale == "1:10000":
                        all_godla.add(godlo_10k)
                    else:
                        # Drill down do target_scale
                        _drill_down(p, zone_bbox, target_scale, all_godla)

    return sorted(all_godla)


def _drill_down(
    parent: Parser2000,
    zone_bbox: BBox,
    target_scale: str,
    result: set[str],
) -> None:
    """
    Rekurencyjnie drazy w dol hierarchii, sprawdzajac przeciecie z bbox.

    Parameters
    ----------
    parent : Parser2000
        Rodzic do drylowania
    zone_bbox : BBox
        Bbox w natywnym CRS strefy
    target_scale : str
        Docelowa skala
    result : set[str]
        Zbiór wynikowych godel (modyfikowany in-place)
    """
    # Specjalny przypadek: z 1:10000 do 1:5000 — galaz 5k
    if parent.scale == "1:10000" and target_scale == "1:5000":
        children = parent.get_children(scale="1:5000")
    else:
        children = parent.get_children()

    for child in children:
        child_bbox = child.get_bbox()

        if not _bboxes_intersect_2000(zone_bbox, child_bbox):
            continue

        if child.scale == target_scale:
            result.add(child.godlo)
        else:
            _drill_down(child, zone_bbox, target_scale, result)
