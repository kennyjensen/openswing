# SA-11 extension: force stability with a fixed minimum spacing

The prescribed finer-mesh check does **not establish stable total drag**.
The final accepted refinement changes CD by **1.02–1.27%**, while the preceding
refinement changes it by **1.90–2.37%**. Lift, Trefftz CDi and moment change
much less. At 272 m/s and 5°, all three finer meshes reject the local section
moment because normal Mach reaches **1.1515** at the center sweep break.

Twelve new serial calls are terminal: nine computed, three rejected, no
timeouts. The original primary result remains **1,060/9,184**. This diagnostic
does not replace the primary meshes, add its successful comparisons to that
score, or establish the unknown native ASWING mesh.

![Fixed-minimum mesh sensitivity](../../artifacts/isae/sa11-extension-mesh-limit-20261108/extension-mesh-limit-v2.png)

[Standalone SVG](../../artifacts/isae/sa11-extension-mesh-limit-20261108/extension-mesh-limit-v2.svg).
Rejected states have no drag score; the crosses at the top of the drag panel
only mark their presence. Their vertical position is not a calculated error.
The figure uses the application palette. Lines join samples, not a proven
continuous convergence curve. The initial figure is retained; revision 2
separates crowded tick labels and includes the lowest Mach sample.

## Protocol and source basis

The [authoritative index](aswing-authoritative-references.md), checksummed
[source catalog](aswing-authoritative-sources.json), and preceding
[physical-mesh/Fourier comparison](isae-sa11-extension-discretization-20261108.md)
were consulted. Drela's steady **Eqs. 150–157 and 200–204** define the geometry,
circulation and residual; **Eqs. 64–74** define forces and moments. ISAE Part I
**§5, p. 21** warns that fine discretization can expose velocity singularities.
Its elliptical-wing count study does not identify the SA-11 generating mesh.

The frozen plan declares requested cosine counts **256, 512 and 1024** at
**3° and 5°, 240 and 272 m/s**, before any new solve. Eight authenticated
64/128 controls are reused. The original extension ASW file, natural-v1 input
interpolation, section data, density, current-wind influences, speed-derived
compressibility, stall law, force conventions and numerical gates are fixed.
The previously established **0.0164659927127284 m** minimum applies throughout
the same logical beam. Mandatory stations remain.

| Requested intervals | Actual intervals | Minimum interval | Maximum interval |
|---:|---:|---:|---:|
| 256 | 160 | 16.615 mm | 32.932 mm |
| 512 | 172 | 16.541 mm | 24.530 mm |
| 1024 | 178 | 16.466 mm | 25.621 mm |

A mesh-only preflight checked all counts before launching solvers and capped
actual size at 256 intervals. Minimum spacing coarsens the requests; these
are not 1024-unknown solves. The meshes are not nested, and the largest
interval does not decrease monotonically. This is a check of the fixed
spacing policy, not an extrapolation to zero interval length.

The predeclared diagnostic stability measure is
`100 * abs(new − old) / abs(new)` for CL, CD, CDi and Cm at each operating point.
Both final refinements must change all four by at most 1% to count as stable
over these samples. This is separate from the unchanged **5% reference
acceptance**, and is not a new requirement for passing an existing ISAE case.

## Computed results and retained rejections

| Speed | Alpha | CD error, 108 actual | CD error, 160 actual | CD error, 172 actual | CD error, 178 actual |
|---|---:|---:|---:|---:|---:|
| 240 m/s | 3° | −4.236% | +4.203% | +2.260% | +1.225% |
| 240 m/s | 5° | −5.195% | +5.217% | +2.784% | +1.497% |
| 272 m/s | 3° | −4.965% | +4.785% | +2.543% | +1.349% |
| 272 m/s | 5° | −6.135% | Rejected | Rejected | Rejected |

The finest accepted results are closer to the archived CD, but the sequence
crosses the reference and remains sensitive to interval placement. Every
operating point fails the predeclared diagnostic stability check: three due
to CD changes, one due to rejected states. No preferred count is selected.

| Accepted operating point | CD change, 160 → 172 | CD change, 172 → 178 | Largest CL/CDi/Cm change over these two steps |
|---|---:|---:|---:|
| 240 m/s, 3° | 1.900% | 1.023% | 0.043% |
| 240 m/s, 5° | 2.367% | 1.268% | 0.045% |
| 272 m/s, 3° | 2.187% | 1.178% | 0.045% |

All nine accepted states are at least **13.81 stall-transition widths**
inside the section limits. Maximum circulation residual, including rejected
states, is **9.21e-16**. Neither an unfinished circulation iteration nor stall
explains the accepted force sensitivity at these points.

## Center Mach rejection and drag sensitivity are distinct

At 272 m/s and 5°, the two receivers adjacent to the center sweep break
reject on all three new meshes. At 178 intervals, the worst is at material
station **t = 0.0081381 m**. The opposite center bound segment contributes
**273.846 m/s**, at physical distance **9.938 mm**, with a shared endpoint
turn of **70.054°**. The aggregate bound contribution has components
`[51.004, 0.00060, −300.989] m/s`; the aggregate wake contribution is
`[0.0755, −0.00684, −0.8635] m/s`. Combined with freestream they produce
**391.755 m/s normal speed, M_perp = 1.151508**. The dominant bound-segment
term was independently reconstructed, agreeing within **8.35e-14 m/s**.

The material-interval floor is respected. It does not impose the same
distance between a force receiver and another bound segment, nor does it
guarantee the local pitching-moment law remains subsonic. These are center
bound-segment interactions, not winglet trailing-leg interactions. Rejected
force diagnostics are retained, but their missing moments and rejected
validity prevent using them as complete matches.

For accepted states, an independent Eq. 67 reduction partitions vortex drag
into the two center-adjacent intervals and all remaining strips. During the
160 → 172 → 178 refinements, the center-pair CD changes by only
**2.39e-7–1.64e-6**, in the direction opposite to the much larger total
vortex-CD changes, **1.76e-4–6.05e-4**. Thus the latest drag change is almost
entirely in the other strips. This partition includes the changing width of
the center intervals; it is an accounting result, not an isolated causal
perturbation. Treating just the two high-velocity center receivers would
not explain the observed aggregate drag changes.

## Verification and next action

- [Frozen plan and mesh preflight](../../artifacts/isae/sa11-extension-mesh-limit-20261108/plan.json),
  [serial driver](../../scripts/verify-sa11-extension-mesh-limit.py), and
  [verified analysis](../../artifacts/isae/sa11-extension-mesh-limit-20261108/analysis.json).
- [Independent checker](../../scripts/check-sa11-extension-mesh-limit.py)
  authenticates 256 source/control pins, every new result artifact, all
  unchanged settings, interval counts and limits, and reference decisions.
  Independent zero-core AVL segment/ray algebra, with the exact Biot–Savart
  constant and current wind/PG transform, agrees with every accepted velocity
  within **1.73e-14 times freestream**. Force/moment coefficient reductions
  agree within **6.67e-16**; vortex-CD reductions within **2.43e-17**.
- Each process uses one BLAS thread, 512 MiB address space and 15 CPU /
  25 wall seconds. Maximum invocation time is **4.40 s**, peak RSS
  **252.63 MiB**. No background or browser/build jobs were launched.
- An initial mesh-only preparation stopped on a diagnostic attribute typo
  before creating a plan or running a solver. It was corrected to use
  `PanelMesh.t0/t1`; the frozen plan and all twelve solves use the corrected
  driver. There were no solve retries or result-recording failures.

Further brute-force mesh increases are not justified by this result. The
next useful audit is the distribution and cancellation of bound-vortex drag
across the remaining strips on these saved nonuniform meshes, checked against
the documented receiver locations and force integration. The center Mach
failure should remain a separate validity issue. No production equation,
default mesh, primary completion fraction or comparison scope changes here.

The subsequent [pair accounting and redistribution experiment](isae-sa11-extension-drag-pairs-20261108.md)
localizes 80–86% of the last two drag changes at 240 m/s, 3° to adjacent
finite-origin wake terms. It independently explains large pair contributions
near width jumps, but smoothing those jumps in three count-preserving trials
does not improve the integrated drag or its refinement stability. No
production mesh change follows from that result.
