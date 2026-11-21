# AE-2: all three 5° speed sweeps attempted with the current solver

Observed 2026-11-10 UTC. The full current AE-2 count rises from **34/2,200 to
548/2,200 at 5%**, through expanded coverage with the same production solver.
No equation, physical input, default or tolerance changed. These are scalar
comparisons on both declared meshes; they are not 548 independent cases.

All three original layups now have their complete commanded-beta-5° sweeps
attempted. Uncoupled and positive-coupling predictions pass every finite
archived comparison. Negative coupling agrees through 16 m/s, then the cold
solutions disagree with the archived branch and some runs fail to return.

| Original layup | Commanded IAS range | Matches / required in this sweep | Computed values | Median / maximum computed error |
|---|---:|---:|---:|---:|
| `[03_90]` uncoupled | 0–22 m/s | **176/184** | 176 | 0.417% / 2.239% |
| `[m15_02]_S` negative coupling | 0–20 m/s | **132/168** | 144 | 0.448% / 356.704% |
| `[p15_02]_S` positive coupling | 0–30 m/s | **240/248** | 240 | 0.290% / 2.407% |
| All three 5° sweeps | | **548/600** | **560** | **0.341% / 356.704%** |

Each layup retains eight unavailable zero-speed slots across the two meshes.
The negative-coupling sweep also retains **12 computed mismatches** and
**16 required outputs from four failed runs**. Its failed-value errors range
from **227.303% to 356.704%**, with median **249.161%**.

The full 2,200-slot scope still includes the other nine incidence sweeps:
**548 passes + 12 computed mismatches + 16 failed-run outputs + 1,528 finite
unrun comparisons + 96 unavailable native values = 2,200**.
The 548/600 subset is not an additional independent progress scope.

![All four native channels on both meshes](../../artifacts/isae/ae2-beta5-sweeps-current-20261110/curves.png)

Every finite native value is plotted. Missing predictions are left absent;
the shorter nominal-160 negative-coupling curve records the failed runs.
The nominal-80 curve is nearly hidden by nominal 160 where they agree.

## The negative-coupling discrepancy

The original archived outputs change sign at 17 m/s. The current default cold
initialization follows the negative-deflection branch at 17–19 m/s. Local
sensor speed still passes, while tip Earth Y, heading and sensor sideslip fail.

| IAS | Nominal mesh | Native tip Y | OpenSwing tip Y | Native heading | OpenSwing heading |
|---:|---:|---:|---:|---:|---:|
| 17 m/s | 160 | +0.191155 m | −0.248456 m | +14.8018° | −18.8431° |
| 18 m/s | 80 | +0.218111 m | −0.281740 m | +16.7860° | −21.8784° |
| 19 m/s | 80 | +0.190580 m | −0.320147 m | +14.7329° | −27.1538° |

These accepted states pass fresh residual and physical checks. OpenSwing's
mismatches persist after its own equations converge. Native convergence and
the solutions' stability and uniqueness remain unproven.

Four new processes ended with **SIGKILL (exit −9)** before saving a solution:
nominal 160 at 18 and 19 m/s, and both meshes at 20 m/s. Each was reaped; logs
are empty and the exact kill cause was not recorded. The inherited CPU limit
is a plausible explanation, not an established diagnosis. No run was retried,
no resource limit was raised, and no partial state receives a pass.

The [completed inverse-speed study](isae-ae2-staged-inverse-20261110.md) remains
separate. On a prescribed positive-deflection branch, its 18/19 m/s controls
recover the archived speeds within 0.221%, while the archived 17 m/s deflection
requires 18.9528 m/s. Thus branch selection can matter without resolving every
archived discrepancy. Those diagnostics add no primary comparisons.

## Numerical and source checks

This expansion executes **134 new physical attempts**, yielding 130 accepted
states and four failed runs, plus six explicit unavailable zero-speed records.
The ten preceding current states are reused only after the independent auditor
checks their identical production/source pins and disjoint job identities.
Historical strict and alternative-branch results are not pooled into this count.

Across all **140 accepted current states**, **2,520 physical checks pass**.
Maximum independently restored full residual is **9.995e−13**. All **69 completed
mesh pairs** pass their original gates: 138 deflection/heading checks, with
maximum relative mesh change **0.04078%**. Three nonzero pairs remain incomplete
at 18–20 m/s; unavailable zero rows and other incidences do not receive mesh passes.

Every child uses one BLAS thread, a 512 MiB address-space limit, a 15 CPU-second
limit and the existing 25-second supervisor deadline. A live `/proc` receipt
confirms inherited CPU/memory/thread limits. All started processes are terminal
and reaped. Accepted solve-only wall times range from 0.536 to 10.075 seconds,
with median 1.703 seconds; these exclude reference checking, imports and reporting.
They do not characterize the four failed solves or browser performance.

The [authoritative source catalog](aswing-authoritative-sources.json) and Part IV
PDF/text hashes were rechecked. Jan **Part IV §3.2, pp. 8–12, Figure 3** identifies
ASWING 5.96, the three laminates, symmetry wall, cosine clustering and section
properties. Literal `.asw`, driver and four-channel output bindings are retained.
The paper's two edge sensors remain distinct from the literal archived sensor
definition. No experimental data enters acceptance.

Nominal 80/160 currently produce 81/161 intervals after inserted breakpoints;
these are not asserted to be the paper's original 40-node arrays. Historical
K/F settings, atmosphere, precise initialization and iteration history remain
unrecovered. The source/setup qualifications in the original registration remain.

Next: use bounded progress diagnostics to locate the high-speed negative-coupling
failure and inspect branch selection against the documented algorithm. Preserve
all four failed attempts, the 17–19 m/s mismatches and the other nine required
sweeps. A different initialization must remain a separately declared diagnostic.
Browser/build checks remain held; AE-2 and the overall project are incomplete.

[Independent full-scope audit](../../artifacts/isae/ae2-beta5-sweeps-current-20261110/assessment.json) ·
[New raw suite report](../../artifacts/isae/ae2-beta5-sweeps-current-20261110/report.json) ·
[Source review](../../artifacts/isae/ae2-beta5-sweeps-current-20261110/source-review.json) ·
[Resource receipt](../../artifacts/isae/ae2-beta5-sweeps-current-20261110/live-resource-check.json) ·
[SVG curves](../../artifacts/isae/ae2-beta5-sweeps-current-20261110/curves.svg)
