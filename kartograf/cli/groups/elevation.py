"""``kartograf elevation``: NMT, NMPT, LAZ and contours from GUGiK/CUZK (ADR-039)."""

import argparse
from functools import partial

from kartograf.cli._args import (
    OUTPUT_TITLE,
    PRODUCT_TITLE,
    SELECTION_TITLE,
    add_area_flags,
    add_output,
    add_quiet,
    add_update_flags,
    examples,
)
from kartograf.cli.availability_cmd import cmd_availability
from kartograf.cli.download_cmd import cmd_download, download_task_arguments
from kartograf.cli.groups import add_group, add_list_sources
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
    SHEET_SYSTEM_CHOICES,
    cz_resolution_help,
    format_text,
    product_choices,
    product_directory,
    resolution_text,
    store_files,
    vertical_crs_text,
)
from kartograf.sources.descriptor import SourceDescriptor
from kartograf.sources.variants import CZ_VERTICAL_TEXT, cz_model_text


def _source_choice(source: SourceDescriptor) -> str:
    """Flags selecting ``source`` in ``elevation download`` (variant registry):
    every required choice - ``--country``, ``--resolution``/``--format``/
    ``--model`` and ``--vertical-crs`` with the height systems of the source
    (``EVRF2007|KRON86``; none for NMT 100 m, contours take only Bpv - may
    be omitted)."""
    flags = f"--product {source.product} --country {source.country.lower()}"
    variant = source.variants[0] if source.variants else None
    systems = "|".join(
        dict.fromkeys(v.vertical_crs for v in source.variants if v.vertical_crs)
    )
    vertical = f" --vertical-crs {systems}" if systems else ""
    if variant is None:
        return flags
    if source.country == "CZ":
        if source.product == "laz":
            return f"{flags} --model {variant.model}{vertical}"
        if variant.label is None:  # contours: one format each
            return f"{flags} --format {variant.format}"
        return f"{flags} --resolution {source.resolution}{vertical}"
    if variant.source_file and source.product != "laz":
        flags += f" --format {variant.format}"
    if variant.label is not None:
        flags += f" --resolution {variant.label}"
    return flags + vertical


def register(subparsers: argparse._SubParsersAction) -> None:
    """``elevation download``, ``list-sources`` and ``availability``."""
    commands = add_group(
        subparsers,
        "elevation",
        help="Wysokosci: NMT, NMPT i chmury LAZ (PL i CZ), warstwice (CZ)",
        description="Dane wysokosciowe NMT/NMPT i chmury punktow LAZ "
        "z GUGiK (PL) i CUZK (CZ) oraz warstwice ZABAGED (CZ).",
    )
    download = commands.add_parser(
        "download",
        help="Pobierz NMT, NMPT, LAZ albo warstwice (arkusze, kafle albo wycinek)",
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
        epilog=examples(
            "kartograf elevation download --product nmt --sheet N-34-130-D-d-2-4 "
            "--resolution 1m --vertical-crs EVRF2007 -o ./data",
            "kartograf elevation download --product laz --country pl --bbox "
            "530000,382000,533000,386000 --vertical-crs KRON86 -o ./data",
            "kartograf elevation download --product nmt --sheet CTES96 "
            "--resolution 5m --vertical-crs Bpv -o ./data",
            "kartograf elevation download --product nmt --country cz --bbox "
            "-447000,-1114000,-446000,-1113000 --bbox-crs EPSG:5514 --cutout "
            "--horizontal-crs EPSG:5514 --resolution 5m --vertical-crs Bpv -o ./data",
        ),
    )

    selection = download.add_argument_group(SELECTION_TITLE)
    selection.add_argument(
        "--product",
        choices=ELEVATION_PRODUCTS,
        default=None,
        help=f"Produkt (wymagany): {product_choices(ELEVATION_PRODUCTS)}",
    )
    selection.add_argument(
        "--country",
        type=str.lower,
        choices=COUNTRIES,
        default=None,
        help="Kraj zrodla danych - wymagany z --bbox/--geometry: "
        f"{COUNTRY_CHOICES}. Z --sheet kraj wynika z godla (podana wartosc "
        "musi sie z nim zgadzac)",
    )
    add_area_flags(
        selection,
        sheet_help="Godlo arkusza - pliki tego arkusza ze zrodla (grubsze godlo "
        "rozwija sie na arkusze zrodla; LAZ PL: kafle przecinajace arkusz, LAZ "
        "CZ: plik godla; NMT 100 m: pliki wojewodztw arkusza): PL-1992 (np. "
        "N-34-130-D-d-2-4), PL-2000 (np. 6.129.30.25.3), CZ SM5 (np. CTES96; "
        "warstwice tylko SM5) albo CZ TM33 (np. 302_5550)",
        geometry_help="Plik geometrii obszaru (SHP albo GPKG): PL - arkusze i "
        "kafle LAZ przecinajace obiekty; CZ LAZ i warstwice - arkusze "
        "przecinajace obwiednie geometrii; wycinek (--cutout) - obwiednia "
        "geometrii",
    )

    product = download.add_argument_group(PRODUCT_TITLE)
    product.add_argument(
        "--resolution",
        "-r",
        metavar="ROZDZIELCZOSC",
        default=None,
        help="Rozdzielczosc siatki - wymagana tam, gdzie jest wybor. PL "
        f"(siatki ASC; NMT 100m - pliki XYZ wojewodztw): {resolution_text()}; "
        "wycinek --cutout tylko 1m (mozna pominac); archiwa (--format): "
        "rozdzielczosci w kartograf elevation list-sources. CZ: "
        f"{cz_resolution_help()}. LAZ i warstwice bez rozdzielczosci. "
        "Jedna wartosc dotyczy kazdego kraju zadania; zadanie PL+CZ z roznymi: "
        "pl=WARTOSC,cz=WARTOSC (np. pl=1m,cz=2m)",
    )
    product.add_argument(
        "--model",
        metavar="MODEL",
        default=None,
        help=f"Model chmury LAZ CZ (wymagany z --product laz gdy zadanie siega CZ): "
        f"{cz_model_text()}. Z --product laz PL i innym produktem: blad",
    )
    product.add_argument(
        "--vertical-crs",
        metavar="UKLAD",
        default=None,
        help=f"Uklad wysokosci (wymagany). PL: {vertical_crs_text()}; NMT 100 m: "
        "pomin (GUGiK nie deklaruje ukladu). CZ: "
        f"{CZ_VERTICAL_TEXT}. LAZ CZ: Bpv = pliki SM5, EVRF2007 = pliki TM33; "
        "chmury nie sa transformowane. Warstwice CZ: Bpv (mozna pominac). Jedna "
        "wartosc dotyczy kazdego kraju "
        "zadania i musi byc dla niego dostepna; PL+CZ z roznymi ukladami: "
        "pl=WARTOSC,cz=WARTOSC (np. pl=EVRF2007,cz=Bpv)",
    )
    product.add_argument(
        "--format",
        metavar="FORMAT",
        default=None,
        help="Format pliku. NMT/NMPT PL: bez flagi siatka ASC (format "
        "produktu); archiwa GUGiK - pliki zrodlowe jak w skorowidzu (bez "
        "konwersji, bez --cutout; arkusze roznych skal wynikaja ze "
        f"skorowidza, bez --scale): {format_text()}. Warstwice CZ (--product "
        f"contours, wymagany): {', '.join(contours_formats())} - ZIP arkusza SM5 "
        "bez konwersji. Warianty: kartograf elevation list-sources",
    )
    sheets = download.add_argument_group("Arkusze obszaru")
    sheets.add_argument(
        "--sheet-system",
        choices=["1992", "2000"],
        default=None,
        help="Uklad godel arkuszy PL - wymagany z --bbox/--geometry dla PL "
        f"(bez --cutout): {SHEET_SYSTEM_CHOICES}. Wycinek --cutout: tylko "
        "1992 (mozna pominac). Z --sheet uklad wynika z godla (podana wartosc "
        "musi sie z nim zgadzac). Nie dotyczy LAZ (uklad kazdego kafla z WFS) "
        "ani CZ",
    )
    sheets.add_argument(
        "--scale",
        metavar="SKALA",
        help="Skala arkuszy PL-2000 do pobrania - wymagana z --bbox/--geometry "
        "--sheet-system 2000 i z godlem PL-2000 1:10000 (np. 7.171.21): "
        f"{SCALE_2000_CHOICES}; z drobniejszym godlem PL-2000 opcjonalna "
        "(rozwija godlo do potomkow w tej skali). PL-1992: niedozwolona - "
        "GUGiK publikuje arkusze PL-1992 tylko w 1:10000 (godlo 7-czlonowe), "
        "grubsze godlo rozwija sie do 1:10000 samo. Nie dotyczy CZ, LAZ "
        "i --cutout. Szczegoly: docs/USAGE.md 1.6",
    )

    cutout = download.add_argument_group("Wycinek zamiast arkuszy")
    cutout.add_argument(
        "--cutout",
        action="store_true",
        help="Tryb JEDNEGO wycinka zamiast arkuszy (tylko --bbox/--geometry; "
        "wymaga --horizontal-crs). PL: wycinek 1 m z WCS GUGiK (--product nmt "
        "albo nmpt, tylko --sheet-system 1992 i --resolution 1m) na siatce "
        "arkuszy, maska ladu PL (poza ladem nodata), plik <wsp>.tif (wersje "
        "w versions/, ponowne uruchomienie uzywa lokalnej wersji; --force "
        "pobiera); kompozycja lotow serwera (najnowszy lot arkuszy: pobierz "
        "arkusze bez --cutout); w trybie --geometry obejmuje CALA obwiednie "
        "geometrii. CZ: wycinek rastra exportImage - obszar CZ z NMT/NMPT "
        "(takze czesc CZ przy --country auto) wymaga --cutout; LAZ bez wycinka",
    )
    cutout.add_argument(
        "--horizontal-crs",
        # the PL cutout set (download/cutout.py) also constrains the CZ path -
        # extending it on one side only requires per-country validation
        type=str.upper,
        choices=list(CUTOUT_CRS),
        default=None,
        help="Uklad poziomy wycinka - wymagany z --cutout (bez --cutout blad); "
        "reprojekcja lokalna przypieta operacja; natywny CZ: EPSG:5514",
    )

    campaigns = download.add_argument_group("Rok danych, loty i kafle (tylko PL)")
    campaigns.add_argument(
        "--year",
        type=int,
        metavar="ROK",
        help="Tylko ten rok danych (rok pozyskania: aktualnosc NMT/NMPT, "
        "akt_rok LAZ); skrot --min-year ROK --max-year ROK; najnowszy lot "
        "z tego roku (wszystkie: --all-campaigns); brak roku na ktoryms "
        "arkuszu/kaflu = blad przed pobraniem; nie dziala z --cutout",
    )
    campaigns.add_argument(
        "--min-year",
        type=int,
        metavar="ROK",
        help="Dolna granica roku danych (wlacznie); najnowszy lot z lat >= ROK "
        "(wszystkie: --all-campaigns); nie dziala z --cutout",
    )
    campaigns.add_argument(
        "--max-year",
        type=int,
        metavar="ROK",
        help="Gorna granica roku danych (wlacznie); najnowszy lot z lat <= ROK "
        "(wszystkie: --all-campaigns); sciezka standardowa nigdy nie cofa sie "
        "na starszy lot; nie dziala z --cutout",
    )
    campaigns.add_argument(
        "--all-campaigns",
        action="store_true",
        help="Bez flagi najnowszy lot na arkusz w zakresie lat (jeden lot); "
        "z flaga wszystkie loty z zakresu lat do <segment>/versions/; flagi "
        "roku ograniczaja tylko dopuszczalne lata; LAZ: bez deduplikacji "
        "pokrycia; nie dziala z --cutout",
    )
    campaigns.add_argument(
        "--full-sheet",
        action="store_true",
        help="NMT/NMPT: gdy najnowszy lot arkusza nie jest pelny "
        "(calyArkuszWypelnionyTrescia), pobierz tez najnowszy pelny lot "
        "z zakresu lat (najwyzej jeden dodatkowy lot na arkusz) i dowiaz go "
        "w <segment>/full_sheet/; pelny = w granicach Polski; nie dziala "
        "z --cutout ani z LAZ",
    )
    campaigns.add_argument(
        "--min-density",
        type=int,
        metavar="N",
        help="Tylko LAZ PL (--product laz; z innym produktem blad): "
        "zostaw kafle o gestosci punktow >= N pkt/m2",
    )

    output = download.add_argument_group(OUTPUT_TITLE)
    add_output(output, store_files(product_directory(p) for p in ELEVATION_PRODUCTS))
    add_update_flags(
        output,
        check_help="Porownaj lokalne wersje ze zrodlem i wypisz raport (aktualne / "
        "nowsza / do pobrania / nie da sie sprawdzic bez pobrania); niczego nie "
        "pobiera. Pliki arkuszy SM5, kafle TM33 DMR 4G/DMP OK EVRF2007 "
        "i LAZ CZ: ETag; wycinki i kafle z ImageServer: bez taniego sygnalu",
        upgrade_help="Pobierz nowsza tresc, gdy sygnal zrodla ja wskazuje (domyslnie "
        "tylko informacja); pliki bez taniego sygnalu zostaja lokalne "
        "(pobranie: --force); z --plan wykonaj zapisany plan",
        force_help="Pobierz ponownie kazdy plik zadania (arkusze, kafle LAZ, "
        "wycinki) i odswiez liste kampanii z GUGiK; ta sama tresc = bez zmian, "
        "inna = nowa wersja; nic nie jest nadpisywane",
        plan_help="Z --check-updates: zapisz plan aktualizacji (JSON "
        "kartograf-plan/1, przy --country auto jeden plan PL i CZ); z --upgrade: "
        "wykonaj plan (pozycje zmienione od planu = blad, bez pobrania)",
    )
    output.add_argument(
        "--workers",
        "-w",
        type=int,
        metavar="N",
        default=4,
        help="Liczba rownoleglych pobran (domyslnie 4; 1 = po kolei)",
    )
    add_quiet(output)
    download.set_defaults(
        _handler=partial(cmd_download, products=ELEVATION_PRODUCTS),
        _task=download_task_arguments,
    )

    add_list_sources(commands, "elevation", ELEVATION_PRODUCTS, _source_choice)
    _register_availability(commands)


def _register_availability(commands: argparse._SubParsersAction) -> None:
    """``elevation availability``: the report of ``check_availability``.

    Not a data command of a project manifest (no ``_task``, ADR-040): it
    writes nothing, the report is its result. ``--country`` and the help
    texts come from ``AVAILABILITY_COUNTRIES`` (``pl``, ``cz``, ``auto``);
    year flags are PL-only (the library rejects them for CZ and narrows
    ``auto`` to PL).
    """
    report = commands.add_parser(
        "availability",
        help="Raport dostepnosci NMT, NMPT i LAZ dla obszaru (bez pobierania)",
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
        epilog=examples(
            "kartograf elevation availability --product nmt --country pl --bbox "
            "565000,242000,569000,246000",
            "kartograf elevation availability --product nmpt --sheet CTES96",
            "kartograf elevation availability --product laz --country pl "
            "--geometry zlewnia.gpkg --min-year 2020 --details",
        ),
    )
    selection = report.add_argument_group(SELECTION_TITLE)
    selection.add_argument(
        "--product",
        choices=AVAILABILITY_PRODUCTS,
        default=None,
        help=f"Produkt (wymagany): {product_choices(AVAILABILITY_PRODUCTS)}",
    )
    selection.add_argument(
        "--country",
        type=str.lower,
        choices=list(AVAILABILITY_COUNTRIES),
        default=None,
        help="Kraj - wymagany z --bbox/--geometry: "
        f"{', '.join(AVAILABILITY_COUNTRIES.values())}. Z --sheet kraj wynika "
        "z godla",
    )
    add_area_flags(
        selection,
        sheet_help="Godlo arkusza: PL (PL-1992 albo PL-2000), CZ SM5 (np. CTES96) "
        "albo kafel TM33 (np. 760_5518); obszar = rama arkusza",
        geometry_help="Plik geometrii obszaru (SHP albo GPKG): obszar = obwiednie "
        "obiektow (LAZ: obwiednia calej warstwy; CZ: obwiednia geometrii) - jak "
        "w elevation download",
    )
    years = report.add_argument_group(
        "Rok danych (tylko PL - CUZK nie publikuje lat nalotu: z --country cz "
        "blad, z --country auto raport tylko czesci PL)"
    )
    years.add_argument(
        "--year",
        type=int,
        metavar="ROK",
        help="Tylko ten rok (warstwa roczna skorowidza GUGiK); skrot --min-year "
        "ROK --max-year ROK",
    )
    years.add_argument(
        "--min-year", type=int, metavar="ROK", help="Dolna granica roku (wlacznie)"
    )
    years.add_argument(
        "--max-year", type=int, metavar="ROK", help="Gorna granica roku (wlacznie)"
    )
    output = report.add_argument_group("Wynik")
    output.add_argument(
        "--details",
        action="store_true",
        help="Dla kazdej kombinacji: godla arkuszy niepelnych (CZ: arkuszy bez "
        "pliku), obszar bez arkuszy i wszystkie polecenia pobrania",
    )
    output.add_argument(
        "--json",
        action="store_true",
        help="Wypisz raport jako JSON (kartograf-availability/1, ten sam "
        "ksztalt co check_availability)",
    )
    output.add_argument(
        "--force",
        action="store_true",
        help="Pomin cache metadanych (odpytaj skorowidze, PRG i pliki CUZK "
        "ponownie, nadpisz cache)",
    )
    report.set_defaults(_handler=cmd_availability)
