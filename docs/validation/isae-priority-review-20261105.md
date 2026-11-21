# ISAE comparison priorities

Reviewed 2026-11-05. The [complete status table](ISAE_STATUS.md) retains
all 42 rows and their previous scores. This review adds no numerical run or
archived-ASWING pass. The preceding development batch completed source steady
derivatives; this turn reviews validation priorities against the current files.

Recent source trim, controller, derivative and browser work improves supported
workflows and implementation evidence. Strict registered scores have not
increased; the linked AE-1/AE-2 follow-ups improve conditional reference agreement.
Independent equations, mesh convergence, Python/browser parity and
matching a historical ASWING calculation answer different questions.

| Scope | Evidence that matters for choosing the next work |
| --- | --- |
| SA | SA-3 passes 308/308 registered comparisons at the user-approved 3% tolerance. SA-1 is 146/154, with remaining high-incidence induced drag discrepancies. Other families retain geometry, drag, setup and unavailable-output issues. |
| UA-1 / UA-2 | Extensive independent equation and time-refinement checks pass. UA-2 has 30/30 harmonic matrix checks, but its 222 native comparison slots remain unverified. More repetitions of those passing equation checks would not supply missing historical provenance. |
| ST-2 | A forty-node uniform still-air interpretation gives median frequency error 0.002322%, maximum 0.012611%, across fourteen frequencies. Historical mesh/setup is unconfirmed; the strict registered score remains 0/490. |
| ST-3 | 930/1,080 static matches and 8/9 conditional modal frequencies. The outstanding modal frequency differs by 2.659%; an independent beam calculation supports the implemented result for the declared inputs. |
| ST-4 | Static divergence agrees with an independent reference within 0.001111%, but significant native modal disagreements remain. One sensitive independent slow-pole comparison still fails at 1.31931%. |
| ST-5 | All 224 final static mesh comparisons pass across sixteen snapshots. These are convergence checks, not native-reference matches. Typical failed native deformation/load comparisons remain fractions of a percent, often about 0.2–1%. |
| ST-6 | Analytical buckling and bent-column supplements are useful implementation tests, but the archive has no paired native model/output. Further synthetic variants cannot establish native ST-6 agreement. |

The next recommended focus is the existing coupled static aeroelastic cases,
AE-1 and AE-2, retaining ST-3/ST-5 as structural regressions. Both adapters already
select `drela-steady-coupled-v1` and Drela spline interpolation. Merely selecting
source equations is therefore not a new correction. Start with a few original
states under the current source, then investigate documented setup, sensor
definitions and continuation before repeating whole sweeps. Preserve all
original targets and gates; do not select a branch or mesh by closeness alone.

The [AE-1 baseline](isae-suite-ae1-20261027.md) shows why it is informative:
at alpha 5 degrees and the final 56 m/s command, sensor-3 deflection is 10.90%
low and elevation 7.17% low. These endpoint errors are much larger than the
reported mesh change. The [AE-2 baseline](isae-suite-st5-ae2-20261027.md) retains
a negative-coupling branch discrepancy at 17–19 m/s and failed cold solves at
20 m/s. Its historical continuation correspondence is unresolved.

Follow-up on 2026-11-05: the [explicit AE-1 frozen-influence scope](isae-ae1-frozen-scope-20261105.md)
now checks every native sensor channel at two endpoints on two meshes, using
literal input bytes. All 24 computed outputs differ by less than 0.275%, versus
10.90% tip-Z error at the freshly verified updated-influence 5° endpoint.
This confirms the [earlier conditional full-curve finding](isae-ae1-literal-frozen-curves.md),
which should be considered alongside the baseline when prioritizing work.
The historical K/F flag remains unknown and strict matches do not increase.
The default remains unchanged; repeating the same AE-1 flag sweep is not a
priority.

The [AE-2 continuation follow-up](isae-ae2-continuation-20261105.md) now reproduces
the positive branch at 18–20 m/s on both meshes, using a full-load 20 m/s solve
and descending continuation. All four native channels differ by at most 2.724%,
with mesh changes below 0.020%. Ascending continuation reaches different,
negative equilibria at 18–19 m/s. Both descending solves fail at 17 m/s; the fine
cold 17 m/s control times out. A real warm-start wall-root derivative bug is
fixed and verified in the browser. Strict scores and historical setup claims
remain unchanged. The next bounded static investigation is the positive branch
near 17 m/s, not another full repetition of the passing 18–20 m/s comparisons.

The [near-17 follow-up](wall-root-custom-trim-20261105.md) retains a coarse
17.75 m/s line-search failure and a fine-mesh memory failure. A sensor-coordinate
trace exposed and fixed the ordinary custom-trim wall-root derivative path;
47 Python tests and the browser comparison pass. One coarse point at
17.9234 m/s is valid but unrefined; the finer sensor case was stopped without an
accepted result in that study. The [selective-sensor optimization](selective-custom-sensors-20261105.md)
now preserves all 6,269 coarse full-solve values while reducing its observed
time from 103.6 to 26.8 s. The nominal40 coordinate case also completes in
51.3 s, with observed output changes up to 0.171%; this is not a new native
comparison or a completed refinement study. All 63 Python tests and the offline
browser comparison pass. Full tangent checks are retained. Further branch
refinement remains separate from expanding flutter coverage.

After these static checks, expand to AE-4/AE-5 flutter with verified original
model/driver/output pairing. The [first AE-4 wall-enabled anchor](isae-ae4-wall-modes-20261105.md)
now computes three positive roots with frequency errors 0.0032–0.0616% and
damping-component errors 0.0686–0.5043% at declared IAS40/native index41.
The original `NN 4`, complex shift `0 200` and solid-wall image are retained.
Historical defaults and the script/output index discrepancy are unresolved;
this conditional anchor adds no native pass or flutter-boundary validation.
The family comparison adapters are still missing. The table
currently lists twelve unregistered families: P-2 through P-5, AE-4 through
AE-7, and FFWT-2 through FFWT-5. This count is read from the current ledger;
older backlog counts describe earlier snapshots.

The matrix-reuse inspection also found that steady derivatives release trim
rows and use a different stencil from the Newton solve. Directly reusing the
last Newton matrix would need explicit state, row and differentiation checks.
The analytical circulation block currently retains duplicate numerical probes;
that optimization remains investigated but unimplemented. No production file,
solver tolerance or model setting changed in this review.

Evidence and the previous status introduction are retained under
`artifacts/isae/priority-review-20261105/`. Distribution archives were not rebuilt
for this documentation-only review.
