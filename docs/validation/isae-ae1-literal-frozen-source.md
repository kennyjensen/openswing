Read-only aerodynamic source audit, 2026-10-25

The frozen versus updated aerodynamic-influence setting is the strongest supported candidate for the growing high-speed discrepancy. This identifies a documented modeling choice to test; it does not identify the historical setting. No aerodynamic law defect was established by this audit.

The independent checks pass 905/905: source and result identities, literal multipliers, script commands, and saved diagnostic consistency over all 98 nominal-120 airflow states. All 292 pins from the accepted corrected full-curve plan still match. The audit made no production imports, aerodynamic evaluations, residual calls, tests or solves. It retains 400 file pins in `source-audit.json`.

Documented setting and historical evidence

Drela's [User Guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt) displays K/F as true. It describes the frozen choice as undeformed geometry with zero wind angles, and the updated choice as recalculating coefficients for current geometry and wind direction. The archived scripts never enter K. Current saved results explicitly report `frozen:false`. The guide also documents automatic loading of matching settings and operating-point files when starting with a case name. No Pazy `.set`, `.pnt` or `.con` is archived. Thus the displayed menu is evidence for a candidate, not proof of the historical flag. The invocation refers to a local `AswingMAC_forced` executable whose exact implementation is unavailable.

The frozen diagnostic prospectively reviewed here selects four conditions (5°/30, 5°/56, 7°/30, 7°/42) at nominal 60 and 120. Every case differs from its pinned prior input only by `freeze_influences:false→true`. The 215/215 plan checks confirm eight cold states, identical physical inputs, no restart states, 120-second child caps, at most two children, no retries, and the existing 0.1% mesh gates. No solver results from that prospective diagnostic are claimed here.

The setting can plausibly produce a discrepancy that grows with deformation: it changes where and how induced-velocity coefficients are evaluated. It must remain distinct from caching or lagging a Newton derivative while retaining the same full residual. Current `frozen_influence.py` explicitly reconstructs jig meshes and x-directed wakes; `aero.py` retains current section frames, circulation and loads. Agreement after toggling this approximation would support a setting explanation, without proving that the archived executable used it or that it is more physically accurate.

Literal aerodynamic data and equation correspondence

Independent multiplication of the archived table gives constant chord 0.10 m, Xax 0.5, dCLda 6.1185/rad, CLmax 1.1 and CLmin −1.1. Cdf, Cdp, Cm, zero-lift alpha and twist are absent; the parser's zero defaults agree with the guide's property table. The first material coordinate is 0.0001, preventing automatic full-wing mirroring; physical root y is zero. Both scripts explicitly select a solid image plane with Earth normal [0,1,0]. Saved conditions and results preserve that wall and an identity Earth pose.

The [steady technical description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf), equations 67/70/72, uses vector lift, velocity-directed profile drag and a quarter-chord moment. Equations 155–158 define the wind-directed bound/control-point offsets and rotated section normal. Equations 202–204 give the smooth stall-leakage model; stall reduces the slope rather than hard-clipping CL. The current corresponding expressions in `aero.py` and `frozen_influence.py` match these formulations on inspection. The supplied slope sets control-point spacing; it is not an instruction to apply a globally linear CL curve with fixed force direction. This is a scoped equation correspondence, not a proof of the complete solver.

Saved strip evidence

| Fine case | Maximum local CL | Maximum leakage-angle equivalent | Saved CDp |
|---|---:|---:|---:|
| 5°, 30 m/s IAS | 0.5011214 | 0.000117683° | 9.4754e−12 |
| 5°, 56 m/s IAS | 0.5532763 | 0.000333981° | 6.3619e−11 |
| 7°, 30 m/s IAS | 0.6973665 | 0.00595948° | 2.2325e−8 |
| 7°, 42 m/s IAS | 0.7165904 | 0.00875291° | 4.4944e−8 |

No strip crosses the literal ±1.1 limits anywhere in the 98 fine states. The table's leakage diagnostic evaluates only the documented scalar function at saved CL, then converts Ks·fstall/dCLda to degrees. It is a velocity-ratio equivalent, not an actual incidence or solved sensitivity. The smooth law has a small nonzero tail inside the limits, so calling stall exactly inactive would be incorrect. Its particularly small 5° tail and saved drag contribution provide no support for missing stall or viscous drag as the principal 5° high-speed explanation.

Other candidates and limits

- The wake-core law is consistent with the documented max(chord fraction, interval length) rule. This one-physical-beam case selects zero core for its own receiver interactions, including their images. Changing the nominal 0.25 core ratio therefore is not a supported mechanism for these structural loads. External probes use finite cores, but do not feed back on this case.
- All saved cases have zero circulation rates and apparent loads. The unsteady-lag toggle therefore cannot explain this steady comparison.
- The current PG setting is fixed zero. At 5°/56, ambient Mach is 0.164604 and maximum section-normal Mach is 0.171734; the corresponding ambient PG scalar, if selected, is about 1.01383. Cm is zero. Historical PG/altitude settings remain unknown. These scales alone are not a rigorous bound on a coupled displacement sensitivity, so compressibility is a secondary unresolved setting, not a proven cause or exclusion.
- Commands specify IAS. The current rho=rhoSL=1.23 makes IAS and true speed equal. Do not change the source coordinates to guessed true airspeeds. Under this steady, incompressible, rate-free model, preserving IAS also preserves reference dynamic pressure; simply rescaling density at fixed true speed would test a different command. Historical atmosphere remains unrecorded.
- Scripts request nominal 40 intervals; current 60/120 convergence controls OpenSwing discretization, not the unknown historical mesh details. The archive stores tip sensor observables, not aerodynamic coefficients, forces, or convergence diagnostics, so it cannot isolate individual load terms or prove historical convergence.

All previous source qualifications remain: RX/RZ are Earth coordinates; the first archived state is unresolved; each displacement series uses its own baseline; the primary reported angle is absolute sensor elevation. No new experimental pass band, calibration, stability claim, or validation-family promotion follows from this audit.

Local source locations: `aswing_doc.txt` lines 1133–1201, 1561–1587, 2239–2312, 2413–2461, 2634–2673; `asw_theory.txt` equations 67/70/72, 155–158, 161, 169/173, 176, 202–204; `openswing/aero.py` lines 176–194, 264–280, 314–370, 454–471, 549–587; `openswing/frozen_influence.py` lines 14–48 and 59–95. Exact file hashes are retained in the JSON.

Two audit-only first attempts are retained in `preparation-history`: an overly literal whitespace check for `!A   7.0`, and an overly specific supervisor syntax check. Both were corrected after inspecting the unchanged source; no scientific input, output, or production file changed.
