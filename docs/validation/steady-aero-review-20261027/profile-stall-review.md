# SA-1 profile-drag and stall source review

**No confirmed profile-drag or stall formula mismatch was found in this bounded review.** This does not establish numerical agreement with ASWING. No production import, test, residual, matrix assembly or solve was performed. The [JSON receipt](profile-stall-review.json) pins the reviewed implementation and primary documents and records exact line/equation references.

| Reviewed behavior | Source comparison | Finding |
|---|---|---|
| Lift and section-normal speed | Steady equations 64, 67 and 69 | The implementation uses relative velocity at the bound-vortex receiver, with its own bound filament excluded. No mismatch identified. |
| Friction and pressure drag | Equation 70 | Both use bound-point velocity, with pressure drag projected perpendicular to the span. The source marks the normal-velocity square in the third term as control-point evaluated; it does not support replacing every profile-drag velocity with control-point velocity. |
| Separation drag | Equation 70 | Uses `2 rho (Vperp / abs(Vperp)) (Vcp · ncp)² chord`, integrated over current interval length. No mismatch identified. |
| Section lift and leakage | Equations 157 and 202–204 | `cl = 2 Gamma / (chord Vperp)` and leakage `Vperp / dCLda * Ks * fstall` agree because `4 pi h = dCLda`. |
| Stable logarithmic stall law | Equation 204 | The `log1p`/`expit` formulation is algebraically equivalent to the published log ratio; its threshold changes numerical evaluation, not the constitutive model. |
| Stall factor and width | Theory pages 40–41 | Defaults 40 and .05 match the theory’s approximate recommended choices. The original 5.96 build constants are not authenticated. This is a setup qualification, not a demonstrated defect. |
| Section moment | Equations 72–74 | Uses the physical quarter-chord lift arm, local-normal-Mach correction of section Cm, and no extra local profile-drag couple. SA-1’s zero section Cm does not remove its lift-arm pitching moment. |
| Unsteady terms in the steady limit | Unsteady equations 33–36 and 48–49 | Circulation-rate lift and control-point lag correction vanish for steady SA-1. Beam-axis velocity belongs to the separate apparent-mass calculation. |
| Fast/current influences | Guide K/F and K/M | Frozen coefficients use undeformed geometry and zero wind angles; current circulation, loads and independently chosen Mach remain active. No contradiction was found for rigid steady SA-1. |

One cross-document distinction remains open for the separate geometry review: steady equation 155 constructs a wind-aligned virtual bound receiver, whereas unsteady equation 29 names a physical quarter-chord arm along the section chord direction. Current code uses the steady receiver construction and the physical moment arm. Interpreting general moving-section kinematics across those descriptions needs separate evidence; it does not establish that SA-1’s steady drag sampling is wrong.

The original script’s F toggle does not identify its pre-toggle startup setting, and the report does not recover the original stall constants. Neither uncertainty licenses choosing the setting or constants that best match the archive. The complete native target set, literal model and original comparison intervals remain unchanged.

Relevant files: [aero.py](../../../openswing/aero.py), [frozen_influence.py](../../../openswing/frozen_influence.py), [steady theory](../../../.reference/asw_theory.pdf), [unsteady theory](../../../.reference/asw_uns_theory.pdf), and [ASWING guide](../../../.reference/aswing_doc.txt). The broader [source inventory](../isae-sa1-source-readiness-20261027/report.md) records native and modified-figure provenance separately.
