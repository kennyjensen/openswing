# Retained SCN load-association check

The printed `cl` and `f_aero` belong to the **following interval**, not to the structural node on the same line. The primary manual explicitly says derived midpoint quantities are shifted upward half a line and the final zeros are dummy entries: `.reference/aswing_doc.txt:2546–2599`. Consequently the nonzero left-tip `cl` and zero right-tip `cl` do not establish an asymmetric physical tip condition. This conclusion needs no model pairing.

All seven headered files have central structural `Fn` jumps consistent with the reported `sum Fz` within their original printed precision:

| File | Fn multiplier | Central jump | Header sum Fz |
|---|---:|---:|---:|
| rect_A3_N12 | 1 | 9.6484 | 9.648 |
| rect_A3_N24 | 1 | 9.7010 | 9.701 |
| rect_A3_N48 | 1 | 9.7271 | 9.727 |
| rect_A3_N96 | 1 | 9.7400 | 9.740 |
| ellip_A8_N6 | 10 | 82.147 | 82.15 |
| ellip_A8_N12 | 10 | 88.694 | 88.69 |
| ellip_A8_N96 | 10 | 90.848 | 90.85 |

The multiplier is read separately from the exponent above each `Fn/10` column. `rect_A3_N6.txt` is headerless, so its force scale and missing total are not inferred from neighboring files.

The tables do **not** establish the exact internal aerodynamic-to-structural load transfer. For example, `ellip_A8_N6.txt:36–37` gives an `Fn` decrement of 21.6930 ± 0.0010. Multiplying its displayed `f_aero=54.1396` by displayed `delta-t=0.4031` gives 21.82367276, with conservative printed bounds about ±0.00543412. The intervals do not overlap. Summing this naive product across N6 gives 82.48841414, whereas the structural root jump is 82.147. N12 similarly gives 88.99853288 versus 88.694. These are rejected arithmetic identifications, not identified solver defects.

The manual calls `f_aero` a lift-force/span diagnostic (`aswing_doc.txt:2503–2509`), and the output omits the full geometry, local bases, local velocity and profile-force vectors. `t` is not by itself proof of the exact physical span metric; the displayed `y` differs substantially near elliptical tips. The display increment determining actual-node versus interpolated output is also absent (`aswing_doc.txt:2497–2501`). Thus the scalar products above cannot be promoted to complete applied-force integrals.

Theory equation 56 conserves the complete distributed and concentrated loads (`asw_theory.txt:642–655`, pp. 13–14). Its structural endpoint-average definition (`:593–598`, p. 12) and the aerodynamic section's local theta-midpoint definition (`:1587–1619`, p. 32) remain distinct. The newly recovered printing rule settles sample association; it does not reveal the missing sample-to-structural-load recovery rule.

The retained `post_analysis.m` plots the shifted derived quantities against nodal `y`, and estimates circulation from fixed chord and freestream speed. Those plots are not an independent exact circulation field. `Rectangular.asw` is not paired to these rectangular outputs; matching CASEI headers alone are not execution proof. No model is reconstructed, no production code is imported, no solve is run, and the original SA1 acceptance denominator is unchanged.

`analyze.py` reproduces the saved-field Decimal arithmetic and `report.json` records every inspected original file hash, primary-source pins, local product bounds and root-force comparison.
