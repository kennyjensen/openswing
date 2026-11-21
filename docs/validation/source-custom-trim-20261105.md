# Custom steady equations and redundant controls with source operators

Date: 2026-11-05. The scoped physical, regression and offline browser checks pass.

The stationary coupled and moving-airflow source policies now accept custom
steady operating equations and weighted allocation of redundant flap/engine
controls. They use the existing simultaneous equilibrium/trim equations and
equality-constrained optimizer. Physical equations, tolerances, tangent-rank,
one-sided smoothness and reduced-curvature checks are unchanged. Moving-airflow
trim also retains its controller equations and solved command variables.

ASWING's [v5.86 release notes](https://web.mit.edu/drela/Public/web/aswing/version_notes.txt)
describe user-defined GCON constraints targeting sensor quantities, and weighted
least-squares constraints for redundant flaps and engines. The public notes do
not establish the exact weight normalization or optimizer. OpenSwing retains
its explicit objective `1/2 sum(weight * (setting - preferred)^2)` under hard
physical constraints. This is a checked local minimum, not a claim of ASWING's
exact weight convention or a global optimum. Its declarative expressions do
not execute arbitrary Fortran GCON routines.

The former restriction concealed a section-recovery mismatch. The parent
residual evaluated custom equations using generic midpoint sections before
the source operator supplied its own constitutive section data. On an undamped
bar with EA increasing from 1000 to 2000, a tip strain of .005 requires 10 N.
Temporarily bypassing only the policy guard, both source policies instead
solved 9.633883476 N: 3.6612% low. The final reported anchor strain did not match
the target's sampling convention. Both failing checks are retained.

Custom evaluation now dispatches through the selected operator's section
recovery. Source constitutive data come from the same helper as the source
residual, including its material damping correction. Undamped sensor strains
use the selected one-sided anchor section. Damped sensor strains retain their
declared adjacent interval estimate because an endpoint material-rate field
is not defined. Source endpoint loads and shell stresses retain their existing
one-sided properties. Ordinary source residuals reuse their already computed
endpoint frames.

The new physical checks cover:

- The variable-stiffness tip target in both source policies: exactly 10 N and
  .005 anchor strain, with the custom target equal to the reported measurement.
- A damped variable-stiffness bar: the same target uses the documented average
  endpoint stiffness of the selected interval; endpoint strain remains null.
- Redundant engines in both policies: minimizing `E1^2 + 4 E2^2` under
  `E1 + 2 E2 = 5` gives `E1=2.5`, `E2=1.25` and spring extension .01.
- A source-airflow controller command: the .005 strain target gives actual
  thrust 5 N and command bias 7 N under proportional position feedback.
- Undefined section measurements, nonsmooth targets and dependent equations:
  each is rejected by its existing physical or tangent check.
- Warm allocated trim from 5 to 8 N, then a separate saved-state time launch:
  solved actuator settings persist, trim equations are released, and launch
  does not recompute equilibrium. This is a held-state launch check, not a new
  forced transient refinement study.
- A deformed lifting wing with three proportional flap distributions:
  the independent minimum-effort projection `[.6, .3, -.3]` reproduces the
  prescribed flap combination 1.5. Every node and circulation value, and CL,
  CD and Cm, agree with the separately solved loaded reference.

All 11 new Python checks and 141 affected regressions pass (152 total), as do
25 JavaScript checks. Regressions include source section and damping recovery,
complete BDF/Radau mechanical columns, existing generic custom targets and
request validation. The actual built browser passes offline custom strain trim
with two redundant engines, project save/restore and a saved-state time launch
in approximately 1.5 minutes including setup. The browser target requires a
10 N total load and obtains settings 5 and 2.5 with .005 anchor strain.
All 138 source/public/dist kernel modules match.

Native replay of both exact exported requests passes 8,962 numerical field
comparisons at the unchanged `2e-8 + 2e-8 * abs(native)` gate, plus strings,
booleans and list lengths. The largest difference uses .002417 of its gate.
Optimizer work counters differ: native uses 10 iterations and the browser 11;
these are retained as diagnostics. The roundoff-sensitive one-sided tangent
ratios are .001620 and .002429 respectively, both below the original limit 1.
That diagnostic is checked independently against its unchanged acceptance gate;
its numerical value is not treated as a physical observable. The initial strict
comparison failure and all six differing fields are retained. No physical gate
or production equation was changed in response. The completed native trim was
reused only after checking its output, request and source hashes; the missing
time replay was then completed.

No new native ASWING reference result is introduced. All 42 ISAE rows and error
summaries remain unchanged. Full ASWING functionality, native agreement, source
steady derivatives and the other broad completion requirements remain open.

Code: [custom dispatch](../../openswing/network.py),
[source section data](../../openswing/source_discrete.py),
[policy validation](../../openswing/numerical_policy.py),
[physical checks](../../tests/test_source_custom_trim.py),
[browser workflow](../../tests/browser/source-custom-trim.spec.js).
Requests, outputs and logs are retained in
`artifacts/isae/source-custom-trim-20261105/`.
