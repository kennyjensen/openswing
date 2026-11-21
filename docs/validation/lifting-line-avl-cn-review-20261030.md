# Further lifting-line and strip-code references

2026-10-30. Two further implementations have been downloaded and inspected:
AVL 3.52 and CN-AeroModels. Their unmodified source selections, licenses and
file hashes are retained under `third_party`. This review identifies specific
comparisons; it establishes no new OpenSwing defect or native ASWING pass.

| Reference | Best use in the remaining SA1–5 investigation | Evidence inspected |
|---|---|---|
| [AVL, Drela/Youngren](https://web.mit.edu/drela/Public/web/avl/) | Force locations, near-field versus Trefftz drag, neighboring vortices and surface-leg forces | Release 3.52 source and version notes; [manifest](../../reference/third_party/avl/SOURCE.json) |
| [CN-AeroModels, Centrale Nantes](https://gitlab.com/lheea/CN-AeroModels) | Section-speed normalization, nonlinear section closure, straight versus bent wakes and strip forces | Revision `f2ec3867988fe94df1e34e3c34f3de310ebf3ffe`; [manifest](../../reference/third_party/cn_aeromodels/SOURCE.json) |
| [MachUpX](https://github.com/usuaero/MachUpX), previously retained | Curved/swept lifting-line singularities, particularly SA-4 | [Earlier source review](lifting-line-source-review-20261030.md) |
| [DUST](https://public.gitlab.polimi.it/DAER/dust) and [TU Delft VSM](https://github.com/awegroup/Vortex-Step-Method), previously retained | Relationship between circulation-control points, force points and section corrections | [DUST review](lifting-line-additional-review-20261030.md), [VSM review](vortex-step-method-review-20261030.md) |

## AVL: an explicit history of force-sampling errors

The [official version notes](https://web.mit.edu/drela/Public/web/avl/version_notes.txt)
record a 3.16 change from geometric-midpoint force evaluation to points following
the selected spacing distribution. The authors report much closer near-field
and Trefftz drag afterward. This directly supports auditing sampling locations,
although it does not identify native ASWING's convention.

In the retained 3.52 source:

- `src/amake.f:139` and `:166` generate an interleaved array of strip endpoints
  and interior points using `SPACER`. At `:348` and `:505`, the same interior
  fraction interpolates the strip geometry and bound-vortex force point.
  `src/sgutil.f:235` defines uniform, cosine, sine and blended distributions.
- `src/aic.f:83` loops over every receiver/source pair. At `:118`, the own
  bound contribution is suppressed when `LVTEST` is set and the indices match;
  immediate neighbors remain. The same-component near-field core is
  `0.0001 * projected_strip_width` (`:99`). Its Trefftz counterpart is zero
  (`src/atpforc.f:163`). These are actual differences from OpenSwing's zero-core
  interactions within one lifting surface, not an instruction to tune a core.
- `src/aero.f:457` uses the bound endpoint-difference vector in the
  Kutta–Joukowski force. `src/atpforc.f:134` and `:290` use projected wake
  geometry for the far-field calculation. Their paired geometry and sampling
  are relevant to SA-4; our force integration uses Drela's section-span vector
  and material interval measure.
- `src/aero.f:608` adds forces on trailing-leg portions lying on the surface
  when enabled. This particular term uses freestream plus rotational velocity,
  explicitly excluding induced velocity (`:652`). **For a steady translating
  case, this term alone cannot change freestream-axis drag:**
  `Vinf · (Vinf × leg) = 0`. This is an algebraic inference from the source,
  and distinguishes it from VSM's induced-flow surface-leg treatment.

OpenSwing already uses the Glauert-angle construction prescribed by ASWING
Eqs.151–156. AVL's force-point history therefore does not reveal an omitted
generic midpoint correction. The unresolved question is the consistent
construction of the curved beam, bound endpoints, section frame and force
receiver. AVL has a different lattice and prescribed wake direction; its
spacing routine cannot be substituted wholesale for ASWING's equations.

## CN-AeroModels: inspect both sides of the lift equation

The [nonlinear lifting-line documentation](https://lheea.gitlab.io/CN-AeroModels/nonlinear_lifting_line.html)
provides the section closure and its `useAWSsquare` option. The implementation
confirms that the choice affects both circulation residual and recovered force:

- `code/src/NonlinearLiftingLine.cpp:156` assembles all source/receiver pairs.
  For a straight horseshoe, only the own bound contribution is omitted when
  its receiver has no chordwise offset (`:179`); neighbors remain. The receiver
  is `center - kappa * chord`, and optional bent horseshoes add finite legs.
- `:480` sums freestream, motion and induced velocity. `:508` projects that
  velocity perpendicular to the section axis. Lines `:542` and `:611` implement
  the two dynamic-pressure and closure choices together. With induced velocity
  included in section speed, the residual reduces to
  `2 Gamma = chord * cl * |Vperp|`.
- `code/src/StripTheory.cpp:167` and `:209` provide a simpler section-only force
  path for inspecting projections and coefficient normalization. It does not
  supply induced drag by itself.

OpenSwing's `openswing/aero.py:470`, `:484` and `:690` already use total local
velocity projected perpendicular to the section span, with
`cl = 2 Gamma / (chord * |Vperp|)`. Thus this inspection does **not** expose a
mistaken use of freestream speed or full three-dimensional speed in that
normalization. The circulation equations still differ: OpenSwing targets
ASWING's tangency/leakage law, while CN-AeroModels uses section polar closure.
Its polar interpolation, stall behavior and wake geometry are not ASWING
reference results.

## Result and next comparison

The most useful lead remains a complete geometry/force comparison for SA-4,
including every adjacent strip. For SA-1/SA-5, compare section-law inputs,
local flow and load projection together. These sources supply independently
inspectable implementations; a closer answer from a different formulation
would not by itself justify changing the ASWING implementation.

All 23 retained files were verified against their manifests, and the AVL
selection was checked byte-for-byte against the official archive. AVL is
GPL v2 or later; CN-AeroModels is EPL 2.0. Neither was installed as a solver or
added to the browser runtime. No aerodynamic solve or numerical parity test
was run in this review. All 131 production Python modules and all 42 case
rows remain unchanged; the 3% reference tolerance is unchanged.

The earlier AeroSandbox and OLAF kernel comparisons remain the executed
external arithmetic evidence. A further legacy TU Delft NLLL site was found,
but its source/manual endpoint timed out, so no implementation claims are
made for it. [Verification record](../../artifacts/isae/lifting-line-avl-cn-review-20261030/verification.json).
