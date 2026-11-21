# SA-11: what total pitching moment can tell us about the invalid root flow

2026-11-08 UTC. The archived total pitching moments do **not** determine a
usable correction for the two invalid winglet-root velocities. At the current
5% tolerance, a broad range of hypothetical root section moments would fit the
total. Matching the printed central values by changing only those two section
moments would instead require a near-singular local Prandtl–Glauert factor.
Neither observation supplies a valid velocity field or an accepted prediction.

This saved-field audit also locates the receiver change in the preceding
[drag comparison](isae-sa11-winglet-receivers-20261108.md): the main-wing
receivers move materially, while the winglet-root receivers essentially stay
fixed. Their improved but still invalid velocities result from changed
circulation. The primary SA-11 score remains **163/9,184 at 5%**. No production
equation, reference target, tolerance, scope or pass count changes.

## Conditional moment calculation

The [authoritative index](aswing-authoritative-references.md) and checksummed
catalog were consulted. Drela's steady description, **Eqs. 72–74, pp. 16–17**,
defines the quarter-chord lift moment and intrinsic section moment, with the
local beam-normal Mach correction. **Eqs. 221 and 225, pp. 53–54**, define the
integrated origin moment and stability-axis transformation. The registered
polar adapter maps archived `CM` to production `Cm_origin`; that convention
is retained.

The calculation reuses the two saved 0°/1° states with each of the native and
whole-beam receiver rules. Conditions remain the disclosed report-derived
−4° twist and bundled Joint correction, original section data, 240 m/s,
density 1.2256, global PG Mach `240/340.21`, frozen influences, and 64 native
endpoint intervals. This conditional setup does not authenticate the original
archived producing input.

For each state, retain **all finite force moments, including the root forces**,
and all valid intrinsic section moments. Call their sum `Cknown`. Replace only
the two undefined intrinsic root moments by hypothetical subsonic values.
This is a deliberately limited algebraic hypothesis: changing a real velocity
would also change forces and could change circulation.

With `w_i = c_i² cm0_i s_y,i ds_i / (S Cref)`, the intrinsic contribution is

```text
Cm_i = w_i (a/U)² M_i² / sqrt(1 - M_i²).
```

Both root weights are negative. Therefore the hypothetical total cannot exceed
`Cknown`. If every root Mach number is at most `m`, the magnitude of the root
contribution is bounded by

```text
|Cm_roots| <= B m² / sqrt(1 - m²),
B = -(a/U)² sum(w_roots) = 7.3037438989e-6.
```

Inverting this monotone inequality yields a necessary lower bound on the
largest hypothetical root Mach. It does not compute or recommend a corrected
velocity. Square roots in the actual saved fields are evaluated only at valid
sections; no full winglet moment is produced.

| Alpha | Receivers | Archived CM | Cknown | Root contribution needed for central token | Necessary condition for printed interval |
|---:|---|---:|---:|---:|---|
| 0° | Native | −0.351307 | −0.353727726 | +0.002420726 | Impossible under this fixed-force hypothesis: root weights are negative |
| 0° | Whole beam | −0.351307 | −0.348307820 | −0.002999180 | At least one root Mach ≥ 0.9999970338 |
| 1° | Native | −0.469163 | −0.472731887 | +0.003568887 | Impossible under this fixed-force hypothesis: root weights are negative |
| 1° | Whole beam | −0.469163 | −0.465246174 | −0.003916826 | At least one root Mach ≥ 0.9999982610 |

The printed intervals retain ±0.0000005 rounding uncertainty. They are an
additional diagnostic, **not a tighter acceptance tolerance**. All four
existing 5% bands intersect this weak moment-only envelope, with no positive
lower Mach bound. For example, the whole-beam known subtotals are already
within 0.854%/0.835% of the archived totals. These incomplete subtotals are
not predictions and are not scored as passes.

The actual whole-beam states still reach local Mach **1.22339/1.53418**, so the
production rejection remains necessary. The exact-token bounds show why fitting
only a root section moment would be uninformative: it would exploit the
singularity at Mach one while leaving the governing field unresolved.

## Which receivers actually moved

Native AVL's cosine spacing is not generally an arithmetic endpoint midpoint.
In `amake.f`, lines 139–145 select every even `SPACER` entry for a strip receiver;
lines 348–367 interpolate that station within its declared section interval.
`sgutil.f`, lines 235–301, defines cosine spacing using the literal
`PI=3.1415926535`. Thus native receivers lie at cosine **angle midpoints within
each section interval**. Reconstructing that rule from the saved AVL input
reproduces its span stations within **2.23e−16 m**.

Drela's ASWING **Eqs. 150–157, pp. 31–33**, instead use the whole logical beam's
Glauert-angle domain. In this conversion, the main wing is split into several
AVL section intervals; each straight winglet spans one interval over its whole
beam. The latter two angle domains therefore coincide to rounding.

| Beam | Maximum force receiver movement | Maximum control receiver movement |
|---|---:|---:|
| Main wing | 18.638883 mm | 17.527455 mm |
| Upper winglet, positive y | 5.516e−13 m | 5.048e−13 m |
| Upper winglet, negative y | 5.517e−13 m | 5.048e−13 m |

The two root receivers are about **0.600659 mm** from the arithmetic midpoint
of their native bound endpoints. A symmetric decomposition of the four saved
velocity fields separates moving receivers from changing circulation. At the
roots, the direct receiver contribution is at most **3.28e−8 of the total
velocity-change norm**; the change is effectively all from the re-solved
circulation. The decomposition closes within 3.56e−15 m/s. This explains why
main-wing force integration improves substantially without removing the root
failure.

## Verification and remaining work

The moment reconstruction first reproduces two already valid baseline controls:
`Cm_origin = −0.2579997585918245` and `−0.3429246755382075`, within **5.56e−17**.
An independent 50-digit scalar reconstruction of forces, moment arms and local
PG terms agrees within **1.12e−16**. A separate 60-digit monotone bisection
checks all eight printed/tolerance envelope results, agreeing with the closed
form within **1.12e−16**. The verifier checks **172 source pins and six artifact
pins**. No new physical solves were needed; all jobs terminated normally.

Keep the documented sampling and force/moment laws. The remaining question is
the local flow at the actual offset wing/winglet junction and the archived
producing setup. A consistent candidate must explain those velocities while
preserving the newly close lift/drag comparison. Agreement of aggregate moment
within 5% cannot resolve this local question or validate a root correction.

- [Moment audit driver](../../scripts/audit-sa11-root-moment-envelope.py)
- [Plan](../../artifacts/isae/sa11-root-moment-envelope-20261108/plan.json)
- [Moment analysis](../../artifacts/isae/sa11-root-moment-envelope-20261108/analysis.json)
- [Independent bound checker](../../scripts/check-sa11-root-moment-envelope.py)
- [Verification receipt](../../artifacts/isae/sa11-root-moment-envelope-20261108/verification.json)
- [Receiver-location source audit](../../scripts/audit-sa11-receiver-locations.py)
- [Receiver-location results](../../artifacts/isae/sa11-root-moment-envelope-20261108/receiver-locations.json)
- [AVL amake.f](../../reference/avl-native-20261108/source/AVL3.52rel09032025/src/amake.f)
- [AVL sgutil.f](../../reference/avl-native-20261108/source/AVL3.52rel09032025/src/sgutil.f)
