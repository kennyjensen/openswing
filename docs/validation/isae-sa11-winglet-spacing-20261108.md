# SA-11: redistributing winglet nodes

2026-11-08 UTC. **Uniform spacing with 16 or 32 intervals per winglet produces
complete rigid-aerodynamic results, including pitching moments, with all five
compared quantities within 3% of the archived alpha-1° values.** This is useful
progress beyond the previously rejected states. The main wing stays at 32
intervals; neither the geometry nor the zero-core prescription changes.

A 64-interval result is not required to accept a matching 32-interval comparison.
The finer runs measure sensitivity, not an additional native-reference pass
criterion. They show a limitation: uniform spacing again reaches local Mach ≥ 1
at 64 and 128 winglet intervals. This does not invalidate the measured 16/32
agreement, but prevents claiming mesh convergence or a general junction repair.

The subsequent [fixed-uniform32 polar comparison](isae-sa11-uniform-polar-20261108.md)
now covers all 0°–5° archived rows at 240/272 m/s: 31 of 42 points match all
seven outputs, while eleven higher-load points still reject local Mach.
This spacing study itself covers one upper-winglet input alternative at one
angle and speed, not the full SA-11 suite. No primary fraction or comparison
scope changes; SA-11 remains **163/9,184 at 5%**.

## Setup and source interpretation

The [authoritative reference index](aswing-authoritative-references.md) and its
checksummed catalog were consulted. Drela's user documentation, **Physical
index**, prescribes zero mutual core for beams in one physical surface and warns
about nearby wake/control-point encounters. Steady **Eqs. 64–74** define section
velocity, forces and moments; **Eqs. 150–161** describe discretization and vortex
influences. Section moments use local normal Mach, not the global PG Mach.

This uses the disclosed **report-minus4** upper-winglet input from the earlier
[incidence study](isae-sa11-angle-response-20261108.md): the Part I report gives
−4° upper-winglet twist while the archived input gives +4°. The prior Joint
scaling correction is retained. These setup differences remain explicit; the
exact model and mesh that produced the archived output are not authenticated.

All cases use alpha 1°, speed 240 m/s, density 1.2256, sound speed 340.21,
global PG Mach 240/340.21, frozen influences, original section properties,
shared physical index 1 and zero mutual core. The current whole-beam Glauert
receiver rule and every aerodynamic equation remain unchanged.

Before solving, twelve cases were declared: 16/32/64/128 intervals per winglet
under cosine clustering at both ends, uniform spacing, or tip clustering
`f(u) = sin(pi*u/2)` from root to tip. The retained main-wing mesh is identical
in every case. The 16-interval cosine control exactly reproduces the earlier
circulation, section velocity and section CL. Winglet root and tip endpoints
remain fixed. Redistributing interior nodes changes filament and receiver
locations; it does not relocate a core independently of its vortex or move the
root wake away from the physical wing tip.

## Successful comparisons at the tested point

The target is row 4 of `wingtip_up_Ma_0_70.txt`: CL 0.336959, raw CD 0.0103591,
CDi 0.00445428, Cm about the origin −0.469163, efficiency 1.20987. The paper's
plotting allowance of 0.0064 is not added. Errors below are signed percentages.

| Winglet spacing | Intervals per winglet | CL error | CD error | CDi error | Cm error | Efficiency error | Maximum normal Mach |
|---|---:|---:|---:|---:|---:|---:|---:|
| Uniform | 16 | −0.432% | +1.843% | +0.725% | −0.425% | −1.686% | 0.612 |
| Uniform | 32 | −0.473% | −0.697% | +0.970% | −0.444% | −2.113% | 0.733 |
| Clustered toward tip | 16 | −0.351% | +2.948% | +0.045% | −0.292% | −0.814% | 0.618 |
| Clustered toward tip | 32 | −0.390% | +0.367% | +0.474% | −0.313% | −1.427% | 0.759 |

All four rows are accepted production solutions, with finite section moments.
Uniform 16/32 gives `Cm_origin = −0.46716802 / −0.46708128`. Both spacings meet
the user's 5% allowance for every quantity compared here. They remain separately
labeled diagnostics because the primary suite retains its declared inputs and
mesh repeats, and because the full polar has not been checked with this spacing.

## What refinement shows

| Intervals per winglet | Cosine maximum normal Mach | Uniform maximum normal Mach | Tip-clustered maximum normal Mach |
|---|---:|---:|---:|
| 16 | 1.534 | 0.612 | 0.618 |
| 32 | 5.395 | 0.733 | 0.759 |
| 64 | 20.781 | 1.059 | 1.155 |
| 128 | 81.738 | 1.812 | 2.079 |

![Winglet spacing, local Mach and surface drag error](../../artifacts/isae/sa11-winglet-spacing-20261108/winglet-spacing.svg)

At 16 intervals, uniform spacing puts the first root receiver 3.340 mm from
the main-wing wake ray, compared with 0.506 mm for cosine spacing. At 32 uniform
intervals it is 1.657 mm away. At 64/128 it approaches to 0.825/0.412 mm, and
the strong root velocity returns. These very large calculated velocities are a
near-filament sensitivity of the present model, not a prediction of physical
supersonic flow around this winglet.

Tip clustering moves the worst velocity to the tip. Its summed wake-induced
speed rises approximately 88/173/342/680 m/s as intervals double; the bound
contribution stays about 1.56 m/s. It therefore trades one close encounter for
another. Uniform spacing provides a useful moderate-resolution candidate
without changing geometry or introducing a fitted vortex-core size. No default
is changed by this study, and no undocumented native spacing is asserted.

Open markers in the plot denote rejected states. Their CD is a formal sum of
finite surface-force terms; their complete pitching moment is unavailable.
Filled markers denote accepted results. The main wing is held fixed throughout,
so these runs are not a whole-aircraft mesh-convergence study.

## Verification and retained evidence

All twelve jobs completed normally, one at a time with one BLAS thread,
512 MiB address-space, 15-second CPU and 25-second wall limits. Process times
were 2.21–2.98 seconds, with peak RSS at most 236.16 MiB. Circulation residuals
were below 1.79e-13 and every section stayed at least 24.43 configured stall
widths inside its limits. Neither stalled sections nor incomplete circulation
convergence explains these changes.

Independent field reconstruction matches production velocities within
2.92e-11 m/s. Scalar projections reproduce force totals; Trefftz replay matches
accepted CDi and efficiency. Source, model, mesh and result hashes are checked.
No browser, build, Vite or background solver job was launched.

- [Preparation, single-case driver and verification](../../scripts/verify-sa11-winglet-spacing.py).
- [Predeclared cases, references and source hashes](../../artifacts/isae/sa11-winglet-spacing-20261108/plan.json).
- [All twelve verified results](../../artifacts/isae/sa11-winglet-spacing-20261108/analysis.json).
- [Unchanged diagnostic model](../../artifacts/isae/sa11-winglet-spacing-20261108/model.asw).
- [Uniform 32 mesh](../../artifacts/isae/sa11-winglet-spacing-20261108/uniform-32-mesh.json) and [accepted solution](../../artifacts/isae/sa11-winglet-spacing-20261108/uniform-32/accepted.json).
- [Plot PNG](../../artifacts/isae/sa11-winglet-spacing-20261108/winglet-spacing.png), [plot generator](../../scripts/plot-sa11-winglet-spacing.py) and [plot provenance](../../artifacts/isae/sa11-winglet-spacing-20261108/plot-provenance.json).
