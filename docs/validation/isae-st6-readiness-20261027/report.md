# ST6 source readiness: no identified archived ASWING targets

The complete pinned ST6 directory has **no identified archived ASWING numerical targets**. Its five curves labelled “Aswing Euler Critical load” are calculated directly from Euler's formula in `Analysis.m`; the other plotted values are experimental transcriptions. Registering them as ASWING solver results would misstate their provenance. No model import, solver, MATLAB script or numerical validation was run for this audit.

The audit covers all **19 original files**, verified against revision `f62943df20e9e4d7d9f50e070477b22426b5f865`, plus the original ISAE Structure report. All hashes, exact CSV tokens, source excerpts and line/page references are in [report.json](report.json). The original technical report PDF has SHA256 `4c332da19860339fad516cedc91b167a2724642e8b61c96b7467f1150db6d66b`.

The earlier backlog correctly identified missing bindings. The retained producer now resolves the main ambiguity: this is an **indirect Euler comparison**, not a missing executable ASWING result series. The report itself calls it “not a direct validation” (§4.6, PDF page 42; cached text lines 3866–3879). It explains that the press's two-end restraint was not reproduced by the ASWING setup used in that study; replacing the upper restraint by a free end and tip mass changes the problem (page 45, lines 4057–4065).

| Specimen | Shape / script label | Experimental rows | Minimum gyration-radius token | Script area |
|---|---|---:|---:|---|
| ST6.A | Angle | 8 | 0.489 | Mean of 8 actual-area tokens |
| ST6.B | Zee | 8 | 0.685 | Mean of 8 actual-area tokens |
| ST6.C | Bar 1 | 8 | 0.181 | Mean of 8 actual-area tokens |
| ST6.D | Bar 2 | 12 | 0.289 | Mean of 12 actual-area tokens |
| ST6.E | Rod | 8 | 0.250 | Mean of 8 actual-area tokens |

There are **44 experimental rows, 176 numeric cells and 44 measured maximum-load ordinates**. The CSVs give length, actual area, effective slenderness and maximum load. Their headers omit units; imperial length/area and pound-force interpretation follows from the script's modulus and explicit `4.44822` load conversion, supported by the report's stated psi units. No experimental uncertainty or comparison tolerance is inferred.

`Analysis.m` reads only those five CSVs. Its decisive expression at line 27 is:

```matlab
Fcr(i) = Area*(pi^2*E)./((K*L(i)/rho).^2);
```

Equivalent branches occur at lines 54, 80, 106, 161. The five branches set `E=10.6E6`, `K=0.5`, use each table's mean actual area and request `linspace(0,120,100)`. Thus the script declares 500 analytical evaluation positions, including five singular zero-length positions; these are not 500 retained ASWING outputs. The commented duplicate specimen 4 branch is not an additional curve. Four specimen plots have EPS/PDF graphics, three also have SVG versions; the separate PDF/SVG modal graphic is a schematic. There are no `.asw`, `.sh`, `.mat`, `.fig` or native eigenvalue/operating exports in this directory.

The report identifies 14S-T aluminium alloy and `E=10.6E6 psi` (rounded `7.3E10 N/m²`), with minimum section radius and `K=.5` in Eq48 (page 45, lines 4071–4097). Original PDF dimension labels give an angle with 6.35 cm legs and .635 cm thickness; a zee with labelled 10.16 cm extents and 1.43 cm thickness; bar drawings of 5.08×2.54 cm and 5.75×1.59 cm; and a 2.54 cm-diameter rod. These are nominal drawings, not complete original ASWING beam records.

**The bar drawing labels conflict with the script.** The drawing calls the 5.08×2.54 cm section Bar 1, consistent with about 2 in² and radius .289 in. The script calls specimen 3, with mean area 1.423125 and radius .181, Bar 1 instead. The smaller drawn Bar 2 is consistent with that specimen 3. The archive is retained unchanged; no pairing is repaired by choosing a label or fitting stiffness.

The report's buckling criterion is the appearance of a “first pure real positive mode” (page 27, lines 2353–2364). The schematic shows imaginary roots moving toward zero and then real roots; it supplies no numeric roots, preload schedule or search tolerance. This is global divergent buckling, explicitly distinct from local skin buckling (page 45, lines 4139–4145). `K=.5` and the clamp drawings suggest an ideal fixed-fixed comparison, but the exact fixture constraints are not encoded as ASWING data. Measured critical loads and formula outputs cannot be reused as independent preload inputs to manufacture a historical replay.

No archived-ASWING adapter scope is justified from these files: **zero identified scalar targets and zero proposed comparison jobs**. Keep ST6 visible as `NO_ARCHIVED_ASWING_TARGETS_IDENTIFIED`. A synthetic Euler-column regression or a separate experimental study could be useful later under its own acceptance criteria; neither would reproduce an archived ASWING calculation. Reopen this boundary only with an independently attributable numerical export and its generating model, supports, loading/base state and modal settings. The cited Niles NACA TN1027 experimental note is not stored here and was not fetched in this bounded audit.
