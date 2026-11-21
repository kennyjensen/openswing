# Flare20 joint aerodynamics and frozen-matrix sensitivity

The mesh sensitivity can be reproduced with a **fixed folded shape and only an
aerodynamic solve**. Structural iteration is therefore not necessary to produce
it. The documented K/F frozen-influence option removes the growing local
velocity, but does **not** resolve the folded-shape moment at the existing 0.1%
mesh limit. These diagnostics do not change production equations, defaults,
native pass counts, or the earlier failed mesh checks.

The original [211-node coupled study](isae-ffwt4-pm2-211-20261107.md) still passes
**0/7** root-moment and nodal-field mesh checks. FFWT-4 native coverage remains
**200/8,000 at 5%**. A 419-node coupled equilibrium has not been computed.

## What produces the local velocity growth

Fresh restoration of all three original 55/107/211-node equilibria reproduces
every saved aerodynamic section velocity exactly. The largest local velocity
occurs on the right tip's first interval next to the main-wing joint.

| Nodes | Maximum section-normal speed | Finite wake-bridge contribution |
| ---: | ---: | ---: |
| 55 | 27.6678 m/s | 3.5600 m/s |
| 107 | 33.5941 m/s | 14.1299 m/s |
| 211 | 47.3730 m/s | 51.5179 m/s |

The main-wing and tip trailing legs start about **0.252 mm apart along the
freestream direction**, although their structural joint positions coincide.
Their origins follow the quarter-chord construction in steady-theory equation
155, which depends on the local span direction. Folding changes that direction.
The component of the origin separation perpendicular to the freestream is
approximately 3e-17 m.

Two collinear semi-infinite rays with different origins do not cancel over the
finite segment between those origins. Independent 64- and 128-point numerical
Biot–Savart quadrature reproduces this finite-segment contribution and the
unequal-circulation remainder to within **9.12e-12 m/s**. At 211 nodes the
finite-segment contribution is 51.52 m/s, while the circulation-imbalance
remainder is only 1.05 m/s. These are vector contributions which partially
cancel other vortices; they are not additive speed magnitudes.

This is not a finite-core crossover: all three literal beams have physical
index 1, so their mutual vortex core is **zero at every mesh**. Although the
raw spacing-limited core values change during refinement, those values do not
apply to these mutual wing influences. Increasing the core or merging the
origins would change the declared aerodynamic model.

The [ASWING guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt),
under **Physical index**, specifies this zero-core treatment and warns about
trailing legs approaching another beam's control points. Our reported maximum
is at the **bound-vortex force point**, so the warning is related evidence,
not an exact description of the sampled location. The force-point and
vortex-origin construction follows equations 67 and 155–161 in the
[steady theory](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf).

## Prescribed-shape controls

The jig control uses the literal undeformed model. The folded control keeps
the main wing undeformed and rotates the two rigid tips about their specified
joint axes by the saved 211-node hinge angles, 40.01215 and -5.63575 degrees.
Each pose is held fixed across all four meshes. Conditions remain speed
22 m/s, alpha 6 degrees, beta 16 degrees, density 1.2256 kg/m³, and Mach 0.
No structural equilibrium is claimed for these controls.

| Nodes | Jig, evolving matrices: peak speed | Folded, evolving matrices: peak speed | Folded, frozen matrices: peak speed |
| ---: | ---: | ---: | ---: |
| 55 | 21.5732 m/s | 27.5916 m/s | 21.4378 m/s |
| 107 | 21.5695 m/s | 33.4719 m/s | 21.4386 m/s |
| 211 | 21.6412 m/s | 47.0016 m/s | 21.4393 m/s |
| 419 | 22.0215 m/s | 99.5108 m/s | 21.4398 m/s |

The moment below sums aerodynamic force moments and section moments on the
negative half-wing about the root. It excludes gravity and is **not the total
mounted sensor moment**. Each difference is normalized by the finer value.

| Mesh pair | Jig, evolving matrices | Folded, evolving matrices | Folded, frozen matrices |
| --- | ---: | ---: | ---: |
| 55 → 107 | 0.23634% | 0.06706% | 0.08146% |
| 107 → 211 | 0.01061% | 0.14443% | 0.13253% |
| 211 → 419 | 0.02838% | 0.16855% | 0.15499% |

Freezing eliminates the large near-joint velocity growth in this control,
but both folded variants remain above 0.1% on the latest moment comparison.
It therefore does not establish mesh convergence or explain every coupled
field difference.

![Prescribed-shape mesh comparisons](../../artifacts/isae/ffwt4-mesh-diagnostics-20261107/frozen-comparison.png)

## Why test K/F, and what remains unknown

The guide's example OPER/K menu displays **F = T**. Its Fast/Slow section
defines the fast option as holding aerodynamic influence matrices at the jig
geometry with zero alpha and beta. Actual flight conditions, local section
frames, circulation and loads remain active. OpenSwing implements this
documented option, while the original Flare20 run used its existing
`freeze_influences=False` default.

The literal `FFWT_Flare20.sh` driver commands alpha 6, beta 16 and speed 22
but never enters K/F. It invokes **ASWING_R_5_92**, whereas the cached guide is
version 5.97. The accompanying aeroelasticity report's FFWT-4 section does
not specify the freeze setting. The displayed menu therefore motivates a
sensitivity study; it does **not authenticate the historical startup value**
or exclude settings restored from an unavailable `.set` file.

In the frozen control, the physical quarter-chord origins still differ by
0.249269 mm. Only the origins used by the frozen influence matrix coincide.
No physical point or joint is moved. The new arm preserves the source,
meshes, poses and solver kernel; only the documented freeze option changes.

## Separate cold coupled equilibrium

A separate 55-node run starts from the unloaded configuration with K/F=True;
it does not reuse an equilibrium from the other setting. It reaches full load
in **19 accepted steps and seven serial jobs**, with zero rejected attempts
and a freshly rebuilt final residual of **5.37654e-13**. All seven solver
processes exit successfully under the same 90-second, 512 MiB, single-BLAS-thread
limits. This result is a converged equilibrium on the coarse mesh, not proof
of spatial accuracy.

| Quantity | Evolving matrices, 55 nodes | Frozen matrices, 55 nodes |
| --- | ---: | ---: |
| Sensor-1 root moment | 0.5445487051 N m | 0.5263612392 N m |
| Error from native initial value, 0.530039 N m | +2.73748% | -0.69387% |
| Right hinge angle | 40.03090 degrees | 50.16402 degrees |
| Left hinge angle | -5.64508 degrees | -4.97956 degrees |

The changed option has a substantial physical effect, including roughly ten
degrees of right-tip fold. Its closer initial moment is evidence of setting
sensitivity, not proof that it reproduces the historical configuration. This
comparison adds **zero native passes** and does not replace either the
unfrozen mesh study or the outstanding full-history checks.

## Evidence and remaining work

All evidence is retained under
`artifacts/isae/ffwt4-mesh-diagnostics-20261107/`. Original reports and helper
hashes are preserved. The principal files are `observations.json`,
`bridge-quadrature.json`, `jig-report.json`, `rigid-fold-report.json`,
`frozen-rigid-fold-report.json`, and their execution receipts. The original
diagnostic summary is `summary.json`; the separate frozen arm is recorded
in `frozen-summary.json`. Plot PNG and SVG files are retained alongside them.
The cold coupled chain and independent boundary assessment are retained in
`frozen-equilibrium-55/`; `job-007/result.json` is the full-load result.
All 139 production kernel modules remain identical to the previously tested
rank-refined archive.

Further coupled spatial refinement and element/circulation-field checks are
still required. The K/F sensitivity cannot be used to select whichever
setting happens to fit the native output. Original startup qualifications,
the rigid-pylon attachment qualification, other PM2 equilibria and gust
histories, the separate Fixed-1 refinement, and shared suite registration
remain open.

## Subsequent frozen-matrix mesh refinement

The [107-node cold refinement](isae-ffwt4-frozen-refinement-20261107.md) now
completes and independently verifies 19 accepted steps, with maximum residual
5.16e-13. Initial native moment error remains 0.687%. The 55/107 pair passes
3/7 mesh gates; main-wing and left-tip field changes remain 0.358–1.044%.
This preserves the K/F qualification and adds no native pass. The separately
planned 211-node frozen run is still required.
