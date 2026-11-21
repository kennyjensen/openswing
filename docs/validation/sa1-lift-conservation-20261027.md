# SA-1 prescribed-circulation lift and drag regression

**All 63 algebraic checks passed.** Production near-field circulation lift and
Trefftz `CLi` agree with an independent circulation integral on a nonuniform
straight grid at four incidences. No circulation or equilibrium solve was
performed. This is a component regression, not an archived-output pass;
registered SA-1 remains **19/154**.

The [prospective protocol](../../artifacts/isae/sa1-lift-conservation-20261027/protocol.json)
pins the original SA-1 model, driver, native table, primary sources and all 123
production Python modules. The [script](../../artifacts/isae/sa1-lift-conservation-20261027/run.py)
checks those pins before and after evaluation. The
[results](../../artifacts/isae/sa1-lift-conservation-20261027/results.json) retain
all matrices, checks and four complete production outputs. The
[process receipt](../../artifacts/isae/sa1-lift-conservation-20261027/process-receipt.json)
records the terminal process and original artifact hashes. A separate
[documentation supplement receipt](../../artifacts/isae/sa1-lift-conservation-20261027/documentation-supplement-receipt.json)
pins the added conditional proofs below and this revised report; the numerical
artifacts and original process receipt remain frozen.

## Fixed inputs and independent identities

The original straight, unit-chord material model is unchanged. Only this
diagnostic's supplied geometry and circulation are synthetic:

```text
Structural nodes: -2.95, -2.2, -0.85, 0, 0, 0.6, 1.7, 2.95 m
Interval Gamma:   0.35,  1.1,  0.7,  9.7, 1.3, 0.9, 0.2 m²/s
Incidence:        -12, 0, 7, 18.091 degrees
U = 47.9 m/s; rho = 1.2256 kg/m³; PG Mach = 0; current wind-aligned wake
```

The repeated root has zero interval width. Its deliberately nonzero circulation
entry contributes zero to the structural integral. It is excluded from
aerodynamic receivers: evaluating at a nonzero net wake filament would be
singular. Separate production wake evaluations retain that zero-width source
pair and verify that its equal and opposite filaments cancel at all six active
receivers. No adjacent positive interval is removed, halved or merged.

For each positive interval, the receiver uses the Glauert midpoint derived in
radical form directly from its endpoints and full span. This implements the
coordinate relation of steady Eqs150–154 independently of production mesh
generation. The zero-width treatment follows Eqs55–56 and their zero-length
limit ([theory text](../../.reference/asw_theory.txt), lines642–675,1572–1593).

With wind unit vector `e`, span vector `s` and lift vector `ell=e cross s`, the
straight-wing induced velocity at the bound line is perpendicular to `e`.
Thus Eq67 gives, before any choice of endpoint load recovery,

```text
L = rho U sum(Gamma_i delta_y_i)
CLi = 2 sum(Gamma_i delta_y_i) / (U Sref).
```

The scalar Biot–Savart operator for the near-field downwash is

```text
W_ij = [1/(sample_i - right_j) - 1/(sample_i - left_j)] / (4 pi)
w = W Gamma
D = -rho sum(Gamma_i w_i delta_y_i).
```

These follow from the trailing filaments in steady Eqs160–161 and the force
projection in Eq67. The production far-wake velocity independently equals
`2 W Gamma`, while its induced drag equals the same near-field drag. The
Trefftz lift definition is Eq207 ([theory text](../../.reference/asw_theory.txt),
lines770–775,1658–1682,2474–2495).

The near-field check uses actual production `f_aero` and `CDi_near`:
`L=(sum(f_aero_i delta_y_i)-qS CDi_near sin(alpha))/cos(alpha)`.
The manual identifies `f_aero` as normal circulation lift per span
([guide](../../.reference/aswing_doc.txt), lines2503–2509). This recovery excludes
profile/separation force, which is nonzero for these arbitrary prescribed
fields. The script also checks the individual normal-force products and full
local velocity vectors against the scalar oracle.

## Observed conservation and quadratic work

At every declared incidence:

| Quantity | Independent value | Production agreement |
|---|---:|---|
| Circulation integral | 4.3625 m³/s | Zero-width insertion unchanged |
| Circulatory lift | 256.105972 N | Near-field and Trefftz agree |
| CLi | 0.03087293443261031 | All four Trefftz outputs agree |
| Induced drag | 0.6955977800354268 N | Near-field and Trefftz agree |

The maximum normalized discrepancy over all 63 checks is
`1.432187701766452e-14`, below the prospective `2e-12` algebraic gate. This gate
does not replace any archived printing tolerance or equilibrium residual gate.

For quadratic drag, define `B=-diag(delta_y) W` and
`Q=(B+B.T)/2`. Then `D=rho Gamma.T Q Gamma`; the antisymmetric part contributes
exactly zero to scalar work. The raw weighted collocation matrix is **not**
symmetric on this grid: `max(abs(B-B.T))=0.05829885065567263`. Treating raw matrix
asymmetry as a failed conservation identity would be incorrect.

The symmetric matrix has eigenvalues from `0.10581844854336049` to
`0.4918944865667942`, and Cholesky factorization succeeds. Nine fixed vectors,
including the unequal circulation, alternating signs and every coordinate
basis vector, give matching direct, symmetric and Cholesky work. Every column
of the production wake operator also agrees with the independent scalar
operator. These checks establish positive quadratic work to a large numerical
margin for this fixed grid. They are not a proof for arbitrary grids or an
interval-certified continuum energy bound.

The run made four prescribed aerodynamic evaluations and fourteen direct linear
wake evaluations, with zero Newton iterations, circulation solves, equilibrium
solves or retries. All four raw `converged` flags are false; residuals range from
0.01846 to 0.30910. Those are retained, expected consequences of prescribing
circulation instead of solving tangency, and are not accepted equilibria.

## Conditional source-derived exclusions

The following are algebraic consequences under stated assumptions, not
reconstructions of the archived executable. They add no evaluations to the run.

**Structural transfer alone cannot change Trefftz efficiency.** Steady Eq211
defines `e=(CLi²+CYi²)/(pi AR CDi)` from the Trefftz coefficients, independently
of structural reactions ([theory text](../../.reference/asw_theory.txt),
lines2474–2495). Holding circulation, wake geometry and reference quantities
fixed, changing only the transfer of aerodynamic loads to structural endpoints
therefore leaves `e` unchanged. It cannot explain the attached-flow efficiency
bias. The [whole-polar analysis](sa1-load-consistency-20261027/report.md) already
finds compatible native circulation-lift integrals inferred independently from
`e/CDi` and `Cm/CDi`. An alternative explanation involving load recovery must
also identify a corresponding change in the wake circulation integral. This
argument does not cover a flexible equilibrium whose changed loads alter its
geometry and circulation. Also, close induced drag alone does not prove equal
circulation: drag is quadratic in circulation, while lift is linear.

**Interval-sided endpoint averaging preserves pointwise circulation lift.**
Eq153 assigns one constant `Gamma_i` to each structural interval
([theory text](../../.reference/asw_theory.txt), lines1578–1581). For the current
straight, planar, isolated wing, the Eq67 lift projection is `rho U Gamma_i`
throughout that interval. Averaging its two one-sided endpoint limits therefore
gives the same `rho U Gamma_i delta_y_i` as midpoint sampling. This projects
onto lift before taking limits; it does not require evaluating singular full
velocity vectors at trailing filaments. Averaging circulation from neighboring
intervals, or replacing an interval's interior tip trace by exterior zero
circulation, introduces an additional recovery rule. Neither follows from the
interval-constant representation itself. Thus endpoint averaging alone cannot
reduce the pointwise lift integral tested here.

**The Fourier trapezoid factor uses structural intervals, not mode count.**
Consider a separate uniform-Glauert-angle grid with `N=I−1` intervals, semispan
`R`, and `Gamma=sum(A_k sin(k theta))` with `K<N`. Discrete sine orthogonality
gives the midpoint sum `M`, endpoint trapezoid sum `T`, and continuous Fourier
integral `C`:

```text
M = R N sin(pi/(2N)) A_1
T = cos(pi/(2N)) M
C = (pi R/2) A_1.
```

Eq150 samples every retained Fourier mode on every structural interval;
`K` controls the number of amplitudes, not the number of integration intervals
([theory text](../../.reference/asw_theory.txt), lines735–746,1572–1576).
Replacing `N` by `K=40` in the trapezoid factor while retaining approximately
200 structural intervals is not that documented discretization. The earlier
[saved-field quadrature audit](steady-aero-review-20261027/load-quadrature-review.md)
verified these identities and found that the actual 200-interval trapezoid
change is too small to explain the attached-flow discrepancy. For positive
`A_1`, `C/M=pi/(2N sin(pi/(2N)))>1`: replacing the midpoint integral by the
continuous Fourier integral at fixed coefficients increases lift, the wrong
direction for the attached positive lift bias. These uniform-angle identities
do not apply unchanged to the synthetic nonuniform grid above or recover the
historical grid, circulation basis or load-transfer implementation.

This regression excludes missing or extra circulation lift from the tested
nonuniform interval weights, zero-width root source handling, incidence
projection, and near-field/Trefftz normalization. It does not recover historical
ASWING circulation, original mesh placement, a nodal recovery rule, or stall
constants. It therefore supplies no correction to the archived SA-1 mismatch
and changes no production equation or acceptance count.
