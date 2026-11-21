# UA-1 repeated-stall browser study: 1/4 cycles audited

This is the historical first-cycle checkpoint. The later [browser follow-up](isae-ua-time-position-20261102.md) failed its strict runtime-agreement check. At this checkpoint, the study was **in progress**. Its first **640 physical steps / 641 unique states** pass the cold-history checks. This is a prefix of the full planned run, not a completed periodic comparison or native ASWING validation.

The actual built app worker starts from its own steady equilibrium. The setup is identical to the passing Python study: 9° mean incidence, k=0.94, peak-to-peak A/c=0.5, section limits ±1.5, stall leakage strength 40, smoothing width 0.05, and circulation lag enabled. The complete four-cycle forcing table is supplied before startup. All 136 loaded scientific modules match the retained Python source byte for byte.

Each serial request advances eight steps with a 45-second worker cap. The physical time grid remains 640 steps per cycle. Full snapshots and restart records are retained. The raw audits verify both BDF predecessors and coefficients across all **79 continuation boundaries**, with **zero rejected integration steps**.

| Quantity | Maximum cold-history error against independent equations |
|---|---:|
| Lift | 0.00868% |
| Circulation, worst strip | 0.00724% |
| Circulation rate, worst strip | 0.03068% |
| Pressure drag | 0.02780% |

All four waveform errors are below the unchanged 0.1% limit. Lift/circulation use peak departures from the independent pre-motion steady state; rate/pressure drag use their own reference peaks. Motion, normalized nonlinear residual and first-step rate also pass their existing limits.

Maximum scaled difference from the retained Python history is **9.423e-09**, below **2e-8**. The comparison covers fixed-axis lift, the complete force vector, fixed-speed pressure drag, every strip's circulation, circulation rate and section lift coefficient, and heave velocity, position and acceleration, at identical physical times. The scale is `max(1, abs(Python value))`.

The nine audit sensitivity tests pass. No production equation, solver tolerance, forcing sample, physical time step or acceptance limit changed. Worker requests took 2.75–6.62 seconds for this prefix; these timings include checkpoint restoration and transport and are not an uninterrupted solve benchmark.

**Remaining at this checkpoint:** 240 browser requests, their raw-history audits, and the full four-cycle periodic accuracy/settling checks. UA-2 stall, broader physical conditions, native reference provenance, and the full ASWING feature goal remain open. This result adds no completed scientific-case or browser-periodic pass count.

[Machine-readable prefix](isae-ua1-stall-periodic-browser-prefix-20261102.json). [Full-study plan](../../artifacts/isae/ua1-stall-periodic-browser-20261102/plan.json). [Retained evidence](../../artifacts/isae/ua1-stall-periodic-browser-20261102). [Completed Python comparison](isae-ua1-stall-periodic-20261102.md).
