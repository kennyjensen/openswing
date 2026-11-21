# Literal zero-area inputs and ST-4 numerical checks

The 64 original ST-4/AE-6 files whose only import blocker was zero reference
area now import unchanged. Structural static and vacuum modal calculations can
use them. Aerodynamic calculations reject them with an explicit request for a
positive reference area; no area is inferred or substituted. Negative area and
nonpositive reference chord/span remain invalid.

The pinned ISAE repository is revision
`f62943df20e9e4d7d9f50e070477b22426b5f865`. All 279 original inputs were checked:
**177 parse unchanged and 102 remain rejected**. An additional 41 bundled
examples were checked. Every other parsed model or rejection is unchanged.
The [source audit](zero-reference-transition.json) limits the solver change to
the parser eligibility rule and two early aerodynamic validation calls. The
other 95 modules, including physical assembly and eigensolvers, are unchanged.

This does **not** establish experimental validation of ST-4 or AE-6. Coverage
remains 16 partial families and 25 pending, with none fully validated. ST-4
numerical evidence is supplemental until its experimental setup is reconciled.

## Numerical evidence

| Check | Result |
|---|---|
| Selected parser, editing, network, aerodynamic and zero-area regressions | 129 passed |
| ST-4 original inputs | 32 construct; one `W0M.asw` remains rejected for missing `End` |
| Unique ST-4 model contents | 27, each at 8, 16 and 32 default intervals |
| Native vacuum modal solves | 81 states; first six positive frequencies in each, 486 comparisons |
| Independent energy beam | 81 states at 64, 128 and 256 nominal intervals |
| Independent continuous beam | 27 models, exact segment transfers and point-mass jumps; analytic uncoupled torsion control |
| OpenSwing frequency refinement | All six frequency errors decrease at both mesh doublings, for every model |
| Largest OpenSwing frequency error at 32 intervals | 1.8565%, sixth mode of `7b_b11.asw` |
| Lowest kinetic mode-shape correlation at 32 intervals | 0.93724, sixth mode of `7d_b39.asw`; further refinement is needed |
| Largest 256-interval energy-reference frequency error versus continuous solution | 0.003866% |
| WebAssembly | Three fresh solves; full A/M matrices, frequencies, finite dimensions and normalization guard agree with native |
| Offline served browser | Three fresh solves; source export, frequencies, complete complex shapes, provenance and desktop/mobile rendering checked |

These runs use fixed root constraints, zero gravity and no aerodynamic or
apparent-mass loads. Original geometry, material properties, distributed
inertias, point masses and complete pylon offsets are retained. The independent
references use the same literal physical properties; they verify numerical
implementation rather than independently reconstructing the experiment.

The energy reference integrates Hermite bending and linear torsion functions
directly. The continuous reference propagates the six-component Rayleigh-beam
state through each uniform segment and applies the variational point-mass
jumps. The continuous calculation uses no mesh; fine energy frequencies locate
its root brackets. It is also checked against closed-form uncoupled torsion.

The first energy mesh inserted attachments beside almost coincident uniform
nodes. Its tiny intervals corrupted some low eigenvalues. The corrected mesh
replaces nearby interior nodes while preserving exact attachment positions.
The original failed calculations and scripts remain archived. Twenty-four
low-frequency reference refinement sequences remain nonmonotonic at the
roundoff floor; their actual errors are bounded against the continuous roots,
rather than hidden behind a monotonic-refinement assertion.

Three browser solves took 3.33, 10.35 and 11.76 seconds on this host; matching
WASM calls took 2.69, 4.59 and 4.56 seconds. These are observations for small
ST-4 models, not general browser performance guarantees. Screenshots show an
active 3D context in both desktop and mobile layouts. No full-repository test
rerun is claimed in this increment.

## Experimental questions still open

The primary [NACA TN-1594 report](https://digital.library.unt.edu/ark:/67531/metadc54595/m2/1/high_res_d/19930082244.pdf)
describes a wing hung from the top of the wind tunnel and measured before and
after runs. The vacuum, zero-gravity models above do not reproduce that setup.
Hanging preload, surrounding air, measurement uncertainty and the mapping
between attachment variants and recorded frequencies need explicit treatment.
The report is also indexed by [NASA](https://ntrs.nasa.gov/citations/19930082244).

The primary whole-wing centroidal polar inertia is 0.0382 lbf·in·s². Dividing
its SI conversion by the 48-inch span gives approximately 0.00354 kg·m.
Thirty imported ST-4 files use 0.0078 kg·m in their rotary-inertia field; two
`Weight7b` files use 0.0035. The factor is consistent with a missed pound-to-
kilogram conversion, but that is an inference, not proven source provenance.
The published polar inertia also does not uniquely establish both sectional
bending and torsional inertia components. No input was fitted or silently
corrected to match a frequency.

Some `Eigen_data_save.csv` entries disagree with the primary table. For
example, the primary run-88 row for variant 7a at 46 inches gives 3.16 Hz,
31.75 Hz and 17.6 Hz for the reported bending/torsion entries; the CSV mapping
does not preserve that row. The full table, including before/after differences,
still needs reconciliation before reporting matched experimental errors.
Archived ASWING outputs also need exact input and operating-setting provenance.

The [Drela user guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
describes reference area, chord and span as coefficient normalization values.
It does not document an automatic replacement for a zero reference area.
Accordingly, the AE-6 aerodynamic/flutter cases remain pending even though
their structural inputs can now be inspected and solved in vacuum.

## Reproduction

The raw `zero-reference-evidence.zip` archive preserves the original models,
source versions, matrices, energy/continuous references, logs, failed reference
attempts, primary scan and browser exports/screenshots. Its manifest pins every
member. Extract it and run the source audit from its `openswing/` directory:

```sh
python3 scripts/verify-zero-reference-transition.py --work ../work --output check.json
```

The archive audit repeats this command after extraction and requires an
identical result. Numerical reruns use `verify-isae-st4.py`,
`verify-isae-st4-reference.py`, `verify-isae-st4-transfer.py` and
`summarize-zero-reference-structure.py`; caches are keyed by source and inputs.
WASM and browser reruns also need the ordinary app runtime/build dependencies.

Machine-readable evidence: [imports](zero-reference-imports.json),
[native states](zero-reference-native.json), [energy reference](zero-reference-energy.json),
[continuous reference](zero-reference-transfer.json), [comparisons](zero-reference-structure.json),
[WASM](zero-reference-wasm.json), [browser](zero-reference-browser.json).
