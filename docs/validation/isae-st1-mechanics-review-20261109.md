# What ST-1 should demonstrate

The user's objective is correct mechanics with behavior similar to ASWING.
ST-1 is a suitable benchmark for that purpose, but **9/200 is an archive
completion score, not a measure of mechanical correctness**. Its denominator
contains unavailable inputs, duplicated conditions on different meshes, and
individual real/imaginary root components. It must remain visible without
being presented as 191 demonstrated mechanical failures.

The initial six matches represented **one loaded, naturally twisted blade on
two meshes**. The subsequent [static-curve comparison](isae-st1-static-curves-20261109.md)
now covers all four static layouts and nine root conditions: 201/201 coordinates
within 5%, worst error 0.762%. This is substantially stronger mechanics evidence.
The 52 previously labelled “physical checks” also include source identity,
setup and save/restore checks. Those checks are useful safeguards, but they
are not 52 independent physical benchmarks. Force balance and a converged
residual alone cannot establish that a constitutive law is correct.

## Initial single-condition evidence

For the `[45/0]3a` blade with a 0.4 kg tip mass, all three displacement-component
errors are below 0.014% on both meshes. The sensor displacement magnitude is
about 0.164 m, so this is a meaningful large-deflection comparison. The full
position-vector difference from ASWING is 1.09 micrometres on the coarse mesh
and 15.20 micrometres on the fine mesh. These are 0.00067% and 0.00930% of the
reference displacement magnitude. The mesh-to-mesh difference is 0.00873%
of that displacement magnitude. Two meshes establish small sensitivity here,
not an observed asymptotic convergence rate.

Displacements above subtract the undeformed sensor anchor [0, −0.22, 0] m.
This particular model has zero distributed weight and no other applied load,
so the jig is its unloaded reference after removing the point mass. No new
unloaded ASWING result or solve is claimed. Original coordinate comparisons
and their existing acceptance decisions remain unchanged.

## Work priorities

The follow-up [modal study](isae-st1-modal-mechanics-20261109.md) declares all
22 named report frequencies. Together with the 201 static coordinates, these
now form the primary mechanics scope. The subsequent
[cross-ply reconstruction](isae-st1-cross-modal-20261109.md) brings this to
212/223 matches, and the [thin-blade comparison](isae-st1-thin-modal-20261109.md)
raises it to 221/223; archive completeness
remains a separate 9/200 measure. The scope change is recorded explicitly.

The pooled count is a progress measure, not a measure of confidence in
all mechanics: 201 coordinates sample nine static curves, while 22 frequencies
test dynamics. Keep the static and modal components prominent separately.
The 55% mode-family activity cutoff is an identification aid, not a published
ASWING requirement; the mixed-mode label conflict alone does not demonstrate
a structural-model error. The [original material-source review](isae-st1-material-source-review-20261109.md)
documents the remaining physical-input conflicts without fitting parameters.


| Mechanical behavior | Evidence to obtain | Current ST-1 coverage |
|---|---|---|
| Nonlinear bending and spanwise shortening | ASWING load–deflection curves from unloaded through large deflection | All nine load curves checked; 201/201 coordinates pass |
| Effects of composite layout and orientation | All four static blade layouts and the report's root angles, including coupling and natural twist | Four layouts and all nine archived root conditions checked |
| Bending and torsional dynamics | The report's identified bending/torsion frequencies, with matched mode identity and equilibrium; mode shapes where available | Twenty named frequencies match on both meshes, including thirteen with documented reconstructions; all configurations computed, with one coupled identity and one printed-value conflict unresolved |
| Numerical reliability | Small mesh sensitivity, residuals, equilibrium reactions and independent beam/section limits | Small loaded-state mesh sensitivity at all nine root conditions; independent gravity/wrench and clamp checks |

These priorities follow ISAE Part III §4.1, Figures 19–22 and Table 3. The
comparison target is the **ASWING prediction**, with experimental curves kept
separate. Use the user's 5% reference allowance and retain strict numerical
checks. Existing independent section/beam tests provide complementary equation
verification; their existence is not a claim that they were rerun in this review.
ST-1 alone does not establish lower-aspect-ratio structural accuracy, as the
report itself explains on p. 34.

Resolve innocuous syntax issues with explicit, minimal derived inputs when
needed. For example, terminating a genuinely empty trailing `Engine` block
introduces no engine or load. Preserve the original file and record the change;
do not require reproducing an undocumented parser quirk before testing the
mechanics. Ambiguous mass/stiffness scaling, geometry, fixtures and mode pairing
still require physical justification. No parameter fitting to reference output.

Prioritize the physically identified modes in the report rather than spending
the next effort reproducing every unclassified archived root. The full complex
root inventory remains an open diagnostic scope; it is not deleted or counted
as passed. The initial review introduced no new denominator. The subsequent static and
modal plans declared their complete targets before scoring; the explicit
[mechanics scope](isae-st1-mechanics-scope.json) now records that selection.

[Saved-result review](../../artifacts/isae/st1-mechanics-review-20261109/review.json)
rechecks source/artifact hashes and computes the displacement metrics without
new solves. [Current numerical baseline](isae-st1-current-20261109.md) and the
[authoritative references](aswing-authoritative-references.md) retain the setup
qualifications and original comparisons.
