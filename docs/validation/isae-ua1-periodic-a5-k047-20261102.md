# UA-1: nonlinear periodic heave at 5°, k=0.47

Updated 2026-11-02. This additional physical condition **passes overall**, with
**14/14 accuracy and refinement gates passing**. It uses the published UA-1 mean-incidence and
frequency labels, with peak-to-peak A/c=0.5. The existing
linear source-curve comparison remains separate. This study checks the full
nonlinear attached-flow response against independently integrated section
equations; it is not native ASWING executable output.

| Quantity | 160 steps/cycle: periodic error | 320 steps/cycle: periodic error | Fine limit |
|---|---:|---:|---:|
| Lift | 0.08016% | 0.02058% | 0.1% |
| Circulation | 0.10588% | 0.02837% | 0.1% |
| Circulation rate | 0.04682% | 0.01196% | 0.1% |

Fine full cold-history errors are **0.01761% / 0.02373% / 0.01653%** for lift, circulation and rate.
Errors use oscillatory variation: the cold history is measured from the
pre-motion steady value, and the periodic lift/circulation from their periodic
means. Rate uses its reference peak. Every strip participates; no strip average
or nonzero mean can hide an error. All three cold and periodic limits remain
0.1%. The provisional SA 3% policy does not apply.

The fine/coarse error ratios range from **0.24942 to 0.26793**;
each must be below 0.35. Fundamental lift-amplitude error is
**-0.01650%** and phase
error is **+0.00496°**. Mean lift
error is **-0.001530%** of dynamic lift.
The maximum final cycle-to-cycle change is
**0.000000%**, against 0.01%.
Maximum residual over both grids is
**9.9753e-11**.

| Gate | Result |
|---|---|
| cold_CL | Pass |
| periodic_CL | Pass |
| last_cycle_change_CL | Pass |
| cold_circulation | Pass |
| periodic_circulation | Pass |
| last_cycle_change_circulation | Pass |
| cold_circulation_rate | Pass |
| periodic_circulation_rate | Pass |
| last_cycle_change_circulation_rate | Pass |
| refinement | Pass |
| amplitude | Pass |
| phase | Pass |
| mean | Pass |
| residual | Pass |

## Physical setup and independent reference

The rigid unit-chord rectangular model has AR200000 and four circulation
unknowns. Mean speed is 10, Mach is zero, gravity is zero, and
stall is disabled. Heave follows the fixed mean-freestream normal, including
the corresponding body-X and body-Z accelerations. Lift is projected onto that
same fixed normal and normalized by the fixed mean dynamic pressure.

Both production histories start from their own steady equilibrium and continue
for eight cycles. The complete acceleration table is supplied before startup.
No reference circulation or periodic initial condition initializes production.
The reference uses one-period integrating-factor quadrature plus the exact
homogeneous transient from the steady initial circulation. Independent direct
DOP853 and Radau integrations cover the entire cold history. Their largest
normalized disagreement is **3.3010e-11**, below 1e-9. A separate 512-interval
quadrature changes the mean and first three lift amplitudes by at most
**1.1102e-16**.

The general setup reproduces the previous 9°, k=.94 request and reference
exactly. The new tests also check changed physical parameters, transient
continuity and detection of a discrepancy confined to one strip. An initial
setup test's bitwise endpoint-clock assertion was corrected to the already
declared 1e-12 clock tolerance; no physical acceptance limit changed.

## Continuation and retained evidence

There are 48 retained segments of 80 steps each, all run
serially with a 45-second cap per numerical subprocess and one BLAS thread.
Every complete snapshot is retained. Separate bounded readers audit all
**3,842 unique states** on both grids, including exact force, frame-motion,
circulation and rate joins, integration order, endpoint BDF coefficients,
accepted predecessors, full forcing cutoff and source hashes.

The original second-segment verifier rejected two internal moments that changed
by one ULP when restored from physical units into solver-scaled units and then
recaptured. A separate two-step reproduction retained the complete result and
isolated those fields; all compared aerodynamic and frame outputs were exact.
The corrected verifier allows at most four ULPs only in dimensional internal
force, internal moment and reaction fields. All remaining restart-state fields
remain exact. Deliberately changing circulation by one ULP or an internal moment
by sixteen ULPs fails its tests. The complete audit observes a maximum of
**2 ULPs** in the allowed fields. This is validation-tool rounding
handling, not a solver or physical-accuracy relaxation.

The failed pilot and its frozen source remain intact. Its successful initial
segment is reused byte for byte after checking identical physical requests and
all 136 production-module hashes. No solve is repeated for that retained
segment. The failed second segment's output was not published before the old
assertion; the resumed study computes that interval and the remaining history.
All accepted segments converge without rejected integration steps. 16
focused tests pass. The final report retains all source and input hashes.

The first full-history reader also incorrectly treated the duplicate initial
record of a resumed segment as a newly integrated step. Its display order is
zero, while its accepted-method record preserves BDF2. The original audit
failure remains recorded. The corrected reader checks both physical BDF
predecessors and the first continued step's coefficients at all
**46 boundaries**, then excludes only the already
checked duplicate from new-step order assertions. Five targeted tests cover
valid continuation and reject lost history, an Euler restart, altered
circulation and incorrect coefficients.
This reassessment reads the retained trajectories and performs no new solve.

## Remaining scope

This adds one physical condition and its temporal-refinement evidence. It does
not add spatial convergence, stall, a browser run of this condition or native
ASWING agreement. The earlier 9°, k=.94 browser and temporal studies retain
their own counts and qualifications. Other frequency/incidence/amplitude
combinations and UA-2 native-reference provenance remain open. Neither UA
family nor the full project is complete.

Evidence: [machine report](isae-ua1-periodic-a5-k047-20261102.json),
[plan](../../artifacts/isae/ua1-periodic-grid-20261102/a5-k047-A05-r1/plan.json),
[full-history audit](../../artifacts/isae/ua1-periodic-grid-20261102/a5-k047-A05-r1/audit.json),
[parameterized study](../../scripts/isae_ua1_periodic_study.py),
[corrected history reader](../../scripts/audit-isae-ua1-periodic-study.py),
[serial runner](../../scripts/run-isae-ua1-periodic-study.py).
