# UA-1 and UA-2: source review and first harmonic comparisons

Updated 2026-11-01. The user moved the active investigation from steady
aerodynamics to UA-1 and UA-2. Work uses small serial jobs with one BLAS thread.
The full project remains incomplete; steady results are retained unchanged.

The [time-domain follow-up](isae-ua-time-20261101.md) now completes two
small-amplitude timestep-refinement checks and confirms the peak-to-peak
amplitude convention from the original papers. It also corrects the physical
UA-2 reconstruction from full-span AR5 to mirrored AR10; native provenance
remains unresolved. A [finite-amplitude follow-up](isae-ua-finite-heave-20261101.md)
adds four passing attached-flow time-refinement checks at k=0.95, with finest
waveform errors of 0.0439–0.0502%; full nonlinear coverage remains unfinished.
The [UA-2 time follow-up](isae-ua2-time-20261101.md) adds four passing lift
refinement checks and two mesh checks for the AR10 reconstruction. A later
[startup study](isae-ua2-startup-20261101.md) passes four local-rate checks with
explicit variable-step refinement. Native provenance remains unresolved.
The [nonlinear UA-2 follow-up](isae-ua2-nonlinear-20261101.md) independently
derives the straight-wing vortex/load equations and adds two passing refinement
checks and one mesh check at A/c=.5, k=.95. Broader and periodic 3D coverage remains.

**UA-1 passes 148/148 equation checks. UA-2 has 222 blocked native-comparison
slots.** These are different kinds of evidence: the UA-1 target is an explicit
MATLAB implementation of ASWING's published equation, while the native origin
of the UA-2 curves is unresolved. Neither result establishes complete family
validation or nonlinear time-response accuracy.

| Scope | Result | Meaning |
|---|---:|---|
| UA-1, 4 circulation unknowns | 74/74 pass | Actual production residual/load linearization against the source equation. |
| UA-1, 8 circulation unknowns | 74/74 pass | Same comparison on a second mesh. |
| UA-2, figure incidence label 0° | 0/74; blocked | Stored curves equal a 2D equation with circulation factor 0.85. |
| UA-2, figure incidence label 5° | 0/74; blocked | Stored curves equal a 2D equation with circulation factor 0.90. |
| UA-2, figure incidence label 9° | 0/74; blocked | Same factor 0.90; native 3D setup remains unverified. |

The [completed batch](../../artifacts/isae/ua-harmonics-20261101-final/report.json)
contains two computed jobs and three unsupported records. All five finish;
the runner exits 1 because comparisons remain open, not because it timed out.
It takes 16.22 seconds including the complete source catalog preflight.
The two numerical workers take 2.47 and 3.15 seconds. The three source-only
records start no solver process.

The reference is revision `f62943df20e9e4d7d9f50e070477b22426b5f865` of the
ISAE archive. The [source audit](../../artifacts/isae/ua-source-pilot-20261101/source-audit.json)
pins both `sim_total.m` scripts, all six UA-2 harmonic FIG files and their
existing numeric extractions. No upstream MATLAB is executed.
The [report text](../../.reference/isae-validation/reports/Experimental_validation_of_ASWING_Part_1_Aerodynamics_V4.txt),
§6.5.1, PDF page 49, explicitly says that UA-1 uses a MATLAB theoretical
function instead of ASWING runs. Its Eq. 29 and the plotting script give

`B(k) = 2π i k (1 + 2 i k)/(1 + 4 i k) − π k²`.

The amplitude curves are `(A/c)|B(k)|`; the plotted phase is
`180° + arg(B(k))`. There are 15 reduced frequencies from 0 to 0.95,
four amplitude ratios 0.05, 0.1, 0.3 and 0.5, and 14 nonzero-frequency
phase values. Zero-frequency phase is undefined and is excluded by the
original script. All three incidence-labelled MATLAB blocks use `alpha=0`
in this dynamic comparison. We therefore count their **74 unique outputs**
once per mesh, rather than tripling identical targets.

The amplitude convention is explicit. With `k = ωc/(2V)`, the source bracket
corresponds to a positive-upward displacement phasor `z/c = (A/c)/2`;
equivalently, it is half the physical CL phasor per unit heave semi-amplitude/c.
The original Chiereghin paper's nomenclature independently confirms `A=2a`,
where A is peak-to-peak displacement. No fitted gain is applied to production.
The [primary-source record](isae-ua-primary-sources-20261101.json) identifies
the reviewed pages and URLs. Historical frozen plans retain the qualification
that preceded this source recovery.

The [adapter](../../scripts/isae_suite_unsteady.py) constructs a rigid rectangular
wing with unit chord and aspect ratio 200,000, zero incidence, Mach zero and
stall disabled. It centrally differentiates `evaluate_aerodynamics` with respect
to each circulation and circulation-rate unknown, plus uniform nodal heave
velocity and acceleration. The matrices and load derivatives are reused across
all frequencies. Apparent mass and circulation-rate lift both participate.
The reference formula is used only on the comparison side.

Across both meshes the maximum amplitude error is **0.0016521%**, maximum
absolute CL-amplitude error is **5.1452e-6**, and maximum phase error is
**0.0006093°**. The largest harmonic-equation residual is **3.41e-16**.
Acceptance uses `max(1e-9, 1e-4 × |reference|)` for amplitude and 0.01°
for phase. These equation tolerances cannot inherit the provisional SA 3%
allowance. Finite tip effects remain in this high-aspect-ratio construction;
two passing meshes are not proof of a spanwise convergence limit.

For UA-2, §6.5.2, PDF page 54, describes actual ASWING simulations with a
modified prescribed-motion routine, 40 circulation nodes and `dt=T/40`.
However, all **222 stored harmonic values** match the archived MATLAB
formula `B(k)` with its circulation term multiplied by 0.85 or 0.90:
maximum amplitude discrepancy **2.22e-16**, phase discrepancy **5.69e-14°**.
The UA directories contain no original `.asw` or shell driver. Thus the saved
labels alone do not establish native 3D output. The correction factors remain
source metadata and are not installed in the solver or counted as predictions.

A separate [20-panel reconstruction](../../artifacts/isae/ua-source-pilot-20261101/wing-n20.json)
and [40-panel reconstruction](../../artifacts/isae/ua-source-pilot-20261101/wing-n40.json)
exercise the actual 3D harmonic response of a full-span AR5 rectangular wing at
zero incidence. Both use the same production equations without correction
factors, take 3.12/3.93 seconds, and have residuals below 3.1e-15. Between these
meshes the maximum amplitude change is **0.0483%**, and phase change is
**0.0137°**. Compared with the corrected 2D plot formula, the 40-panel amplitude
differs by −24.97% to +13.71%, and phase by +1.81° to +13.73°.
Those differences are **not errors against verified native ASWING runs**.
This preliminary full-span AR5 interpretation is superseded for physical
reconstruction by the primary paper's semi-AR5 definition, giving mirrored
AR10. Actual native root/end-wall treatment remains unresolved, and the linear
response does not reproduce finite-amplitude single-cycle simulations.

Twenty-one focused tests pass, including actual production harmonic response,
an added-mass omission that must fail, the distinct lag-disabled response,
source provenance, rejection of forged native UA-2 successes, and serial
runner accounting. All 136 production Python files retain their prior hashes.
Only comparison tooling, tests and status documentation change. The initial
pilot's missing fixture constraint and the first batch's missing inline-blocker
hook were corrected; their failed attempts remain in the evidence directories.
The final batch above supersedes those integration attempts.

The production time-path follow-ups now include four passing [periodic checks](isae-ua1-periodic-20261101.md)
at k=0.95, verifying waveform, amplitude, phase and zero-incidence mean for all
four amplitudes. Other frequencies/incidences remain open. The
[phase-average/mean source review](isae-ua1-phase-sources-20261101.md) recovers
six linear plot curves at k=0.47/0.94. Their [numerical phase comparison](isae-ua1-phase-20261101.md)
now passes 12/12 curve checks on two meshes, including the production
steady-incidence response. Nonlinear nonzero-incidence periodic response and
independent native UA-2 comparison remain unfinished. Experimental LEV offsets
are not acceptance targets.

To repeat a fresh bounded batch, select `--adapters unsteady --cases UA-1 UA-2`
with `scripts/run-isae-suite.py`, `--workers 1`, `--max-new-jobs 1`,
`--timeout-seconds 30`, `--relative-tolerance 0` and a new output directory.
Use `--resume` for subsequent jobs. The separate reconstruction script is
`scripts/verify-isae-ua-wing.py`; run each mesh separately.
