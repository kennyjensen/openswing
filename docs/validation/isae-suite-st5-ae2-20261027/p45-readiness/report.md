P4/P5 source audit: no complete input set is yet executable.

| Family | ASW series | Stored slots | Finite targets | Unavailable axis values | Separate ASW-m slots | Experimental finite/stored |
|---|---:|---:|---:|---:|---:|---:|
| P-4 | 20 | 2000 | 1990 | 10 | 2000 | 2172/2540 |
| P-5 | 16 | 1600 | 1592 | 8 | 1600 | 2095/2456 |

The unmodified model curves pair into 1,000 P4 and 800 P5 receiver rows (axial and swirl at each stored radius/station). Experimental curves have different digitized radial grids and are not merged into these receiver counts.

All eight original FIG hashes and cached extraction hashes verify. Raw curves and NaNs are retained. No repeated graphic series within the same file/model/station/component was found; duplicates, if present, would remain raw evidence but not independent targets. Experimental and modified ASW-m curves remain separate.

Saved XData is velocity (m/s); YData is r/R. Model curves have 100 radial rows spanning 0..1.5. FIG titles establish x/D={.125,.5,1,2,3} for P4 and{.125,.5,1,2} for P5. P4 prose omits 2 from its list; use FIG titles. All 18 original ASW swirl curves have NaN at the axis; do not replace it by zero.

P4 is explicitly a MATLAB reproduction of the jet model (report 1088–1092), not a recovered ASWING executable run. GWS 5X4.3 and 5000 RPM are documented. P4_B filenames say DA4002, but the report’s second static case is APC Sport 4.2X2 at 9000 RPM (1125–1137,1461–1477); diameter/RPM pairing remains unresolved.

P5 is attributed to an ASWING sensor bench (1088–1097). GWS 5X4.3 at 5000 RPM / ratio .52 and DA4002 nominal 9 in at 5000 RPM / ratio .64 are documented. Axial tails recover 5.486400000000001 and 12.192 m/s as output-derived freestream candidates, not independent driving-input proof. Total axial velocity needs freestream added to the component API’s increment; original sensor projection and signed swirl remain unbound.

The existing actuator_disk/jet_profile/jet_velocity API can evaluate unmodified fields, but independent power, density and CdA are missing for every case. Exact spin, advance-speed convention and sensor setup also remain unresolved for P5. Nominal propeller geometry and rounded ratios do not establish the historical input tuple. ASW-m additionally needs its omitted hub-core parameters. Readable HG metadata contains graphics settings; opaque MCOS workspace content was not exhaustively decoded.

Preferred next recovery: P5_A_GWS, 8 ASW curves / 800 slots / 796 finite. Obtain its original bench or independent input record before an executable adapter. A blocked inventory can immediately preserve all 36 ASW curves / 3,600 slots / 3,582 finite. Do not recover power/CdA from the acceptance curves, fit experiments, or invent FIG precision tolerances. Source-only audit; no production imports, solvers or repository changes.

Exact pins, line excerpts, per-axis classification and all sample values are in report.json, source-excerpts.json, figure-metadata.json and raw-figure-series.json.
