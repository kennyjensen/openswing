# Unloaded browser evidence closeout

The unloaded browser workflow remains incomplete. The corrected-kernel attempt failed the desktop WebGL context-health assertion. Its single instrumented follow-up reached the numerical/export assertions and captured a healthy desktop viewport, but disappeared without a terminal result, mode-pane capture, mobile checks or postflight audit. No browser was restarted and no production code was changed during this closeout.

The follow-up recorded severe memory pressure: the final GPU-process resident set was 4,603,380 KiB, host `MemAvailable` was zero and `SwapFree` was 8 KiB. Its recorded process identities are now absent in the same boot. No context-loss or page-crash event was logged; the last desktop context gate was healthy. Cgroup memory events were unreadable. These observations do not prove an OOM kill, explain the first context loss, or establish a renderer defect or repair.

Both corrected-kernel attempts completed the two selected low-mode root/shape checks and exported all requested physical conditions. The largest native/browser root-component difference was 1.9326762412674725e-12 per second. The instrumented follow-up also completed the selected-mode plot-label/trace checks and eigenvalue/output CSV assertions. Empty request/error arrays are retained only through its last checkpoint: the final offline/error assertions were not reached. The configured 600-second test, 240-second solve and 180-second runtime deadlines were unchanged; no terminal test deadline outcome is recoverable.

The only follow-up image is `attempts/current_diagnostic_incomplete/run-01/artifacts/unloaded-wing25-desktop-webgl.png`. Visual review shows a segmented green wing, grid and axes within the desktop canvas. There is no desktop mode-pane or mobile screenshot. This does not establish completion of the browser workflow, total-spectrum classification, loaded-wing flutter agreement or experimental validation.

The [summary](durrant-unloaded-browser-closeout.json) records exact completion boundaries and resource observations. `attempts/` preserves every original fixture/record file without changing stale running states. The original historical incomplete archive is retained byte-for-byte under `history/`. `source-map.json` maps every relative preparation pin to deduplicated bytes in `objects/`; these include the 58-module kernels, packaged UI/runtime, input data, test fixture and wrapper. The old historical `aero.py` was recovered from a preserved source snapshot by its exact preflight hash because the original historical dist symlink now resolves to the corrected kernel. This recovery does not create a historical postflight audit.

Host Chromium and the Mesa configuration remain externally pinned dependencies and are not bundled. Existing absolute paths inside original records are provenance, not a portable browser launch recipe. The [archive](durrant-unloaded-browser-records.zip) is portable for offline evidence verification. Extract `verify_archive.py` from it, then run:

```sh
python3 verify_archive.py durrant-unloaded-browser-records.zip
```

The command checks archive membership, every byte digest, fixture/preflight source maps, original failure terminal records and incomplete follow-up evidence. It does not rerun numerical analyses or launch a browser. To reconstruct an archived relative fixture file, use `source-map.json` to copy the indicated object bytes to that relative path in a separate directory. A fresh execution would require separately provisioning and verifying the recorded host/browser dependencies and choosing a new output directory; none was attempted here.
