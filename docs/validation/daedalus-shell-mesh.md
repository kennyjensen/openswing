# Daedalus: display-only shell tables and the physical mesh

Shell display fields no longer change a fresh computational mesh. A new
Daedalus trim and four-frequency comparison confirms that this correction
**does not resolve the Bode disagreement**. At the drawing's yaw-dip frequency,
1.15737773741517 Hz, the calculated magnitude is **2.172 times** the drawing.

## Correction and saved cases

The [ASWING guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
identifies `Cshell`, `Nshell` and `Atshell` as shell recovery
inputs for displayed strain/stress. Their doubled stations previously added
mandatory computational nodes and changed material-arc sampling. They now
remain available for recovery without changing fresh physical meshes. Geometry,
stiffness, load, control and attachment breaks remain active. This correction
does not implement every historical ASWING `KBREAK` option.

For nominal 16 panels per beam, the literal Daedalus model now has 108 nodes,
103 elements and 82 circulation unknowns, versus 117, 112 and 91 previously.
The wing loses six shell-only nodes, the stabilizer two, and the fin one.

Saved states retain the mesh construction that produced their equations.
Old packets without recipe metadata use their original all-table breaks,
including material-arc quadrature; new packets identify the physical-only
recipe. This applies to steady warm starts, saved time launches, checkpoint
replay, flow inspection and controller paths. The existing identity and
physical/discrete residual checks remain binding. No state interpolation or
identity tolerance relaxation is used. Changed requested counts, spacing,
explicit nodes, source or attachments still require a compatible mesh.

The original C16 Daedalus state restores with a full residual of `4.36e-13`.
Both original 16/32 meshes and both corrected meshes reproduce the separately
frozen mesh reports exactly. Curved-beam regression checks also cover the
arc coordinates, aerodynamic/structural sampling points and transported frames.

Verification passes 140 existing focused native tests and 49 new recipe tests.
The [focused WASM test](../../scripts/test-mesh-recipe-wasm.mjs) passes 67 checks
using frozen native fixtures, including actual historical-source packets,
nonzero BDF2/Radau checkpoints, unchanged identity/residual gates and shell-edit
invariance. The source implementation and shipped kernel use the same modules.

## Fresh aircraft comparison

The run retains the literal `dae.asw`, 6.7 m/s speed, Mach 0.1, unsteady
circulation, seven steady-level trim constraints and six released net-load
equations. The old physical state supplies an explicitly declared *new study
initial guess*: retained nodal fields are copied, and element resultants and
circulation are interpolated before a complete equilibrium correction. This
study preparation is separate from saved-state restoration.

One corrected equilibrium, one full descriptor and one native F3 input column
supply four full sparse harmonic solves. The final fresh base residual is
`5.86e-11`. All original rank, residual and conditioning gates pass, with no
fitted property, altered physical condition or relaxed tolerance.

| Frequency, Hz | Old C16 yaw | Corrected C16 yaw | Drela drawing |
| --- | ---: | ---: | ---: |
| 0.1 | 0.121697 | 0.121426 | 0.118238 |
| 1 | 0.0749405 | 0.0752493 | 0.0587461 |
| 1.157377737 | 0.0734544 | 0.0738024 | 0.0339862 |
| 10 | 0.208850 | 0.207464 | 0.171868 |

Rates are degrees/second per native F3 unit. At 1 Hz the corrected yaw
magnitude is 28.1% high and roll is 32.7% low. The largest complex change across
all four outputs and four frequencies is 0.982%, relative to the old response.
Four samples do not locate a new curve minimum or establish mesh convergence.
The earlier [full C32 comparison](daedalus-rudder-four-outputs.md) remains a
separate result on its recorded original mesh.

The study passes 142/142 numerical checks. An independent saved-array audit
passes 453/453 checks, reconstructing yaw, roll, sideslip and bank without
another aircraft solve. The supervised native run took 97.6 seconds, including
70.5 seconds for trim and 19.8 seconds for linearization. These shared-host
observations are not browser benchmarks or a controlled speed comparison.

## Reproduce and inspect

Import the [corrected-mesh cruise project](../../examples/dae-cruise-physical-mesh-project.json)
through **Project & saved cases**, load its case, and select
**control.3 · Rudder → Flight frame → Yaw rate r** after solving. The project
requests 101 logarithmic UI frequencies; this study checked four exact
frequencies. Its saved equilibrium is separately recaptured and residual-checked
with current recipe metadata before publication.

The [report](daedalus-shell-mesh.json), [CSV](daedalus-shell-mesh.csv) and
[evidence archive](daedalus-low-frequency-shell-mesh-20261025-evidence.zip)
retain source snapshots, inputs, raw complex states, independent checks and
process receipts. The [low-frequency modal analysis](daedalus-low-frequency-modes.md)
identifies a strongly participating 1.233 Hz mode on the original C16 mesh;
it has not established a missing physical term or the cause of the mismatch.
The reference trim, mesh and phase response remain unknown. Agreement with
Drela and the full OpenSwing goal remain unverified.
