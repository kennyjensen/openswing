# ISAE AE-1: saved load and twist reconstruction — 2026-10-25

The six selected fine-mesh states from the [full AE-1 sweep](isae-ae1-sweep.md) pass **71,043/71,043 saved-data checks**. No load-transfer or output-definition defect is supported by this reconstruction. The experimental mismatch remains.

The audit independently reconstructs section frames from saved nodal rotations, aerodynamic strip forces and couples, their transfer to structural nodes, internal cut loads, section curvature and projected tip twist. It uses Python's standard library and the retained velocities, circulation and geometry. There are **no new aerodynamic evaluations, residual calls or aircraft solves**. The [report](isae-ae1-loads.json), [720 strip rows](isae-ae1-load-strips.csv), [360 positive-half structural rows](isae-ae1-load-sections.csv), [execution receipt](isae-ae1-loads-execution.json) and [reconstruction script](../../scripts/analyze-isae-ae1-loads.py) retain the details and input hashes.

| Root incidence / speed | Projected tip twist | Contribution from quarter-chord lift couples | Contribution from lift-force arms |
| --- | ---: | ---: | ---: |
| 5° / 30 m/s | 0.57863° | 0.53398° | 0.04464° |
| 5° / 40 m/s | 1.05376° | 0.99164° | 0.06212° |
| 5° / 56 m/s | 1.99905° | 1.97030° | 0.02874° |
| 7° / 30 m/s | 0.78583° | 0.74026° | 0.04557° |
| 7° / 38 m/s | 1.24447° | 1.20648° | 0.03798° |
| 7° / 41 m/s | 1.42985° | 1.40402° | 0.02583° |

**These contributions hold each converged geometry and section compliance fixed.** They are an algebraic attribution of the saved response, not the response to adding a pitching moment or changing a load in a newly coupled equilibrium. The lift-force-arm term includes the deformed span geometry and structural coupling. The literal section pitching coefficient `Cm` is zero, so its contribution is exactly zero. Smooth stall/profile drag contributes less than **3.83 × 10⁻⁸°**; rounding accounts for the displayed row sums.

The physical lift arm is `(0.25 − Xax) × chord × c = −0.0191 × c` metres. Here `c` is the current unit chord direction, and the reference axis coincides with the elastic axis because `Cea=Nea=0`. The bound-vortex velocity point is displaced along the wind direction; it is a different point and must not replace the physical chord arm in the torque calculation. These conventions follow [ASWING steady theory](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf), equations 67, 69–70 and 72–73 (printed pp. 16–17), with vortex geometry in equations 155–157 (pp. 31–32). The audit retains the nonzero tension-axis offsets in structural recovery.

Quarter-chord lift couples account for **92.28–98.56%** of projected twist in this attribution. About **55.0–56.1%** of the applied quarter-chord torque lies in the inner half of the semispan, while **78.7–79.7%** of the projected twist accumulates there. These describe load location and deformation location separately; the deformation share is not an attribution to loads in that region alone.

Local incidence in the strip CSV is `atan2(V·n, V·c)` at the saved bound-vortex force point, using the current physical section frame. Its range across the selected 5° states is **3.69–5.27°**, and across the 7° states **5.34–6.76°**. It differs from prescribed root incidence, incidence based on freestream alone, and `cl/dCLda`, the equivalent angle of a two-dimensional linear lift law. The exported `da_eff` is the documented linearized change in section normal projected onto velocity; it is not an exact angle difference.

No selected strip is flagged stalled; the largest `cl` is **0.71201**, below the 1.1 limit. Nevertheless, the smooth leakage function is nonzero below that limit. Its largest positive-half profile-force magnitude sum is **2.21 × 10⁻⁶ N**. The control-point normal velocity is inferred from the saved circulation residual plus the leakage law, equations 202–204 (printed pp. 40–41); no independent control-point velocity field is claimed.

Reconstructed strip forces agree within **1.73 × 10⁻¹⁴ N**, and strip couples within **3.30 × 10⁻¹⁶ N m**. All-node force and moment balance errors are at most **1.63 × 10⁻¹² N** and **3.10 × 10⁻¹⁴ N m**. The complete load-to-projected-twist attribution closes within **5.12 × 10⁻¹³°**. At 5°/56 m/s, integrating material torsion gives 2.12115°, while the exact projected tip chord angle is 1.99905°; the curved-frame observation map explains the difference and recovers the existing leading/trailing-edge output.

The [source qualifications](isae-ae1-source-scope.md) remain in force: 5°/56 m/s is after the reported peak with an unresolved recovery boundary; 7°/41 m/s is at or above a reported instability indicator. The other selected speeds are below reported indicators, which does not certify stability. This audit neither evaluates stability nor resolves the processed experimental displacement axis.

Two diagnostic failures are preserved in the study evidence: an initial parser guard expected `Beam` instead of the literal `Beam 1`; a subsequent guard expected no point-force records instead of the 34 exactly zero records. The second attempt passed all 70,215 other checks. The corrected attempt added explicit zero-vector checks and passed all 71,043 checks without changing numerical gates or reconstruction equations. Sessions 3132 and 93685 exited 1, and accepted session 59299 exited 0; all were reaped. The source copies, logs and failed reports remain under the study directory recorded in the execution receipt.
