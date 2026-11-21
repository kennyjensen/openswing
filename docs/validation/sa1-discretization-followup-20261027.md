# SA-1: node provenance and circulation-load follow-up

SA-1 remains **19/154 registered archived-output checks passing**. All 22 baseline
jobs completed. This follow-up corrects comparison metadata and narrows the
remaining discrepancy; it does not change the numerical kernel or reference gates.

## Implemented correction

The shared driver parser now records `NODE/I` as `requested_nodes` and
`node_count_token`, rather than declaring a panel count. Its consumers explicitly
describe the existing interval counts as reconstructions. The node allocation and
Fourier count used by the historical executable remain unknown.
This supersedes the metadata description in finding 2 of the earlier
[equation review](steady-aero-review-20261027.md); that review is retained as a
record of the code and evidence examined before the correction.

The five adapters using that parser were migrated together. Their 2,849 planned
jobs and 14,614 scalar slots preserve all job IDs, original targets, execution
routes, numerical settings and source pins. SA-1 still has 22 jobs, 154 slots,
and the existing 200/400-interval reconstructions. No automatic subtraction of one
or fit-selected mesh was introduced. **105 focused tests passed**; see the
[change/verification receipt](steady-aero-review-20261027/node-metadata-correction.json).

The [additional settings audit](steady-aero-review-20261027/legacy-mesh-settings-review.md)
found a public saved run whose per-beam counts are corroborated by its output.
It did not establish the meaning of every other settings field, a universal
spacing rule, or the absent SA-1 settings. Unrelated `.set` files cannot establish
the original SA-1 run configuration.

## Spacing diagnostic

Earlier refinement tested cosine spacing only. A predeclared diagnostic evaluated
uniform spacing at the same two interval counts, at the same representative
attached and stalled incidences. It also retained a 40-mode Fourier check on the
200-interval mesh. No spacing or mode count was selected by closeness to ASWING.

| Incidence | Uniform intervals | Circulation representation | CL error | CDi error |
|---:|---:|---|---:|---:|
| 1.9971° | 200 | Pointwise | −0.7298% | −0.3453% |
| 1.9971° | 400 | Pointwise | −0.3935% | −0.2031% |
| 1.9971° | 200 | 40 Fourier modes | −0.7298% | −0.3452% |
| 18.091° | 200 | Pointwise | −3.2382% | −4.7269% |
| 18.091° | 400 | Pointwise | −2.9993% | −4.7186% |
| 18.091° | 200 | 40 Fourier modes | −3.2383% | −4.7268% |

All six solves completed; none of their 42 diagnostic scalar comparisons matches
the archived printed interval. They are not added to the registered denominator.
The results show that spacing matters and that the tested uniform grids do not
resolve either incidence. They do not rule out every possible historical mesh.
The cosine 400-interval results remain approximately +0.058% in attached CL and
−2.67% in stalled CL.

The [protocol and completion receipt](../../artifacts/isae/sa1-spacing-diagnostic-20261027/receipt.json)
retain the original inputs, six complete results, and an interrupted diagnostic
summary write. The first solved record was reused after fixing serialization;
only the five remaining cases were then solved. An independent
[scalar replay](steady-aero-review-20261027/spacing-oracle.json) reproduces all six
states within 1.6e−13 m/s in velocity and 5.5e−12 N in total force, without
production solver imports or additional physical solves.

## Whole-polar load diagnosis

The [complete load-consistency analysis](sa1-load-consistency-20261027/report.md)
uses all 11 native rows, propagating their actual printed intervals. The native
moment and efficiency provide compatible independent reconstructions of the
circulation-lift integral. The original dimensional-force/coefficient
normalization is also consistent in every row.

At 18.091°, the total CL difference is −0.02879580. Only −0.00011244, or **0.3905%**,
comes from profile lift. The remaining difference is in the inferred
circulation-lift integral. This does not distinguish a historical circulation
distribution from a force-integration difference. Drag also contains substantial
cancellation: a CDi deficit of −0.00314842 is offset by a profile-CD excess of
+0.00361697. A total-drag check alone would hide the component errors.

These results do not support a constant lift multiplier, a profile-force
projection correction, or changing the stall law without further source evidence.
The [equation review](steady-aero-review-20261027.md) remains applicable.

## Evidence correction and next requirement

The earlier six-case Fourier diagnostic writer used `Lift`/`Drag` keys where the
matcher expected `lift`/`drag`. A
[saved-result correction](../../artifacts/isae/sa1-basis-diagnostic-20261027/reference-check-correction.json)
restores those diagnostic comparisons without rerunning or editing the original
records. Three attached diagnostic cases each have two matching outputs, rather
than the originally recorded one. This bookkeeping error never affected the
22-job registered baseline, the scalar oracle, or the 19/154 status.

Exact reference reproduction still needs evidence of the historical node layout,
circulation representation and load/stall implementation. A new reference run
could distinguish a difference from the present published-equation implementation
from a difference specific to the archived run; it would not by itself recover
unrecorded historical settings. SA-1 remains the priority and no full case pass is
claimed.

A [portable reference-capture kit](../../artifacts/isae/sa1-reference-capture-kit-20261027-r2/README.txt)
is now prepared from the pinned original model, driver and table. It preserves the
exact original command stream and keeps any optional startup-settings probe in a
separate process and directory. **No ASWING executable was run.** The
[capture tool and instructions](isae-sa1-reference-capture.md) allow a future
supplied executable to produce logs, settings and a polar with recorded hashes and
timestamps. Its 25 focused tests passed using explicitly labelled fake processes;
they verify capture mechanics, not aerodynamic results. A new capture would help
isolate numerical differences but would not recover the archived run's missing
historical settings.
