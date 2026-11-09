# ADR-061: HSG from the least permeable SoilGrids layer of 0-100 cm: `depth_rule="least-permeable"`

**Date:** 2026-11-09
**Status:** Accepted (the author's approval of the recommendations of PROGRESS item 29, 2026-11-09)
**Standard:** Nogat 1.0: DEV-10.1 (offline tests), DEV-10.5 (CLI = API parity)

**Context:** `calculate_hsg(depth=...)` classifies one SoilGrids layer, in practice the topsoil `0-5cm`.
NEH 630 ch. 7 (2009) assigns the hydrologic soil group by "the water transmitting soil layer with the lowest
saturated hydraulic conductivity" and by the depth to a water impermeable layer or a water table; for a soil
deeper than 100 cm to both, Table 7-1 uses the Ksat of the least transmissive layer within 0-100 cm: A > 10,
B > 4.0 to <= 10, C > 0.40 to <= 4.0, D <= 0.40 µm/s (the 40/10/1 µm/s limits apply to the layer within 0-50 cm
when an impermeable layer lies at 50-100 cm or the water table at 60-100 cm). Hydrograf asked on 2026-11-08 (its
ADR-075, Hydroni area h07, SoilGrids 2.0 set h07/2026-2): the 0-5 cm layer gives HSG B 95.1 %, A 4.8 % by area,
while by the least permeable layer of 0-100 cm the area is B 98.5 %, C 1.5 % with the Ksat classes of Rawls,
Brakensiek & Saxton (1982) and B 96.4 %, A 2.1 %, C 1.5 % with Saxton & Rawls (2006): the topsoil alone
overstates group A where loamy sand lies only at the surface (PROGRESS item 29).

SoilGrids gives clay, sand and silt at 0-5, 5-15, 15-30, 30-60, 60-100 and 100-200 cm, no Ksat, no depth to a
restrictive layer and no water table.

**Options considered:**
- (a) Topsoil only (today). It ignores a less permeable layer below the surface, against the criterion of
  NEH 630, and overstates A on sands over loams - rejected as the only behaviour; kept as the one-layer call.
- (b) Saxton & Rawls (2006): a continuous Ksat from clay and sand (and organic matter) per layer, then the
  NEH 630 thresholds. It needs organic matter (SoilGrids `soc`, one more input per layer), its regression gives
  for SoilGrids' smoothed textures a Ksat near the A/B limit (on h07 it moved 2.1 % of the area to A where the
  class approach keeps B), and its groups would no longer agree with the texture table of the one-layer call -
  rejected.
- (c) Rawls, Brakensiek & Saxton (1982) class Ksat and the NEH 630 thresholds applied to it. One value per USDA
  texture class (cm/h: sand 21.0, loamy sand 6.11, sandy loam 2.59, loam 1.32, silt loam 0.68, sandy clay loam
  0.43, clay loam 0.23, silty clay loam 0.15, sandy clay 0.12, silty clay 0.09, clay 0.06; µm/s = cm/h x 2.778).
  With the > 100 cm limits it gives A for sand and loamy sand, B for sandy loam, C for loam, silt loam, silt,
  sandy clay loam, clay loam, silty clay loam, D for the clays: loam, silt loam and silt would be C, while the
  table of ADR-025 (b) puts them in B, so a uniform loam profile would get B from the one-layer call and C from
  the profile - rejected (changing the table is the product decision of ADR-025 (b), not part of this rule).
- (d) Rawls (1982) class Ksat to find the limiting layer, its group from the texture table of ADR-025 (chosen).
  The order of the 1982 values never gives a lower Ksat a milder group of `TEXTURE_TO_HSG`, so the least
  permeable layer is also the layer of the strictest group, and a uniform profile has the group of its one-layer
  call. This is the variant Hydrograf measured: B 98.5 % / C 1.5 % on h07.
- (e) The profile as the new default of `soil hsg`. The repository is frozen until 0.8.0 and every choice of
  data is explicit (ADR-044); the existing calls (`depth="0-5cm"`, Hydrograf's bootstrap) keep their result -
  rejected.

**Decision:**
1. **The option.** `calculate_hsg`, `check_hsg` and `validate_hsg_request` take `depth_rule` (CLI
   `--depth-rule`), allowed values `least-permeable`; exactly one of `depth` and `depth_rule` (catalog constraint
   `one_of`, group `depth`; both given is a `ValidationError` with `options` `("depth", "depth_rule")`, an unknown
   rule one with `option` `depth_rule` and `allowed`). Without a rule the call is the one-layer call of before:
   a missing `depth` is the same error, the store segment, the units of the inputs and the sidecar do not change.
2. **The layers.** `least-permeable` reads clay, sand and silt (`mean`) at `0-5cm`, `5-15cm`, `15-30cm`, `30-60cm`
   and `60-100cm` (`HSG_PROFILE_DEPTHS`; 100-200 cm is outside the 0-100 cm range of NEH 630), as ordinary
   SoilGrids versions of the store (`soil/global_soilgrids_<property>_<depth>_mean/`). The report units of the
   inputs are `<property> <depth> <unit>`; the plan has 15 `landcover` positions and one `hsg`.
3. **The classification.** Per layer the USDA texture of ADR-025; per cell the layer with the lowest
   `RAWLS_1982_KSAT_CM_H` (the shallowest of equal values) gives the texture and its group by `TEXTURE_TO_HSG`.
   The 1982 table has no silt class: silt takes the value of silt loam (both B). A cell without data in any of the
   five layers is 0 (no data): the limiting layer is unknown there.
4. **The store.** The raster is a version of `hsg/global_soilgrids_0-100cm_least-permeable_mean/` (tokens depth,
   rule, statistic; `describe_segment` knows it), reused when the 15 input sha256 are the same. The sidecar
   `extra` has `depth` `0-100cm`, `depth_rule`, `depths` (the five layers), `ksat` (the source of the Ksat values)
   and, for every entry of `source_files`, its `depth`.
5. **Out of reach.** The water-table criterion of NEH 630 (wet valley soils as D or A/D, B/D, C/D) and an
   impermeable layer within 100 cm need another soil source than SoilGrids; the rule assumes a profile deeper
   than 100 cm to both. `hsg_from_rasters` stays a one-layer function.

**Consequences:**
- Hydrograf gets the profile group through `calculate_hsg(..., depth_rule="least-permeable")` (CLI
  `kartograf soil hsg --depth-rule least-permeable ...`); the one-layer results and stores are unchanged.
- A profile request fetches 15 SoilGrids rasters instead of 3 (five times the transfers on the first call;
  later calls reuse the versions).
- The groups of the rule are never milder than those of any of its layers, and a sand over loam is B, not A.
- Open for the author: loam, silt loam and silt are B by the table of ADR-025 (b) but C by the NEH 630
  > 100 cm limits applied to the Rawls (1982) Ksat; changing that is a change of the table for both calls.
