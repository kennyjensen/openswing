# FFWT-4 full-history spatial/time study — in progress

The nominal128 mesh (159 actual nodes) is being used for the complete Fixed-1
gust history at dt=0.0018625 s. The required horizon is 2.9651 s, or 1,592
physical steps. It starts from an independent cold equilibrium with the same
literal model, original first gust, operating point and authenticated kernel
as the completed initial spatial and nominal32 time studies.

The last independently audited prefix is **1,162 accepted steps through
2.164225 s**, with zero rejected steps and maximum residual 9.974633e-9,
below the unchanged 1e-8 residual limit. All 117 selected process jobs exited
successfully; none was excluded. All **146/146 reached native values** pass at
5%, with median/max error **0.762790%/0.892512%**. This covers the gust peak,
its falling load and the beginning of the unforced response. Another
**430 physical steps** remain
on this mesh. A partial history cannot establish full-window spatial or
temporal accuracy.

At the native peak time, **0.9983 s**, OpenSwing predicts **1.139318 N m**
against **1.132400 N m**, an error of **0.610899%**. This compares the same
physical time in both histories; no phase shift is applied.

![Computed prefix and archived ASWING history](../../artifacts/isae/ffwt4-spatial-time-20261106/n128-d8/plots-s1162/comparison.png)

The plot includes every computed time step and marks the uncomputed interval
in gray. Native errors use exact matching time indices; the displayed native
time tokens are rounded in the original output. No interpolation or alignment
fit is used to score the comparison.

At the earlier audited state at step 842 (1.568225 s), an independent
evaluation of the literal gust formula confirms that all **535 aerodynamic gust sample positions** have
left its compact spatial slab. Their normalized coordinates are
2.135856–2.140863, beyond the slab's upper boundary of 2. The independently
calculated gust is zero at every sample, and the reported reference gust is
also zero. This confirms the end of the prescribed forcing; it does not
replace the remaining unforced-response history or its accuracy checks.

The [complete source inventory](isae-ffwt4-sources-20261106.md) expands the
main ISAE scope to **200/8,000** across all 40 archived histories. The
fixed-wing subset remains **200/1,600** from the previous complete Fixed-1
history. Values repeated on this finer mesh do not add native targets.

## Controlled comparisons

`artifacts/isae/ffwt4-spatial-time-20261106/study-plan.json` records the planned
complete histories and unchanged gates:

| Nominal intervals | Actual nodes | Time step (s) | Required steps | Purpose |
| ---: | ---: | ---: | ---: | --- |
| 128 | 159 | 0.0018625 | 1,592 | Coarser member of the spatial pair; 1,162 steps audited |
| 256 | 287 | 0.003725 | 796 | Coarser member of the finest-mesh time pair |
| 256 | 287 | 0.0018625 | 1,592 | Finer member of both comparisons |

Spatial comparisons hold dt fixed; temporal comparisons hold the mesh fixed.
Every shared physical time is required, along with every shared material node
for displacement and small rotation-vector checks. Root moment and its
increment from t=0 retain their separate 0.1% gates. The field comparisons
also use 0.1%. A failed gate requires further refinement; no tolerance or
physical parameter is adjusted to obtain a pass. Other physical fields and
exact historical defaults remain qualified separately.

## Small serial jobs and independent checks

Each continuation job advances at most ten steps, using one BLAS thread and
512 MiB virtual address space. The cold two-step start had a 150-second cap;
continuations through step 242 used 90 seconds, and later jobs use 150 seconds
to leave headroom at gust onset. These are wall-clock caps, not solver
tolerances. The latest eight ten-step jobs all completed successfully. The
independent read-only history audit completed in 160.32 seconds, with no
physical solves. Actual return codes, requests,
complete losslessly compressed results, checkpoints and reports are retained.
No coarse-mesh state is transferred to the finer mesh. BDF1 is used only at
the first physical step, followed by BDF2 with both predecessors preserved.

The independent history assessor checks all source hashes, actual imported
module paths, mesh identity, exact input requests, every saved time and
residual, the root sensor's left trace, BDF order and coefficients, checkpoint
replay, contiguous coverage and successful process exits. All 1,600 target
slots remain present, including uncomputed values. Eleven audit tests pass.

The first audit attempt exposed a checker format error: canonical BDF1 data
stores three coefficients `[1/h, -1/h, 0]`, while the new checker initially
expected two. The corrected checker requires the zero third coefficient and
the documented scheme. The saved coefficients were already correct. The
failed checker and original test run are retained; no solver output, equation
or numerical tolerance was changed. `audit-attempts.json` records the failure
and successful follow-up.

Each new assessment saves an immutable copy of the process receipts. Its
hash remains valid when later continuation jobs append to the live journal.
The source journal's original hash is retained as provenance. The original
unwrapped prefix assessment is preserved alongside the version with immutable
receipts; its original journal bytes are available in the latter's receipt copy.

## Full-history field comparison

`scripts/assess-isae-ffwt4-field-refinement-v2.py` prepares the independent
comparison for the planned complete histories. It accepts authenticated
`HISTORY_ASSESSED` results only when every required step is present. It checks
the source inputs, archived equations, process receipts and saved results;
spatial comparisons may change only nominal mesh count, and temporal
comparisons may change only the step size on the same initial mesh. The
original field checker remains unchanged as its shared-time comparison core.

The reader distills one saved segment at a time into lossless JSONL nodal
fields, then compares the two streams. This avoids retaining both complete
nonlinear histories in memory. It reconstructs displacement by subtracting
jig geometry and checks nodal continuity across every restart. Every shared
time and material node contributes to the comparison; fine-only times are
still checked for valid fields. No time or spatial interpolation is used.

The four combined 0.1% quantity gates cover total root moment, its increment
from each history's own initial value, displacement and rotation vectors.
Each root quantity must pass both the original 200-output-time gate and the
denser shared-time gate. Each retains its own finer-grid maximum as its
normalization scale. Vector scales use shared times and every fine-grid node.
Rotation-vector subtraction is restricted to norms below 0.1 rad. Missing
tails, mismatched grids, changed physical inputs and nonfinite fields cannot
produce a pass. A zero scale cannot establish a relative accuracy gate.

Review against the original run plan found why the explicit original gates
are necessary: a larger peak between native output times can enlarge the
shared-time normalization. Merely including all native samples in the denser
comparison does not preserve their original gate. The version-2 wrapper
retains both calculations and requires both to pass. The preceding shared-time
checker and its evidence are preserved; no complete physical comparison had
yet been assessed with it, and no solver result or native-match count changed.

All **59 focused tests** pass: 15 new native-gate checks, 23 field-comparison
tests, 11 history checks and 10 initial-mesh checks. They include a constructed
case that passes all four shared-time gates but fails both original native-time
gates; the combined verdict correctly fails. The converse case verifies that
an error between native outputs cannot be hidden by passing native samples.
The earlier tests include an error between native output times
hidden by a large steady moment, interior nodal errors with an unchanged root
sensor, invalid fine-only states, incomplete histories and changed restart
fields. A CLI check of version 2 against the real 562-step assessment also
rejects the incomplete history before creating an output directory; the
earlier version's 322-step rejection is preserved. These tests verify
the checker; no full-window field accuracy result exists yet. A passing grid
pair would measure refinement change, not prove an absolute error bound.

An additional reader preflight checks 33 real saved snapshots around the
gust peak (31 unique times, including two continuation overlaps). Both shared
nodal states agree exactly across the restarts. The maximum rotation-vector
norm is 0.013570 rad, within the reader's small-rotation regime. This checks
the saved-field interface; it is not a spatial or temporal refinement result.

Evidence is under `artifacts/isae/ffwt4-spatial-time-20261106/`:

- `n128-d8/serial-terminal.json`: live journal of actual child exits.
- `n128-d8/assessment-s1042.json` and its `.terminals.json` companion:
  independently checked prefix and immutable process receipts. The earlier
  82-, 322-, 562-, 842-, 962- and 1,002-step assessments and receipt copies are preserved.
- `n128-d8/plots-s1162/comparison.png` and `.svg`: the audited prefix against
  the complete archived first history, with pinned plot inputs.
- `history-audit-tests-v2.xml`: eleven passing tests. The earlier nine-test
  run and failed checker source are retained separately.
- `field-refinement-tests.xml`: 44 passing focused checks, including 23 new
  full-history field tests. `field-refinement-contract.json` preserves the
  actual CLI refusal of an incomplete history and the checker/test hashes.
- `field-native-gates-tests.xml`: 59 passing checks, including the 15 added
  original-time gate tests. `field-native-gates-contract.json` records the
  version-2 checker, its expected incomplete-history refusal and source pins.
- `field-reader-s562.py` and `.json`: reproducible real-field preflight,
  two restart comparisons and authenticated inputs around the peak.
- `gust-clearance-s842.py` and `.json`: independent evaluation of the
  prescribed gust at the saved final coordinates; all 535 samples are outside
  its spatial slab. This is a forcing check, not a full-history accuracy pass.
- `study-plan.json`: complete comparison windows, grids and gates.

Full-history numerical accuracy is still unassessed. The rest of the fixed
histories, hinged cases, other state fields and shared suite registration
remain required; no whole-family validation is claimed.
