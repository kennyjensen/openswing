# AP-2 original reference catalog

The [machine catalog](isae-ap2-reference.json) retains all **117 stored MAT ratio
cells**, four directly paired endpoint CL/CD tokens, and six coefficient tokens
from three unpaired TXT exports. This is source extraction and a declared input
reconstruction; no solver runs or numerical validation are performed here.

The planned two-mesh scope contains **237 jobs and 248 scalar slots**: 234 jobs
compare 117 ratios on 150/300 intervals, with eight additional endpoint coefficient
slots; three blocked TXT jobs retain six further slots. Repeated mesh targets and
algebraically dependent endpoint ratios are not independent validations.

| Series | Original model | Alpha | MAT shape | Cdp |
|---|---|---:|---:|---:|
| APROPOS1 | APROPOS1.asw | 1.05° | 4×13 | 0.0045 |
| APROPOS4 | APROPOS.asw | 4.2° | 5×13 | 0.005 |

The original source directory is pinned at ISAE revision
`f62943df20e9e4d7d9f50e070477b22426b5f865`, under `2 - Propellers/AP - Aero
Propulsive Cases - Propeller Wing Interaction/AP-2 - Propeller lateral and
vertical position on the wing lift to drag ratio`.

`AP2_Jet_Wing_interaction.m` lines 19–36 and 88–107 declare the vertical grids,
axial coordinate and nested producer loops. Every MAT `y_p` coordinate exactly
equals the corresponding experimental CSV first X-column times 0.64. Those
coordinates are independently specified inputs; experimental CL/CD ordinates
are not used. `change_ppropeller_position.m` lines 9–10 and 13–23 changes only the
two Engine rows. Generated variants preserve every non-Engine byte and original
line ending. Five-significant-digit coordinate tokens match both retained
endpoint models; intermediate files are explicitly reconstructions. Endpoint
requests use the complete original model bytes unchanged.

Both `.sh` drivers lines 8–24 declare NODE I150, V=50, shared engine power 1=330,
the incidence, selectors 74/75 and the CSV destination. The four-column exports
label CL and CD directly. The commented MATLAB `Var11/Var17` expressions at
lines 33/102 conflict with the retained columns. A stale output selection is a
plausible explanation, not established producer history. This conflict does not
erase the direct shell/export pairing or explicit coordinate/mutator recipe.

The final CSV ratios exactly equal the final MAT cells. APROPOS4's ratio also
occurs in the opposite-z first row; its positive saved z and final grid position
are necessary pairing evidence. APROPOS1_temp.txt happens to reproduce MAT
row 1, column 6 as a ratio, but selecting input coordinates from that coincidence
would be output-derived pairing. All three TXT files remain unpaired.

Every MAT double retains its native `float.hex()` value. Tolerance 0 is an exact
stored-value identity diagnostic, **not recovered ASWING printed precision**.
The two CSV endpoints retain their own decimal coefficient tokens and original
half-last-place bounds (CL 5e-7, CD 5e-8). Endpoint ratio intervals are propagated
from those bounds and stored separately. They are not assigned to other MAT
cells, and no lost CL/CD columns are inferred from ratios. Aerodynamic CL/CD
must remain distinct from net engine force.

Original startup state, atmosphere/PG/KF, influence-update policy, executable
identity and exact historical node arrays remain unresolved. The 300-interval
mesh is a declared current refinement. No complete-family validation is claimed.

Regenerate and check without running physics:

```sh
.venv/bin/python scripts/extract-isae-ap2-reference.py
.venv/bin/python scripts/extract-isae-ap2-reference.py --check
```
