# SA-6: the archived control order reaches the same roots

Using each converged point to initialize the next one does not resolve the
35%-chord model's derivative discrepancy. The complete `F1=4,8,...,44` sequence
reproduces the retained independent cold starts: maximum relative circulation
difference **7.18e−14**, maximum static/state coefficient difference
**2.05e−13**. Every native pass/fail decision is unchanged.

The original [`Post_Stall_15c.sh`](../../.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/1%20-%20Aerodynamics/SA%20-%20Steady%20Aerodynamics%20Cases/SA%20-%206%20-%20Straight%20Wing%20-%20Rolling%20and%20Yawing%20Moments%20induced%20by%20various%20Ailerons/Simulation/chordwise/Post_Stall_15c.sh)
loads the **35%-chord** model despite its filename. It declares speed 20 m/s,
incidence 12°, the eleven ordered controls, then `XX` and `MM`. The sequence
test starts the first point cold and gives every later solve the immediately
preceding circulation. All ten supplied seeds are accepted without a cold
fallback. This is a plausible interpretation of sequence initialization;
the script does not expose ASWING's internal initialization algorithm.

The retained qualified settings remain frozen influences, stall strength 20,
width 0.05, zero PG Mach and 128 requested intervals. Literal model properties,
force references and all comparison gates stay fixed. Neither the historical
strength nor the exact native node distribution is recovered by this test.

| Scope, eleven states on one mesh | Cold starts | Sequential starts |
|---|---:|---:|
| Six static coefficients | 66/66 | 66/66 |
| All six state columns | 343/396 | 343/396 |
| Pitch-rate subset | 36/66 | 36/66 |

Pitch-rate errors remain:

| Channel | Passing checks | Failed-check median error | Maximum failed error |
|---|---:|---:|---:|
| CXq | 0/11 | 22.775% | 63.825% |
| CYq | 11/11 | — | — |
| CLq | 8/11 | 3.642% | 4.340% |
| Clq | 9/11 | 3.119% | 3.191% |
| Cmq | 8/11 | 3.923% | 4.665% |
| Cnq | 0/11 | 18.848% | 102.016% |

An independent scalar verifier reconstructs the straight-wing Biot–Savart
velocities, complete leakage residual, lift/profile forces and quarter-chord
moments. Its maximum residual is **1.25e−14**, and static coefficients agree
within **6.67e−16**. Direct scalar matrix multiplication checks all six tangent
columns: maximum linear residual **6.22e−14**, coefficient reconstruction
error **8.89e−16**. It also reads every original native token, checks all
**462** comparisons, and verifies the exact predecessor circulation and hash
chain. Local normal Mach remains below 0.062.

Eleven nonlinear calls and eleven prescribed-field derivative evaluations
run in three serial batches of four, four and three states. Each derivative
evaluation uses one factorization for all six inputs. The numerical batch
loops take 1.17, 0.92 and 0.72 seconds after imports and input verification;
these timings include both equilibrium and derivative evaluations. All
workers finish successfully, with one BLAS thread and no background work.
The predeclared rule does not extend the study to other models because no
distinct branch or native gains appear. No global uniqueness claim follows.

The source review also distinguishes this comparison from a dynamic response.
Steady theory §8.4 assumes negligible time derivatives of the internal state;
unsteady equations 35 and 48 introduce separate circulation-rate terms.
Those passages do not justify adding circulation-rate lift to this steady
matrix comparison. They do not identify the archived producer's internal code.

One historical comparison-helper hash (`isae_suite_polars.py`) has changed
since the cold captures. The plan records both hashes instead of claiming
the historical helper is current. All original model, driver and output pins
are verified, all 136 production modules match the previous completed audit,
and the present physical fields and derivatives are evaluated afresh.

Production equations and all 42 registered status rows remain unchanged.
The complete qualified SA-6 state scope remains **2,780/3,168**, including
**282/528** pitch-rate checks. This result rules out this particular control
sequence as the missing setup detail; it does not complete native reproduction.

Evidence: [declared plan](../../artifacts/isae/sa6-native-control-sequence-20261101/plan.json),
[independent verification and comparisons](../../artifacts/isae/sa6-native-control-sequence-20261101/verification.json),
[serial producer](../../artifacts/isae/sa6-native-control-sequence-20261101/run.py),
[scalar verifier](../../artifacts/isae/sa6-native-control-sequence-20261101/verify.py).
