# SA-6 mesh evidence from native apparent inertia

2026-10-31. The archived apparent-inertia tensors constrain a spanwise
integration moment, but do not recover a unique native mesh. A compatible
40-interval modified-cosine candidate gains five sampled derivative matches
and loses two, both in pitch rate. It does not resolve the discrepancy.
Production equations, defaults, reference values and registered counts remain
unchanged. This is a diagnostic under the previously qualified frozen-influence,
stall-strength-20 settings; those native settings remain unverified.

## Evidence independent of circulation

All four paired source decks have a straight rigid span of 1.524 m, constant
0.254 m chord, constant 4° physical twist, and zero moment reference. Their
44 native `.fmat` exports contain the apparent-mass and apparent-inertia
tensors. Drela's Technical Description, equations 247–256, gives a normal
section added mass proportional to chord squared and a separate intrinsic
inertia along the span axis. Under this literal geometry,

```
Qy = Ixx / Mzz = Izz / Mxx = -Ixz / Mxz
   = sum(ds_i * y_i^2) / span
```

The intrinsic spanwise inertia does not enter these three ratios. Preserving
half a unit of each tensor token's last printed digit, their common interval is
**0.1933666268591901 ≤ Qy ≤ 0.1934165118131139 m²**. The continuum value
is 0.193548 m². This inference uses printed precision, not the provisional
3% comparison tolerance. The mass components also agree with the literal
chord, span, density and twist within their printed intervals.

The finite search covers nominal counts 4–128, uniform/cosine/modified-cosine
spacing, three choices of mandatory stations, and arithmetic-midpoint,
Glauert-midpoint or trapezoidal sampling. **57 combinations** satisfy the ratio
interval, all using arithmetic-midpoint sampling within this search.
With the source control boundaries inserted, compatible nominal counts are:

| Spacing | Compatible counts |
|---|---|
| Uniform | 32, 33, 34, 35, 36, 37 |
| Cosine | 41, 42, 43, 44, 45, 46, 48 |
| Modified cosine | 37, 38, 39, 40, 41, 42 |

This is a necessary condition under the geometry and quadrature assumptions,
not a unique mesh identification. It also does **not** show that aerodynamic
force sampling should use arithmetic midpoints. Apparent-mass integration
and aerodynamic collocation are separate quantities. Published Glauert
aerodynamic sampling remains in every new solve.

## Eight-case pilot

The predeclared pilot uses all four paired models at controls 4° and 44°.
It changes only the mesh from the saved nominal cosine-128 setup to nominal
modified-cosine-40, with source breaks retained. The resulting mesh has
42 strips. Alpha 12°, speed 20 m/s, zero PG Mach, frozen influences,
stall strength 20, width 0.05, literal section data and pointwise circulation
closure are unchanged. All six static coefficients and all 36 state
derivatives are scored at the existing gates; tiny references keep their
original absolute tolerances.

| Scope | Saved cosine-128 | Modified-cosine-40 | Gains / losses |
|---|---:|---:|---:|
| Static coefficients | 48/48 | 48/48 | 0 / 0 |
| All state derivatives | 253/288 | 256/288 | 5 / 2 |
| Pitch-rate subset | 24/48 | 22/48 | 0 / 2 |

Both losses are `Clq` at 44° control in the 30c and 35c variants. Gains occur
in two `CXp`, two `Cna`, and one `Cla` comparisons. The candidate's failed
pitch-rate checks have these errors; they describe this pilot only:

| Output | Median absolute relative error | Maximum |
|---|---:|---:|
| CXq | 47.18% | 216.77% |
| CLq | 5.20% | 5.31% |
| Cmq | 5.58% | 5.70% |
| Cnq | 55.78% | 161.51% |
| Clq | 3.78% | 4.03% |

The predeclared full-scope extension requires a derivative gain with no
derivative or static losses. That criterion fails. No full sweep or change
to the accepted settings follows from this pilot.

## Verification and runtime

Eight cold bases and eight analytic six-column state responses completed in
one native Python process with BLAS threads fixed to one. The solver calls
took about 1.6 seconds altogether. The process exited with status 0; it left
no background job. No Vite, Chromium or Playwright job was launched.

An independent straight-wing implementation reconstructs the finite-segment
and trailing-ray fields, complete stall residual/Jacobian, section loads,
moments and state derivatives. Maximum coefficient disagreement is
**8.89e-15**, maximum nonlinear residual **4.74e-14**, and maximum circulation
response disagreement **9.06e-14**. Independent rational arithmetic verifies
the native rounding intervals. The composite-midpoint integration identity
reproduces the candidate second moments, and every scored scalar is checked
against its original native token. The actual aerodynamic sample points are
also verified to remain Glauert midpoints.

These checks support the diagnostic's numerical integrity; they do not prove
historical ASWING equivalence. The qualified complete SA-6 result remains
static **528/528**, control derivative **528/528**, state derivatives
**2,780/3,168**. The registered static default remains **290/528**.

Evidence and reproducible scripts:

- [Tensor audit](../../artifacts/isae/sa6-native-mesh-20261031/tensor-audit.json)
- [Predeclared pilot](../../artifacts/isae/sa6-native-mesh-20261031/pilot-plan.json)
- [Completed calls](../../artifacts/isae/sa6-native-mesh-20261031/pilot-terminal.json)
- [Independent verification and every comparison](../../artifacts/isae/sa6-native-mesh-20261031/verification.json)
- [Producer](../../artifacts/isae/sa6-native-mesh-20261031/audit.py),
  [serial pilot](../../artifacts/isae/sa6-native-mesh-20261031/pilot.py),
  [verifier](../../artifacts/isae/sa6-native-mesh-20261031/verify.py)
