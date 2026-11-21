# Frozen K/F scalar oracle for straight SA-1

The independent saved-field replay finds **no operator defect** in the six frozen straight-wing states. It uses only retained circulation, literal model constants and scalar Biot–Savart integrals. No production module is imported and no circulation equation is solved. [The receipt](report.json) pins the original inputs, current code, prospective protocol and complete [replay results](replay.json). All 123 kernel pins still match the frozen protocol.

Actual freestream and lift axes remain `e=(cos(alpha),0,sin(alpha))` and `l=(-sin(alpha),0,cos(alpha))`. The influence wake points along fixed body x. Bound and force points are `(c/4,y,0)`; control points lie another `h=c*a0/(4*pi)` downstream. For an interval `a..b`, the independent scalar velocity per circulation is

```
w(d) = [(1+hypot(d,y-b)/d)/(y-b) - (1+hypot(d,y-a)/d)/(y-a)] / (4*pi)
w(0) = [1/(y-b) - 1/(y-a)] / (4*pi)
```

Summing with retained Gamma gives body-z induced velocities `w_hv` and `w_cp`. Consequently `V_hv=(U*cos(alpha),0,U*sin(alpha)+w_hv)` and control-point tangency is `U*sin(alpha)+w_cp`. Section speed is the norm of that actual relative velocity. Eqs67/70 then give lift `rho*Gamma*(-V_z,0,V_x)*ds` and profile force `rho*c*(.5*(Cdf+Cdp)*|V|+2*tangency²/|V|)*V*ds`. Eq72 gives the section pitching couple `-c/4*lift_z`; the total moment also includes the beam-position moment of the complete force.

For the fixed wake, `w_Trefftz=2*w_hv`, `CLi=2*sum(Gamma*ds)/(U*S)` and `CDi=-2*sum(Gamma*w_hv*ds)/(U²*S)`. Projecting physical circulation force onto the actual axes gives:

```
CL_circulation = CLi - sin(alpha)*CDi
CDi_near       = cos(alpha)*CDi
Cm             = -cos(alpha)*CLi/4
```

These differ from the wind-aligned identities and hold in all six saved states. The maximum discrepancies are 4.57e-13 m/s in local velocity, 2.96e-14 in normalized residual, 9.10e-13 N in total force, 2.37e-12 in total moment, 3.76e-12 m/s in infinite-wake velocity and 6.11e-15 across reconstructed coefficients. Five [scalar checks](oracle-tests.py) passed, including direct integration of the bound line and both infinite rays, force identities and reflection.

One interpretation boundary remains. The theory's section4.6 and the guide's K/F entry explicitly freeze influence functions at zero angles. Section8.1 does not separately specify the historical exporter axes under that switch. The current result reports a zero-angle fixed-wake diagnostic; this oracle checks that declared convention. The projection of its transverse-force vector onto actual lift axes is retained separately, without claiming that it is the original ASWING output definition. No native reference checks are promoted by this replay.

Reproduce with the [oracle](oracle.py), supplying all six `row*-frozen-n*-k0.json` files via `--input` and a new path via `--output`. Existing receipts are never overwritten. Primary source pages, exact excerpts and hashes are retained in the JSON.
