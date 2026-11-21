# UA-2: independently assembled harmonic matrix check

Updated 2026-11-03. **30/30 frequency checks pass** on the current source:
all 15 archived frequency coordinates on both 20- and 40-strip meshes.
Four additional high-frequency diagnostics pass separately. This is equation
verification for the reconstructed AR10 wing, not recovered ASWING output.
The **222 native comparison slots remain unverified**.

The independently integrated straight-wing horseshoes supply C. For unit chord,
zero incidence and small prescribed heave, the published lag and load equations
reduce to

`(C + 2 i omega/(pi V) I) Gamma = -w`,

`CL_cir = 2/(V b) (1 + i omega/V) sum(widths * Gamma)`,

`CL_added = -pi a/(2 V^2)`.

The [independent derivation](isae-straight-wing-heave-reference.md) supplies the
vortex integrals; production supplies a separate central differentiation of
its actual residual and load code. No production matrices are used to build
the reference. Each production matrix is reused across all frequencies.
Both the total complex lift and the circulation contribution after subtracting
apparent mass are compared. Displacement phasor is 0.5 chord; the response is
a small-signal transfer, not a finite-amplitude time-history result.

The maximum scaled complex difference is
**5.455243e-11**, below the predeclared **1e-8** limit.
Scaling is max(1, magnitude of the corresponding independent complex lift).
Both meshes pass production residual and zero-state checks. The mesh change
is 0.051008% on the same max(1, magnitude)
scale; it is a reported diagnostic, without a newly imposed mesh pass gate.

The finite-span circulation gain relative to the two-dimensional equation is
frequency dependent and complex:

| Reduced frequency k | Gain magnitude, 40 strips | Phase |
|---:|---:|---:|
| 0 | 0.76656999 | 0.000000° |
| 0.95 | 0.95380689 | 4.595686° |
| 10 | 0.99586500 | 0.785104° |
| 100 | 0.99970883 | 0.118648° |

At k=0 the gain is the limiting steady unit-velocity response; the prescribed
heave load itself is zero. k=10 and 100 are asymptotic diagnostics outside the
archived range 0–0.95. They do not add archived comparison targets. These
results are consistent with finite-span effects entering through the real
spatial matrix while the local lag dominates at high frequency. They do not
justify applying the archived MATLAB factors 0.85/0.90 to production, and
do not prove what an unavailable native ASWING model would produce.

The prior [inclined periodic study](isae-ua2-incidence-periodic-n40-20261101.md)
and [browser verification](isae-ua2-incidence-periodic-browser-20261101.md) retain
their original source hashes and time/mesh evidence. This new check closes a
current-source frequency-operator question. It does not rerun those histories,
establish arbitrary-geometry accuracy or validate three-dimensional stall.
The next milestone is to assess the current UA-2 time/checkpoint evidence and
state its remaining limits before moving to **ST-1 through ST-6**, as requested.
Separate interface/storage work does not delay that sequence.

Both mesh jobs ran serially, one BLAS thread each, under a 45-second process
cap. No production equations, source modules or accuracy limits changed.
The frozen plan, both numerical results and combined checks are retained in
[the evidence directory](../../artifacts/isae/ua2-harmonic-matrix-20261103).
[Machine summary](isae-ua2-harmonic-matrix-20261103.json). The complete project remains unfinished.
