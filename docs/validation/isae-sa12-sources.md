# SA-12 ground-effect source audit

**This source audit is not a validation pass.** Both original inputs construct unchanged. The archive contains six 85-point polars, 75 digitized lift measurements and 71 digitized drag measurements. All 28 upstream files pass their pinned Git blob, SHA-256 and byte-count checks.

The primary experiment is [Recant, NACA-TN-705](https://ntrs.nasa.gov/citations/19930081443). Its flap geometry points to [Wenzinger and Harris, NACA-TR-664](https://ntrs.nasa.gov/citations/19930091739). The rectangular NACA 23012 wing has span 1.524 m, chord 0.254 m and aspect ratio 6. The ground height is measured at its quarter chord. The flapped model represents a full-span 40-degree slotted flap through fixed section properties.

| Input | Section alpha | dCL/da | CLmax | Cdf |
| --- | ---: | ---: | ---: | ---: |
| no_flap | 0 | 6 | 1.5 | 0.01 |
| slotted_flap | 12.5 | 7.44 | 2.6 | 0.04 |

The scripts prescribe 35.76 m/s, solid ground and heights 0.127, 0.508 and 1000 m. They do not archive Euler pitch. A physically matched tunnel setup requires the freestream parallel to the board; the supplied incidence datum and actual archived pose must be distinguished.

The primary precision table states estimated bounds: angle ±0.1 degree, CL ±0.001, CLmax ±0.005, CD ±0.001, unflapped CDmin ±0.0005, Cm ±0.001, flap angle ±1 degree and height ±1/16 inch. These bounds do not cover digitization or every setup/property error.

The no-flap close-ground drag plot uses `0.01 + CDi` in the original MATLAB postprocessing. That display correction is not raw solver drag and is not applied silently here.

Outstanding source/setup issues:

- Both literal models parse and construct. The flapped input changes fixed section alpha, dCLda, CLmax and Cdf; its geometry and control derivatives do not represent a deflected flap. No input repairs are made.
- Ground in the asw file specifies a structural constraint. Solid-ground aerodynamic images are enabled separately in the six command scripts.
- The reference height is at the quarter chord. Source Xax=0.25 and x=0 place it at the body origin. Heights 0.127 and 0.508 m represent h/c=0.5 and 2; the nominal infinity script retains an image at Rz=1000 m.
- The tunnel flow is parallel to the ground board. The source scripts prescribe alpha and Rz but do not record Euler pitch; their nine-column archives cannot establish the actual pose. Pitch=alpha aligns freestream and board for the supplied input; zero pitch is a separate diagnostic.
- All scripts toggle K/F once. The documented default is frozen, but the actual startup state/settings files are unavailable. No exact archived mode count or PG setting is recorded.
- NODE I 100 is explicit, but node versus interval counting, feature stations and Fourier truncation require separate reconciliation. A request for 100 intervals is not proven to reproduce that mesh.
- The no-flap infinity script omits the explicit anchored-defaults command found in the other five scripts.
- All six source sweeps skip 11.25, 11.5, 11.75 and 12 degrees. Every stored row is retained; the missing reference data are not invented.
- ISAE describes plain-wing lift coordinates shifted to zero lift. The input section alpha is 0 although the report cites a physical section zero-lift angle of -1 degree. No fitted angle shift is introduced. The chord versus zero-lift datum needs reconciliation for pitch relative to the ground.
- Only the close-ground no-flap drag display replaces total CD by 0.01+CDi. The report describes disabled post-stall drag, but the command scripts do not record such a toggle. Raw total CD and this fixed display transformation remain separate.
- Plain-wing and slotted-flap section constants are described as obtained from two-dimensional experiments; the included XFOIL CSV is not the stated source of these constants.
- The literal flapped file is an equivalent single lifting line. It cannot resolve the slot, flap-ground interaction or changing section behavior with ground proximity.
- Both inputs set section Cm=0. The measured flap pitching-moment curves in the primary report are not represented by those properties, and no experimental Cm CSV is supplied. Agreement with the archived near-zero Cm would not validate the physical flap moment.
- The equivalent straight chord does not reproduce the actual deflected flap tip. Its computed geometric clearance is not the physical flapped-wing clearance.
- Primary estimated errors do not include CSV digitization uncertainty, source-property mismatch or all apparatus effects. They are not standard deviations.
- The primary uses Reynolds number 609,000, effective Reynolds number 974,000 and a stationary board. The two-dimensional section reference has different Reynolds and tunnel conditions. Parameter provenance alone does not establish agreement.

All originals, commands, CSV row mappings and primary pins are retained in [the source data](isae-sa12-sources.json). The upstream shell and MATLAB programs have not been executed.
