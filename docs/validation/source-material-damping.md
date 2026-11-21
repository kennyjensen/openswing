# Source material damping

Updated 2026-10-26. The experimental fixed-frame vacuum modal operator now
accepts finite nonnegative `tdeps` and `tdgam`, extending `drela-fixed-vacuum-v1`.
The zero-damping equations and previous saved policy identities are preserved.
This is implementation verification, **not archived ASWING agreement**.

## Defining equations and an explicit interpretation

[Drela's unsteady theory](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf),
Eqs. 57–60, defines componentwise material strain-rate damping in local c/s/n
axes. Translational times are `[tdgam, tdeps, tdgam]`; curvature times are
`[tdeps, tdgam, tdeps]`. Normal/shear coupling and section offsets remain in the
full load compliance. Mechanical strains subtract the corresponding time times
the strain rate from that load response; total forces and moments include both
elastic and viscous contributions.

For translation this implementation uses the published Eq. 60 approximation:

`strain_rate = Ta * (delta_velocity - omega_average cross delta_position) / h`.

It maps the local damped strain back through `Ta.T` in compatibility. Rendered
Eq. 61 instead prints a bare body-axis diagonal damping matrix. For unequal
times that expression contradicts Eq. 57: rigidly rotating a straight beam can
change which damping time acts on axial extension. We therefore follow the
defining local constitutive law, and do not claim literal Eq. 61 reproduction.
The independent rotated-beam check explicitly distinguishes these expressions.
Eq. 60 itself omits an endpoint covariance term and is not advertised as the
exact derivative of the nonorthogonal averaged transform.

Curvature uses the full Eq. 62 derivative of `Ka * delta_angles`: both endpoint
Euler rates and both `Kdot` contributions are retained. This is checked against
independent finite time differences of the published Euler geometry. It does
not use the old midpoint rotation-log rate. The inherited unloaded interval
length is fixed; the theory neglects extension-rate effects in curvature.

Time constants use the arithmetic average of the two inward endpoint values,
consistent with the source material-property rule. Whole tables and sampled
endpoint values must be finite and nonnegative. Exact historical time sampling,
finite-extension conventions and curved coarse-grid rotational equivalence
remain unverified. No reference frequency or damping coefficient was fitted.

## Verification and complete spectra

Sixteen focused checks pass, including coupled section offsets, sided damping
tables, rigid rotation, the translation approximation and full curvature rate.
Two independent four-interval scalar cases cover oscillating and overdamped
responses. All **56 finite poles** match, including **40 relaxation poles**;
maximum relative error is **1.285e-11**. Relaxation poles from damped rigid
strain directions are retained and labeled, not discarded as unwanted roots.
Five manufactured-field recovery tests, 99 related regressions, five existing
modal tests and 38 distinct JavaScript tests pass. The source material
passivity diagnostic uses the averaged source compliance, including offsets;
positive unequal times do not guarantee passivity for every coupled section.

The [dual axial/torsional example](../../examples/source-vacuum-damped-check.asw)
has 16 elastic poles and 16 relaxation poles. For each independent undamped
source-grid frequency `w`, its elastic roots satisfy
`lambda^2 + tau*w^2*lambda + w^2 = 0`, with `tau = 0.002`.
All **32 roots** match within **7.21e-11**
relative error. Maximum full-pencil left/right backward error is
**3.17e-16**. Native dispatch took
**0.86 s** on this machine.

Reproduce it with:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python scripts/verify-source-damped-modes.py /tmp/source-damped-check
```

The output directory must not exist. Inputs, gates, kernel hashes and results
are retained before comparing the complete spectrum.

## Browser and output meaning

The offline built UI passes **873/873 checks**.
All **16,200** A/M entries agree with native output
within **1.11e-16** absolute difference.
All 32 native and browser left/right eigenpairs satisfy their full equations;
spectrum matching preserves repeated-root multiplicities. Startup took
**14.56 s**, and the solve took **3.12 s**.
These timings describe this run, not a general performance guarantee.
The result and project reopen exactly without recomputation. Modal section and
sensor strains, structural interval plots and desktop/mobile rendering pass.

With damping, source interval strains are the corrected mechanical strains.
There is no defined source endpoint strain-rate interpolation, so endpoint
mechanical strains are explicitly unavailable. Sensors report the selected
adjacent interval strain estimate and its nonorthogonal transform, while anchor
loads and total-torque shell shear stress retain their one-sided sampling.
The UI and CSV distinguish these locations. Undamped intervals retain their
previous endpoint recovery. Pointwise damped strain recovery remains open.

Open the [saved project](../../examples/source-vacuum-damped-check-project.json)
to inspect the computed result, or choose **Coupled eigenmodes → ASWING
fixed-frame vacuum modes · experimental** and load the example.

The [machine report](source-material-damping.json) and
[evidence archive](source-material-damping-20261026-evidence.zip) retain the
source, inputs, comparisons and test receipts. Source aerodynamic/apparent
inertia, moving frames, Bode/time integration and archived modal comparisons
remain incomplete. The full ASWING goal remains active.

Subsequent work adds [stationary still-air apparent inertia](source-still-air-modes.md)
under a distinct modal policy. It retains this damping law and adds no archived
ASWING reference pass; moving-frame and source Bode/time work remain open.
