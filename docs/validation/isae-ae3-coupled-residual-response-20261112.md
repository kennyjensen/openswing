# AE-3: coupled response to the omitted circulation residual

Observed 2026-11-12 UTC. The full coupled tangent predicts the previously
measured pointwise/Fourier rolling-coefficient difference within **0.062%**.
The correction is driven mainly by flow errors around the aileron boundaries.
Structural deformation amplifies the fixed-shape response by **3.33×**; allowing
the prescribed net-roll-moment constraint to change roll acceleration adds
another **3.17×**. Their product explains the **10.56×** amplification found
in the [independent field study](isae-ae3-representation-fields-20261112.md).
All **38 checks pass**. **Primary AE-3 remains 434/725**.

## Same physical state, different circulation equations

The accepted 76-mode state is expressed on the identical 328-interval
pointwise mesh. Positions, rotations, internal forces and internal moments
transfer exactly. Physical circulation differs by at most **6.94e-18 m²/s**
in the checked transfer. Projecting the pointwise flow residual back into the
Fourier equations recovers the original full residual within **3.31e-19**.

All non-flow equations remain converged to **1.33e-13**. The newly exposed
pointwise flow residual has maximum magnitude **0.00845**, or **0.5023 m/s**.
Thus the transferred state has the same physical loads and geometry; the
pointwise equations expose the tangency components omitted by the Fourier
projection. It is not accepted as a converged pointwise solution.

The full 4,277-variable Jacobian retains all mechanical, circulation and
roll-acceleration variables. Its action agrees with fresh central differences
of the full residual within **7.73e-10** under the existing directional gate.
Linear-solve residuals are below **2.68e-17**. Output derivatives are checked
at two step sizes. No nonlinear, rank or native-comparison gate is relaxed.

## Where the amplification enters

| Response to the same flow residual | Predicted aerodynamic ΔCl | Amplification from preceding row |
|---|---:|---:|
| Circulation changes; shape and frame acceleration fixed | .000005213716 | — |
| Circulation and structure respond; frame acceleration fixed | .000017376112 | 3.33277× |
| Full coupled response, including roll acceleration | .000055042911 | 3.16773× |
| Independently converged pointwise endpoint minus Fourier endpoint | .000055076845 | Observed comparison |

The predicted coefficient increment differs from the observed increment by
**0.06161%**. The maximum normalized state-increment error is **0.06179%**.
Both satisfy the prospectively declared 5% prediction check. This is evidence
for the response mechanism at this state, not a native ASWING pass.

Taking one full Newton step gives Cl=.000613740785 and reduces the full
residual from .00845 to **1.29e-7**. That residual is still above the original
nonlinear solve tolerance: this probe is **not** recorded as a new equilibrium.
The comparison endpoint remains the independently converged cold pointwise
solution, Cl=.000613774376.

## Which spanwise errors matter

Two predeclared partitions split the same forcing into tips, aileron-boundary
neighborhoods and the remaining span. Tips are the outer 5% of each semispan,
|t|≥.57912 m. Aileron boundaries are at |t|=.48768 m. The two neighborhood
half-widths are .01524 m and .03048 m. These are alternative diagnostic
partitions and must not be added together.

| Region | Narrow boundary neighborhood: signed share | Wider boundary neighborhood: signed share |
|---|---:|---:|
| Aileron boundaries | 107.94% | 94.15% |
| Tips | −5.07% | −5.07% |
| Remaining span | −2.87% | 10.93% |

These are signed contributions to the linear coefficient correction, so a
share can exceed 100% when other regions cancel part of it. The small
non-flow remainder contributes less than 0.000025%. The partitioned state
responses sum to the full response within **9.18e-15** in the checked norm;
their output corrections sum within **1.66e-14**.

The tip has the largest local velocity defect, but that maximum does not
identify the dominant rolling-moment error. Both partitions instead identify
the control-boundary neighborhoods as dominant. The tested discrepancy is
consistent with circulation truncation amplified by the coupled response;
it does not support modifying the vortex law or removing frame coupling.

## Scope and execution

The conditional setup is unchanged: 59.4556 m/s, rho 1.2256, PG Mach zero,
F1=1, sibling dCLdF=.0686, dCMdF=-.0102, frozen influences and free roll
acceleration with net Mx=0. The source model, mesh, constitutive equations,
force conventions and primary comparison are unchanged. Historical control
identity and the archived constraint mask remain unresolved. The primary
comparison already uses pointwise circulation; these alternative Fourier
diagnostics do not explain away its native-reference failures.

Drela steady §8.4, Eqs.212–213, pp.51–52, explicitly includes structural and
acceleration responses in the total-force/moment constrained Jacobian.
Steady §5.6, Eqs.200–201, defines the local and weighted flow constraints.
Jan Part IV §3.3, pp.10–13, distinguishes the mounted and rolling experiments
and original versus modified ASWING. The [authoritative index](aswing-authoritative-references.md)
and checksummed catalog govern the interpretation.

One serial worker completes in **3.45 CPU seconds / 4.95 supervised wall
seconds**, excluding library preload and parent evidence checks. It is reaped
normally, with one BLAS thread and unchanged limits of **512 MiB address
space / 15 CPU seconds / 25 wall seconds**. The complete matrix occupies
**12.13 MB** and uses 18 local geometry groups. No production source changes
or new primary passes are claimed. Browser/build verification remains held.

[Prospective plan](../../artifacts/isae/ae3-coupled-residual-response-20261112/plan.json)
· [Results and all checks](../../artifacts/isae/ae3-coupled-residual-response-20261112/cases/mapped76/report.json)
· [Terminal receipt](../../artifacts/isae/ae3-coupled-residual-response-20261112/cases/mapped76/terminal.json)
