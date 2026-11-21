# SA-13 airship source and reconstruction audit

The [pressure-geometry follow-up](isae-sa13-pressure-geometry-20261109.md)
identifies the red pressure values as `100*(backward radius slope)^2 - 5`.
The first term has a possible local radial-source interpretation in the report;
the offset and pressure mapping remain unresolved. This qualifies the earlier
Cp interpretation below without changing reference values or denominators.

The [current discrete-load follow-up](isae-sa13-discrete-loads-20261109.md)
identifies the exact nodal-radius/next-station-slope relation in all 183 finite
red-curve lift values, including RS1's 9° incidence and R101's maximum-diameter
normalization. Those findings supersede the corresponding unresolved questions
below for the discrete load curves. Original complete models, continuous-curve
derivative inputs and pressure setup remain unavailable; no native pass is added.

**Historical reconstruction record.** The endpoint display defect below was
subsequently repaired by the [source transition](endpoint-source-transition.json).
See the [2026-11-09 pressure audit](isae-sa13-pressure-reference-20261109.md)
for the current reference-observable conflict. Neither change recovers the
missing original models or increases the 0/612 native comparison count.

The [primary-geometry follow-up](isae-sa13-primary-geometry-20261109.md)
recovers six numerical ZR III bow radii and qualifies the previously used
Figure 3 nose coordinate: the same primary report's text gives a different
coordinate. Neither interpretation is established as the original ASWING input.

**No physical validation claim.** This family supplies four MATLAB figures and no `.asw` models or operating scripts. Four separately named graph-based inputs are available for diagnostic calculations.

The [pinned source data](isae-sa13-sources.json) retain every numeric sample, gap, label and outline. The primary references are [NACA-TR-405](https://ntrs.nasa.gov/citations/19930091479) and [NACA-TM-574](https://ntrs.nasa.gov/citations/19930094841).

| Figure | Primary hull | Primary incidence | Finite measured samples | Reported AR | Reconstructed L/D |
|---|---|---:|---:|---:|---:|
| r33 | R-33 | 10° | 35 | 16.0 | 8.12314 |
| r101 | R-101 | 10° | 16 | 11.0 | 5.57714 |
| rs1 | RS-1 | 9° | 24 | 6.0 | 3.22712 |
| pressure | ZR III (primary; ISAE filename says R101) | 0° | 22 | — | 7.29522 |

## Primary-source conflicts

TR-405 Figure6 uses 9° for RS-1; ISAE Figure24 labels it 10°. Figures6/7 normalize transverse load per unit axial length by dynamic pressure and maximum diameter. Figure8 (R-101) divides by dynamic pressure alone, so its ordinate is dimensional; its caption specifies a 33.01-inch model. These curves cannot all be treated as the same local lift coefficient.

TM-574 describes the ZR III hull. Its Figure3 and Bernoulli equation show static gauge pressure as a percentage of freestream dynamic pressure, equivalent to 100Cp. The ISAE pressure filename says R101 and labels the ordinate as a dynamic-pressure ratio. Negative values are consistent with Cp, not with a nonnegative local dynamic pressure.

The raw outlines imply length/diameter ratios near8.1,5.5,3.2, while ISAE labels the first three16,11,6. The report defines aspect ratio using diameter. This discrepancy must remain visible; no aspect ratio was fitted to a measured force curve.

## Explicit geometry reconstruction

The unlabeled upper/lower outlines share their x samples and a constant center. Subtracting that center gives signed radius. Closed tips use the nearest outline zero crossing, or linear extrapolation of the first/last positive segment when no crossing is stored. Only the contiguous positive interior is used, with zero-radius endpoints. The same geometric scale converts x and radius, and reconstructed length is one metre. Original negative samples remain unchanged in the source record.

- [r33 diagnostic input](isae-sa13-r33-outline.asw): linear_extrapolation at the nose, linear_interpolation at the tail; source center 0; setup outcomes 32: constructed, 64: constructed, 128: constructed.
- [r101 diagnostic input](isae-sa13-r101-outline.asw): linear_extrapolation at the nose, linear_extrapolation at the tail; source center 0; setup outcomes 32: constructed, 64: constructed, 128: constructed.
- [rs1 diagnostic input](isae-sa13-rs1-outline.asw): linear_extrapolation at the nose, linear_extrapolation at the tail; source center 0; setup outcomes 32: constructed, 64: constructed, 128: constructed.
- [pressure diagnostic input](isae-sa13-pressure-outline.asw): linear_interpolation at the nose, linear_interpolation at the tail; source center -19.5; setup outcomes 32: constructed, 64: constructed, 128: constructed.

The R33 input currently fails display construction: its mathematically zero tail radius evaluates as a tiny negative floating-point value. Native aerodynamic quadrature still constructs. The source audit retains the exact error and spline extrema; no positive endpoint was substituted. The interpolant also overshoots the largest radius sample, which is a separate geometry-accuracy concern.

This construction is conditional on the plotted outlines representing physical geometry at equal scale. Natural cubic interpolation and caps introduce further uncertainty. It supplies a reproducible diagnostic model, not recovered original ASWING input. No force/pressure values, drag offsets or solver tolerances were fitted.

## Remaining work

- No asw file, operating command, mesh, units, reference area, sensor placement or exact executable state is supplied for SA-13. Figure legend labels alone do not establish how the curves were computed.
- All raw samples and NaN gaps are retained. The first three abscissas are not literal normalized s/L despite that axis label; their x ticks are hidden. Two unlabeled curves resemble the primary hull outlines.
- Graph-based reconstruction assumes equal horizontal/vertical geometry scale in each stored outline, removes its center, finds closed caps geometrically and normalizes length to1. It is not an independently measured radius table.
- R33 has one negative signed outline radius; the pressure figure has three. These remain in the source record. A separately named closed-body reconstruction uses the contiguous positive outline and zero crossings, without relaxing the parser or radius validity checks.
- The three reported aspect ratios16/11/6 are approximately twice the geometric length/diameter ratios of the stored outlines. Do not impose these reported numbers as L/D without reconciliation.
- RS-1 primary incidence is9deg, not the10deg ISAE caption. The saved ASWING states do not establish their actual incidence; compare the two as explicit diagnostics.
- The R101 primary load ordinate differs dimensionally from the R33/RS1 normalization. The primary model length33.01in can set a conditional dimensional reconstruction, but maximum diameter inferred from a plotted outline carries geometric uncertainty.
- The pressure filename identifies R101, whereas the cited primary report and Figure3 identify ZRIII. The pressure ordinate represents100Cp, not100q_local/q_infinity.
- Source-series labels Continuous ASWING5.96 and Discrete ASWING5.96 are preserved. ISAE describes a modified radius-derivative implementation, but neither its code nor exact radius/derivative input is supplied.
- Natural cubic interpolation, endpoint closure and digitization noise affect radius derivatives and surface velocities. Mesh refinement alone does not remove geometry uncertainty.
- The R33 natural spline overshoots the largest radius sample and evaluates its exact zero tail knot as a tiny negative floating-point value. Native quadrature constructs, but current display geometry rejects that radius. This reproducible interpolation/display defect is retained; no positive endpoint was substituted to bypass it.
- Body force density must be compared in body transverse axes, not substituted by a global wind-axis lift coefficient. Viscous stern forces, finite-body apparent-mass factors and measured uncertainty require separate treatment.
- These are source and reconstruction checks, not experimental validation. No production module or physical-validity guard is changed.
