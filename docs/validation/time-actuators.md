# Inverse actuator targets during time integration

This increment is integrated. It adds implicit flap/engine targets while retaining
the unsteady trajectory equations. Full ASWING compatibility remains unproven.

All 140 distinct targeted native tests have passing evidence. The corrected
eight-file collection initially retained one error-message expectation failure;
restoring the expected phrase and rerunning the affected initialization file and
all new actuator tests produced 43 passes. The other 97 passes remain unchanged.
All 52 standalone JavaScript tests and both final offline WebGL browser workflows
pass, including case/solution restoration, checkpoint continuation, legacy-case
defaults and saved-equilibrium launch.

Six independent native mechanics/refinement/unit cases compare 714 physical
values. Maximum force/acceleration error is below 4e-14; BDF1/BDF2 refinement
reduces trajectory error, and Radau matches the polynomial trajectory within
4e-15. Converted-unit physical differences are below 8e-13. Four packaged-WASM
replays independently check their references and compare 350 physical values
with maximum scaled native difference 1.33419e-14. The standalone figure and
final desktop/mobile/plot captures were inspected. Raw outcomes, source/runtime
fingerprints and retained failures are in `time-actuators-checks.json`.

The preceding integrated stall kernel passed all 1,188 native tests. The new full
1,216-test, 71-file regression is separate and remains pending; the original
supervisor stopped after one passing 21-test file, whose evidence is retained.

The [public ASWING guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
describes selection of operating constraints, time tables acting on active
constraint parameters, and the distinction between steady constraints and the
unsteady kinematic equations. Imposing velocity directly during unsteady motion
requires changing the original program's constraint logic. The
[unsteady formulation, §11.2.3](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf)
also admits implicit residual equations for flap and engine controls. OpenSwing
retains the existing trajectory equations and adds explicit actuator/target pairs
to its common implicit system.

`actuator_constraints` is a list of `variable`, `quantity`, and `target` records.
Variables are declared `control.#` or `power.#` actuators. Targets are net force,
net moment, linear/angular frame acceleration, surface lift, or radial
acceleration. A frame acceleration target requires the corresponding free or
mixed net-load equation. Each actuator and target has one owner; duplicate
targets, simultaneously prescribed actuators, and competing controller laws are
rejected. An acceleration forcing label cannot simultaneously be an inverse
target and a controller command, including alternative capitalization.

The browser accepts rows such as `E1 Ax .2` or `F1 My 0`. Target values use input
units; `Gx/Gy/Gz` use degrees/input T² in browser rows and forcing tables, with
radians/input T² in the kernel API. The `L` target remains lift at load multiplier
N=1; the instantaneous equation applies the selected N. Net loads include
inertial reaction, while support reactions remain separate. The existing radial
acceleration definition and reference offsets are retained.

Forcing tables can vary the active targets, including `L` and `Ar`. Relative
columns add the initial target, and all specified values become zero after the
last sample. Saved-equilibrium launch checks the original state before applying
new time inputs. Checkpoints retain target selections, actual actuator values,
original forcing offsets, and BDF history. The time view plots and exports solved
actuator settings, separately from prescribed input columns. Named cases and
computed archives retain the new settings; older cases default to no inverse
actuator constraints.

Every accepted inverse BDF step or Radau stage system undergoes an additional
centered finite-difference rank check at the accepted solution, with column and
row scaling. This detects unresolved actuator authority even when the residual
is zero. It is local numerical evidence; it does not prove global branch
uniqueness. Optional temporal checks also compare solved actuator settings.

The independent rigid-body study prescribes `a_x(t)=0.2+t` for a one-kilogram
body with no other forces. Its required force is `F_x(t)=0.2+t`, and direct
integration gives `U_x(t)=-10+0.2t+t²/2` and
`X(t)=-10t+0.1t²+t³/6`. BDF1 and BDF2 use two step sizes; Radau integrates this
polynomial reference. A separate length/time/force unit system checks physical
equivalence. The tests additionally check independent torque/inertia relations,
forcing jumps and cutoff, a prescribed-motion net-force target, flap pitching
moment, surface lift with added mass and N scaling, and radial acceleration with
distinct reference points and rotating axes.

Initial failures are retained: a test command named a nonexistent file; an older
checkpoint lacked the optional load-target field used by new result reporting;
and the radial reference test requested physical accuracy tighter than the
default normalized solve tolerance. The checkpoint report now derives its
targets from the restored system. The radial solve uses a tighter tolerance
while preserving the original physical comparison threshold. Interrupted
browser/WASM supervisors have no terminal pass and remain incomplete records.
The first styled browser replay timed out at final WebGL inspection while a
native regression also ran. The next attempt failed before loading the page
because its local server had stopped. The final two workflows use their own
recorded server, unchanged assertions and unchanged 600-second timeouts.

Velocity, attitude, position and climb-angle inverse histories, legacy companion
file interoperability, original spline endpoint conventions, aircraft validation,
and full ASWING executable parity remain open.
