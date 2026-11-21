# ST-2 documented-node mesh comparison

Using uniform material-arc spacing, **40 unique structural nodes and still-air inertia**, the first seven frequencies of both original Pazy modal models agree with the archived ASWING frequencies to **0.012611% or better**. The median across all fourteen frequencies is **0.002322%**. This is conditional frequency agreement, not a recovered historical setup or a completed native validation. The registered ST-2 score remains **0/490**.

All 24 predeclared cases completed: two original orientations, vacuum/still air, 39/40 unique nodes, and cosine/modified-cosine/uniform spacing. No material, stiffness, mass, gravity, aerodynamic coefficient, source file or acceptance interval was adjusted. Every alternative is retained below.

## Why these cases

The ISAE structural report, section 4.2 (PDF page 34), specifies **forty structural nodes** for the Pazy wing and identifies the vertical and self-weight-deformed horizontal modal configurations. The previous nominal 40-interval request produces 42 unique nodes after inserting the mandatory property break at t=0.52. The public modal folders do not supply the original mesh coordinates or a modal run script.

The ASWING guide, “Considerations for Data Discontinuities,” describes a zero-length computational interval at doubled input stations for break-enabled variables. The original Pazy input doubles x/y/z/chord rows at t=0.52, along with its GJ change. OpenSwing currently represents this location by a shared node with sided property evaluation. The plan therefore includes 39 unique nodes (plus an implicit collapsed duplicate) and 40 unique nodes. Neither interpretation is asserted to be the historical node bookkeeping. GJ is not in the guide’s listed break-enabled variables, and the guide warns that other discontinuous properties can receive either sided value depending on roundoff.

The requests use nominal counts 37 and 38; adding both endpoints and the required internal break gives 39 and 40 unique nodes. Uniform spacing refers to the base material-arc grid before inserting the break. Modified cosine is the existing option independently supported by SA-2 coordinates; it is not assumed to be ASWING’s universal default.

## All spacing/count results

Values are median / maximum absolute frequency error against the original `.e00` file, in percent. Seven positive roots per configuration are selected in computed frequency order, with unique conjugate partners. No target-frequency search chooses the roots.

| Medium | Unique nodes | Spacing | Upright error, % | Horizontal error, % |
|---|---:|---|---:|---:|
| vacuum | 39 | cosine | 0.713674 / 1.486078 | 0.713419 / 1.485097 |
| vacuum | 39 | modified-cosine | 0.711442 / 1.094261 | 0.711196 / 1.093589 |
| vacuum | 39 | uniform | 0.709079 / 0.730710 | 0.708878 / 0.730567 |
| vacuum | 40 | cosine | 0.712947 / 1.393097 | 0.712717 / 1.392206 |
| vacuum | 40 | modified-cosine | 0.710830 / 1.021897 | 0.710610 / 1.021298 |
| vacuum | 40 | uniform | 0.676727 / 0.708589 | 0.676629 / 0.708411 |
| still air | 39 | cosine | 0.048659 / 0.812756 | 0.037412 / 0.812000 |
| still air | 39 | modified-cosine | 0.014531 / 0.421722 | 0.011059 / 0.421273 |
| still air | 39 | uniform | 0.008005 / 0.059838 | 0.005619 / 0.059909 |
| still air | 40 | cosine | 0.040509 / 0.719965 | 0.031131 / 0.719298 |
| still air | 40 | modified-cosine | 0.008304 / 0.349499 | 0.007090 / 0.349122 |
| still air | 40 | uniform | 0.002327 / 0.012611 | 0.002317 / 0.009227 |

## Forty-node uniform still-air frequencies

Errors below are signed percentages. The row number is the positive-frequency ordinal; archived physical mode labels have not been recovered.

| Ordinal | Upright ASWING, Hz | Upright OpenSwing, Hz | Error, % | Horizontal ASWING, Hz | Horizontal OpenSwing, Hz | Error, % |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 4.59834807 | 4.59838079 | +0.000712 | 4.67646418 | 4.67649092 | +0.000572 |
| 2 | 29.13513943 | 29.13704455 | +0.006539 | 29.19784330 | 29.19973636 | +0.006484 |
| 3 | 43.44772542 | 43.44671421 | -0.002327 | 43.22663692 | 43.22563520 | -0.002317 |
| 4 | 81.35922387 | 81.35739520 | -0.002248 | 81.40635124 | 81.40456206 | -0.002198 |
| 5 | 128.14296581 | 128.14375386 | +0.000615 | 116.43481996 | 116.43266425 | -0.001851 |
| 6 | 135.52799709 | 135.51090531 | -0.012611 | 147.36667546 | 147.35307810 | -0.009227 |
| 7 | 158.57142696 | 158.58066836 | +0.005828 | 158.61584074 | 158.62527067 | +0.005945 |

The horizontal equilibrium has a 17.295 mm downward tip displacement and a maximum rotation of 2.4035 degrees. Its large fifth/sixth-frequency shifts from the upright configuration are retained, rather than comparing both orientations about an undeformed state.

## Physical verification and interpretation

All 24 cases preserve the literal original files, including both physically null Weight rows at t=0.558. Each case passes fresh equilibrium residual, original total mass, gravity force, clamp, global force/moment balance, spectrum uniqueness and conjugacy checks. The complete 20-root descriptor calculation retains both vector sides and the full sparse A/M matrices. All **960 original-pencil eigenvector checks** pass; the largest backward error is **4.319e-16** and the largest fresh base residual is **1.995e-14**.

The unchanged physics reproduces the same spacing/medium pattern in both orientations. This strengthens the explanation that historical mesh and still-air settings account for much of the earlier discrepancy. It does not prove those settings: the public files do not identify the node array or the precise treatment of the doubled station. No default is changed or chosen by fitting a target.

The separate [upright independent refinement](isae-st2-independent-refinement-20261104.md) remains relevant: fine meshes converge to an independent beam calculation within 0.02377%, while some fine frequencies move away from the archived ASWING values. Close agreement at a particular coarse discretization does not make that discretization more accurate in the continuum limit. This study compares historical output; the independent study checks the physical equations.

Every original real and imaginary printed interval is still evaluated using exact decimal reference bounds. **0/336 repeated component comparisons pass** across the 24 diagnostic jobs; the forty-node uniform still-air pair gives **0/28**. These counts include repeated use of the same two seven-root archives and do not add independent reference cells. Neither frequency component precision nor tiny real components (reference half-widths down to 5e-22) are relaxed, rounded to zero or omitted. The registered score remains 0/490.

All jobs ran serially with one BLAS thread and a 512 MiB address-space cap. The fixed batch took **467.6 seconds**, with a **19.01-second** median job. The assessment reuses saved results; it runs no new aircraft solves. Production kernels and browser bundles are unchanged, so no new browser build or release package is needed for this diagnostic.

Remaining work includes the original mesh/break interpretation, the small residual frequency differences, independent validation of the gravity-loaded modal configuration, invalid active static attachment anchors in other ST-2 files, and the remaining registered cases. No entire family or project goal is declared complete.

## Evidence

- [Portable assessment, all 24 cases and hashes](isae-st2-documented-mesh-20261104.json).
- [Fixed plan](../../artifacts/isae/st2-documented-mesh-20261104/plan.json), [serial receipts](../../artifacts/isae/st2-documented-mesh-20261104/serial-receipt.json), and [saved-result assessment](../../artifacts/isae/st2-documented-mesh-20261104/assess.py).
- [ISAE structural report, local text](../../.reference/isae-validation/reports/Experimental_validation_of_ASWING_Part_3__Structure_V5.txt), section 4.2; [ASWING guide](../../.reference/aswing_doc.txt), “Considerations for Data Discontinuities.” Both source hashes are pinned in the plan.
- Original requests, full outputs, sparse matrices, spectra and verification reports are retained under `artifacts/isae/st2-documented-mesh-20261104/jobs/`.
