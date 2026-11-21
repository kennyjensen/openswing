# ST-3 additional static and modal comparisons

2026-11-04. Exact still-air calculations for all three original modal layups
match **8/9** ASWING workbook frequencies within their recorded decimal
intervals when compared as ascending three-frequency sets. All **9/9**
64→128 interval mesh checks pass. This does not resolve the disputed modal
labels or authenticate the original ASWING operating settings.

| Literal layup | ASWING frequency set (Hz) | OpenSwing, 128 intervals (Hz) | Conditional matches |
|---|---|---|---:|
| 0_3_90 | 3.7, 24.3, 25.9 | 3.798389, 24.267960, 25.912461 | 2/3 |
| p15_0 | 3.63, 22.5, 26.6 | 3.629656, 22.525354, 26.585569 | 3/3 |
| m15_0 | 3.62, 22.5, 26.6 | 3.621312, 22.481931, 26.578141 | 3/3 |

Remaining recorded-precision failures:

- `0_3_90`, rank 1: +0.098389 Hz (2.659%), versus a ±0.05 Hz interval.

Each job uses the unchanged vertical-wing `.asw`, upright self-weight
gravity [0, 0, −9.81], stationary fixed frame, density 1.23 and **exactly zero
mean flow**. The current `drela-fixed-still-air-v1` operator retains thin-strip
apparent inertia. No small positive airspeed, property fit, reduced mode model
or altered native frequency is substituted. The full descriptor search retains
12 eigenpairs; the three lowest positive frequencies are selected before
looking at the workbook, with complete saved modal outputs.

Six serial cold calculations took **231.47 seconds**
in total. Six fresh restored equilibrium checks pass. All 144 reported left/
right eigenvector residual checks pass, with maximum backward error
3.68e-16. Mechanical-shape comparisons
track the same branches across meshes, with minimum MAC
0.999996921. These are numerical checks, not
native eigenvector comparisons; archived eigenvectors are unavailable.

The workbook labels the coupled columns differently from Dunn’s original
table. The [existing source audit](isae-st3-sources.json) retains that conflict.
The new comparison preserves every original label and reports the frequency
set separately. Half-last-recorded-place intervals follow the workbook’s
General-format numeric tokens and report Table 5, interpreted as rounded
values; they are not experimental uncertainty. Density, orientation and mesh
are declared settings rather than recovered native startup.

## Separate static snapshot

The literal `Static_Deflection_analysis/test.asw` contains one 4.905 N point
weight on the beam reference axis, zero pylon offset, zero bending–torsion
coupling, and zero distributed weight. The documented Weight convention uses
absolute undeformed point coordinates; `Xax` does not move that point off axis.
A 64-interval solve gives a planar equilibrium with exactly zero twist and
zero applied My. Its fresh restored residual is 4.35e-16; force and moment
balance pass. Tip y/z are 0.522235/−0.179008 m, inside the listing’s coarse
printed y/z intervals.

However, `test.txt` reports **6.39° tip twist and 0.3158 N·m My**. Both
torsional quantities differ by 100% from the centered-load result. No reviewed
driver writes `test.txt`; the retained three static scripts write `temp.txt`.
The same-name files cannot be treated as an authenticated matching run.
No input is modified to create the missing torsion, and no native pass is
added for this diagnostic. The failed first reporting wrapper is retained;
its saved solve was restored and checked without a second cold solve.

The original **930/1,080** static baseline remains unchanged. This supplemental
modal comparison expands tested layup coverage but does not complete ST-3.
The modal cases were subsequently [integrated into the shared suite](isae-st3-suite-integration-20261104.md);
the remaining frequency discrepancy and historical setup remain open.
No production or application code changed.

[Portable results](isae-st3-additional-20261104.json). Full plans, unchanged
source pins, modal outputs, process logs and the static diagnostic are retained
under `artifacts/isae/st3-additional-20261104/`.
