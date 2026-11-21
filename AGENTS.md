# ISAE progress tracking

After changing any completion fraction or tracked comparison scope in
`docs/validation/ISAE_STATUS.md`, run `npm run isae:progress -- --reason "Brief description"`.
This records the current UTC observation and regenerates `public/isae-progress/`.
Run `npm run isae:progress:check` before finishing a status update.

Do not backdate observations or rewrite prior progress events. Keep unavailable
reference values in their declared denominators. The scope selection file is
`docs/validation/isae-progress-scopes.json`: update it explicitly if the table
adds independent scopes or changes which fraction is primary. Do not combine
alternative model settings or computed-only subsets with their parent totals.

Use small serial validation jobs with one BLAS thread. Do not start background
solver jobs or multiple agents for progress tracking. The Vite development
watcher already regenerates plots on status edits; no separate watcher needs
to be started by the coding agent.

# Authoritative ASWING and AVL references

Store downloaded reference material in the visible `reference/` directory.
The `.reference` symlink exists only to preserve older scripts and evidence
paths; use `reference/` in new documentation and downloads.

Treat Romain Jan's **Experimental validation of ASWING**, Parts I–IV, as
authoritative primary references for ISAE case setup, documented ASWING results,
model modifications and limitations, as requested by the user. Consult the
[reference index](docs/validation/aswing-authoritative-references.md) and its
checksummed source catalog before investigating a case or changing its setup.
The index also includes Drela's steady/unsteady technical descriptions, the
extended user manual and the related ICAS validation paper.

Treat Drela and Youngren's AVL documentation, source and native results as
authoritative references too, as requested by the user. Establish matching
geometry, discretization, operating conditions and force conventions before
comparing solvers. If OpenSwing agrees with native AVL under those conditions
but disagrees with an ISAE ASWING result, prioritize auditing the test setup
and ASW-to-AVL conversion. In particular, check normal versus streamwise
chord, sweep breaks, incidence and zero-lift angle, physical components,
reference dimensions, wake direction, compressibility and profile drag.
Agreement on simplified controls supports this investigation but does not
validate an untested ISAE geometry or establish every ASWING-specific feature.

Keep original ASWING, ISAE-modified ASWING and experimental curves distinct.
Use the documented version and settings for each comparison; do not silently
substitute another lifting-line method or fit parameters to make a case pass.
Reconcile conflicts between reports, theory, scripts and archived output
explicitly, with page/equation references. A report's stated limitation is
evidence to account for, not permission to discard an existing comparison.
