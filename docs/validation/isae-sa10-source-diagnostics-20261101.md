# SA-10: explain rejected local flow from cached vortex coefficients

2026-11-01. Local-Mach rejections now identify the strongest bound-vortex and
grouped wake contributions at the failed force point. The exception also gives
the circulation residual, so a converged circulation solution can be
distinguished from a physically valid subsonic flow. This is an error-reporting
change; the underlying SA-10 discrepancy remains unresolved.

## What is reported

The existing force-point influence operator supplies one row of bound and ray
coefficients. Coincident wake strengths are combined before multiplication and
ranking, using exactly the same incidence operator as the flow evaluation.
No matrix is rebuilt or solved in this error path. The observer records:

- Incident, jet, bound and wake velocity vectors in body axes/input units,
  together with their reconstructed total and reconstruction error.
- Up to three largest nonzero terms of each vortex type, source beam and strip
  station, circulation, effective core and physical source coordinates.
- For wake groups, net circulation, member count, up to four source endpoints,
  and distance to the physical half-ray.
- Whether the influence geometry is current or frozen at the jig geometry.

The station is the source strip's circulation/force sample, not its endpoint.
Coefficients include the configured Prandtl–Glauert map and ground images;
reported distances identify the physical ray. Large terms can cancel, so an
individual term is not presented as the complete local flow. Incident velocity
includes the evaluator's freestream, rotational, gust, volume and motion terms.
Only the largest contribution is appended to the short exception message.

## Verification and actual SA-10 evidence

Eight targeted tests pass in 3.17 seconds. They cover independent expanded
horseshoe fields with PG and both ground-image signs; exact and near-exact
shared-ray cancellation; current and frozen geometry with a displaced mesh,
rates and gust; and a zero-circulation gust rejection. The cancellation tests
forbid reassembly and full-field application during reporting. JSON output is
checked for finite values in these cases. An initial fixture omitted mandatory
Unit/Constant blocks; its two failures are retained before the correction.

Five saved rejected SA-10 peak receivers also pass a one-row replay. It takes
4.65 seconds after imports and uses no new aircraft solve. Each one-row
operator contains 45,152–100,640 bytes of arrays. Production reporting uses the
already-cached operator, so even this one-row assembly is unnecessary there.

| Saved rejected state | Stall strength | Local normal Mach | Largest grouped ray speed, m/s | Distance to that ray |
|---|---:|---:|---:|---:|
| TS 80/60/40, 25°, 128 requested intervals per beam | 40 | 1.08671 | 624.122 | 6.94919 µm |
| TS 60/40/80, 25°, 128 requested intervals per beam | 20 | 1.00575 | 872.873 | 42.0917 µm |
| TS 80/60/40, 25°, 128 requested intervals per beam | 20 | 1.11399 | 640.142 | 6.94919 µm |
| Louvered, 15°, 400 requested intervals | 20 | 2.51724 | 2707.895 | 0.250481 mm |
| Louvered, 25°, 400 requested intervals | 20 | 3.17274 | 3434.783 | 0.243142 mm |

All five circulation residuals are below 3.57e-14. Reconstructed total velocity
agrees with the original saved flow within 2.21e-14 of freestream speed. The
prior independent 60-digit physical-coordinate audits agree within 1.20e-10
of freestream speed, including the ranked wake origins, strengths and source
identities. A separate scalar/JSON verifier checks the saved diagnostics and
all 42 unchanged ISAE status rows without importing the solver.

Example additional message:

> Largest grouped wake contribution: 624.1217 (input L/T), source strip beam 2,
> t=0.5590013; distance to its physical ray=6.949188e-06 (input L).
> Other vortex terms may partly cancel it.

These results reproduce the implemented source geometry; they do not establish
the historical ASWING force-sampling convention at a sharp corner. No source
smoothing, artificial core, tolerance relaxation or accepted ISAE result is
introduced. SA-10 remains **1,256/2,268** in the default registered scope.

The existing browser worker forwards exception text, but browser verification
remains suspended following UserLAnd disconnections. No Vite/Chromium process,
full build or distribution refresh was launched. Packaged browser sources
remain stale relative to this change. The full project goal is incomplete.

[Replay and pinned sources](../../artifacts/isae/sa10-source-diagnostics-20261101/plan.json),
[results](../../artifacts/isae/sa10-source-diagnostics-20261101/analysis.json),
[test log](../../artifacts/isae/sa10-source-diagnostics-20261101/tests.log),
[verification](../../artifacts/isae/sa10-source-diagnostics-20261101/verification.json).
