# ASW comments after property edits

The property editor used the general normalized serializer after every change.
That serializer deliberately gathered comments into a preamble and expanded
every beam into separate property tables. It is still available for explicit
canonical export; ordinary property edits now use a local source writer.

Value edits preserve the original shared station table and change only the
affected value column, normalizing that column's scaling when needed. Station
tokens, other properties, comments, blank lines, line endings and unrelated
blocks remain intact. If a shared table's edited property needs a new station
grid, only that column is split into a separate adjacent table. Single-property
row edits preserve annotations by station; deleted-row inline notes become
standalone notes at the same column. Inserted rows precede notes belonging to
the following existing row, including when a station is prepended.

The existing exact Weight-station alias rule is retained through local station
column edits rather than canonicalizing the whole file. After serialization,
the source is reparsed and its complete model-data signature must match the
intended edited model. An unexpected semantic change rejects the edit. Original
models remain untouched when an edit fails. No aerodynamic or structural
equations were changed.

Validation passed 25 distinct native test cases in small serial batches:

- Five checks for exact value-token edits under both interpolation policies and
  LF/CRLF line endings, plus shared scaled-column behavior.
- Four checks for independent grids, insertion/deletion, descending tables and
  property addition/removal. The insertion/deletion case was checked again after
  adding a prepended-station assertion.
- Three actual bridge edits of the Drela `dae`, `usa` and `fw` examples. Every
  original comment stays on its original line for these value edits.
- Thirteen existing invalid-edit, control, spline-report, unknown-content and
  attachment-equivalence regressions.

An initial combined run reached its 25-second wall limit; successful jobs were
split into batches with one BLAS thread, 10–15 CPU seconds, 45–55 wall seconds
and a 768 MiB address-space limit. All jobs exited or were reaped. No solver,
browser, Node or build job was started. Browser regression expectations now
require the original commented source with just the edited stiffness values;
those browser checks remain unexecuted under the existing testing hold.

The development server serves the new writer and updated editor backend, and
its kernel manifest includes the new module. Refresh the app to load them.
ISAE status fractions and comparison scope are unchanged.

Evidence: [verification record](../../artifacts/asw-comment-preservation-20261115/checks.json).
