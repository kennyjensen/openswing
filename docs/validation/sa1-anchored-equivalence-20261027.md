# SA-1 rigid versus anchored route comparison

The current rigid adapter and the default mounted equilibrium route agree to roundoff at both tested original incidences. Selecting the anchored route therefore does not repair the archived SA-1 discrepancy at these two states. The registered SA-1 native comparison remains **19/154**; this bounded diagnostic adds no acceptance targets or passes.

The [prospective protocol](../../artifacts/isae/sa1-anchored-equivalence-20261027/protocol.json) was pinned before execution. Both routes used the unchanged `SA_1.asw`, nominal 200 intervals, identical initial node/sample arrays, pointwise circulation, `natural-v1` interpolation and the default `midpoint-v1` structural operator. Conditions were the original 1.9971° and 18.091° incidences, speed 47.9, density 1.2256, PG Mach zero, current influences, zero sideslip/rates/accelerations, no image/gust, and the existing stall/profile laws. The mounted route used the literal root clamp, explicit gravity `[0,0,-9.81]`, empty operating constraints and loads, and the unchanged four-stage continuation request. Construction verified zero compliance, zero mass and identical initial meshes before every cold API call.

| Incidence | Rigid CL | Mounted CL | Maximum difference in Gamma/U | Maximum normalized difference across seven outputs | Native printed matches, each route |
|---|---:|---:|---:|---:|---:|
| 1.9971° | 0.1448810319872067 | 0.1448810319872067 | 2.776e−17 | 6.661e−16 | 2/7: Drag and CDi |
| 18.091° | 1.0502308248018282 | 1.0502308248018284 | 3.331e−16 | 6.661e−16 | 0/7 |

Lift/Drag differences above are divided by the literal `qS=8295.48524320`; the other five scalar differences are absolute. The prospective route-equivalence gate was 1e−8, distinct from every original printed half-last-place tolerance. [comparison.json](../../artifacts/isae/sa1-anchored-equivalence-20261027/comparison.json) retains all seven values, signed differences and exact native tokens/tolerances for both cases. The native CL values remain 0.144797 and 1.07903 respectively.

Node rotations agree exactly. Node positions and aerodynamic sample positions agree exactly at low incidence and differ by at most 2.2204460493e−16 m at high incidence. All other retained mesh/frame fields passed the declared comparison. The largest normalized mounted force imbalance was 1.316e−15; the largest normalized moment imbalance was 1.096e−16. The literal support can carry the applied aerodynamic wrench without changing the zero-compliance shape.

| Incidence | Rigid fresh normalized residual | Mounted fresh full-system residual | Rigid worker duration | Mounted worker duration |
|---|---:|---:|---:|---:|
| 1.9971° | 1.793e−16 | 3.035e−16 | 21.72 s | 24.43 s |
| 18.091° | 6.008e−15 | 1.980e−15 | 9.69 s | 33.68 s |

Each rigid result was freshly evaluated at its saved circulation without another root solve. Each mounted physical state was restored into a newly constructed matching network; restoration performed zero residual calls, followed by exactly one full residual and a snapshot from that same evaluation. Complete residual vectors, meshes, Gamma, node positions/rotations, full solver outputs and restored outputs are retained in each of the four worker directories.

The low-incidence rigid circulation solve reported the direct method with 205 evaluations. The high-incidence rigid solve reported pseudo-arclength continuation, 39 accepted steps, 41 attempts and 515 evaluations; its full native trace is retained. Each mounted call completed four load stages and reported 108 network residual evaluations. Observational profiling recorded one internal cold aerodynamic initialization plus 101 prescribed-circulation aerodynamic evaluations per mounted call. These are the existing algorithm's operations, not four additional independently prescribed operating states. The default API does not export every mounted Newton iterate; the retained evidence is its full result, progress events, stage/evaluation counts, restored state and raw fresh residual. No rerun was performed to augment that trace.

All four subprocesses exited 0 and were reaped; none reached the fixed 180-second cap. Total supervised execution was 95.319788927 s. All 123 kernel pins, the original inputs and the prospective implementation pins remained unchanged. The [execution receipt](../../artifacts/isae/sa1-anchored-equivalence-20261027/execution-receipt.json) and [per-process receipts](../../artifacts/isae/sa1-anchored-equivalence-20261027/process-receipts.json) retain durations and exit status. All 80 declared numerical/geometry/parity comparisons passed; these are diagnostic checks, not archived-target matches.

The [source mapping review](sa1-script-mapping-review-20261027.md) explains why exact arithmetic predicts this equivalence: internal loads and reactions cannot change geometry when compliance is zero, and both routes use the same aerodynamic evaluator. A separate read-only review found no blocking setup issue. This experiment tests **rigid versus default mounted API behavior** at two current reconstructed states. It does not run the source-coupled structural policy, authenticate the historical ASWING executable or establish every-state/global root uniqueness.
