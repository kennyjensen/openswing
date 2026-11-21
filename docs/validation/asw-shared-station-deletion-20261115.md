# Shared ASW station deletion

Deleting a station in Beam Properties now removes that row from every property
in its original ASW table. The other rows and independent tables retain their
values and source formatting. A deleted row's inline comment stays in place as
a standalone comment.

The trash button passes the original row index so doubled stations are
unambiguous, including identical chord entries with different Ccg values.
Descending source tables map the editor's ascending row index back to the
correct source line. The saved model is reparsed and checked against the
expected distributions. Invalid row indices, changes to other rows, or an
invalid remaining grid reject the operation without changing the original
model. Undo restores the source through the existing editor history.

Validation: 42 distinct native checks pass in small serial batches with one
BLAS thread, 15 CPU seconds, 55 wall seconds and a 768 MiB address-space limit.
These cover scaled tables, both interpolation policies, ascending/descending
source, first/middle/last row deletion, comments, doubled stations and the
Daedalus insertion/deletion round trip. An initial endpoint fixture placed a
sensor outside the shortened beam and was correctly rejected; its sensors now
use the retained middle station for the valid-deletion comparisons.

The lightweight editor interaction suite also passes 10 checks / 136 assertions,
including trash-button transport and Undo for doubled stations. It runs with a
DOM/RPC fixture in the isolated JavaScript tool runtime. No Node, browser, build
or solver job was started. Browser checks remain on hold; ISAE completion
fractions and comparison scopes are unchanged.

Evidence: [checks.json](../../artifacts/asw-shared-station-deletion-20261115/checks.json).
