# Legacy settings and operating-point evidence

`scripts/fetch-legacy-settings.py` retrieves ten public `.set`/`.pnt` fixtures
into excluded `.reference/legacy-settings-research`. The source manifest records
repository revision, original path, byte length, SHA-256 and Git blob identity;
all three byte checks must pass. The original files are not distributed in the
OpenSwing source or local-app archive. Fetching and verifying all ten fixtures
has passed.

Sources are [WingLoop](https://github.com/LeonardoAVONI/WingLoop/tree/23b3a685bbfd282cda1996011b6a94aad020311a)
and [FBHALE](https://github.com/facebookarchive/FBHALE/tree/b4673025f664a199322f40db7ba159a5fa3e04aa).
Their wrappers use ASWING's PGET/SGET commands; that usage does not establish the
meaning of every numeric field. This is evidence gathering, not a working importer.

The public ASWING user guide describes compile-dependent `NFLPX` and `NENGX`
limits and contiguous parameter arrays. A fixed numeric map inferred from one
file therefore cannot establish general compatibility. The guide's `(column,row)`
operating-grid selectors also must not be assumed to be serialized array indices.

The inspected `.pnt` examples begin with counts `62 119 62`, followed by numeric
index/value arrays and an `F 0` record. The logical flag, signed indices and full
array conventions still require authoritative evidence. Matching a few apparent
speed/angle/control values is insufficient to assign the remaining meanings.
The `.set` fixtures contain additional counts, flags, constraint presets and
node/settings data; their complete layout remains unresolved.

The extended manual distinguishes `.pnt` operating-point definitions from binary
`.state` computed-solution archives. OpenSwing JSON projects, saved equilibria
and physical time checkpoints already exist, but do not establish compatibility
with either legacy format. All of those compatibility requirements remain open.

Additional primary wrappers inspected at pinned revisions:

- `michaelkapteyn/Aswing.py`, revision
  `4c5883db67cb52b97a8706b036e29795a78e064e`: `oper.py`, `params.py` and
  `model.py` write interactive commands and operating-grid selectors. They do
  not decode `.set`/`.pnt` arrays or establish the missing index/flag meanings.
- The MIT-linked `LeonardoAVONI/91_ASWING_Public`, revision
  `9034dfa560e7663f92eec5ce46e3a91d3df4ae0f`, explicitly excludes the ASWING
  source and executable in its installation documentation. Its public tree
  therefore does not provide a reference executable for interchange testing.

Those files and repository trees are cached under excluded `.reference` paths.
No wrapper source has been copied into the numerical implementation. The
computed-result archive in OpenSwing projects is independent of this unresolved
legacy format research.

## Authoritative format limitation and implementation gate

Drela's [official FAQ](https://web.mit.edu/drela/Public/web/aswing/aswing_faq.txt)
confirms that `.pnt` and `.set` are memory-block dumps whose layouts depend on
both the code version and compiled array dimensions. Incompatible layouts are
rejected by ASWING itself; the formats are deliberately absent from the manual.
This is stronger evidence than inferring dimensions from the example counts.
`legacy-point-file-audit.json` pins the retrieved FAQ and the remaining gates.
The full FAQ stays under excluded `.reference` and is not redistributed.

A supported import/export profile therefore needs an identified build and a
verified field/unit map. Matching `62 119 62` does not identify that profile.
The eight observed point files have subsequent token counts 62, 2, 62, 119, 20
and 12; neither the signed indices nor `F 0` nor the trailing arrays has a
verified semantic interpretation. Preserve those observations without imposing
unverified constraints on a model.

The documented feature is an ordered stack of operating-point definitions,
with per-point constraints and specified scalar values, distinct current scalar
values, and common stack settings. It does not serialize computed beam states.
A codec must preserve those distinctions and reject unmapped active fields
before modifying browser state. Completion requires verified bidirectional
PSAV/PGET interchange for each supported profile and offline browser import,
selection/editing, export and rollback checks. The present JSON projects and
saved physical states remain useful independent features; a legacy codec is
still unimplemented.
