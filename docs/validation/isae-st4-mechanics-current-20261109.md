# ST-4 published mechanical frequencies

The current OpenSwing solver matches **66 of 72 published ASWING frequencies
within 5%**, across all 24 configurations in ISAE Part III Table 6, p. 48.
Median absolute error is **0.2028%**. Twenty complete three-frequency sets pass.
The six failures have errors **5.556–19.703%**, median **14.073%**. No production
equation, original input, source frequency or tolerance was changed.

## What the comparison measures

The primary [scope](isae-st4-mechanics-scope.json) compares each complete
three-frequency set in ascending order. Each reference is used exactly once;
both nominal 64/128 meshes must pass. There is no nearest-target assignment,
selection of a better mesh, deletion of a mode or pooling of alternate inputs.
All original labels and input-position qualifications remain in the evidence.

This is an explicit comparison-method and progress-scope change. The 72-cell
named-mode plan preceded solving. The spectral comparison was added after
partial results exposed ambiguity in the provisional energy-based labels.
The original named-mode check remains **54/72**, unchanged: it requires a
torsion-dominant mode with more than half the strain energy in torsion.
That rule is not an authenticated definition of the report's labels. Several
mixed modes have matching frequencies but different labels under that rule;
the 7b/11-inch configuration fails its dominance test altogether. Native
ASWING eigenvectors are unavailable. Spectral agreement does not validate
those native mode identities.

The older **93/3,749 vacuum archive** remains separate, including all 3,656
unavailable outputs. The workbook, CSV, named-mode result, historical airflow
study and sensitivity inputs overlap with this scope and add no primary votes.
The original source entries and their denominators are preserved.

## Remaining frequency differences

These are ascending-rank comparisons of the complete three-frequency sets;
the middle and highest columns are not assertions of physical mode identity.

| Configuration | Frequency rank | Paper, Hz | OpenSwing, Hz | Error |
|---|---:|---:|---:|---:|
| Unloaded, original WING input | Middle | 40.54 | 32.7170 | 19.297% |
| Unloaded, original WING input | Highest | 48.8 | 39.1851 | 19.703% |
| 7d, 33 inches | Highest | 39.1 | 35.3117 | 9.689% |
| 7f, 24 inches | Lowest | 5.82 | 5.49663 | 5.556% |
| 7f, 40 inches | Lowest | 4.5 | 3.70067 | 17.763% |
| 7f, 40 inches | Highest | 34.9 | 38.5236 | 10.383% |

The original unloaded input predicts bending frequencies 6.5874/39.1851 Hz
and torsion 32.7170 Hz. The latter is 32.957% below the literal 48.8 Hz
torsion label. The rank comparison above deliberately does not rescue a
middle-frequency target by pairing it with the highest predicted frequency.

Three source findings constrain the remaining investigation:

* **Unloaded inertia:** Table 12, p. 53, and WING/W0M specify 0.0078 kg m.
  Original Weight7b files instead use 0.0035. NACA TN1594, printed p. 4,
  gives a whole-wing centroidal polar inertia of 0.0382 inch-pound-second²;
  division by span and unit conversion gives 0.0035400 kg m. The original
  unloaded driver names a missing `W0.asw`; the retained W0M is not that input.
* **7d at 69% span:** the printed first bending frequency resembles the
  33-inch CSV row, while its upper frequencies resemble the 39-inch row.
  The actual 39-inch input predicts 38.9846 and 21.3875 Hz, close to the
  paper's 39.1 and 21.4. Moving individual reference modes to that other
  model would mix physical configurations, so the original comparison stays.
* **7f positions:** the paper's 83%-span triplet resembles the workbook's
  32-inch row, rather than the supplied 40-inch case. The 32-inch input gives
  4.54216, 21.4915 and 34.9025 Hz, all within 0.94% of that paper triplet.
  The separate 24-inch workbook triplet repeats the 7c/21-inch values with
  the upper labels exchanged. That correspondence is suspect but remains
  unresolved; the original 24-inch model and reference values are retained.

These are evidence of setup/data correspondence problems, not proof of the
exact historical generating inputs. The supplied 35-inch model also differs
from the paper's printed 0.72-span position beyond ordinary rounding; its
three frequencies happen to pass, and the position qualification remains.

The subsequent [source-row audit](isae-st4-source-rows-20261109.md) strengthens
the position evidence using the paper's experimental columns, independently
of OpenSwing predictions. It also finds a 7.93% disagreement between the
7f/48-inch CSV entry and its directly paired native ASWING export. All 69
original ST-4 files are unchanged since the first public structural upload;
that history does not recover the missing unloaded input. The accompanying
plot preserves both conflicting sources. Primary values and passes are unchanged.

## Source-backed unloaded diagnostic

A separate two-mesh diagnostic changes only WING's distributed `mgcc/g` from
0.0078 to the **0.0035 already present in the original 7b files**. Other beam
properties, original mass coordinates, inertia-axis assignment and numerical
settings stay fixed. No frequency was used to choose the value.

It predicts **6.62131, 40.48285 and 48.87209 Hz**, reproducing all three
unloaded paper frequencies within **0.327% on both meshes**. Its 64
left/right matrix-equation checks and mesh/shape checks pass. This strongly
supports a different inertia in the historical unloaded run. It does not
recover the missing W0 input or reconcile Table 12, and **adds no primary
passes**. The original-input failures above remain.

The elementary uncoupled torsion estimate, `f = sqrt(GJ / I) / (4 L)`, gives
32.724 Hz with 0.0078 and 48.852 Hz with 0.0035. Thus the observed change has
the magnitude expected from the beam equations. The diagnostic preserves the
archive's assignment to `mgcc`; it does not claim that this uniquely identifies
the physical split of the two sectional rotary-inertia components.

## Numerical evidence and execution

All **32 parseable original models** were computed on both meshes: **64 states**.
Six verified earlier states were reused and 58 completed in the new continuation.
The interrupted earlier job and its receipt remain intact. W0M's missing final
Beam terminator and the absent W0 input remain explicit source limitations.

All 72 primary frequency/shape mesh checks pass: maximum frequency change
**0.08325%**, minimum shape MAC **0.9999076**. The independent six-state
implementation of the same discrete beam and point-mass equations reproduces
all 192 checked low frequencies within **3.69e−12 relative**. All **2,048**
left/right eigen-equation checks pass, with maximum residual **8.78e−12**.
Maximum equilibrium/mass check error is **4.45e−16** in its corresponding units.

All 31 frequencies in the five directly paired native exports agree within
0.745%, but only 20 pass the stricter 0.1% mesh-change gate. Higher-frequency
refinement was open at this 64/128 checkpoint. The subsequent
[128/192 refinement](isae-st4-native-refinement-20261109.md) passes all 31,
including independent continuous-reference and full saved-shape/matrix checks.
The old 20/31 result remains unchanged; neither overlap adds primary votes.
The separate named-mode workbook and CSV comparisons remain 59/81 and 67/96.

The **18 focused classification/accounting checks pass**, including rejection
of incomplete triplets, duplicated modes, invalid values, a failing coarse
mesh and inconsistent shapes. An independently written arithmetic comparison
agrees with the reusable spectral scorer on all 72 entries.

Jobs were serial, with one BLAS thread and the existing 512 MiB address-space,
15 CPU-second and 25 wall-second per-state caps. Maximum recorded RSS was
157,576 KiB. Main-study solver time totals 323.75 s; complete supervised
process time totals 727.58 s, including the six reused states. All 141
production modules retain their planned hashes. No browser/build job ran.

The [recurring-suite integration](isae-st4-recurring-20261109.md) is complete,
including a fresh full native-export replay. Native startup settings, mode
identity, historical input correspondence, airflow/flutter and the full paper
replay through the new adapter remain open. This is substantial evidence for the specified mechanical equations;
no whole-family or full-ASWING validation is claimed.

Evidence: [frozen original plan](../../artifacts/isae/st4-mechanics-resumed-20261109/plan.json),
[named-mode summary](../../artifacts/isae/st4-mechanics-resumed-20261109/summary.json),
[complete spectral comparison](../../artifacts/isae/st4-mechanics-resumed-20261109/analysis.json),
[continuation receipt](../../artifacts/isae/st4-mechanics-resumed-20261109/continuation.json),
[inertia diagnostic](../../artifacts/isae/st4-unloaded-inertia-20261109/summary.json),
[focused checks](../../artifacts/isae/st4-mechanics-resumed-20261109/focused-tests.xml).
Primary sources: [ISAE Part III](../../reference/aswing-authoritative-20261108/isae-part-3-structure.pdf),
[NACA TN1594](../../reference/isae-st4-primary/NACA-TN-1594.pdf),
[unit/source audit](st4-primary-setup.json),
[authoritative reference catalog](aswing-authoritative-sources.json).
