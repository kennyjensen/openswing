# SA-11 extension: adjacent wake terms and a redistribution check

The latest mesh-dependent drag change is concentrated in **finite-origin
trailing-wake interactions between neighboring strips**. These terms account
for **79.97% and 86.06%** of the last two changes in near-field vortex CD at
240 m/s and 3°. The changing bound-vortex term is much smaller.

A follow-up that smooths interval widths **does not fix the integrated drag**.
Three new runs retain every mandatory station, each mandatory span's interval
count, the 16.466 mm minimum, original inputs and aerodynamic equations. They
still change CD by **2.24% and 1.12%** across refinements and match the archived
CD slightly worse. Thus the large local terms are explained, but suppressing
individual width jumps is not a sufficient repair of the aggregate result.

No production meshing rule, aerodynamic equation, primary comparison scope
or completion fraction changes. SA-11 stays **1,060/9,184**. The previously
identified center-Mach rejection remains a separate validity issue.

![Redistribution result](../../artifacts/isae/sa11-extension-redistribution-20261108/extension-redistribution.png)

[Standalone SVG](../../artifacts/isae/sa11-extension-redistribution-20261108/extension-redistribution.svg).
The left panel uses the unchanged 5% reference tolerance. The 1% line on the
right is only the previously declared mesh-stability diagnostic, not a new
passing criterion for the primary suite.

## References and scope

The [authoritative index](aswing-authoritative-references.md) and checksummed
[source catalog](aswing-authoritative-sources.json) were consulted. Drela's
steady description **Eqs. 55–56, pp. 13–14** gives the conservative discrete
force balance; **Eqs. 64–70, pp. 15–16** gives the local force; **Eqs. 149–161,
pp. 30–33** gives PG mapping, vortex influences and Glauert receiver locations.
**Eqs. 207–211, p. 49** defines the separate Trefftz calculation.

Five saved accepted extension states at **240 m/s, alpha 3°**, with
60/108/160/172/178 actual intervals, are reused. They retain the original ASW
file and current-wind influences, density 1.2256, speed-derived PG Mach,
natural-v1 interpolation, section properties, stall model and fixed minimum.
The five field audits require **zero new aerodynamic solves**. The prior
[winglet drag-closure audit](isae-sa11-drag-closure-20261108.md) supplies the
decomposition framework, but its different geometry and frozen-wake cases
are not substituted for these extension states.

## Exact accounting of the saved fields

In wind coordinates, a semi-infinite ray is separated algebraically into
half of the infinite-ray field and its finite-origin contribution. The
finite bound-segment field is integrated independently, with the same
own-bound exclusion and zero same-component core. Each term is contracted
with the saved circulation and the original beam-span force measure:

```text
CD_ij = rho Gamma_i Gamma_j
        * [v_ij cross (span_i ds_i)] dot wind / (q S)
q = rho V² / 2
```

All own trailing legs and all neighboring contributions remain present.
The partitions are signed accounting terms, not separately removable loads.

| Actual intervals | Bound CD | Half-wake CD | Finite-origin CD | Near-field vortex CD |
|---:|---:|---:|---:|---:|
| 60 | 0.01247436 | 0.01190013 | −0.01577436 | 0.00860013 |
| 108 | 0.01429951 | 0.01189808 | −0.01710317 | 0.00909442 |
| 160 | 0.01612676 | 0.01189729 | −0.01751873 | 0.01050531 |
| 172 | 0.01613408 | 0.01189702 | −0.01785688 | 0.01017422 |
| 178 | 0.01613663 | 0.01189642 | −0.01803530 | 0.00999775 |

At 160 → 172 intervals, the near-field vortex CD change is −0.000331096.
Finite-origin wake changes −0.000338154, of which immediately neighboring
pairs contribute −0.000264766. At 172 → 178, the corresponding changes are
−0.000176464, −0.000178412 and −0.000151872. Bound and half-wake changes
partly oppose the finite-origin change.

The center-adjacent pair's combined bound/finite-origin contribution changes
only −2.11e-7 and −6.19e-8 in these two steps. The stronger changing terms
are elsewhere on the wing. Earlier coarse refinements include larger,
opposing bound and finite-origin changes, so the finest-mesh percentages
should not be generalized to every mesh transition.

## A closed-form neighboring-pair check

Consider two adjacent collinear bound segments with lengths L and R,
receiver fractions f and g measured from each segment's start, and direction
u in wind coordinates. Define beta = sqrt(1 − M²) and

```text
kappa = (u_x / beta) / sqrt((u_x / beta)² + u_y² + u_z²)
G = 1/(1−f) − L/((1−f)L+R) + R/(L+gR) − 1/g
CD_pair_finite = rho Gamma_i Gamma_j kappa G / (4 pi q S)
```

This is derived directly from the two ray terms above, using the straight
bound-segment force measure. It describes the **combined off-diagonal
finite-origin contribution**, not total drag. In this straight surrogate,
equal widths and arithmetic-midpoint receivers give G = 0; unequal widths
can produce a nonzero pair term even at arithmetic midpoints. Reflection
and uniform length scaling obey the expected algebraic identities.

For each saved mesh, the strongest non-center neighboring pair is selected
by absolute contribution. Its two nearly collinear segments are replaced
only in this analytical check by their mean geometric direction. Their
lengths, receiver fractions and circulations are measured from the saved
state. No parameter is fitted to a drag target.

| Actual intervals | Selected neighboring width ratio | Actual finite-origin pair CD | Straight-surrogate difference |
|---:|---:|---:|---:|
| 60 | 4.178 | 0.00152062 | +0.094% |
| 108 | 2.099 | 0.00085716 | +0.115% |
| 160 | 1.973 | 0.00066923 | +0.179% |
| 172 | 1.483 | 0.00039505 | +0.262% |
| 178 | 1.485 | 0.00041711 | +0.252% |

The angle between the selected segments is only 0.013–0.023°. The small
surrogate differences retain the effects of actual curvature, receiver
offset and beam force measure. The formula agrees with an exact straight
two-segment field calculation within **9.76e-19 in CD**.

A [candidate-node audit](../../artifacts/isae/sa11-extension-drag-pairs-20261108/spacing-transitions.json)
also identifies the spacing mechanism. The strongest 60/108-interval pair
starts at mandatory station t = 0.432 m; the following short remainder and
full cosine interval already exist before coarsening. For 160/172/178, the
selected neighboring retained intervals span **1 versus 2, 3 versus 2, and
6 versus 4** original candidate intervals. Their shared stations are not
mandatory. Thus both mandatory-node insertion and minimum-spacing
coarsening can produce the local width changes; not every jump is newly
introduced by the minimum rule.

## Count-preserving redistribution falsifies a simple smoothing fix

The geometry evidence motivated a predeclared three-call check. Within each
span between mandatory stations, retain exactly the existing number of
intervals and distribute them uniformly in material arc length. Preserve
endpoints, all attachment/property stations, the minimum spacing, original
model and all other settings. Explicit diagnostic nodes use the normal
production solver; no force sample or vortex term is manually changed.

| Actual intervals | Maximum adjacent width ratio after redistribution | Original CD error | Redistributed CD error |
|---:|---:|---:|---:|
| 160 | 1.206 | +4.203% | +5.064% |
| 172 | 1.084 | +2.260% | +2.761% |
| 178 | 1.075 | +1.225% | +1.623% |

All three states converge, with maximum normal Mach **0.81972** and minimum
stall margin **20.37 transition widths**. Mandatory-span counts and uniform
material lengths are checked independently. Despite much smaller width
jumps, the net non-center neighboring bound/finite-origin term increases
slightly. Other local contributions compensate when nodes and circulation
are redistributed. The CD refinement changes are **2.241% and 1.120%**,
compared with **1.900% and 1.023%** in the controls. No mesh in the experiment
is selected as a replacement.

The trial therefore does not support changing the production coarsener or
adding a width-ratio parameter. Large individual pair terms explain where
sensitivity is expressed; they do not by themselves establish its complete
cause or imply that removing those terms is correct.

## Evidence and remaining work

- Pair [plan](../../artifacts/isae/sa11-extension-drag-pairs-20261108/plan.json),
  [driver](../../scripts/audit-sa11-extension-drag-pairs.py),
  [independent scalar/formula checker](../../scripts/check-sa11-extension-drag-pairs.py),
  [verified analysis](../../artifacts/isae/sa11-extension-drag-pairs-20261108/analysis.json),
  and [node-origin checker](../../scripts/check-sa11-extension-spacing-transitions.py).
  All 271 source/control pins and saved pair arrays are authenticated.
  Maximum velocity discrepancy is **1.29e-14 times freestream**; near-CD
  reconstruction error is **3.75e-16**.
- Redistribution [plan](../../artifacts/isae/sa11-extension-redistribution-20261108/plan.json),
  [driver](../../scripts/verify-sa11-extension-redistribution.py),
  [checker](../../scripts/check-sa11-extension-redistribution.py), and
  [verified analysis](../../artifacts/isae/sa11-extension-redistribution-20261108/analysis.json).
  All 275 pins, preserved station/count/minimum invariants, forces, moments
  and independent physical fields verify. Maximum field discrepancy is
  **1.38e-14 times freestream**, force/moment coefficient error **3.34e-16**.
- Five saved-field jobs and three physical calls ran serially with one BLAS
  thread, 512 MiB address space, 15 CPU / 25 wall seconds per invocation.
  Longest invocation **3.70 s**, peak RSS **272.84 MiB**. All are terminal;
  no solver retry, timeout, browser or build job occurred. A preparation
  check caught omitted domain endpoints before writing the redistribution
  plan or solving; it was corrected to use the full mandatory-station list.

More node-count or width-ratio tuning is not supported by this result. The
remaining question is the full discrete load recovery and sampling used by
ASWING for these inputs, including the distinction between structural
averages and Glauert aerodynamic samples. The explicit equations checked
here agree with the implemented field and local force; no contradictory
source evidence or verified replacement rule has yet been established.
