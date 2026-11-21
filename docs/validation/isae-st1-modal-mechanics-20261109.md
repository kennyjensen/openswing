# ST-1 modal mechanics: named frequencies and mixed mode identity

**Update:** the subsequent [cross-ply comparison](isae-st1-cross-modal-20261109.md)
adds four documented-reconstruction matches, and the
[thin-blade study](isae-st1-thin-modal-20261109.md) adds nine, bringing current
modal coverage to **20/22**. The two-layout study below retains its original evidence and
scope-change history.

**Seven of the report's 22 named frequencies pass at 5%.** The seven matches
have maximum fine-grid error **0.365%**. One computed comparison has unresolved
mode identity; 14 targets need further input/setup reconstruction. The static
suite remains [201/201](isae-st1-static-curves-20261109.md).

The progress table now uses those two independent mechanics scopes as its
primary ST-1 measure: **208/223**, with the old **9/200 archive inventory**
retained separately. This is an explicit scope change, not 199 newly matched
archive cells. Static displacements and modal frequencies are independent
observables; repeated meshes and alternate physical settings receive no extra
votes. All 22 frequency targets, including the unresolved ones, were declared
before the first modal solve. The original archive denominator remains intact.

## Named frequency comparisons

Targets are the **ASW** rows of ISAE Part III Table 3, p. 35, rather than the
experimental rows. Three bending modes and the first torsional mode are checked
for each of the first three layouts; the two thin-blade orientations also have
a first in-plane mode, giving 22 published frequency cells.

| Layout | Report label | ASWING, Hz | OpenSwing N80, Hz | Error | Result |
|---|---|---:|---:|---:|---|
| `[20/−70/−70/20]2a` | 1B | 5.86 | 5.865955 | 0.102% | Pass |
| Same | 2B | 36.8 | 36.762152 | 0.103% | Pass |
| Same | 3B | 103 | 102.994365 | 0.0055% | Pass |
| Same | 1T | 187 | 187.532665 | 0.285% | Pass |
| `[45/0]3s` | 1B | 4.75 | 4.751899 | 0.0400% | Pass |
| Same | 2B | 29.81 | 29.768797 | 0.139% | Pass |
| Same | 3B | 83.7 | 83.394562 | 0.365% | Pass |
| Same | 1T | 95.0 | 137.089955 | 44.305% | Identity unresolved; literal label comparison fails |

The **95 Hz frequency is present**: OpenSwing gives 95.025512 Hz, within
0.027% of the printed number. Its mode is predominantly in-plane bending,
with 31.9% torsional activity; the 137.09 Hz mode has 68.6% torsional activity.
The reported 95 Hz number is not substituted for the torsional branch to obtain
a pass. Conversely, this label mismatch alone does not establish incorrect
beam mechanics.

The angle-ply archive similarly includes a 98.65 Hz mode before the third
bending mode. Its computed shape is 99% in-plane bending; the torsional mode
is near 187.53 Hz, as Table 3 specifies. Sorting frequencies without examining
shapes would pair these incorrectly.

## Coupled-blade branch diagnostic

![Mode branches under self-weight](../../artifacts/isae/st1-modal-mechanics-20261109/branches.png)

[SVG](../../artifacts/isae/st1-modal-mechanics-20261109/branches.svg).

With gravity removed, the lower branch is pure in-plane bending at 115.65 Hz,
and the upper is essentially pure torsion at 118.43 Hz. At quarter, half and
full gravity they become mixed but preserve their dominant identities. Adjacent
mass/inertia-weighted shape correlations favor the same branches over swapping
them. Correlations for the first interval are about 0.66 on the diagonal versus
0.34 off-diagonal; subsequent same-branch correlations exceed 0.995. This is a
sampled branch diagnostic, not a continuous proof between every load level.

The source `post_traitement.m` compares the coupled blade's first four listed
roots with the four experimental frequencies. Its fourth native root is
597.11245 rad/s, approximately 95.03 Hz. The report then labels that number 1T.
Our computed shapes and load dependence support a reference-label explanation,
but native eigenvectors are unavailable, so the identity conflict stays open.
All lower-gravity states are diagnostics and add no native passes.

## Setup and numerical evidence

Original modal files are preserved, with only an explicit `End` appended to
their empty trailing Engine blocks. Unlike the static angle-ply file, its modal
file specifies mass per length 0.091 kg/m; the original rotary inertias and all
stiffnesses are also retained. The coupled modal file uses 0.0697 kg/m and
EIcs=0.102 N m². Both have zero tip mass and zero root twist.

The base is the nonlinear equilibrium under self-weight, as described in
Part III §4.1, pp. 28 and 31. The original drivers request 40 structural nodes
and issue `f` before the eigenvalue solve. Drela's user documentation identifies
MODE `F` as the vacuum toggle (local `reference/aswing_doc.txt`, line 3485).
The primary comparison therefore uses the fixed-frame source vacuum operator.
The archived executable's initial toggle state and exact node coordinates are
not available. Current meshes use 40/80 cosine intervals and 41/81 nodes.
A preceding angle-ply still-air run remains a separate diagnostic; no fluid
parameter was fitted to improve agreement.

The solver uses the full descriptor pencil and shifted inverse iteration,
consistent with Drela's unsteady description §13.3, Eqs. 144–149. The survey
shift is −0.01 + 0i, selected to retrieve low modes broadly; the source script's
−0.1 + 300i shift explains why its returned list need not cover all named modes.
Changing a search shift does not alter the eigenvalue problem.

Mode identification precedes reference matching. A mode needs more than 55%
of its structural kinetic shape activity in a family: normal displacement and
chordwise rotation for bending, chordwise displacement and normal rotation for
in-plane bending, or spanwise rotation for torsion. The first three bending
modes must have zero, one and two internal displacement zeros. The first
torsional mode must have no internal twist zero. No reference frequency enters
that selection.

All eight compared mode shapes match across meshes with weighted MAC above
0.999993. Their frequency changes are at most 0.586%. All accepted base states
converge. Replaying the saved original sparse A/M matrices and both eigenvectors
for 96 returned modes gives 192 action-relative eigen-equation residuals, all
below 1.47e−12. These are numerical checks, not additional physical benchmarks.
They do not prove completeness of the entire descriptor spectrum.

One count-16 coupled N80 attempt reached the 25 s wall limit without returning
a result. It remains recorded as an interrupted attempt. A count-12 survey on
the same N80 equations retains every named target and the in-plane branch,
completes in 3.66 s after imports, and passes the unchanged numerical gates.
This does not claim a general fix for the larger survey's performance.
An initial independent-checker time-unit mistake is also retained: the exported
matrices already satisfy `M dz/dt = A z`, so their physical eigenvalue must not
be divided by the internal time scale again. Correcting that checker changed
no physical result, production source or reference value.

Seven accepted primary/refinement/branch jobs used one BLAS thread, 512 MiB
address-space, 15 s CPU and 25 s wall limits. Peak RSS stayed below 260 MiB;
accepted solves took 2.73–9.14 s after imports. All 141 production modules
remain unchanged. Browser/build work remains held.

## Remaining setups

| Layout | Required named frequencies | Current issue |
|---|---:|---|
| `[0/90]3s` | 4 | Modal file scales GKn by 1e−5 and includes an unnamed extra scale. Its archived roots differ from Table 3 and the postprocessor. The report's material table also differs in mass and shear properties. Audit these separately; do not silently normalize physical values. |
| `[45/0]s`, up | 5 | Supplied file has negative distributed mass/weight scaling, with no corresponding driver establishing the reported orientation. Positive inertia and the generating setup need reconciliation. |
| `[45/0]s`, down | 5 | Same setup issue. Table 3 literally prints 218 Hz for 3B, while the original postprocessor uses 21.8 Hz. Both sources are preserved; the target remains unresolved. |

The original table was rendered and inspected in
[Table 3](../../artifacts/isae/st1-modal-mechanics-20261109/table3.png).
Negative mass discussed on report p. 36 concerns applying static forces in ST-3;
it does not establish a negative-inertia convention for ST-1 modes.

The subsequent [Minguet source review](isae-st1-material-source-review-20261109.md)
confirms the physical cross-ply shear stiffness and thin-blade coupling
magnitude from the original thesis. It prepares an explicit cross-ply
reconstruction. Its first attempt hit the wall limit before modal dispatch,
so no result or additional pass follows; all 14 pending targets remain.

[Primary runner](../../scripts/verify_st1_modal_mechanics.py) ·
[branch diagnostic](../../scripts/diagnose_st1_modal_branches.py) ·
[saved-result verifier and plotter](../../scripts/summarize_st1_modal_mechanics.py) ·
[summary](../../artifacts/isae/st1-modal-mechanics-20261109/summary.json) ·
[scope definition](isae-st1-mechanics-scope.json) ·
[authoritative references](aswing-authoritative-references.md).
