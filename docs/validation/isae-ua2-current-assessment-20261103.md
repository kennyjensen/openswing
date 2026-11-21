# UA-2 current-kernel assessment, 2026-11-03

The attached-flow implementation has sufficient independent equation, time/mesh
refinement and runtime evidence to begin the requested ST-1 through ST-6 tests.
This is an engineering priority decision, **not full UA-2/native ASWING validation**.

| Current selected check | Result |
|---|---|
| Python time intervals, 20/40 strips | 6/8 pass; all eight computed |
| Built browser worker intervals, 20/40 strips | 6/8 pass; all eight computed |
| Fresh startup and owned continuation | 4/4 pass in each runtime |
| Aerodynamic waveform checks | 8/8 pass in each runtime |
| Browser/Python comparison | 8/8 pass; maximum scaled difference 1.247e-08, limit 2e-8 |
| Accepted steps | 128 in each runtime, zero rejected steps |
| Focused precision, static and tangent tests | 27 pass |
| Independent harmonic matrix checks | 30/30 pass; retained source audit linked below |
| Native ASWING comparison | 222 slots unverified |

The source displacement formulation preserves Drela's beam compatibility
expression while avoiding subtraction of rounded absolute positions. The original
40-strip startup local acceleration was 3.697454e-4 m/s²; it is now 5.367804e-14 in
Python and 2.385825e-14 in the browser. No physical limit was changed.

Both runtimes still fail the two 40-strip **legacy checkpoint** intervals at
2.866640e-8 and 2.886132e-8 m/s², versus the unchanged 2e-8 local-motion limit.
The zero reference makes percentage error undefined. The first legacy failure
also occurs with the frozen pre-correction kernel (2.463153e-8). Old checkpoint
history was not projected, repaired or reinitialized to produce a pass.
All current aerodynamic errors pass: maximum lift/circulation/rate waveform
errors are approximately 0.002225% / 0.005265% / 0.002994% of reference scales.

The initial 20-strip late replay timed out at 45 seconds. Its failed attempt is
retained; two eight-step requests completed each pending 16-step interval on the
same grid. The first browser warmup failed because the test HTTP server omitted
the .mjs MIME type; its plan, harness and failure are preserved. The corrected
server required no production runtime change. The assessment import-path error
was also corrected before generating an assessment; it caused no solver rerun.

All 136 source modules match public/kernel and dist/kernel. Download refresh is
tracked separately. The current browser checks cover selected intervals, not a
new complete eight-cycle run. Existing longer trajectories/refinement evidence
retain their original source hashes. The harmonic matrix audit is
[reported separately](isae-ua2-harmonic-matrix-20261103.md).

Remaining UA-2 work: legacy-history precision, broader inclined/stalled periodic
conditions and provenance-bound native ASWING comparisons. Unavailable native
inputs do not become passes. The next numerical priority is ST-1 through ST-6.

Machine summary: [current assessment](isae-ua2-current-assessment-20261103.json).
Raw, hash-bound requests/results and retained attempts are under
`artifacts/isae/ua2-displacement-time-20261103/`.
