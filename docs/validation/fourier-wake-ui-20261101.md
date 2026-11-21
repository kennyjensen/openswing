# Browser controls for the continuous Fourier wake check

2026-11-01. The browser source now connects the verified continuous Fourier
wake diagnostic to rigid steady analyses and rigid angle sweeps. This is an
optional comparison of the selected circulation's wake integral. It does
not alter the main force, drag, efficiency, residual or circulation result.

## Use and supported scope

In **Settings → Circulation representation**, select positive Fourier mode
counts for every lifting beam and enable **Check continuous Fourier wake**.
Run rigid steady aerodynamics, or run a rigid steady angle sequence. The
coefficient note shows reference CDi, its signed percentage difference from
the discrete value, and reference span efficiency. The Solver report includes
the complete integral, energy matrix and quadrature metadata. JSON exports
retain the result under `trefftz.continuous_fourier`.

The diagnostic supports straight projected traces in free space, including
angled tip sails and intersecting or joined traces. Pointwise/mixed bases,
curved projected traces, ground images or unresolved integration return an
explicit unavailable reason. A missing or undefined reference value is not
displayed as zero. A zero discrete CDi uses an absolute difference instead
of division by zero. A missing diagnostic from an older loaded kernel gives
a reload instruction.

The control is shown only for rigid steady analysis. Switching analysis modes
retains the saved preference but does not request the unsupported check.
Mounted, time, modal and frequency requests explicitly asking for it are
rejected at the JSON boundary. This is a current interface limit; the Python
prescribed-mesh API retains its existing supported inputs. No coupled or
dynamic implementation is claimed here.

Existing case files migrate the absent checkbox to `false` in their editable
configuration; archived bytes are retained. New cases save the explicit
choice. The option is a reporting request, not a `FlightCondition` field.

Example JSON request, with ASW source supplied as a string:

```json
{
  "action": "solve",
  "mode": "rigid",
  "source": "<ASW source text>",
  "panels": 48,
  "condition": {"speed": 30, "alpha": 5, "circulation_modes": {"1": 12}},
  "fourier_wake_diagnostic": true
}
```

The same top-level option is retained by `action: "operating_points"` for
rigid stacks, including previous-point initialization.

## Verification and limits

**12 native JSON-boundary tests pass in 5.20 seconds.** They verify equality
of the entire ordinary result with the diagnostic removed, finite reference
serialization, explicit pointwise unavailability, two sequential angle
points with retained diagnostics, strict boolean validation, and rejection
of unsupported analysis requests before parsing or solving.

**13 JavaScript checks pass in 1.06 seconds**, including request gating,
signed comparison display, zero/undefined/tiny reference handling, and saved
configuration migration. The latter also runs the existing moving-vacuum
configuration checks so the new field cannot silently change their saved
identity. `node --check web/main.js` passes. All checks ran serially; numerical
work used one computational thread.

No browser, Vite server, Playwright run or distribution build was launched,
following the UserLAnd disconnect investigation. Consequently rendered UI and
WASM execution of this new control remain **unverified**. `public/kernel`,
`dist` and downloadable bundles have not been refreshed. These source/native
checks are not browser validation or a complete release.

The [preceding 78-state wake replay](fourier-wake-nonparallel-20261101.md)
continues to supply the SA-7/SA-10 mathematical evidence. No new ISAE aircraft
solve or registered comparison is included here. All 42 status-table rows
remain unchanged, including SA-10 at **1,256/2,268**. The remaining SA-6–SA-10
discrepancies and the full ASWING feature goal are unfinished.

[Plan](../../artifacts/isae/fourier-wake-ui-20261101/plan.json),
[native tests](../../artifacts/isae/fourier-wake-ui-20261101/python-tests.log),
[JavaScript tests](../../artifacts/isae/fourier-wake-ui-20261101/js-tests.log),
[receipt](../../artifacts/isae/fourier-wake-ui-20261101/receipt.json).
