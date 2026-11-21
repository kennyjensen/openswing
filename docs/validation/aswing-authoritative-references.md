# Authoritative ASWING and AVL reference library

Verified and downloaded 2026-11-08 UTC. At the user's request, the four ISAE
reports are authoritative primary sources for their case definitions, ASWING
results, modifications and stated limitations. They must be consulted alongside
Drela's technical descriptions and the corresponding archived models, scripts
and numerical output.

The user also designates AVL's documentation, source and native results as
authoritative. When a matched OpenSwing/AVL comparison agrees but an ISAE
ASWING comparison does not, the first investigation should be the case setup
and ASW-to-AVL conversion. This requires matching the actual case, not merely
showing agreement on a related simplified wing.

## ISAE experimental-validation reports

Romain Jan's reports were downloaded from the author's
[ISAE validation repository](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/tree/f62943df20e9e4d7d9f50e070477b22426b5f865/5%20-%20Technical%20Reports).
The checked `main` revision is `f62943df20e9e4d7d9f50e070477b22426b5f865`.
All four downloads match both the upstream Git blob identifiers and the
previously retained SHA-256 checksums. These are verified copies of reports
already present in the older reference cache, now collected under clear names.

| Report | Version in revision notes | Pages | Local files |
|---|---|---:|---|
| Experimental validation of ASWING. **Part I: Aerodynamics** | I.4.0, 28 February 2025 | 78 | [PDF](../../reference/aswing-authoritative-20261108/isae-part-1-aerodynamics.pdf), [searchable text](../../reference/aswing-authoritative-20261108/isae-part-1-aerodynamics.txt) |
| **Part II: Propellers** | II.2.0, 28 February 2025 | 32 | [PDF](../../reference/aswing-authoritative-20261108/isae-part-2-propellers.pdf), [searchable text](../../reference/aswing-authoritative-20261108/isae-part-2-propellers.txt) |
| **Part III: Structure** | III.5.0, 28 February 2025 | 56 | [PDF](../../reference/aswing-authoritative-20261108/isae-part-3-structure.pdf), [searchable text](../../reference/aswing-authoritative-20261108/isae-part-3-structure.txt) |
| **Part IV: Aeroelasticity** | IV.4.0, 28 February 2025 | 44 | [PDF](../../reference/aswing-authoritative-20261108/isae-part-4-aeroelasticity.pdf), [searchable text](../../reference/aswing-authoritative-20261108/isae-part-4-aeroelasticity.txt) |

The cover year is 2024; the latest revision notes in these files are dated
2025. File suffixes such as `V4` do not identify an ASWING executable version.
The reports describe both original and modified ASWING results. Their revision
notes explain that some cases are only partially repeatable because the modified
source is not distributed. Read each case's own repeatability classification.

## Related primary references

These PDFs were also downloaded, parsed and checksummed in the same collection.

| Source | Use | Local copy and publisher/author source |
|---|---|---|
| Jan, Delbecq & Benard, **Evaluation of ASWING for overall aircraft design of unconventional configurations. Application to joined wings with folding wingtips**, ICAS 2024 | Related validation of joined wings and folding wingtips | [PDF](../../reference/aswing-authoritative-20261108/jan-2024-icas-joined-wings.pdf), [text](../../reference/aswing-authoritative-20261108/jan-2024-icas-joined-wings.txt), [ICAS source](https://www.icas.org/icas_archive/icas2024/data/papers/icas2024_0254_paper.pdf) |
| Drela, **ASWING 5.99 Technical Description — Steady Formulation**, 10 March 2015 | Governing steady equations and discretization | [PDF](../../reference/aswing-authoritative-20261108/drela-aswing-steady.pdf), [text](../../reference/aswing-authoritative-20261108/drela-aswing-steady.txt), [MIT source](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf) |
| Drela, **ASWING 5.99 Technical Description — Unsteady Extension**, 10 March 2015 | Unsteady equations, time integration, frequency response and modes | [PDF](../../reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf), [text](../../reference/aswing-authoritative-20261108/drela-aswing-unsteady.txt), [MIT source](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf) |
| Avoni, **ASWING Extended User Manual**, version 1.0, 16 September 2025 | Operating workflow and practical settings; its introduction identifies ASWING 5.98 | [PDF](../../reference/aswing-authoritative-20261108/aswing-extended-user-manual.pdf), [text](../../reference/aswing-authoritative-20261108/aswing-extended-user-manual.txt), [MIT source](https://web.mit.edu/drela/Public/web/aswing/ASWING_Extended_User_Manual.pdf) |

Drela's [original user documentation](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
is also available in the existing [local text](../../reference/aswing_doc.txt).
The different document/software version labels are retained deliberately;
they should not be treated as proof that every archived run used the same code.

The [Daedalus animation source supplement](daedalus-animation-sources-20261113.json)
adds Drela's *Analysis of Exact and ROM Bode Responses for Alternative State
Vector Definitions* (title-page date 23 August 2008), downloaded from MIT on
13 November 2026. Its direct descriptor equations and singular-mass ROM
counterexample are distinct from a Daedalus reference solution. The supplement
also records the June 2008 Bode PDF and June 2009 GIF publication histories;
these dates do not establish identical operating settings. See the
[image comparison](daedalus-animation-20261113.md) for the resulting limits.

The [Daedalus plume/version review](daedalus-plume-receivers-20261114.md)
adds a [fresh official release-note receipt](../../reference/daedalus-plume-receivers-20261114/receipt.json),
byte-identical to the retained notes. It distinguishes documented version
changes from a conditional receiver-specific plume diagnostic. The latter
does not identify or recreate the historical defect.

The [ST-4 node-placement supplement](isae-st4-node-placement-sources-20261109.json)
adds Drela's **Method for Simultaneous Wing Aerodynamic and Structural Load
Prediction**, AIAA-89-2200 (1989), downloaded from a public mirror and retained
with checksums in [reference/](../../reference/st4-node-placement-20261109/).
Its Eqs. 37–38 provide a specific spacing prescription. The official manual
associates this paper with ASWING 3.x; it is not proof of the later 5.x default.
The [current comparison](isae-st4-node-placement-20261109.md) preserves that
version boundary and the unspecified point-load node adjustments. The original
eight-source catalog remains unchanged.

The later [Daedalus wing comparison](daedalus-wing-paper-20261113.md) examines
this same paper's Figures 7–8 and roll-pinned mount description. It retains the
distinction between the 240 lb steady-wing case, the literal modern `dae.asw`,
and the subsequent full-aircraft Bode drawing. Current static shape agreement
and a conditional joint-release diagnostic do not establish that drawing's
operating point or dynamic validation.

The [current source-equation K/F comparison](daedalus-frozen-source-20261114.md)
also checks the official manual's Engine jet rule: the plume centerline follows
the aircraft x-axis in fast mode. The corrected implementation and freshly
trimmed full response still fail to reproduce the later Bode dip. That result
does not change the independent steady evidence from the wing paper.

The [lagged-influence derivative review](daedalus-lagged-influence-20261114.md)
reconciles the steady Newton approximation discussion with the unsteady
partial-derivative definitions and the 1999 paper's matrix reuse. An explicitly
conditional omission of loaded influence-geometry derivatives changes yaw by
only -0.00773% at the published dip. It does not identify the historical
Jacobian or justify removing production derivatives.

The [wing-property/weight audit](daedalus-paper-properties-20261114.md) compares
the 1989 paper's Figure 7 with the literal public wing tables. It also adds
Cruz's **Weight Analysis of the Daedalus Human Powered Aircraft**, Technical
Soaring 14(1), 1990, from the [primary journal](https://ts.ostiv.org/index.php/ts/article/view/760).
The [source supplement](daedalus-weight-sources-20261114.json) retains the PDF,
text, download receipt and visually checked table page. Measured component
weights are distinct from the 1989 plotted model and the later ASWING example;
none identifies the 2008 Bode operating-point file. The original catalog stays
unchanged.

The subsequent [measured-mass sensitivity](daedalus-measured-mass-20261114.md)
uses Cruz's component totals with seven explicitly assumed distributions.
Full source gravity/inertia tangents and coupled responses do not reproduce
the Bode dip. These fixed-mean-state diagnostics and exported conditional
`.asw` variants neither identify historical input settings nor substitute
measured component totals for a documented mass distribution.

The [localized wing-mass study](daedalus-wing-peak-mass-20261114.md) then uses
Figure 7's traced peak excess, kept separate from Cruz's measured totals.
Its point-mass placement is explicit, and a fresh physical trim includes the
resulting shape/preload changes. The full response still misses the Bode dip.
This tests one historical-model hypothesis; it neither reconstructs the full
Figure 7 input nor authenticates the later Bode setup.

The [in-plane-stiffness audit](daedalus-paper-stiffness-20261114.md) independently
traces Figure 7's EIn curve, excluding crossings and merged curves. A partial
reconstruction at readable original input stations changes yaw at the later
Bode dip by only +0.0583% after a physical retrim. This documents a historical
property difference without identifying the later model or validating its
dynamic response. No production material property is changed.

The [principal-axis audit](daedalus-section-axes-20261114.md) reconciles the
older paper's signed fore/aft bending variables with the modern stress-integral
definitions. Independent constitutive and zero-lift-orientation calculations
agree with the literal Daedalus model. It also records the distinction between
the inverse rotation returned by printed modern Eq. 43 and a physical twist
increment under Eq. 30, without inferring native utility behavior or changing
the supplied aircraft. The angular interpolation between nodes remains a
separate source-comparison question.

The [interior-rate comparison](daedalus-rate-interpolation-20261114.md) verifies
the documented Glauert midpoint positions and distinguishes nodal body-axis
angular velocities from interior interpolation choices. A conditional
componentwise-rate replay changes the Daedalus dip response negligibly. A
separate local Euler-interpolation probe is not counted as a coupled response
or proof of the native interpolant; production interpolation is unchanged.

The later [independent mounting-span comparison](daedalus-mount-continuum-20261114.md)
checks the short wing–fairing boom segment against a continuous spatial rod,
including preload and real local inertia. Its conditional replay of the actual
aircraft loads supports the mounting mechanics, while retaining all disclosed
unit-input discrepancies. It neither identifies the historical Bode setup nor
substitutes a changed material property into the public aircraft.

The [flight-research supplement](daedalus-flight-research-sources-20261114.json)
adds Sullivan and Zerweckh's **Flight Test Results for the Daedalus and Light
Eagle Human Powered Aircraft**, NASA-CR-183305 (1988), downloaded from
[NASA](https://ntrs.nasa.gov/citations/19890001519). This primary source is
cited by Drela's wing-load paper. Its Light Eagle dynamics and Daedalus
performance remain distinct; neither identifies the 2008 Bode input. The
[current mode-shape review](daedalus-mode-shapes-20261114.md) records the
wing/boom coupling evidence, zero-speed versus flight-mode distinction, and
an apparent factor-of-ten inconsistency in the printed inertia conversions.
No reported prototype parameter is substituted into the public `dae.asw`.

The [historical lag-law supplement](daedalus-historical-lag-sources-20261113.json)
checks Drela's **Integrated Simulation Model for Preliminary Aerodynamic,
Structural, and Control-Law Design of Aircraft**, AIAA-99-1394 (1999), against
a fresh [official MIT copy](https://web.mit.edu/drela/Public/web/aswing/asw_aiaa.pdf).
It matches the retained PDF byte-for-byte. Printed pp. 5/8, Eqs. 15–16 and
22–25, already contain quarter-chord circulation/rate loads and the same
`b=2/π` lag approximation. This does not authenticate the later Daedalus run
settings. The eight-source catalog remains unchanged; the supplement preserves
its download receipt and visually checked page numbers.

The [archived Daedalus input review](daedalus-historical-input-20261114.md)
adds an October 2008 capture of the public `dae.asw`, byte-identical to the
current MIT download and literal worktree file. It also retains 2007 captures
of the **5.60 steady** and **5.64 unsteady** technical descriptions with their
printed 2005/2006 dates. The
[source supplement](daedalus-historical-input-sources-20261114.json) records
archive checksums and receipts. These historical primary sources constrain
the version comparison; they do not recover the 2008 operating point or
supersede the current 5.99 implementation target. A focused load/lag comparison
finds the same forms, and reconciles the older full-wake discussion with the
FAQ's stated local approximation.

## AVL

The official [AVL distribution](https://web.mit.edu/drela/Public/web/avl/)
provides the documentation and source used here. The retained
[AVL 3.52 archive](../../reference/avl-native-20261108/avl3.52.tgz) has SHA-256
`0b588ecea9222f5b625d0af0c87ae31daf3cdba1532cf0bbb36f93d6e854849b`.
The [native build and controls](avl-native-controls-20261108.md) document
provenance and build changes. The
[matched geometry and field comparison](avl-matched-fields-20261108.md)
compares nine one-row controls with production OpenSwing, including straight
swept wings and continuous winglets. These controls establish agreement for
their stated conditions; actual SA-2, SA-10 and SA-11 conversions require
their own checks.

The [loaded Daedalus multi-surface comparison](daedalus-coupled-avl-20261114.md)
checks native AVL with all four lifting surfaces interacting. It separates
the native quartic core from ASWING's Eq. 161 core, then receiver and force
conventions. The four total lateral moment derivatives are close under the
declared steady conditions; substantial differences in smaller components
remain. A separate full-dynamic diagnostic finds a small direct wing–fin
airflow effect at the yaw dip. Neither check establishes historical ASWING
Bode agreement or authorizes substituting AVL's core law.

The subsequent [SA-11 conversion audit](isae-sa11-avl-conversion-20261108.md)
checks the actual upper and upper/lower winglet geometry on two grids each.
Its linear, incompressible comparisons identify incidence interpolation and
beam-versus-bound-line conventions; they do not establish an archived ISAE pass.

The [archived-speed SA-11 baseline comparison](isae-sa11-avl-baseline-20261108.md)
extends the native operator comparison to nonzero PG Mach. Both solvers show
the same loading bias with the supplied baseline slope and agree much better
with the archived lift/CDi after the independently documented slope transfer.
Total drag and the exact archived generating input remain unresolved.
The [curved SA-11 extension comparison](isae-sa11-curved-extension-20261108.md)
samples the original spline at every ASW node. It verifies shared source
endpoints while retaining distinct receiver rules. Unlike the earlier straight
controls, its native force-field replay must include AVL's small same-component
quartic core. Both the native core and ASW zero-core laws are checked separately;
their difference does not authorize changing ASWING's documented prescription.
The [paired-speed moment audit](isae-sa11-moment-speed-20261108.md) uses original
archived 255/266 m/s differences to check the local-Mach moment law. It isolates
native-versus-whole-beam receiver sampling with fixed vortex endpoints; close
integrated AVL loading alone does not establish identical section velocity.
The [actual-winglet receiver check](isae-sa11-winglet-receivers-20261108.md)
restores whole-beam sampling on fixed native endpoints. It sharply reduces
the formal drag discrepancy at two angles, while local-Mach rejection remains;
this distinguishes receiver conventions from a production force-law change.
The [0–5° follow-up](isae-sa11-whole-beam-polar-20261108.md) confirms formal
CL/CD agreement within 0.731%/0.241% across all 21 archived rows on the disclosed
alternative setup. Each state still rejects at two root receivers, so this
agreement constrains the local-flow investigation without adding primary passes.
The [separate Trefftz check](isae-sa11-whole-beam-wake-20261108.md) applies
Eqs. 207–211 to those saved fields, keeping total drag, near-field vortex drag,
Trefftz CDi and efficiency distinct. CDi/efficiency errors stay within 5%,
while analytic root-ray attribution confirms the offset-origin mechanism.
The [three-angle drag decomposition](isae-sa11-drag-closure-20261108.md)
separates drag-axis, force-measure, bound and finite-origin wake effects using
the saved fields. It identifies receiver sampling as a separate concern from
the rejected root moments; no altered force law follows from the accounting.
The [root-moment and receiver-location audit](isae-sa11-root-moment-envelope-20261108.md)
checks AVL's section-local cosine angle rule against its source and saved
stations. The winglet-root points essentially do not move; their changed flow
comes from circulation. Total moment within 5% cannot identify a local root
correction, and no moment limiter is inferred from that aggregate agreement.
The [independent-input availability check](isae-sa11-independent-input-search-20261108.md)
finds only aerodynamic placeholders in the author's older repository. A
retained independent AVL thesis describes a different Boeing 747 winglet model;
neither source supplies a paired SA-11 input or authenticates its setup.

## How these sources govern the comparison

The supplementary [SA-11 Chreim review](isae-sa11-chreim-review-20261108.md)
follows the wake criticism cited in ISAE Part I, p. 17. Its
[source supplement](sa11-chreim-sources-20261108.json) records the downloaded
2023 author manuscript and the unavailable 2019 thesis. This independent
formulation research does not establish undocumented ASWING behavior. In
particular, Jan explicitly says his validation did not observe the cited wake
instabilities. The eight-source authoritative catalog above is unchanged.

- Use the ISAE reports as primary evidence for the documented test setup,
  selected airfoil properties, observables, results and known limitations.
  Preserve their distinction between original ASWING, ISAE modifications and
  experimental data. Our acceptance target remains the tested ASWING output.
- Use Drela's equations and operational documentation to establish the
  intended native algorithm and defaults. A reported ISAE modification applies
  when the selected comparison actually uses it.
- Check the report together with its `.asw`, `.sh`, settings and output files.
  Record conflicts with exact pages, equations and file revisions; do not
  silently choose the source that makes a result pass.
- Use AVL as an authoritative independent reference for its documented
  formulation. Check normal versus streamwise chord, sweep breaks, incidence,
  zero-lift angle, physical components, references, mesh, wake direction,
  compressibility and drag conventions before interpreting a discrepancy.
  Agreement with native AVL makes case interpretation and conversion a
  priority; it does not by itself prove undocumented ASWING behavior.
- Other lifting-line codes and papers provide independent diagnostics. Their
  methods do not establish undocumented native ASWING behavior.
- Prefer the original PDF for equations, symbols, tables and figures. Extracted
  text is a search aid, with explicit PDF page markers.

This source policy is also recorded in [AGENTS.md](../../AGENTS.md).

## Immediate relevance to SA-10 and SA-11

Part I, **p. 35**, explicitly reports local lift divergence at the junction
between the wing and tip sails in ASWING. The author attributes the difficulty
to circulation continuity at the three-branch connection and distinguishes it
from the continuous wingtip configuration. This is primary evidence of a
reported native ASWING limitation, not merely a conjecture from other solvers.
It does not prove that OpenSwing's SA-11 Mach rejection has the same cause.

For SA-11, **Table 2, p. 23** labels the case fully repeatable. The discussion
on **p. 35** says MSES supplied the airfoil polars, omits some numerical setup
details, and states the limitations of the transonic predictions. Geometry is
provided in **Appendix D, pp. 65–68**. These statements must be reconciled with
the supplied models and output, rather than using transonic experimental
disagreement to dismiss a failure to match ASWING. Page 35 was visually checked
against the PDF during this acquisition.

## Provenance and availability

The [source catalog](aswing-authoritative-sources.json) records source URLs,
retrieval timestamps, local paths, PDF page counts and SHA-256 checksums for all
eight PDFs and their extracted text. Per-download receipts are retained beside
the files. The local PDFs live under the ignored `reference/` directory; the
tracked catalog preserves the URLs and hashes for a fresh checkout. Existing
reference copies and historical validation evidence have been preserved.
The former `.reference` name is a compatibility symlink to this visible folder,
so older evidence paths continue to resolve without rewriting historical records.

Newer journal versions were located under DOIs
[10.2514/1.C038192](https://doi.org/10.2514/1.C038192),
[10.2514/1.C038193](https://doi.org/10.2514/1.C038193) and
[10.2514/1.C038194](https://doi.org/10.2514/1.C038194). Their full PDFs were not
retrieved in this acquisition, and no unseen contents are used as evidence.
Jan's thesis, [2023ESAE0046](https://theses.fr/2023ESAE0046), is already retained
as a [289-page PDF](../../reference/isae-circulation-count-20261029/Jan-2023-thesis.pdf)
and [searchable text](../../reference/isae-circulation-count-20261029/Jan-2023-thesis.txt).
The earlier statement that no local full text was available was incorrect.
On 2026-11-08 the PDF was checked against its existing
[download receipt](../../reference/isae-circulation-count-20261029/Jan-2023-thesis.receipt.json):
SHA-256 `40e6a250f0024c8abf67e2ed02deffcd02ac2e3f09cce461bcae532797481650`.
This is an additional retained primary source, separate from the eight PDFs
downloaded into the collection above. Its printed pp. 93 and 96 discuss SA-11;
the later standalone Part I report retains the same setup qualifications.

This acquisition changes reference guidance only. It does not change solver
equations, comparison denominators, pass counts or progress observations.
