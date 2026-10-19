"""``kartograf elevation``: NMT, NMPT, LAZ and contours from GUGiK/CUZK (ADR-039)."""

from dataclasses import replace

from kartograf.catalog import shared
from kartograf.catalog.shared import OUTPUT_TITLE, PL_SHEETS, PRODUCT_TITLE
from kartograf.catalog.spec import Command, Constraint, Example, Group, Param
from kartograf.download.availability import (
    AVAILABILITY_COUNTRIES,
    AVAILABILITY_PRODUCTS,
)
from kartograf.download.cutout import CUTOUT_CRS
from kartograf.download.cz_contours import contours_formats
from kartograf.download.options import (
    COUNTRIES,
    COUNTRY_CHOICES,
    ELEVATION_PRODUCTS,
    SCALE_2000_CHOICES,
    SCALES_2000,
    SHEET_SYSTEM_CHOICES,
    cz_resolution_help,
    format_text,
    product_choices,
    product_directory,
    resolution_text,
    store_files,
    vertical_crs_text,
)
from kartograf.sources.variants import (
    CZ_VERTICAL_TEXT,
    cz_model_text,
    format_tokens,
    resolution_label,
    variants,
)

_SHEET_PRODUCTS = ("nmt", "nmpt")
# The sheet systems of the elevation commands: the PL ones and the CZ ones of
# the sheet products (SM5 sheets, TM33 tiles).
_ACCEPTS = (*PL_SHEETS, "cz_sm5", "cz_tm33")


def _products() -> list[tuple[str, str]]:
    return shared.product_summaries(ELEVATION_PRODUCTS, product_choices)


def _resolutions() -> list[str]:
    """Every grid label of the sheet products of both countries."""
    found = [v for product in _SHEET_PRODUCTS for v in variants(product=product)]
    values = sorted({v.resolution_m for v in found if v.resolution_m is not None})
    return [resolution_label(value) for value in values]


def _vertical_systems() -> list[str]:
    """The height systems of every variant, registry order."""
    return list(dict.fromkeys(v.vertical_crs for v in variants() if v.vertical_crs))


def _formats() -> list[str]:
    """The ``--format`` tokens: the file formats of the PL sheet products and
    the CZ contours."""
    found = tuple(
        v
        for product in _SHEET_PRODUCTS
        for v in variants(product=product, country="PL")
    )
    return list(dict.fromkeys((*format_tokens(found), *contours_formats())))


def _models() -> list[str]:
    """The CUZK models of the CZ point clouds."""
    found = variants(product="laz", country="CZ")
    return list(dict.fromkeys(v.model for v in found if v.model is not None))


def _sheet_systems() -> list[str]:
    """The PL sheet systems the registry has variants for (``--sheet-system``)."""
    found = variants(country="PL")
    return sorted({system for v in found for system in v.systems})


def _resolution_help() -> str:
    return (
        "Rozdzielczosc siatki - wymagana tam, gdzie jest wybor. PL "
        f"(siatki ASC; NMT 100m - pliki XYZ wojewodztw): {resolution_text()}; "
        "wycinek --cutout tylko 1m (mozna pominac); archiwa (--format): "
        "rozdzielczosci w kartograf elevation list-sources. CZ: "
        f"{cz_resolution_help()}. LAZ i warstwice bez rozdzielczosci. "
        "Jedna wartosc dotyczy kazdego kraju zadania; zadanie PL+CZ z roznymi: "
        "pl=WARTOSC,cz=WARTOSC (np. pl=1m,cz=2m)"
    )


def _model_help() -> str:
    return (
        "Model chmury LAZ CZ (wymagany z --product laz gdy zadanie siega CZ): "
        f"{cz_model_text()}. Z --product laz PL i innym produktem: blad"
    )


def _vertical_crs_help() -> str:
    return (
        f"Uklad wysokosci (wymagany). PL: {vertical_crs_text()}; NMT 100 m: "
        "pomin (GUGiK nie deklaruje ukladu). CZ: "
        f"{CZ_VERTICAL_TEXT}. LAZ CZ: Bpv = pliki SM5, EVRF2007 = pliki TM33; "
        "chmury nie sa transformowane. Warstwice CZ: Bpv (mozna pominac). Jedna "
        "wartosc dotyczy kazdego kraju "
        "zadania i musi byc dla niego dostepna; PL+CZ z roznymi ukladami: "
        "pl=WARTOSC,cz=WARTOSC (np. pl=EVRF2007,cz=Bpv)"
    )


def _format_help() -> str:
    return (
        "Format pliku. NMT/NMPT PL: bez flagi siatka ASC (format "
        "produktu); archiwa GUGiK - pliki zrodlowe jak w skorowidzu (bez "
        "konwersji, bez --cutout; arkusze roznych skal wynikaja ze "
        f"skorowidza, bez --scale): {format_text()}. Warstwice CZ (--product "
        f"contours, wymagany): {', '.join(contours_formats())} - ZIP arkusza SM5 "
        "bez konwersji. Warianty: kartograf elevation list-sources"
    )


def _scale_help() -> str:
    return (
        "Skala arkuszy PL-2000 do pobrania - wymagana z --bbox/--geometry "
        "--sheet-system 2000 i z godlem PL-2000 1:10000 (np. 7.171.21): "
        f"{SCALE_2000_CHOICES}; z drobniejszym godlem PL-2000 opcjonalna "
        "(rozwija godlo do potomkow w tej skali). PL-1992: niedozwolona - "
        "GUGiK publikuje arkusze PL-1992 tylko w 1:10000 (godlo 7-czlonowe), "
        "grubsze godlo rozwija sie do 1:10000 samo. Nie dotyczy CZ, LAZ "
        "i --cutout. Szczegoly: docs/USAGE.md 1.6"
    )


def _sheet_system_help() -> str:
    return (
        "Uklad godel arkuszy PL - wymagany z --bbox/--geometry dla PL "
        f"(bez --cutout): {SHEET_SYSTEM_CHOICES}. Wycinek --cutout: tylko "
        "1992 (mozna pominac). Z --sheet uklad wynika z godla (podana wartosc "
        "musi sie z nim zgadzac). Nie dotyczy LAZ (uklad kazdego kafla z WFS) "
        "ani CZ"
    )


def _output_files() -> str:
    return store_files(product_directory(p) for p in ELEVATION_PRODUCTS)


_DOWNLOAD_PARAMS = (
    shared.product(lambda: ELEVATION_PRODUCTS, product_choices),
    shared.country(
        lambda: COUNTRIES,
        "Kraj zrodla danych - wymagany z --bbox/--geometry: "
        f"{COUNTRY_CHOICES}. Z --sheet kraj wynika z godla (podana wartosc "
        "musi sie z nim zgadzac)",
    ),
    *shared.area(
        sheet="Godlo arkusza - pliki tego arkusza ze zrodla (grubsze godlo "
        "rozwija sie na arkusze zrodla; LAZ PL: kafle przecinajace arkusz, LAZ "
        "CZ: plik godla; NMT 100 m: pliki wojewodztw arkusza): PL-1992 (np. "
        "N-34-130-D-d-2-4), PL-2000 (np. 6.129.30.25.3), CZ SM5 (np. CTES96; "
        "warstwice tylko SM5) albo CZ TM33 (np. 302_5550)",
        accepts=_ACCEPTS,
        geometry="Plik geometrii obszaru (SHP albo GPKG): PL - arkusze i "
        "kafle LAZ przecinajace obiekty; CZ LAZ i warstwice - arkusze "
        "przecinajace obwiednie geometrii; wycinek (--cutout) - obwiednia "
        "geometrii",
    ),
    Param(
        "resolution",
        "per_country",
        _resolution_help,
        short="-r",
        metavar="ROZDZIELCZOSC",
        allowed=_resolutions,
        task=True,
        section=PRODUCT_TITLE,
    ),
    Param(
        "model",
        "str",
        _model_help,
        metavar="MODEL",
        allowed=_models,
        task=True,
        section=PRODUCT_TITLE,
    ),
    Param(
        "vertical_crs",
        "per_country",
        _vertical_crs_help,
        metavar="UKLAD",
        allowed=_vertical_systems,
        task=True,
        section=PRODUCT_TITLE,
    ),
    Param(
        "format",
        "str",
        _format_help,
        metavar="FORMAT",
        allowed=_formats,
        task=True,
        section=PRODUCT_TITLE,
    ),
    Param(
        "sheet_system",
        "str",
        _sheet_system_help,
        allowed=_sheet_systems,
        choices=True,
        task=True,
        section="Arkusze obszaru",
    ),
    Param(
        "scale",
        "str",
        _scale_help,
        metavar="SKALA",
        allowed=lambda: SCALES_2000,
        task=True,
        section="Arkusze obszaru",
    ),
    Param(
        "cutout",
        "flag",
        "Tryb JEDNEGO wycinka zamiast arkuszy (tylko --bbox/--geometry; "
        "wymaga --horizontal-crs). PL: wycinek 1 m z WCS GUGiK (--product nmt "
        "albo nmpt, tylko --sheet-system 1992 i --resolution 1m) na siatce "
        "arkuszy, maska ladu PL (poza ladem nodata), plik <wsp>.tif (wersje "
        "w versions/, ponowne uruchomienie uzywa lokalnej wersji; --force "
        "pobiera); kompozycja lotow serwera (najnowszy lot arkuszy: pobierz "
        "arkusze bez --cutout); w trybie --geometry obejmuje CALA obwiednie "
        "geometrii. CZ: wycinek rastra exportImage - obszar CZ z NMT/NMPT "
        "(takze czesc CZ przy --country auto) wymaga --cutout; LAZ bez wycinka",
        default=False,
        task=True,
        section="Wycinek zamiast arkuszy",
    ),
    Param(
        "horizontal_crs",
        "str",
        "Uklad poziomy wycinka - wymagany z --cutout (bez --cutout blad); "
        "reprojekcja lokalna przypieta operacja; natywny CZ: EPSG:5514",
        # the PL cutout set (download/cutout.py) also constrains the CZ path -
        # extending it on one side only requires per-country validation
        allowed=lambda: list(CUTOUT_CRS),
        choices=True,
        normalize="upper",
        task=True,
        section="Wycinek zamiast arkuszy",
    ),
    Param(
        "year",
        "int",
        "Tylko ten rok danych (rok pozyskania: aktualnosc NMT/NMPT, "
        "akt_rok LAZ); skrot --min-year ROK --max-year ROK; najnowszy lot "
        "z tego roku (wszystkie: --all-campaigns); brak roku na ktoryms "
        "arkuszu/kaflu = blad przed pobraniem; nie dziala z --cutout",
        metavar="ROK",
        task=True,
        section="Rok danych, loty i kafle (tylko PL)",
    ),
    Param(
        "min_year",
        "int",
        "Dolna granica roku danych (wlacznie); najnowszy lot z lat >= ROK "
        "(wszystkie: --all-campaigns); nie dziala z --cutout",
        metavar="ROK",
        task=True,
        section="Rok danych, loty i kafle (tylko PL)",
    ),
    Param(
        "max_year",
        "int",
        "Gorna granica roku danych (wlacznie); najnowszy lot z lat <= ROK "
        "(wszystkie: --all-campaigns); sciezka standardowa nigdy nie cofa sie "
        "na starszy lot; nie dziala z --cutout",
        metavar="ROK",
        task=True,
        section="Rok danych, loty i kafle (tylko PL)",
    ),
    Param(
        "all_campaigns",
        "flag",
        "Bez flagi najnowszy lot na arkusz w zakresie lat (jeden lot); "
        "z flaga wszystkie loty z zakresu lat do <segment>/versions/; flagi "
        "roku ograniczaja tylko dopuszczalne lata; LAZ: bez deduplikacji "
        "pokrycia; nie dziala z --cutout",
        default=False,
        task=True,
        section="Rok danych, loty i kafle (tylko PL)",
    ),
    Param(
        "full_sheet",
        "flag",
        "NMT/NMPT: gdy najnowszy lot arkusza nie jest pelny "
        "(calyArkuszWypelnionyTrescia), pobierz tez najnowszy pelny lot "
        "z zakresu lat (najwyzej jeden dodatkowy lot na arkusz) i dowiaz go "
        "w <segment>/full_sheet/; pelny = w granicach Polski; nie dziala "
        "z --cutout ani z LAZ",
        default=False,
        task=True,
        section="Rok danych, loty i kafle (tylko PL)",
    ),
    Param(
        "min_density",
        "int",
        "Tylko LAZ PL (--product laz; z innym produktem blad): "
        "zostaw kafle o gestosci punktow >= N pkt/m2",
        metavar="N",
        task=True,
        section="Rok danych, loty i kafle (tylko PL)",
    ),
    shared.output_dir(_output_files),
    *shared.update_params(
        check="Porownaj lokalne wersje ze zrodlem i wypisz raport (aktualne / "
        "nowsza / do pobrania / nie da sie sprawdzic bez pobrania); niczego nie "
        "pobiera. Pliki arkuszy SM5, kafle TM33 DMR 4G/DMP OK EVRF2007 "
        "i LAZ CZ: ETag; wycinki i kafle z ImageServer: bez taniego sygnalu",
        upgrade="Pobierz nowsza tresc, gdy sygnal zrodla ja wskazuje (domyslnie "
        "tylko informacja); pliki bez taniego sygnalu zostaja lokalne "
        "(pobranie: --force); z --plan wykonaj zapisany plan",
        force="Pobierz ponownie kazdy plik zadania (arkusze, kafle LAZ, "
        "wycinki) i odswiez liste kampanii z GUGiK; ta sama tresc = bez zmian, "
        "inna = nowa wersja; nic nie jest nadpisywane",
        plan="Z --check-updates: zapisz plan aktualizacji (JSON "
        "kartograf-plan/1, przy --country auto jeden plan PL i CZ); z --upgrade: "
        "wykonaj plan (pozycje zmienione od planu = blad, bez pobrania)",
    ),
    shared.workers("Liczba rownoleglych pobran (domyslnie 4; 1 = po kolei)", 4),
    shared.QUIET,
    replace(shared.JSON, section=OUTPUT_TITLE),
)

_DOWNLOAD_CONSTRAINTS = (
    Constraint(
        "one_of",
        ("sheet", "bbox", "geometry"),
        "Podaj dokladnie jeden obszar: --sheet, --bbox albo --geometry",
    ),
    Constraint(
        "requires",
        ("horizontal_crs",),
        "--cutout wymaga --horizontal-crs",
        "cutout",
    ),
    Constraint(
        "applies_to",
        (),
        "--horizontal-crs dziala tylko z --cutout",
        "horizontal_crs",
        {"cutout": True},
    ),
    Constraint(
        "excludes",
        ("sheet",),
        "--cutout dziala tylko z --bbox/--geometry",
        "cutout",
    ),
    Constraint(
        "excludes",
        ("min_year", "max_year"),
        "--year wyklucza sie z --min-year/--max-year",
        "year",
    ),
    Constraint(
        "applies_to",
        (),
        "--min-density dziala tylko z --product laz",
        "min_density",
        {"product": ["laz"]},
    ),
    Constraint(
        "applies_to",
        (),
        "--model dotyczy tylko --product laz",
        "model",
        {"product": ["laz"]},
    ),
)

_DOWNLOAD_EXAMPLES = (
    Example(
        {
            "product": "nmt",
            "sheet": "N-34-130-D-d-2-4",
            "resolution": "1m",
            "vertical_crs": "EVRF2007",
        },
        title="Arkusz PL: NMT 1 m w EVRF2007",
    ),
    Example(
        {
            "product": "laz",
            "country": "pl",
            "bbox": [530000, 382000, 533000, 386000],
            "bbox_crs": "EPSG:2180",
            "vertical_crs": "KRON86",
        },
        title="Chmura LAZ PL dla prostokata",
    ),
    Example(
        {
            "product": "nmt",
            "sheet": "CTES96",
            "resolution": "5m",
            "vertical_crs": "Bpv",
        },
        title="Arkusz CZ SM5: NMT 5 m w Bpv",
    ),
    Example(
        {
            "product": "nmt",
            "country": "cz",
            "bbox": [-447000, -1114000, -446000, -1113000],
            "bbox_crs": "EPSG:5514",
            "cutout": True,
            "horizontal_crs": "EPSG:5514",
            "resolution": "5m",
            "vertical_crs": "Bpv",
        },
        title="Wycinek CZ w S-JTSK",
    ),
)

_AVAILABILITY_PARAMS = (
    replace(
        shared.product(lambda: AVAILABILITY_PRODUCTS, product_choices),
        task=False,
    ),
    replace(
        shared.country(
            lambda: list(AVAILABILITY_COUNTRIES),
            "Kraj - wymagany z --bbox/--geometry: "
            f"{', '.join(AVAILABILITY_COUNTRIES.values())}. Z --sheet kraj wynika "
            "z godla",
        ),
        task=False,
    ),
    *(
        replace(param, task=False)
        for param in shared.area(
            sheet="Godlo arkusza: PL (PL-1992 albo PL-2000), CZ SM5 (np. CTES96) "
            "albo kafel TM33 (np. 760_5518); obszar = rama arkusza",
            accepts=_ACCEPTS,
            geometry="Plik geometrii obszaru (SHP albo GPKG): obszar = obwiednie "
            "obiektow (LAZ: obwiednia calej warstwy; CZ: obwiednia geometrii) - jak "
            "w elevation download",
        )
    ),
    Param(
        "year",
        "int",
        "Tylko ten rok (warstwa roczna skorowidza GUGiK); skrot --min-year "
        "ROK --max-year ROK",
        metavar="ROK",
        section="Rok danych (tylko PL - CUZK nie publikuje lat nalotu: z "
        "--country cz blad, z --country auto raport tylko czesci PL)",
    ),
    Param(
        "min_year",
        "int",
        "Dolna granica roku (wlacznie)",
        metavar="ROK",
        section="Rok danych (tylko PL - CUZK nie publikuje lat nalotu: z "
        "--country cz blad, z --country auto raport tylko czesci PL)",
    ),
    Param(
        "max_year",
        "int",
        "Gorna granica roku (wlacznie)",
        metavar="ROK",
        section="Rok danych (tylko PL - CUZK nie publikuje lat nalotu: z "
        "--country cz blad, z --country auto raport tylko czesci PL)",
    ),
    Param(
        "details",
        "flag",
        "Dla kazdej kombinacji: godla arkuszy niepelnych (CZ: arkuszy bez "
        "pliku), obszar bez arkuszy i wszystkie polecenia pobrania",
        argument=None,
        section="Wynik",
    ),
    Param(
        "json",
        "flag",
        "Wypisz raport jako JSON (kartograf-availability/1, ten sam "
        "ksztalt co check_availability)",
        argument=None,
        section="Wynik",
    ),
    Param(
        "force",
        "flag",
        "Pomin cache metadanych (odpytaj skorowidze, PRG i pliki CUZK "
        "ponownie, nadpisz cache)",
        default=False,
        section="Wynik",
    ),
)

COMMANDS = (
    Command(
        "elevation download",
        "Pobierz NMT, NMPT, LAZ albo warstwice (arkusze, kafle albo wycinek)",
        "data",
        "download_data",
        "kartograf-download/1",
        _DOWNLOAD_PARAMS,
        description=(
            "Pobierz NMT, NMPT i chmury punktow LAZ z GUGiK (PL) albo CUZK (CZ) "
            "do magazynu wersji. PL: --bbox/--geometry wybiera arkusze/kafle LAZ, "
            "--cutout --horizontal-crs daje wycinek 1 m z WCS GUGiK; NMT 100 m "
            "(--resolution 100m) to pliki XYZ wojewodztw obszaru. "
            "CZ: rastry SM5/TM33 z plikow CUZK albo ImageServer (kafle TM33 "
            "DMR 4G i DMP OK z plikow ETRS89/EVRF2007); dla obszaru rastra "
            "--cutout wymagane. LAZ CZ: --model i arkusz SM5/TM33 albo obszar "
            "(arkusze z indeksu), bez --cutout i bez transformacji chmur. "
            "Warstwice CZ (--product contours --format SHP|DGN): ZIP arkusza SM5 "
            "1:1, obszar = arkusze SM5 z indeksu, bez --cutout."
        ),
        effects=("network", "store_write"),
        project_task=True,
        check_function="check_data",
        check_result_schema="kartograf-plan/1",
        tool="elevation_download",
        constraints=_DOWNLOAD_CONSTRAINTS,
        examples=_DOWNLOAD_EXAMPLES,
    ),
    shared.list_sources_command("elevation", lambda: ELEVATION_PRODUCTS),
    Command(
        "elevation availability",
        "Raport dostepnosci NMT, NMPT i LAZ dla obszaru (bez pobierania)",
        "query",
        "check_availability",
        "kartograf-availability/1",
        _AVAILABILITY_PARAMS,
        description=(
            "Bez pobierania danych: PL - dla jakich lat, ukladow, "
            "rozdzielczosci, ukladow wysokosci i formatow obszar ma komplet "
            "pelnych arkuszy (LAZ: kafli) wg skorowidza GUGiK (skorowidz WFS "
            "i maska ladu PRG; kompletna kombinacja: caly lad obszaru lezy "
            "w arkuszach pelnych, calyArkuszWypelnionyTrescia); CZ - ktore "
            "arkusze SM5 i kafle TM33 obszaru (indeks KladyMapovychListu) maja "
            "pliki CUZK, z data publikacji i rozmiarem z naglowkow HEAD (CUZK "
            "nie publikuje lat nalotu). --country auto: czesci PL i CZ obszaru "
            "w jednym raporcie. Stopka podaje polecenia pobrania kompletnych "
            "kombinacji (PL: najnowszej)."
        ),
        effects=("network",),
        tool="elevation_availability",
        constraints=(
            Constraint(
                "one_of",
                ("sheet", "bbox", "geometry"),
                "Podaj dokladnie jeden obszar: --sheet, --bbox albo --geometry",
            ),
            Constraint(
                "excludes",
                ("min_year", "max_year"),
                "--year wyklucza sie z --min-year/--max-year",
                "year",
            ),
        ),
        examples=(
            Example(
                {
                    "product": "nmt",
                    "country": "pl",
                    "bbox": [565000, 242000, 569000, 246000],
                    "bbox_crs": "EPSG:2180",
                },
                title="Dostepnosc NMT PL dla prostokata",
            ),
            Example(
                {"product": "nmpt", "sheet": "CTES96"},
                title="Dostepnosc NMPT dla arkusza CZ",
            ),
            Example(
                {
                    "product": "laz",
                    "country": "pl",
                    "geometry": "zlewnia.gpkg",
                    "min_year": 2020,
                },
                title="Dostepnosc LAZ PL od 2020 dla geometrii",
                run={"details": True},
            ),
        ),
    ),
)

GROUPS = (
    Group(
        "elevation",
        "Wysokosci: NMT, NMPT i chmury LAZ (PL i CZ), warstwice (CZ)",
        "Dane wysokosciowe NMT/NMPT i chmury punktow LAZ "
        "z GUGiK (PL) i CUZK (CZ) oraz warstwice ZABAGED (CZ).",
        products=_products,
    ),
)
