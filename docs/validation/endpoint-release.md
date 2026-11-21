# Exact endpoint repair: browser verification

The actual built application now accepts closed bodies whose prescribed terminal radius is exactly zero. Cubic roundoff previously produced a tiny negative value at some terminal knots and rejected otherwise valid display geometry. Exact terminal queries now use the stored value; nearby interpolated values and derivative orders one through three are unchanged.

The original candidate regression completed 2,989 test cases: 2,965 passed, and 24 failed on outdated test setup that also failed on the baseline. All 24 failures map to 36 subsequently passing repaired checks. Physical accuracy and matrix/residual comparison limits were retained. The original full-run wrapper returned143 when reaped after the detached process completed; complete JUnit and pytest summaries are preserved rather than claiming a clean original exit. The final36-check process exited successfully.

The actual served build, without routing in a candidate file, passes21 offline solve/export comparisons:16 SA-13 body states and5 SA-14 states spanning all four original inputs. Both genuinely negative-radius controls still reject. This also checks recovery from invalid input and the mobile Plots view.

The largest coefficient difference from the pinned native references is 7.10543e-15; the largest strip-force difference is 9.66338e-13 in the applicable input units. These checks establish numerical execution consistency, not experimental agreement.

The completed SA-14 consolidation records15 partial families and26 pending in the source coverage ledger. The earlier SA-12 release contained13/28. Historical numerical studies keep their original solver hashes through the explicit source-transition record; they are not relabelled as fresh calculations on the repaired parser.

- [Source boundary and current display checks](endpoint-source-transition.json)
- [Full regression failure accounting](endpoint-regression-acceptance.json)
- [Original full JUnit](endpoint-regression-full.xml) and [repaired-check JUnit](endpoint-regression-repaired.xml)
- [Actual offline browser results](endpoint-release-browser.json)
- [Remaining physical-validation work](isae-coverage.md)

All40 broad ASWING requirements remain Partial. The swept force-velocity limit, high-angle discrepancies and missing feature/format/reference validation remain unfinished.
