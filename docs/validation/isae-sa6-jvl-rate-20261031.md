# SA-6 rotation-rate comparison with JVL source

2026-10-31. JVL's optional forces on the on-wing portions of trailing vortex
legs cannot explain the remaining SA-6 pitch-rate discrepancy. A scalar audit
of all **88 saved states and 8,624 strips** finds exactly zero additional force
and moment for normalized pitch rate. Transplanting that term would instead
spoil all 88 currently passing `CYp` comparisons. No production equation,
setting, reference value or acceptance count changes.

## Source comparison

The retained upstream [JVL 2.16 provenance](../../reference/third_party/jvl/DOWNLOAD_PROVENANCE.json)
and [2.20 provenance](../../reference/third_party/jvl/versions/2.20/DOWNLOAD_PROVENANCE.json)
identify the downloaded source archives. The verifier checks the archive hashes
and exact bytes of all four inspected source files. No JVL executable is built
or run here.

In both versions, the surface flow-tangency assembly in `src/jsetup.f` uses
local onset velocity `Vbar − Wbar × (r − rref)` at the control point, with
explicit derivatives of that cross product. The bound-vortex force assembly
uses the same kinematics at the vortex midpoint and differentiates both
circulation and velocity in `rho Gamma (V × dl)`. Those mechanisms agree with
the corresponding published ASWING kinematics and bound-force formulation;
this does not establish complete solver equivalence.

The `fstall` expressions in these two `jsetup.f` files occur in **comments**,
not executable surface stall-leakage equations. They cannot corroborate a
particular ASWING leakage Jacobian. JVL's separate `cdcl.f` drag polar is not
ASWING's equations 202–204.

JVL's `ltrforce` branch adds forces on the trailing-leg portions between each
bound-vortex endpoint and the trailing edge. See
[2.16 `jsfforc.f`](../../reference/third_party/jvl/src/jsfforc.f), starting at line 841,
and [2.20 `jsfforc.f`](../../reference/third_party/jvl/versions/2.20/src/jsfforc.f),
starting at line 513. ASWING's surface forces are instead specified by the
steady technical description's equations 67 and 70, with moments in 72.
The JVL option is examined only as a possible explanation, not adopted.

## Cancellation and independent check

This audit covers the existing, separately qualified frozen-influence /
strength-20 comparison: four aileron models, eleven controls, two meshes.
For each saved straight-wing horseshoe, the bound endpoints have equal x/z,
the chord is constant, and the two trailing legs lie along x. Freestream and
pitch-induced velocity are in the x/z plane. Corresponding points on the legs
therefore produce opposite y-directed forces. Their moment arms differ only
in y, so their moments also cancel. This holds for arbitrary circulation and
its pitch-rate derivative, including nonuniform stalled loading.

The audit evaluates JVL's midpoint force/moment prescription on every pair.
Individual leg responses are nonzero, while each six-component pair sum is
exactly zero. The cancellation also holds under exact integration along the
legs; it is not caused by midpoint quadrature.

As a nonzero control, normalized roll rate produces a spanwise gradient in
vertical onset velocity. The hypothetical extra side-force derivative is

```text
delta CYp = rho (2 U / b) cos(alpha) (3 c / 4) integral(Gamma dy) / (q S)
```

It ranges from **+0.193977 to +0.292462**, whereas every native `CYp` is zero.
An independent closed-form reconstruction agrees with the pair accumulation
within **5.00e−16**. The verifier checks all 44 original native tokens, retained
input/result hashes, geometry assumptions, and unchanged comparison gates.
No parameter is fitted, no ASWING target is replaced, and no new solve is used.

Evidence: [audit and per-state receipt](../../artifacts/isae/sa6-jvl-rate-audit-20261031/receipt.json),
[independent verification](../../artifacts/isae/sa6-jvl-rate-audit-20261031/verification.json),
[replay script](../../artifacts/isae/sa6-jvl-rate-audit-20261031/audit.py).

The qualified state comparison remains **2,780/3,168**, including **282/528**
pitch-rate outputs. The native local stall/rate response remains unresolved.
Registered SA-6 and all other case counts remain unchanged. Browser testing
remains suspended after the UserLAnd disconnects; this audit uses only serial
standard-library Python file reads and scalar arithmetic.
