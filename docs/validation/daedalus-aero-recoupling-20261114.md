# Daedalus: converged aerodynamic refinement on the original structure

Fully coupling the **164-panel aerodynamics** to the original structural
mesh at **1.5 Hz** changes roll amplitude by **−5.4316%**, compared with
**−5.4595% after one correction**. The additional feedback changes the complex
roll response by only **0.0394% of its original amplitude**. The full modified
harmonic equations converge, and repeating the final differentiation with a
different step confirms the result.

Thus, omitted repeated aerodynamic feedback does not explain the much larger
**−15.9151% roll-amplitude change** from refining the entire aircraft and
retrimming. Structural discretization and the changed loaded equilibrium
remain to be separated. The published yaw dip is still unmatched.

![Recoupled aerodynamic refinement and full-equation convergence](../../artifacts/daedalus-aero-recoupling-20261114/report/aero-recoupling.png)

## Scope and equations

This continues the [first-variation study](daedalus-roll-aero-20261114.md).
The literal `dae.asw`, 6.7 m/s operating point, original structural mesh,
steady geometry, controls and physical parameters remain fixed. The fine
aerodynamic grid samples the same structural interpolants, with live vortex
influence, circulation lag, plume and complete moving-arm load transfer.
The **oscillatory aircraft motion is now updated**, rather than prescribed
from the original response.

The fine mean aerodynamic loads differ from the coarse loads. As in the
first-variation calculation, a constant residual offset holds the original
equilibrium. This defines a conditional comparison, not a physically retrimmed
fine-grid aircraft or a proposed physical preload. All repeated feedback in
the resulting **linear harmonic problem** is included; this is not a nonlinear
finite-amplitude time response.

The [authoritative index](aswing-authoritative-references.md), its source
catalog, and the already reviewed steady and unsteady equations govern this
comparison. The steady description's Eqs. 150–161 define the sampled vortex
system; the unsteady description's Eqs. 33–49 define circulation and loads.
Its Eqs. 135–136 give the harmonic state and output equations.

Write `K0 = i*omega*M0 - A0`. At each candidate full state `z`, solve the
fine circulation equations for that motion and the unit F3 input. Let
`DeltaL(z,1)` be the resulting fine-minus-coarse external load derivative,
including nodal and global force/moment rows. Then evaluate and correct

```text
r(z) = K0*z - B0 - DeltaL(z,1)
K0 * correction = -r(z)
z_next = z + correction
```

The original descriptor is a preconditioner for the **complete modified
equations**. Its 82 coarse circulation variables remain auxiliary variables
with their original circulation constraints. Their coarse load contribution
is canceled by `DeltaL`; the actual loads use the separately solved 164-panel
circulation. No motion, equation or aerodynamic mode is discarded.

Each correction uses exact beam/velocity elimination: the factorization has
748 equations, and the complete 2,044-coordinate state is recovered and
checked. The base record's `structural_coordinates` field counts this entire
original descriptor, including auxiliary circulation and frame variables;
it does not mean 2,044 purely structural degrees of freedom. The original
full matrices and source equations are unchanged.

## Response comparison

These are signed **amplitude changes relative to the original response**.
The last column is the previously computed 211-node / 164-panel aircraft
with its own trim. It changes more than the aerodynamic mesh.

| Output | One correction | Converged fixed-equilibrium coupling | Whole mesh + retrim |
| --- | ---: | ---: | ---: |
| Yaw rate | +0.62281% | +0.62109% | +0.10561% |
| Roll rate | −5.45945% | −5.43161% | −15.91514% |
| Sideslip | +0.33202% | +0.33003% | −0.25803% |
| Bank | −4.39235% | −4.37841% | −13.63539% |

The converged amplitudes are **0.09490204 deg/s/F3** yaw,
**0.01082969 deg/s/F3** roll, **0.02443411 deg/F3** sideslip and
**0.001073598 deg/F3** bank. Relative to the original amplitudes, the complex
changes after the first correction are only **0.00337%, 0.03937%, 0.00303%
and 0.04392%**, respectively.

The preceding study reported the roll **amplitude derivative** as −5.4740%.
The amplitude of its extrapolated complex response is −5.4595%; the small
difference comes from taking a complex magnitude. The subsequent shift to
−5.4316% comes from repeated coupling. The bank derivative, −4.4987%, must
likewise be distinguished from its −4.3924% one-correction amplitude change.

The remaining **10.4835 percentage-point roll difference** between this
conditional model and the complete refinement is not an exact structural
contribution. The full refinement also changes the steady loaded state, body
discretization and aerodynamic geometry. This calculation closes the repeated
feedback qualification at 164 panels; it does not establish grid convergence
or native ASWING agreement.

## Convergence and independent checks

Acceptance requires maximum full residual below **2e−11**, relative residual
below **2e−8**, and every output's next relative complex correction below
**2e−7**. The thresholds were retained when iteration 3 narrowly missed the
output criterion.

| Corrections already applied | Maximum full residual | Largest next relative output correction |
| --- | ---: | ---: |
| 0 | 9.744e−7 | 6.369e−2 |
| 1 | 7.382e−9 | 4.667e−4 |
| 2 | 9.728e−11 | 1.235e−5 |
| 3 | 2.169e−12 | 2.558e−7 |
| **4 — accepted** | **1.759e−13** | **5.065e−9** |

The accepted relative full residual is **9.547e−12**. The reported response
is the state after four corrections, whose fine circulation and modified
residual were actually evaluated. A fifth correction is computed only to
measure what remains.

Fourth-order derivatives use step **5e−4**. The accepted state is independently
reevaluated with step **1e−3**, including a new fine circulation solve and new
coarse/fine load derivatives. That check also passes all convergence gates.

| Verification | Largest difference or residual |
| --- | ---: |
| First load correction versus prior component calculation | 1.093e−13 in scaled residual units |
| First corrected state versus prior full-matrix solve | 3.328e−11 in scaled state units |
| 48 transferred coarse loads versus native network evaluations | 8.327e−17 in scaled residual units |
| Total force/moment transfer closure | 1.648e−12 in the relevant physical units |
| Fine harmonic circulation equation | 1.224e−16 |
| Auxiliary coarse circulation equation | 2.917e−17 |
| Complete coarse/fine circulation directional probes | 2.074e−11 |
| Final load correction change between derivative steps | 2.177e−13 in scaled residual units |
| Final fine circulation change between steps | 1.264e−9 relative |
| Next output correction change between steps | 3.541e−9 relative |

The exact structured solve retains the full-pencil reciprocal condition
estimate **2.110388e−8** and the original numerical acceptance gates. It is
not a modal approximation or a fit to the reference drawing.

## Execution and evidence

There are **37 terminal jobs: 36 successful and one unsuccessful**, all
reaped. The initial `update-0-fine` stopped with an OpenBLAS allocation error
under the 512 MiB address-space limit. Its files are retained. The replacement
`update-0-fine-v2` uses the existing exact beam/velocity elimination and
replays the prior uneliminated solution before further iterations.

Every numerical child uses one BLAS thread with limits of **512 MiB address
space, 15 CPU seconds and 25 wall seconds**. Maximum recorded use is
**4.263 CPU seconds, 17.917 wall seconds and 133.204 MiB resident memory**.
No cap was increased. Later job groups ran under a foreground serial
subprocess driver; each numerical child kept its individual supervisor and
limits. All parent sessions are closed. Browser/build jobs remain held.

The [calculation driver](../../scripts/check_daedalus_aero_recoupling.py)
stores immutable input plans, runners, states and terminal receipts, one
fresh tag at a time. The accepted state and checks are in
[update-4-fine](../../artifacts/daedalus-aero-recoupling-20261114/update-4-fine/result.json),
with the independent step check in
[update-4-wide](../../artifacts/daedalus-aero-recoupling-20261114/update-4-wide/result.json).
The [report driver](../../scripts/report_daedalus_aero_recoupling.py) produces
the [complete results](../../artifacts/daedalus-aero-recoupling-20261114/report/result.json),
[CSV](../../artifacts/daedalus-aero-recoupling-20261114/report/comparison.csv)
and plot. A [verification receipt](../../artifacts/daedalus-aero-recoupling-20261114/verification.json)
checks the archived jobs and unchanged production files.

No production physics, aircraft parameter, ISAE fraction or comparison scope
changed. The next investigation should separate structural discretization
from the changed loaded equilibrium using the existing coarse/fine cases,
while retaining the unresolved native yaw comparison.
