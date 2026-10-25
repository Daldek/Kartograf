<!-- BEGIN kartograf -->
## Kartograf

Kartograf downloads official spatial data of Poland and Czechia (elevation models and LAZ, orthophotos, land cover, soils and HSG, boundaries, cadastre) into a versioned store with metadata. Not for hydrological computation (use Hydrolog) or IMGW and CHMU series (use IMGWTools).

Rule: discover, check, run, read.

1. Discover: `kartograf commands list`, then `kartograf commands schema --command NAME`; do not guess options or allowed values.
2. Check: add `--check` to a command that downloads; the plan fetches and writes nothing. Select the data explicitly (product, resolution, vertical CRS, area).
3. Run with `--json` and an absolute `--root`: the result is a `kartograf-result/1` envelope, an error a `kartograf-error/1` document (decide by `code`).
4. Read `status`, `result`, `items` and `notices`; `partial` and `failed` are results, not errors.

<!-- kartograf:block_commands -->

Update this block: `kartograf commands guide --format agents-md-block --inject AGENTS.md`.
Full guide: https://raw.githubusercontent.com/Daldek/Kartograf/main/AGENTS.md
<!-- END kartograf -->
