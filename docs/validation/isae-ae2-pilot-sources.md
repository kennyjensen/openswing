AE-2 source preparation, 2026-10-25

A useful next comparison is the literal vertical `[03_90].asw` at root incidence 5° and scripted indicated speed 10 m/s. The archived sensor row gives RY = −0.0258200 m and Psi = −0.572223°, hence plotted displacement +0.0258200 m and total tip angle 5.572223°. This is a conditional comparison with archived ASWING output. It does not establish a matched experimental validation or recover the original producing state.

The separately identified experimental point is the uncoupled wing's `ALPHA_1_W` sample at 9.057511458580507 m/s, digitized midchord tip deflection 0.001581596333254276 m, CSV line 4 columns 3–4. Retain its raw coordinate and value; do not average it with the strain-derived series or replace an earlier nonzero sample by zero. No simultaneous twist observation is asserted. The root’s proposed pilot evaluates both conditions on nominal 40/80/160 meshes. No solver was called in this preparation.

The primary experiment is [Dunn's 1992 MIT thesis](https://dspace.mit.edu/entities/publication/55aa429a-7a4a-4908-87e6-7ecc1ece5ae5), sections 4.5 and 5.2.3 and Figures 24, 27, 29 and 31. Its averages include both static preflutter and oscillatory postflutter measurements. Hollow symbols are video observations; solid symbols are estimates converted from root strain measurements using an assumed load shape. They are distinct methods, not replicate uncertainty bounds. The low-speed 1°/9.06 m/s and 5°/10 m/s conditions lie well below the uncoupled experimental flutter boundary shown in Figure 24. No precise new digitization of that boundary was performed.

The three main vertical files represent uncoupled, positive-angle and negative-angle laminate variants. They all misleadingly share the internal name `[0_3/90]_s`; paths and hashes identify the actual inputs. All use a 0.558 m vertical span, 0.14 m chord, material domain 0.0001–0.558 and a full root clamp at physical z=0. The chord multiplier sets Xax=0, making the beam reference axis the leading edge. One sensor is at the tip midchord point (0.07,0,0.558) m. The secondary report's claim of a leading/trailing-edge sensor pair is inconsistent with these literal files.

| Variant | EIcc | GJ | EInn | EIcs |
|---|---:|---:|---:|---:|
| Literal uncoupled | 1.4163 | 1.0 | 2.5 | 0 |
| Report uncoupled | 1.4163 | 1.2 | 18499 | 0 |
| Literal positive | 1.29 | 1.2 | 25000 | 0.250 |
| Report positive | 1.2947 | 1.2 | 22775 | 0.5151 |
| Literal negative | 1.42 | 1.2 | 25000 | −0.551 |
| Report negative | 1.2947 | 1.4 | 22775 | −0.5151 |

These beam rigidities have units N m². Primary laminate plate D coefficients have units N m and cannot be substituted directly. Keep report-derived and literal models separate; no property fitting or silent substitution is justified. ST-3 states and properties are also different and cannot be reused simply because the layup labels match.

The two remaining `.asw` files are horizontal alternatives with different physical definitions. The flat file's sensor is at the root and its clamp is interior to its material domain. The other alternative ends with an unterminated Engine block and is the one rejected import. Neither is a replacement for the three vertical models. Authoritative coverage remains four imports available, one rejected, physical comparison pending.

All 12 scripts specify a solid image plane with Earth normal +z and anchored defaults. Root incidence is entered as ASWING beta because the wing is vertical. `!V` specifies indicated speed; `+` adds a point to the stack and final `XX` solves the entire stack, including its last declared speed. All script stack counts match their archived output counts. The source inventory contains 275 output rows, with one all-NaN initial row in each sweep. Those 12 missing states must remain missing.

The exact output comparison is uppercase Earth RY versus `sensor.position_earth[1]`, and Psi versus sensor heading. The archived plots use −RY and requested beta minus Psi. Do not substitute anchor displacement, elevation, aerodynamic incidence, or a baseline-subtracted coordinate. The plot's horizontal coordinate is sensor V, which differs from requested indicated speed. At the selected archived row it is 10.0115 m/s and local sensor beta is 6.27943°.

The six experimental CSVs contain 48 series and 585 raw points, with B/W coordinates retained separately. The negative-layup T CSV is scaled by 100 in the archived MATLAB reduction; primary Figure 31 confirms a degree axis and near-zero-speed levels 1°, 5°, 10°, 15°. Record that conversion explicitly alongside raw values. The upstream MATLAB's forced first deflection zeros, B/W averages and half-difference bars are not a defensible replacement for the raw observations.

The historical K/F influence choice, K/M Mach setting, exact mesh/circulation settings, Earth pose, atmosphere and executable identity remain unproven. No `.set`, `.pnt` or `.con` files were found within this archived family, although ASWING documents automatic loading of such files. Their absence from the archive does not establish their absence in the original working directory. The primary experiment used a finite pedestal cover disk; the scripted ideal infinite wall remains a model approximation.

The earlier nominal-40 attempt failed on wall intersection before a full residual and never attempted 80/160. Current `wall_root.py` admits the declared full endpoint chord with parallel steady unpowered wind. Root's separate readiness report now records six successful constructor/clearance checks with zero residual, aerodynamic, derivative or solve calls and 41/81/161 actual elements. This removes that specific setup blocker without proving convergence or experiment agreement. The beta5 readiness checks used Mach0; the proposed beta5 pilot declares Mach10/340.21 instead. That change must remain explicit in the final pilot contract.

The next pilot can therefore provide meaningful conditional numerical/model evidence using the exact literal input. Density1.23 kg/m³, zero altitude, gravity9.81 m/s², identity Earth frame, zero F1, pointwise circulation and updated influence matrices are declared reconstruction settings. They must not be described as recovered experimental or historical inputs. A fully matched experimental baseline remains blocked by specimen-property correspondence, atmosphere/speed definition and the other setup qualifications above.

Preparation verification: 701 source assertions passed. All 45 archived reference pins from the previous preparation remain exact; 47 of its total49 pins match, with only the mutable coverage ledger and current geometry implementation changed. No production imports, physics calls, production changes, repository documentation changes or validation promotion occurred. `source-pins.json`, `inventory.json`, `baseline-plan.json` and `source-report.json` preserve the mappings and provenance. Primary thesis contents and rendered review images are local-only evidence and must be excluded from redistributed archives.
