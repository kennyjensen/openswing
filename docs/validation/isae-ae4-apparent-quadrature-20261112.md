# AE-4: apparent-fluid quadrature and unsteady load audit

Observed 2026-11-12 UTC. **Apparent-mass load quadrature does not explain the
remaining near-flutter damping discrepancy.** Replacing Glauert-station
sampling with endpoint averaging removes only **0.098–0.101% of the remaining
native damping gap on nominal 160**. The production equations are unchanged.

Independent calculations of the actual Pazy-wing apparent loads,
circulation-rate lift and circulation lag agree with the implemented actions.
All **69 numerical checks** pass in six bounded serial stages. These are
equation and diagnostic checks, not additional native-reference passes.
The registered comparison remains **50/1,200 at 5%**; 1,116 components remain
unrun. AE-4 is not fully validated.

## Question and authoritative equations

The [authoritative index](aswing-authoritative-references.md) and checksummed
catalog were consulted. Drela's steady description, pp.12–14, Eqs.49–56,
defines ordinary endpoint averages for the structural box equations.
Its vortex-influence section, pp.31–32, Eqs.150–154, separately defines
Glauert-angle sampling. That section explicitly limits its redefinition of
the averaging subscript to the section itself.

Drela's unsteady description, pp.8–9, Eqs.33–44, specifies circulation-rate
lift and thin-strip apparent force/couple. The lag correction and implied
two-dimensional response appear on pp.10–11, Eqs.48–56. The section physics
does not unambiguously establish the historical integration rule for apparent
loads in a moving-airflow run. In particular, continuous equations alone do
not prove that all aerodynamic contributions share circulation's quadrature.

OpenSwing currently integrates moving-airflow apparent loads at its aerodynamic
stations, whereas its separate stationary-fluid operator averages completed
endpoint loads. This audit tests that distinction without asserting that either
is the unavailable archived executable's exact implementation. Jan Part IV
§3.4, pp.13–16, remains authoritative for the Pazy case; no AE-3 airfoil or flap
modification is imported into AE-4.

## Controlled comparison

| IAS (m/s) | Nominal intervals | Current critical real part (1/s) | Endpoint diagnostic (1/s) | Native ASWING (1/s) | Native gap removed |
|---:|---:|---:|---:|---:|---:|
| 69 | 80 | −0.1254639112 | −0.1256374523 | −0.1780785000 | 0.330% |
| 69 | 160 | −0.1340178245 | −0.1340610399 | −0.1780785000 | 0.0981% |
| 70 | 160 | +0.6890984943 | +0.6890481526 | +0.6392872200 | 0.1011% |

The endpoint alternative still misses the critical native real components by
**29.448%, 24.718% and 7.784%**, respectively. Each state still passes five of
its six paired native components. These alternative comparisons overlap the
existing targets and add no primary votes.

At 69 m/s, doubling the mesh reduces the quadrature-induced damping shift from
0.00017354/s to 0.00004322/s, approximately a factor of four. The residual
native difference is two to three orders of magnitude larger. The actual
mode shifts agree with independent left/right eigenvector sensitivity estimates
to within 0.00423% relative to the shift. Mechanical mode-shape correlations
exceed 0.9999999986; the result is not explained by switching computed branches.
Native eigenvectors remain unavailable.

Only apparent-fluid quadrature changes in this diagnostic. The saved complete
physical matrices retain circulation, its lag, rate lift, stiffness, real
inertia, load-transfer conventions, gravity, geometry, root constraints and
all four modes in the original shifted search. Each correction is assembled
from an independent transcription of Eqs.43–44, preserving the current
aerodynamic interval length in both alternatives. No matrix coefficients are
thresholded or equations removed.

At these fixed-frame bases, absolute rates and accelerations vanish and
circulation is below 1.3e−18. Thus the apparent-load tangent depends on base
flow crossed with perturbed angular velocity, midchord acceleration and
angular acceleration. The audit verifies these conditions rather than applying
the simplification to a general loaded or rotating wing. It does not implement
nonlinear endpoint-induced-flow sampling.

Fresh physical probes independently check the current apparent-load actions.
A separate full mass-matrix action checks circulation-rate lift, its
quarter-chord moment and the lag equation. The largest discrepancy in these
normalized actions is **3.50e−20**. This supports the audited terms on this wing;
it does not establish the entire aeroelastic model or historical setup.

## Verification, retained failure and next work

Each of the three load audits and three complete modal solves finishes with
one BLAS thread under **512 MiB address space /15 CPU /25 wall-second** caps.
The largest successful worker uses **6.36 CPU seconds, 8.59 supervised wall
seconds and 243.2 MiB peak RSS**. All workers are terminal and reaped.
Complete left/right eigen-equation residuals, mass normalization and root
clamping pass. All **142 production modules** retain their prior hashes.

The first audit is retained as a rejected attempt: it assumed exact equality
between unloaded and current aerodynamic element lengths. Gravity creates a
maximum difference of 2.68e−9 m on nominal 80. The revised diagnostic uses the
same current aerodynamic length in both quadratures, isolating the intended
change. It does not relax an accuracy gate or change production physics.
The first worker was also reaped and stayed within its limits.

The final source/dependency audit completes in 1.24 wall seconds. Original
artifacts, the prospective plan, matrices, vectors, receipts and failed attempt
remain available. No browser, build or background solver job was started.

Next broaden the registered fixed-incidence speed sweep in small serial jobs.
Keep the existing near-onset damping failures, exact archived mesh/startup
settings, the 103 m/s branch mismatch and wall/frame limitations open. The
[previous refinement study](isae-ae4-onset-refinement-20261112.md) still gives
onset interpolation 69.1628 versus 69.2179 m/s, a 0.0795% difference; that close
onset estimate does not replace the failed damping or unrun comparisons.

- [Complete assessment and source hashes](../../artifacts/isae/ae4-apparent-quadrature-r2-20261112/assessment.json)
- [Prospective plan](../../artifacts/isae/ae4-apparent-quadrature-r2-20261112/plan.json)
- [Independent equations and serial harness](../../artifacts/isae/ae4-apparent-quadrature-r2-20261112/run.py)
- [Retained rejected length assumption](../../artifacts/isae/ae4-apparent-quadrature-20261112/cases/v69-n80-audit/report.json)
