# Daedalus: coupled sensitivity to aerodynamic refinement

At **1.157378 Hz**, the complete aerodynamic load differences from the
82→164→328-panel study produce a **+0.592% / +0.865% first variation of yaw
amplitude**, respectively, through the original full aircraft descriptor.
The change is small and increases yaw, whereas the published drawing requires
a substantially lower value. This further weakens aerodynamic panel resolution
as the explanation for the dip. It does **not** establish convergence of a
retrimmed, fully recoupled fine-grid aircraft.

The baseline remains **0.074218 deg/s per F3**, compared with **0.033986** in
the drawing. No production parameter, physical equation or ISAE count changed.
The [preceding resolution study](daedalus-aero-resolution-20261113.md) contains
the geometry, circulation, core-spacing and prescribed-motion checks.

## Calculation and interpretation

The original 6.7 m/s source-equation/SEGSPL model supplies the loaded structure
and full 2,044-coordinate harmonic state. Each aerodynamic grid reuses its
previously solved steady and harmonic circulation. All grids use the same
original structural position, rotation and local-motion interpolants; body
panels and point attachments remain unchanged. Each new job performs 17
direct aerodynamic evaluations, rather than repeating the circulation solves.

For every fine subinterval, the complete force and intrinsic moment are summed
about the parent interval's aerodynamic receiver. The source network's existing
symmetric endpoint transfer then places that wrench on the original structural
nodes. This preserves the exact total force and moment about every reference.
It does not create new structural nodes or distribute forces using an unrelated
beam discretization. Point loads, body shoulders and engine forces/couples are
transferred separately at their actual moving attachment positions.

The global force/moment rows are formed at **each perturbed geometry before
differentiation**. Consequently, moving moment arms multiplying the mean loads
are included. The residual vector contains nodal force/couple and the six
free-frame force/moment rows. It has no circulation-row contribution: fine
circulation has already been solved for the specified motion and input.
The source constitutive compatibility rows remain unchanged. The selected
model has no nonlinear hinge law or custom operating constraint requiring an
additional distributed-couple row.

Write the original full harmonic pencil as `K0 = i*omega*M0 - A0`, with
`K0*z0 = B0`. Let `dL` be the fine-minus-coarse external load derivative,
after circulation elimination, evaluated along `z0` and the F3 input. Solve:

```text
K0 * dz = dL
dH = C * dz
first variation of amplitude / amplitude = real(dH / H0)
```

This uses the complete original structural, aerodynamic and free-frame
feedback. It is the derivative at zero of an affine interpolation between the
two circulation-eliminated aerodynamic load operators. The fine mean loads
differ, so an affine offset is implicit in keeping the original equilibrium.
That offset is a diagnostic definition, not a proposed physical preload.
Higher orders in the changed feedback and a structural retrim are omitted.
In particular, `abs(H0+dH)` is an extrapolated first-order diagnostic, **not**
a new fine-grid Bode prediction.

The [authoritative reference index](aswing-authoritative-references.md) and its
checksummed catalog govern the calculation. Sampling follows the steady
technical description's Eqs. 150–161; the unsteady circulation/load terms follow
Eqs. 33–49. The full descriptor sign and forcing convention follow the
unsteady frequency-response formulation. No native AVL convention or alternate
lag law is substituted.

## Results

Percentages here are sensitivities to the disclosed refinement, not errors
against ASWING. All four outputs are retained.

| Output | Baseline amplitude | 82→164 amplitude first variation | 82→328 amplitude first variation | 82→328 phase first variation |
| --- | ---: | ---: | ---: | ---: |
| Yaw rate, deg/s/F3 | 0.07421777 | +0.5922% | +0.8653% | +0.0720° |
| Roll rate, deg/s/F3 | 0.02421862 | −1.3499% | −1.0591% | +1.3469° |
| Sideslip, deg/F3 | 0.03031630 | +0.5129% | +0.6322% | −0.2718° |
| Bank, deg/F3 | 0.00309191 | −1.2034% | −0.8185% | +1.6100° |

The yaw complex corrections are **0.7319% / 0.8744%** of the baseline. Adding
them once gives amplitudes **0.074658 / 0.074860**, respectively. At 328 panels,
wing and fin load differences contribute **+0.41795 / +0.51293 percentage
points** to yaw's amplitude first variation; the other groups partly offset
these. The full per-component complex outputs are in the
[projection result](../../artifacts/daedalus-aero-feedback-20261113/first-variation/result.json).

The fixed-shape mean-load changes remain explicit. Relative to 82 panels,
164 panels change global `(Fx,Fy,Fz)` by
`(−0.06452,+0.03626,+0.40177) lb` and `(Mx,My,Mz)` by
`(−0.07478,+2.51202,+0.70832) lb ft`. At 328 panels the changes are
`(−0.09860,+0.06159,−1.03887) lb` and
`(+0.01535,+12.67553,+1.20002) lb ft`.
These are not claimed to satisfy a new equilibrium, and the pitch-moment
change is a reason to retain the retrim qualification.

## Numerical checks

The reusable mesh sampler was extracted from the previous driver without
changing its sampling formula. Replayed full aerodynamic wrenches at all three
grids agree with the saved resolution study within **2.025e−9** in their
respective force/moment units. This also verifies the extraction against the
existing observations.

| Check | Largest difference or residual |
| --- | ---: |
| Fine-to-coarse transfer: total force/moment closure | 1.929e−12 |
| Coarse transfer versus full network, real/imaginary probes | 4.164e−17 in scaled residual units |
| Coarse load derivatives versus prior component accounting | 3.981e−14 in scaled residual units |
| Load derivative change when stencil width is halved | 5.348e−14 in scaled residual units |
| Corresponding wrench derivative change | 3.051e−9 |
| Original full harmonic solve: scaled residual | 9.171e−18 |
| Correction solves: scaled residual | 6.475e−20 |
| Sum of component solutions versus separate total solve | 3.631e−16 in scaled state units |

Fresh load stencils retain the previous fourth-order widths **1e−3 / 5e−4**.
The acceptance gates are 2e−8 for scaled load derivatives, 2e−6 for wrench
derivatives, and the unchanged production harmonic-solve gates. The original
grid is checked against two full nonlinear network evaluations with identical
circulation, circulation rate and all six acceleration operating slots.

There are three successful capture jobs and one successful projection job.
The latter solves 12 component and two total right-hand sides using the full
2,044-coordinate matrix. All use one BLAS thread and caps of **512 MiB address
space, 15 CPU seconds and 25 wall seconds**. Maximum observed use is
**5.526 CPU seconds, 10.378 wall seconds and 165.446 MiB resident memory**.
All children and parent sessions were reaped. Browser/build jobs remain held.

## Evidence and next work

Immutable input hashes, runner snapshots, complex arrays and terminal receipts
are retained for [82](../../artifacts/daedalus-aero-feedback-20261113/capture-1/result.json),
[164](../../artifacts/daedalus-aero-feedback-20261113/capture-2/result.json) and
[328 panels](../../artifacts/daedalus-aero-feedback-20261113/capture-4/result.json),
and the [coupled projection](../../artifacts/daedalus-aero-feedback-20261113/first-variation/result.json).
Use [the bounded driver](../../scripts/check_daedalus_aero_feedback.py) with
one fresh tag at a time. Its `project` stage reads the explicitly named accepted
captures. No previous observation or progress event is rewritten.

This closes the initial question of whether the observed load changes produce
a large **first-order** yaw correction through the existing coupled system.
They do not. The subsequent [full current-source refinement](daedalus-structural-resolution-20261113.md)
now retrims and solves a 211-node / 164-lifting-panel aircraft. Its dip-frequency
yaw amplitude changes by −0.217%, while roll/bank remain more mesh-sensitive.
That complete combined refinement is distinct from this first-variation
diagnostic. The original Bode operating settings and native agreement remain
unresolved.
