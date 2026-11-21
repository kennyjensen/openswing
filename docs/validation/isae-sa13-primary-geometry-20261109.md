# SA-13: primary geometry follow-up

SA-13 is the current focus following the user's explicit instruction on
2026-11-09; **SA-12 remains open**. SA-13 stays **0/612**, including the
136 unavailable reference entries. This investigation makes no solver change
and does not promote the graph reconstructions to native ASWING inputs.

## Numerical geometry recovered from the cited report

[NACA-TM-574](../../reference/isae-sa13/naca-tm-574.pdf),
**printed p.8 / PDF p.10**, gives six values of `(r/a)^2` for the ZR III bow.
Its line-source length is `a = 10 m` (printed pp.2, 10). These values establish
six numerical radius constraints independently of the ISAE outline and force
curves. The table was checked visually against the PDF; it is the right-hand
geometry column, not the source-strength table on the following page.

| Frame coordinate (m) | Published `(r/a)^2` | Derived radius (m) |
|---:|---:|---:|
| 180 | 0.478 | 6.91375 |
| 170 | 0.986 | 9.92975 |
| 160 | 1.335 | 11.55422 |
| 150 | 1.610 | 12.68858 |
| 140 | 1.770 | 13.30413 |
| 130 | 1.851 | 13.60515 |

The radius precision is limited by the three-decimal published squared values.
This is a partial bow table, not a complete radius/derivative definition.
It concerns the pressure case's cited ZR III model; it does not provide the
R33, R101 or RS1 ASWING input files.

## A coordinate conflict within that primary report

**Printed p.10 / PDF p.12** gives the designed nose at frame **187.4 m** and
the calculated streamline nose at **186.9 m**. However, **Figure 3 / PDF p.30**
annotates the nose **+197.5 m** and stern **−12.5 m**. Both readings were
checked visually. The earlier SA-13 source record used the figure's annotation;
it is now explicitly qualified by the conflicting text. Neither is silently
corrected or selected by aerodynamic agreement.

As a diagnostic, map the existing closed, normalized ISAE outline onto each
of those two nose/stern pairs, apply the same scale to x and radius, and linearly
interpolate its radius at each published frame. No force or pressure data
determine these mappings.

| Nose anchor | Assumed length | Outline radius errors at frames 180 → 130 |
|---|---:|---|
| Text: 187.4 m | 199.9 m | −14.31%, −7.69%, −9.73%, −5.71%, −6.02%, −4.91% |
| Figure: 197.5 m | 210.0 m | +36.74%, +7.56%, +6.96%, +2.47%, +0.14%, +1.66% |

These are **conditional geometry differences**, not OpenSwing aerodynamic
errors or pass/fail decisions. Endpoint reconstruction, plotted-outline scale
and interpolation remain assumptions. The two documented anchors produce
substantially different bow geometry; another mesh sweep would not resolve
that uncertainty. This also does not resolve the separate
[pressure-observable conflict](isae-sa13-pressure-reference-20261109.md).

## Next work and retained scope

Use the numerical radius constraints to audit a disclosed pressure-case
reconstruction and its radius derivatives before any additional aerodynamic
comparison. Seek the missing full radius/derivative and sensor definitions;
the original and ISAE-modified ASWING curves must remain distinct. Searches for
the older R33/R101 ARC reports have not yet recovered their numerical geometry.
No match to the experimental curves substitutes for an archived ASWING match.

SA-12's matched AVL controls continue to support the physical ground-image
calculation. Its archived-result discrepancy and historical setup remain open;
the endpoint-only image approximation that violates impermeability is not
adopted. SA-14 follow-up was also
[deferred](isae-sa14-default-setup-20261109.md) when the user selected SA-13.

## Evidence

The standard-library-only [audit](../../scripts/audit_sa13_primary_geometry.py)
authenticates five source/script hashes and emits the six radii and both
coordinate interpretations without invoking a solver:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python3 scripts/audit_sa13_primary_geometry.py --output /tmp/sa13-geometry-new.json
```

The output path must be new, preserving prior observation timestamps.
[Saved analysis](../../artifacts/isae/sa13-primary-geometry-20261109/analysis.json),
[radius table image](../../artifacts/isae/sa13-primary-geometry-20261109/tm574-p10.png),
[nose-coordinate text image](../../artifacts/isae/sa13-primary-geometry-20261109/tm574-p12.png),
and [Figure 3](../../reference/isae-sa13/naca-tm-574-p30.png) retain the evidence.
The [publisher record](https://ntrs.nasa.gov/citations/19930094841) identifies
the primary report. No completion fraction or tracked scope changed.
