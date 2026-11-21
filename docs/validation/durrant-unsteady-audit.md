# Unsteady-load implementation audit

**Historical scope:** This audit preceded the apparent pitch-rate self-field
correction. Its mass/source findings and direct load-formula checks retain their
stated scope; references to the “current” flutter roots or future checks describe
that earlier investigation. The subsequent loaded-tangent work found and
corrected the own-bound contribution. Complete original records and scripts are
preserved in `durrant-source-audit-records.zip`; original absolute paths are
provenance, not installation requirements.

No mismatch was found in the straight, zero-incidence pitch/heave reduction of the implemented ASWING lag, circulation-rate lift or apparent-mass force/moment. A finite-incidence difference between the steady and unsteady documents' aerodynamic-point conventions remains a bounded interpretation issue. Neither finding validates the Durrant flutter boundary.

Sources were inspected as pinned local PDFs/text, including rendered unsteady pages 9–10. The JSON companion pins all inspected code/document hashes and records 48 direct production-function checks. No kernel, main-study or frozen-study files were changed.

## Coordinates and verified reduction

Let local c,s,n be right-handed, h positive along n, theta positive about s, x the reference-axis fraction of chord, a=(1/4-x)c and d=(1/2-x)c. Thus positive pitch rotates c toward -n, while s cross c = -n. Let U be positive along c and let m_a=pi*rho*c²/4 per span. At the flat zero-incidence state:

```
R_Gamma = U*theta - h_dot + (3/4-x)*c*theta_dot
          - Gamma/(pi*c) - (2/pi)*Gamma_dot/U

L_circ = rho*(U*Gamma + c*Gamma_dot)
M_circ = -a*L_circ

L_am = m_a*(U*theta_dot - h_ddot + d*theta_ddot)
M_am = -m_a*(c*U*theta_dot/4 + c²*theta_ddot/32) - d*L_am
```

These agree with the independently derived transfer expressions supplied by the `independent_flutter_reference` agent. The factor c²/32 in the pitch-acceleration term is correct: in printed unsteady equation 44 the c/4 outside the bracket multiplies c/8 inside it.

| Document expression | Implementation | Finding |
|---|---|---|
| Unsteady 26,30–32: relative incident velocity includes local translation and rotation | `aero.py` 323–331 and `LocalMotion.velocity_at`, `local_motion.py` 95–96 | Correct at the supplied evaluation points; see finite-incidence point caveat below. |
| Unsteady 34–35: rho*Gamma*(V cross s) plus rho*c*Gamma_dot*(V cross s)/Vperp | `aero.py` 456–457 | Signs, normalization and both terms agree. |
| Unsteady 36: both steady and rate lift act at quarter-chord | `aero.py` 484–487 | Both receive the same true local quarter-chord moment arm. No midchord relocation of the rate lift is warranted. |
| Unsteady 43: normal apparent force from V cross total angular rate minus midchord acceleration | `inertia.py` 172–180 | Correct scalar pitch/heave reduction; local acceleration evaluated at true midchord. |
| Unsteady 44: intrinsic apparent couple plus midchord force arm | `inertia.py` 181–182 | Correct U*theta_dot coefficient, c²/32 rotary term, force-arm sign. |
| Steady 84–85: velocity in apparent rate term evaluated on beam axis | `aero.py` 488–500 | Correct point. Includes induced, gust and jet flow when angular rates make the term active. |
| Unsteady 48–51: empirical downwash -(2/pi)*Gamma_dot/Vperp | `aero.py` 376–384,454–455 | Correct sign and coefficient. At fixed dCLda=2pi the transfer is (1+2ik)/(1+4ik). |
| Physical circulation-rate units | `linear_dynamics.py` 96–100; kinematic rows 111–114 | Gamma_dot decodes with the same circulation scale, with derivatives per input T. No extra W factor belongs on it; W scales angular-velocity states, not input time. |

The independently reduced apparent-load scalars were compared with `surface_apparent_loads` in 48 cases: four reference-axis locations, four pitch/heave combinations and three orientations including the vertical-wing orientation. Maximum absolute component difference was 3.47e-18 in input force/moment units. This verifies that reduction and frame transport, not the entire aerodynamic solver.

Circulation orientation is also consistent: a bound filament directed along +s induces negative n velocity at a downstream control point; positive geometric incidence is cancelled by positive Gamma, which generates positive n force because c cross s=n. Quarter-chord moment then has sign -a*L. For the 25% reconstruction, a=-0.00004723 m; for 75%, a=-0.012695424 m. The small 25% quarter arm sharply limits the direct moment effect of an alternate quarter-point convention.

## Finite-incidence point convention: unresolved, not a correction

Steady equations 155–157 locate the vortex and control points along the freestream direction xi, divided by |xi cross s|. `frozen_influence.py` 14–41 implements those expressions. `aero.py` then samples the moving-section velocity at those same points. Unsteady equations 29–31 instead define the quarter-chord offset as `(c/4-xo)*c_hat` for its local motion. The force moment remains at the true local quarter-chord in the code, as required by both moment expressions.

For an unswept straight section whose chord and wind differ by delta, the normal pitch-rate velocity at a wind-aligned point has an extra cos(delta) factor compared with a point at the same chordwise distance along c. The difference vanishes in the zero-incidence linearization because the altered point offset multiplies the first-order angular rate. At a loaded finite-incidence base it survives in the tangent. The JSON records exact geometric comparisons at 0°,5°,10°,20° and -8.3885°. The latter corresponds approximately to the recorded 25% tip chord rotation -12.5585° plus body beta4.17°, ignoring bending-induced changes of local span. Its factor difference is about 1.07%, and its quarter-point separation is about 6.9 micrometres. These local estimates do not quantify a flutter-speed shift.

The unsteady text only derives the control-point scalar formula in a small-disturbance 2D limit; it does not explicitly settle a finite-incidence replacement of the steady control point. Therefore a changed finite-angle implementation requires a justified interpretation and an independently discriminating check. It cannot be presented as an established bug from this audit or substituted to match the thesis.

## Durrant root-locus comparison scope

Section4.2 explicitly says Figures4.9 and4.10 use aerodynamic cases1–4 at incidence4.17° (`thesis.txt` 4513–4518; printed75/PDF88). Figure4.10 identifies Case4 by its solid line. Thus the Case4/physical-incidence comparison is supported. Neither the figure nor surrounding text specifies the original ASWING body beta setting, and the original `.pnt` input is absent; that software-coordinate mapping remains unverified. The approximate 21Hz frequency and branch-shape reading must remain separate from the precisely tabulated Case4 speed33.21m/s.

## Next check

Use the independent full lift-and-moment transfer evaluation under development to check the entire flat-section evaluation path, rather than changing an algebraically correct term. If that agrees, isolate finite-span induction and the loaded-state/stall tangent with explicitly labelled diagnostic variants. Retain the virtual/true point distinction as a finite-angle source interpretation to resolve, without treating it as the demonstrated explanation for the 25% discrepancy.

Reproduction: the unchanged `/tmp/audit-openswing-unsteady-implementation-20261009.py` was rerun with `/home/userland/aswing/.venv/bin/python`; its complete original JSON reproduced exactly. The prior reports are preserved in `/tmp/openswing-durrant-source-audit-20261009/before-correction/`. The 48 executable comparisons cover `surface_apparent_loads`; the other formula-table entries are algebraic inspections. All pinned source hashes were rechecked.
