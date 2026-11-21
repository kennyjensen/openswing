# Nonlinear endpoint apparent-fluid loads

Updated 2026-10-30. The thin-strip endpoint operator now includes the full
noncirculatory velocity/rate and acceleration terms of the unsteady theory.
It is a prerequisite for flowing source dynamics, not a completed source
airflow network or a new browser analysis policy. The active aerodynamic path
shares its force/couple arithmetic, preserving its previous results.

## Implemented physics

[`endpoint_motion_wrench`](../../openswing/apparent_box.py) accepts relative
fluid velocity at the beam axis and absolute axis acceleration, section rate
and angular acceleration. With physical chord/span/normal axes `c_hat/s_hat/n_hat`,
the midchord offset is `d=(0.5-Xax)*chord*c_hat`. Its acceleration is

```
a_mid = a_axis + alpha_abs × d + omega_abs × (omega_abs × d)
```

For a moving frame, `omega_abs=Omega+omega_local` and
`alpha_abs=alpha_frame+omega_local_dot+Omega×omega_local`. The angular transport
term follows differentiation in Earth axes, consistent with the existing source
moving real-inertia operator. This is an explicit physical interpretation of
the transport omission in the printed equations, not an assertion about a
historical ASWING executable.

Using `mu=pi*rho*chord²/4` and `h=(V_relative×omega_abs)·n_hat`, the force and
couple densities about the beam axis are

```
f = mu * (h - a_mid·n_hat) * n_hat
m = d × f - mu * (chord*h/4 + chord²*(alpha_abs·s_hat)/32) * s_hat
```

These are the thin-strip loads in Drela's
[unsteady theory](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf),
Eqs.41–44, with the moving-frame interpretation stated above. Zero-lift angle
and controls do not rotate the physical material axes. The function has no
airspeed division and permits zero chord or density; this does not imply a
complete zero-speed circulatory solver.

`interval_motion_wrench` averages completed endpoint force/couple products over
the declared material interval. It takes the averaged force moment about the
arithmetic midpoint, as in the box balance/Eq.266. It does not average endpoint
`r×f`, symmetrize the response or add a real-mass `ds²/12` correction to fluid
inertia. At zero rates it reduces to the previously verified endpoint
acceleration operator, including varying-property nonsymmetry.

The existing `surface_apparent_loads` retains its current section sampling and
absolute kinematics, and calls the shared section-force kernel. No circulation,
wake, stall, force-receiver or aerodynamic quadrature convention changed.

## Verification

The [machine record](source-apparent-motion.json) pins production modules and
retains the exact check scope. Evidence is under
[`artifacts/isae/source-apparent-motion-20261030`](../../artifacts/isae/source-apparent-motion-20261030/).

* **160 native tests pass**, including 19 new endpoint/interval checks. They
  cover analytical pitch/heave loading, centrifugal loading, the stationary
  limit, rotation/translation covariance, endpoint-product averaging and all
  six rigid acceleration-response columns.
* A separate five-point/Richardson derivative of an actual composed Earth-frame
  point trajectory checks absolute midchord acceleration. Nonparallel frame
  and local rates distinguish the angular transport term from its omission.
* **All 19 new checks pass in WASM** against the packaged modules.
* **256 saved pre-change force/moment pairs, 1,536 components, are bitwise
  identical natively.** The WASM comparison also has zero measured difference.
  The retained fixture covers rigid and elastic motion and varying section
  geometry, including zero chord and zero interval length.
* All seven ordinary time/frequency browser scenarios pass across the original
  run and the corrected rerun. They include offline solves, actual free-flight
  motion, forcing events, playback, exports, frequency channels, cancellation,
  and mobile rendering. These exercise the existing analysis routes, not a
  newly enabled source airflow route.

Two test issues were retained and resolved. A rigid-motion zero-strain test
failed at `4.48e-15` against its fixed `3e-15` bound; the same failure was
reproduced using the pre-change production modules. Its bound now scales with
floating-point precision, interval length, and the respective velocity/rate
units. No production or ISAE tolerance was relaxed. The browser test needed
to select the mobile Settings tab before editing duration; the corrected
workflow passes without a UI code change.

## Remaining integration

The endpoint API receives a supplied fluid velocity. It does not choose a
wake receiver, solve circulation or assemble the full flowing source network.
The published aerodynamic discretization uses Glauert force/control points;
blindly evaluating wake velocity at structural endpoints could place a receiver
on a trailing filament. That sampling and coupling must be resolved consistently
with the documented aerodynamic formulation before enabling source airflow
modes, time response or frequency response.

The existing stationary source-fluid policy and its identity are unchanged.
Body apparent mass, finite-span fluid effects, wall corrections and point
aerodynamic volumes are outside this thin-strip operator. Full-aircraft source
dynamic validation, archived ASWING agreement and the SA-1–SA-5 discrepancies
remain unfinished. `ISAE_STATUS.md` and its passing counts are unchanged.
