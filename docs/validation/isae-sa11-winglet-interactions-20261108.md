# SA-11: localize the remaining main-mesh drag sensitivity

2026-11-08 UTC. **The outer main-wing intervals explain most of the observed
mesh sensitivity.** A prescribed local mesh change reproduces **94.18%** of
the total-drag increment change previously obtained by refining the entire
main wing. It preserves all 28 interior main-wing intervals and both complete
16-interval winglets. This is stronger evidence of localization, not a solver
correction or a convergence result.

The primary paper suite remains **21/48** and the original archive remains
**1,060/9,184**. The following alternatives add no passes to either scope.

[Comparison page](../../public/isae-sa11-paper/wake-interactions.html), served
at `/isae-sa11-paper/wake-interactions.html`, includes the plot and downloadable
data and diagnostic mesh.

## Governing references and fixed conditions

The [authoritative index](aswing-authoritative-references.md) and
[source catalog](aswing-authoritative-sources.json) were consulted; the ISAE
Part I and Drela steady PDF/text checksums were authenticated. Jan **p.35** and
**Figure 22, p.39** motivate the wingtip-device comparison. Drela's **Eqs.55–56**
give conservative load balance; **Eqs.64–70** prescribe the local aerodynamic
force; **Eqs.149–161** define the PG vortex field and receiver construction.
**Eqs.207–211** define the separate Trefftz result.

In particular, Eq.67 uses the velocity at the bound-vortex location. This
investigation retains that rule. No finite-origin wake term is omitted and no
Trefftz-plus-profile replacement is made.

The [same-main-wing control](isae-sa11-same-mainwing-20261108.md) supplies the
models: the disclosed report-derived upper-winglet geometry, and a copy with
only its winglets and Joint block removed. Main-wing section data and geometry
are identical between that pair. The producing historical ASWING input remains
unrecovered; the archived baseline file has different main-wing airfoil data.
Consequently, the historical drag increment is a qualified comparison target,
not proof that the archived pair isolates geometry alone.

All work here uses **240 m/s**, density **1.2256**, PG Mach **240/340.21**,
frozen body-x influences, the physical incidence for drag projection, and the
same original stall/zero-core laws. The minimum arc interval remains
**16.4659927127284 mm**. No post-stall repairs are involved.

## Nine saved-state interaction audits

The audit reuses both valid quarter-degree CL = 0.5 brackets and the common
3° state for the bare/upper pair on the 32- and 62-interval main meshes.
Each ordered receiver/source contribution is evaluated as

```text
CD_ij = rho Gamma_i Gamma_j
        [v_ij × (span_i ds_i)] · flight_direction / (q S)
```

The velocity is separated exactly into finite bound segments, half of the
infinite trailing wake, and the finite-origin remainder. These are accounting
terms; none can be removed merely because it is large. Own trailing legs
remain present, with only the own bound segment excluded as in the source
formulation. Uniform freestream contributes zero drag in this contraction.

The total field agrees with a separate transcription of AVL's zero-core
segment/ray formulas, adjusted only for AVL's rounded inverse-four-pi constant.
This verifies the evaluated field; it is not a new native executable run or
evidence for substituting AVL's core law.

At equal CL = 0.5, the change in upper-minus-bare total CD between the main
32 and main 62 pairs is **+0.0015297253**. Its signed decomposition is:

| Contribution | Fraction of total change |
|---|---:|
| Bound-vortex field | +7.89% |
| Half-infinite trailing wake | +14.54% |
| Finite-origin trailing wake | +78.11% |
| Other strip forces, including profile drag | −0.54% |

The finite-origin **cross-beam** terms alone contribute **+0.0013736040**, or
**89.79%** of the total change. Opposing terms explain why this exceeds the
net finite-origin fraction. Of that signed cross-beam change, **99.83%**
involves a main-wing member within **0.125 m of the projected spanwise tip**.
The binning was an exploratory localization after the complete beam partition;
it is not a new acceptance gate.

Here the ASW parameter `t` equals the projected span coordinate `y` in metres.
The artifact's phrase “material distance” refers to this parameter difference,
**not beam arc length**. The figure and this report use the precise projected
span convention. All signed bins, including small opposing contributions,
remain in the saved analysis.

## Six new local-tip controls

Starting with the original 32 main intervals, replace only the outer two
intervals on each side with the already prescribed finer-grid nodes. The cut
is at approximately **|t| = 1.0413 m**, retaining the inner **28 intervals**
exactly. Thus only the outer **0.2013 m of projected span per side** changes,
enclosing the region identified above. The resulting main wing has **46
intervals**. Both winglet meshes remain exactly unchanged at 16 intervals each.

The six angles were declared before running: bare 3°, 3.25°, 3.5° and upper
2.5°, 2.75°, 3°. They supply valid adjacent CL = 0.5 brackets. All six states
converge, with maximum normal Mach **0.63342** and at least **17.64 stall
transition widths** of margin. Minimum spacing and all retained source,
receiver, chord, length and position arrays pass independent identity checks.

| At 240 m/s, upper minus bare | Archived ASWING | Main 32 | Tip-only 46 | Whole-main 62 |
|---|---:|---:|---:|---:|
| Total ΔCD at CL = 0.5 | −0.002768932 | −0.003794251 | −0.002353586 | −0.002264526 |
| Trefftz ΔCDi at CL = 0.5 | −0.002633414 | −0.002856068 | −0.002625248 | −0.002636424 |
| Total benefit error | — | 37.03% too strong | 15.00% too weak | 18.22% too weak |
| Lift increment at 3° | 0.02750100 | 0.03142177 | 0.02798885 | 0.02831651 |

The tip-only result matches the Trefftz benefit within **0.31%** and the lift
increment within **1.77%**. Its total drag benefit remains **15.00% low**.
The **94.18%** figure describes how much of the earlier mesh-induced change
this local control reproduces; it is not a validation completion percentage.

This supports investigating the local main-tip/winglet coupling rather than
requiring uniform refinement of the winglet or the whole main wing. It does
not establish the correct native mesh, prove a defect in the documented force
law, or justify selecting whichever mesh best matches one target. The minimum
spacing prevents dangerously close horseshoes, but does not itself prove an
accurate integrated drag. The next diagnostic should separate source/receiver
placement from circulation changes on this fixed local geometry.

![Wake interaction and local-tip control](../../artifacts/isae/sa11-winglet-interactions-20261108/wake-interactions.svg)

## Verification and reproducibility

- Nine saved-field audits required **zero new solves**. Their independent
  fields agree within **5.71e−16 of freestream**; scalar pair reductions agree
  within **3.65e−17 in CD**. Main-main operators are identical within each
  fixed-mesh bare/upper pair, and winglet geometry is identical between meshes.
- The six local-tip solves pass the independent velocity, force, moment and
  Mach audit. Maximum circulation residual is **3.73e−16**; independently
  reconstructed velocities agree within **5.77e−16 of freestream**.
- Equal-lift interpolation uses adjacent valid quarter-degree brackets and
  Decimal arithmetic. Force decomposition closes within **1.05e−17 in CD**.
- Each process used one BLAS thread, 512 MiB address space and 15 CPU / 25 wall
  seconds. The longest recorded three-solve batch was **5.08 seconds**, peak
  RSS **284.83 MiB**. No new timeout or rejection occurred.
- An initial preparation rejected the older `COMPUTED_DIAGNOSTIC` status label
  before creating output. Schema recognition was corrected without computing,
  replacing or discarding a physical result. The plot was visually inspected.
- Browser, Vite, build and background solver jobs remain unstarted. No
  production equation, default, primary scope or tolerance changed.

Evidence: [interaction plan](../../artifacts/isae/sa11-winglet-interactions-20261108/plan.json),
[verified accounting](../../artifacts/isae/sa11-winglet-interactions-20261108/analysis.json),
[local-tip plan](../../artifacts/isae/sa11-tip-local-mesh-20261108/plan.json),
[local-tip analysis](../../artifacts/isae/sa11-tip-local-mesh-20261108/analysis.json),
[bare-field verification](../../artifacts/isae/sa11-tip-local-mesh-20261108/verification-wing_alone.json),
[upper-field verification](../../artifacts/isae/sa11-tip-local-mesh-20261108/verification-upper_winglet.json).

Drivers: `scripts/audit_sa11_winglet_interactions.py`,
`scripts/analyze_sa11_winglet_interactions.py`,
`scripts/verify_sa11_tip_local_mesh.py`,
`scripts/analyze_sa11_tip_local_mesh.py` and
`scripts/plot_sa11_winglet_interactions.py`. Plans and report files are created
exclusively; use a fresh output directory for a new observation.
