# SA-14 zero-angle geometry checkpoint

SA-14 stays **281/360 at 5%**. Four small, independent diagnostics close out
this investigation before the user-requested switch to ST-1. No production
equation, original input, primary mesh or comparison denominator was changed.

The original finite-body model at zero incidence gives CL = −0.0090568662
on the nominal-64 grid, versus archived ASWING −0.000362896. The model's
nominally constant-radius middle is not constant after cubic interpolation:
the radius reaches 0.1725123 m versus the tabulated 0.1613532 m, a 6.92% bulge.

| Isolated diagnostic | Computed CL | Absolute CL error |
|---|---:|---:|
| Original nominal-64 baseline | −0.0090568662 | 0.0086939702 |
| Drela SEGSPL endpoint policy | −0.0090563052 | 0.0086934092 |
| Body nodes inferred from local export | −0.0090568660 | 0.0086939700 |
| Body and wing nodes inferred from local export | −0.0089467889 | 0.0085838929 |
| Deliberately flat cylindrical middle | −0.0007319602 | 0.0003690642 |

The last diagnostic repeats the two plateau-end radius stations to separate
the cubic segments, retaining every original numeric value. This explicitly
changes the radius derivatives and geometry; it is not a parser correction or
an authenticated historical input. It reduces the zero-angle discrepancy by
95.75%, but still does not match the archive within 5%. It is evidence that
radius interpolation and the resulting volume-induced flow deserve further
investigation, not grounds for adopting this modified model as the reference.

The original local-load export at 4.7° supports 18 body intervals (six before
the joint, twelve after), matching all 20 printed station rows including the
duplicated joint and terminal row. A 78-interval modified-cosine wing matches
all 78 nonroot printed stations. The two root rows differ by 0.218 micrometres
from zero. These nodes are inferred from a different-angle export; the original
polar node arrays are still unavailable. They scarcely change the lift offset.

All four fresh solves converged and passed independent force/moment closure.
Solve/check time after imports was 0.10–0.13 s; peak resident memory stayed
below 234 MiB. Each process used one BLAS thread with 512 MiB address-space,
15 s CPU and 25 s wall limits. An initial report-serialization failure is
retained separately; it produced a valid physical result but no accepted
diagnostic report. Its serializer was corrected before the four final runs.

[Reproduction script](../../scripts/diagnose_sa14_offset.py) and
[retained evidence](../../artifacts/isae/sa14-low-angle-20261109/) include the
source hashes, modified input, full physical output and coordinate checks.
The source interpretation follows the [authoritative reference index](aswing-authoritative-references.md),
ISAE Part I §6.3 (p. 43), the original radius table, and the manual's beam
spline rule (repeated stations separate spline segments). This checkpoint
adds no native comparison passes. High-angle and local-load issues remain open.
