# AE-2 uncoupled archived ASWING catalog

The acceptance target is the four supplied computed ASWING sweeps, not experimental agreement. This catalog reads literal bytes only. It changes no property, imports no production model and executes no physics.

| Command beta | Positive commanded IAS (m/s) | Finite states | Retained initial all-NaN state |
|---|---|---:|---:|
| 1° | 1–28 | 28 | 1 |
| 5° | 1–22 | 22 | 1 |
| 10° | 1–20 | 20 | 1 |
| 15° | 1–17 | 17 | 1 |

There are **87 positive finite coordinates**, 91 total rows, 348 finite sensor values and 16 NaNs. Scripts insert each preceding state with `+`; the final speed is executed by `XX` without a trailing `+`. No final point is dropped. Each row retains all six original tokens, source lines, explicit IAS command and four masks. The original `i`/`t` columns are sequence coordinates, not input speed or asserted transient time.

The four sensor-1 selections are 14/19/20/18: Earth `RY` (m), heading `Psi` (degrees), local airspeed `V` (m/s), and local incidence `beta` (degrees). `Analysis.m` lines 101/106/111/116 plot `-RY` against sensor `V`; lines 156/161/166/171 plot commanded beta minus `Psi` against sensor `V`. These transformations are retained alongside raw signed channels. The missing IAS0 row supplies no usable native or archived baseline; it is not replaced by zero. Sensor speed is not silently used as the commanded freestream.

The original model is `[03_90].asw`, 1705 bytes, SHA256 `eb35a50606bcceee263352cbd40ffd509b504082c78ba61732ad52ce03193db8`. Its constants are g=9.81, rhoSL=1.23, sound speed=340.21 (line 14). Sensor 1 is at the tip midchord (line 18); the root is clamped at t=.0001 (line 28). Literal stiffness and all other fields remain unchanged. Matching names alone cannot establish the bytes consumed by the historical executable.

The scripts explicitly request a solid ground image with Earth normal (0,0,1), anchored constraints, beta and IAS. They do not record K/F, PG Mach, ambient density/altitude, exact initial pose/controls, mesh, executable checksum, or possible startup settings. The report attributes AE-2 Figure 3 to ASWING 5.96; no version banner/build is retained in these files. The separate pinned settings review distinguishes evidence from inference, including why local sensor speed cannot uniquely recover the atmosphere. Current assigned TAS=IAS is conditional on the declared rho=rhoSL=1.23 reconstruction, not a recovered historical fact.

At beta5/IAS10, output data row 11 (physical line 14) contains RY=-0.0258200 m, Psi=-0.572223°, V=10.0115 m/s and sensor beta=6.27943°. Prior archive-control m80/m160 cases are reusable **only** for the exact pilot condition (updated influences and PG Mach=10/340.21), source, panel request, cold arguments and unchanged 111 kernel files. Both prior terminal receipts and every saved output pin are checked. Nominal 80/160 requests produced 81/161 intervals in that accepted pilot. Other settings variants require fresh states. The source catalog contains 174 two-mesh entries in principle, with 172 new states if that exact pilot condition policy is retained; it is not an execution plan or authorization.

`manifest.json` is the complete provenance/row catalog; `candidate-inputs.json` is an explicitly conditional, unexecuted pilot-settings template; `archive-states.csv` is a flat convenience export. Reproduce this source-only extraction in a fresh stage with the retained generator and pinned inputs. Original raw scripts/model/outputs are copied byte-for-byte under `sources/`. Primary guide/report fulltexts are dependencies only and are not copied.
