"""Messages of the files of the releases of a data set (``download.releases``)."""

from kartograf.messages import Text

MESSAGES = {
    "unknown_version": Text(
        "--version {version}: {dataset} has no release Kartograf knows under this "
        "version (--product {product}); it reads {versions}. A newer release is read "
        "by the Kartograf release that adds it after checking its layout",
        "--version {version}: {dataset} nie ma wydania o tej wersji znanego "
        "Kartografowi (--product {product}); czytane są {versions}. Nowsze wydanie "
        "czyta wydanie Kartografa, które je dodaje po sprawdzeniu jego układu",
    ),
    "refused_version": Text(
        "--version {version}: {dataset} {version} (Zenodo record {record}) is not "
        "read: {refusal}; Kartograf reads {versions}",
        "--version {version}: {dataset} {version} (rekord Zenodo {record}) nie jest "
        "czytane: {refusal}; Kartograf czyta {versions}",
    ),
    "layout_hint": Text(
        "a release of another layout is read by the Kartograf release that checked "
        "it; the release: https://doi.org/{doi}",
        "wydanie o innym układzie czyta wydanie Kartografa, które je sprawdziło; "
        "wydanie: https://doi.org/{doi}",
    ),
    "zip_length": Text(
        "{dataset} {version} (Zenodo record {record}): the ZIP {url} has {length} "
        "bytes, not the {expected} of the release Kartograf knows - another layout, "
        "nothing written",
        "{dataset} {version} (rekord Zenodo {record}): ZIP {url} ma {length} bajtów, "
        "nie {expected} wydania znanego Kartografowi - inny układ, nic nie zapisano",
    ),
    "member_count": Text(
        "{dataset} {version} (Zenodo record {record}): {count} members of the ZIP "
        "match {pattern} instead of one - another layout, nothing written",
        "{dataset} {version} (rekord Zenodo {record}): {count} członków ZIP pasuje "
        "do {pattern} zamiast jednego - inny układ, nic nie zapisano",
    ),
    "member_differs": Text(
        "{dataset} {version} (Zenodo record {record}): {member} has {size} bytes "
        "with CRC {crc32}, not the {expected_size} bytes with CRC {expected_crc32} "
        "of the release Kartograf knows - another file, nothing written",
        "{dataset} {version} (rekord Zenodo {record}): {member} ma {size} bajtów z "
        "CRC {crc32}, nie {expected_size} bajtów z CRC {expected_crc32} wydania "
        "znanego Kartografowi - inny plik, nic nie zapisano",
    ),
    "member_method": Text(
        "{dataset} {version} (Zenodo record {record}): {member} is packed by "
        "method {method} or encrypted - another layout, nothing written",
        "{dataset} {version} (rekord Zenodo {record}): {member} jest spakowany "
        "metodą {method} albo zaszyfrowany - inny układ, nic nie zapisano",
    ),
    "member_sha256": Text(
        "{dataset} {version} (Zenodo record {record}): {member} has SHA-256 "
        "{sha256}, not the {expected} of the release Kartograf knows - another file, "
        "nothing written",
        "{dataset} {version} (rekord Zenodo {record}): {member} ma SHA-256 {sha256}, "
        "nie {expected} wydania znanego Kartografowi - inny plik, nic nie zapisano",
    ),
    "range_size": Text(
        "{product} {country}: {dataset} {version} (Zenodo record {record}): {count} "
        "{count:plural(file|files)}, {size_text}, read from the ZIP of {zip_size} at "
        "{url} by range requests - {transfer} to transfer",
        "{product} {country}: {dataset} {version} (rekord Zenodo {record}): {count} "
        "{count:plural(plik|pliki|plików)}, {size_text}, czytane z ZIP {zip_size} "
        "pod {url} zapytaniami o zakres - {transfer} do przesłania",
    ),
    "whole_archive": Text(
        "{product} {country}: {url} does not answer range requests ({error}): the "
        "whole ZIP of {zip_size} is downloaded to read {count} "
        "{count:plural(file|files)} from it",
        "{product} {country}: {url} nie odpowiada na zapytania o zakres ({error}): "
        "cały ZIP {zip_size} jest pobierany, by przeczytać z niego {count} "
        "{count:plural(plik|pliki|plików)}",
    ),
    "newer_release": Text(
        "{dataset} {version} (Zenodo record {record}, https://doi.org/{doi}, "
        "{published}) is newer than every release Kartograf knows (up to "
        "{newest}): it is read only by a Kartograf release that adds it after "
        "checking its layout",
        "{dataset} {version} (rekord Zenodo {record}, https://doi.org/{doi}, "
        "{published}) jest nowsze niż każde wydanie znane Kartografowi (do "
        "{newest}): czyta je dopiero wydanie Kartografa, które je doda po "
        "sprawdzeniu jego układu",
    ),
    "concept_failed": Text(
        "{dataset}: the newest release could not be asked at "
        "https://doi.org/{concept_doi}: {error}",
        "{dataset}: nie udało się zapytać o najnowsze wydanie pod "
        "https://doi.org/{concept_doi}: {error}",
    ),
}
