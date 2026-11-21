# P-3 source readiness

P-3 retains **84 finite ASWING-labelled force/moment coefficient targets** across **28 conditions**: four advance labels (0.2, 0.45, 0.70, 1.0), seven propeller angles (0° through 90° in 15° steps), and CN, Cn and CT. No complete original-input comparison is executable yet. This audit adds no registered jobs or numerical results.

| Saved classification | Curves | Finite scalar values | Meaning |
|---|---:|---:|---|
| Red ASWING | 12 | 84 |Archived prediction candidates|
| Black Exp | 12 | 84 |Separate measurements|
| Blue Leng BEMT | 12 | 84 |Separate nonlinear-model predictions|

Each of the three original FIG files has 12 seven-point curves. The saved title explicitly assigns colors; square, circle, upward triangle and diamond markers bind the four advance labels. Independent inspection of primary-report Figure 9 confirms the mapping. All 252 stored pairs match the existing extraction bitwise. Raw values, float hex encodings, graphics paths and source pins are retained in [report.json](report.json), including the yaw curve’s negative zero. There are no duplicate curves within a figure. The 28 conditions count each CN/Cn/CT triplet once.

The report identifies P-3 as **partial / data only** (Table 1, PDF p13) and says such cases retain ASWING outputs because modified source cannot be distributed (§3, PDF p12). The three figures and Figure 9 call the red curves ASWING predictions. **P-3 is not explicitly identified as a MATLAB theory reproduction**: that statement belongs to P-4 static. A saved MATLAB figure does not establish which implementation produced its curves. The P-3 directory contains only these three figures: no input model, shell driver, MATLAB producer, raw solver export or modified executable/build.

The documented flow relations are v=V∞sinαp, Vd=V∞cosαp+½ΔVe, and μ=λcosαp. Figure 9 prints CDA(μ)=0.0019μ²−0.0026μ+0.0006. These are printed calibration coefficients; unrounded producer values are not recovered. The report describes a NACA0012 propeller with linear blade-pitch variation and 20° tip pitch. It literally prints radius Re=0.85 m, confirmed in the PDF; this audit does not silently correct the scale. Pitch moment is explicitly excluded.

Execution remains blocked by missing row-wise CP/shaft power, exact advance-ratio velocity convention, RPM, density, confirmed dimensional scale/full blade and radial P-factor coefficients, and an original component request/build. The retained figures and report do not establish the CN/CT force or Cn yaw-moment denominators, normal/yaw axis signs, spin direction, or moment origin. The rig drawing alone does not fix those conventions. Measured CT/CP functions are cited but their original driving table is absent here. No power, geometry or sign was inferred from the red acceptance curves.

Stored FIG double precision is not recovered ASWING print precision; this report invents no comparison tolerance. Readable HG metadata contains graphics annotations. Opaque MCOS/function payloads remain unexecuted and incompletely decoded, so this is not an exhaustive workspace claim.

The next step is to obtain the original P-3 producer/input table or pinned cited primary material establishing geometry, CP and normalization, then define one explicit component request before comparing all 84 targets. Until then the curves support blocked source registration only. The bounded audit used standard-library data decoding, with zero production/numerical-package imports, solver calls or upstream-script execution; all source pins were rechecked before writing.
