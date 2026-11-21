# SA-1: information recovered from native distributions

SA-1 remains **19/154 registered archived-output checks passing**, with all 22
baseline jobs complete. This follow-up adds independently checked evidence about
the archived discretization and circulation. It establishes no production solver
correction and adds no acceptance checks to the registered denominator.

The [paper/history review](sa1-history-followup-20261027.md) records the setup
information recovered from all four accompanying ISAE reports. Part 1's stated
lift limits, drag coefficients, lift slope and discretization differ from the
retained SA-1 model or driver. The original native table therefore remains the
target, with its original model and driver preserved. The
[balance audit](sa1-discrete-balance-audit-20261027.md) excludes an arc-length
correction, a finite load at the duplicated ground interval, and a change of
moment averaging as explanations for SA-1's force discrepancy.

## The archived station listings provide more information than first inferred

The manual describes a nonzero `D` as a fixed output increment in parameter `t`;
`D=0` lists actual structural nodes. The historical SCN rectangular N12 listing
has interior `t` gaps of 0.0727, 0.1000, 0.1068 and 0.1005. Four-decimal endpoint
rounding allows only 0.0001 uncertainty in each gap. These cannot be one constant
increment, even after excluding intervals touching the outer tips and duplicated
root. The elliptical N12 listing independently gives the same contradiction.

Thus **actual structural-node output is strongly inferred**, conditional on the
documented `D` contract applying to these files. The setting itself was not
echoed. Counts of N+2 rows, N positive intervals and one duplicate root reinforce
the inference. This narrows the earlier unresolved-display qualification; it
does not recover unprinted precision, the node-generation algorithm, or the
original SA-1 node coordinates. Derived `cl` and `f_aero` remain interval samples
printed on the preceding node line, not nodal values.

The [saved inference](../../artifacts/isae/sa1-native-cl-inversion-20261027/node-listing-inference.json)
retains the original tokens, bounds, source hashes and manual line references.

## Reconstructing circulation without guessing airfoil parameters

Four headered rectangular convergence distributions at 3 degrees and N=12, 24,
48 and 96 contain local `cl`. The retained author's postprocessor uses local
chord 0.2 m. Its header reference chord of 0.1546 m is a different normalization
quantity. The exact producing model remains unresolved, so straight, untwisted,
constant-chord geometry is an explicit condition of this diagnostic.

Under that condition, the documented relation

```text
cl = 2 Gamma / (local_chord * local_section_speed)
```

and the published horseshoe influence kernel allow a numerical reconstruction
of Gamma from the saved `cl`. The local speed includes induced velocity and
therefore requires an inverse solve. This uses no lift slope, stall parameter
or airfoil tangency equation. Both current and zero-angle frozen influence
conventions were retained under a
[protocol fixed before execution](../../artifacts/isae/sa1-native-cl-inversion-20261027/protocol.json).
Neither convention is selected by closeness to the archived forces.

All eight reconstructions and all 168 prescribed continuation stages converged.
The maximum scaled residual was 7.68e-13 against the declared 1e-12 threshold.
An [independent scalar replay](../../artifacts/isae/sa1-native-cl-inversion-20261027/independent-replay.json)
recomputed induced velocities, residuals, Jacobians, forces and circulation
integrals from the retained fields without invoking the inverse solver or
production modules. The maximum force difference was 5.33e-15 N; maximum
integral difference was 5.56e-17 m³/s.

For zero induced side force and the declared coefficient convention, native
efficiency and induced drag independently imply

```text
Integral(Gamma dy) = U * Bref / 2 * sqrt(pi * Sref * efficiency * CDi).
```

| N | Current-influence integral difference | Frozen-influence integral difference | Nominal integrals inside native header bounds |
|---:|---:|---:|---|
| 12 | +0.05809% | −0.00965% | Both |
| 24 | +0.04304% | −0.02430% | Both |
| 48 | +0.04359% | −0.02357% | Both |
| 96 | +0.05592% | −0.01117% | Both |

These are diagnostic overlaps with intervals propagated from the printed native
U, Bref, Sref, efficiency and CDi. They are **not strict parity results**: the
printed local `cl` and node-coordinate uncertainty has not been propagated
through the inverse. The frozen case additionally depends on an unresolved
native coefficient-export convention. A separate
[decimal-bound check](../../artifacts/isae/sa1-native-cl-inversion-20261027/native-integral-bound-check.json)
reproduces all four saved native intervals with explicit lower and upper pi
constants. Finite continuation steps and sampled Jacobian conditioning do not
prove global uniqueness of the recovered branch.

## A remaining discrepancy in the assumed force sampling

The [full results](../../artifacts/isae/sa1-native-cl-inversion-20261027/results.md)
retain complete forces separately from circulation-only forces. Their difference
includes unknown profile and other loads. The
[profile-force check](../../artifacts/isae/sa1-native-cl-inversion-20261027/cone-report.md)
tests one specific interpretation: only nonnegative profile forces remain, and
their directions use the reconstructed local velocities at the retained force
samples. Under the declared planar geometry, all Eq70 profile-force terms point
along local velocity. Their total must therefore lie between the smallest and
largest local `Vz/Vx` slopes.

This check uses the native dynamic-pressure token, 245.1, with its printed
interval. Multiplying separately rounded central density and speed instead gives
245.2 and noticeably changes this small residual. Both circulation-force
components use the same pressure scaling. All eight corners of the native
Fx/Fz/pressure print box were evaluated, holding the inverse fields fixed.

| N | Current-influence residual can satisfy direction condition | Frozen-influence residual can satisfy direction condition |
|---:|---|---|
| 12 | No | Yes |
| 24 | No | Yes |
| 48 | No | Yes |
| 96 | Yes | Yes |

For the three incompatible current-influence cases, the minimum lower-direction
deficits over that print box are 0.00644, 0.00585 and 0.00493 N. This isolates an
inconsistency in the **declared sampling and residual interpretation**. It does
not exclude current-wake physics or establish the native F setting. Unpropagated
local `cl` and coordinate rounding, other applied loads, or different native
velocity sampling/load recovery could change the condition. Satisfying this
necessary condition also does not prove a valid profile-force distribution.

The numerical work comprises eight inverse field reconstructions, no new
forward aerodynamic solves and no ASWING executions. All cases and failures
(none in this batch) were retained. The original model, solver, acceptance gates
and 19/154 registered result are unchanged. Historical node generation and the
mapping from circulation samples to integrated aerodynamic loads remain the
unresolved implementation questions.
