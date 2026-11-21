# ST-5: audit of the remaining near-zero force difference

The sole primary miss remains required: **16,687/16,688** observations pass.
The source token and exponent are correct, OpenSwing's equilibrium residual
is already about **6.1e-14**, and four coordinate-precision probes do not
resolve the discrepancy. No production equation, target or tolerance changed.

## Original output and force scale

The case is `Rigid_Joint/JW_1_30lb_80_20`, forward beam at printed
`t = 1.795828 ft`, original text line 67. The original `Fn/10` column has
exponent 1, so the token `-0.000029` means **−0.000290 lb**. The derivative
MATLAB file agrees with all **240** force entries in this snapshot; it is a
copy of the export, not an independent ASWING run.

| Quantity | Archived ASWING | Current OpenSwing |
|---|---:|---:|
| Local chord force, Fc (lb) | −16.6652 | −16.665869609 |
| Local span force, Fs (lb) | 10.83504 | 10.834715689 |
| Local normal force, Fn (lb) | −0.000290 | −0.000328058454 |

The Fn error is **0.00003805845 lb**, or **13.1236%**. The relative error
of the complete three-component force vector is **0.0037478%**. That vector
measure provides scale; it does not replace the required component comparison.
The declared Fn allowance remains 5% of the native magnitude plus its original
printed half-unit: **0.0000195 lb**, less than the actual error.

The OpenSwing normal projection sums approximately
`0.0090803993 − 1.7109680908 + 1.7015596331 lb`.
The sum of absolute terms is about **10,430 times** the resulting Fn. This
explains why a small change in force or orientation can produce a large
relative error in this component; it does not identify the source of the error.

## Mirrored source locations

At the opposite location, `t = −1.795828 ft` (line 46), native Fn is
**+0.000330 lb** and OpenSwing gives **+0.000328055025 lb**. The two native
values sum to **0.000040 lb**, exceeding their combined **0.000010 lb**
printed half-unit allowance. OpenSwing's corresponding sum is about
**−3.43e-9 lb**.

This native left/right asymmetry is evidence to investigate, not proof that
the export is wrong. Other archived node pairs are not exactly mirrored at
printed precision, and the original unrounded nodes, iteration history and
executable are unavailable. The source audit retains all sixteen cases and
all force-vector/mirror comparisons in its machine-readable evidence.

## Predeclared coordinate probes

Two perturbation directions were declared before solving, each evaluated
at both endpoints. The first moves only the failing node by **±0.0000005 ft**.
The second moves all **30 ordinary positive-side rows** by their own printed
half-unit in the same direction. Known exact model anchors remain fixed.
Mesh nodes and recovered output locations move together; original geometry,
loads, properties, all 80 output rows and the recovery equations are retained.

| Diagnostic | Fn (lb) | Change from nominal (lb) | Native Fn error |
|---|---:|---:|---:|
| Failing node, lower printed endpoint | −0.000324475336 | +0.000003583118 | 11.8880% |
| Failing node, upper printed endpoint | −0.000331641570 | −0.000003583116 | 14.3592% |
| Positive ordinary nodes, lower endpoints | −0.000324466527 | +0.000003591926 | 11.8850% |
| Positive ordinary nodes, upper endpoints | −0.000331650379 | −0.000003591926 | 14.3622% |

The largest tested coordinate effect is **9.44% of the original absolute
discrepancy**. All four predictions still fail the unchanged component gate.
These two directions are not an exhaustive coordinate-uncertainty bound and
do not recover the original ASWING mesh. They give no basis for selecting a
different nominal node or promoting another pass.

All four cold solves pass the physical checks. Fresh residuals remain below
**6.07e-14**, force imbalance below **1.43e-14 lb**, moment imbalance below
**3.57e-11 lb-ft**, and joint-position mismatch below **4.0e-15 ft**.
Jobs ran serially with one BLAS thread and the existing 512 MiB, 15 CPU-second
and 25 wall-second child limits. Maximum measured child usage was
**3.60 CPU seconds, 16.84 wall seconds and 94,004 KiB peak RSS**.
No numerical attempt failed or was retried.

## Reference interpretation and remaining work

The [authoritative reference index](aswing-authoritative-references.md) and
its checksummed catalog govern this comparison. Jan's
[Part III](../../reference/aswing-authoritative-20261108/isae-part-3-structure.pdf),
§4.5, pp. 40–44, supplies the joined-wing loads and joint definitions.
The report's modified in-plane link remains distinct from the public literal
type-2 roller; this force miss belongs to the rigid-joint case.

The archived `.sh` requests one `X` before exporting. Drela's
[user documentation](../../reference/aswing_doc.txt), “Computation of an
operating point” and “Iteration Limit — I,” explains that another `X` continues
iterations if the iteration limit was reached. One `X` therefore does not
establish the archived residual. The driver path contains `Aswing_R_5_92`,
which does not authenticate the executable's contents. No native stopping
threshold or convergence failure is inferred from those facts.

The audit rules out a force-token/exponent mistake and finds no evidence that
tightening OpenSwing's nominal equilibrium solve would help. The tested
coordinate shifts do not explain the miss. Native stopping behavior,
unrounded node generation and export recovery remain possible explanations;
none is established. Further work should address those source/setup questions
and the separate joint/reaction-display uncertainties, while retaining this
failure and the unavailable modal evidence.

## Evidence and reproduction

- [Prepared hypotheses and pinned sources](../../artifacts/isae/st5-force-audit-20261110-v2/study.json)
- [Original-output and mirrored-force audit](../../artifacts/isae/st5-force-audit-20261110-v2/archive-audit.json)
- [Four-probe summary and timing](../../artifacts/isae/st5-force-audit-20261110-v2/summary.json)
- [Final saved-artifact verification](../../artifacts/isae/st5-force-audit-20261110-v2/verification.json)
- [Diagnostic driver](../../scripts/investigate_st5_force.py)

Use `prepare` with a new output directory, then `archive`, four separate
`run --case NAME` invocations in the declared order, and `summarize`.
Set all four BLAS/thread environment variables to 1. Existing attempts cannot
be overwritten. The earlier archive-reader metadata failure is preserved in
`artifacts/isae/st5-force-audit-20261110/archive-failure.json`; it ran no solver.
The corrected reader and all successful numerical evidence are in the v2
directory above. These diagnostics add no primary observations or passes.
