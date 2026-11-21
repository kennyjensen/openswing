# Mobile startup repair after the UI cleanup

The user reported:

> Cannot read properties of null (reading 'id')

`createResponsiveWorkbench` moved a `.scope-note` element and two validation-link
elements into mobile panels. The prior UI cleanup removed those elements from
`web/main.js` but left the moves in `web/responsive-workbench.js`. At widths up to
720px, `move(null, destination)` attempted to read `node.id` while creating its
desktop-position anchor and aborted startup.

The obsolete moves are now removed. Required model/settings/geometry/result
panels and the four workspace tabs still move using their original anchors.
The fix does not hide errors from missing required UI elements with a blanket
null guard.

`tests/responsive-workbench.test.mjs` uses a lightweight DOM to execute the actual
layout controller, without starting a browser or numerical kernel. Its main
layout fixture derives the detail tabs and presence of the deleted elements from
the current `web/main.js`. Three bodies / 217 assertions pass:

- Mobile startup without scope or validation-link nodes.
- Three full desktop/mobile resize cycles, preserving node identity and restoring
  every pane to its original desktop location.
- Main and detail tab selection, including leaving the plots workspace.

Restoring the old scope-note move in an isolated negative check reproduces the
user's exact exception. The existing development server returns the corrected
module over HTTP; its executable code contains none of the three removed-element
references. Full browser rendering remains unverified under the UserLAnd test
hold. No Node, browser, Vite startup, build or solver job was run. No physics,
ISAE fractions or saved numerical inputs changed. Manually reload the app.

The broader flight-condition metadata review was interrupted by this report and
has made no production changes. The full ASWING-equivalence goal remains open.
