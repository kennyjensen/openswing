# ST-6 symmetric fixed-fixed column supplement

**9/9 exact discrete-reference cases and 4/4 final pole/mesh comparisons pass.**
The final critical-load bracket center is 0.01785% above the continuous Euler
value. Coarse continuum failures and unsuccessful execution attempts remain
separate from these passing checks.

This study checks the first symmetric flexural buckling mode of an ideal
fixed-fixed column under uniform dead compression. It extends the earlier
[cantilever supplement](isae-st6-column-supplement-20261103.md), but remains an
analytical verification. The original ST-6 archive contains no attributable
ASWING numerical solution; its five Euler curves use `K=0.5` in `Analysis.m`.

The [literal model](../../examples/fixed-fixed-column-half.asw) represents one
symmetric half of a 2 m column. Its root uses documented `Ground` type 0 and
its midpoint uses type 2, which prevents rotation while permitting translation.
Reflection gives zero transverse displacement and rotation at both full-column
ends. The half has length L=1 m, a 1 kg midpoint mass, EIcc=100 N m² and
EInn=200 N m². The corresponding full-column midpoint mass is 2 kg. Finite
torsional stiffness avoids redundant rigid rotational constraints; extension
and shear are exactly rigid. There is no distributed mass or airflow.

Bank −90 degrees and the half-model tip weight impose the prescribed uniform
compression. This is a device for obtaining the same loaded transverse
equations, not a model of the full specimen's gravity loading or test press.
The first symmetric critical load is

```text
Pcr = pi² EI / L² = 4 pi² EI / (2L)² = 986.960440109 N
```

The separate continuous beam-column reference uses `q=sqrt(P/EI)`:

```text
k(P) = P q / [2 tan(qL/2) − qL]
lambda² = −k(P)/m
k(0) = 12 EI/L³
```

An exact reference for endpoint-average integration replaces the angle qL
inside the tangent with `a_n=2n atan(qL/(2n))`. The separate subtracted qL
remains the physical length factor. Consequently,

```text
Pcr,n = EI [ (2n/L) tan(pi/(2n)) ]²
k_n(0) = 12 EI / [ L³ (1 − 1/n²) ]
```

The verifier checks both bending directions, both members of each modal pair,
and every translation/rotation component. A fresh restored equilibrium checks
the straight base, mass, force/moment balance and full residual. Original
sparse A/M matrices are saved and reloaded for independent multiplication of
all left/right eigenvectors. The four-interval dense control establishes four
finite roots. The larger full-pencil shifted calculations retain their
unclassified total finite dimension; they do not claim a complete spectrum.

Five reference tests pass. These independently solve the four-state boundary
problem for displacement, rotation, moment and transverse force, and check
the zero-load limit, fixed-fixed Euler load, critical shape and stability sign.
No production matrix supplies the analytical references.

The predeclared study uses 48/96 uniform intervals at 0.5 and 1.5 times the
continuous critical load, plus brackets at 0.9999/1.0001 times each grid's exact
critical load. Final continuum and mesh gates are 0.1%; bracket width is 0.02%.
Each job runs serially with one BLAS thread and a 512 MiB address-space cap.
The initial child limit is 90 seconds. Two above-critical attempts exhausted
it: the 48-interval solve had saved its complete result and matrices, and a
verification-only replay finished its checks without another solve. The
96-interval attempt had not saved its matrices and required a 180-second
extension. A diagnostic retry stopped at a tracing-callback signature error;
the corrected callback then completed the identical request. Those unsuccessful
attempts remain recorded. The four previously unrun bracket jobs use the same
180-second resource extension. No physical input or accuracy gate changed.
Sparse matrix storage avoids dense JSON expansion.

| Load / direction | N48 continuum error | N96 continuum error | N48→N96 change |
|---|---:|---:|---:|
| 0.5 Pcr, EI=100 | 0.05542% | 0.01385% | 0.04156% |
| 0.5 Pcr, EI=200 | 0.03267% | 0.008166% | 0.02450% |
| 1.5 Pcr, EI=100 | 0.09295% | 0.02323% | 0.06973% |
| 1.5 Pcr, EI=200 | **0.1256% — fails** | 0.03141% | 0.09417% |

At 1.5 Pcr, the weaker direction has growing/decaying real roots while the
stronger direction remains oscillatory. The four-interval zero-load dense
control differs from the continuum by 3.280%; it passes the exact discrete
reference, not the final continuum gate. All 72 original-pencil left/right
checks pass, with maximum backward error 6.31e-15. All 14,136 displacement and
rotation components pass; maximum normalized error is 2.12e-11. Maximum
scaled discrete-pole error is 3.73e-12. All nine fresh restored bases pass.

| Intervals | Stable lower load (N) | Unstable upper load (N) | Center error versus Euler |
|---:|---:|---:|---:|
| 48 | 987.56673893 | 987.76427203 | 0.07144% |
| 96 | 987.03791256 | 987.23533988 | 0.01785% |

These bracket each mesh's numerical instability threshold, not the continuous
Euler value 986.96044011 N. Their relative widths are 0.02%; the center changes
by 0.05358% between meshes. The final bracket's worst endpoint differs from
Euler by 0.02785%, within the unchanged 0.1% gate.

[Machine assessment](../../artifacts/isae/st6-fixed-fixed-20261104/assessment.json)
retains every case, source/output hash, coarse error and recovery. The saved-only
assessor completed successfully after all child processes reached terminal states.

The traced 96-interval above-critical dispatch took 103.11 seconds. It reached
the first matrix-assembly progress event at approximately 74.92 seconds and
finished assembly 26.25 seconds later. The earlier interval includes a small
amount of verifier setup. Stack samples locate substantial work in the cold
equilibrium's grouped structural Jacobian. This identifies a concrete next
performance investigation; it is not a measured speedup or evidence of an
incorrect equilibrium. The source structural class disables the separate
analytic-mechanics path, so merely enabling the frequency geometry flag would
not address this grouped-Jacobian work.

This scope excludes antisymmetric modes, distributed-mass modes, post-buckling,
the actual experimental fixtures and native ASWING agreement. The new example
has not been run in the browser. No production solver equation changes here.

To run a single case in a new directory:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  timeout 90s prlimit --as=536870912 -- .venv/bin/python \
  scripts/verify-fixed-fixed-column.py /tmp/fixed-column \
  --intervals 96 --ratio 1.5
```
