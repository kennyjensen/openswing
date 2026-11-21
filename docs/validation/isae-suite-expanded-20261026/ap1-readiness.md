# AP-1 next-adapter readiness — source only

The archive supports **six literal model/driver/span-output pairs, containing 900 rows**, but a complete unchanged-input adapter is not ready. Three `PROWIMd` states explicitly have zero lift slope, which current lifting aerodynamics rejects. The source coupled structural operator also rejects engines, while rigid aero does not return the archived internal resultant fields. No solver, residual, production import, browser or experimental comparison was run.

All 22 original AP-1 files match the pinned archive manifest (revision `f62943df20e9e4d7d9f50e070477b22426b5f865`). Full paths/hashes are in `source-pins.json`; every numeric export row, original token and printed precision is in `rows.json`.

| Literal model / driver | Written outputs | Rows × columns | Incidence |
|---|---|---:|---|
| `Aswing_Simulation/PROWIM.asw` / `PROWIM.sh` | `PROWINA0.txt`, `PROWINA4.txt`, `PROWINA10.txt` | 3 × 150 × 9 | 0°, 4°, 10° |
| `Aswing_Simulation/PROWIMd.asw` / `PROWIM_d.sh` | `PROWINA0d.txt`, `PROWINA4d.txt`, `PROWINA10d.txt` | 3 × 150 × 9 | 0°, 4°, 10° |
| No recovered generating write | `PROWIN.txt` | 100 × 10 | Header 0°; power/setup unpaired |
| No recovered generating write | `PROWIM.t` | 1 × 3 (`i,t,CL`) | Incidence/power unpaired |

The six paired tables contain 7,200 non-`t` field slots plus 78 global output scalars. The unpaired tables add 900 non-`t` span fields, 13 header outputs and one CL target. Thus all 1,001 archived span/operating rows remain accounted for; no negative-span, stall or zero rows were discarded. The MATLAB plotter merely reads these tables and compares experimental curves; it supplies no missing solver state.

## Recoverable operating inputs and power semantics

Both drivers specify `NODE / I 150`, speed 50, `!E1 500`, and `!E2 333`; later writes repeat E1=500. The first write does not specify alpha, but its archived header explicitly reports zero. All six headers report beta zero, sea-level altitude, no rates/accelerations, zero flap, and **MachPG=0**. Literal density is 1.2256 kg/m³; header dynamic pressure 1532 Pa confirms it. Physical Mach 0.1470 is separate from the PG setting.

Both engine records use **KPeng=1, type 1**. Therefore 500 W applies to each disk: it is not split, and 333 is not the second engine's power. Current `validate_engines` rejects undeclared key 2. A future adapter must retain `!E2 333` in source provenance while explicitly forwarding active `powers={1:500}`. Exact historical handling of that unused command is not recovered. The ±1 N·m resultant jumps at the two engine stations independently support the paired 500 W / 500 rad/s interpretation and the output scaling.

`PROWIM` uses engines at (-.23, ±.3, 0), with Ω=+500/-500 rad/s. `PROWIMd` moves them to x=-.201 and reverses the signs. Both use radius .118 m, thrust direction (-1,0,0), and drag area .00044874 m². **Omega is rad/s, not RPM**; the original propeller report expressly says 500 rad/s. There is no recovered pitch or RPM governor. The `d` input also changes dCLda from 5.72 to **0 at both knots**; neither position nor lift-slope differences may be repaired or treated as mere spin reversal.

Primary locators: `aswing_doc.txt:668–715,2064–2065`; `asw_theory.txt:1004–1016,1131ff`; original propeller report text `:1229–1241`. Source-read implementation: `propulsion.py:11–24,66–72`; `aero.py:418`.

## Output mapping and normalization

The paired columns are `t,y,z-z0,tw-tw0,Mc'/10,Ms'/10,Fn/10,cl,a_flap`. Only Mc, Ms and Fn use the printed powers of ten in header line 31: A0 uses (0,-1,0), A4 (1,0,2), A10 (1,1,2), for both models. Internal moments are local c/s components in N·m, force is local n in N; displacement is m and twist is degrees. `PROWIN` adds `f_aero` and uses (0,0,1). Its adjoining signed fields require a fixed-width or validated numeric-token decoder, not plain whitespace splitting.

The guide locates state/resultant quantities at nodes and shifts derived `cl`/`f_aero` upward by half an interval, with a dummy zero in the last row (`aswing_doc.txt:2537–2600`). Do not compare `cl` directly at its same-row printed `t`/`y`, as the plotting script does. Retain both one-sided root/engine rows and all rounded coordinate duplicates. Paired coordinates have half-place uncertainties .005 m in t and .0005 m in y. Counts and attachment repetitions are consistent with NODE/I150 structural output, but saved display/startup settings and exact unrounded nodes are absent. The extra `a_flap` column is everywhere zero; its nonzero semantics, units and sampling are not established by the reviewed primary display list.

Preserve literal Sref=.1536 m², Cref=.24 m and Bref=.64 m although mirrored full span is 1.28 m. The plot coordinate is y/.64 (2y/full geometric span), not y/1.28. Do not repair these reference values or clamp span efficiency above one.

**Aerodynamic coefficients must be separated from net engine-inclusive forces.** Source Eq185 defines aerodynamic-only Lift. At alpha zero, archived CD=.03630 implies aerodynamic drag 8.542 N, whereas archived net Fx is -6.756 N; directly using current result CD would compare different quantities. Current `distributed_aero_force` exposes the necessary separation (`aero.py:659,683–688,782–810`). A prospective mapping projects that force into freestream lift/drag and retains net Fx/Fy/Fz separately; exact historical exporter code remains unavailable. Trefftz efficiency uses CLi/CYi, not necessarily printed average CL (source Eqs207–211).

## Smallest defensible next step

1. Add a dedicated source-only decoder/canonical plan for all six pairs and two unpaired records. Preserve every field and the independent printed-coordinate qualifications. The generic polar worker neither forwards powers nor models this output schema; the ST3 span decoder hardcodes incompatible exponents.
2. Establish the full resultant recovery route. `solve_rigid` can exercise unchanged positive-slope PROWIM aero at all three incidences, including local cl and separate aerodynamic/engine wrenches, but cannot certify Mc/Ms/Fn. Legacy mounted `StaticNetwork` has engines and is a potential explicitly different operator route requiring a trace/sign audit. Source coupled engine support is absent (`source_coupled.py:34–35`).
3. Keep all three PROWIMd states blocked by explicit zero dCLda (`aero.py:321`), until primary evidence or a physically justified algorithm establishes its semantics. No default-2π substitution. Keep `PROWIN` and `PROWIM.t` unpaired; `PROWIN` has ±6 N·m attachment jumps, unlike the paired ±1 N·m states.

If two current meshes are later declared, there are 12 paired mesh jobs, 14,400 non-t span slots and 156 global output slots; half of the case jobs inherit the zero-slope blocker. Nominal current 150/300 **intervals** would be a reconstruction, not the original 150-node grid. Historical K/F, core/startup state and jet direction remain conditional (`aswing_doc.txt:761–765,1574ff`). No gate, runtime estimate or reference pass has been selected by this audit.
