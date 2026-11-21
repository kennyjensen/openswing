# SA-11: actual winglet geometry compared with native AVL

2026-11-08 UTC. The user has designated AVL as authoritative and prioritized
SA-11 over further SA-2 work. Four small comparisons now use the actual SA-11
upper and upper/lower winglet geometry, rather than the earlier rectangular
winglet controls. OpenSwing and native AVL agree closely in these **linear,
incompressible, one-chord-row diagnostics**. Both retain large junction
velocities that increase with span refinement.

This narrows the investigation: a gross conversion error or an elementary
vortex-kernel error does not explain these particular results. It does not
establish agreement with the archived transonic ASWING cases. SA-11 remains
**163/4,592 at 5%**; no production equations or registered comparisons change.

## Inputs and conversion

The source models are the bundled
[upper](../../examples/isae-sa11-wingtip-up.asw) and
[upper/lower](../../examples/isae-sa11-wingtip-up-and-down.asw) examples.
Their [provenance](../../examples/isae-sa11-winglet-sources.json) discloses
Joint-station scaling corrections; surface geometry and section properties
remain those of the pinned ISAE files. No junction gaps are closed and no
winglet origins are moved. All parts retain physical component 1.

The conversion follows the [ASWING chord FAQ](https://web.mit.edu/drela/Public/web/aswing/aswing_faq.txt)
and [AVL input documentation](https://web.mit.edu/drela/Public/web/avl/avl_doc.txt):

- Divide ASWING's beam-normal chord by `|x cross beam_tangent|` to obtain
  streamwise chord. Subtract `Xax * streamwise_chord` from the beam-axis x
  coordinate to obtain the leading edge. In these files Xax is zero.
- Convert the zero-lift-line angle `theta = twist + alpha` to the projected
  AVL incidence `atan(across * tan(theta))`. ASWING's `alpha` is the angle of
  the zero-lift line above the chord axis, not an angle to subtract blindly.
- Set `CLAF = dCLda/(2*pi)`. Use one chord row and **uniform chord spacing**
  (`Cspace=0`): native `CSPACER` then gives exactly the ASWING control-point
  offset `dCLda/(4*pi) * streamwise_chord`. With cosine chord spacing, AVL's
  CLAF shift is nonlinear, even with one chord row.
- Split surfaces at the original sweep/property breaks, preserving jumps in
  airfoil properties. Keep component identifiers, reference area, chord,
  span and the literal moment origin unchanged.

Native AVL generates each span mesh. OpenSwing receives those exact endpoints
and actual bound/control receiver stations for this diagnostic. All four
endpoint/receiver comparisons agree within **8.89e-16 m**. The explicit meshes
are retained separately; they are not a proposed change to default spacing.

Conditions are alpha 5 degrees, unit speed, Mach zero, no rotation, and frozen
body-x wake. Native AVL has no input profile drag or section pitching moment.
OpenSwing retains the source section data but disables stall for the linear
comparison. The table below compares isolated vortex forces, not total drag
including those unmatched profile inputs or total pitching moment.

## Results

Circulation error is the maximum absolute difference divided by the maximum
native circulation magnitude; it is not a maximum relative error at each strip.
CL/CD columns are OpenSwing minus native AVL, relative to native AVL.

| Actual geometry | Vortices | Circulation difference | Vortex CL difference | Vortex CD difference | Native peak speed / freestream | OpenSwing peak speed / freestream |
|---|---:|---:|---:|---:|---:|---:|
| Upper winglets | 64 | 0.1831% | +0.0908% | +0.5337% | 4.9354 | 4.9234 |
| Upper winglets | 128 | 0.1803% | +0.1126% | +0.5150% | 18.6289 | 18.5728 |
| Upper/lower winglets | 96 | 0.7562% | +0.2001% | +0.6909% | 37.8832 | 37.9644 |
| Upper/lower winglets | 192 | 0.6387% | +0.3961% | +1.9533% | 119.0257 | 120.7543 |

These are full local speed magnitudes at bound receivers, not section-normal
Mach numbers. Refinement moves the closest receivers toward the junctions;
the table is not a fixed-location convergence test. Native vortex drag also
changes materially with mesh: 0.01460 to 0.01717 for upper winglets, and
0.02661 to 0.02255 for upper/lower. Agreement between solvers does not make
these grids converged.

All four native solves and all four production calls completed. Native solve
time totaled 1.19 s; production aerodynamic calls totaled 0.55 s. These exclude
Python imports, setup, provenance checks and the earlier native build.

## Remaining differences are identifiable

Native AVL constructs a tangency normal perpendicular to the **bound vortex**.
OpenSwing's documented section frame is perpendicular to the **beam**. Taper
makes these directions different. The force integrations also use different
segment vectors: AVL uses the bound segment; OpenSwing uses the beam tangent
times material length. Their segment lengths differ locally by up to 4.85%
for the upper model and 7.75% for the upper/lower model. This is a formulation
distinction to reconcile with ASWING's equations, not a reason to change them
to improve a comparison.

The lower winglet adds a conversion issue: its twist varies from −7 to −11
degrees while chord tapers. AVL interpolates chord-weighted sine/cosine of
incidence (`amake.f`, `CHSIN`/`CHCOS`), whereas ASWING's input twist is
interpolated as an angle. Even correct endpoint conversion leaves up to
**0.7263 degrees** difference in interior projected incidence. Including the
bound-versus-beam distinction, tangency normals differ by at most 0.7134
degrees for upper winglets and 2.5032 degrees for upper/lower winglets.

Using the native normals with OpenSwing's influence operator reproduces
native circulation within **7.57e-8 relative error**, after accounting for
AVL's source-level rounded `1/(4*pi)` constant. The native tiny fourth-power
core remains different from OpenSwing's zero same-component core. Reconstructing
the beam-normal equations reproduces production circulation within
**4.29e-15 relative error**. Native bound-induced velocity is reproduced within
1.46e-6 times freestream across these cases. The audit also reconstructs the
native force output directly from exported circulation, velocity and endpoints.

## Stall and reference-case limits

The upper/lower file explicitly gives `CLmax=0.8`. At alpha 5 degrees, its
linear solutions flag 64/96 and 138/192 strips as stalled. A separate coarse
linear-field check at alpha zero still has 16 sections outside their declared
limits (section CL range −0.30794 to +0.98052). Low aircraft incidence alone
does not guarantee that every cambered, twisted section is below stall.

Consequently these are conversion/kernel diagnostics, not validation of the
stalled solution. No post-stall repair is attempted. The archived transonic
operating conditions, frozen/current influence setting, section properties
and normalization still require direct reconciliation. A successful AVL run
also does not establish that its local velocities would satisfy ASWING's
section-normal Mach restriction.

## Reproduction and retained evidence

The driver is [audit-sa11-avl-conversion.py](../../scripts/audit-sa11-avl-conversion.py);
the saved-evidence check is [analyze-sa11-avl-conversion.py](../../scripts/analyze-sa11-avl-conversion.py).
Each case runs serially with one BLAS thread. Native AVL uses the previously
[verified build](avl-native-controls-20261108.md), with only the read-only
[field export](avl-matched-fields-20261108.md) added to its output routine.

- [Upper model evidence](../../artifacts/isae/sa11-avl-conversion-20261108/plan.json)
- [Upper/lower model evidence](../../artifacts/isae/sa11-avl-conversion-lower-20261108/plan.json)
- [Combined verified results](../../artifacts/isae/sa11-avl-conversion-review-20261108/report.json)

The first upper/lower analysis stopped because it incorrectly assumed the
two incidence-interpolation rules coincided. That failed analysis and its
native output are preserved. Correcting the analysis reproduced identical
native model, total, strip and element files byte-for-byte. The original
plan's unused upper/lower refinement was superseded by the lower-only follow-up.
All four completed outcomes and 147 source/production/status pins were checked;
no prior progress events were rewritten.
