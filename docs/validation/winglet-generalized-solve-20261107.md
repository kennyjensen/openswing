# Winglet generalized lifting line: solved section equations

2026-11-07. All nine nonlinear section-equation cases converge on the controlled
sharp, unswept winglet. Connecting the surfaces before constructing the
generalized vortex geometry keeps the peak velocity near 1.10 times freestream
as the grid is refined. Lift and drag also become substantially less sensitive
to resolution. The connected result still differs from the independent
finite-chord calculation; this is not native ASWING validation or a production
algorithm change. SA-11 remains **163/4,592 at 5%**.

## Scope and equations

This follows the [prescribed-field study](winglet-generalized-fields-20261107.md).
It uses exactly the saved physical and effective geometries at 50, 100 and 200
main-wing intervals, with proportionate winglet resolution. The physical
fixture has main span 1 m, two 0.2 m winglets, constant 0.1 m chord and 1 m/s
freestream. The section incidence is `1/(2*pi)` radians. The
[original control report](unswept-winglet-junction-20261107.md) explains its
relationship to Kleine et al.'s published case and the printed angle mismatch.

The three variants are an uncorrected lifting line, a connected generalized
lifting line, and the generalized construction applied to separate main-wing
and winglet groups. Physical geometry and section properties are identical;
grouping changes the geometry used for induced velocity. Receiver-specific
geometry, joint length 0.15 chord, blending parameter 1, and the previously
measured near-wake joint gaps are retained without adjustment. There is no
finite core, compressibility correction or stall model in this ideal control.

The nonlinear section law is `Cl = 2*pi*alpha_eff`, with zero profile drag and
section moment. Let `a` and `n` be the local axial and normal unit vectors,
`V = U_inf + A*Gamma`, and `Vp = hypot(V.a, V.n)`. The solved residual is

```text
R = Gamma - pi*c*Vp*atan2(V.n, V.a).
```

The driver also executes the intact `_lifting_line_residual`, `_calc_v_i`,
`_get_section_lift` and `_correct_CL_for_sweep` method bodies from MachUpX
revision `9935476395b205e74612b6dc53d931eb1cad8d5e`. For this fixture its residual
`2*|V cross dl|*Gamma - Vp^2*dS*Cl` equals `2*Vp*ds*R`. The ideal section adapter
supplies the section coefficients; in-plane and total-velocity options are
enabled. Sweep correction has unit factor and zero lift angle here.

This is an independent harness using selected source methods, not a full
MachUpX application run. The [official developer notes](https://machupx.readthedocs.io/en/latest/developer_notes.html)
describe the generalized vortex geometry and velocity options. These choices
define a different section equation from the earlier ASWING-style tangency
control; changing circulation closure and geometry must be distinguished.

Forces are `rho*Gamma*(V cross physical_dl)` and moments use the original
receiver positions about the origin. Reference density is 1.225 kg/m³, area
0.1 m² and chord 0.1 m. The physical force elements are not replaced by the
receiver-dependent effective bound segments.

## Converged results

Each case starts from the saved tangency circulation and uses SciPy's hybrid
root solver with an analytic Jacobian. There are no retries, fitted parameters
or continuation steps. Every solve reports success in eight residual evaluations.

| Main-wing intervals | Vortex construction | CL | CD | Maximum speed / freestream |
|---:|---|---:|---:|---:|
| 50 | Uncorrected | 0.982003 | 0.027767 | 1.430030 |
| 100 | Uncorrected | 1.001458 | 0.029177 | 1.943933 |
| 200 | Uncorrected | 1.029949 | 0.031490 | 3.154468 |
| 50 | Connected generalized | 0.917913 | 0.027381 | 1.096383 |
| 100 | Connected generalized | 0.916997 | 0.027475 | 1.100640 |
| 200 | Connected generalized | 0.916518 | 0.027505 | 1.103290 |
| 50 | Generalized, separate groups | 0.955530 | 0.029515 | 1.332234 |
| 100 | Generalized, separate groups | 0.959035 | 0.030920 | 1.650817 |
| 200 | Generalized, separate groups | 0.962850 | 0.032283 | 2.292802 |

From N50 to N200 the connected result changes CL by **−0.152%**, CD by
**+0.454%** and peak velocity by **+0.630%**. Its final N100-to-N200 changes
are −0.0523%, +0.1117% and +0.2408%, respectively. The uncorrected result
changes CL by +4.88%, CD by +13.41% and peak velocity by +120.59% across the
same grids. Separate generalized groups retain substantial growth in velocity
and drag. Stable circulation closure alone does not remove that growth.

![Solved winglet comparison](../../artifacts/isae/winglet-generalized-solve-20261107-review/generalized-solve-comparison.png)

## Comparison with finite chord

The [four-row finite-chord control](winglet-finite-chord-20261107.md) supplies
an independent comparison at N50 and N100. Percentages below are signed model
differences relative to that control, not accuracy scores against ASWING.

| Connected generalized result | CL versus all finite edges | CL versus spanwise edges only | CD versus all finite edges |
|---|---:|---:|---:|
| N50 | −4.297% | −5.542% | +4.248% |
| N100 | −4.572% | −5.820% | +4.435% |

The two CL comparisons retain the distinction between lifting-line forces and
the extra chordwise-edge forces in the vortex-lattice calculation. This does
not establish either model as the true answer. Four chord rows are not a
certified continuum solution; that study also finds growing velocities on
some actual vortex edges. Its flat-sheet geometry, incidence convention and
wake discretization limitations remain applicable.

The connected correction improves numerical refinement behavior, but also
changes the solved lift distribution. It cannot be adopted merely because a
subset of coefficient differences falls below the project's 5% allowance.
There are no native ASWING reference outputs for this ideal fixture.

## Verification and reproducibility

The maximum reduced circulation residual is **2.89e−14 m²/s**; the maximum
original source residual is **8.93e−16**. Source and reduced equations agree
within **2.60e−17** at the initial and final states. Five-point directional
differences independently check the analytic Jacobian at both states, with
maximum absolute discrepancy **2.32e−8**. Circulations and section axial
velocities remain positive.

A separate saved-state audit reconstructs induced velocity using compensated
scalar sums, the section equation using scalar trigonometry, and forces and
moments using componentwise cross products. The maximum velocity difference
is **2.67e−15 m/s**; symmetry and load sums pass. All input, source and result
hashes are checked. No new solves occur during analysis.

The nine root solves total 0.182 s, with the longest 0.0534 s on this host.
These timings exclude geometry/influence preparation, derivative checks,
startup and artifact recording. They are not browser or SA-11 timings.
Jobs run serially, three cases per invocation, with one BLAS thread.

```sh
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 timeout 60s prlimit --as=805306368 .venv/bin/python scripts/verify-winglet-generalized-solve.py --batch 50 --output artifacts/isae/winglet-generalized-solve-new-n50
```

Repeat sequentially with `--batch 100` and `--batch 200`, each using a fresh
output directory, then analyze the three batches:

```sh
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 timeout 60s prlimit --as=805306368 .venv/bin/python scripts/analyze-winglet-generalized-solve.py --batches artifacts/isae/winglet-generalized-solve-new-n50 artifacts/isae/winglet-generalized-solve-new-n100 artifacts/isae/winglet-generalized-solve-new-n200 --output artifacts/isae/winglet-generalized-solve-new-review
```

- [N50 results](../../artifacts/isae/winglet-generalized-solve-20261107-n50/results.json)
- [N100 results](../../artifacts/isae/winglet-generalized-solve-20261107-n100/results.json)
- [N200 results](../../artifacts/isae/winglet-generalized-solve-20261107-n200/results.json)
- [Independent audit](../../artifacts/isae/winglet-generalized-solve-20261107-review/analysis.json)
- [Plot as SVG](../../artifacts/isae/winglet-generalized-solve-20261107-review/generalized-solve-comparison.svg)

All 141 production module hashes and the ISAE status/scope hashes remain
unchanged. This study supplies an explicit stable alternative on an ideal
two-branch corner. The swept, offset and three-branch SA-11 junctions, force-law
compatibility, wake derivatives and native ASWING agreement remain unresolved.

The subsequent [SA-11 topology audit](isae-sa11-generalized-topology-20261107.md)
checks the actual offset and branching root arrangements against the pinned
grouping routines. It finds that the ideal connected-path construction cannot
be transferred merely by aliasing structural joints to aerodynamic continuity.
Its signed three-branch field decomposition also retains a large geometric
contribution even when the circulation imbalance is below 0.1%.
