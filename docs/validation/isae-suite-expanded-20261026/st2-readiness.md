# ST-2 original-ASWING adapter readiness

**No unchanged-input execution route is ready.** There are two original modal exports and one static span export, but all six retained models have actual Weight anchors at **t=.558 outside the [.0001,.55] beam domain**. Current source static and dynamic constructors retain this rejection. The new station alias resolves only mathematically equal decimal coordinates; it cannot equate .558 with .55.

All 146 original files are pinned and verified against the archived revision. No production imports, model solves or old report regeneration were performed. The bounded parser correction below has 21 passing source-only tests.

| Original target | Candidate input | Required numeric coverage | Pairing limit |
|---|---|---:|---|
| `01_Modal_Undeformed/Pazy_wing.e00` | Same-folder `Pazy_wing.asw` | 7 complex rows / 14 components | No driver, saved base, gravity/medium, mesh or selection settings |
| `02_Modal_Gravity/Pazy_wing.e00` | Same-folder `Pazy_wing.asw` | 7 complex rows / 14 components | Same limitation; folder name is not an executable setup |
| `03_Static_Structural/temp.txt` | Strongest candidate: retained 3 kg bending model | **46 rows × 9 columns**, 368 non-t fields | Both bending and torsion drivers overwrite this filename after MATLAB changes the models |

The native exports contain **60 rows and 396 non-coordinate scalar targets**. Two workbooks add ten separately qualified ASWING-labelled frequency cells; they must not replace the fourteen higher-precision complex targets. All other ordinary Beam/GFEM shape, frequency and sweep files are identified by the original READMEs as UM/NAST or finite-element results, not ASWING exports. The 77 experimental static observations are also separate targets.

## Static pairing and fields

`temp_analysis1.sh` launches the bending model and `temp_analysis2.sh` the torsion model; both run `PLPA g`, `OPER x`, then write `temp.txt`. Neither preserves NODE or explicit operating constraints. `change_mass*.m` rewrites the Weight records before each run. The retained bending input has two 1.5 kg loads at x=.05, y=.558; its total weight including .3745 kg/m over .55 m is 31.45061475 N, consistent with the exported 31.45 N. The retained torsion inputs have different loads/positions. This supports a final bending-state inference, not a unique generating-byte proof.

Retain `t,y,z-z0,tw-tw0,Mc'/10,Ms'/10,Fn/10,cl,a_flap`. The resultant powers are **(1,0,1)**: multiply Mc and Fn by ten, leave Ms unchanged. Displacement is metres, local Euler twist degrees, moments N·m and force N. Preserve source tokens and their rounding intervals. The guide's node/interval distinction and last derived dummy apply; the extra all-zero `a_flap` column lacks independently established nonzero semantics. Do not substitute experimentally projected chord twist or negate the archive's local twist.

The former `archive_profile` reader skipped 34 lines although numeric rows begin on **line 33**. Consequently, the historical report contains only 44 rows and omits t=.0001 and .00118. Its “all printed stations” wording overstates coverage. The MATLAB tip reader has the same skip count but uses only the final row, so its tip extraction is unaffected.

The correction adds `scripts/isae_st2_archive.py`, a strict stdlib header/separator parser retaining every row, all nine tokens, printed precision and physical resultant scaling. `summarize-isae-st2.py` changes only its import and loader call. **Historical JSON and plots remain untouched**; the parent separately corrected the Markdown coverage wording after these tests. The existing three-quantity y/z/twist comparison is not relabelled as full-field validation.

## Modal targets and existing helper limits

Each `.e00` header specifies frequency as eigenvalue modulus/(2π). Keep the seven positive-imaginary roots in each file, including the tiny printed real parts; no full-spectrum or branch labels are supplied. Matching basename/title/location supports candidate pairing only.

The only workbook ASWING columns are `01_Modal_Undeformed/00_Comparisons/GFEM_vs_Beam_VS_ASWING.xlsx` I11:I15 = **4.59, 29.1, 43.4, 128, 81.4 Hz**, and `02_Modal_Gravity/00_Comparisons/GFEM_vs_Beam.xlsx` G3:G7 = **4.67, 29.2, 43.2, 116, 81.4 Hz**. Their B labels are OOP1,OOP2,T1,IP1,OOP3; adjacent D labels swap the last two. Report tables repeat these values, so they are not independent targets or proof of `.e00` branch mapping.

`isae_st2.static_model` replaces Weight blocks and attaches them at .55; `modal_model` removes two zero objects. The static verifier runs these explicit reconstructions against experiments and an independent rod reference. The modal verifier runs derived models against a Rayleigh reference, with declared meshes/gravity choices; it does not compare the `.e00` files. Reusing either worker unchanged would silently change this task's target and input scope.

## Concrete next step

Register the three native exports as blocked records covering all 396 non-coordinate fields, keep the ten workbook summary cells separate, and retain all six model records. First recover or justify the original attachment handling; do not clamp anchors or remove objects while claiming literal replay.

Once that prerequisite and the static source pair are established, current `drela-steady-section-v1` supports the coupled stiffness, offsets, gravity and rotating pylons, and `drela-fixed-vacuum-v1` provides a potential fixed-frame modal route. Explicit base gravity/medium and mesh/selection assumptions would still be required. No new missing kernel has been demonstrated, and no expensive run or tolerance choice is justified by this audit alone.
