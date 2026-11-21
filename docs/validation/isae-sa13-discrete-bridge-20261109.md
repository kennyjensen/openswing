# SA-13: discrete lift relation verified through the full JSON solve

Three complete rigid aerodynamic requests through `run_worker_json` reproduce
**180 valid archived lift-station values to roundoff** on the explicitly
reconstructed linear-radius segments. This extends the earlier isolated
body-kernel check through parsing, mesh construction, aerodynamic evaluation,
force/moment assembly, coefficient normalization and JSON serialization.

No production solver module changed. The plotted force-per-length quantities
now explicitly say that they are **interval averages**, helping distinguish
them from the station densities in the archived curves.

## Results and setup

| Hull | Compared stations | Maximum absolute station-coefficient error | Aerodynamic JSON call time | Complete process time |
|---|---:|---:|---:|---:|
| R33 | 62 | 1.14e-15 | 0.132 s | 6.75 s |
| R101 | 54 | 6.67e-15 | 0.073 s | 9.72 s |
| RS1 | 64 | 1.02e-14 | 0.050 s | 7.45 s |

The process times include Python imports and source verification. These are
body-only cases; they do not establish timing for coupled aircraft analyses or
browser loading. Peak RSS is 217–221 MiB. Each serial job had one BLAS thread,
512 MiB address-space, 15 CPU-second and 25 wall-second limits.

The inputs are the unchanged `.asw` reconstructions from the
[discrete-load audit](isae-sa13-discrete-loads-20261109.md): stored positive
radii, two-point linear radius pieces and explicit stored x stations. The
requests use unit speed/density, zero PG Mach, the default frozen influences,
and the independently identified angles 10°/10°/9°. No load value participates
in geometry construction or result conversion. These remain disclosed
reconstructions, not recovered original input files.

All three requests converge and contain no lifting panels, concentrated body
shoulder loads or other applied aerodynamic sources. The same original
terminal-zero assignments, invalid R33 tail interval and missing reference
values remain outside the physical replay and inside the retained scope.

## Recovering station density from public output

The verifier consumes only each returned strip's integrated force `F_z`,
integrated local moment `M_y`, length `h` and reported reference position `x_r`.
For these uniform-flow linear-radius segments, Eq.68 gives an affine force
density. Its two coefficients are therefore determined by total force and first
moment. With `x_c` the arithmetic interval midpoint:

```text
M_y about midpoint = M_y + (x_c − x_r) F_z
f_z at left station = F_z/h + 6 M_y_about_midpoint/h²
C at left station = f_z/(q∞ D_max).
```

This conversion does not call `body_loads` and does not subtract a correction
computed from the archived load. It also **does not apply to an arbitrary
non-affine load distribution**: integrated force and moment cannot uniquely
recover such a distribution.

The moment-reference translation matters. The public `strip.position` is a
Glauert force point, generally different from the arithmetic midpoint. Treating
its local moment as a midpoint moment produces maximum coefficient errors
of **0.304, 0.299 and 0.443** respectively. The independent verifier includes
that incorrect conversion as a negative control.

## Independent integral and assembly checks

For each segment, the returned integrated force agrees with the endpoint-area
identity `F_z = ρ U² sin(α) cos(α) π(R_1² − R_0²)`. The local moment agrees with
the analytic integral of the squared linear radius about its actual reference
point. Whole-body force and moment also agree with the corresponding
open-ended body integrals, including endpoint terms, and the CL/CD/Cm
projections and normalizations agree independently.

An independent standard-library verifier reads the saved public JSON responses,
checks the original ordinate and radius data, and recomputes forces and moments
with Decimal arithmetic. Across all 180 intervals, maximum absolute differences
are **8.65e-20 in force** and **8.04e-21 in local moment**. It imports neither
OpenSwing nor numerical libraries and performs no new solve.

## UI description and evidence

[`loading-data.js`](../../web/loading-data.js) now titles the Fx/Fy/Fz-per-length
plots as mean loads and explains that the average is plotted at the reported
station. Numeric values, interpolation and physics are unchanged. The four
existing plotting-data tests pass; browser rendering has not been rerun.

- [Bounded JSON reproducer](../../scripts/check_sa13_discrete_bridge.py).
- [R33 record](../../artifacts/isae/sa13-discrete-bridge-20261109/r33.json),
  [R101 record](../../artifacts/isae/sa13-discrete-bridge-20261109/r101.json),
  [RS1 record](../../artifacts/isae/sa13-discrete-bridge-20261109/rs1.json).
  Each pins its saved request, full response and all 141 unchanged modules.
- [Independent verifier](../../scripts/verify_sa13_discrete_bridge.py) and
  [verification receipt](../../artifacts/isae/sa13-discrete-bridge-20261109/verification.json).

This is native Python through the browser's JSON boundary. It does not verify
the current packaged WebAssembly code or browser rendering; the existing
UserLAnd loading/build hold remains in place.

The primary SA-13 comparison remains **0/612**. Its complete original setup,
endpoint/output conventions, modified continuous curves and pressure mapping
are not established by this reconstruction. All missing references remain in
their denominators; no alternative or computed subset is added to the primary
progress total. SA-12 remains open.
