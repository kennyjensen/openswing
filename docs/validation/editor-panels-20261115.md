# Editor panels — 2026-11-15

The Editor tab now contains File, ASW Editor, Beam Properties and Beam Nodes in
that order. All four use native `details`/`summary` disclosures. File and ASW
Editor start open; Beam Properties and Beam Nodes start collapsed. Desktop and
mobile share these same elements, so resizing preserves drafts and disclosure
states. The desktop's separate property/node tabs are consolidated into Editor;
the mobile Editor, Settings, Plots and Output tabs remain.

File contains Load and Save, the existing Drela example selector (Daedalus,
ultralight sailplane and flying wing), vehicle name, beam and panel counts,
Sref/Cref/Bref and moment reference with length units, then surface/beam names.
Daedalus remains the default. The ASW editor, highlighting and Apply edits action
are unchanged.

Project/saved-case UI, its startup/refresh hooks and input-compatibility UI are
removed. Internal configuration capture remains available to steady-flight trim
and result handling. Property/node controls remain available with shorter status
text and without the long instructional paragraphs.

Validation used the existing lightweight JavaScript runner in the isolated V8
tool runtime: 28 checks / 538 assertions pass across responsive layout (including
mobile startup and repeated resizing with drafts), aircraft loading, steady
flight and Daedalus request construction. The evaluated Editor markup has
balanced elements, unique IDs, four disclosures and the correct control parents.
The existing Vite server returned HTTP 200 for the five changed UI modules/styles.
No browser, local Node, build or solver job was started for this change; visual
browser verification remains open under the existing hold. Manually refresh the
app to load the updated UI.

Evidence: [check receipt](../../artifacts/editor-panels-20261115/checks.json),
[source hashes](../../artifacts/editor-panels-20261115/source-sha256.json), and
[evaluated Editor markup](../../artifacts/editor-panels-20261115/editor-fragment.html).
ISAE completion fractions and scopes are unchanged.
