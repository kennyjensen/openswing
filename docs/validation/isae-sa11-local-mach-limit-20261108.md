# SA-11: mathematical Mach limit versus the OpenSwing hard stop

2026-11-08 UTC. The user asked why the local-Mach limit exists and whether
it can be removed. **The full-analysis hard stop is an OpenSwing implementation
choice; native ASWING's runtime behavior at that limit has not been established.**
The underlying section-moment equation does have a mathematical singularity.
Those two statements must remain distinct when diagnosing SA-11.

Follow-up: the [partial surface-force display](isae-sa11-partial-forces-20261108.md)
now exposes finite lift/drag sums in the rejection panel and diagnostic JSON.
Complete results and coupled equilibria still require a valid moment; the
formula and its gate are unchanged. The implementation audit below records the
state before this presentation follow-up.

## Published requirement

The [authoritative index](aswing-authoritative-references.md) and checksummed
catalog identify Drela's steady technical description. **Equation 73, printed
p. 17**, defines the section pitching-moment coefficient as

```text
cm = (cm0 + sum(dcm/d(deltaF) * deltaF)) / sqrt(1 - M_perp^2)
M_perp = |V_perp| / sound_speed.
```

Equation 72 multiplies this coefficient by the local normal dynamic pressure,
chord squared and section span direction. The velocity includes the induced
flow; this is not merely the flight Mach number. The
[original user guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt),
under **Prandtl-Glauert Mach number — M**, explicitly says this local section-Cm
scaling is always computed independently of the global PG Mach setting.
The [MIT technical description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf#page=17)
and guide were opened again during this audit. Neither cited passage specifies
a clipping rule or the executable's failure behavior at Mach one.

For a nonzero numerator, the correction becomes unbounded approaching Mach one
from below and has no real value above it. The SA-11 upper winglets have nonzero
section `Cm` (−0.1123 in the supplied file). Setting the global PG Mach to zero
does not disable this independently specified moment correction.

## Actual implementation

In `openswing/aero.py`, `evaluate_aerodynamics` computes circulation and the
lifting-strip lift/profile-force arrays before checking `local_mach >= 1`.
The next expression is `p["cm"] / np.sqrt(1 - local_mach ** 2)`. The guard
currently raises an `AnalysisError`, preserving rejected-section and vortex
diagnostics, before assembling a complete force/moment result.

Deleting only that guard would not supply a real section moment. Replacing
the square root by an absolute value, clipping local Mach, using flight Mach,
or omitting the affected section moment would each change the model and its
derivatives. None is established as native ASWING behavior by this audit.
The existing source-guided implementation is unchanged.

For a prescribed rigid geometry, finite force sums can be retained separately
as diagnostics while the moment remains unavailable. The existing
[whole-beam study](isae-sa11-whole-beam-polar-20261108.md) already does that in
research artifacts. This would also be possible as an explicit partial-output
UI policy; it is not implemented by this documentation change. Finite force
sums alone do not verify the near-junction velocity, and a coupled equilibrium
still needs the missing section moments in its structural equations.

The next native evidence should explicitly record any section-Mach or moment
limiting treatment, along with its mesh and velocity sampling. Published
ASWING output does not by itself establish which of those implementation or
setup differences prevented an undefined moment.

No solver, input, scope or pass-count change is made. SA-11 remains
**163/9,184 at 5%**. This clarification neither declares native ASWING would
abort nor treats OpenSwing's rejected states as native-reference passes.

## Older-publication and related-source check

A follow-up checked Drela's [AIAA 99-1394 paper, printed p. 5](https://web.mit.edu/drela/Public/web/aswing/asw_aiaa.pdf#page=6),
also retained as `reference/asw_aiaa.pdf`. Its section-moment expression after
Eq. 16 already uses the same local perpendicular-Mach correction. That passage
does not specify a cap or an above-unity continuation. The public FAQ and
version notes did not supply a section-moment limiter in this search. These
checks provide no evidence for replacing the published expression, and do not
establish what an executable does outside its domain.

The apparent matching square root in public JVL is a different operation:
`reference/third_party/jvl/src/jtpforc.f:916` defines `pgmat`, called at line 111 with
the global `amach`. Its `1/sqrt(1-mach**2)` constructs the vortex-coordinate
transformation. It is not evidence of a local ASWING section-moment limiter.
No solver equation or comparison fraction was changed by this follow-up.
