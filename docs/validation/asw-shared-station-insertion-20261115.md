# Shared ASW station insertion

Adding one station in Beam Properties now adds a row to the property's original
ASW table. For Daedalus's `t chord y Ccg` table, the chord editor's `+` therefore
adds the same station to chord, y and Ccg. Selecting either companion property
loads the added station from the updated source. Independent tables keep their
own grids.

The selected property's new value comes from the editor. Companion values are
sampled from their existing distributions at the new station, using the model's
interpolation policy, or its extrapolation outside the original range. Existing
values are retained. This samples each companion curve at the added knot; it
does not promise that rebuilding every interpolation policy with that extra
knot preserves the entire curve between stations.

The source writer recognizes a single inserted point with all old points
unchanged. It inserts exactly one numeric line, retaining the header, existing
rows, comments and line endings. It encodes new values under the scaling active
at that position, including negative station scales and shortened directives.
If those coefficients cannot represent a new value to floating-point accuracy,
the edit is rejected. Original models are never mutated by the operation.

Shared distributions are rebuilt and included in the complete model-signature
check after reparsing the saved source. Broader independent grid replacements
retain the existing separate-table behavior. Value-only edits and Undo retain
their existing paths.

Validation uses small serial native Python batches with one BLAS thread and
per-process limits of 15 CPU seconds, 55 wall seconds and 768 MiB address space.
The new checks cover both interpolation policies, LF/CRLF, ascending/descending
tables, insertion before/between/after existing stations, varying scale/offset
directives, zero and negative coefficients, preservation of original rows and
comments, and the real Daedalus editor bridge with chord/y/Ccg selection.

The evidence record contains the executed test results and served-source checks:
[checks.json](../../artifacts/asw-shared-station-insertion-20261115/checks.json).
Browser/build jobs remain on hold; no solver was run. ISAE completion fractions
and comparison scopes are unchanged.
