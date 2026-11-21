# Daedalus: current aircraft force and angular-momentum balance

The current source-equation/SEGSPL model's force and moment balances agree
with an independent construction along its rudder responses at **0.2 Hz and
1.157378 Hz**. The largest difference from the saved matrix action is
**8.958e−12** in normalized residual units. No missing brace-anchor reaction,
duplicated external moment, or incorrect nodal load transfer was found.
**The Bode gap remains 0.074218 versus 0.033986 deg/s/F3 at the dip.** No
production equation, aircraft parameter or completion fraction changed.

![Independent yaw-moment balance](../../artifacts/daedalus-source-balance-20261114/report/yaw-balance.png)

The displayed moments include aerodynamic, real-inertia and gravity terms
about the fixed model moment reference. They are components of the supplied
coupled response, not independently excited aircraft responses. Their sum
vanishes because the free-flight equations require external load plus inertial
reaction to balance. A small direct boom moment does not imply that boom
compliance is unimportant: it changes tail motion and therefore tail loads.

## Independent construction

The [authoritative steady description](../../reference/aswing-authoritative-20261108/drela-aswing-steady.pdf),
printed pp. 13–14 and 37–38, supplies conservative beam force/moment balance
in Eqs. 55–56 and whole-aircraft balances in Eqs. 179 and 188. It explicitly
excludes net strut force from the whole-aircraft sum because the attached
anchor carries the opposite force. Joint loads also cancel. The
[unsteady description](../../reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf),
Eqs. 9–16, 23/27 and 37–40, supplies frame kinematics, gravity orientation and
absolute centroid acceleration/inertial moments.

The reference imports no production physics. It reconstructs physical node
and flight-frame motion directly from the raw descriptor amplitudes, including
the ASWING bank/elevation/heading convention. It computes aerodynamic loads
using the [independently checked current evaluator](daedalus-circulation-phase-20261114.md),
then transfers lifting, body, point-drag and engine wrenches to their nodes.
Real mass uses the declared endpoint product averaging and symmetric source
transfer, including the finite-segment rotary term exactly once. Point masses
retain their moving pylon arms. The complete weight is **233.3019332 lb**.

Beam internal resultants, rigid-joint reactions and live bilateral braces are
assembled independently. Beam and joint global wrenches cancel internally.
Brace endpoint loads cancel with their fixed-anchor reactions; the ground
reaction and anchor balance is checked separately. No second aggregate
aircraft inertia is added to the six free-flight equations.

Fresh native captures use the current loaded state and saved full-matrix
response. Fourth-order stencils at widths 1e−3 and 5e−4 provide comparison
targets, without recomputing trim or harmonic responses. The independent
aerodynamic calculation uses complex steps 1e−24 and 1e−20. A separate
derivative check of the composed Earth rotation verifies the reference's
Euler-rate matrix.

## Coverage and results

| Equations checked independently | Rows per frequency |
| --- | ---: |
| Nodal force and moment balance | 648 |
| Rigid ground/joint constraints | 30 |
| Circulation | 82 |
| Whole-aircraft force and moment balance | 6 |
| Node and flight-frame kinematics | 660 |
| **Total checked** | **1,426** |
| **Beam constitutive/compatibility equations excluded** | **618** |

The full descriptor has 2,044 rows. This study does **not** independently
evaluate the remaining strain/curvature equations or predict the aircraft
motion from scratch. Internal resultants, reactions and motion are supplied
from the accepted solution. Checking their equilibrium does not validate the
stiffness equations that determined them.

| Check across both frequencies | Largest absolute difference |
| --- | ---: |
| External nodal force versus native stencils | 8.917e−11 lb/F3 |
| External nodal couple versus native stencils | 2.161e−10 lb ft/F3 |
| Checked residual rows versus native stencils | 1.702e−11 normalized |
| Checked residual rows versus saved matrix action | 8.958e−12 normalized |
| Whole-aircraft force imbalance | 2.355e−10 lb/F3 |
| Whole-aircraft moment imbalance | 1.062e−9 lb ft/F3 |
| Yaw-moment imbalance | 5.261e−11 lb ft/F3 |

The fixed componentwise load gate is `2e−6 + 2e−7*abs(reference)`; normalized
residual gates are `2e−8 + 2e−8*abs(reference)`. Frame-chart comparisons use
`2e−8 + 2e−8*abs(reference)`, with the base Earth rotation checked at 2e−12.
Separate transfer-conservation checks use 2e−10 absolute/relative gates. No
tolerance was relaxed after seeing a result. These are supplementary checks,
not additional ISAE or native-ASWING passes.

At the dip, the wing's combined yaw moment is **−7.5345 + 8.1012i lb ft/F3**;
the vertical tail contributes **7.1158 − 7.2219i**. The other components close
the balance. The opposing wing/tail contributions are consistent with a
coupled cancellation mechanism, but this accounting does not identify which
historical settings produced Drela's deeper notch.

## Evidence and remaining work

- [Saved-data verification and component totals](../../artifacts/daedalus-source-balance-20261114/report/result.json)
- [All component force/moment values](../../artifacts/daedalus-source-balance-20261114/report/wrenches.csv)
- [Dip-frequency comparison](../../artifacts/daedalus-source-balance-20261114/analyze-dip-v2/result.json)
- [Low-frequency comparison](../../artifacts/daedalus-source-balance-20261114/analyze-slow/result.json)
- [Independent balance equations](../../scripts/daedalus_source_balance_reference.py)
- [Bounded capture/comparison driver](../../scripts/check_daedalus_source_balance.py)
- [Saved-data report generator](../../scripts/report_daedalus_source_balance.py)

All **six serial jobs** are terminal and reaped: five succeed, and the first
reference attempt is retained as rejected. It caught a sign error in the
new reference Euler-rate conversion before aerodynamic/load evaluation.
Differentiating `Rz(−heading) Ry(elevation) Rx(−bank)` established the corrected
sign; all gates stayed unchanged. The rejected reference source and driver
remain available. This was a diagnostic correction, not an OpenSwing fix.

Each job uses one BLAS thread, 512 MiB address space, 15 CPU seconds and
25 wall seconds. Maximum observed CPU time is **4.413 s**, wall time
**8.802 s**, and RSS **101.09 MiB**. The report verifies 874 source/input
hashes, including three archived source versions, and the authoritative
steady/unsteady PDF and text hashes.

The declared endpoint discretization, parsed material values and loaded state
remain assumptions. Intrinsic point inertia/spin and the actual file's other
zero terms are not nonzero-feature tests. The selected body apparent-mass
factor and other aerodynamic limitations remain those disclosed in the
preceding comparison. This does not identify the historical Bode settings or
establish full ASWING equivalence.

Next independently check the **remaining 618 current beam strain/curvature
equations**, especially their coupled wing/boom/tail rotation conventions.
That closes a specific gap in the current-operator equation audit before
attributing the mismatch to unavailable historical settings. ISAE status,
progress history and browser/build verification remain unchanged.
