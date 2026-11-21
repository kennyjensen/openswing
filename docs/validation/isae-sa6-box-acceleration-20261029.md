# SA-6 source-box acceleration response

Updated 2026-10-29. SA-1 remains paused. No complete ISAE family passes.

The documented endpoint-load rule is now shared between the source still-air
modal loads and a rigid acceleration-response report. The report evaluates the
actual endpoint frames and positions, uses the source operator's unloaded
interval lengths, and preserves nonsymmetry for varying section properties.
It is explicitly separate from the legacy symmetric apparent-mass tensor.

For constant straight sections, this rule equals an arithmetic-midpoint mass
operator. For varying chord, physical twist or axis offset, evaluating one
midpoint section is generally different from averaging completed endpoint
forces and couples. The [source derivation](../../artifacts/isae/apparent-inertia-box-20261029/source-review.json)
records steady Eqs. 55–56, unsteady Eq. 266, the constant-section proof, and
the general nonsymmetric expression. The inconsistency between printed
unsteady Eqs. 266 and 267 remains qualified; the latter is not used to override
the preceding balance equation.

For endpoint operators K0/K1 and rigid acceleration maps H0/H1, the interval
response is `length/2 * Hmid.T @ (K0 @ H0 + K1 @ H1)`. The applied reaction is
the negative of this matrix times the six reference accelerations. No
symmetrization, apparent center of mass, fitted parameter, or real-mass
finite-segment correction is introduced.

## SA-6 comparison

The [separate diagnostic](../../artifacts/isae/apparent-inertia-box-20261029/sa6/comparison.json)
retains all four original models, eleven archived control states, and both
previously declared meshes. The 64/128 nominal meshes have 66/130 intervals
after required control-table boundaries are inserted. There is no search for
the historical mesh or selection based on agreement.

Eight model/mesh operators cover 1,584 apparent-mass/inertia comparison slots
(18 entries × 44 original files × two meshes). The mass coefficients do not
depend on control deflection, so each operator is reused across those states.
No real-mass target is added to this diagnostic. Every original decimal target,
tiny nonzero entry, and half-printed-unit tolerance is retained.

| Nominal intervals | Legacy apparent checks | Source-box apparent checks | Typical failed Ixx error | Typical failed Ixz error | Typical failed Izz error |
|---|---:|---:|---:|---:|---:|
| 64 | 220/792 | 308/792 | 0.0644% | All 44 origin checks pass | 0.0447% |
| 128 | 220/792 | 220/792 | 0.0941% | 0.0444% | 0.0744% |

Percentages are median absolute relative errors among failed entries. The
origin and archived centroid-coordinate results are identical here. Source-box
total is **528/1,584**, compared with **440/1,584** for legacy apparent entries.
The 88 additional matches are coarse-mesh Ixz at both reported references;
the finer mesh does not pass those targets. No complete row matches.
The finer-mesh legacy Ixx/Ixz/Izz errors are 0.1091% / 0.0594% / 0.0894%.
Improvement therefore does not establish historical exporter agreement.

This diagnostic leaves the registered **1,760/2,904** mass scope and static
**88/528** scope unchanged. The registered count includes real-mass zeros and
must not be combined with this apparent-only diagnostic. The static rolling
and yawing discrepancies remain independent of these acceleration terms.

## Verification and scope

The 27 new operator tests cover independent endpoint impulses, constant-strip
midpoint energy, varying-section nonsymmetry, frame/reference covariance,
broadcasting and invalid inputs. All 55 source/legacy still-air integration
tests pass, including five new report/physical-load tests. Those tests apply
all six rigid accelerations to the actual wet and dry structural residuals
at straight and deformed geometry and compare their load difference to the
reported operator. Existing source scalar modal-spectrum tests still pass.

The SA-6 comparison also independently evaluates all six endpoint force/couple
impulses per operator; maximum matrix difference is 5.83e-18. It performs no
aerodynamic or nonlinear solves. The packaged WASM check reproduces all
**288 matrix entries in eight cases exactly** in this runtime. The browser
build passes and all 130 packaged kernel modules match the source.
Native calculation, [WASM evidence](../../artifacts/isae/apparent-inertia-box-20261029/wasm.json),
build and execution receipts are retained in the
[artifact directory](../../artifacts/isae/apparent-inertia-box-20261029/).

The new response report is available through
`SourceQuiescentNetwork.rigid_acceleration_report(meshes, reference)` and the
normal still-air fluid report. The existing source still-air policy remains
limited to stationary fixed-frame modes. This change does not enable moving
frame/fluid nonlinear dynamics, replace the default flowing-air solver, or
claim the original ASWING exporter used this sampling.

The remaining steady-force and yaw-moment discrepancies require investigation
of their own aerodynamic equations and force/moment integration. Choosing the
coarser mesh because one inertia entry passes would not resolve them.

```sh
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/compare-sa6-box-acceleration.py \
  --output-dir /tmp/sa6-box-acceleration
```
