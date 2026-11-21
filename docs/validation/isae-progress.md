# Timestamped ISAE progress

Open **ISAE progress** in the workbench header, or visit
`http://localhost:8085/isae-progress/` when your server uses port 8085.
The dashboard shows an overall plot, one plot for every actual ISAE case,
family filters, a UTC change log, and downloadable PNG/SVG/CSV/JSON files.
The static dashboard also opens directly from `public/isae-progress/index.html`.

`ISAE_STATUS.md` remains the status source. Each change to a tracked pass count,
denominator, scope or acceptance threshold records a new UTC observation and
regenerates the plots. A prose-only edit does not create a duplicate observation.
The first snapshot is the current status at the time tracking was introduced;
earlier results are not backdated. Initially the curves have one real point.

The development server watches the status and scope files and updates the
dashboard automatically. Restart an already-running server once to load this
new watcher. For updates when the server is stopped, run:

```sh
npm run isae:progress -- --reason "FFWT-4 initial comparison added"
```

To keep automatic updates running without the web server:

```sh
npm run isae:progress:watch
```

The standalone watcher polls file metadata once per second and runs no solver.
The development watcher reuses Vite's file watcher. Updates are serialized and
locked across processes. Do not start a second watcher if Vite is already
running. Both build commands refresh progress before packaging. Matplotlib is
needed to generate plots (`.venv/bin/pip install -e '.[plots]'` if absent).

After a status update, `npm run isae:progress:check` verifies that the history
and generated plots match the current fractions. Repository instructions also
require this update/check workflow for future coding-agent changes.

## What the percentages mean

- **All 41 cases, equal weight:** mean of the tracked case percentages. Cases
  without native targets or without a registered denominator contribute zero.
- **Known checks, pooled:** total passing scalar comparisons divided by total
  required scalar comparisons with known counts. Unknown denominators are
  excluded from this second metric and their case count is displayed.
- **Per case:** the declared native-comparison scope selected in
  `isae-progress-scopes.json`. Missing outputs stay in its denominator.

SA-9 is absent upstream and excluded. UA-1 and ST-6 have supplemental analytical
checks but no authenticated native denominator; they are marked unscored here.
ST-5 combines its four distinct static scopes. Smaller conditional studies,
alternative initializations, repeated mesh comparisons and historical versions
are not silently merged with their parent totals. The selected scopes are
shown below the charts. Counts may include mesh repeats, as in the status table.

The default comparison allowance is 5%. Several saved rows still use their
explicitly labeled historical thresholds; this tool does not rescore predictions.
Changing a threshold or scope is recorded even if the fraction is unchanged.
A lower percentage can reflect newly added required checks. Passing 100% of a
tracked comparison scope does not establish complete physical validation.

The append-only event sequence is stored in
`docs/validation/isae-progress/history.json`. Each event includes the source
and scope-file hashes, all counts, changes from the preceding event, and a
hash linking the history. Writes are atomic; an interrupted plot generation
is retried on the next update without adding another event. Full history is
exported in `public/isae-progress/data.json` and `history.csv`.

Verification on 2026-11-06: 12 Python tracking/coverage checks, one development
watcher test, and 14 real Chromium checks pass. The browser checks cover all
41 charts, desktop/mobile layout, family filtering, refresh, CSV download and
unchanged history on page open. No external requests or solver runs occur.
Screenshots and the browser report are retained in
`artifacts/isae/progress-dashboard-20261106/final/`.
