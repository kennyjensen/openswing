# Daedalus: Fourier circulation and temporal mode truncation

The documented Fourier circulation representation **does not resolve the
current Bode discrepancy**. It changes how many temporal modes are needed to
cover a given range of eigenvalues, but the close yaw minimum remains a
truncation effect accompanied by poor agreement elsewhere. No aircraft
parameter, production equation, default or ISAE fraction changed.

![Matched pole ranges](../../artifacts/daedalus-fourier-modes-20261114/report-v2/matched-cutoffs.png)

[Four-output figure](../../artifacts/daedalus-fourier-modes-20261114/report-v2/fourier-modes.png),
[matched-range SVG](../../artifacts/daedalus-fourier-modes-20261114/report-v2/matched-cutoffs.svg),
[complex data](../../artifacts/daedalus-fourier-modes-20261114/report-v2/comparison.csv),
[complete report](../../artifacts/daedalus-fourier-modes-20261114/report-v2/result.json).

## Scope and primary references

Drela's [steady technical description](../../reference/aswing-authoritative-20261108/drela-aswing-steady.pdf),
printed p. 15, Eqs. 62–63, explicitly permits pointwise circulation or a Fourier
series in Glauert angle. The [unsteady description](../../reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf),
printed pp. 28–29 and 31–32, Eqs. 145–149 and 177–189, supplies the modal
eigenproblem, shift-invert calculation and reduced-model projection. Spatial
circulation coefficients and temporal eigenmodes are different quantities.

This comparison uses the already checked
[eight-coefficient Fourier case](daedalus-operator-options-20261113.md):
32 circulation coefficients, 82 lifting intervals, 108 structural nodes and
1,994 dynamic coordinates. The pointwise comparison has 82 circulation
unknowns and 2,044 coordinates. Both use literal `dae.asw`, 6.7 m/s, PG Mach
0.1, the source-equation/SEGSPL operator, aerodynamic lag and plume enabled.
Each uses its own previously converged equilibrium and complete saved matrices;
the pointwise equilibrium is not silently relabeled as a Fourier solution.

No new trim, aerodynamic linearization or physical-parameter sweep was run.
The full responses already agree in yaw magnitude at the reference dip within
0.0046%: **0.074218 pointwise / 0.074214 Fourier**, versus **0.033986** in the
digitized drawing.

## Matching mode ranges instead of counts

The two strongly cancelling complex pairs occur around 1.25 and 1.30 Hz in
both models. Both pairs are included within the first **21 Fourier-model
temporal modes**, versus **32 pointwise-model modes**. Simply retaining the
same number of temporal modes therefore selects different dynamics.

The following cutoffs were selected on eigenvalue magnitude, with complete
conjugate pairs retained. The rate units are s⁻¹; the cutoff is not a damped
oscillation frequency in Hz.

| Pole-magnitude cutoff | Pointwise modes | Fourier modes | Pointwise yaw at reference dip | Fourier yaw at reference dip | Fourier yaw error at 0.1 Hz |
| --- | ---: | ---: | ---: | ---: | ---: |
| 20 s⁻¹ | 55 | 38 | 0.032497 | 0.033492 | −28.83% |
| 40 s⁻¹ | 79 | 55 | 0.073673 | 0.073708 | +2.80% |
| Full system | — | — | 0.074218 | 0.074214 | +2.92% |

Yaw units are deg/s per native F3 unit. At the 20 s⁻¹ cutoff, the Fourier
result is only **1.45% low at the reference minimum**, but roll, sideslip and
bank there still differ by **−18.92%, +15.58% and −38.03%**. Its yaw RMS
magnitude error over the 61-point 0.1–10 Hz log grid is **6.461 dB**, versus
**1.785 dB** for the full Fourier system. The complete report also retains
the predeclared 5 and 10 s⁻¹ cutoffs and their distances from computed poles.
No cutoff was fitted to the drawing.

The fixed-count comparison gives the same warning. Forty Fourier-model
temporal modes give **0.033366** at the dip (−1.82%), but yaw at 0.1 Hz is
**28.92% low**. Fifty-seven modes give 0.073646; 65 give 0.049038. The sums
need not converge monotonically because complex modal contributions cancel.
The close single-frequency values are not new native-reference passes.

## Numerical verification

The serial queries request 64 poles near the fixed real shift −0.01 s⁻¹;
completion of the last conjugate pair gives 65 modal coordinates. Targeted
two-sided inverse iteration improves 25 columns in batches of 12, 12 and 1.
The original-pencil and pairing tolerances are unchanged. An attempted
comparison before those refinements finished was rejected by the pole-pairing
gate and retained as failed evidence.

The accepted mass-pairing error is **1.972e−7** against its fixed 2e−5 gate.
Independent projected-system solves agree with the residue sums within
**1.094e−9**. Exact cyclic-coordinate elimination retains all observable
dynamics; fresh full-matrix solves at 0.1, 1.157378 and 10 Hz agree with the
retained state within **3.576e−13** and with the saved outputs within
**2.067e−13**. These are numerical checks, not native-ASWING validation.

The [shared modal driver](../../scripts/check_daedalus_source_modes.py) now
accepts explicit source/study paths and obtains coordinate indices from the
saved layout. Its default pointwise matrices, forcing, outputs and retained
indices are checked **exactly equal** to the
[archived preceding implementation](../../artifacts/daedalus-source-modes-20261114/shared-driver-8ae6737824e3.py).
The [report driver](../../scripts/report_daedalus_fourier_modes.py) uses only
saved responses and modes. All nine jobs are terminal and reaped: eight
successes and one rejected comparison. Maximum observed RSS is 113.13 MiB,
CPU time 4.57 s and wall time 7.91 s. Limits remain one BLAS thread, 512 MiB
address space, 15 CPU seconds and 25 wall seconds. Browser/build jobs remain
held; no solver is running.

The comparison covers these two circulation representations and the stated
mode selections. It does not prove completeness of the finite spectrum or
convergence of every reduced response, nor identify the historical plot's
method, operating settings or mode count. It weakens modal truncation as a
whole-curve explanation and provides no basis for changing the full solver
to deepen one dip. Further work needs a documented physical or setup
difference that improves the complete response, rather than selecting a
truncation solely for its minimum.
