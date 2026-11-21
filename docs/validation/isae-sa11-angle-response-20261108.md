# SA-11: incidence changes do not resolve the root-flow failure

2026-11-08 UTC. Three small, serial production calls test the two
[prepared incidence conventions](isae-sa11-angle-conventions-20261108.md)
against a fresh −4° control. Both alternatives leave two rejected upper-winglet
root sections. Incidence interpretation changes the integrated forces modestly
but does not explain the excessive local velocity. This favors investigating
the junction representation next; it does not establish a particular repair.

## Fixed setup and results

Upper-winglet-only input, alpha 1°, speed 240 m/s, PG Mach 240/340.21,
frozen influences, original section data, shared physical index 1 and the
unchanged zero-core same-surface interaction. The exact 64-interval endpoint
grid from the earlier native-AVL comparison is retained, with production
whole-beam Glauert receivers. This is a disclosed diagnostic grid, not an
authenticated archived ASWING discretization or a claim about the default mesh.

The common Joint multiplier correction is retained. Beyond that, only the
four upper-winglet twist tokens differ between the prepared inputs. The
production parser confirms that the other distributions, records, reference
quantities, and all frozen vortex endpoints/receivers are unchanged. Computed
section normals agree with the independent scalar construction within 2e-14.

Reference at this row: CL = 0.336959 and raw CD = 0.0103591. The comparison
uses raw archived drag, before the common 0.0064 plotting allowance.

| Interpretation | ASW twist | Formal CL error | Formal CD error | Maximum normal Mach | Rejected sections |
|---|---:|---:|---:|---:|---:|
| Report-sign control | −4.000000° | −0.692% | +0.065% | 1.534184 | 2 |
| Horizontal-cut 4° toe-out | −4.770283° | −1.073% | +0.621% | 1.514995 | 2 |
| Unswept-section −4° incidence | −5.004796° | −1.189% | +0.806% | 1.509162 | 2 |

**These are rejected-state surface-force sums, not accepted aerodynamic
results.** Section moments and a complete equilibrium remain unavailable.
Both alternative angles follow explicit source interpretations, not a fit to
the archived forces. Neither is authenticated as the original producing input.

The fresh control reproduces the saved circulation, velocity and section CL
exactly, and its formal force sums reproduce the prior independently replayed
values. All three circulation residuals are below 1e-14. Minimum section stall
margins are 25.4–26.4 times the configured stall width, so this result is
unrelated to a stalled-section fix.

At the worst root receiver the summed wake-induced speed decreases from
488.0 to 481.1 or 479.0 m/s; the summed bound-induced speed is only
4.52, 4.43 or 4.40 m/s. These vector magnitudes are attribution diagnostics,
not additive scalar flow speeds. The frozen 53.211 mm quarter-chord root
offset remains unchanged, as does the receiver's close proximity to the
main-wing root wake ray. Incidence changes alter circulation but leave this
geometry mechanism intact.

## Implication for the next experiment

Do not select an incidence merely because it reduces a force error. Preserve
the explicitly labeled variants and resolve their interpretation when comparing
the full paper geometry. For the immediate failure, prioritize the following
controlled tests from the [reassessment](isae-sa11-reassessment-20261108.md):

1. Small symmetric attachment-position changes on the fixed grid, recording
   root ray distances and separate bound/wake velocities. Use prescribed
   perturbations to measure sensitivity, not a search for a passing value.
2. Isolate coincident versus offset quarter-chord roots, then separately
   introduce a smooth transition of quarter-chord position/tangent, chord and
   incidence. NASA describes junction fillets and rounded corners, but neither
   the physical radius nor native ASWING's junction treatment is established.
3. Repeat each fixed geometry on a second grid. A lower peak at one sample is
   insufficient; local flow and complete loads must remain well behaved as
   discretization changes. Retain the paper's absolute curves and matched-lift
   drag increments as independent constraints on the geometry experiment.

The sharp-corner singularity literature supports testing a smooth geometry.
It does not authorize silently changing the benchmark, adding a fitted core,
or calling the current native-ASWING comparison passed. Successful native
Figure 22 results remain evidence that our reproduction is incomplete.

## Execution and evidence

Each invocation ran one production solve with one BLAS thread, no subprocesses
or background jobs, and own-process limits of 512 MiB address space, 15 CPU
seconds and 25 wall seconds. All three terminated normally. Solves took
0.024–0.056 seconds; complete processes, including imports and source checks,
took 3.48–7.17 seconds. Reported peak RSS was 215–217 MiB. This does not
establish the cause of the earlier UserLAnd crash; the interrupted Vite,
browser and build work remains stopped.

- [Single-case driver](../../scripts/verify-sa11-angle-response.py).
- [Verification, errors and per-case report hashes](../../artifacts/isae/sa11-angle-response-20261108/verification.json).
- [Control](../../artifacts/isae/sa11-angle-response-20261108/report_minus4/report.json),
  [horizontal-cut variant](../../artifacts/isae/sa11-angle-response-20261108/horizontal_toe_minus4/report.json),
  [unswept-section variant](../../artifacts/isae/sa11-angle-response-20261108/unswept_incidence_minus4/report.json).

Each case retains its exact model, module/input hashes, mesh, condition,
geometry, circulation/velocity/force arrays and full rejection diagnostics.
Checks independently reconstruct span-normal Mach and scalar force projections,
verify every artifact/current-input hash, and confirm both rejected beams.

Primary SA-11 completion remains **163/9,184 at 5%**. No completion fraction,
comparison scope, original model, production equation or guard changed.
