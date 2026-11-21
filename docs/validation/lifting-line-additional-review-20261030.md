# Additional lifting-line implementation comparisons

2026-10-30. DUST and OpenFAST/OLAF add useful comparisons to the retained
MachUpX, AeroSandbox, XFLR5 and JVL sources. Selected unmodified sources are
now retained under `reference/third_party/dust` and `reference/third_party/openfast`, with exact
revisions, download URLs, hashes and license information in `SOURCE.json`.
These are reference selections, not installed solvers or browser dependencies.

The subsequent [Vortex Step Method inspection](vortex-step-method-review-20261030.md)
adds TU Delft's explicit treatment of control/force locations and chordwise
surface-vortex forces. It retains another pinned source selection and identifies
a formulation comparison to pursue; it adds no executed solver comparison or
native ASWING pass.

The useful result is a narrower investigation: baseline vortex arithmetic
agrees with another independently compiled implementation, while source-line
geometry, force sampling and the treatment of nearby filaments differ among
the codes. No new ASWING match or justified production correction was found.

| Implementation | Most useful question | Limitation for ASWING reproduction |
|---|---|---|
| [MachUpX](https://github.com/usuaero/MachUpX) | How does a numerical lifting line handle curved/swept-wing singularities? | Receiver-dependent local straightening and jointed wakes change the formulation. |
| [DUST](https://public.gitlab.polimi.it/DAER/dust) | Are the circulation-control point, its 2D correction, and the force-velocity point used consistently? | Uses a different section closure, finite-core vortex rings and optional load formulas. |
| [OpenFAST/OLAF](https://openfast.readthedocs.io/en/main/source/user/aerodyn-olaf/OLAFTheory.html) | Are collocation, section-speed projection and Kutta–Joukowski normalization consistent? | Rotor/free-wake formulation with configurable regularization and a different spanwise collocation rule. |
| [AeroSandbox](https://github.com/peterdsharpe/AeroSandbox) | Are horseshoe signs, factors and force directions correct? | Different section data and straight-segment force geometry. |
| [XFLR5](https://sourceforge.net/p/xflr5/code/1506/tree/trunk/xflr5/) | Are straight-wing loading, polar interpolation and induced-drag normalization consistent? | Classical LLT is not a general curved-beam ASWING formulation. |
| JVL, already retained | How does Drela's related code evaluate nonlinear section behavior and forces? | Its vortex-lattice geometry and same-component core convention differ from the ASWING equations. |

The [earlier review](lifting-line-source-review-20261030.md) records the first
three downloads and the AeroSandbox horseshoe comparison. The
[JVL/source-geometry review](../../artifacts/isae/sa4-source-geometry-review-20261030/README.md)
records its force and finite-core conventions.

## DUST: separate circulation and force locations

Retained revision: `3b1d2e61f0b74a3c9fdde9c850951c73f8c6ad3e`.
In [mod_liftlin.f90](../../reference/third_party/dust/src/aeroel/mod_liftlin.f90):

- Lines 555–607 sum all lifting-line contributions at the downstream control
  point, project velocity into the section plane, and subtract a 2D incidence
  contribution proportional to `Gamma / (pi * chord * section_speed)` before
  looking up the polar and updating circulation. Its circulation sign
  convention must be preserved when comparing this formula.
- Lines 931–950 place that control point half a local chord downstream of the
  bound-segment midpoint. It is a chord-directed offset, unlike ASWING's
  wind-directed construction.
- Lines 717–784 provide two load formulas. The optional AVL-style path uses
  circulation and velocity on the bound-segment midpoint; the other uses the
  section coefficients and corrected section angle. Lines 825–883 show the
  former's full velocity sum and `rho * Gamma * (V cross segment)` force.
  `ll_loads_avl` defaults to false in the retained parameter source.

The [doublet velocity routine](../../reference/third_party/dust/src/aeroel/mod_doublet.f90),
lines 224–252, applies a Rankine core based on each segment's length. There is
no adjacent-strip exclusion in this loop. The default `rankine_rad` is 0.1,
so the core radius is 10% of segment length. The separate endpoint cutoff
defaults to 0.001 times segment length. These settings apply within the
retained lifting-line velocity path, whereas OpenSwing uses zero core for
interactions within one physical lifting surface.

The [parameter source](../../reference/third_party/dust/src/general/mod_sim_param.f90),
lines 401–431, also enables a stall regularization by default that removes
isolated stalled sections. Therefore matching DUST near stall would require
recording its polar and regularization settings; it cannot validate the
ASWING stall law by itself. No such smoothing or core was introduced here.

This is useful evidence for checking the complete relationship between
source geometry, section closure and force recovery. It does not resolve
the [ASWING quarter-chord notation ambiguity](../../artifacts/isae/quarter-chord-source-audit-20261030/report.md).
In particular, DUST does not justify changing only OpenSwing's force receiver.

## OLAF: collocation and section normalization

Retained revision: `2895884d2be01862173c88d70f86b358d2f1a50a`.
In [FVW_Wings.f90](../../reference/third_party/openfast/modules/aerodyn/src/FVW_Wings.f90):

- Lines 109–114 select van Garrel's full-cosine approximation, which uses
  neighboring panel widths. Lines 218–225 interpolate receivers onto the
  straight bound segments. This differs from OpenSwing's global Glauert
  angular midpoint and independent offset construction; neither difference
  establishes an error against Drela's equations.
- Lines 417–468 include every lifting-line/first-wake ring in the nonlinear
  circulation iteration. Neighbors are not arbitrarily omitted. The
  Biot–Savart kernel handles points exactly on a straight segment separately.
- Lines 556–580 project velocity and `V cross dl` into the section plane,
  then equate polar lift and the projected Kutta–Joukowski force. This makes
  the section-speed, panel-area and force-line definitions explicit.

The [OLAF theory](https://openfast.readthedocs.io/en/main/source/user/aerodyn-olaf/OLAFTheory.html)
describes the available core models. Their selection is a modeling choice,
separate from the zero-core arithmetic comparison below.

## Executed comparison and its limits

The [harness](../../artifacts/isae/lifting-line-additional-review-20261030/compare_olaf.py)
compiles the unmodified `FVW_BiotSavart.f90` with a small NWTC type shim selecting
64-bit reals. It calls only `ui_seg_11` with unit circulation and no core;
this is not a full OpenFAST build or a nonlinear solver comparison.

All **13,020 baseline finite-segment vector comparisons** pass the preselected
2e−8 scaled tolerance. They cover deterministic random geometry at three
length scales, every non-self bound contribution at the six saved SA-4
force-point sets, and every bound contribution at their tangency points.
The largest scaled error is **9.85e−10**. Eight very small upstream-zero
vectors account for the largest differences. No own-bound force convention,
wake-ray model, integrated drag or refined equilibrium is validated by this.

A separate nine-point proximity witness deliberately approaches a unit
segment. OLAF's endpoint-vector expression loses accuracy and returns zero
at distances 1e−9–1e−11 in this double-precision build, while OpenSwing's
expression retains the finite off-axis velocity. These differences are
retained as failed parity diagnostics, outside the baseline count. This
shows why an external code's cutoff cannot be treated as the exact answer
near a singularity. It is not a newly discovered OpenSwing defect.

[Full numerical results](../../artifacts/isae/lifting-line-additional-review-20261030/olaf-comparison.json)
retain every group, source/input hashes, build command and the proximity
witness. All 131 production Python modules were unchanged during execution.

The strongest remaining SA-4 questions are the source-line construction from
the input geometry and the consistent force/self-influence convention on that
line. MachUpX, DUST and OLAF provide distinct examples to audit those choices,
but none supplies the missing native ASWING convention. SA-1/SA-5 additionally
need section-law/loading comparisons; arithmetic agreement does not settle
their high-angle circulation differences. All native ledger counts are unchanged.

The subsequent [input-spline audit](../../artifacts/isae/sa4-input-spline-audit-20261030/report.md)
reproduces the SA-4 bend with compiled Drela SPLINE/SEGSPL routines. This rules
out a Python spline implementation error as its cause, without establishing
the native ASWING caller or subsequent discrete beam/source geometry.

The following [CASEI coordinate audit](../../artifacts/isae/scn-discrete-length-audit-20261030/report.md)
adds a native-output constraint on that discrete step: among four tested
interpretations, only SEGSPL plus computational-node chord lengths survives
every rounding-aware coordinate exclusion check. Three coarse meshes have
simultaneous feasibility witnesses, but native grid generation is still
unresolved. No source geometry or force formula is changed by that finding.

Public DUST downloads intermittently timed out. All three retained Fortran
files were ultimately retrieved at the pinned commit, with their full MIT
permission notices intact; its root README/license downloads remain unavailable
in the manifest. OLAF's Apache-2.0 license is retained. No full external solver
was installed, and no browser package was rebuilt.
