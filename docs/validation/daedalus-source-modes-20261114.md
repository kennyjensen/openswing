# Daedalus: current modes and reduced-model Bode comparison

Modal truncation can produce a yaw dip close to Drela's drawing without
changing aircraft properties, but **the tested truncations do not match all
four published curves**. A 57-mode expansion gives 0.032415 deg/s/F3 at the
reference minimum, 4.62% below the digitized 0.033986. Increasing the expansion
to 112 modes raises it to 0.053865; the full system remains 0.074218. The
57-mode model also underpredicts yaw at 0.1 Hz by 29.68%, versus the full
system's +2.98%. This is a numerical mechanism worth distinguishing from
physics errors, not a demonstrated explanation of the historical plot.

![Four-output modal comparison](../../artifacts/daedalus-source-modes-20261114/report/modal-comparison.png)

[SVG](../../artifacts/daedalus-source-modes-20261114/report/modal-comparison.svg),
[complex comparison CSV](../../artifacts/daedalus-source-modes-20261114/report/comparison.csv),
[complete report](../../artifacts/daedalus-source-modes-20261114/report/result.json).

## Documented method and historical uncertainty

Drela's [unsteady technical description](../../reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf),
printed pp. 28–29, Eqs. 145–149, specifies the generalized eigenproblem and
shift-invert Arnoldi method. Printed pp. 31–32, Eqs. 177–189, constructs a
reduced model from selected modes and their mass-dual left vectors. The
[original manual](../../reference/aswing_doc.txt), MODE / Reduced Order Model
generation, selects slow modes by eigenvalue magnitude and requires the user
to generate modes first. Its example of 18 available modes is not a universal
aircraft default; the selected count defaults to the available count.

The [release notes](../../reference/daedalus-provenance-20261113/version_notes.txt)
introduce full/ROM Bode selection in 5.64. Version 5.78, 12 April 2008, fixes
omitted conjugate modes. Version 5.80, 1 July 2008, lists fixes for acceleration,
Earth position and heading outputs; those are not direct yaw-rate outputs.
The [publication-history check](daedalus-animation-20261113.md) dates the Bode
PDF to June 2008 but does not identify its selected method or mode count.
There is still no evidence that this particular drawing used a ROM.

## Controlled current-model comparison

Every result uses the same saved 6.7 m/s source-equation/SEGSPL equilibrium,
literal `dae.asw`, 82 pointwise circulation coordinates and complete 2,044-state
descriptor. Input is one native F3 unit. No mass, stiffness, damping, aerodynamic
coefficient, operating constraint or physical parameter is fitted.

| Model | Yaw at 1.157378 Hz, deg/s/F3 | Error versus drawing there | Yaw error at 0.1 Hz | Yaw RMS magnitude error, dB |
| --- | ---: | ---: | ---: | ---: |
| Full system | 0.074218 | +118.38% | +2.98% | 1.781 |
| 28 modes | 0.070286 | +106.81% | −3.65% | 11.710 |
| 57 modes | 0.032415 | −4.62% | −29.68% | 6.549 |
| 112 modes | 0.053865 | +58.49% | −12.93% | 2.273 |

The RMS statistic uses the 61 equally spaced log-frequency samples from
0.1–10 Hz; four inserted diagnostic frequencies remain in the plotted/data
comparison but are not given extra RMS weight. The 57-mode yaw minimum on
the saved grid is at 1.165914 Hz. Its other outputs at the reference frequency
still differ by **−19.59% roll, +15.78% sideslip and −38.75% bank**. Thus the
single close yaw value is not a four-output pass or a reason to replace the
full-system solution with a particular truncation.

Queries request 28, 56 and 112 poles near the fixed real shift −0.01 s⁻¹,
then sort the computed poles by magnitude. The 56-pole cutoff intersects a
complex pair; completing its conjugate gives 57 real modal coordinates.
All reported truncations retain complete pairs. Requested cutoffs
4/8/12/16/20/24/28/40 and the complete available sets are retained in the
report; the 40-mode request retains 39 rather than splitting the next pair.
Counts were not selected to minimize reference error. The queries do not
prove completeness of the finite spectrum, and 112 modes are not yet a
converged replacement for the full-system response.

## What cancels near the dip

Two strong current-model pairs have damped frequencies **1.252462 and
1.297750 Hz**. Their individual yaw contributions at 1.157378 Hz are:

| Pair eigenvalue, s⁻¹ | Complex yaw contribution, deg/s/F3 | Magnitude |
| --- | --- | ---: |
| −4.956795 ± 7.869451 i | −0.084003 − 0.043058 i | 0.094396 |
| −6.939570 ± 8.154006 i | +0.108477 + 0.093529 i | 0.143230 |

These complex contributions partially cancel each other and other modes.
Their magnitudes must not be added. These are coupled aircraft modes, not an
identification of either pair as an isolated tailboom resonance. The older
[modal study](daedalus-low-frequency-modes.md) used a different 2,215-coordinate
operator and remains separate evidence.

## Numerical checks and limits

Earth position and heading are unobservable in these four outputs. Position
coordinates can be removed directly; heading **rate** also enters the
bank/elevation equations at the pitched equilibrium, so it must first be
eliminated by a row operation. The initial attempted row/column deletion was
rejected. Fresh full-system solves at 0.1, 1.157378 and 10 Hz agree with the
retained-state solve within 9.690e−12 and with the saved outputs within
2.727e−12. No physical dynamics are discarded by this cyclic-coordinate step.

The larger query needed targeted two-sided inverse iteration for 26 columns,
processed in batches of at most 12. Checks remain on the original pencil;
no tolerance was relaxed. The accepted 112-mode mass-pairing error is
6.941e−6 against its fixed 2e−5 gate. Independently solving each projected
system agrees with the corresponding residue sum within 8.568e−10. The
57-mode response recovered from the larger query agrees with the first
query's result within the report's 2e−7 absolute gate.

A separate [contour calculation](../../artifacts/daedalus-source-modes-20261114/contour-v3/result.json)
checks the two strongest complex-pair residues without left eigenvectors in
its estimator. Sixteen resolvent samples on each radius-0.2 s⁻¹ circle agree
with the modal residues within **6.044e−9 relative** across the four outputs;
the 8-to-16-node change is at most **2.621e−8**. Cyclic coordinates are recovered
after each solve and all 2,044 original equations are checked. This is a
numerical residue check, not an independent aerodynamic or native-ASWING
validation.

All 23 jobs are terminal and reaped: 12 successes and 11 retained rejected
attempts. Rejections cover incorrect cyclic-elimination assumptions, pole
accuracy gates, the 12-column batch cap and bounded memory failures. Repeated
NPZ decompression was fixed by loading each vector matrix once. Real-factor
initialization and exact cyclic-coordinate elimination avoid the observed
OpenBLAS/SuperLU allocation failures without raising resource limits.
Every job used one BLAS thread, 512 MiB address space, 15 CPU seconds and
25 wall seconds. Maximum observed RSS was 337.68 MiB on a rejected attempt;
the final comparison used 131.03 MiB. Maximum CPU/wall times were 8.78/10.79 s.
No solver remains running. Browser/build jobs and ISAE fractions are unchanged.

Reproduce with the [modal driver](../../scripts/check_daedalus_source_modes.py)
and [contour/report driver](../../scripts/report_daedalus_source_modes.py), using
fresh tags and small serial jobs. Plans retain input hashes and the exact
runner version, including rejected attempts.

The next useful scope is the saved eight-Fourier-coefficient model from the
[operator-options comparison](daedalus-operator-options-20261113.md). Its full
Bode response barely changes, but its 32 circulation coordinates replace
82 pointwise coordinates. That changes how a fixed number of slow temporal
modes samples the aerodynamic states. Comparing those documented spatial
and temporal truncations can test the ROM hypothesis more faithfully;
it still cannot authenticate an unknown historical setting or justify fitting
a mode count to one dip.
