# FW mesh sensitivity at 38 ft/s

The original 40-panel R5 frequency discrepancy decreases with refinement,
but the change is not monotonic. The user then redirected the investigation
to Daedalus Bode response. All ten bounded jobs are complete and reaped;
no further FW solver job is running.

| Requested count | Actual lifting panels | Descriptor states | R5 growth, 1/s | R5 angular frequency, rad/s | Frequency error |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 32 | 40 | 796 | −6.991913 | 1.572284 | −5.3329% |
| 48 | 56 | 1100 | −7.014569 | 1.584838 | −4.5771% |
| 64 | 72 | 1404 | −7.004456 | 1.580377 | −4.8457% |

The published reference is **−7.002315 + 1.660856i/s**. The two refined
frequencies fall inside the current 5% target, but retain a difference larger
than the estimated 0.01/s PDF coordinate uncertainty. This does not establish
an asymptotic mesh limit or the original ASWING discretization.

All cases use literal `fw.asw`, the current `accurate-arc-v2` recipe and the
same inferred free-glide constraints. Physical properties and production
equations are unchanged. Piecewise physical-field interpolation supplies
only an unconverged initial guess on each new native mesh; the full nonlinear
equilibrium is then corrected. Residuals are **8.433e−13** and **6.029e−13**
for the 56- and 72-panel cases. No interpolated field is accepted as a result.

At 56 panels only R5 was sought. At 72 panels the three middle roots were
sought: approximately **−4.279153 + 5.653989i/s**, **−7.004456 + 1.580377i/s**,
and **−6.326290 + 4.511086i/s**. All **16/16** full nonlinear residual
directional checks pass at the two prescribed widths. Other roots on the
finer meshes were not checked. The method retains the full descriptor and
uses the shifted Arnoldi operator in Drela's Unsteady Extension, pp. 28–29,
Eqs. 144–149; no reduced model is used.

The [checkpoint](../../artifacts/fw-mesh-refinement-20261114/checkpoint.json)
retains all source hashes, numerical values, residual checks and terminal
receipts. Each job used one BLAS thread under the existing 512 MiB address
space, 15 CPU-second and 25 wall-second limits. The longest solve used
13.481 CPU seconds. The
[runner](../../scripts/check_fw_mesh_refinement_20261114.py) remains available
for an explicitly chosen follow-up. An unexecuted draft all-mode report was
removed when the scope changed; no nine-mode refined result is claimed.

The original [comparison](fw-current-mesh-20261114.md), its app plot and its
18/108 compared-position coverage remain unchanged. These alternative mesh
settings are not added to that total. No ISAE fraction or scope changed.
