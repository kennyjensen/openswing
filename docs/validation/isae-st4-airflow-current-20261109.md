# ST-4 current-code airflow and 40-node spacing check

The structural ST-4 result remains **66/72 paper frequencies**, with the separate
**31/31 direct native frequencies** passing. This diagnostic revisits the flowing
air export shared with AE-6; it changes no structural result or production equation.

On the original 7a model, a 40-node modified-cosine mesh reduces the low-frequency
error at 120.5 m/s from **48.94% to 1.48%** relative to the same-count cosine mesh.
At 139.5 m/s it restores the native slow pole's negative sign, but its magnitude
still differs by **24.62%**. Mesh interpretation is therefore material. These
two spacing hypotheses do not establish the historical node coordinates or
numerical convergence, and no validated passes are added.

## Sources and setup

The [authoritative reference index](aswing-authoritative-references.md) and
checksummed catalog govern this comparison. Part III, pp. 28–30, describes
40-node cosine structural modal discretization; its ST-4 discussion on p. 40
refers back to the modal protocol. Part IV, p. 10, describes 40 structural nodes
and circulations for the preceding aeroelastic bench; p. 18 describes the
OPER-then-MODE procedure. Its AE-6 section on p. 20 uses the same weight-dipole
representation and preceding protocol. These statements support a 40-node
diagnostic, but do not supply an exact archived node array or the detailed
meaning of “cosine” in the generating executable.

The subsequent [node-placement audit](isae-st4-node-placement-20261109.md)
also distinguishes unique physical nodes from native coincident nodes at load
jumps. Equal reported counts alone do not establish equivalent native meshes.
Its separately tested 1989 formula does not resolve the airflow mismatch.

The original `Weight7a/7a_b17.asw`, `Flutter_analysis.sh` and `eig.txt` are
unchanged. Script operating points 2 and 40 correspond to 120.5 and 139.5 m/s.
Their six and nine exported roots remain in source order. The script does not
explicitly set the node grid, circulation representation or startup Mach.

Both prospective alternatives request 38 intervals plus the literal interior
weight station, yielding **40 actual structural nodes**. The existing modified
cosine option was independently checked against SA-2 coordinates in the
[earlier spacing audit](isae-sa1-sa5-spacing-20261029.md); its coefficients are
not fitted here. Testing it does not authenticate its use in ST-4.

The disclosed flow setup is fixed: density 1.0771417304 kg/m³, zero incidence
and sideslip, gravity 9.81 m/s² toward body −z, fixed perturbation frame,
pointwise circulation, enabled aerodynamic lag and PG Mach zero. Each solve
requests 16 roots around 0+300i. The source geometry/structural policies are
`drela-segspl-v1` and `drela-moving-airflow-v1`. Moving influences are explicitly
retained from the earlier study; changing application defaults since that study
does not silently change this comparison. Historical startup remains qualified.

## Sensitive components

| Speed | Quantity | Native ASWING | Cosine | Cosine error | Modified cosine | Modified error |
|---:|---|---:|---:|---:|---:|---:|
| 120.5 m/s | Lowest oscillatory Im(λ), rad/s | 3.3632329 | 1.71731729 | 48.9385% | 3.41295484 | 1.4784% |
| 139.5 m/s | Slow structural Re(λ), 1/s | −0.088874035 | +0.021353711 | 124.0269% | −0.110757882 | 24.6234% |

The remaining identified nonzero components differ by at most 4.876% with
cosine and 3.103% with modified cosine. The latter slow-pole absolute error is
0.021884 1/s; proximity to zero makes its relative error sensitive.

![The two sensitive components on both declared grids](../../artifacts/isae/st4-airflow-current-20261109/forty-nodes/comparison.png)

The raw component checks are **24/30 for cosine** and **25/30 for modified
cosine** at 5%, with the existing 5e−8 absolute gate for zero imaginary parts.
These are alternative diagnostic counts, not two independent validation scopes.
Four slots in each denominator remain unavailable: the two unidentified tiny
complex roots at operating point 40 have no authenticated counterpart. They
are not assigned to zero or dropped. Other correspondences use ascending
frequency within oscillatory roots and increasing absolute magnitude within
real roots, rather than nearest-target selection. Native physical mode identity
is still conditional because the export contains no eigenvectors.

The older **4/30 strict** airflow result remains explicitly historical; it is
not replaced by these looser, unrefined diagnostic comparisons. No best-setting
selection, pooling of alternatives or primary progress increase follows.

## Numerical verification and execution

All four fresh states converge. An independent reread of saved full sparse A/M
matrices and all 64 returned left/right eigenvector pairs passes **192 checks**:
128 relative-action equations and 64 unit mass pairings. Maximum equation error
is 2.394e−11, below 1e−8; maximum pairing error is 9.52e−15. The fresh equilibrium
residuals also pass. This verifies the discrete solves, not spatial convergence.

Each job runs serially with one BLAS thread, 512 MiB address-space, 15 CPU-second
and 25 wall-second child limits. All terminate successfully in **8.99–13.22 s**,
using at most **126,796 KiB resident memory**. A preceding 16-interval resource
probe is retained separately; it is not part of the comparison. No browser,
build or kernel-loading test was started.

The current production tree differs in 35 modules from the November 4 airflow
study. This refresh pins all 141 production modules, the probe, original input
and outputs, and governing references. It does not promote old numerical
results to current-code evidence. The four-job assessment additionally verifies
Part IV against the source catalog. All original artifacts remain intact.

The remaining useful distinction is between the native discrete setup and
converged continuum behavior. A closer answer on one coarse grid does not
justify altering physical coefficients, changing the default spacing, or
calling a stability boundary validated. The previous independent-flow audit
already supports the underlying equations for the disclosed straight-wing
setup. Exact node generation and point-weight placement remain the next setup
questions; the six structural paper discrepancies retain their separate
[source-row evidence](isae-st4-source-rows-20261109.md).

[Probe script](../../scripts/verify_st4_airflow_current.py),
[independent saved-matrix assessment](../../scripts/assess_st4_airflow_current.py),
[frozen four-job plan](../../artifacts/isae/st4-airflow-current-20261109/forty-nodes/plan.json),
[complete component ledger](../../artifacts/isae/st4-airflow-current-20261109/forty-nodes/assessment.json).
