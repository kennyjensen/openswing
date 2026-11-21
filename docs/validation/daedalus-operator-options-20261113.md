# Daedalus: endpoint equations, circulation and dynamic options

**Drela's Bode curves are still unmatched.** Fresh calculations using the
documented endpoint beam equations give **0.074218 deg/s/F3** at the drawing's
1.157378 Hz yaw dip, compared with **0.0339862** in the reference: **118.4% high**.
The older midpoint calculation gave 0.0737892. Switching structural operators
therefore does not explain this discrepancy. The user has requested continued
work on this comparison; it remains the active focus.

![Four-output comparison](../../artifacts/daedalus-source-summary-20261113/comparison/comparison.png)

[Vector plot](../../artifacts/daedalus-source-summary-20261113/comparison/comparison.svg),
[combined data](../../artifacts/daedalus-source-summary-20261113/comparison/result.json).

## Controlled comparisons

All cases use 6.7 m/s, fixed PG Mach 0.1, the same C16 material node stations,
unchanged mass/stiffness data, SEGSPL interpolation and the
`drela-moving-airflow-v1` endpoint operator. The baseline has pointwise
circulation, updated influence coefficients, aerodynamic lag and propeller
plume enabled. Each row below changes only the stated option relative to that
baseline. These are separate hypotheses, not jointly optimized settings.

| Case | Yaw at 0.1 Hz, deg/s/F3 | Yaw at reference dip, deg/s/F3 | Error at reference dip | Four-output RMS error, dB | Magnitudes within 5% |
|---|---:|---:|---:|---:|---:|
| Drela drawing | 0.118238 | 0.0339862 | — | — | — |
| Endpoint equations, pointwise circulation | 0.121763 | 0.0742178 | +118.4% | 2.453 | 85/260 |
| Eight Fourier modes per lifting beam | 0.121688 | 0.0742144 | +118.4% | 2.469 | 85/260 |
| Aerodynamic lag disabled | 0.119666 | 0.0597741 | +75.9% | 4.096 | 59/260 |
| Propeller plume disabled, thrust retained | 0.109309 | 0.0714428 | +110.2% | 2.419 | 74/260 |

The Fourier comparison changes yaw at the specified dip frequency by only
**0.0046% in magnitude**. This is one declared eight-mode comparison, not a
Fourier-convergence demonstration or recovery of the historical mode count.
The pointwise case has 82 circulation unknowns and 2,044 dynamic coordinates;
the Fourier case has 32 circulation coefficients and 1,994 dynamic coordinates.
Both retain 108 structural nodes, 103 elements and 82 lifting intervals.

Disabling lag deepens yaw's dip but makes the excessive roll/bank cancellation
worse. ASWING's [original manual](../../reference/aswing_doc.txt),
“Lag aero effects modeled,” explicitly specifies an enabled default. This
diagnostic gives no reason to change it. The disabled-plume comparison uses
the same manual's negative-`Rdisk` option: the disk's magnitude and direct
engine thrust law remain unchanged. No option, aircraft property, input gain
or tolerance was fitted or changed in production.

Each full comparison covers 65 frequencies and all four published magnitude
channels. The four-output score and 5% count use the same definitions as the
[preceding speed study](daedalus-speed-controlled-20261113.md). These descriptive
counts are not ISAE passes. Original operating settings, phase response and
high-frequency mesh convergence remain open.

Individual results retain complex outputs, trim, checks and process receipts:

- [Endpoint baseline](../../artifacts/daedalus-source-20261113/report/result.json),
  [CSV](../../artifacts/daedalus-source-20261113/report/comparison.csv).
- [Fourier](../../artifacts/daedalus-source-fourier8-20261113/report/result.json),
  [CSV](../../artifacts/daedalus-source-fourier8-20261113/report/comparison.csv).
- [Lag disabled](../../artifacts/daedalus-source-nolag-20261113/report/result.json),
  [CSV](../../artifacts/daedalus-source-nolag-20261113/report/comparison.csv).
- [Plume disabled](../../artifacts/daedalus-source-noplume-20261113/report/result.json),
  [CSV](../../artifacts/daedalus-source-noplume-20261113/report/comparison.csv).

## Constraints and section lift margins

A separate mixed-frame calculation prescribes axial, normal and pitch
accelerations while leaving lateral, roll and yaw accelerations free. It retains
elastic motion and all twelve frame kinematic states. The exact restriction of
the fresh descriptor was checked against the complete nonlinear mixed-frame
residual in three directions before eight harmonic solves.

Yaw at the reference dip is **0.07421757**, versus **0.07421777** in fully free
flight: less than **0.001%** difference. This particular constraint choice does
not explain the notch. It does not establish that every historical constraint
combination is equivalent. See the [result](../../artifacts/daedalus-source-constraints-20261113/longitudinal-prescribed-immutable/result.json).

The fresh baseline's [section loads](../../artifacts/daedalus-source-section-audit-20261113/loaded-sections/sections.json)
also show no sections beyond their declared stall limits:

| Surface | Minimum section cl | Maximum section cl |
|---|---:|---:|
| Wing | 0.30646 | 1.29879 |
| Stabilizer | −0.39799 | −0.10405 |
| Fin | −0.01717 | 0.00866 |
| Fairing | 0.0000525 | 0.0007608 |

The wing's upper limit is 1.7. The smooth stall law remains enabled; being below
the nominal limit does not make its mathematical contribution identically zero.
This section audit is not a separate stall-disabled response comparison.

## Reference provenance and the plume-history clue

The [authoritative index](aswing-authoritative-references.md) and source catalog
were consulted. Drela's steady discretization, unsteady Eqs. 34–56, manual
options and original plotted outputs remain the targets. The new endpoint
calculation removes an earlier comparison's dependence on midpoint structural
equations and natural spline endpoints; it does not claim native executable
equivalence for all aerodynamic discretization details.

A fresh download of the official `dae.asw` is **byte-identical** to the bundled
file. Its HTTP Last-Modified value is **2 June 2008, 05:15:49 GMT**. The reference
Bode PDF embeds creation date **D:20080602005353**, without an explicit timezone.
The shared calendar date supports a relationship between the posted files but
does not recover their run settings or prove they represent an identical run.
The attempted public `dae.pnt` and `dae.set` URLs return 404. The complete public
Avoni repository tree contains no Daedalus-named file. Downloads, hashes,
headers and failed requests are retained in the
[provenance receipt](../../reference/daedalus-provenance-20261113/receipt.json).

Drela's [release notes](https://web.mit.edu/drela/Public/web/aswing/version_notes.txt)
describe a plume correction in **5.83, 6 September 2008**: previously only the
first beam received the plume correctly. That postdates the PDF's creation
metadata. The disabled-plume case above measures an available documented
option; it **does not reproduce or conclusively exclude the old bug**, whose
precise erroneous behavior is unavailable. Its approximately 4% yaw change at
the dip gives no full-match explanation by itself.

## Numerical evidence and resource limits

The [serial runner](../../scripts/check_daedalus_source_operator.py) retains
immutable job plans, script snapshots, pinned physical sources and terminal
receipts. The original midpoint fields are only provisional starting guesses;
their identity is never relabeled as an accepted endpoint equilibrium. Exact
material node stations are preserved, and new-policy trim equations are solved.
The Fourier initial circulation is explicitly projected into its sine space
before correction. All accepted states receive a fresh tangent-rank check.

For the lag-disabled case, the accepted steady state remains valid because all
base circulation rates are zero. The state and input blocks are reused from
the freshly built endpoint case: disabling terms proportional to Gamma-dot
cannot change their zero-rate partials. Its mass block is recomputed, and the
complete assembled matrices are checked against the lag-disabled full residual.
Other changed physical cases receive fresh trim and complete matrix assembly.

All **268 harmonic solves** pass their numerical gates: four 65-frequency
comparisons plus eight constrained-frame samples. Matrix directional checks,
full harmonic residuals and reciprocal-condition estimates remain in the linked
results. These checks certify the calculations against their declared equations,
not agreement with Drela's reference curve.

Workers retain one BLAS thread and configured **512 MiB address-space, 15 CPU
second and 25 wall-second** caps. One Fourier geometry worker was killed at
the CPU cap and reaped; its failure is preserved. All 648 geometry columns were
then rebuilt with complete fourth-order residual stencils in 64-column batches,
including the final eight columns. No accuracy threshold was relaxed. An earlier
mixed-frame adapter attempt stopped because the reusable solver requires
immutable matrices; the corrected attempt marks the matrices immutable.
One successful baseline geometry receipt reports 15.150 CPU seconds at the
configured 15-second OS limit, so it must not be described as strictly below
that limit. Future work should keep expensive geometry assembly split.

Production equations/defaults, ISAE counts and tracked scopes are unchanged.
Node, browser, Vite, build and WASM checks remain held.

## Next comparison: motion in the animations

**Follow-up completed:** the [quantitative animation study](daedalus-animation-20261113.md)
now compares the fresh 0.2/1 Hz harmonic states with calibrated GIF images.
It supports 1 Hz local boom bending within image uncertainty, while native
Bode agreement, absolute fin motion and the mean tail shape remain open.
It also documents the PDF/GIF publication-date distinction. The following
paragraphs preserve the initial extraction's scope and limitations.

The next focus is measuring the boom and fin response in Drela's 0.2 and 1 Hz
animations, to distinguish local tail motion from its coupling into aircraft
yaw. Initial [projected boom traces](../../artifacts/daedalus-animation-trace-20261113/first-cycle-filtered/result.json)
retain 19 frames per first cycle. Their harmonic-fit residuals are **1.03 px**
and **0.69 px**. Simulation times come from frame annotations, not GIF playback
delay. The original unfiltered extraction is retained too; annotation and
palette-overlap pixels made its endpoint estimates unreliable.

These are **image-coordinate candidate landmarks**, not measured physical
deflections. Camera projection, viewing scale, occlusion and the separation of
frame motion from elastic motion still need calibration. The two animations
have different framing. The intended next check is to project the freshly
computed nodal harmonic motion into each calibrated view at native F3 amplitude
40, preserving the reference's time convention. No physical motion or phase
agreement is claimed yet.
