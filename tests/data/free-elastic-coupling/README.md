# Independent combined free-elastic regression

`fixture.json` and `model.asw` define the fixed physical case. The fixture's
source-only status records its pre-execution declaration; validation is recorded
separately in `provenance.json` and the linked report.

`manufacture-16.npz` contains the independent 32-point-quadrature circulation and
positive nodal aerodynamic wrenches. The adapter subtracts those wrenches once
as fixed body-coordinate loads and adds the declared preload/balancer.

`expected-16.npz` contains the independent continuous-rod/aerodynamic harmonic
responses for both inputs at all three declared frequencies. No native response
was used to construct the expected arrays. Tests retain all 31 physical groups
and 186 complete complex comparisons at the original 1% limit.

See [the validation report](../../../docs/validation/free-elastic-coupling.md)
for assumptions, refinement results, reproduction and the evidence archive.
This is not a Daedalus reference match.
