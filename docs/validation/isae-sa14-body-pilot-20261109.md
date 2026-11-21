# SA-14: current wing–body pilot and lift increments

All six sampled total-lift comparisons pass the 5% gate on current OpenSwing.
This is three original configurations at 5° on two reconstructed meshes, not a
full refresh of SA-14. The primary historical count remains **115/360 at 3%**;
all 128 slots with unconverged native rows remain required.

## Setup and evidence

The [source audit](isae-sa14-sources.md), authoritative source catalog and ISAE
Part I §6.3, pp. 40–44, were reviewed. The three unchanged original models and
their original polar drivers/tables are authenticated in the
[current plan](../../artifacts/isae/sa14-body-pilot-20261109/plan.json).

The [documented-startup reconstruction](isae-sa14-default-setup-20261109.md)
uses frozen influences, speed-derived PG Mach 0.20575527, speed 70 m/s,
rhoSL 1.2256 kg/m³ and 64/128 nominal lifting intervals. Actual body interval
counts also include required joints. Original section data, stall settings,
core rule and natural-v1 interpolation remain unchanged. The exact historical
startup, node array and circulation mode count remain unverified.

The adapter previously emitted a contradictory generic qualification claiming
Mach zero/current influences even after its SA-14 settings had been corrected.
That stale qualification is now removed only for SA-14; fourteen existing
source/adapter checks pass. The runner no longer embeds an earlier test count
or goal-turn description into new plans. No production equation changed.

This pilot includes the material-knot body-quadrature correction introduced
during SA-13. Its fresh source pins supersede neither the old single-point
artifact nor the authentic deferral record; both are retained as history.

## Total lift

| Original configuration | Archived CL | Current CL, N64 | Error | Current CL, N128 | Error |
|---|---:|---:|---:|---:|---:|
| Finite wing/body | 0.328182 | 0.32628576 | −0.578% | 0.32605311 | −0.649% |
| Wing/“infinite” body | 0.324771 | 0.32735909 | +0.797% | 0.32713129 | +0.727% |
| Wing only | 0.323899 | 0.32735909 | +1.068% | 0.32713129 | +0.998% |

All six states meet the eleven numerical checks. The independent Decimal
acceptance calculation agrees with the adapter, using the original table
tokens and unchanged absolute floor. Residuals are below 1.34e−15. These are
two-mesh samples, not a continuum-convergence proof: maximum local normal Mach
increases from approximately 0.213 to 0.340 at the outermost wing stations.
Both remain below the local-Mach rejection limit.

Full data: [analysis](../../artifacts/isae/sa14-body-pilot-20261109/analysis.json).
Each serial job used one BLAS thread with 512 MiB address-space, 15 CPU-second
and 25 wall-second limits. Solve plus result processing took 0.276–0.459 s
after imports; complete tool process times were approximately 4.2–6.5 s.
Maximum peak RSS was 238,444 KiB. No background solver or browser/build job ran.

## The interference increment remains different

Passing total CL can hide an error in the much smaller body contribution.
Subtracting each wing-only value exposes a sign difference:

| Quantity | Archived difference | Current N64 | Current N128 |
|---|---:|---:|---:|
| Finite wing/body minus wing only, ΔCL | +0.004283 | −0.00107332 | −0.00107818 |
| “Infinite” wing/body minus wing only, ΔCL | +0.000872 | 0 | 0 |

The finite-body increment error is about **125% of the archived increment**,
even though every total CL passes. This is a diagnostic difference of rounded
outputs, not a new acceptance scope or a reason to change the 5% total-CL gate.

The [independent public-force audit](../../scripts/audit_sa14_body_increment.py)
checks every saved strip force and reconstructs wind-axis CL from dimensional
forces, the actual angle and original normalization. Wing and body totals
close within 4.55e−13 N. At N64, adding the finite body changes the wing's CL
by −0.00455552 and adds body CL +0.00348219, yielding the small negative net
increment. At N128 those contributions are −0.00449207 and +0.00341389.
Thus this discrepancy is not an omitted body force in the reported total.

All three current wing lattices are exactly identical at each mesh. The
infinite-body and wing-only wing-strip results are also exactly identical
after removing their different beam numbers.
[Audit data](../../artifacts/isae/sa14-body-pilot-20261109/body-increment.json).

## Interpreting the constant-body result

The supplied “infinite” body is a finite straight constant-radius segment,
from −12.7 to +12.7 m with radius 0.16129 m. Under the selected frozen
zero-angle approximation, its axial area derivative is zero and its axis is
parallel to the influence wind. Consequently both source and transverse
doublet strengths vanish in the current volume-field equations. Its distributed
body-lift area derivative also vanishes. This explains the exact equality
with wing-only without modifying a body law or suppressing a nonzero term.

Drela's steady §4.6, p. 36, explicitly describes precomputing vortex and volume
influences on jig geometry at zero wind angles. ISAE Part I p. 43 attributes
the near-absent constant-body interference to an implementation conditional
and reports instability after changing it. The present result provides an
alternative explanation under the documented frozen setting; it does not
establish what that historical executable did or disprove the report's source
inspection. The archived infinite-body and wing-only values also differ
slightly, despite the report describing identical curves.

The next useful checks are the original local-load exports and a bounded
attached-flow polar refresh, retaining this increment diagnostic. Mesh/setup
differences and the historical volume treatment remain unresolved. Total-lift
agreement alone cannot validate wing–body interference or justify a physics
change. SA-12 and SA-13 remain open.

## Reproduction

The six jobs were executed one at a time with `scripts/verify_sa14_defaults.py`
(`prepare`, then `run --index 0` through `5`, then `summary`), using the output
directory above and the saved before-plan. The prepared plan pins all solver
modules, source inputs and comparison code. Reports record artifact checksums.
`scripts/audit_sa14_body_increment.py --output <directory>` independently
checks the saved force ledger without importing OpenSwing or running a solve.
Writers refuse to replace existing artifacts; use a fresh directory to replay.
