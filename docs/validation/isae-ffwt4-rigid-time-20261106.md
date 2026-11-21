# FFWT-4 attachment mechanics: integrated rigid-tip comparison

Both explicit rigid extensions and endpoint pylons converge toward an
independent exact finite-rotation solution. Six complete synthetic histories
at three time steps finish with **140 accepted steps, zero rejections and
14 successful serial jobs**. At dt=0.005 s, all six measured quantities in
both representations are within **0.0577%** of their declared physical scales,
below the unchanged 0.1% numerical gate. This is additional mechanics evidence;
native FFWT-4 coverage remains **200/8,000** and production input handling is
unchanged.

This follows the [section-load, steady-matrix and prescribed-BDF study](isae-ffwt4-rigid-extension-20261106.md).
It replaces the absence of any integrated comparison with a controlled
single-axis vacuum comparison. It does not establish native ASWING's
out-of-range attachment convention or general three-dimensional equivalence.

## Literal inputs and declared synthetic model

Parsing the three original PM2 files confirms that all six rejected objects
have mass **0.0102 kg**, with **zero drag area, volume, spin and intrinsic
inertia entries**. Thus point airflow is not an active term for these six
objects; it remains required for general point-object support. Their literal
positions, stations, properties and source hashes are retained in the new
assessment.

The synthetic model retains a rigid lifting-surface tip over
t=[0.364, 0.5], with a hinge at y=0.364 m. Two 0.0102 kg masses use the literal
right-tip locations (-0.0139, 0.3521, 0) and (-0.0139, 0.4965, 0) m. There is
no airflow or gravity, and all beams are massless and exactly rigid.

The extension representation adds an actual nonlifting rigid beam over
t=[0.3521, 0.364], joined rigidly to the tip. The other representation uses
the tip's endpoint pylon while retaining the same physical point position.
The retained mesh is identical; the models have 16 and 11 nodes respectively.
Every beam obeys the production minimum of four intervals.

The spring and release are explicitly synthetic: initial angle 0.4 rad,
zero initial velocity, natural frequency 5 rad/s and duration 0.2 s. The
inertia about the x-axis hinge is derived from both point masses:

```
I = 0.0102 [(0.3521 - 0.364)^2 + (0.4965 - 0.364)^2]
k = 25 I
I theta'' + k theta = 0
theta(t) = 0.4 cos(5 t)
```

A constant tip couple k·0.4 establishes the initial equilibrium and is
removed after the initial snapshot. This uses the production moving-frame
structural equations and material-Euler BDF2 integration, with BDF1 startup.
There is no reduced oscillator inside the production solve; the scalar
solution is an independent comparison only. Spring stiffness and initial
conditions were chosen before running the histories, without aircraft fitting.

## Temporal accuracy

The table gives maximum errors over all computed post-release times, in
percent of fixed physical scales. Angle, rate and angular-acceleration scales
are 0.4 rad, 2 rad/s and 10 rad/s². The overview position, velocity and
acceleration scales use the larger point radius R=0.1325 m:
R·A, R·A·omega and R·(A+A²)·omega². The pre-release initial acceleration is
excluded because it belongs to the loaded equilibrium, not the released ODE.

| Representation | dt (s) | Angle | Angular velocity | Angular acceleration | Point position | Point velocity | Point acceleration |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Endpoint pylon | 0.020 | 0.6661% | 0.8846% | 0.6935% | 0.6184% | 0.8738% | 0.6122% |
| Endpoint pylon | 0.010 | 0.1790% | 0.2281% | 0.1831% | 0.1654% | 0.2242% | 0.1593% |
| Endpoint pylon | 0.005 | 0.0461% | 0.0576% | 0.0465% | 0.0425% | 0.0565% | 0.0402% |
| Explicit extension | 0.020 | 0.6661% | 0.8854% | 0.6939% | 0.6184% | 0.8745% | 0.6123% |
| Explicit extension | 0.010 | 0.1790% | 0.2283% | 0.1832% | 0.1654% | 0.2244% | 0.1593% |
| Explicit extension | 0.005 | 0.0461% | 0.0577% | 0.0465% | 0.0425% | 0.0566% | 0.0402% |

The latest step halving reduces these errors by factors 3.885–3.966,
consistent with second-order convergence. Coarser histories fail the 0.1%
gate; both finest histories pass all six quantities. A supplemental assessment
also normalizes each point by **its own radius**, so the much smaller inboard
motion cannot be hidden by the outboard scale. All **12/12** individual-point
position/velocity/acceleration checks pass at the finest step, with maximum
error **0.0566%**. These checks overlap the overview quantities and are not
additional native-reference values.

![Temporal errors against the exact oscillator](../../artifacts/isae/ffwt4-rigid-time-20261106/plots/convergence.png)

The two finite-step trajectories still differ. At dt=0.005 s their maximum
hinge-angle difference is 6.77e-8 rad and maximum point-acceleration component
difference is 6.13e-5 m/s². Both differences decrease on refinement. This
supports consistent continuous mechanics, while retaining the earlier finding
that endpoint reduction is not exactly identical at a finite BDF step.
These values are not error bounds for an actual FFWT-4 gust trajectory.

## Evidence and remaining requirements

The assessor authenticates source/helper hashes, all 14 actual terminal
receipts, the six complete time windows, unchanged physical states at every
checkpoint boundary, replay of accepted discrete states, BDF predecessor
retention and every residual against 1e-10. Maximum residual is 9.914e-11.
All jobs use one BLAS thread, a 512 MiB address-space limit and at most ten
physical steps. Each had a 150-second cap and finished in under 23 seconds.

An initial assessor incorrectly required a recalculated diagnostic residual
norm to be bitwise identical at a restart (1.922e-15 versus 3.224e-16).
Every physical field was exactly unchanged. The corrected assessor compares
physical states and accepted order exactly and applies the unchanged 1e-10
gate to both residuals. The failed assessor and receipt are preserved; no
physical trajectory was rerun or altered to correct this check.

Evidence is in `artifacts/isae/ffwt4-rigid-time-20261106/`: `assessment.json`,
`point-assessment.json`, complete compressed results/checkpoints, terminal
receipts, the preserved failed assessor, and PNG/SVG convergence plots.
Reproduction helpers are `scripts/verify-isae-ffwt4-rigid-time.py`,
`scripts/assess-isae-ffwt4-rigid-time.py` and
`scripts/assess-isae-ffwt4-rigid-time-points.py`.

General integrated three-dimensional motion, full point tensor/spin dynamics,
local-rate/acceleration matrix equivalence, point airflow and browser execution
remain outside this new comparison. The six literal offending objects have
zero tensor/spin/airflow fields, but actual hinged-wing gust histories still
need their own spatial/time refinement. Native input semantics remain
unrecovered; the original ISAE models and production attachment rules are
unchanged. No whole family or project completion is claimed.
