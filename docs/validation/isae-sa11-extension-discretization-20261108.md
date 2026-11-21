# SA-11 extension: physical mesh versus circulation mode count

Changing from pointwise circulation to **20, 30 or 40 Fourier modes** changes
the archived total-drag error by at most **0.182 percentage points** at the
four checked states. Every 5% decision remains unchanged. The much larger
effect is the physical horseshoe mesh, consistent with the preceding
[force-budget and receiver audit](isae-sa11-extension-drag-budget-20261108.md).

All eighteen new calls complete with the original equations and the fixed
**16.466 mm minimum horseshoe spacing**. These are disclosed diagnostic
alternatives; the primary result stays **1,060/9,184**.

![Physical mesh and mode count](../../artifacts/isae/sa11-extension-practical-mesh-20261108/extension-discretization.png)

[Standalone SVG](../../artifacts/isae/sa11-extension-practical-mesh-20261108/extension-discretization.svg).
The figure uses the application palette and was visually inspected. Lines
connect the sampled counts; they do not prove convergence between samples.

## Source basis and unchanged conditions

The [authoritative reference index](aswing-authoritative-references.md) and
[catalog](aswing-authoritative-sources.json) were consulted. ISAE Part I
**§5, p. 21** recommends 20–40 circulation variables or Fourier coefficients
from an elliptical-wing study. This motivates the fixed count range; it does
not identify the native SA-11 counts or guarantee convergence on a swept wing.

Drela's steady description **Eqs. 150–153 and 200–204** provides the sine
representation and weighted residual. One logical beam forms this extension
model, so the connected-multibeam Fourier-domain uncertainty from the winglet
studies does not apply here.

All cases retain the original extension ASW file, section parameters, 3°
aircraft incidence, 240/272 m/s, density 1.2256, current-wind influences,
automatic speed-dependent PG Mach, natural-v1 input interpolation, stall law,
force definitions and numerical gates. Minimum spacing and mandatory stations
are fixed. No original reference or input is repaired.

## Fourier counts at fixed physical meshes

The existing nominal 64/128 requests produce 60/108 intervals after minimum
spacing. Four previously verified pointwise states are reused. Twelve new
calls use all three prescribed Fourier counts on both meshes at both speeds.

| Speed | Actual intervals | Pointwise CD error | 20 modes | 30 modes | 40 modes |
|---|---:|---:|---:|---:|---:|
| 240 m/s | 60 | −7.249% | −7.249% | −7.235% | −7.256% |
| 240 m/s | 108 | −4.236% | −4.060% | −4.224% | −4.231% |
| 272 m/s | 60 | −8.411% | −8.418% | −8.399% | −8.421% |
| 272 m/s | 108 | −4.965% | −4.783% | −4.954% | −4.960% |

Each mode setting independently gives **24/28** matching scalar comparisons,
the same outcome as the four pointwise controls. These three alternatives are
not added together or to the primary total. Only drag and CD fail, on the
60-interval mesh. All twelve states are accepted by the unchanged numerical
gates; maximum normal Mach is **0.76138**, and all sections are at least
**18.85 stall-transition widths** inside their limits.

The sine basis and projection were reconstructed without the production
basis helper:

```text
S_ik = sin(k (theta_i + theta_(i+1))/2)
T_ki = (2/pi) S_ik (theta_i − theta_(i+1))
Gamma = S A
R_projected = T R_local
```

Maximum circulation reconstruction error is **4.16e-13**, projection error
**7.11e-19**, and the converged projected residual **1.32e-16**. Local residual
maxima are **0.00201–0.02149 of freestream**. A truncated Fourier projection
does not require each local residual to vanish; no extra local-residual
threshold is introduced or used to conceal the distinction.

An independently assembled tangency operator uses the retained AVL
segment/ray algebra in extended precision, zero core and the exact
Biot–Savart constant, rotated into the actual wind frame. Solving its
projected linear system reproduces the nonlinear production circulation
within **5.28e-9 relative**. The small nonzero stall leakage remains in the
production calculation; it is omitted only from this separate linear check.
Reintroducing the printed Eq. 204 leakage reproduces the saved local residual
within **4.94e-15**. This supports the implemented projected equations and
rules out an unconverged circulation iteration as the cause at these points.

## Pointwise interpretation of the recommended range

Six additional cases use cosine 20/30/40 interval requests, keeping the same
minimum. Mandatory stations give 26/34/44 actual intervals and pointwise
unknowns. All counts were declared before these six solves.

| Requested intervals | Actual intervals | CD error, 240 m/s | CD error, 272 m/s |
|---:|---:|---:|---:|
| 20 | 26 | −12.327% | −14.070% |
| 30 | 34 | −10.165% | −11.670% |
| 40 | 44 | −9.857% | −11.327% |

Each case matches five of seven fields; only drag and CD fail. The separate
diagnostic outcome is **30/42**, not an addition to the primary score. Maximum
normal Mach is **0.6730**, residual **2.28e-16**, and minimum stall margin
**18.84 widths**. The independent linear circulation check agrees within
**5.64e-9 relative**; scalar force/moment coefficient reductions agree within
**2.23e-16**.

Thus the report's general count recommendation does not recover the archived
extension drag in this setup. The smaller meshes worsen the discrepancy,
while more Fourier coefficients on a fixed mesh have little effect. This
evidence does not authenticate the native mesh, establish a converged force
limit, or justify a fitted drag correction.

## Evidence and next action

- Fourier [plan](../../artifacts/isae/sa11-extension-modes-20261108/plan.json),
  [verified analysis](../../artifacts/isae/sa11-extension-modes-20261108/analysis.json),
  [serial driver](../../scripts/verify-sa11-extension-modes.py), and
  [independent checker](../../scripts/check-sa11-extension-modes.py).
- Pointwise [plan](../../artifacts/isae/sa11-extension-practical-mesh-20261108/plan.json),
  [verified analysis](../../artifacts/isae/sa11-extension-practical-mesh-20261108/analysis.json),
  [serial driver](../../scripts/verify-sa11-extension-practical-mesh.py), and
  [independent checker](../../scripts/check-sa11-extension-practical-mesh.py).
- 244 Fourier and 247 pointwise source/artifact pins authenticated. Eighteen
  new physical calls, all terminal; no retries, timeouts or recording failures.
  Each invocation uses one BLAS thread, 512 MiB address space and 15 CPU /
  25 wall seconds. Longest invocation: **3.78 s**; peak RSS: **262.37 MiB**.
  Browser/build checks remain under the existing hold.

Further mode-count tuning is not supported by these results. The remaining
numerical question is whether the force results stabilize under a fixed
minimum-spacing policy, independently of matching the archive. Such a check
must retain the published receiver/force laws, separate mesh changes from
source/setup conflicts, and keep every rejected result visible. The original
winglet-input and .75/.78 normalization blockers remain unresolved.

The subsequent [fixed-minimum stability check](isae-sa11-extension-mesh-limit-20261108.md)
now answers that question for twelve prescribed finer requests: CD still
changes 1.02–1.27% on the last accepted refinement, while all three new
272 m/s, 5° states reject at the center sweep break. It does not establish
a stable force limit or justify replacing the primary mesh.
