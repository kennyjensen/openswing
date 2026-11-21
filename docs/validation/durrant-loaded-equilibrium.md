# Independent loaded-equilibrium review at 24 m/s

The saved 25% wing equilibria pass an independent reconstruction of aerodynamic loads, gravity, elastic-axis torsional constitutive balance and three discrete twisting virtual-work tests. The imposed section Cm=−0.1 produces nearly all of the baseline mean twist. This closes a useful local static-consistency check; it does not establish the loaded flutter boundary or validate the reconstructed operating condition against the experiment.

The inputs are the preserved loaded N8 baseline and its Cm=0 and zero-section-alpha/body-beta variants. Requested N8 has 10 actual structural/aerodynamic intervals. Baseline settings are U=24 m/s, rho=1.225 kg/m³, influence Mach=0, body beta=4.17°, section alpha=4°, Cm=−0.1 and gravity=(0,0,−9.805) m/s². The zero-incidence variant retains Cm and gravity. Neither variant is the independently checked unloaded analogue or the thesis's Case 1.

No new equilibrium solve or extraction adapter was needed: saved positions, rotation matrices, interval resultants, circulation, section wrenches, reactions and source distributions were sufficient. `review.py` imports no OpenSwing implementation and calls no production aerodynamic or structural evaluator. It independently reconstructs the wake, velocity, tangency/stall law, section lift/drag/moment, mass loading and work. Saved circulation is an input checked against the independently rebuilt tangency residual. Primitive rotation operations use SciPy.

## Primary equations and coordinate conventions

The pinned ASWING steady theory supplies the offset constitutive equations (17–20), pp. 8–9; force/moment balance (46–56), pp. 12–13; Glauert coordinate (63), p. 15, and interpolation (151–154), pp. 31–32; section loads (67–74), pp. 16–17; gravity at the actual CG (77–79), p. 17; wind-aligned vortex/control points (155–157), p. 32; and circulation/stall closure (202–204), p. 40. The PDF is `/home/userland/aswing/.reference/asw_theory.pdf`, SHA-256 `ff3aadbf986644697e22d8d4e65ffcd596b279b45f39bba7b61ac0e58d22ee4c`.

For these inputs, jig c=+x, s=+z, n=−y; this is right handed. Section axes follow the saved rotations. The actual elastic-axis offset is e=Cea c+Nea n, with Cea=0 and Nea=0.001 m. The reference axis is Xax=0.2505 chord, so the quarter-chord lift arm is slightly nonzero. Chord is 0.09446 m, span 0.718 m and GJ=0.7101 N m².

Independent section formulas are

```
F_lift = rho Gamma (V cross s) current_ds
M_Cm   = 0.5 rho |V_perp|² chord² Cm_local current_ds s
M_lift = ((0.25-Xax) chord c) cross F_lift
M_EA   = M_reference - e cross F
Cm_local = Cm_input / sqrt(1-(|V_perp|/sound_speed)²)
```

The local Cm Mach factor remains required by equation (73) even when the influence Mach input is zero. The independent drag formula includes the post-stall leakage contribution in equation (70), despite Cdf=Cdp=0. Gravity is integrated at r+Ccg c+Ncg n using fixed real mass per original span length. The resulting local EA torque is compared with GJ times the local span component of the relative rotation logarithm divided by original element length. This uses the saved implementation's geodesic rotation interpolation; it is not a claim that its discrete kinematics are identical to the original ASWING Euler-angle discretization.

## Numerical results

| Case | Tip body-z angle | Integrated local torsion curvature | Sum of local aerodynamic EA torques: Cm / lift / drag (N m) |
|---|---:|---:|---|
| Baseline | −6.568971° | −6.570823° | −0.22677461 / +0.000269713 / −2.51e−10 |
| Cm=0 only | −0.057059° | −0.042135° | 0 / +0.001394396 / −1.009e−7 |
| Section alpha=0, body beta=0 | −6.558683° | −6.560315° | −0.22665123 / +0.000121740 / −0.000167216 |

Tip body-z rotation and integrated local torsion are separate finite-rotation quantities. Summing torques projected onto different local span axes is a diagnostic, not a global moment balance.

Across all three cases, maximum absolute independent reconstruction differences are:

- Aerodynamic strip force: 8.77e−15 N; strip moment: 1.05e−15 N m; induced/relative velocity: 6.31e−12 m/s.
- Circulation tangency minus stall leakage: 5.12e−11 m/s, largest in the zero-incidence saved state.
- Actual-EA torque minus GJ times torsional curvature: 5.83e−14 N m.
- Global force balance including root reaction: 1.03e−12 N; global moment balance about the root EA: 3.27e−13 N m.
- Three discrete twisting virtual-work residuals with epsilon=1e−6 rad and gravity quadrature order 8: 1.53e−11 N m.

The straight, uniform-beam scalar formula theta_tip=rho U² chord² Cm L²/(4GJ) gives −6.54706°, or −6.56341° with the freestream local Mach correction. Its closeness supports the expected scale and sign of the dominant Cm effect. It omits lift, gravity, bending and actual local flow and is not a validation of the coupled equilibrium.

## Twisting work and bending coupling

For nodal virtual rotations delta_theta_i=phi_i s_i, phi_i=(s_i/L)^p for p=1,2,3, each nodal EA position is held fixed. The independent interval internal work is

```
N · (delta_r_i - delta_r_j)
+ 0.5 (dr cross N) · (delta_theta_i + delta_theta_j)
+ M_mid · (delta_theta_i - delta_theta_j).
```

The external work uses independently rebuilt wrenches at their actual Glauert stations and differentiated interpolation of the perturbed nodal geometry. The root variation is zero, so support work vanishes. For the linear span profile p=1, the work decomposition is:

| Case | Cm | Lift including offset | Drag | Gravity | Total external | Total internal |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | −0.113462371 | +0.000067457 | −2.39e−10 | −0.000137225 | −0.113532139 | +0.113532139 |
| Cm=0 | 0 | +0.000696523 | −5.03e−8 | −0.000425497 | +0.000270976 | −0.000270976 |
| Zero incidence | −0.113459170 | +0.000094774 | −0.000114997 | +0.000140637 | −0.113338756 | +0.113338756 |

All entries are N m of work per unit virtual twist amplitude. They are not an additive decomposition of the nonlinear physical tip angle. The Cm=0 case has substantial bending and small competing twisting contributions; a scalar lift-arm calculation misses the transport of bending moments through the rotating section axes.

For a continuous pure-EA twist delta_Omega=phi s, define M_EA=M_ref−e cross N. The independent continuum work identity is

```
W_internal = -integral T_EA phi' ds
             +integral phi (kappa cross M_EA_local)_s ds
             +integral phi (r_EA'_local cross N_local)_s ds.
```

For Cm=0 and p=1, those terms are +0.000752342, −0.001047770 and +0.000024452 N m. Their sum is −0.000270976 N m. The bending-transport term is larger than the direct torsion term, explaining why the small net twist cannot be inferred from local external torque alone.

## Interpolation and convergence limits

The saved internal couples are midpoint resultants. Extending them as constant body vectors inside each interval creates an artificial continuum work discrepancy. The force-balanced extension is

```
M_ref(f) = M_mid - [(f-0.5) dr] cross N,
```

with endpoint couples M_mid±dr cross N/2. Using this extension, the continuum internal work agrees with the exact discrete internal work within 2.8e−17 N m for all three cases, all three virtual profiles and quadrature orders 4, 8 and 16. The original constant-midpoint diagnostic is preserved separately, with its source and results hashes; it is not evidence of a physical imbalance.

A continuous pure-EA virtual twist shares nodal values with the discrete variation but is different inside each interval. Two effects are explicitly separated:

1. Using analytic phi=(s/L)² or (s/L)³ instead of interpolating its nodal values changes external aerodynamic work by about 1.06% or 2.11% in the baseline. This is a choice of virtual field, not an equilibrium error.
2. With nodal-linear phi, the remaining pure-EA versus interpolated-geodesic virtual-field differences are 1.54e−6 to 3.77e−6 N m for the baseline, 1.21e−6 to 1.83e−6 N m for zero incidence, and 2.54e−7 to 8.04e−7 N m for Cm=0. The last case has 0.30–0.83% relative differences because its total work nearly cancels. The exact discrete tests still balance to numerical precision.

Increasing continuum quadrature from 4 to 16 changes internal work by at most 2.8e−17 N m. Gravity-work changes in the finite-difference discrete test are at most 7.6e−12 N m. Across epsilon=1e−5, 1e−6 and 1e−7, every discrete work residual is below 3.85e−10 N m; the smallest epsilon shows the expected subtraction sensitivity.

No matched loaded N16/N32 saved states were available in these inputs. These are quadrature and virtual-field consistency checks on the same N8 physical state, not a physical mesh-convergence demonstration. A later mesh check should preserve the same source and condition, independently reconstruct each loaded state's circulation/wrenches and EA torque, and compare actual torsional curvature, tip angle and virtual work under the same material profiles.

## Evidence and remaining scope

`review-results.json` records every section torque, every error and every work/quadrature variant. `evidence-audit.json` verifies the three original and copied input hashes, pinned primary sources, current script hash and preserved first-version script/result pairing. Input/source fingerprints are recorded in `inputs.json`. Both independent postprocessing and the provenance audit exited 0. No main, frozen helper, native kernel or prior diagnostic source was modified.

This review finds no static Cm sign, EA moment-arm, gravity-transfer or local torsional constitutive error at the three saved U=24 m/s states. It does not independently validate the derivative of those loads at a loaded state, mode continuation through root coalescence, the loaded flutter crossing, full structural/aerodynamic continuum convergence, or the thesis reconstruction. The absence of a matched experimental static twist dataset remains a separate limitation.

## Portable record archive

The sibling `durrant-loaded-equilibrium-records.zip` contains the independently
authored `review.py`, its three complete saved inputs, original results and
provenance audit. Its member manifest checks every retained file. Extract it
into a fresh directory and run `review.py` with NumPy/SciPy to recompute the
static reconstruction; it uses the included relative input paths and imports
no OpenSwing module. The original `audit.py` additionally checks the recorded
original absolute paths, so that historical audit requires the original
workspace. No primary PDF is redistributed in this archive.
