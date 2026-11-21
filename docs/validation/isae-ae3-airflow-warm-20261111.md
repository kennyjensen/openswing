# AE-3: sparse moving-airflow warm correction and sideslip verification

Observed 2026-11-11 UTC. **Moving-airflow steady solves can now use the existing
complete sparse Newton correction when starting from a saved equilibrium.**
The four AE-3 sideslip perturbations complete under the unchanged resource
limits. Their independently reconverged response agrees with the implicit
derivative to within **2.217e−11** across all six coefficient rows.

This confirms the implemented derivative on the selected branch. It does not
resolve its disagreement with the archived ASWING CLb or validate the historical
setup. The last complete native comparison remains **434/725 passing**, with
612 computed, 178 mismatches and 113 unavailable.

## Performance problem and adopted change

The warm-corrector eligibility check accepted only the ordinary static and
stationary source-coupled network classes. A moving-airflow steady network
therefore bypassed the existing complete sparse matrix/beam-factor route.
Its generic dense correction was too expensive for the first full-size AE-3
perturbation worker. That worker exited −9 before the supervisor's wall timeout.
A 15-second CPU hard limit was installed, consistent with that termination;
the failed worker's CPU usage was not retained, so no speedup ratio is claimed.

Two dispatch guards changed:

- `seeded_corrector._decline_reasons` accepts the exact `SourceAirflowNetwork`
  class when explicitly constructed for steady trim. Existing mounted-support,
  operating-constraint, feedback, hinge, engine, strut and cache-ownership
  restrictions remain. Time-network instances and custom subclasses retain
  their previous path.
- `equilibrium_state.correct` uses the network Jacobian for the corresponding
  dense recovery path, preserving the existing treatment of wall-root derivative
  probes. Ordinary physical trials still reject crossings of the wall.

The residual, matrix entries, factor algorithm, nonlinear convergence rule,
final fresh tangent and rank threshold are unchanged. The solver releases its
Newton factor before the final tangent. These changes were tested in an isolated
package before adoption; the entire production Python package then matched the
tested candidate byte for byte. Original versions of both edited files remain
in the evidence directory.

## Verification

**32 distinct regression tests pass:** seven new moving-airflow tests and 25
existing eligibility/adapter tests. The new tests cover real and zero real mass,
updated and frozen influences, nonzero frame rates and accelerations, and
agreement with both cold equilibria and the original dense correction. Injected
factor failure checks dense recovery at a stationary wall root, including
continued rejection of physical wall crossings. Time and custom-class exclusions
are checked separately.

The initial wall fixtures incorrectly combined that stationary boundary with
frame acceleration and were correctly rejected. Corrected stationary-wall
fixtures pass; nonzero motion remains covered by the other four tests. The
original test source and failed records are retained. AST comparison verifies
that the four earlier passing motion tests and their imports were unaffected
by that fixture correction.

Four full-size AE-3 workers each solve one sideslip perturbation. They pass
**36 fresh physical checks**, followed by **12 comparisons to the implicit
derivative and six step-refinement checks**: **54 numerical checks total**.
Maximum freshly evaluated full residual is **2.740e−13**. Each corrected state
also passes the original final tangent rank check using a conservative sparse
certificate, without a dense iteration factor.

Worker CPU time is **11.962–13.629 seconds**, wall time **14.281–19.257 seconds**,
and peak RSS at most **129,584 KiB**. Every job runs serially with one BLAS thread,
512 MiB address space, 15 CPU seconds and 25 wall seconds. All children are reaped.
These are local Python measurements; browser and build checks remain held.

## What the sideslip check establishes

The [authoritative reference index](aswing-authoritative-references.md) and its
checksummed sources were consulted. Drela steady Eq. 1 and §8.5 Eq. 218 agree
with the implemented sideslip sign and stability-axis rotation. Eqs. 155–157
specify wind-aligned vortex receivers, while §4.6 describes lagging some influence
dependences during Newton iteration. §§8.3–8.6 define the implicit equilibrium
response and aerodynamic force mapping.

The tested base is the previously disclosed sibling-control/roll-acceleration
diagnostic, at 27.0934 m/s and nominal 80 intervals, as described in the
[full native-MM setup study](isae-ae3-mm-setup-20261111.md). The original
constraint is restored and checked first. Its actual nonzero angular acceleration
is then held fixed; only sideslip changes. Independent nonlinear solves use
±0.0001 and ±0.00005 radians, with a tighter 1e−11 equilibrium tolerance to
resolve these small differences. They do not use the implicit derivative as
their initial perturbation.

| CLb calculation | Value |
|---|---:|
| Archived ASWING | 0.002120000000 |
| Full implicit response | 0.003505391695 |
| Independent nonlinear difference, step 0.0001 rad | 0.003505391595 |
| Independent nonlinear difference, step 0.00005 rad | 0.003505391673 |

The **65.35% native discrepancy remains**. The agreement between the latter
three calculations rules out a substantial derivative-linearization error on
this particular branch; it does not prove historical ASWING equivalence.

A separate experiment held wind-dependent receivers fixed to isolate their
contribution. Its input-refinement metric was **5.252e−6**, above the unchanged
**2e−7** gate. That diagnostic remains failed and unqualified; no receiver or
wake approximation was adopted. Investigating the archived influence convention
and CLb setup remains useful, with this failed experiment preserved.

## Evidence and provenance

- [Candidate assessment](../../artifacts/isae/ae3-airflow-warm-20261111/assessment.json): regression provenance, all four nonlinear results, derivative comparisons, checks and timings.
- [Adoption receipt](../../artifacts/isae/ae3-airflow-warm-20261111/adoption.json): exact package parity, preserved originals, changed functions and native-result source continuity.
- [Regression tests](../../tests/test_source_airflow_seeded.py).
- [Original diagnostic plan and failed attempts](../../artifacts/isae/ae3-sideslip-20261111/plan.json).

The complete native comparison retains its original source hashes. Its twelve
coefficient jobs used cold solves; checkpoint auxiliary jobs restore states and
evaluate the unchanged full-observable helper. Only the two warm-dispatch
functions changed. Their source continuity is recorded explicitly; this update
adds no native votes and does not claim a new full native replay.
