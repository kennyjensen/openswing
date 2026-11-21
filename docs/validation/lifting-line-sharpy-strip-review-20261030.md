# Further reference codes: SHARPy/UVLM and AeroBeams

2026-10-30. Two more independently developed implementations have been located
and inspected. Eighteen unmodified files, including original licenses, are
retained as reference selections. Neither solver was installed or executed.
No new OpenSwing defect, corrected ASWING result, or numerical parity with
these two packages is claimed.

| Reference | Retained revision | Useful comparison | Important limit |
|---|---|---|---|
| [SHARPy](https://github.com/ImperialCollegeLondon/sharpy) and its [UVLM backend](https://github.com/ImperialCollegeLondon/UVLM) | SHARPy `7c9883e3719ff8f6905396a0ae1da765ce96b899`; UVLM `d8af34a22baf1cddd38f1e362274c407637aab1c` | Shared-edge circulation, wake connectivity, force sampling, induced/profile drag separation | A vortex lattice, with chordwise surface filaments and a different closure, rather than ASWING's lifting line |
| [AeroBeams.jl](https://github.com/luizpancini/AeroBeams.jl) | `7751b374b5046a98befca2ae06eb7f06d2ce5491` | Section velocity projections, strip-force axes, sweep factors, force/moment transfer to a flexible beam | Strip theory with prescribed spanwise corrections; its optional aspect-ratio drag estimate does not solve a 3D wake |

The selected UVLM revision is exactly the submodule commit recorded by the
retained SHARPy tree. Manifests record source URLs, SHA-256 hashes and upstream
Git blob hashes: [SHARPy](../../reference/third_party/sharpy/SOURCE.json),
[UVLM](../../reference/third_party/sharpy_uvlm/SOURCE.json), and
[AeroBeams](../../reference/third_party/aerobeams/SOURCE.json).
SHARPy/UVLM use BSD-3-Clause licenses; AeroBeams uses MIT.

## SHARPy: shared filaments and force recovery

The steady horseshoe route in
[`include/steady.h:259`](../../reference/third_party/sharpy_uvlm/include/steady.h)
calls `calculate_static_forces`. In
[`include/postproc.h:61`](../../reference/third_party/sharpy_uvlm/include/postproc.h),
that routine traverses the surface-ring edges, skips the trailing-edge edge,
and samples velocity at each edge's geometric midpoint. It sums induced
velocity from every surface, then evaluates
`rho * Gamma * (velocity cross edge_vector)` and divides the load between
the edge's two nodes (lines 125–173).

**Inference from this assembly:** two coincident, oppositely oriented shared
edges sample the same velocity. Their forces therefore combine in proportion
to the difference of their circulations. Equal circulation cancels a shared
edge; different circulation leaves a net filament. This cancellation requires
coincident geometry and does not imply deleting adjacent-strip influence.

The finite-wake force routine makes that difference explicit:
`postproc.h:365–372` forms the chordwise difference for spanwise edges, and
`:412–421` forms the spanwise difference for chordwise edges. Both bound and
wake surfaces contribute to the sampled velocity. This corroborates the
shared-leg accounting found in the earlier VSM review.

This is a useful geometry/accounting comparison for SA-4, but does not reveal
a missing term by itself. ASWING's documented force uses the section-span
vector and interval measure; UVLM uses actual lattice-edge vectors, including
chordwise surface edges. Its finite-segment kernel also has endpoint and
near-collinearity cutoffs (`include/biotsavart.h:367–390`). Neither the edge
forces nor that cutoff should be transplanted in isolation.

SHARPy's optional polar correction is also different from ASWING's nonlinear
circulation equation. In
[`polaraeroforces.py:193–235`](../../reference/third_party/sharpy/sharpy/generators/polaraeroforces.py),
the routine extracts lift from existing forces, obtains polar drag/moment
using either that lift or an inferred angle `cl / (2*pi) + alpha_zero`, then
adds profile drag to the existing induced drag. Optional lift replacement
happens in the force correction. This routine is not an independent
implementation of Drela's stall-leakage closure and cannot authenticate the
SA-1 high-angle section law.

## AeroBeams: useful strip checks, limited induced-drag evidence

In [`src/Aerodynamics.jl:55–88`](../../reference/third_party/aerobeams/src/Aerodynamics.jl),
the relative velocity is transformed into the section frame. The section
speed is the norm of its tangential and normal components, excluding the
spanwise component. The same speed enters the dynamic-pressure factor in
`:1966`. This is consistent with OpenSwing's use of section-plane speed for
circulation normalization (`openswing/aero.py:476–486`), without establishing
equivalence of either solver's complete aerodynamic loads.

The attached-flow normal and tangential coefficients are separate
(`Aerodynamics.jl:570` and `:658`). An optional induced-drag contribution is
formed from `cnC^2 / (pi * AR) / cos(alpha)` at `:683–685`; the option defaults
to false in `src/AeroSurface.jl:301`. It is an aspect-ratio estimate, not a
Trefftz-plane calculation from solved circulation. Thus this code is less
useful than MachUpX, DUST or OLAF for the remaining 3D drag discrepancy.

The load-transfer routine at `Aerodynamics.jl:1949–2002` makes its section
axes, swept-chord factor, spanwise correction and nodal force/moment rotations
explicit. Those are useful independent audit points for structural coupling.
The available Beddoes–Leishman stall models are different physical models
from Drela's published leakage law; no ASWING stall equivalence was established.

## Priority for the remaining SA-1–SA-5 work

The most relevant retained references remain:

1. **MachUpX:** source-line geometry and curved/swept-wing singularities.
2. **AVL, DUST, VSM and SHARPy/UVLM:** consistent source/control/force locations,
   shared filaments and near-field force accounting.
3. **CN-AeroModels and XFLR5:** nonlinear section inputs, speed normalization
   and straight-wing loading, with their different closure laws recorded.
4. **AeroBeams:** section-frame and beam-load projections, rather than a 3D
   induced-drag reference.

The earlier [AeroSandbox](lifting-line-source-review-20261030.md) and
[OLAF](lifting-line-additional-review-20261030.md) executed comparisons already
support the baseline vortex arithmetic. The
[AVL/CN review](lifting-line-avl-cn-review-20261030.md) and
[VSM review](vortex-step-method-review-20261030.md) cover other force conventions.
The subsequent [SA-4 force-vector audit](../../artifacts/isae/sa4-force-vector-audit-20261030/report.md)
tested a specific AVL-inspired substitution and found it insufficient; this
review does not reopen it as an untested fix.

A legacy TU Delft NLLL manual was found again, but the upstream endpoint still
timed out. No source inspection or implementation claims are made for it.

All eighteen downloads match the upstream Git blob identities and their local
manifests. OpenSwing's production Python files and `ISAE_STATUS.md` remain
byte-for-byte unchanged. The 3% acceptance policy and all registered case
counts are unchanged. [Verification record](../../artifacts/isae/lifting-line-sharpy-strip-review-20261030/verification.json).
