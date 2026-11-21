# SA-12 flapped image-wake hypothesis

Observed 2026-11-09 UTC. **A single endpoint-only image-wake approximation
reproduces all twelve sampled flapped CL/CD/CDi values within 0.93%.** It
also violates the induced no-through-flow condition at the ground. This is
evidence about a possible historical approximation, not an acceptable solver
correction or an authenticated reconstruction of the archived executable.
No production equation, default, model, tolerance or primary pass count changed.

The preceding [native AVL comparison](isae-sa12-avl-ground-20261109.md)
verified the physical wind-parallel image operator independently. The
[paired flap study](isae-sa12-flap-pose-20261109.md) found that switching to
frozen influences improves close-ground agreement but worsens the far-height
result. This follow-up tests the remaining endpoint-only hypothesis on the
same four flapped points, selected before calculation. It extends the earlier
[unflapped diagnostic](isae-sa12-pose-diagnostics-20261109.md).

## Controlled calculation

The original flapped model, speed, density, section slope and incidence,
nonlinear stall law, 100-interval mesh, height and raw reference targets are
unchanged. There are no fitted parameters or substituted drag measurements.
All four archived stall flags are zero.

The hypothesis uses zero Euler pitch and current influences. It reflects
both endpoints of each image bound vortex about the ground but retains the
original wind direction for the image's trailing legs. At nonzero alpha this
is different from reflecting the complete horseshoe path. The same choice
is used at every point; no point-specific setup selection is made.

An initial control uses the complete reflection and pitch=alpha at h/c=0.5,
alpha=2°. The independent nonlinear calculation reproduces the previously
saved production circulation within 5.51e−14 and coefficients within 4.00e−15.
Its sampled induced wall-normal velocity is 2.92e−16 m/s. The four hypothesis
calculations then run separately through the same diagnostic equations.

| Original flapped point | CL error | Raw CD error | Formal CDi error | Maximum sampled induced wall-normal speed |
|---|---:|---:|---:|---:|
| h/c=0.5, alpha=−5° | −0.0723% | −0.0193% | −0.1857% | **0.661 m/s** |
| h/c=0.5, alpha=2° | −0.4449% | −0.9271% | −0.3111% | **0.518 m/s** |
| h/c=2, alpha=5° | +0.1127% | −0.0634% | −0.0164% | **0.382 m/s** |
| h=1000 m, alpha=5° | +0.1349% | +0.0138% | +0.0193% | 1.42e−7 m/s |

Errors are signed relative to the magnitude of the raw ASWING reference.
The common parallel rays allow a formal infinite-wake CDi calculation, but
that does not make the ground image physically valid. All twelve lift/drag
values satisfy the 5% coefficient gates. Four exactly zero Cm predictions
still fail the unchanged gates for tiny archived moment residues. These
numeric matches add **zero** primary ISAE passes because this is a separate,
physically invalid diagnostic operator.

Compared with the physical wind-parallel baseline, the close-ground raw-CD
errors fall from −7.86%/+6.73% to −0.019%/−0.927%. At h/c=2, the error falls
from +1.50% to −0.063%. At 1000 m, the effect is negligible: the CD change is
−7.56e−10. Near-field circulation forces account for approximately 97.2%,
98.9% and 99.5% of the three finite-height CD changes. Direct stall drag is
at most 1.04e−6, and the smallest section stall margin is 5.11 transition
widths. The result gives no basis for changing stall parameters.

## Interpretation against the references

The [authoritative index](aswing-authoritative-references.md) and checksummed
source catalog remain controlling. Jan Part I **p.20 and Figure 8, p.21**
requires ground impermeability. Drela steady **§4.5, Eqs.165–173 and Figure
17, p.35**, describes the image geometry, while **Eqs.160–161** integrate
the vortex path. Reflection of that complete path satisfies the induced
ground boundary condition; reflecting only its origins generally does not.

The wall defect above measures induced velocity alone. It therefore does
not depend on interpreting a body-frame freestream component as penetration
through a stationary board. Separately, zero pitch at nonzero alpha does not
represent the wind-parallel tunnel reconstruction described by the baseline.
Both distinctions matter when interpreting the original scripts.

The consistent improvement across flapped and earlier unflapped samples makes
a historical image/wake approximation a stronger explanation than it was from
the unflapped points alone. However, it **does not prove** that the ISAE-modified
ASWING binary used this operator. Its source, initial K/F state and numerical
Euler attitude are unavailable. The four-point experiment changes pose and
image-wake construction together relative to the baseline; it does not uniquely
identify every historical setting. The earlier unflapped control separately
showed that zero pitch with complete reflection left an 11.01% raw-CD error.

Jan Part I **p.38 and Figure 23, p.40** and the original shell/model files
remain the setup evidence. The report's post-stall limitation and MATLAB's
no-flap `0.01 + CDi` plotting replacement were not used to alter these raw
targets. Close archive agreement alone cannot justify installing an operator
that conflicts with the ground boundary condition.

## Verification and consequences

Five independent diagnostic equilibria completed: one physical replay control
and four hypothetical image constructions. Maximum normalized circulation
residual is 1.24e−14. An independent finite-difference directional check of
each nonlinear Jacobian agrees within 1.04e−11 relative. Saved raw reference
tokens and all sixteen hypothesis decisions were checked with Decimal
arithmetic; **198 source/artifact hashes verify**.

Each invocation ran serially in the foreground with one BLAS thread, 512 MiB
address-space, 15 CPU-second and 25 wall-second limits. Jobs took 3.05–17.12 s
with peak RSS below 192 MiB. No browser, build, background solver or additional
production solve was started.

- [Immutable plan](../../artifacts/isae/sa12-flap-image-wake-20261109/plan.json)
- [Results, source pins and drag decompositions](../../artifacts/isae/sa12-flap-image-wake-20261109/analysis.json)
- [Serial diagnostic driver](../../scripts/diagnose_sa12_flap_image_wake.py)

### Regression against the physical boundary condition

A subsequent source review confirmed that both current and frozen production
fields already use the factored influence operator at every mesh size; there
is no separate fine-mesh switch that could explain the archive discrepancy.
The complete-path image reflection remains in both the direct kernel and the
optimized operator. Figure 17 was visually checked again; it does not establish
the missing historical Euler attitude or the modified binary's implementation.

The new `test_cosine_wing_images_cancel_induced_ground_normal_flow` in
[test_factored_influence.py](../../tests/test_factored_influence.py) protects
the physical constraint independently of archived coefficients. It uses the
SA-12 span and closest quarter-chord height, cosine meshes with 32/200
intervals, wind angles −5°/+5°, and zero/quarter-chord vortex cores. Across
all eight combinations the factored field agrees with the direct field and
cancels induced ground-normal flow at nine probes within 2e−13 m/s. The
endpoint-only construction exceeds 0.01 m/s in every combination, confirming
that the fixture detects this specific incorrect approximation.

**8 tests passed in 10.91 s**. Two preceding bounded attempts exited on their
25-second alarm before reporting test results. The successful lightweight
pytest invocation retained one BLAS thread, 512 MiB and 15 CPU seconds, with
a 45-second wall cap and no external plugin discovery or assertion rewriting;
Python assertions remained enabled. It finished in 17.57 seconds including
startup. Solver-job limits were not changed. The [receipt](../../artifacts/isae/sa12-ground-boundary-regression-20261109/receipt.json)
retains both timeouts and the successful run, and verifies unchanged production
source hashes against the preceding native-AVL plan. No new equilibrium solve
or primary ISAE pass results from this regression coverage.

### Inspecting the image geometry in the app

The solved **Horseshoes** view now includes image vortices when solid-ground
or free-surface images are enabled. Real bound lines/wakes remain cyan/violet;
image bound lines/wakes are amber/rose. This makes the ground/wake orientation
visible when inspecting SA-12. Both real and image wakes are drawn for one
reference span; the solver still uses semi-infinite legs.

[vortex-overlay.js](../../web/vortex-overlay.js) reflects both endpoints and
the wake direction using the solved body-axis plane, then applies the same
display-frame transform as the aircraft. Frozen influences use their returned
jig sources and wake direction. Time snapshots use their own solved plane;
modal/Bode views show their base-state images. This changes the drawing only,
and the original result data are not mutated. Unsolved jig previews and
rejected-flow source markers retain their existing scope.

Twelve JavaScript checks pass in the serial
`tests/surface-faces.test.mjs` and
[vortex-ground-overlay.test.mjs](../../tests/vortex-ground-overlay.test.mjs)
run. The six new checks cover ground-off behavior, both image signs, frozen
and current wake directions, body/Earth views, full-path reflection and input
immutability. The Earth-view expectation independently reflects every drawn
point across Earth Z=0. JavaScript syntax checks pass. Browser rendering and
the packaged build have not been rerun under the existing resource hold; no
new browser, solver or build job was started for this UI change.

The historical **2,324/4,080 at 3%** remains unchanged. The next investigation
should distinguish a documented ASWING ground/wake approximation from a case
setup mismatch, rather than tune section properties to compensate. Current
physical equations remain in place. A full 5% SA-12 rerun and resolution of
the declared setup are still outstanding; post-stall repairs remain deferred.
