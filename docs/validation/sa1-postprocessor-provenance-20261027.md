# SA1 plotted-curve provenance recovered from early CASE2 sources

**The saved ASWING-ISAE CL and CD curves have recovered mixed/derived recipes.** The earliest retained [postprocessor](../../.reference/sa1-public-history-20261027/earliest-Single_Wing/Post_treatment/post_analysis.m) supplies them explicitly. An independent replay reproduces the current modified-CD figure within a maximum absolute difference of **1.5681900222830336e-15**; the mixed-CL coordinates match exactly, including both NaN gaps. [Source pins, expressions and replay rows](sa1-postprocessor-provenance-20261027.json).

| Saved label | Author's expression | Classification |
|---|---|---|
| ASWING 5.96 CL/CD | Native `CASE2_CL.txt` columns 6/7, plotted against CSV column 1 (lines 13, 69, 101) | Native coefficient values with changed plot abscissae. |
| ASWING-ISAE CL | CSV columns 3/4, then the final two native CL values at CSV column-1 angles (lines 67, 73) | Mixed comparison-series and native endpoints; the CSV gaps remain. |
| ASWING-ISAE CD | Native CD plus `polyval(polyfit(XFOIL alpha, XFOIL CD, 5), CSV alpha)`, minus its first value (lines 5, 92–104, 109) | Native drag with a fitted external-airfoil correction. |

The historical [airfoil file](../../.reference/sa1-public-history-20261027/earliest-Single_Wing/Post_treatment/naca0012Re2E6M027.txt), lines 2–11, identifies XFOIL 6.97, NACA 0012, Mach .270, Reynolds number 2.110e6 and Ncrit 1. Column 3 is **total CD**; CDp is column 4. The variable name `naca0012cdp` in the script therefore must not be read as pressure-drag provenance. All 18 retained airfoil rows, spanning 0–10°, enter the stated fifth-degree fit. Six figure evaluations exceed 10°, reaching 18.0914°, and are polynomial extrapolations. These conditions belong to the external postprocessor input and do not establish the native ASWING Mach or stall law.

The replay used the exact historical inputs: early `CASE2_CL.csv` and `CASE2_CL.txt` Git blobs equal the current SA1 CSV and native-table blobs. NumPy 2.5.3 performed the author's specified fit solely against the retained airfoil data; no archived or figure target entered that fit. SciPy decoded the saved FIG as data. The CD result is numerically consistent with the recovered recipe, but is not bit-identical to MATLAB; no acceptance tolerance was introduced. No aircraft solver or production module was invoked.

The alternate drivers remain distinct evidence. `CASE2_POLAIRE.sh` and `CASE2_POLAIRE_mod.sh` both invoke **CASE10**, request NODE/I40 and declare the same operating commands. They differ in executable path and output filename, writing the two root `TEST_POLAIRE` files. The CASE2 plot block reads neither file. The two similarly named `Post_treatment` tables have different values and no explicit writer among these reviewed drivers. None of these facts establishes their executable build or makes them producers of the plotted mixed/derived curves.

This note supplements the frozen source-readiness review. It changes no source input, solver setting, precision gate, target denominator or historical result.
