# Static sections with offsets, shear and gravity couples

Updated 2026-10-26. Success means reproducing tested **ASWING outputs with
the original model and operating settings**. Agreement with experiments is
optional. This increment extends the static implementation and preserves the
established ST-3/ST-5 results; it does not establish a new archived-reference
pass for the added section terms.

## Available formulation

Under **Settings → Structural static → Structural equations**, the new
**ASWING static · general sections · experimental** option supports coupled
bending/torsion stiffness, finite axial and shear stiffness, all four elastic
and tension-axis offsets, and ordinary/additional distributed weights with
separate CG offsets. Rigid joints, concentrated forces/moments and rotating
point-weight pylons are supported. Lifting-surface beam charts are required.

The numerical pair is `drela-segspl-v1` / `drela-steady-section-v1`.
The previous zero-offset pair and default midpoint formulation retain their
identities. Inspection, model edits, solves, projects and saved solutions carry
the selected pair; incompatible saved-state identities are rejected. Leaving
structural analysis restores the default formulation and reinspects the model.

The section equations use the full net bending/torsion stiffness E, without
adding another parallel-axis correction. With local force F, moment M,
offset matrix H and direct axial/shear compliance D, the translated moment is
M′ = M + HF, curvature change is E⁻¹M′, and reference-axis strain is
DF + HᵀE⁻¹M′. Endpoint transforms act on body resultants before this section
translation. The average transform is generally not a rotation.

Ordinary and additional distributed weights use their own sided endpoint
values, CG arms and frames. Symmetric endpoint transfer preserves the selected
distributed force and moment exactly, including zero-net-weight couples.
Static mass and first moment follow this load rule. Dynamic inertia and spin
are explicitly unavailable. Signed-weight bookkeeping remains distinct from
physical positive mass, including negative spline samples between positive
table values.

Interval recovery reports all three translational strains. Tension-axis axial
strain and translated shell torque are identified separately. Endpoint traces
and sensor strains use actual sided sections. Interval estimates remain
labeled estimates; their plotting coordinates do not imply point sampling.

## Verification and reference comparisons

Eight independent section tests pass: six algebra/residual/Jacobian checks and
two analytic equilibrium limits. Exact rational oracles were derived separately
from the solver after reviewing the rendered primary equations. The tests cover
coupled offsets, finite shear, shell recovery, signed CG loads, conservation,
saved-state identity and the zero-offset limit. A prior exact-equality assertion
failed on 2.78×10⁻¹⁷ floating-point roundoff; its correction and original failure
are retained. No physical tolerance or reference gate was widened.

The existing structural/recovery/sensor suite passes 58 tests. Boundary checks
pass 109 Python tests and 25 JavaScript tests, with nine syntax checks. Five
existing Python solve tests were deliberately excluded from that boundary run;
the integration checks below exercise actual solves.

Three cold native bridge solves and five fresh saved-state residual checks pass
**124/124** integration checks:

| Case | Grid | Solve time | Fresh residual |
|---|---:|---:|---:|
| Original ST-3 static snapshot | 176 intervals | 1.45 s | 2.60×10⁻¹⁶ |
| Original ST-5 static snapshot | 70 intervals | 0.95 s | 1.08×10⁻¹⁴ |
| Synthetic coupled-section/CG check | 8 intervals | 0.82 s | 9.20×10⁻¹³ |

ST-3/ST-5 positions, rotations, internal forces/moments and reactions are
bit-for-bit identical to the previously checked zero-offset formulation.
Restoring the old states with their original operator also preserves their
residuals and physical fields exactly. The synthetic case independently checks
the section matrices, two CG load families, mass and first moment; it is not
an archived ASWING case.

A separate saved-field ST-3 audit now establishes the coordinate-rounding
witness for the source formulation itself: **269/270 structural entries and
44/45 complete rows** on each of the 44/88/176-interval grids. It uses one
previously frozen allowed coordinate per row, shared across all six structural
outputs and all three grids, with sided reporting splines at the actual
breakpoint. All 930 arithmetic checks pass, without another solve or coordinate
search. Direct printed-center matches remain 220/270; another 90 conditional
zero entries are separate. The sole discrepancy remains the exact-tip moment:
archived 5.59×10⁻⁹ N·m versus effectively zero. This demonstrates consistency
with rounding, not recovery of the historical unrounded mesh/exporter.

ST-5 retains its close finite-grid comparison: forward/rear tip-deflection
differences are 0.00084% / 0.0086%, with twist differences about 0.013%.
Strict printed-precision and mesh differences remain recorded in the
[earlier comparison](isae-source-discrete-integration.md).

## Browser and saved projects

The offline built UI completes the synthetic case in **2.53 s**. Startup takes
**36.65 s**, including verifier preflight and browser/runtime initialization;
these are separate single-run measurements on this host. All **2,466 numerical
values** agree with native output under the predeclared 2×10⁻⁸ absolute plus
relative criterion; the maximum absolute difference is 5.33×10⁻¹⁵. Only the
evaluation counter is excluded. The browser audit passes 1,111 checks.

The [saved project](../../examples/source-section-check-project.json) contains
the exact checked result and opens without solving. Its
[synthetic input](../../examples/source-section-check.asw) is also included.
The result reopens byte-for-byte; both the preceding zero-offset ST-5 project
and historical midpoint ST-5 project retain their exact sealed solution records.
The browser executes only one solve, makes no HTTP requests after startup and
reports no page or network errors. Desktop/mobile screenshots were inspected.
This browser/native agreement verifies implementation consistency, not an
additional archived ASWING benchmark.

The subsequent [mounted aeroelastic extension](isae-source-coupled.md) adds a
separate fourth policy for steady aerodynamic coupling. The static policy and
results described here retain their original scope and identity.

## Remaining limits

The archive inventory found no qualified unchanged static export that exercises
the added section/CG terms. Candidate files have missing or invalid definitions,
unlinked outputs, or only modal results. Those inputs were not repaired or
fitted to manufacture a reference pass. The new terms therefore have independent
equation/analytic verification, with archived regression coverage only for the
zero-offset limit.

Body-axis charts, stepped beam axes, non-rigid joint laws, struts, engines,
aerodynamic loading and motion/dynamics remain outside these source operators.
Average-before-inversion stiffness follows the rendered equations; scalar
EA/GK and offset averaging, unloaded arc for ds, the exact historical spline
caller and exporter sampling remain declared interpretations or uncertainties.
Other aerodynamic and aeroelastic reference differences remain open. The full
ASWING implementation is incomplete.

See the [reference status](isae-aswing-reference-status.md),
[previous browser integration](isae-source-static-browser.md) and
[machine-readable report](isae-source-section.json).
