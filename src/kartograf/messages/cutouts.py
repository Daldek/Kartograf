"""Messages of the cutouts (``download.cutout``, ``orto_cutout``, ``cz_cutout``)."""

from kartograf.messages import Text

MESSAGES = {
    # ``download.cutout``.
    "cutout_product_invalid": Text(
        "PL cutout product: {cutout_products:join( or )} (got {product})",
        "Produkt wycinka PL: {cutout_products:join( albo )} (podano {product})",
    ),
    "cutout_crs_unsupported": Text(
        "Unsupported target CRS for PL cutout: {horizontal_crs} (available: "
        "{cutout_crs})",
        "Nieobslugiwany uklad docelowy wycinka PL: {horizontal_crs} (dostepne: "
        "{cutout_crs})",
    ),
    "cutout_vertical_crs_invalid": Text(
        "Vertical CRS of {product} PL: {systems:join( or )} (got {vertical_crs})",
        "Uklad wysokosci {product} PL: {systems:join( albo )} (podano {vertical_crs})",
    ),
    "no_wcs_cutout": Text(
        "{product} PL has no WCS cutout",
        "{product} PL nie ma wycinka WCS",
    ),
    "provider_cutout_mismatch": Text(
        "Provider does not match the cutout: provider {attr} is {actual}, cutout "
        "{expected} - pass a provider with the product, vertical CRS and resolution "
        "of the cutout",
        "Provider niezgodny z wycinkiem: {attr} providera {actual}, wycinka "
        "{expected} - podaj provider z produktem, pionem i rozdzielczoscia wycinka",
    ),
    "cutout_disk_space_low": Text(
        "Not enough disk space for the cutout: at least ~{needed_gib:.1f} GiB needed "
        "({width} x {height} px float32 grid and EPSG:2180 working file), "
        "~{free_gib:.1f} GiB free in {probe}",
        "Za malo miejsca na dysku dla wycinka: potrzeba co najmniej ~{needed_gib:.1f} "
        "GiB (siatka {width} x {height} px float32 i plik roboczy EPSG:2180), wolne "
        "~{free_gib:.1f} GiB w {probe}",
    ),
    "version_no_sidecar": Text(
        "{version_path}: version without a readable sidecar",
        "{version_path}: wersja bez czytelnego sidecara",
    ),
    "cutout_outside_land": Text(
        "{product} cutout: area entirely outside PL land (PRG mask: state boundary "
        "without territorial sea and inland waters) - GUGiK has no data here; change "
        "--bbox",
        "wycinek {product}: obszar w calosci poza ladem PL (maska PRG: granica "
        "panstwa bez morza terytorialnego i wod wewnetrznych) - GUGiK nie ma tu "
        "danych; zmien --bbox",
    ),
    "cutout_size_estimate": Text(
        "cutout {width} x {height} px float32 (~{size_mib:.0f} MiB), {chunks} GUGiK "
        "WCS requests fetched sequentially - {wcs_time_text} "
        "({wcs_request_seconds}-{wcs_request_seconds_2} s per request as measured)",
        "wycinek {width} x {height} px float32 (~{size_mib:.0f} MiB), {chunks} "
        "zapytan WCS GUGiK pobieranych po kolei - {wcs_time_text} "
        "({wcs_request_seconds}-{wcs_request_seconds_2} s na zapytanie wg pomiaru)",
    ),
    "cutout_description": Text(
        "cutout {product} {vertical_crs} "
        "({min_x:.0f},{min_y:.0f})-({max_x:.0f},{max_y:.0f})",
        "wycinek {product} {vertical_crs} "
        "({min_x:.0f},{min_y:.0f})-({max_x:.0f},{max_y:.0f})",
    ),
    "cutout_all_nodata": Text(
        "cutout is entirely nodata - GUGiK WCS returned no data for the area (on land "
        "per PRG mask)",
        "wycinek w calosci nodata - WCS GUGiK nie zwrocil danych dla obszaru (na "
        "ladzie wg maski PRG)",
    ),
    # ``download.cz_cutout``.
    "cz_all_nodata": Text(
        "{path} is entirely nodata - area outside the CUZK raster coverage (outside "
        "the CZ boundary?)",
        "{path} jest w calosci nodata - obszar poza pokryciem rastra CUZK (poza "
        "granica CZ?)",
    ),
    "cz_cutout_requires_upgrade": Text(
        "The CZ cutout plan requires update='upgrade'",
        "Plan wycinka CZ wymaga update='upgrade'",
    ),
    "cz_cutout_unsupported_crs": Text(
        "Unsupported target CRS for the CZ cutout: {horizontal_crs!r} (available: "
        "{cutout_crs})",
        "Nieobslugiwany uklad docelowy wycinka CZ: {horizontal_crs!r} (dostepne: "
        "{cutout_crs})",
    ),
    # ``download.orto_cutout``.
    "orto_cutout_pl_only": Text(
        "--cutout with --product orto works only for PL (a cutout from GUGiK WCS) - "
        "for a PL area use --country pl, CZ orthophoto: without --cutout",
        "--cutout z --product orto dziala tylko dla PL (wycinek z WCS GUGiK) - dla "
        "obszaru PL uzyj --country pl, ortofotomapa CZ: bez --cutout",
    ),
    "orto_cutout_crs_required": Text(
        "--horizontal-crs required with --cutout --product {product}: only "
        "{orto_cutout_crs} (no image resampling)",
        "--horizontal-crs wymagane z --cutout --product {product}: tylko "
        "{orto_cutout_crs} (bez przeprobkowania obrazu)",
    ),
    "orto_cutout_crs_unsupported": Text(
        "--horizontal-crs {horizontal_crs} does not work with --product {product}: an "
        "orthophoto cutout supports only {orto_cutout_crs} (no image resampling)",
        "--horizontal-crs {horizontal_crs} nie dziala z --product {product}: wycinek "
        "ortofotomapy tylko {orto_cutout_crs} (bez przeprobkowania obrazu)",
    ),
    "orto_disk_space_low": Text(
        "Not enough disk space for the cutout: at least ~{need_gib:.1f} GiB needed "
        "({width} x {height} px RGB grid and WCS chunks), ~{free_gib:.1f} GiB free in "
        "{probe}",
        "Za malo miejsca na dysku dla wycinka: potrzeba co najmniej ~{need_gib:.1f} "
        "GiB (siatka {width} x {height} px RGB i kawalki WCS), wolne ~{free_gib:.1f} "
        "GiB w {probe}",
    ),
    "orto_wcs_unreadable_tiff": Text(
        "Orthophoto WCS: unreadable cutout GeoTIFF: {error}",
        "WCS ortofotomapy: nieczytelny GeoTIFF wycinka: {error}",
    ),
    "cutout_size_mismatch": Text(
        "{width_px} x {height_px} px instead of {expected_width} x {expected_height}",
        "{width_px} x {height_px} px zamiast {expected_width} x {expected_height}",
    ),
    "pixel_size_mismatch": Text(
        "pixel {pixel_width:g} x {pixel_height:g} m instead of {step:g} m",
        "piksel {pixel_width:g} x {pixel_height:g} m zamiast {step:g} m",
    ),
    "nw_corner_mismatch": Text(
        "NW corner {origin_x:.3f}/{origin_y:.3f} instead of {min_x:.3f}/{max_y:.3f}",
        "naroznik NW {origin_x:.3f}/{origin_y:.3f} zamiast {min_x:.3f}/{max_y:.3f}",
    ),
    "band_layout_mismatch": Text(
        "{band_count} bands {dtypes} instead of 3 uint8 bands (RGB)",
        "{band_count} pasm {dtypes} zamiast 3 pasm uint8 (RGB)",
    ),
    "crs_mismatch": Text(
        "CRS EPSG:{epsg} instead of {expected_crs}",
        "uklad EPSG:{epsg} zamiast {expected_crs}",
    ),
    "orto_wcs_grid_mismatch": Text(
        "Orthophoto WCS returned a different grid than requested: {problems}",
        "WCS ortofotomapy zwrocil inna siatke niz zapytanie: {problems}",
    ),
    "true_orto_no_coverage": Text(
        "true orto cutout: GUGiK WCS has no true orthophoto in this area - it covers "
        "only selected cities, e.g. Gdansk",
        "wycinek true orto: WCS GUGiK nie ma w tym obszarze prawdziwej ortofotomapy - "
        "obejmuje tylko wybrane miasta, np. Gdansk",
    ),
    "remedy_change_bbox": Text("change --bbox", "zmien --bbox"),
    "high_orto_no_coverage": Text(
        "high orthophoto cutout: GUGiK WCS has no orthophoto with a pixel of 10 cm or "
        "smaller in this area",
        "wycinek ortofotomapy high: WCS GUGiK nie ma w tym obszarze ortofotomapy o "
        "pikselu 10 cm i mniejszym",
    ),
    "remedy_bbox_or_standard": Text(
        "change --bbox or use --coverage standard",
        "zmien --bbox albo uzyj --coverage standard",
    ),
    "orto_no_coverage_area": Text(
        "orthophoto cutout {coverage}: GUGiK WCS has no orthophoto in this area (e.g. "
        "sea or an area across the border)",
        "wycinek ortofotomapy {coverage}: WCS GUGiK nie ma w tym obszarze "
        "ortofotomapy (np. morze albo obszar za granica)",
    ),
    "cutout_image_all_zero": Text(
        "{what}, and the area image is entirely 0,0,0; version was not created, "
        "{remedy}",
        "{what}, a obraz obszaru jest w calosci 0,0,0; wersja nie powstala, {remedy}",
    ),
    "cutout_size_notice": Text(
        "cutout {width} x {height} px RGB uint8 (~{size_mib:.0f} MiB), {chunks} GUGiK "
        "WCS requests ({variant} {resolution}) downloaded sequentially",
        "wycinek {width} x {height} px RGB uint8 (~{size_mib:.0f} MiB), {chunks} "
        "zapytan WCS GUGiK ({variant} {resolution}) pobieranych po kolei",
    ),
    "orto_cutout_download_label": Text(
        "orthophoto cutout {variant} {resolution} "
        "({min_x:.0f},{min_y:.0f})-({max_x:.0f},{max_y:.0f})",
        "wycinek ortofotomapy {variant} {resolution} "
        "({min_x:.0f},{min_y:.0f})-({max_x:.0f},{max_y:.0f})",
    ),
    "no_wcs_image_cutout": Text(
        "--product {product!r}: no WCS image cutout - cutouts are available for "
        "--product orto and true-orto",
        "--product {product!r}: brak wycinka WCS obrazu - wycinek maja --product orto "
        "i true-orto",
    ),
    "wcs_time_seconds": Text("approx. {low}-{high} s", "ok. {low}-{high} s"),
    "wcs_time_minutes": Text("approx. {low}-{high} min", "ok. {low}-{high} min"),
}
