# Independent frozen-influence stall reference

2026-11-07. An independent infinite-wing solution agrees with OpenSwing's
frozen and wind-aligned stall calculations, including upper/lower transitions
and analytic control/incidence derivatives. This closes a missing equation
check; it does **not** resolve the SA-6 native-output discrepancy. Its static
score remains **470/528** and its separate F1 score remains **370/528** at 5%.
No production equation, stall parameter or acceptance tolerance changed.

## Reference construction

The local ASWING Technical Description, equations 155–159 and 202–204, gives
the sampling positions, rotated section normal and smooth leakage law. Let
`a` be flight incidence, `t` the combined physical twist, zero-lift rotation
and control rotation, `a0` the lift slope and `c_l` the circulation coefficient.
For a uniform infinite wing the scalar circulation equation is

```
a0 sin(a+t) - c_l cos(phi) - Ks f(c_l) = 0
phi = t       for frozen influences
phi = a+t     for wind-aligned influences
f(c_l) = w [softplus((c_l-CLmax)/w) - softplus((CLmin-c_l)/w)]
```

Its derivative with respect to `c_l` is strictly negative on the tested
domain, so a bracketed scalar bisection gives the unique root. The standalone
[reference](../../scripts/section_stall_reference.py) uses only Python's
standard library; it does not import OpenSwing's geometry, vortex, stall or
derivative routines. Control and incidence derivatives follow implicit
differentiation of this scalar equation. Reported state derivatives include
transport into the fixed base stability axes used by OpenSwing's API.

Pressure drag follows the published normal-flow expression. Pitching moment
uses the **physical chord arm in equation 72**, which differs from the
wind-directed sampling point in equation 155. The initial reference confused
these arms and failed its moment checks. Correcting that derivation resolved
the failures without modifying OpenSwing or loosening the gates. The original
reference files are retained under `initial-reference/` in the evidence folder.

## Results

The [reproducible driver](../../scripts/verify-frozen-stall.py) uses twist 4°,
zero-lift rotation 3.7°, incidence 12°, slope 5.77, CLmin −0.4, CLmax 1.4,
Ks 40, width 0.05 and control slope 0.071. Six uniform control settings
(-44, -40, -32, 0, 4, 44) cover both transitions in each influence mode.
Aspect ratios 5,900, 59,000 and 590,000 approach the independent infinite-wing
limit; these are synthetic equation checks, not substitutions for SA-6 decks.

| Quantity | Observed result | Required gate |
| --- | ---: | ---: |
| Final-span CL/CD/Cm maximum absolute error, 36 comparisons | 3.444e-6 | < 1e-4 |
| Final-span control/incidence derivative maximum absolute error, 72 comparisons | 1.237e-5 | < 1e-4 |
| Error reduction for each tenfold span increase, 24 ratios | 9.96–10.09 times | > 5 times |
| Maximum circulation residual, 36 states | 1.139e-13 | ≤ 1e-8 |

All 14 new regression tests pass. The existing stall-parameter study now
explicitly selects wind-aligned influences, preserving its published reference
after the application default changed; its archived result files are untouched.
The general stall regression covers both influence modes at 25° and 35°.
It retains its lift-reduction and pressure-drag gates and checks the strip
flag against the model's actual lift limits. Smooth stall affects loads before
that flag becomes true. At 25° the frozen rectangular wing reaches only
`c_l=1.19893` against CLmax 1.2, while still showing substantial pressure drag;
at 35° both modes cross the limit. All four revised cases pass; the other 75
existing aero/stall tests passed in the preceding run.

The packaged Pyodide/WASM kernel also passes four endpoint cases (±44 in
both influence modes): all 36 coefficient/derivative comparisons agree with
native Python within 1.555e-15, below the 2e-9 parity gate. They independently
pass the same 1e-4 reference gate. The runner verifies packaged module bytes
against current sources before executing; this is kernel verification, not
a new full browser-interface test.

![Independent section curves and convergence](../../artifacts/isae/frozen-stall-reference-20261107/section-reference.svg)

Evidence: [native frozen results](../../artifacts/isae/frozen-stall-reference-20261107/frozen.json),
[native current results](../../artifacts/isae/frozen-stall-reference-20261107/current.json).
[WASM results](../../artifacts/isae/frozen-stall-reference-20261107/wasm.json)
and the [execution receipt](../../artifacts/isae/frozen-stall-reference-20261107/verification.json)
retain the corresponding checks.
Each file pins the reference and production sources. Jobs run serially with
one BLAS thread. These checks support the implemented section equations;
they do not establish the original SA-6 startup settings or isolate every
finite-span wake/control interaction. The remaining task is to find a
source-supported explanation of the native rolling-moment and sensitivity
differences without fitting stall strength to the reference outputs.
