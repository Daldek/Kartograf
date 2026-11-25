"""
``kartograf server``: the read-only HTTP server of the command catalog (ADR-063).

The server answers the catalog (``commands list``, ``commands schema``, ...), the
queries without paths (``sheet parse``, ``<group> list-sources``, ...), the plans of
the data commands (``POST /api/v1/<group>/download?check=true``) and ``script
generate`` at ``/api/v1/<group>/<verb>``, each route the ``rest`` of its catalog
entry (AGI-6.1); ``GET /api/v1/server`` (``nogat-server/1``, AGI-6.7) and ``GET
/api/v1/openapi.json`` (OpenAPI 3.1 from the catalog, AGI-6.2). It runs nothing,
writes no data and takes no path from a client; its plans are detached plans
(ADR-063 decision 4), its errors ``application/problem+json`` in the language of
``Accept-Language`` (AGI-6.3, AGI-6.4), its limits per client (decision 8).

The modules: ``routes`` (the routes of the catalog), ``calls`` (a request as a call
of the library, with the refusals and the limits), ``problems`` (the problem
documents), ``openapi`` (the OpenAPI document), ``settings``, ``limits`` and
``stats`` (the limits and the daily totals), ``app`` (the Starlette application),
``serving`` (uvicorn with Nogat's logs) and ``nogat_logging`` (Nogat's reference
module, copied byte for byte). Only ``app`` and ``serving`` import Starlette or
uvicorn (the extra ``server``).
"""
