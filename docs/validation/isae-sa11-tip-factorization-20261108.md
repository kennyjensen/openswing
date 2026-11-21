# SA-11: separate circulation sampling from force quadrature

2026-11-08 UTC. **The full main-wing/winglet force change is dominated by
circulation sampling and response, not receiver quadrature.** At the two
checked incidences, receiver quadrature contributes about **0.90%**, the main
circulation step distribution **47.5%**, and winglet circulation **51.6%**.
This refines the interpretation of the preceding finite-origin wake audit:
its large separated receiver terms mostly cancel with half-wake terms.

Eight main-only Fourier trials do **not** establish a remedy. All compute,
but the main-46 / 20-mode upper-winglet state has **53.15% CD error** and a
**26.04% local flow defect**, despite satisfying the projected equations.
Two main-32 / 30-mode states also retain failed numerical diagnostics due to
severe conditioning. No equation, default, tolerance or primary scope changes.
The paper suite remains **21/48**, original archive **1,060/9,184**.

[Plot and full data](../../public/isae-sa11-paper/circulation-sampling.html),
served at `/isae-sa11-paper/circulation-sampling.html`.

## Source basis and exact scope

The [authoritative index](aswing-authoritative-references.md) and checksummed
[catalog](aswing-authoritative-sources.json) were consulted. Drela steady
**Eqs.62–63** describe pointwise and Fourier circulation; **Eqs.64–70** give
the velocity and local force; **Eqs.149–161** define vortex geometry and PG
mapping; **Eqs.200–204** prescribe tangency, Fourier weighting and stall leakage.
Jan Part I **p.35 / Figure 22 p.39** supplies the SA-11 context. His **§5, p.21**
recommendation of 20–40 circulation variables concerns an elliptical-wing
study; it does not identify the original SA-11 mode count or mode domain.

The [local-tip control](isae-sa11-winglet-interactions-20261108.md) preserves
the inner 28 main intervals and both 16-interval winglets, changing main 32 to
46 intervals only near the tips. Here we reuse its upper-winglet states at
**240 m/s, 2.75° and 3°**. Frozen body-x influence geometry, actual incidence
for drag projection, PG Mach 240/340.21, density 1.2256, section data, stall
law and zero shared-surface core remain fixed.

The attribution covers **cross-beam vortex drag at fixed incidence**. It is
not an attribution of all drag terms or of the earlier CL = 0.5 interpolation.
Original source files and the disclosed report-derived model remain distinct;
the historical generating input, mesh and mode settings remain unrecovered.

## Common intervals reproduce both saved fields

The two main meshes have 48 intervals in their union. Each original straight
bound segment is split at these shared material boundaries. Equal inherited
circulations make the new internal trailing legs cancel exactly. For force
reduction, split the original interval weight but duplicate its original
receiver and frame. This reproduces the original discrete force without
resampling its solution or inventing a continuous circulation interpolant.

The shared representation has 48 main and 32 winglet algebraic intervals.
It is **not** a new physical mesh; the minimum-spacing rule is unchanged.
Source polylines differ only by **1.11e−16 m** after subdivision. Their
contribution to the observed force change is zero at the reported precision.

All 16 combinations of four factors are evaluated:

- Receiver positions, span frames and force weights.
- Source polyline geometry.
- Main-wing piecewise-constant circulation distribution.
- Winglet circulation at its unchanged intervals.

The main-circulation factor includes **source sampling and jump locations as
well as amplitudes**. It must not be interpreted solely as a change in smooth
physical loading. Hybrid combinations are algebraic diagnostics, not converged
states, and are never used for reference passes.

Symmetric attribution averages each factor's marginal effect over every order
of applying the changes. A separate checker averages all 24 orders directly.
The assigned contributions sum to the full cross-beam force change.

| Incidence | Full cross-beam ΔCD change | Receiver quadrature | Main circulation steps | Winglet circulation |
|---|---:|---:|---:|---:|
| 2.75° | +0.000786502 | 0.9043% | 47.5071% | 51.5886% |
| 3° | +0.000846357 | 0.9041% | 47.4982% | 51.5977% |

At 3°, receiver changes alone contribute **+0.001248658** to the separated
finite-origin term, but only **+0.000007652** to the full interaction. The
half-wake contribution largely cancels it. Thus the earlier location finding
remains useful, but a large finite-origin term alone does not establish a
force-quadrature defect. This does not rule out every same-beam integration
issue elsewhere in the configuration.

## Independently replay the unchanged winglet constraints

Both winglet control-point sets are identical. Rebuild their zero-core PG
influence matrix independently, including the bound segment, physical normal
and small saved stall-leakage term. With main circulation prescribed, solve
the 32-by-32 conditional winglet equations:

```text
A_ww Gamma_w = leakage − freestream_normal − A_wm Gamma_m
```

This conditional linear replay recovers all four saved winglet distributions
within **7.45e−16 relative error**. Its matrix condition number is **9.94**.
The winglet circulation changes by **2.87–2.89% in vector norm** between the
meshes. Outer-main forcing supplies **102.88%** of that change's signed
projection; interior-main forcing opposes about **2.88%**. The stall-leakage
contribution is below **0.000005%**. Response vectors and their norms are
retained so cancellation is visible.

The maximum change in the *main-induced component* of winglet normal control
velocity is **35.68–37.00 m/s**. The winglet's own response balances this;
it is not the total tangency defect or section-normal speed. All underlying
states remain valid under the unchanged local-Mach gate. This check therefore
supports a circulation-coupling/discretization investigation, not a stalled
Newton iteration or a stall-model repair.

## Main-only Fourier trial: all eight outcomes retained

At **240 m/s and 3°**, use the same bare/upper models and main 32 / local-tip
46 meshes. Change only the main beam to **20 or 30 Fourier modes**. Winglets
remain pointwise at 16 intervals each. No mesh or mode count is selected by
its reference error, and no count is asserted to be a native SA-11 default.

| Upper-winglet representation | Main intervals | CD error against archive | Maximum local tangency defect / V |
|---|---:|---:|---:|
| Pointwise control | 32 | +2.88% | below 1e−12 |
| Fourier 20 | 32 | +2.88% | 0.2451% |
| Fourier 30 | 32 | +2.89% | 0.0949% |
| Pointwise control | 46 | −4.31% | below 1e−12 |
| Fourier 20 | 46 | +53.15% | 26.0440% |
| Fourier 30 | 46 | −3.19% | 3.8507% |

All eight new physical calls compute without rejection, with maximum normal
Mach **0.66476** and minimum lift-limit margin **17.17 transition widths**.
Independent zero-core velocities, total forces, moments, normal Mach and
local/projected residual reconstruction pass for all eight.

**Six of eight pass every tight numerical diagnostic.** Both main-32 /
30-mode cases retain two failed checks:

- Reconstructing circulation from exported sine coefficients misses the
  2e−10 absolute diagnostic gate: errors are **1.44e−9** and **1.53e−9 m²/s**.
- An independent conditional projected solve misses the 2e−9 relative gate:
  differences are **3.23e−8** and **4.04e−8**.

Their sine-sampling condition number is **7.00e6**; the projected matrices
have condition numbers **2.65e13** and **1.19e14**. These small numerical
discrepancies are recorded, not presented as native-reference failures or
discarded to improve a score. The gates remain unchanged.

The much larger 20-mode / main-46 discrepancy is a **different issue**. Its
projected matrix condition number is only **224.46**, and independent equations
reproduce its circulation within **1.47e−15 relative error**. The projected
residual is around **1.2e−15**, while the maximum local residual is 0.26044.
The weighted Fourier equations are solved accurately but do not constrain the
unresolved local flow. The trial provides no reason to adopt this truncation.

The next useful work is the main-tip circulation representation and its
coupling to the winglet, while preserving the source-defined distinction
between logical beams, physical surface indices and structural joints. A
merged Fourier domain or imposed circulation continuity needs independent
source justification; it cannot be inferred from a better integrated score.

![Circulation and Fourier diagnostics](../../artifacts/isae/sa11-tip-factorization-20261108/circulation-sampling.svg)

## Verification and retained execution evidence

The [combined analysis](../../artifacts/isae/sa11-tip-factorization-20261108/analysis.json)
authenticates **602 pins**, retains every combination, failed gate and source
reference, and links the individual reports. Original discrete forces are
reconstructed within **8.68e−19 in CD**. Independent permutation attribution
agrees within **2.17e−19**; conditional winglet response closes within
**7.00e−15 m²/s**. No production equation or default changed.

All jobs ran serially with one BLAS thread, 512 MiB address space and
15 CPU / 25 wall seconds per process. The longest recorded two-solve Fourier
batch was **2.38 seconds**, peak RSS **181.94 MiB**. The longer independent
diagnostic calls also completed within their caps. No background, browser,
Vite or build tests were started.

Preparation/checker failures remain recorded: the initial endpoint check
required bitwise rather than roundoff identity; the first Fourier plan omitted
recorder preflight; the older checker rejected new configuration labels; and
a diagnostic JSON writer initially encountered a NumPy boolean. Their retained
scripts, receipts and partial output document the corrections. No physical
solve was repeated or discarded. The two failed strict Fourier audits remain
failed in the complete diagnostic report. The plot was visually inspected.

Evidence: [factorization plan](../../artifacts/isae/sa11-tip-factorization-20261108/plan.json),
[conditional-check plan](../../artifacts/isae/sa11-tip-factorization-20261108/constraint-plan-r2.json),
[Fourier plan](../../artifacts/isae/sa11-tip-fourier-r2-20261108/plan.json),
[2.75° attribution](../../artifacts/isae/sa11-tip-factorization-20261108/a11/report.json),
[3° attribution](../../artifacts/isae/sa11-tip-factorization-20261108/a12/report.json).

Scripts: `audit_sa11_tip_factorization.py`, `check_sa11_tip_factorization.py`,
`verify_sa11_tip_fourier.py`, `check_sa11_tip_fourier.py`,
`check_sa11_tip_fourier_diagnostics.py`, `analyze_sa11_tip_factorization.py`
and `plot_sa11_tip_factorization.py`, all under `scripts/`.
