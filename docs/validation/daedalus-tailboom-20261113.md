# Daedalus tailboom compliance and resonance investigation

Observed 2026-11-13 UTC. The tailboom is flexible in OpenSwing, and its
flexibility changes the rudder-to-yaw notch substantially. Fresh independent
checks support the current boom mechanics. They do **not** close the mismatch
with Drela's Bode curve or establish identical native ASWING discretization.
No production equations, aircraft properties, defaults or ISAE counts changed.

Drela's [official example page](https://web.mit.edu/drela/Public/web/aswing/)
explicitly attributes the reduced 1 Hz response to tailboom compliance.
The [retained GIFs and source receipt](../../reference/daedalus-rudder-animations-20261113/source-receipt.json)
identify operating point 1 and forcing amplitude F3=40, but do not identify
the trim speed. Compliance can create a transfer-function minimum through
cancellation; that minimum need not equal a bare boom's natural frequency.

## Literal input and current equations

The [current-code audit](../../artifacts/daedalus-tailboom-20261113/audit/result.json)
checks the actual [dae.asw](../../examples/dae.asw) against independently entered
values from its tables, including their multipliers:

| Boom station x [ft] | EIcc = EInn [lb ft²] | GJ [lb ft²] | Weight per length [lb/ft] |
|---:|---:|---:|---:|
| −6.5 | 50,000 | 25,000 | 0.150 |
| 0 | 80,952.38 | 25,000 | 0.150 |
| 4 | 100,000 | 25,000 | 0.150 |
| 12 | 11,000 | 11,000 | 0.110 |
| 20 | 7,500 | 7,500 | 0.060 |

The doubled stations separate two-point linear property segments. There is no
multi-point spline-endpoint ambiguity in these boom distributions. Weight is
divided by the model's gravity, 32.18 ft/s², to obtain inertial mass. Integrated
weight is 3.295 lb for the entire beam and 2.32 lb for its aft 0–20 ft portion.

The file leaves axial and shear stiffness unspecified; their rigid defaults
agree with the [ASWING user guide's property table](../../reference/aswing_doc.txt).
Bending and torsion remain finite. Both material damping times are zero.
The fin is connected rigidly to the boom through its actual **one-foot lateral
offset**, not through coincident centerlines. The current joint geometry retains
that offset; fin-root and boom-tip incremental rotations agree in the saved
coupled responses.

The section compliance law implements Drela's steady Eqs. 18–20, p. 8
([authoritative PDF](../../reference/aswing-authoritative-20261108/drela-aswing-steady.pdf)).
On the restored, loaded corrected-C16 state, the current full structural
compatibility derivative differs from the saved aircraft block by at most
**2.78e−17**, and from the separately derived reference block by **9.10e−13**.
No aircraft residual or new full-aircraft linearization was evaluated in this
audit. The [older loaded boom–fin continuum comparison](daedalus-component-checks.md)
also retains its independent 0.02064% finest-grid motion error; it was not rerun
or counted as fresh evidence here.

## Fresh static and modal checks

The new component fixture cuts the literal boom at x=0, clamps that end, and
keeps its aft 20 ft stiffness and weight distributions. It excludes the fin,
stabilizer, air, gravity preload and free-flight motion. Current production
static/dynamic equations are compared with two independent calculations:

- Static tip-force/tip-couple compliance from continuum integrals of
  `(20−x)²/EI`, `(20−x)/EI` and `1/EI`, split at every stiffness break.
- The first two bending frequencies from cubic-Hermite Euler–Bernoulli elements,
  integrating the literal variable EI and mass with four-point Gauss quadrature.
  Refining the reference from nominal 80 to 160 changes frequencies by at most
  5.23e−6 relative, below the declared 1e−5 check.

The reference tip compliance for a unit lateral force is **0.05491049 ft/lb**.
Its first two bending frequencies are **7.187706 and 25.932399 Hz**. Each mode
occurs twice because the isolated boom has equal bending stiffness in both
directions. These are deliberately **bare-boom**, not installed-aircraft,
frequencies.

| Nominal intervals | Actual intervals | Largest static compliance error | First bending frequency error | Second bending frequency error | Declared 1% component gate |
|---:|---:|---:|---:|---:|---|
| 16 | 18 | 1.0247% | 0.0628% | 2.3782% | Needs refinement |
| 32 | 34 | 0.3069% | 0.00492% | 0.6395% | Pass |

The [16-interval result](../../artifacts/daedalus-tailboom-beam-20261113/beam-16/result.json)
and [32-interval result](../../artifacts/daedalus-tailboom-beam-20261113/beam-32/result.json)
retain every compliance entry, both duplicate modes, and the residual checks.
Modal residuals are below 1.3e−14. The coarse higher-mode error is retained;
passing this component gate does not validate the complete aircraft Bode plot.

## Coupled stiffness experiment

This part uses the **2026-10-25 corrected C16 aircraft matrices**, at the
previously documented 6.7 m/s trimmed state. It is a new matrix experiment,
not a fresh current-code aircraft solve. The audit above verifies the current
structural block against that saved block before modifying it.

Only beam 4's bending/torsion compliance changes. The whole beam includes its
forward −6.5–0 ft portion. Mass, loaded geometry, prestress, aerodynamic matrices,
joint constraints, input and output conventions remain fixed. A constant
constitutive-residual correction holds the equilibrium while its incremental
stiffness changes. This is equivalent to adjusting the rest strain to retain
the loaded base, and is **not** a prediction for a modified `.asw` retrimmed from
the same jig geometry. It isolates tangent stiffness sensitivity without
silently changing flight condition.

For stiffness multiplier k, the section compliance becomes S/k. The complete
verified compatibility derivative, including loaded moment transport, is
changed accordingly. Only 63 boom compatibility rows change; the full coupled
descriptor remains in the harmonic solve. All **36 solves** pass its original
conditioning and full-equation residual checks. The unmodified complex yaw
response reproduces overlapping saved samples within **1.39e−17 deg/s**.

| Boom EI/GJ multiplier | Yaw amplitude at 1 Hz [deg/s/F3] | Boom-tip lateral motion relative to root at 1 Hz [mm/F3] | Lowest of nine sampled yaw amplitudes [deg/s/F3] | Frequency of that sample [Hz] |
|---:|---:|---:|---:|---:|
| 0.5 | 0.103309 | 12.833 | 0.089750 | 0.7000 |
| 1 | 0.075249 | 9.342 | 0.073368 | 1.0965 |
| 2 | 0.087616 | 5.424 | 0.046338 | 1.5000 |
| 100 | 0.130138 | 0.113 | 0.045298 | 2.0000, sampled boundary |

These are sampled minima, not refined extrema. Stiffening the boom substantially
removes the near-1.1 Hz minimum and changes fin displacement and phase. Softening
shifts the minimum lower; doubling stiffness shifts it higher. Thus the small
direct boom term in the [older algebraic decomposition](daedalus-rudder-coupling.md)
did not mean boom compliance was unimportant: its influence also acts through
the tail and the rest of the coupled aircraft.

![Yaw response and boom motion under the stiffness diagnostic](../../artifacts/daedalus-tailboom-20261113/report/tailboom-sensitivity.png)

[SVG plot](../../artifacts/daedalus-tailboom-20261113/report/tailboom-sensitivity.svg)
and [combined results](../../artifacts/daedalus-tailboom-20261113/report/result.json).
The reference drawing remains approximately 0.03399 deg/s/F3 at 1.15738 Hz,
against 0.07380 for the unmodified saved C16 model at that same frequency.
None of these stiffness changes is a proposed fit or new default.

Two subsequent nine-frequency jobs separate bending from torsion. Since the
literal boom has no section offsets or cross-stiffness, its local curvature
rows split exactly into c/n bending and s-axis torsion. The runner asserts
those conditions before selecting either compliance block.

| Changed stiffness, with all other stiffness retained | Yaw at 1 Hz [deg/s/F3] | Yaw at 1.15738 Hz [deg/s/F3] |
|---|---:|---:|
| None | 0.075249 | 0.073802 |
| Bending EI only ×100 | 0.124691 | 0.110915 |
| Torsion GJ only ×100 | 0.073707 | 0.068475 |
| Both ×100 | 0.130138 | 0.116967 |

**Bending is the dominant boom contribution to this notch sensitivity.** At
1 Hz, stiffening bending alone raises yaw amplitude about 66%; stiffening
torsion alone changes it about −2%. Torsion has some influence, especially
near the minimum, but it does not explain the factor-of-two reference gap.
All 18 additional full-pencil solves pass the existing gates. The
[separate comparison record](../../artifacts/daedalus-tailboom-20261113/bending-torsion-comparison.json)
retains their complex responses and source receipts without rewriting the
earlier 36-solve report or plot.

## Remaining limits and next comparison

No omitted boom bending stiffness, missing mass conversion, disconnected fin,
or missing structural compatibility derivative was found. The independent
mechanics checks and coupled sensitivity support the modeled mechanism; the
reference notch's depth is still unexplained.

There is a concrete implementation distinction to keep visible: the default
browser policy still uses spatial rotation-midpoint structural equations and
natural interpolation. The separate `drela-moving-airflow-v1` policy uses the
published endpoint-average structural discretization and Drela spline policy.
The present audit checks the **default**, which generated the saved Bode
comparison; continuum agreement does not prove identical finite-grid native
ASWING behavior. See [numerical policy](../../openswing/numerical_policy.py) and
[source equations](../../openswing/source_discrete.py).

The next useful aircraft comparison is a separately trimmed run using that
published-equation policy, with the same physical model, speed, constraints and
observables, against the current default. Its base state must be computed for
its own operator; the old state must not be relabeled or silently restored
under another policy. The published operating point remains unidentified, so
even that comparison would not by itself close the native-reference mismatch.

## Execution record

The [runner](../../scripts/check_daedalus_tailboom.py) executes one capped child
per invocation. All completed jobs were serial, with one BLAS thread and limits
of 512 MiB address space, 15 CPU seconds and 25 wall seconds. Maximum numerical
job use was **4.318 CPU seconds, 12.251 wall seconds and 136.4 MiB RSS**. Every
child and parent tool session completed; no solver remains in the background.
Production sources were unchanged across all jobs. Browser/build tests remain
held.

The first bare-boom fixture omitted the mandatory reference dimensions and
was rejected by the parser before a solve. That failed attempt remains in
`artifacts/daedalus-tailboom-20261113/beam-16/`. Adding valid reference dimensions
created a new study directory; the old attempt was not overwritten. The two
initial runner revisions used for numerical work are retained as `runner-v1.py`
and `runner-v2.py` and authenticated against each job's input pins by the report.
The report's runner is retained as `runner-v3.py`; each later component-split
job also retains its exact `runner.py` beside its input hashes and terminal receipt.

To repeat, choose fresh directories and invoke serially:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  .venv/bin/python -B scripts/check_daedalus_tailboom.py audit --study NEW_STUDY
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  .venv/bin/python -B scripts/check_daedalus_tailboom.py beam --panels 32 --study NEW_BEAM_STUDY
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  .venv/bin/python -B scripts/check_daedalus_tailboom.py response --factor 1 --study NEW_STUDY
```

The saved-matrix route requires the explicitly pinned historical files under
`/tmp/openswing-daedalus-shell-mesh-20261025/results/`; absence is an error, not
permission to substitute a newer matrix. The independent bare-boom route does
not require those historical files. No ISAE completion fraction or tracked
scope changed, so no new ISAE progress observation is warranted.
