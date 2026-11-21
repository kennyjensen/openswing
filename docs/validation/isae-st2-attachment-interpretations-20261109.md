# ST-2: which physical attachment matches the archived loads?

**The archived bending moments support the existing 8 mm rigid tip arm.**
An explicit massless rigid beam, connected to the main wing by a rigid joint,
reproduces the pylon model to roundoff. Moving the physical mass onto the
wing tip or making the extension flexible changes the archived resultants.
This is stronger evidence for the physical reconstruction; it does not prove
a general ASWING rule for an attachment coordinate outside a beam's domain.

The primary ST-2 result stays **91/91** under its declared setup. This study
does not change production code, original sources, reference values, acceptance
gates, registered comparison scopes or progress fractions.

## Evidence and hypotheses

The original bending file has a main beam ending at t=0.55, with two weights
totalling 3 kg at t=0.558 and physical coordinates (0.05, 0.558, 0) m.
Drela's [Weight documentation](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
distinguishes the anchor coordinate from the point object's physical position.
His steady description, §3.3, Eqs. 87–90 and 95–96, defines the rigid arm and
its force/moment transfer; §3.6 describes rigid joints. Part III §4.2, p. 34,
specifies the Pazy test setup; §2.8, pp. 25–26, discusses concentrated loads
and structural discretization. These reviewed passages do not establish
clipping or extrapolation for an out-of-domain input coordinate.

The source catalog's Part III and steady-theory PDF/text hashes were verified.
The retained original `temp.txt` provides both total weight and local beam
resultants. Its coordinates support the already reviewed modified-cosine
45-interval mesh, rather than uniquely recovering all historical settings.

Four **explicit derived inputs** were evaluated, without editing the source:

| Interpretation | Physical model |
|---|---|
| Tip load | Anchor and physical span position both at 0.55 m; chord arm stays 0.05 m |
| Rigid extension | Original physical position retained; 8 mm massless, infinitely stiff beam joined to the wing tip |
| Massless elastic extension | Same geometry, original EIcc/GJ/EInn/EA continued through the extension, zero extension mass |
| Elastic extension with mass | Same finite stiffness and original 0.3745 kg/m continued through the extension |

The main beam's original geometry, properties, sensors, clamp and load mass
are unchanged. Its grids remain exactly the previous 45/90-interval grids;
all 46 native stations are sampled directly. The extension uses 4/8 uniform
intervals. Each physical state has independent gravity force/moment checks,
equilibrium/clamp checks, retained requests/results and source hashes.

## What the archived data distinguish

Fine-grid results at the original wing tip (t=0.55):

| Interpretation | Mc′, N m | Inside native −0.161 ± 0.0005? | Total weight, N | Inside native 31.45 ± 0.005? |
|---|---:|---:|---:|---:|
| Tip load | ≈0 | No | 31.45061475 | Yes |
| Rigid extension | −0.16141670 | Yes | 31.45061475 | Yes |
| Massless elastic extension | −0.16010100 | No | 31.45061475 | Yes |
| Elastic extension with mass | −0.16009873 | No | 31.48000551 | No |

Both grids give the same accept/reject outcomes above. The native exponent
row is applied before comparison: Mc′ and Fn scale by ten; Ms′ does not.
The published values and original precision intervals are unchanged.

| Interpretation | Fields passing at 5% on both grids / full 368-field scope | Fine-grid force/moment fields inside printed precision / 138 |
|---|---:|---:|
| Tip load | 263/368 | 21/138 |
| Rigid extension | 275/368 | 138/138 |
| Massless elastic extension | 275/368 | 127/138 |
| Elastic extension with mass | 275/368 | 111/138 |

Each alternative retains the same 92 unavailable `cl`/`a_flap` fields.
The unchanged clamped-root y comparison fails its strict roundoff gate in
each model. These are overlapping diagnostic alternatives, **not additive
progress counts**, and none replaces the primary mechanics or archive scope.

The 5% acceptance count alone cannot distinguish the three extension models.
Their difference is visible in the printed force/moment data. In particular,
the massless elastic extension moves the main wing by only 0.0218 mm relative
to the pylon but misses eleven printed bending moments. The extension with
distributed mass also contradicts the exported total weight. Moving the load
onto the tip shifts main-wing positions by up to 2.7301 mm and removes the
nonzero tip bending moment altogether.

These checks rule out the **specified** alternative models at the archived
precision under the matched operating point. They do not rule out every
possible extrapolation algorithm, prove the exact generating input bytes,
or justify a universal endpoint-clipping policy.

## Independent rigid-extension check

At both grids, the explicit rigid extension and the existing pylon give
main-wing positions within 2.11e−15 m and rotation entries within 2.34e−15.
Every extension node follows the rigid-arm kinematics within 7.22e−16 m;
joint positions and rotations coincide to roundoff. All main-wing endpoint
force/moment components agree within 7.47e−14 in their respective SI units.
This tests the existing rigid-joint/beam implementation through a different
model topology. It uses no new fitted material coefficient or solver change.

All eight revised states converge and pass the numerical gates. Maximum
field-peak mesh change is 0.01116%, below the predeclared 1% gate. Solver time
after imports totals 6.23 seconds; peak RSS is 145,152 KiB. Jobs ran serially
with one BLAS thread, 512 MiB address space, 15 CPU seconds and 25 wall seconds.
No browser, build or kernel-loading jobs were started.

The initial study specified two extension intervals, below the public API's
four-interval minimum. That request was rejected before solving. Its plan,
two completed tip-load controls and rejected request remain intact. A separate
revision uses four/eight intervals and reruns all eight states; neither the
original plan nor its script was rewritten.

The remaining compatibility question is native handling of the invalid
attachment parameter. The physical reconstruction is now independently
checked as both a pylon and a literal, in-domain two-beam ASW model. General
out-of-domain behavior remains unchanged until supported by native evidence.

Evidence: [revised plan](../../artifacts/isae/st2-attachment-interpretations-20261109/refined/plan.json),
[all fields and mesh comparisons](../../artifacts/isae/st2-attachment-interpretations-20261109/refined/summary.json),
[independent joint and native-load audit](../../artifacts/isae/st2-attachment-interpretations-20261109/attachment-audit.json),
[explicit rigid-extension input](../../artifacts/isae/st2-attachment-interpretations-20261109/refined/job-3/model.asw),
[study executor](../../scripts/verify_st2_attachment_interpretations.py),
[corrected mesh-plan entry point](../../scripts/verify_st2_attachment_refinement.py),
[read-only audit](../../scripts/audit_st2_attachment_evidence.py).
