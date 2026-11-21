# ST-2: return to the published structural comparisons

ST-2 is the active focus following the user's request to move on from ST-1.
The first current-code static pilot reproduces the published ASWING 3 kg
bending deflection within **0.065% on both meshes**, using an explicitly
reconstructed tip attachment. This is promising evidence for the mechanics;
it does not resolve ASWING's treatment of the original attachment station.
The registered archive count remains **56/490 at 5%**.

## Source and comparison scope

The authoritative source is Jan, *Experimental validation of ASWING, Part III*,
section 4.2, p. 34, Figure 23 on p. 36 and Table 4 on p. 37. Its PDF and
searchable text match the [authoritative source catalog](aswing-authoritative-sources.json).
The report specifies forty structural nodes and describes the upright and
self-weight-deformed modal configurations, static bending and static torsion.
The target here is documented **ASWING output**, distinct from experiment and
UM/NAST.

The six original EPS files retain 77 ASWING ordinates:

| Published curve | Ordinates recovered |
|---|---:|
| Skin off, bending deflection | 11 |
| Skin on, bending deflection | 16 |
| Skin off, torsion deflection | 11 |
| Skin on, torsion deflection | 14 |
| Skin off, torsion angle | 11 |
| Skin on, torsion angle | 14 |

The [extraction and pilot script](../../scripts/verify_st2_static_pilot.py)
reads the original red ASWING paths and calibrates against labelled axis ticks.
It retains printed coordinate uncertainty and verifies every load abscissa
against the input load list used by `Post_treatment.m`. Experimental ordinates
are not used as targets. These are 77 plotted ordinates, including overlapping
load conditions across curves, not 77 independent cases. They are candidate
mechanics comparisons; no new primary scope is registered by this pilot.

## First static result

The selected condition was fixed before either solve: the largest bending
load, 3 kg, from the skin-on curve. The source uses the same simplified beam
properties for both skin labels. No skin stiffness adjustment is introduced.
The observable follows the original MATLAB producer: minus the difference
between loaded and unloaded tip z. The unloaded state includes self-weight.

| Mesh | OpenSwing deflection | ASWING plot | Relative error |
|---|---:|---:|---:|
| 40 nodes, cosine | 0.269570787 m | 0.269449859 m | 0.044880% |
| 80 nodes, cosine | 0.269622484 m | 0.269449859 m | 0.064066% |

The coarse-to-fine observable change is **0.019174%**, below the predeclared
1% mesh gate. Both loaded and unloaded states pass equilibrium residual,
force/moment balance, independently calculated gravity force and root clamp
checks. The two serial jobs took 2.37 and 1.92 seconds after imports, respectively,
each including both load states. They used one BLAS thread, a 512 MiB address
space cap, 15 seconds CPU and 25 seconds wall time. Both processes exited
successfully. All 141 production modules and original reference files remain
unchanged.

## Attachment qualification and next work

Both original Weight rows have attachment parameter **t = 0.558**, beyond the
beam endpoint **t = 0.55**. The pilot explicitly anchors the load at the tip
while retaining the original physical mass coordinates **(0.05, 0.558, 0) m**,
giving an 8 mm spanwise rigid extension. It changes only the Weight records.
This is the previously disclosed archive-coordinate pylon reconstruction;
it is not proof that native ASWING clamps an out-of-domain attachment.
Cosine spacing is also prospective; the report gives the node count but not
the complete node array.

Next work is to compare the remaining published curves under that disclosed
setup and audit the attachment convention. Torsion must use the producer's
negated local section angle, which differs from experimentally projected chord
twist. The source/report load-coordinate conflict remains explicit. The two
skin labels must not be treated as recovered skin-specific structural models.

Existing modal work already supports close frequency agreement: the registered
56 computed frequency components are within 1.228% at 5%; the separate
[forty-node study](isae-st2-documented-mesh-20261104.md) reaches 0.012611% with
uniform spacing and still-air inertia. Its old strict-decimal count is historical.
Both upright and loaded modes also have independent beam-reference checks.
The 56 tiny real eigenvalue components retain their original archive gates;
the 378 unavailable outputs remain in the registered denominator. Neither those
bookkeeping counts nor this one static pilot establish complete ST-2 validation.

Evidence: [fixed plan and all extracted ordinates](../../artifacts/isae/st2-static-pilot-20261109/plan.json),
[coarse result](../../artifacts/isae/st2-static-pilot-20261109/job-0/report.json),
[fine result](../../artifacts/isae/st2-static-pilot-20261109/job-1/report.json),
[verified summary](../../artifacts/isae/st2-static-pilot-20261109/summary.json).
Requests and complete physical outputs are retained alongside each result.
