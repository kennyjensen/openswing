# AE-2 comparison with archived ASWING: solver settings

Updated 2026-10-25. The target is reproducing tested ASWING results with the
original model and matched operating settings. Experimental agreement is not
an acceptance requirement. The broader OpenSwing goal remains incomplete.

At the archived 5° / commanded 10 m/s point, frozen influences reduce the
fine-mesh tip-displacement difference from 1.17% to 0.43–0.47%. Sensor heading
and speed also improve. The sensor flow-angle difference remains about 0.14°.
None of the four configurations reproduces all four outputs to printed precision;
this is a completed settings comparison, not a full reference-case pass.

## Inputs and scope

The original `[03_90].asw` bytes are retained, SHA-256
`eb35a50606bcceee263352cbd40ffd509b504082c78ba61732ad52ce03193db8`.
No stiffness, section-property or atmosphere fit was made. The previously
considered specimen-stiffness reconstruction is excluded from these runs.

The archived scripts set anchored constraints, a solid wall, beta and an IAS
sweep. They do not specify the historical K/F influence setting or K/M PG Mach.
The report attributes this case to ASWING 5.96, but the producing executable and
startup setting files are unavailable. Official menu examples support the finite
alternatives below; they do not recover the historical settings. Density
1.23 kg/m³, altitude zero, IAS treated as TAS, identity frame and gravity
9.81 m/s² remain declared assumptions. Local section Mach and selected PG Mach
are separate quantities in the implementation.

The predeclared comparison is updated/frozen influences × PG zero/U÷340.21
on nominal 80/160 meshes (81/161 actual elements). It contains six new independent
cold solves and two exact reused updated/U÷340.21 pilot states. All four
configurations are retained; choosing the smallest error does not establish
historical provenance or justify changing application defaults.

## Results

The archive target at file line 14 is RY = −0.0258200 m, Psi = −0.572223°,
V = 10.0115 m/s, beta = 6.27943°. The file's `t=11` is a stack coordinate,
not speed. Displacement is minus Earth Y at the literal midchord sensor;
there is no gravity-baseline subtraction. Psi is heading and sensor beta is
local aerodynamic flow angle; they must not be interchanged.

Fine-mesh results; differences are OpenSwing minus archived ASWING:

| Influences | PG Mach | Displacement (mm) | Displacement difference | ΔPsi (°) | ΔV (m/s) | Δbeta (°) |
|---|---|---:|---:|---:|---:|---:|
| Updated | 0 | 26.114624 | +1.1411% | -0.006033 | -0.041887 | -0.152655 |
| Updated | U / 340.21 | 26.122996 | +1.1735% | -0.006222 | -0.041897 | -0.152123 |
| Frozen | 0 | 25.932300 | +0.4349% | -0.001949 | -0.002423 | -0.137598 |
| Frozen | U / 340.21 | 25.940568 | +0.4670% | -0.002135 | -0.002417 | -0.137050 |

All eight mesh checks pass the predeclared 1% relative limit: displacement and
incremental projected twist for each configuration. The largest change is
0.01489%. Mesh differences use the finer value as denominator, no numerical floor,
and an explicit exact-zero rule. Total angle including the prescribed 5° is
not used to dilute the twist convergence metric.

The independent saved-data audit passes 1,046 checks.
All six new cases pass fresh full-equation residual, global force/moment
balance, root-clamp and physical-wall checks. Across all eight states the maximum
fresh normalized residual is 6.071e-13.
New cold solves take 1.09–2.65 s each, 11.51 s combined; the sequential batch
including six process startups and verification takes 72.88 s. No browser or
production-kernel change was made in this study.

The strict rounding comparison uses half the last printed place independently
for each archived output. It is a diagnostic of literal numerical reproduction,
not a tolerance selected after seeing the errors. Differences remain larger
than that precision for all configurations.

## Remaining reference work

The uncoupled archive has 87 positive-speed states across beta 1°, 5°, 10° and
15°, with four finite output channels per state. Four initial zero-speed rows
contain only NaNs and are retained as missing reference data. This study checks
one of those 87 coordinates on two meshes. The remaining curves, other layups,
and additional aeroelastic outputs remain unverified.

Next, resolve the sensor flow-angle difference and remaining setup/discretization
uncertainty, then compare the full archived sweeps under explicitly recorded
settings. A low displacement error alone does not establish a four-channel
match. Experimental disagreement does not block this reference target.

[Archived coordinate catalog](isae-ae2-aswing-catalog.md) ·
[Values and mesh checks](isae-ae2-aswing-settings.json) ·
[CSV](isae-ae2-aswing-settings.csv) ·
[Predeclared plan](isae-ae2-aswing-settings-plan.json) ·
[Source review](isae-ae2-aswing-settings-sources.md) ·
[Independent saved-data audit](isae-ae2-aswing-settings-audit.json) ·
[Raw evidence](isae-ae2-aswing-settings-20261025-evidence.zip)

## Sensor-field follow-up

The [independent field diagnostic](isae-ae2-sensor-reference.md) evaluates eight
field products using the two saved frozen-PG0 states, with zero new equilibria.
All 130 field checks and 711 saved-data audit checks pass. Moving only the
receiver worsens agreement: at nominal 160, speed becomes 10.1202114303 m/s
and beta 5.95590644131°, versus archived 10.0115 m/s and 6.27943°.
The current jig-receiver result is independently reproduced. Historical
sensor/core and circulation settings remain unresolved. Coordinate coverage
is still one of 87; no model or default changed.
