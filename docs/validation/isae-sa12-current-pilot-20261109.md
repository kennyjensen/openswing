# SA-12 current-source baseline

Observed 2026-11-08/09 UTC. Focus moved from SA-11 to SA-12 at the user's
request. No evidence-backed quick SA-11 fix was established; its primary
21/48 count is retained. No further SA-11 solver calls are part of this update.

Six fresh SA-12 states are numerically valid. **16/18 CL, CD and CDi checks
pass at 5%.** Including the six unchanged tiny-Cm gates, the pilot is
**16/24**. This is a subset of the historical 4,080 comparisons, not an
additional scope or a full-family validation. The historical 3% count remains
2,324/4,080; it has not been relabeled as a fresh 5% result.

| Original model | Height / chord | Alpha | CL error | CD error | CDi error | Passing CL/CD/CDi |
|---|---:|---:|---:|---:|---:|---:|
| Slotted-flap equivalent | 0.5 | 0° | −0.286% | −0.475% | −0.186% | 3/3 |
| Slotted-flap equivalent | 2 | 0° | +0.122% | −0.027% | −0.016% | 3/3 |
| Slotted-flap equivalent | 3,937 (nominal infinity) | 0° | +0.134% | +0.011% | +0.019% | 3/3 |
| No flap | 0.5 | 8° | −3.566% | **+33.719%** | **−6.377%** | 1/3 |
| No flap | 2 | 8° | −0.959% | +2.306% | −1.866% | 3/3 |
| No flap | 3,937 (nominal infinity) | 8° | +0.110% | −0.005% | −0.008% | 3/3 |

Errors are signed relative to the raw archived ASWING coefficient. All six
computed Cm values are exactly zero. Archived values range in magnitude from
about 1.16e−29 to 2.95e−13; their printed absolute gates remain failures.
These models have a straight quarter-chord axis and zero section Cm. Those
tiny residual comparisons are retained but distinguished from the lift/drag
discrepancies.

## Setup and source evidence

The [authoritative index](aswing-authoritative-references.md), checksummed
catalog, and [original SA-12 source audit](isae-sa12-sources.md) govern this
comparison. Jan Part I, **p.38 and Figure 23, p.40**, describes the rectangular
NACA 23012 wing, fixed section constants for the slotted-flap equivalent,
quarter-chord ground height and ground-effect limitations. Drela's steady
description, **§4.5, Eqs.165–175**, defines the image geometry and signs.

The pilot uses the unchanged original `.asw` files and raw `.txt` values,
speed 35.76 m/s, density 1.2256 kg/m³, solid ground, heights 0.127/0.508/1000 m,
Mach correction zero, current influences, stall strength 40 and width 0.05.
The existing adapter reconstructs 100 cosine intervals from the numeric
NODE/I 100 request. Historical node locations and circulation truncation
remain unknown. Each point is well below its section stall transition; the
smallest margin is 11.04 transition widths.

**Euler pitch equals alpha is a declared reconstruction**, making wind parallel
to the ground board. The shell scripts prescribe alpha, height and ground
normal but do not archive Euler attitude. Their K/F toggle also depends on an
unarchived startup state. Neither choice is claimed to recover the historical
state exactly. The nominal infinity file still includes images at 1000 m.

Jan describes disabling a divergent post-stall drag contribution close to the
ground, but the archived scripts do not record that toggle. The original MATLAB
plot uses **0.01 + CDi** for the close-ground no-flap drag curve. That display
transformation is distinct from raw CD and has not been substituted into the
acceptance tests. Experimental data are not the acceptance target.

## Independent verification and remaining lead

All six saved states were replayed using an independent transcription of AVL's
segment/ray velocity law, zero core, and the exact 1/(4π) constant. Ground
images were reflected analytically, including every self image. The checker
reconstructs section circulation normalization, the nonlinear tangency equation,
near-field forces and moment normalization. A separate infinite-line wake
calculation reproduces Trefftz CDi. Errors are at roundoff: maximum relative
velocity discrepancy 2.70e−15 and maximum coefficient discrepancy 6.67e−16.
An exact-decimal check independently confirms all 24 acceptance decisions.
This verifies the implemented calculation for the disclosed setup; it does
not establish the missing historical setup or mesh convergence.

At no-flap h/c=0.5 and alpha=8°:

| Quantity | OpenSwing | Archived ASWING |
|---|---:|---:|
| Total CD | 0.022496813 | 0.016824000 |
| Trefftz CDi | 0.013478926 | 0.014397100 |
| CD − CDi | 0.009017886 | 0.002426900 |

OpenSwing's near-field circulation drag equals its Trefftz value for this
planar, board-parallel setup. Its remaining drag is friction; direct stall drag
is only 2.36e−11. The archived CD−CDi difference cannot automatically be called
profile drag: near-field and Trefftz contributions may differ with ground/wake
pose. The next investigation is therefore the **close-ground pose and drag
conventions**, before changing the solver. A previous zero-attitude diagnostic
reduced the raw-CD difference without eliminating it and did not yield a valid
parallel-ground Trefftz comparison; it is not substituted here.

## Reproduction and accounting

The [driver](../../scripts/verify_sa12_current_pilot.py) runs one unchanged
adapter call per invocation. The [saved-state checker](../../scripts/check_sa12_current_pilot.py)
runs one case per invocation with no physical solve. Both enforce one BLAS
thread, a 512 MiB address-space limit, 15 CPU seconds and a 25-second wall
alarm. The six solver calls took 2.21–3.71 seconds each, with peak RSS below
191 MiB. No production solver or reference inputs changed.

[Complete results, comparisons and 194 verified source/artifact hashes](../../artifacts/isae/sa12-current-pilot-20261108/analysis.json)
are retained alongside the original plan, full saved fields and per-state
verification receipts. The directory was created on November 8; observations
carry their actual UTC timestamps across midnight.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python scripts/check_sa12_current_pilot.py \
  --output artifacts/isae/sa12-current-pilot-20261108 --index 0
```

Receipts use exclusive creation to preserve evidence; a fresh rerun needs a
new output directory prepared by the driver. The pilot adds no primary passes,
removes no reference values and makes no full-polar claim.
