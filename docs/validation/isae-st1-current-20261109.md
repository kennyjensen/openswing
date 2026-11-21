# ST-1 current baseline and next focus

The user requested switching to ST-1 after the
[SA-14 checkpoint](isae-sa14-low-angle-20261109.md). SA-12, SA-13 and SA-14
remain open. The current registered ST-1 scope now passes **6/200 at 5%**,
versus **2/200 at original printed precision**. This change applies the user's
existing tolerance to fresh computations; it is not an improvement to the
structural equations or an expansion of computed coverage.

Both unchanged `[45_0]_3a` static solves converge, and all **52 setup/numerical checks**
pass. All 37 registered records were refreshed: two computed states and 35
unsupported/inventory records. The other 194 scalar targets remain required.
The [subsequent mechanics review](isae-st1-mechanics-review-20261109.md)
clarifies that these are one physical condition on two meshes; the 52 checks
include source/setup and save/restore bookkeeping. It sets the next priority
to representative ASWING static curves and identified bending/torsion modes.

| Body-relative sensor position | Archived ASWING, m | Nominal 100, m | Error | Nominal 200, m | Error |
|---|---:|---:|---:|---:|---:|
| X | −0.129671 | −0.129671038510 | 0.000030% | −0.129679125110 | 0.006266% |
| Y | −0.189497 | −0.189496845695 | 0.000081% | −0.189493515411 | 0.001839% |
| Z | −0.0949139 | −0.094914981735 | 0.001140% | −0.094926270241 | 0.013033% |

These are absolute body-coordinate positions from the native rx/ry/rz export,
not the baseline-subtracted experimental deflections. Their agreement does
not establish the other static configurations or the modal response. The
coarse-to-fine change still moves away from the finite-grid archived values;
both results and the original strict failures remain available.

## Source interpretation and remaining work

The [authoritative references](aswing-authoritative-references.md) were checked
before the refresh. ISAE Part III §4.1, pp. 28–31, describes nonlinear loaded
and unloaded blade equilibria followed by modal analysis about the equilibrium.
Table 2 labels ST-1 fully repeatable. That classification is retained alongside
the unresolved details in the supplied files; it is not evidence that the
current comparison already covers the family.

The report says 40 cosine-clustered structural nodes; the retained static
driver requests `I 100`. The current comparison preserves its existing nominal
100/200 grids, with the exact sensor station giving 101/201 actual intervals.
It uses the literal 0.4 kg tip mass, original stiffness and variable twist,
clamp at +0.28 m, sensor at −0.22 m, body gravity [0, 0, −9.81], and no airflow.
Historical node arrays, startup pose/airflow and continuation remain unverified.
The complete beam-anchor position is measurable despite the supplied parallel
sensor vectors; undefined triad-dependent measurements remain unavailable.

The source issues identified at this baseline are listed below. The subsequent
mechanics review governs the priority; it permits explicit syntax-only derived
inputs and prioritizes physically identified modes over unclassified roots.

1. Resolve the two other directly paired static inputs, `[20_m70_20]_2a` and
   `[45_0]_3s`. Their remaining syntax blocker is a trailing empty `Engine`
   header without `End`; neither has the ambiguous surplus scale values.
   Their final mass/twist settings must also be reconciled with the generating
   postprocessor before claiming a native comparison. Any explicit syntax-only
   derived input must be retained separately from its original bytes.
2. Audit the extra distribution scale value in four `[0_90]` inputs against
   named columns and documented units. These affect the mesh study and other
   static/modal comparisons, so silently dropping a value is inappropriate.
3. Establish each modal equilibrium and vacuum/airflow setting before comparing
   all 76 archived complex roots. Retain their real and imaginary parts,
   including 25 real-only roots; selected positive frequencies alone would
   cover a different target set.

The 194 unavailable slots comprise 42 other position components and 152
eigenvalue components. Additional unpaired plots/arrays remain outside the
original 200-slot scope. Missing targets have no assigned numerical error.

## Verification and reproduction

[The serial runner](../../scripts/verify_st1_current.py) preserves the existing
adapter and strict contracts, then applies the shared 5% acceptance layer.
An independent Decimal calculation rechecks all 200 decisions against the
original tokens. The summary authenticates 270 pins, every retained job
artifact, all numerical gates and both strict/accepted result views. All 141
production modules are unchanged.

Each physical job performs one cold solve and one restored-state residual;
residuals are 3.68e−16 and 4.04e−16. Job times including production imports and
verification are 8.09 s and 7.16 s; peak resident memory is below 232 MiB.
Each foreground process is limited to one BLAS thread, 512 MiB address space,
15 CPU seconds and 25 wall seconds. No browser/build/background solver job ran.

[Machine summary](../../artifacts/isae/st1-current-20261109/summary.json) ·
[plan and original source pins](../../artifacts/isae/st1-current-20261109/plan.json) ·
[historical strict comparison](isae-suite-st1-20261027.md).
