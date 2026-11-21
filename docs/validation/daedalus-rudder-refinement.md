# Daedalus rudder response: retained 32-panel failure

The 32-requested-panel-per-beam attempt stopped during dynamic linearization. The source returned from its trim construction, but the moving-field derivative did not resolve under step refinement: `GeometryDerivativeUnresolved`, with reported scaled change `2.1e-6` against the unchanged `2e-8` accuracy criterion. **No 32-panel A/M/B matrices, yaw curve or 16→32 response comparison were produced.**

The saved failure-integrity audit passed 52/52 checks. This confirms the preserved failure, inputs, source, raw capture and process records; it does not turn the numerical failure into a pass. The one child exited with code 1 and was reaped after 621.94 s. It did not time out and was not retried.

The case used 197 nodes, 192 elements, 155 circulation unknowns and a prospective 3,719-variable descriptor. Speed remained 30 ft/s, PG Mach 0.1, with Earth-following gravity, ground effect off, a free-flight frame and the same seven steady/level trim targets. Only the seven solved 16-panel scalar trim coordinates supplied initial guesses; no old physical state was transplanted. The published ASWING rudder plot's operating point remains unidentified: 30 ft/s is a declared comparison setting, not an identified reference condition.

The source trim construction returned in 594.81 s. The raw post-trim state, layout, seven returned trim coordinates and progress are preserved. The capture records 6,797 source-owned network residual evaluations up to that point. Its residual field is null, and the independent fresh full dynamic residual check was never reached. Consequently this report does not claim a separately verified full residual or final rank at the returned 32-panel state.

| Work | Recorded result |
|---|---|
| Frequency-analysis construction / make-system call | One attempt each; make-system returned |
| Full dynamic linearization | One attempt; zero completed |
| F3 input stencil | Zero |
| Harmonic responses | Zero of the planned 203 |
| Extra fresh full dynamic residual check | Zero |
| Physical state transplants / retries | Zero |

The accuracy guard compares refined moving-field columns; its rounded aggregate error is not an identified bad receiver or exact state column. Saved progress bounds the failing batch to zero-based columns 736–751, without identifying which column failed. The source distinguishes an unavailable decomposition from an unresolved derivative and propagates this accuracy failure. The original guard, base/rank criteria and harmonic tolerances were not relaxed. A useful next diagnostic is to identify the failing column and field at the saved state before proposing a numerical change; no such follow-up was executed for this report.

Earlier 8/16-panel responses and failures remain unchanged. There is no new refinement curve, convergence estimate, stability verdict or matched-reference validation. No solver source, defaults, hosted bundle or validation-family classification changed. Peak recorded RSS was 395,532 KiB; elapsed time and memory are observations from this one failed attempt, not performance comparisons.

[Machine-readable report](daedalus-rudder-refinement.json) and [evidence archive](daedalus-rudder-refinement-20261024-evidence.zip). The focused archive retains the failed attempt, exact frozen inputs, raw post-trim capture, traceback, progress, source review, failure audit and lifecycles. Unexecuted success-report, plot and audit preparations are retained and clearly distinguished. Unchanged source and prior responses are resolved through hash-bound mesh, sweep and directional-check archives; primary PDFs are not redistributed. Reproduction requires the recorded historical paths or a reviewed remapping.
