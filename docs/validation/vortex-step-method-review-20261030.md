# Vortex Step Method source review

2026-10-30. The [TU Delft Vortex Step Method implementation](https://github.com/awegroup/Vortex-Step-Method)
adds a useful comparison for the remaining SA-4 force/geometry questions.
Selected unmodified files from revision
`716eb8d266c06b7fcce740a9b66a26bec1d75197` are retained in
[`third_party/vortex_step_method`](../../third_party/vortex_step_method/SOURCE.json),
including its MIT license and hashes. This is a source inspection, not a full
external solver run or a new native ASWING comparison.

## What the implementation actually does

| Operation | Retained source | Relevance |
|---|---|---|
| Circulation closure | `BodyAerodynamics.py:759`, `utils.py:183`, `Panel.py:244` | VSM sums the full vortex system at the three-quarter-chord point, then subtracts the section's infinite 2D bound-vortex contribution on the diagonal. The correction belongs to its polar-based closure. |
| Force direction | `BodyAerodynamics.py:1274` and `:1983` | The VSM force direction uses quarter-chord flow. It includes other panels' bound vortices, including immediate neighbors, and excludes only the own bound segment from this added bound contribution. |
| Alternate LLT path | `utils.py:217`, `BodyAerodynamics.py:1986` | The standalone LLT influence matrix omits all bound segments. The VSM force-direction path explicitly adds the non-self bound contributions back. Inspecting only the LLT helper would give the wrong description of the VSM force calculation. |
| Chordwise surface-vortex force | `BodyAerodynamics.py:1164` | Adjacent panel legs share their endpoints and combine through the circulation jump. The code adds their Kutta–Joukowski forces, sampled on the legs. This is separate from induced velocity. |
| Induced-drag cross-check | `BodyAerodynamics.py:1116` | A separate Trefftz calculation uses wake circulation jumps and half the far-wake velocity. Its applicability is restricted to uniform translating inflow. |
| Regularization | `Solver.py:66`, `Filament.py:94` | The bound-vortex core defaults to 5% of segment length; trailing filaments have a different viscous-core treatment. Those conventions differ from OpenSwing's zero-core interactions within a physical lifting surface. |

These source locations refer to the pinned files, not a moving upstream branch.
The actual routines were inspected, including the compiled-loop source in
`utils.py`; no claim of numerical parity with this package has been made.

## New lead and its limits

The authors' [2026 supporting paper](https://doi.org/10.1088/1742-6596/3224/4/042030)
separates section-force magnitude and direction and introduces a force on
chordwise attached vortex legs, particularly relevant to sweep. The
[institutional abstract](https://orbit.dtu.dk/en/publications/from-thin-airfoil-theory-to-finite-wings-consistent-implementatio/)
also describes comparisons on curved wings. This is a useful lead for the
near-field/Trefftz discrepancy. The abstract and implementation were inspected;
attempts to retrieve that paper's full PDF returned HTTP 403. The older
`docs/Aerodynamic_model.pdf` retained with the source is a different document.

This does **not** establish a missing force term in OpenSwing. Its ASWING-based
construction uses wind-directed offsets and horseshoes starting at the bound
line; VSM has chordwise surface legs leading to the trailing edge. OpenSwing
also solves Drela's tangency/leakage equations rather than VSM's polar closure.
Adding VSM's force or 2D correction alone would mix formulations. The existing
[quarter-chord audit](../../artifacts/isae/quarter-chord-source-audit-20261030/report.md)
already demonstrates why changing only a receiver can be inconsistent.

The useful next derivation is to compare the **complete** source geometry,
section equation, force location and integration vector against Drela's
equations on the same straight and swept limiting cases. This source supplies
another explicit implementation to inspect, not permission to omit adjacent
strips or tune a core until the ISAE outputs agree.

No OpenSwing production code, mesh defaults, tolerances or native pass counts
changed. The prior [AeroSandbox](lifting-line-source-review-20261030.md) and
[OLAF](lifting-line-additional-review-20261030.md) arithmetic comparisons remain
the executed external checks; no new equilibrium was computed in this review.
