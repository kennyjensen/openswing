# ST-4 dimensional airflow with zero reference area

The unchanged original `Weight7a/7a_b17.asw` now completes a flowing-air modal
calculation. Previously it failed before calculation because its `Sref = 0`
prevented aerodynamic coefficient normalization. The Reference area is an
output scale, not the area used to calculate section loads: Drela's
[Reference-block documentation](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
specifies it for overall coefficients. The literal model is retained without
inserting a replacement area.

Dimensional steady loads, circulation, loaded equilibria and modes can now use
zero Sref. Area-normalized coefficients are `null`, with a normalization reason;
the workbench displays unavailable coefficients while retaining dimensional
results. Span efficiency remains defined through
`(L_i² + Y_i²)/(pi Bref² q D_i)`, in which Sref cancels. Exactly unloaded wakes
retain the existing zero-efficiency reporting convention. Positive-area force
and coefficient formulas are retained. Coefficient-derivative actions still
require positive Sref; the optional continuous-Fourier coefficient diagnostic
reports unavailable rather than inventing an area.

The initial rejected run is preserved. Its identical 16-interval request now
finishes in **53.95 s**, peak RSS **111,660 KiB**, under the same 180 s / 512 MiB
limits with one BLAS thread. The fresh base residual is **2.29e-16**. Independent
multiplication of the saved full A/M arrays verifies all **32 left/right
residuals**, maximum backward error **1.76e-16**. All 16 returned roots and their
vectors remain in the result, including real and negative-frequency roots.

The pilot uses the source beam/airflow equations and full-pencil Arnoldi, with
16 roots near `0 + 300i`. Source settings establish the first commanded indicated
speed 120, sideslip zero, anchored defaults and all-point eigenvalue calculation.
Declared assumptions remain: no startup sidecar, sea-level density 1.0771417304,
zero incidence/attitude/rates, Earth gravity 9.81 toward −z, PG Mach zero, enabled
aerodynamic lag, live influences, uniform 16 intervals plus attachment stations,
and fixed perturbation frame. Density equals the file's sea-level density, so
true and indicated speed coincide under this declared setup. These assumptions
are not authenticated historical settings.

The first six archived roots are compared using an injective complex-proximity
assignment. This is a diagnostic correspondence, not verified mode identity.

| Archived ordinal | ASWING (real, imaginary), /s | OpenSwing (real, imaginary), /s | Real-component error | Imaginary-component error |
|---|---|---|---:|---:|
| 1 | -24.82247, 5.876936 | -23.07139, 13.10255 | 7.054% | 122.949% |
| 2 | -4.444598, 101.9036 | -4.360334, 102.0236 | 1.896% | 0.118% |
| 3 | -3.494512, 187.8581 | -3.583848, 190.5159 | 2.556% | 1.415% |
| 4 | -8.33652, 355.7367 | -8.461471, 357.521 | 1.499% | 0.502% |
| 5 | -394.8427, 0 | -406.415, -9.179009e-13 | 2.931% | 9.2e-13 /s absolute |
| 6 | -8.274898, 542.5079 | -8.200371, 550.2581 | 0.901% | 1.429% |

Only **1/12 scalar components** matches printed precision: the nearly-zero
imaginary component of the real root. No complete root matches. Four higher
oscillatory frequencies differ by 0.118–1.429%; the low-frequency pair differs
by 7.226 /s (122.95%). Damping differences span 0.901–7.054%. This coarse pilot
is not mesh-converged and does not change the registered ST-4 score.
The next numerical test is the same point on a finer mesh; no settings fitting
or tolerance change is justified by this result.

The script/source audit covers **six drivers and 1,674 archived complex roots**.
All 18 model/driver/output hashes match the pinned ISAE manifest. Five exports
contain exactly 300 rows; several stop before the end of their requested sweep.
The 7a script requests 41 points (120–140), 7c and the root-level W0M script
51 (95–120), 7d 21 (130–140), 7e 41 (110–130), and 7f 41 (90–110), all in
0.5 speed increments. These are requested sequences, not proof of a complete
export or a recovered startup stack. W0M's separate missing-End issue remains.

Native verification covers zero-area dimensional load parity, exact source
modal-pencil invariance under a reporting-area change, nonzero sideforce,
unavailable coefficient outputs, original positive-area Trefftz controls and
coefficient-derivative guards: **42 tests pass across the initial run and the
two corrected rechecks**. The initial run's two failures are retained: a test
used the wrong system-state attribute, and a new over-strict low-level finite
check changed an existing invalid-reference diagnostic. Both were corrected;
all original physical tolerances remain unchanged.

The actual offline browser now passes rigid dimensional-load output, unavailable
coefficient display, the same 16-root modal calculation and byte-exact saved
solution/project reopening. Its modal solve takes **45.98 s**; maximum
scaled complex-pole difference from CPython is **1.96e-13**
against the unchanged 2e-7 parity gate. No page errors occurred. GPU rendering
was disabled for this bounded test. The initial harness launch failure (missing
default browser path) is retained; the recheck uses the already-installed
Chromium executable. This check used the served development workbench and the
same current kernel; release packaging is a separate build check.

[Browser evidence](../../artifacts/isae/st4-airflow-zero-area-20261103/browser.json)
and [browser test log](../../artifacts/isae/zero-reference-airflow-20261103/browser-recheck.log).
The full ASWING goal and ST-4 family validation remain open.

Evidence: [original rejection](../../artifacts/isae/st4-airflow-pilot-20261103/execution.json),
[source audit](../../artifacts/isae/st4-airflow-pilot-20261103/source-audit.json),
[unchanged pilot request](../../artifacts/isae/st4-airflow-zero-area-20261103/request.json),
[conditional reference assessment](../../artifacts/isae/st4-airflow-zero-area-20261103/assessment.json),
[initial tests](../../artifacts/isae/zero-reference-airflow-20261103/tests.log),
and [corrected rechecks](../../artifacts/isae/zero-reference-airflow-20261103/recheck.log).
