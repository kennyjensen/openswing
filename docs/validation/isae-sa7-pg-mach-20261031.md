# SA-7: actual flight Mach does not resolve the efficiency difference

2026-10-31. Six cold solves test the documented Prandtl–Glauert Mach option
on the full tandem model. The 70 m/s driver speed gives an atmospheric Mach
of **0.20575527**. Using that value instead of the retained incompressible
choice leaves the sample at **20/21** checks and worsens the remaining
−5° efficiency error from **3.540% to 4.134%**.

Registered SA-7 remains **395/812**, including its mismatched current
fore-only pairing. The separate strength-20 full-aircraft diagnostic remains
**404/406**. This experiment supplies no new registered passes or production
default change.

## Predetermined test

The guide and steady theory allow the PG Mach to equal the actual flight
Mach or a prescribed value; theory section 4.1 permits zero for low-speed
work. The historical PG setting is unrecorded. This is a direct comparison
of those two documented choices, without fitting an intermediate Mach.

Both choices use the same literal full-aircraft model, 128-interval mesh,
current influence geometry, and previously investigated stall strength 20.
Angles −5°, 0° and 20° cover the remaining efficiency failure and two passing
controls. The 3%/original-absolute gates remain unchanged. Strength 20 is
still a qualified reconstruction, not an authenticated native setting.

| Incidence | PG Mach = 0 | PG Mach = 0.20575527 | Remaining failure |
|---|---:|---:|---|
| −5° | 6/7 | 6/7 | Efficiency: +3.540% → +4.134% |
| 0° | 7/7 | 7/7 | None |
| 20° | 7/7 | 7/7 | None |
| Total | 20/21 | 20/21 | Zero gains, zero losses |

The predeclared rule was to extend the actual-Mach choice to the full polar
only if it gained checks without losses. That condition is not met, so no
full rerun is launched or implied. These six calls do not certify either
setting over the entire polar.

## Verification

All six solves converge, remain locally subsonic, and terminate successfully.
Independent strip reconstruction gives maximum circulation-equation residual
**1.72e−14**, normalized by flight speed. Resultant forces agree exactly and
origin moments within **4.45e−16** after coefficient normalization. A separate
verifier checks all **42 native scalar comparisons**, the actual-Mach
calculation, source hashes, pass transitions and the extension decision.

The remaining low-lift discrepancy is therefore not removed by this
documented compressibility alternative. Native discretization and producing
settings remain unresolved. Solver equations, target values and comparison
policy are unchanged; the full project remains incomplete.

Artifacts: [plan](../../artifacts/isae/sa7-pg-mach-20261031/plan.json),
[results and equation checks](../../artifacts/isae/sa7-pg-mach-20261031/analysis.json),
[verification receipt](../../artifacts/isae/sa7-pg-mach-20261031/receipt.json),
[run log](../../artifacts/isae/sa7-pg-mach-20261031/run.log).
