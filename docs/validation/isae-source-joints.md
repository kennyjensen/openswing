# Source-discrete joint support

2026-10-26. Acceptance remains reproduction of tested ASWING outputs with
the original models and operating settings. Experimental agreement is optional.
This increment adds missing joint support; it does not claim a new archived
ASWING reference pass.

All three opt-in source operators now accept Ground types 0/1/2 and Joint
types 0/1/2/3. They reuse the established joint kinematics and conservative
reaction transfer. Previously supported rigid-joint cases retain their
equations, policy identities and saved-state formats. The browser default
remains the midpoint formulation.

The joint pylon rotates with beam 1. A pin transmits force without a beam-2
couple; a roller transmits couple without constraining relative translation.
A sprung joint evaluates Jangle using the beam-1 structural moment, including
the relevant distributed endpoint couple. This is generally different from
the free-end reaction couple. Aerodynamic circulation derivatives include
their contribution to this moment. These definitions follow the
[ASWING theory](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
Eqs. 190–199 and the joint wrench equations.

Jangle retains its existing natural cubic interpolation and sided slope breaks.
Version-2 saved states preserve hinge winding. Each source beam still requires
a nonsingular, uncut Euler chart; a hinge winding state does not remove that
restriction. Historical spline endpoint and interior-joint trace conventions
remain unproved. Equilibrium convergence alone does not establish stability.

## Verification

The 36 focused tests pass, covering off-axis ground/joint constraints and
reaction balance, finite rotations, source gravity/aero endpoint moments,
the direct circulation derivative and saved hinge charts. They include an
analytic 30° rigid-link solution and a small mounted flexible-joint solve.
An isolated pinned mechanism is correctly rejected. Forty existing source
regressions and 30 JavaScript checks also pass.

The existing `articulated.asw` example is used unchanged for the integration
checks: 12 cosine intervals per beam, structural gravity −9.80665 m/s², and
a separate free-air mounted case at 30 m/s, 5° incidence and density
1.225 kg/m³. Native cold solves take 1.44 and 3.39 seconds on this host.
Fresh full residuals are 8.01×10⁻¹⁵ and 1.94×10⁻¹⁴. These are implementation
fixtures, not ISAE reference models. The final native integration passes
107/107 checks, including four prior-policy restorations. An independent
saved-field audit passes 414/414 checks, reconstructing endpoint moments,
finite hinge rotations and aerodynamic load transfer. The machine-readable report records
restoration, offline browser parity and release checks with their exact inputs.

The two offline browser solves take 3.25/9.41 s after 25.38 s startup. All
18,658 compared numerical values agree with native execution; the maximum
absolute difference is 8.51×10⁻¹². Both hinge reports and curvature plots are
checked, new projects restore byte-for-byte, and all four older policy projects
restore their saved results. The execution counter alone is excluded from
physical parity. Checked projects are available for
[structural equilibrium](../../examples/articulated-source-structural-project.json)
and [mounted equilibrium](../../examples/articulated-source-mounted-project.json).

The initial integration harness incorrectly required equal signed mirror
angles; the common +x axes require opposite angles. It also required exact
cross-runtime mesh coordinates, exceeding the existing eight-epsilon identity
contract. Both harness defects and their outputs are retained. The two solved
physical states are reused; no replacement cold solve was needed. The mounted
fixture explicitly disables the wall setting inherited from the AE-2 project
template before its first solve.

The first browser attempt rejected inherited trim-control selections while
loading the test project, before any solve. The corrected project clears those
selections and explicitly selects the same structural gravity as the native
request. Neither the model nor either native solved state changes.
The second attempt completed both solves and the UI checks before its final
harness assertion compared an undefined JavaScript property with its omitted
JSON form. Saved-only completion checks use the worker's actual JSON boundary.
No additional browser run or solve is used to close that assertion.

## Archived-case follow-up

The original-file inventory identifies standard sprung joints in the FFWT
folding-wing models. At this joint-integration stage, the selected FFWT-1
Flare10 model was not yet compared: two zero-stiffness singleton tables and
a descending two-point Jangle table were rejected by the reader. The subsequent
[original-file pilot](isae-ffwt-original.md) adds those narrow compatibility
rules and records two mounted solves with remaining reference differences.

The [ASWING input guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
defines zero stiffness as rigid. Both singleton tables contain only those
rigid values. Reversing the paired two-point Jangle rows preserves the exact
moment–angle function, including its sign and extrapolation. These findings
support narrow compatibility extensions that leave the original file intact;
historical reader behavior and the precise executable version remain uncertain.
The compatibility appendix supersedes the earlier blanket recommendation not
to reorder those rows. No compatible identical-physics sibling was found.

The ST-5 `Link_Joint` exports use a documented custom joint modification and
cannot serve as references for standard ASWING type-2 joints. No archive values,
material properties or acceptance tolerances were changed in this increment.

See the [machine-readable record](isae-source-joints.json),
[evidence archive](isae-source-joints-20261026-evidence.zip), and
[overall reference status](isae-aswing-reference-status.md).
