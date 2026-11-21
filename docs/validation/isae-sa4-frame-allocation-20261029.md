# SA-4: interior frames and node allocation

Updated 2026-10-29. A source-supported interpretation of the requested node
count improves a selected SA-4 subset from **70/140 to 87/140** checks at 3%.
It recovers one failed solve and ten drag checks, while five solves remain
unpassed. A separate interior-frame experiment improves one state but loses
another. Neither diagnostic establishes a general correction or changes the
registered SA-4 counts: **528/588** with default spacing and **518/588** with
the earlier fixed-count modified-spacing candidate.

## Node count: a qualified source interpretation

The original SA-4 CL driver requests `NODE / I = 80`; the CD driver requests
`I = 20`. The existing comparison interpreted these as 80 and 20 nonzero
intervals, with 160 and 40 for refinement. The ASWING guide describes `I`
as a node count. Its break rules create a zero-length interval at the
duplicated root control-property station in this model. If the requested
count is the actual node count, the nonzero interval count is therefore `I−2`.

Public SCN studies support this interpretation: the CASEI driver requests
8, 14 and 98 nodes, and the corresponding retained listings contain 6, 12
and 96 nonzero intervals plus a doubled root. CASEI has the same ground/root
topology and an identical control-derivative table as SA-4. Its geometry and
aerodynamic properties differ. Actual SA-4 computational nodes are not
archived, insufficient node requests can be increased, and the SCN listing
increment is not recorded. This evidence supports a fixed diagnostic; it
does not authenticate the exact historical SA-4 mesh.

The predeclared comparison changes 80/160 to **78/156** intervals and 20/40
to **18/36**. Refinement doubles the corrected coarse count; it is not a
second literal historical request. The modified cosine recipe and its
material-arc mapping are retained, with original frames, all physical
inputs, solver settings and acceptance gates. There is no count sweep or
fitting to force outputs. The curved-axis extension of the spacing recipe
remains unauthenticated.

The subset contains all 16 jobs unpassed in either the original or modified
spacing comparison, plus four lowest-positive-incidence passing controls,
one at each original count. All 20 cold calls finished, without retries or
timeouts; all child processes exited zero and were reaped. Fifteen returned
valid solutions and five reported solver errors. Maximum accepted normalized
circulation residual is `3.595e-13`; maximum accepted normal Mach is 0.782493.

| Selected group | Jobs | Modified-spacing baseline | Count candidate | Result |
|---|---:|---:|---:|---|
| Unpassed in either earlier comparison | 16 | 42/112 | 59/112 | 17 gained, no lost checks in this subset |
| Passing controls | 4 | 28/28 | 28/28 | All retained; maximum output error 1.524% |
| Total | 20 | 70/140 | 87/140 | Five solver errors remain |

The 17 gains are specific:

- The five coarse CD-table states at 7.60807–9.59654° regain both drag and
  CD: ten checks. Total-CD errors fall to **+2.335–2.988%**, close to the
  provisional limit at the highest angle.
- The CL-table state at 6.10°/156 intervals converges and passes all seven
  outputs, with maximum error **1.937%**. It failed at 160 intervals.

The unresolved outputs remain significant:

- Solves fail at 2.62°/78 and 4.06°, 4.60°, 5.13°, 5.57°/156. These states
  contribute no accepted reference values or physical error percentages.
- At 7.06°, CD remains **6.405% low** on 78 intervals and **4.999% low** on
  156. CDi is **6.825% / 6.274% low**, and efficiency **7.119% / 6.543% high**.
  The coarse drag error worsens despite no additional pass-count loss.
- At zero aircraft incidence, both grids still pass only drag and CD.
  The 78-interval absolute CL/Cm errors grow to **1.0324e-5 / 8.5727e-6**;
  the 156-interval differences are **4.9200e-6 / 4.1363e-6**. The candidate
  therefore does not resolve the small-load comparisons.

Independent saved-result replay passes **2,809 checks with zero mismatches**,
covering source hashes, exact job selection, process eligibility, numerical
gates, reference arithmetic and all gains/losses. These are audit checks,
not additional ISAE outputs. The saved modified-spacing baselines precede
the verified analytic-Jacobian hookup; the physical residual is unchanged.
The 64 remaining registered SA-4 jobs were not rerun for this count candidate,
so 87/140 must not be extrapolated into a full SA-4 score.

## Interior frame interpolation: a separate experiment

The source audit found no demonstrated error in the unloaded frame algebra,
chord-plane projection or parsing of the supplied properties. Drela's
Technical Description defines the nodal Euler frames and weighted position
sampling, but the available text does not uniquely establish historical
interior-angle interpolation. The diagnostic interpolates endpoint Euler
angles at the existing material Glauert fraction instead of reevaluating
the jig tangent there. All other mesh fields and sampled properties stay fixed.

The geometry-only study covered ten meshes: both grids for SA-1 through
SA-5, using SA-4's primary 80/160 CL scope. It made no aerodynamic calls.
Straight SA-1/SA-2 and sided SA-5 frames agree to roundoff. Maximum SA-3 frame
differences are 3.111°/3.843°, and SA-4 differences are 1.099°/3.727°, near
the curved tips. Increasing differences between these two grids do not
establish a converged interpolation limit.

Eight subsequent cold calls used the original default node positions and
changed only interior frames. Seven valid states and one solver error were
returned, with all eight children reaped, no timeouts and no retries.
The original results are saved same-count controls predating the primary
direct solve's analytic-Jacobian hookup; these paired convergence transitions
therefore do not isolate the frame change. The separate full default-mesh
recheck preserved all original pass counts and the same six solver failures.

| Case | Intervals | Incidence | Original → frame candidate |
|---|---:|---:|---:|
| SA-3 | 100 | 7.04348° | 7/7 → 7/7 |
| SA-3 | 200 | 7.04348° | 7/7 → 7/7 |
| SA-4 | 80 | 0.29° | 7/7 → 7/7 |
| SA-4 | 160 | 0.29° | 7/7 → 7/7 |
| SA-4 | 80 | 4.06° | 7/7 → 7/7 |
| SA-4 | 160 | 4.06° | 0/7 → 7/7 |
| SA-4 | 80 | 7.06° | 3/7 → 3/7 |
| SA-4 | 160 | 7.06° | 3/7 → 0/7 |

The total changes from 41/56 to **45/56**. The recovered 4.06° state has
maximum output error 0.334% but reaches normal Mach **0.986108**. At 7.06°,
the fine-grid candidate fails with normalized residual 2.12. Thus this
construction is not a general fix. No 320-interval or supplementary CD-scope
flow calls were included. It was not combined with the count candidate.

## Zero-incidence input detail

SA-4 is not a uniform zero-section-offset case at zero aircraft incidence.
Its `alpha` property, defined by the ASWING guide as the zero-lift-line angle
above the chord axis, is **−0.1° at t = 0.988585, 1.00841 and 1.01783**.
These are literal model lines 783, 786 and 788, mirrored on the other half.
Twist and section Cm are zero. Every diagnostic preserves these entries.

The archived zero-incidence targets are CL = −7.71102e-6,
Cm = −5.94266e-6 and CDi = 2.73363e-10. Their small magnitudes do not make
them pure solver roundoff: the model supplies localized nonzero incidence
offsets, and sampling their interpolated distribution changes with the mesh.
This is an input-based explanation for a nonzero response, not a quantified
attribution of every discrepancy. The existing strict tiny-reference policy
remains in effect for CDi.

## Interpretation and evidence

The strongest common theme remains discretization of local induced velocity
and near-field forces: spacing resolves SA-2, substantially improves SA-5,
and changes SA-4 branches and drag. The count interpretation explains the
five new coarse drag regressions from the earlier SA-4 spacing test. It does
not resolve curved-tip solve failures or the high-incidence CDi deficits
shared by SA-1 and SA-5. Independent section-limit checks have not identified
a stall-law defect. Changes that recover one selected state while losing
another are retained as diagnostics, not promoted to production defaults.

Primary sources are the [ASWING User Guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt),
[Technical Description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf)
(pp. 5, 31–33 and 45), and the pinned public ISAE files listed in the
[source review](../../artifacts/isae/sa4-node-allocation-20261029/source-review.json).
The local guide citations include lines 1179, 1338–1386 and the version notes
at lines 591–598. Node-allocation claims are explicitly inferences from those
sources and the retained SCN listings.

Detailed evidence:

- [Count protocol and source pins](../../artifacts/isae/sa4-node-allocation-20261029/protocol.json),
  [all 20 comparisons](../../artifacts/isae/sa4-node-allocation-20261029/report.json),
  [independent replay](../../artifacts/isae/sa4-node-allocation-20261029/saved-result-review.json),
  [execution receipt](../../artifacts/isae/sa4-node-allocation-20261029/root-execution-receipt.json).
- [Geometry-only frame study](../../artifacts/isae/sa1-sa5-frame-interpolation-20261029/report.json),
  [eight flow comparisons](../../artifacts/isae/sa34-endpoint-frame-flow-20261029/report.json),
  [process eligibility](../../artifacts/isae/sa34-endpoint-frame-flow-20261029/independent-terminal-receipt.json).
- [Literal zero-lift-angle entries](../../artifacts/isae/sa4-node-allocation-20261029/zero-incidence-source-observation.json).

All registered scores and production aerodynamic equations/defaults are
unchanged by these studies. The separate implemented source structural
interval-length correction is documented in the
[Eq.48 audit](source-rigid-arc-measure-20261029.md).
