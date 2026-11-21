# ASWING input breaks and compatibility notes

2026-10-30. The documented default KBREAK property list does **not** explain
the remaining SA-1–SA-5 differences. All five literal ISAE inputs have the same
required break locations under that list and OpenSwing's current broader
physical-break policy: the center plane at `t=0`.

This is a comparison of mandatory station locations. It does not establish
native node generation, duplicated-node counts, the interpolation of properties
onto computational nodes, or complete native mesh equivalence.

## Source requirement and implementation

The [ASWING User Guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt),
“Considerations for Data Discontinuities”, distinguishes doubled stations that
enable computational breaks from other variables. Its default list is:

`x y z twist Dmgcc Dmgnn Dmg DCcg DNcg chord alpha`, plus indexed `dCLdF` and
`dCMdF` controls. The list does not include `dCDdF`. Additional variables can be
enabled in a native build's `INDEXB.INC`; the exact historical build is unknown.
The guide calls for a warning when other variables have a **value jump**, but
does not warn for a slope break alone.

OpenSwing now exposes these cases as nonfatal `compatibility_notes` in model
inspection and an expandable **ASWING input compatibility** list in the browser.
Each note identifies the beam, property, source table line, input stations,
left/right values and reflection flag. Checks use the scaled, ordered input
table. Mirrored copies do not generate duplicate messages. Notes refresh after
edits and do not change source serialization, model identity, mesh construction
or equations. Unsupported-input diagnostics remain separate and still block
analysis. In particular, this does not make Daedalus's documented input jumps
an error that prevents loading or solving.

The existing stronger physical-break policy remains in place. Implementing the
complete native property-to-node interpolation and zero-length interval rules
still requires separate work; this addition implements the documented warning,
not full KBREAK parity.

## Repository audit

The [reproducible audit](../../artifacts/isae/input-break-audit-20261030/run.py)
checks all 279 `.asw` files in the pinned public ISAE snapshot. Its independent
transcription of the guide's list is compared with current mandatory locations;
actual value jumps are independently enumerated and checked against the new
compatibility notes. Source hashes and all outcomes are retained in
[results.json](../../artifacts/isae/input-break-audit-20261030/results.json).

| Scope | Result |
| --- | --- |
| Files parsed | 212/279 |
| Parsed files with additional OpenSwing break locations | 7, all in FFWT-5 |
| Parsed files missing a documented mandatory break location | 0 |
| Parsed files with value jumps outside the documented default list | 21 |
| SA-1–SA-5 files with a differing break location | 0/5 |
| SA-1–SA-5 files with compatibility value-jump notes | 0/5 |

The seven FFWT-5 files add breaks at `t=±0.875`. This identifies a native-mesh
compatibility question, not proof that the native builds used a different mesh.
Other files can have nondefault property jumps coincident with already enabled
geometry/control breaks; such coincidence does not remove the guide's warning
about the property's native interpolation.

All 67 parse failures remain recorded, rather than being counted as clean
inputs. Their causes are: 37 out-of-range sensor stations, 14 missing engine
block terminators, six distribution column-count mismatches, five numeric-input
errors, two missing beam terminators, two duplicate twist distributions and one
scaling-column mismatch. This audit does not establish whether each rejected
file is invalid in native ASWING or requires a compatibility extension.

No equilibrium is rerun by this audit and no native output check is newly
passed. All 42 main ISAE status rows and the 3% tolerance are preserved.

## Verification

The focused parser, edit/serialization, JSON bridge and new compatibility tests
pass **103/103**. They cover sided values, scaling/reversal, mirror handling,
equal-valued slope breaks, the literal documented property list, high-index
controls, live edits and an actual aerodynamic solve with a compatibility note.
An unknown distribution still fails the normal solve gate.

The initial test run had one incorrect expected mesh in the new test: the
rectangular fixture also contains pre-existing control breaks at `t=±2`.
Correcting that expectation produced the passing run; production mesh behavior
was not changed. [Native test log](../../artifacts/isae/input-break-audit-20261030/tests-final.log).

The [browser workflow](../../tests/browser/input-compatibility.spec.js) also
passes: load a mass-jump model, inspect its note, run the normal aerodynamic
analysis successfully, then reload a smooth model and verify the note clears.
It uses the real browser worker and packaged Pyodide kernel. The first launch
failed because the host lacked `libnspr4.so`; the successful run uses the
existing extracted browser libraries. WebGL initialization failed on this host
and the application used its software viewer fallback; this is not a WebGL
rendering verification. [Browser log](../../artifacts/isae/input-break-audit-20261030/browser-libraries.log).

`npm run build` completes and packages the local browser application.
[Build log](../../artifacts/isae/input-break-audit-20261030/build.log).
