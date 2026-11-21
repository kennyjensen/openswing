# Conditional comparison with ISAE's archived Pazy output

2026-10-25. OpenSwing agrees within **0.8%** with the archived ASWING
baseline-subtracted tip displacement and sensor elevation at 5° and 30 m/s for a declared reconstruction of the simplified ISAE
model. Its no-flow sag differs by 51 nanometres, near the reference's printed resolution. This is a
two-state source-output comparison, not experimental validation, mesh convergence
or identification of every historical operating setting. Coverage remains
**18 partial / 23 pending / 0 fully validated**.

| Quantity | OpenSwing | Archived ASWING | Difference |
| --- | ---: | ---: | ---: |
| No-flow sensor-3 z | −0.0172946512 m | −0.0172946 m | −0.0000000512 m |
| Baseline-subtracted sensor-3 z, 30 m/s | 0.0570917686 m | 0.0566515 m | +0.77715% |
| Absolute sensor-3 elevation, 30 m/s | 0.6038204974° | 0.599742° | +0.68004% |

The native aerodynamic state's absolute sensor-3 z is 0.0397971175 m versus
0.0393569 m in the archive. Each displacement difference uses its own baseline;
the historical sag is not substituted into the native calculation. The plotted
historical angle is `Theta[3]`, the third sensor's elevation, rather than a
rotation-vector component. The separate projected LE–TE chord angle is
0.6038206138° in OpenSwing. The MATLAB helper's unused `theta2` expression has
a different sign convention and is not used for this comparison.

## Source and declared conditions

The [source audit](isae-ae1-literal-source.json) follows the pinned ISAE revision
`f62943df20e9e4d7d9f50e070477b22426b5f865`. The literal AE-1 file has two Weight
rows anchored at `t=.558` beyond the beam endpoint `.55`; every mass, inertia,
drag, volume and spin-load attribute in those rows is zero. The
[derived input](../../examples/pazy-isae-ae1-null-weights-removed.asw) removes
exactly those two rows (original lines 27 and 29). Every other source byte and
all 26 parsed distributions remain unchanged. Geometry is not moved or snapped.

Related ST-2 scripts deliberately use `.558` with nonzero masses, so it is not
established as a simple typo. The ASWING guide distinguishes the beam anchor
coordinate from the physical pylon-end position but does not document an
out-of-range anchor rule. OpenSwing's general attachment guard is unchanged;
this explicit null-row derivation does not establish literal-file compatibility.

The two independently cold runs use the public steady solver and four load
continuation steps each. The no-flow case has body gravity `(0,0,−9.81)` m/s².
The aerodynamic case uses 5° incidence, 30 m/s, density 1.23 kg/m³, PG Mach 0,
identity Earth attitude, gravity magnitude 9.81 m/s² and an ideal solid wall
normal to `(0,1,0)`. Controls, powers, frame rates and accelerations are zero;
all complete inputs are retained in the evidence. The source's `.0001` root
station, fully clamped root, sensor pylons and `.52` stiffness break are retained.
Nominal 30 panels produce **31 intervals / 32 nodes**. The historical script's
`NODE I40` setting is different and does not establish discrete equivalence.

The historical 30 m/s row is identified from the explicit speed commands and
MATLAB's consecutive 0–56 m/s axis. The output's second column is an operating
index, not a measured speed. Its first row is not accompanied by an explicit
serialized zero-speed operating state. Historical gravity, altitude/atmosphere,
PG override and Earth attitude are not fully recorded. The close sag match
supports the transverse-gravity reconstruction but does not uniquely prove it.

This simplified literal model and gravity hypothesis remain separate from the
[primary-property zero-gravity experimental sweep](isae-ae1-sweep.md). The primary
authors' comparison neglects gravity, and gravity in an upright tunnel setup may
act spanwise. Neither those assumptions nor the earlier experimental discrepancies
are revised by the present agreement with archived solver output.

## Numerical verification and remaining work

Both requested states completed without retries or extra operating conditions:
**272/272 case/provenance checks** passed: 26 numerical gates and 246
checks of frozen source/input pins. Native case elapsed times were 0.823 and
1.620 seconds, including output and fresh-state verification on this host;
these are not browser timings. The fresh scaled residual maxima were
7.52e−14 and 1.16e−13. Root-pose gates passed. The worst relative global
force/moment balance defect was 1.23e−12. Relative balance is the L2 norm of
applied plus support resultant divided by the larger resultant norm, with
explicit handling of exact zero and no denominator floor.

The [independent saved-data audit](isae-ae1-literal-audit.json) passes
**244/244 checks** by reconstructing sensor poses and elevations from saved
positions/rotation matrices and recomputing residual bounds, root poses,
force/moment resultants and comparison metrics. It imports no production solver
and runs no physics. Source checks separately verify 127 pins. Both native
children exited successfully and were reaped; all 123 frozen execution pins
remained unchanged. Preparatory helper errors occurred before physics and are
retained with their corrections.

The next comparison should extend the unchanged model and assumptions across
meshes and the archived speed curves, then revisit experimental setup and
measurement uncertainty. There is no fitted coefficient, experimental passband,
stability result or family promotion here. The separate
[viewport recovery](isae-viewport-recovery.md) concerns display of a previously
computed primary-property result and adds no numerical states to this study.

The [machine comparison](isae-ae1-literal-pilot.json) retains metrics, numerical
gates, balance definitions and source pins. The
[evidence archive](isae-ae1-literal-and-viewer-20261025-evidence.zip) includes the
literal and derived source, exact diff, prospective protocol, complete conditions,
mesh, full native outputs, progress, independent audits and terminal receipts.
The [archive check](isae-ae1-literal-and-viewer-archive.json) verifies integrity
and extracted hashes; it does not rerun physics.
