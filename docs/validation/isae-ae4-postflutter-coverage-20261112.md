# AE-4: undeformed flutter branch at 71–75 m/s

The registered comparison advances from **122/1,200 to 181/1,200 at 5%**.
Ten new cold runs compare every integer speed from 71 through 75 m/s on both
declared cosine meshes. **59/60 new native components pass**, with no unmatched
or unavailable values in this batch. This adds coverage of the growing
oscillatory branch; the remaining damping and setup discrepancies stay open.

The cumulative assessment was observed at
**2026-11-12T15:46:59.243985+00:00**. No production code or acceptance gate
changed during this batch. AE-4 is not fully validated.

## Native comparison and mesh convergence

| IAS (m/s) | Nominal 40 | Largest paired error | Nominal 80 | Largest paired error | Mesh gates at 0.1% |
|---:|---:|---:|---:|---:|---:|
| 71 | 5/6 | 6.154% | 6/6 | 4.309% | 4/6 |
| 72 | 6/6 | 3.910% | 6/6 | 2.989% | 4/6 |
| 73 | 6/6 | 2.817% | 6/6 | 2.376% | 4/6 |
| 74 | 6/6 | 2.162% | 6/6 | 2.033% | 4/6 |
| 75 | 6/6 | 1.721% | 6/6 | 1.825% | 4/6 |

Each native comparison retains all three reported positive-frequency modes,
with real and imaginary components counted separately. All four computed
modes remain in the raw evidence. The existing complete-set matching contract
is unchanged.

The new failure is the growing mode's real component at **71 m/s**:

| Result | Real part (1/s) | Native error |
|---|---:|---:|
| Archived ASWING | +1.4394902000 | — |
| OpenSwing nominal 40 | +1.5280806845 | 6.154% |
| OpenSwing nominal 80 | +1.5015183899 | 4.309% |

Both solvers retain a growing oscillatory mode throughout 71–75 m/s. The
growth-rate offset remains **+0.0725 to +0.0886 /s** on nominal40 and
**+0.0620 to +0.0769 /s** on nominal80. Relative errors become smaller as
the growth rate increases. These passes therefore coexist with an unresolved
absolute offset; they do not repair the near-onset discrepancy.

The independent mesh gate passes **20/30 components**, four of six at each
speed. Native agreement within 5% does not establish spatial convergence.
At 75 m/s the finer mesh's growth-rate error is slightly greater than the
coarser mesh's, so improvement is not universally monotonic with refinement.

## Accounting and source identity

The cumulative ledger now contains **188 paired values: 181 pass and seven
fail**, plus **16 unmatched**, **12 unknown-initial-state values** and
**984 unrun**. The selected scope is **216/1,200**, covering 38 computed jobs
and the two explicitly unavailable initial-state jobs. Failed paired errors
have median **9.017%**, range **5.913–48.809%**.

The [comparison CSV](../../artifacts/isae/ae4-postflutter-coverage-20261112/comparisons.csv)
retains all 1,200 required slots, including blank predictions for unavailable
or unrun values. The assessment checks named columns, unique component keys,
counts and a read-back comparison against the accepted records. No existing
result was overwritten or counted twice. The overlapping **86/108** historical
sample and the eighteen historical modal tables' **9,480** components remain
separate.

The [authoritative reference index](aswing-authoritative-references.md), its
checksummed catalog, Jan Part IV §3.4, the original Pazy input, `alpha_0.sh`
and native eigenvalue export were checked before selecting this contiguous
interval. The insertion-stack mapping remains native index = IAS + 1.
Declared zero incidence, density1.23, PG Mach0, gravity9.81, solid wall,
fixed frame, pointwise circulation, lag, updated influences and cosine40/80
remain unchanged. The required material station gives 41/81 actual intervals.
Native startup/restraint settings and the exact `I 40` convention remain
unauthenticated.

The ten new runs use the current implementation. The parent ledger retains
its original evidence and source pins. Its sole intervening production change
was the [bordered-LU storage-lifetime fix](isae-ae4-spacing-refinement-20261112.md),
which changed no equations or stopping gates. The subsequent
[circulation audit](isae-ae4-circulation-audit-20261112.md) reproduced the
earlier pointwise69/103 cosine40 roots exactly. The new batch is explicitly
identified as a later code epoch; inherited results are not relabelled as
fresh solves.

## Execution and next work

All **160 helper numerical checks** pass, along with the adapter's full
matrix-equation, mass-pairing, clamp, classification and result contracts.
All ten workers ran serially with one BLAS thread and are terminal and reaped.
Maximum child CPU /supervised wall /RSS are **9.31 s /11.44 s /299.8 MiB**.
The **512 MiB address-space /15 CPU /25 wall-second** caps are unchanged;
library preload remains separately bounded. All 142 production modules keep
their batch-start hashes. Browser/build checks remain held.

Next, extend the declared sweep through **76–79 m/s** on both meshes; 80 m/s
already has retained evidence. Keep near-onset damping, the conditional
103 m/s slow branch and tiny roots, native settings, wall/frame support,
mesh convergence, deformed branches and time histories open. AE-3 remains
open at 434/725.

- [Prospective batch selection](../../artifacts/isae/ae4-postflutter-coverage-20261112/selection.json)
- [Cumulative assessment, errors and exit receipts](../../artifacts/isae/ae4-postflutter-coverage-20261112/assessment.json)
- [Complete required-value ledger](../../artifacts/isae/ae4-postflutter-coverage-20261112/comparisons.csv)
