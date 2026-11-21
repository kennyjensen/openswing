# SA-11: comparison organized around the paper

2026-11-08 UTC. At the user's request, SA-11 now has a **paper-focused primary
suite: 20/48 checks pass at 5% (41.67%)**. There are 18 numerical mismatches,
one rejected solution and nine missing comparisons. This is a deliberate
change in comparison scope, **not a new improvement in the solver**. The
original archive remains **1,060/9,184 (11.54%)**, with every original
unavailable value still in that denominator.

The new [comparison page](../../public/isae-sa11-paper/index.html) is served at
`/isae-sa11-paper/` by the normal development server. It includes the plots,
counts, settings, individual results and independent verification.

| Configuration | Pass / required | Numerical mismatch | Rejected | Missing coverage | Failed errors: median / maximum |
|---|---:|---:|---:|---:|---:|
| Bare wing | 2/12 | 10 | 0 | 0 | 7.35% / 18.80% |
| Planar extension | 8/12 | 4 | 0 | 0 | 8.43% / 10.16% |
| Upper winglet | 10/12 | 1 | 0 | 1 | 5.25% / 5.25% |
| Upper/lower winglets | 0/12 | 3 | 1 | 8 | 7.57% / 36.42% |
| **Total** | **20/48** | **18** | **1** | **9** | Errors apply only to computed mismatches |

## What the new tests measure

Jan, *Experimental validation of ASWING, Part I*, **p.35**, describes SA-11 as
a comparison of lift and drag trends for four wingtip configurations. **Figure
22, p.39**, plots CL against incidence and CD against CL, at Mach labels 0.70
and 0.80. It does not show the extra 0.75/0.78 archive tables. The
[authoritative index](aswing-authoritative-references.md), catalog, actual PDF
figure and [paper/table audit](isae-sa11-reassessment-20261108.md) were checked.

The fixed [suite specification](sa11-paper-suite.json) uses the same 48 sample
ordinates as that prior source-only paper/table audit:

- **Lift:** CL at 1°, 3° and 5°, for each configuration and speed.
- **Drag:** CD at **equal CL = 0.3, 0.5 and 0.7**, for each configuration and
  speed. Each solver/reference curve supplies its own incidence at that lift.
- All four configurations and both speeds remain required. A comparison
  cannot pass without a valid complete solution. Missing points, insufficient
  interpolation coverage and rejected solutions remain in the 48-check total.

Actual speeds are 240 and 272 m/s, with the retained density 1.2256 and sound
speed 340.21. Reference targets are the numerical **ASWING 5.96 curves**,
authenticated against Figure 22; experimental markers are not targets. The
paper's uniform CD plotting allowances, 0.0064/0.0075, are excluded from both
error calculations and the new plots. Adding those offsets would dilute the
relative drag error.

Interpolation is linear between consecutive accepted quarter-degree rows.
There is no extrapolation, interpolation over rejected points, bridging of
larger unrun gaps or automatic branch selection on nonmonotone polars. Each
configuration uses one fixed saved setup across its curve. The 128-request
repeat, dimensional lift/drag duplicates, CDi, Cm and span efficiency remain
in their separate original regression records; they are not extra votes here.
No unavailable original target is deleted and no alternative passes are added
to the old total.

## Declared setups and remaining differences

| Configuration | Setup used for this first assessment |
|---|---|
| Bare wing | Original file, including dCLda = 7/rad. Cosine 64 request, minimum 16.466 mm, 62 actual intervals; current-wind influences. |
| Planar extension | Original file. Cosine 64 request, same minimum, 60 actual intervals; current-wind influences. The modified-cosine candidate is separate. |
| Upper winglet | Disclosed Joint correction and the report's Figure 40 −4° upper-winglet twist; original airfoil properties. 32 main-wing + 16 + 16 winglet intervals; frozen influences. |
| Upper/lower winglets | Disclosed Joint-station correction and −4° upper-winglet twist; original CLmax = 0.8 retained. 32 + 16 + 16 + 5 + 5 intervals; frozen influences. |

The exact spacing floor is **0.0164659927127284 m**. These setups are recorded
in the specification and artifact hashes. The winglet inputs are explicitly
report-derived alternatives, not claims to have recovered the original
producing input. No new model edits, solver changes, fitted airfoil parameters
or physical solves were made for this assessment.

The bare-wing lift is **6.86–7.98% high** at the selected angles; its low-lift
drag is **18.76–18.80% high** at equal CL = 0.3. Its section slope remains
7/rad while the other configurations use 6.34/rad. That source inconsistency
is still relevant; this suite does not silently replace the baseline data.

The extension's six lift checks pass, with maximum error **0.437%**. Its
remaining four equal-lift drag failures are **6.92–10.16% low**. This continues
to be a real drag discrepancy on the declared cosine mesh.

The upper-winglet case's **294/294 same-incidence checks remain passing**.
The new equal-lift comparison answers a different question: at the 0.80 label,
CL = 0.7, CD is **5.253% high**. Its CL is about 0.4% low at a fixed angle, so
matching lift requires slightly higher incidence and drag. At the 0.70 label,
the saved curve ends at CL = 0.68516 at 5°; the CL = 0.7 drag check remains
missing rather than extrapolated. This distinction is why the paper-focused
suite is useful even where the earlier same-angle suite is green.

The upper/lower case still has sparse coverage, its distinct CLmax/stall-input
issue, and the rejected 272 m/s, 5° solution. Its high-incidence mismatch is
retained, but the user's deferral of post-stall repairs remains in effect.

## Wingtip benefit at equal lift

The artifact also records all **18 CD(configuration) − CD(bare wing)** values
at the three common lift coefficients. These derived differences are not
counted again in the 48-point primary score. The common experimental plotting
allowance cancels exactly.

For example, at CL = 0.5 the planar-extension drag change is:

| Mach label | Archived ASWING ΔCD | OpenSwing ΔCD |
|---|---:|---:|
| 0.70 | −0.00072622 | −0.00294916 |
| 0.80 | −0.00069303 | −0.00292483 |

Thus this setup gets the direction of the extension benefit but overstates
its size. Both the baseline and extension errors contribute.

The saved upper-winglet and baseline runs use different frozen/current
influence conventions. Their arithmetic differences are retained as qualified
diagnostics, but **a matched-setup winglet-benefit comparison remains
unavailable**. The report does not declare it validated. The next useful work
is to align those settings on the fixed meshes, resolve the baseline input
discrepancy, and fill the missing equal-lift bracket. This is more directly
connected to SA-11's purpose than further broad mesh-count sweeps. Lower-winglet
stall repairs remain deferred.

![Lift and matched-lift drag comparison](../../artifacts/isae/sa11-paper-suite-20261108/paper-comparison.svg)

## Verification and reproducibility

This assessment reuses verified saved states and makes **zero physical solver
calls**. It ran as a small foreground process, with 512 MiB address-space,
15 CPU-second and 25 wall-second limits. No browser, Vite or background solver
was started. One preparation assertion initially confused a recorded
pre-change source snapshot with its post-change hash; it was corrected before
any output artifact was written. No numerical result was discarded.

- [Assessment](../../artifacts/isae/sa11-paper-suite-20261108/analysis.json)
  preserves all 48 identities, raw targets, individual settings, interpolation
  brackets, errors, missing reasons, supplementary increments and **568 pins**.
- [Independent verification](../../artifacts/isae/sa11-paper-suite-20261108/verification.json)
  authenticates those pins, independently reduces saved forces and uses
  Decimal arithmetic to recheck interpolated values and every decision.
  Maximum coefficient reduction error is **4.45e−16**; maximum interpolation
  difference is **3.47e−18**.
- Seven focused [scoring guard tests](../../tests/test_sa11_paper_suite.py)
  pass, including no extrapolation, no rejected/missing-point interpolation,
  branch ambiguity, matched-lift versus matched-angle sampling, and exclusion
  of the experimental drag allowance from acceptance.
- The [PNG](../../artifacts/isae/sa11-paper-suite-20261108/paper-comparison.png)
  was visually inspected. Plot colors follow the existing VibeLattice palette.

To assess a later set of saved evidence, update the explicit specification and
use a new output directory; prior observations must not be overwritten:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 npm run test:isae:sa11:paper -- --output artifacts/isae/sa11-paper-suite-NEW
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python scripts/check_sa11_paper_suite.py artifacts/isae/sa11-paper-suite-NEW
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python scripts/plot_sa11_paper_suite.py artifacts/isae/sa11-paper-suite-NEW
```

The progress scope now explicitly selects this paper-focused fraction, while
the original archive fraction remains in `ISAE_STATUS.md`. Its timestamped
change must be read as a **scope change**, not a jump in numerical accuracy.
Full SA-11, transonic experimental accuracy and ASWING parity remain open.
