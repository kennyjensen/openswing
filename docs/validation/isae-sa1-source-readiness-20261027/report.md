# SA-1 complete source and acceptance audit

The pinned SA-1 family contains **nine files, one original model, one driver and one native ASWING operating export**. The definite native acceptance set is **77 scalar outputs: all seven output columns at all 11 operating points**. The two current meshes expand these to 154 checks; the previously completed broad baseline matched 19. This source audit performs no physical solves, model construction, residual evaluations or matrix assembly.

The [machine-readable report](report.json) retains all original text lines, every native numeric token and its exact decimal interval, every model property table, all CSV rows, all nine stored figure series, binary figure values including NaNs, source locations and SHA-256 pins. All nine original files match the immutable archive manifest. Independent decoding of both original MATLAB figures exactly matches their earlier cached extraction; MATLAB and the downloaded shell script were not executed.

## Complete target inventory

| Source | Retained content | Acceptance treatment |
|---|---|---|
| `Aswing_Simulation_V5_96_Only/SA_1_CL.txt` | 11 rows × Lift, Drag, CL, CD, CDi, CM and span efficiency = **77 outputs**; another 33 index/sequence/incidence values | Native targets, with every printed token and half-last-place interval retained. |
| `SA_1_CL.fig`, `SA_1_CD.fig`: ASWING 5.96 | 22 coefficient values | Exact duplicates of native CL/CD values. Their plotted incidences differ from the native incidences; they are separate provenance witnesses, not 22 new native targets. |
| `SA_1_CD.fig`: ASWING-ISAE | 11 finite modified-labelled values | Retain separately. Modified producer, inputs and comparison precision are missing. |
| `SA_1_CL.fig`: ASWING-ISAE | 13 stored positions: 11 finite values and two NaN gaps | Mixed provenance; retain every position without assigning a native-output denominator. |
| Remaining FIG series | Experiments and three regression curves | Preserved; not substitutes for archived ASWING outputs. |
| Two CSV files and two PNG files | Experimental digitization and separately labelled lifting-line results | Preserved ancillary evidence; experimental agreement is outside the ASWING acceptance target. |

The figures contain 101 stored sample pairs, including four nonfinite pairs across the modified lift and one regression series. Their binary values are retained with hexadecimal floating-point and IEEE-754 representations. Binary storage precision is not an inferred ASWING printing tolerance.

The modified lift figure has a concrete provenance conflict. Its first nine finite points exactly equal the `Lifting_Line` columns of `Experimental_Data/SA_1_CL.csv`; the original PNG labels that curve **“Present LL (2-D Star-CCM+)”**. After two NaN gaps, its final two finite lift values exactly copy native ASWING CL. The report calls the improvements ASWING-m, but the retained figure alone cannot authenticate those points as a separate ASWING execution. The modified drag curve likewise lacks its generating modified model/script. No inverse fit, interpolation or relabelling resolves these gaps.

## Literal model and driver

`SA_1.sh` launches `aswing SA_1`, selects `NODE`, `I`, `200`, then `OPER`, `K`, `I`, `100`, and toggles `F` once. The following `%`, `a`, `d` commands select **Anchored defaults**, then DONE, in the constraint editor. It declares `!V 47.9`, then the eleven incidence tokens below, inserting ten `+` points, executes `xx`, selects output indices `68 72 73 74 75 76 77 78`, and writes `SA_1_CL.txt`.

```text
0.029369  1.9971  4.1116  6.1087  8.1351  10.103
12.1      14.097  15.095  16.006  18.091
```

All eleven native incidence centers equal these driver values. The retained title `Mowe_temp`, model basename and output filename also align. There is no retained executable hash, startup settings file, saved point stack or exact nonlinear iteration history.

The unchanged model uses metres, seconds and newtons; constants are gravity 9.81, sea-level reference density 1.2256 and sound speed 340.21. Its reference area/chord/span are 5.9 m², 1 m and 5.9 m, with all three reference origins zero. A rigid ground is at beam 1, t = 0. The chord distribution begins at t = 0, so the guide’s per-variable symmetry convention mirrors the literal 2.95 m semispan to a 5.9 m full span. The wing is straight, unswept, untwisted and massless. Zero values for infinity-default stiffnesses mean rigidity, not a flexible zero-stiffness beam.

The airfoil data are exactly `dCLda = 6.2832/rad`, limits ±1.2, `Cdf = .00352562`, `Cdp = .00771413`, and zero section moment and zero-lift offset. Literal `Xax = 0` places the reference s-axis at the leading edge; the section moment is defined at quarter chord. Constant property tables end at t = .5, but this does not redefine the geometric half-span. Their constant values and the straight geometry do not justify changing any original endpoint or coefficient.

The primary ISAE report instead gives slope about 6.26, limits ±1.5, Cdf = 0 and Cdp = .01 on page 25. Those are source differences to retain. They are not permission to replace the literal inputs.

## Structural nodes and circulation variables are distinct

**`NODE I 200` requests structural grid nodes, not 200 intervals or 200 circulation unknowns.** The primary version notes for 5.67, dated 22 January 2007, explicitly identify the `i` command as selecting the number of nodes, with a minimum of one per breakpoint and automatic increases when necessary. This predates 5.96. Exact node insertion and the resulting original arrays remain unrecovered; there is no source-supported mapping from I to Fourier count K.

Drela’s theory distinguishes pointwise circulation at structural intervals from a Fourier circulation representation; K can be smaller than the number of structural intervals. Its equations 200–201 impose weighted residuals when K is smaller. The ISAE report independently defines K circulation coefficients and I structural nodes on pages 18–19; its convergence section recommends 20–40 circulation variables/Fourier coefficients. Its conclusion explicitly distinguishes 40 structural nodes from 40 circulation variables. The SA-1 text’s “40 nodes” refers to circulation distribution, so it must not simply be treated as a contradiction of the driver’s I = 200.

The extended manual’s page 21 image separately displays **100 nodes** and Fourier modes **k = 1 and k = 19**. Its caption says 180 nodes, an internal caption/image disagreement that must remain visible. Neither the image nor the caption establishes k = 19 as a universal default. The manual is dated September 2025 and explicitly uses ASWING 5.98, so it cannot identify the original SA-1 build. The version notes also mention a correction to circulation-mode defaults on LOAD, without specifying a numeric default.

The historical OpenSwing study explicitly used **pointwise** circulation and nominal interval counts. Those are reconstruction choices, not recovered original arrays or a recovered original basis. The exact structural node arrays, circulation basis and K remain open. Changing K because it brings the results closer would not recover those settings. A prospective source-based comparison must declare I and K independently, and distinguish requested nodes from resulting intervals.

## Operating state and output definitions

The guide identifies `!V` as indicated airspeed. The original rhoSL and 47.9 m/s produce a dynamic-pressure normalization consistent with **all 22 printed Lift/CL and Drag/CD pairs**, allowing both printed fields’ original rounding intervals. Historical altitude and true airspeed remain unrecovered; using actual density 1.2256 and true speed 47.9 is an explicit sea-level reconstruction.

`K/I 100` is the Newton iteration limit. `F` toggles frozen, undeformed, zero-incidence influence matrices against matrices updated using current wind-aligned geometry. The guide displays fast = T as a default, so a single F toggle supports current influences only conditionally on that startup state. Startup can auto-read `.set`, `.pnt` and `.con` files, none retained for this case. Fixed-zero PG Mach and speed-derived Mach are distinct supported choices; the script does not identify which was active. The anchored constraint mode is explicitly selected, but zero sideslip, rates, accelerations, gust and other untouched numeric settings still require the corresponding default semantics or recovered startup evidence.

The `+` command inherits the preceding point’s parameters; `XX` converges the stack. This establishes the requested sequence, not the exact historical warm-start/branch history. A set of current cold jobs must retain that qualification.

Lift and drag are forces in N; CL, CD, CDi, CM and span efficiency are dimensionless. The original export header defines the seven target columns; public guide output-selector numbering cannot silently replace the retained version’s numbering. All negative CM tokens stay negative, with the zero moment reference and original quarter-chord arm retained.

**Span efficiency uses Trefftz lift and side force, not the printed total-force CL.** Drela’s equation 211 is `e = (CLi² + CYi²) / (π AR CDi)`. In the first native row, substituting printed total CL instead gives approximately .98362095, whereas the original efficiency is .984903. All eleven rows show this distinction. It is not a rounding repair or a reason to change the efficiency target. CDi and efficiency need their own source-faithful output recovery.

The theory’s approximately 40 stall factor and .05 transition width are published choices, not independently recovered constants of the original 5.96 build. Its separation model does not make circulation decrease after stall. The original limits, drag law, residual gates and printed tolerances must remain intact.

## Complete-family acceptance checklist

1. Compare every one of the 77 native outputs at the eleven exact native incidences; preserve raw tokens, signs and original decimal intervals. Require a complete seven-output match for each state, with repeated meshes accounted separately.
2. Establish physical and numerical validity independently: fresh residuals, complete setup and source hashes, force/moment integration, coefficient normalization, Trefftz outputs, and prospectively specified mesh checks. Retain every failure.
3. Resolve or explicitly qualify original build/startup settings, separate structural and circulation grids, and sequence/continuation history. Do not infer them from closeness to targets.
4. Account for all 22 duplicate native figure values and their different plotted incidences without treating them as extra independent outputs or replacing driver incidences.
5. Resolve the producer, setup, precision and mixed provenance of the 22 finite modified-labelled values and two missing samples before claiming complete family reproduction. No source-supported decimal acceptance interval is currently recovered for those binary figure values.
6. Keep experimental, other lifting-line and regression series visible as ancillary evidence. Matching them does not establish ASWING parity.

The exact original source paths and hashes, all extracted values and the detailed acceptance checklist are in [report.json](report.json). No complete SA-1 pass is established by this audit.

The source association is strong at the filename/title/command level, but cannot prove generation timing. All original files have immutable SHA-256 and Git-blob identities; the native text and script contain no creation timestamp or executable hash. The figures’ MATLAB headers record 26 February 2025, which dates figure storage only. Neither the executable directory name `AswingMAC_12_02_21` nor the folder label `V5_96_Only` authenticates the executable actually used. No evidence establishes that the native table is stale, and no evidence proves it was produced from exactly the retained model bytes.

## Primary provenance

The pinned [ISAE aerodynamics report](../../../.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/5%20-%20Technical%20Reports/Experimental_validation_of_ASWING_Part_1_Aerodynamics_V4.pdf) provides the SA-1 description and Figure 11 on pages 22, 25–26; independent structural/circulation definitions appear on pages 18–21 and 58. Exact cached-text line locations are retained for each fact in the JSON.

The [ASWING guide](../../../.reference/aswing_doc.txt) supplies symmetry, rigidity, unit/reference, startup, stack, iteration, fast/slow and PG conventions. The [Drela theory](../../../.reference/asw_theory.pdf) supplies equations 62–63 and 200–201 for circulation representation, 67/69/70/72 for aerodynamic loads, 207–211 for Trefftz outputs, and 220–225 for force/moment coefficients. These primary descriptions do not authenticate a specific original executable build.

The [version notes](../../../.reference/version_notes.txt) supply the pre-5.96 NODE/I count statement. The [extended manual](../../../.reference/ASWING_Extended_User_Manual.pdf), page 21, was rendered and visually inspected for its separate node/Fourier labels and contradictory caption.

The prior [SA-1 study](../sa1.md) and [completed broad baseline](../isae-suite-current.json) remain historical evidence with their original hashes and settings. This report neither reruns nor rewrites them.
