# AE-4: independent elastic and structural balance audit

**The checked Pazy stiffness and balance derivatives agree with independently
transcribed Drela equations.** The analytic self-weight state reproduces the
saved equilibrium, and all **1,488 mechanical columns** of the two saved A
matrices pass. Fresh finite-perturbation actions also pass. No stiffness,
offset or structural-balance implementation error was identified in this
96 m/s state.

Two bounded serial jobs pass **1,584 numerical checks**. No production code,
physical input, default or acceptance gate changed. These diagnostics add
no native-reference votes: **AE-4 remains 357/1,200 at 5%**. The assessment
was observed at **2026-11-13T04:08:15.538043+00:00**.

## Independent equations and equilibrium

The [authoritative reference index](aswing-authoritative-references.md) and
checksummed source catalog were consulted. Drela's steady PDF **p.8,
Eqs.18–20**, and **pp.12–13, Eqs.48–56**, were visually inspected. These
define the offset moment, elastic compliance, endpoint-average compatibility
and conservative force/moment balance. Jan Part IV §3.4, p.15 and the
original Pazy model and driver remain the case setup authority.

The original section values are retained: **EIcc=4.4, EInn=3300,
EIcn=−0.12 N·m²**, **EA=9.6e6 N**, and coincident CG, elastic and tension
axis offsets **−0.005 m along the chord**. Shear stiffness is infinite.
Torsional stiffness is **GJ=6.5 N·m²** below `t=0.52` and **16.9 N·m²**
above it. The inserted material node means no interval crosses that jump;
the interval stiffnesses on each side are checked explicitly.

At zero incidence the wing is straight and compressed by its own weight.
With unloaded span coordinate `s`, span `L=0.55 m`, mass per length
`μ=0.6787 kg/m`, and `g=9.81 m/s²`, the independent solution is:

```
z(s) = s − μg/EA · (Ls − s²/2)
N(s_mid) = μ(L − s_mid) · gravity_vector
M(s_mid) = centroid_offset × N(s_mid)
```

The root reactions oppose the total weight and its offset moment. Because
the CG, tension and elastic axes coincide, the translated elastic moment
vanishes and the section frames stay untwisted. Tip shortening is
**1.0489892e−7 m**. The calculation accounts for the input's root parameter
`t=0.0001` corresponding to physical `z=0`.

The analytic positions differ from the saved states by at most
**3.18e−16 m** in vector norm. Internal-force and internal-moment differences
are at most **4.53e−15 N** and **5.11e−16 N·m**. These independent resultants
and the compressed geometry—not production-reported base loads—supply the
expected derivatives.

## Complete mechanical block

The expected block includes every node position/rotation, internal
force/moment and root reaction column. Rows cover structural compatibility,
nodal force/moment balance and root constraints. It contains the existing-load
terms from differentiating the rotated resultants, the force moment arm,
and the rotated centroid offset under gravity.

The bending/torsion inverse, offset maps and derivatives are explicit
transcriptions using the original constants. Production Section,
stiffness-inverse, Euler-chart and mechanical-tangent helpers are not used
to form expected values. The independent block is saved separately and does
not replace or modify the matrix used by the modal solver.

| Mesh | Mechanical columns | Numerical checks | Relative error of complete block |
|---|---:|---:|---:|
| Cosine40 | 504 | 552 | 1.869e−12 |
| Cosine80 | 984 | 1,032 | 1.888e−12 |

Maximum individual column error is **6.402e−12 relative** for pose columns
and **2.927e−15** for internal-wrench/reaction columns. Their predeclared
gates are **1e−8** and **1e−10**, respectively. These gates do not replace or
relax the native-reference or spatial-convergence gates.

Four physical directions per mesh exercise geometry, internal wrenches and
the real/imaginary parts of the higher-frequency mode. Centered residual
differences at **1e−4, 1e−5 and 1e−6** give **24 directional actions** with
maximum relative error **4.782e−9**, below the existing 5e−5 action gate.
The physical probes preserve the wall root; all algebraic columns are still
retained in the matrix comparison.

The aerodynamic scope matters: the base circulation is effectively zero,
profile drag and moment inputs are zero, and the local/frame rates are zero.
Thus pose derivatives of aerodynamic wrenches vanish for this selected
block. **Circulation and local velocity/rate columns, and flow-equation
rows, are outside this audit.** It is not a validation of general loaded,
curved or rotating configurations, nor of the entire A matrix.

## Interpretation and next work

Together with the [independent inertia audit](isae-ae4-real-inertia96-20261113.md),
this provides independent equation checks for the selected structural block
and all local-acceleration columns. The declared endpoint averaging and
unloaded structural-length interpretation are retained; these checks do not
authenticate the archived ASWING node placement or startup settings.

The [damping discrepancy](isae-ae4-high-mode96-20261113.md) remains:
at 96 m/s the higher pair has **−0.137936/s native**, **−0.095961/s cosine40**,
**+0.023701/s cosine80**, and **+0.053766/s cosine160**. Fine-grid native
real-component error is **138.98%**, and spatial damping convergence still
fails. Passing equation checks do not turn these into native matches.

Next independently audit the **aerodynamic coupling blocks** on this same
state: circulation-induced velocity and forces, solid-wall images, section
flow tangency, and response to local translation/rotation rates. Preserve
the bound-vortex and wake conventions in the authoritative descriptions,
all original coefficients and the full descriptor system. Separate that
implementation check from unresolved historical node/setting ambiguity;
then resume the unrun native sweep points.

Both workers completed and were reaped, using at most **0.863 CPU seconds,
1.058 supervised wall seconds and 95.9 MiB RSS**, with separately bounded
library preload. Limits remain one BLAS thread and **512 MiB address space
/15 CPU seconds /25 wall seconds**. Production hashes are unchanged.
No browser, build, WASM or background solver job ran.

Primary accounting stays **357 passes, 23 paired failures, 16 unmatched,
12 unknown initial values and 792 unrun**. Failed paired errors remain
median **9.017%**, range **5.498–117.182%**. The finer-mesh diagnostic,
overlapping 86/108 sample and separate 9,480-component historical archive
remain distinct. AE-4 and the broader project are incomplete.

- [Prospective plan and source hashes](../../artifacts/isae/ae4-elastic96-20261113/plan.json)
- [Assessment and all checks](../../artifacts/isae/ae4-elastic96-20261113/assessment.json)
- [Independent equation implementation](../../artifacts/isae/ae4-elastic96-20261113/run.py)
