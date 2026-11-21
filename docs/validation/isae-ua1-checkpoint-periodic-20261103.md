# UA-1: complete checkpoint-corrected periodic verification

Updated 2026-11-03. **All 12 frozen accuracy gates pass** for the current-source
four-cycle repeated-stall supplement. This completes the two-grid Python study;
the complete browser comparison and native ASWING agreement remain open.

The runs use 320 and 640 steps/cycle, a fresh cold equilibrium on each grid,
the complete forcing history before startup, and the same independently derived
DOP853/Radau reference used by the earlier study. Both references and all source
files are hash-verified. No production equations, nonlinear tolerances, physical
inputs or acceptance limits changed during the revalidation.

**3,840 steps converge with zero rejections**, with **3,842 unique states and 190
restart boundaries checked**. Every current state and BDF predecessor retains
displacement coordinates that exactly reconstruct its physical positions.
The maximum local acceleration is **7.532555e-17 m/s²**,
below the unchanged **2e-8** limit. The earlier checkpoint precision failure
does not recur in either complete history.

| Fourth-cycle waveform | 320 steps/cycle | 640 steps/cycle |
|---|---:|---:|
| Lift | 0.064649% | 0.016880% |
| Circulation | 0.040246% | 0.011519% |
| Circulation rate | 0.121000% | 0.033317% |
| Pressure drag | 0.256364% | 0.066288% |

The **0.1% waveform limit applies to the fine result**, with circulation and
circulation rate checked on every strip. Cold-history waveform gates also pass.
The largest fine/coarse error ratio across cold and periodic quantities is
**0.286205**, below the unchanged **0.35** limit. This establishes actual
timestep improvement; the coarse rate/drag errors are retained as coarse failures
of the fine-result threshold, not removed or accepted under a looser limit.

The largest third-to-fourth-cycle change is
**0.0000190%**. Fine position and velocity
errors are **0.007211%** and
**0.003236%** of their prescribed motion scales.
Mean lift, lift amplitude, lift phase, startup rate, nonlinear residual, settling
and repeated stall checks also pass. Lift phase error is
**0.0010280 degrees**.

This is a **supplemental equation-based case** with declared section limits
±1.5, mean incidence 9°, reduced frequency 0.94 and peak-to-peak A/c=0.5.
It is not recovered native UA-1 input or proof of general dynamic-stall physics.
The [published harmonic benchmark](isae-ua1-checkpoint-periodic-progress-20261103.md)
continues to pass 148/148 on these identical solver bytes. Registered case
counts do not change: this revalidates the existing periodic supplement with
expanded physical-state checks after the checkpoint corrections.

The built-browser four-cycle comparison is next. Broader UA-2 current-source
time/mesh/browser validation remains pending, and its 222 native comparison
slots remain unverified because the saved curves reproduce corrected 2D formulas.
The full ASWING replacement remains incomplete.

Evidence: [combined raw-history audit](../../artifacts/isae/ua1-stall-chart-periodic-20261103/audit.json),
[completion summary](isae-ua1-checkpoint-periodic-20261103.json), and the retained
[coarse-stage report](isae-ua1-checkpoint-periodic-progress-20261103.md).
