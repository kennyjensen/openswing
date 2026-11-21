# Curved-wing station spacing in the public CASEI listings

2026-10-30 follow-up: the [fixed node-generation comparison](../../artifacts/isae/scn-node-generation-audit-20261030/report.md)
extends the coordinate evidence to all five meshes and executes the related
Drela polygon/spline routines. None of 44 tested recipes reproduces every
station; polygon tables worsen agreement and ordinary quadrature refinement
does not remove the remaining mismatch. The historical results below remain
retained as their original, separately qualified scope.

Updated 2026-10-29. The previously inferred modified-cosine formula is much
closer to the public curved-wing stations when applied to **material arc
length** than directly to the file's parameter `t`. Neither tested spline
reproduces every printed station. This supports the mapping used in the
SA-1–SA-5 spacing diagnostic without authenticating a universal ASWING
node-generation algorithm. Production defaults and registered scores are
unchanged.

A [source follow-up](../../artifacts/isae/scn-curved-spacing-20261029/arc-source-note.md)
confirms that ASWING's theory defines material arc by the full three-dimensional
length integral. The manual specifies cubic geometry in `t` but does not
identify its arc table, integration rule or inverse routine. JVL's separate
airfoil `SCALC` and surface `MAKESURF` routines use polygon lengths for different
purposes; neither is an authenticated ASWING caller or a basis for replacing
the published arc integral to fit the remaining coordinate discrepancies.

## Fixed formula, independent geometry comparison

The formula remains exactly the candidate previously checked against
rectangular-wing and WingLoop-tail station evidence:

```
q = largest binary32 value below 1
u_j = sin((2*j/N - 1) * asin(q))
eta_j = 0.7*u_j + 0.3*u_j^3
```

The tips and center are set exactly to −1, 0 and +1. No coefficient, count,
angular clip or endpoint rule was fitted to CASEI. The comparison uses the
original CASEI geometry and N6/N12/N96 public listings. Independent cubic
equations evaluate the existing natural and zero-third endpoint rules;
arc length integrates `sqrt(1 + x'(t)^2)` because this model has `y=t,z=0`.
Inverse arc length uses bracketed bisection.

| Mapping | N6 stations | N12 stations | N96 stations | Total within printed interval | Maximum `t` error |
|---|---:|---:|---:|---:|---:|
| Directly to `t` | 3/7 | 3/13 | 3/97 | 9/117 | 9.393 mm |
| Natural-spline material arc | 5/7 | 9/13 | 75/97 | 89/117 | 0.0791 mm |
| Zero-third-spline material arc | 5/7 | 9/13 | 87/97 | 101/117 | 0.0620 mm |

The printed half-unit is **0.05 mm**. Each listing counts its doubled root
once, retaining both source rows. The denominator 117 sums stations across
three resolutions; it is not 117 globally unique locations. The direct map
matches only the imposed root and tips. All 351 comparisons, including
misses, are retained. Tightening quadrature changes inverse coordinates by
at most 1.013e-13 m; the maximum inverse-arc residual is 3.55e-14 m.

An independent saved-data review passes 2,028 audit checks with no mismatches.
It checks exact Decimal print intervals, formula identity, source hashes,
saved spline equations and process receipts. It does not rerun integration
or inverse solves. No aerodynamic calculations were made.

## What this resolves for SA-1–SA-5

The original material-arc extension was supported only by straight/swept-wing
coordinates, where parameter and arc fractions cannot distinguish these
choices. CASEI supplies independent curved-axis evidence in favor of material
arc mapping. A direct-parameter replacement is therefore poorly supported by
these coordinates.

This does not resolve SA-4. CASEI is a different input model from registered
SA-3 and SA-4; the exact historical producer and `D=0` listing setting remain
unverified. A closer zero-third station comparison also does not override
the [fresh spline-policy flow comparison](isae-sa34-spline-endpoints-20261029.md),
where switching policies loses three selected output checks and introduces
another failed solve. Station placement, discrete node positions and
aerodynamic frame construction are separate questions.

The complete spacing comparison remains **1,186/1,288 → 1,204/1,288**:
SA-2 gains all remaining checks, SA-5 improves, SA-1 is nearly unchanged,
SA-3 retains its passes, and SA-4 regresses overall. The
[case-by-case report](isae-sa1-sa5-spacing-20261029.md) separates near-field
drag sensitivity, high-incidence circulation/induced-drag deficits, curved-tip
geometry failures and undefined zero-lift efficiency outputs.

## Can printed-coordinate rounding explain the box-position mismatch?

A separate geometry-only calculation encloses the Eq.48 zero-strain node
positions while each interior printed `t` varies by **±0.05 mm**. Root and
literal tip parameters stay fixed. This addresses the earlier box-position
comparison, not the modified-cosine station test above.

The calculation solves the spline equations as exact rational numbers from
the literal decimal input. Outward-rounded interval arithmetic bounds arc
integration with the midpoint-rule second-derivative remainder. A mean-value
bound includes the shared-node cancellation between adjacent box intervals;
it propagates all allowed interior-parameter perturbations simultaneously.
The native `y` interval also includes its ±0.05 mm print allowance.

| Spline | Listing | Positive nodes whose mismatch cannot be explained by `t` rounding | Remaining tip gap after both print allowances |
|---|---|---:|---:|
| Natural | N6 | 2/3 | At least 4.476 mm |
| Natural | N12 | 2/6 | At least 1.880 mm |
| Natural | N96 | 0/48 excluded | Inconclusive |
| Zero-third | N6 | 2/3 | At least 2.727 mm |
| Zero-third | N12 | 2/6 | At least 1.399 mm |
| Zero-third | N96 | 0/48 excluded | Inconclusive |

Central-coordinate enclosures are at most 1.078e-9 m wide and contain the
earlier numerical integrals. The fine-grid rounding bounds widen to
0.241/0.217 mm; overlap with a printed interval **does not prove that a
matching geometry is attainable**. This study excludes print precision as
the coarse discrepancy's explanation under either retained spline. It does
not choose a native historical algorithm or resolve the fine listing.
The enclosure assumes the platform's ordinary binary64 arithmetic and
elementary-operation rounding; it is not a platform-independent formal proof.
The exact producer and listing-setting qualifications still apply.
An independent review confirms the spline/derivative equations, source hashes
and all 114 saved positive-node classifications (eight exclusions across both
policies); it does not repeat the integration.

## Reproduction

- [Predeclared protocol](../../artifacts/isae/scn-curved-spacing-20261029/protocol.json)
  and [geometry-only script](../../artifacts/isae/scn-curved-spacing-20261029/run.py).
- [All coordinates and errors](../../artifacts/isae/scn-curved-spacing-20261029/report.json)
  and [execution receipt](../../artifacts/isae/scn-curved-spacing-20261029/terminal-receipt.json).
- [Independent review](../../artifacts/isae/scn-curved-spacing-20261029/saved-review.md)
  and [its saved results](../../artifacts/isae/scn-curved-spacing-20261029/saved-review.json).
- [Printed-parameter enclosure protocol](../../artifacts/isae/scn-box-rounding-20261029/protocol.json),
  [all resulting intervals](../../artifacts/isae/scn-box-rounding-20261029/report.json)
  and [execution receipt](../../artifacts/isae/scn-box-rounding-20261029/terminal-receipt.json).
- [Independent enclosure review](../../artifacts/isae/scn-box-rounding-20261029/source-review.md).
