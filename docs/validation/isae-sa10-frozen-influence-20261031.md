# SA-10 frozen-influence comparison

2026-10-31. The alternate frozen-influence interpretation of the drivers'
`K/F` toggle worsens the sampled SA-10 comparison. It does not resolve the
tip-sail failures. Registered SA-10 stays **1,256/2,268**; production defaults,
native data and validity gates are unchanged.

## Controlled scope

The guide defines frozen influences using undeformed geometry and zero wind
angles; steady theory section 4.6 describes the same option. The six SA-10
drivers toggle F before solving their operating-point stacks. The guide's
displayed initial F=T supports the current-influence reconstruction already
used, but the producing executable's startup state is not retained.

We therefore test the other setting explicitly on the five runnable literal
models: wing alone, wing extension, Louvered, TS_60_40_80 and TS_80_60_40.
The original TS_60_45_30 joint conflict remains excluded and blocked.

The predeclared 35 cold calls comprise 10°, 20° and 25° on each model's
registered fine mesh, at stall strengths 40 and 20, plus five zero-incidence
strength-40 controls. Circulation remains pointwise. Only the frozen-influence
flag changes relative to the matched controls. Strength 20 remains an
unconfirmed native setting. Native CM uses the corrected origin reference.

## Native comparisons

Each nonzero-incidence scope contains 15 conditions and seven outputs per
condition. Rejected states remain in the denominator.

| Stall strength | Current influences | Frozen influences | Gains | Losses | Valid frozen states |
|---|---:|---:|---:|---:|---:|
| 40, default | 47/105 | 14/105 | 2 | 35 | 9/15 |
| 20, diagnostic | 89/105 | 28/105 | 0 | 61 | 9/15 |

| Model | Current → frozen, strength 40 | Current → frozen, strength 20 |
|---|---:|---:|
| Wing alone | 11/21 → 6/21 | 21/21 → 7/21 |
| Wing extension | 8/21 → 3/21 | 21/21 → 9/21 |
| Louvered | 8/21 → 5/21 | 21/21 → 12/21 |
| TS_60_40_80 | 7/21 → 0/21 | 12/21 → 0/21 |
| TS_80_60_40 | 13/21 → 0/21 | 14/21 → 0/21 |

Among failed finite outputs of the valid, nonzero-incidence frozen states,
default-strength median errors are **CL 7.35%, CD 5.89%, CDi 12.47%,
CM 7.74%**; maxima are 9.07%, 12.04%, 15.39% and 9.71%, respectively.
Rejected states have no accepted coefficient error. These are diagnostic
statistics, not replacements for the registered error column.

All twelve nonzero-incidence tip-sail conditions are rejected, including
both 10° states at both strengths. Their mathematical local normal Mach
values range from **94.66 to 174.95**, far outside the subsonic model's
domain. They are not physical aircraft-flow predictions. The frozen wake
geometry aggravates the close-filament interactions; no resulting force
coefficients are accepted.

## Independent checks

All 35 calls terminate: **23 computed states and 12 local-Mach rejections**,
with no worker failures. All processes are reaped. An independent scalar
reconstruction gives maximum local tangency residual **4.84e−12**, normalized
by flight speed. Thus the rejected cases solve the declared circulation
equations but fail local-flow validity.

Reconstructed valid-state forces agree exactly, and origin moments agree
within **4.87e−16** after coefficient normalization. At zero incidence,
where current and frozen influence geometry coincide for these rigid cases,
all five fresh wrenches reproduce the saved current-influence controls within
**4.60e−24** scaled error.

A separate 60-digit Biot–Savart integration reconstructs **30 peak velocity
vectors**, one for every nonzero-incidence frozen state. It uses the frozen
x-directed wake and the actual angled freestream as distinct vectors.
Maximum error is **8.81e−9 times flight speed**, and every local-Mach
classification agrees. These checks independently reproduce the singular
field behavior; they do not turn rejected states into valid solutions.

The final verifier reads the five original full-variable output tables and
checks all **245 native scalar entries**, the pass transitions, source hashes
and five zero-incidence controls. Analysis and verification complete without
physical retries. No production tests are added because solver code is unchanged.

This rules out the tested frozen setting as a remedy across the sampled
models. It does not recover the historical startup settings. Together with
the [tip-sail Fourier comparison](isae-sa10-tip-fourier-20261031.md), it narrows
the remaining investigation to discretization/source geometry and native
setup differences, rather than either tested option alone. The broader
SA-6–SA-10 comparison and full project remain unfinished.

Artifacts: [predeclared plan](../../artifacts/isae/sa10-frozen-influence-20261031/plan.json),
[comparison and equation checks](../../artifacts/isae/sa10-frozen-influence-20261031/analysis.json),
[independent fields](../../artifacts/isae/sa10-frozen-influence-20261031/field-verification.json),
[verification receipt](../../artifacts/isae/sa10-frozen-influence-20261031/receipt.json),
[run log](../../artifacts/isae/sa10-frozen-influence-20261031/run.log).
