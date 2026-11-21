# AE-4 wall-root modal refinement

A fine cosine mesh exposed a differentiation failure: the fixed fourth-order
coordinate stencil moved a mounted root outside the existing regular geometry
neighborhood. The stencil now reduces only the affected root-coordinate steps
using the root's translation scale and maximum attachment lever arm. Its
largest displacement is at most half the unchanged neighborhood radius.
Physical clearance, all constraint rows and complete descriptor matrices remain
unchanged. Steps below the existing modal minimum of 1e-7 are rejected.

The original declared IAS40 / native index41 comparison now runs on both
41- and 81-element meshes. All 13 physical/source checks pass for each mesh,
including full left/right pencil residuals and mass normalization. Each mesh
passes 6/6 reference components at the user-approved 5% allowance. These are
six distinct native cells repeated across two meshes, with the same conditional
historical setup as the [first anchor](isae-ae4-wall-modes-20261105.md).

| Component | Maximum native error, 41 elements | Maximum native error, 81 elements |
|---|---:|---:|
| Frequency (imaginary part) | 0.0616% | 0.1499% |
| Damping (real part) | 0.5044% | 0.6267% |

The largest 41→81 change is about 0.212% in frequency and 0.122% in damping.
Agreement does not improve monotonically with refinement; no node count is
selected by best fit. Further spatial study, historical settings, the full
speed/incidence sweep and flutter crossings remain open.

The clustered-strip regression compares the complete sparse pencil against an
independent smaller-step dense stencil, checks strict physical clearance after
leaving the derivative context, preserves nonwall scales, and exercises the
unresolved-step rejection. Four new step tests and ten existing moving-wall
tests pass. The initial too-small test fixture failed during static setup; its
floor-rejection test now isolates the owned derivative neighborhood explicitly.
The original failure is retained.

The first fine request reaches a memory limit while exporting dense A/M lists
under a 512 MiB process address cap. The identical numerical request completes
under 768 MiB, with streamed JSON writing. No numerical tolerance, requested
mode or exported matrix was removed. This is a diagnostic export resource cost,
not evidence of a solver stall. Recorded solve timings are platform-specific,
not a controlled performance comparison.

[Machine evidence](isae-ae4-refinement-20261105.json) and retained requests/results
under `artifacts/isae/ae4-refinement-20261105/` contain the full source pins.
The browser verification is recorded separately in that folder.

The exact 81-element request also passes the actual offline WASM worker: all
ten gates and 4,869,334 numeric comparisons pass, including the complete base,
A/M matrices, selected roots and independent full left/right residuals. The
worker solve including matrix export took 112.22 s in this run (171.69 s total).
This verifies the worker; UI selection and a full flutter sweep remain separate.
The combined focused and regression evidence contains 336 distinct passing
Python tests. A broader accounting-test attempt hit its 90-second cap after
293 passes; the remaining acceptance-specific tests were checked separately.
This is not a claim that the full repository test suite ran.
