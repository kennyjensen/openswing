# SA-6 public input and native-output history

2026-11-01. No earlier committed SA-6 model or native matrix was recovered
that could explain the remaining rate-derivative differences. All four
paired models, all 44 compared native `.fmat` files and the one retained
chordwise driver have identical bytes throughout the inspected public history.
This rules out a subsequent committed edit to those files as the explanation;
it does not prove that the archived outputs were generated from the archived
inputs and settings.

## Scope and evidence

The audit starts from the exact files used by the
[complete frozen-influence comparison](isae-sa6-frozen-derivatives-20261031.md),
not similarly named experimental or single-aileron models. It reuses the
cached GitHub trees for all 14 commits reachable from retained revision
[`f62943df20e9`](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/commit/f62943df20e9e4d7d9f50e070477b22426b5f865).
The commit-parent graph is checked for complete ancestry. Every tree is
untruncated and its SHA and cached-response digest are checked.

File matching retains the complete `Simulation/chordwise/...` suffix across
parent-directory renames. Every match is unique; no same-name alternative is
silently selected. Git blob identities are also reconstructed directly from
the local comparison-file bytes, including the Git blob header.

| Compared files | Files | Populated commits | Exact file checks |
|---|---:|---:|---:|
| 15%, 20%, 30%, 35%-chord paired models | 4 | 13 | 52 |
| Native matrices, 11 operating points per model | 44 | 13 | 572 |
| Retained chordwise shell driver | 1 | 13 | 13 |
| Total | 49 | 13 | **637** |

The four model names are `Straight_Wing_20b_15c`, `Straight_Wing_20b_20c`,
`Straight_Wing_20b_30c` and `Straight_Wing_20b_35c`. The oldest commit precedes
their import; the other 13 contain all 49 files. There are no changed blobs
or ambiguous entries in this scope. Earlier paths use `Ailerons` in place
of the current numbered case directory.

## Driver identity and limits

The literal `Post_Stall_15c.sh` invokes `aswing Straight_Wing_20b_35c`.
Its operating commands specify speed 20, incidence 12 degrees and F1 values
4 through 44 degrees in increments of four. The filename alone therefore
cannot identify the loaded model. That mismatch is already present in the
earliest populated tree; no historical version loading the 15%-chord model
was recovered. The script is inspected as text and never executed.

No dedicated driver for each of the other three paired models is established
by this audit. The retained native headers and comparison adapter continue
to supply their declared operating points. Frozen influences and stall
strength 20 remain a qualified reconstruction, not authenticated settings.
Uncommitted edits, inputs predating the public import, working-directory
defaults and the producing executable are outside the available history.

The [prior receiver comparison](../../artifacts/isae/sa6-frozen-derivatives-20261031/receiver-analysis.json)
already tested live-wind rotational-velocity points with frozen induced-flow
matrices: its eight-state sample changes from 253/288 to 247/288, with six
gains and twelve losses. The [apparent-load audit](isae-sa6-rate-output-audit-20261031.md)
also already covers both acceleration/output conventions. These checks were
reviewed, not rerun or counted again. Neither is a new correction to SA-6.

## Status

The qualified full SA-6 comparison remains **2,780/3,168 state derivatives**,
including **282/528 pitch-rate checks**, with **528/528 statics** and
**528/528 F1 derivatives**. Failed fine-mesh pitch-rate errors remain typically
20.81% for CXq, 18.84% for Cnq, 3.84% for CLq and 3.96% for Cmq. These are
the prior full-scope results, not newly evaluated outputs or registered gains.

Production equations, physical settings, reference values and all 42 registered
status rows are unchanged. No aerodynamic solve, download, browser, build or
background numerical job is used. The next investigation must address the
unresolved native rate/stall response or obtain stronger settings evidence;
public-history substitutions do not provide a remedy for these files.
SA-6–SA-10 and the full project remain unfinished.

[Declared scope and pins](../../artifacts/isae/sa6-source-history-20261101/plan.json),
[complete file histories](../../artifacts/isae/sa6-source-history-20261101/analysis.json),
[verification receipt](../../artifacts/isae/sa6-source-history-20261101/receipt.json).
