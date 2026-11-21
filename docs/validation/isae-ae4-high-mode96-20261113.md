# AE-4: the 96 m/s damping discrepancy persists on refinement

The finer mesh does **not** recover the archived damping sign. At 96 m/s,
the higher-frequency pair has growth rate **+0.053766/s on cosine160**,
compared with **+0.023701/s on cosine80** and **−0.137936/s in ASWING**.
The registered 40/80 results reproduce, a different eigenvalue search returns
the same modes, and independent residual-action checks pass. These checks
have not identified an eigensolver or assembled-derivative error.

All **128 numerical checks in 13 serial stages** pass. These are diagnostic
checks, not new native-reference comparisons. **Primary AE-4 remains
357/1,200 at 5%**; no model parameter, equation, default or gate changed.
The assessment was observed at **2026-11-13T03:43:07.020013+00:00**.

![Higher-pair refinement at 96 m/s](../../artifacts/isae/ae4-high-mode96-20261113/higher-mode-refinement.png)

## Three-grid comparison

| Model | Actual intervals / nodes | Re(λ), 1/s | Im(λ), rad/s | Real-component error | Frequency error |
|---|---:|---:|---:|---:|---:|
| Archived ASWING | Unknown | −0.13793642 | 182.71029 | — | — |
| OpenSwing cosine40 | 41 /42 | −0.09596129 | 182.82262 | 30.431% | 0.0615% |
| OpenSwing cosine80 | 81 /82 | +0.02370068 | 182.44620 | 117.182% | 0.1445% |
| OpenSwing cosine160 | 161 /162 | +0.05376579 | 182.35221 | 138.979% | 0.1960% |

The required material station at `t=0.52` adds one interval to each nominal
grid. At all three resolutions, the higher pair's real component fails and
its frequency passes the native 5% comparison. Cosine160 is a diagnostic,
not a replacement for either registered mesh.

The real-component changes decrease from **0.119662/s** for 40→80 to
**0.030065/s** for 80→160, a factor of **3.980**. This is consistent with an
approximately second-order correction over these three grids, but does not
establish a converged continuum value. The remaining 80→160 real change is
**55.919%**, failing the unchanged 0.1% spatial gate. Its frequency change is
**0.05155%**, which passes that separate gate. No extrapolated root is used
as a reference comparison or a new vote.

The 160-grid absolute damping offset from ASWING is **+0.191702/s**. The small
native real component magnifies percentage error, but the growth/decay sign
disagreement is real and retained. The other selected oscillatory pair is
already unstable: its 160-grid real part is **+10.805313/s**. Thus the sign of
the higher pair alone is not a whole-wing stability criterion.

## Reproduction and equation checks

Each mesh runs a cold equilibrium, complete sparse A/M assembly and the
original four-mode search at shift `0+200i` in separate bounded workers.
All four roots, full left/right vectors, matrices, clamp checks and source
identities are retained; no state or matrix term is discarded.

The repeated cosine40/80 roots agree with the saved cold comparisons to
**1.28e−13 relative**. The critical real parts differ by at most
**3.14e−15/s**. The additional two-root search at `0+183i` recovers the higher
pair within **8.66e−14/s in its real component**. Each returned vector is
checked against its own closest original mode; the second positive-frequency
mode is retained and checked too. Full left/right pencil residuals across
all stages are at most **4.02e−15**, below the unchanged 1e−8 gate.

For each of the two registered meshes, centered residual differences along
the real and imaginary parts of the higher mode independently check A and M
at step sizes 1e−4, 1e−5 and 1e−6. The largest relative action error is
**7.44e−10**, below the 5e−5 gate. The independent circulation-lag coefficient
from Drela's unsteady Eq.49 agrees to **1.64e−16 relative**.

Computed mode shapes retain high overlap across meshes. Separate
translation/rotation correlations for 40→80 are **0.99999299 /0.99999386**;
for 80→160 they are **0.99999956 /0.99999961**. These use interpolation at
common physical jig-span coordinates with trapezoidal span weights. The
assessment also retains the combined six-coordinate correlation, with its
coordinate-scaling limitation disclosed. This supports correspondence of the
computed modes; native eigenvectors remain unavailable.

These checks validate the equations actually assembled and solved. They do
not independently prove all underlying force laws, section properties or
historical ASWING settings. The opposite-sign circulation-lag and
circulation-rate-load sensitivities retained in the assessment are diagnostic
contractions, not fitted coefficients or permission to change either term.

## Sources, accounting and next discriminator

The [authoritative index](aswing-authoritative-references.md) and checksummed
catalog, Jan Part IV §3.4 (printed p.15), Drela's steady/unsteady descriptions,
the original `Pazy_wing.asw`, `alpha_0.sh` and native modal export remain the
setup authority. The driver says `I 40`, but its exact native node positions,
count convention and startup settings remain unauthenticated. The documented
vertical unloaded Pazy configuration is retained. Original ASWING outputs
remain distinct from experiment and other models.

The prior [spacing study](isae-ae4-spacing-refinement-20261112.md) and
[circulation representation audit](isae-ae4-circulation-audit-20261112.md)
already found that tested alternative settings do not consistently resolve
the other sensitive native roots. This result gives no basis for choosing
a mesh or parameter by its agreement with a single archived value.

Next independently audit the **real-mass and structural-inertia actions**
on this Pazy state, including centroid offsets, sectional inertia, integration
and transfer to the beam nodes. The earlier
[apparent-fluid load audit](isae-ae4-apparent-load-audit-20261112.md) explicitly
used measured production real-inertia contributions when isolating its
aerodynamic loads; it was not an independent real-inertia validation.
Use the existing saved matrices and original inputs with bounded physical
probes. Retain the native setup ambiguity and the damping failure regardless
of whether that independent audit passes.

All 13 numerical children completed and were reaped, with maxima of
**7.72 CPU seconds, 8.86 wall seconds and 232.4 MiB RSS**. The limits stay at
one BLAS thread and **512 MiB address space /15 CPU seconds /25 wall seconds**.
The figure ran separately within those caps and was visually inspected.
No browser, build, WASM or background solver job ran. Production source hashes
remain unchanged.

The primary ledger remains **357 passes, 23 paired failures, 16 unmatched,
12 unknown initial values and 792 unrun**, totaling 1,200 components.
The primary failed-error range remains **5.498–117.182%**, median **9.017%**;
the 138.979% diagnostic above is not mixed into that registered statistic.
The overlapping 86/108 sample and separate 9,480-component historical archive
remain unchanged. AE-4 and the broader project remain incomplete.

- [Plan and source hashes](../../artifacts/isae/ae4-high-mode96-20261113/plan.json)
- [Assessment, stage receipts and comparisons](../../artifacts/isae/ae4-high-mode96-20261113/assessment.json)
- [Standalone SVG](../../artifacts/isae/ae4-high-mode96-20261113/higher-mode-refinement.svg)
- [Latest registered 96–99 m/s comparison](isae-ae4-96-99-20261113.md)
