# ST-4 refinement near critical damping and the slow-root crossing

Two sensitive conditions from the [41-speed comparison](isae-st4-speed-sweep-20261104.md)
now have finer independent meshes and fresh **160-interval full OpenSwing API**
results. Refinement preserves the main native discrepancies: at 120.5 m/s the
lowest frequency remains about **43.10%** below the archive;
at 139.5 m/s both implementations retain a positive slow root while the archived
branch is negative. ST-4 is still not validated against native ASWING.

## Sensitive values

| Speed (m/s) | Quantity | Archived ASWING | OpenSwing N128 | OpenSwing N160 | Finest independent reference |
|---:|---|---:|---:|---:|---:|
| 120.5 | Lowest oscillating frequency, rad/s | 3.3632329 | 1.915705570 | 1.913721198 | 1.913335845 |
| 139.5 | Slow structural Re(λ), 1/s | -0.88874035E-01 | +0.033819941 | +0.034399706 | +0.035365705 |

The public runs change only the requested cosine interval count from 128 to 160.
The independent formulation changes its structural and aerodynamic resolutions
separately: cubic Hermite bending/linear torsion with a uniform structural grid,
and the documented constant-strength horseshoe model on a cosine aerodynamic grid.
All meshes retain the literal weight station. A/S below are requested aerodynamic/
structural intervals; mandatory stations can add a node or replace a nearby uniform
structural node. Final reference meshes are A768/S384 at 120.5 and A768/S512 at 139.5.

The original `.asw`, density, gravity, incidence, fixed frame, enabled lag, shift,
16-root request and physical equations remain fixed. No fitted damping, stiffness,
mass, stall correction, altered wake law or modal-basis truncation is introduced.
The independent reference remains limited to this straight, zero-incidence pilot.

## Resolution checks

The component gate remains **0.1%**, with the existing 5e-8 absolute treatment of
zero imaginary components. The largest percentage below includes nonzero components
only. Failed coarse levels remain failures; shape agreement cannot turn a failed
component into a pass. These gates measure numerical refinement, not agreement
with the native archive's printed precision.

| Speed | Comparison | Meshes | Passing components | Largest component change |
|---:|---|---|---:|---:|
| 120.5 | structural mesh | reference A256/S128 @ 120.5 → ref120p5_a256_s192 | 11/12 | 0.25594% |
| 120.5 | structural mesh | ref120p5_a256_s192 → ref120p5_a256_s256 | 12/12 | 0.09126% |
| 120.5 | aerodynamic mesh | ref120p5_a256_s256 → ref120p5_a512_s256 | 11/12 | 0.12827% |
| 120.5 | aerodynamic mesh | ref120p5_a512_s256 → ref120p5_a768_s256 | 12/12 | 0.04127% |
| 120.5 | structural mesh | ref120p5_a512_s256 → ref120p5_a512_s384 | 12/12 | 0.06461% |
| 120.5 | structural mesh | ref120p5_a768_s256 → ref120p5_a768_s384 | 12/12 | 0.06358% |
| 120.5 | aerodynamic mesh | ref120p5_a512_s384 → ref120p5_a768_s384 | 12/12 | 0.04229% |
| 120.5 | production mesh | OpenSwing N128 @ 120.5 → public120p5_n160 | 11/12 | 0.10369% |
| 120.5 | implementation comparison | public120p5_n160 → ref120p5_a768_s384 | 12/12 | 0.05736% |
| 139.5 | structural mesh | reference A256/S128 @ 139.5 → ref139p5_a256_s192 | 13/14 | 0.89937% |
| 139.5 | structural mesh | ref139p5_a256_s192 → ref139p5_a256_s256 | 13/14 | 0.31899% |
| 139.5 | aerodynamic mesh | ref139p5_a256_s256 → ref139p5_a512_s256 | 14/14 | 0.06024% |
| 139.5 | structural mesh | ref139p5_a512_s256 → ref139p5_a512_s384 | 13/14 | 0.23097% |
| 139.5 | structural mesh | ref139p5_a512_s384 → ref139p5_a512_s512 | 14/14 | 0.07294% |
| 139.5 | aerodynamic mesh | ref139p5_a512_s384 → ref139p5_a768_s384 | 14/14 | 0.02924% |
| 139.5 | aerodynamic mesh | ref139p5_a512_s512 → ref139p5_a768_s512 | 14/14 | 0.02878% |
| 139.5 | structural mesh | ref139p5_a768_s384 → ref139p5_a768_s512 | 14/14 | 0.07340% |
| 139.5 | production mesh | OpenSwing N128 @ 139.5 → public139p5_n160 | 13/14 | 1.68538% |
| 139.5 | implementation comparison | public139p5_n160 → ref139p5_a768_s512 | 12/14 | 2.73146% |

The four comparisons into the finest independent grids pass
**52/52** component checks.
The production N128→N160 comparisons pass
**24/26**.
Finest independent/OpenSwing N160 comparisons pass **24/26**.
Minimum mechanical shape MAC across those two implementation comparisons is
**0.999999837**. Reference shapes are evaluated
at the production nodes after transforming from elastic-axis displacement to the
original beam axis. Production-to-production shape interpolation is diagnostic only.

The implementation/reference components still outside the gate are:

| Speed | Archived row ordinal | Component | Difference |
|---:|---:|---|---:|
| 139.5 | 3 | Re | 2.73146% |
| 139.5 | 6 | Re | 0.16005% |

The near-zero real pole makes relative errors unusually demanding: its absolute
OpenSwing/reference difference at 139.5 is
**0.000965999 1/s**.
Its native discrepancy is **138.71%**, with opposite sign.
This does not relax either gate or certify the production instability boundary.
The archive still omits this low branch at 140 and includes two unidentified tiny
complex roots at 139.5, so neither an exact native crossing speed nor overall native
stability is inferred.

## Reference memory correction and equation checks

The first A768/S256 attempt failed under the existing 512-MiB address-space cap
during a bordered Newton factorization. The completed Arnoldi LU and its operator
were still retained even though Newton no longer used them. Releasing those objects
before Newton removes that overlapping allocation; the same resolution then completes
under the same cap. This changes storage lifetime only. The reference equations,
unknowns, pivoting policy, correction algorithm and residual gate are unchanged.

The original failure and pre-change source are retained. A repeated A256/S256
case verifies **all 16 roots and full eigenvectors are bit-identical** after the
memory change. All **four independent formula tests** pass. Every new saved
reference eigenvector is rechecked against reassembled physical equations:
**224 checks**, with the original 1e-8 relative-action gate.
The two new production cases add **64 independently recomputed
left/right checks** against their unscaled sparse A/M, also at 1e-8.
The retained N128 production cases are checked again separately.
The first verifier attempt exceeded the cap while copying a full matrix into
extended precision. Its retained replacement promotes and evaluates one CSR row
at a time, preserving extended-precision products and the same residual gate.

Production kernels have not changed, and all 136 source/public/dist copies remain
identical to the previous verified application. No new browser run or application
build is needed for this reference-only source and evidence change. Older reports
retain historical code pins; the exact earlier reference source is preserved here.

## Measured full-run timings

All jobs were serial, one BLAS thread, capped at 180 seconds and 512 MiB. Values
are single-run observations, not controlled performance benchmarks. Modes/output
combines eigensolution with physical output recovery; it is not a pure eigensolver
timing. Matrix capture and JSON serialization account for the remaining total.

| Speed | Imports (s) | Base/preparation (s) | Matrix assembly (s) | Modes/output (s) | Total (s) | Peak RSS (MiB) |
|---:|---:|---:|---:|---:|---:|---:|
| 120.5 | 9.45 | 5.24 | 49.20 | 68.78 | 134.94 | 291.6 |
| 139.5 | 11.57 | 4.96 | 48.52 | 79.71 | 146.07 | 294.4 |

## Native status and next work

The two new full API anchors give **4/30 strict scalar matches**,
all nominally zero imaginary components; four required slots remain unavailable
because of the two unidentified tiny roots. There are no complete native root
matches. This conditional airflow scope does not replace the registered ST-4
vacuum baseline of 0/3,749. All other ISAE family counts and broad Partial
requirements remain unchanged. The SA-only 3% allowance is not applied.

Further production refinement is still required where the table fails. These
results support the independent equation audit and show that the examined mesh
changes do not resolve the native discrepancy. Historical startup/discretization
and native mode identities remain unauthenticated. A critical-speed calculation
would need its own convergence and original-equation checks; no interpolated
crossing is presented as validated here.

[Portable exact comparison data](isae-st4-critical-refinement-20261104.json)
contains all retained roots, component errors, gates and source pins.
The [local assessment](../../artifacts/isae/st4-critical-refinement-20261104/assessment.json)
also records each reassembled vector residual and mesh pairing.
