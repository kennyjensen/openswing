# SA-11 next-adapter readiness

The two unchanged one-beam inputs support a bounded rigid-polar adapter using existing production APIs. Register **all eight tables: 328 rows and 2,296 required output scalars**. Four tables have a demonstrated force/coefficient normalization conflict with their supplied models, so this is conditional archived-output comparison, not a verified historical setup. No production import, mesh, residual, solve, or repository edit was performed.

The pinned original revision is `f62943df20e9e4d7d9f50e070477b22426b5f865`. The base folder is `1 - Aerodynamics/SA - Steady Aerodynamics Cases/SA - 11 - Swept Back Wing with Whitcomb Winglet - Transoninc Lift and Drag/Aswing_Simulations/`. All **65/65** family files passed independent byte-count, SHA-256 and Git-blob checks against the archive manifest. `source-audit.json` records exact paths/hashes; `rows.json` retains all 26,896 numeric tokens and source line numbers.

| Model folder | Driver stem | Output stem | Labels | Rows each |
| --- | --- | --- | --- | ---: |
| `wing_alone` | `wing_alone_polar_Ma_` | `wing_alone_Ma_` | `0_70`, `0_75`, `0_78`, `0_80` | 41 |
| `wing_extension` | `wing_extentsion_polar_Ma_` | `wing_extension_Ma_` | same four | 41 |

Drivers end in `.sh`, tables in `.txt`, and each folder's unchanged model is `<folder>.asw`. The extension driver's spelling is original. Each executable argument names that local model and each `w` command names its exact table. Both model Names and all table titles say `Wing_alone`; the title is not a reason to substitute the baseline model for the extension.

Each row has **82 numeric columns**, although the multiword header splits into 122 whitespace tokens. Required zero-based columns 75–81 are Lift [N], Drag [N], CL, CD, CDi, CM, efficiency. `span eff.` is one scalar, not two columns. Retain all row echoes: 69–71 are actual V/beta/alpha; 72–74 are VIAS_ref/beta_ref/alpha_ref. Every driver and table has alpha 0–10 degrees in 0.25-degree increments; every `conv` is 1; no token is missing/nonfinite. Extension stall flags are 1 at rows 40–41 for 0.70 and rows 36–41 for 0.80. Preserve those rows and flags.

The exact speeds are 240, 255, 266 and 272 m/s. With literal sound speed 340.21 they imply Mach 0.705446636, 0.749537051, 0.781870021 and 0.799506187. Filename labels are not commands to replace these speeds. Both models specify rhoSL=1.2256 and Sref=0.9329 m². Extension changes section drag, lift slope and CLmax specification as well as geometry; preserve its literal file and all duplicated section stations.

## Normalization evidence and limits

For each positive printed force/coefficient pair, this audit independently bounded qS by `(F−hF)/(C+hC)` and `(F+hF)/(C−hC)` and compared it to the literal `0.5*rhoSL*V²*Sref`. No tolerance was expanded.

| Variant/label | Lift interval contains literal qS | Drag interval contains literal qS | Implied S from lift, at literal rhoSL |
| --- | ---: | ---: | --- |
| alone 0.70 | 40/41 | 40/41 | 0.932897–0.932905 m² |
| alone 0.75 | 0/41 | 0/41 | 97.669629–97.670455 m² |
| alone 0.78 | 0/41 | 0/41 | 97.669789–97.670399 m² |
| alone 0.80 | 41/41 | 41/41 | 0.932897–0.932905 m² |
| extension 0.70 | 41/41 | 41/41 | 0.932898–0.932904 m² |
| extension 0.75 | 0/41 | 0/41 | 97.669786–97.670340 m² |
| extension 0.78 | 0/41 | 0/41 | 97.669679–97.670308 m² |
| extension 0.80 | 41/41 | 41/41 | 0.932897–0.932903 m² |

The two small 0.70 exceptions are baseline row 23 drag and row 37 lift, retained in `rows.json`; thus even that table is not an exact all-row printed-precision normalization pass. The four 0.75/0.78 polars imply approximately 104.7 times the supplied rho*S. This establishes an unmatched normalization, not which historical model, density, force units or runtime reference setting generated them. Do not rescale inputs/outputs, infer the separate cant0 geometry, or drop force columns. The existing `isae-sa11-archive.md` documents the large conflict; the backlog's lowest-risk-pair recommendation needs this qualification.

## Settings and smallest integration

No reviewed driver declares NODE/I, and no `.set`, `.pnt` or `.con` is retained anywhere in this case. The primary guide documents automatic restoration of these files at startup (`aswing_doc.txt:1574–1587`) and inheritance between operating points. The scripts alone cannot recover mesh, initial influences, branch history or PG state.

For 0.70/0.80, `kk` and `mm` follow the last `!A` and precede `xx`; they are absent at 0.75/0.78. The guide documents doubled OPER commands in general (2184–2188), K options (2238), and M toggling specified PG Mach versus V/a (2413–2429), but not the exact original KK/MM parser behavior. The original report says PG was activated (Part 1 text:2585–2589); it does not establish each table's numerical PG value. Do not claim the absent commands disable PG.

1. Add a dedicated SA-11 planning/decoding route after the current source freeze. Reuse the reviewed **82-column** schema in `isae_suite_extra_polars.decode_table`, plus the literal heredoc decoder and seven-output worker in `isae_suite_polars`. The base ten-column decoder will not discover these tables; the extra module's existing family counts/routes are specific to SA-10/12/14/15.
2. Keep one required record for every row/channel. A declared two-grid 64/128 reconstruction would yield 656 jobs and 4,592 scalar comparison slots; these are new computational grids, not recovered historical nodes. Prefer the 0.70/0.80 rows first for execution priority, while retaining the other 164 rows as explicit unmatched-source records or clearly labeled unmatched-source diagnostics. None may disappear from family accounting.
3. Set PG explicitly. Reusing the current extra-polar defaults would silently impose `mach=0`; that contradicts the reported PG-enabled intent. `mach=None` uses current speed/atmospheric sound speed and is a defensible declared reconstruction, not a proven archived setting. Preserve literal density, current declared influence/stall settings, natural-v1 interpolation and all current local-Mach guards. There is no basis to tune PG or influences to the archive.
4. Reuse the existing physical gates unchanged: convergence, circulation residual ≤1e−8 and independent force/moment normalization/decomposition errors ≤2e−10. Compare each of the seven original tokens at its own half printed unit. Keep numerical validity, reference match, settings uncertainty, and normalization conflict separate. Existing solves return near-field CD with independently reconstructed total drag; preserve that reviewed mapping.
5. Add source-only tests for eight unique pairs, 41 rows each, 82-column mapping, every command coordinate, stall flags, literal model hashes, PG declaration, and retained normalization conflicts. No new aerodynamic algorithm is needed for these two inputs. Runtime/convergence at transonic conditions has not been assessed here.

The remaining winglet/cant0 variants are outside this bounded readiness review; no broader SA-11 completion is claimed.
