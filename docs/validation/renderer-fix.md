# Renderer redraw scheduling and multisampling

The integrated WebGL viewer now draws when geometry, camera, size or visibility
changes, and continues drawing while orbit damping moves the camera. Time, mode
and frequency playback already update the viewer for each changed geometry.
Context loss cancels pending draws; restoration redraws the latest scene.
Multisample antialiasing is disabled. The existing device-pixel-ratio cap of two
is unchanged; diagonal edges are visibly less smooth.

This follows the five preserved [diagnostic attempts](renderer-diagnostics.md).
Stopping idle draws alone did not resolve their GPU-memory growth during orbit
damping. Two further bounded fixtures distinguish the multisampling change from
the redraw scheduler:

| Fixture | Result | Maximum observed GPU RSS |
| --- | --- | ---: |
| Original continuous renderer, only antialiasing disabled | Passed; final sample at frame 877, camera/geometry/grid/mobile checks, actual context reports antialias false | 203,780 KiB |
| On-demand renderer with antialiasing disabled | All eleven interaction checks passed; 24 geometry updates, damping and idle, zoom, ground/grid, mobile, synthetic loss/update/restore, clear/repopulate | 195,388 KiB |

Both retained the original 100-second wall limit, 1,048,576 KiB GPU-memory
ceiling and 2,097,152 KiB host-available-memory floor. The interaction runner was
byte-identical to its earlier failed version. It does not independently read
context attributes; that readback belongs to the separate continuous-renderer
fixture. Neither fixture loads the numerical runtime or solves an aircraft.

The production file matches the tested uninstrumented candidate exactly, SHA256
`c3cd526d20be4e9c6ffe3bbaf9afc3af86079177c2e6f8d07865d769790c78a3`.
Its instrumented counterpart differs only by the retained read-only probe
assignment. All twelve interaction captures were inspected, including the
expected edge-on views of the thin vertical fixture. The production build
completed successfully. The subsequent complete unloaded-wing application
replay also passes and is [recorded separately](durrant-unloaded-browser-repaired.json).
Its two selected roots match native within 1.933e-12 per second; exports and
desktop/mobile WebGL checks pass under the original assertions and deadlines.
The fixture archive retains its creation-time note that this replay was pending;
the later application evidence is a separate artifact.

These results support the change on the prescribed Chromium/Mesa/Vulkan stack.
They do not identify an underlying driver defect, prove the cause of prior
process disappearance, or establish long-duration playback and general
hardware/browser coverage. Synthetic context restoration is distinct from
recovery after uncontrolled resource exhaustion. Numerical modules are unchanged.

The [summary](renderer-fix.json) and [evidence archive](renderer-fix-records.zip)
retain both new fixtures, source versions, captures, resource observations,
build output and integration review. The earlier diagnostic archive is unchanged.
Extract `verify_archive.py` and run:

```sh
python3 verify_archive.py renderer-fix-records.zip
```

The verifier audits bytes, source pins and retained terminal outcomes; it does
not rerun the browser or claim completion of broader graphics validation.
