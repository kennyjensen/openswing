# Continuous Fourier wakes with nonparallel traces

2026-11-01. The explicit continuous Fourier wake diagnostic now supports
arbitrary orientations of straight traces, including shared endpoints and
crossings. Its application to the retained SA-10 tip-sail pilot changes CDi
by only **0.019–0.391%**, with **no pass/fail changes**. Wake-output quadrature
alone does not resolve those sampled discrepancies.

The API remains `fourier_wake_diagnostic=True`; see the
[usage and original implementation](fourier-wake-diagnostic-20261101.md).
The option is off by default. It uses the selected sine coefficients and
does not change the aircraft circulation, loads, discrete wake outputs or
derivatives. Curved projected traces, ground images and pointwise or mixed
bases remain explicitly unsupported by this diagnostic. The main solver's
geometry support is unchanged. A later [browser-control update](fourier-wake-ui-20261101.md)
wires rigid steady requests and output displays in source; browser-runtime
verification and refreshed packaged kernels remain pending.

## Extension and independent verification

Source and receiver traces now have individual complex directions in the
common wind-normal plane. The analytic source velocity retains the signed
side of the source sheet. Its tangential jump contributes to work on an
angled receiver, so receiver quadrature is split at sheet crossings as well
as source-tip neighborhoods. Both mutual directions must converge and obey
reciprocity at the existing `2e-10` relative energy tolerance.

For joined tips, forming a point as `center + half_span*cos(theta)` can round
it onto the singular source endpoint. Endpoint-relative distances formed
with half-angle identities preserve the small separation. Vertices that
differ only within the existing `64*eps*span` geometry resolution are
reconciled; no vortex core is introduced. Coincident traces are combined
before integration, preserving exact cancellation.

The self term remains exact:

`D_self = rho*pi/8 * sum(n*A_n²)`.

Six added checks cover crossing, separated and joined traces, a perpendicular
elliptic control with zero mutual energy, reversed orientation and rigid-frame
invariance, and approach to exact opposite-wake cancellation. Three cases
use an independent adaptive double integral of logarithmic wake energy:

`D_ij = -rho/(8*pi) * integral integral Gamma_i'(theta)*Gamma_j'(phi)*log(|r_i-r_j|²) dtheta dphi`.

That reference uses neither the production source resolvent nor its velocity
quadrature. All **19 wake-diagnostic tests pass in 8.12 seconds**. The first
attempt exposed the endpoint precision problem and an unjustified assumed
convergence rate in the cancellation test. The latter was replaced by
mirrored-angle symmetry, monotonic approach and exact cancellation checks;
the physical comparison tolerances were not loosened. Both attempts are kept.

## Saved SA-10 comparison

The preceding [Fourier pilot](isae-sa10-tip-fourier-20261031.md) supplies all
32 retained Fourier requests for `TS_60_40_80` and `TS_80_60_40`: 20 computed
states and 12 local-Mach rejections. Four pointwise controls are excluded
because they have no selected Fourier representation. The diagnostic is
available for all 20 computed states; all 12 invalid states remain rejected.

The scope includes the retained 64-interval, 25-degree states as well as the
128-interval states at 10, 20 and 25 degrees. Consequently its denominators
differ from the earlier pilot's 42-output fine-mesh summaries. Every group
below contains five computed and three rejected requests, seven outputs each.
Only CDi and efficiency are replaced for the diagnostic comparison. Native
tokens and the existing 3%/strict-zero rule determine all decisions.

| Stall strength | Modes per beam | Original diagnostic sample | Continuous wake sample | Gains / losses |
|---:|---:|---:|---:|---:|
| 40 | 20 | 17/56 | 17/56 | 0 / 0 |
| 40 | 40 | 15/56 | 15/56 | 0 / 0 |
| 20 | 20 | 19/56 | 19/56 | 0 / 0 |
| 20 | 40 | 25/56 | 25/56 | 0 / 0 |

These **76/224** sample checks include 84 unavailable outputs from the 12
rejected requests. On computed states alone the result is **76/140**. Neither
count is a registered family result or evidence of mesh convergence.

| Computed output | Passing states | Original failed median / maximum error | Continuous failed median / maximum error |
|---|---:|---:|---:|
| CDi | 10/20 | 5.85% / 8.83% | 5.72% / 9.22% |
| Efficiency | 16/20 | 8.02% / 8.22% | 8.36% / 8.55% |

For example, `TS_60_40_80` at 10 degrees, 128 intervals and 20 modes changes
from 8.75% to 9.14% high CDi at strength 40. The retained strength-20 version
changes from 8.83% to 9.22% high. The local-flow and circulation discrepancies
must therefore be investigated separately from this output integration.
This does not establish which algorithm or discretization produced the native
exports.

## Replay integrity and remaining scope

No nonlinear aircraft solve or aerodynamic field evaluation is used. Native
files, saved states and current implementation are hashed before and after
the replay. Reconstructed geometry agrees exactly with the saved geometry;
the maximum relative coefficient difference is `5.11e-17`, and the maximum
circulation reconstruction difference is `1.29e-15`.

All **58 SA-7** independently reconstructed continuous wakes still agree:
maximum CDi difference `8.89e-16`, efficiency difference `2.78e-15`, and
circulation-lift difference `4.45e-16`. The entire 78-state wake replay takes
**3.62 seconds after imports**, serially with one computational thread.

A separate verifier rechecks all 140 native scalar entries and 280 original/
diagnostic pass decisions with decimal arithmetic, every exact self-energy
term, all 12 rejection statuses and all four excluded controls. The largest
relative self-energy discrepancy is `6.47e-16`. The first replay completed
the calculations but failed while serializing a NumPy boolean; that attempt
is preserved and the serialization fix changes no numerical calculation.

All 42 registered status rows remain unchanged. SA-10 remains **1,256/2,268**,
and the full project remains incomplete. Future work must address the
remaining circulation/junction-flow discrepancies, unsupported diagnostic
geometry and pending browser integration; this optional reference does not
replace those requirements. No browser, build or background numerical job
was launched or left running by this replay.

[Plan](../../artifacts/isae/fourier-wake-nonparallel-20261101/plan.json),
[replay](../../artifacts/isae/fourier-wake-nonparallel-20261101/replay.json),
[independent verification](../../artifacts/isae/fourier-wake-nonparallel-20261101/verification.json),
[tests](../../artifacts/isae/fourier-wake-nonparallel-20261101/tests.log),
[receipt](../../artifacts/isae/fourier-wake-nonparallel-20261101/receipt.json).
