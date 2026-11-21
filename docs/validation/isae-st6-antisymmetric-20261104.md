# ST-6 antisymmetric fixed-fixed column supplement

**11/11 analytical cases,
4/4 final pole/mesh comparisons and 2/2 offline browser cases pass.**
The browser completes 426/426
harness checks. This extends the
[symmetric supplement](isae-st6-fixed-fixed-20261104.md) to the antisymmetric
subspace of an ideal fixed-fixed column. Original fixtures and native ASWING
agreement remain unverified.

The [literal example](../../examples/fixed-fixed-column-antisymmetric.asw)
uses a massless 1 m half-column, EIcc=100 and EInn=200 N m², and unit midpoint
bending inertias. Its midpoint has zero transverse displacement and free bending
rotation. Reflection gives a 2 m fixed-fixed column with 2 kg midpoint mass and
2 kg m² midpoint bending inertias. The first antisymmetric instability is a
higher buckling mode: the full column already has the lower symmetric threshold.
Stability labels here refer only to the represented antisymmetric subspace.

Documented Ground type 0 fixes the root. A pinned Joint connects the midpoint
to a massless guide beam grounded at its other end. Zero bending/shear compliance
provides exact transverse restraint; finite axial stiffness permits axial motion
without initially carrying compression. A fresh physical residual checks the
full prescribed compressive resultant in the column and zero guide preload.
Increasing guide EA from 1000 to 10000 N changes the checked pole magnitudes by
at most 0 relatively. No large penalty
stiffness or undocumented support type is introduced.

The independent reference solves `w'=theta`, `EI theta'=M`,
`M'=-P theta-F`, `F'=0` with `w(0)=theta(0)=w(L)=0` and `theta(L)=1`.
For `q=sqrt(P/EI)`, `a=qL`, its endpoint rotational stiffness is

```text
k_theta = EI q [sin(b) - a cos(b)] / [2(1-cos(b)) - a sin(b)]
lambda² = -k_theta / J
b = a                              (continuous beam)
b = 2n atan(a/(2n))                 (endpoint-average integration)
```

The zero-load limits are `4 EI/L` and
`(EI/L)(4-1/n²)/(1-1/n²)`, respectively. The continuous antisymmetric Euler
root obeys `tan(a)=a`, with `a=4.493409457909064`. Six formula tests compare
these closed forms and shapes against a separately solved four-state transfer
problem, including a continuous matrix exponential and the instability signs.
No production matrix supplies the reference.

| Final case | EI (N m²) | Pole error versus continuum | Change from preceding mesh |
|---|---:|---:|---:|
| n128-half | 100 | 0.00905% | 0.02714% |
| n128-half | 200 | 0.00422% | 0.01266% |
| n192-over | 100 | 0.03541% | 0.04424% |
| n192-over | 200 | 0.01202% | 0.01502% |

The final meshes are N128 below and N192 above the antisymmetric threshold.
All four errors and changes satisfy the unchanged 0.1% gate. The original
N64→N128 above-critical weak-axis comparison fails the mesh gate and remains
recorded; N64 continuum errors there are 0.3178% and 0.1081%. The dense N4
zero-load control differs from the continuum by 2.470%, while passing the exact
discrete reference and establishing four finite roots. Larger runs verify the
four requested roots without claiming their Arnoldi count is a full-spectrum audit.

The N128 critical-load bracket is **2019.30622424–2019.71012588 N**,
versus the continuous **2019.07285564 N**. Its center is
0.02156% high and its relative width is 0.02%.
The worst endpoint differs from the continuous value by
0.03156%, within the 0.1% gate.
This brackets the discrete instability; both endpoints lie above the continuous
threshold.

All 88 independent full-pencil left/right checks
and 22,800 displacement/rotation component checks pass.
Maximum scaled discrete-pole error is 2.18e-12; normalized shape
error is 3.53e-11; pencil backward error is 1.4e-14.
Every case restores and checks a fresh straight equilibrium, total mass,
force/moment balance and the actual axial preload distribution.

Two N16 cases run through the built application's real offline WASM worker.
Full bases, physical modal outputs, both eigenvector sides, instability labels,
desktop/mobile plots and exact project/result save-reopen pass. The browser
harness now normalizes at a shared nonzero displacement or rotation component;
the old last-node displacement convention cannot normalize a grounded guide.
Production kernels are unchanged; the existing build's kernel hashes are checked.

Jobs run serially with one BLAS thread and a 512 MiB address-space cap.
The main jobs use 90-second limits; the separately declared N192 refinement uses
180 seconds. An initial invalid two-interval guide request and a subsequent
verifier indexing error are retained. The completed dense result from the latter
was verified from saved matrices without another solve. No physical equation or
acceptance threshold was changed to recover those attempts.

[Portable numerical results](isae-st6-antisymmetric-20261104.json) retain the
gates, coarse comparisons and evidence hashes. Raw matrices, full vectors,
requests, browser exports and screenshots are in
`artifacts/isae/st6-antisymmetric-20261104/`. The new reusable verifier is
`scripts/verify-antisymmetric-column.py`. Distributed-mass buckling,
post-buckling and original ISAE fixture reconstruction remain outside this check.
