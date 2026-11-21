# SA12 saved-result discrepancy audit

The 1020 completed jobs remain numerically valid conditional comparisons: **52/4080 raw scalar matches**, comprising CL 6, CD 34, CDi 6 and Cm 6. Only the three no-flap zero-alpha rows match all four fields on both grids. No source-supported wrapper mapping correction was established.

The material lift/drag differences grow near ground and under flap loading. N200 RMS differences are:

| Configuration | CL RMS | Raw CD RMS | CDi RMS |
|---|---:|---:|---:|
| Flap, h/c=0.5 | 0.04346505 | 0.0343022 | 0.00384355 |
| Flap, h/c=2 | 0.02068748 | 0.006839302 | 0.003364508 |
| Flap, h/c=inf | 0.007754578 | 0.001296501 | 0.001821601 |
| No_Flap, h/c=0.5 | 0.02516338 | 0.01084342 | 0.00122736 |
| No_Flap, h/c=2 | 0.009851775 | 0.001570149 | 0.0007701828 |
| No_Flap, h/c=inf | 0.001144598 | 0.000134632 | 0.0001461455 |

The inf label means the original 1000 m origin height with images still enabled. Across all six tables, maximum N100-to-N200 changes are CL 2.23e-5, CD 8.74e-6 and CDi 3.56e-6. These do not explain largest archived differences: CL .08358, raw CD .06991 and CDi .00662.

At no-flap alpha 8, h/c=.5, N200 gives CL .68599094 versus .71136 and raw CD .02249673 versus .016824. Its saved post-stall drag term is only 2.36e-11, so post-stall deactivation alone cannot explain this pre-stall difference. At h=1000 m the same raw CD is .02750627 versus .0275078. At flap alpha 8, h/c=.5, raw CD error is +.03584651, of which the current saved post-stall contribution is .01411296; this also leaves a substantial difference.

All current CDi_near and Trefftz CDi agree to floating arithmetic in this flat wind-parallel setup. In the archive, 25 close-ground no-flap rows have raw CD below CDi. That does not prove either archived column is wrong: near/far drag are different definitions in general. Original MATLAB line 122 plots .01+CDi for precisely that close-ground no-flap curve. The adapter correctly retains raw CD as its own target.

The literal flap setup uses section alpha +12.5, slope 7.44, CLmax 2.6 and Cdf .04 with zero geometric twist and flap derivatives. The manual defines alpha as zero-lift-line incidence; the report says the fixed slotted flap was represented by section constants. No extra 40-degree geometric flap or control is justified. The report also explicitly states close-ground post-stall drag was deactivated after divergence (cached aerodynamics report lines 2882–2888), but does not prove which setting generated each saved table.

Current Cm is exactly zero for every job, consistent with the straight quarter-chord axis and zero section Cm. The 1014 nonzero archived moments have magnitude at most 1.0032e-9 and fail their tiny printed-unit gates. Keep these numerical residues separate from material CL/CD/CDi differences without relaxing acceptance.

Historical Euler pose and initial F-toggle state remain unresolved. Current pitch=alpha is explicitly declared and internally consistent; missing pose does not prove wrong pose. Current stall flags mean local cl exceeds the limit, while soft leakage can already contribute pressure drag. Archived stall flags are retained and must not be equated to this diagnostic. Internal wrench/decomposition checks and the prior algebra audit are not operator-parity proof.

Next source comparison: no-flap alpha 8 h/c=.5 against the same h=1000 m state, checking image/force-point velocities and influence-state semantics. Recover historical settings before assigning causality. No fits, new tolerances, physics, production imports or repository edits occurred. All source locators, six-table statistics, 36 selected strip states and pins are in report.json. A separate P2 reporting-only addendum preserves the already published evidence chain.
