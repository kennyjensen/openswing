# UA-1 phase-average and mean-lift source bindings

Reviewed 2026-11-01 against pinned ISAE revision
`f62943df20e9e4d7d9f50e070477b22426b5f865`. The
[source manifest](isae-ua1-phase-sources-20261101.json) pins both MATLAB scripts
and nine CSV files, including their headers. This review adds no pass counts.

`Phase average/Post_Traitement.m` constructs six curves labelled “ASWING phase
Average” directly from the same linear equation used by `sim_total.m`. It does
not read native ASWING trajectories for those curves.

| Quantity | Literal source setting |
|---|---|
| Reduced frequencies | 0.47 and 0.94; distinct from the 0.475 and 0.95 time-study frequencies |
| Peak-to-peak A/c | 0.5 |
| Mean incidence | 0°, 5°, 9° at each frequency |
| Samples | 100 equally spaced phase points, including both endpoints |
| Incidence axis | Mean incidence plus `(180/pi)*(A/c)*k*sin(2*pi*t)` |
| Lift | `Re[-(A/c)*B(k)*exp(i*2*pi*t)] + 2*pi*alpha_mean_rad` |
| Bracket | `B(k)=2*pi*i*k*(1+2*i*k)/(1+4*i*k)-pi*k^2` |

The six input CSVs have `Exp` and `Exp_Steady` headers. The script also plots
constant-offset “corrected” curves: offsets 0.8/1.4 at k=0.94 and 0.6/1.0 at
k=0.47 for the 5°/9° cases. These are separate plotting adjustments and are not
production-model corrections or native reference outputs.

The plotted static curve is another hand-written formula: linear slope 2π,
limits ±0.84, and an outer slope of 2π/40. This is not a recovered native polar
and does not replace Drela's documented section stall model.

`LEV_effect.m` reads experimental min/max/steady CSV columns. It shifts the
zero-incidence experimental midpoint by −0.03, draws a zero theoretical line,
uses a constant 0.68 line at 5°, and takes the 9° comparison line from a CSV
steady value. These experimental offsets and constants are outside the user's
requested native-ASWING comparison scope.

The periodic time study checks zero-incidence mean lift against the symmetry
of the attached-flow equations. It does not claim to reproduce experimental
LEV shifts. The subsequent [numerical phase comparison](isae-ua1-phase-20261101.md)
now passes all six linear curves on both meshes (12/12 curve checks), including
the production steady-incidence derivative. Nonlinear finite-amplitude motion
at nonzero mean incidence remains unfinished. This source inventory and its
pinned JSON remain the record of the earlier source-only review.
