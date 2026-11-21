# FFWT-1 static mechanics and setup checks

The Flare30 nominal equilibrium agrees with a separately assembled rigid
two-hinge torque balance. Experimental validation remains incomplete. This
study uses the unchanged integrated-08 source and preserves the earlier
[nominal comparison](isae-ffwt1-nominal-07.md); it does not change the browser
solver, acceptance thresholds or experimental targets.

## Mechanical cross-check

The reconstructed archive model has a grounded rigid main wing and two rigid
tips. The reference rotates each tip with Rodrigues' formula and balances
integrated aerodynamic torque, analytic gravity torque and the two finite
hinge springs. It shares the production parser, mesh, section interpretation,
hinge-law interpolation slope and aerodynamic kernel. Its mechanical assembly
is independent; its aerodynamics are not.

At 22 m/s, zero incidence/sideslip and the original 100/40/40 mesh, physical
starboard/port folds are −11.00675357°/−11.00379810°. The independently assembled
root agrees within 1.6e−14 degrees, with torque closure below 2e−17 N·m and
circulation residual 4.20e−14. The full saved network independently replays at
8.53e−13, passing its unchanged 1e−12 residual gate. The reduced calculation
separately requires torque closure below 1e−12 N·m and normalized circulation
residual below 1e−12.

The reference geometry differs from the full geometry by at most 8.2e−17 m.
Passing the old circulation directly to that slightly different geometry gives
circulation residual 1.69e−12, above the gate. That intermediate projection is
not an accepted equilibrium replay; fresh circulation is solved for the reduced
root. Its mechanical torque projection nevertheless agrees within 1.3e−17 N·m.

The terminal hinge traces give positive physical spring stiffness
9.9998324e−7 N·m/rad on both sides. The port input's negative angle/moment slope
comes from the trace orientation. It does not represent negative stiffness.
The analytic reference uses the exactly antisymmetric two-knot source law;
the interpolator's raw zero-angle roundoff of ±1.12e−16 rad is recorded.

## Local restoring behavior

Circulation is re-equilibrated at each perturbed pair of tip angles. Centered
differences at steps 1e−4, 5e−5 and 2.5e−5 rad give the coupled restoring matrix
below, with rows and columns ordered starboard, port, in N·m/rad:

```text
 0.1847745735   0.0005831496
 0.0005891837   0.1842013345
```

Successive maximum matrix changes are 1.25e−7 and 3.12e−8 N·m/rad. The symmetric
part has positive eigenvalues 0.18383546 and 0.18514044 N·m/rad. The small
antisymmetric part is retained. This supports local restoring work in the two
rigid fold coordinates; it does not establish full aeroelastic dynamic
stability, global uniqueness or an experimental branch.

The literal model is not aerodynamically symmetric: the starboard tip has
section lift limits ±1.1 and the port tip ±1.4. Neither angle equality nor a
symmetric restoring matrix is imposed.

## Hanging-start branch

At exactly zero flow the reference uses zero aerodynamic force and finds the
gravity/spring hanging root near −89.99747° on both sides. A first increasing
speed sequence reaches 4 m/s, then its 6 m/s trial fails the local Mach guard.
A separate adaptive continuation starts from the verified 4 m/s state and
halves failed speed increments while preserving every failure. It reaches
5.123046875 m/s, then stops at its declared minimum speed interval after
298.26 seconds. Mach-domain failures and circulation residuals above the
unchanged 1e−12 gate prevent further accepted progress.

The retained branch ends around −78.17290° starboard / −76.05204° port.
It does not connect to the nominal 22 m/s root, and no return branch or
hysteresis result is claimed. Failure to bridge these steps does not prove
that a physical equilibrium branch is absent. The hanging-start protocol is
documented for the thesis's numerical velocity sweep; it does not establish
the acquisition history of every nominal experimental incidence point.

## Full-network mesh refinement

The cold 50/20/20 solve reaches full load in 39.86 seconds and its fresh replay
has residual 1.50e−13. Its port fold −10.99965389° differs from the original mesh
by +0.00414421°; starboard differs by +0.00709750°.

The cold 200/80/80 solve stops cleanly at its 300-second cap. Its last accepted
load fraction is 2.30137e−5; a later trial is unaccepted. Both saved partial
states replay at their original factors. Neither supplies a full-load fine
mesh angle, so these full-network runs do not establish mesh convergence.
The fine run spends much of its time in full Jacobian fallback; performance
and strict residual behavior remain unresolved at that mesh.

The two-angle reference permits a separate aerodynamic-mesh check without
assembling the full structural network. Each mesh starts at the original
computed angles; no cross-mesh public checkpoint is imported.

| Requested intervals, main/starboard/port | Starboard fold | Port fold | Reduced outcome |
|---|---:|---:|---|
| 50/20/20 | −10.99965607° | −10.99965389° | Torque and circulation pass |
| 100/40/40 | −11.00675357° | −11.00379810° | Torque and circulation pass |
| 200/80/80 | −10.98227476° | −10.98227259° | Torque and circulation pass |
| 400/160/160 | — | — | First evaluation rejected by local Mach guard |

These reduced roots do not turn the capped full-network run into a successful
solve. Refinement is nonmonotone and the finest mesh has no accepted root;
an asymptotic error estimate is not established. The finest trial reports
643.22 m/s local section-normal velocity near a main-wing hinge at a freestream
speed of 22 m/s. The subsonic validity guard remains active.

All three logical beams have physical index 1. [Drela's input documentation](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
assigns zero mutual vortex core to beams sharing that index and warns of
numerical noise when a trailing leg approaches another beam's control points.
The archived indices and core settings are retained here. A per-source airflow
diagnostic confirms that the failed finest-mesh force point is only 2.806665 μm
from the main-wing endpoint and adjacent tip-root wake filaments. Effective
mutual cores are zero despite the nominal 0.0195 m configured source radius.
Individual source contributions exceed 4,000 m/s and partially cancel; the
remaining section-normal velocity is 643.22 m/s. The circulation residual at
that imposed geometry is already 1.20e−13.

An independent 80-digit evaluation of all 724 source contributions, retaining
the captured float64 geometry, PG coefficients and circulation, agrees with the
double-precision total velocity within 8.48e−13 m/s. The extreme velocity
therefore persists at high precision: kernel/summation roundoff is not its
primary cause at that state. This does not rule out upstream geometry or
circulation error. It diagnoses the implemented lifting-line model at that
imposed geometry and does not prove that original ASWING takes the same
path or fails in the same way. Changing physical indices, core behavior or
mesh placement would be a separately declared model/numerical study, not an
accuracy-preserving speed optimization of this literal calculation.

## Physical setup evidence

The [primary thesis](https://research-information.bris.ac.uk/ws/portalfiles/portal/388426634/Final_Copy_2024_01_23_Healy_F_PhD_Redacted.pdf)
places the hinges at ±365 mm and gives 61 g tip masses with absolute spanwise
CG ±424.3 mm. Relative to the primary hinge/elastic-axis datum, its
forward-positive chord coordinate maps the published −13.9 mm to ASW's
aft-positive +13.9 mm. The archive instead has hinges at ±364 mm,
61.4584 g distributed tip mass and spanwise CG ±432 mm.

Four separate static inputs retain the reconstruction, change hinge position
only, then change mass/spanwise CG, then include the chordwise CG. Point masses
use existing attachment stations. The original rotary inertia entries remain
unchanged; these are static sensitivity inputs, not validated dynamic models.
The archive's half-chord hinge placement remains an explicit assumption.
Independent quaternion and closed-form gravity checks cover all four variants:
108 fixed-angle evaluations agree within 2.78e−17 N·m without any aerodynamic
or root solve.

For these reconstructed hinge axes and side conventions, primary and ASW
sideslip signs are opposite. The nominal local-flow measurements
map to port (V, α, β_ASW) = (23.2 m/s, −0.8°, +2.0°) and starboard
(23.2 m/s, −1.8°, −0.7°). Two measured locations do not define the whole-span
flow. Any calculation applying either tuple uniformly is a conditional
sensitivity study, not a matched reconstruction of the tunnel flow.

Six conditional calculations on the original 100/40/40 mesh use the same
reviewed two-hinge reference. The baseline receives a fresh residual replay;
the other five are new local roots seeded from computed equilibria. All pass
the separate 1e−12 torque/circulation gates. No measured angle seeds a solve.

| Static input and uniformly imposed flow | Physical port fold |
|---|---:|
| Reconstructed archive, 22/0/0 | −11.00379810° |
| Hinge position only, 22/0/0 | −11.06934886° |
| Hinge + mass/spanwise CG, chordwise CG still zero, 22/0/0 | −9.74296419° |
| Hinge + mass/full CG, 22/0/0 | −11.04014944° |
| Full CG variant, port local-flow tuple applied to the whole wing | −11.25536996° |
| Full CG variant, starboard local-flow tuple applied to the whole wing | −14.64407581° |

The raw nominal port measurement remains −12.56345178° at digitized incidence
−0.10836057°. All three setup changes together shift the nominal prediction
by only −0.03635°. The spanwise and chordwise CG contributions largely oppose
one another. The two uniform-flow surrogates show sensitivity to flow setup;
their spread is not an uncertainty interval or a validated spatial-flow model.
The study takes 20.45 seconds for six cases including instrumentation, with 53
saved evaluations. That is not a browser or full-network performance claim.

Matched curves, hanging-branch reachability, dynamic stability, flexible-main
wing and fixture properties, friction/contact, experimental uncertainty and
complete raw-study packaging remain unfinished. No original ASWING executable
is available. Coverage remains **17 partial / 24 pending / 0 fully validated**;
FFWT-1 remains pending.

## Evidence scope

The [selected evidence archive](isae-ffwt1-static-08-evidence.zip) contains this
static study's scripts, source snapshots, model variants, retained failures and
numerical records. Its [verification record](isae-ffwt1-static-08-evidence.json)
checks every selected member after clean extraction. This is not the complete
historical FFWT raw-study archive or a fresh full-suite test. The previously
audited application downloads retain their earlier contents; this documentation
study does not rebuild or change the production app.

The [machine-readable study index](isae-ffwt1-static-08.json) pins eleven result
reports. After extraction, Python's standard library suffices to regenerate
that index from the retained results:

```sh
python3 physical-validation-08/build_summary.py --work . --output reproduced.json
```

This command reproduces the report index, not the numerical solves.
