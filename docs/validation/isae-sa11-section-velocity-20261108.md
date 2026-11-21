# Wake velocity dominates the remaining SA-11 winglet peaks

2026-11-08 UTC. The bound-velocity correction that improved the smooth controls
does **not** repair the actual SA-11 winglet failures. Across eight retained
states, six explicit adaptations of the correction leave the same states above
the local-Mach limit. At each primary maximum, the wake's section-normal
velocity is **33.6–1,687 times** the corrected bound contribution.

This rules out a bound-correction-only substitution as a sufficient repair.
It does not rule out a complete alternative formulation with consistently
changed circulation, wake and force equations. Production behavior is unchanged;
the registered SA-11 comparison remains **163/4,592 at 5%**. These bundled
winglet diagnostics are not additional registered reference passes.

## Controlled replay and provenance

The [original junction archive](isae-sa11-winglet-junction-20261107.md) supplies
the 30 m/s, 5-degree, pointwise-circulation cases for both bundled winglet
models at 48 and 96 requested intervals per beam. Required breakpoints increase
the actual interval counts. All beams retain physical index 1 and zero mutual
core, consistent with the [ASWING user guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt).

Four frozen-influence cases reuse the saved circulation arrays. The original
four current-wind observations did not retain circulation, so four small serial
native calls recapture it. Each reproduces its earlier computed/rejected outcome
and maximum Mach within the declared tolerance. Computed lift, drag and moment
coefficients also reproduce the earlier outputs. The original Mach gate remains
active; rejected-call fields are retained as diagnostics, not accepted solutions.

Input hashes, complete flight settings and original production-module hashes
are verified before reuse. The field replay checks the saved bound/wake
decomposition and relative velocity. All eight original circulation fields
satisfy the current normalized local residual within **2.30e-12**.

## What was changed in the diagnostic fields

The [smooth-control audit](curved-section-velocity-20261107.md) describes the
bound correction from [Li et al. (2020), §2.2](https://backend.orbit.dtu.dk/ws/portalfiles/portal/220872251/Li_2020_J._Phys._Conf._Ser._1618_052038.pdf).
Here the source geometry, circulation and wake remain fixed while the force
velocity is evaluated as

```
V_candidate = V_ambient + W(hv) + B_3D(probe) - B_2D(probe).
```

The primary probe is `hv + 0.5*chord*section_chord_direction`. Its infinite
two-dimensional line passes through `hv` along the local section span. The
three-dimensional bound field retains every segment; no root source is removed.

The mapping from ASWING's wind-directed quarter-chord construction to this
different section model is not uniquely specified by the paper. Two additional
probes therefore check sensitivity: ASWING's existing slope-adjusted control
point, and a half-chord offset along the influence wind divided by
`|wind cross span|`. Each probe is evaluated with both the local section span
and the actual bound-segment tangent as the infinite-line direction. This gives
six adaptations per state; none changes any source location or chooses a core.

For direct replay, both three-dimensional and infinite-line fields use the
original PG transformation. That is a controlled extension of the published
incompressible construction, not an asserted ASWING prescription. A second
control uses identity PG for both the original and primary corrected fields,
at the same circulation. Removing PG does not change the outcome.

These calculations are not a full implementation of MIRAS, not a new equilibrium,
and not a finite-angle/stall equivalence claim. In particular, the original
bound point is retained as the reference for the new probe; the physical wing
surface is not rebuilt around a new quarter-chord definition.

## Results

The numbers below are section-normal speed divided by the file's sound speed,
340.21 m/s. Values above unity identify invalid use of the subsonic model; they
are not predictions of physical supersonic flow at these low flight speeds.

| Geometry | Influences | Intervals/beam | Original maximum | Primary corrected maximum | Samples at/above unity, before → after |
|---|---|---:|---:|---:|---:|
| Upper | Frozen | 48 | 3.593822 | 3.603934 | 2 → 2 |
| Upper | Frozen | 96 | 14.249293 | 14.259392 | 6 → 6 |
| Upper | Current wind | 48 | 0.181903 | 0.176915 | 0 → 0 |
| Upper | Current wind | 96 | 0.353519 | 0.347898 | 0 → 0 |
| Upper/lower | Frozen | 48 | 10.357742 | 10.393689 | 8 → 8 |
| Upper/lower | Frozen | 96 | 21.318853 | 21.334204 | 16 → 16 |
| Upper/lower | Current wind | 48 | 3.048750 | 3.078043 | 4 → 4 |
| Upper/lower | Current wind | 96 | 3.469369 | 3.498778 | 6 → 6 |

All six probe/direction adaptations preserve the above/below-unity classification
of all eight states. The incompressible primary control does too. Thus neither
the small PG factor nor these local two-dimensional mapping choices conceal a
successful repair.

![SA-11 velocity correction and source contributions](../../artifacts/isae/sa11-section-velocity-20261108-review/sa11-section-velocity.png)

At the N96 current-wind upper/lower maximum, the wake contributes **1,184.77 m/s**
in the section-normal plane; the corrected bound field contributes **5.95 m/s**.
For the N96 frozen upper model, these magnitudes are **4,847.66 m/s** and
**2.87 m/s**. Vector magnitudes are reported separately and should not be added
as scalar speeds. The complete vectors and projections remain in the artifacts.

Changing the section speed also changes the native stall leakage. With the
original control-point field and circulation retained, the primary substitution
raises the maximum normalized native residual to between **5.05e-6 and 0.489**,
all above the native `1e-8` circulation gate. This is a diagnostic of the
substitution's feedback, not the residual of a fully implemented Li model.
It confirms that swapping only the reported force velocity would be inconsistent.

## Root and free-tip mechanisms differ

The frozen upper model retains its near-root wake interaction between
longitudinally offset origins, already derived in the original junction audit.
The current-wind upper/lower maximum is adjacent to a lower root. At N96 its
single lower-root ray contributes **1,638.41 m/s** before cancellation with
other rays, at a shortest ray distance of **5.698 micrometres**. It carries
0.0815750 m²/s circulation. The neighboring grouped ray contributes 379.98 m/s
in a largely opposing direction. This is a wake-source issue, not the smooth
curved-bound self-field corrected in the preceding study.

For the upper-only current-wind model, the maximum is instead at the free upper
tip. The last-panel circulation falls from **0.0322270 to 0.0161980 m²/s** on
48→96 refinement, while the force probe's shortest distance to the tip ray
falls from **66.44 to 16.61 micrometres**. The strongest grouped wake ray is
the nearby interior endpoint, not the free-tip endpoint alone. The complete
wake speed at the probe grows from **57.62 to 118.11 m/s**.

The probe moves closer to a sharp endpoint as the mesh is refined. This peak
sequence therefore does **not** by itself prove divergence at a fixed physical
location, nor failure of integrated lift convergence. The continued root Mach
rejections remain a separate problem. A useful next test must distinguish
fixed-location fields, a moving endpoint probe, and integrated loads rather
than treating their convergence as interchangeable.

## Verification and next action

Independent adaptive Biot–Savart line integration at the selected original and
corrected maxima agrees with the bound fields within **4.82e-13 m/s**. A separate
saved-array audit reconstructs all normal Mach values and decompositions, checks
the source manifests, and groups wake sources by exact endpoint equality.
Original production/status/scope files retain all **143** recorded hashes.

The four recaptured native calls take **8.66 seconds** in total. All eight
jobs' recorded stages total **17.46 seconds**, excluding process startup and
the separate plot audit. Every job runs serially with one BLAS thread and
terminates successfully. No corrected-circulation solves were attempted.

The next investigation should target the wake representation at the actual
root and tip, with fixed-location checks separating discretization error from
endpoint asymptotics. Further tuning of the smooth-bound correction is not
supported as a standalone fix for these failures. A production change still
needs a consistent formulation and independent accuracy evidence; none is
adopted from this field replay.

- [One-case serial driver](../../scripts/verify-sa11-section-velocity.py)
- [Saved-array and wake-source audit](../../scripts/analyze-sa11-section-velocity.py)
- [Analysis, all mapping ranges and source decompositions](../../artifacts/isae/sa11-section-velocity-20261108-review/analysis.json)
- [Standalone SVG plot](../../artifacts/isae/sa11-section-velocity-20261108-review/sa11-section-velocity.svg)

Each of the eight `artifacts/isae/sa11-section-velocity-20261108-{upper,both}{48,96}-{frozen,current}/`
directories retains its exact driver, plan, native observation, arrays, results
and hash manifest. The first job's UTC observation began shortly before midnight
on November 7; original observation timestamps are retained unchanged.

The subsequent [fixed-probe wake comparison](isae-sa11-fixed-wake-probes-20261108.md)
retains common off-sheet observation positions on both grids. It finds localized
main-wing wake sensitivity near the upper root and a 14.87% change in the
current-wind lower-winglet circulation integral. It also identifies the
coarse-receiver/fine-vortex-origin coincidence that would invalidate a naive
comparison directly on the lifting line.
