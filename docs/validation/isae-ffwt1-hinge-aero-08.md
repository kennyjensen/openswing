# FFWT-1 hinge aerodynamics and one archived ASWING point

Updated 2026-10-15. This is a conditional validation study of integrated08;
production code, app defaults and accuracy gates are unchanged. FFWT-1 remains
pending. ISAE coverage remains **17 partial / 24 pending / 0 fully validated**.
The user has no original ASWING executable; this study uses archived output,
published equations and independent mechanical/geometry checks.

## What the source audit establishes

The implemented steady vortex and force-point construction agrees with
Drela's steady equations 155–157: its chordwise offsets follow the flow vector
divided by the magnitude of its cross product with the local span tangent.
They are generally different from material quarter-chord points after folding.
The separate force/moment transfer correctly uses the material chord direction
in equation 72. Replacing these with material quarter-chord vortex positions
would change the documented formulation.

Equations 62 and 153 permit piecewise-constant circulation. The inspected
sources do not specify an additional equality of circulation across this
hinge, or a free-end zero-circulation equation missing from the current panel
system. Every panel horseshoe already closes through its endpoint wakes.
A square sine basis with one mode per panel, when nonsingular, is an alternative
representation of the same discrete unknowns; truncation changes that problem and does not itself remove the
near-wake singular behavior documented in the [static study](isae-ffwt1-static-08.md).
All archived beams have physical index 1, for which the guide specifies zero
mutual core. Exact original executable endpoint treatment remains unverified.

The guide documents K/F as a distinct approximation that freezes influence
geometry at the undeformed jig and zero incidence/sideslip. Its example K-menu
display shows it enabled, but none of the 30 archived command scripts specifies K/F.
The scripts' NODE I requests are structural grid counts, not Fourier orders.
Realized meshes, circulation orders and startup settings remain unknown.

An earlier reduced-reference review incorrectly said a new frozen cache would
retain the posed geometry. Source inspection shows `FrozenInfluences` recovers
the undeformed jig even when constructed from posed meshes. The original review
is retained with an explicit correction in the evidence.

## Explicit frozen-influence calculation

This calculation enables the documented approximation without changing its
default. It uses the previously checked two-angle rigid mechanical reference,
the same reconstructed Flare30 input, true speed 22 m/s, alpha/beta zero and
level body gravity. It shares the production aerodynamic kernel and is not an
independent aerodynamic solver or a browser performance benchmark.

| Main / each tip intervals | Port physical fold (degrees) | Circulation residual | Local root time (s) |
| --- | ---: | ---: | ---: |
| 50 / 20 | −10.8511497862 | 8.39e−16 | 0.34 |
| 100 / 40 | −10.8409944778 | 8.39e−15 | 0.86 |
| 200 / 80 | −10.8363032505 | 5.34e−14 | 3.74 |
| 400 / 160 | −10.8355546830 | 1.72e−13 | 21.85 |

All four nominal roots meet the unchanged 1e−12 circulation and 1e−12 N m
torque gates. Successive angle changes shrink, but this is not a rigorous error
bound. At 100/40/40, enabling K/F changes port physical fold by +0.162804° from
the updated-geometry root. It does not resolve the earlier nominal experimental
discrepancy. Four cache-reuse checks across prescribed speed/pose inputs, including a repeat,
show exact array equality of circulation and torques with newly constructed
caches. The raw field named `gamma_and_torque_byte_equal` overstates the check:
`assert_array_equal` establishes element equality, not general byte identity.

The hanging-start calculation accepts its zero-speed root near −89.9975°.
Every positive-speed trial, from 2 down to 0.001953125 m/s, fails the inner
circulation continuation. The next step would violate the chosen 0.001 m/s
minimum interval. The 146.37-second study therefore ends incomplete with all
failures retained, below its 300-second cap. There is no demonstrated connection
to the 22 m/s root, return branch or hysteresis result. Failure of this procedure
does not prove absence of a physical branch.

## Comparison with one preselected archived output row

The original `Aswing_simulation/FFWT_Flare30_V22.txt`, data row 7 (file line 10),
reports port sensor **Phi[2] = −9.82052°**. The associated script requests
alpha **−0.1693206313886364°** and indicated speed **22 m/s**. Its printed
**alpha[2] = +5.59330°** is a local sensor flow angle, not the global incidence.
Phi is the sensor bank angle; physical hinge fold is a different observable.

The following calculations assume the requested global incidence was achieved,
sea-level density makes true speed 22 m/s, beta is zero, and body/Earth attitude
is level. They use the explicit reconstructed input and 100/40/40 mesh. Each
starts from the already computed zero-incidence root with the same influence
option. Neither the archived angle nor an experimental angle is used as a seed
or fitting target. Rates, accelerations, controls and other settings use the
recorded calculation defaults; their archived values are unproven.

| Observable | Archived ASWING | Updated influences | Frozen influences |
| --- | ---: | ---: | ---: |
| Port sensor bank Phi[2] (degrees) | −9.820520 | −9.921147 | −9.765875 |
| Bank difference from archive (degrees) | — | −0.100627 | +0.054645 |
| Wind-normal aerodynamic Lift (N) | 1.928940 | 1.914078 | 1.926448 |
| Lift difference (%) | — | −0.7705 | −0.1292 |
| Root Mc′[1], left trace (N m) | −0.471843, trace unknown | −0.474310 | −0.472161 |
| Root Mc′[1], right trace (N m) | same trace ambiguity | −0.474358 | −0.472161 |
| Port local alpha, full airflow (degrees) | 5.593300 | 5.528820 | 5.446758 |
| Port local alpha, kinematic flow (degrees) | convention unknown | 5.514264 | 5.426695 |
| Port physical hinge fold (degrees) | not printed | −11.418322 | −11.240759 |

Both roots pass: circulation residuals 4.75e−13 and 2.16e−14, maximum torque
imbalance below 2.65e−16 N m. Re-evaluation with correctly deformed sensor
positions preserves forces/moments exactly and passes the same circulation
gate. The local solves plus sensor postprocessing take 5.25 and 0.85 seconds; the complete
two-case harness takes 6.79 seconds. These reduced calculations do not measure
the general full-network solver or browser load/solve time.

Lift uses equation 185's freestream-normal projection and excludes gravity.
Root Mc′ is the internal moment about the local beam c axis at sensor 1,
coincident with the ground support; here Nta is zero, so Mc′ equals Mc.
An independent sum of external aerodynamic and gravitational wrenches reproduces
both saved nominal structural moment traces within 3.89e−16 N m and forces
within 8.89e−16 N. It then computes both traces at the archived incidence without
another aerodynamic or structural solve. Updated-influence Mc′ differs from the
archive by −0.002467 / −0.002515 N m (left/right), and frozen by about
−0.000318 N m on either side. The archive's trace convention is unknown; neither
side is selected by agreement. A first control-harness status-label error is
retained separately; the corrected control passes.

Both implemented sensor-flow conventions are reported because the archive
does not establish the original sensor-flow setting. Missing producing model
bytes, global operating state, startup constraints, branch, mesh, circulation
order and K/F prevent attributing the remaining differences to a particular
implementation. This point cannot identify the archived K/F setting or establish
ASWING parity. It is not a matched experimental accuracy result.

## Independent finite-chord geometry preparation

A separate geometry-only reference implements the primary study's oblique,
shared hinge edges and trapezoidal panels, using its 1 m span and 0.078 m chord.
All 90 geometric controls pass: flat coverage is 0.078 m², hinge vertices remain
coincident to 5.56e−17 m, rigid lengths to 8.33e−17 m, and rotated coordinates
agree with a separate quaternion construction to 1.12e−16 m. A preview and all
90 geometry arrays are retained.

This is preparation for an independent finite-chord reference, not an
aerodynamic validation result. It has no vortex-ring assembly, circulation
solve or force calculation. Half-chord hinge datum, chord/span grid blending,
and exact 30° versus rounded archive axes remain explicit assumptions. The
primary formulation's complete vortex-ring geometry and trailing-edge wake,
quarter/three-quarter panel convention checks, aerodynamic controls and
refinement remain to be implemented before comparing loads or equilibria.

## Evidence and remaining work

The [machine-readable index](isae-ffwt1-hinge-aero-08.json) pins the source
reviews and calculation outputs. The [selected evidence ZIP](isae-ffwt1-hinge-aero-08-evidence.zip)
includes the integrated08 kernel, inputs, retained attempts, independent
controls and report builder. Its [verification record](isae-ffwt1-hinge-aero-08-evidence.json)
describes the clean extraction checks; it is not a complete historical FFWT
archive or a fresh replay of every solver run.

Remaining work includes mesh/branch convergence for updated influences,
comparison of complete curves under documented assumptions, a checked
independent finite-chord aerodynamic reference, matched experimental setup,
and dynamic response/stability. The current app and previously audited app
downloads retain their prior contents; they have not been rebuilt for these
additional validation documents.
