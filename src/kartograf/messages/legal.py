"""
Formulas that keep their wording in every language.

The attributions of the GUGiK licence and of the PGW Wody Polskie publication are
stored in the sidecar of every file, so a file must not depend on the language of the
person or program that wrote it. The Polish text is the English one by design (the
guard test allows it for this area only).
"""

from kartograf.messages import Text

_GUGIK_ATTRIBUTION = (
    "Dane: Glowny Urzad Geodezji i Kartografii (www.geoportal.gov.pl), "
    "art. 40a ust. 2 pkt 1 ustawy Prawo geodezyjne i kartograficzne"
)
# The source of the IIaPGW geodatabase and the reservation of its publication page
# (https://apgw.gov.pl/pl/III-cykl-materialy-do-pobrania, 2026-11-06; no licence named).
_PGW_ATTRIBUTION = (
    "Dane: PGW Wody Polskie, KZGW, IIaPGW (apgw.gov.pl); materialy pomocnicze, "
    "prawnie obowiazuja plany gospodarowania wodami ogloszone w Dzienniku Ustaw"
)

MESSAGES = {
    "gugik_attribution": Text(_GUGIK_ATTRIBUTION, _GUGIK_ATTRIBUTION),
    "pgw_attribution": Text(_PGW_ATTRIBUTION, _PGW_ATTRIBUTION),
}
