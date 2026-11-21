# UA-1 browser discrepancy and nodal BDF precision

**The full stalled browser comparison has not passed.** The original run completed 220 passing eight-step requests, then stopped at request 221 (part220) on its fixed 2e-8 Python-agreement gate. The retained segment converged with eight accepted steps and no rejections, but its lift difference reached 2.20484e-8 and its largest force-coefficient difference reached 2.23267e-8. No comparison limit was relaxed.

The raw audits cover 1,729 unique states and 215 continuation boundaries. The complete returned trajectory through the failed request contains 1,768 physical steps. It remains an incomplete, failed periodic-runtime study. The complete Python equation comparison remains separately recorded; no native ASWING agreement is established.

Force decomposition locates almost all of the discrepancy in apparent-mass force. At the first failed lift sample, the total CL difference is -2.20484e-8, of which -2.20067e-8 comes from apparent mass. Circulation, circulation-rate and pressure-drag differences are much smaller. Tiny differences in local structural acceleration affect this force.

The BDF implementation reconstructed absolute positions before differentiating them. Since `r = r_jig + L * displacement`, the constant jig position cancels analytically. The implementation now differentiates the stored displacement coordinates first and multiplies by L. This preserves small motion that can be lost when added to a large fixed coordinate. It changes floating-point evaluation, not the BDF equations, coefficients, physical model, or default tolerance. It applies to nodal translation; it does not introduce a compensated checkpoint format.

**19 targeted tests pass:** eight independent derivative checks, four equilibrium/restart checks, and seven oscillator and source-tangent checks. The derivative tests include analytically known velocities where the reconstructed absolute positions are indistinguishable in double precision. The oscillator check retains the expected temporal convergence.

The unmodified tighter-tolerance diagnostic reached its 45-second job cap. With displacement differentiation, both eight-step Python and built-browser replays finish at their requested tolerances. Their strict cross-runtime agreement checks still fail:

| Nonlinear tolerance | Python seconds | Browser seconds | Browser maximum residual | Maximum scaled Python difference | Agreement gate |
|---|---:|---:|---:|---:|---|
| 1e-10 | 3.47 | 5.49 | 8.290e-11 | 2.196e-08 | Fail (2e-8) |
| 1e-12 | 3.91 | 5.85 | 6.496e-13 | 3.051e-08 | Fail (2e-8) |

These are paired replays of the same retained browser checkpoint, with all 136 current solver modules verified in the actual built worker. The requested-tolerance failure is preserved. The tighter case runs separately under the tolerance declared before either production replay. Neither is a cold-start periodic case. Only `openswing/time_integration.py` changes among the 136 scientific modules.

| Browser replay | Lift error | Circulation error | Rate error | Pressure-drag error |
|---|---:|---:|---:|---:|
| requested | 0.002750% | 0.004051% | 0.002264% | 0.000000% |
| tight | 0.002750% | 0.004051% | 0.002264% | 0.000000% |

The last table covers **only the nine retained times** in this short window. It uses the independent continuous equations and the original full-cold-history normalization scales. It must not be read as a full-period pass. The 0.1% physical waveform limit and the 2e-8 runtime comparison serve different checks.

**Remaining:** resolve the force sensitivity in the coupled time equations and establish a complete periodic comparison with the corrected implementation. Increasing tolerance stringency alone has not resolved the runtime discrepancy. Investigate the scaled kinematic blocks, angular/linear acceleration reconstruction and saved displacement precision before changing any comparison gate. UA-2 stall and native reference provenance also remain open.

The first diagnostic CLI launch failed before a solve because the repository import path was absent; the recorded successful Python invocations set `PYTHONPATH=.`. All numerical failures, timeout records, raw trajectories, and the original frozen source remain retained.

[Machine-readable report](isae-ua-time-position-20261102.json). [Correction and replay evidence](../../artifacts/isae/ua-time-position-20261102). [Original failed periodic study](../../artifacts/isae/ua1-stall-periodic-browser-20261102).
