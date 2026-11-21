# Independent unloaded finite-wing and section verification

**Evidence scope:** The independent reference and its WASM replay below are
verified. A fresh corrected-kernel run has also completed all three native grids
and all twelve reference cases. Its physical result payloads equal the earlier
results exactly; the unloaded zero-circulation limit is unchanged. See the
[current run and reproduction instructions](durrant-unloaded-current/README.md).
Historical records remain separately pinned. The initial unloaded browser
attempt completed physics/export checks but stopped during display checks
without a terminal result; it remains incomplete. The fresh corrected-kernel
attempt failed its desktop WebGL context-health check. An instrumented follow-up
passed the numerical/export and desktop context checks, then stopped without a
terminal result or mobile checks under recorded severe memory pressure. The
[browser closeout](durrant-unloaded-browser-closeout.md) preserves all three
attempts and their source pins; none is a complete passing unloaded workflow.
The subsequent rebuilt application, with the [renderer change](renderer-fix.md),
passes the complete offline numerical/export and desktop/mobile WebGL workflow.
The two selected native/browser root components agree within 1.933e-12 per
second, with physical shape MAC at least 0.9999999999999996. All 59 original
assertions and the 600/240/180-second test/solve/readiness deadlines are retained.
This fourth attempt has its own [record](durrant-unloaded-browser-repaired.json)
and source pins; the historical incomplete/failed attempts remain unchanged.
It does not classify all returned roots or establish loaded flutter agreement.

The independent reference recovers the native kernel’s two low unloaded-wing
modes increasingly closely as the grid is refined. Using the documented
Glauert aerodynamic sampling, complex-root differences are **.01814% and
.01324% at N32**, decreasing by approximately four with each grid doubling.
The direct prescribed-motion section-force comparison has maximum scaled
component discrepancy **2.67e-10**. These results test the unloaded dynamic
terms; the loaded Durrant Case 4 flutter discrepancy remains unresolved.

## Physical scope and primary evidence

The wing uses the existing [material transcription](durrant-reference.json):
the main-table 25%-wing geometry, stiffness and distributed inertia. The
supplied plan sets speed 24 m/s, density 1.225 kg/m³, Mach zero, zero body incidence,
zero section camber/Cm/profile drag, zero gravity, disabled stall, and enabled
ASWING lag. It retains every independent mechanical coordinate. This is an
unloaded diagnostic analogue, not published Case 1 or Case 4.

The independent model imports NumPy/SciPy and the project-relative material
table. It imports no production geometry, structural assembly, aerodynamic
influence, load, linearization or eigenvalue implementation. Cubic Hermite
bending and linear twist discretize the independent beam energies; material
interfaces are explicit nodes. The structural derivation and source conflicts
remain those described in [the structural study](durrant-structure.md).

[ASWING steady theory](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
equations 63 and 151–157, specifies the global material Glauert angle and the
spanwise force/control-point position. For independent span coordinate s∈[0,L],

```
theta_j = acos(2*s_j/L - 1)
s_a = L/2 + L/2*cos((theta_i + theta_(i+1))/2)
```

The angle is not reset at material interfaces. For this wing, the end cells
[0,.012] and [.712,.718] metres remain unchanged through N32. Their Glauert
fractions are .2510533895 and .7494755222 rather than the arithmetic fraction
.5. Requested grid count alone therefore does not demonstrate refinement of
those two sampling discrepancies.

[ASWING unsteady theory](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf),
equations 29–36, 41–44 and 49–56, supplies circulation/rate loads, apparent mass
and empirical lag. With elastic-axis normal displacement h, span twist phi,
chord c, and offsets

```
a = (.25-Xax)*c - Cea
d = (.50-Xax)*c - Cea
e = (.75-Xax)*c - Cea
ma = rho*pi*c^2/4
```

the control-point normal flow is `U*phi - h_dot + e*phi_dot`. Quarter-chord
virtual work uses `H-a*P`, where H and P are independent heave/twist shape
rows. Fluid kinetic energy uses `(H-d*P)` and intrinsic torsional coefficient
`c²/32`. The apparent pitch-rate matrix per unit speed is
`ma*outer(H-(d+c/4)*P,P)`. These retain the intrinsic apparent pitching couple,
which cannot be reproduced by moving the normal force alone. The circulation
lag is ASWING’s empirical rational model, not exact Theodorsen aerodynamics.
Pinned document hashes and explicit conditions are in
[durrant-unloaded-reference.json](durrant-unloaded-reference.json).

## One implementation, explicit sampling choices

`scripts/durrant_unloaded_reference.py` replaces the separate exploratory
variants with four named choices. They share all physical equations, material
data, beam fields and structural mass/stiffness.

| Option | CP/influence sampling | Circulation virtual work | Fluid quadrature |
| --- | --- | --- | --- |
| `arithmetic_integrated` | Arithmetic midpoint | Integrated FE shapes | Integrated FE shapes |
| `glauert_cp` | Global Glauert point | Integrated FE shapes | Integrated FE shapes |
| `glauert_circulation` | Global Glauert point | One Glauert point | Integrated FE shapes |
| `glauert_all` | Global Glauert point | One Glauert point | One Glauert point |

For every Glauert option, influence targets and heave/twist kinematics move
together. One-point load/mass quadrature uses panel length times the same
shape rows at that point. Real structural M/K remain unchanged. Mechanical
and aerodynamic grids may differ; shapes are reported on their union. The
independent Hermite fields remain different from production endpoint motion
interpolation, so this is not an exact duplicate of the native discretization.

The arithmetic baseline is retained. No parameter was fitted and no
physical-agreement tolerance was chosen after seeing the root differences.

## Wing results

The table reports complex-root distance divided by independent-root magnitude
for the two shape-matched modes in .1–40 Hz. Matching uses physical complex
translations and chord-scaled rotations, span integration, and a one-to-one
assignment. Ambiguous matches are labelled; frequency proximity does not
choose the mode association.

| Sampling | N8 mode 1 / mode 2 | N16 mode 1 / mode 2 | N32 mode 1 / mode 2 |
| --- | --- | --- | --- |
| Arithmetic baseline | 8.71548% / 2.78751% | 6.24346% / 1.94889% | 4.15719% / 1.30351% |
| Glauert CP | 1.12380% / .65644% | .24683% / .16098% | .05931% / .04078% |
| Glauert CP and circulation | .16493% / .29372% | .03999% / .08041% | .00936% / .02139% |
| Glauert CP and all airloads | .29634% / .19599% | .07275% / .05180% | .01814% / .01324% |

The N32 full-sampling reference roots are −43.329400728+77.340430956i and
−34.936939967+167.736005883i per second; native roots are −43.343309+77.348506i and
−34.915690+167.728072i. Both low modes are damped throughout this unloaded
study. Individual quadrature stages need not reduce every error monotonically;
the prescribed full-sampling result is retained even when another stage has
an accidentally smaller finite-grid discrepancy.

Native records contain two local descriptor searches, shifts −.1+100i and
−.3+200i, with 24 roots per search and centered tangent step 1e-5. Original-pencil
left/right backward errors are below 1e-9. The independent calculations retain
their full spectra separately. The arithmetic N8 spectrum has **two** high-frequency growing conjugate pairs,
while CP-only N8 has one; those pairs are absent on N16/N32. Their scaled roots,
in inverse seconds, are:

| Sampling | Growing roots |
| --- | --- |
| Arithmetic N8 | 0.014160509195093112 ± 68523.54579905943i |
| Arithmetic N8 | 0.31200958279115376 ± 63057.82634389833i |
| Glauert CP N8 | 0.38144116773023956 ± 63057.82863248084i |

These are four and two roots with positive real part, respectively, not purely
real roots. The circulation-load and full-airload variants have no growing root
at these grids. **No case has a positive purely real divergence root.** The v1
prose's singular “pair” undercounted arithmetic N8; its archived full spectrum
already contained both pairs. Scaling leaves all these growth counts unchanged. Local native searches do not prove full
native-spectrum stability, and coarse high-frequency pairs are not labelled
physical flutter.

[Convergence figure (PNG)](durrant-unloaded.png) · [SVG](durrant-unloaded.svg) · [PDF](durrant-unloaded.pdf). The figure input/output hashes and final visual review are retained separately.

## Numerical conditioning and explicit historical reproduction

The first full-spectrum reference WASM replay failed its existing **2e-7 scaled
root tolerance**. Maximum discrepancies were 1.0324e-6 at N8 and 3.633e-5 at
N32. Tiny original-pencil residuals did not establish accurately located roots:
the mass-normalized displacement/velocity pencil contains squared mechanical
frequencies, with A norms around 1e12. The failed run, diagnostic spectra, source
pins, and original native results remain in the history archives.

The default `eigensystem_scaling='energy_convective'` applies a reversible
coordinate/equation transformation. If original coordinates are
`z=[q,v,Gamma]`, the scaled coordinates use `Omega*q`, `v`, and
`sqrt(rho*delta_s)*Gamma`. Omega is the positive wet mechanical frequency.

```
z = R*x
R = diag(1/Omega, I, 1/sqrt(rho*delta_s))
tau = 2/(pi*U)
E = diag(Omega, I, sqrt(rho*delta_s)/tau)
w0 = abs(U)/chord
A_scaled = E*A*R/w0
B_scaled = E*B*R
lambda_physical = w0*lambda_scaled
```

The aerodynamic rows are scaled in full, including their coupling terms; the
circulation-rate mechanical B block remains. The circulation scale has matching
energy units, but is not asserted to equal an exact fluid-energy diagonal.
Lag-off omits those circulation coordinates; a retained mechanical basis keeps
its existing selected modes and dimension. Zero density keeps circulation's
original units rather than dividing by zero. The zero-speed analytic wet-mode
path is unchanged. Right eigenvectors are returned to original coordinates
before physical shapes and original-pencil residuals are evaluated.

The reusable implementation uses ordinary helper functions, with no monkeypatch
or production import. Explicit `eigensystem_scaling='unscaled'` calls the original
`eig(A,B)` path and reproduces archived roots and shapes within 3.06e-16. No
mechanical or aerodynamic assembly formula, physical matrix, modal truncation,
or rank selection changed. Three independently parameterized neutral scalings
and an ordinary `eig(B_scaled^-1*A_scaled)` route corroborate the calculation;
the v2 audit's standard-route discrepancies are below 7.02e-12 scaled over all
study and API checks.

Numerical changes to archived roots are reported separately from physical
native/reference differences. Across the 12 cases, the largest absolute change
is 72.30 per second at a high-frequency Glauert-circulation N32 root (1.0234e-4
scaled). For the full-sampling N32 low mode, the change is 3.65e-4 per second.
These are retained rather than hidden behind the small residuals. A first-order
left/right sensitivity diagnostic explains why the unscaled residual alone was
weak; it is not presented as a rigorous error bound.

The separately labelled diagnostic energy-scaling WASM replay passed all 110
N8 and 374 N32 roots under the **unchanged 2e-7 tolerance**: maximum scaled
native/WASM differences were 5.6071e-9 and 7.4377e-10. Shape, growth-sign and
left/right residual checks also passed. The promoted v2 API also completed its own standalone hash-pinned replay with
terminal exit 0: all 110 and 374 roots passed, with maximum scaled discrepancies
5.6070563e-9 and 7.4377234e-10. No production module was loaded. This is recorded
in `durrant-reference-wasm.json` with the executed script, input, terminal and
log; the diagnostic history remains separate. No physical-agreement tolerance was
introduced or fitted.

## Direct section verification

`scripts/durrant_section_transfer.py` compares independent scalar and vector
force/moment formulas and differentiates the actual aerodynamic evaluator
under prescribed heave/pitch motion. It solves no equilibrium, beam tangent,
eigensystem or time trajectory. Normal force and span moment are retained
separately for steady circulation, circulation-rate loads, apparent
acceleration and apparent pitch rate.

The completed sweep has five pitch axes (.25,.2505,.3844,.5,.75 chord), lag
enabled/disabled, aspect ratios 200000 and .718/.09446, and dimensionless
frequencies r=omega*c/U of 0, .25, .5, 1, 2. Every configuration uses 4 panels and
tangent steps 1e-4 and 1e-5: 20 configurations, 100 frequency samples and 1160
production evaluator calls. The finite-span reference uses independently
defined cosine nodes/Glauert points and closed scalar Biot–Savart integrals.

Maximum scaled finite-reference load discrepancy is 2.6703e-10; tangent-step
change is 2.6436e-8; circulation discrepancy is 1.6667e-11. The large-span
departure from the infinite-span formula is 1.4142e-5 and remains explicitly
recorded. Quarter-/mid-/three-quarter-chord identities and pitch-axis covariance
also pass. These checks distinguish an omitted intrinsic pitching couple from
apparently correct heave-only results.

## Reproduction and evidence

From this checkout, use its existing scientific
Python environment. Both CLIs require explicit bounded plans. Output paths
must be fresh, except exact study resumes.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-durrant-unloaded.py --plan docs/validation/durrant-unloaded-current/plan.json --output /tmp/durrant-unloaded-new --native compute --kernel-root "$PWD"
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-durrant-section.py --plan docs/validation/durrant-section-plan.json --output /tmp/durrant-section-new.json --kernel-root "$PWD"
```

The wing CLI defaults to independent-only work (`--native none`). `--native
saved` verifies the archived terminal records, current kernel hashes, source
text, conditions, discretization and residuals before comparison. `--native
compute` explicitly runs the same native calculation, once per unique native
ID; `--case ID` selects a bounded subset. Native imports are confined to the
explicitly named kernel checkout. This candidate replay reused 3 completed
native calculations without another native equilibrium/tangent run.

Wing outputs are atomic per-case compressed JSON records and an atomic
`run.json`. `--resume` verifies the exact plan, sources, kernel, selection,
completed hashes and Linux process identity before reuse. A live recorded
process is refused. Completed records remain valid if later work is interrupted;
a stale state file alone never counts as completion. Administrative guards for
live ownership, changed plan/artifact, missing kernel and unknown case were
exercised separately from the scientific comparisons.

Evidence includes:

- `durrant-unloaded-results/run.json` and its pinned per-case/native records:
  all 12 reference cases completed against the saved native outputs.
- `durrant-unloaded-scaling-audit.json`: all 120 physical matrix blocks and 16
  complete original pencils remain bitwise identical. The explicit unscaled
  path reproduces 2728 archived roots and all retained shapes within 3.06e-16.
  The 12 scaled cases retain full spectra, root changes, native comparisons and
  independent standard-matrix checks. All 3 native records are byte-identical.
  Additional checks cover lag-off, retained modes, zero density and zero speed.
- `durrant-reference-wasm.json`, `durrant-reference-wasm-terminal.json`, and
  their pinned script/input/log: standalone exact-v2 reference replay passed,
  without a production import. `durrant-unloaded.provenance.json` pins the
  plotter and figure inputs/outputs; `durrant-unloaded-visual-review.json` records
  the parent's visual review against the PNG hash.
- `durrant-section.json` and `durrant-section-preservation.json`: the 100-sample
  sweep passed; 12000 real-valued matrix entries reproduce the original sweep
  within 4.45e-16.
- Exact v2 commands and successful terminal outcomes are in
  `durrant-unloaded-v2-terminal.json` and `durrant-unloaded-v2-audit-terminal.json`
  with their logs. Historical administrative guard evidence remains in the
  immutable v1 candidate archive.
- `durrant-unloaded-prototypes.zip`: immutable exploratory sources, primary
  derivations and original results for audit, not the executable implementation.
  The v1 candidate archive retains the complete earlier consolidation/audit.
- `durrant-unloaded-history/integration-v1.zip` preserves all 49 earlier candidate files
  with member hashes; `durrant-unloaded-history/conditioning-evidence.zip` preserves
  the numerical diagnosis, original failed replay and successful separately
  labelled scaling replay. The v2 audit extracts the original pencil's AST and
  verifies every assembly entry without importing or rerunning a native kernel.

The existing `durrant-reference.json` is shared and byte-identical; no separate
material transcription is introduced.

## Current integration and remaining scientific work

The reusable scripts, historical native records, numerical diagnosis and
successful independent-reference WASM replay are integrated. The original v2
handoff is retained byte-for-byte in
`durrant-unloaded-history/integration-v2.zip` plus the explicitly pinned sibling
history archives in `integration-v2-members.json`, avoiding duplicate ZIPs. The audit of that historical
reference uses an explicit archive path:

```sh
.venv/bin/python scripts/audit-durrant-unloaded-integration.py --archive docs/validation/durrant-unloaded-history/integration-v1.zip --output /tmp/durrant-reference-history-audit.json
```

The production kernel has since received the apparent-rate self-influence
correction. All three native grids were freshly computed, followed by twelve
reference cases, with unchanged settings and tolerances and terminal exit zero.
All 63 required source dependencies were unchanged during the run. The complete
native physical payloads and reference results equal the earlier results exactly,
so the reported comparison values and plotted physical data also remain valid.
The new source pins and complete comparison are in
`durrant-unloaded-current/completion-summary.json`.

Saved-native mode deliberately rejects old kernel fingerprints and currently
accepts only the original prototype record layout. Current computed records
are reusable through guarded `--resume`; they must not be relabelled as that
older external-input format. The browser attempts remain incomplete or failed;
their completed modal/export assertions do not establish the full workflow.
Loaded equilibrium, prestress, stall, finite-speed flutter boundaries
and experimental agreement remain distinct scientific work. No broad ASWING
requirement is closed by this unloaded study alone.
