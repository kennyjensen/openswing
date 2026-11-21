# Circulation-finish memory reduction

The original 419-node frozen-matrix Flare20 cold continuation stopped with an
actual `MemoryError` in job 16. Jobs 1–15 completed successfully; the last
accepted load fraction was 0.000706205589464036, with a rebuilt physical
residual of 7.389339779351617e-14. The failed job and old kernel remain intact
in `artifacts/isae/source-tree-production-20261107/nodes-419/`.

The failing allocation was a 5,444 × 416 array (17.28 MiB) containing complete
circulation columns, including mechanical load rows. The circulation-only
finish used just its 416 × 416 tangency/leakage block (1.32 MiB). It now obtains
that block directly from the same analytic derivative before allocating the
section-force/moment arrays and their transfer into mechanical equations.
The complete coupled Newton assembly remains available and unchanged.

Stall leakage, bound/collocation induced velocities, engine inflow and jets,
ground images and circulation-basis projection retain their existing chain
rules. A candidate circulation correction still requires every original
mechanical, operating and circulation equation to pass the unchanged 1e-12
physical residual limit. An unsuccessful candidate leaves coupled Newton
available. No tolerance, source input, vortex treatment or default changes.

## Verification

- **50 Python checks pass.** Seven circulation-finish checks retain the saved
  stall case, full physical acceptance and negative controls; 18 load-comparator
  checks protect sided jumps and per-component normalization. Another 25
  checks cover missing capture and 24 combinations of two structural
  formulations, stall, Fourier modes, frozen influences, bodies, joints,
  ground images and engine types 0–2. All 24 smaller blocks match their full
  counterparts bit for bit and pass two centered physical-residual stencils.
- **Seven WebAssembly checks pass**, including rejection of a flow correction
  that disturbs mechanical balance and restoration after failed derivatives.
- A new immutable 140-module kernel completed a **separate cold 419-node
  history: 19/19 successful jobs, zero load rejections**, each with a 90-second,
  512 MiB cap and one BLAS thread. No old checkpoint identity was edited.
  The first 15 saved coordinate vectors and load fractions are bit-for-bit
  identical to the old kernel. Job 16, which previously failed, now succeeds.
- Independent reconstruction verifies every saved boundary, source, kernel,
  continuation link and rotation guard. Final rebuilt residual is
  **9.769457443802023e-14** at full load. The complete 211-node coarse state
  reconstructs with **all 45,775 numeric outputs unchanged**, residual
  **8.045516265008119e-13**. AST checks show unchanged physical functions and
  unchanged complete derivative calculations when the optional early return
  is not requested.
- The production build succeeds with all 140 current modules. **19 built-browser
  checks pass**, continuing through the former failure point (step 16),
  reloading the page/worker, and accepting step 17. The steps take
  **23.586/21.674 s after worker readiness**; initial loading and the reload
  are excluded. Normalized state differences from Python are at most
  **3.062e-16**, with rebuilt residuals at most **8.333e-14**. There are no
  page errors or external requests. These are two continuation steps, not
  a full browser cold solve or a native-ASWING comparison.

## Mesh evidence

The nested 211/419 pair passes **0/7 original numerical gates**, versus 1/7
for 107/211. The unchanged threshold is 0.1%. This does not establish mesh
accuracy even though the full nonlinear equations converge.

| Quantity | 211/419 change | Result at 0.1% |
| --- | ---: | --- |
| Root moment | 0.150815% | Fail |
| Beam 1 displacement | 0.166270% | Fail |
| Beam 1 rotation | 0.142350% | Fail |
| Beam 2 displacement | 0.167529% | Fail |
| Beam 2 rotation | 0.161975% | Fail |
| Beam 3 displacement | 0.245603% | Fail |
| Beam 3 rotation | 0.255865% | Fail |

The supplemental sided endpoint-load comparison passes **11/18** independent
component gates. Each beam and each body-axis component uses its own finer-grid
maximum; left/right traces at point loads, joints and supports are kept separate.
The seven failed components change **0.1116–0.6645%**. The largest is the left-tip
body-x moment. The circulation cell RMS differences are **0.354%, 1.354%,
1.119%** for main/right/left beams; these are diagnostics of piecewise-constant
representations, not a shared-collocation or circulation-accuracy pass.

![Equilibrium mesh and sided-load checks](../../artifacts/isae/circulation-finish-memory-20261107/refinement-419.png)

The new root moment is **0.5280027484 N m**, versus the archived initial
**0.530039 N m** (0.384170% difference). Hinge angles are **50.265681°** and
**−4.980272°**. The declared K/F=True sensitivity arm remains distinct from
an authenticated historical default. Native attachment semantics remain
qualified. No gust-history values have been computed by this equilibrium study.

Native FFWT-4 remains **200/8,000 at 5%**. Numerical mesh gates stay **0.1%**.
The overall progress chart therefore receives no additional native-completion
event. All earlier successful boundaries, failed jobs, kernels and assessments
are retained.

## Next investigation

The root-moment change is nearly the same for 107/211 (0.15298%) and 211/419
(0.15082%), while several nodal changes grow. A still finer global mesh is not
yet justified as a way to resolve this trend. Separate circulation/load
quadrature from structural discretization on fixed physical geometry near
folding joints, retaining the documented vortex indices and unmodified source
inputs. The current evidence does not identify which of these causes dominates.

Evidence and process receipts: `artifacts/isae/circulation-finish-memory-20261107/`.
The frozen pre-execution load criteria remain in
`artifacts/isae/ffwt4-frozen-419-20261107/load-field-plan.json`.
