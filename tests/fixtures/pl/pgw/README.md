# PGW Wody Polskie: the IIaPGW geodatabase (ADR-059)

Recorded on 2026-11-06. `archive.json` holds the only spatial file that
<https://apgw.gov.pl/pl/III-cykl-materialy-do-pobrania> links ("Geobaza IIaPGW"): its URL,
the answer to its `HEAD` (200, no `ETag` and no `Last-Modified`; header names in their
canonical form, the cookie and security headers left out) and member names of the ZIP
(a subset of the 304: the first ones, the `gdb` marker of the geodatabase and its
`timestamps`).

`head` is the answer to a `HEAD` that asks for the file as it is (no `Accept-Encoding`, or
`identity`). The server compresses its answers on request: to the `Accept-Encoding: gzip,
deflate` that `requests` sends by default it answers with `Content-Encoding: gzip`, the `HEAD`
with `Content-Length: 20` (`head_gzip`) and the `GET` chunked, without a length
(`get_gzip`); `requests` decodes that body to the 142,048,450 bytes of the ZIP.

The tests do not hold the 142 MB file. They serve the tiny archive of
`kartograf.testing.build_pgw_archive`, which has the published structure: the same
geodatabase name, feature datasets, layers, identifier and geometry columns, fields and
CRS definition, recorded from the real archive in `src/kartograf/_data/pgw_geodatabase.json`
by `scripts/build_pgw_geodatabase.py`.
