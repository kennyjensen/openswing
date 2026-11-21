# SA-1 physical and virtual quarter-chord locations

**A consistent change between these quarter-chord constructions is a common translation of the aerodynamic geometry for literal SA-1. It cannot change the exact influence matrices, circulation or force coefficients.** This narrows an existing source-notation ambiguity; it is not a production correction. Registered SA-1 acceptance remains **19/154**. No roots, residuals, matrices or production modules were evaluated, and no production file changed. The [receipt](sa1-quarter-chord-translation-20261027.json) pins the reviewed evidence.

Steady theory 5.99 p16, Eq67 and its following text explicitly evaluate lift velocity at the bound-vortex receiver. Page32, Eqs155–156 place that receiver and the control point along the freestream direction. The unsteady description p8, Eqs29–32 instead names a physical quarter-chord offset along the local chord axis. The 1999 paper contains both notations in one document: printed p5 (PDF p6), the velocity summation and Eqs15–16 use the physical quarter-chord location; printed p7 (PDF p8) gives the wind-aligned bound/control-point construction. These passages do not explicitly define a mixed receiver/vortex convention.

For literal SA-1, chord is constant, `c=1 m`, `Xax=0`, lift slope is constant 6.2832, and twist and section zero-lift offset are zero. The wing is straight and planar. Consider the reviewed stationary, isolated current-wake case with uniform freestream, zero spanflow and no aerodynamic ground images, gust, engine or body influences. Let

```text
ex = (1, 0, 0)
e  = (cos(alpha), 0, sin(alpha))
h  = dCLda/(4 pi)
```

With beam node positions r_i and unchanged Glauert sample positions r_a, the documented virtual construction is

```text
bound endpoint: A_i = r_i + (c/4) e
force-velocity receiver: H_a = r_a + (c/4) e
control point: C_a = H_a + h c e.
```

A construction placing the bound line and force receiver at the physical quarter chord, while retaining the same downstream control-point separation, is

```text
A_i' = r_i + (c/4) ex
H_a' = r_a + (c/4) ex
C_a' = H_a' + h c e.
```

Every point changes by the same vector

```text
t = (c/4)(ex - e)
A_i' = A_i + t;  H_a' = H_a + t;  C_a' = C_a + t.
```

Every trailing ray also translates by t: `A_i + lambda e` becomes `A_i + t + lambda e`, without changing its direction. In the Biot–Savart integral, each receiver-to-vortex difference is unchanged, `(R+t)-(X+t)=R-X`, and each vortex line element is unchanged. Consequently every force and control-point influence coefficient is identical. The Fourier/pointwise basis, Glauert sample coordinates along the span, interval lengths and section frames are also unchanged.

Uniform freestream contributes the same velocity at either receiver. Thus for every circulation vector Gamma, not merely a converged solution, the bound normal speed, `cl=2 Gamma/(c Vperp)`, control-point normal velocity, stall leakage and complete circulation residual are identical. The residual Jacobian and root set are identical as well. Current-wake Kutta–Joukowsky and profile forces therefore remain the same, as do integrated CL, CD, CLi, CDi and span efficiency. This is an exact real-arithmetic identity; no bitwise equivalence after floating-point reassembly is claimed or tested.

## Moment placement is a separate definition

Current code already uses the physical quarter-chord arm `(c/4-Xax*c) c_hat` for the circulatory section moment, independently of the virtual influence receiver (`aero.py:587–590`, steady Eq72). Translating only the influence geometry as above leaves that arm and the beam/reference positions unchanged, so the currently defined Cm is unchanged too.

If a physical applied wrench were instead relocated by t while its reference origin stayed fixed, its moment would require `Delta M = t cross F`. That is a change in wrench placement, not a consequence of translating vortex coordinates. Translating the moment reference by the same t would remove that change. When only the circulatory force application point is relocated, the formula uses the circulatory force alone, not the profile-force sum.

For this SA-1 section with zero intrinsic Cm, the existing physical-arm identity is

```text
Cm_physical = -(c/(4 Cref)) [CLi cos(alpha) + CDi sin(alpha)].
```

Applying the circulatory force at the virtual quarter point instead would give `Cm_virtual = -(c/(4 Cref)) CLi`; the difference is exactly the corresponding moment-arm translation. The existing [complete-polar consistency analysis](sa1-load-consistency-20261027/report.md) already finds the native moments compatible with the physical-arm identity within their original print intervals. Changing the moment arm cannot alter the lift discrepancy.

This proof does not authorize moving only the velocity receiver while leaving the vortex source geometry fixed. Such a mixed construction changes relative distances and needs an explicit source rule, including how bound self-influence is treated. No such rule was recovered. The translation proof also does not cover varying chord/Xax or frames, nonuniform flow, rotation, relative placement of other bodies/surfaces, or a fixed image plane.

The 1999 paper and later descriptions still do not supply the missing historical endpoint aerodynamic-force recovery rule. Their conservative structural balances and aerodynamic Glauert sampling do not uniquely specify that transfer. The consistent quarter-chord translation examined here supplies no new mechanism for the SA-1 mismatch and no justification for fitting or changing production equations.
