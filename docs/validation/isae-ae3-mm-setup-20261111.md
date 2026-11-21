# AE-3: native MM outputs under the disclosed roll-constraint setup

Observed 2026-11-11 UTC. The full native adapter makes the setup hypothesis
testable beyond rolling moment. At the lowest speed, the independently sourced
sibling control slope plus the conditional roll-acceleration constraint matches
**41/42 derivatives**, including all six control derivatives. Its apparent-mass
yz term is within **3.25%** at every saved speed on both meshes. This strengthens
the case for a mismatch between the retained input and archived generating
setup. It does not recover that setup or establish full AE-3 validation.

The primary [complete native comparison](isae-ae3-native-completion-20261111.md)
remains **434/725 passing**, with 612 computed, 178 mismatches and 113 unavailable.
No primary vote, original input, governing equation or acceptance gate changed.

## Exactly what was compared

The [authoritative reference index](aswing-authoritative-references.md) and its
checksummed catalog remain the basis for the interpretation. Jan Part IV §3.3,
pp. 13–14, distinguishes mounted and freely rolling experiments and the original
and modified ASWING models. The original `Roll_rate.sh` contains `% / 4 23 / P / d`.
The extended manual's Fig. 1.5, p. 12, and explanation on p. 13 support the
**conditional** interpretation: free body roll acceleration and enforce zero
net rolling moment. The original executable's constraint mask is unavailable.

The previous [roll sweep](isae-ae3-roll-sweep-20261111.md) independently selected
0.0686 from original sibling model files, replacing only the retained 20O
model's 0.0581 lift-control slope. Moment-control slope −0.0102, geometry, root
attachment, normalization, Mach zero, F1 = 1, updated influences and all other
settings stay fixed. This value was not fitted to the new derivative or mass
comparisons. The literal and sibling settings remain separate diagnostics.

This study restores the four existing nominal-80 endpoint equilibria. It
verifies each original constrained operator identity and fresh full residual,
then freezes its **actual solved angular acceleration**, transfers only the
physical state into a fixed-acceleration network, and checks that the physical
residual, coordinates, frames and aerodynamic outputs are preserved. All four
physical-residual transfers are exactly equal. This follows the production
derivative convention of freezing converged trim variables; fixed acceleration
does not necessarily mean zero acceleration.

The unchanged full-observable helper then computes the 42 derivatives, 42
mass/inertia/centroid fields and six rates, alongside six finite coefficients.
Each endpoint therefore compares all **96 distinct native fields**. One exact
factorization supplies all seven response columns. Full-tangent checks, the
scaled rank gate, input/output refinement, linear residual checks and independent
apparent-mass recovery from acceleration loads remain active.

Both operators in the helper's parity check are moving-airflow operators for
these diagnostics; that check does not establish coupled-versus-airflow parity.
The independently checked constrained-to-fixed state transfer is the relevant
additional evidence. The primary adapter's stricter base-operator contract is
unchanged. Fixed-acceleration derivatives about a roll-free base remain a
disclosed hypothesis for the archived `MM` output, not a recovered convention.

## Endpoint comparison

All counts use the original 5% policy; references of magnitude <=1e−8 keep their
original printed absolute gates. Alternative settings are never summed into
the primary denominator.

| Setup, nominal 80 | Speed (m/s) | Coefficients | Derivatives | Mass/inertia/centroid | Rates | All native fields |
|---|---:|---:|---:|---:|---:|---:|
| Literal, zero acceleration — primary control | 27.0934 | 4/6 | 30/42 | 29/42 | 6/6 | 69/96 |
| Literal, free roll acceleration | 27.0934 | 4/6 | 29/42 | 29/42 | 6/6 | 68/96 |
| Sibling slope, free roll acceleration | 27.0934 | 6/6 | **41/42** | 30/42 | 6/6 | **83/96** |
| Literal, zero acceleration — primary control | 59.4556 | 5/6 | 27/42 | 29/42 | 6/6 | 67/96 |
| Literal, free roll acceleration | 59.4556 | 4/6 | 27/42 | 29/42 | 6/6 | 66/96 |
| Sibling slope, free roll acceleration | 59.4556 | 5/6 | 30/42 | 31/42 | 6/6 | 72/96 |

Freeing roll acceleration alone does not improve aggregate agreement. The
sibling-control setting supplies the additional independent input difference.
At low speed, the sibling diagnostic's errors are **0.252% in Cl**, **0.207%
in CldF1**, **0.211% in Clu**, **2.094% in CX** and **1.327% in CXdF1**.
The only failed derivative there is CLb: native 0.002120 versus 0.003505392,
an absolute difference of 0.001385392 and **65.35%** relative error.

All 12 low-speed mass/inertia failures have native magnitudes <=1e−8 and remain
failed under the original absolute gates. Some are within 5% in relative terms;
others are tiny asymmetric native cross terms where the current symmetric
calculation is effectively zero. They have not been dropped or reclassified.

At high speed, Cl and CldF1 still differ by **28.50% and 26.99%** on this mesh;
Clu differs by **6.36%**. Several other derivative discrepancies persist, including
CYa (0.002010 versus 0.007268323) and CXp (0.000030 versus 0.000247342).
The existing coefficient-only refinement reduced high-speed Cl error to 13.01%
at nominal 160; it does not validate these nominal-80 derivative predictions.

## Independent geometry evidence from apparent mass

The saved apparent tensor integrates deformed section normals and moment arms
under Drela steady §8.7, Eqs. 237–256. It therefore tests geometry independently
of the finite aerodynamic coefficient mapping. This assessment maps **all 18
apparent mass/inertia fields** at all twelve saved sweep states, including tiny
values. Origin and centroid inertia outputs remain separate native fields under
the disclosed zero-real-mass reporting convention.

| Speed (m/s) | yz apparent-mass error, nominal 80 | Nominal 160 |
|---:|---:|---:|
| 27.0934 | 1.022% | 1.428% |
| 38.5020 | 0.896% | 1.354% |
| 43.0429 | 0.849% | 1.347% |
| 47.2340 | 0.725% | 1.284% |
| 50.9245 | 0.514% | 1.162% |
| 59.4556 | 3.250% | 1.830% |

At the high-speed nominal-80 endpoint, the native yz value is −2.019e−5. The
primary literal/zero-acceleration result is +6.90740077e−5; the sibling/roll-free
result is −1.95338154e−5. This sign and magnitude agreement is a useful clue,
but the full apparent tensors still have failed fields. Every such field and
its original tolerance is retained in the assessment.

All saved tensors are authenticated against the earlier sweep's recorded hashes.
The two nominal-80 endpoints receive fresh current-code residual and tensor
checks here, reproducing their saved tensors exactly. Intermediate and nominal-160
states use their previously checked saved outputs; no fresh current-code solve
or residual evaluation is claimed for them in this study.

## Verification and next step

Four small serial workers pass **184 fresh numerical checks** with maximum full
residual **5.003e−13**. They start no equilibrium solves. Worker time is
**8.048–8.241 wall seconds**, **5.335–5.554 CPU seconds**, with at most
**146,604 KiB peak RSS**. The limits remain one BLAS thread, 512 MiB address space,
15 CPU seconds and 25 wall seconds. All children are reaped.

The first attempt reached report writing but failed to serialize a NumPy boolean.
Its evidence and original script are preserved. The corrected reporting path
converts comparison scalars to Python floats and uses a new output directory;
the four successful workers supply all counted numerical evidence. No numerical
algorithm or limit changed during this retry.

The next useful checks are CLb's force/kinematic convention and the remaining
high-speed derivative sensitivity, with the literal primary setup retained.
The new agreement supports further setup investigation; it is insufficient to
replace the primary model or to assign the unavailable embedded curves.

- [Diagnostic runner](../../scripts/probe_isae_ae3_mm_setup.py).
- [Complete assessment](../../artifacts/isae/ae3-mm-setup-r2-20261111/assessment.json): all endpoint fields, primary controls, all saved tensor fields, strict and 5% decisions, numerical checks and source hashes.
- [Source-only assessor](../../artifacts/isae/ae3-mm-setup-r2-20261111/assess.py).
