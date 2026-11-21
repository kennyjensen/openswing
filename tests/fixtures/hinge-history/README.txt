Pinned fixtures for generic hinge regression controls

source/dead-couple.asw is a grounded rigid two-link spring with the analytic
law q[deg]=M[Nm]. source/rigid-hinge-release.asw supplies the inertial hinge
history control. These manufactured controls are not FFWT experiments.

history/owned-v2-release-400-0.35-0.02-order2.json preserves the recorded
owned-history trajectory and its original refinement-required status.
It is used to check checkpoint/history identity and rejection of whole-turn
record edits, not to declare time-discretization accuracy.

legacy/ preserves two original version1 equilibrium packets at +400 and
-720 degrees. Tests must recover the spring branch from the original
loads/law, without fitting the target state or geometric rotation.

rank/ contains four saved finite-spring matrix controls and their paired
explicitly released-hinge matrices. Tests preserve the1e-10 rank gate,
require two released modes to remain detectable, and verify that row/column
equilibration does not alter the original matrix or hide dependent rows.
These are recorded matrix controls, not a generic proof that noisy finite
differences distinguish every weak spring from a released mechanism.

All13 data files are byte-identical to frozen integrated04 inputs. Exact
source-to-release mappings and hashes are in provenance.json. No fixture
contains a /tmp or /home path; all data access is local to this directory.
