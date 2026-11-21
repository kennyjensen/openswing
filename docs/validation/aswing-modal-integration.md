# Published modal method: implementation and original ST-4 comparison

Updated 2026-10-26. The full-descriptor modal solver now follows Drela's
shifted Arnoldi formulation, retaining every equation and reusing a sparse
LU factorization. Fresh browser settings select **ASWING · shifted Arnoldi**.
Existing saved solver choices and the Python API's dense default are preserved.
This is progress toward ASWING parity, not completion of the full project.

## Equations and implementation

The [primary-method review](aswing-modal-method.md) maps unsteady theory
Eqs. 147–149 to `H x = solve(A - mu M, M x)`, using standard complex ARPACK
and transforming its eigenvalues once. The new path applies no finite-rank
reduction or integrator deflation. Each backsolve is checked against the
unchanged shifted matrix. It reports a local selection, not a complete
finite-spectrum census or certified zero multiplicity.

Left vectors first use the paper's Eqs. 150–152 inverse iteration, with one
reused factorization per supplied pole and the stated complex mass
normalization. Singular or unresolved iterations and repeated selected poles
have explicit, recorded original-pencil Schur/nullspace recovery. Close-pole
pairing uses the union of independently checked left bases; each proposed
vector must still satisfy its own original equation. The selected mass-pairing
matrix is measured separately. General defective chains remain unsupported.

An independent analytic test exposed a mistake in the first close-pole pairing
implementation, which used only the first pole's basis. The correction retains
all member bases; the same test and accuracy gates then pass. Both attempts
are retained. No custom mechanical condensation or relaxed weak-inertia
classification was promoted.

The implementation is in [modal_arnoldi.py](../../openswing/modal_arnoldi.py)
and [linear_dynamics.py](../../openswing/linear_dynamics.py). Exact historical
ASWING balancing and Arnoldi settings remain unknown. The pinned ARPACK-NG
reference retains its upstream license and is included in source packaging;
runtime execution continues through SciPy's ARPACK interface.

## Unchanged original ST-4 model

Four fresh native runs use the original `7a_b17.asw`, declared fixed vacuum
frame, unloaded zero-gravity base, uniform mesh with its original point-mass
anchor, and the archived request for 16 roots near `-0.1 + 300i`. All physical
properties and numerical accuracy gates are unchanged. Each run passes its
base, original-pencil, selected-root and mass-normalization checks.

| Nominal intervals | Actual intervals | Solve including assembly, s | Six ordinal frequency differences from ASWING |
|---:|---:|---:|---|
| 16 | 17 | 6.96 | +0.0498% to +1.5110% |
| 32 | 33 | 13.52 | −0.0011% to +0.0944% |
| 64 | 65 | 13.71 | −0.2782% to −0.0092% |
| 128 | 129 | 134.26 | −0.3698% to −0.0178% |

Timings are observations on this host, not controlled performance benchmarks;
the 128-interval run overlapped other tests. The first six ascending positive
roots in the selected set are compared to the six archived ordinals. This does
not certify that the selected roots are globally lowest or reconstruct the
archive's unavailable mode shapes and complete spectrum.

The original **32-to-64 mesh gate fails three of six frequencies**. A separately
declared 128-interval extension then passes the same 0.1% gate from 64 to 128:
changes range from 0.00338% to 0.09192%. The original failure remains recorded;
the extension does not relabel it. All six finest-grid frequencies still differ
from the archive's printed precision. The closer intermediate-grid match is
not a reason to tune the mesh to the reference.

Historical mesh, gravity/startup state and vacuum-toggle settings remain
qualified. Consequently **no new archived-ASWING case is marked complete**.
Experiment matching is not a requirement for this comparison.

## Verification and browser delivery

The final focused Python run passes 69 tests, with the two existing strict
expected failures retained for the separate dense weak-inertia reduction.
Thirteen new analytic tests cover constrained reactions, time/coordinate
changes, weak inertia, numerical zero modes, repeated and nearby distinct
poles, and explicit fallback. Twenty-one JavaScript project/policy checks pass.
The coupled heave/pitch native check also returns the expected eight selected
roots, including the unstable pair `0.77290818 +/- 32.44995145i`.

The nominal 32-interval case passes **836 offline browser checks**. Startup
takes 14.06 s and the solve 12.27 s. Native/browser agreement covers the full
base, all 749,088 A/M entries, all 16 selected roots, original left/right
equations and independently measured mass pairing. No external or offline HTTP
requests occur during the solve. New projects reopen byte-for-byte; three
older source-vacuum, damped-vacuum and midpoint projects restore their original
results and solver choices without recomputation. Desktop and mobile rendering
are checked.

Three additional UI regression checks pass across isolated runs: geometry and
coupled modes in one run, and vacuum/dense/reduced-method compatibility in a
fresh run. Test fixes select visible mobile workspaces and count the current
red surface palette at a fixed animation phase. Earlier failures and the
combined runner's global timeout remain in the evidence; the combined suite
is not reported as having completed.

The [machine report](aswing-modal-integration.json) and
[evidence archive](aswing-modal-integration-20261026-evidence.zip) retain source
pins, actual requests, results, failed tests and mesh checks. The original
[dense comparison](isae-st4-source-modes.md) and
[rank diagnosis](isae-st4-rank-diagnostic.md) remain historical evidence.

Remaining work includes resolving historical ST-4 discretization/settings,
broader modal comparisons, moving-frame and circulatory source dynamics,
source-consistent Bode/time integration and pointwise damped-strain recovery.
