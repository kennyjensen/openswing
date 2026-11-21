# SA-11: upper/lower coverage and low-lift drag

2026-11-08 UTC. The same **48 paper targets still pass 21/48 at 5%**.
Six bounded serial runs resolve four missing comparisons: three are reference
mismatches and one is a rejected state. The current breakdown is **21 pass,
21 mismatch, two rejected and four missing**. This is additional evidence,
not a solver change, new comparison scope or new pass. The original archive
remains **1,060/9,184**.

| Configuration | Pass / required | Mismatch | Rejected | Missing | Failed errors: median / maximum |
|---|---:|---:|---:|---:|---:|
| Bare wing | 2/12 | 10 | 0 | 0 | 7.12% / 18.90% |
| Planar extension | 8/12 | 4 | 0 | 0 | 7.41% / 8.76% |
| Upper winglet | 11/12 | 1 | 0 | 0 | 5.25% / 5.25% |
| Upper/lower winglets | 0/12 | 6 | 2 | 4 | 11.82% / 36.42% |

[Comparison plots](../../public/isae-sa11-paper/index.html) are served at
`/isae-sa11-paper/`. The [v3 evidence specification](sa11-paper-suite-v3.json)
retains the identities, values, 5% tolerance and interpolation rules of all
48 targets. The preceding [v2 results](isae-sa11-paper-aligned-20261108.md)
remain intact.

## Unchanged setup

The authoritative [index](aswing-authoritative-references.md), checksummed
catalog, Jan Part I **p.35 / Figure 22, p.39**, and the existing authenticated
upper/lower model were consulted. The recorded source checks include the
report and Drela steady formulation. As before, the Joint-station correction
and upper twist of −4° from **Figure 40, p.68**, are disclosed. Lower twist,
70 μm root offset, physical surface index, section properties and reference
dimensions are unchanged.

The original upper/lower file sets CLmax = 0.8; the upper-only model has 2.0.
Neither was altered. The 32 + 16 + 16 + 5 + 5 mesh reproduces the earlier
geometry bit for bit, with the same minimum horseshoe spacing. Frozen
body-x influence geometry, zero shared-surface vortex core, PG correction,
stall strength 40 and width 0.05 remain fixed.

The six angles were declared before running: **0.5°, 0.75°, 3° at 240 m/s**,
and **0.25°, 0.5°, 3° at 272 m/s**. The lower-angle pairs bracket CL = 0.3
without exceeding the quarter-degree interpolation limit. The 3° points
fill existing lift targets; no post-stall repair or high-angle extension was
attempted. CL = 0.5 and 0.7 still lack valid brackets at both speeds, and all
four remain in the denominator.

## Newly resolved comparisons

| Target | Archived ASWING | OpenSwing | Error / outcome |
|---|---:|---:|---|
| CD at CL = 0.3, 240 m/s | 0.009788422 | 0.010890698 | +11.261% |
| CD at CL = 0.3, 272 m/s | 0.009643348 | 0.010837119 | +12.379% |
| CL at 3°, 240 m/s | 0.537409 | 0.423434542 | −21.208% |
| CL at 3°, 272 m/s | 0.578077 | Unavailable | Rejected: local normal Mach 1.041522 |

Five new states are accepted. The faster 3° result retains the production
rejection and contributes no accepted force or moment comparison. The
previous faster 5° rejection is also retained.

At the accepted 3° point, independently evaluated stall leakage corresponds
to **2.751° of tangency angle** at the most affected section. This is not an
aircraft incidence correction. It confirms that the original section limit
materially affects this operating point; it does not establish which limit
the historical ASWING run used.

## Low-lift force accounting identifies a separate useful target

At CL = 0.3, independently reconstructed direct stall-pressure drag is only
**0.000005807 / 0.000006951** at the two speeds: **0.527% / 0.582% of the
total drag discrepancy**. Removing that term alone could not repair the
comparison. This does not isolate indirect stall effects on circulation.

The configured-model change from upper-only to upper/lower at equal lift is:

| Speed | Archived ΔCD | OpenSwing ΔCD | Main-wing contribution | Upper-winglet contribution | Lower-winglet contribution |
|---:|---:|---:|---:|---:|---:|
| 240 m/s | +0.00008143 | +0.00100596 | −0.00108252 | +0.00105928 | +0.00102920 |
| 272 m/s | +0.00003729 | +0.00101053 | −0.00118814 | +0.00109284 | +0.00110583 |

The main/upper changes largely cancel, leaving an increment comparable to
the lower elements' own drag. This localizes the next useful audit to the
lower-element loads and their interactions at low lift. It does not prove
that an isolated lower-element force is wrong: native per-beam loads are
unavailable, the section lift limits differ between models, and each model
uses its own equal-lift incidence. No geometry or parameter fit follows.

## Verification

Each physical run was a separate foreground process, with one BLAS thread,
512 MiB address space, 15 CPU seconds and 25 wall seconds. The longest
recorded batch took **5.50 seconds**, total **28.70 seconds**, peak RSS
**183.86 MiB**. These are local Python measurements, not browser timings.

For all five accepted states, an independent zero-core segment/ray operator
reconstructs bound and control-point velocities. Direct evaluations of the
section CL, stall leakage and vortex/friction/pressure/stall-pressure forces
also agree. Maximum velocity error is **1.10e−15 of freestream**, tangency
defect **2.95e−14 of freestream**, and section-force error **2.28e−13 N**.
The rejected state has an authenticated rejection receipt, not a full
accepted-field replay. No failed state was discarded or relabeled as passing.

The independent 48-target checker authenticates **912 source/artifact hashes**
and verifies every interpolation and decision in Decimal arithmetic. Force
coefficient reduction differs by at most **4.45e−16**, interpolation by
**6.94e−18**. No solver, browser, build, default or acceptance-gate change.

- [Declared run plan](../../artifacts/isae/sa11-lower-coverage-20261108/plan.json)
- [All 48 results](../../artifacts/isae/sa11-paper-suite-coverage-20261108/analysis.json)
- [Independent score verification](../../artifacts/isae/sa11-paper-suite-coverage-20261108/verification.json)
- [Equal-lift force accounting](../../artifacts/isae/sa11-paper-suite-coverage-20261108/low-lift-diagnostics.json)
- [Serial driver](../../scripts/verify_sa11_lower_coverage.py), [field checker](../../scripts/check_sa11_lower_coverage.py), [coverage scorer](../../scripts/sa11_paper_suite_coverage.py)
