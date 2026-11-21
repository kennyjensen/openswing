# Mounted solver acceleration

A later [exact-reuse optimization](mounted-tangent-reuse.md) builds on this version.

The 2026-10-11 follow-up retains the physical equations, mesh, precision,
finite-difference steps, rank check, four load increments and existing convergence
tolerances. It applies to ordinary mounted equilibrium. The full ASWING goal
remains incomplete; all 40 broad requirements remain Partial.

Rigid structures with zero beam compliance and no elastic hinge/strut restraints
can start intermediate load steps from a copy of the preceding Jacobian.
Finite-stiffness models retain the original fresh Jacobian at every stage.
The initial rank check, first loaded step and final full-load step use fresh
Jacobians. A warm attempt has a 50-evaluation budget; if it fails, the same load
step retries with a fresh Jacobian and the original solver budget before load
reduction. MINPACK can request fresh derivatives at a changed state. Trim,
allocation, custom-target, saved-state and dynamic initialization retain their
existing continuation/correction paths.

Unconstrained steady trial evaluations compute the original forces, moments and
circulation residual, including body, propulsion, inertia, ground and validity
checks. They defer report formatting, wake diagnostics and sensor reporting.
Detailed results and operating/dynamic residuals retain full evaluations. The
report mode is part of the aerodynamic cache key, so a trial entry cannot stand
in for a full report at the same state.

Sequential single-run observations on the same shared host:

| Case, unchanged 48-panel setting | Native before | Native after | Browser before | Browser after |
|---|---:|---:|---:|---:|
| Default rectangular wing | 16.827 s | 8.899 s | 45.981 s | 23.376 s |
| Flexible wing | 17.809 s | 13.795 s | 41.552 s | 31.940 s |

Browser times cover the actual UI worker request through reply, excluding cold
runtime loading. Native times exclude profiling. Timing varies with device and
host load. Default residual evaluations fall from 1900 to 1150; flexible-wing
evaluations remain 1860, with less work per trial. Profiling of the default case reduces full
Jacobian assemblies from five to three.

All 151 selected native tests pass, including 14 new cases. Trial/full
residuals and complete Jacobians are exactly equal in nine configurations:
rigid, flexible, powered, wing/body, articulated, frozen-influence, ground-effect,
Fourier-circulation and moving-frame cases. Forced warm failures recover the
same physical equilibrium with a fresh solve at the same load. Existing tests
check independent structural mechanics, mesh refinement, force/moment balance,
propulsion, bodies, ground, joints, struts, trim, local airflow, detailed section
output and saved equilibria. This is not a full-suite run.

Complete native comparisons cover 7,965 and 7,677 numeric fields respectively,
excluding only the top-level evaluation counter. Every other numeric field must
satisfy 1e-8 absolute plus 1e-8 relative error, and all nonnumeric fields must
match. Maximum differences divided by max(1, |baseline|) are
3.26e-13 and
0. The actual rebuilt
browser passes complete same-runtime before/after comparisons using the same
bounds; only its software provenance and evaluation counter are excluded.
The 71 served modules match the measured candidate and main source.
The default result is numerically equivalent within these checks. The complete
native flexible result is byte-identical to its baseline, including the evaluation
count. The flexible browser export also retains every compared value exactly,
including its evaluation count; only software provenance changes. Report deferral
alone also retained the entire default output byte for byte.

An earlier candidate reused the final tangent and produced excessive near-zero
moment drift on the flexible wing. Even with a fresh final tangent, seven near-zero
moments exceeded the unchanged browser comparison bound (maximum difference
2.785e-8); both versions were rejected. The accepted implementation keeps the
original fresh-stage method for finite-stiffness models. The failed candidate
browser workflow remains recorded as FAIL. The first baseline-browser harness failed
after a successful solve because its in-memory request contained an undefined
property omitted by JSON. Its retained physical result passed an independent
export/provenance audit; the original workflow remains recorded as FAIL. The
corrected flexible baseline and the final browser comparison pass.

[Machine-readable results](mounted-acceleration.json) and
[evidence](mounted-acceleration-evidence.zip) retain the original and candidate
sources, requests, outputs, profiles, selected-test record, browser observations
and rejected attempts. Each evidence member has a SHA-256 entry in MANIFEST.json.
To repeat native measurements, extract the evidence and run its
`measure-mounted.py baseline NEW_LABEL` and
`measure-mounted.py candidate-06 NEW_LABEL` using the repository virtualenv;
add `--flexible` for that case, and use single-threaded BLAS as in
`bench-sequential.sh`.
