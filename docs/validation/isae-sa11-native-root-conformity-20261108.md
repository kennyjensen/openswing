# SA-11: aligned native AVL root meshes reduce, but do not resolve, local spikes

2026-11-08 UTC. Analysis of six retained native AVL states and two new small
serial native runs identifies a real sensitivity to the chordwise mesh at the
upper-winglet root. Aligning the shared root origins reduces peak normal Mach
from **2.49 to 1.09** on the coarse span mesh and **10.30 to 2.86** on the finer
mesh. Local velocity still grows under refinement, and near-field vortex drag
changes **10.62%**. This is useful evidence about the conversion/discretization,
not a production fix or a validated ASWING result.

**SA-11 remains 163/4,592 at 5%.** No production equation, original model,
Mach guard, comparison fraction or tracked scope changes. SA-2 stall-region
work remains deferred. These upper-winglet diagnostics remain separate from
the primary adapter's baseline/extension comparisons.

## What the retained meshes show

At the positive wing/upper-winglet junction, both root chords have
`y = 1.2426 m`, `z = 0.15257 m`, but different streamwise extents:

| Root section | Leading-edge x | Trailing-edge x | Streamwise chord |
|---|---:|---:|---:|
| Main wing | 0.95348000 m | 1.15598248 m | 0.20250248 m |
| Upper winglet | 1.02453000 m | 1.15567633 m | 0.13114633 m |

These are the existing normal-to-streamwise chord conversion, not new geometry.
The winglet starts 71.05 mm aft of the main-wing leading edge and ends
0.30614 mm ahead of its trailing edge. Independent cosine grids on the two
chords do not place any root vortex origins at the same x. Even the nearest
origins differ by 24.347, 8.041 and 1.376 mm for 2, 4 and 8 chordwise rows.
Meanwhile, the worst winglet force point lies only **0.5065 mm** from the root
line on the coarse mesh, and **0.1267 mm** on the finer mesh.

For signed root circulations `s_j` at ordered collinear origins `x_j`, let
`S_j = sum(s_1 ... s_j)` and let `K_j` be the downstream-ray velocity kernel.
The saved root field can be written exactly as

```
sum(s_j K_j) = sum(S_j (K_j - K_(j+1))) + S_last K_last.
```

Each kernel difference is a finite streamwise segment. This reexpression
adds or removes no vortex. The final ray carries only the total circulation
imbalance; the finite segments retain the chordwise distribution and offsets.

| Original chord rows | Span strips | Total root circulation jump | Finite-segment velocity norm at worst point | Residual-ray velocity norm |
|---:|---:|---:|---:|---:|
| 2 | 64 | 3.279% | 308.38 m/s | 68.32 m/s |
| 2 | 128 | 1.330% | 1,602.33 m/s | 103.28 m/s |
| 4 | 64 | 3.271% | 747.13 m/s | 0.000426 m/s |
| 4 | 128 | 1.295% | 3,374.11 m/s | 0.0000395 m/s |
| 8 | 64 | 3.265% | 153.80 m/s | 0.000979 m/s |
| 8 | 128 | 1.290% | 2,290.83 m/s | 0.0000173 m/s |

These are vector norms, not scalar contributions to total Mach. The worst
receiver changes with chord count. The distinction explains why improving
total root-circulation continuity alone does not remove the field spike.

The independent finite-segment/ray identity closes within **1.36e−12 m/s**.
Reconstructing bound plus wake velocity agrees with native exports within
**1.07e−4 m/s**. This latter comparison uses zero core, while native AVL has its
tiny numerical core; it is not a roundoff-equality claim.

## A bounded native mesh-conformity control

AVL's **Vortex Lattice Spacing Distributions**, rules 3 and 4, describe
chordwise `SURFACE` subdivisions with the same component and span stations,
and require attention to both chord and span refinement at bends.
They do not establish a particular native ASWING junction rule.
[Retained AVL manual](../../reference/avl-native-20261108/source/AVL3.52rel09032025/avl_doc-AVL350-04242025.txt:1155).

The two predeclared controls partition the main wing into three chordwise
pieces without moving its external boundaries: the part ahead of the winglet
root chord, the overlapping part, and the small part behind it. The main-wing
fraction cuts are **0, 0.3508599062, 0.9984882009, 1**. The overlap and winglet
each have four cosine chord rows, giving exactly coincident shared root
origins. Each exposed main-wing portion has one chord row. All pieces retain
component 1 and identical span stations. Original section incidence, CLAF,
reference dimensions, operating conditions and frozen body-x wakes remain.

The literal planform boundaries reconstruct within **1.12e−16 m**; all four
shared root origins coincide exactly in the native exports. Spanwise receiver
coordinates match the previous mesh. There are 320/640 vortices, versus
256/512 in the retained four-row controls: this is a different discretization,
not an equal-vortex-count comparison. No native ASWING rule has been replaced.

Both use the explicit report-derived **−4° twist alternative**, alpha 1° and
PG Mach `240/340.21`, as in the preceding study. The original +4° source file
is unchanged. Native AVL is linear here and omits ASWING profile drag, stall
and section pitching-moment laws.

| Root mesh | Span positions across physical beams | Vortices | CL error vs archived ASWING | CDi error vs archive | Near-field vortex CD | Peak normal Mach at native force points |
|---|---:|---:|---:|---:|---:|---:|
| Independent chord grids | 64 | 256 | −0.280% | −1.045% | 0.00500095 | 2.49142 |
| Shared root origins | 64 | 320 | −0.220% | −1.144% | 0.00462499 | 1.09163 |
| Independent chord grids | 128 | 512 | −0.123% | −0.143% | 0.00531584 | 10.30082 |
| Shared root origins | 128 | 640 | +0.032% | −0.290% | 0.00511605 | 2.86050 |

Mach is diagnosed by scaling native velocities to 240 m/s and projecting
perpendicular to the ASW beam tangent. Native force points are generally not
ASWING's quarter-chord receivers. This is neither a native AVL acceptance
gate nor a successful production OpenSwing solution.

![Native AVL root-alignment comparison](../../artifacts/isae/sa11-native-aligned-root-20261108/aligned-root.png)

[Exportable SVG](../../artifacts/isae/sa11-native-aligned-root-20261108/aligned-root.svg).
The plot uses the application's VibeLattice color order and was visually checked.

## What remains after alignment

The largest field moves to the first chordwise row at the winglet root.
Circulation differences at paired origins and the exposed main-wing portions
produce large, opposing velocities. Their vector sum gives root-wake norms
of **271.88 and 493.43 m/s** on the two meshes. Bound-vortex norms rise from
**56.36 to 564.44 m/s**. Root alignment therefore removes part of the mesh
sensitivity but leaves both wake and sharp-bend bound-field contributions.
Matching origins does not itself enforce matching chordwise circulation.

Across these aligned meshes, CL changes **0.253%**, Trefftz CDi **0.865%**, and
near-field vortex CD **10.618%**. Close lift/CDi agreement still does not
establish locally valid flow, converged near-field drag, or full moments.

Native forces independently reconstruct within **4.45e−16** in coefficient.
At each worst point, 96-point bound-filament quadrature plus analytic rays
matches native velocity within **5.79e−5 m/s**; increasing quadrature to 192
changes it by at most **7.23e−10 m/s**. The independently evaluated control
normal residual is below **4.81e−7 times freestream**, including the same
zero-core/native-numerical-core difference. No production vortex kernel is
used for these checks.

This supports auditing connected-surface representation and local velocity
sampling, rather than changing the elementary kernel or increasing a core
until a run passes. It does **not** establish that a conforming mesh alone
cures the sharp partial-chord junction, or recover the original ASWING
producing setup. The next useful comparison should separate the residual
sharp-bend bound field from the exposed main-wing root wake, while retaining
the actual geometry and checking the published section-force definition.
Another unconstrained resolution sweep would not resolve that distinction.

## Evidence and reproduction

- [Six-state root analysis](../../artifacts/isae/sa11-native-root-conformity-20261108/analysis.json)
  and [reproducer](../../scripts/analyze-sa11-native-root-conformity.py).
- [Two-run plan](../../artifacts/isae/sa11-native-aligned-root-20261108/plan.json)
  and [native driver](../../scripts/verify-sa11-native-aligned-root.py).
  Prepare a fresh `--output` directory, then invoke `--case 0` and `--case 1`
  serially. Never run both at once.
- [Independent checks](../../artifacts/isae/sa11-native-aligned-root-20261108/analysis.json)
  and [analyzer](../../scripts/analyze-sa11-native-aligned-root.py).

Both native jobs completed, taking **0.433 seconds total** inside the native
subprocesses, excluding Python startup/provenance work. They used one BLAS
thread, a 45-second outer limit, 768 MiB address-space limit and a 30-second
native timeout. There are no background solvers or new production solves.
