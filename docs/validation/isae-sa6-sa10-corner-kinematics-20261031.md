# SA-6/SA-10: corner intervals and material-point kinematics

2026-10-31. Two specific hypotheses are now ruled out as standalone fixes:
adding the omitted zero-length aerodynamic corner interval in SA-10, and
changing only the rotational-velocity sampling points in SA-6. No production
equation, input, tolerance or registered pass count changes.

## SA-10: the corner interval cancels

The [ASWING guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
requires duplicated computational nodes at prescribed geometry breaks. The
[steady description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
section 2, permits a finite frame-angle jump across zero material length.
This supports preserving the two one-sided frames at Louvered's 45° bend,
rather than averaging the corner into a smooth section.

For this literal geometry the coincident structural nodes have quarter-chord
endpoints A and B separated only along the wind direction. If a complete
horseshoe is assigned to the zero-length structural interval, its velocity is

`V_AB = V_finite(A→B) + V_ray(B) − V_ray(A) = 0`.

The finite filament exactly cancels the difference of its two trailing rays,
for any circulation. Its physical force length and Fourier integration
weight also vanish. Adding only a trailing-ray term would omit that required
bound-filament cancellation and change the model incorrectly.

The audit uses all nine retained pointwise conditions: 5°/15°/25° on the
100/200/400 requested meshes. It tests four neighboring receivers on each
of the two bends. Independent 60-digit integration gives **72 vectors**;
production kernels give **144 vectors**, including an additional Mach-0.6
transformation control. Maximum residual interval velocity is 5.86e−13 of
freestream speed. The two previously rejected refined states remain
rejected; these are field evaluations, not new accepted aircraft solutions.

A second manufactured control removes the endpoint gap entirely: two
straight bound filaments share one vertex and form a continuous 45° bend.
At distance d from that vertex, the neighboring bound filament approaches

`V_x = Γ tan(22.5°) / (4π d)`.

Ten independent finite-filament evaluations, on both sides over five
distances, approach this limit; the smallest-distance relative discrepancy
is 8.54e−13. Therefore sharing endpoints alone cannot guarantee a bounded
local velocity at a sharp nonzero-circulation bend. This explains why the
missing zero-length interval is not the cause of the previous refinement
failure. It does not authenticate native ASWING's complete force sampling.

[Plan](../../artifacts/isae/sa10-corner-interval-20261031/plan.json),
[results and analytic controls](../../artifacts/isae/sa10-corner-interval-20261031/analysis.json).

## SA-6: material-point rotational velocities do not recover the rates

The [unsteady description](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf),
equations (29–30), places the quarter-chord kinematic point along the section
chord. This differs from extending the steady wind-directed source location
to kinematics. The diagnostic keeps the frozen induced-flow operators and
the verified strength-20 base states, and changes only the rotational
velocity term `−Ω × r`. It does not move vortex sources or induced-field
receivers. Two variants were declared before either result was inspected:

| Sampled state-derivative scope | Pass count | Gains | Losses |
|---|---:|---:|---:|
| Original frozen settings | 253/288 | — | — |
| Material quarter-chord kinematics; original CP kinematics | 245/288 | 0 | 8 |
| Material quarter-chord and analogous material CP kinematics | 247/288 | 0 | 6 |

The second variant is an explicit extension to the control point, not a
claim that equations (29–30) specify that location. Eight operating points
cover all four paired chordwise models at 4° and 44° control, on the finest
registered mesh. All sixteen saved-matrix responses finish. Independent
differentiation of the force, moment and leakage equations supplies the
changed forcing; the largest scaled linear residual is 8.54e−16. Static,
F1, speed, incidence and sideslip responses stay unchanged by construction.
These are linear sensitivity calculations, not modified nonlinear solves.

At the 15%-chord model's 4° control, native CLq is 1.99878. The baseline is
2.09195; the two variants give 2.15664 and 2.16935, farther from the target.
CXq, Cmq and Cnq also worsen there. This does not resolve the pitch-rate
discrepancy or justify a production change.

[Quarter-chord-only results](../../artifacts/isae/sa6-material-kinematics-20261031/hv/receiver-analysis.json),
[quarter-chord/control-point results](../../artifacts/isae/sa6-material-kinematics-20261031/hv-cp/receiver-analysis.json).

## Related source lead and remaining work

Drela's [JVL 2.20 formulation](https://web.mit.edu/drela/Public/web/jvl/jvl.pdf),
section 9.2, derives an additional self-induced velocity from a gently curved
vortex sheet. Its small-curvature assumption and finite sheet area are
explicit. That is a useful distinction from a sharp lifting-line corner,
but it is not an established ASWING correction. The rendered derivation was
inspected and [retained with provenance](../../artifacts/isae/sa10-corner-interval-20261031/reference-source.json).
No JVL term or smoothing parameter was inserted into OpenSwing.

SA-6's rate/export convention and SA-10's native discretization/force
convention remain unresolved. The previous complete diagnostic comparisons
and their native-setting qualifications remain in force. The
[verification receipt](../../artifacts/isae/sa10-corner-interval-20261031/receipt.json)
records the inputs, terminal processes and unchanged registered acceptance.
