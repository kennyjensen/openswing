# Property point editing — 2026-11-15

## Property selector follow-up

The subsequent cleanup removes both Load property and Remove property from the
panel. Dropdown selections load automatically; custom names load on Enter or
field completion. Undo remains available. The updated interaction suite passes
nine checks / 117 assertions; the obsolete removal check was deleted and the
custom-name check now exercises automatic loading. Browser tests are updated
but remain unexecuted under the hold. No backend removal capability was changed.
Evidence: [control cleanup checks](../../artifacts/property-controls-20261115/checks.json).

The autocomplete input filtered its datalist to the current `chord` text, hiding
the other names from the normal dropdown interaction. A native select now shows
all names supplied by the selected beam's inspection metadata in the first
group, “Defined in file.” Other properties are in a second group; “Other…”
retains entry of arbitrary indexed flap derivatives. Selecting a property loads
it immediately. Changing beams refreshes the list and selects an available
property. No parsing or solver changes were required.

The updated interaction suite passes ten checks / 120 assertions in isolated
V8, including the previous drag, cancellation, auto-apply and Undo checks. Browser
tests use native selection now but remain unexecuted under the existing hold.
Evidence: [selector checks](../../artifacts/property-selector-20261115/checks.json).

## Current interaction: apply when editing finishes

The user's follow-up removes the Preview edit, Preview omission and Apply preview
steps described in the original implementation below. The plot now has an
accessible pencil icon with a 44-pixel touch target. Its connected curve moves
immediately with each point. Releasing a drag, releasing an arrow key, or
completing a table/transform field change validates and applies the edit through
the existing worker and model-inspection path. Remove property is direct; Undo
restores earlier applied edits. Scale/offset/symmetry transformations are consumed
once, and successful dragging retains edit mode. Cancellation restores both the
point and curve without saving. Invalid edits leave the applied source intact
and display an error; stale replies cannot overwrite changed settings or raw
ASW edits. The HTML and SVG touch-action fix is retained.

`web/distribution-spline.js` reproduces the existing natural and Drela spline
policies for the live display only, with mirrored halves, doubled-station jumps,
and extrapolation. The worker remains responsible for validation and serialized
model values. No aerodynamic/structural solver or native interpolation code was
changed. Its independent reference fixture was generated with native
`openswing.asw.Distribution.evaluate`, including left-sided endpoints. The
1,458 samples cover both policies, irregular spacing, mirrored and discontinuous
tables, descending input and extrapolation. Maximum absolute difference scaled
by `1 + abs(reference)` is 5.2467e-15.

Eight interaction checks (96 assertions) and eleven spline checks (26 assertions)
pass in the isolated V8 runtime. Browser drag/touch and property-workflow tests
have been updated but remain unexecuted. Four read-only HTTP checks confirm the
existing server serves the changed modules and stylesheet. A small, single-thread
native fixture-generation process exited normally and was reaped; no solver,
Node, browser or build job was started. ISAE status remains unchanged.

Current evidence: [checks](../../artifacts/property-direct-edit-20261115/checks.json)
and [source hashes](../../artifacts/property-direct-edit-20261115/source-sha256.json).

## Original implementation (superseded interaction)

The property plot now has an Edit toggle for dragging its existing station/value
points. The graft text box, draw/clear controls, tangent checkbox and graft
tolerance are removed from the UI and request builder. Backend graft capability
and its native mathematical tests remain available; this is a workbench change.

Dragging updates the table in place and clears any previous Apply candidate.
The previous checked spline fades until Preview reconstructs the actual curve
through the existing property-editing backend. Apply and Undo retain the existing
source/geometry workflow. Successful previews synchronize the table to the
previewed values and reset consumed scale/offset/symmetry inputs, preventing
repeated transformations when a point is subsequently dragged. Omission previews
disable dragging. Keyboard arrows move focused points; Shift increases the step.
Cancellation or Escape restores the point at the start of that drag. Mirrored
centers and doubled-station jumps retain their station positions, and other
points cannot cross their neighbors.

The user's initial mobile check could highlight points but scrolled instead of
dragging. The fix applies `touch-action: none` to the HTML plot container and SVG
while editing, with pointer capture on the SVG. Scrolling outside the plot is
unchanged; switching Edit off restores ordinary gestures within it. A manual
refresh is needed because development autoreload is disabled.

Seven lightweight checks / 64 assertions pass in the isolated V8 runtime. They
execute the real editor and pointer handlers against a small DOM and RPC fixture,
covering transformed pointer coordinates, draft/table synchronization, no writes
before Apply, Preview/Apply/Undo, one-time scaling, cancellation, keyboard edits,
disabled state, station constraints, failed previews and omission previews. The
HTML ancestor's edit class and touch-action CSS are checked explicitly. The RPC
fixture is workflow evidence, not independent spline validation.

The existing Vite server serves the updated editor, new pointer module and CSS.
The obsolete browser graft tests are replaced by mouse-drag and actual Chromium
touch-injection tests. Those browser tests remain unexecuted under the existing
browser/build hold. Actual mobile gesture behavior after this fix still needs
confirmation. No Node/browser/build/solver process was launched for this change.

Evidence: [checks](../../artifacts/property-point-editor-20261115/checks.json)
and [source hashes](../../artifacts/property-point-editor-20261115/source-sha256.json).
ISAE status fractions and scopes are unchanged.
