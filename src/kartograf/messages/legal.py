"""
Formulas that keep their wording in every language.

The attribution of the GUGiK licence is stored in the sidecar of every file, so a file
must not depend on the language of the person or program that wrote it. The Polish text
is the English one by design (the guard test allows it for this area only).
"""

from kartograf.messages import Text

_GUGIK_ATTRIBUTION = (
    "Dane: Glowny Urzad Geodezji i Kartografii (www.geoportal.gov.pl), "
    "art. 40a ust. 2 pkt 1 ustawy Prawo geodezyjne i kartograficzne"
)

MESSAGES = {
    "gugik_attribution": Text(_GUGIK_ATTRIBUTION, _GUGIK_ATTRIBUTION),
}
