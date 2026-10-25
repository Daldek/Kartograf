"""Messages of the CLMS Auth Proxy."""

from kartograf.messages import Text

MESSAGES = {
    # ``auth.proxy``.
    "clms_credentials_bad_json": Text(
        "CLMS_CREDENTIALS is not valid JSON ({error})",
        "CLMS_CREDENTIALS nie jest poprawnym JSON ({error})",
    ),
    "clms_credentials_bad_shape": Text(
        "CLMS_CREDENTIALS must be a JSON object with the fields client_id and "
        "private_key",
        "CLMS_CREDENTIALS musi byc obiektem JSON z polami client_id i private_key",
    ),
}
