"""
Parser godeł map topograficznych dla układów 1992 i 2000.

This module provides the SheetParser class for parsing Polish topographic
map sheet identifiers (godła) and extracting information about scale,
coordinate system, and sheet components.
"""

import re
from typing import Dict, Optional

from kartograf.exceptions import ParseError, ValidationError


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

    def __init__(self, godlo: str, uklad: Optional[str] = None):
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

        self._original_godlo = godlo.strip()
        if not self._original_godlo:
            raise ParseError("Godło nie może być puste")

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

    def _validate_uklad(self, uklad: Optional[str]) -> str:
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

    def _parse_components(self) -> Dict[str, str]:
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
    def components(self) -> Dict[str, str]:
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
