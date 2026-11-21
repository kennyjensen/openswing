# SA-1: current evidence boundary

**SA-1 remains incomplete at 19/154 registered archived-output checks.** All
22 baseline jobs finish. The broader OpenSwing goal is also incomplete.

The [finer-mesh study](sa1-mesh-limit-followup-20261027.md) and
[initialization study](sa1-alpha-continuation-followup-20261027.md) narrowed the
discrepancy without establishing a correction. Two independent follow-up
reviews found no remaining concrete implementation change justified by the
examined sources that would resolve SA-1. This is an evidence limit, not proof
that the implementation is free of defects or equivalent to ASWING.

The same missing historical information remained unresolved in the last three
consecutive goal turns: the angle-sequence review, the finer-mesh review, and
this source audit. The first two produced useful numerical evidence; this pass
found no further justified numerical action. Because the user has prioritized
SA-1 until it fully passes, work on other case families does not remove this
blocker.

| Missing discriminator | Why it matters |
|---|---|
| Actual computational nodes and circulation representation/count | The driver requests nodes but does not retain their final allocation or Fourier count. |
| Circulation sampling and discrete load recovery | Published conservative balances do not uniquely identify the archived executable's mapping to integrated loads. |
| Executable build and startup settings | The actual PG/F state and compiled constants are not authenticated by a banner, saved settings or implementation. |

The native table contains no executable version or computation date. The driver
path `AswingMAC_12_02_21` has no documented date interpretation, so it cannot
establish a contradiction with the recorded 5.96 release date. The longitudinal
output columns also do not contain the lateral quantities added in that release.
The public history preserves the same model and table bytes; it supplies no
new setup evidence.

The ISAE aerodynamics report, p18, explicitly states stall factor 40 and width
0.05 in its model description, consistent with the implemented values. This
corroborates the documented choice; it does not authenticate the producing
binary. The report's SA-1 setup elsewhere differs from the retained model, as
recorded in the [paper/history review](sa1-history-followup-20261027.md).

A bounded public check also found a
[2026 conference listing](https://icas2026.dglr.de/icas2026/sessionlist-thu.html)
for an ASWING stall extension. The author's
[project description](https://leonardoavoni.com/project-stall.html) describes an
extension for flexible-aircraft stall and does not provide the historical SA-1
settings or detailed implementation needed here. A title and research overview
cannot establish a replacement rule for the archived baseline. The examined
pages are retained in the [retrieval receipt](../../.reference/sa1-evidence-boundary-20261027/receipt.json).

Further progress toward exact archived parity requires new discriminating
reference evidence, such as a native trace with settings, nodes and circulation,
or an authenticated description of the relevant discrete implementation.
The existing [reference-capture kit](isae-sa1-reference-capture.md) is prepared
for such evidence. No executable or additional settings are available from the
user, and no further request for them was made.

No numerical solve, parameter change, production edit, tolerance change or
acceptance-scope change was made in this pass. The completed diagnostics remain
available; repeating the same mesh or initialization studies is not the next
action.
