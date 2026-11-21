# AE-4: Fourier circulation audit on the Pazy model

**The complete Fourier basis reproduces the pointwise equations and modes.**
The tested truncated series do not resolve the archived damping or slow-root
differences. Twelve bounded cold solves complete with **342 numerical checks
passing**. No production code, default setting or acceptance gate changes;
the primary comparison remains **122/1,200**.

![AE-4 circulation comparison](../../artifacts/isae/ae4-circulation-audit-20261112/circulation-comparison.png)

## Scope and source equations

The authoritative [reference index](aswing-authoritative-references.md) and
checksummed catalog were consulted, including Jan Part IV §3.4, Drela's steady
and unsteady descriptions, the extended manual and the literal AE-4 model,
driver and archived modal results. Original model properties, gravity, solid
wall, updated influences, circulation lag, four-mode search and shift `0+200i`
are retained. This follows the declared comparison settings, not a newly
authenticated native startup configuration.

Drela steady Eqs.62–63 (p.15) define pointwise and Fourier circulation as
alternatives. Eqs.150–153 (p.31) sample sine modes at each interval's Glauert
midpoint. Eq.201 (p.40) applies sine-weighted residuals with angle widths.
With sample matrix `S` and residual-test matrix `T`, a Fourier system should
therefore obey

```
A_K = L A_point R        M_K = L M_point R
R = diag(I, S, I)        L = diag(I, T, I)
```

The nonidentity blocks occupy only circulation coordinates and flow-equation
rows. They are rectangular when fewer Fourier coefficients than intervals
are retained. These checks include both the state and rate matrices, keeping
all mechanical, constraint and kinematic equations. They use fresh cold
equilibria and independently formed sine samples/angle weights.

On cosine40, the required material station at `t=0.52` gives **41 intervals**,
so `K=41` is complete. The predeclared truncations are **9, 19 and 39** modes;
`K=19` is also tested on cosine80, which has 81 intervals. Each setting is
tested at 69 and 103 m/s. `K=0` in OpenSwing selects pointwise circulation,
not zero circulation.

The extended manual §1.3.5/Fig.1.13 shows modes 1–19 on an unrelated
180-node example. It does not establish AE-4's Fourier count. The literal
`alpha_0.sh` specifies `I 40` and the eigenvalue search but does not print or
select the circulation count. No count was chosen by fitting this study's
outputs, and no count or wall/beam Fourier convention is authenticated as the
archived executable's setting.

## Full-basis equivalence passes

At both speeds, the largest row-scaled matrix difference is **1.31e−15**.
The complete-basis inverse defect is **7.74e−15**, the largest scaled root
difference is **3.57e−14**, and the sensitive real components differ by at
most **3.06e−15 /s**. The fresh pointwise controls also reproduce the earlier
pointwise eigenvalues exactly after the preceding LU-lifetime repair.

The truncated systems likewise satisfy their rectangular matrix-projection
checks. Independent residual directional derivatives, every retained left and
right eigenpair, mass pairing, clamps and fresh base residuals pass their
existing gates. Thus these results rule out a circulation-coordinate conversion
or residual-projection error for the audited Pazy operating points. They do
not independently validate the underlying pointwise aerodynamics or recover
the native run's settings.

## Truncation does not resolve the native discrepancy

| Representation | Base intervals | Flutter-mode Re(λ), IAS 69 (1/s) | Native error | Candidate slow Re(λ), IAS 103 (1/s) | Conditional native error |
|---|---:|---:|---:|---:|---:|
| Archived ASWING | — | −0.1780785000 | — | +0.0333341770 | — |
| Pointwise | 40 | −0.0911608982 | 48.809% | +0.0932973898 | 179.885% |
| Fourier, K=9 | 40 | −0.1057602690 | 40.610% | +0.1150966308 | 245.281% |
| Fourier, K=19 | 40 | −0.1058976507 | 40.533% | +0.1378861013 | 313.648% |
| Fourier, K=39 | 40 | −0.0905042054 | 49.177% | +0.0757460532 | 127.232% |
| Fourier, K=41, complete | 40 | −0.0911608982 | 48.809% | +0.0932973898 | 179.885% |
| Fourier, K=19 | 80 | −0.1399756080 | 21.397% | +0.1473393482 | 342.007% |

No tested truncated setting passes either sensitive component. Increasing the
structural mesh at fixed `K=19` changes the critical real parts by **24.35%**
at 69 m/s and **6.42%** at 103 m/s, both above the existing **0.1% mesh gate**.
Two meshes do not prove structural or Fourier convergence. These findings
do not rule out every possible native circulation setting; they give no
evidence for changing the default to one of these tested counts.

The 103 m/s reference remains the conditional NN10 slow-branch candidate
from the [transition comparison](isae-ae4-transition-coverage-20261112.md).
Its imaginary part `3.6546462e−7 /s` remains retained. The primary NN4 export
has a slightly different real candidate and an additional tiny complex root.
Its full target set remains unpaired under the original matching contract;
none of those components is discarded or replaced by this diagnostic.

## Execution, accounting and next work

All twelve solver workers ran serially with one BLAS thread, and all are
terminal and reaped. Child CPU, supervised wall time and RSS are at most
**12.05 s, 12.45 s and 120.1 MiB**. The limits remain **512 MiB address space,
15 CPU seconds and 25 wall seconds**. Library preload is separately bounded.
Complete sparse matrices, all four selected modes, bases and circulation
bases are retained. Source hashes are unchanged. Browser/build work remains
held; this workload does not include UI modal-output recovery and is not a
browser benchmark.

Primary accounting stays **122/1,200**: 128 paired components, six mismatches,
16 unmatched, 12 unknown initial values and 1,044 unrun. The failed paired
errors remain median **11.47%**, range **5.91–48.81%**. The diagnostics above
are alternative settings and receive no extra tracked scope or primary votes.
The overlapping historical sample and 9,480 historical modal components stay
separate.

Next, resume the declared undeformed sweep at **71–75 m/s** on both cosine
meshes, in small serial batches. This covers more of the unstable branch
without fitting settings to the remaining two sensitive modes. Native node
placement, restraint settings, tiny-root identities, wall/frame support,
spatial convergence, deformed branches and time histories remain open.

- [Prospective plan and source pins](../../artifacts/isae/ae4-circulation-audit-20261112/plan.json)
- [Combined assessment and all twelve results](../../artifacts/isae/ae4-circulation-audit-20261112/assessment.json)
- [Standalone SVG](../../artifacts/isae/ae4-circulation-audit-20261112/circulation-comparison.svg)
- [Prior spacing refinement and memory fix](isae-ae4-spacing-refinement-20261112.md)
