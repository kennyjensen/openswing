# UA-1 apparent-mass sensitivity: structured linear-solve refinement

**Both short browser replays pass the original 2e-8 runtime-agreement gate.** The complete stalled periodic case remains unpassed: these are two eight-step replays of the same retained checkpoint, not new cold-start trajectories. All 136 solver modules are verified in the actual built browser worker.

The structured solver forms a local solution by subtracting its coupling to the border solution. The subtraction can discard small constrained motions when the terms are large. Those motion errors are amplified by BDF acceleration and apparent-mass loads. Independent dense and refined solves of the same retained matrices remove the newly introduced normal-motion noise; the old checkpoint history still contributes during the first few steps.

The production solver now applies up to three iterative-refinement corrections to the original block equations, using the existing sparse and border factorizations. It uses ordinary double precision, does not form a global dense matrix, and retains the original linear-residual guard and nonlinear acceptance equations. Geometry, stall parameters, time steps, physical equations and default tolerances are unchanged.

| Requested nonlinear tolerance | Python seconds | Browser seconds | Maximum scaled runtime difference | Result |
|---|---:|---:|---:|---|
| 1e-10 | 4.38 | 5.51 | 1.927e-14 | Pass |
| 1e-12 | 4.18 | 4.54 | 3.155e-14 | Pass |

The preceding implementation failed at 2.196e-8 and 3.051e-8. All eight steps in each corrected replay converge without rejection. These timings describe only the measured segment; they are not a full-case performance claim.

| Short-window equation error | Lift | Circulation | Circulation rate | Pressure drag |
|---|---:|---:|---:|---:|
| requested | 0.002750% | 0.004051% | 0.002264% | 0.000000% |
| tight | 0.002750% | 0.004051% | 0.002264% | 0.000000% |

These equation errors cover nine retained times, with the original full-history normalization. They do not establish a complete periodic pass.

**20 targeted implementation tests pass:** six analytical cancellation tests, four complete response comparisons (flap, engine, released mass and spin), five Radau block/guard checks, three sparse-failure fallback checks, and two independent free/mixed-frame restart checks. The flap comparison initially failed by 3.812e-6 N in force balance with both the old and new linear solve. Its solve tolerance is now stricter (1e-10 instead of 1e-8) for both algorithms; the comparison limits are unchanged. The initial batch timeout and both failing baseline results remain recorded.

**Additional local-state audit: still unresolved.** The existing replay gate compares lift, force coefficients, pressure drag, section lift, circulation/rate and frame heave motion. It does not compare all local nodal rates. Those additional fields show a maximum spanwise acceleration difference of **0.000285156 m/s²**, velocity difference **6.270e-8 m/s**, and position difference **2.910e-11 m**. Full-state runtime agreement is therefore not established. The jig spans 200,000 m to approximate the two-dimensional limit. In CPython, the batched arc quadrature returns straight-interval lengths 7.276e-12–1.455e-11 m too large even though every sampled derivative norm is exactly one. Evaluating the same Gauss rule about a constant baseline removes that error in a read-only diagnostic. This is a concrete next investigation; the production quadrature has not been changed or revalidated.

**Remaining:** resolve the spanwise geometry/kinematics precision issue, then a fresh complete UA-1 stalled periodic study using this implementation and current Python/browser baselines; subsequent UA-2 revalidation and stall coverage; broader physical conditions and independently attributable native-ASWING outputs. No registered full-case pass count changes.

[Machine-readable report](isae-ua-time-refinement-20261102.json). [Paired replay evidence](../../artifacts/isae/ua-time-refinement-20261102). [Earlier failed comparison](isae-ua-time-position-20261102.md).
