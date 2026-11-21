# UA-2: source displacement precision correction in progress

Updated 2026-11-03. The source beam translation residual now retains small
jig-relative translations and strains. **All four fresh startup/continuation
intervals pass on 20/40 strips**, and **27 focused tests pass**. The full selected
study remains incomplete: **4/8 pass, two legacy replays fail one physical gate,
one replay hit its time limit and one is pending**. No native ASWING pass is added.

The original 40-strip cold start produced spurious spanwise acceleration of
**3.697454e-4 m/s²**. Absolute node coordinates jumped by about 4.44e-16 m during
1.817e-6 s startup steps. Eq.48 used these reconstructed absolute positions,
so subtraction lost the displacement information already retained by BDF and
checkpoints. The corrected residual evaluates the same equation from the stored
relative translations and keeps strain separate from the unit span tangent.
It retains the original reference defect, rotations, constitutive law and
normalization. No clipping, rigid-motion override, empirical gain or tolerance
change is introduced.

The corrected 40-strip cold maximum is **5.367804e-14 m/s²**, below the unchanged
**2e-8** local-motion bound. Aerodynamic errors are essentially unchanged.
Five new tests check sub-ULP translations, sub-ULP strain and equivalence to the
literal finite-rotation equation. Sixteen existing source-structure tests and
six complete-residual/matrix-derivative tests also pass. A prior combined test
command reached its 45-second job cap; the separate completed test files provide
the 27-pass count, without counting the interrupted run.

| Interval | Initialization | Status | Maximum local acceleration, m/s² | Largest lift/circulation/rate waveform error |
|---|---|---|---:|---:|
| n40-part000 | cold | pass | 5.367804e-14 | 0.000025% |
| n40-part001 | owned_continuation | pass | 3.808590e-26 | 0.000024% |
| n40-part290 | legacy_replay | fail | 2.866640e-08 | 0.005265% |
| n40-part300 | legacy_replay | fail | 2.886132e-08 | 0.003368% |
| n20-part000 | cold | pass | 1.853385e-14 | 0.000003% |
| n20-part001 | owned_continuation | pass | 4.149285e-25 | 0.000003% |
| n20-part290 | legacy_replay | time limit | — | — |
| n20-part300 | legacy_replay | pending | — | — |

Waveform errors retain the earlier full-history independent-reference scales,
including each strip's own circulation/rate scale. All completed intervals
converge for 16 steps with zero rejections and pass the existing 0.1% waveform
limits. Current fresh trajectories cover 32 startup steps per mesh; they are not
fresh eight-cycle histories or new temporal-refinement evidence. The later
intervals explicitly replay original checkpoints, with the full forcing and
BDF predecessors retained.

Both completed legacy 40-strip intervals exceed only the local-motion bound:
**2.87–2.89e-8 m/s²**, versus 2e-8. The same first legacy interval also fails with
the frozen pre-correction kernel (**2.463153e-8 m/s²**), so this failure predates
the source-displacement correction. Its corrected maximum is 2.866640e-8 m/s².
The replay retains old, already-rounded state/history information; it is not
silently projected onto a new equilibrium or reinitialized. Failed gates remain
failures. The baseline probe finished and saved its full trajectory before a
reporting assertion expected a browser-only provenance field. Its retained
output was reassessed without another solve; the launcher had verified every
frozen module and its imported source module path before execution.

The remaining 20-strip legacy replay reached 45 seconds before producing a result.
It will be recovered in eight-step requests with unchanged physical time nodes and
BDF history; the original timeout remains recorded. Browser verification of this
correction is pending. Public/dist kernels and downloads still contain the
preceding source version and have not been advertised as updated.

The previous harmonic, time-refinement and periodic studies retain their
original source hashes. The 222 native UA-2 comparison slots remain unverified.
Finish the bounded regression/browser assessment, then proceed to **ST-1 through
ST-6** as requested; unrelated interface/storage work does not delay that
sequence. Neither UA-2 nor the full project is declared complete.

[Machine report](isae-ua2-displacement-progress-20261103.json) · [Corrected study](../../artifacts/isae/ua2-displacement-time-20261103) · [Retained original failure](../../artifacts/isae/ua2-time-current-20261103).
