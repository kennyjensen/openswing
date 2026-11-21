# ST-4 gravity and documented-term diagnostic

2026-11-04. Neither removing gravity nor directing it toward the wing tip
resolves the native ST-4 mismatch. Both change the sensitive roots substantially,
but neither reproduces both the oscillating pair and slow real branch.
No production equation, original input, operating default or acceptance gate changed.

| Declared axial gravity (m/s²) | Lowest pair at 120.5 m/s (1/s) | Frequency error | Slow root at 139.5 m/s (1/s) | Real-root error |
|---|---|---:|---:|---:|
| Archived ASWING; gravity orientation unauthenticated | -25.040334 + 3.363233i | — | -0.088874 | — |
| Current axial gravity -9.81 | -25.105116 + 1.917948i | 42.97% | +0.034861 | 139.22% |
| Zero gravity | -25.122058 + 4.563757i | 35.70% | -0.242100 | 172.41% |
| Toward-tip gravity +9.81 | -25.139059 + 6.162800i | 83.24% | -0.520912 | 486.12% |

Removing gravity restores a negative slow root at 139.5, but its absolute
error grows from 0.123735 to 0.153226 1/s. At 120.5 its frequency error falls
from 42.97% to 35.70%, while its real-component error grows from 0.259% to
0.326%. Toward-tip gravity increases both discrepancies further. A sign match
or a smaller single error is not validation. No intermediate gravity value
is fitted or adopted, and arbitrary off-axis attitudes are not tested here.

These are four new independent-reference calculations, with 256 requested
cosine aerodynamic and 128 uniform structural intervals; the mandatory weight
station is retained. The -9.81 baselines reuse the identical resolutions from
the [speed sweep](isae-st4-speed-sweep-20261104.md). They are not the finer
reference/public results in the [critical-region study](isae-st4-critical-refinement-20261104.md).
The new gravity alternatives have no separate mesh-convergence claim. This
distinction explains the baseline 42.97% here versus the latest OpenSwing
N160 error of 43.10%.

The same 16-mode full descriptor calculation is used, with all degrees of
freedom retained. Independently reassembling each physical system verifies
**64/64 full eigenvector equations**, with maximum relative action residual
**1.46e-15** against 1e-8. The minimum integrated
mechanical shape MAC against the baseline is **0.999853961**.
This supports tracking the same reference branches; native mode identities
remain qualified because archived eigenvectors are unavailable. All jobs
were serial, one BLAS thread, capped at 90 seconds and 512 MiB; the four
calculations took 7.85–12.37 seconds each, including imports and reassembly.

The targeted documentation audit found no new mismatch in the retained
quarter-chord steady/rate lift (unsteady Eqs. 33–36), midchord apparent mass
and pitch-rate loads (43–44), or local circulation lag b=2/pi (48–49).
The input manual's separate local-Mach correction applies to section Cm;
Cm is zero here. It also explicitly says wake-core radius has no effect for
a single surface. Neither term supplies an omitted correction for this pilot.

The original driver sets speed, anchored constraints and modal operations,
but not the initial gravity orientation, PG Mach or mesh distribution.
The experimental hanging installation supports examining toward-tip gravity,
but does not establish the archived native startup. The manual review does
not recover this particular run's initial node distribution.

All registered family scores and all broad Partial requirements remain
unchanged. ST-4 still has its 0/3,749 registered vacuum baseline, the latest
conditional airflow failures, and incomplete production mesh checks (24/26).
These diagnostics narrow two candidate explanations; they do not prove the
archive wrong or validate the complete model. The delivered Python/WASM
application and its previously verified packages are unchanged.

[Portable results and source audit](isae-st4-gravity-diagnostic-20261104.json).
Raw complete vectors, timings and source pins remain in
`artifacts/isae/st4-gravity-diagnostic-20261104/`.
