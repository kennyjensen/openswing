# SA-14 wing/body source audit

**Comparisons are pending.** All 50 upstream files are pinned to the repository revision. The four literal models remain unchanged. [Machine-readable sources](isae-sa14-sources.json) retain all measurements, commands, polars, load exports and geometry tables.

The primary reference is [Martina, NACA-TN-3730 (April 1956)](https://ntrs.nasa.gov/citations/19920075067). Its test is at Mach 0.19 and Reynolds number 4 million. The swept wing has span 127.26 in, area 14.021 sqft and no twist for the selected comparisons. The body is elliptic/constant/parabolic with fineness ratio 10.

## Import and geometry

| Input | Native mesh | Display | Note |
|---|---|---|---|
| wing_body | All 25/50/100 requested meshes construct | constructed | Original input |
| wing_only | All 25/50/100 requested meshes construct | constructed | Original input |
| infinite_body | All 25/50/100 requested meshes construct | constructed | Original input |
| body_only | All 25/50/100 requested meshes construct | rejected | 12× geometric scale; different reference values |

## Measurements and normalization

Figure7 supplies 48 local-load points for wing alone and wing/body at 4.7°, 8.8° and 12.9°. Figure24 supplies 44 total/exposed lift points. Figure17.csv supplies 24 additional points labelled iw=4°; its name conflicts with the primary figure numbering and it has no matching original input.

The three directories containing Figure7/17/24 CSVs are exact duplicates. The actual ASWING evidence consists of three CL polar tables and two load-distribution text exports, plus manually embedded plotting arrays.

For local loads, use 2y/b and wind-axis force per unit span divided by q times the mean geometric chord Sw/b. The primary exposed-wing integration starts at 2y/b=0.1. Figure24 total balance lift includes the body; its other two series contain exposed-wing pressure lift.

The MATLAB script instead divides normal-section cl times chord by 0.593969696m and multiplies archived global CL by 0.86176422. Those prescriptions will remain separate diagnostics. Neither supplies a replacement for the primary force normalization.

Primary Figure17 shows negative incremental loading from a change of incidence. The positive absolute loads in Figure17.csv resemble the iw=4° branch of primary Figure15. This mapping remains conditional until the digitization can be traced.

## Remaining qualifications

- All four original inputs parse. The body-only file uses feet-to-metre factors 0.3048 while the coupled model uses inch-to-metre 0.0254. Its geometry is 12 times larger, with different references; do not substitute it as the coupled fuselage.
- Body-only display currently rejects a tiny negative closed-tip radius; native body quadrature constructs. The isolated SA13 endpoint candidate is not applied to these pinned results.
- Figure7/17/24 CSVs under ASWING_data and ASWING_simulations are byte-identical to Experimental_data; they are duplicate measurements, not independent archived solver output.
- Figure17.csv has absolute iw=4deg labels and positive loads. Primary Figure17 is negative incremental loading. Figure15 is the likely source of the absolute series, but the digitization provenance is unresolved and no iw=4deg input is supplied.
- The primary local-load normalization uses mean geometric chord Sw/b, not mean aerodynamic chord. The postprocessor uses 0.42*sqrt(2), with manually copied normal-section cl/chord rows.
- Primary Figure24 distinguishes total wing/body balance lift from pressure-integrated exposed-wing lift with/without body. A global CL or a constant area multiplier is not interchangeable with those observables.
- Polars contain only CL and do not record mesh or PG. Load-distribution exports use PG Mach 0.2058 at 4.7deg but 0 at 8.8/12.9deg, while the primary test Mach is 0.19; retain the mixed settings explicitly.
- The supplied NACA63A012.txt is airfoil coordinates, not the claimed XFOIL polar. Literal inputs set dCLda 6.2832 and CLmax 2; exact section polar provenance and high-angle validity are unresolved.
- The ISAE report attributes weak archived constant-body interference to a source-code conditional and reports unresolved instability after modification. The cited conditional alone does not establish that explanation; matching executable/source evidence is unavailable.
- No image-vortex body boundary correction is inferred from these measurements. Numerical body-field verification and physical wing/body agreement require separate evidence.
- No physical parameter, geometry, digitized value, source label or solver tolerance is fitted or silently changed.
