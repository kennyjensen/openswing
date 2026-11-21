# VibeLattice editor palette

Implemented 2026-10-10. The live [VibeLattice stylesheet](https://avl.vibefoil.com/js/dist/styles.css)
matched the local reference byte for byte (SHA-256
`76bad65ce45ca24f03f4699757a1ea92ecafe2175e4e152378aa79cc8103ee15`).
OpenSwing uses background `#0f1115`, text/caret `#f8f8f2`, keywords
`#f92672`, numbers `#ae81ff`, strings `#e6db74` and comments `#75715e`.
The vocabulary follows ASW blocks, fields and control derivatives, including
Fortran-style numbers. Escaped highlighting overlays the existing native
textarea, retaining selection, editing, resize and source export behavior.

One actual production browser workflow passed in 61.040 seconds (terminal
exit 0). Computed colors matched on desktop at 1440 pixels and mobile at
390 and 320 pixels. Native typing, dirty state, Apply and exact ASW download
bytes passed. Selection remained readable, and resizing and horizontal/vertical
scrolling preserved alignment. The same textarea and source survived mobile
tab changes and desktop restoration. No page errors occurred. Both saved
screenshots were inspected.

All 306 file pins, 55 host dependency pins and 61 served files remained
unchanged during verification. The evidence includes the exact UI sources,
reference stylesheet, test, output and screenshots. See [the machine-readable
record](editor-theme.json) and [evidence archive](editor-theme-evidence.zip).
This workflow verifies the editor; it did not run a numerical solve or establish
exhaustive token coverage. Earlier numerical and mobile-layout workflows retain
their original source fingerprints.
