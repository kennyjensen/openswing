# ST-5 static gravity reporting: deferred verification

Focus moved to AE-1 on 2026-11-10 at the user's request. The accepted ST-5 mechanics score remains 16,687/16,688; no new native passes are claimed.

`openswing/source_recovery.py` now exposes the distributed gravity force per undeformed material length, projected on the physical midpoint normal, for the two static source policies. This extends reporting without changing residual or constitutive equations. Other policies leave the quantity unavailable. Point weights and support reactions remain separate. The plot selector and CSV source were extended; endpoint CSV rows do not inherit an interval load.

All 14 analytical/output tests pass, including signed distributed weights, custom gravity, rotations, unsupported policies and two small fresh static solutions. A broader damping-output check passed four tests and failed one: its manufactured modal fixture lacks `system.base`, now required by the wall-root wrapper before the output stencil. That failure has not yet been adjudicated. The exact failure is retained in the JUnit file.

The planned all-sixteen saved-data production replay and fresh ST-5 parity solve were not started after the user changed focus. Three JavaScript tests are written but unexecuted; browser/build verification remains held. Existing historical kernel-pinned audits retain their original identities and may reject the changed recovery file. No claim is made that every production module is unchanged or that the downloadable build contains this feature.

Evidence: [deferred receipt](../../artifacts/isae/st5-static-gravity-20261110/deferred.json), [14 passing tests](../../artifacts/isae/st5-static-gravity-20261110/analytic-tests.xml), [broader check including failure](../../artifacts/isae/st5-static-gravity-20261110/damping-tests.xml). The prior [independent normal-load audit](isae-st5-reaction-display-20261110.md) remains valid saved evidence; it is not a verification run of this new production field.
