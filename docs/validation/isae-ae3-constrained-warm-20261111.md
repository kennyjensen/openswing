# AE-3: constrained sparse warm correction

Observed 2026-11-11 UTC. **The Python solver now uses its existing complete
sparse Newton path for mounted steady moving-frame corrections with canonical
acceleration/net-load constraints.** The two AE-3 roll-target checks take
**5.36 / 5.45 supervised wall seconds**, compared with **24.72 / 24.78 seconds**
in the saved dense runs. They reproduce the same physical solution under the
same resource and acceptance limits.

This is a performance improvement, not a new ASWING reference match. The last
complete native comparison remains **434/725 passing at 5%**, with 178 measured
mismatches and 113 unavailable targets. Browser and build checks remain held;
these timings describe local Python execution.

## Change and source basis

The warm-solver eligibility guard previously declined every operating constraint,
including AE-3's `angular_acceleration.x` unknown paired with its net `moment.x`
target. The resulting dense correction and final dense rank check consumed
nearly the whole 25-second worker budget.

Only `seeded_corrector._decline_reasons` changed. It now admits the canonical
`acceleration.{x,y,z}` / `force.{x,y,z}` and
`angular_acceleration.{x,y,z}` / `moment.{x,y,z}` pairs for the exact
`SourceAirflowNetwork` class in steady-trim mode. It reuses the existing
`acceleration_load_constraints` predicate. Other network classes with operating
constraints, time-network instances, noncanonical pairs, custom equations,
control allocation and existing exclusions retain their previous paths.

The full acceleration columns and net-load rows remain in the matrix. The beam
factor leaves these global variables in its reduced system, then recovers the
eliminated beam variables and checks the original full linear equations. No
acceleration is frozen and no load equation is dropped. The residual, matrix
entries, nonlinear acceptance, factor algorithm and rank threshold are unchanged.
Newton factors are released before the fresh final tangent. Its existing sparse
rank certificate retains the full-SVD fallback when the bound is inconclusive.

The [authoritative reference index](aswing-authoritative-references.md) and its
[checksummed catalog](aswing-authoritative-sources.json) were consulted. Drela's
[steady description](../../reference/aswing-authoritative-20261108/drela-aswing-steady.pdf),
§3.8, p. 29, describes partial beam solutions combined through joint and global
variables without approximating the full Newton solution. Section 4.6, pp. 36–37,
separately discusses lagged influence terms. This dispatch change uses the
already implemented complete matrix; it introduces no new influence approximation.
Jan's [Part IV](../../reference/aswing-authoritative-20261108/isae-part-4-aeroelasticity.pdf)
remains authoritative for AE-3's documented setup and original/modified-ASWING
distinction. The conditional sibling-control and free-roll setup remains a
diagnostic, not a replacement for the literal-model primary comparison.

## Verification

**43 regression tests pass**, comprising 13 new constrained tests, 23 existing
eligibility tests and seven existing moving-airflow warm-correction tests.

The new tests cover roll acceleration with and without real mass, both frozen
and updated influences, and all six acceleration/net-load pairs with real mass.
They compare warm results with cold solves and the original dense warm route;
check geometry, internal loads, circulation, operating values and external loads;
and verify a fresh full residual and independently differenced full-matrix action.
They also check unchanged seeds, cache ownership, factor release, dense recovery
after injected factor failure, and rejection of unsupported constraint contexts.
The existing wall-root tests continue to reject physical wall crossings.

The two full-size AE-3 jobs retain the previous inputs and saved seed. Their
net-roll-moment targets are **−0.0001 and +0.0001 N m**, with the same nominal
80 / actual 82-interval grid. Each uses one Newton correction and no dense
iteration tangent. The final rank certificate gives a conservative reciprocal
condition lower bound of approximately **1.15e−7**, above the unchanged **1e−10**
threshold. The saved dense calculation's full-SVD value was approximately
2.38e−6; the certificate is a bound, not an estimate of that value.

| Measure | Negative target | Positive target |
|---|---:|---:|
| Candidate supervised wall time | 5.358 s | 5.452 s |
| Saved dense supervised wall time | 24.721 s | 24.778 s |
| Candidate worker CPU time | 3.589 s | 3.663 s |
| Candidate worker wall time | 4.433 s | 4.518 s |
| Peak RSS | 107,912 KiB | 107,012 KiB |
| Fresh full residual | 9.656e−13 | 9.654e−13 |

**46 numerical checks pass**, including fresh residuals, net-load targets,
apparent-inertia action, support balance, root constraints, dense-result parity
and the centered roll response. Across **13,260 recorded scalar values**, the
largest absolute dense-parity difference is **2.56e−13**; all retain the prior
`2e−9 + 2e−7 × |reference|` parity gate. The centered acceleration and Cl responses
agree with the previously computed full tangent within **0.0000842% / 0.0001264%**.
These tests confirm the same conditional branch, not the archived MM mask.

All numerical children ran serially with one BLAS thread and unchanged
**512 MiB address space / 15 CPU seconds / 25 wall seconds**. All fourteen
launched children were reaped. Eleven jobs completed successfully. Three
nonpassing attempts remain recorded: an initial wall timeout without a test
result, a missing required load-factor argument in the new test, and a diagnostic
audit that expected an equilibrium-state packet from an output-only result.
The two harness mistakes were corrected; their original source and failures
remain in the evidence directory. Neither required changing the solver candidate
or loosening a gate. Earlier passing eligibility functions were authenticated
against their preserved source after the test-only correction.

## Adoption and remaining work

The [assessment](../../artifacts/isae/ae3-constrained-warm-20261111/assessment.json)
records tests, field comparisons, timings and every terminal attempt. The
[adoption receipt](../../artifacts/isae/ae3-constrained-warm-20261111/adoption.json)
verifies that the entire production Python package matches the tested isolated
candidate. Only the eligibility function differs from the preserved original.
The [new regressions](../../tests/test_constrained_airflow_seeded.py) are part of
the normal test suite.

The native comparison keeps its original source hashes and was not repeated.
Its coefficient jobs use cold equilibria, and auxiliary jobs restore checkpoints
and evaluate unchanged observables. The receipt explicitly records this source
continuity; the warm-only change adds no native votes. Progress fractions and
unavailable denominators are unchanged.

The subsequent [independent nonlinear control-response check](isae-ae3-control-nonlinear-20261111.md)
completes eight full solves and passes 130 checks, with both the roll constraint
active and the actual acceleration held fixed. The high-speed reference
discrepancy, original model identity, control slopes and MM setup remain unresolved.
