# AE-3: actual rigid-wing comparison with native AVL

Observed 2026-11-11 UTC. The literal rigid AE-3 geometry and control input now
agree with native AVL on both existing meshes: matched circulation differs by
at most **4.34 × 10⁻⁹ relative maximum norm**. All **26 numerical and geometry
checks pass**. This supports the current aerodynamic implementation for these
conditions; it does not validate the flexible archived ASWING case.

The primary comparison remains **50/725 at 5%**: 72 computed values,
22 mismatches and 653 uncomputed targets. No production equation, original
model, tolerance, mesh default or comparison denominator changed.

| Quantity | Nominal 80 (82 intervals) | Nominal 160 (162 intervals) |
|---|---:|---:|
| Native AVL rolling coefficient, ASW stability axes | −0.001818151153 | −0.001816826932 |
| OpenSwing total, original receivers | −0.001783613530 | −0.001794644180 |
| Difference from native AVL | 1.900% | 1.221% |
| OpenSwing total, matched native receivers | −0.001807101989 | −0.001805759265 |
| OpenSwing circulation-force moment, matched receivers | −0.001812931788 | −0.001811589176 |
| Native fields evaluated with ASW force/arm conventions | −0.001812931780 | −0.001811589169 |
| Difference after matching force/arm conventions | 0.000000397% | 0.000000397% |
| Matched circulation relative maximum difference | 4.336 × 10⁻⁹ | 4.339 × 10⁻⁹ |
| Maximum receiver displacement | 0.1175 mm | 0.02938 mm |

The rigid-wing numbers are compared with native **AVL**, not scored as matches
to the archived flexible **ASWING** result. The first archived flexible rolling
coefficient remains −0.002056; the corresponding current flexible results are
−0.001562894 /−0.001575255. The substantial native-ASWING discrepancy remains.

![Matched AE-3 circulation](../../artifacts/isae/ae3-native-avl-r2-20261111/circulation.png)

## What was matched and checked

The [authoritative index](aswing-authoritative-references.md), its checksummed
catalog, Jan Part IV §3.3 pp.10–13, Drela's steady formulation and the retained
AVL documentation/source govern the conversion. This uses the actual literal
`Straight_20O.asw`, F1=+1, zero alpha/beta/rates and PG Mach zero. Reference
area/chord/span remain 0.185/0.15/1.2192, with moment origin at zero. OpenSwing
uses 27.0934 m/s; AVL's velocities and circulation are normalized by freestream
speed. No stall occurs in either OpenSwing diagnostic.

The original ASW node arrays include the root and aileron breaks. Four AVL
surface bands share one physical component. Each original interval becomes one
spanwise AVL interval, with one chordwise row. Streamwise chord is normal chord
divided by the magnitude of the cross product of the body-x direction and beam
tangent. `CLAF=dCLda/(2*pi)` follows AVL's documented section-slope prescription.
Control input is represented by the equivalent section-normal incidence from
Drela's Eqs.158–159; it is **not** a claim of equivalence to a physically hinged
AVL flap model.

Native exported bound endpoints match the original ASW endpoints exactly.
Native receiver/control-point coordinates are also matched in a separate
OpenSwing calculation, to within 4.2 × 10⁻¹⁷ m. Original production-generated
receiver results remain alongside it. This distinction matters: the different
receiver rules produce maximum circulation differences of 7.81% /4.09% before
matching, while the integrated total rolling moments differ by 1.90% /1.22%.
Those original discrepancies are retained, not erased by redefining the mesh.

Native normals are reconstructed from the converted input. A separate native
operator transcription reproduces native circulation and induced fields to
approximately roundoff. Replacing only those normals with ASW's section
normals changes circulation by less than 5 × 10⁻¹⁵ relative in this planar case:
the different spanwise normal components do not contribute to its flow-tangency
condition. This conclusion is specific to the tested geometry and flow.

The native executable retains its tiny same-component quartic core and rounded
Biot–Savart constant. OpenSwing retains its documented zero core on the same
physical surface. Neither convention was changed to improve the comparison.
The existing native instrumentation adds output only; 395 native source files,
build objects, original binary and instrumented binary were verified.

## Why the rolling moments are not identical

Native geometric-axis Cl is +Mx/qSb; ASW stability-axis Cl at alpha zero is
−Mx/qSb. That sign transformation is explicit and checked by reconstructing
native forces and moments from its exported circulation and induced velocities.

Even with identical circulation, AVL applies the force using the bound-vortex
vector and native bound receiver. Drela's ASW section law uses the beam tangent
and interval length, with the local quarter-chord moment arm and intrinsic
section pitching moment (steady Eqs.72–73). The present conversion supplies no
intrinsic section Cm to AVL. The table therefore separates these terms.
After transferring native fields to the ASW force vectors and arms, the
circulation-force rolling moment agrees within 3.98 × 10⁻⁹ relative. The remaining
ASW intrinsic moment contribution is approximately +5.83 × 10⁻⁶ in Cl.
These accounting checks do not justify replacing either solver's force law.

## Execution and next step

Both numerical workers exited zero and were reaped. They ran serially with one
BLAS thread and unchanged limits of **512 MiB address space /15 CPU seconds
/25 wall seconds**. Observed CPU times were 3.43 /3.64 seconds, wall times
19.07 /15.28 seconds, and peak resident memory approximately 90 /101 MiB.
These include imports, checking and diagnostic work; they are not browser
performance measurements. Fresh circulation residuals are below 3.8 × 10⁻¹⁷.

The first attempt timed out before generating AVL input or launching AVL. Its
[terminal receipt](../../artifacts/isae/ae3-native-avl-20261111/cases/m80/terminal.json)
and original driver remain intact. The successful driver moves repeated full
archive/build verification outside the numerical deadline, checks runtime
sources inside it, and records execution phases. The parent verifies all source
pins before and after each solve. The resource limits were not raised.

The next useful constraint is the archived **local control derivative** and its
relationship to the finite F1=1 result, using the quasi-steady elastic response
specified in Drela §8.4, pp.51–52. Establish that calculation before scoring the
currently unavailable derivative slots. Continue auditing the documented
control coefficients and historical setup; the preceding
[input investigation](isae-ae3-control-setup-20261111.md) retains the report/model
conflict. No coefficient fit, assumed historical input or derivative inferred
from a finite coefficient is adopted. Original ASWING, ASWING-m and experiment
remain distinct. Browser/build checks remain held.

[Prospective plan](../../artifacts/isae/ae3-native-avl-r2-20261111/plan.json) ·
[Assessment and receipts](../../artifacts/isae/ae3-native-avl-r2-20261111/assessment.json) ·
[CSV](../../artifacts/isae/ae3-native-avl-r2-20261111/comparison.csv) ·
[Vector plot](../../artifacts/isae/ae3-native-avl-r2-20261111/circulation.svg)
