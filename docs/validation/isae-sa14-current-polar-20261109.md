# SA-14: complete current CL-table refresh

Current OpenSwing matches **281/360 original archived CL values at 5%**.
All 360 planned comparisons were attempted serially. The same current results
give **277/360 at 3%**, compared with the historical 115/360 at 3%.
Only four added passes come from changing the current allowance from 3% to 5%.
The historical-to-current change also includes settings and implementation
changes since that old run; it is not evidence of a new production physics fix
in this refresh.

This completes the registered global-CL table refresh, not SA-14 validation.
The archive contains 128 finite CL values with its convergence flag off.
They retain their existing comparison slots and are explicitly distinguished
below. Historical node placement, startup state and local-load agreement
remain unresolved. SA-13 remains open, as the user requested when confirming
the move to SA-14.

## Results

| Original configuration | Within 5% / required | Numerically valid OpenSwing states | Remaining failures |
|---|---:|---:|---|
| Finite wing/body | 89/120 | 97/120 | Eight low-angle CL mismatches; 23 local-Mach rejections |
| Wing/constant “infinite” body | 95/120 | 97/120 | Two strict near-zero mismatches; 23 local-Mach rejections |
| Wing only | 97/120 | 97/120 | 23 local-Mach rejections |
| Total | **281/360** | **291/360** | **79 retained failures** |

Diagnostic subsets reuse those same slots and are not added to the total:

| Archive classification | Within 5% / required | Numerically valid OpenSwing states |
|---|---:|---:|
| Native convergence flag on | 188/232 | 198/232 |
| Native convergence flag off | 93/128 | 93/128 |
| Native stall flag off | 164/174 | 174/174 |
| Native stall flag on | 117/186 | 117/186 |

Agreement with the 93 unconverged archived numbers is not a claim of matching
converged native solutions. All original values and flags remain in the plan.
No unavailable row was removed or filled with a prediction.

## Remaining discrepancies

**Finite-body offset:** both meshes fail CL at 0°, 0.5°, 1° and 1.5°. Failed
relative errors have a median of 17.86%; the maximum is 2395.72%, dominated by
the small zero-angle reference. The absolute CL errors are 0.00667–0.00869.
At zero angle, OpenSwing predicts −0.00905687/−0.00898616, versus archived
−0.000362896. At 0.5°, errors are about 24.5%; at 1°, 11.2%; at 1.5°, 6.8%.
The finite-body comparisons pass from 2° onward whenever the current state is
numerically valid. The zero-angle offset persists under the tested refinement.

This reinforces the [six-point force audit](isae-sa14-body-pilot-20261109.md):
at 5°, the small finite-body increment has the opposite sign to the archive
even though total CL passes. The body load is included correctly. The next
investigation should isolate the finite body's volume-induced flow, radius
interpolation and original local-load conventions, without fitting the offset.

**Strict near-zero output:** the constant-body model predicts exactly zero CL
at zero angle; its archived value is 7.98535e−10. Both mesh comparisons fail
the existing printed-precision rule for tiny references. This is a 100%
relative error with an absolute difference below 8e−10, and is distinct from
the finite-body offset. The near-zero rule was not relaxed.

**High-angle validity:** all 69 numerical rejections occur at N128, from 18.5°
through 31°, on rows marked stalled by the archive. The section-normal Mach
reaches unity at the outer wing station, making the current section moment
correction undefined. For the first finite-body rejection, M_perp is 1.01549
at t=−1.615318 m; the strongest grouped wake contribution is 269.22 m/s from
a ray 0.0003649 m away. Circulation residual is already 1.50e−14. This is not
an unconverged circulation iteration or a resource timeout. The same pattern
on wing-only shows that it is not specific to the body. These failures remain
open; no post-stall or local-Mach workaround was introduced.

## Setup, numerical checks and runtime

The [source audit](isae-sa14-sources.md), authoritative reference catalog,
ISAE Part I §6.3 and the original models/drivers/tables govern the comparison.
The [startup audit](isae-sa14-default-setup-20261109.md) reconstructs frozen
influences and speed-derived PG Mach from the documented defaults and original
driver commands. Speed is 70 m/s, density 1.2256 kg/m³, PG Mach 0.20575527,
with 64/128 nominal lifting intervals and current natural-v1 interpolation.
This remains a declared reconstruction of unrecorded historical settings.

Every successful state passes the existing eleven numerical/force checks.
The independent summary reads the original table tokens, verifies every saved
result checksum, and recomputes the 5% acceptance with Decimal arithmetic and
the unchanged tiny-reference rule. Errors and rejected states cannot pass.
All 141 production modules are unchanged during this refresh.

Sixty foreground invocations each executed six cold solves serially, with one
BLAS thread and a 512 MiB address-space / 15 CPU-second / 25 wall-second process
limit. No invocation reached those limits. Peak RSS was at most 238,260 KiB.
Individual solve plus report times after imports ranged from 0.065 to 0.606 s,
with median 0.214 s and sum 80.08 s. Whole-process overhead and source checking
are additional. No background solver, browser, Vite test or build was started.

## Reproduction and retained evidence

[Pinned full plan](../../artifacts/isae/sa14-current-polar-20261109/plan.json),
[all results and summary](../../artifacts/isae/sa14-current-polar-20261109/analysis.json),
[failure and tolerance details](../../artifacts/isae/sa14-current-polar-20261109/comparison-details.json).
Each job directory retains strict and 5% results, timing/checksums and, when
available, the full public force ledger. Earlier artifacts are unchanged.

`scripts/verify_sa14_polar.py` has `prepare`, `batch` and `summary` actions.
Each `batch --start N --count 6` invocation runs sequentially under the limits;
starts range from 0 to 354 in steps of six. The caller sets
`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1` and uses the project
virtual environment. Completed results may be resumed only after checksum
verification; incomplete directories require inspection. Summary requires
every registered job. Use a fresh output directory for a new pinned run.
