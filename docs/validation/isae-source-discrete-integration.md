# Reusable static formulation: archived ST-3 and ST-5

Updated 2026-10-26. The comparison target is the archived **ASWING output with
unchanged input models**, not experimental measurements. The full project is
incomplete. This increment moves the ST-5 prototype into an explicit Python
solver API and checks it on both original static cases. It does not select a
new default in the browser.

Subsequent work: the [browser and reporting follow-up](isae-source-static-browser.md)
now provides the bounded static option, source-specific section/sensor recovery,
and verified preservation of old and new projects. The results below retain
their original scope and source pins.

| Case | Intervals | Native solve time | Strict structural matches |
|---|---|---|---|
| ST-3 original negative-coupling snapshot | 44 / 88 / 176 | 0.61 / 0.75 / 1.13 s | 220 / 270 on each grid |
| ST-5 original rigid-joint 20 lb 80/20 snapshot | 70 / 140 / 280 | 0.72 / 0.96 / 1.63 s | 403 / 129 / 120 of 1,120 |

All six cold solves and six independent network restorations pass the existing
residual, load-balance, and attachment checks. Maximum fresh residuals are
2.60×10⁻¹⁶ for ST-3 and 1.09×10⁻¹⁴ for ST-5. ST-3 passes all ten mesh checks.
ST-5 retains its earlier mesh sensitivity: 0/14 and then 4/14 checks pass.
Refining this case moves the solution away from the finite-grid archive; mesh
convergence and reproduction of a particular archived grid are distinct tests.

On the archived ST-5 grid, forward/rear tip-deflection differences remain
0.00084% / 0.0086%, and tip-twist differences remain about 0.013%. Every
structural channel's maximum absolute error is below 0.025% of its archived
absolute envelope. These are descriptive errors, not a widened acceptance
tolerance. The new implementation preserves the preceding
[source-discrete diagnostic](isae-st5-source-discrete.md).

ST-3's coarse tip deflection is 40.0461 mm versus printed 40.0 mm; twist is
21.9620° versus 22.0°. Its original signed weights remain at the rotating
±0.07 m pylons, producing the required force couple. Strict comparison at
printed coordinate centers gives 220/270 structural matches and accounts
separately for 90 conditional zero values. The earlier midpoint-solver
[rounding analysis](isae-st3-reference.md) found 269/270 compatible structural
entries; that coordinate-witness calculation has not been repeated for this
new operator. The archived 5.59×10⁻⁹ N·m tip-moment residual is still retained
as a difference, rather than fitted by changing the load.

## Implementation and preservation

`parse_asw(source, beam_interpolation='drela-segspl-v1')` opts into independent
segmented beam cubics with zero third derivatives on the end intervals.
`natural-v1` remains the default. Joint laws and time-forcing tables retain
their existing interpolation. Literal ASW export preserves the source bytes;
the numerical policy is metadata, not an invented ASW field.

`openswing.source_discrete.solve_source_discrete` implements the documented
endpoint matrix averages and inverse of averaged bending/torsion stiffness.
It supports a full symmetric coupled stiffness matrix, exact rigid directions,
finite axial stiffness, endpoint-averaged distributed gravity, concentrated
forces/moments, and rotating point-weight pylons. Both sparse and full Newton
paths differentiate the selected residual without a process-global patch.

The current scope is static lifting-surface beams with zero section and
distributed-CG offsets, rigid shear, and rigid Ground/Joint constraints.
Unsupported body charts, stepped axes, flexible shear, other joints, struts,
airflow, moving-frame loads and dynamics are rejected. Euler singularities and
branch crossings are explicit limitations. EA averaging and use of unloaded
arc length for unsubscripted ds remain declared interpretations of the source;
the historical executable's exact choices are not established.

Saved states identify both interpolation and structural operator. Old untagged
states retain their original equations, including all three existing mesh
recipes. A state from one operator cannot silently initialize another. The new
static solver exports no dynamic launch. Editing, symmetry, grafting, frequency
model copies and frequency-matrix reuse preserve or check interpolation policy.

`source_discrete_elements` contains the selected operator's constitutive local
loads and strains. Inherited midpoint section/sensor reports are explicitly
supplemental; completing their integration is still required before exposing
this solver as a complete browser analysis option.

## Verification and reproduction

The 124 parser/edit/mesh/state checks pass, including an independent rational
cubic-coefficient oracle and unchanged frozen legacy states. Sixteen focused
structural tests pass across targeted runs: exact axial extension and discrete
bending/torsion limits, coupled/rigid stiffness, point-pylon conservation, both
Jacobian paths, scope rejection and state-policy separation. Fixture-only
failed attempts are retained. Another 74 solver, frequency-reuse and saved
Daedalus regressions pass.

Six project-format regressions pass. A separate offline Node/Pyodide replay
solves the same 70-interval ST-5 case in 1.79 s after 10.83 s runtime setup.
All 9,325 numeric values in the core result agree with native execution under
the predeclared 2×10⁻⁸ absolute plus relative gate; the maximum absolute
difference is 7.89×10⁻¹¹. No network requests occur. This verifies the WASM
runtime, not browser UI selection or project integration of the new policy.

The reference replay uses the existing full-output decoders, original three
grids for each case, and unchanged numerical/precision gates:

```sh
.venv/bin/python scripts/verify-source-discrete-integration.py prepare --stage /tmp/my-source-static-check
.venv/bin/python scripts/verify-source-discrete-integration.py run --stage /tmp/my-source-static-check
```

The [machine-readable report](isae-source-discrete-integration.json) records
source identities, timings, per-case summaries and verification receipts.
Next work is complete section/output recovery, the remaining section/load and
joint models, consistent aerodynamic/dynamic equations, and browser selection
with project-policy preservation. No experimental-property reconstruction is
required to complete these ASWING comparisons.
