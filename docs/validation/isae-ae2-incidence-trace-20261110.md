# AE-2: tracing the positive incidence branch

The primary native-reference score remains **708/2,200 at 5%**. This diagnostic
adds no comparison votes. It investigates whether the independently verified
1°, 17 m/s positive-deflection equilibrium of the negative-coupling wing can
be followed toward the archived 5° point. Original cold-start comparisons,
including their twelve branch mismatches, remain intact.

## Setup and evidence

The starting state is the original nominal-160 (161 physical intervals)
`m15_02`, 1°, IAS 17 m/s solution. All four native outputs pass; its full
residual is 2.053e−13. The [primary comparison](isae-ae2-incidence-branch-20261110.md)
records the original input, result, independent checks and reference accounting.
The authoritative index and checksummed Part IV §3.2, pp. 8–12, Figure 3 govern
the setup. No stiffness, geometry, airfoil, sensor, atmosphere or frozen-influence
setting changes. Incidence is commanded as beta for this vertical wing.

The declared trace starts with a same-condition 1° control, then uses 2°, 3°,
4° and 5°. Each accepted state must be independently restored and checked before
becoming the next seed. The warm corrector tolerance is explicitly 1e−12 to
preserve the existing full-residual acceptance gate. A traced branch does not
establish uniqueness, dynamic stability or the original ASWING iteration history.

## Unchanged warm path

The original production warm control passes all **21 checks**. Its four sensor
outputs are bit-identical to the accepted cold solution; normalized coordinates
differ by at most **2.776e−17**. It takes zero Newton iterations. The final tangent
uses 974 residual calls and 6.023 seconds; rank certification takes 0.908 seconds.
The complete child uses 9.245 CPU seconds and 12.122 elapsed seconds.

The original 2° warm attempt terminates at the **15-second CPU cap**, without
a saved result. Its log records the residual decreasing from 0.0174484 to
0.00740785 before termination. This is an execution limitation, not evidence
that the positive branch ends there. Its failure receipt is preserved in
[`ae2-incidence-trace-20261110`](../../artifacts/isae/ae2-incidence-trace-20261110/).

## Complete tangent comparison

The existing complete moving-geometry chain rule and original full-residual
stencils were assembled separately at the identical 2° request / 1° seed.
Both retain constrained wall-root derivatives and all physical equations.

| Measure | Complete geometry assembly | Original stencils |
|---|---:|---:|
| Assembly CPU seconds | 0.99570 | 5.95103 |
| Assembly elapsed seconds | 1.21557 | 6.05710 |
| Residual calls | 20 | 974 |
| Newton linear residual | 1.30e−15 | 6.02e−15 |

The maximum scaled matrix difference is **3.185e−8**, against the declared
2e−5 gate. Relative matrix difference is **8.885e−11**. Relative Newton-direction
difference is **3.248e−7**, against the declared 1e−4 gate. Both gates pass.
This is approximately six times less CPU for tangent assembly at this one
state, not a complete-solve or browser speedup claim.

[Pinned matrix assessment](../../artifacts/isae/ae2-incidence-tangent-20261110/assessment.json).

## Resource qualification

Two separately retained control attempts enabled complete geometry assembly
also for the final rank check. Both exit with an OpenBLAS allocation error;
neither supplies an accepted state. The second progress log reaches the
completed tangent and then `equilibrium_rank`, narrowing that failure to rank
certification rather than imports or nonlinear convergence. A startup-only
import check succeeded under the same memory limit. The exact allocation cause
has not been established; no memory limit is raised and no matrix entries or
rank requirements are discarded.

The subsequent diagnostic enables the complete assembly **only for sparse
Newton iteration matrices**. It reuses production Newton, line search, physical
residuals, dense recovery, original final stencil tangent and original rank gate.
The override exists only in the isolated child process; production files and
defaults are unchanged. The script records the actual tangent choice explicitly.

Each numerical/verification child remains serial with one BLAS thread,
512 MiB address space, 15 CPU seconds and a 25-second supervisor deadline.
Source verification occurs before and after each child. Failed executions are
preserved separately. Browser/build tests remain held.

## Outcome and next work

The revised same-condition control reaches zero-iteration equilibrium and starts
the original final stencil tangent, but its child reaches the 25-second elapsed
cap before finishing. It uses 5.779 CPU seconds, so this failure is distinct from
the original 2° attempt's CPU limit. No result is saved or accepted. The revised
2°–5° steps remain unstarted. The original verified 1° control and successful
matrix comparison remain valid evidence; none of these failed processes proves
a physical branch termination.

The [saved-only assessment](../../artifacts/isae/ae2-incidence-iteration-20261110/assessment.json)
checks the pinned sources and all six supervised process receipts: two normal
completions (original control solve and independent verification), four retained
failures, all reaped. The matrix jobs are separately complete and assessed.
No production source changed and no background solver remains running.

Next: separate Newton convergence, final tangent construction, rank certification
and independent physical checks into bounded stages, preserving every acceptance
gate. A saved intermediate candidate must not become a new seed or native pass
until all stages finish. The branch trace is still open; the remaining original
native sweeps and ten unresolved original executions also remain required.

Scripts: [original trace](../../scripts/probe_isae_ae2_incidence.py),
[matrix comparison](../../scripts/probe_isae_ae2_incidence_tangent.py),
[direct final-tangent diagnostic](../../scripts/probe_isae_ae2_incidence_direct.py),
[iteration-only diagnostic](../../scripts/probe_isae_ae2_incidence_iteration.py).
