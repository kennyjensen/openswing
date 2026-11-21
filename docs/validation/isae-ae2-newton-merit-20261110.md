# AE-2: Newton direction, stall curvature and line-search experiment

Observed 2026-11-10 UTC. The approximate Newton matrix is **not the main cause
of damping at the sampled difficult state**: lagged and complete-geometry
matrices produce directions differing by only **2.353e−8 relative**. A separate
correction-norm line-search experiment halves the final control step's iteration
count, but **does not complete the 20 m/s case**. Production remains unchanged.
The primary current score remains **548/2,200**; these diagnostics add no votes.

| Check | Result |
|---|---|
| Nominal-80, 20 m/s, saved 87.5% boundary | Restored against original source and full physical residual |
| Lagged versus full Newton direction | Relative difference 2.353e−8; maximum coordinate difference 1.330e−8 |
| Central directional derivative check | Lagged 0.144245%; complete 0.144227% relative norm error |
| Full-step squared-residual increase | 7,569.825 times the starting value; both matrices accept only 1/16 under the original merit |
| Circulation share of full-step squared residual | 99.98861% |
| 19 m/s final-step control, correction merit | 13 iterations versus 26 original; 20 physical/parity checks pass |
| 20 m/s correction-merit attempt | Full load and 96.875% attempts reject; 92.1875% boundary saved, then supervisor timeout |
| Independent partial-state verification | Fresh residual 4.207e−14 at 92.1875%; no full-load solution |

![Newton direction and merit diagnostics](../../artifacts/isae/ae2-correction-merit-20261110/comparison.png)

The right-hand green star is the independently verified partial load boundary;
it is not a completed 20 m/s solution.

## What the direction comparison establishes

Both diagnostics start at exactly the same normalized coordinates from the
original nominal-80, 20 m/s checkpoint. The requested full-load residual is also
identical. Each process assembles and factors only its own matrix. The lagged
matrix uses the existing structural/circulation block solve; the complete matrix
uses the existing exact beam elimination. Original-equation linear solve defects
are below 1.83e−15. Neither matrix is promoted to a new default.

Central directional differences use three perturbation sizes, 1e−4, 1e−5 and
1e−6, independent of matrix assembly. Their approximately 0.144% mismatch is
retained, mainly in the balance rows; this is not an assertion of an exact full
Jacobian or a complete derivative validation. It is far too similar between
methods to explain the large difference between the infinitesimal and full-step
merits. This comparison concerns one original frozen-influence case and state.

At the full Newton step, the squared physical residual grows by roughly 7,570
while the squared remaining correction, computed with the same fixed matrix,
falls to **0.26735** of its initial value. With the original squared-residual
criterion, the first accepted fraction is **1/16**. This distinction motivates
a globalization experiment; it does not authorize accepting an unconverged
physical solution.

## Section-level explanation

Seven points along the same original direction are evaluated without changing
any input. Each section's circulation residual is reconstructed from control-point
normal velocity minus the documented stall leakage. The literal log-add-exp form
of Drela's **Eq. 204** independently reproduces the production stable evaluation
for all **567 section samples**. No lift-limit, stall-strength or width adjustment
is made.

The original section limits are ±1.1. At the boundary, 28 of 81 sections exceed
the upper limit and the largest section coefficient is 1.11975. At the full trial,
48 exceed it and the maximum is 1.23036. The largest circulation defect occurs
near t=0.52506 m, where normalized tangency is 0.36791 and stall leakage is
0.87838. The resulting −0.51047 residual dominates the full-step merit. Local
perpendicular speeds remain 18.56–23.14 m/s; the observed issue is not a velocity
singularity. Reproducing this local formula does not validate every aerodynamic
force derivative or establish the archived equilibrium branch.

## A bounded numerical experiment, not a production change

The experimental function is an explicit saved copy of production `equilibrate`
with exactly two merit-selection replacements. It applies to nonhinged cases
the correction-norm criterion already used in the hinged route:

`merit = ||J_current^{-1} R(trial)||²`.

The matrix remains fixed throughout each line search. All physical equations,
source inputs, structural and circulation coupling, geometry bounds, rank gates,
load refinement, matrix-refresh rules and final residual target remain. The
existing finite-iteration limits also remain. The original function and generated
variant are independently compared by the saved-only audit. This criterion is
not claimed to be a documented ASWING default.

The 19 m/s control starts at the original 75% boundary. Its final load step takes
**13 iterations, two damped**, compared with **26 iterations, eighteen damped**.
It passes the original eighteen physical checks and two prior-result agreement
checks. Maximum normalized-coordinate difference is **8.737e−13**; the largest
sensor-channel difference is **2.457e−11** degrees. Fresh full-load residual is
**8.646e−14**. This supports that completed control, not a whole cold-start or
browser speedup.

The 20 m/s experiment starts at 87.5%. It rejects full load and 96.875% before
converging at **92.1875%** after 36 recorded iterations across those attempts.
It writes an explicitly pending result, then reaches the 30.082-second supervisor
deadline before completing its reporting/checksum phase. The terminal receipt
remains **SIGKILL, supervisor timeout**; it is not reclassified as a successful
process. A separate bounded job restores the packet through production identity,
checksum and physical-boundary checks and obtains **4.207e−14** fresh residual.
This verifies only the partial boundary of the disclosed numerical variant.
It supplies no full-load sensor prediction, original-suite pass or production
continuation result. The failed original attempt and the new timeout remain.

All five supervised numerical processes are reaped: four exit zero and one times
out. Peak use is **151.5 MiB** and **10.278 CPU seconds**, within the original
one-thread, 512 MiB, 15 CPU-second limits. The independent partial verification
also exits zero. Diagnostic worker alarms remain 25 seconds after setup and
outer deadlines 30 seconds. UTC elapsed intervals and monotonic process times
are not interchangeable on this device; no whole-run speed benchmark is claimed.

## Source alignment and next work

The authoritative index and checksummed catalog were consulted; Jan Part IV and
Drela steady PDF/text checksums match. Jan **Part IV §3.2, pp. 8–12, Figure 3**
remains the native AE-2 target. Drela **§4.6, Eq. 176, p. 36** supports lagging
nonlocal influence geometry while retaining circulation coupling. **§5.7,
Eq. 204, pp. 40–42** supplies the section stall law. The original frozen-influence
setup helps explain why the two assembled directions nearly coincide.

The control improvement is insufficient to change the default: the difficult
case remains incomplete, and complete cold-start, other-layup and other-incidence
controls have not been run with the variant. A continuation-path/conditioning
audit can use the two verified boundaries, but their existence does not establish
a fold, uniqueness, dynamic stability or an error in archived ASWING results.

Next: resume the remaining original incidence sweeps, beginning with the 7°
sweeps where supplied, using the unchanged production solver and small serial
jobs. Keep the high-speed branch discrepancy and this line-search candidate
separate. Browser/build tests remain held; the full project is incomplete.

[Saved audit](../../artifacts/isae/ae2-correction-merit-20261110/assessment.json) ·
[Direction plan](../../artifacts/isae/ae2-newton-directions-20261110/plan.json) ·
[Section report](../../artifacts/isae/ae2-newton-sections-20261110/report.json) ·
[Experimental plan and exact replacements](../../artifacts/isae/ae2-correction-merit-20261110/plan.json) ·
[Independent partial-boundary verification](../../artifacts/isae/ae2-correction-merit-20261110/pending-verification.json)
