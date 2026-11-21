# Additional aerodynamic reference codes: OpenAeroStruct and PyTornado

2026-10-30. Two more implementations were downloaded and inspected for the
remaining SA-1–SA-5 discrepancies. Both are vortex-lattice methods (VLM), useful
for isolating geometry, velocity and force calculations. Neither implements
ASWING's nonlinear lifting-line section law. This review found no confirmed
new OpenSwing defect and ran no new aircraft solution or ISAE comparison.

## New retained sources

| Code | Pinned revision | Most useful comparison |
|---|---|---|
| [OpenAeroStruct](https://github.com/mdolab/OpenAeroStruct) | `0a4d614f9494cbadaba4a6fa32a33d6e54e14f34` | Separate tangency and force receivers; conversion from ring circulation to force-producing circulation; bound-vector force integration |
| [PyTornado](https://github.com/airinnova/pytornado) | `6c005b302f894f26cf406c9f8107bb5f050f053f` | Explicit three-leg horseshoes, trailing-leg origins, all-source velocity summation, force and moment recovery |

The 24 unmodified source/documentation/license files total 224,479 bytes.
Each directory's manifest records immutable URLs, SHA-256 hashes and verified
Git blob identities: [OpenAeroStruct](../../reference/third_party/openaerostruct/SOURCE.json),
[PyTornado](../../reference/third_party/pytornado/SOURCE.json). Both include their Apache
2.0 license. These selections are incomplete reference packages, not new
runtime dependencies. The
[download script](../../artifacts/isae/lifting-line-oas-pytornado-review-20261030/download_sources.py)
reproduces the selections and refuses to overwrite locally changed files.

## OpenAeroStruct findings

In the pinned `openaerostruct/aerodynamics` sources:

- `collocation_points.py:143–167` constructs three-quarter-chord tangency
  receivers, quarter-chord force receivers and quarter-chord endpoint vectors.
  Both receiver types use arithmetic spanwise midpoints.
- `states.py:60–125` has distinct influence/velocity paths for solving the
  circulation and evaluating loads. `eval_mtx.py:304–393` sums all ring edges
  and adds the trailing wake. There is no general deletion of adjacent
  spanwise strips in these loops.
- `horseshoe_circulations.py:49–78` takes differences between consecutive
  chordwise ring circulations. The physical force must use that converted
  circulation rather than directly using every ring strength.
- `panel_forces.py:100–108` computes density times circulation times the
  cross product of total local velocity and the actual bound endpoint vector.
  `lift_drag.py:48–66` projects the integrated forces into wind axes.

Its singularity handling must be recorded in any numerical comparison:
`eval_mtx.py:11–24` zeros a finite-segment contribution when the absolute
denominator `|r1||r2| + r1·r2` is at most `1e-10`. This is a dimensional cutoff,
not a demonstrated ASWING core rule. An external result near that cutoff
cannot be treated as an exact reference.

## PyTornado findings

The pinned `src/lib/pytornado/aero/c_lattice.cpp:203–230` puts bound endpoints
at the panel quarter chord, starts each trailing leg at its bound endpoint,
and uses an arithmetic bound midpoint for force evaluation. A conforming
spanwise panel boundary therefore shares the quarter-chord endpoint when its
chord endpoints agree. This is a useful check on adjacent wake origins.

`c_downwash.cpp:30–95` loops over every source panel and all three horseshoe
legs for the tangency matrix. `c_results.cpp:64–158` does the same at each
force receiver and uses the actual bound endpoint vector for Kutta–Joukowski
force. It does not skip whole neighboring strips. The section and load paths
also include aircraft rotation with explicit reference-point offsets.

Two differences matter before using it as a numerical reference. The wake is
represented by finite legs of length **10,000 geometry units**
(`c_lattice.cpp:54–61`), and the kernel includes an `EPSILON` denominator
regularization (`c_results.cpp:112`, `c_downwash.cpp:78`). Neither matches an
unregularized semi-infinite ray automatically. Its
[theory documentation](https://pytornado.readthedocs.io/en/latest/theory/)
also explicitly excludes stall from this linear VLM model.

## Which references are most valuable for the current errors?

| Question | Priority references already retained | Why |
|---|---|---|
| SA-4 curved/swept source geometry and refinement | MachUpX, FLOWPanel, DUST | Explicitly distinguish source geometry, section velocity and force velocity |
| SA-1/SA-5 high-angle section behavior | JVL, XFLR5, CN-AeroModels, DUST | Inspect section normalization, polar/stall closure and circulation convergence, keeping their different stall laws separate |
| Near-field versus Trefftz drag | AVL/JVL, VortexLattice.jl, TASOPT, VSM | Separate force integration, circulation jumps, shared filaments and wake-energy factors |
| Additional geometry/force bookkeeping check | OpenAeroStruct, PyTornado | Small, readable implementations with distinct solve and load stages |
| Later strip/beam coupling checks | AeroBeams, Aeroelasticity.jl, SHARPy | Relative section motion, frame transformations and distributed load transfer |

The [existing VortexLattice.jl comparison](vortexlattice-force-audit-20261030.md)
already passes 1,164 controlled force/wake checks. Its consistent substitution
of arithmetic force receivers barely reduces the SA-2 near/far drag gap and
worsens all 96 retained SA-4 fields. The new source reviews therefore do not
justify trying that isolated substitution again. The
[TASOPT comparison](lifting-line-flowpanel-tasopt-review-20261030.md) also
supports wake-strength signs and normalization at prescribed circulation.

The remaining useful investigation is to compare the complete mapping from
beam/input geometry to source endpoints, section/force receivers and the
section equation. At fixed geometry and circulation, velocities and loads
can be compared separately; only after that should independently solved
circulation be compared. This separates an arithmetic error from a formulation
or input difference. Drela's equations remain the implementation target.

No production source, numerical default, acceptance tolerance or ISAE status
was edited in this review. Source inspection is not an additional ASWING pass.
